#!/usr/bin/env pwsh
#requires -Version 5.1
# Stop all GraphTrace services: frontend (Vite/Node), backend (uvicorn/Python), MCP server, agent services

[CmdletBinding()]
param(
    [switch]$Force   # Skip confirmation prompt
)

Write-Host "`nGraphTrace — Stop All Services`n" -ForegroundColor Cyan
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Gray

$stopped = 0

# ── Helper ──────────────────────────────────────────────────────────────────
function Stop-ByPort {
    param([int]$Port, [string]$Label)
    $conn = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    if ($conn) {
        $pid = $conn.OwningProcess | Select-Object -First 1
        $proc = Get-Process -Id $pid -ErrorAction SilentlyContinue
        if ($proc) {
            Write-Host "  Stopping $Label (PID $pid, port $Port)..." -ForegroundColor Yellow
            Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
            Write-Host "  OK: $Label stopped" -ForegroundColor Green
            return 1
        }
    }
    Write-Host "  $Label not running on port $Port" -ForegroundColor Gray
    return 0
}

# ── Frontend: Vite dev server (port 5173) ───────────────────────────────────
Write-Host "`nFrontend (Vite, port 5173):" -ForegroundColor White
$stopped += Stop-ByPort -Port 5173 -Label "Frontend/Vite"

# ── Backend: uvicorn (port 8011) ────────────────────────────────────────────
Write-Host "`nBackend (uvicorn, port 8011):" -ForegroundColor White
$stopped += Stop-ByPort -Port 8011 -Label "Backend/uvicorn"

# ── MCP Server (port 8012) ──────────────────────────────────────────────────
Write-Host "`nMCP Server (port 8012):" -ForegroundColor White
$stopped += Stop-ByPort -Port 8012 -Label "MCP Server"

# ── Agent services (ports 8020-8027) ────────────────────────────────────────
Write-Host "`nAgent Services (ports 8020-8027):" -ForegroundColor White
foreach ($port in 8020..8027) {
    $stopped += Stop-ByPort -Port $port -Label "Agent:$port"
}

# ── Summary ─────────────────────────────────────────────────────────────────
Write-Host "`n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Gray
if ($stopped -gt 0) {
    Write-Host "Stopped $stopped service(s).`n" -ForegroundColor Green
} else {
    Write-Host "No GraphTrace services were running.`n" -ForegroundColor Gray
}
