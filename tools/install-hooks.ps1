# tools/install-hooks.ps1 — cài móc git để chặn push khi kiểm thử hỏng.
#
# Dùng một lần:  powershell -ExecutionPolicy Bypass -File tools/install-hooks.ps1
# Gỡ:            Remove-Item .git/hooks/pre-push
#
# Móc tự tìm Python có đủ thư viện (fastapi). Nếu máy chưa cài đủ phụ thuộc thì nó BỎ QUA
# kiểm thử kèm cảnh báo, để không chặn oan những lần push chỉ sửa docs.

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
cd "$(git rev-parse --show-toplevel)" || exit 1
PY="${DSH_PYTHON:-python}"
if ! "$PY" -c "import fastapi" >/dev/null 2>&1; then
  echo "[pre-push] Bỏ qua kiểm thử: python hiện tại chưa cài đủ phụ thuộc (requirements.txt)."
  exit 0
fi
echo "[pre-push] Đang chạy bộ kiểm thử…"
"$PY" -m unittest discover -s tests -q || {
  echo "[pre-push] Kiểm thử hỏng — push bị chặn. Chạy: $PY -m unittest discover -s tests -v"
  exit 1
}
'@
[System.IO.File]::WriteAllText($hook, $body, [System.Text.UTF8Encoding]::new($false))
Write-Host "Đã cài .git/hooks/pre-push — mỗi lần push sẽ chạy kiểm thử trước (nếu máy có đủ phụ thuộc)." -ForegroundColor Green
Write-Host "Mẹo: đặt biến DSH_PYTHON trỏ tới Python có fastapi để móc dùng đúng trình thông dịch." -ForegroundColor Yellow
