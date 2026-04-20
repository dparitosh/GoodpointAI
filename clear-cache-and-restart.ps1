#!/usr/bin/env pwsh
# Clear all caches and restart frontend with correct UI

param(
    [switch]$SkipCacheClear
)

Write-Host "`n🧹 GraphTrace - Cache Clear & Restart`n" -ForegroundColor Cyan

# Navigate to e2etraceapp
Set-Location -Path "$PSScriptRoot\e2etraceapp"

if (-not $SkipCacheClear) {
    Write-Host "Step 1: Clearing Vite cache..." -ForegroundColor Yellow
    
    # Remove Vite cache directories
    if (Test-Path "node_modules\.vite") {
        Remove-Item -Recurse -Force "node_modules\.vite"
        Write-Host "  ✓ Removed node_modules\.vite" -ForegroundColor Green
    }
    
    if (Test-Path ".vite") {
        Remove-Item -Recurse -Force ".vite"
        Write-Host "  ✓ Removed .vite" -ForegroundColor Green
    }
    
    if (Test-Path "dist") {
        Remove-Item -Recurse -Force "dist"
        Write-Host "  ✓ Removed dist" -ForegroundColor Green
    }
    
    Write-Host ""
}

Write-Host "Step 2: Starting frontend server..." -ForegroundColor Yellow
Write-Host "  Server will be at: http://127.0.0.1:5173/#/" -ForegroundColor Cyan
Write-Host ""
Write-Host "IMPORTANT: Open in INCOGNITO/PRIVATE window!" -ForegroundColor Red
Write-Host "  Chrome/Edge: Ctrl+Shift+N" -ForegroundColor White
Write-Host "  Firefox: Ctrl+Shift+P" -ForegroundColor White
Write-Host ""
Write-Host "Expected UI: Graph Dashboard (NOT 'AI-Powered Migration')" -ForegroundColor Green
Write-Host ""
Write-Host "Starting server (press Ctrl+C to stop)..." -ForegroundColor Yellow
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Gray
Write-Host ""

# Start dev server
npm run dev -- --host 127.0.0.1 --port 5173
