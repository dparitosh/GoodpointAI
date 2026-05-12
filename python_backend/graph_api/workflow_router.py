"""
Workflow Management API Router

Endpoints for:
- Creating workflows from MCP decomposition
- Managing workflow definitions and steps
- Executing workflows
- Tracking execution progress
- Stage-aware workflow monitoring
"""

import logging
import uuid
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from core.db_session import get_db
from models.workflow_models import (
    WorkflowDefinition, WorkflowExecution, WorkflowStep, WorkflowStepExecution,
    WorkflowDefinitionCreate, MigrationStage
)
from services.mcp_workflow_adapter import (
    MCPWorkflowAdapter, MCPIntegrationHelper
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/workflows",
    tags=["workflows"],
    responses={404: {"description": "Not found"}}
)


# ============================================================================
# MCP Integration Endpoints
# ============================================================================

@router.post("/from-mcp-decomposition", status_code=201)
async def create_workflow_from_mcp(
    mcp_response: Dict[str, Any],
    source_id: str,
    target_id: str,
    workflow_name: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Create a workflow from MCP TaskDecomposer output.
    
    Converts MCP subtasks (with dependencies and capabilities) into
    executable WorkflowDefinition with WorkflowStep records.
    
    Args:
        mcp_response: Response from TaskDecomposerAgent
        source_id: Source system ID
        target_id: Target system ID
        workflow_name: Optional workflow name
        
    Returns:
        Created workflow with all steps
        
    Example:
        POST /api/workflows/from-mcp-decomposition?source_id=src1&target_id=tgt1
        {
            "decomposition_status": "success",
            "original_goal": "migrate PLM schema",
            "subtasks": [
                {
                    "id": "subtask_xxx",
                    "type": "data_discovery",
                    "required_capabilities": ["discover_files"],
                    "payload": {"source": "..."},
                    "dependencies": [],
                    "priority": 5
                },
                ...
            ]
        }
    """
    try:
        # Validate MCP response structure
        if not MCPIntegrationHelper.validate_mcp_response(mcp_response):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid MCP decomposition response structure"
            )
        
        # Create adapter and convert
        adapter = MCPWorkflowAdapter(db)
        workflow = await adapter.create_workflow_from_mcp_decomposition(
            mcp_response=mcp_response,
            source_id=source_id,
            target_id=target_id,
            workflow_name=workflow_name
        )
        
        db.commit()
        
        return {
            "workflow_id": workflow.id,
            "workflow_name": workflow.name,
            "original_goal": mcp_response.get("original_goal"),
            "steps_created": len(mcp_response.get("subtasks", [])),
            "status": "created",
            "message": f"Workflow created from MCP decomposition with {len(mcp_response.get('subtasks', []))} steps"
        }
        
    except ValueError as e:
        logger.error(f"Invalid MCP decomposition: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error creating workflow from MCP: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create workflow from MCP decomposition"
        )


# NOTE: Must be POST — List[Dict[str,Any]] cannot be passed as a query parameter via GET.
@router.post("/mcp-complexity/{task_id}")
async def estimate_workflow_complexity(
    task_id: str,
    subtasks: List[Dict[str, Any]],
    db: Session = Depends(get_db)
):
    """
    Estimate workflow complexity from MCP subtasks.
    
    Returns:
        Complexity level ("simple", "medium", "complex")
    """
    complexity = MCPIntegrationHelper.estimate_workflow_complexity(subtasks)
    return {
        "task_id": task_id,
        "complexity": complexity,
        "num_subtasks": len(subtasks),
        "estimated_duration_minutes": {
            "simple": "5-10",
            "medium": "15-30",
            "complex": "45-120"
        }.get(complexity, "unknown")
    }


# ============================================================================
# Workflow Definition Endpoints
# ============================================================================

@router.post("/definitions", status_code=201)
async def create_workflow_definition(
    workflow_def: WorkflowDefinitionCreate,
    db: Session = Depends(get_db)
):
    """Create a new workflow definition"""
    try:
        workflow_id = f"wf_{uuid.uuid4().hex[:12]}"
        
        # Create workflow record
        workflow = WorkflowDefinition(
            id=workflow_id,
            name=workflow_def.name,
            description=workflow_def.description,
            source_id=workflow_def.source_id,
            target_id=workflow_def.target_id,
            definition_config={"steps": len(workflow_def.steps)},
            mcp_decomposition_id=workflow_def.mcp_decomposition_id,
            created_by="api"
        )
        db.add(workflow)
        db.flush()
        
        # Create step records
        for idx, step_def in enumerate(workflow_def.steps):
            step = WorkflowStep(
                id=f"step_{uuid.uuid4().hex[:12]}",
                workflow_id=workflow_id,
                name=step_def.name,
                description=step_def.description,
                step_type=step_def.step_type.value,
                stage=step_def.stage,
                expression=step_def.expression,
                expression_language=step_def.expression_language,
                parameters=step_def.parameters,
                depends_on=step_def.depends_on,
                sequence_order=step_def.sequence_order or idx,
                retries=step_def.retries,
                timeout_seconds=step_def.timeout_seconds,
                allow_failure=step_def.allow_failure
            )
            db.add(step)
        
        db.commit()
        
        return {
            "workflow_id": workflow_id,
            "name": workflow.name,
            "steps_count": len(workflow_def.steps),
            "status": "created"
        }
        
    except Exception as e:
        logger.error(f"Error creating workflow: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create workflow definition"
        )


@router.get("/definitions/{workflow_id}")
async def get_workflow_definition(
    workflow_id: str,
    db: Session = Depends(get_db)
):
    """Get workflow definition with all steps"""
    try:
        workflow = db.query(WorkflowDefinition).filter(
            WorkflowDefinition.id == workflow_id
        ).first()
        
        if not workflow:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Workflow {workflow_id} not found"
            )
        
        steps = db.query(WorkflowStep).filter(
            WorkflowStep.workflow_id == workflow_id
        ).order_by(WorkflowStep.sequence_order).all()
        
        return {
            "id": workflow.id,
            "name": workflow.name,
            "description": workflow.description,
            "source_id": workflow.source_id,
            "target_id": workflow.target_id,
            "steps": [
                {
                    "id": step.id,
                    "name": step.name,
                    "stage": step.stage,
                    "step_type": step.step_type,
                    "depends_on": step.depends_on,
                    "sequence_order": step.sequence_order
                }
                for step in steps
            ],
            "created_at": workflow.created_at.isoformat() if workflow.created_at else None
        }
        
    except Exception as e:
        logger.error(f"Error retrieving workflow: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve workflow"
        )


# ============================================================================
# Workflow Execution Endpoints
# ============================================================================

@router.post("/execute/{workflow_id}", status_code=202)
async def execute_workflow(
    workflow_id: str,
    execution_params: Optional[Dict[str, Any]] = None,
    db: Session = Depends(get_db)
):
    """
    Start execution of a workflow.
    
    Returns:
        Execution ID for monitoring progress
    """
    try:
        # Verify workflow exists
        workflow = db.query(WorkflowDefinition).filter(
            WorkflowDefinition.id == workflow_id
        ).first()
        
        if not workflow:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Workflow {workflow_id} not found"
            )
        
        # Create execution record
        execution_id = f"wexec_{uuid.uuid4().hex[:12]}"
        execution = WorkflowExecution(
            id=execution_id,
            workflow_id=workflow_id,
            status="pending",
            current_stage=MigrationStage.IDLE.value,
            progress_percentage=0.0,
            execution_context=execution_params or {},
            created_by="api"
        )
        db.add(execution)
        db.commit()
        
        # NOTE: Execution kickoff is intentionally deferred to background workers.
        # This endpoint creates the execution record for polling.
        
        return {
            "execution_id": execution_id,
            "workflow_id": workflow_id,
            "status": "pending",
            "progress_percentage": 0.0,
            "message": "Workflow execution started"
        }
        
    except Exception as e:
        logger.error(f"Error starting workflow execution: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to start workflow execution"
        )


@router.get("/executions/{execution_id}")
async def get_execution_status(
    execution_id: str,
    db: Session = Depends(get_db)
):
    """Get current status of a workflow execution"""
    try:
        execution = db.query(WorkflowExecution).filter(
            WorkflowExecution.id == execution_id
        ).first()
        
        if not execution:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Execution {execution_id} not found"
            )
        
        # Get step executions
        step_executions = db.query(WorkflowStepExecution).filter(
            WorkflowStepExecution.execution_id == execution_id
        ).all()
        
        return {
            "execution_id": execution.id,
            "workflow_id": execution.workflow_id,
            "status": execution.status,
            "current_stage": execution.current_stage,
            "progress_percentage": execution.progress_percentage,
            "total_steps": execution.total_steps,
            "completed_steps": execution.completed_steps,
            "failed_steps": execution.failed_steps,
            "started_at": execution.started_at.isoformat() if execution.started_at else None,
            "completed_at": execution.completed_at.isoformat() if execution.completed_at else None,
            "duration_ms": execution.duration_ms,
            "error_message": execution.error_message,
            "step_executions": [
                {
                    "step_id": se.step_id,
                    "status": se.status,
                    "completed_at": se.completed_at.isoformat() if se.completed_at else None,
                    "duration_ms": se.duration_ms,
                    "error": se.error_message
                }
                for se in step_executions
            ]
        }
        
    except Exception as e:
        logger.error(f"Error retrieving execution status: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve execution status"
        )


@router.get("/executions/{execution_id}/stages")
async def get_execution_stage_timeline(
    execution_id: str,
    db: Session = Depends(get_db)
):
    """
    Get stage transition timeline for execution.
    Shows which stages were completed and timing info.
    """
    try:
        execution = db.query(WorkflowExecution).filter(
            WorkflowExecution.id == execution_id
        ).first()
        
        if not execution:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Execution {execution_id} not found"
            )
        
        metadata = execution.execution_metadata or {}
        stage_transitions = metadata.get("stage_transitions", [])
        
        return {
            "execution_id": execution_id,
            "workflow_id": execution.workflow_id,
            "current_stage": execution.current_stage,
            "stage_timeline": stage_transitions,
            "total_duration_ms": execution.duration_ms
        }
        
    except Exception as e:
        logger.error(f"Error retrieving stage timeline: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve stage timeline"
        )
