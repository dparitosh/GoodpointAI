@echo off
REM Batch script to start both frontend and backend services
REM Usage: start-all.bat

echo Starting GraphTrace Full Stack Application...
echo.

REM Start backend in a new command window
echo Starting Backend Server...
start "GraphTrace Backend" cmd /k "%~dp0start-backend.bat"

REM Wait a bit for backend to start
echo Waiting for backend to initialize...
timeout /t 3 /nobreak >nul

REM Start frontend in a new command window
echo Starting Frontend Server...
start "GraphTrace Frontend" cmd /k "%~dp0start-frontend.bat"

echo.
echo ========================================
echo GraphTrace Services Starting...
echo Backend API: http://localhost:8000
echo API Docs: http://localhost:8000/docs
echo Frontend: http://localhost:5173
echo.
echo Close the individual command windows to stop services
echo ========================================
echo.
pause
