# PowerShell script to start both frontend and backend services
# Usage: .\start-all.ps1

Write-Host "Starting GraphTrace Full Stack Application..." -ForegroundColor Green
Write-Host ""

# Get script directory
$scriptDir = $PSScriptRoot

# Start backend in a new PowerShell window
Write-Host "Starting Backend Server..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-File", "$scriptDir\start-backend.ps1"

# Wait a bit for backend to start
Write-Host "Waiting for backend to initialize..." -ForegroundColor Yellow
Start-Sleep -Seconds 3

# Start frontend in a new PowerShell window
Write-Host "Starting Frontend Server..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-File", "$scriptDir\start-frontend.ps1"

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "GraphTrace Services Starting..." -ForegroundColor Green
Write-Host "Backend API: http://localhost:8011" -ForegroundColor Cyan
Write-Host "API Docs: http://localhost:8011/docs" -ForegroundColor Cyan
Write-Host "Frontend: http://localhost:5173" -ForegroundColor Cyan
Write-Host ""
Write-Host "Close the individual PowerShell windows to stop services" -ForegroundColor Yellow
Write-Host "========================================" -ForegroundColor Green
