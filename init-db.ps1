# GraphTrace Database Initialization and Seeding Script
# This script ensures the database schema is created and populated with necessary default data for the UI and API.

$ErrorActionPreference = 'Stop'
$root = Get-Location
$backendPath = Join-Path $root "python_backend"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  GraphTrace Database Initialization" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

if (-not (Test-Path $backendPath)) {
    Write-Host "ERROR: python_backend folder not found at $backendPath" -ForegroundColor Red
    exit 1
}

Push-Location $backendPath

try {
    # 1. Environment and Venv Check
    if (-not (Test-Path "venv")) {
        Write-Host "Creating virtual environment..." -ForegroundColor Yellow
        python -m venv venv
    }
    
    Write-Host "Activating virtual environment..." -ForegroundColor Gray
    & ".\venv\Scripts\Activate.ps1"
    
    # 2. Set environment variables
    $env:GRAPH_TRACE_LOAD_DOTENV = "true"
    
    # Check for encryption key
    $keyFile = Join-Path $backendPath ".graphtrace.encryption_key"
    if (-not $env:GRAPH_TRACE_CONFIG_ENCRYPTION_KEY) {
        if (Test-Path $keyFile) {
            $env:GRAPH_TRACE_CONFIG_ENCRYPTION_KEY = (Get-Content $keyFile -Raw).Trim()
            Write-Host "Loaded encryption key from file." -ForegroundColor Gray
        } else {
            Write-Host "Generating new encryption key..." -ForegroundColor Yellow
            python -m pip install cryptography --quiet
            $key = python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
            $env:GRAPH_TRACE_CONFIG_ENCRYPTION_KEY = "$key".Trim()
            Set-Content -Path $keyFile -Value $env:GRAPH_TRACE_CONFIG_ENCRYPTION_KEY -Encoding ASCII
        }
    }

    # 3. Initialize Schema and Basic Config
    Write-Host "`n[1/4] Initializing Database Schema..." -ForegroundColor Yellow
    python -m scripts.init_db_schema
    if ($LASTEXITCODE -ne 0) { throw "Schema initialization failed." }
    Write-Host "  OK: Schema initialized." -ForegroundColor Green

    # 4. Seed Admin Configurations (LLM, Providers, etc.)
    # This is critical for the UI to show available providers
    Write-Host "`n[2/4] Seeding Admin Configurations (LLM, Providers)..." -ForegroundColor Yellow
    python -m scripts.seed_admin_configs
    if ($LASTEXITCODE -ne 0) { throw "Admin configuration seeding failed." }
    Write-Host "  OK: Admin configurations seeded." -ForegroundColor Green

    # 5. Seed Pipeline Configurations (Templates, File Patterns)
    # This is required for creating new extraction pipelines
    Write-Host "`n[3/4] Seeding Pipeline Configurations..." -ForegroundColor Yellow
    python -m scripts.seed_pipeline_configs --force
    if ($LASTEXITCODE -ne 0) { throw "Pipeline configuration seeding failed." }
    Write-Host "  OK: Pipeline configurations seeded." -ForegroundColor Green

    # 6. Unstructured workflows / OpenSearch / Neo4j seeding is OPTIONAL.
    # It depends on external services and can time out in deployment environments.
    Write-Host "`n[4/4] Skipping Unstructured Workflow seeding (optional)" -ForegroundColor Gray
    Write-Host "      To include it, run: cd python_backend; .\venv\Scripts\Activate.ps1; python -m scripts.seed_unstructured_workflows --workflows-only" -ForegroundColor Gray

    Write-Host "`n========================================" -ForegroundColor Green
    Write-Host "  Database Initialization Complete!" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Green
    Write-Host "You can now start the backend server." -ForegroundColor Gray
}
catch {
    Write-Host "`n========================================" -ForegroundColor Red
    Write-Host "  DATABASE INITIALIZATION FAILED" -ForegroundColor Red
    Write-Host "========================================" -ForegroundColor Red
    Write-Host "Error: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "`nPlease ensure PostgreSQL is running and your .env credentials are correct." -ForegroundColor Yellow
}
finally {
    Pop-Location
}
