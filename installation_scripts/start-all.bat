@echo off
REM Batch script to start full GraphTrace stack
REM Usage: start-all.bat

echo Starting GraphTrace Full Stack Application...
echo.

REM Start backend in a new command window
echo Starting Backend Server...
start "GraphTrace Backend" cmd /k "%~dp0start-backend.bat"

REM Start MCP Server in a new command window
echo Starting MCP Server...
start "GraphTrace MCP Server" cmd /k "cd /d %~dp0.. && .venv\Scripts\activate && set PYTHONPATH=%~dp0.. && set GRAPH_TRACE_LOAD_DOTENV=true && python -m mcp_server.main"

REM Start Agent Services in new command windows
echo Starting Data Analyst Agent...
start "Data Analyst Agent" cmd /k "cd /d %~dp0.. && .venv\Scripts\activate && set PYTHONPATH=%~dp0.. && set GRAPH_TRACE_LOAD_DOTENV=true && python -m agent_services.data_analyst.main"

echo Starting ETL Orchestrator Agent...
start "ETL Orchestrator Agent" cmd /k "cd /d %~dp0.. && .venv\Scripts\activate && set PYTHONPATH=%~dp0.. && set GRAPH_TRACE_LOAD_DOTENV=true && python -m agent_services.etl_orchestrator.main"

echo Starting Visualization Agent...
start "Visualization Agent" cmd /k "cd /d %~dp0.. && .venv\Scripts\activate && set PYTHONPATH=%~dp0.. && set GRAPH_TRACE_LOAD_DOTENV=true && python -m agent_services.visualization_agent.main"

echo Starting Query Planner Agent...
start "Query Planner Agent" cmd /k "cd /d %~dp0.. && .venv\Scripts\activate && set PYTHONPATH=%~dp0.. && set GRAPH_TRACE_LOAD_DOTENV=true && python -m agent_services.query_planner.main"

echo Starting Quality Monitor Agent...
start "Quality Monitor Agent" cmd /k "cd /d %~dp0.. && .venv\Scripts\activate && set PYTHONPATH=%~dp0.. && set GRAPH_TRACE_LOAD_DOTENV=true && python -m agent_services.quality_monitor.main"

echo Starting Chat Coordinator Agent...
start "Chat Coordinator Agent" cmd /k "cd /d %~dp0.. && .venv\Scripts\activate && set PYTHONPATH=%~dp0.. && set GRAPH_TRACE_LOAD_DOTENV=true && python -m agent_services.chat_coordinator.main"

REM Wait a bit for backend to start
echo Waiting for servers to initialize...
timeout /t 3 /nobreak >nul

REM Start frontend in a new command window
echo Starting Frontend Server...
start "GraphTrace Frontend" cmd /k "%~dp0start-frontend.bat"

echo.
echo ========================================
echo GraphTrace Services Starting...
echo Backend API: http://localhost:8011
echo API Docs: http://localhost:8011/docs
echo MCP Server: http://localhost:8012
echo Frontend: http://localhost:5173
echo.
echo Close the individual command windows to stop services
echo ========================================
echo.
pause
