# PowerShell script to start the GraphTrace React frontend
# Usage: .\start-frontend.ps1

Write-Host "Starting GraphTrace Frontend..." -ForegroundColor Green

# Check if Node.js is installed
if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
    Write-Host "Error: Node.js is not installed or not in PATH" -ForegroundColor Red
    Write-Host "Please install Node.js from https://nodejs.org/" -ForegroundColor Yellow
    exit 1
}

# Check if npm is installed
if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
    Write-Host "Error: npm is not installed or not in PATH" -ForegroundColor Red
    exit 1
}

# Display Node and npm versions
Write-Host "Node version: $(node --version)" -ForegroundColor Cyan
Write-Host "npm version: $(npm --version)" -ForegroundColor Cyan
Write-Host ""

# Navigate to frontend directory
Set-Location -Path "$PSScriptRoot\agentic-restored\e2etraceapp"

# Check if .env file exists
if (-not (Test-Path ".env")) {
    Write-Host "Note: .env file not found (OK). Using default settings." -ForegroundColor Yellow
}

# Check if node_modules exists
if (-not (Test-Path "node_modules")) {
    Write-Host "node_modules not found. Installing dependencies..." -ForegroundColor Yellow
    npm install
} else {
    Write-Host "Checking for dependency updates..." -ForegroundColor Yellow
    npm install
}

# Start the development server
Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "Starting Vite dev server..." -ForegroundColor Green
Write-Host "Frontend will be available at: http://localhost:5173" -ForegroundColor Cyan
Write-Host "Press Ctrl+C to stop the server" -ForegroundColor Yellow
Write-Host "========================================" -ForegroundColor Green
Write-Host ""

npm run dev
