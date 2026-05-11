#requires -Version 5.1

[CmdletBinding()]
Param(
    [switch]$Check,
    [switch]$Start,
    [switch]$Reset,
    [switch]$Force   # Skip confirmation prompt for -Reset
)

if ($PSVersionTable.PSVersion.Major -lt 5) {
    Write-Host "This script requires Windows PowerShell 5.1+ (or PowerShell 7+). Current: $($PSVersionTable.PSVersion)" -ForegroundColor Red
    exit 1
}

$scriptDir = $PSScriptRoot
$repoRoot = $scriptDir

# Fallback pathing in case script run from elsewhere
if (Test-Path "$scriptDir\scripts\start.py") {
    $repoRoot = $scriptDir
}

$venvPython = Join-Path (Join-Path (Join-Path $repoRoot ".venv") "Scripts") "python.exe"

# Ensure relative paths in the Python scripts resolve correctly even if the user
# runs this script from a different working directory.
Set-Location $repoRoot

if (-not (Test-Path $venvPython)) {
    Write-Host "Virtual environment not found! Create it and install dependencies:" -ForegroundColor Red
    Write-Host "  1) python -m venv .venv" -ForegroundColor Red
    Write-Host "  2) .\.venv\Scripts\Activate.ps1" -ForegroundColor Red
    Write-Host "  3) pip install -r requirements.txt" -ForegroundColor Red
    Write-Host "  4) cd e2etraceapp; npm install" -ForegroundColor Red
    exit 1
}

if ($Check) {
    & $venvPython "$repoRoot\scripts\diagnostics.py"
    exit $LASTEXITCODE
}

if ($Reset) {
    Write-Host ""
    Write-Host "====================================" -ForegroundColor Red
    Write-Host "   GraphTrace Schema Reset" -ForegroundColor Red
    Write-Host "====================================" -ForegroundColor Red
    Write-Host "This will DROP all GraphTrace tables and recreate them empty." -ForegroundColor Yellow
    Write-Host "ALL DATA WILL BE LOST. This cannot be undone." -ForegroundColor Yellow
    Write-Host ""

    if (-not $Force) {
        $confirm = Read-Host "Type 'yes' to confirm reset"
        if ($confirm -ne 'yes') {
            Write-Host "Aborted." -ForegroundColor Cyan
            exit 0
        }
    }

    $backendDir = Join-Path $repoRoot "python_backend"
    $env:GRAPH_TRACE_LOAD_DOTENV = "true"

    Write-Host ""
    Write-Host "[1/2] Dropping and recreating all tables..." -ForegroundColor Cyan
    # run via Start-Process so cwd is python_backend (module resolution)
    $proc = Start-Process -FilePath $venvPython `
        -ArgumentList "-m", "scripts.reset_postgres_schema", "--yes", "--confirm-db", "graphtrace" `
        -WorkingDirectory $backendDir `
        -NoNewWindow -Wait -PassThru
    if ($proc.ExitCode -ne 0) {
        Write-Host "[FAIL] Schema reset failed. Check database connectivity and credentials." -ForegroundColor Red
        exit 1
    }

    Write-Host ""
    Write-Host "[2/2] Seeding fresh default configuration..." -ForegroundColor Cyan
    $proc2 = Start-Process -FilePath $venvPython `
        -ArgumentList "-m", "scripts.init_db_schema" `
        -WorkingDirectory $backendDir `
        -NoNewWindow -Wait -PassThru
    if ($proc2.ExitCode -ne 0) {
        Write-Host "[FAIL] Schema init failed after reset." -ForegroundColor Red
        exit 1
    }

    Write-Host ""
    Write-Host "====================================" -ForegroundColor Green
    Write-Host "   Reset Complete!" -ForegroundColor Green
    Write-Host "====================================" -ForegroundColor Green
    Write-Host "All tables have been recreated and seeded with defaults." -ForegroundColor Green
    Write-Host "Run '.\graphtrace.ps1 -Start' to launch the stack." -ForegroundColor Cyan
    exit 0
}

if ($Start -or (-not $Check -and -not $Reset)) {
    # Check diagnostics quickly before starting
    & $venvPython "$repoRoot\scripts\diagnostics.py"
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Please fix diagnostic errors above before starting!" -ForegroundColor Yellow
        exit 1
    }
    
    Write-Host "Launching full UI+API stack..." -ForegroundColor Green
    & $venvPython "$repoRoot\scripts\start.py"
}

