$ErrorActionPreference = 'Continue'
$root = (Resolve-Path "$PSScriptRoot\..\..").Path

Write-Host "Apache diagnostics (optional)" -ForegroundColor Green

if (-not (Get-Command httpd -ErrorAction SilentlyContinue)) {
  Write-Host "Apache httpd not found on PATH. Install Apache HTTP Server and add httpd.exe to PATH." -ForegroundColor Yellow
  exit 0
}

httpd -v

$conf = "$root\apache\graphtrace-httpd.conf"
if (Test-Path $conf) {
  Write-Host "Validating syntax for $conf" -ForegroundColor Cyan
  httpd -t -f $conf
} else {
  Write-Host "No sample config found at $conf" -ForegroundColor Yellow
}
