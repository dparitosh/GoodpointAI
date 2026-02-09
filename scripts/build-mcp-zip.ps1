# PowerShell script to build deployment artifact for MCP Server
# Usage: .\scripts\build-mcp-zip.ps1

$ErrorActionPreference = "Stop"

$repoRoot = "$PSScriptRoot\.."
$sourceDir = "$repoRoot\mcp_server"
$distDir = "$repoRoot\dist"
$zipPath = "$distDir\mcp_server_deploy.zip"

Write-Host "Building MCP Server deployment artifact..." -ForegroundColor Cyan

# 1. Clean/Create dist directory
if (Test-Path $distDir) {
    Remove-Item $distDir -Recurse -Force
}
New-Item -ItemType Directory -Path $distDir | Out-Null

# 2. Validate prerequisites
if (-not (Test-Path "$sourceDir\requirements.txt")) {
    Write-Error "requirements.txt missing in $sourceDir"
}

# 3. Create Zip
# We want the *contents* of mcp_server to be at the root of the zip
Write-Host "Creating ZIP archive at $zipPath..." -ForegroundColor Yellow

Compress-Archive -Path "$sourceDir\*" -DestinationPath $zipPath -Force

Write-Host "Build complete!" -ForegroundColor Green
Write-Host "Artifact: $zipPath" -ForegroundColor Green
Write-Host "Deploy using: az webapp deployment source config-zip --resource-group <resource-group> --name <app-name> --src $zipPath" -ForegroundColor Gray
