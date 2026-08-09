@echo off
REM Debug launcher - shows error text in this window
cd /d "%~dp0"

where python >nul 2>&1
if errorlevel 1 (
    echo Python is not installed or not in PATH.
    pause
    exit /b 1
)

python -X utf8 -u "%~dp0run.pyw"
echo.
echo Exit code: %ERRORLEVEL%
pause
