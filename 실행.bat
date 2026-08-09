@echo off
REM Law capture launcher - ASCII only (Korean breaks in .bat on some PCs)
cd /d "%~dp0"

where pythonw >nul 2>&1
if errorlevel 1 (
    echo Python is not installed or not in PATH.
    echo Install Python 3.10 or newer from https://www.python.org/downloads/
    echo During install, check "Add Python to PATH".
    pause
    exit /b 1
)

start "" pythonw "%~dp0run.pyw"
