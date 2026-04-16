import json
import logging
from typing import Optional, Any, Dict, List, Awaitable, cast
import redis
import redis.asyncio as redis_async
from datetime import datetime

from .config import Settings

logger = logging.getLogger(__name__)
RedisError = redis.exceptions.RedisError

class StateManager:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.redis: Optional[redis_async.Redis] = None
        self.use_redis = False
        self._memory_store: Dict[str, str] = {}
        self._connected = False

    @property
    def is_connected(self) -> bool:
        """True only when backing Redis connection is active."""
        return self._connected

    async def connect(self):
        """Initialize connection to Redis"""
        if self.settings.REDIS_URL:
            try:
                self.redis = redis_async.from_url(
                    self.settings.REDIS_URL,
                    encoding="utf-8",
                    decode_responses=True
                )
                await self.redis.ping()
                self.use_redis = True
                self._connected = True
                logger.info("Connected to Redis")
                return
            except (RedisError, OSError, RuntimeError, ValueError, TypeError) as e:
                logger.warning("Failed to connect to Redis: %s. Falling back to in-memory storage.", e)
        
        self.use_redis = False
        self._connected = False
        logger.warning("Using in-memory storage. interactions will not persist across restarts.")

    async def close(self):
        if not self.redis:
            return

        aclose = getattr(self.redis, "aclose", None)
        if callable(aclose):
            aclose_result = aclose()
            if hasattr(aclose_result, "__await__"):
                await cast(Awaitable[object], aclose_result)
        else:
            close_result = self.redis.close()
            if hasattr(close_result, "__await__"):
                await cast(Awaitable[object], close_result)

        self.use_redis = False
        self._connected = False
        self.redis = None

    async def register_agent(self, agent_id: str, metadata: Dict[str, Any], ttl: int = 300):
        """Register an active agent with a TTL"""
        key = f"agent:{agent_id}"
        metadata["last_heartbeat"] = datetime.now().isoformat()
        value = json.dumps(metadata)

        if self.use_redis and self.redis:
            try:
                await self.redis.set(key, value, ex=ttl)
            except (RedisError, OSError, RuntimeError, ValueError, TypeError) as e:
                logger.error("Failed to register agent %s: %s", agent_id, e)
        else:
            self._memory_store[key] = value

    async def get_active_agents(self) -> List[Dict[str, Any]]:
        """Get all currently active agents"""
        agents = []
        
        if self.use_redis and self.redis:
            try:
                keys = await self.redis.keys("agent:*")
                if not keys:
                    return []
                
                # Using mget for efficiency, but keys is a list of keys
                agents_json = await self.redis.mget(keys)
                for j in agents_json:
                    if j:
                        agents.append(json.loads(j))
            except (RedisError, OSError, RuntimeError, ValueError, TypeError, json.JSONDecodeError) as e:
                logger.error("Failed to get active agents: %s", e)
        else:
            for key, val in self._memory_store.items():
                if key.startswith("agent:"):
                    try:
                        agents.append(json.loads(val))
                    except (TypeError, ValueError, json.JSONDecodeError):
                        pass
                        
        return agents

    async def save_task_state(self, task_id: str, state: Dict[str, Any], ttl: int = 3600):
        """Persist task state/result"""
        key = f"task:{task_id}"
        value = json.dumps(state)

        if self.use_redis and self.redis:
            try:
                await self.redis.set(key, value, ex=ttl)
            except (RedisError, OSError, RuntimeError, ValueError, TypeError) as e:
                logger.error("Failed to save task state %s: %s", task_id, e)
        else:
            self._memory_store[key] = value

    async def get_task_state(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve task state"""
        key = f"task:{task_id}"
        
        if self.use_redis and self.redis:
            try:
                data = await self.redis.get(key)
                if data:
                    return json.loads(data)
                return None
            except (RedisError, OSError, RuntimeError, ValueError, TypeError, json.JSONDecodeError) as e:
                logger.error("Failed to get task state %s: %s", task_id, e)
                return None
        else:
            data = self._memory_store.get(key)
            if data:
                return json.loads(data)
            return None
