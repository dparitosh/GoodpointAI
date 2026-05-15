import httpx
import logging
import time
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
        self._mcp_available: Optional[bool] = None
        self._mcp_check_timestamp: float = 0

    async def _is_mcp_available(self) -> bool:
        """Quick check if MCP is available (cached for 5 seconds)."""
        now = time.time()
        
        # Use cached result if recent
        if self._mcp_available is not None and (now - self._mcp_check_timestamp) < 5:
            return self._mcp_available
        
        try:
            async with httpx.AsyncClient(timeout=1.0) as client:
                response = await client.get(f"{self.base_url}/health", follow_redirects=True)
                self._mcp_available = response.status_code == 200
                self._mcp_check_timestamp = now
                if not self._mcp_available:
                    logger.debug("MCP health check failed with status %d", response.status_code)
                return self._mcp_available
        except Exception:
            self._mcp_available = False
            self._mcp_check_timestamp = now
            logger.debug("MCP unavailable (connection failed)")
            return False

    @retry(
        stop=stop_after_attempt(1),
        wait=wait_exponential(multiplier=1, min=1, max=1),
        retry=retry_if_exception_type((httpx.ConnectError, httpx.TimeoutException)),
        reraise=False  # Don't reraise, return empty list instead
    )
    async def list_agents(self) -> List[Dict[str, Any]]:
        if not await self._is_mcp_available():
            logger.debug("MCP unavailable, skipping list_agents")
            return []
        
        async with httpx.AsyncClient(timeout=2.0) as client:
            try:
                response = await client.get(f"{self.base_url}/mcp/v1/agents")
                response.raise_for_status()
                return response.json()
            except httpx.HTTPError as e:
                logger.debug("Failed to list MCP agents: %s", e)
                return []

    @retry(
        stop=stop_after_attempt(1),
        wait=wait_exponential(multiplier=1, min=1, max=1),
        retry=retry_if_exception_type((httpx.ConnectError, httpx.TimeoutException, httpx.ReadTimeout)),
        reraise=False
    )
    async def submit_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        if not await self._is_mcp_available():
            logger.debug("MCP unavailable, cannot submit task")
            return {"error": "MCP server unavailable", "task_id": None}
        
        async with httpx.AsyncClient(timeout=2.0) as client:
            try:
                response = await client.post(f"{self.base_url}/mcp/v1/tasks", json=task)
                response.raise_for_status()
                return response.json()
            except httpx.HTTPError as e:
                logger.debug("Failed to submit task to MCP: %s", e)
                return {"error": str(e), "task_id": None}

    @retry(
        stop=stop_after_attempt(1),
        wait=wait_exponential(multiplier=1, min=1, max=1),
        retry=retry_if_exception_type((httpx.ConnectError, httpx.TimeoutException)),
        reraise=False
    )
    async def get_task_status(self, task_id: str) -> Dict[str, Any]:
        if not await self._is_mcp_available():
            logger.debug("MCP unavailable, cannot get task status")
            return {"task_id": task_id, "status": "unavailable"}
        
        async with httpx.AsyncClient(timeout=2.0) as client:
            try:
                response = await client.get(f"{self.base_url}/mcp/v1/tasks/{task_id}")
                response.raise_for_status()
                return response.json()
            except httpx.HTTPError as e:
                logger.debug("Failed to get task status %s: %s", task_id, e)
                return {"task_id": task_id, "status": "unknown"}

    async def check_health(self) -> bool:
        async with httpx.AsyncClient(timeout=2.0) as client:
            try:
                response = await client.get(f"{self.base_url}/health")
                return response.status_code == 200
            except Exception:
                return False

    @retry(
        stop=stop_after_attempt(1),
        wait=wait_exponential(multiplier=1, min=1, max=1),
        retry=retry_if_exception_type((httpx.ConnectError, httpx.TimeoutException)),
        reraise=False
    )
    async def get_system_status(self) -> Dict[str, Any]:
        if not await self._is_mcp_available():
            logger.debug("MCP unavailable, returning degraded status")
            return {
                "system_health": "unavailable",
                "active_agents": [],
                "task_queue_size": 0,
                "performance_metrics": {"mcp_available": False},
            }
        
        async with httpx.AsyncClient(timeout=2.0) as client:
            try:
                response = await client.get(f"{self.base_url}/mcp/v1/system/status")
                response.raise_for_status()
                return response.json()
            except httpx.HTTPError as e:
                logger.debug("Failed to get system status: %s", e)
                return {
                    "system_health": "unavailable",
                    "active_agents": [],
                    "task_queue_size": 0,
                    "performance_metrics": {"mcp_available": False},
                }


# Module-level singleton — shared across all consumers (main.py, agentic_router.py, etc.)
mcp_client: MCPClient = MCPClient()
