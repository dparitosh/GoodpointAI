$ErrorActionPreference = 'Continue'

Write-Host "GraphTrace diagnostics (Windows)" -ForegroundColor Green

$root = (Resolve-Path "$PSScriptRoot\..\..").Path

function Show-Section($name) {
  Write-Host ""; Write-Host "== $name ==" -ForegroundColor Cyan
}

function Try-Run($label, $script) {
  try {
    Write-Host "- $label" -ForegroundColor Gray
    & $script
  } catch {
    Write-Host "  FAIL: $($_.Exception.Message)" -ForegroundColor Red
  }
}

Show-Section "Tooling"
Try-Run "Python" { python --version }
Try-Run "Node" { node --version }
Try-Run "npm" { npm --version }

Show-Section "Backend DB / Config"
Try-Run "DB/config checks" {
  Push-Location "$root\python_backend"
  try {
    if (Test-Path "venv\Scripts\Activate.ps1") { & ".\venv\Scripts\Activate.ps1" }
    python -m scripts.diagnose_db_config
  } finally { Pop-Location }
}

Show-Section "Backend HTTP (if running)"
foreach ($port in @(8000, 8011)) {
  try {
    $runtime = Invoke-WebRequest -UseBasicParsing -TimeoutSec 5 "http://127.0.0.1:$port/api/config/runtime"
    Write-Host "- Runtime config (port $port)" -ForegroundColor Gray
    Write-Host "  HTTP $($runtime.StatusCode)" -ForegroundColor Gray

    $health = Invoke-WebRequest -UseBasicParsing -TimeoutSec 5 "http://127.0.0.1:$port/health"
    Write-Host "- Health (port $port)" -ForegroundColor Gray
    Write-Host "  HTTP $($health.StatusCode)" -ForegroundColor Gray
  } catch {
    Write-Host "- Skipping port $port (not GraphTrace backend or not running)" -ForegroundColor Gray
  }
}

Show-Section "Frontend (if running)"
Try-Run "Frontend root" {
  $resp = Invoke-WebRequest -UseBasicParsing -TimeoutSec 5 http://localhost:5173/
  Write-Host "  HTTP $($resp.StatusCode)" -ForegroundColor Gray
}

Show-Section "Apache (optional)"
if (Get-Command httpd -ErrorAction SilentlyContinue) {
  Try-Run "Apache httpd version" { httpd -v }
  Try-Run "Apache config syntax (if conf exists)" {
    $conf = "$root\apache\graphtrace-httpd.conf"
    if (Test-Path $conf) {
      httpd -t -f $conf
    } else {
      Write-Host "  (no apache\graphtrace-httpd.conf found)" -ForegroundColor Gray
    }
  }
} else {
  Write-Host "- Apache not installed (skipped)" -ForegroundColor Gray
}

Write-Host ""; Write-Host "Diagnostics complete." -ForegroundColor Green
