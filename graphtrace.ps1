Param(
    [switch]$Check,
    [switch]$Start
)

$scriptDir = $PSScriptRoot
$repoRoot = $scriptDir

# Fallback pathing in case script run from elsewhere
if (Test-Path "$scriptDir\scripts\start.py") {
    $repoRoot = $scriptDir
}

$venvPython = Join-Path (Join-Path (Join-Path $repoRoot ".venv") "Scripts") "python.exe"

if (-not (Test-Path $venvPython)) {
    Write-Host "Virtual environment not found! Please run python -m venv .venv and pip install -r requirements.txt" -ForegroundColor Red
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

