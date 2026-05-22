Param(
  [switch]$SkipFrontend,
  [switch]$SkipBackend,
  [switch]$RunDiagnostics
)

<#
.SYNOPSIS
    Automated bootstrap script for GraphTrace (Windows)
    
.DESCRIPTION
    This script automates the installation of GraphTrace backend and frontend.
    It is an alternative to the manual step-by-step installation in docs/INSTALLATION.md
    
    If you encounter pip errors (e.g., hash validation), use the manual installation method instead:
    - Reference: docs/INSTALLATION.md (Manual Installation section)
    - This involves manually running venv, pip install, and npm install commands
    
.NOTES
    Recommended: Use manual installation method (docs/INSTALLATION.md) for most reliable setup
    This bootstrap script is provided as a convenience for faster automated setup
#>

$ErrorActionPreference = 'Stop'

function Assert-Command($name, $hint) {
  if (-not (Get-Command $name -ErrorAction SilentlyContinue)) {
    Write-Host "Missing required command: $name" -ForegroundColor Red
    Write-Host $hint -ForegroundColor Yellow
    exit 1
  }
}

Write-Host "GraphTrace bootstrap (Windows)" -ForegroundColor Green
Write-Host "Alternative: Use manual installation (docs/INSTALLATION.md) for more reliable setup" -ForegroundColor Yellow

Assert-Command python "Install Python 3.10+ and ensure it's on PATH."
Assert-Command node "Install Node.js 18+ (includes npm)."
Assert-Command npm "Install Node.js 18+ (includes npm)."

$root = $PSScriptRoot

if (-not $SkipBackend) {
  Write-Host "[1/3] Backend: venv + deps + DB schema + seed" -ForegroundColor Cyan
  Push-Location "$root\python_backend"
  try {
    if (-not (Test-Path "venv")) {
      python -m venv venv
    }
    & ".\venv\Scripts\Activate.ps1"

    python -m pip install --upgrade pip
    python -m pip cache purge
    python -m pip install --no-cache-dir -r requirements.txt
    
    if ($LASTEXITCODE -ne 0) {
      Write-Host "ERROR: pip install failed" -ForegroundColor Red
      Write-Host "Fallback: Use manual installation method from docs/INSTALLATION.md" -ForegroundColor Yellow
      exit 1
    }

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

    python -m scripts.init_db_schema
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
