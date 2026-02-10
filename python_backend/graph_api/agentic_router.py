"""
 AGENTIC BACKEND ORCHESTRATOR - FastAPI Multi-Agent Coordination
    
Implements Modular Cognition Pattern (MCP) with intelligent agent routing
Following AGENTIC_REFACTORING_GUIDE.md principles
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from enum import Enum
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query, Response
from pydantic import BaseModel, Field
import neo4j

from .dependencies import get_driver
from services.mcp_client import MCPClient

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/agentic", tags=["Agentic Orchestration"])

#  AGENT TYPE DEFINITIONS
class AgentType(str, Enum):
    DATA_ANALYST = "data_analyst"
    ETL_ORCHESTRATOR = "etl_orchestrator"
    QUERY_PLANNER = "query_planner"
    VISUALIZATION_AGENT = "visualization_agent"
    QUALITY_MONITOR = "quality_monitor"
    CHAT_COORDINATOR = "chat_coordinator"

#  TASK DEFINITIONS
class TaskType(str, Enum):
    DATA_ANALYSIS = "data_analysis"
    PIPELINE_ORCHESTRATION = "pipeline_orchestration"
    GRAPH_QUERY = "graph_query"
    VISUALIZATION_GENERATION = "visualization_generation"
    QUALITY_ASSESSMENT = "quality_assessment"
    CHAT_PROCESSING = "chat_processing"

#  PYDANTIC MODELS
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
    last_activity: datetime = Field(default_factory=datetime.now)
    performance_metrics: Dict[str, float] = {}

class AgenticTask(BaseModel):
    id: str = Field(default_factory=lambda: f"task_{int(datetime.now().timestamp() * 1000)}")
    type: TaskType
    required_capabilities: List[str]
    payload: Dict[str, Any]
    priority: int = 5
    timeout: int = 30
    created_at: datetime = Field(default_factory=datetime.now)

class AgenticTaskResult(BaseModel):
    task_id: str
    agent_id: str
    agent_type: AgentType
    success: bool
    result: Dict[str, Any] = {}
    error: Optional[str] = None
    execution_time: float
    timestamp: datetime = Field(default_factory=datetime.now)

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
    timestamp: datetime = Field(default_factory=datetime.now)

#  MCP CLIENT INSTANCE
mcp_client = MCPClient()


#  API ENDPOINTS

@router.post("/task", response_model=AgenticTaskResult)
async def process_agentic_task(
    task: AgenticTask,
    _background_tasks: BackgroundTasks,
    driver_instance: neo4j.AsyncDriver = Depends(get_driver)
):
    """Process a task with intelligent agent routing via MCP Server"""
    try:
        # Delegate to MCP Server
        result_dict = await mcp_client.submit_task(task.model_dump(mode="json"))
        return AgenticTaskResult(**result_dict)
    except Exception as e:
        logger.error("Task processing failed: %s", e)
        raise HTTPException(status_code=500, detail=f"Task processing failed: {str(e)}") from e

@router.post("/chat", response_model=ChatResponse)
async def process_chat_message(
    chat_request: ChatRequest,
    driver_instance: neo4j.AsyncDriver = Depends(get_driver)
):
    """Process chat message with multi-agent coordination"""
    try:
        session_id = chat_request.session_id or f"session_{int(datetime.now().timestamp())}"
        
        # Create chat processing task
        chat_task = AgenticTask(
            type=TaskType.CHAT_PROCESSING,
            required_capabilities=["process_natural_language", "coordinate_agent_responses"],
            payload={
                "message": chat_request.message,
                "context": chat_request.context,
                "session_id": session_id
            }
        )
        
        # Delegate to MCP Server
        result_dict = await mcp_client.submit_task(chat_task.model_dump(mode="json"))
        result = AgenticTaskResult(**result_dict)
        
        if result.success:
            chat_data = result.result
            return ChatResponse(
                message=chat_data.get("primaryResponse", "I understand your request."),
                agent_responses=[],
                suggested_actions=chat_data.get("followupQuestions", []),
                requires_followup=chat_data.get("collaborationNeeded", False),
                session_id=session_id
            )
        else:
            return ChatResponse(
                message="I'm sorry, I encountered an issue processing your message.",
                session_id=session_id
            )
    
    except Exception as e:
        logger.error("Chat processing failed: %s", e)
        raise HTTPException(status_code=500, detail=f"Chat processing failed: {str(e)}") from e

@router.get("/status", response_model=SystemStatus)
async def get_system_status():
    """Get current agentic system status"""
    status_data = await mcp_client.get_system_status()
    return SystemStatus(**status_data)

@router.get("/agents", response_model=List[AgentDefinition])
async def get_orchestrator_agents(
    response: Response,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
):
    """Get list of configured agents (paged)."""
    agents_data = await mcp_client.list_agents()
    agents = [AgentDefinition(**a) for a in agents_data]
    
    response.headers["X-Total-Count"] = str(len(agents))
    return agents[skip : skip + limit]

@router.post("/agents/{agent_id}/reset")
async def reset_agent(agent_id: str):
    """Reset agent status - Deprecated in MCP Architecture"""
    raise HTTPException(status_code=501, detail="Agent reset not supported in distributed MCP architecture")

@router.get("/metrics")
async def get_performance_metrics():
    """Get system performance metrics"""
    status = await mcp_client.get_system_status()
    # Extract metrics from status
    # MCP server status.performance_metrics matches
    
    active_agent_count = len([a for a in status["active_agents"] if a.get("status") == "ready"])
    
    return {
        "system_metrics": status["performance_metrics"],
        "agent_count": len(status["active_agents"]),
        "active_agents": active_agent_count,
        "timestamp": datetime.now()
    }

#  SYSTEM STATUS ENDPOINTS

@router.get("/system/status")
async def get_agentic_system_status():
    """Get overall agentic system status"""
    try:
        # Return real orchestrator status (no fabricated payloads)
        status_data = await mcp_client.get_system_status()
        return SystemStatus(**status_data)
    except Exception as e:
        logger.warning("Agentic system status unavailable: %s", e)
        return {
            "status": "unavailable",
            "agents": [],
            "mcp_server": {"connected": False},
            "error": str(e),
            "timestamp": datetime.now().isoformat(),
        }

@router.get("/agents/active")
async def get_active_agents_list(
    response: Response,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
):
    """Get list of currently active agents"""
    try:
        agents_data = await mcp_client.list_agents()
        active_agents = [
            AgentDefinition(**agent)
            for agent in agents_data
            if str(agent.get("status", "")).lower() in ("ready", "active", "running")
        ]

        response.headers["X-Total-Count"] = str(len(active_agents))
        return {
            "status": "success",
            "active_agents": active_agents[skip : skip + limit],
            "total_count": len(active_agents),
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        logger.error("Error getting active agents: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e

@router.get("/agents/metrics")
async def get_agent_metrics():
    """Get performance metrics for all agents"""
    try:
        status = await mcp_client.get_system_status()
        system_metrics = status["performance_metrics"]
        
        tasks_completed = int(system_metrics.get("tasks_completed", 0) or 0)
        tasks_failed = int(system_metrics.get("tasks_failed", 0) or 0)
        total_tasks = tasks_completed + tasks_failed
        success_rate = (tasks_completed / total_tasks) * 100.0 if total_tasks else 0.0
        error_rate = (tasks_failed / total_tasks) * 100.0 if total_tasks else 0.0

        return {
            "status": "success",
            "metrics": {
                "total_tasks_processed": total_tasks,
                "tasks_completed": tasks_completed,
                "tasks_failed": tasks_failed,
                "average_response_time": float(system_metrics.get("average_response_time", 0.0) or 0.0),
                "success_rate": round(success_rate, 2),
                "error_rate": round(error_rate, 2),
                "agent_utilization": system_metrics.get("agent_utilization", {}),
            },
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        logger.error("Error getting agent metrics: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


