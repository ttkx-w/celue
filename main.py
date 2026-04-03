"""
贵金属短线量化交易系统 - 主程序
"""

import asyncio
import yaml
import logging
from datetime import datetime, time
from pathlib import Path
from typing import Optional

from strategies.dual_thrust import DualThrustStrategy, DualThrustConfig
from strategies.mean_revert import MeanRevertStrategy, MeanRevertConfig
from risk.position import PositionManager, PositionConfig

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)


class TradingSystem:
    """贵金属短线量化交易系统"""
    
    def __init__(self, config_dir: str = './config'):
        self.config_dir = Path(config_dir)
        self.load_config()
        self.init_strategies()
        self.init_risk_manager()
        
        # 状态
        self.is_running = False
        self.daily_loss = 0.0
        self.trade_count = 0
        
    def load_config(self):
        """加载配置文件"""
        # 策略配置
        strategy_path = self.config_dir / 'strategy.yaml'
        with open(strategy_path, 'r') as f:
            self.strategy_config = yaml.safe_load(f)
        
        # 风控配置
        risk_path = self.config_dir / 'risk.yaml'
        with open(risk_path, 'r') as f:
            self.risk_config = yaml.safe_load(f)
        
        logger.info(f"配置加载完成")
    
    def init_strategies(self):
        """初始化策略"""
        # Dual Thrust
        dt_cfg = self.strategy_config['dual_thrust']
        self.dual_thrust = DualThrustStrategy(DualThrustConfig(
            k1=dt_cfg['k1'],
            k2=dt_cfg['k2'],
            n=dt_cfg['n'],
            atr_multiplier=dt_cfg['stop_loss_atr']
        ))
        
        # 均值回归
        mr_cfg = self.strategy_config['mean_revert']
        self.mean_revert = MeanRevertStrategy(MeanRevertConfig(
            bollinger_period=mr_cfg['bollinger']['period'],
            bollinger_std=mr_cfg['bollinger']['std_dev'],
            rsi_period=mr_cfg['rsi']['period'],
            rsi_overbought=mr_cfg['rsi']['overbought'],
            rsi_oversold=mr_cfg['rsi']['oversold'],
            atr_multiplier=mr_cfg['stop_loss_atr']
        ))
        
        logger.info("策略初始化完成")
    
    def init_risk_manager(self):
        """初始化风控管理"""
        pos_cfg = self.risk_config['position']
        capital = self.risk_config['capital']['initial']
        
        self.position_manager = PositionManager(
            PositionConfig(
                max_risk_per_trade=pos_cfg['max_risk_per_trade'],
                max_position_pct=pos_cfg['max_position_pct'],
                max_total_position=pos_cfg['max_total_position'],
                min_lot=pos_cfg['min_lot']
            ),
            total_capital=capital
        )
        
        logger.info(f"风控初始化完成, 资金: {capital}元")
    
    def get_current_strategy(self) -> str:
        """根据时间选择策略"""
        now = datetime.now().time()
        
        # 日盘 09:00-11:30 → 均值回归
        if time(9, 0) <= now <= time(11, 30):
            return 'mean_revert'
        
        # 下午 13:30-15:00 → 观察模式
        elif time(13, 30) <= now <= time(15, 0):
            return 'observe'
        
        # 夜盘 21:00-02:30 → 突破策略
        elif time(21, 0) <= now or now <= time(2, 30):
            return 'dual_thrust'
        
        else:
            return 'closed'  # 收盘
    
    def check_risk_limits(self) -> bool:
        """检查风控限制"""
        # 日最大亏损
        max_daily_loss = self.risk_config['daily']['max_loss']
        capital = self.risk_config['capital']['initial']
        
        if self.daily_loss >= capital * max_daily_loss:
            logger.warning(f"达到日最大亏损限制: {self.daily_loss}")
            return False
        
        # 日最大交易次数
        max_trades = self.risk_config['daily']['max_trades']
        if self.trade_count >= max_trades:
            logger.warning(f"达到日最大交易次数: {self.trade_count}")
            return False
        
        return True
    
    def should_force_close(self) -> bool:
        """是否需要强制平仓"""
        now = datetime.now().time()
        
        # 日盘平仓时间
        close_time = self.risk_config['daily']['close_time']
        h, m = map(int, close_time.split(':'))
        if time(h, m) <= now <= time(15, 0):
            return True
        
        # 夜盘平仓时间
        night_close = self.risk_config['daily']['night_close_time']
        h, m = map(int, night_close.split(':'))
        if time(h, m) <= now <= time(2, 30):
            return True
        
        return False
    
    async def run_bar(self, bar_data: dict):
        """处理单根K线"""
        symbol = bar_data['symbol']
        strategy_name = self.get_current_strategy()
        
        if strategy_name == 'closed':
            return
        
        if strategy_name == 'observe':
            # 观察模式，不交易
            logger.info(f"[{symbol}] 观察模式")
            return
        
        # 选择策略
        strategy = self.dual_thrust if strategy_name == 'dual_thrust' else self.mean_revert
        
        # 检查风控
        if not self.check_risk_limits():
            logger.warning(f"[{symbol}] 风控限制，跳过交易")
            return
        
        # 强制平仓检查
        if self.should_force_close():
            logger.info(f"[{symbol}] 强制平仓时间")
            strategy.reset()
            # TODO: 发送平仓指令
            return
        
        # 生成信号
        signal = strategy.generate_signal(
            current_price=bar_data['close'],
            open_price=bar_data['open'],
            highs=bar_data['highs'],
            lows=bar_data['lows'],
            closes=bar_data['closes']
        )
        
        if signal:
            logger.info(f"[{symbol}] 信号: {signal}, 价格: {bar_data['close']}")
            # TODO: 计算仓位并发送订单
    
    async def run(self):
        """主循环"""
        logger.info("交易系统启动")
        self.is_running = True
        
        while self.is_running:
            # TODO: 从数据源获取实时K线
            # bar_data = await self.get_bar_data()
            # await self.run_bar(bar_data)
            
            await asyncio.sleep(1)  # 临时
    
    def stop(self):
        """停止系统"""
        logger.info("交易系统停止")
        self.is_running = False
        
        # 重置策略
        self.dual_thrust.reset()
        self.mean_revert.reset()
        
        # 记录当日数据
        logger.info(f"当日交易次数: {self.trade_count}")
        logger.info(f"当日盈亏: {self.daily_loss}")


def main():
    """主入口"""
    system = TradingSystem('./config')
    
    try:
        asyncio.run(system.run())
    except KeyboardInterrupt:
        system.stop()


if __name__ == '__main__':
    main()