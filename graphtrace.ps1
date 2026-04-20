#requires -Version 5.1

[CmdletBinding()]
Param(
    [switch]$Check,
    [switch]$Start
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

if ($Start -or (-not $Check)) {
    # Check diagnostics quickly before starting
    & $venvPython "$repoRoot\scripts\diagnostics.py"
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Please fix diagnostic errors above before starting!" -ForegroundColor Yellow
        exit 1
    }
    
    Write-Host "Launching full UI+API stack..." -ForegroundColor Green
    & $venvPython "$repoRoot\scripts\start.py"
}

