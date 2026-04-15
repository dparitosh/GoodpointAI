import sys
import os
import logging
from typing import Dict, Any, List
from pathlib import Path
import uuid

# Add repo root to path to allow importing agent_services package
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

from agent_services.base.agent_service import AgentService
from agent_services.base.models import AgentCapability, AgentTaskRequest, AgentType

logger = logging.getLogger("task_decomposer")

class TaskDecomposerAgent(AgentService):
    def __init__(self):
        super().__init__(
            agent_type=AgentType.TASK_DECOMPOSER,
            agent_name="Task Decomposer Agent",
            port=8027
        )

    def get_capabilities(self) -> List[AgentCapability]:
        return [
            AgentCapability(
                name="decompose_task",
                description="Breaks down complex natural language requests into an executable DAG of subtasks",
            )
        ]

    async def process_task(self, task: AgentTaskRequest) -> Dict[str, Any]:
        logger.info(f"Task Decomposer received task {task.task_id} of type {task.task_type}")
        
        goal = task.payload.get("goal", "")
        if not goal:
            return {
                "decomposition_status": "failed",
                "error": "No goal provided for decomposition",
            }
            
        # Example Cognitive Graph Mapping
        # In a fully LLM-integrated environment, wed pass the `goal` to OpenAI to emit this JSON DAG
        # Here we dynamically simulate decomposition based on keywords
        subtasks = []
        
        goal_lower = goal.lower()
        if "migrate" in goal_lower and "schema" in goal_lower:
            # 1. Discover the schema files
            discovery_id = str(uuid.uuid4())
            subtasks.append({
                "id": f"subtask_{discovery_id}",
                "parent_task_id": task.task_id,
                "type": "data_discovery",
                "required_capabilities": ["discover_files", "profile_files"],
                "payload": {"source": task.payload.get("source", "unknown"), "operation": "schema_discovery"},
                "dependencies": [],
                "priority": 5
            })
            
            # 2. Quality Scan mapping (depends on discovery)
            dq_id = str(uuid.uuid4())
            subtasks.append({
                "id": f"subtask_{dq_id}",
                "parent_task_id": task.task_id,
                "type": "data_quality_scan",
                "required_capabilities": ["scan_folder_quality"],
                "payload": {"scan_type": "null_constraints", "report": True},
                "dependencies": [f"subtask_{discovery_id}"],
                "priority": 4
            })
            
            # 3. Final ETL pipeline build (depends on quality check)
            etl_id = str(uuid.uuid4())
            subtasks.append({
                "id": f"subtask_{etl_id}",
                "parent_task_id": task.task_id,
                "type": "pipeline_orchestration",
                "required_capabilities": ["manage_data_pipelines"],
                "payload": {"action": "build_migration", "strict": True},
                "dependencies": [f"subtask_{dq_id}"],
                "priority": 3
            })
        else:
            # Default single-branch analysis
            analysis_id = str(uuid.uuid4())
            subtasks.append({
                "id": f"subtask_{analysis_id}",
                "parent_task_id": task.task_id,
                "type": "data_analysis",
                "required_capabilities": ["generate_insights"],
                "payload": {"topic": goal},
                "dependencies": [],
                "priority": 5
            })

        logger.info(f"Decomposed '{goal}' into {len(subtasks)} subtasks with strict dependency chains.")

        return {
            "decomposition_status": "success",
            "original_goal": goal,
            "subtasks": subtasks,
        }

# Create singleton and export app
agent = TaskDecomposerAgent()
app = agent.app

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8027)

