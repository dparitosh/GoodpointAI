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
set "REPO_ROOT=%~dp0..\"
set "VENV_DIR=%REPO_ROOT%.venv"
if not exist "%VENV_DIR%\Scripts\python.exe" (
    echo Creating virtual environment at %VENV_DIR%...
    python -m venv "%VENV_DIR%"
)

echo Activating virtual environment...
call "%VENV_DIR%\Scripts\activate.bat"

REM Navigate to backend directory
cd /d "%REPO_ROOT%python_backend"

REM Check if .env file exists
if not exist ".env" (
    echo .env file not found. You must configure environment variables.
    echo Please run '..\bootstrap.ps1' first to set up the environment.
    pause
    exit /b 1
)

findstr /C:"yourpassword" .env >nul
if not errorlevel 1 goto ConfigError
findstr /C:"postgresql://postgres:password@" .env >nul
if not errorlevel 1 goto ConfigError
goto ConfigOK

:ConfigError
echo.
echo CRITICAL CONFIGURATION REQUIRED:
echo You must edit python_backend\.env with your actual PostgreSQL credentials.
echo Default placeholders ('yourpassword') are still present.
echo.
echo 1. Open python_backend\.env
echo 2. Set DATABASE_URL=postgresql://user:pass@host:port/dbname
echo 3. Re-run start-backend.bat
echo.
pause
exit /b 1

:ConfigOK

REM Install/upgrade dependencies
echo Installing/updating dependencies...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

REM Ensure encryption key exists (load from file or generate and persist)
if "%GRAPH_TRACE_CONFIG_ENCRYPTION_KEY%"=="" (
    if exist ".graphtrace.encryption_key" (
        echo Loading encryption key from .graphtrace.encryption_key...
        set /p GRAPH_TRACE_CONFIG_ENCRYPTION_KEY=<.graphtrace.encryption_key
    ) else (
        echo Generating and saving encryption key...
        for /f "delims=" %%i in ('python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"') do (
            set GRAPH_TRACE_CONFIG_ENCRYPTION_KEY=%%i
            echo %%i>.graphtrace.encryption_key
        )
    )
)

REM Initialize DB schema (non-fatal if fails)
echo Initializing database schema...
python -m scripts.init_db_schema 2>nul

REM Set PYTHONPATH
set PYTHONPATH=%REPO_ROOT%python_backend

REM Start the server
echo.
echo ========================================
echo Starting FastAPI server on port 8011...
echo API Documentation: http://localhost:8011/docs
echo Press Ctrl+C to stop the server
echo ========================================
echo.

python -m uvicorn main:app --host 0.0.0.0 --port 8011 --reload
