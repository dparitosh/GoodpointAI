#!/usr/bin/env pwsh
# Fix Landing Page Display - Complete Restart

param(
    [switch]$Force
)

Write-Host "`n🔧 FIXING LANDING PAGE DISPLAY ISSUE`n" -ForegroundColor Cyan
Write-Host "════════════════════════════════════════════`n" -ForegroundColor Gray

# Step 1: Stop all running servers
Write-Host "Step 1: Stopping existing servers...`n" -ForegroundColor Yellow

# Stop Vite (Frontend)
$viteProcesses = Get-Process -Name "node" -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -like "*vite*" }
if ($viteProcesses) {
    Write-Host "  Stopping frontend server..." -ForegroundColor White
    $viteProcesses | Stop-Process -Force
    Start-Sleep -Seconds 2
    Write-Host "  ✓ Frontend stopped`n" -ForegroundColor Green
} else {
    Write-Host "  Frontend not running`n" -ForegroundColor Gray
}

# Stop Uvicorn (Backend)
$uvicornProcesses = Get-Process -Name "python*" -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -like "*uvicorn*" }
if ($uvicornProcesses) {
    Write-Host "  Stopping backend server..." -ForegroundColor White
    $uvicornProcesses | Stop-Process -Force
    Start-Sleep -Seconds 2
    Write-Host "  ✓ Backend stopped`n" -ForegroundColor Green
} else {
    Write-Host "  Backend not running`n" -ForegroundColor Gray
}

# Step 2: Clear caches
Write-Host "Step 2: Clearing caches...`n" -ForegroundColor Yellow

Set-Location -Path "$PSScriptRoot\e2etraceapp"

if (Test-Path "node_modules\.vite") {
    Remove-Item -Recurse -Force "node_modules\.vite"
    Write-Host "  ✓ Cleared node_modules\.vite" -ForegroundColor Green
}

if (Test-Path ".vite") {
    Remove-Item -Recurse -Force ".vite"
    Write-Host "  ✓ Cleared .vite" -ForegroundColor Green
}

if (Test-Path "dist") {
    Remove-Item -Recurse -Force "dist"
    Write-Host "  ✓ Cleared dist" -ForegroundColor Green
}

Write-Host ""

# Step 3: Verify route configuration
Write-Host "Step 3: Verifying route configuration...`n" -ForegroundColor Yellow

$routeFile = "src\routes\index.jsx"
$routeContent = Get-Content $routeFile -Raw

if ($routeContent -match 'index:\s*true,\s*element:\s*<LandingPage') {
    Write-Host "  ✓ Route configuration is correct" -ForegroundColor Green
    Write-Host "    Home route (/) → LandingPage`n" -ForegroundColor Gray
} else {
    Write-Host "  ❌ Route configuration may be incorrect!" -ForegroundColor Red
    Write-Host "    Check: $routeFile`n" -ForegroundColor Gray
}

# Step 4: Start servers
Write-Host "Step 4: Starting servers...`n" -ForegroundColor Yellow

Write-Host "  Starting backend..." -ForegroundColor White
Set-Location -Path "$PSScriptRoot\python_backend"

Start-Process powershell -ArgumentList @(
    "-NoExit",
    "-Command",
    "Write-Host '🚀 Backend Server (Port 8011)' -ForegroundColor Cyan; `
     cd '$PWD'; `
     `$env:GRAPH_TRACE_LOAD_DOTENV='true'; `
     python -m uvicorn main:app --host 0.0.0.0 --port 8011 --reload"
)

Write-Host "  ✓ Backend starting (new window)..." -ForegroundColor Green

Write-Host "`n  Starting frontend..." -ForegroundColor White
Set-Location -Path "$PSScriptRoot\e2etraceapp"

Start-Process powershell -ArgumentList @(
    "-NoExit",
    "-Command",
    "Write-Host '🚀 Frontend Server (Port 5173)' -ForegroundColor Cyan; `
     cd '$PWD'; `
     npm run dev -- --host 127.0.0.1 --port 5173"
)

Write-Host "  ✓ Frontend starting (new window)...`n" -ForegroundColor Green

# Step 5: Wait and verify
Write-Host "Step 5: Waiting for servers to initialize...`n" -ForegroundColor Yellow

Write-Host "  Waiting 10 seconds..." -ForegroundColor Gray
Start-Sleep -Seconds 10

Write-Host "`n  Testing endpoints..." -ForegroundColor White

# Test backend
try {
    $health = Invoke-RestMethod -Uri "http://localhost:8011/health" -TimeoutSec 5
    Write-Host "  ✓ Backend: " -NoNewline -ForegroundColor Green
    Write-Host "http://localhost:8011 ($($health.status))" -ForegroundColor Gray
} catch {
    Write-Host "  ⚠ Backend: Still starting..." -ForegroundColor Yellow
}

# Test frontend
try {
    $null = Invoke-WebRequest -Uri "http://127.0.0.1:5173" -TimeoutSec 5 -UseBasicParsing
    Write-Host "  ✓ Frontend: " -NoNewline -ForegroundColor Green
    Write-Host "http://127.0.0.1:5173" -ForegroundColor Gray
} catch {
    Write-Host "  ⚠ Frontend: Still starting..." -ForegroundColor Yellow
}

Write-Host "`n════════════════════════════════════════════`n" -ForegroundColor Gray

Write-Host "✅ SETUP COMPLETE!`n" -ForegroundColor Green

Write-Host "📋 NEXT STEPS:`n" -ForegroundColor Cyan

Write-Host "1. Check the two PowerShell windows for server logs" -ForegroundColor White
Write-Host "   • Backend window (port 8011)" -ForegroundColor Gray
Write-Host "   • Frontend window (port 5173)`n" -ForegroundColor Gray

Write-Host "2. Open browser in INCOGNITO/PRIVATE mode:" -ForegroundColor White
Write-Host "   Chrome/Edge: Ctrl+Shift+N" -ForegroundColor Gray
Write-Host "   Firefox: Ctrl+Shift+P`n" -ForegroundColor Gray

Write-Host "3. Navigate to: " -NoNewline -ForegroundColor White
Write-Host "http://127.0.0.1:5173/#/`n" -ForegroundColor Cyan

Write-Host "4. Expected landing page:" -ForegroundColor White
Write-Host "   ✓ 'AI-Powered Migration Platform' hero" -ForegroundColor Green
Write-Host "   ✓ GoodPoint AgenticAI branding" -ForegroundColor Green
Write-Host "   ✓ Migration workflow steps" -ForegroundColor Green
Write-Host "   ✓ Tool cards`n" -ForegroundColor Green

Write-Host "════════════════════════════════════════════`n" -ForegroundColor Gray

Write-Host "⚠️  IMPORTANT: Use incognito mode to bypass browser cache!`n" -ForegroundColor Red

Set-Location -Path $PSScriptRoot
