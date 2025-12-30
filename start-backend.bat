@echo off
REM Batch script to start the GraphTrace Python backend
REM Usage: start-backend.bat

echo Starting GraphTrace Backend Server...

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo Error: Python is not installed or not in PATH
    pause
    exit /b 1
)

REM Navigate to backend directory
cd /d "%~dp0python_backend"

REM Check if virtual environment exists
if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
)

REM Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate.bat

REM Check if .env file exists
if not exist ".env" (
    echo Warning: .env file not found. Please create one with Neo4j credentials.
    echo Example .env contents:
    echo NEO4J_URI=neo4j+s://your-instance.databases.neo4j.io
    echo NEO4J_USER=neo4j
    echo NEO4J_PASSWORD=your-password
    echo NEO4J_DATABASE=neo4j
    echo.
)

REM Install/upgrade dependencies
echo Installing/updating dependencies...
python -m pip install --upgrade pip
python -m pip install -r requirement.txt

REM Set PYTHONPATH
set PYTHONPATH=%~dp0python_backend

REM Start the server
echo.
echo ========================================
echo Starting FastAPI server on port 8011...
echo API Documentation: http://localhost:8011/docs
echo Press Ctrl+C to stop the server
echo ========================================
echo.

python -m uvicorn main:app --host 0.0.0.0 --port 8011 --reload
