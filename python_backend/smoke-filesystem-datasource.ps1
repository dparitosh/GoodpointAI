#requires -Version 5.1

[CmdletBinding()]
param(
  [Parameter(Mandatory)] [string]$DataSourcePath,
  [string]$BaseUrl = "http://127.0.0.1:8011",
  [int]$TimeoutSec = 20,
  [string]$QualityScanTableName = "__filesystem_datasource_test__"
)

if ($PSVersionTable.PSVersion.Major -lt 5) {
  Write-Host "This script requires Windows PowerShell 5.1+ (or PowerShell 7+). Current: $($PSVersionTable.PSVersion)" -ForegroundColor Red
  exit 1
}

$ErrorActionPreference = "Stop"

function Invoke-Json {
  param(
    [Parameter(Mandatory)] [ValidateSet("GET","POST","PUT","DELETE")] [string]$Method,
    [Parameter(Mandatory)] [string]$Url,
    [object]$Body = $null
  )

  if ($null -ne $Body) {
    $json = $Body | ConvertTo-Json -Depth 10
    return Invoke-RestMethod -Method $Method -Uri $Url -ContentType "application/json" -Body $json -TimeoutSec $TimeoutSec
  }

  return Invoke-RestMethod -Method $Method -Uri $Url -TimeoutSec $TimeoutSec
}

Write-Host "Filesystem datasource smoke test" -ForegroundColor Cyan
Write-Host "BaseUrl: $BaseUrl" -ForegroundColor Cyan
Write-Host "DataSourcePath: $DataSourcePath" -ForegroundColor Cyan

# 1) Filesystem health
try {
  $fsHealth = Invoke-Json -Method GET -Url "$BaseUrl/api/filesystem/health"
  Write-Host "OK  GET /api/filesystem/health => $($fsHealth.status)" -ForegroundColor Green
} catch {
  Write-Host "ERR filesystem health failed: $($_.Exception.Message)" -ForegroundColor Red
  exit 1
}

# 2) Directory listing (accepts absolute paths)
try {
  $listPayload = @{ path = $DataSourcePath; recursive = $false }
  $list = Invoke-Json -Method POST -Url "$BaseUrl/api/filesystem/list" -Body $listPayload
  $count = if ($list.count) { $list.count } else { ($list.files | Measure-Object).Count }
  Write-Host "OK  POST /api/filesystem/list => $count entries" -ForegroundColor Green
} catch {
  Write-Host "ERR filesystem list failed: $($_.Exception.Message)" -ForegroundColor Red
  exit 1
}

# 3) Optional: deterministic quality scan using filesystem fallback (requires Postgres reachable)
try {
  $scanPayload = @{ data_source = $DataSourcePath }
  $scan = Invoke-Json -Method POST -Url "$BaseUrl/api/analytics/quality/scan/$QualityScanTableName" -Body $scanPayload
  Write-Host "OK  POST /api/analytics/quality/scan/$QualityScanTableName => $($scan.status) (scan_id=$($scan.scan_id))" -ForegroundColor Green
} catch {
  Write-Host "WARN quality scan failed (Postgres must be reachable for persistence): $($_.Exception.Message)" -ForegroundColor Yellow
}

Write-Host "Done." -ForegroundColor Cyan
