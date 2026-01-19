Param(
  [switch]$NoStop,
  [switch]$NoRemoveDeps
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

Write-Host "Clean reset complete." -ForegroundColor Green
Write-Host "Next: ./bootstrap.ps1 -RunDiagnostics" -ForegroundColor Cyan
