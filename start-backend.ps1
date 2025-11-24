# PowerShell script to start the GraphTrace Python backend
# Usage: .\start-backend.ps1

Write-Host "Starting GraphTrace Backend Server..." -ForegroundColor Green

# Check if Python is installed
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host "Error: Python is not installed or not in PATH" -ForegroundColor Red
    exit 1
}

# Navigate to backend directory
Set-Location -Path "$PSScriptRoot\python_backend"

# Check if virtual environment exists
if (-not (Test-Path "venv")) {
    Write-Host "Creating virtual environment..." -ForegroundColor Yellow
    python -m venv venv
}

# Activate virtual environment
Write-Host "Activating virtual environment..." -ForegroundColor Yellow
& ".\venv\Scripts\Activate.ps1"

# Check if .env file exists
if (-not (Test-Path ".env")) {
    Write-Host "Warning: .env file not found. Please create one with Neo4j credentials." -ForegroundColor Yellow
    Write-Host "Example .env contents:" -ForegroundColor Yellow
    Write-Host "NEO4J_URI=neo4j+s://your-instance.databases.neo4j.io" -ForegroundColor Cyan
    Write-Host "NEO4J_USER=neo4j" -ForegroundColor Cyan
    Write-Host "NEO4J_PASSWORD=your-password" -ForegroundColor Cyan
    Write-Host "NEO4J_DATABASE=neo4j" -ForegroundColor Cyan
    Write-Host ""
}

# Install/upgrade dependencies
Write-Host "Installing/updating dependencies..." -ForegroundColor Yellow
python -m pip install --upgrade pip
python -m pip install -r requirement.txt

# Set PYTHONPATH
$env:PYTHONPATH = "$PSScriptRoot\python_backend"

# Start the server
Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "Starting FastAPI server on port 8000..." -ForegroundColor Green
Write-Host "API Documentation: http://localhost:8000/docs" -ForegroundColor Cyan
Write-Host "Press Ctrl+C to stop the server" -ForegroundColor Yellow
Write-Host "========================================" -ForegroundColor Green
Write-Host ""

python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
