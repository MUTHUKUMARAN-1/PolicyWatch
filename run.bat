@echo off
title PolicyWatch - Privacy Policy & Terms Change Tracker
echo ========================================================
echo    Starting PolicyWatch Unified Web Application...
echo ========================================================

cd /d "%~dp0"

IF EXIST ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
) ELSE (
    echo [!] Virtual environment (.venv) not found. Using system Python.
)

python run.py
pause
