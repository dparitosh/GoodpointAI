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

class ChatCoordinatorAgent(AgentService):
    def __init__(self):
        super().__init__(
            agent_type=AgentType.CHAT_COORDINATOR,
            agent_name="Chat Coordination Agent",
            port=8025
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
            AgentCapability(name="process_natural_language", description="Process natural language"),
            AgentCapability(name="coordinate_agent_responses", description="Coordinate agent responses"),
            AgentCapability(name="manage_conversation_context", description="Manage conversation context")
        ]

    async def process_task(self, task: AgentTaskRequest):
        # Structured Chat Logic
        message = task.payload.get("message", "").lower()
        context = task.context or {}
        
        # 1. Simple Keyword Intent Classification (Placeholder for LLM)
        intent = "general_chat"
        if "analyze" in message or "pattern" in message or "trend" in message:
            intent = "data_analysis_request"
        elif "etl" in message or "pipeline" in message or "load" in message:
            intent = "etl_request"
        elif "chart" in message or "plot" in message or "visualize" in message:
            intent = "visualization_request"
            
        # 2. Formulate Response based on Intent
        response_text = ""
        collaboration_needed = False
        
        if intent == "data_analysis_request":
            response_text = "I understand you want to analyze data. I will coordinate with the Data Analyst agent."
            collaboration_needed = True
        elif intent == "etl_request":
            response_text = "I'll ask the ETL Orchestrator to check the pipelines."
            collaboration_needed = True
        elif intent == "visualization_request":
            response_text = "I can have the Visualization Agent prepare a chart for you."
            collaboration_needed = True
        else:
            response_text = f"I received your message: '{message}'. How can I help you with your graph data today?"

        return {
            "status": "Chat processed", 
            "task_id": task.task_id,
            "primaryResponse": response_text,
            "intent": intent,
            "collaborationNeeded": collaboration_needed,
            "followupQuestions": ["Would you like to see more details?"],
            "timestamp": datetime.now().isoformat()
        }

if __name__ == "__main__":
    agent = ChatCoordinatorAgent()
    agent.start()
