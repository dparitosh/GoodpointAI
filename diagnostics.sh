#!/bin/bash
# GraphTrace System Diagnostics and Validation Script
# Tests all components before starting the application

set -e  # Exit on error

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$SCRIPT_DIR/python_backend"
FRONTEND_DIR="$SCRIPT_DIR/e2etraceapp"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Counters
PASSED=0
FAILED=0
WARNINGS=0

echo "=================================================="
echo "  GraphTrace System Diagnostics"
echo "  Date: $(date)"
echo "=================================================="
echo ""

# Function to print test results
print_status() {
    local status=$1
    local message=$2
    if [ "$status" == "PASS" ]; then
        echo -e "${GREEN}✓ PASS${NC} - $message"
        ((PASSED++))
    elif [ "$status" == "FAIL" ]; then
        echo -e "${RED}✗ FAIL${NC} - $message"
        ((FAILED++))
    elif [ "$status" == "WARN" ]; then
        echo -e "${YELLOW}⚠ WARN${NC} - $message"
        ((WARNINGS++))
    else
        echo -e "${BLUE}ℹ INFO${NC} - $message"
    fi
}

echo "=== System Prerequisites ==="
echo ""

# Check Python
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
    print_status "PASS" "Python 3 installed: $PYTHON_VERSION"
    
    # Check minimum version (3.8+)
    PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
    PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)
    if [ "$PYTHON_MAJOR" -ge 3 ] && [ "$PYTHON_MINOR" -ge 8 ]; then
        print_status "PASS" "Python version meets requirements (>=3.8)"
    else
        print_status "FAIL" "Python version too old (need >=3.8, have $PYTHON_VERSION)"
    fi
else
    print_status "FAIL" "Python 3 not found. Please install Python 3.8+"
fi

# Check pip
if command -v pip3 &> /dev/null; then
    PIP_VERSION=$(pip3 --version | cut -d' ' -f2)
    print_status "PASS" "pip3 installed: $PIP_VERSION"
else
    print_status "FAIL" "pip3 not found"
fi

# Check Node.js
if command -v node &> /dev/null; then
    NODE_VERSION=$(node --version)
    print_status "PASS" "Node.js installed: $NODE_VERSION"
    
    # Check minimum version (18+)
    NODE_MAJOR=$(echo $NODE_VERSION | cut -d'v' -f2 | cut -d'.' -f1)
    if [ "$NODE_MAJOR" -ge 18 ]; then
        print_status "PASS" "Node.js version meets requirements (>=18)"
    else
        print_status "WARN" "Node.js version <18 may have compatibility issues"
    fi
else
    print_status "FAIL" "Node.js not found. Please install Node.js 18+"
fi

# Check npm
if command -v npm &> /dev/null; then
    NPM_VERSION=$(npm --version)
    print_status "PASS" "npm installed: $NPM_VERSION"
else
    print_status "FAIL" "npm not found"
fi

# Check git
if command -v git &> /dev/null; then
    GIT_VERSION=$(git --version | cut -d' ' -f3)
    print_status "PASS" "git installed: $GIT_VERSION"
else
    print_status "WARN" "git not found (optional but recommended)"
fi

echo ""
echo "=== Backend Configuration ==="
echo ""

# Check backend directory
if [ -d "$BACKEND_DIR" ]; then
    print_status "PASS" "Backend directory exists: $BACKEND_DIR"
else
    print_status "FAIL" "Backend directory not found: $BACKEND_DIR"
fi

# Check requirements.txt (note: it's requirement.txt not requirements.txt)
if [ -f "$BACKEND_DIR/requirement.txt" ]; then
    print_status "PASS" "Backend requirements file exists"
    REQUIRED_PACKAGES=$(wc -l < "$BACKEND_DIR/requirement.txt")
    print_status "INFO" "Found $REQUIRED_PACKAGES required packages"
else
    print_status "FAIL" "Backend requirement.txt not found"
fi

# Check main.py
if [ -f "$BACKEND_DIR/main.py" ]; then
    print_status "PASS" "Backend main.py exists"
else
    print_status "FAIL" "Backend main.py not found"
fi

# Check .env file
if [ -f "$BACKEND_DIR/.env" ]; then
    print_status "PASS" "Backend .env file exists"
    
    # Validate required environment variables
    if grep -q "NEO4J_URI" "$BACKEND_DIR/.env"; then
        print_status "PASS" "NEO4J_URI configured"
    else
        print_status "FAIL" "NEO4J_URI not found in .env"
    fi
    
    if grep -q "NEO4J_USER" "$BACKEND_DIR/.env"; then
        print_status "PASS" "NEO4J_USER configured"
    else
        print_status "FAIL" "NEO4J_USER not found in .env"
    fi
    
    if grep -q "NEO4J_PASSWORD" "$BACKEND_DIR/.env"; then
        print_status "PASS" "NEO4J_PASSWORD configured"
    else
        print_status "FAIL" "NEO4J_PASSWORD not found in .env"
    fi
else
    print_status "FAIL" "Backend .env file not found - Neo4j credentials required"
fi

# Check if Python packages are installed
if command -v python3 &> /dev/null; then
    echo ""
    echo "Checking Python packages..."
    
    for package in fastapi uvicorn neo4j python-dotenv pydantic sqlalchemy; do
        if python3 -c "import $package" 2>/dev/null; then
            VERSION=$(python3 -c "import $package; print($package.__version__)" 2>/dev/null || echo "unknown")
            print_status "PASS" "$package installed: $VERSION"
        else
            print_status "FAIL" "$package not installed"
        fi
    done
fi

echo ""
echo "=== Frontend Configuration ==="
echo ""

# Check frontend directory
if [ -d "$FRONTEND_DIR" ]; then
    print_status "PASS" "Frontend directory exists: $FRONTEND_DIR"
else
    print_status "FAIL" "Frontend directory not found: $FRONTEND_DIR"
fi

# Check package.json
if [ -f "$FRONTEND_DIR/package.json" ]; then
    print_status "PASS" "Frontend package.json exists"
    
    # Count dependencies
    DEPS=$(grep -c "\"react\|\"vite\|\"echarts" "$FRONTEND_DIR/package.json" || echo "0")
    print_status "INFO" "Found $DEPS key dependencies in package.json"
else
    print_status "FAIL" "Frontend package.json not found"
fi

# Check vite.config.js
if [ -f "$FRONTEND_DIR/vite.config.js" ]; then
    print_status "PASS" "Vite configuration exists"
else
    print_status "FAIL" "vite.config.js not found"
fi

# Check index.html
if [ -f "$FRONTEND_DIR/index.html" ]; then
    print_status "PASS" "Frontend index.html exists"
else
    print_status "FAIL" "Frontend index.html not found"
fi

# Check node_modules
if [ -d "$FRONTEND_DIR/node_modules" ]; then
    print_status "PASS" "Frontend node_modules exists"
    MODULE_COUNT=$(ls -1 "$FRONTEND_DIR/node_modules" | wc -l)
    print_status "INFO" "Installed $MODULE_COUNT npm packages"
else
    print_status "WARN" "Frontend node_modules not found - run 'npm install'"
fi

# Check .env file (optional for frontend)
if [ -f "$FRONTEND_DIR/.env" ]; then
    print_status "PASS" "Frontend .env file exists"
else
    print_status "WARN" "Frontend .env file not found (optional)"
fi

echo ""
echo "=== Port Availability ==="
echo ""

# Check if ports are available
if command -v lsof &> /dev/null; then
    # Backend port 8000
    if lsof -Pi :8000 -sTCP:LISTEN -t >/dev/null 2>&1; then
        PID=$(lsof -Pi :8000 -sTCP:LISTEN -t)
        print_status "WARN" "Port 8000 already in use by PID $PID"
    else
        print_status "PASS" "Port 8000 available for backend"
    fi
    
    # Frontend port 5173
    if lsof -Pi :5173 -sTCP:LISTEN -t >/dev/null 2>&1; then
        PID=$(lsof -Pi :5173 -sTCP:LISTEN -t)
        print_status "WARN" "Port 5173 already in use by PID $PID"
    else
        print_status "PASS" "Port 5173 available for frontend"
    fi
else
    print_status "WARN" "lsof not available - cannot check port availability"
fi

echo ""
echo "=== Network Connectivity ==="
echo ""

# Check internet connectivity
if ping -c 1 8.8.8.8 &> /dev/null; then
    print_status "PASS" "Internet connectivity available"
else
    print_status "WARN" "No internet connectivity (may affect package installation)"
fi

# Check Neo4j connectivity (if .env exists)
if [ -f "$BACKEND_DIR/.env" ]; then
    source "$BACKEND_DIR/.env" 2>/dev/null || true
    if [ ! -z "$NEO4J_URI" ]; then
        # Extract host from URI
        NEO4J_HOST=$(echo $NEO4J_URI | sed -E 's|.*://([^:/]+).*|\1|')
        if ping -c 1 "$NEO4J_HOST" &> /dev/null 2>&1 || nslookup "$NEO4J_HOST" &> /dev/null 2>&1; then
            print_status "PASS" "Neo4j host reachable: $NEO4J_HOST"
        else
            print_status "WARN" "Cannot reach Neo4j host: $NEO4J_HOST"
        fi
    fi
fi

echo ""
echo "=== File Permissions ==="
echo ""

# Check script executability
if [ -x "$SCRIPT_DIR/start-all.sh" ] || [ -f "$SCRIPT_DIR/start-all.sh" ]; then
    if [ -x "$SCRIPT_DIR/start-all.sh" ]; then
        print_status "PASS" "start-all.sh is executable"
    else
        print_status "WARN" "start-all.sh exists but not executable (run: chmod +x start-all.sh)"
    fi
fi

# Check write permissions in log directory
if [ -d "/tmp" ]; then
    if [ -w "/tmp" ]; then
        print_status "PASS" "/tmp directory is writable for logs"
    else
        print_status "FAIL" "/tmp directory not writable"
    fi
fi

echo ""
echo "=== Summary ==="
echo ""
echo -e "Tests Passed:  ${GREEN}$PASSED${NC}"
echo -e "Tests Failed:  ${RED}$FAILED${NC}"
echo -e "Warnings:      ${YELLOW}$WARNINGS${NC}"
echo ""

if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}✓ All critical checks passed!${NC}"
    echo ""
    echo "Next steps:"
    echo "  1. Review any warnings above"
    echo "  2. Run installation script if needed: ./install.sh"
    echo "  3. Start services: ./start-all.sh"
    exit 0
else
    echo -e "${RED}✗ Some critical checks failed!${NC}"
    echo ""
    echo "Please fix the issues above before proceeding."
    echo "Common fixes:"
    echo "  - Install missing Python packages: cd python_backend && pip3 install -r requirement.txt"
    echo "  - Install missing npm packages: cd e2etraceapp && npm install"
    echo "  - Create backend .env file with Neo4j credentials"
    exit 1
fi
