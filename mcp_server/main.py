import logging
import contextlib
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any

from fastapi import FastAPI, HTTPException, Response
from neo4j import AsyncGraphDatabase
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from pydantic import BaseModel, Field
import neo4j

from .config import get_settings
from .orchestrator import AgenticOrchestrator
from .models import AgenticTask, AgenticTaskResult, SystemStatus, AgentDefinition, AgenticSubtask, TaskType, TaskStatus
from .state_manager import StateManager
from .queue_client import MessageQueueClient
from .dag_executor import DAGExecutor

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("mcp_server")

settings = get_settings()

@contextlib.asynccontextmanager
async def lifespan(fastapi_app: FastAPI):
    # Startup
    logger.info("Starting MCP Server...")
    
    # Initialize infrastructure
    state_manager = StateManager(settings)
    await state_manager.connect()
    
    queue_client = MessageQueueClient(settings)
    await queue_client.connect()
    
    fastapi_app.state.state_manager = state_manager
    fastapi_app.state.queue_client = queue_client
    
    # Initialize Orchestrator with state manager
    fastapi_app.state.orchestrator = AgenticOrchestrator(state_manager=state_manager)
    # Initialize DAG Executor
    fastapi_app.state.dag_executor = DAGExecutor(orchestrator=fastapi_app.state.orchestrator)

    # Neo4j is optional. Attempt best-effort initialization.
    fastapi_app.state.neo4j_driver = None  # type: ignore[attr-defined]
    try:
        if getattr(settings, "NEO4J_URI", None):
            fastapi_app.state.neo4j_driver = AsyncGraphDatabase.driver(
                settings.NEO4J_URI,
                auth=(getattr(settings, "NEO4J_USERNAME", "neo4j"), getattr(settings, "NEO4J_PASSWORD", "")),
            )
            logger.info("Neo4j driver initialized")
    except (neo4j.exceptions.Neo4jError, OSError, RuntimeError, ValueError) as e:
        logger.warning("Neo4j driver not initialized (non-fatal): %s", e)
        fastapi_app.state.neo4j_driver = None  # type: ignore[attr-defined]

    yield
    
    # Shutdown
    logger.info("Shutting down MCP Server...")
    if hasattr(fastapi_app.state, 'queue_client'):
        await fastapi_app.state.queue_client.close()
    if hasattr(fastapi_app.state, 'state_manager'):
        await fastapi_app.state.state_manager.close()
        
    neo4j_driver: Optional[neo4j.AsyncDriver] = getattr(fastapi_app.state, "neo4j_driver", None)
    if neo4j_driver is not None:
        await neo4j_driver.close()

app = FastAPI(
    title="GoodpointAI MCP Server",
    description="Model Context Protocol Server for Agent Orchestration",
    version="1.0.0",
    lifespan=lifespan
)

@app.get("/health")
async def health_check():
    neo4j_ok: bool = False
    if app.state.neo4j_driver is not None:
        try:
            await app.state.neo4j_driver.verify_connectivity()
            neo4j_ok = True
        except Exception:
            neo4j_ok = False
    return {
        "status": "healthy",
        "service": settings.MCP_SERVER_ID,
        "neo4j_connected": neo4j_ok,
    }

@app.get("/metrics")
async def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

@app.get("/mcp/v1/agents")
async def list_agents():
    # Return list of agents from orchestrator
    orchestrator: AgenticOrchestrator = app.state.orchestrator
    return list(orchestrator.agents.values())

@app.post("/mcp/v1/agents/register")
async def register_agent(agent: AgentDefinition):
    orchestrator: AgenticOrchestrator = app.state.orchestrator
    return await orchestrator.register_agent(agent)

@app.post("/mcp/v1/tasks", response_model=AgenticTaskResult)
async def submit_task(task: AgenticTask):
    orchestrator: AgenticOrchestrator = app.state.orchestrator
    dag_executor: DAGExecutor = app.state.dag_executor
    if dag_executor.orchestrator is not orchestrator:
        dag_executor.orchestrator = orchestrator
    # Use DAG executor natively. If no subtasks, it delegates immediately to standard execution
    result = await dag_executor.execute_task_with_subtasks(task)
    return result


@app.get("/mcp/v1/tasks/{task_id}", response_model=AgenticTaskResult)
async def get_task_status(task_id: str):
    orchestrator: AgenticOrchestrator = app.state.orchestrator
    state_manager: StateManager = app.state.state_manager

    # Check in-memory result cache first (fastest path)
    if task_id in orchestrator.task_results:
        return orchestrator.task_results[task_id]

    # Fall back to persistent state (survives server restarts)
    persisted = await state_manager.get_task_state(task_id)
    if persisted:
        return AgenticTaskResult(**persisted)

    raise HTTPException(status_code=404, detail="Task not found")


class DagSubmission(BaseModel):
    """Submit a pre-decomposed subtask DAG for parallel/sequential execution.

    The ``subtasks`` list is executed by DAGExecutor in dependency order.
    Each subtask ``type`` must be a valid TaskType value.
    Each subtask ``dependencies`` list references other subtask ``id`` values.
    """
    parent_task_id: str = Field(default_factory=lambda: f"dag_{uuid.uuid4().hex[:12]}")
    goal: str = ""
    subtasks: List[Dict[str, Any]]
    priority: int = 5


@app.post("/mcp/v1/tasks/dag", response_model=AgenticTaskResult)
async def submit_dag(submission: DagSubmission):
    """Execute a list of subtasks as a dependency-ordered DAG.

    Subtask format::

        {
            "id": "st_abc",
            "type": "data_discovery",           # TaskType value
            "required_capabilities": ["discover_files"],
            "payload": {...},
            "dependencies": [],                  # ids of subtasks that must finish first
            "priority": 5
        }
    """
    orchestrator: AgenticOrchestrator = app.state.orchestrator
    dag_executor: DAGExecutor = app.state.dag_executor

    wrapper_id = submission.parent_task_id

    # Build AgenticSubtask objects
    built_subtasks: List[AgenticSubtask] = []
    for raw in submission.subtasks:
        raw_type = raw.get("type", "data_analysis")
        try:
            task_type = TaskType(raw_type)
        except ValueError:
            task_type = TaskType.DATA_ANALYSIS
        built_subtasks.append(
            AgenticSubtask(
                id=raw.get("id") or f"st_{uuid.uuid4().hex[:12]}",
                parent_task_id=wrapper_id,
                type=task_type,
                required_capabilities=raw.get("required_capabilities", []),
                payload=raw.get("payload", {}),
                dependencies=raw.get("dependencies", []),
                priority=raw.get("priority", 5),
            )
        )

    wrapper_task = AgenticTask(
        id=wrapper_id,
        type=TaskType.TASK_DECOMPOSITION,
        required_capabilities=[],
        payload={"goal": submission.goal, "source": "dag_endpoint"},
        subtasks=built_subtasks,
        priority=submission.priority,
    )

    result = await dag_executor.execute_task_with_subtasks(wrapper_task)
    return result


@app.get("/mcp/v1/capabilities")
async def list_capabilities():
    """Return a deduplicated map of capability → [agent_id, …] for the director pattern."""
    orchestrator: AgenticOrchestrator = app.state.orchestrator
    cap_map: Dict[str, List[str]] = {}
    for agent_id, agent in orchestrator.agents.items():
        for cap in agent.capabilities:
            cap_map.setdefault(cap.name, []).append(agent_id)
    return {"capabilities": cap_map, "agent_count": len(orchestrator.agents)}

@app.get("/mcp/v1/system/status", response_model=SystemStatus)
async def get_system_status():
    orchestrator: AgenticOrchestrator = app.state.orchestrator
    return orchestrator.get_system_status()

@app.get("/")
async def root():
    return {"message": "MCP Server is running", "docs": "/docs"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "mcp_server.main:app", 
        host=settings.MCP_SERVER_HOST, 
        port=settings.MCP_SERVER_PORT, 
        reload=True
    )
