# PowerShell script to start the GraphTrace Python backend
# Usage: .\.\start-backend.ps1
#
# If you encounter "script execution is disabled" error, use:
#   powershell -ExecutionPolicy Bypass -File .\.\.\start-backend.ps1
#
# For production/customer environments, set POSTGRES_* environment variables:
#   $env:POSTGRES_HOST = "your-host"
#   $env:POSTGRES_PORT = "5432"
#   $env:POSTGRES_USER = "postgres"
#   $env:POSTGRES_PASSWORD = "password"
#   $env:POSTGRES_DATABASE = "graphtrace"

Set-ExecutionPolicy -ExecutionPolicy Bypass -Scope Process -Force

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
    Write-Host "Note: .env file not found (OK). You can configure integrations in the UI." -ForegroundColor Yellow
    Write-Host "Example .env contents:" -ForegroundColor Yellow
    Write-Host "" -ForegroundColor Yellow
    Write-Host "# PostgreSQL configuration (use POSTGRES_* for flexibility):" -ForegroundColor Cyan
    Write-Host "POSTGRES_HOST=localhost" -ForegroundColor Cyan
    Write-Host "POSTGRES_PORT=5432" -ForegroundColor Cyan
    Write-Host "POSTGRES_USER=postgres" -ForegroundColor Cyan
    Write-Host "POSTGRES_PASSWORD=your_password" -ForegroundColor Cyan
    Write-Host "" -ForegroundColor Yellow
    Write-Host "# Optional integrations:" -ForegroundColor Cyan
    Write-Host "NEO4J_URI=neo4j+s://your-instance.databases.neo4j.io" -ForegroundColor Cyan
    Write-Host "NEO4J_USER=neo4j" -ForegroundColor Cyan
    Write-Host "NEO4J_PASSWORD=your-password" -ForegroundColor Cyan
    Write-Host "GRAPH_TRACE_ALLOWED_LOCAL_ROOTS=D:\\path\\to\\your\\import\\folder" -ForegroundColor Cyan
    Write-Host "" -ForegroundColor Yellow
    Write-Host "See: POSTGRESQL_CONNECTION_TROUBLESHOOTING.md for detailed config" -ForegroundColor Yellow
}

# Install/upgrade dependencies
Write-Host "Installing/updating dependencies..." -ForegroundColor Yellow
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

# Ensure encryption key exists for DB-backed encrypted configuration.
# We prefer an explicit session env var so .env is not required for installs.
if (-not $env:GRAPH_TRACE_CONFIG_ENCRYPTION_KEY) {
    try {
        $key = python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
        $env:GRAPH_TRACE_CONFIG_ENCRYPTION_KEY = $key.Trim()
        Write-Host "Generated GRAPH_TRACE_CONFIG_ENCRYPTION_KEY for this session." -ForegroundColor Yellow
    } catch {
        Write-Host "Warning: could not generate GRAPH_TRACE_CONFIG_ENCRYPTION_KEY (cryptography missing?)." -ForegroundColor Yellow
        Write-Host "Set GRAPH_TRACE_CONFIG_ENCRYPTION_KEY manually for encrypted DB config." -ForegroundColor Yellow
    }
}

# Ensure DB schema exists and seed default configuration.
try {
    python -m scripts.init_db_schema
} catch {
    Write-Host "Warning: DB schema/seed step failed (non-fatal): $($_.Exception.Message)" -ForegroundColor Yellow
}

# Set PYTHONPATH
$env:PYTHONPATH = "$PSScriptRoot\python_backend"

# Show PostgreSQL configuration
Write-Host "" -ForegroundColor White
Write-Host "PostgreSQL Configuration:" -ForegroundColor Yellow
Write-Host "  POSTGRES_HOST: $(if ($env:POSTGRES_HOST) { $env:POSTGRES_HOST } else { 'localhost (default)' })" -ForegroundColor Cyan
Write-Host "  POSTGRES_PORT: $(if ($env:POSTGRES_PORT) { $env:POSTGRES_PORT } else { '5432 (default)' })" -ForegroundColor Cyan
Write-Host "  POSTGRES_USER: $(if ($env:POSTGRES_USER) { $env:POSTGRES_USER } else { 'postgres (default)' })" -ForegroundColor Cyan
Write-Host "  POSTGRES_DATABASE: $(if ($env:POSTGRES_DATABASE) { $env:POSTGRES_DATABASE } else { 'graphtrace (default)' })" -ForegroundColor Cyan

# Start the server
Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "Starting FastAPI server on port 8011..." -ForegroundColor Green
Write-Host "API Documentation: http://localhost:8011/docs" -ForegroundColor Cyan
Write-Host "Health Check: http://localhost:8011/health" -ForegroundColor Cyan
Write-Host "Press Ctrl+C to stop the server" -ForegroundColor Yellow
Write-Host "========================================" -ForegroundColor Green
Write-Host ""

python -m uvicorn main:app --host 0.0.0.0 --port 8011 --reload
