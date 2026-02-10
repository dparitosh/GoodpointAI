# PowerShell script to start Data Analyst Agent Service
# Usage: .\start-agent-data-analyst.ps1

$scriptDir = $PSScriptRoot
$repoRoot = Split-Path $scriptDir -Parent
Set-Location "$repoRoot"

Write-Host "Starting Data Analyst Agent Service..." -ForegroundColor Cyan

# Set PYTHONPATH to include project root so we can import 'agent_services' and 'python_backend'
$env:PYTHONPATH = "$repoRoot"
$env:GRAPH_TRACE_LOAD_DOTENV = "true"

$venvPython = Join-Path (Join-Path (Join-Path $repoRoot ".venv") "Scripts") "python.exe"
if (-not (Test-Path $venvPython)) { $venvPython = "python" }

try {
    # Run the agent service using the venv Python
    & $venvPython -m agent_services.data_analyst.main
}
catch {
    Write-Host "Error starting Data Analyst Agent: $_" -ForegroundColor Red
    Read-Host "Press Enter to exit..."
}
