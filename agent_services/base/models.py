import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from enum import Enum
from pydantic import BaseModel, Field


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# Replicating enums to ensure consistency across services
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


class TaskPriority(int, Enum):
    LOW = 1
    NORMAL = 5
    HIGH = 9
    CRITICAL = 10


class TaskStatus(str, Enum):
    PENDING = "pending"
    # Use IN_PROGRESS (matches mcp_server/models.py TaskStatus)
    IN_PROGRESS = "in_progress"
    RUNNING = "running"   # alias kept for backwards compat
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


# Request Model: What the Agent receives
class AgentTaskRequest(BaseModel):
    task_id: str
    task_type: str
    payload: Dict[str, Any]
    priority: int = 5
    context: Dict[str, Any] = {}
    created_at: datetime = Field(default_factory=_utcnow)


# Response Model: What the Agent returns
class AgentTaskResponse(BaseModel):
    task_id: str
    status: TaskStatus
    result: Dict[str, Any]
    error: Optional[str] = None
    execution_time_ms: float = 0.0
    completed_at: datetime = Field(default_factory=_utcnow)


# Registration Model: What the Agent sends to MCP Server
class AgentCapability(BaseModel):
    name: str
    description: str
    parameters: Dict[str, Any] = {}


class AgentRegistration(BaseModel):
    agent_id: str
    agent_type: AgentType
    service_url: str  # Where this agent can be reached (e.g., http://localhost:8020)
    capabilities: List[AgentCapability]
    version: str = "1.0.0"
    metadata: Dict[str, Any] = {}
