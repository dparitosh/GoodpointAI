# PowerShell script to start Quality Monitor Agent Service
# Usage: .\start-agent-quality-monitor.ps1

$scriptDir = $PSScriptRoot
$repoRoot = Split-Path $scriptDir -Parent
Set-Location "$repoRoot"

Write-Host "Starting Quality Monitor Agent Service..." -ForegroundColor Cyan

$env:PYTHONPATH = "$repoRoot"
$env:GRAPH_TRACE_LOAD_DOTENV = "true"

try {
    python -m agent_services.quality_monitor.main
}
catch {
    Write-Host "Error starting Quality Monitor Agent: $_" -ForegroundColor Red
    Read-Host "Press Enter to exit..."
}
