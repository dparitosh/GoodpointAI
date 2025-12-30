#!/bin/bash
# Start all GraphTrace services (Backend + Frontend)

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

echo "=================================================="
echo "  Starting GraphTrace Full Stack Application"
echo "=================================================="
echo ""

# Check if services are already running
if lsof -Pi :8011 -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo -e "${BLUE}Backend already running on port 8011${NC}"
else
    echo "Starting Backend..."
    cd "$SCRIPT_DIR/python_backend"
    source venv/bin/activate
    nohup python main.py > "$SCRIPT_DIR/logs/backend.log" 2>&1 &
    echo "Backend started (PID: $!)"
    echo "  Log: $SCRIPT_DIR/logs/backend.log"
fi

# Wait for backend to start
echo "Waiting for backend to initialize..."
sleep 3

if lsof -Pi :5173 -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo -e "${BLUE}Frontend already running on port 5173${NC}"
else
    echo "Starting Frontend..."
    cd "$SCRIPT_DIR/e2etraceapp"
    nohup npm run dev > "$SCRIPT_DIR/logs/frontend.log" 2>&1 &
    echo "Frontend started (PID: $!)"
    echo "  Log: $SCRIPT_DIR/logs/frontend.log"
fi

echo ""
echo "=================================================="
echo -e "  ${GREEN}GraphTrace Services Started${NC}"
echo "=================================================="
echo ""
echo "Access Points:"
echo "  Backend API:       http://localhost:8011"
echo "  API Documentation: http://localhost:8011/docs"
echo "  Frontend App:      http://localhost:5173"
echo ""
echo "Logs:"
echo "  Backend:  tail -f $SCRIPT_DIR/logs/backend.log"
echo "  Frontend: tail -f $SCRIPT_DIR/logs/frontend.log"
echo ""
echo "To stop services:"
echo "  ./stop-all.sh"
echo ""
