import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from mcp_server.config import Settings
from mcp_server.state_manager import StateManager
from mcp_server.queue_client import MessageQueueClient

@pytest.fixture
def mock_settings():
    return Settings(
        REDIS_URL="redis://mock:6379/0",
        AZURE_SERVICE_BUS_CONNECTION_STRING="Endpoint=sb://mock.servicebus.windows.net/;SharedAccessKeyName=RootManageSharedAccessKey;SharedAccessKey=mock",
        MCP_QUEUE_NAME="mock-queue"
    )

@pytest.mark.asyncio
async def test_state_manager_connection(mock_settings):
    with patch("redis.asyncio.from_url") as mock_redis_cls:
        mock_redis = AsyncMock()
        mock_redis_cls.return_value = mock_redis
        
        manager = StateManager(mock_settings)
        await manager.connect()
        
        assert manager.is_connected is True
        mock_redis.ping.assert_called_once()
        
        await manager.close()
        mock_redis.close.assert_called_once()
        assert manager.is_connected is False

@pytest.mark.asyncio
async def test_state_manager_task_persistence(mock_settings):
    with patch("redis.asyncio.from_url") as mock_redis_cls:
        mock_redis = AsyncMock()
        # Mock get to return bytes or string
        mock_redis.get.return_value = '{"status": "done"}'
        mock_redis_cls.return_value = mock_redis
        
        manager = StateManager(mock_settings)
        await manager.connect()
        
        # Test Save
        await manager.save_task_state("task-1", {"status": "done"})
        mock_redis.set.assert_called_once()
        
        # Test Get
        res = await manager.get_task_state("task-1")
        assert res == {"status": "done"}

    @pytest.mark.asyncio
    async def test_queue_client_publish(mock_settings):
        with patch("azure.servicebus.aio.ServiceBusClient.from_connection_string") as mock_sb_cls:
            mock_client = AsyncMock()
            mock_sender = AsyncMock()
            
            mock_sb_cls.return_value = mock_client
            # get_queue_sender IS synchronous in azure-servicebus library (it returns a sender object)
            # but the sender object methods are async
            mock_client.get_queue_sender.return_value = mock_sender
            
            client = MessageQueueClient(mock_settings)
            await client.connect()
            
            assert client.is_connected is True
            
            # Test Publish
            await client.publish_message({"msg": "test"}, correlation_id="123")
            mock_sender.send_messages.assert_called_once()
            
            await client.close()

@pytest.mark.asyncio
async def test_infra_graceful_missing_config():
    # Settings with empty values
    empty_settings = Settings(
        REDIS_URL="",
        AZURE_SERVICE_BUS_CONNECTION_STRING=""
    )
    
    # State Manager
    manager = StateManager(empty_settings)
    await manager.connect()
    assert manager.is_connected is False
    # Should not raise
    await manager.save_task_state("t1", {}) 
    
    # Queue Client
    q_client = MessageQueueClient(empty_settings)
    await q_client.connect()
    assert q_client.is_connected is False
    # Should not raise
    await q_client.publish_message({})
