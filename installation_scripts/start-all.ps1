# PowerShell script to start both frontend and backend services
# Usage: .\start-all.ps1

Write-Host "Starting GraphTrace Full Stack Application..." -ForegroundColor Green
Write-Host ""

# Get script directory
$scriptDir = $PSScriptRoot

# Clean up existing processes first
if (Test-Path "$scriptDir\stop-all.ps1") {
    Write-Host "Cleaning up existing processes..." -ForegroundColor Yellow
    & "$scriptDir\stop-all.ps1"
} else {
    Write-Host "Warning: stop-all.ps1 not found, skipping cleanup." -ForegroundColor Yellow
}

# Start backend in a new PowerShell window
Write-Host "Starting Backend Server..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-File", "$scriptDir\start-backend.ps1"

# Start MCP Server in a new PowerShell window
Write-Host "Starting MCP Server..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-File", "$scriptDir\start-mcp-server.ps1"

# Start Data Analyst Agent in a new PowerShell window
Write-Host "Starting Data Analyst Agent..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-File", "$scriptDir\start-agent-data-analyst.ps1"

# Start ETL Orchestrator Agent in a new PowerShell window
Write-Host "Starting ETL Orchestrator Agent..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-File", "$scriptDir\start-agent-etl-orchestrator.ps1"

# Start Visualization Agent in a new PowerShell window
Write-Host "Starting Visualization Agent..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-File", "$scriptDir\start-agent-visualization.ps1"

# Start Query Planner Agent in a new PowerShell window
Write-Host "Starting Query Planner Agent..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-File", "$scriptDir\start-agent-query-planner.ps1"

# Start Quality Monitor Agent in a new PowerShell window
Write-Host "Starting Quality Monitor Agent..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-File", "$scriptDir\start-agent-quality-monitor.ps1"

# Start Chat Coordinator Agent in a new PowerShell window
Write-Host "Starting Chat Coordinator Agent..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-File", "$scriptDir\start-agent-chat-coordinator.ps1"

# Wait a bit for backend to start
Write-Host "Waiting for servers to initialize..." -ForegroundColor Yellow
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
