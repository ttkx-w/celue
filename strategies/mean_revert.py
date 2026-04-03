"""
均值回归策略
适用于贵金属震荡行情
"""

import numpy as np
from typing import Optional, Tuple
from dataclasses import dataclass


@dataclass
class MeanRevertConfig:
    bollinger_period: int = 20
    bollinger_std: float = 2.0
    rsi_period: int = 14
    rsi_overbought: float = 70
    rsi_oversold: float = 30
    atr_multiplier: float = 1.5


class MeanRevertStrategy:
    """
    均值回归策略
    
    核心逻辑:
    1. 布林带: 价格触及下轨(超卖)做多，触及上轨(超买)做空
    2. RSI确认: RSI<30确认做多，RSI>70确认做空
    3. 中轨作为均值回归目标
    """
    
    def __init__(self, config: MeanRevertConfig):
        self.config = config
        self.position = None
        self.entry_price = None
        self.stop_loss = None
        
    def calculate_bollinger(self, closes: np.ndarray) -> Tuple[float, float, float]:
        """
        计算布林带
        Returns: (中轨, 上轨, 下轨)
        """
        period = self.config.bollinger_period
        std_multiplier = self.config.bollinger_std
        
        # 中轨 = SMA
        middle = np.mean(closes[-period:])
        
        # 标准差
        std = np.std(closes[-period:])
        
        # 上轨 = 中轨 + N * 标准差
        upper = middle + std_multiplier * std
        
        # 下轨 = 中轨 - N * 标准差
        lower = middle - std_multiplier * std
        
        return middle, upper, lower
    
    def calculate_rsi(self, closes: np.ndarray) -> float:
        """计算RSI"""
        period = self.config.rsi_period
        
        # 价格变化
        deltas = np.diff(closes[-period-1:])
        
        # 上涨和下跌
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        
        # 平均上涨和下跌
        avg_gain = np.mean(gains)
        avg_loss = np.mean(losses)
        
        if avg_loss == 0:
            return 100
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        return rsi
    
    def calculate_atr(self, highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, period: int = 14) -> float:
        """计算ATR"""
        tr_list = []
        for i in range(1, len(closes)):
            tr = max(
                highs[i] - lows[i],
                abs(highs[i] - closes[i-1]),
                abs(lows[i] - closes[i-1])
            )
            tr_list.append(tr)
        return np.mean(tr_list[-period:]) if len(tr_list) >= period else tr_list[-1]
    
    def generate_signal(self,
                        current_price: float,
                        highs: np.ndarray,
                        lows: np.ndarray,
                        closes: np.ndarray) -> Optional[str]:
        """
        生成交易信号
        
        逻辑:
        - 价格触及下轨 + RSI<30 → 做多
        - 价格触及上轨 + RSI>70 → 做空
        - 价格回归中轨 → 平仓
        """
        # 计算指标
        middle, upper, lower = self.calculate_bollinger(closes)
        rsi = self.calculate_rsi(closes)
        atr = self.calculate_atr(highs, lows, closes)
        
        # 无持仓时检查入场信号
        if self.position is None:
            # 触及下轨 + RSI超卖 → 做多
            if current_price <= lower and rsi < self.config.rsi_oversold:
                self.position = 'long'
                self.entry_price = current_price
                self.stop_loss = current_price - self.config.atr_multiplier * atr
                return 'long'
            
            # 触及上轨 + RSI超买 → 做空
            elif current_price >= upper and rsi > self.config.rsi_overbought:
                self.position = 'short'
                self.entry_price = current_price
                self.stop_loss = current_price + self.config.atr_multiplier * atr
                return 'short'
        
        # 有持仓时检查平仓信号
        elif self.position == 'long':
            # 止损检查
            if current_price < self.stop_loss:
                self.position = None
                self.entry_price = None
                self.stop_loss = None
                return 'close_long'
            
            # 回归中轨止盈
            if current_price >= middle:
                self.position = None
                self.entry_price = None
                self.stop_loss = None
                return 'close_long'
                
        elif self.position == 'short':
            # 止损检查
            if current_price > self.stop_loss:
                self.position = None
                self.entry_price = None
                self.stop_loss = None
                return 'close_short'
            
            # 回归中轨止盈
            if current_price <= middle:
                self.position = None
                self.entry_price = None
                self.stop_loss = None
                return 'close_short'
        
        return None
    
    def reset(self):
        """重置策略状态"""
        self.position = None
        self.entry_price = None
        self.stop_loss = None
    
    def get_state(self) -> dict:
        """获取当前策略状态"""
        return {
            'position': self.position,
            'entry_price': self.entry_price,
            'stop_loss': self.stop_loss,
            'rsi': None,  # 需要传入数据计算
            'bollinger': None,
        }


# 使用示例
if __name__ == '__main__':
    config = MeanRevertConfig()
    strategy = MeanRevertStrategy(config)
    
    # 模拟超卖数据
    closes = np.array([460, 458, 455, 452, 450, 448, 446, 444, 442, 440,
                       438, 436, 434, 432, 430, 428, 426, 424, 422, 420])
    highs = closes + 5
    lows = closes - 5
    current_price = 415  # 假设触及下轨
    
    signal = strategy.generate_signal(current_price, highs, lows, closes)
    print(f"信号: {signal}")
    print(f"RSI: {strategy.calculate_rsi(closes)}")
    print(f"布林带: {strategy.calculate_bollinger(closes)}")