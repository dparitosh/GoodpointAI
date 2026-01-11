@echo off
REM Batch script to start the GraphTrace React frontend
REM Usage: start-frontend.bat

echo Starting GraphTrace Frontend...

REM Check if Node.js is installed
node --version >nul 2>&1
if errorlevel 1 (
    echo Error: Node.js is not installed or not in PATH
    echo Please install Node.js from https://nodejs.org/
    pause
    exit /b 1
)

REM Check if npm is installed
npm --version >nul 2>&1
if errorlevel 1 (
    echo Error: npm is not installed or not in PATH
    pause
    exit /b 1
)

REM Display Node and npm versions
echo Node version:
node --version
echo npm version:
npm --version
echo.

REM Navigate to frontend directory
cd /d "%~dp0e2etraceapp"

REM Check if .env file exists
if not exist ".env" (
    echo Warning: .env file not found. Creating default .env file...
    (
        echo # Frontend Environment Variables
        echo # The VITE_ prefix is required for Vite to expose these to the client
        echo VITE_API_BASE_URL=http://localhost:8011
        echo VITE_NEO4J_URI=bolt://localhost:7687
        echo VITE_NEO4J_USER=neo4j
    ) > .env
    echo Created .env file with default values
)

REM Check if node_modules exists
if not exist "node_modules" (
    echo node_modules not found. Installing dependencies...
    npm install
) else (
    echo Checking for dependency updates...
    npm install
)

REM Start the development server
echo.
echo ========================================
echo Starting Vite dev server...
echo Frontend will be available at: http://localhost:5173
echo Press Ctrl+C to stop the server
echo ========================================
echo.

npm run dev
