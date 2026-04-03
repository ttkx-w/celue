"""
仓位管理模块
基于波动率和风险百分比动态计算仓位
"""

import numpy as np
from dataclasses import dataclass


@dataclass
class PositionConfig:
    max_risk_per_trade: float = 0.02  # 单笔风险 2%
    max_position_pct: float = 0.20    # 单品种最大仓位 20%
    max_total_position: float = 0.40  # 总仓位上限 40%
    min_lot: int = 1                  # 最小手数


class PositionManager:
    """
    仓位管理器
    
    核心原则:
    1. 单笔风险不超过总资金的 2%
    2. 止损距离 = ATR * 倍数
    3. 仓位 = (风险金额) / (止损距离 * 合约单位)
    """
    
    def __init__(self, config: PositionConfig, total_capital: float):
        self.config = config
        self.total_capital = total_capital
        self.positions = {}  # 当前持仓 {symbol: lots}
        
    def calculate_lot_size(self,
                           atr: float,
                           atr_multiplier: float,
                           contract_unit: float,
                           price: float) -> int:
        """
        计算开仓手数
        
        Args:
            atr: ATR值
            atr_multiplier: ATR止损倍数
            contract_unit: 合约单位 (黄金1000克/手, 白银15千克/手)
            price: 当前价格
            
        Returns:
            开仓手数
        """
        # 风险金额 = 总资金 * 单笔风险比例
        risk_amount = self.total_capital * self.config.max_risk_per_trade
        
        # 止损距离 = ATR * 倍数
        stop_distance = atr * atr_multiplier
        
        # 单手止损金额 = 止损距离 * 合约单位
        loss_per_lot = stop_distance * contract_unit
        
        # 计算手数 = 风险金额 / 单手止损金额
        lots = risk_amount / loss_per_lot
        
        # 取整 (向下取整到最小手数)
        lots = int(lots)
        lots = max(lots, self.config.min_lot)
        
        # 检查仓位上限
        position_value = lots * contract_unit * price
        max_position_value = self.total_capital * self.config.max_position_pct
        
        if position_value > max_position_value:
            lots = int(max_position_value / (contract_unit * price))
            lots = max(lots, self.config.min_lot)
        
        return lots
    
    def check_total_position_limit(self, new_position_value: float) -> bool:
        """检查总仓位是否超限"""
        current_total = sum(self.positions.values())  # 简化计算
        new_total = current_total + new_position_value
        limit = self.total_capital * self.config.max_total_position
        return new_total <= limit
    
    def update_position(self, symbol: str, lots: int, action: str):
        """更新持仓记录"""
        if action == 'open':
            self.positions[symbol] = self.positions.get(symbol, 0) + lots
        elif action == 'close':
            current = self.positions.get(symbol, 0)
            self.positions[symbol] = max(0, current - lots)
    
    def get_position(self, symbol: str) -> int:
        """获取当前持仓"""
        return self.positions.get(symbol, 0)
    
    def get_total_position_pct(self) -> float:
        """获取总仓位比例"""
        total_value = sum(self.positions.values())  # 简化
        return total_value / self.total_capital if self.total_capital > 0 else 0


# 黄金白银合约参数
CONTRACT_PARAMS = {
    'AU': {
        'unit': 1000,      # 克/手
        'margin_rate': 0.08,  # 保证金比例 8%
        'min_price_change': 0.01,  # 最小变动价位
    },
    'AG': {
        'unit': 15,        # 千克/手
        'margin_rate': 0.08,
        'min_price_change': 1,
    }
}


def calculate_required_margin(symbol: str, lots: int, price: float) -> float:
    """计算所需保证金"""
    params = CONTRACT_PARAMS.get(symbol)
    if not params:
        return 0
    
    # 保证金 = 手数 * 合约单位 * 价格 * 保证金比例
    margin = lots * params['unit'] * price * params['margin_rate']
    return margin


# 使用示例
if __name__ == '__main__':
    config = PositionConfig()
    manager = PositionManager(config, total_capital=100000)
    
    # 黄金: ATR=5, 价格=450, 止损2倍ATR
    atr = 5.0
    price = 450.0
    lots = manager.calculate_lot_size(atr, 2.0, 1000, price)
    
    print(f"黄金建议开仓: {lots}手")
    print(f"所需保证金: {calculate_required_margin('AU', lots, price):.2f}元")
    print(f"止损距离: {atr * 2}元/克")
    print(f"最大亏损: {lots * 1000 * atr * 2:.2f}元")