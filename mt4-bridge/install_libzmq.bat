# ZeroMQ 库安装脚本 (Windows)

## 方法1: 使用预编译库

1. 下载 ZeroMQ Windows 版本:
   https://github.com/zeromq/libzmq/releases

2. 解压后复制:
   - `libzmq.dll` → `C:\Program Files\[MT4路径]\MQL4\Libraries\`
   - `libsodium.dll` → 同目录

## 方法2: 使用 mql-zmq 项目

git clone https://github.com/nicholasnadel/ZeroMQ-MT4

复制内容:
- Include/ZMQ/* → MQL4/Include/ZMQ/
- Libraries/* → MQL4/Libraries/

## Python 安装 ZeroMQ

pip install pyzmq