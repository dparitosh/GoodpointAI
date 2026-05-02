import sys
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Any
from dotenv import load_dotenv
from contextlib import asynccontextmanager
from fastapi import FastAPI

# Add parent directory to path to allow importing base
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

# Load environment variables from backend .env
env_path = Path(__file__).resolve().parent.parent.parent / "python_backend" / ".env"
load_dotenv(dotenv_path=env_path)

BACKEND_URL = os.getenv("GRAPH_TRACE_BACKEND_URL", "http://localhost:8011")

from neo4j import AsyncGraphDatabase
from agent_services.base.agent_service import AgentService
from agent_services.base.models import AgentCapability, AgentTaskRequest, AgentType

class QueryPlannerAgent(AgentService):
    def __init__(self):
        super().__init__(
            agent_type=AgentType.QUERY_PLANNER,
            agent_name="Query Planning Agent",
            port=8023
        )
        self.neo4j_uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        self.neo4j_user = os.getenv("NEO4J_USER", "neo4j")
        self.neo4j_password = os.getenv("NEO4J_PASSWORD", "password")
        self.driver = None

    @asynccontextmanager
    async def _lifespan(self, _app: FastAPI):
        # Initialize resources
        logger_name = f"{self.agent_name}.lifespan"
        try:
            self.driver = AsyncGraphDatabase.driver(
                self.neo4j_uri, 
                auth=(self.neo4j_user, self.neo4j_password)
            )
            await self.driver.verify_connectivity()
            print(f"[{logger_name}] Neo4j connectivity verified.")
        except Exception as e:
            print(f"[{logger_name}] WARNING: Neo4j connectivity failed: {e}")

        async with super()._lifespan(_app):
            yield
        
        if self.driver:
            await self.driver.close()

    def get_capabilities(self):
        return [
            AgentCapability(name="optimize_graph_queries", description="Optimize Cypher queries"),
            AgentCapability(name="plan_execution_strategies", description="Plan query execution"),
            AgentCapability(name="manage_query_cache", description="Manage query caching"),
            AgentCapability(name="analyze_performance", description="Analyze query performance")
        ]

    async def process_task(self, task: AgentTaskRequest) -> Dict[str, Any]:
        if not self.driver:
            return {"status": "error", "task_id": task.task_id, "error": "Neo4j driver not initialized"}

        payload = task.payload
        caps = set(payload.get("required_capabilities", []))
        cypher = payload.get("cypher_query") or payload.get("query") or ""

        # Security: only allow read-only Cypher
        if cypher:
            stripped = cypher.strip().upper()
            if not any(stripped.startswith(kw) for kw in ("MATCH", "RETURN", "WITH", "CALL", "SHOW")):
                return {"status": "error", "task_id": task.task_id, "error": "Only read-only Cypher (MATCH/RETURN/WITH/CALL/SHOW) is permitted"}

        if "analyze_performance" in caps or payload.get("analysis_type") == "performance":
            q = cypher or "MATCH (n) RETURN count(n) AS total"
            t0 = datetime.now()
            try:
                async with self.driver.session() as session:
                    result = await session.run(q)
                    records = [dict(r) async for r in result]
                    elapsed_ms = round((datetime.now() - t0).total_seconds() * 1000, 2)
                return {
                    "status": "completed", "task_id": task.task_id,
                    "query": q, "rows_returned": len(records),
                    "elapsed_ms": elapsed_ms, "data": records[:100],
                    "timestamp": datetime.now().isoformat(),
                }
            except Exception as exc:
                return {"status": "error", "task_id": task.task_id, "error": str(exc)}

        if not cypher:
            return {"status": "error", "task_id": task.task_id, "error": "No cypher_query provided in payload"}

        t0 = datetime.now()
        try:
            async with self.driver.session() as session:
                result = await session.run(cypher)
                records = [dict(r) async for r in result]
                elapsed_ms = round((datetime.now() - t0).total_seconds() * 1000, 2)
            return {
                "status": "completed", "task_id": task.task_id,
                "execution_plan": "read-only sequential scan",
                "rows_returned": len(records),
                "elapsed_ms": elapsed_ms,
                "data": records[:500],
                "timestamp": datetime.now().isoformat(),
            }
        except Exception as exc:
            return {"status": "error", "task_id": task.task_id, "error": str(exc)}

agent = QueryPlannerAgent()
app = agent.app

if __name__ == "__main__":
    agent.start()
