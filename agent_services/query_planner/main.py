import sys
import os
import asyncio
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from contextlib import asynccontextmanager
from fastapi import FastAPI

# Add parent directory to path to allow importing base
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

# Load environment variables from backend .env
env_path = Path(__file__).resolve().parent.parent.parent / "python_backend" / ".env"
load_dotenv(dotenv_path=env_path)

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
    async def _lifespan(self, app: FastAPI):
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

        async with super()._lifespan(app):
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

    async def process_task(self, task: AgentTaskRequest):
        # Implementation of Query Planner logic
        # Placeholder for now
        
        return {
            "status": "Query plan generated", 
            "task_id": task.task_id,
            "execution_plan": "Computed optimized path",
            "estimated_cost": 10,
            "timestamp": datetime.now().isoformat()
        }

if __name__ == "__main__":
    agent = QueryPlannerAgent()
    agent.start()
