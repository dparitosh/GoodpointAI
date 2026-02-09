from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient
from mcp_server.main import app
from mcp_server.models import TaskType

def test_health_check():
    with TestClient(app) as client:
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

def test_list_agents():
    with TestClient(app) as client:
        response = client.get("/mcp/v1/agents")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0

@patch("mcp_server.orchestrator.AgenticOrchestrator.execute_task", new_callable=AsyncMock)
def test_submit_task(mock_execute):
    # Setup mock return value
    mock_execute.return_value = {
        "task_id": "test-task-123",
        "agent_id": "test-agent-001",
        "status": "completed",
        "result": {"status": "success"},
        "agent_type": "data_analyst",
        "success": True,
        "error": None,
        "execution_time": 0.1,
        "timestamp": "2024-01-01T00:00:00"
    }
    
    payload = {
        "type": "data_analysis",
        "payload": {"query": "test"},
        "required_capabilities": ["analyze_data_patterns"]
    }
    
    with TestClient(app) as client:
        response = client.post("/mcp/v1/tasks", json=payload)
        assert response.status_code == 200
        assert response.json()["task_id"] == "test-task-123"
