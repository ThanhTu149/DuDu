# tools/push.ps1 — kiểm thử, commit và push, rồi xác nhận đã đồng bộ.
#
# Dùng:
#   powershell -ExecutionPolicy Bypass -File tools/push.ps1 "web: mô tả thay đổi"
#
# Không truyền mô tả thì script dùng mô tả mặc định kèm thời gian.

param(
    [string]$Message = ""
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

if (-not $Message) {
    $Message = "chore: cập nhật " + (Get-Date -Format "yyyy-MM-dd HH:mm")
}

# 1. Kiểm thử
Write-Host "== Kiểm thử ==" -ForegroundColor Cyan
function Resolve-TestPython {
    $candidates = @()
    if ($env:DUDU_PYTHON) { $candidates += $env:DUDU_PYTHON }
    if ($env:DSH_PYTHON) { $candidates += $env:DSH_PYTHON }
    $candidates += (Join-Path $root ".venv\Scripts\python.exe")
    $runtimeDir = Join-Path $HOME ".dsh\dsh-runtimes"
    if (Test-Path $runtimeDir) {
        Get-ChildItem $runtimeDir -Directory -ErrorAction SilentlyContinue | ForEach-Object {
            $candidates += (Join-Path $_.FullName "dependencies\python\python.exe")
        }
    }
    $candidates += "python"
    $candidates += "python3"
    foreach ($candidate in $candidates) {
        if (-not $candidate) { continue }
        $exists = (Test-Path $candidate) -or (Get-Command $candidate -ErrorAction SilentlyContinue)
        if (-not $exists) { continue }
        try {
            & $candidate -c "import fastapi" *> $null
            if ($LASTEXITCODE -eq 0) { return $candidate }
        } catch {}
    }
    return "python"
}
$python = Resolve-TestPython
Write-Host "Python: $python" -ForegroundColor DarkGray
$env:PYTHONPATH = $root
& $python -m unittest discover -s tests
if ($LASTEXITCODE -ne 0) {
    Write-Host "Kiểm thử hỏng — không push." -ForegroundColor Red
    exit 1
}

Write-Host "== Kiểm tra cú pháp JavaScript ==" -ForegroundColor Cyan
node --check web/assets/app.js
if ($LASTEXITCODE -ne 0) {
    Write-Host "JavaScript lỗi cú pháp — không push." -ForegroundColor Red
    exit 1
}

# 2. Commit nếu có thay đổi
$pending = git status --porcelain
if ($pending) {
    git add -A
    git commit -m $Message | Out-Host
    if ($LASTEXITCODE -ne 0) { exit 1 }
} else {
    Write-Host "Không có thay đổi mới để commit." -ForegroundColor Yellow
}

# 3. Push
git push origin main
if ($LASTEXITCODE -ne 0) {
    Write-Host "Push thất bại (có thể remote có commit mới) — thử: git pull --rebase origin main" -ForegroundColor Red
    exit 1
}

# 4. Xác nhận đồng bộ
git fetch -q origin
$local = git rev-parse --short HEAD
$remote = git rev-parse --short origin/main
if ($local -ne $remote) {
    Write-Host "LỆCH: local=$local remote=$remote" -ForegroundColor Red
    exit 1
}
Write-Host "Đã push và đồng bộ: $local" -ForegroundColor Green
