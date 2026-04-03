//+------------------------------------------------------------------+
//| MT4 ZeroMQ Bridge EA                                             |
//| 接收 Python 策略信号并执行交易                                    |
//+------------------------------------------------------------------+
#property strict
#property version "1.00"

#include <ZMQ/ZMQ.mqh>

// ZeroMQ 配置
string PUB_HOST = "tcp://*:5555";   // 发送行情数据
string REP_HOST = "tcp://*:5556";   // 接收交易指令

// 全局变量
Context context;
Socket pubSocket;
Socket repSocket;

// 交易参数
input double RiskPercent = 2.0;     // 单笔风险百分比
input int ATRPeriod = 14;           // ATR周期
input double ATRStopMult = 2.0;     // ATR止损倍数

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
    // 初始化 ZeroMQ
    context = Context("mt4_bridge");
    
    // 创建 Publisher Socket (发送行情)
    pubSocket = context.createSocket(ZMQ_PUB);
    pubSocket.bind(PUB_HOST);
    
    // 创建 Reply Socket (接收指令)
    repSocket = context.createSocket(ZMQ_REP);
    repSocket.bind(REP_HOST);
    
    Print("MT4 ZeroMQ Bridge 启动成功");
    Print("行情端口: 5555, 指令端口: 5556");
    
    return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
    pubSocket.close();
    repSocket.close();
    context.term();
    Print("MT4 ZeroMQ Bridge 已关闭");
}

//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick()
{
    // 发送行情数据到 Python
    string symbol = Symbol();
    double bid = Bid;
    double ask = Ask;
    double high = iHigh(symbol, PERIOD_M5, 0);
    double low = iLow(symbol, PERIOD_M5, 0);
    double open = iOpen(symbol, PERIOD_M5, 0);
    double volume = iVolume(symbol, PERIOD_M5, 0);
    
    // 构建消息
    string msg = StringFormat("%s|%s|%f|%f|%f|%f|%f|%f|%d",
        symbol,
        TimeToString(TimeCurrent(), TIME_SECONDS),
        open, high, low, bid, ask,
        iClose(symbol, PERIOD_M5, 0),
        volume);
    
    // 发送行情
    ZmqMsg zmqMsg(msg);
    pubSocket.send(zmqMsg);
    
    // 检查是否有交易指令
    CheckTradeCommands();
}

//+------------------------------------------------------------------+
//| 检查交易指令                                                      |
//+------------------------------------------------------------------+
void CheckTradeCommands()
{
    ZmqMsg request;
    
    if(repSocket.recv(request, true))  // 非阻塞接收
    {
        string cmd = request.getData();
        ProcessTradeCommand(cmd);
    }
}

//+------------------------------------------------------------------+
//| 处理交易指令                                                      |
//+------------------------------------------------------------------+
void ProcessTradeCommand(string cmd)
{
    // 解析指令格式: ACTION|SYMBOL|LOTS|PRICE|STOPLOSS
    string parts[];
    StringSplit(cmd, '|', parts);
    
    if(ArraySize(parts) < 4)
    {
        SendResponse("ERROR|Invalid command format");
        return;
    }
    
    string action = parts[0];
    string symbol = parts[1];
    double lots = StringToDouble(parts[2]);
    double price = StringToDouble(parts[3]);
    double stopLoss = 0;
    double takeProfit = 0;
    
    if(ArraySize(parts) >= 5) stopLoss = StringToDouble(parts[4]);
    if(ArraySize(parts) >= 6) takeProfit = StringToDouble(parts[5]);
    
    // 执行交易
    int result = -1;
    
    if(action == "BUY")
    {
        RefreshRates();
        result = OrderSend(symbol, OP_BUY, lots, Ask, 3, stopLoss, takeProfit, "ZMQ_BUY", 0, 0, clrGreen);
    }
    else if(action == "SELL")
    {
        RefreshRates();
        result = OrderSend(symbol, OP_SELL, lots, Bid, 3, stopLoss, takeProfit, "ZMQ_SELL", 0, 0, clrRed);
    }
    else if(action == "CLOSE_BUY")
    {
        CloseOrders(symbol, OP_BUY);
        result = 0;
    }
    else if(action == "CLOSE_SELL")
    {
        CloseOrders(symbol, OP_SELL);
        result = 0;
    }
    
    // 返回结果
    if(result >= 0)
        SendResponse(StringFormat("OK|%s|%s|%d", action, symbol, result));
    else
        SendResponse(StringFormat("ERROR|%s|%d", action, GetLastError()));
}

//+------------------------------------------------------------------+
//| 关闭指定类型订单                                                  |
//+------------------------------------------------------------------+
void CloseOrders(string symbol, int orderType)
{
    for(int i = OrdersTotal() - 1; i >= 0; i--)
    {
        if(OrderSelect(i, SELECT_BY_POS, MODE_TRADES))
        {
            if(OrderSymbol() == symbol && OrderType() == orderType)
            {
                if(orderType == OP_BUY)
                    OrderClose(OrderTicket(), OrderLots(), Bid, 3, clrBlue);
                else if(orderType == OP_SELL)
                    OrderClose(OrderTicket(), OrderLots(), Ask, 3, clrOrange);
            }
        }
    }
}

//+------------------------------------------------------------------+
//| 发送响应                                                          |
//+------------------------------------------------------------------+
void SendResponse(string response)
{
    ZmqMsg reply(response);
    repSocket.send(reply);
}
//+------------------------------------------------------------------+