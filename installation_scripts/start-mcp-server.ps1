# PowerShell script to start the GraphTrace MCP Server
# Usage: .\start-mcp-server.ps1

Write-Host "Starting GraphTrace MCP Server..." -ForegroundColor Green

# Opt into repo-local `.env` loading for local development.
if (-not $env:GRAPH_TRACE_LOAD_DOTENV) {
    $env:GRAPH_TRACE_LOAD_DOTENV = "true"
}

# Check if Python is installed
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host "Error: Python is not installed or not in PATH" -ForegroundColor Red
    exit 1
}

# Use repo-root .venv so VS Code tasks and scripts share one environment.
$repoRoot = Split-Path $PSScriptRoot -Parent
$venvPath = Join-Path $repoRoot ".venv"
$venvPython = Join-Path $venvPath "Scripts\python.exe"
$venvActivate = Join-Path $venvPath "Scripts\Activate.ps1"

if (-not (Test-Path $venvPath)) {
    Write-Host "Virtual environment not found. Please run bootstrap.ps1 first." -ForegroundColor Red
    exit 1
}

Write-Host "Activating virtual environment..." -ForegroundColor Yellow
& $venvActivate

# Navigate to repo root
Set-Location -Path "$repoRoot"

# Start the server
Write-Host "Starting MCP Server on port 8012..." -ForegroundColor Green
$env:PYTHONPATH = "$repoRoot"
& $venvPython -m mcp_server.main
