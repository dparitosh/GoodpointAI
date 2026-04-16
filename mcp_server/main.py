import logging
import contextlib
from fastapi import FastAPI, HTTPException, Response
from neo4j import AsyncGraphDatabase
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from typing import Optional

import neo4j

from .config import get_settings
from .orchestrator import AgenticOrchestrator
from .models import AgenticTask, AgenticTaskResult, SystemStatus, AgentDefinition
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
    return {
        "status": "healthy", 
        "service": settings.MCP_SERVER_ID,
        "neo4j_connected": app.state.neo4j_driver is not None
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
    if task_id in orchestrator.task_results:
        return orchestrator.task_results[task_id]
    raise HTTPException(status_code=404, detail="Task not found")

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
