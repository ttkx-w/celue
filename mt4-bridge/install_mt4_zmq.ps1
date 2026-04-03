# MT4 ZeroMQ 桥接一键配置脚本
# 运行方式: 右键 -> 以管理员身份运行

$ErrorActionPreference = "Stop"

# 配置
$MT4_PATH = "C:\Users\EC Markets MetaTrader 4 Terminal"
$MQL4_PATH = "$MT4_PATH\MQL4"
$USER_NAME = "lx男朋友的电脑"

# 颜色输出
function Write-Step($msg) {
    Write-Host "`n=== $msg ===" -ForegroundColor Cyan
}

function Write-Success($msg) {
    Write-Host "✅ $msg" -ForegroundColor Green
}

function Write-Error($msg) {
    Write-Host "❌ $msg" -ForegroundColor Red
}

# 开始
Write-Host "MT4 ZeroMQ 桥接配置脚本" -ForegroundColor Yellow
Write-Host "用户: $USER_NAME"
Write-Host "MT4: $MT4_PATH"

# Step 1: 检查 MT4 目录
Write-Step "检查 MT4 目录"
if (-not (Test-Path $MT4_PATH)) {
    Write-Error "MT4 目录不存在: $MT4_PATH"
    Write-Host "请确认 MT4 安装路径后重新运行"
    pause
    exit 1
}
Write-Success "MT4 目录存在"

# 创建 MQL4 子目录
$dirs = @("Experts", "Libraries", "Include")
foreach ($dir in $dirs) {
    $path = "$MQL4_PATH\$dir"
    if (-not (Test-Path $path)) {
        New-Item -ItemType Directory -Path $path -Force | Out-Null
        Write-Success "创建目录: $dir"
    }
}

# Step 2: 下载 ZeroMQ 库
Write-Step "下载 ZeroMQ 库"
$zmqUrl = "https://github.com/nicholasnadel/ZeroMQ-MT4/archive/refs/heads/main.zip"
$zmqZip = "$env:TEMP\zeromq-mt4.zip"
$zmqExtract = "$env:TEMP\zeromq-mt4"

try {
    Write-Host "正在下载 ZeroMQ..."
    Invoke-WebRequest -Uri $zmqUrl -OutFile $zmqZip -UseBasicParsing
    Write-Success "下载完成"
    
    Write-Host "正在解压..."
    Expand-Archive -Path $zmqZip -DestinationPath $zmqExtract -Force
    Write-Success "解压完成"
} catch {
    Write-Error "下载失败: $($_.Exception.Message)"
    Write-Host "请手动下载: https://github.com/nicholasnadel/ZeroMQ-MT4"
    pause
    exit 1
}

# Step 3: 复制 ZeroMQ 文件
Write-Step "安装 ZeroMQ 到 MT4"

# 复制 Include 文件
$zmqInclude = "$zmqExtract\ZeroMQ-MT4-main\Include\ZMQ"
if (Test-Path $zmqInclude) {
    Copy-Item -Path $zmqInclude -Destination "$MQL4_PATH\Include\ZMQ" -Recurse -Force
    Write-Success "复制 Include/ZMQ"
} else {
    Write-Error "找不到 ZMQ Include 文件"
}

# 复制 Libraries 文件
$zmqLibs = Get-ChildItem "$zmqExtract\ZeroMQ-MT4-main\Libraries" -Filter "*.dll"
foreach ($lib in $zmqLibs) {
    Copy-Item -Path $lib.FullName -Destination "$MQL4_PATH\Libraries" -Force
    Write-Success "复制库: $($lib.Name)"
}

# Step 4: 下载 EA 文件
Write-Step "下载交易策略文件"
$githubRepo = "https://raw.githubusercontent.com/ttkx-w/celue/main/mt4-bridge"

$files = @(
    @{Url="$githubRepo/mt4_zmq_bridge.mq4"; Dest="$MQL4_PATH\Experts\mt4_zmq_bridge.mq4"},
    @{Url="$githubRepo/mt4_strategy.py"; Dest="$MT4_PATH\mt4_strategy.py"},
    @{Url="$githubRepo/mt4_trading_system.py"; Dest="$MT4_PATH\mt4_trading_system.py"}
)

foreach ($file in $files) {
    try {
        Write-Host "下载: $($file.Dest)"
        Invoke-WebRequest -Uri $file.Url -OutFile $file.Dest -UseBasicParsing
        Write-Success "下载完成: $(Split-Path $file.Dest -Leaf)"
    } catch {
        Write-Error "下载失败: $($file.Url)"
    }
}

# Step 5: 安装 Python 依赖
Write-Step "安装 Python 依赖"
try {
    $pythonCmd = Get-Command python -ErrorAction SilentlyContinue
    if ($pythonCmd) {
        Write-Host "检测到 Python: $($pythonCmd.Source)"
        
        # 安装依赖
        pip install pyzmq numpy 2>&1 | Out-Null
        Write-Success "安装 pyzmq numpy"
    } else {
        Write-Host "未检测到 Python，请手动安装:" -ForegroundColor Yellow
        Write-Host "  pip install pyzmq numpy"
    }
} catch {
    Write-Error "Python 依赖安装失败"
}

# Step 6: 配置说明
Write-Step "配置完成"
Write-Host @"
========================================
✅ MT4 ZeroMQ 桥接已安装!

下一步操作:
1. 打开 MT4
2. Navigator -> Expert Advisors -> mt4_zmq_bridge
3. 拖到 XAUUSD 图表 (5分钟周期)
4. 勾选 "Allow live trading"
5. 在文件夹中运行: python mt4_trading_system.py

文件位置:
- EA: $MQL4_PATH\Experts\mt4_zmq_bridge.mq4
- Python: $MT4_PATH\mt4_trading_system.py

测试命令:
cd "$MT4_PATH"
python mt4_strategy.py
========================================
"@ -ForegroundColor Green

# 清理临时文件
Remove-Item $zmqZip -Force -ErrorAction SilentlyContinue
Remove-Item $zmqExtract -Recurse -Force -ErrorAction SilentlyContinue

pause