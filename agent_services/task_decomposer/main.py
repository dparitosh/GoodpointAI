import sys
import os
import logging
from typing import Dict, Any, List
import uuid

# Add parent dir to path so we can import base module
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from agent_services.base.agent_service import AgentService
from agent_services.base.models import AgentTaskRequest, AgentType, AgentCapability

logger = logging.getLogger("task_decomposer")

class TaskDecomposerAgent(AgentService):
    def __init__(self):
        super().__init__(
            agent_type=AgentType.TASK_DECOMPOSER,
            agent_name="Task Decomposer Agent",
            port=8027
        )

    async def initialize(self):
        logger.info(f"Initialized {self.agent_name} logic.")

    def get_capabilities(self) -> List[AgentCapability]:
        return [
            AgentCapability(name="decompose_goal", description="Decompose high-level goals into dependency-ordered subtasks"),
            AgentCapability(name="build_task_dag", description="Produce subtask DAG with capability requirements"),
        ]

    async def process_task(self, request: AgentTaskRequest) -> Dict[str, Any]:
        logger.info("Task Decomposer received task %s of type %s", request.task_id, request.task_type)
        
        goal = request.payload.get("goal", "")
        if not goal:
            return {
                "decomposition_status": "failed",
                "error": "No goal provided for decomposition",
                "subtasks": [],
            }
            
        # Example Cognitive Graph Mapping
        # In a fully LLM-integrated environment, wed pass the `goal` to OpenAI to emit this JSON DAG
        # Here we dynamically simulate decomposition based on keywords
        subtasks: List[Dict[str, Any]] = []
        
        goal_lower = goal.lower()
        if "migrate" in goal_lower and "schema" in goal_lower:
            # 1. Discover the schema files
            discovery_id = str(uuid.uuid4())
            subtasks.append({
                "id": f"subtask_{discovery_id}",
                "parent_task_id": request.task_id,
                "type": "data_discovery",
                "required_capabilities": ["discover_files", "profile_files"],
                "payload": {"source": request.payload.get("source", "unknown"), "operation": "schema_discovery"},
                "dependencies": [],
                "priority": 5
            })
            
            # 2. Quality Scan mapping (depends on discovery)
            dq_id = str(uuid.uuid4())
            subtasks.append({
                "id": f"subtask_{dq_id}",
                "parent_task_id": request.task_id,
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
                "parent_task_id": request.task_id,
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
                "parent_task_id": request.task_id,
                "type": "data_analysis",
                "required_capabilities": ["generate_insights"],
                "payload": {"topic": goal},
                "dependencies": [],
                "priority": 5
            })

        logger.info("Decomposed '%s' into %d subtasks with strict dependency chains.", goal, len(subtasks))

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

