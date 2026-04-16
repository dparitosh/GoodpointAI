#requires -Version 5.1

[CmdletBinding()]
param(
  [string]$BaseUrl = "http://127.0.0.1:8011",
  [string]$WorkflowId = "wf_demo_001",
  [int]$TimeoutSec = 10
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

Write-Host "Backend smoke test against $BaseUrl" -ForegroundColor Cyan

try {
  $health = Invoke-Json -Method GET -Url "$BaseUrl/health"
  Write-Host "OK  /health => $($health.status)" -ForegroundColor Green
} catch {
  Write-Host "ERR /health failed: $($_.Exception.Message)" -ForegroundColor Red
  Write-Host "Tip: If you see '>>>', you're inside Python REPL. Exit with exit() then re-run this script in PowerShell." -ForegroundColor Yellow
  exit 1
}

try {
  $payload = @{ action = "start"; execution_params = @{} }
  $exec = Invoke-Json -Method POST -Url "$BaseUrl/api/workflows/$WorkflowId/execute" -Body $payload
  $status = if ($exec.status) { $exec.status } else { "ok" }
  Write-Host "OK  POST /api/workflows/$WorkflowId/execute (start) => $status" -ForegroundColor Green
} catch {
  Write-Host "ERR workflow start failed: $($_.Exception.Message)" -ForegroundColor Red
  exit 1
}

Write-Host "Done." -ForegroundColor Cyan
