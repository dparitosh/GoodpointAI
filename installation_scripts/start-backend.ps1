Param(
    [switch]$UpdateDeps
)

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
$repoRoot = Split-Path $PSScriptRoot -Parent
$venvPath = Join-Path $repoRoot ".venv"
$venvPython = Join-Path $venvPath "Scripts\python.exe"
$venvActivate = Join-Path $venvPath "Scripts\Activate.ps1"

if (-not (Test-Path $venvPath)) {
    Write-Host "Creating virtual environment at $venvPath" -ForegroundColor Yellow
    python -m venv $venvPath
}

# Increase OpenSearch timeout to avoid startup/latency errors
if (-not $env:OPENSEARCH_TIMEOUT_S) {
    $env:OPENSEARCH_TIMEOUT_S = "30"
}

Write-Host "Activating virtual environment..." -ForegroundColor Yellow
& $venvActivate

# Navigate to backend directory
Set-Location -Path "$repoRoot\python_backend"

# Check if .env file exists and validate configuration
if (-not (Test-Path ".env")) {
    Write-Host "Running for first time? .env file not found." -ForegroundColor Yellow
    Write-Host "Please run '..\bootstrap.ps1' to set up the environment and create .env." -ForegroundColor Red
    exit 1
} else {
    $envContent = Get-Content ".env" -Raw
    if ($envContent -match "yourpassword" -or $envContent -match "postgresql://postgres:password@") {
        Write-Host ""
        Write-Host "CRITICAL CONFIGURATION REQUIRED:" -ForegroundColor Red -BackgroundColor Black
        Write-Host "You must edit python_backend\.env with your actual PostgreSQL credentials." -ForegroundColor Red
        Write-Host "Default placeholders ('yourpassword') are still present." -ForegroundColor Red
        Write-Host ""
        Write-Host "1. Open python_backend\.env" -ForegroundColor Yellow
        Write-Host "2. Set DATABASE_URL=postgresql://user:pass@host:port/dbname" -ForegroundColor Yellow
        Write-Host "3. Re-run start-backend.ps1" -ForegroundColor Yellow
        exit 1
    }
}

# Install/upgrade dependencies
if ($UpdateDeps) {
    Write-Host "Installing/updating dependencies..." -ForegroundColor Yellow
    & $venvPython -m pip install --upgrade pip
    & $venvPython -m pip install -r requirements.txt
} else {
    Write-Host "Skipping dependency check (run with -UpdateDeps to force)." -ForegroundColor Gray
}

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
$env:PYTHONPATH = "$repoRoot\python_backend"

# Determine Port from .env or default to 8011
$port = 8011
$envFile = "$repoRoot\.env"
if (Test-Path $envFile) {
    $envContent = Get-Content $envFile
    foreach ($line in $envContent) {
        if ($line -match "^PORT=(\d+)") {
            $port = $matches[1]
            Write-Host "Found PORT in .env: $port" -ForegroundColor Yellow
            break
        }
    }
}

# Start the server
Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "Starting FastAPI server on port $port..." -ForegroundColor Green
Write-Host "API Documentation: http://localhost:$port/docs" -ForegroundColor Cyan
Write-Host "Press Ctrl+C to stop the server" -ForegroundColor Yellow
Write-Host "========================================" -ForegroundColor Green
Write-Host ""

& $venvPython -m uvicorn main:app --host 0.0.0.0 --port $port --reload
