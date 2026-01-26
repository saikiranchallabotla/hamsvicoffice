@echo off
REM Offline Package Installation Script for Hamsvic
REM Run this script on a new system to install all dependencies without internet

echo ==========================================
echo  Hamsvic Offline Package Installer
echo ==========================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.13 first
    pause
    exit /b 1
)

REM Create virtual environment if it doesn't exist
if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
)

echo Activating virtual environment...
call venv\Scripts\activate.bat

echo Installing packages from local cache...
pip install --no-index --find-links=packages -r requirements.txt

echo.
echo ==========================================
echo  Installation Complete!
echo ==========================================
echo.
echo To run the server:
echo   1. Activate venv: venv\Scripts\activate
echo   2. Run: python manage.py runserver
echo.
pause
