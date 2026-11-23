# tools/run-web.ps1 — chạy web DuDu bằng một lệnh.
#
#   powershell -ExecutionPolicy Bypass -File tools\run-web.ps1
#   (hoặc bấm đúp run.bat ở thư mục gốc repo)
#
# Script tự tìm Python có đủ fastapi/uvicorn theo thứ tự: biến DUDU_PYTHON → .venv →
# python/python3 trên PATH → một số bản Python cài kèm công cụ phát triển (nếu có). Nếu cổng 8000
# đang bận vì DuDu chạy sẵn, nó chỉ mở trình duyệt; nếu cổng bận vì app khác, nó tự nhảy
# sang 8010/8020/…

param(
    [int]$Port = 8000,
    [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch { }
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

function Test-PythonDeps {
    param([string]$Exe)
    if (-not $Exe) { return $false }
    try {
        & $Exe -c "import fastapi, uvicorn" *> $null
        return ($LASTEXITCODE -eq 0)
    } catch {
        return $false
    }
}

function Resolve-Python {
    $candidates = @()
    if ($env:DUDU_PYTHON) { $candidates += $env:DUDU_PYTHON }
    $candidates += (Join-Path $root ".venv\Scripts\python.exe")
    $candidates += "python"
    $candidates += "python3"

    # Một số bản Python cài kèm công cụ phát triển trên máy (nếu có)
    $runtimeDir = Join-Path $HOME ".dsh\dsh-runtimes"
    if (Test-Path $runtimeDir) {
        Get-ChildItem $runtimeDir -Directory -ErrorAction SilentlyContinue | ForEach-Object {
            $candidates += (Join-Path $_.FullName "dependencies\python\python.exe")
        }
    }

    foreach ($candidate in $candidates) {
        if (-not $candidate) { continue }
        $exists = (Test-Path $candidate) -or (Get-Command $candidate -ErrorAction SilentlyContinue)
        if (-not $exists) { continue }
        if (Test-PythonDeps $candidate) { return $candidate }
    }
    return $null
}

function Test-PortInUse {
    param([int]$PortNumber)
    try {
        $conn = Get-NetTCPConnection -LocalPort $PortNumber -State Listen -ErrorAction SilentlyContinue
        if ($conn) { return $true }
    } catch {
        # máy không có cmdlet: thử mở socket trực tiếp
        try {
            $client = New-Object System.Net.Sockets.TcpClient
            $client.Connect("127.0.0.1", $PortNumber)
            $client.Close()
            return $true
        } catch { return $false }
    }
    return $false
}

function Test-DuDuRunning {
    param([int]$PortNumber)
    try {
        $health = Invoke-RestMethod -Uri "http://127.0.0.1:$PortNumber/api/health" -TimeoutSec 3
        return [bool]$health.ok
    } catch {
        return $false
    }
}

$python = Resolve-Python
if (-not $python) {
    Write-Host ""
    Write-Host "  Chưa tìm thấy Python có đủ thư viện (fastapi, uvicorn)." -ForegroundColor Yellow
    Write-Host "  Cài một lần bằng các lệnh sau (trong thư mục repo):"
    Write-Host ""
    Write-Host "      python -m venv .venv"
    Write-Host "      .venv\Scripts\python.exe -m pip install --upgrade pip"
    Write-Host "      .venv\Scripts\python.exe -m pip install -r requirements.txt"
    Write-Host ""
    Write-Host "  Rồi chạy lại run.bat. (Hoặc đặt biến DUDU_PYTHON trỏ tới python.exe có sẵn.)"
    Write-Host ""
    if (-not $NoBrowser) { Read-Host "Nhấn Enter để đóng" }
    exit 1
}

if (-not (Test-Path (Join-Path $root "data\processed\matrix.json"))) {
    Write-Host "  Thiếu data\processed\matrix.json — chạy: $python data\build_matrix.py" -ForegroundColor Yellow
    if (-not $NoBrowser) { Read-Host "Nhấn Enter để đóng" }
    exit 1
}

# Cổng: nếu DuDu đang chạy sẵn thì chỉ mở trình duyệt
for ($i = 0; $i -lt 6; $i++) {
    $tryPort = $Port + ($i * 10)
    if (-not (Test-PortInUse $tryPort)) {
        $Port = $tryPort
        break
    }
    if (Test-DuDuRunning $tryPort) {
        $url = "http://127.0.0.1:$tryPort"
        Write-Host ""
        Write-Host "  DuDu đã chạy sẵn tại $url" -ForegroundColor Green
        Write-Host "  (Cửa sổ này chỉ mở trình duyệt, không khởi động thêm server.)"
        if (-not $NoBrowser) { Start-Process $url }
        Start-Sleep -Seconds 2
        exit 0
    }
    if ($i -eq 5) {
        Write-Host "  Các cổng 8000–8040 đều đang bận. Tắt bớt ứng dụng rồi chạy lại." -ForegroundColor Red
        if (-not $NoBrowser) { Read-Host "Nhấn Enter để đóng" }
        exit 1
    }
}

$url = "http://127.0.0.1:$Port"
$modelFile = Join-Path $root "ml\models\eta_rf.joblib"

Write-Host ""
Write-Host "  DuDu — Trung tâm điều phối giao hàng" -ForegroundColor Green
Write-Host "  Python : $python"
Write-Host "  Địa chỉ: $url"
Write-Host "  Dừng   : nhấn Ctrl+C trong cửa sổ này"
if (-not (Test-Path $modelFile)) {
    Write-Host "  Ghi chú: chưa có mô hình ETA — nút 'ETA mô hình' sẽ dùng OSRM free-flow." -ForegroundColor Yellow
    Write-Host "           Muốn bật ETA ML: python ml\build_dataset.py --force; python ml\train_eta.py"
}
Write-Host ""

$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONPATH = $root

if (-not $NoBrowser) {
    $openCommand = "Start-Sleep -Seconds 3; Start-Process '$url'"
    Start-Process -FilePath "powershell" -WindowStyle Hidden `
        -ArgumentList "-NoProfile", "-Command", $openCommand | Out-Null
}

try {
    & $python -m uvicorn backend.app:app --host 127.0.0.1 --port $Port
} finally {
    Write-Host ""
    Write-Host "  Server đã dừng."
    if (-not $NoBrowser) { Read-Host "Nhấn Enter để đóng" }
}

