import logging
import contextlib
from fastapi import FastAPI, Depends, HTTPException, Response
from neo4j import AsyncGraphDatabase
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

from .config import get_settings
from .orchestrator import AgenticOrchestrator
from .models import AgenticTask, AgenticTaskResult, SystemStatus, AgentDefinition
from .state_manager import StateManager
from .queue_client import MessageQueueClient

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("mcp_server")

settings = get_settings()

@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting MCP Server...")
    
    # Initialize infrastructure
    state_manager = StateManager(settings)
    await state_manager.connect()
    
    queue_client = MessageQueueClient(settings)
    await queue_client.connect()
    
    app.state.state_manager = state_manager
    app.state.queue_client = queue_client
    
    # Initialize Orchestrator with state manager
    app.state.orchestrator = AgenticOrchestrator(state_manager=state_manager)
    
    # Initialize Neo4j Driver (placeholder validation)
    try:
        app.state.neo4j_driver = AsyncGraphDatabase.driver(
            settings.NEO4J_URI,
            auth=(settings.NEO4J_USERNAME, settings.NEO4J_PASSWORD)
        )
        logger.info("Neo4j driver initialized")
    except Exception as e:
        logger.error(f"Failed to initialize Neo4j driver: {e}")
        app.state.neo4j_driver = None

    yield
    
    # Shutdown
    logger.info("Shutting down MCP Server...")
    if hasattr(app.state, 'queue_client'):
        await app.state.queue_client.close()
    if hasattr(app.state, 'state_manager'):
        await app.state.state_manager.close()
        
    if app.state.neo4j_driver:
        await app.state.neo4j_driver.close()

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
    result = await orchestrator.execute_task(task, app.state.neo4j_driver)
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
