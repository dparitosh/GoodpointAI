# PowerShell script to start Visualization Agent Service
# Usage: .\start-agent-visualization.ps1

$scriptDir = $PSScriptRoot
$repoRoot = Split-Path $scriptDir -Parent
Set-Location "$repoRoot"

Write-Host "Starting Visualization Agent Service..." -ForegroundColor Cyan

$env:PYTHONPATH = "$repoRoot"
$env:GRAPH_TRACE_LOAD_DOTENV = "true"

try {
    python -m agent_services.visualization_agent.main
}
catch {
    Write-Host "Error starting Visualization Agent: $_" -ForegroundColor Red
    Read-Host "Press Enter to exit..."
}
