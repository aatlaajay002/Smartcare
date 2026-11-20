@echo off
title SmartCare - Smart Healthcare System
cd /d "%~dp0Backend"
echo.
echo  === SmartCare launcher ===
python --version >nul 2>&1
if errorlevel 1 (
  echo  Python is not installed or not in PATH. Install it from python.org and tick "Add Python to PATH".
  pause
  exit /b
)
if not exist venv (
  echo  First-time setup: creating virtual environment...
  python -m venv venv
)
call venv\Scripts\activate
echo  Checking requirements (first time takes 1-3 minutes)...
python -m pip install -r requirements.txt -q
if not exist .env copy .env.example .env >nul
echo.
echo  Starting the app - your browser will open automatically.
echo  Keep this window open. Press Ctrl+C to stop.
echo.
python app.py
pause
