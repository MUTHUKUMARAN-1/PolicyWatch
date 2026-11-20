@echo off
title PolicyWatch Setup
echo ========================================================
echo    PolicyWatch Environment Setup & Dependencies
echo ========================================================

cd /d "%~dp0"

IF NOT EXIST ".venv" (
    echo [*] Creating virtual environment (.venv)...
    python -m venv .venv
)

call .venv\Scripts\activate.bat

echo [*] Installing required Python packages...
python -m pip install --upgrade pip
pip install -r requirements.txt

echo [*] Initializing database and migrations...
python -c "import sys, os; sys.path.insert(0, '.'); from models import database as db; db.init_db(); from models import sample_data; sample_data.insert_sample_data(); print('[+] Database ready!')"

echo ========================================================
echo Setup completed successfully! Run 'run.bat' to start PolicyWatch.
echo ========================================================
pause
