import httpx
import logging
from typing import Dict, Any, Optional, List
from pydantic_settings import BaseSettings, SettingsConfigDict
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

logger = logging.getLogger(__name__)

class MCPSettings(BaseSettings):
    MCP_SERVER_URL: str = "http://localhost:8012"
    MCP_TIMEOUT: float = 10.0  # per-request timeout for task/agent calls

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

class MCPClient:
    def __init__(self, settings: Optional[MCPSettings] = None):
        self.settings = settings or MCPSettings()
        self.base_url = self.settings.MCP_SERVER_URL

    @retry(
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=1, min=1, max=3),
        retry=retry_if_exception_type((httpx.ConnectError, httpx.TimeoutException)),
        reraise=True
    )
    async def list_agents(self) -> List[Dict[str, Any]]:
        async with httpx.AsyncClient(timeout=self.settings.MCP_TIMEOUT) as client:
            try:
                response = await client.get(f"{self.base_url}/mcp/v1/agents")
                response.raise_for_status()
                return response.json()
            except httpx.HTTPError as e:
                logger.error(f"Failed to list MCP agents: {e}")
                raise

    @retry(
        stop=stop_after_attempt(1),
        wait=wait_exponential(multiplier=1, min=1, max=3),
        retry=retry_if_exception_type((httpx.ConnectError, httpx.TimeoutException, httpx.ReadTimeout)),
        reraise=True
    )
    async def submit_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        async with httpx.AsyncClient(timeout=self.settings.MCP_TIMEOUT) as client:
            try:
                response = await client.post(f"{self.base_url}/mcp/v1/tasks", json=task)
                response.raise_for_status()
                return response.json()
            except httpx.HTTPError as e:
                logger.error(f"Failed to submit task to MCP: {e}")
                raise

    @retry(
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=1, min=1, max=3),
        retry=retry_if_exception_type((httpx.ConnectError, httpx.TimeoutException)),
        reraise=True
    )
    async def get_task_status(self, task_id: str) -> Dict[str, Any]:
        async with httpx.AsyncClient(timeout=self.settings.MCP_TIMEOUT) as client:
            try:
                response = await client.get(f"{self.base_url}/mcp/v1/tasks/{task_id}")
                response.raise_for_status()
                return response.json()
            except httpx.HTTPError as e:
                logger.error(f"Failed to get task status {task_id}: {e}")
                raise

    async def check_health(self) -> bool:
        async with httpx.AsyncClient(timeout=2.0) as client:
            try:
                response = await client.get(f"{self.base_url}/health")
                return response.status_code == 200
            except Exception:
                return False

    @retry(
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=1, min=1, max=3),
        retry=retry_if_exception_type((httpx.ConnectError, httpx.TimeoutException)),
        reraise=True
    )
    async def get_system_status(self) -> Dict[str, Any]:
        async with httpx.AsyncClient(timeout=self.settings.MCP_TIMEOUT) as client:
            try:
                response = await client.get(f"{self.base_url}/mcp/v1/system/status")
                response.raise_for_status()
                return response.json()
            except httpx.HTTPError as e:
                logger.error("Failed to get system status: %s", e)
                raise


# Module-level singleton — shared across all consumers (main.py, agentic_router.py, etc.)
mcp_client: MCPClient = MCPClient()
