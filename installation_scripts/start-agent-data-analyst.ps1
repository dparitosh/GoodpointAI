# PowerShell script to start Data Analyst Agent Service
# Usage: .\start-agent-data-analyst.ps1

$scriptDir = $PSScriptRoot
$repoRoot = Split-Path $scriptDir -Parent
Set-Location "$repoRoot"

Write-Host "Starting Data Analyst Agent Service..." -ForegroundColor Cyan

# Set PYTHONPATH to include project root so we can import 'agent_services' and 'python_backend'
$env:PYTHONPATH = "$repoRoot"
$env:GRAPH_TRACE_LOAD_DOTENV = "true"

# Ensure we are using the python from the environment
# Adjust this if using a specific venv
# python agent_services/data_analyst/main.py

try {
    # Run the agent service
    # We use python -m agent_services.data_analyst.main to resolve imports cleanly
    python -m agent_services.data_analyst.main
}
catch {
    Write-Host "Error starting Data Analyst Agent: $_" -ForegroundColor Red
    Read-Host "Press Enter to exit..."
}
