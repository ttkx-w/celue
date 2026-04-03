"""
MT4 贵金属量化交易系统
整合策略 + MT4 桥接 + 实时交易
"""

import time
import numpy as np
from typing import Optional
from datetime import datetime

from mt4_strategy import MT4Bridge, MT4Config
from strategies.dual_thrust import DualThrustStrategy, DualThrustConfig
from strategies.mean_revert import MeanRevertStrategy, MeanRevertConfig
from risk.position import PositionManager, PositionConfig, CONTRACT_PARAMS


class MT4TradingSystem:
    """
    MT4 贵金属量化交易系统
    
    架构:
    MT4 EA → ZeroMQ → Python 策略 → ZeroMQ → MT4 执行
    """
    
    def __init__(self):
        # MT4 桥接器
        self.bridge = MT4Bridge(MT4Config(
            pub_host="tcp://localhost:5555",
            rep_host="tcp://localhost:5556",
            symbols=["XAUUSD", "XAGUSD"]
        ))
        
        # 策略配置 (调整为 MT4 外汇参数)
        # Dual Thrust - 黄金
        self.gold_strategy = DualThrustStrategy(DualThrustConfig(
            k1=0.3,          # 降低突破系数 (外汇波动更大)
            k2=0.4,
            n=4,
            atr_multiplier=1.5  # 外汇止损更紧
        ))
        
        # 均值回归 - 白银 (波动更大)
        self.silver_strategy = MeanRevertStrategy(MeanRevertConfig(
            bollinger_period=20,
            bollinger_std=2.5,   # 扩大标准差
            rsi_period=14,
            rsi_overbought=75,   # 调整阈值
            rsi_oversold=25,
            atr_multiplier=1.2
        ))
        
        # 仓位管理
        self.position_manager = PositionManager(
            PositionConfig(
                max_risk_per_trade=0.02,
                max_position_pct=0.20,
                max_total_position=0.40,
                min_lot=0.01       # MT4 最小手数
            ),
            total_capital=10000   # 模拟账户金额
        )
        
        # MT4 合约参数 (外汇)
        self.mt4_params = {
            'XAUUSD': {
                'unit': 100,          # 1手 = 100盎司
                'point': 0.01,        # 最小变动
                'pip_value': 10,      # 1 pip = $10
            },
            'XAGUSD': {
                'unit': 5000,         # 1手 = 5000盎司
                'point': 0.001,
                'pip_value': 50,
            }
        }
        
        # 状态
        self.running = False
        self.daily_loss = 0.0
        self.trade_count = 0
    
    def start(self):
        """启动交易系统"""
        print("=" * 50)
        print("MT4 贵金属量化交易系统启动")
        print("=" * 50)
        
        self.bridge.start()
        self.running = True
        
        # 等待数据
        print("等待 MT4 行情数据...")
        time.sleep(5)
        
        # 开始交易循环
        self._run_loop()
    
    def stop(self):
        """停止系统"""
        self.running = False
        self.bridge.stop()
        print("交易系统已停止")
    
    def _run_loop(self):
        """主交易循环"""
        print("\n开始实时交易...")
        
        while self.running:
            try:
                # 处理每个品种
                self._process_symbol("XAUUSD", self.gold_strategy)
                self._process_symbol("XAGUSD", self.silver_strategy)
                
                # 检查强制平仓时间
                self._check_close_time()
                
                time.sleep(1)  # 1秒循环
                
            except KeyboardInterrupt:
                self.stop()
                break
            except Exception as e:
                print(f"错误: {e}")
                time.sleep(5)
    
    def _process_symbol(self, symbol: str, strategy):
        """处理单个品种"""
        # 获取数据
        bars = self.bridge.get_bars(symbol, count=30)
        if bars is None or len(bars['closes']) < 20:
            return
        
        price = self.bridge.get_current_price(symbol)
        if not price:
            return
        
        # 计算策略信号
        closes = bars['closes']
        highs = bars['highs']
        lows = bars['lows']
        
        # Dual Thrust 需要开盘价
        open_price = closes[-1] if symbol == "XAUUSD" else closes[-1]
        
        # 生成信号
        signal = strategy.generate_signal(
            current_price=price['bid'],
            open_price=open_price,
            highs=highs,
            lows=lows,
            closes=closes
        )
        
        if signal:
            self._execute_signal(symbol, signal, price)
    
    def _execute_signal(self, symbol: str, signal: str, price: dict):
        """执行交易信号"""
        # 计算仓位
        bars = self.bridge.get_bars(symbol, count=30)
        atr = self._calculate_atr(bars['highs'], bars['lows'], bars['closes'])
        
        params = self.mt4_params[symbol]
        
        # 计算手数
        lots = self._calculate_lots(symbol, atr, price)
        
        if lots < 0.01:
            print(f"[{symbol}] 仓位太小，跳过")
            return
        
        # 计算止损
        stop_loss = self._calculate_stop_loss(signal, price, atr, params['point'])
        
        # 执行交易
        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] 信号: {signal}")
        print(f"品种: {symbol}, 手数: {lots}")
        print(f"止损: {stop_loss}")
        
        result = None
        
        if signal == 'long':
            result = self.bridge.send_command(
                'BUY', symbol, lots,
                stop_loss=stop_loss
            )
        elif signal == 'short':
            result = self.bridge.send_command(
                'SELL', symbol, lots,
                stop_loss=stop_loss
            )
        elif signal == 'close_long':
            result = self.bridge.send_command('CLOSE_BUY', symbol, lots)
        elif signal == 'close_short':
            result = self.bridge.send_command('CLOSE_SELL', symbol, lots)
        
        if result and result['success']:
            self.trade_count += 1
    
    def _calculate_lots(self, symbol: str, atr: float, price: dict) -> float:
        """计算开仓手数"""
        capital = 10000  # 模拟账户
        risk_pct = 0.02  # 2% 风险
        atr_mult = 1.5
        
        # 风险金额
        risk_amount = capital * risk_pct
        
        # 止损距离 (点数)
        stop_points = atr * atr_mult
        
        # 点值
        pip_value = self.mt4_params[symbol]['pip_value']
        
        # 手数 = 风险金额 / (止损点数 * 点值)
        lots = risk_amount / (stop_points * pip_value)
        
        # MT4 最小手数 0.01
        lots = max(0.01, round(lots, 2))
        
        # 最大手数限制 (模拟账户保守)
        lots = min(lots, 0.5)
        
        return lots
    
    def _calculate_stop_loss(self, signal: str, price: dict, 
                             atr: float, point: float) -> float:
        """计算止损价格"""
        atr_mult = 1.5
        stop_distance = atr * atr_mult
        
        if signal == 'long':
            return price['ask'] - stop_distance
        elif signal == 'short':
            return price['bid'] + stop_distance
        
        return 0
    
    def _calculate_atr(self, highs: np.ndarray, lows: np.ndarray, 
                       closes: np.ndarray, period: int = 14) -> float:
        """计算 ATR"""
        tr_list = []
        for i in range(1, len(closes)):
            tr = max(
                highs[i] - lows[i],
                abs(highs[i] - closes[i-1]),
                abs(lows[i] - closes[i-1])
            )
            tr_list.append(tr)
        
        return np.mean(tr_list[-period:]) if len(tr_list) >= period else tr_list[-1]
    
    def _check_close_time(self):
        """检查强制平仓时间"""
        # 外汇24小时交易，不需要强制平仓
        # 但可以设置休息时段
        pass


if __name__ == '__main__':
    system = MT4TradingSystem()
    system.start()