# PowerShell script to start Chat Coordinator Agent Service
# Usage: .\start-agent-chat-coordinator.ps1

$scriptDir = $PSScriptRoot
$repoRoot = Split-Path $scriptDir -Parent
Set-Location "$repoRoot"

Write-Host "Starting Chat Coordinator Agent Service..." -ForegroundColor Cyan

$env:PYTHONPATH = "$repoRoot"
$env:GRAPH_TRACE_LOAD_DOTENV = "true"

$venvPython = Join-Path (Join-Path (Join-Path $repoRoot ".venv") "Scripts") "python.exe"
if (-not (Test-Path $venvPython)) { $venvPython = "python" }

try {
    & $venvPython -m agent_services.chat_coordinator.main
}
catch {
    Write-Host "Error starting Chat Coordinator Agent: $_" -ForegroundColor Red
    Read-Host "Press Enter to exit..."
}
