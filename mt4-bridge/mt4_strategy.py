"""
MT4 ZeroMQ Bridge - Python 策略端
连接 MT4 接收行情，发送交易指令
"""

import zmq
import json
import threading
import time
import numpy as np
from datetime import datetime
from typing import Optional, Dict, List
from dataclasses import dataclass


@dataclass
class MT4Config:
    pub_host: str = "tcp://localhost:5555"  # MT4 行情推送
    rep_host: str = "tcp://localhost:5556"  # MT4 指令接收
    symbols: List[str] = ["XAUUSD", "XAGUSD"]
    bar_period: int = 5  # 5分钟


class MT4Bridge:
    """
    MT4 ZeroMQ 桥接器
    
    功能:
    1. 接收 MT4 推送的实时行情
    2. 发送交易指令到 MT4
    3. 管理订单状态
    """
    
    def __init__(self, config: MT4Config):
        self.config = config
        self.context = zmq.Context()
        
        # Subscriber Socket - 接收行情
        self.sub_socket = self.context.socket(zmq.SUB)
        self.sub_socket.connect(config.pub_host)
        self.sub_socket.setsockopt_string(zmq.SUBSCRIBE, "")
        
        # Request Socket - 发送指令
        self.req_socket = self.context.socket(zmq.REQ)
        self.req_socket.connect(config.rep_host)
        
        # 数据缓存
        self.bars: Dict[str, List[dict]] = {s: [] for s in config.symbols}
        self.current_prices: Dict[str, dict] = {}
        
        # 状态
        self.running = False
        self.position: Dict[str, Optional[str]] = {s: None for s in config.symbols}
        
        print(f"MT4 Bridge 初始化完成")
        print(f"行情端口: {config.pub_host}")
        print(f"指令端口: {config.rep_host}")
    
    def start(self):
        """启动桥接器"""
        self.running = True
        
        # 启动行情接收线程
        thread = threading.Thread(target=self._receive_prices, daemon=True)
        thread.start()
        
        print("MT4 Bridge 已启动，等待行情...")
        
        # 等待数据
        time.sleep(2)
    
    def stop(self):
        """停止桥接器"""
        self.running = False
        self.sub_socket.close()
        self.req_socket.close()
        self.context.term()
        print("MT4 Bridge 已停止")
    
    def _receive_prices(self):
        """接收行情数据"""
        while self.running:
            try:
                msg = self.sub_socket.recv_string(flags=zmq.NOBLOCK)
                self._process_bar(msg)
            except zmq.Again:
                time.sleep(0.01)
    
    def _process_bar(self, msg: str):
        """处理行情数据"""
        # 格式: SYMBOL|TIME|OPEN|HIGH|LOW|BID|ASK|CLOSE|VOLUME
        parts = msg.split('|')
        if len(parts) < 8:
            return
        
        symbol = parts[0]
        bar_time = parts[1]
        open_p = float(parts[2])
        high_p = float(parts[3])
        low_p = float(parts[4])
        bid = float(parts[5])
        ask = float(parts[6])
        close = float(parts[7])
        volume = int(parts[8]) if len(parts) >= 9 else 0
        
        # 更新当前价格
        self.current_prices[symbol] = {
            'bid': bid,
            'ask': ask,
            'time': bar_time
        }
        
        # 添加到K线缓存
        bar = {
            'time': bar_time,
            'open': open_p,
            'high': high_p,
            'low': low_p,
            'close': close,
            'volume': volume
        }
        
        self.bars[symbol].append(bar)
        
        # 保持最近100根K线
        if len(self.bars[symbol]) > 100:
            self.bars[symbol] = self.bars[symbol][-100:]
        
        print(f"[{symbol}] {bar_time} O:{open_p} H:{high_p} L:{low_p} C:{close}")
    
    def send_command(self, action: str, symbol: str, lots: float, 
                     stop_loss: float = 0, take_profit: float = 0) -> dict:
        """
        发送交易指令
        
        action: BUY, SELL, CLOSE_BUY, CLOSE_SELL
        """
        cmd = f"{action}|{symbol}|{lots}|0|{stop_loss}|{take_profit}"
        
        try:
            self.req_socket.send_string(cmd)
            response = self.req_socket.recv_string(timeout=5000)
            
            # 解析响应
            parts = response.split('|')
            if parts[0] == "OK":
                print(f"✅ 交易成功: {action} {symbol} {lots}手")
                if action == "BUY":
                    self.position[symbol] = "long"
                elif action == "SELL":
                    self.position[symbol] = "short"
                elif action.startswith("CLOSE"):
                    self.position[symbol] = None
                return {'success': True, 'response': response}
            else:
                print(f"❌ 交易失败: {response}")
                return {'success': False, 'error': response}
                
        except zmq.Again:
            print("❌ MT4 连接超时")
            return {'success': False, 'error': 'timeout'}
    
    def get_bars(self, symbol: str, count: int = 20) -> np.ndarray:
        """获取K线数据"""
        bars = self.bars[symbol][-count:]
        if len(bars) < count:
            return None
        
        # 返回 numpy 数组
        closes = np.array([b['close'] for b in bars])
        highs = np.array([b['high'] for b in bars])
        lows = np.array([b['low'] for b in bars])
        
        return {'closes': closes, 'highs': highs, 'lows': lows}
    
    def get_current_price(self, symbol: str) -> Optional[dict]:
        """获取当前价格"""
        return self.current_prices.get(symbol)


# 使用示例
if __name__ == '__main__':
    config = MT4Config(
        pub_host="tcp://localhost:5555",
        rep_host="tcp://localhost:5556"
    )
    
    bridge = MT4Bridge(config)
    bridge.start()
    
    # 测试运行
    try:
        while True:
            price = bridge.get_current_price("XAUUSD")
            if price:
                print(f"XAUUSD 当前价格: Bid={price['bid']}, Ask={price['ask']}")
            time.sleep(1)
    except KeyboardInterrupt:
        bridge.stop()