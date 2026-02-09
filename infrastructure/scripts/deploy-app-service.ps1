# Deploy MCP Server to Azure App Service
# This script creates and deploys the MCP server as an Azure App Service using code-based ZIP deployment (Python)

param(
    [Parameter(Mandatory=$true)]
    [ValidateSet('dev', 'staging', 'prod')]
    [string]$Environment,
    
    [Parameter(Mandatory=$false)]
    [string]$Location = "eastus",
    
    [Parameter(Mandatory=$false)]
    [string]$ResourceGroup = "rg-graphtrace-$Environment",
    
    [Parameter(Mandatory=$false)]
    [string]$AppServicePlan = "asp-graphtrace-$Environment",
    
    [Parameter(Mandatory=$false)]
    [string]$AppName = "app-mcp-server-$Environment"
)

$ErrorActionPreference = "Stop"

Write-Host "🚀 Deploying MCP Server to Azure App Service" -ForegroundColor Cyan
Write-Host "Environment: $Environment" -ForegroundColor Yellow
Write-Host "Method: ZIP Deployment (Python)" -ForegroundColor Yellow
Write-Host ""

# Step 1: Ensure resource group exists
Write-Host "📦 Checking resource group..." -ForegroundColor Cyan
$rgExists = az group exists --name $ResourceGroup | ConvertFrom-Json
if (-not $rgExists) {
    Write-Host "Creating resource group: $ResourceGroup" -ForegroundColor Yellow
    az group create --name $ResourceGroup --location $Location
}

# Step 2: Ensure App Service Plan exists
Write-Host "📦 Checking App Service Plan..." -ForegroundColor Cyan
$planExists = az appservice plan show --name $AppServicePlan --resource-group $ResourceGroup 2>$null
if (-not $planExists) {
    Write-Host "Creating App Service Plan: $AppServicePlan" -ForegroundColor Yellow
    
    # Choose SKU based on environment
    $sku = switch ($Environment) {
        'dev' { 'B1' }
        'staging' { 'P1V3' }
        'prod' { 'P2V3' }
    }
    
    az appservice plan create `
        --name $AppServicePlan `
        --resource-group $ResourceGroup `
        --location $Location `
        --sku $sku `
        --is-linux
}

# Step 3: Ensure App Service exists
Write-Host "📦 Checking App Service..." -ForegroundColor Cyan
$appExists = az webapp show --name $AppName --resource-group $ResourceGroup 2>$null
if (-not $appExists) {
    Write-Host "Creating App Service: $AppName" -ForegroundColor Yellow
    
    az webapp create `
        --name $AppName `
        --resource-group $ResourceGroup `
        --plan $AppServicePlan `
        --runtime "PYTHON:3.12"
}

# Step 4: Configure startup command
Write-Host "⚙️ Configuring startup command..." -ForegroundColor Cyan
az webapp config set `
    --name $AppName `
    --resource-group $ResourceGroup `
    --startup-file "python -m uvicorn main:app --host 0.0.0.0 --port 8000"

# Step 5: Configure App Settings
Write-Host "⚙️ Configuring application settings..." -ForegroundColor Cyan

# Get Key Vault reference if using managed secrets (placeholder logic)
# Real logic would verify KV exists, but here we set standard vars
# In a real pipeline, these Key Vault refs would be passed or resolved

az webapp config appsettings set `
    --name $AppName `
    --resource-group $ResourceGroup `
    --settings `
        MCP_SERVER_ID="$AppName" `
        MCP_SERVER_PORT=8000 `
        PYTHONUNBUFFERED=1 `
        ENABLE_METRICS=true `
        ENABLE_TRACING=true `
        LOG_LEVEL=INFO `
        DEVELOPMENT_MODE=false

Write-Host "✅ App Settings configured" -ForegroundColor Green

# Step 6: Enable Application Insights
Write-Host "📊 Enabling Application Insights..." -ForegroundColor Cyan
$aiName = "ai-graphtrace-$Environment"
$aiExists = az monitor app-insights component show --app $aiName --resource-group $ResourceGroup 2>$null

if (-not $aiExists) {
    Write-Host "Creating Application Insights: $aiName" -ForegroundColor Yellow
    az monitor app-insights component create `
        --app $aiName `
        --location $Location `
        --resource-group $ResourceGroup
}

$aiConnectionString = az monitor app-insights component show `
    --app $aiName `
    --resource-group $ResourceGroup `
    --query connectionString `
    -o tsv

az webapp config appsettings set `
    --name $AppName `
    --resource-group $ResourceGroup `
    --settings APPLICATIONINSIGHTS_CONNECTION_STRING="$aiConnectionString"

# Step 7: Deploy application
Write-Host "🚢 Deploying application..." -ForegroundColor Cyan

# Determine paths
# Script is in infrastructure/scripts
# Root is ../..
# MCP Server is mcp_server/
$rootPath = Resolve-Path "$PSScriptRoot\..\.."
$sourcePath = Join-Path $rootPath "mcp_server"
$zipPath = Join-Path $rootPath "mcp-server-$Environment.zip"

Write-Host "Source: $sourcePath" -ForegroundColor Gray
Write-Host "Artifact: $zipPath" -ForegroundColor Gray

if (Test-Path $zipPath) {
    Remove-Item $zipPath -Force
}

# Create ZIP excluding unnecessary files
Write-Host "Packaging application..." -ForegroundColor Yellow

# Use Compress-Archive if available (PowerShell 5+)
if (Get-Command Compress-Archive -ErrorAction SilentlyContinue) {
    
    # Compress-Archive has limits on excludes and file locking, so we might want to copy to temp first
    # But for simplicity in this script, we'll use a direct approach or best effort
    # Excluding files with Compress-Archive is tricky as it doesn't have a -Exclude param for recursive folders easily
    
    # Alternative strategy: Copy to temp dir, clean, zip temp dir
    $tempDir = Join-Path $rootPath "temp_deploy_$Environment"
    if (Test-Path $tempDir) { Remove-Item $tempDir -Recurse -Force }
    New-Item -ItemType Directory -Path $tempDir | Out-Null
    
    # Copy files
    Copy-Item -Path "$sourcePath\*" -Destination $tempDir -Recurse -Force
    
    # Clean temp dir
    $excludes = @('*.pyc', '__pycache__', '.git', 'tests', '.env', '.venv', 'venv')
    foreach ($item in $excludes) {
        Get-ChildItem -Path $tempDir -Recurse -Filter $item | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
    }
    
    # Zip
    Compress-Archive -Path "$tempDir\*" -DestinationPath $zipPath -Force -CompressionLevel Optimal
    
    # Cleanup temp
    Remove-Item $tempDir -Recurse -Force
    
} else {
    # Fallback to tar if Compress-Archive isn't handy (unlikely on Windows)
    # Or just warn
    Write-Host "Compress-Archive not found. Trying zip/tar..." -ForegroundColor Yellow
    tar -czf $zipPath -C "$rootPath" "mcp_server"
}

if (Test-Path $zipPath) {
    Write-Host "Deploying ZIP package..." -ForegroundColor Yellow
    az webapp deploy `
        --resource-group $ResourceGroup `
        --name $AppName `
        --src-path $zipPath `
        --type zip `
        --async true
} else {
    Write-Error "Failed to create deployment artifact at $zipPath"
}

# Step 8: Wait for deployment
Write-Host "⏳ Waiting for deployment to complete..." -ForegroundColor Cyan
Start-Sleep -Seconds 30

# Step 9: Verify deployment
Write-Host "✅ Verifying deployment..." -ForegroundColor Cyan
$appUrl = az webapp show --name $AppName --resource-group $ResourceGroup --query defaultHostName -o tsv
$healthUrl = "https://$appUrl/health"

Write-Host "Testing health endpoint: $healthUrl" -ForegroundColor Yellow

try {
    # Use -SkipCertificateCheck in case of self-signed or propagation delay issues purely for verification
    # But for App Service prod URLs it should be valid
    $response = Invoke-RestMethod -Uri $healthUrl -Method Get -ErrorAction SilentlyContinue
    if ($response) {
         Write-Host "✅ Health check passed!" -ForegroundColor Green
         Write-Host "Response: $($response | ConvertTo-Json -Depth 1 -Compress)" -ForegroundColor Gray
    } else {
         Write-Host "⚠️ Health check didn't return data. App might be starting." -ForegroundColor Yellow
    }
} catch {
    Write-Host "⚠️ Health check failed. App might still be starting..." -ForegroundColor Yellow
    Write-Host "Error: $_" -ForegroundColor Red
}

# Step 10: Display summary
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "✅ Deployment Complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "App Name: $AppName" -ForegroundColor White
Write-Host "Environment: $Environment" -ForegroundColor White
Write-Host "URL: https://$appUrl" -ForegroundColor White
Write-Host "Health: https://$appUrl/health" -ForegroundColor White
Write-Host "API Docs: https://$appUrl/docs" -ForegroundColor White
Write-Host "Metrics: https://$appUrl/metrics" -ForegroundColor White
Write-Host ""
Write-Host "View logs:" -ForegroundColor Yellow
Write-Host "  az webapp log tail --name $AppName --resource-group $ResourceGroup" -ForegroundColor Gray
Write-Host ""
