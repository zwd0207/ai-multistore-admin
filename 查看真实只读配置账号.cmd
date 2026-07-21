@echo off
chcp 65001 >nul
title PXG Local Configuration Administrator
cd /d "%~dp0backend"
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" "scripts\show_local_config_admin.py"
) else (
  python "scripts\show_local_config_admin.py"
)
echo.
pause
