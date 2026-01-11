$ErrorActionPreference = 'Stop'
$root = (Resolve-Path "$PSScriptRoot\..\..").Path

Write-Host "Frontend diagnostics" -ForegroundColor Green

Push-Location "$root\e2etraceapp"
try {
  npm test --silent -- --run

  try {
    $resp = Invoke-WebRequest -UseBasicParsing -TimeoutSec 5 http://localhost:5173/
    Write-Host "Frontend reachable: HTTP $($resp.StatusCode)" -ForegroundColor Cyan
  } catch {
    Write-Host "Frontend check skipped/failed (dev server not running?): $($_.Exception.Message)" -ForegroundColor Yellow
  }
} finally {
  Pop-Location
}
