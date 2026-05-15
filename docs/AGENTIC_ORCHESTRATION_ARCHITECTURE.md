# Agentic Orchestration Architecture: Formal Agent & Tool Framework

**Document Date**: May 15, 2026  
**Architecture Version**: 2.0 (MCP-based)  
**Scope**: How agents, tools, and agentic orchestration formally handle workflows in the Migration Wizard

---

## Executive Summary

The GoodPoint AgenticAI system implements a **formal agentic orchestration framework** combining:

1. **Canonical Agent Types** - 12 specialized agent definitions with distinct capabilities
2. **Formal Task Types** - 16 task types representing decomposable workflow units
3. **Tool Registry** - MCP-based tool exposure for agent capability execution
4. **Workflow Definition** - DAG-based workflow structures with typed step execution
5. **Orchestration Modes** - Reactive, Proactive, and Intelligent routing policies
6. **Migration Stages** - 10 formal migration stages managing workflow progression

---

## Part 1: Canonical Agent Types

### Formal Definition
Agents are formally defined in [agentic_router.py](../python_backend/graph_api/agentic_router.py) as an `AgentType` enum with associated capabilities.

```python
class AgentType(str, Enum):
    DATA_ANALYST = "data_analyst"
    ETL_ORCHESTRATOR = "etl_orchestrator"
    QUERY_PLANNER = "query_planner"
    VISUALIZATION_AGENT = "visualization_agent"
    QUALITY_MONITOR = "quality_monitor"
    DATA_DISCOVERY_AGENT = "data_discovery_agent"
    CHAT_COORDINATOR = "chat_coordinator"
    TASK_DECOMPOSER = "task_decomposer"
    SCHEMA_CORRELATOR = "schema_correlator"
    PLM_DIRECTOR = "plm_director"
    REPORTING_AGENT = "reporting_agent"
    DATA_PROFILER = "data_profiler"
```

### Agent Capabilities Model

Each agent has formally defined capabilities:

```python
class AgentCapability(BaseModel):
    name: str                          # Capability name (e.g., "discover_files")
    description: str                   # Human-readable description
    parameters: Dict[str, Any] = {}   # Required parameters

class AgentDefinition(BaseModel):
    id: str                            # Unique agent identifier
    type: AgentType                    # Agent classification
    name: str                          # Human-readable name
    capabilities: List[AgentCapability]  # List of capabilities
    status: str = "ready"              # Current status (ready|busy|error)
    last_activity: datetime            # Last execution timestamp
    performance_metrics: Dict[str, float] = {}  # Latency, throughput, etc.
```

### Agent Inventory

| Agent | Type | Primary Capability | Used In |
|-------|------|-------------------|---------|
| **DataDiscoveryAgent** | `DATA_DISCOVERY_AGENT` | discover_files, profile_files | Step 2: Discovery |
| **DataProfilerAgent** | `DATA_PROFILER` | semantic_profiling, column_semantics | Step 2: Profiling |
| **QualityMonitorAgent** | `QUALITY_MONITOR` | scan_folder_quality, validate_data | Step 4: Validation |
| **SchemaCorrelatorAgent** | `SCHEMA_CORRELATOR` | transform_schema, map_columns | Step 3: Mapping |
| **ETLOrchestratorAgent** | `ETL_ORCHESTRATOR` | manage_data_pipelines, load_data | Step 5: Execution |
| **TaskDecomposerAgent** | `TASK_DECOMPOSER` | workflow_decomposition | Workflow Planning |
| **ReportingAgent** | `REPORTING_AGENT` | generate_insights, report_generation | Step 6: Report |
| **ChatCoordinatorAgent** | `CHAT_COORDINATOR` | chat_processing | AI Chat & Guidance |
| **PLMDirectorAgent** | `PLM_DIRECTOR` | plm_migration_orchestration | Overall Workflow |

---

## Part 2: Formal Task Types

### Task Type Definition

Tasks are formally defined as executable work units that agents can perform:

```python
class TaskType(str, Enum):
    DATA_ANALYSIS = "data_analysis"
    PIPELINE_ORCHESTRATION = "pipeline_orchestration"
    GRAPH_QUERY = "graph_query"
    VISUALIZATION_GENERATION = "visualization_generation"
    QUALITY_ASSESSMENT = "quality_assessment"
    CHAT_PROCESSING = "chat_processing"
    DATA_DISCOVERY = "data_discovery"
    DATA_QUALITY_SCAN = "data_quality_scan"
    FILE_BATCH_PROCESSING = "file_batch_processing"
    WORKFLOW_DECOMPOSITION = "workflow_decomposition"
    SEMANTIC_PROFILE = "semantic_profile"
    SCHEMA_CORRELATION = "schema_correlation"
    PLM_MIGRATION_ORCHESTRATION = "plm_migration_orchestration"
    REPORT_GENERATION = "report_generation"
    SMART_GUIDANCE = "smart_guidance"
    DATA_HEALTH_REPORT = "data_health_report"
    # Migration wizard unified steps
    PROFILING = "profiling"
    QUALITY_SCAN = "quality_scan"
    ETL_PIPELINE = "etl_pipeline"
    WORKFLOW_RUN = "workflow_run"
```

### Agentic Task Formal Model

```python
class AgenticTask(BaseModel):
    id: str = Field(default_factory=lambda: f"task_{int(datetime.now().timestamp() * 1000)}")
    type: TaskType                     # Task classification
    required_capabilities: List[str]   # Capabilities needed (e.g., ["discover_files", "profile_files"])
    payload: Dict[str, Any]           # Task parameters
    priority: int = 5                  # Priority (1-10, default 5)
    timeout: int = 30                  # Task timeout in seconds
    created_at: datetime = Field(default_factory=datetime.now)

class AgenticTaskResult(BaseModel):
    task_id: str                       # Original task ID
    agent_id: str                      # Executing agent ID
    agent_type: AgentType              # Agent classification
    success: bool                      # Execution status
    result: Dict[str, Any] = {}       # Output payload
    error: Optional[str] = None        # Error message if failed
    execution_time: float              # Time taken (seconds)
    timestamp: datetime = Field(default_factory=datetime.now)
```

### Task Capability Mapping

| Task Type | Required Capabilities | Expected Result |
|-----------|----------------------|-----------------|
| `DATA_DISCOVERY` | discover_files, profile_files | { discovered_files[], file_profiles[], file_count } |
| `SEMANTIC_PROFILE` | semantic_profiling, column_semantics | { column_semantics[], entity_classifications[], data_types[] } |
| `DATA_QUALITY_SCAN` | scan_folder_quality, validate_data | { quality_score, violations[], anomalies[] } |
| `SCHEMA_CORRELATION` | transform_schema, map_columns | { field_mappings[], schema_suggestions[] } |
| `ETL_PIPELINE` | manage_data_pipelines, load_data | { records_loaded, errors[], warnings[] } |
| `WORKFLOW_DECOMPOSITION` | task_decomposition | { subtasks[], dependencies[], execution_order[] } |
| `REPORT_GENERATION` | generate_insights | { report_html, readiness_score, recommendations[] } |

---

## Part 3: MCP-Based Tool Registry & Execution

### MCP (Model Context Protocol) Integration

The backend formally exposes capabilities to agents via **MCP server**:

```
Frontend                Backend (FastAPI)              MCP Server
                       ┌────────────────────┐        ┌──────────────┐
User Interaction  ───> │ agentic_router     │───────>│ Task Queue   │
                       │ /api/agentic/task  │        │ Agent Pool   │
                       └────────────────────┘        │ Tool Handler │
                                                    └──────────────┘
```

### Formal Tool Definition (MCP Perspective)

```python
class MCPCapabilityToStepTypeMapper:
    """Maps MCP required_capabilities to backend WorkflowStepType"""
    
    CAPABILITY_MAPPING = {
        "discover_files": WorkflowStepType.DISCOVERY,
        "profile_files": WorkflowStepType.PROFILING,
        "scan_folder_quality": WorkflowStepType.PROFILING,
        "manage_data_pipelines": WorkflowStepType.ETL_EXECUTION,
        "validate_data": WorkflowStepType.VALIDATION,
        "transform_schema": WorkflowStepType.SCHEMA_MAPPING,
        "load_data": WorkflowStepType.ETL_EXECUTION,
        "generate_insights": WorkflowStepType.PYTHON,
    }
```

### Tool Exposure Endpoints

```
POST /api/agentic/task
├─ Submit: AgenticTask
├─ Routing: Match required_capabilities to available agents
├─ Execution: Call MCP server via mcp_client.submit_task()
└─ Response: AgenticTaskResult

GET /api/agentic/status
├─ Returns: MCP system status
├─ Fields: active_agents, task_queue_size, performance_metrics
└─ Graceful Degradation: Returns default unavailable status if MCP is down

GET /api/agentic/agents
├─ Returns: List[AgentDefinition]
├─ Fields: id, type, capabilities, status, performance_metrics
└─ Pagination: skip, limit parameters
```

---

## Part 4: Workflow Orchestration Architecture

### Formal Workflow Definition

Workflows are formally structured as **Directed Acyclic Graphs (DAGs)** with typed steps:

```python
class WorkflowStepType(str, Enum):
    """Workflow step types for execution"""
    SQL = "sql"                    # SQL transformation
    PYTHON = "python"             # Python script execution
    API = "api"                    # External API call
    DISCOVERY = "discovery"       # Data discovery (agent-driven)
    PROFILING = "profiling"       # Semantic profiling (agent-driven)
    SCHEMA_MAPPING = "schema_mapping"  # Column mapping (agent-driven)
    ETL_EXECUTION = "etl_execution"    # Data load (agent-driven)
    VALIDATION = "validation"     # Quality checks (agent-driven)
```

### Workflow Step Definition

```python
class WorkflowStep:
    """Individual step in a workflow DAG"""
    id: str                          # Step identifier
    type: WorkflowStepType          # Step classification
    name: str                        # Human-readable name
    order: int                       # Execution order in DAG
    dependencies: List[str]          # Prerequisite step IDs
    
    # Agent assignment
    assigned_agent: Optional[str]   # Agent ID (if agent-driven)
    agent_type: Optional[AgentType] # Agent type
    
    # Task configuration
    task_type: Optional[TaskType]   # Task to execute
    task_payload: Dict[str, Any]    # Task parameters
    
    # Execution control
    status: WorkflowStepStatus      # pending|running|completed|failed
    retry_count: int = 0            # Number of retries
    max_retries: int = 3            # Maximum retry attempts
    timeout: int = 300              # Timeout in seconds
    
    # Results
    result: Optional[Dict[str, Any]] # Step output
    error: Optional[str]            # Error message
    execution_time: float           # Time taken
```

### Workflow Instance Structure

```python
class WorkflowInstance:
    """Complete workflow instance (database-backed)"""
    
    # Identification
    id: str                         # Unique workflow ID
    name: str                       # Human-readable name
    
    # Configuration
    source_id: str                  # Source system ID
    target_id: str                  # Target system ID
    workflow_config: JSON           # DAG structure (nodes, edges)
    ai_agents_enabled: List[str]   # Enabled agent IDs
    
    # Execution state
    status: WorkflowStatus          # draft|configured|running|completed|failed
    current_stage: MigrationStage   # Current migration phase
    progress_percentage: float      # Overall progress (0-100%)
    
    # Statistics
    total_records: int              # Total records to process
    processed_records: int          # Records processed
    failed_records: int             # Failed record count
    quality_score: Optional[float]  # Data quality score
    
    # Scheduling
    schedule_enabled: bool          # Recurrence enabled
    schedule_cron: Optional[str]    # Cron expression
```

---

## Part 5: Migration Wizard Workflow

### Wizard Step to Agent Mapping

The Migration Wizard implements a **5-step (6-including report) formalized workflow**:

```
┌─────────────────────────────────────────────────────────────┐
│          MIGRATION WIZARD WORKFLOW ARCHITECTURE              │
└─────────────────────────────────────────────────────────────┘

Step 1: CONNECT (Configuration)
├─ Agent: None (User input)
├─ Task: Manual configuration
├─ Output: sourceSystem, targetSystem
├─ Next Stage: IDLE → DISCOVERING

Step 2: DISCOVERY (Data Understanding)
├─ Agent: DataDiscoveryAgent
├─ Task: DATA_DISCOVERY
├─ Capability: discover_files, profile_files
├─ Output: discovered_files[], file_profiles[]
├─ Parallel: DATA_HEALTH_REPORT (DataHealthAgent)
├─ Parallel: SEMANTIC_PROFILE (DataProfilerAgent)
├─ Next Stage: DISCOVERING → PROFILING

Step 3: MAP (Schema Mapping)
├─ Agent: SchemaCorrelatorAgent
├─ Task: SCHEMA_CORRELATION
├─ Capability: transform_schema, map_columns
├─ Input: sourceSchema, targetSchema
├─ Output: field_mappings[], suggestions[]
├─ Next Stage: PROFILING → SCHEMA_MAPPING

Step 4: VALIDATE (Quality Checks)
├─ Agent: QualityMonitorAgent
├─ Task: DATA_QUALITY_SCAN
├─ Capability: scan_folder_quality, validate_data
├─ Input: rules[], field_mappings[]
├─ Output: quality_score, violations[]
├─ Next Stage: SCHEMA_MAPPING → VALIDATION

Step 5: EXECUTE (Data Load)
├─ Agent: ETLOrchestratorAgent
├─ Task: ETL_PIPELINE
├─ Capability: manage_data_pipelines, load_data
├─ Input: field_mappings[], transformations[]
├─ Output: records_loaded, errors[]
├─ Next Stage: VALIDATION → DATA_MIGRATION → COMPLETED

Step 6: REPORT (Migration Summary)
├─ Agent: ReportingAgent
├─ Task: REPORT_GENERATION
├─ Capability: generate_insights
├─ Input: All previous step results
├─ Output: readiness_score, recommendations[]
└─ Final Stage: COMPLETED
```

### Migration Stages (Formal State Machine)

```python
class MigrationStage(str, Enum):
    """Formal migration progression stages"""
    IDLE = "idle"                # Initial state
    INITIALIZING = "initializing"    # Preparing workflow
    DISCOVERING = "discovering"      # Step 2 active
    PROFILING = "profiling"          # Step 2 semantic profiling
    SCHEMA_MAPPING = "schema_mapping" # Step 3 active
    DATA_MIGRATION = "data_migration" # Step 5 active
    VALIDATION = "validation"        # Step 4 active
    PAUSED = "paused"               # User paused
    COMPLETED = "completed"         # Workflow finished
    FAILED = "failed"               # Error occurred
    CANCELLED = "cancelled"         # User cancelled
```

---

## Part 6: Agentic Orchestration Modes

### Formal Orchestration Configuration

```python
class AgenticOrchestrationConfig(BaseModel):
    """Agentic orchestration configuration"""
    enabled: bool = True
    orchestration_mode: str = Field(
        "intelligent", 
        pattern="^(reactive|proactive|intelligent)$"
    )
    workflows: List[Dict[str, Any]] = Field(default_factory=list)
    intelligent_features: Dict[str, bool] = Field(default_factory=dict)
```

### Three Orchestration Modes

#### 1. **Reactive Mode**
- **Behavior**: Agents respond to explicit user actions
- **When Used**: Conservative deployments, manual oversight
- **Workflow**: User → Action → Agent Response
- **Example**: User clicks "Run Discovery" → Calls DATA_DISCOVERY task

#### 2. **Proactive Mode**
- **Behavior**: System suggests actions based on state
- **When Used**: Guided workflows with AI suggestions
- **Workflow**: System observes → Suggests → User approves
- **Example**: "Based on your data, I recommend profiling first"

#### 3. **Intelligent Mode** (Default)
- **Behavior**: System auto-orchestrates with human oversight
- **When Used**: Full automation with fallback to manual
- **Workflow**: System → Analyze → Execute → Report → Wait for approval
- **Example**: Discovery runs automatically → Profiling queued → User reviews results

---

## Part 7: MCP Workflow Adapter

### Formal Task Decomposition to Workflow Conversion

The `MCPWorkflowAdapter` formally converts MCP TaskDecomposer output into executable workflows:

```python
class MCPWorkflowAdapter:
    """Adapter to convert MCP TaskDecomposer output to WorkflowDefinition"""
    
    async def create_workflow_from_mcp_decomposition(
        self,
        mcp_response: Dict[str, Any],  # MCP TaskDecomposer output
        source_id: str,
        target_id: str,
        workflow_name: Optional[str] = None,
    ) -> WorkflowDefinition:
        """
        Conversion Process:
        1. Parse mcp_response["subtasks"] array
        2. For each subtask:
           - Extract required_capabilities
           - Map to WorkflowStepType via MCPCapabilityToStepTypeMapper
           - Create WorkflowStep with ordered execution
           - Preserve dependencies as DAG edges
        3. Return WorkflowDefinition with complete DAG
        """
```

### Capability to Step Type Mapping

```python
CAPABILITY_MAPPING = {
    "discover_files": WorkflowStepType.DISCOVERY,
    "profile_files": WorkflowStepType.PROFILING,
    "scan_folder_quality": WorkflowStepType.PROFILING,
    "manage_data_pipelines": WorkflowStepType.ETL_EXECUTION,
    "validate_data": WorkflowStepType.VALIDATION,
    "transform_schema": WorkflowStepType.SCHEMA_MAPPING,
    "load_data": WorkflowStepType.ETL_EXECUTION,
    "generate_insights": WorkflowStepType.PYTHON,
}
```

---

## Part 8: Request/Response Flow

### Complete Request Flow in Migration Wizard

```
Frontend (MigrationWizard.jsx)
│
├─ Step 1: User fills Connect form
│  └─ setWizardData({ sourceSystem, targetSystem })
│
├─ Step 2: User clicks "Run Discovery"
│  └─ POST /api/agentic/discovery
│     ├─ Create: AgenticTask {
│     │   type: TaskType.DATA_DISCOVERY,
│     │   required_capabilities: ["discover_files", "profile_files"],
│     │   payload: { source_id, target_id }
│     │ }
│     ├─ Call: mcp_client.submit_task()
│     ├─ MCP Server: Routes to DataDiscoveryAgent
│     └─ Response: AgenticTaskResult { success, result: { discovered_files, file_profiles } }
│  └─ setWizardData({ discoveryStatus: "completed", discoveryInsights: [...] })
│
├─ Parallel: Smart Guidance fetch
│  └─ POST /api/agentic/smart-guidance
│     ├─ Create: AgenticTask {
│     │   type: TaskType.SMART_GUIDANCE,
│     │   payload: { source_name, file_count, file_types, user_role }
│     │ }
│     └─ Response: SmartGuidanceResponse { recommendation, headline, reason }
│
├─ Parallel: Semantic Profiling (fire-and-forget)
│  └─ POST /api/agentic/profile
│     ├─ Create: AgenticTask {
│     │   type: TaskType.SEMANTIC_PROFILE,
│     │   payload: { discovered_files }
│     │ }
│     └─ Response: semanticProfile { column_semantics, entity_classifications }
│
├─ Step 3: User configures mappings
│  └─ setWizardData({ fieldMappings: [...], selectedTemplate: {...} })
│
├─ Step 4: User runs validation
│  └─ POST /api/agentic/quality-scan
│     ├─ Create: AgenticTask {
│     │   type: TaskType.DATA_QUALITY_SCAN,
│     │   payload: { rules: [...], field_mappings: [...] }
│     │ }
│     └─ Response: { quality_score, violations, anomalies }
│  └─ setWizardData({ qualityResults: [...], qualityChecks: { passed, failed, warnings } })
│
├─ Step 5: User executes migration
│  └─ POST /api/agentic/execute-migration
│     ├─ Create: WorkflowInstance (persisted to DB)
│     ├─ Create: Execution plan with WorkflowSteps
│     ├─ For each step:
│     │  ├─ Create: AgenticTask for step type
│     │  ├─ Call: mcp_client.submit_task()
│     │  └─ Record: WorkflowStep result
│     └─ Response: { execution_id, status: "running" }
│  └─ Polling: GET /api/agentic/execute-migration/{execution_id}/status
│
└─ Step 6: Generate Report
   └─ POST /api/agentic/report
      ├─ Collect: All previous step results
      ├─ Create: AgenticTask {
      │   type: TaskType.REPORT_GENERATION,
      │   payload: { discover, profile, quality, etl, ... }
      │ }
      ├─ If MCP unavailable: Use local report builder
      └─ Response: { readiness_score, recommendations, report_html }
```

---

## Part 9: Graceful Degradation & Error Handling

### Formal Error Classification

```python
class ErrorCategory(str, Enum):
    """Formal error categories"""
    VALIDATION = "validation"
    CONFIGURATION = "configuration"
    EXECUTION = "execution"
    DEPENDENCY = "dependency"
    TIMEOUT = "timeout"
    RESOURCE = "resource"
    UNKNOWN = "unknown"

class ErrorSeverity(str, Enum):
    """Error severity levels"""
    INFO = "info"       # Non-blocking
    WARNING = "warning" # Recoverable
    ERROR = "error"     # Needs intervention
    CRITICAL = "critical"  # Workflow blocked
```

### Fallback Responses

When agents/MCP unavailable:

```python
# Graceful Degradation Pattern
try:
    result_dict = await mcp_client.submit_task(task)
except Exception:
    # Use local fallback
    result_dict = get_fallback_by_error_type(task.type)
    
# MCP Client already implements this:
# - Returns degraded status instead of raising
# - DEBUG logging instead of ERROR
# - Returns {"system_health": "unavailable"} for status endpoint
```

---

## Part 10: Integration Points

### Frontend → Backend Communication

```javascript
// MigrationWizard.jsx orchestration hooks
const useAgenticSystemStatus = () => {
  // GET /api/agentic/status
  // Monitors: active_agents, task_queue_size, performance_metrics
}

const useAISuggestions = () => {
  // POST /api/agentic/smart-guidance
  // Returns: recommendation, headline, reasoning
}
```

### Backend State Management

```python
# Core component: agentic_router.py
@router.post("/task", response_model=AgenticTaskResult)
async def process_agentic_task(task: AgenticTask) -> AgenticTaskResult:
    """
    Central dispatcher for all agentic tasks.
    - Validates task against agent capabilities
    - Routes to MCP server
    - Records execution metrics
    - Handles errors gracefully
    """
```

---

## Part 11: Performance Metrics & Monitoring

### Agent Performance Tracking

```python
# AgentDefinition includes performance_metrics:
{
    "latency_ms": 1250,           # Average response time
    "throughput_tasks_per_second": 2.5,  # Tasks processed per second
    "error_rate": 0.02,           # 2% error rate
    "availability": 0.98,         # 98% uptime
    "last_activity": "2024-05-15T10:20:30Z"
}
```

### Workflow Execution Tracking

```python
# WorkflowInstance tracks:
- progress_percentage: 0-100%
- processed_records vs total_records
- quality_score: 0-100
- execution_time per step
```

---

## Part 12: Formal API Reference

### Agentic Orchestration Endpoints

```
POST /api/agentic/task
├─ Purpose: Submit any agentic task
├─ Request: { type, required_capabilities, payload, priority, timeout }
└─ Response: { task_id, agent_id, success, result, execution_time }

GET /api/agentic/status
├─ Purpose: Get system status and available agents
└─ Response: { system_health, active_agents, task_queue_size, metrics }

GET /api/agentic/agents
├─ Purpose: List available agents
├─ Query: skip, limit
└─ Response: List[AgentDefinition]

POST /api/agentic/discovery
├─ Purpose: Run data discovery on folder
├─ Request: { source_id, target_id, recursive }
└─ Response: { discovered_files, file_profiles, file_count }

POST /api/agentic/chat
├─ Purpose: Chat with coordination agent
├─ Request: { message, context, session_id, workflow_context }
└─ Response: { reply, suggestions, confidence }

POST /api/agentic/smart-guidance
├─ Purpose: Get AI recommendation for first step
├─ Request: { source_name, file_count, user_role, nlp_query }
└─ Response: { recommendation, headline, reason, next_steps, complexity }

POST /api/agentic/execute-migration
├─ Purpose: Start workflow execution
├─ Request: { workflow_id, execution_params }
└─ Response: { execution_id, status, started_at }

GET /api/agentic/execute-migration/{execution_id}/status
├─ Purpose: Poll execution progress
└─ Response: { status, progress, completed_steps, current_step, errors }
```

---

## Summary: Formal Orchestration Model

```
┌──────────────────────────────────────────────────────────────┐
│            AGENTIC ORCHESTRATION MODEL                       │
├──────────────────────────────────────────────────────────────┤
│                                                               │
│  12 Canonical Agents                                          │
│  └─ Each with formal capabilities, status, metrics           │
│                                                               │
│  ↓                                                             │
│                                                               │
│  16 Task Types + Formal Task Model                           │
│  └─ Each with required_capabilities, payload, timeout        │
│                                                               │
│  ↓                                                             │
│                                                               │
│  MCP Tool Registry                                            │
│  └─ discover_files, profile_files, validate_data, etc.       │
│                                                               │
│  ↓                                                             │
│                                                               │
│  Capability → Step Type Mapping                              │
│  └─ Convert tool exposures to workflow steps                 │
│                                                               │
│  ↓                                                             │
│                                                               │
│  Workflow DAG Execution                                       │
│  └─ Orchestrate steps with dependencies                      │
│                                                               │
│  ↓                                                             │
│                                                               │
│  3 Orchestration Modes (Reactive/Proactive/Intelligent)      │
│  └─ Route execution based on configuration                   │
│                                                               │
│  ↓                                                             │
│                                                               │
│  10 Migration Stages + Formal State Machine                  │
│  └─ Track workflow progression                               │
│                                                               │
│  ↓                                                             │
│                                                               │
│  Graceful Degradation & Error Handling                       │
│  └─ Fallback responses, retry logic, monitoring              │
│                                                               │
└──────────────────────────────────────────────────────────────┘
```

---

## Key Formal Properties

✅ **Type-Safe**: All agents, tasks, and steps formally typed (Pydantic + Python Enums)  
✅ **Capability-Based**: Agents matched to tasks by required_capabilities  
✅ **DAG-Based**: Workflows structured as directed acyclic graphs  
✅ **State-Tracked**: 10 migration stages provide formal progression tracking  
✅ **Metrics-Enabled**: Performance tracking at agent and workflow levels  
✅ **Degradation-Ready**: Graceful fallbacks when agents/MCP unavailable  
✅ **MCP-Integrated**: Tools exposed via Model Context Protocol  
✅ **Database-Backed**: Workflow instances persisted with full audit trail  
✅ **Mode-Configurable**: Reactive/Proactive/Intelligent orchestration modes  
✅ **Error-Classified**: Formal error categories and severity levels  

---

**Architecture Designed For**: Production-grade agentic orchestration with human oversight and graceful degradation.

**Last Updated**: May 15, 2026
