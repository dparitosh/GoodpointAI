import sys
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List
from dotenv import load_dotenv
from contextlib import asynccontextmanager
from fastapi import FastAPI

import httpx

# Add parent directory to path to allow importing base
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

# Load environment variables from backend .env
env_path = Path(__file__).resolve().parent.parent.parent / "python_backend" / ".env"
load_dotenv(dotenv_path=env_path)

BACKEND_URL = os.getenv("GRAPH_TRACE_BACKEND_URL", "http://localhost:8011")

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
            AgentCapability(name="generate_graph_layouts", description="Generate optimal graph layouts"),
            AgentCapability(name="create_chart_configurations", description="Create chart configurations"),
            AgentCapability(name="visualize_schema_clusters", description="Visualize schema cluster groupings from corpus analysis"),
        ]

    async def process_task(self, task: AgentTaskRequest) -> Dict[str, Any]:
        payload = task.payload
        chart_type: str = payload.get("chart_type", "graph")
        layout: str = payload.get("layout", "force")
        source_id: str = payload.get("source_id", "")
        nodes: List[Dict[str, Any]] = payload.get("nodes", [])
        edges: List[Dict[str, Any]] = payload.get("edges", [])

        # Fetch graph data from backend when source_id provided and no inline data
        if source_id and not (nodes or edges):
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    resp = await client.get(
                        f"{BACKEND_URL}/api/graph/nodes",
                        params={"source_id": source_id, "limit": 200},
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        nodes = data.get("nodes", [])
                        edges = data.get("edges", data.get("relationships", []))
            except Exception:
                pass

        # Build chart config from whatever data we have
        chart_config: Dict[str, Any] = {
            "type": chart_type if not (nodes or edges) else "graph",
            "layout": layout,
            "nodes": [
                {
                    "id": str(n.get("id", i)),
                    "label": n.get("label") or n.get("name") or str(n.get("id", i)),
                    "group": (n.get("labels") or [None])[0],
                }
                for i, n in enumerate(nodes[:500])
            ],
            "edges": [
                {
                    "from": e.get("from") or e.get("source") or e.get("startNodeId"),
                    "to": e.get("to") or e.get("target") or e.get("endNodeId"),
                    "label": e.get("type") or e.get("label", ""),
                }
                for e in edges[:1000]
            ],
        }

        return {
            "status": "completed",
            "task_id": task.task_id,
            "chart_config": chart_config,
            "node_count": len(chart_config["nodes"]),
            "edge_count": len(chart_config["edges"]),
            "timestamp": datetime.now().isoformat(),
        }

agent = VisualizationAgent()
app = agent.app

if __name__ == "__main__":
    agent.start()
