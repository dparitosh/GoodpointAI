# Agent Services

This directory contains the independent microservices for the Agentic AI system.
Each service is a standalone FastAPI application that registers with the central MCP Server (Port 8012).

## Service Architecture

| Service | Port | Description |
| :--- | :--- | :--- |
| **Data Analyst** | 8020 | Analyzes graph patterns and executes data queries |
| **ETL Orchestrator** | 8021 | Manages data pipelines and transformations |
| **Visualization** | 8022 | Generates graph layouts and chart configurations |
| **Query Planner** | 8023 | Optimizes Cypher queries and execution plans |
| **Quality Monitor** | 8024 | Monitors data integrity and detects anomalies |
| **Chat Coordinator** | 8025 | Handles natural language processing and intent routing |

## Base Framework

All agents inherit from `agent_services.base.agent_service.AgentService`.
This base class handles:
- FastAPI app initialization
- Health checks (`/health`)
- Info endpoints (`/info`)
- MCP Registration (`POST /mcp/v1/agents/register`)
- Task Execution wrapper (`POST /execute`)

## Running Agents

Use the provided PowerShell scripts in the root directory:
- `start-agent-data-analyst.ps1`
- `start-agent-etl-orchestrator.ps1`
- etc.

Or start the full stack with `start-all.ps1`.
