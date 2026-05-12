import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Union
from enum import Enum
from pydantic import BaseModel, Field


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _new_subtask_id() -> str:
    return f"subtask_{uuid.uuid4().hex[:12]}"


def _new_task_id() -> str:
    return f"task_{uuid.uuid4().hex[:12]}"


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
    TASK_DECOMPOSITION = "task_decomposition"
    SCHEMA_CORRELATION = "schema_correlation"
    PLM_MIGRATION_ORCHESTRATION = "plm_migration_orchestration"
    REPORT_GENERATION = "report_generation"
    SEMANTIC_PROFILE = "semantic_profile"
    SMART_GUIDANCE = "smart_guidance"
    DATA_HEALTH_REPORT = "data_health_report"
    # ── Unified AI Workflow steps ──────────────────────────────────────────
    PROFILING = "profiling"
    QUALITY_SCAN = "quality_scan"
    ETL_PIPELINE = "etl_pipeline"
    WORKFLOW_RUN = "workflow_run"
    WORKFLOW_DECOMPOSITION = "workflow_decomposition"


class TaskStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


class AgentCapability(BaseModel):
    name: str
    description: str
    parameters: Dict[str, Any] = {}


class AgentDefinition(BaseModel):
    id: str
    type: AgentType
    name: str
    capabilities: List[AgentCapability]
    status: str = "ready"
    service_url: Optional[str] = None
    metadata: Dict[str, Any] = {}
    last_activity: datetime = Field(default_factory=_utcnow)
    performance_metrics: Dict[str, float] = {}


class AgenticSubtask(BaseModel):
    id: str = Field(default_factory=_new_subtask_id)
    parent_task_id: str
    type: TaskType
    required_capabilities: List[str]
    payload: Dict[str, Any]
    status: TaskStatus = TaskStatus.PENDING
    dependencies: List[str] = []
    priority: int = 5
    timeout: int = 30
    created_at: datetime = Field(default_factory=_utcnow)


class AgenticTask(BaseModel):
    id: str = Field(default_factory=_new_task_id)
    type: TaskType
    required_capabilities: List[str]
    payload: Dict[str, Any]
    status: TaskStatus = TaskStatus.PENDING
    subtasks: List[AgenticSubtask] = []
    priority: int = 5
    timeout: int = 30
    created_at: datetime = Field(default_factory=_utcnow)


class AgenticTaskResult(BaseModel):
    task_id: str
    agent_id: str
    # Accept both AgentType enum values and plain strings (e.g. "system")
    agent_type: Union[AgentType, str]
    success: bool
    result: Dict[str, Any] = {}
    error: Optional[str] = None
    execution_time: float
    timestamp: datetime = Field(default_factory=_utcnow)


class ChatRequest(BaseModel):
    message: str
    context: Dict[str, Any] = {}
    session_id: Optional[str] = None
    intent: Optional[str] = None


class ChatResponse(BaseModel):
    message: str
    agent_responses: List[Dict[str, Any]] = []
    suggested_actions: List[str] = []
    requires_followup: bool = False
    session_id: str


class SystemStatus(BaseModel):
    active_agents: List[AgentDefinition]
    task_queue_size: int
    system_health: str
    performance_metrics: Dict[str, Any]
    timestamp: datetime = Field(default_factory=_utcnow)
