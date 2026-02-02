Param(
  [switch]$NoStop,
  [switch]$NoRemoveDeps,
  [switch]$ResetDatabase
)

$ErrorActionPreference = 'Continue'

Write-Host "GraphTrace clean reset (Windows)" -ForegroundColor Green
$root = $PSScriptRoot

function Stop-Port($port) {
  $conns = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique
  foreach ($pid in $conns) {
    try {
      Write-Host "Stopping process PID=$pid (port $port)" -ForegroundColor Yellow
      Stop-Process -Id $pid -Force
    } catch {
      Write-Host "Failed to stop PID=${pid}: $($_.Exception.Message)" -ForegroundColor DarkYellow
    }
  }
}

if (-not $NoStop) {
  Stop-Port 8000
  Stop-Port 8011
  Stop-Port 5173
}

Write-Host "Removing runtime artifacts..." -ForegroundColor Cyan

# Backend artifacts
Remove-Item -Force -Recurse -ErrorAction SilentlyContinue "$root\python_backend\__pycache__"
Remove-Item -Force -Recurse -ErrorAction SilentlyContinue "$root\python_backend\.pytest_cache"
Remove-Item -Force -Recurse -ErrorAction SilentlyContinue "$root\python_backend\logs"

# Remove backend runtime working data (uploads/exports/temp, etc.)
Remove-Item -Force -Recurse -ErrorAction SilentlyContinue "$root\python_backend\data"

# Frontend artifacts
Remove-Item -Force -Recurse -ErrorAction SilentlyContinue "$root\e2etraceapp\dist"
Remove-Item -Force -Recurse -ErrorAction SilentlyContinue "$root\e2etraceapp\.vite"

if (-not $NoRemoveDeps) {
  Write-Host "Removing dependencies (venv/node_modules)..." -ForegroundColor Cyan
  Remove-Item -Force -Recurse -ErrorAction SilentlyContinue "$root\python_backend\venv"
  Remove-Item -Force -Recurse -ErrorAction SilentlyContinue "$root\e2etraceapp\node_modules"
}

if ($ResetDatabase) {
  Write-Host "Resetting database schema (drop & recreate tables)..." -ForegroundColor Yellow
  Push-Location "$root\python_backend"
  try {
    if (Test-Path "venv\Scripts\Activate.ps1") {
      & ".\venv\Scripts\Activate.ps1"
      python -m scripts.reset_postgres_schema --yes
      python -m scripts.init_db_schema
    } else {
      Write-Host "  venv not found. Run bootstrap.ps1 first, then use:" -ForegroundColor Yellow
      Write-Host "    python -m scripts.reset_postgres_schema --yes" -ForegroundColor Cyan
      Write-Host "    python -m scripts.init_db_schema" -ForegroundColor Cyan
    }
  } finally {
    Pop-Location
  }
}

Write-Host ""
Write-Host "Clean reset complete." -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "  ./bootstrap.ps1           # Reinstall dependencies and init DB" -ForegroundColor White
Write-Host "  ./start-all.ps1           # Start frontend + backend" -ForegroundColor White
Write-Host ""
Write-Host "To also reset database, use: ./clean.ps1 -ResetDatabase" -ForegroundColor Yellow
