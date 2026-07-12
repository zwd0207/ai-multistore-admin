@echo off
chcp 65001 >nul
title PXG 试运营登录信息
cd /d "%~dp0codex1\backend"
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" "scripts\show_local_pxg_trial_code.py"
) else (
  python "scripts\show_local_pxg_trial_code.py"
)
echo.
pause
