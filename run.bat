@echo off
chcp 65001 >nul
title DuDu - Trung tam dieu phoi giao hang
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\run-web.ps1" %*
if errorlevel 1 pause
