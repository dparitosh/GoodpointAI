"""
Workflow Context Repository - Data access layer for workflow state

Provides methods to retrieve workflow execution state for use in chat context
and agent decision-making.
"""

from typing import Optional, List
from datetime import datetime
import logging

from sqlalchemy.orm import Session
from sqlalchemy import desc

from models.workflow_models import WorkflowInstance, WorkflowStatus, WorkflowStage
from models.workflow_context_models import (
    WorkflowContext,
    WorkflowContextResponse,
    WorkflowSourceInfo,
    WorkflowTargetInfo,
    WorkflowStats,
)
from core.db_session import SessionLocal

logger = logging.getLogger(__name__)


class WorkflowContextRepository:
    """Repository for retrieving workflow context information"""
    
    def __init__(self, session: Optional[Session] = None):
        """Initialize repository with optional session"""
        self.session = session or SessionLocal()
    
    def get_context(self, workflow_id: str) -> Optional[WorkflowContext]:
        """
        Retrieve complete workflow context by workflow ID
        
        Args:
            workflow_id: Workflow identifier
            
        Returns:
            WorkflowContext or None if not found
        """
        try:
            workflow = self.session.query(WorkflowInstance).filter(
                WorkflowInstance.id == workflow_id
            ).first()
            
            if not workflow:
                return None
            
            return self._orm_to_context(workflow)
            
        except Exception as e:
            logger.error(f"Error retrieving workflow context {workflow_id}: {str(e)}")
            raise
    
    def get_context_by_source(self, source_id: str) -> Optional[WorkflowContext]:
        """
        Retrieve most recent workflow context for a source system
        
        Args:
            source_id: Source system identifier
            
        Returns:
            Most recent WorkflowContext or None if not found
        """
        try:
            workflow = self.session.query(WorkflowInstance).filter(
                WorkflowInstance.source_id == source_id
            ).order_by(desc(WorkflowInstance.created_at)).first()
            
            if not workflow:
                return None
            
            return self._orm_to_context(workflow)
            
        except Exception as e:
            logger.error(f"Error retrieving workflow context for source {source_id}: {str(e)}")
            raise
    
    def get_active_context(self, workflow_id: str) -> Optional[WorkflowContext]:
        """
        Retrieve workflow context if workflow is in active status
        (RUNNING, PAUSED, VALIDATING, LOADING)
        
        Args:
            workflow_id: Workflow identifier
            
        Returns:
            WorkflowContext if active, None otherwise
        """
        try:
            active_statuses = [
                WorkflowStatus.RUNNING,
                WorkflowStatus.PAUSED,
            ]
            
            workflow = self.session.query(WorkflowInstance).filter(
                WorkflowInstance.id == workflow_id,
                WorkflowInstance.status.in_([s.value for s in active_statuses])
            ).first()
            
            if not workflow:
                return None
            
            return self._orm_to_context(workflow)
            
        except Exception as e:
            logger.error(f"Error retrieving active workflow context {workflow_id}: {str(e)}")
            raise
    
    def list_active_contexts(self, skip: int = 0, limit: int = 10) -> List[WorkflowContext]:
        """
        Retrieve list of currently active workflows
        
        Args:
            skip: Number of records to skip
            limit: Maximum number to return
            
        Returns:
            List of WorkflowContext objects
        """
        try:
            active_statuses = [
                WorkflowStatus.RUNNING,
                WorkflowStatus.PAUSED,
            ]
            
            workflows = self.session.query(WorkflowInstance).filter(
                WorkflowInstance.status.in_([s.value for s in active_statuses])
            ).order_by(
                desc(WorkflowInstance.updated_at)
            ).offset(skip).limit(limit).all()
            
            return [self._orm_to_context(w) for w in workflows]
            
        except Exception as e:
            logger.error(f"Error listing active workflow contexts: {str(e)}")
            raise
    
    def get_stage_info(self, workflow_id: str) -> Optional[dict]:
        """
        Get brief stage and progress information
        
        Lightweight query for frequent updates in chat context
        
        Args:
            workflow_id: Workflow identifier
            
        Returns:
            Dict with stage, progress_percentage, status or None
        """
        try:
            workflow = self.session.query(WorkflowInstance).filter(
                WorkflowInstance.id == workflow_id
            ).first()
            
            if not workflow:
                return None
            
            return {
                "workflow_id": workflow.id,
                "status": workflow.status.value if workflow.status else None,
                "current_stage": workflow.current_stage.value if workflow.current_stage else None,
                "progress_percentage": workflow.progress_percentage,
                "total_records": workflow.total_records,
                "processed_records": workflow.processed_records,
                "quality_score": workflow.quality_score,
            }
            
        except Exception as e:
            logger.error(f"Error retrieving stage info for {workflow_id}: {str(e)}")
            raise
    
    def _orm_to_context(self, workflow: WorkflowInstance) -> WorkflowContext:
        """Convert WorkflowInstance ORM to WorkflowContext Pydantic model"""
        
        source = WorkflowSourceInfo(
            source_id=workflow.source_id,
            source_name=workflow.source_name,
            source_type=workflow.source_type,
        )
        
        target = WorkflowTargetInfo(
            target_id=workflow.target_id,
            target_name=workflow.target_name,
            target_type=workflow.target_type,
        )
        
        stats = WorkflowStats(
            total_records=workflow.total_records or 0,
            processed_records=workflow.processed_records or 0,
            failed_records=workflow.failed_records or 0,
            quality_score=workflow.quality_score,
            progress_percentage=workflow.progress_percentage or 0.0,
        )
        
        error_msg = None
        if workflow.status == WorkflowStatus.FAILED:
            # Try to extract error from execution_metadata
            if workflow.execution_metadata and isinstance(workflow.execution_metadata, dict):
                error_msg = workflow.execution_metadata.get("last_error")
        
        return WorkflowContext(
            workflow_id=workflow.id,
            workflow_name=workflow.name,
            status=WorkflowStatus(workflow.status.value) if workflow.status else WorkflowStatus.DRAFT,
            current_stage=WorkflowStage(workflow.current_stage.value) if workflow.current_stage else WorkflowStage.IDLE,
            progress_percentage=workflow.progress_percentage or 0.0,
            source=source,
            target=target,
            stats=stats,
            started_at=workflow.started_at,
            estimated_completion_at=workflow.next_run_at,  # Use next_run_at as estimated completion
            description=workflow.description,
            ai_agents_enabled=workflow.ai_agents_enabled or [],
            error_message=error_msg,
        )
    
    def close(self):
        """Close database session"""
        if self.session:
            self.session.close()
    
    def __enter__(self):
        """Context manager support"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()
