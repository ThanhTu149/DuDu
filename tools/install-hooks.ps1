# tools/install-hooks.ps1 — cài móc git để chặn push khi kiểm thử hỏng.
#
# Dùng một lần:  powershell -ExecutionPolicy Bypass -File tools/install-hooks.ps1
# Gỡ:            Remove-Item .git/hooks/pre-push

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$hookDir = Join-Path $root ".git\hooks"
if (-not (Test-Path $hookDir)) {
    Write-Host "Không phải repo git: thiếu .git/hooks" -ForegroundColor Red
    exit 1
}

$hook = Join-Path $hookDir "pre-push"
$body = @'
#!/bin/sh
# Chặn push nếu kiểm thử hỏng (cài bởi tools/install-hooks.ps1)
python -m unittest discover -s tests
'@
Set-Content -Path $hook -Value $body -Encoding UTF8 -NoNewline
Write-Host "Đã cài .git/hooks/pre-push — mỗi lần push sẽ chạy kiểm thử trước." -ForegroundColor Green
Write-Host "Nhớ đặt PYTHONPATH trỏ về gốc repo nếu chạy từ thư mục con." -ForegroundColor Yellow
