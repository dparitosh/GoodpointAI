import json
import logging
import os
import random
import re
import httpx
import uvicorn
import asyncio
from typing import List, Dict, Any, Optional
from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
from fastapi import FastAPI

from .models import AgentTaskRequest, AgentTaskResponse, AgentRegistration, AgentCapability, TaskStatus, AgentType

# Configure Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("agent_service")

class AgentService(ABC):
    def __init__(self, 
                 agent_type: AgentType, 
                 agent_name: str, 
                 port: int,
                 mcp_server_url: str = "http://localhost:8012"):
        self.agent_type = agent_type
        self.agent_name = agent_name
        self.port = port
        self.mcp_server_url = os.getenv("MCP_SERVER_URL", mcp_server_url)
        self.agent_id = f"{agent_type.value}-{os.getenv('AGENT_INSTANCE_ID', 'default')}"
        # Heartbeat task reference held to prevent GC
        self._registration_task: Optional[asyncio.Task] = None

        # Initialize FastAPI
        self.app = FastAPI(
            title=f"{agent_name} Service",
            version="1.0.0",
            lifespan=self._lifespan
        )
        self._setup_routes()

    @abstractmethod
    def get_capabilities(self) -> List[AgentCapability]:
        """Define capabilities of this specific agent."""
        pass

    @abstractmethod
    async def process_task(self, task: AgentTaskRequest) -> Dict[str, Any]:
        """Implement the core logic for the agent here."""
        pass

    def _setup_routes(self):
        @self.app.get("/health")
        async def health_check():
            return {"status": "healthy", "agent_id": self.agent_id}

        @self.app.get("/info")
        async def agent_info():
            return {
                "id": self.agent_id,
                "type": self.agent_type,
                "name": self.agent_name,
                "capabilities": self.get_capabilities()
            }

        @self.app.post("/execute", response_model=AgentTaskResponse)
        async def execute_task(task: AgentTaskRequest):
            logger.info("Received task %s of type %s", task.task_id, task.task_type)
            loop = asyncio.get_running_loop()
            start_time = loop.time()

            try:
                result = await self.process_task(task)
                duration_ms = (loop.time() - start_time) * 1000
                return AgentTaskResponse(
                    task_id=task.task_id,
                    status=TaskStatus.COMPLETED,
                    result=result,
                    execution_time_ms=duration_ms
                )
            except Exception as e:
                logger.error("Task %s execution failed: %s", task.task_id, e, exc_info=True)
                duration_ms = (loop.time() - start_time) * 1000
                return AgentTaskResponse(
                    task_id=task.task_id,
                    status=TaskStatus.FAILED,
                    result={},
                    error=str(e),
                    execution_time_ms=duration_ms
                )

    @asynccontextmanager
    async def _lifespan(self, app: FastAPI):
        # Startup: Register with MCP Server
        # Hold a reference to the task so it is not garbage-collected.
        self._registration_task = asyncio.create_task(self._maintain_registration())

        yield

        # Shutdown: cancel heartbeat
        if self._registration_task and not self._registration_task.done():
            self._registration_task.cancel()
            try:
                await self._registration_task
            except asyncio.CancelledError:
                pass
        logger.info("Shutting down agent service...")

    async def _maintain_registration(self):
        """Periodically register with MCP server (heartbeat pattern).
        
        A random jitter of 0–5 s is applied on each iteration so all
        agents don't thunder-herd the MCP server simultaneously on restart.
        """
        while True:
            await self.register_with_mcp()
            jitter = random.uniform(0, 5)
            await asyncio.sleep(30 + jitter)

    async def register_with_mcp(self):
        """Register valid endpoint with the MCP Server so it can route tasks here."""
        # Use server-side AgentDefinition field names (id, type, name)
        # instead of client-side AgentRegistration names (agent_id, agent_type).
        
        payload = {
            "id": self.agent_id,
            "type": self.agent_type.value,
            "name": self.agent_name,
            "service_url": f"http://{os.getenv('AGENT_SERVICE_HOST', 'localhost')}:{self.port}",
            "capabilities": [c.model_dump() for c in self.get_capabilities()],
            "status": "ready",
            "metadata": {"version": "1.0.0"}
        }
        
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                # Assuming /mcp/v1/agents/register endpoint exists or will exist
                # If not, we need to create it in MCP Server.
                # For now, we'll try to hit a standard registration endpoint.
                resp = await client.post(
                    f"{self.mcp_server_url}/mcp/v1/agents/register", 
                    json=payload
                )
                if resp.status_code in (200, 201):
                    logger.info("Successfully registered with MCP Server (Heartbeat).")
                else:
                    logger.warning("Registration failed: %s - %s", resp.status_code, resp.text)
        except Exception as e:
            # Log as debug to avoid spamming console if MCP is down for a while
            logger.debug("Could not register with MCP Server (is it running?): %s", e)

    async def _adaptive_llm_call(
        self,
        backend_url: str,
        system_prompt: str,
        user_content: str,
        llm_provider: str = "openai",
        max_attempts: int = 3,
        temperature: float = 0.1,
        max_tokens: int = 1800,
    ) -> Optional[Any]:
        """Error-adaptive LLM call — Marker 1 (AI-Powered Agent).

        Inspects each failure and modifies the request before retrying:
          - HTTP 429 (rate-limited)  → exponential back-off
          - HTTP 400/422 (too large) → truncate user_content, retry
          - Non-JSON response        → inject correction turn, retry
          - Timeout                  → halve max_tokens, retry

        Returns parsed JSON (dict or list) on success, None on full exhaustion.
        """
        backend_url_resolved = os.getenv("GRAPH_TRACE_BACKEND_URL", backend_url)
        messages: List[Dict[str, Any]] = [
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_content},
        ]
        current_max_tokens = max_tokens
        current_user_content = user_content
        is_ollama = str(llm_provider).strip().lower() == "ollama"
        if is_ollama:
            ollama_cap = max(32, int(os.getenv("OLLAMA_MAX_TOKENS_CAP", "256")))
            current_max_tokens = min(current_max_tokens, ollama_cap)
            request_timeout = max(5.0, float(os.getenv("OLLAMA_REQUEST_TIMEOUT_SECONDS", "75")))
            min_retry_max_tokens = max(32, int(os.getenv("OLLAMA_MIN_RETRY_MAX_TOKENS", "96")))
        else:
            request_timeout = 30.0
            min_retry_max_tokens = 512

        for attempt in range(max_attempts):
            try:
                async with httpx.AsyncClient(timeout=request_timeout) as client:
                    resp = await client.post(
                        f"{backend_url_resolved}/api/llm/chat",
                        params={"provider": llm_provider},
                        json={
                            "messages": messages,
                            "temperature": temperature,
                            "max_tokens": current_max_tokens,
                        },
                    )

                if resp.is_success:
                    raw = resp.json().get("response", "")
                    raw = re.sub(r"```(?:json)?", "", raw).strip().strip("`").strip()
                    m = re.search(r"\[.*\]|\{.*\}", raw, re.DOTALL)
                    if m:
                        return json.loads(m.group(0))
                    # Non-JSON response — ask LLM to fix its output format
                    if attempt < max_attempts - 1:
                        logger.debug(
                            "LLM returned non-JSON (attempt %d/%d) — injecting correction turn",
                            attempt + 1, max_attempts,
                        )
                        messages.append({"role": "assistant", "content": raw[:500]})
                        messages.append({
                            "role": "user",
                            "content": (
                                "Your previous response was not valid JSON. "
                                "Output ONLY a valid JSON array or object — "
                                "no markdown, no explanation, no code fences."
                            ),
                        })
                        continue
                    return None

                # HTTP error — inspect status and adapt payload
                status = resp.status_code
                if status == 429 and attempt < max_attempts - 1:
                    wait = 2 ** attempt
                    logger.debug("LLM rate-limited (attempt %d) — backing off %ds", attempt + 1, wait)
                    await asyncio.sleep(wait)
                elif status in (400, 422) and attempt < max_attempts - 1:
                    current_user_content = current_user_content[: len(current_user_content) // 2]
                    messages[1] = {"role": "user", "content": current_user_content}
                    logger.debug(
                        "LLM rejected payload HTTP %d (attempt %d) — truncating to %d chars",
                        status, attempt + 1, len(current_user_content),
                    )
                else:
                    logger.debug("LLM HTTP %d on attempt %d — aborting", status, attempt + 1)
                    return None

            except httpx.TimeoutException:
                current_max_tokens = max(min_retry_max_tokens, current_max_tokens // 2)
                logger.debug(
                    "LLM timeout (attempt %d) — retrying with max_tokens=%d",
                    attempt + 1, current_max_tokens,
                )
            except Exception as exc:
                logger.debug("LLM call error (attempt %d/%d): %s", attempt + 1, max_attempts, exc)
                if attempt >= max_attempts - 1:
                    return None
                await asyncio.sleep(1)

        logger.debug("All %d LLM retry attempts exhausted", max_attempts)
        return None

    def start(self):
        """Run the service"""
        uvicorn.run(self.app, host="0.0.0.0", port=self.port)
