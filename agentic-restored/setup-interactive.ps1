# GraphTrace Interactive Setup Script
# This script prompts for all configuration details and sets up the environment
# Usage: .\setup-interactive.ps1

Param(
    [switch]$SkipDependencies,
    [switch]$SkipDiagnostics,
    [switch]$Force
)

$ErrorActionPreference = 'Stop'
$script:root = $PSScriptRoot

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

function Write-Banner {
    param([string]$Text)
    Write-Host ""
    Write-Host ("=" * 70) -ForegroundColor Cyan
    Write-Host "  $Text" -ForegroundColor Cyan
    Write-Host ("=" * 70) -ForegroundColor Cyan
    Write-Host ""
}

function Write-Section {
    param([string]$Text)
    Write-Host ""
    Write-Host ">> $Text" -ForegroundColor Yellow
    Write-Host ("-" * 50) -ForegroundColor DarkGray
}

function Write-Success {
    param([string]$Text)
    Write-Host "  [OK] $Text" -ForegroundColor Green
}

function Write-Warning {
    param([string]$Text)
    Write-Host "  [WARN] $Text" -ForegroundColor Yellow
}

function Write-Error {
    param([string]$Text)
    Write-Host "  [ERROR] $Text" -ForegroundColor Red
}

function Read-ConfigValue {
    param(
        [string]$Prompt,
        [string]$Default = "",
        [switch]$IsPassword,
        [switch]$Required
    )
    
    $displayDefault = if ($Default) { " [$Default]" } else { "" }
    $displayPrompt = "  $Prompt$displayDefault`: "
    
    if ($IsPassword) {
        Write-Host $displayPrompt -NoNewline -ForegroundColor White
        $secureValue = Read-Host -AsSecureString
        if ($secureValue.Length -eq 0 -and $Default) {
            return $Default
        }
        $BSTR = [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureValue)
        $value = [System.Runtime.InteropServices.Marshal]::PtrToStringAuto($BSTR)
        [System.Runtime.InteropServices.Marshal]::ZeroFreeBSTR($BSTR)
    } else {
        $value = Read-Host -Prompt $displayPrompt
        if ([string]::IsNullOrWhiteSpace($value) -and $Default) {
            $value = $Default
        }
    }
    
    if ($Required -and [string]::IsNullOrWhiteSpace($value)) {
        Write-Error "This field is required. Please enter a value."
        return Read-ConfigValue -Prompt $Prompt -Default $Default -IsPassword:$IsPassword -Required:$Required
    }
    
    return $value.Trim()
}

function Read-YesNo {
    param(
        [string]$Prompt,
        [bool]$Default = $true
    )
    
    $defaultStr = if ($Default) { "Y/n" } else { "y/N" }
    $value = Read-Host -Prompt "  $Prompt [$defaultStr]"
    
    if ([string]::IsNullOrWhiteSpace($value)) {
        return $Default
    }
    
    return $value.ToLower() -in @("y", "yes", "true", "1")
}

function Test-Command {
    param([string]$Command)
    return $null -ne (Get-Command $Command -ErrorAction SilentlyContinue)
}

function Test-Port {
    param([int]$Port)
    $connection = Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue
    return $null -ne $connection
}

function Test-PostgresConnection {
    param(
        [string]$Host,
        [int]$Port,
        [string]$Database,
        [string]$User,
        [string]$Password
    )
    
    try {
        # Try using psql if available
        if (Test-Command "psql") {
            $env:PGPASSWORD = $Password
            $result = & psql -h $Host -p $Port -U $User -d $Database -c "SELECT 1" 2>&1
            $env:PGPASSWORD = ""
            return $LASTEXITCODE -eq 0
        }
        
        # Try TCP connection
        $tcpClient = New-Object System.Net.Sockets.TcpClient
        $tcpClient.Connect($Host, $Port)
        $connected = $tcpClient.Connected
        $tcpClient.Close()
        return $connected
    } catch {
        return $false
    }
}

function Test-Neo4jConnection {
    param(
        [string]$Uri,
        [string]$User,
        [string]$Password
    )
    
    try {
        # Extract host:port from URI
        if ($Uri -match "neo4j(\+s)?://([^:]+):?(\d+)?") {
            $host = $Matches[2]
            $port = if ($Matches[3]) { [int]$Matches[3] } else { 7687 }
            
            $tcpClient = New-Object System.Net.Sockets.TcpClient
            $tcpClient.Connect($host, $port)
            $connected = $tcpClient.Connected
            $tcpClient.Close()
            return $connected
        }
        return $false
    } catch {
        return $false
    }
}

# ============================================================================
# MAIN SCRIPT
# ============================================================================

Write-Banner "GraphTrace Interactive Setup"

Write-Host "  This script will guide you through setting up GraphTrace for a new environment."
Write-Host "  It will prompt for configuration details and generate the necessary files."
Write-Host ""

# ============================================================================
# STEP 1: SYSTEM REQUIREMENTS CHECK
# ============================================================================

Write-Section "Step 1: System Requirements Check"

$systemOk = $true

# Check Python
if (Test-Command "python") {
    $pythonVersion = (python --version 2>&1) -replace "Python ", ""
    if ([version]$pythonVersion -ge [version]"3.8") {
        Write-Success "Python $pythonVersion detected"
    } else {
        Write-Error "Python 3.8+ required, found $pythonVersion"
        $systemOk = $false
    }
} else {
    Write-Error "Python not found. Install Python 3.8+ and add to PATH."
    $systemOk = $false
}

# Check Node.js
if (Test-Command "node") {
    $nodeVersion = (node --version) -replace "v", ""
    if ([version]$nodeVersion -ge [version]"18.0") {
        Write-Success "Node.js $nodeVersion detected"
    } else {
        Write-Error "Node.js 18+ required, found $nodeVersion"
        $systemOk = $false
    }
} else {
    Write-Error "Node.js not found. Install Node.js 18+ from https://nodejs.org/"
    $systemOk = $false
}

# Check npm
if (Test-Command "npm") {
    $npmVersion = npm --version
    Write-Success "npm $npmVersion detected"
} else {
    Write-Error "npm not found. It should be installed with Node.js."
    $systemOk = $false
}

if (-not $systemOk) {
    Write-Host ""
    Write-Error "System requirements not met. Please install missing software and try again."
    exit 1
}

# ============================================================================
# STEP 2: POSTGRESQL CONFIGURATION
# ============================================================================

Write-Section "Step 2: PostgreSQL Database Configuration"

Write-Host "  GraphTrace requires PostgreSQL for storing application data."
Write-Host "  Please provide your PostgreSQL connection details."
Write-Host ""

$pgHost = Read-ConfigValue -Prompt "PostgreSQL Host" -Default "localhost"
$pgPort = Read-ConfigValue -Prompt "PostgreSQL Port" -Default "5432"
$pgDatabase = Read-ConfigValue -Prompt "PostgreSQL Database Name" -Default "graphtrace"
$pgUser = Read-ConfigValue -Prompt "PostgreSQL Username" -Default "postgres"
$pgPassword = Read-ConfigValue -Prompt "PostgreSQL Password" -IsPassword -Required

# Test PostgreSQL connection
Write-Host ""
Write-Host "  Testing PostgreSQL connection..." -ForegroundColor Gray
if (Test-PostgresConnection -Host $pgHost -Port $pgPort -Database $pgDatabase -User $pgUser -Password $pgPassword) {
    Write-Success "PostgreSQL connection successful"
} else {
    Write-Warning "Could not verify PostgreSQL connection. Make sure PostgreSQL is running."
    Write-Host "    Hint: You may need to create the database first:" -ForegroundColor Gray
    Write-Host "    CREATE DATABASE $pgDatabase;" -ForegroundColor Gray
    
    if (-not (Read-YesNo -Prompt "Continue anyway?" -Default $false)) {
        exit 1
    }
}

# ============================================================================
# STEP 3: NEO4J CONFIGURATION
# ============================================================================

Write-Section "Step 3: Neo4j Database Configuration"

Write-Host "  GraphTrace uses Neo4j for graph-based data storage and lineage tracking."
Write-Host "  You can use Neo4j AuraDB (cloud) or a local Neo4j instance."
Write-Host ""
Write-Host "  URI Format Examples:" -ForegroundColor Gray
Write-Host "    - Local:      neo4j://localhost:7687" -ForegroundColor Gray
Write-Host "    - Cloud SSL:  neo4j+s://xxxxx.databases.neo4j.io" -ForegroundColor Gray
Write-Host ""

$neo4jUri = Read-ConfigValue -Prompt "Neo4j URI" -Default "neo4j://localhost:7687"
$neo4jUser = Read-ConfigValue -Prompt "Neo4j Username" -Default "neo4j"
$neo4jPassword = Read-ConfigValue -Prompt "Neo4j Password" -IsPassword -Required
$neo4jDatabase = Read-ConfigValue -Prompt "Neo4j Database" -Default "neo4j"

# Test Neo4j connection
Write-Host ""
Write-Host "  Testing Neo4j connection..." -ForegroundColor Gray
if (Test-Neo4jConnection -Uri $neo4jUri -User $neo4jUser -Password $neo4jPassword) {
    Write-Success "Neo4j connection successful"
} else {
    Write-Warning "Could not verify Neo4j connection. Make sure Neo4j is running."
    
    if (-not (Read-YesNo -Prompt "Continue anyway?" -Default $false)) {
        exit 1
    }
}

# ============================================================================
# STEP 4: APPLICATION PORTS
# ============================================================================

Write-Section "Step 4: Application Port Configuration"

Write-Host "  Configure the ports for the backend API and frontend server."
Write-Host ""

$backendPort = Read-ConfigValue -Prompt "Backend API Port" -Default "8011"
$frontendPort = Read-ConfigValue -Prompt "Frontend Server Port" -Default "5173"

# Check if ports are in use
if (Test-Port -Port $backendPort) {
    Write-Warning "Port $backendPort is already in use"
    if (Read-YesNo -Prompt "Stop the process using port $backendPort?" -Default $false) {
        $pid = (Get-NetTCPConnection -LocalPort $backendPort -ErrorAction SilentlyContinue | Select-Object -First 1 -ExpandProperty OwningProcess)
        if ($pid) {
            Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
            Write-Success "Stopped process on port $backendPort"
        }
    }
}

if (Test-Port -Port $frontendPort) {
    Write-Warning "Port $frontendPort is already in use"
    if (Read-YesNo -Prompt "Stop the process using port $frontendPort?" -Default $false) {
        $pid = (Get-NetTCPConnection -LocalPort $frontendPort -ErrorAction SilentlyContinue | Select-Object -First 1 -ExpandProperty OwningProcess)
        if ($pid) {
            Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
            Write-Success "Stopped process on port $frontendPort"
        }
    }
}

# ============================================================================
# STEP 5: OPTIONAL SERVICES
# ============================================================================

Write-Section "Step 5: Optional Services (press Enter to skip)"

Write-Host "  OpenSearch is used for vector search and retrieval features."
Write-Host "  Leave blank to disable OpenSearch integration."
Write-Host ""

$opensearchUrl = Read-ConfigValue -Prompt "OpenSearch URL (optional)" -Default ""

# ============================================================================
# STEP 6: SECURITY CONFIGURATION
# ============================================================================

Write-Section "Step 6: Security Configuration"

Write-Host "  GraphTrace uses an encryption key to secure sensitive configuration data."
Write-Host ""

$generateKey = Read-YesNo -Prompt "Generate a new encryption key?" -Default $true
$encryptionKey = ""

if ($generateKey) {
    Write-Host "  Generating encryption key..." -ForegroundColor Gray
    # We'll generate this after setting up the venv
} else {
    $encryptionKey = Read-ConfigValue -Prompt "Enter encryption key (Fernet format)" -Required
}

# ============================================================================
# STEP 7: CORS CONFIGURATION
# ============================================================================

Write-Section "Step 7: CORS Configuration"

$corsOrigins = "http://localhost:$frontendPort,http://127.0.0.1:$frontendPort"
Write-Host "  Default CORS origins: $corsOrigins" -ForegroundColor Gray
$additionalOrigins = Read-ConfigValue -Prompt "Additional CORS origins (comma-separated, optional)" -Default ""
if ($additionalOrigins) {
    $corsOrigins = "$corsOrigins,$additionalOrigins"
}

# ============================================================================
# STEP 8: REVIEW CONFIGURATION
# ============================================================================

Write-Section "Step 8: Configuration Review"

Write-Host ""
Write-Host "  PostgreSQL:" -ForegroundColor White
Write-Host "    Host:     $pgHost" -ForegroundColor Gray
Write-Host "    Port:     $pgPort" -ForegroundColor Gray
Write-Host "    Database: $pgDatabase" -ForegroundColor Gray
Write-Host "    User:     $pgUser" -ForegroundColor Gray
Write-Host ""
Write-Host "  Neo4j:" -ForegroundColor White
Write-Host "    URI:      $neo4jUri" -ForegroundColor Gray
Write-Host "    User:     $neo4jUser" -ForegroundColor Gray
Write-Host "    Database: $neo4jDatabase" -ForegroundColor Gray
Write-Host ""
Write-Host "  Application:" -ForegroundColor White
Write-Host "    Backend:  http://localhost:$backendPort" -ForegroundColor Gray
Write-Host "    Frontend: http://localhost:$frontendPort" -ForegroundColor Gray
Write-Host ""
if ($opensearchUrl) {
    Write-Host "  OpenSearch:" -ForegroundColor White
    Write-Host "    URL: $opensearchUrl" -ForegroundColor Gray
    Write-Host ""
}

if (-not (Read-YesNo -Prompt "Proceed with this configuration?" -Default $true)) {
    Write-Host ""
    Write-Host "Setup cancelled. Run the script again to reconfigure." -ForegroundColor Yellow
    exit 0
}

# ============================================================================
# STEP 9: CREATE CONFIGURATION FILES
# ============================================================================

Write-Section "Step 9: Creating Configuration Files"

# Create logs directory
$logsDir = Join-Path $root "logs"
if (-not (Test-Path $logsDir)) {
    New-Item -ItemType Directory -Path $logsDir -Force | Out-Null
    Write-Success "Created logs directory"
}

# Create Backend .env
$backendEnvPath = Join-Path $root "python_backend\.env"
$backendEnvContent = @"
# GraphTrace Backend Configuration
# Generated by setup-interactive.ps1 on $(Get-Date -Format "yyyy-MM-dd HH:mm:ss")

# ============================================================================
# POSTGRESQL DATABASE
# ============================================================================
POSTGRES_HOST=$pgHost
POSTGRES_PORT=$pgPort
POSTGRES_DATABASE=$pgDatabase
POSTGRES_USER=$pgUser
POSTGRES_PASSWORD=$pgPassword

# SQLAlchemy Database URL (constructed from above)
DATABASE_URL=postgresql+psycopg://${pgUser}:${pgPassword}@${pgHost}:${pgPort}/${pgDatabase}

# ============================================================================
# NEO4J GRAPH DATABASE
# ============================================================================
NEO4J_URI=$neo4jUri
NEO4J_USER=$neo4jUser
NEO4J_PASSWORD=$neo4jPassword
NEO4J_DATABASE=$neo4jDatabase

# ============================================================================
# OPENSEARCH (Optional)
# ============================================================================
$(if ($opensearchUrl) { "OPENSEARCH_URL=$opensearchUrl" } else { "# OPENSEARCH_URL=http://localhost:9200" })
OPENSEARCH_TIMEOUT_S=5

# ============================================================================
# APPLICATION SETTINGS
# ============================================================================
BACKEND_PORT=$backendPort
ALLOWED_ORIGINS=$corsOrigins

# Enable loading this .env file
GRAPH_TRACE_LOAD_DOTENV=1

# Encryption key for DB-backed configuration (will be set by setup script)
# GRAPH_TRACE_CONFIG_ENCRYPTION_KEY=<generated>
"@

# Backup existing .env if it exists
if (Test-Path $backendEnvPath) {
    $backupPath = "$backendEnvPath.backup.$(Get-Date -Format 'yyyyMMdd_HHmmss')"
    Copy-Item $backendEnvPath $backupPath
    Write-Warning "Backed up existing .env to $backupPath"
}

Set-Content -Path $backendEnvPath -Value $backendEnvContent -Encoding UTF8
Write-Success "Created python_backend/.env"

# Create Frontend .env
$frontendEnvPath = Join-Path $root "e2etraceapp\.env"
$frontendEnvContent = @"
# GraphTrace Frontend Configuration
# Generated by setup-interactive.ps1 on $(Get-Date -Format "yyyy-MM-dd HH:mm:ss")

# API Base URL (backend)
VITE_API_BASE_URL=http://localhost:$backendPort

# Development proxy target
VITE_DEV_PROXY_TARGET=http://127.0.0.1:$backendPort
"@

if (Test-Path $frontendEnvPath) {
    $backupPath = "$frontendEnvPath.backup.$(Get-Date -Format 'yyyyMMdd_HHmmss')"
    Copy-Item $frontendEnvPath $backupPath
    Write-Warning "Backed up existing frontend .env to $backupPath"
}

Set-Content -Path $frontendEnvPath -Value $frontendEnvContent -Encoding UTF8
Write-Success "Created e2etraceapp/.env"

# ============================================================================
# STEP 10: INSTALL DEPENDENCIES
# ============================================================================

if (-not $SkipDependencies) {
    Write-Section "Step 10: Installing Dependencies"

    # Backend dependencies
    Write-Host "  Setting up Python backend..." -ForegroundColor Gray
    Push-Location (Join-Path $root "python_backend")
    try {
        # Create venv if needed
        if (-not (Test-Path "venv")) {
            Write-Host "    Creating virtual environment..." -ForegroundColor Gray
            python -m venv venv
        }
        
        # Activate venv
        & ".\venv\Scripts\Activate.ps1"
        
        # Upgrade pip
        Write-Host "    Upgrading pip..." -ForegroundColor Gray
        python -m pip install --upgrade pip --quiet
        
        # Install requirements
        Write-Host "    Installing Python packages..." -ForegroundColor Gray
        python -m pip install -r requirement.txt --quiet
        
        Write-Success "Backend dependencies installed"
        
        # Generate encryption key if needed
        if ($generateKey) {
            Write-Host "    Generating encryption key..." -ForegroundColor Gray
            $encryptionKey = python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
            
            # Add to .env file
            Add-Content -Path $backendEnvPath -Value "`nGRAPH_TRACE_CONFIG_ENCRYPTION_KEY=$encryptionKey"
            
            # Also save to key file for VS Code integration
            $keyFile = Join-Path (Get-Location) ".graphtrace.encryption_key"
            Set-Content -Path $keyFile -Value $encryptionKey -Encoding ASCII
            
            Write-Success "Encryption key generated and saved"
        }
        
        # Set the encryption key in environment for DB init
        $env:GRAPH_TRACE_CONFIG_ENCRYPTION_KEY = $encryptionKey
        $env:GRAPH_TRACE_LOAD_DOTENV = "1"
        
        # Initialize database schema
        Write-Host "    Initializing database schema..." -ForegroundColor Gray
        try {
            python -m scripts.init_db_schema
            Write-Success "Database schema initialized"
        } catch {
            Write-Warning "Database schema initialization failed: $_"
            Write-Host "    This may be OK if PostgreSQL is not running yet." -ForegroundColor Gray
        }
    }
    finally {
        Pop-Location
    }

    # Frontend dependencies
    Write-Host ""
    Write-Host "  Setting up React frontend..." -ForegroundColor Gray
    Push-Location (Join-Path $root "e2etraceapp")
    try {
        Write-Host "    Installing npm packages..." -ForegroundColor Gray
        npm install --quiet 2>$null
        Write-Success "Frontend dependencies installed"
    }
    finally {
        Pop-Location
    }
}

# ============================================================================
# STEP 11: RUN DIAGNOSTICS
# ============================================================================

if (-not $SkipDiagnostics) {
    Write-Section "Step 11: Running Diagnostics"
    
    $diagScript = Join-Path $root "diagnostics\windows\diagnose-all.ps1"
    if (Test-Path $diagScript) {
        & $diagScript
    } else {
        Write-Warning "Diagnostics script not found"
    }
}

# ============================================================================
# SETUP COMPLETE
# ============================================================================

Write-Banner "Setup Complete!"

Write-Host "  Configuration files created:" -ForegroundColor White
Write-Host "    - python_backend/.env" -ForegroundColor Gray
Write-Host "    - e2etraceapp/.env" -ForegroundColor Gray
Write-Host ""
Write-Host "  To start GraphTrace:" -ForegroundColor White
Write-Host "    .\start-all.ps1" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Or start services individually:" -ForegroundColor White
Write-Host "    .\start-backend.ps1   # Backend API at http://localhost:$backendPort" -ForegroundColor Gray
Write-Host "    .\start-frontend.ps1  # Frontend at http://localhost:$frontendPort" -ForegroundColor Gray
Write-Host ""
Write-Host "  Access Points:" -ForegroundColor White
Write-Host "    Frontend:   http://localhost:$frontendPort" -ForegroundColor Cyan
Write-Host "    Backend:    http://localhost:$backendPort" -ForegroundColor Cyan
Write-Host "    API Docs:   http://localhost:$backendPort/docs" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Configuration UI: http://localhost:$frontendPort/#/data-config" -ForegroundColor Cyan
Write-Host ""

