@echo off
REM Batch file to start the Production Portal application

echo ===========================================
echo   Starting Production Portal Server...
echo ===========================================
echo.
REM Change directory to the script's location (where production_portal code is)
cd /d "%~dp0"

REM Check if virtual environment exists
IF NOT EXIST ".\venv\Scripts\activate.bat" (
    echo ERROR: Virtual environment 'venv' not found in this directory.
    echo Please ensure the virtual environment is created and named 'venv'.
    pause
    exit /b 1
)

echo Activating virtual environment...
call .\venv\Scripts\activate.bat

echo.
echo Starting Waitress server on port 5000 with more threads...
echo (Press CTRL+C to stop the server)
echo.
REM Run the Waitress server with increased threads (e.g., 10)
waitress-serve --host=0.0.0.0 --port=5000 --threads=50 --call app:create_app

echo.
echo Server stopped.
pause