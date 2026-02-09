import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock
from mcp_server.orchestrator import AgenticOrchestrator
from mcp_server.models import AgenticTask, TaskType, AgentType, AgentDefinition

@pytest.fixture
def orchestrator():
    return AgenticOrchestrator()

def test_orchestrator_initialization(orchestrator):
    assert len(orchestrator.agents) > 0
    assert any(a.type == AgentType.DATA_ANALYST for a in orchestrator.agents.values())
    assert any(a.type == AgentType.CHAT_COORDINATOR for a in orchestrator.agents.values())

@pytest.mark.asyncio
async def test_route_task_to_agent(orchestrator):
    # Create a task requiring data analysis capabilities
    task = AgenticTask(
        type=TaskType.DATA_ANALYSIS,
        required_capabilities=["analyze_data_patterns"],
        payload={}
    )
    
    agent_id = await orchestrator.route_task_to_agent(task)
    assert agent_id is not None
    agent = orchestrator.agents[agent_id]
    assert agent.type == AgentType.DATA_ANALYST

@pytest.mark.asyncio
async def test_route_task_no_agent_found(orchestrator):
    task = AgenticTask(
        type=TaskType.DATA_ANALYSIS,
        required_capabilities=["non_existent_capability"],
        payload={}
    )
    
    agent_id = await orchestrator.route_task_to_agent(task)
    assert agent_id is None

@pytest.mark.asyncio
async def test_execute_task_success(orchestrator):
    # Mock the driver and executing the specific task method
    mock_driver = AsyncMock()
    
    # We need to mock the internal method to avoid actual DB calls or complex logic for now
    # Since we are testing orchestration logic, mocking the specific execution is valid
    orchestrator._execute_data_analysis_task = AsyncMock(return_value={"status": "success"})
    
    task = AgenticTask(
        type=TaskType.DATA_ANALYSIS,
        required_capabilities=["analyze_data_patterns"],
        payload={}
    )
    
    result = await orchestrator.execute_task(task, mock_driver)
    
    assert result.success is True
    assert result.agent_type == AgentType.DATA_ANALYST
    assert "status" in result.result

@pytest.mark.asyncio
async def test_execute_task_failure(orchestrator):
    mock_driver = AsyncMock()
    # Mock raising an exception
    orchestrator._execute_data_analysis_task = AsyncMock(side_effect=ValueError("Test Error"))
    
    task = AgenticTask(
        type=TaskType.DATA_ANALYSIS,
        required_capabilities=["analyze_data_patterns"],
        payload={}
    )
    
    result = await orchestrator.execute_task(task, mock_driver)
    
    assert result.success is False
    assert result.error == "Test Error"
