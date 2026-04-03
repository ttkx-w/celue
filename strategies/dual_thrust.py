"""
Dual Thrust 突破策略
适用于贵金属趋势行情
"""

import numpy as np
from typing import Optional, Tuple
from dataclasses import dataclass


@dataclass
class DualThrustConfig:
    k1: float = 0.4      # 上通道系数
    k2: float = 0.6      # 下通道系数
    n: int = 4           # 回溯周期
    atr_multiplier: float = 2.0  # 止损ATR倍数


class DualThrustStrategy:
    """
    Dual Thrust 突破策略
    
    核心逻辑:
    1. 计算过去N根K线的最高价HH、最低价LL
    2. 计算开盘价OC = 当日开盘价
    3. Range = HH - LL
    4. 上轨 = OC + K1 * Range
    5. 下轨 = OC - K2 * Range
    6. 价格突破上轨做多，突破下轨做空
    """
    
    def __init__(self, config: DualThrustConfig):
        self.config = config
        self.position = None  # 当前持仓状态
        self.entry_price = None
        self.stop_loss = None
        
    def calculate_range(self, highs: np.ndarray, lows: np.ndarray) -> float:
        """计算价格区间"""
        hh = np.max(highs[-self.config.n:])
        ll = np.min(lows[-self.config.n:])
        return hh - ll
    
    def calculate_levels(self, open_price: float, range: float) -> Tuple[float, float]:
        """计算突破水平"""
        upper = open_price + self.config.k1 * range
        lower = open_price - self.config.k2 * range
        return upper, lower
    
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
        return np.mean(tr_list[-period:])
    
    def generate_signal(self, 
                        current_price: float,
                        open_price: float,
                        highs: np.ndarray,
                        lows: np.ndarray,
                        closes: np.ndarray) -> Optional[str]:
        """
        生成交易信号
        
        Returns:
            'long': 做多信号
            'short': 做空信号
            'close_long': 平多信号
            'close_short': 平空信号
            None: 无信号
        """
        # 计算突破水平
        range = self.calculate_range(highs, lows)
        upper, lower = self.calculate_levels(open_price, range)
        
        # 计算ATR止损
        atr = self.calculate_atr(highs, lows, closes)
        
        # 无持仓时检查突破信号
        if self.position is None:
            if current_price > upper:
                # 突破上轨，做多
                self.position = 'long'
                self.entry_price = current_price
                self.stop_loss = current_price - self.config.atr_multiplier * atr
                return 'long'
            elif current_price < lower:
                # 突破下轨，做空
                self.position = 'short'
                self.entry_price = current_price
                self.stop_loss = current_price + self.config.atr_multiplier * atr
                return 'short'
        
        # 有持仓时检查止损/止盈
        elif self.position == 'long':
            # 追踪止损更新
            new_stop = current_price - self.config.atr_multiplier * atr
            if new_stop > self.stop_loss:
                self.stop_loss = new_stop
            
            # 触发止损
            if current_price < self.stop_loss:
                self.position = None
                self.entry_price = None
                self.stop_loss = None
                return 'close_long'
                
        elif self.position == 'short':
            # 追踪止损更新 (做空方向相反)
            new_stop = current_price + self.config.atr_multiplier * atr
            if new_stop < self.stop_loss:
                self.stop_loss = new_stop
            
            # 触发止损
            if current_price > self.stop_loss:
                self.position = None
                self.entry_price = None
                self.stop_loss = None
                return 'close_short'
        
        return None
    
    def reset(self):
        """重置策略状态（日内平仓后调用）"""
        self.position = None
        self.entry_price = None
        self.stop_loss = None
    
    def get_state(self) -> dict:
        """获取当前策略状态"""
        return {
            'position': self.position,
            'entry_price': self.entry_price,
            'stop_loss': self.stop_loss,
            'upper_level': None,  # 需要传入数据计算
            'lower_level': None,
        }


# 使用示例
if __name__ == '__main__':
    config = DualThrustConfig(k1=0.4, k2=0.6, n=4)
    strategy = DualThrustStrategy(config)
    
    # 模拟数据测试
    highs = np.array([450, 452, 455, 458, 460])
    lows = np.array([445, 447, 450, 452, 455])
    closes = np.array([448, 450, 453, 456, 458])
    open_price = 450
    current_price = 461
    
    signal = strategy.generate_signal(current_price, open_price, highs, lows, closes)
    print(f"信号: {signal}")
    print(f"状态: {strategy.get_state()}")