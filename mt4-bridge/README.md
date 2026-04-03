# MT4 ZeroMQ 桥接部署指南

## 架构说明

```
┌─────────┐   ZeroMQ PUB (5555)   ┌──────────────┐
│  MT4 EA │ ──────────────────────>│ Python 策略  │
│         │   推送实时行情          │              │
│         │                        │ Dual Thrust  │
│         │   ZeroMQ REP (5556)   │ 均值回归     │
│         │ <─────────────────────│              │
│         │   接收交易指令          │              │
└─────────┘                        └──────────────┘
```

## 部署步骤

### Step 1: 安装 ZeroMQ 库到 MT4

1. 下载 MT4 ZeroMQ 库:
   - https://github.com/nicholasnadel/ZeroMQ-MT4
   - 或使用 `mql-zmq` 库

2. 复制文件到 MT4 目录:
   ```
   ZeroMQ.mqh → MQL4/Include/ZMQ/
   libzmq.dll → MQL4/Libraries/
   ```

### Step 2: 安装 EA 到 MT4

1. 复制 `mt4_zmq_bridge.mq4` 到 `MQL4/Experts/`

2. 在 MT4 中编译:
   - MetaEditor → 打开文件 → Compile

3. 将 EA 添加到图表:
   - Navigator → Expert Advisors → MT4 ZeroMQ Bridge
   - 拖到 XAUUSD 或 XAGUSD 图表
   - 勾选 "Allow live trading"

### Step 3: 安装 Python 依赖

```bash
pip install zmq numpy
```

### Step 4: 启动交易系统

```bash
# 先启动 MT4 EA

# 然后运行 Python 策略
cd mt4-bridge
python mt4_trading_system.py
```

## 参数调整 (外汇 vs 期货)

| 参数 | 上期所期货 | MT4 外汇 |
|------|-----------|---------|
| 突破系数 K1 | 0.4 | 0.3 |
| 突破系数 K2 | 0.6 | 0.4 |
| ATR 止损倍数 | 2.0 | 1.5 |
| 布林带标准差 | 2.0 | 2.5 |
| 最小手数 | 1手 | 0.01手 |
| RSI 超买 | 70 | 75 |
| RSI 超卖 | 30 | 25 |

## 常见问题

### Q: ZeroMQ 连接失败
检查:
- MT4 EA 是否正在运行
- 端口 5555/5556 是否被占用
- Firewall 是否允许

### Q: 行情数据不更新
检查:
- MT4 是否已登录服务器
- 是否选择了正确的图表周期 (5分钟)
- EA 是否启用了 live trading

### Q: 交易指令失败
检查:
- 模拟账户是否有足够余额
- 手数是否符合平台限制
- 止损价格是否合理

## 文件说明

| 文件 | 作用 |
|------|------|
| `mt4_zmq_bridge.mq4` | MT4 EA，负责行情推送和订单执行 |
| `mt4_strategy.py` | ZeroMQ 桥接器，接收行情/发送指令 |
| `mt4_trading_system.py` | 完整交易系统，整合策略 + 桥接 |

---

**状态**: 代码完成，待用户部署测试