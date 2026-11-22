@echo off
chcp 65001 >nul
title DuDu - chay bang Docker
cd /d "%~dp0"

where docker >nul 2>&1
if errorlevel 1 (
  echo Khong tim thay Docker. Cai Docker Desktop truoc: https://www.docker.com/products/docker-desktop/
  pause
  exit /b 1
)

docker info >nul 2>&1
if errorlevel 1 (
  echo Docker Desktop chua chay. Mo Docker Desktop, doi den khi icon bao "Engine running" roi chay lai file nay.
  pause
  exit /b 1
)

echo Dang build va khoi dong DuDu bang Docker...
docker compose up -d --build
if errorlevel 1 (
  echo Build/chay container that bai. Xem log: docker compose logs
  pause
  exit /b 1
)

set READY=0
for /l %%i in (1,1,60) do (
  curl -s -o nul http://127.0.0.1:8000/api/health && set READY=1 && goto :ready
  timeout /t 1 >nul
)
:ready
if "%READY%"=="0" echo Server chua san sang, thu mo lai sau vai giay.

start "" http://127.0.0.1:8000
echo.
echo   DuDu dang chay tai http://127.0.0.1:8000
echo   Xem log : docker compose logs -f
echo   Dung    : docker compose down
echo.
pause
