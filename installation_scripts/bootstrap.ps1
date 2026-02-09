Param(
  [switch]$SkipFrontend,
  [switch]$SkipBackend,
  [switch]$RunDiagnostics
)

$ErrorActionPreference = 'Stop'

function Assert-Command($name, $hint) {
  if (-not (Get-Command $name -ErrorAction SilentlyContinue)) {
    Write-Host "Missing required command: $name" -ForegroundColor Red
    Write-Host $hint -ForegroundColor Yellow
    exit 1
  }
}

Write-Host "GraphTrace bootstrap (Windows)" -ForegroundColor Green

Assert-Command python "Install Python 3.11+ and ensure it's on PATH."
Assert-Command node "Install Node.js 18+ (includes npm)."
Assert-Command npm "Install Node.js 18+ (includes npm)."

$root = Split-Path $PSScriptRoot -Parent

# Keep a single shared venv at repo root so VS Code tasks and scripts run against
# the same interpreter and installed packages.
$venvPath = Join-Path $root ".venv"
$venvPython = Join-Path $venvPath "Scripts\python.exe"
$venvActivate = Join-Path $venvPath "Scripts\Activate.ps1"

function Ensure-Venv() {
  if (-not (Test-Path $venvPath)) {
    Write-Host "Creating virtual environment at $venvPath" -ForegroundColor Yellow
    python -m venv $venvPath
  }

  & $venvActivate

  if (-not (Test-Path $venvPython)) {
    Write-Host "ERROR: venv python not found at $venvPython" -ForegroundColor Red
    exit 1
  }
}

if (-not $SkipBackend) {
  Write-Host "[1/3] Backend: venv + deps + DB schema + seed" -ForegroundColor Cyan
  Ensure-Venv
  Push-Location "$root\python_backend"
  try {
    & $venvPython -m pip install --upgrade pip
    & $venvPython -m pip install -r requirements.txt

    $keyFile = Join-Path (Get-Location) ".graphtrace.encryption_key"
    if (-not $env:GRAPH_TRACE_CONFIG_ENCRYPTION_KEY) {
      if (Test-Path $keyFile) {
        $env:GRAPH_TRACE_CONFIG_ENCRYPTION_KEY = (Get-Content $keyFile -Raw).Trim()
        Write-Host "Loaded GRAPH_TRACE_CONFIG_ENCRYPTION_KEY from $keyFile" -ForegroundColor Yellow
      }
    }

    if (-not $env:GRAPH_TRACE_CONFIG_ENCRYPTION_KEY) {
      $key = $null
      try {
        $key = python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())" 2>$null
      } catch {
        $key = $null
      }

      if (-not $key -or $LASTEXITCODE -ne 0) {
        Write-Host "cryptography not available yet; installing cryptography..." -ForegroundColor Yellow
        python -m pip install cryptography
        $key = python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
      }

      if ($key) {
        $env:GRAPH_TRACE_CONFIG_ENCRYPTION_KEY = "$key".Trim()
        Set-Content -Path $keyFile -Value $env:GRAPH_TRACE_CONFIG_ENCRYPTION_KEY -Encoding ASCII
        Write-Host "Generated and saved GRAPH_TRACE_CONFIG_ENCRYPTION_KEY to $keyFile" -ForegroundColor Yellow
      } else {
        Write-Host "ERROR: Could not generate GRAPH_TRACE_CONFIG_ENCRYPTION_KEY." -ForegroundColor Red
        Write-Host "Set GRAPH_TRACE_CONFIG_ENCRYPTION_KEY and re-run bootstrap." -ForegroundColor Yellow
        exit 1
      }
    }

    & $venvPython -m scripts.init_db_schema
  }
  finally {
    Pop-Location
  }
}

if (-not $SkipFrontend) {
  Write-Host "[2/3] Frontend: npm install" -ForegroundColor Cyan
  Push-Location "$root\e2etraceapp"
  try {
    npm install
  }
  finally {
    Pop-Location
  }
}

if ($RunDiagnostics) {
  Write-Host "[3/3] Diagnostics" -ForegroundColor Cyan
  & "$root\diagnostics\windows\diagnose-all.ps1"
}

Write-Host "Bootstrap complete." -ForegroundColor Green
Write-Host "Next: .\start-all.ps1" -ForegroundColor Cyan
