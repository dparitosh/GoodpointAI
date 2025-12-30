#!/bin/bash
# GraphTrace Complete Installation Script
# Installs all dependencies for backend and frontend

set -e  # Exit on error

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$SCRIPT_DIR/python_backend"
FRONTEND_DIR="$SCRIPT_DIR/e2etraceapp"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo "=================================================="
echo "  GraphTrace Installation Script"
echo "  Date: $(date)"
echo "=================================================="
echo ""

# Check prerequisites
echo "Checking prerequisites..."
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Error: Python 3 not found${NC}"
    echo "Please install Python 3.8 or higher from https://www.python.org/"
    exit 1
fi

if ! command -v node &> /dev/null; then
    echo -e "${RED}Error: Node.js not found${NC}"
    echo "Please install Node.js 18+ from https://nodejs.org/"
    exit 1
fi

if ! command -v npm &> /dev/null; then
    echo -e "${RED}Error: npm not found${NC}"
    exit 1
fi

echo -e "${GREEN}✓ All prerequisites found${NC}"
echo ""

# Backend Installation
echo "=== Installing Backend Dependencies ==="
echo ""

cd "$BACKEND_DIR"

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "Creating Python virtual environment..."
    python3 -m venv venv
    echo -e "${GREEN}✓ Virtual environment created${NC}"
else
    echo -e "${YELLOW}Virtual environment already exists${NC}"
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo "Upgrading pip..."
python -m pip install --upgrade pip --quiet

# Install backend dependencies
echo "Installing Python packages from requirement.txt..."
if [ -f "requirement.txt" ]; then
    pip install -r requirement.txt
    echo -e "${GREEN}✓ Backend dependencies installed${NC}"
else
    echo -e "${RED}Error: requirement.txt not found${NC}"
    exit 1
fi

# Check for .env file
if [ ! -f ".env" ]; then
    echo ""
    echo -e "${YELLOW}! Warning: .env file not found${NC}"
    echo "Creating template .env file..."
    cat > .env << 'EOF'
# Neo4j Configuration
NEO4J_URI=neo4j+s://your-instance.databases.neo4j.io
NEO4J_USER=neo4j
NEO4J_PASSWORD=your-password-here
NEO4J_DATABASE=neo4j

# Application Configuration
ENVIRONMENT=development
LOG_LEVEL=INFO
ALLOWED_ORIGINS=http://localhost:5173,http://localhost:5174

# Optional: API Keys
OPENAI_API_KEY=your-openai-key-here
EOF
    echo -e "${GREEN}✓ Template .env file created${NC}"
    echo -e "${YELLOW}! Please edit python_backend/.env with your actual Neo4j credentials${NC}"
else
    echo -e "${GREEN}✓ .env file exists${NC}"
fi

echo ""
echo "=== Installing Frontend Dependencies ==="
echo ""

cd "$FRONTEND_DIR"

# Clean install
if [ -d "node_modules" ]; then
    echo "Existing node_modules found. Cleaning..."
    rm -rf node_modules package-lock.json
fi

# Install npm dependencies
echo "Installing npm packages..."
npm install

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Frontend dependencies installed${NC}"
else
    echo -e "${RED}Error: npm install failed${NC}"
    exit 1
fi

# Check for frontend .env
if [ ! -f ".env" ]; then
    echo "Creating frontend .env file..."
    cat > .env << 'EOF'
# Frontend Environment Variables
# The VITE_ prefix is required for Vite to expose these to the client
VITE_API_BASE_URL=http://localhost:8011
VITE_APP_NAME=GraphTrace
VITE_APP_VERSION=1.0.0
EOF
    echo -e "${GREEN}✓ Frontend .env file created${NC}"
fi

# Return to root
cd "$SCRIPT_DIR"

echo ""
echo "=================================================="
echo "  Installation Complete!"
echo "=================================================="
echo ""
echo "Installed Components:"
echo "  ✓ Python virtual environment"
echo "  ✓ Backend Python packages (FastAPI, Neo4j, etc.)"
echo "  ✓ Frontend npm packages (React, Vite, etc.)"
echo ""
echo "Next Steps:"
echo "  1. Configure Neo4j credentials in python_backend/.env"
echo "  2. Run diagnostics: ./diagnostics.sh"
echo "  3. Start services:"
echo "     - All services: ./start-all.sh"
echo "     - Backend only: ./start-backend.sh"
echo "     - Frontend only: ./start-frontend.sh"
echo ""
echo "Access Points:"
echo "  Backend API:  http://localhost:8011"
echo "  API Docs:     http://localhost:8011/docs"
echo "  Frontend:     http://localhost:5173"
echo ""
