#!/usr/bin/env python3
"""
MT4 File Bridge - 策略端
通过文件系统与 MT4 EA 通信
"""

import time
import numpy as np
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List
from dataclasses import dataclass


@dataclass
class StrategyConfig:
    symbol: str = "USDJPY"
    lots: float = 0.01
    risk_percent: float = 1.0
    # Dual Thrust 参数
    range_period: int = 10
    k1: float = 0.4  # 开仓系数
    k2: float = 0.4  # 平仓系数
    # 均值回归参数
    ma_period: int = 20
    deviation_threshold: float = 2.0


class MT4FileBridge:
    """
    MT4 文件桥接器
    
    通信协议:
    - tick.txt: MT4 → Python (行情数据)
    - cmd.txt: Python → MT4 (交易指令)
    - result.txt: MT4 → Python (交易结果)
    """
    
    def __init__(self, mt4_data_path: str):
        self.data_path = Path(mt4_data_path)
        self.tick_file = self.data_path / "tick.txt"
        self.cmd_file = self.data_path / "cmd.txt"
        self.result_file = self.data_path / "result.txt"
        
        # 确保目录存在
        self.data_path.mkdir(parents=True, exist_ok=True)
        
        # 数据缓存
        self.bars: List[dict] = []
        self.current_price: Optional[dict] = None
        self.position: Optional[str] = None  # 'long' or 'short'
        
        print(f"数据目录: {self.data_path}")
    
    def read_tick(self) -> Optional[dict]:
        """读取行情数据"""
        if not self.tick_file.exists():
            return None
        
        try:
            content = self.tick_file.read_text(encoding='utf-8').strip()
            parts = content.split(',')
            
            return {
                'symbol': parts[0],
                'time': parts[1],
                'open': float(parts[2]),
                'high': float(parts[3]),
                'low': float(parts[4]),
                'bid': float(parts[5]),
                'ask': float(parts[6]),
                'volume': int(parts[7])
            }
        except Exception as e:
            print(f"读取tick错误: {e}")
            return None
    
    def send_command(self, action: str, symbol: str, lots: float,
                     sl: float = 0, tp: float = 0) -> Optional[str]:
        """
        发送交易指令
        
        action: BUY, SELL, CLOSE
        """
        cmd = f"{action},{symbol},{lots},{sl},{tp}"
        self.cmd_file.write_text(cmd, encoding='utf-8')
        print(f"发送指令: {cmd}")
        
        # 等待结果
        time.sleep(0.5)
        
        if self.result_file.exists():
            result = self.result_file.read_text(encoding='utf-8')
            self.result_file.unlink()
            
            if "OK" in result:
                if action == "BUY":
                    self.position = 'long'
                elif action == "SELL":
                    self.position = 'short'
                elif action == "CLOSE":
                    self.position = None
            
            return result
        
        return None
    
    def update_bars(self, tick: dict):
        """更新K线缓存"""
        bar = {
            'time': tick['time'],
            'open': tick['open'],
            'high': tick['high'],
            'low': tick['low'],
            'close': tick['bid'],
            'volume': tick['volume']
        }
        
        self.bars.append(bar)
        
        # 保持最近100根
        if len(self.bars) > 100:
            self.bars = self.bars[-100:]
        
        self.current_price = tick


class DualThrustStrategy:
    """
    Dual Thrust 策略
    
    短线突破策略，适合5分钟周期
    """
    
    def __init__(self, config: StrategyConfig, bridge: MT4FileBridge):
        self.config = config
        self.bridge = bridge
        
        # 计算范围
        self.upper_range = 0
        self.lower_range = 0
        self.today_high = 0
        self.today_low = 0
    
    def calculate_range(self):
        """计算今日突破范围"""
        if len(self.bridge.bars) < self.config.range_period:
            return
        
        # 取前N根K线的高点和低点
        bars = self.bridge.bars[-self.config.range_period:]
        highs = [b['high'] for b in bars]
        lows = [b['low'] for b in bars]
        
        hh = max(highs)
        ll = min(lows)
        hc = bars[-1]['close']
        lc = bars[0]['open']
        
        range_val = max(hh - lc, hc - ll)
        
        self.upper_range = bars[-1]['close'] + self.config.k1 * range_val
        self.lower_range = bars[-1]['close'] - self.config.k2 * range_val
    
    def check_signal(self, tick: dict) -> Optional[str]:
        """
        检查交易信号
        
        返回: BUY, SELL, CLOSE, None
        """
        if len(self.bridge.bars) < self.config.range_period:
            return None
        
        self.calculate_range()
        
        current_price = tick['bid']
        
        # 突破上轨 → 做多
        if current_price > self.upper_range and self.bridge.position != 'long':
            return "BUY"
        
        # 突破下轨 → 做空
        if current_price < self.lower_range and self.bridge.position != 'short':
            return "SELL"
        
        # 多单止盈/止损
        if self.bridge.position == 'long':
            if current_price < self.lower_range:  # 回落突破下轨
                return "CLOSE"
        
        # 空单止盈/止损
        if self.bridge.position == 'short':
            if current_price > self.upper_range:  # 反弹突破上轨
                return "CLOSE"
        
        return None


class MeanReversionStrategy:
    """
    均值回归策略
    
    价格偏离均值过大时反向入场
    """
    
    def __init__(self, config: StrategyConfig, bridge: MT4FileBridge):
        self.config = config
        self.bridge = bridge
    
    def calculate_ma(self) -> float:
        """计算均线"""
        if len(self.bridge.bars) < self.config.ma_period:
            return 0
        
        closes = [b['close'] for b in self.bridge.bars[-self.config.ma_period:]]
        return np.mean(closes)
    
    def calculate_std(self) -> float:
        """计算标准差"""
        if len(self.bridge.bars) < self.config.ma_period:
            return 0
        
        closes = [b['close'] for b in self.bridge.bars[-self.config.ma_period:]]
        return np.std(closes)
    
    def check_signal(self, tick: dict) -> Optional[str]:
        """检查交易信号"""
        if len(self.bridge.bars) < self.config.ma_period:
            return None
        
        ma = self.calculate_ma()
        std = self.calculate_std()
        
        if std == 0:
            return None
        
        current_price = tick['bid']
        deviation = (current_price - ma) / std
        
        # 偏离过大 → 反向入场
        if deviation > self.config.deviation_threshold and self.bridge.position != 'short':
            return "SELL"  # 价格过高，做空
        
        if deviation < -self.config.deviation_threshold and self.bridge.position != 'long':
            return "BUY"  # 价格过低，做多
        
        # 回归均值 → 平仓
        if abs(deviation) < 0.5 and self.bridge.position:
            return "CLOSE"
        
        return None


def main():
    """策略运行主函数"""
    
    # 配置数据路径
    MT4_DATA_PATH = "C:/Users/吴雪松/AppData/Roaming/MetaQuotes/Terminal/05F402213219D64DFADE08EEA591FF8D/MQL4/Files/bridge"
    
    # 初始化桥接
    bridge = MT4FileBridge(MT4_DATA_PATH)
    
    # 初始化策略
    config = StrategyConfig(symbol="USDJPY", lots=0.01)
    
    # 使用 Dual Thrust 策略
    strategy = DualThrustStrategy(config, bridge)
    
    # 也可以使用均值回归策略
    # strategy = MeanReversionStrategy(config, bridge)
    
    print("=" * 60)
    print("MT4 File Bridge 策略启动")
    print(f"品种: {config.symbol}")
    print(f"手数: {config.lots}")
    print("=" * 60)
    
    last_signal = None
    tick_count = 0
    
    while True:
        try:
            # 读取行情
            tick = bridge.read_tick()
            
            if tick:
                # 更新数据
                bridge.update_bars(tick)
                tick_count += 1
                
                # 显示行情
                print(f"[{tick['time']}] {tick['symbol']} "
                      f"Bid={tick['bid']:.5f} Ask={tick['ask']:.5f} "
                      f"Bars={len(bridge.bars)}")
                
                # 检查信号（每10个tick检查一次）
                if tick_count % 10 == 0 and len(bridge.bars) >= config.range_period:
                    signal = strategy.check_signal(tick)
                    
                    if signal and signal != last_signal:
                        print(f"信号: {signal}")
                        
                        if signal in ["BUY", "SELL"]:
                            result = bridge.send_command(
                                signal, config.symbol, config.lots
                            )
                            print(f"结果: {result}")
                        elif signal == "CLOSE":
                            result = bridge.send_command(
                                "CLOSE", config.symbol, config.lots
                            )
                            print(f"结果: {result}")
                        
                        last_signal = signal
            
            # 等待下一个tick
            time.sleep(1)
            
        except KeyboardInterrupt:
            print("\n策略已停止")
            break


if __name__ == "__main__":
    main()