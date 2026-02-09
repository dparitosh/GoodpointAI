# Application Capabilities & Feature Guide

This guide details the capabilities, user interface navigation, and the underlying Agentic AI architecture of the GraphTrace platform.

---

## 1. Multi-Agent Architecture
The system is not just a standard web app; it is powered by a **Swarm of Specialized AI Agents** coordinated via the Model Context Protocol (MCP).

| Agent Name | Role | Responsibilities | Used In UI |
| :--- | :--- | :--- | :--- |
| **Chat Coordinator** | *The Router* | Analyzes user input, detects intent, and routes tasks to the correct specialist agent. | All Chat Interfaces |
| **ETL Orchestrator** | *The Mover* | Connects to source DBs, discovers schemas, runs "Smart Mapping", orchestrates data movement. | Migration Wizard |
| **Data Analyst** | *The Query Expert* | Translates English -> SQL (Relational) or Cypher (Graph). Understands deep analytics. | Search, Analytics Hub |
| **Visualization Agent** | *The Artist* | Takes raw data and decides how to present it (Line Chart vs Bar vs Table). | Analytics Hub, Dashboards |
| **Query Planner** | *The Strategist* | Breaks down complex multi-step questions (e.g., "Compare X and Y") into sub-tasks. | Conversational Search |
| **Quality Monitor** | *The Auditor* | Runs background scans using SODA/Great Expectations to find anomalies. | Quality Reports |

### Agent Behavior & Interaction Model
Unlike traditional "stateless" API endpoints, the agents in GraphTrace operate as **autonomous, goal-directed entities**. When a user initiates a request (e.g., "Map this schema"), the agent does not merely execute a hardcoded script. Instead, it:
1.  **Decomposes the Goal**: Break downs the high-level objective into a sequence of logical steps (Plan).
2.  **Selects Tools**: Dynamically chooses the right MCP tools for the job (e.g., `read_schema`, `generate_embedding`, `run_sql`).
3.  **Executes & Reasons**: Performs actions and analyzes the output. If a step fails (e.g., a query syntax error), the agent observes the error message, self-corrects the query, and retries without crashing the workflow.
4.  **Collaborates**: Agents communicate via the **Chat Coordinator**. If the *Data Analyst* realizes a user is asking for a chart, it hands off the processed data to the *Visualization Agent* to render the final graphic.
This behavior transforms the system from a passive tool into an active **Co-Pilot**, capable of handling ambiguity and complex multi-stage workflows.

---

## 2. Capability Guide by UI Tab

The navigation bar is organized into 5 primary Functional Areas.

### A. Migration Tab (`/migration`)
**Core Capability**: Moving data from Legacy SQL to Knowledge Graph.
*   **Agent involved**: `ETL Orchestrator`.
*   **Workflow Steps**:
    1.  **Connect**: Select Source (Legacy PLM) and Target (Neo4j).
    2.  **Schema (Discovery)**: The Agent scans the source DB metadata (tables, types, FKs) automatically. *No manual DDL entry required.*
    3.  **Map**: The Agent uses Embeddings to match columns (e.g., `part_no` ≈ `ComponentID`). User reviews confidence scores.
    4.  **Validate**: SODA checks run on sample data to ensure quality.
    5.  **Execute**: The actual data pipeline runs.

### B. Search Tab (`/search`)
**Core Capability**: Asking questions about your data in plain English.
*   **Agents involved**: `Chat Coordinator`, `Data Analyst`, `Query Planner`.
*   **Features**:
    *   **Conversational Interface**: Chat-like experience.
    *   **Reasoning Chain**: click to see *how* the AI built the SQL query.
    *   **Multi-Source**: Can query Postgres (metrics) and Neo4j (relationships) simultaneously.

### C. Insights Tab (`/analytics` & group)
**Core Capability**: Deep-dive reporting and visual analysis.
This section is split into sub-modules:

1.  **Analytics Hub (`/analytics`)**:
    *   **Query Builder**: Drag-and-drop UI to build queries without code.
    *   **Natural Language**: The `Data Analyst Agent` interface for generating reports.
    *   **Quality Reports**: View the results of the `Quality Monitor Agent`'s background scans.
2.  **Data Lineage (`/lineage`)**:
    *   **Visual Graph**: See upstream/downstream dependencies.
    *   **Impact Analysis**: Click a node to simulate "If I change this field, what breaks?"
3.  **Observability (`/observability`)**:
    *   **System Health**: Real-time stats on API latency and Agent status.
4.  **Self-Healing (`/self-healing`)**:
    *   **Circuit Breakers**: Monitor pipelines that stopped due to errors.
    *   **Auto-Fix**: Trigger AI remediation scripts.

### D. Workflows Tab (`/rule-engine`)
**Core Capability**: Logic and Governance.
*   **Rule Engine**: Define "Blocker" rules (e.g., "Cost cannot be negative").
*   **Workflow Manager**: View the history of all Agentic executions (success/fail logs).

### E. Advanced Tab (`/graph-explorer`)
**Core Capability**: Direct lower-level access.
*   **Graph Explorer**: Raw access to the Neo4j database using Cypher queries.
*   **Multi-Modal Analyzer**: Upload PDFs/Images. Uses Vision Models (LLaVA) to extract data from diagrams/screenshots.

---

## 3. Technology Stack

*   **Frontend**: React 18, Vite, React Flow (Graph Viz), ECharts (Charts).
*   **Backend**: Python 3.12, FastAPI, Pydantic (Data Validation).
*   **AI/LLM**:
    *   **Orchestration**: Custom MCP Server.
    *   **Models**: Supports Local LLMs (Ollama) or Azure OpenAI.
    *   **Vector DB**: OpenSearch (for semantic search).
*   **Data Stores**:
    *   **PostgreSQL**: Primary transactional store.
    *   **Neo4j**: Knowledge Graph & Lineage store.
