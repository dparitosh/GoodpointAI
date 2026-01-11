$ErrorActionPreference = 'Stop'
$root = (Resolve-Path "$PSScriptRoot\..\..").Path

Write-Host "Backend diagnostics" -ForegroundColor Green

Push-Location "$root\python_backend"
try {
  if (Test-Path "venv\Scripts\Activate.ps1") { & ".\venv\Scripts\Activate.ps1" }
  python -m scripts.diagnose_db_config

  foreach ($port in @(8000, 8011)) {
    try {
      $runtime = Invoke-WebRequest -UseBasicParsing -TimeoutSec 5 "http://127.0.0.1:$port/api/config/runtime"
      Write-Host "Runtime OK (port $port): HTTP $($runtime.StatusCode)" -ForegroundColor Cyan

      $health = Invoke-WebRequest -UseBasicParsing -TimeoutSec 5 "http://127.0.0.1:$port/health"
      Write-Host "Health OK (port $port): HTTP $($health.StatusCode)" -ForegroundColor Cyan
    } catch {
      Write-Host "Skipping port $port (not GraphTrace backend or not running)" -ForegroundColor Yellow
    }
  }
} finally {
  Pop-Location
}
