# PowerShell script to stop all GraphTrace services (Python and Node.js)
# Usage: .\stop-all.ps1

Write-Host "Stopping GraphTrace Services..." -ForegroundColor Yellow

# Stop Python processes (Backend + MCP Server)
$python_procs = Get-Process python -ErrorAction SilentlyContinue
if ($python_procs) {
    Write-Host "Stopping $($python_procs.Count) Python process(es)..." -ForegroundColor Cyan
    Stop-Process -Name python -Force -ErrorAction SilentlyContinue
} else {
    Write-Host "No Python processes found." -ForegroundColor DarkGray
}

# Stop Node.js processes (Frontend / Vite)
$node_procs = Get-Process node -ErrorAction SilentlyContinue
if ($node_procs) {
    Write-Host "Stopping $($node_procs.Count) Node.js process(es)..." -ForegroundColor Cyan
    Stop-Process -Name node -Force -ErrorAction SilentlyContinue
} else {
    Write-Host "No Node.js processes found." -ForegroundColor DarkGray
}

# Stop uvicorn if running as separate executable (rare on Windows but possible)
$uvicorn_procs = Get-Process uvicorn -ErrorAction SilentlyContinue
if ($uvicorn_procs) {
    Write-Host "Stopping uvicorn process(es)..." -ForegroundColor Cyan
    Stop-Process -Name uvicorn -Force -ErrorAction SilentlyContinue
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "All GraphTrace services have been stopped." -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
