# PowerShell script to start the GraphTrace Python backend
# Usage: .\start-backend.ps1

Write-Host "Starting GraphTrace Backend Server..." -ForegroundColor Green

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
$repoRoot = $PSScriptRoot
$venvPath = Join-Path $repoRoot ".venv"
$venvPython = Join-Path $venvPath "Scripts\python.exe"
$venvActivate = Join-Path $venvPath "Scripts\Activate.ps1"

if (-not (Test-Path $venvPath)) {
    Write-Host "Creating virtual environment at $venvPath" -ForegroundColor Yellow
    python -m venv $venvPath
}

Write-Host "Activating virtual environment..." -ForegroundColor Yellow
& $venvActivate

# Navigate to backend directory
Set-Location -Path "$repoRoot\agentic-restored\python_backend"

# Check if .env file exists
if (-not (Test-Path ".env")) {
    Write-Host "Note: .env file not found (OK). You can configure integrations in the UI." -ForegroundColor Yellow
    Write-Host "Example .env contents:" -ForegroundColor Yellow
    Write-Host "DATABASE_URL=postgresql://postgres:password@127.0.0.1:5432/graphtrace" -ForegroundColor Cyan
    Write-Host "NEO4J_URI=neo4j+s://your-instance.databases.neo4j.io" -ForegroundColor Cyan
    Write-Host "NEO4J_USER=neo4j" -ForegroundColor Cyan
    Write-Host "NEO4J_PASSWORD=your-password" -ForegroundColor Cyan
    Write-Host ""
}

# Install/upgrade dependencies
Write-Host "Installing/updating dependencies..." -ForegroundColor Yellow
& $venvPython -m pip install --upgrade pip
& $venvPython -m pip install -r requirements.txt

# Ensure encryption key exists for DB-backed encrypted configuration.
# Load from key file if available, otherwise generate and persist.
$keyFile = Join-Path (Get-Location) ".graphtrace.encryption_key"
if (-not $env:GRAPH_TRACE_CONFIG_ENCRYPTION_KEY) {
    if (Test-Path $keyFile) {
        $env:GRAPH_TRACE_CONFIG_ENCRYPTION_KEY = (Get-Content $keyFile -Raw).Trim()
        Write-Host "Loaded GRAPH_TRACE_CONFIG_ENCRYPTION_KEY from $keyFile" -ForegroundColor Yellow
    } else {
        try {
            $key = & $venvPython -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
            $env:GRAPH_TRACE_CONFIG_ENCRYPTION_KEY = $key.Trim()
            Set-Content -Path $keyFile -Value $env:GRAPH_TRACE_CONFIG_ENCRYPTION_KEY -Encoding ASCII
            Write-Host "Generated and saved GRAPH_TRACE_CONFIG_ENCRYPTION_KEY to $keyFile" -ForegroundColor Yellow
        } catch {
            Write-Host "Warning: could not generate GRAPH_TRACE_CONFIG_ENCRYPTION_KEY (cryptography missing?)." -ForegroundColor Yellow
            Write-Host "Set GRAPH_TRACE_CONFIG_ENCRYPTION_KEY manually for encrypted DB config." -ForegroundColor Yellow
        }
    }
}

# Ensure DB schema exists and seed default configuration.
try {
    & $venvPython -m scripts.init_db_schema
} catch {
    Write-Host "Warning: DB schema/seed step failed (non-fatal): $($_.Exception.Message)" -ForegroundColor Yellow
}

# Set PYTHONPATH
$env:PYTHONPATH = "$PSScriptRoot\agentic-restored\python_backend"

# Start the server
Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "Starting FastAPI server on port 8011..." -ForegroundColor Green
Write-Host "API Documentation: http://localhost:8011/docs" -ForegroundColor Cyan
Write-Host "Press Ctrl+C to stop the server" -ForegroundColor Yellow
Write-Host "========================================" -ForegroundColor Green
Write-Host ""

& $venvPython -m uvicorn main:app --host 0.0.0.0 --port 8011 --reload
