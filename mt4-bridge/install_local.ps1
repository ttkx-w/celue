# MT4 Simple Bridge 一键配置脚本
# 在 Windows PowerShell 中运行

$MT4Path = "C:\Users\EC Markets MetaTrader 4 Terminal"
$ExpertsPath = "$MT4Path\MQL4\Experts"
$FilesPath = "$MT4Path\MQL4\Files\bridge"

# 创建目录
Write-Host "创建目录..."
New-Item -ItemType Directory -Force -Path $ExpertsPath | Out-Null
New-Item -ItemType Directory -Force -Path $FilesPath | Out-Null

# EA 内容
$EAContent = @"
//+------------------------------------------------------------------+
//| MT4 Simple Bridge EA                                              |
//| 通过文件系统与 Python 通信                                        |
//+------------------------------------------------------------------+
#property strict
#property version "1.00"

int OnInit() { Print("Bridge启动"); return INIT_SUCCEEDED; }
void OnDeinit(int r) { Print("Bridge关闭"); }

void OnTick()
{
    string s = Symbol();
    string tick = s + "," + TimeToString(TimeCurrent()) + "," +
                  DoubleToString(iOpen(s,0,0),5) + "," +
                  DoubleToString(iHigh(s,0,0),5) + "," +
                  DoubleToString(iLow(s,0,0),5) + "," +
                  DoubleToString(Bid,5) + "," +
                  DoubleToString(Ask,5) + "," +
                  IntegerToString(iVolume(s,0,0));

    int h = FileOpen("bridge/tick.txt", FILE_CSV|FILE_WRITE|FILE_ANSI);
    if(h > 0) { FileWriteString(h, tick); FileClose(h); }

    int h2 = FileOpen("bridge/cmd.txt", FILE_CSV|FILE_READ|FILE_ANSI);
    if(h2 > 0) {
        string cmd = FileReadString(h2);
        FileClose(h2);
        FileDelete("bridge/cmd.txt");
        if(StringLen(cmd) > 0) ProcessCmd(cmd);
    }
}

void ProcessCmd(string cmd)
{
    string p[]; StringSplit(cmd, ",", p);
    if(ArraySize(p) < 3) return;

    string act = p[0];
    string sym = p[1];
    double lot = StringToDouble(p[2]);
    double sl = ArraySize(p)>3 ? StringToDouble(p[3]) : 0;
    double tp = ArraySize(p)>4 ? StringToDouble(p[4]) : 0;

    if(act=="BUY") OrderSend(sym, OP_BUY, lot, Ask, 3, sl, tp, "BR",0,0,clrGreen);
    else if(act=="SELL") OrderSend(sym, OP_SELL, lot, Bid, 3, sl, tp, "BR",0,0,clrRed);
    else if(act=="CLOSE") {
        for(int i=OrdersTotal()-1; i>=0; i--) {
            if(OrderSelect(i,SELECT_BY_POS) && OrderSymbol()==sym) {
                if(OrderType()==OP_BUY) OrderClose(OrderTicket(),OrderLots(),Bid,3,clrBlue);
                else OrderClose(OrderTicket(),OrderLots(),Ask,3,clrOrange);
            }
        }
    }
}
"@

# 写入 EA 文件
Write-Host "写入 EA 文件..."
[System.IO.File]::WriteAllText("$ExpertsPath\mt4_simple_bridge.mq4", $EAContent, [System.Text.Encoding]::UTF8)

# Python 桥接脚本
$PythonContent = @"
#!/usr/bin/env python3
"""MT4 Simple Bridge - Python 端"""
import os
import time
from pathlib import Path

MT4_DATA_DIR = Path("$MT4Path/MQL4/Files/bridge")

class MT4Bridge:
    def __init__(self):
        self.tick_file = MT4_DATA_DIR / "tick.txt"
        self.cmd_file = MT4_DATA_DIR / "cmd.txt"
        MT4_DATA_DIR.mkdir(parents=True, exist_ok=True)

    def read_tick(self):
        if not self.tick_file.exists():
            return None
        try:
            parts = self.tick_file.read_text().strip().split(',')
            return {
                'symbol': parts[0], 'time': parts[1],
                'open': float(parts[2]), 'high': float(parts[3]),
                'low': float(parts[4]), 'bid': float(parts[5]),
                'ask': float(parts[6]), 'volume': int(parts[7])
            }
        except:
            return None

    def send_command(self, action, symbol, lots, sl=0, tp=0):
        self.cmd_file.write_text(f"{action},{symbol},{lots},{sl},{tp}")
        time.sleep(0.5)

def main():
    bridge = MT4Bridge()
    print("MT4 Bridge 启动")
    while True:
        tick = bridge.read_tick()
        if tick:
            print(f"[{tick['time']}] {tick['symbol']} Bid={tick['bid']} Ask={tick['ask']}")
        time.sleep(1)

if __name__ == "__main__":
    main()
"@

# 写入 Python 文件
Write-Host "写入 Python 文件..."
$PythonPath = "C:\temp\mt4_bridge.py"
[System.IO.File]::WriteAllText($PythonPath, $PythonContent, [System.Text.Encoding]::UTF8)

Write-Host ""
Write-Host "✅ 配置完成！"
Write-Host ""
Write-Host "后续步骤："
Write-Host "1. 打开 MT4"
Write-Host "2. Navigator → Experts → mt4_simple_bridge"
Write-Host "3. 拖到 XAUUSD 5分钟图表"
Write-Host "4. 勾选 Allow live trading"
Write-Host "5. 运行: python C:\temp\mt4_bridge.py"
Write-Host ""
Write-Host "文件位置:"
Write-Host "EA: $ExpertsPath\mt4_simple_bridge.mq4"
Write-Host "Python: $PythonPath"