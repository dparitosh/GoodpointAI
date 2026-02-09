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

class VisualizationAgent(AgentService):
    def __init__(self):
        super().__init__(
            agent_type=AgentType.VISUALIZATION_AGENT,
            agent_name="Visualization Agent",
            port=8022
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
            AgentCapability(name="generate_graph_layouts", description="Generate optimal graph layouts"),
            AgentCapability(name="create_chart_configurations", description="Create chart configurations")
        ]

    async def process_task(self, task: AgentTaskRequest):
        # Implementation of Visualization logic
        # Placeholder for now
        
        return {
            "status": "Visualization generated", 
            "task_id": task.task_id,
            "chart_config": {"type": "bar", "data": []},
            "timestamp": datetime.now().isoformat()
        }

if __name__ == "__main__":
    agent = VisualizationAgent()
    agent.start()
