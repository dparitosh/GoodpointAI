# System Architecture

## Overview
GraphTrace uses a **Multi-Agent Architecture** powered by the **Model Context Protocol (MCP)** to deliver intelligent data migration, lineage, and analytics.

## Components

### 1. Frontend (`frontend/e2etraceapp`)
- **Framework**: React 18, Vite.
- **State Management**: React Query, Context API.
- **Micro-Frontend/Components**:
  - `MigrationWizard`: Orchestrates the ETL agent workflow.
  - `GraphExplorer`: Visualizes Neo4j data (Cytoscape/ReactFlow).
  - `ConversationalSearch`: Chat interface for the Data Analyst agent.

### 2. Backend (`backend/python_backend`)
- **Framework**: FastAPI (Python 3.11+).
- **Architecture**: Modular Monolith with Router-Service-Repository pattern.
- **Database**:
  - **Primary**: PostgreSQL (Data persistence, Config).
  - **Graph**: Neo4j (Lineage, optional).
  - **Search**: OpenSearch (Vector/Fulltext, optional).
- **Authentication**: JWT / API Key.

### 3. MCP Server & Agents
The system uses `mcp-server` to coordinate specialized AI agents:
- **ETL Orchestrator**: Handles schema discovery, mapping, and validation.
- **Data Analyst**: Translates NL to SQL/Cypher.
- **Query Planner**: Decomposes complex questions into sub-queries.
- **Quality Monitor**: Proactively scans for data anomalies.
- **Visualization Agent**: Suggests and formats charts.

## Data Flow

1.  **Migration**: Source -> ETL Agent -> Staging -> Validation -> Neo4j/Postgres.
2.  **Search**: User Prompt -> Chat Coordinator -> Data Analyst -> SQL/Cypher -> Result.

## Deployment
- **Local**: PowerShell orchestration (`start-all.ps1`).
- **Cloud**: Azure App Service (Zip deploy / Container).
