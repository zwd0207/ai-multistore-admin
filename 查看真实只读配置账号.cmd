@echo off
chcp 65001 >nul
title PXG Real Readonly Configuration Account
cd /d "%~dp0codex1\backend"
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" "scripts\show_local_config_admin.py"
) else (
  python "scripts\show_local_config_admin.py"
)
echo.
pause
