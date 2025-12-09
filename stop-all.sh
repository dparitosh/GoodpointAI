#!/bin/bash
# Stop all GraphTrace services

echo "Stopping GraphTrace services..."

# Stop backend (port 8000)
if lsof -Pi :8000 -sTCP:LISTEN -t >/dev/null 2>&1; then
    PID=$(lsof -Pi :8000 -sTCP:LISTEN -t)
    echo "Stopping backend (PID: $PID)..."
    kill $PID
    echo "Backend stopped"
else
    echo "Backend not running"
fi

# Stop frontend (port 5173)
if lsof -Pi :5173 -sTCP:LISTEN -t >/dev/null 2>&1; then
    PID=$(lsof -Pi :5173 -sTCP:LISTEN -t)
    echo "Stopping frontend (PID: $PID)..."
    kill $PID
    echo "Frontend stopped"
else
    echo "Frontend not running"
fi

# Also kill by process name (backup)
pkill -f "python.*main.py" 2>/dev/null
pkill -f "vite" 2>/dev/null

echo "All services stopped"
