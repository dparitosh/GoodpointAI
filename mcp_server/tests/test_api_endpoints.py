from fastapi.testclient import TestClient
from mcp_server.main import app
from mcp_server.models import AgenticTask, TaskType
from unittest.mock import MagicMock, AsyncMock
from mcp_server.orchestrator import AgenticOrchestrator

client = TestClient(app)

def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"

def test_list_agents():
    response = client.get("/mcp/v1/agents")
    assert response.status_code == 200
    agents = response.json()
    assert isinstance(agents, list)
    # Check if we have agents
    assert len(agents) > 0
    # Check structure
    assert "id" in agents[0]
    assert "type" in agents[0]

import pytest
from mcp_server.models import AgenticTaskResult, AgentType

@pytest.mark.asyncio
async def test_submit_task():
    # Mock the orchestrator on app.state
    
    msg_result = AgenticTaskResult(
        task_id="test-task-123",
        agent_id="test-agent",
        agent_type=AgentType.DATA_ANALYST,
        success=True,
        result={"status": "done"},
        execution_time=0.1
    )

    mock_orchestrator = MagicMock()
    mock_orchestrator.execute_task = AsyncMock(return_value=msg_result)
    mock_orchestrator.agents = {} 
    
    # Replace the orchestrator
    app.state.orchestrator = mock_orchestrator
    
    task_payload = {
        "id": "test-task-123",
        "type": "data_analysis",
        "required_capabilities": ["analyze_data"],
        "payload": {}
    }
    
    response = client.post("/mcp/v1/tasks", json=task_payload)
    
    assert response.status_code == 200
    data = response.json()
    assert data["task_id"] == "test-task-123"
    assert data["success"] is True
    
    # Verify call
    mock_orchestrator.execute_task.assert_called_once()

def test_get_task_status():
    # Setup mock
    mock_orchestrator = MagicMock()
    app.state.orchestrator = mock_orchestrator
    
    # Pre-populate results
    result_obj = AgenticTaskResult(
        task_id="existing-task",
        agent_id="agent-1",
        agent_type=AgentType.CHAT_COORDINATOR,
        success=True,
        result={"foo": "bar"},
        execution_time=0.5
    )
    
    # The endpoint accesses orchestrator.task_results directly
    mock_orchestrator.task_results = {
        "existing-task": result_obj
    }
    
    response = client.get("/mcp/v1/tasks/existing-task")
    assert response.status_code == 200
    assert response.json()["task_id"] == "existing-task"
    
    # Test 404
    response = client.get("/mcp/v1/tasks/non-existent")
    assert response.status_code == 404
