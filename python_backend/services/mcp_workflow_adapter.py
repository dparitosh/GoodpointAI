"""
MCP Workflow Adapter Service

Converts MCP TaskDecomposer agent output (decomposed subtasks) into
executable WorkflowDefinition and WorkflowStep records.

Maps MCP subtask dependencies and capabilities to backend step types.
"""

import logging
import uuid
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from models.workflow_models import (
    WorkflowDefinition, WorkflowStep, WorkflowStepType, MigrationStage
)

logger = logging.getLogger(__name__)


class MCPCapabilityToStepTypeMapper:
    """Maps MCP required_capabilities to backend WorkflowStepType"""
    
    CAPABILITY_MAPPING = {
        "discover_files": WorkflowStepType.DISCOVERY,
        "profile_files": WorkflowStepType.PROFILING,
        "scan_folder_quality": WorkflowStepType.PROFILING,
        "manage_data_pipelines": WorkflowStepType.ETL_EXECUTION,
        "validate_data": WorkflowStepType.VALIDATION,
        "transform_schema": WorkflowStepType.SCHEMA_MAPPING,
        "load_data": WorkflowStepType.ETL_EXECUTION,
        "generate_insights": WorkflowStepType.PYTHON,
    }
    
    STAGE_MAPPING = {
        WorkflowStepType.DISCOVERY: MigrationStage.DISCOVERING,
        WorkflowStepType.PROFILING: MigrationStage.PROFILING,
        WorkflowStepType.SCHEMA_MAPPING: MigrationStage.SCHEMA_MAPPING,
        WorkflowStepType.ETL_EXECUTION: MigrationStage.DATA_MIGRATION,
        WorkflowStepType.VALIDATION: MigrationStage.VALIDATION,
        WorkflowStepType.SQL: None,
        WorkflowStepType.PYTHON: None,
        WorkflowStepType.API: None,
    }
    
    @classmethod
    def get_step_type_from_capabilities(
        cls, 
        capabilities: List[str]
    ) -> WorkflowStepType:
        """
        Map MCP required_capabilities to WorkflowStepType.
        Prioritizes first matching capability.
        
        Args:
            capabilities: List of required capabilities from MCP subtask
            
        Returns:
            WorkflowStepType (defaults to PYTHON if no match)
        """
        for cap in capabilities:
            if cap in cls.CAPABILITY_MAPPING:
                return cls.CAPABILITY_MAPPING[cap]
        return WorkflowStepType.PYTHON
    
    @classmethod
    def get_stage_from_step_type(
        cls, 
        step_type: WorkflowStepType
    ) -> Optional[str]:
        """Get MigrationStage for a given step type"""
        stage = cls.STAGE_MAPPING.get(step_type)
        return stage.value if stage else None


class MCPWorkflowAdapter:
    """Adapter to convert MCP TaskDecomposer output to WorkflowDefinition"""
    
    def __init__(self, db_session: Session):
        """
        Initialize adapter.
        
        Args:
            db_session: SQLAlchemy session for DB operations
        """
        self.db = db_session
        self.mapper = MCPCapabilityToStepTypeMapper()
    
    async def create_workflow_from_mcp_decomposition(
        self,
        mcp_response: Dict[str, Any],
        source_id: str,
        target_id: str,
        workflow_name: Optional[str] = None,
    ) -> WorkflowDefinition:
        """
        Convert MCP TaskDecomposer response to WorkflowDefinition.
        
        Args:
            mcp_response: Response from TaskDecomposerAgent.execute_task()
                Expected structure:
                {
                    "decomposition_status": "success",
                    "original_goal": "...",
                    "subtasks": [
                        {
                            "id": "subtask_uuid",
                            "type": "discovery|quality_scan|pipeline_orchestration",
                            "required_capabilities": ["discover_files", "profile_files"],
                            "payload": {"source": "...", "operation": "..."},
                            "dependencies": ["subtask_uuid1", "subtask_uuid2"],
                            "priority": 5
                        },
                        ...
                    ]
                }
            source_id: Source system ID
            target_id: Target system ID
            workflow_name: Optional workflow name (defaults to goal-based name)
            
        Returns:
            WorkflowDefinition created and saved to DB
            
        Raises:
            ValueError: If decomposition failed or structure invalid
        """
        # Validate input
        if mcp_response.get("decomposition_status") != "success":
            raise ValueError(f"MCP decomposition failed: {mcp_response.get('decomposition_status')}")
        
        subtasks = mcp_response.get("subtasks", [])
        if not subtasks:
            raise ValueError("MCP decomposition returned no subtasks")
        
        # Create workflow
        workflow_id = f"wf_{uuid.uuid4().hex[:12]}"
        original_goal = mcp_response.get("original_goal", "MCP-generated workflow")
        workflow_name = workflow_name or f"Workflow: {original_goal}"
        
        workflow = WorkflowDefinition(
            id=workflow_id,
            name=workflow_name,
            description=f"Auto-generated from MCP decomposition goal: {original_goal}",
            source_id=source_id,
            target_id=target_id,
            definition_config={
                "original_goal": original_goal,
                "mcp_decomposition_response": mcp_response,
                "created_from_mcp": True,
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
            mcp_decomposition_id=mcp_response.get("task_id"),
            created_by="mcp_adapter",
        )
        self.db.add(workflow)
        
        # Create steps from subtasks
        subtask_id_to_step_id = {}  # Map MCP subtask IDs to WorkflowStep IDs
        steps_to_add = []
        
        for idx, subtask in enumerate(subtasks):
            step_id = f"step_{uuid.uuid4().hex[:12]}"
            subtask_id_to_step_id[subtask["id"]] = step_id
            
            # Determine step type from capabilities
            capabilities = subtask.get("required_capabilities", [])
            step_type = self.mapper.get_step_type_from_capabilities(capabilities)
            stage = self.mapper.get_stage_from_step_type(step_type)
            
            # Build step expression from payload
            expression = self._build_step_expression(
                subtask_type=subtask.get("type"),
                capabilities=capabilities,
                payload=subtask.get("payload", {})
            )
            
            # Create step record
            step = WorkflowStep(
                id=step_id,
                workflow_id=workflow_id,
                name=subtask.get("id", f"step_{idx}"),
                description=f"MCP subtask: {subtask.get('type')}",
                step_type=step_type.value,
                stage=stage,
                expression=expression,
                expression_language="python",  # Default for MCP-generated steps
                parameters=subtask.get("payload", {}),
                depends_on=[],  # Will update after mapping
                sequence_order=subtask.get("priority", 0),
                retries=1,
                timeout_seconds=3600,
                allow_failure=False,
            )
            steps_to_add.append(step)
        
        # Update dependencies (map MCP subtask IDs to WorkflowStep IDs)
        for step in steps_to_add:
            mcp_subtask = next(
                (st for st in subtasks if st["id"] == step.name),
                None
            )
            if mcp_subtask:
                step.depends_on = [
                    subtask_id_to_step_id[dep_id]
                    for dep_id in mcp_subtask.get("dependencies", [])
                    if dep_id in subtask_id_to_step_id
                ]
        
        # Persist all steps
        for step in steps_to_add:
            self.db.add(step)
        
        # Flush to get all IDs
        self.db.flush()
        
        logger.info(
            f"Created workflow {workflow_id} from MCP decomposition "
            f"with {len(steps_to_add)} steps"
        )
        
        return workflow
    
    def _build_step_expression(
        self,
        subtask_type: str,
        capabilities: List[str],
        payload: Dict[str, Any]
    ) -> str:
        """
        Build a step expression from MCP subtask metadata.
        
        Args:
            subtask_type: Type of subtask (e.g., "data_discovery", "data_quality_scan")
            capabilities: Required capabilities
            payload: Subtask payload
            
        Returns:
            Expression string (pseudo-code or SQL template)
        """
        if "discover" in subtask_type.lower():
            source = payload.get("source", "unknown")
            return f"DISCOVER SOURCE: {source}"
        
        elif "quality" in subtask_type.lower():
            scan_type = payload.get("scan_type", "comprehensive")
            return f"SCAN DATA QUALITY: {scan_type}"
        
        elif "pipeline" in subtask_type.lower():
            action = payload.get("action", "build")
            return f"EXECUTE ETL PIPELINE: {action}"
        
        elif "analysis" in subtask_type.lower():
            topic = payload.get("topic", "general")
            return f"ANALYZE: {topic}"
        
        else:
            # Generic expression - could be enhanced with LLM
            return f"EXECUTE SUBTASK: {subtask_type}"
    
    async def update_execution_from_step_results(
        self,
        workflow_execution_id: str,
        step_execution_results: Dict[str, Any]
    ) -> None:
        """
        Update workflow execution with results from step executions.
        Useful for aggregating step results back to workflow level.
        
        Args:
            workflow_execution_id: ID of workflow execution
            step_execution_results: Dict mapping step_id → execution result
        """
        # This would be called by WorkflowExecutorService after execution
        logger.info(
            f"Updated workflow execution {workflow_execution_id} "
            f"with {len(step_execution_results)} step results"
        )


class MCPIntegrationHelper:
    """Helper functions for MCP integration"""
    
    @staticmethod
    def validate_mcp_response(response: Dict[str, Any]) -> bool:
        """Validate MCP TaskDecomposer response structure"""
        required_keys = {"decomposition_status", "subtasks"}
        if not required_keys.issubset(response.keys()):
            logger.error(f"Invalid MCP response structure: missing keys {required_keys - set(response.keys())}")
            return False
        
        if response["decomposition_status"] != "success":
            return False
        
        for subtask in response.get("subtasks", []):
            subtask_required = {"id", "type", "required_capabilities", "payload", "dependencies", "priority"}
            if not subtask_required.issubset(subtask.keys()):
                logger.error(f"Invalid subtask structure in MCP response")
                return False
        
        return True
    
    @staticmethod
    def estimate_workflow_complexity(subtasks: List[Dict[str, Any]]) -> str:
        """
        Estimate workflow complexity based on number of subtasks and dependencies.
        
        Args:
            subtasks: List of MCP subtasks
            
        Returns:
            Complexity level: "simple", "medium", "complex"
        """
        num_tasks = len(subtasks)
        avg_dependencies = sum(len(st.get("dependencies", [])) for st in subtasks) / max(num_tasks, 1)
        
        if num_tasks <= 3 and avg_dependencies <= 1:
            return "simple"
        elif num_tasks <= 10 and avg_dependencies <= 2:
            return "medium"
        else:
            return "complex"
