from datetime import datetime
from typing import Dict, List, Optional, Any
from enum import Enum
from pydantic import BaseModel, Field

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

class TaskPriority(int, Enum):
    LOW = 1
    NORMAL = 5
    HIGH = 9
    CRITICAL = 10

class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"

# Request Model: What the Agent receives
class AgentTaskRequest(BaseModel):
    task_id: str
    task_type: str
    payload: Dict[str, Any]
    priority: int = 5
    context: Dict[str, Any] = {}
    created_at: datetime = Field(default_factory=datetime.now)

# Response Model: What the Agent returns
class AgentTaskResponse(BaseModel):
    task_id: str
    status: TaskStatus
    result: Dict[str, Any]
    error: Optional[str] = None
    execution_time_ms: float = 0.0
    completed_at: datetime = Field(default_factory=datetime.now)

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
