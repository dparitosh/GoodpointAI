@echo off
REM Batch script to start the GraphTrace Python backend
REM Usage: start-backend.bat

echo Starting GraphTrace Backend Server...

REM Opt into repo-local `.env` loading for local development.
if "%GRAPH_TRACE_LOAD_DOTENV%"=="" set GRAPH_TRACE_LOAD_DOTENV=true

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo Error: Python is not installed or not in PATH
    pause
    exit /b 1
)

REM Use repo-root .venv so VS Code tasks and scripts share one environment.
set "REPO_ROOT=%~dp0"
set "VENV_DIR=%REPO_ROOT%.venv"
if not exist "%VENV_DIR%\Scripts\python.exe" (
    echo Creating virtual environment at %VENV_DIR%...
    python -m venv "%VENV_DIR%"
)

echo Activating virtual environment...
call "%VENV_DIR%\Scripts\activate.bat"

REM Navigate to backend directory
cd /d "%REPO_ROOT%agentic-restored\python_backend"

REM Check if .env file exists
if not exist ".env" (
    echo Warning: .env file not found. Please create one with Neo4j credentials.
    echo Example .env contents:
    echo NEO4J_URI=neo4j+s://your-instance.databases.neo4j.io
    echo NEO4J_USER=neo4j
    echo NEO4J_PASSWORD=your-password
    echo NEO4J_DATABASE=neo4j
    echo GRAPH_TRACE_ALLOWED_LOCAL_ROOTS=D:\path\to\your\import\folder
    echo.
)

REM Install/upgrade dependencies
echo Installing/updating dependencies...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

REM Ensure encryption key exists (generate if missing)
if "%GRAPH_TRACE_CONFIG_ENCRYPTION_KEY%"=="" (
    echo Generating session encryption key...
    for /f "delims=" %%i in ('python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"') do set GRAPH_TRACE_CONFIG_ENCRYPTION_KEY=%%i
)

REM Initialize DB schema (non-fatal if fails)
echo Initializing database schema...
python -m scripts.init_db_schema 2>nul

REM Set PYTHONPATH
set PYTHONPATH=%REPO_ROOT%agentic-restored\python_backend

REM Start the server
echo.
echo ========================================
echo Starting FastAPI server on port 8011...
echo API Documentation: http://localhost:8011/docs
echo Press Ctrl+C to stop the server
echo ========================================
echo.

python -m uvicorn main:app --host 0.0.0.0 --port 8011 --reload
