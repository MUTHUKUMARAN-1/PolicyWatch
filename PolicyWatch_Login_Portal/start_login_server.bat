@echo off
title PolicyWatch Login Portal
echo ====================================================================
echo Starting PolicyWatch Authentication & Change Tracker Portal...
echo ====================================================================
cd /d "%~dp0"

echo Launching Python Server on http://localhost:5050...
start "" "http://localhost:5050"
python server.py --port 5050

pause
