# PowerShell script to start ETL Orchestrator Agent Service
# Usage: .\start-agent-etl-orchestrator.ps1

$scriptDir = $PSScriptRoot
$repoRoot = Split-Path $scriptDir -Parent
Set-Location "$repoRoot"

Write-Host "Starting ETL Orchestrator Agent Service..." -ForegroundColor Cyan

$env:PYTHONPATH = "$repoRoot"
$env:GRAPH_TRACE_LOAD_DOTENV = "true"

$venvPython = Join-Path $repoRoot ".venv" "Scripts" "python.exe"
if (-not (Test-Path $venvPython)) { $venvPython = "python" }

try {
    & $venvPython -m agent_services.etl_orchestrator.main
}
catch {
    Write-Host "Error starting ETL Agent: $_" -ForegroundColor Red
    Read-Host "Press Enter to exit..."
}
