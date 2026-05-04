# GraphTrace Agent System — Low-Level Specification

> **Version**: 1.0 · **Date**: 2026-05-02  
> **Scope**: All agent microservices, the MCP Orchestrator, DAGExecutor, and every interaction contract between them.

---

## Table of Contents

1. [System Architecture Overview](#1-system-architecture-overview)
2. [Communication Protocol](#2-communication-protocol)
3. [Base Agent Contract](#3-base-agent-contract)
4. [MCP Server (Orchestrator)](#4-mcp-server-orchestrator)
5. [DAGExecutor](#5-dagexecutor)
6. [Agent 1 — ChatCoordinator (Director)](#6-agent-1--chatcoordinator-director)
7. [Agent 2 — TaskDecomposer (Planner)](#7-agent-2--taskdecomposer-planner)
8. [Agent 3 — DataDiscovery](#8-agent-3--datadiscovery)
9. [Agent 4 — DataAnalyst](#9-agent-4--dataanalyst)
10. [Agent 5 — ETLOrchestrator](#10-agent-5--etlorchestrator)
11. [Agent 6 — QualityMonitor](#11-agent-6--qualitymonitor)
12. [Agent 7 — QueryPlanner](#12-agent-7--queryplanner)
13. [Agent 8 — VisualizationAgent](#13-agent-8--visualizationagent)
14. [Capability Routing Algorithm](#14-capability-routing-algorithm)
15. [DAG Execution Flow](#15-dag-execution-flow)
16. [Full Interaction Sequences](#16-full-interaction-sequences)
17. [Data Models Reference](#17-data-models-reference)
18. [Port and URL Registry](#18-port-and-url-registry)

---

## 1. System Architecture Overview

```
┌──────────────────────────────────────────────────────────────────────────┐
│                        GraphTrace Agent System                           │
│                                                                          │
│   ┌──────────┐     HTTP     ┌─────────────────────────────────────────┐ │
│   │  Client  │ ──────────▶ │           MCP Server :8012              │ │
│   │ (FastAPI │             │  ┌────────────────┐  ┌────────────────┐  │ │
│   │ backend  │ ◀────────── │  │  Orchestrator  │  │  DAGExecutor   │  │ │
│   │  :8011)  │             │  │  (cap routing) │  │  (dep-ordered) │  │ │
│   └──────────┘             │  └───────┬────────┘  └───────┬────────┘  │ │
│                            │          │                    │           │ │
│                            └──────────┼────────────────────┼───────────┘ │
│                                       │ HTTP/POST          │             │
│                    ┌──────────────────┼────────────────────┘             │
│                    ▼                  ▼                                   │
│   ┌──────────────────────────────────────────────────────────────────┐  │
│   │                     Agent Microservices                          │  │
│   │                                                                  │  │
│   │  ┌───────────────┐  ┌────────────────┐  ┌─────────────────────┐ │  │
│   │  │ ChatCoord     │  │ TaskDecomposer │  │  DataDiscovery      │ │  │
│   │  │ :8025         │  │ :8027          │  │  :8026              │ │  │
│   │  │ (Director)    │  │ (Planner)      │  │  (File scanner)     │ │  │
│   │  └───────────────┘  └────────────────┘  └─────────────────────┘ │  │
│   │                                                                  │  │
│   │  ┌───────────────┐  ┌────────────────┐  ┌─────────────────────┐ │  │
│   │  │ DataAnalyst   │  │ ETLOrchestrator│  │  QualityMonitor     │ │  │
│   │  │ :8020         │  │ :8021          │  │  :8024              │ │  │
│   │  │ (Neo4j+PG)    │  │ (Pipelines)    │  │  (Rules+SODA)       │ │  │
│   │  └───────────────┘  └────────────────┘  └─────────────────────┘ │  │
│   │                                                                  │  │
│   │  ┌───────────────┐  ┌────────────────┐                          │  │
│   │  │ QueryPlanner  │  │ Visualization  │                          │  │
│   │  │ :8023         │  │ :8022          │                          │  │
│   │  │ (Cypher opt.) │  │ (Layouts)      │                          │  │
│   │  └───────────────┘  └────────────────┘                          │  │
│   └──────────────────────────────────────────────────────────────────┘  │
│                                                                          │
│   External stores (accessed by agents directly or via backend API):      │
│   ┌────────────┐  ┌────────────────┐  ┌──────────────────────────────┐ │
│   │ Neo4j :7687│  │ Postgres :5433 │  │ Filesystem (folder sources)  │ │
│   └────────────┘  └────────────────┘  └──────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────────┘
```

**Key design decisions:**

| Decision | Detail |
|---|---|
| All agents are independent FastAPI processes | No shared memory; all interaction via HTTP |
| MCP Server is the single task router | Clients submit tasks to `:8012/mcp/v1/tasks` |
| Capability-score routing | Agent selected by `|intersection(required, agent_caps)| / |required|` |
| DAGExecutor handles multi-step plans | Dependency-ordered, parallel-where-possible |
| Auto-registration heartbeat | Every agent re-registers with MCP every 30 s |
| Postgres is authoritative config store | No direct ORM from agents; all DB access via backend API |

---

## 2. Communication Protocol

### 2.1 Task Submission — Single Task

**Endpoint**: `POST http://127.0.0.1:8012/mcp/v1/tasks`

**Request body** (`AgenticTask`):

```json
{
  "id": "t_abc123",
  "type": "data_analysis",
  "required_capabilities": ["data_analysis"],
  "payload": {
    "analysis_type": "connectivity",
    "limit": 20
  },
  "priority": 5,
  "subtasks": []
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `id` | string | yes | Unique task identifier |
| `type` | TaskType enum | yes | Routing hint (see §17) |
| `required_capabilities` | string[] | yes | Capabilities the assigned agent must have |
| `payload` | object | yes | Agent-specific input data |
| `priority` | int 1–10 | no | Higher = more urgent (default 5) |
| `subtasks` | AgenticSubtask[] | no | Pre-built DAG; if non-empty, DAGExecutor runs it instead of routing the parent |

**Response body** (`AgenticTaskResult`):

```json
{
  "task_id": "t_abc123",
  "agent_id": "data_analyst_1777658707",
  "agent_type": "data_analyst",
  "success": true,
  "result": { "analysis_type": "connectivity", "data": [...] },
  "error": null,
  "execution_time": 0.32,
  "timestamp": "2026-05-02T09:00:00"
}
```

### 2.2 Task Submission — Pre-built DAG

**Endpoint**: `POST http://127.0.0.1:8012/mcp/v1/tasks/dag`

**Request body** (`DagSubmission`):

```json
{
  "parent_task_id": "dag_abc",
  "goal": "migrate schema from sampletest",
  "priority": 5,
  "subtasks": [
    {
      "id": "st_001",
      "type": "data_discovery",
      "required_capabilities": ["discover_files", "profile_files"],
      "payload": { "source_name": "sampletest", "include_profiling": true },
      "dependencies": [],
      "priority": 8
    },
    {
      "id": "st_002",
      "type": "data_quality_scan",
      "required_capabilities": ["monitor_data_quality"],
      "payload": { "source_name": "sampletest" },
      "dependencies": ["st_001"],
      "priority": 7
    }
  ]
}
```

**Response**: Same `AgenticTaskResult` with nested `subtask_results[]`.

### 2.3 Agent Registration

**Endpoint**: `POST http://127.0.0.1:8012/mcp/v1/agents/register`

**Request body** (`AgentDefinition`):

```json
{
  "id": "data_analyst-default",
  "type": "data_analyst",
  "name": "Data Analyst Agent",
  "service_url": "http://localhost:8020",
  "capabilities": [
    { "name": "data_analysis", "description": "...", "parameters": {} }
  ],
  "status": "ready",
  "metadata": { "version": "1.0.0" }
}
```

### 2.4 Direct Agent Execution

Every agent also exposes its own `POST /execute` endpoint for direct invocation:

**Endpoint**: `POST http://127.0.0.1:<port>/execute`

**Request body** (`AgentTaskRequest`):

```json
{
  "task_id": "t_001",
  "task_type": "data_analysis",
  "payload": { "analysis_type": "simple_pattern" },
  "priority": 5,
  "context": {}
}
```

**Response** (`AgentTaskResponse`):

```json
{
  "task_id": "t_001",
  "status": "completed",
  "result": { ... },
  "error": null,
  "execution_time_ms": 320.5,
  "completed_at": "2026-05-02T09:00:00"
}
```

---

## 3. Base Agent Contract

**File**: `agent_services/base/agent_service.py`

Every agent extends `AgentService(ABC)` and must implement:

```python
def get_capabilities(self) -> List[AgentCapability]:
    ...  # return list of this agent's capabilities

async def process_task(self, task: AgentTaskRequest) -> Dict[str, Any]:
    ...  # core logic; return result dict
```

### 3.1 Lifecycle

```
uvicorn starts
    │
    ├─▶ FastAPI lifespan startup
    │       ├─▶ asyncio.create_task(_maintain_registration())
    │       └─▶ agent-specific init (Neo4j driver, Postgres pool, etc.)
    │
    ├─▶ _maintain_registration() loop (every 30 s)
    │       └─▶ POST /mcp/v1/agents/register  ← heartbeat keeps MCP registry fresh
    │
    └─▶ HTTP server ready
            ├─▶ GET  /health          → {"status":"healthy","agent_id":"..."}
            ├─▶ GET  /info            → {id, type, name, capabilities[]}
            └─▶ POST /execute         → AgentTaskResponse
```

### 3.2 Standard HTTP routes (all agents)

| Method | Path | Description |
|---|---|---|
| GET | `/health` | Liveness check. Returns `{"status":"healthy","agent_id":"..."}` |
| GET | `/info` | Returns full agent metadata and capability list |
| POST | `/execute` | Execute a task. Calls `process_task()` internally |

---

## 4. MCP Server (Orchestrator)

**File**: `mcp_server/main.py`, `mcp_server/orchestrator.py`  
**Port**: `8012` (bound to `127.0.0.1`)

### 4.1 Goals and Objectives

- Single entry point for all task routing in the agent system
- Maintains a live registry of all agent definitions and their capabilities
- Selects the best-matching agent for each task via capability scoring
- Forwards tasks to the selected agent's `/execute` endpoint via HTTP
- Manages a DAGExecutor instance for multi-step task execution
- Tracks task results and system metrics
- Optionally integrates Redis (StateManager) for distributed state

### 4.2 Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/health` | Liveness + Neo4j connection status |
| GET | `/metrics` | Prometheus metrics |
| GET | `/mcp/v1/agents` | List all registered agents |
| POST | `/mcp/v1/agents/register` | Register or update an agent |
| POST | `/mcp/v1/tasks` | Submit a task (single or DAG if subtasks present) |
| GET | `/mcp/v1/tasks/{task_id}` | Get task result by ID |
| POST | `/mcp/v1/tasks/dag` | Submit a pre-built DAG of subtasks |
| GET | `/mcp/v1/capabilities` | Map of capability → [agent_id, …] |
| GET | `/mcp/v1/system/status` | Full system status snapshot |

### 4.3 Agent Registry

On startup, `_initialize_agents()` pre-populates the registry with static entries for all 8 agent types using their default ports. Each microservice's 30 s heartbeat then upserts its own live entry with `{agent_type}-default` as the ID.

Two registry entries coexist for each running agent:
- `{agent_type}_{timestamp}` — static entry created at MCP startup
- `{agent_type}-default` — live entry registered by the microservice itself

Both are eligible for routing. The latest-registered entry wins when capabilities are tied.

### 4.4 Capability Routing — `select_best_agent()`

```python
score = len(intersection(required_capabilities, agent.capabilities)) / len(required_capabilities)
```

- Iterates all registered agents
- Computes coverage score for each
- Returns the agent with the highest score
- On tie: last-iterated agent (dict insertion order)
- On zero score (no match): raises `HTTPException(503)`

### 4.5 Task Execution Flow (single task)

```
POST /mcp/v1/tasks
    │
    ▼  DAGExecutor.execute_task_with_subtasks(task)
    │
    ├─ task.subtasks is non-empty?
    │     YES → DAG execution path (see §5)
    │     NO  ↓
    │
    ▼  orchestrator.execute_task(task)
    │
    ├─ select_best_agent(required_capabilities) → agent
    │
    ├─ POST agent.service_url + "/execute"
    │       payload: AgentTaskRequest(task_id, task_type, payload, priority)
    │
    └─ wrap response → AgenticTaskResult
```

---

## 5. DAGExecutor

**File**: `mcp_server/dag_executor.py`

### 5.1 Goals

Execute a list of subtasks in dependency order, running independent subtasks concurrently.

### 5.2 Algorithm

```
execute_task_with_subtasks(task):
    if task.subtasks is empty:
        return orchestrator.execute_task(task)   ← plain single-agent dispatch

    pending = {st.id: st for st in task.subtasks}
    completed_ids = set()

    LOOP while pending is not empty:
        ready = [st for st in pending if all(dep in completed_ids for dep in st.dependencies)]

        if ready is empty and pending is not empty:
            ABORT → deadlock detected

        results = await asyncio.gather(*[orchestrator.execute_task(st) for st in ready])

        for each (st, result) in zip(ready, results):
            mark st COMPLETED or FAILED
            add st.id to completed_ids
            remove st from pending

    return AgenticTaskResult{
        subtask_results: [r.model_dump() for r in subtask_results.values()]
    }
```

**Concurrency**: All subtasks whose dependencies are satisfied in the same iteration are dispatched with `asyncio.gather()` — true parallel HTTP calls.

**Failure handling**: A crashed subtask (exception) is marked `FAILED` and removed from `pending`, but execution continues for other subtasks. Final `success` is `True` only if all subtasks ended `COMPLETED`.

---

## 6. Agent 1 — ChatCoordinator (Director)

**File**: `agent_services/chat_coordinator/main.py`  
**Port**: `8025`  
**Role**: System entry point for all natural language requests. Classifies intent, orchestrates multi-agent DAGs.

### 6.1 Goals and Objectives

- Accept free-text user messages from the frontend or backend
- Classify intent using keyword matching
- For complex goals (e.g. migration): delegate to TaskDecomposer, then submit a DAG to MCP
- For single-agent goals: dispatch a task directly to MCP with the right capability
- For conversational input: return a helpful response without dispatching any agent
- Maintain optional Neo4j connectivity for graph-aware conversations

### 6.2 Capabilities

| Capability | Description |
|---|---|
| `process_natural_language` | Classify user intent from free-text messages |
| `coordinate_agent_responses` | Director: decompose goal and dispatch multi-agent DAG |
| `manage_conversation_context` | Maintain conversation history and context |
| `route_user_requests` | Route user requests to the correct specialist agent |

### 6.3 Intent Classification

`_classify_intent(message)` scans `_INTENT_MAP` in priority order:

| Keywords matched | Intent | Dispatches to | Capability required |
|---|---|---|---|
| migrate, schema, etl migration | `migration` | TaskDecomposer → DAG | `decompose_goal` |
| analyze, pattern, trend, distribution, insight | `data_analysis` | DataAnalyst | `data_analysis` |
| quality, dq, scan, anomaly, validate | `quality_check` | QualityMonitor | `monitor_data_quality` |
| discover, files, profile, catalog, infer schema | `data_discovery` | DataDiscovery | `discover_files` |
| pipeline, etl, load, transform | `etl_request` | ETLOrchestrator | `manage_data_pipelines` |
| chart, plot, visualize, graph layout | `visualization` | DataAnalyst + Viz | `generate_graph_layouts` |
| query, cypher, match, neo4j | `graph_query` | DataAnalyst | `execute_cypher_queries` |
| sql, postgres, table, select | `sql_query` | DataAnalyst | `sql_query` |
| *(no match)* | `general_chat` | *(none)* | — |

### 6.4 Task Input

```json
{
  "task_id": "...",
  "task_type": "chat_processing",
  "payload": {
    "message": "I need to migrate schema from sampletest"
  },
  "priority": 5
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `message` | string | yes | Free-text user input |
| `goal` | string | no | Alias for `message` |

### 6.5 Task Output

**Simple response** (no agent dispatch):

```json
{
  "status": "completed",
  "task_id": "...",
  "primaryResponse": "I received: '...'. How can I help?",
  "intent": "general_chat",
  "collaborationNeeded": false,
  "followupQuestions": ["Would you like to analyze your data?", "..."]
}
```

**Multi-agent DAG result** (migration intent):

```json
{
  "status": "completed",
  "task_id": "...",
  "primaryResponse": "Decomposing migration into discovery → quality → ETL pipeline...",
  "intent": "migration",
  "collaborationNeeded": true,
  "plan": {
    "subtask_count": 3,
    "subtasks": [
      { "id": "st_001", "type": "data_discovery", "capabilities": ["discover_files","profile_files"], "depends_on": [] },
      { "id": "st_002", "type": "data_quality_scan", "capabilities": ["monitor_data_quality"], "depends_on": ["st_001"] },
      { "id": "st_003", "type": "pipeline_orchestration", "capabilities": ["manage_data_pipelines"], "depends_on": ["st_002"] }
    ]
  },
  "execution_result": { "subtask_results": [...] }
}
```

**Single-agent dispatch result**:

```json
{
  "status": "completed",
  "task_id": "...",
  "primaryResponse": "Running data analysis...",
  "intent": "data_analysis",
  "collaborationNeeded": true,
  "agent_type": "data_analysis",
  "capabilities_used": ["data_analysis"],
  "agent_result": { ... }
}
```

### 6.6 Internal Flow (Migration)

```
process_task(message="migrate schema from sampletest")
    │
    ├─▶ _classify_intent()  → intent="migration", needs_agents=True
    │
    ├─▶ _decompose_goal(message, task_id)
    │       └─▶ POST MCP /mcp/v1/tasks
    │               type="task_decomposition"
    │               required_capabilities=["decompose_goal"]
    │               payload={goal: message, parent_task_id: task_id}
    │           ◀── {subtasks: [disc, qual, etl]}
    │
    ├─▶ _submit_dag(dag_id, message, subtasks)
    │       └─▶ POST MCP /mcp/v1/tasks/dag
    │               {parent_task_id, goal, subtasks}
    │           ◀── AgenticTaskResult with subtask_results
    │
    └─▶ return composed response with plan + execution_result
```

### 6.7 Timeouts

| Operation | Timeout |
|---|---|
| `_decompose_goal()` → MCP | 15 s |
| `_submit_dag()` → MCP/DAGExecutor | 90 s |
| `_dispatch_single()` → MCP | 30 s |

---

## 7. Agent 2 — TaskDecomposer (Planner)

**File**: `agent_services/task_decomposer/main.py`  
**Port**: `8027`  
**Role**: Translates a free-text goal string into a dependency-ordered subtask DAG.

### 7.1 Goals and Objectives

- Accept a natural language goal from ChatCoordinator
- Match the goal against a library of 8 known templates via keyword matching
- Produce a list of concrete subtasks with typed `required_capabilities` and `dependencies`
- Extract source/data-source names from the goal text to propagate into subtask payloads
- Return the complete DAG so the caller (ChatCoordinator) can submit it via `/mcp/v1/tasks/dag`

### 7.2 Capabilities

| Capability | Description |
|---|---|
| `decompose_goal` | Decompose a high-level goal into a dependency-ordered subtask DAG |
| `build_task_dag` | Produce subtask DAG with capability requirements and dependencies |
| `decompose_task` | Break a complex task into atomic executable subtasks |

### 7.3 Task Input

```json
{
  "task_id": "decomp_abc",
  "task_type": "task_decomposition",
  "payload": {
    "goal": "migrate schema from sampletest (local_folder) [active]",
    "parent_task_id": "chat_task_001"
  }
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `goal` | string | yes | Natural language goal to decompose |
| `message` | string | no | Alias for `goal` |
| `source_name` | string | no | Override extracted source name |
| `source` | string | no | Legacy alias for source name |

### 7.4 Source Name Extraction — `_extract_source(payload)`

Regex search on the `goal` field:

1. Match `from <name>` — captures text before `(` or end-of-line
2. Fallback: Match `source <name>`
3. Strips whitespace; ignores `"unknown"` and empty strings
4. Returns `{"source_name": "<extracted>"}` or `{}`

**Example**: `"migrate schema from sampletest (local_folder)"` → `{"source_name": "sampletest"}`

### 7.5 Goal Templates

Each template is a builder function `(task_id, payload) → List[subtask_dict]`.

Templates are matched in this order (first match wins):

| Priority | Keywords | Template | DAG Shape |
|---|---|---|---|
| 1 | migrate, migration, schema migration | `_build_migration_dag` | discover → quality_scan → etl |
| 2 | file batch, bulk process, batch process | `_build_file_batch_dag` | etl (batch) |
| 3 | visualize, chart, plot, graph layout | `_build_visualization_dag` | data_analysis → visualization |
| 4 | cypher, neo4j query, graph query | `_build_query_dag` | query_plan → cypher_exec |
| 5 | quality, dq scan, data quality, anomaly, validate | `_build_quality_dag` | quality_scan → insights |
| 6 | discover, profile files, file catalog, infer schema | `_build_discovery_dag` | discovery (single) |
| 7 | etl, pipeline, load data, transform | `_build_etl_dag` | discover → etl |
| 8 | analyze, analysis, pattern, trend, insight | `_build_analysis_dag` | discover → analysis |
| default | *(no match)* | `_build_analysis_dag` | discover → analysis |

#### Template Details

**`_build_migration_dag`** — Schema Migration (3 subtasks, sequential):

```
[st_1] data_discovery
       caps: [discover_files, profile_files]
       payload: {source_name, include_profiling: true}
       deps: []
       priority: 8
    ↓
[st_2] data_quality_scan
       caps: [monitor_data_quality]
       payload: {source_name}
       deps: [st_1]
       priority: 7
    ↓
[st_3] pipeline_orchestration
       caps: [manage_data_pipelines]
       payload: {source_name, action: "build_migration"}
       deps: [st_2]
       priority: 6
```

**`_build_analysis_dag`** — Data Analysis (2 subtasks, sequential):

```
[st_1] data_discovery     caps: [discover_files]    deps: []
    ↓
[st_2] data_analysis      caps: [data_analysis]     deps: [st_1]
                           payload: {analysis_type: "simple_pattern"}
```

**`_build_quality_dag`** — Quality Check (2 subtasks, sequential):

```
[st_1] data_quality_scan  caps: [monitor_data_quality]     deps: []
    ↓
[st_2] data_analysis      caps: [generate_insights]        deps: [st_1]
                           payload: {analysis_type: "quality_summary"}
```

**`_build_discovery_dag`** — File Discovery (1 subtask):

```
[st_1] data_discovery     caps: [discover_files, profile_files, infer_schema]
                           payload: {source_name, include_profiling: true}
```

**`_build_etl_dag`** — ETL Pipeline (2 subtasks, sequential):

```
[st_1] data_discovery          caps: [discover_files]           deps: []
    ↓
[st_2] pipeline_orchestration  caps: [manage_data_pipelines]    deps: [st_1]
```

**`_build_visualization_dag`** — Visualization (2 subtasks, sequential):

```
[st_1] data_analysis            caps: [data_analysis]            deps: []
                                 payload: {analysis_type: "connectivity"}
    ↓
[st_2] visualization_generation caps: [generate_graph_layouts]   deps: [st_1]
```

**`_build_query_dag`** — Graph Query (2 subtasks, sequential):

```
[st_1] graph_query  caps: [optimize_graph_queries]    payload: {query}   deps: []
    ↓
[st_2] graph_query  caps: [execute_cypher_queries]    payload: {cypher_query}  deps: [st_1]
```

**`_build_file_batch_dag`** — File Batch (1 subtask):

```
[st_1] file_batch_processing  caps: [file_batch_processing]
                               payload: {directory, recursive: true, extraction_method: "hybrid"}
```

### 7.6 Task Output

```json
{
  "decomposition_status": "success",
  "original_goal": "migrate schema from sampletest (local_folder) [active]",
  "template_used": "migrate",
  "subtask_count": 3,
  "subtasks": [
    {
      "id": "st_1a68bd9c",
      "parent_task_id": "decomp_abc",
      "type": "data_discovery",
      "required_capabilities": ["discover_files", "profile_files"],
      "payload": { "source_name": "sampletest", "include_profiling": true },
      "dependencies": [],
      "priority": 8
    },
    ...
  ],
  "execution_order": ["st_1a68bd9c", "st_4e9747f5", "st_078352fc"]
}
```

---

## 8. Agent 3 — DataDiscovery

**File**: `agent_services/data_discovery/main.py`  
**Port**: `8026`  
**Role**: File system enumeration, pandas-based profiling, schema inference, quality check delegation.

### 8.1 Goals and Objectives

- Resolve a data source (by `source_id`, `source_name`, or direct `folder_path`) to a local filesystem path
- Enumerate all files recursively within the resolved folder
- Profile each file using pandas — row counts, column stats, null rates, type inference
- Optionally infer semantic data types (identifier, categorical, timestamp, decimal, etc.)
- Run quality checks per file (SODA Core if available, else builtin pandas checks)
- Build a data catalog entry for a registered source
- Optionally fire-and-forget a `DATA_QUALITY_SCAN` task to QualityMonitor via MCP

### 8.2 Capabilities

| Capability | Description |
|---|---|
| `discover_files` | Enumerate all files in a folder-type data source |
| `profile_files` | Per-file row count, column count, null rates, type hints |
| `catalog_datasource` | Build a data catalog entry for a registered data source |
| `scan_folder_quality` | Run quality checks across all files in a folder data source |
| `infer_schema` | Infer column types and schema from CSV/JSON/XML samples |

### 8.3 Source Resolution — `_resolve_folder_path(source_id, folder_path, source_name)`

Resolution priority:

1. **`folder_path`** — used directly if provided
2. **`source_id`** — `GET http://localhost:8011/api/data-sources/{source_id}` → extract `connection.folder_path` / `file_path` / `connection_string` / `uri`
3. **`source_name`** — `GET http://localhost:8011/api/data-sources?limit=200` → fuzzy name match (`name_lower in ds_name or ds_name in name_lower`) → extract same connection fields

### 8.4 Task Input (`_handle_discovery`)

```json
{
  "task_id": "...",
  "task_type": "data_discovery",
  "payload": {
    "source_id": "conn_abc123",
    "source_name": "sampletest",
    "folder_path": "D:\\data\\files",
    "recursive": true,
    "include_profiling": true
  }
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `source_id` | string | no | Registered data source ID (looked up via backend API) |
| `source_name` | string | no | Source display name (fuzzy matched against backend list) |
| `folder_path` | string | no | Direct filesystem path (overrides source lookup) |
| `recursive` | bool | no | Whether to recurse subdirectories (default `true`) |
| `include_profiling` | bool | no | Whether to run per-file profiling (default `true`) |

### 8.5 File Discovery — `_discover_files(folder, recursive)`

Enumerates all files under `folder` using `Path.glob("**/*")`.

Returns per file:

```json
{
  "path": "D:\\data\\files\\orders.csv",
  "name": "orders.csv",
  "ext": ".csv",
  "file_type": "csv",
  "size_bytes": 48291,
  "modified_at": "2025-11-15T14:22:00"
}
```

Supported file types: `csv`, `tsv`, `json`, `jsonl`, `xml`, `xlsx`, `xls`, `parquet`, `avro`, `pdf`, `txt`, `log`, `png/jpg/jpeg` (image), `step/stp/igs/iges` (cad), `other`.

### 8.6 File Profiling — `_profile_file(file_meta)`

Uses pandas to load file into a DataFrame:

| File type | Parser |
|---|---|
| csv/tsv | `pd.read_csv()` with encoding fallback: utf-8-sig → cp1252 → latin-1 |
| xlsx/xls | `pd.read_excel()` with openpyxl; fallback to xlrd |
| json/jsonl | `pd.read_json()` |
| parquet | `pd.read_parquet()` |
| xml | `pd.read_xml()` |

Per-column statistics computed:

| Stat | Type | Description |
|---|---|---|
| `null_count` | int | Number of null cells |
| `valid_count` | int | Number of non-null cells |
| `null_rate` | float | `null_count / row_count` |
| `null_percentage` | float | `null_rate × 100` |
| `completeness` | float | `(1 - null_rate) × 100` |
| `distinct_count` | int | Number of unique values |
| `cardinality_ratio` | float | `distinct_count / row_count` |
| `sample_values` | string[] | Up to 5 sample values |
| `distinct_values` | string[] | Up to 10 unique values |
| `top_values` | object[] | Top 5 by frequency with count and % |
| `type` | string | pandas dtype string |
| `semantic_type` | string | Inferred semantic type (see below) |
| `python_types` | string[] | Distinct Python types in column (sampled 100 rows) |
| `statistics` | object | min/max/mean/median/std_dev/q25/q75 (numeric cols only) |

**Semantic type inference** (`_infer_semantic_type`):

| Condition | Semantic Type |
|---|---|
| int/uint, cardinality > 95% | `identifier` |
| int/uint | `integer` |
| float, all values are whole numbers | `integer (stored as float)` |
| float | `decimal` |
| datetime dtype | `timestamp` |
| bool | `boolean` |
| object, parseable as datetime | `date/timestamp (as text)` |
| object, parseable as numeric | `numeric (as text)` |
| object, cardinality < 5% | `categorical` |
| object, cardinality < 50% | `semi-categorical` |
| object, high cardinality | `text` |

### 8.7 Quality Checks — `_run_quality_checks(df)`

Tries SODA Core first:

```
SODA SodaCL (if soda-core installed):
  checks for data:
    - row_count > 0
    - missing_count < 100
    - duplicate_count = 0
```

Falls back to builtin pandas checks if SODA unavailable:

| Check | Pass Condition |
|---|---|
| `row_count > 0` | `len(df) > 0` |
| `missing_count < 100` | `df.isnull().sum().sum() < 100` |
| `duplicate_count = 0` | `df.duplicated().sum() == 0` |
| `max_null_rate < 50%` | max column null rate < 0.5 |

Each check returns: `{name, outcome, fail, pass, value, engine}`.

### 8.8 Task Output

```json
{
  "status": "completed",
  "source_id": "conn_abc123",
  "folder_path": "D:\\FileHistory\\...\\import",
  "total_files": 71,
  "total_size_bytes": 67639902,
  "by_type": { "csv": 7, "xml": 8, "other": 43 },
  "file_count": 71,
  "profiles": [
    {
      "path": "...",
      "file_type": "csv",
      "row_count": 1500,
      "column_count": 12,
      "null_rate": 0.02,
      "completeness": 98.0,
      "columns": [ { "name": "order_id", "semantic_type": "identifier", ... } ],
      "quality_checks": [ { "name": "row_count > 0", "outcome": "pass", ... } ]
    }
  ]
}
```

---

## 9. Agent 4 — DataAnalyst

**File**: `agent_services/data_analyst/main.py`  
**Port**: `8020`  
**Role**: Executes Neo4j Cypher queries and Postgres SQL queries; performs structural graph analysis.

### 9.1 Goals and Objectives

- Execute read-only Cypher queries against Neo4j and return structured record sets
- Execute read-only SQL SELECT queries against Postgres with a hard 1000-row cap
- Perform graph pattern analysis (connectivity, centrality, simple node distribution)
- Generate analytical insights from query results
- Enforce security: only MATCH/RETURN/WITH/CALL/SHOW allowed for Cypher; only SELECT for SQL

### 9.2 Capabilities

| Capability | Description |
|---|---|
| `data_analysis` | Analyze graph patterns, node distributions, statistics |
| `graph_query` | Execute read-only queries against Neo4j |
| `sql_query` | Execute read-only queries against Postgres |
| `execute_cypher_queries` | Execute Cypher graph queries and return structured results |
| `generate_insights` | Generate analytical insights from graph and relational data |
| `statistical_analysis` | Perform statistical analysis on datasets |

### 9.3 Connections

| Connection | Source |
|---|---|
| Neo4j | `NEO4J_URI` / `NEO4J_USER` / `NEO4J_PASSWORD` env vars |
| Postgres | Parsed from `DATABASE_URL` env var (postgresql://user:pass@host:port/db) |

Both connections are established on startup via `AsyncGraphDatabase.driver()` and `asyncpg.create_pool()`.

### 9.4 Task Input

**Cypher query** (routes when `execute_cypher_queries` in caps OR `cypher_query` in payload):

```json
{
  "task_type": "graph_query",
  "payload": {
    "cypher_query": "MATCH (n) RETURN labels(n) as lbl, count(n) as cnt LIMIT 10",
    "required_capabilities": ["execute_cypher_queries"]
  }
}
```

**SQL query** (routes when `analysis_type == "sql_query"` OR `sql_query` key in payload):

```json
{
  "task_type": "data_analysis",
  "payload": {
    "sql_query": "SELECT * FROM connection_configs WHERE status = 'active'",
    "required_capabilities": ["sql_query"]
  }
}
```

**Graph analysis** (default):

```json
{
  "task_type": "data_analysis",
  "payload": {
    "analysis_type": "connectivity",
    "limit": 20
  }
}
```

| `analysis_type` value | Neo4j Query |
|---|---|
| `connectivity` | Pareto query: top-N nodes by degree (most connected first) |
| `centrality` | Betweenness centrality approximation via 2-hop paths |
| `simple_pattern` *(default)* | `MATCH (n) RETURN labels(n), count(n) ORDER BY count DESC LIMIT N` |

### 9.5 Security Controls

| Query type | Enforcement |
|---|---|
| Cypher | `query.strip().upper()` must start with `MATCH`, `RETURN`, `WITH`, `CALL`, or `SHOW` |
| SQL | `query.strip().lstrip("(").upper()` must start with `SELECT`. Query is further wrapped: `SELECT * FROM (query) _q LIMIT 1000` |

### 9.6 Task Output

**Cypher result**:

```json
{
  "analysis_type": "cypher_query",
  "row_count": 25,
  "data": [
    { "lbl": ["Product"], "cnt": 12 },
    ...
  ]
}
```

**SQL result**:

```json
{
  "analysis_type": "sql_query",
  "row_count": 8,
  "data": [ { "id": "...", "name": "sampletest", ... }, ... ]
}
```

**Graph analysis result**:

```json
{
  "analysis_type": "connectivity",
  "data": [
    { "nodeId": "prod_001", "labels": ["Product"], "degree": 42 },
    ...
  ]
}
```

---

## 10. Agent 5 — ETLOrchestrator

**File**: `agent_services/etl_orchestrator/main.py`  
**Port**: `8021`  
**Role**: Data pipeline management, large-scale file batch processing with lineage tracking.

### 10.1 Goals and Objectives

- Execute ETL pipelines for data loading, transformation, and migration
- Process thousands of files in parallel using `FileBatchProcessor`
- Track processing lineage to Neo4j and results to Postgres
- Support multiple extraction methods: hybrid, OCR, vision LLM, text parser
- Perform data discovery on staged records (schema inference on in-memory data)
- Monitor pipeline health and report job status

### 10.2 Capabilities

| Capability | Description |
|---|---|
| `manage_data_pipelines` | Manage ETL pipelines: build, run, monitor |
| `perform_data_discovery` | Analyze sources, stage data, and run quality checks on in-memory records |
| `handle_data_transformations` | Apply transformation rules to data |
| `monitor_pipeline_health` | Monitor pipeline execution health and report metrics |
| `file_batch_processing` | Discover and process thousands of files in parallel with lineage tracking |

### 10.3 Connections

| Connection | Source |
|---|---|
| Neo4j | `NEO4J_URI` / `NEO4J_USER` / `NEO4J_PASSWORD` env vars |
| Postgres | `DATABASE_URL` env var via SQLAlchemy `create_engine()` |

### 10.4 Task Routing in `process_task()`

```
task.payload["type"] == "discovery"
  OR "perform_data_discovery" in required_capabilities
    → perform_discovery(task)

task.payload["type"] == "file_batch_processing"
  OR "file_batch_processing" in required_capabilities
    → process_file_batch(task)

otherwise → {"status":"success", "message":"Task type acknowledged (placeholder)"}
```

### 10.5 File Batch Processing — Input

```json
{
  "task_type": "file_batch_processing",
  "payload": {
    "directory": "D:\\data\\imports",
    "recursive": true,
    "concurrency": 8,
    "db_flush_size": 50,
    "extraction_method": "hybrid",
    "vision_model": "llava:latest"
  }
}
```

| Field | Type | Default | Description |
|---|---|---|---|
| `directory` | string | — | Root directory to crawl (mutually exclusive with `file_paths`) |
| `file_paths` | string[] | — | Explicit list of absolute file paths |
| `recursive` | bool | `true` | Crawl subdirectories |
| `concurrency` | int | `8` | Parallel worker count |
| `db_flush_size` | int | `50` | Rows per Postgres flush |
| `extraction_method` | string | `"hybrid"` | `hybrid` / `ocr` / `vision_llm` / `text_parser` |
| `vision_model` | string | `"llava:latest"` | Ollama model for vision extraction |

### 10.6 File Batch Processing — Output

```json
{
  "status": "completed",
  "job_id": "abc123def",
  "total_files": 350,
  "processed": 350,
  "succeeded": 347,
  "failed": 3,
  "started_at": "2026-05-02T09:00:00",
  "completed_at": "2026-05-02T09:04:32",
  "errors_summary": [
    { "file": "D:\\data\\corrupt.pdf", "error": "..." }
  ]
}
```

---

## 11. Agent 6 — QualityMonitor

**File**: `agent_services/quality_monitor/main.py`  
**Port**: `8024`  
**Role**: Rule Engine execution, data anomaly detection, transformation validation, DQ reporting.

### 11.1 Goals and Objectives

- Execute active Rule Sets from Postgres against in-memory record payloads
- Detect data anomalies using rule expressions evaluated per-record
- Validate transformation outputs for correctness and completeness
- Delegate folder/source-level DQ scans to the FastAPI backend quality endpoint
- Generate a quality score (0–100) representing aggregate pass rate

### 11.2 Capabilities

| Capability | Description |
|---|---|
| `monitor_data_quality` | Execute quality rules and compute quality score |
| `detect_anomalies` | Detect data anomalies using rule expressions |
| `validate_transformations` | Validate data transformations post-execution |
| `generate_quality_reports` | Generate formatted quality reports with scores and breakdowns |
| `execute_rules` | Execute Rule Engine rule sets against in-memory records |

### 11.3 Connections

| Connection | Purpose |
|---|---|
| Neo4j (optional) | Graph-level quality checks |
| Backend API `http://localhost:8011` | Source DQ scans, rule set loading (via `core.db_session`) |

### 11.4 Task Routing in `process_task()`

```
"scan_datasource_quality" in caps
  OR source_id present in payload
  OR folder_path present in payload
    → _scan_datasource_via_backend(task)

otherwise:
    records = payload.get("records", [])
    → rule engine execution on records
    → compute quality_score, anomaly count
```

### 11.5 Task Input — Rule Engine Mode

```json
{
  "task_type": "data_quality_scan",
  "payload": {
    "records": [
      { "id": 1, "name": "Alice", "email": "alice@example.com" },
      { "id": 2, "name": "", "email": null }
    ],
    "entity_type": "contact"
  }
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `records` | object[] | no | In-memory records to validate |
| `entity_type` | string | no | Filters rule sets by `target_entity_type` |
| `source_id` | string | no | Triggers backend DQ scan path |
| `folder_path` | string | no | Triggers backend DQ scan path |

### 11.6 Rule Engine Execution — `_run_rule_engine_direct(records, entity_type)`

1. Opens a Postgres session via `SessionLocal()`
2. Queries all active `RuleSet` records with matching `target_entity_type` (or null)
3. For each RuleSet, loads active `Rule` records ordered by `sequence_order`
4. Calls `RuleEngine.execute_rule_set(rule_set, rules, records, stop_on_critical)`
5. Aggregates `overall_pass_rate` across all rule sets → `quality_score`

### 11.7 Task Output

```json
{
  "status": "Quality check completed",
  "task_id": "...",
  "quality_score": 87.5,
  "anomalies_found": 2,
  "rule_validation": {
    "quality_score": 87.5,
    "rule_sets_executed": 2,
    "results": [
      {
        "rule_set_id": "rs_001",
        "rule_set_name": "Contact Validation",
        "status": "completed",
        "overall_pass_rate": 87.5,
        "rules_passed": 7,
        "rules_failed": 1,
        "total_failures": 2,
        "duration_ms": 45
      }
    ]
  },
  "timestamp": "2026-05-02T09:00:00"
}
```

---

## 12. Agent 7 — QueryPlanner

**File**: `agent_services/query_planner/main.py`  
**Port**: `8023`  
**Role**: Cypher query optimization, execution plan generation, query cache management.

### 12.1 Goals and Objectives

- Analyze incoming Cypher queries and suggest optimization hints
- Generate execution strategies for multi-step graph traversals
- Manage a query result cache to avoid repeated expensive graph operations
- Analyze and report on query execution performance

### 12.2 Capabilities

| Capability | Description |
|---|---|
| `optimize_graph_queries` | Optimize Cypher queries for performance |
| `plan_execution_strategies` | Plan multi-step query execution strategies |
| `manage_query_cache` | Manage a query result cache |
| `analyze_performance` | Analyze and report on query execution performance |

### 12.3 Connections

| Connection | Source |
|---|---|
| Neo4j | `NEO4J_URI` / `NEO4J_USER` / `NEO4J_PASSWORD` env vars |

### 12.4 Task Input

```json
{
  "task_type": "graph_query",
  "payload": {
    "query": "MATCH (n:Product)-[:RELATES_TO]->(m) RETURN n, m LIMIT 100",
    "required_capabilities": ["optimize_graph_queries"]
  }
}
```

### 12.5 Task Output (current placeholder)

```json
{
  "status": "Query plan generated",
  "task_id": "...",
  "execution_plan": "Computed optimized path",
  "estimated_cost": 10,
  "timestamp": "2026-05-02T09:00:00"
}
```

> **Note**: Full query plan generation (EXPLAIN/PROFILE analysis) is not yet implemented. The current response is a placeholder. The agent is correctly wired into the capability registry and DAG routing.

---

## 13. Agent 8 — VisualizationAgent

**File**: `agent_services/visualization_agent/main.py`  
**Port**: `8022`  
**Role**: Graph layout generation, chart configuration production.

### 13.1 Goals and Objectives

- Generate graph layout configurations (force-directed, hierarchical, etc.) from Neo4j data
- Create frontend-consumable chart configuration objects
- Manage UI rendering state for graph visualization
- Handle user interaction events (node click, edge hover, zoom) to trigger re-queries

### 13.2 Capabilities

| Capability | Description |
|---|---|
| `generate_graph_layouts` | Generate optimal graph layouts from Neo4j data |
| `create_chart_configurations` | Create frontend-compatible chart config objects |

### 13.3 Connections

| Connection | Source |
|---|---|
| Neo4j | `NEO4J_URI` / `NEO4J_USER` / `NEO4J_PASSWORD` env vars |

### 13.4 Task Input

```json
{
  "task_type": "visualization_generation",
  "payload": {
    "source": "sampletest",
    "layout": "force",
    "required_capabilities": ["generate_graph_layouts"]
  }
}
```

### 13.5 Task Output (current placeholder)

```json
{
  "status": "Visualization generated",
  "task_id": "...",
  "chart_config": { "type": "bar", "data": [] },
  "timestamp": "2026-05-02T09:00:00"
}
```

> **Note**: Full Neo4j-driven layout generation is not yet implemented. The agent is correctly wired into the capability registry and DAG routing.

---

## 14. Capability Routing Algorithm

### 14.1 `select_best_agent(required_capabilities, agents)` — full pseudo-code

```python
def select_best_agent(required: List[str], agents: Dict[str, AgentDefinition]) -> AgentDefinition:
    best_agent = None
    best_score = -1.0

    for agent in agents.values():
        if agent.status != "ready":
            continue
        agent_cap_names = {c.name for c in agent.capabilities}
        intersection = set(required) & agent_cap_names
        score = len(intersection) / len(required) if required else 0.0

        if score > best_score:
            best_score = score
            best_agent = agent

    if best_agent is None or best_score == 0:
        raise HTTPException(503, "No agent available for required capabilities")

    return best_agent
```

### 14.2 Capability-to-Agent Mapping (live registry)

| Capability | Primary Agent | Port |
|---|---|---|
| `process_natural_language` | ChatCoordinator | 8025 |
| `coordinate_agent_responses` | ChatCoordinator | 8025 |
| `route_user_requests` | ChatCoordinator | 8025 |
| `decompose_goal` | TaskDecomposer | 8027 |
| `build_task_dag` | TaskDecomposer | 8027 |
| `decompose_task` | TaskDecomposer | 8027 |
| `discover_files` | DataDiscovery | 8026 |
| `profile_files` | DataDiscovery | 8026 |
| `catalog_datasource` | DataDiscovery | 8026 |
| `infer_schema` | DataDiscovery | 8026 |
| `scan_folder_quality` | DataDiscovery | 8026 |
| `data_analysis` | DataAnalyst | 8020 |
| `execute_cypher_queries` | DataAnalyst | 8020 |
| `graph_query` | DataAnalyst | 8020 |
| `sql_query` | DataAnalyst | 8020 |
| `generate_insights` | DataAnalyst | 8020 |
| `statistical_analysis` | DataAnalyst | 8020 |
| `manage_data_pipelines` | ETLOrchestrator | 8021 |
| `perform_data_discovery` | ETLOrchestrator | 8021 |
| `file_batch_processing` | ETLOrchestrator | 8021 |
| `handle_data_transformations` | ETLOrchestrator | 8021 |
| `monitor_pipeline_health` | ETLOrchestrator | 8021 |
| `monitor_data_quality` | QualityMonitor | 8024 |
| `detect_anomalies` | QualityMonitor | 8024 |
| `execute_rules` | QualityMonitor | 8024 |
| `generate_quality_reports` | QualityMonitor | 8024 |
| `scan_datasource_quality` | QualityMonitor | 8024 |
| `optimize_graph_queries` | QueryPlanner | 8023 |
| `plan_execution_strategies` | QueryPlanner | 8023 |
| `manage_query_cache` | QueryPlanner | 8023 |
| `analyze_performance` | QueryPlanner | 8023 |
| `generate_graph_layouts` | VisualizationAgent | 8022 |
| `create_chart_configurations` | VisualizationAgent | 8022 |

---

## 15. DAG Execution Flow

### 15.1 Migration Example — Full Timeline

```
User message: "migrate schema from sampletest (local_folder) [active]"

T+0.0s  POST /api/agentic/task (FastAPI backend :8011)
            → POST http://127.0.0.1:8012/mcp/v1/tasks
               type=chat_processing, caps=[process_natural_language]
               payload={message: "migrate schema from sampletest..."}

T+0.1s  MCP routes to ChatCoordinator (8025) → POST /execute
        ChatCoordinator._classify_intent() → intent="migration"

T+0.2s  ChatCoordinator._decompose_goal()
            → POST MCP /mcp/v1/tasks
               type=task_decomposition, caps=[decompose_goal]
               payload={goal: "migrate schema...", parent_task_id: "th_xxx"}
        MCP routes to TaskDecomposer (8027) → POST /execute

T+0.5s  TaskDecomposer matches template "migrate"
        _extract_source() → source_name="sampletest"
        Returns 3 subtasks: [disc(deps=[]), qual(deps=[disc]), etl(deps=[qual])]
        ChatCoordinator receives subtasks list

T+0.7s  ChatCoordinator._submit_dag()
            → POST MCP /mcp/v1/tasks/dag
               {parent_task_id: "dag_xxx", goal, subtasks: [disc, qual, etl]}

T+0.8s  DAGExecutor.execute_task_with_subtasks()
        Iteration 1: ready=[disc] (no deps)
            → POST DataDiscovery:8026/execute
               payload={source_name: "sampletest", include_profiling: true}

T+0.9s  DataDiscovery._resolve_folder_path(source_name="sampletest")
            → GET :8011/api/data-sources?limit=200
            → fuzzy match: "sampletest" ⊆ "sampletest (local_folder) [active]"
            → folder_path = "D:\FileHistory\...\import"
        _discover_files() → 71 files found
        _profile_file() × N → per-file stats
        disc subtask: COMPLETED

T+1.3s  Iteration 2: ready=[qual] (disc COMPLETED)
            → POST QualityMonitor:8024/execute
               payload={source_name: "sampletest"}
        Rule engine: no active rule sets → quality_score=100
        qual subtask: COMPLETED

T+1.8s  Iteration 3: ready=[etl] (qual COMPLETED)
            → POST ETLOrchestrator:8021/execute
               payload={source_name: "sampletest", action: "build_migration"}
        ETL: placeholder response
        etl subtask: COMPLETED

T+2.2s  DAGExecutor returns: success=true, subtask_results=[disc,qual,etl]
        ChatCoordinator wraps and returns full director response

T+4.0s  Client receives response
```

### 15.2 Parallel Execution Example — Quality DAG

For `_build_quality_dag` if subtasks had no dependencies between them they would run in parallel. The current quality DAG is sequential (scan → insights). The DAGExecutor would execute both concurrently if both had `dependencies: []`:

```python
# Concurrent dispatch (asyncio.gather)
results = await asyncio.gather(
    orchestrator.execute_task(st_scan),    # → QualityMonitor
    orchestrator.execute_task(st_insights) # → DataAnalyst
)
```

---

## 16. Full Interaction Sequences

### 16.1 Cypher Query (shortest path)

```
Client → POST MCP/tasks {type:graph_query, caps:[execute_cypher_queries], payload:{cypher_query:"MATCH ..."}}
MCP    → select_best_agent([execute_cypher_queries]) → DataAnalyst (score=1.0)
MCP    → POST :8020/execute {task_type:graph_query, payload:{cypher_query:"MATCH ..."}}
DataAnalyst → security check (MATCH prefix OK)
DataAnalyst → neo4j_driver.session().run(query)
DataAnalyst ← [{labels: ["Product"], cnt: 12}, ...]
MCP    ← AgenticTaskResult{success:true, result:{analysis_type:cypher_query, row_count:N, data:[...]}}
Client ← response
```

### 16.2 Data Discovery (single-step)

```
Client → POST MCP/tasks {type:data_discovery, caps:[discover_files], payload:{source_name:"sampletest"}}
MCP    → DataDiscovery:8026 (score=1.0)
DataDiscovery → GET :8011/api/data-sources?limit=200  ← fuzzy name match
DataDiscovery → _discover_files(folder_path) → 71 files
DataDiscovery → _profile_file() × 71
DataDiscovery ← {status:completed, total_files:71, profiles:[...], by_type:{...}}
```

### 16.3 Registration Heartbeat

```
Agent startup (any agent)
    │  asyncio.create_task(_maintain_registration())
    │
    LOOP every 30 s:
        POST MCP :8012/mcp/v1/agents/register
        {
          id: "data_discovery_agent-default",
          type: "data_discovery_agent",
          name: "Data Discovery Agent",
          service_url: "http://localhost:8026",
          capabilities: [discover_files, profile_files, catalog_datasource, scan_folder_quality, infer_schema],
          status: "ready"
        }
        ← {id, type, name, ...}   (registered/updated)
```

---

## 17. Data Models Reference

### AgentType Enum

| Value | Agent |
|---|---|
| `data_analyst` | DataAnalyst |
| `etl_orchestrator` | ETLOrchestrator |
| `query_planner` | QueryPlanner |
| `visualization_agent` | VisualizationAgent |
| `quality_monitor` | QualityMonitor |
| `data_discovery_agent` | DataDiscovery |
| `chat_coordinator` | ChatCoordinator |
| `task_decomposer` | TaskDecomposer |

### TaskType Enum (MCP models)

```
DATA_ANALYSIS, GRAPH_QUERY, DATA_QUALITY_SCAN, PIPELINE_ORCHESTRATION,
VISUALIZATION_GENERATION, CHAT_PROCESSING, TASK_DECOMPOSITION,
DATA_DISCOVERY, FILE_BATCH_PROCESSING
```

### AgentTaskRequest (sent by MCP to each agent)

```python
class AgentTaskRequest(BaseModel):
    task_id: str
    task_type: str
    payload: Dict[str, Any]
    priority: int = 5
    context: Dict[str, Any] = {}
    created_at: datetime = Field(default_factory=datetime.now)
```

### AgentTaskResponse (returned by each agent)

```python
class AgentTaskResponse(BaseModel):
    task_id: str
    status: TaskStatus            # pending | running | completed | failed
    result: Dict[str, Any]
    error: Optional[str] = None
    execution_time_ms: float = 0.0
    completed_at: datetime = Field(default_factory=datetime.now)
```

### AgenticTaskResult (MCP wraps agent response for clients)

```python
class AgenticTaskResult(BaseModel):
    task_id: str
    agent_id: str
    agent_type: str
    success: bool
    result: Dict[str, Any]
    error: Optional[str] = None
    execution_time: float
    timestamp: datetime
```

### AgenticSubtask (used in DAG)

```python
class AgenticSubtask(BaseModel):
    id: str                                 # unique subtask ID
    parent_task_id: str
    type: TaskType
    required_capabilities: List[str]
    payload: Dict[str, Any] = {}
    dependencies: List[str] = []           # ids of subtasks that must complete first
    priority: int = 5
    status: TaskStatus = PENDING
```

---

## 18. Port and URL Registry

| Service | Port | Bind | Module |
|---|---|---|---|
| FastAPI Backend | 8011 | 0.0.0.0 | `python_backend/main.py` |
| MCP Server | 8012 | 127.0.0.1 | `mcp_server/main.py` |
| DataAnalyst | 8020 | 0.0.0.0 | `agent_services/data_analyst/main.py` |
| ETLOrchestrator | 8021 | 0.0.0.0 | `agent_services/etl_orchestrator/main.py` |
| VisualizationAgent | 8022 | 0.0.0.0 | `agent_services/visualization_agent/main.py` |
| QueryPlanner | 8023 | 0.0.0.0 | `agent_services/query_planner/main.py` |
| QualityMonitor | 8024 | 0.0.0.0 | `agent_services/quality_monitor/main.py` |
| ChatCoordinator | 8025 | 0.0.0.0 | `agent_services/chat_coordinator/main.py` |
| DataDiscovery | 8026 | 0.0.0.0 | `agent_services/data_discovery/main.py` |
| TaskDecomposer | 8027 | 0.0.0.0 | `agent_services/task_decomposer/main.py` |
| PostgreSQL | 5433 | 127.0.0.1 | — |
| Neo4j (Bolt) | 7687 | 127.0.0.1 | — |
| Redis | 6379 | localhost | — (optional, StateManager falls back to in-memory) |
| Frontend (Vite) | 5173 | 127.0.0.1 | `e2etraceapp/` |

### Environment Variables Used by Agents

| Variable | Default | Used by |
|---|---|---|
| `NEO4J_URI` | `bolt://localhost:7687` | DataAnalyst, ETLOrchestrator, QualityMonitor, QueryPlanner, VisualizationAgent, ChatCoordinator |
| `NEO4J_USER` | `neo4j` | same as above |
| `NEO4J_PASSWORD` | `""` | same as above |
| `DATABASE_URL` | — | DataAnalyst, ETLOrchestrator |
| `MCP_SERVER_URL` | `http://localhost:8012` | all agents (for registration) |
| `GRAPH_TRACE_BACKEND_URL` | `http://localhost:8011` | DataDiscovery, QualityMonitor |
| `AGENT_INSTANCE_ID` | `default` | all agents (suffix for agent_id) |
