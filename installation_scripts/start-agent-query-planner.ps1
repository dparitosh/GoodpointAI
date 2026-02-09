# PowerShell script to start Query Planner Agent Service
# Usage: .\start-agent-query-planner.ps1

$scriptDir = $PSScriptRoot
$repoRoot = Split-Path $scriptDir -Parent
Set-Location "$repoRoot"

Write-Host "Starting Query Planner Agent Service..." -ForegroundColor Cyan

$env:PYTHONPATH = "$repoRoot"
$env:GRAPH_TRACE_LOAD_DOTENV = "true"

$venvPython = Join-Path $repoRoot ".venv" "Scripts" "python.exe"
if (-not (Test-Path $venvPython)) { $venvPython = "python" }

try {
    & $venvPython -m agent_services.query_planner.main
}
catch {
    Write-Host "Error starting Query Planner Agent: $_" -ForegroundColor Red
    Read-Host "Press Enter to exit..."
}
