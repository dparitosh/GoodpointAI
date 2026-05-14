"""
Workflow Context Models - Pydantic models for workflow state in conversations

Enables chat endpoints to access workflow execution state and pass it to agents
for step-aware, context-conscious recommendations and processing.
"""

from pydantic import BaseModel, Field
from typing import Optional, Dict, List, Any
from enum import Enum
from datetime import datetime


class WorkflowStage(str, Enum):
    """Workflow execution stage"""
    IDLE = "idle"
    EXTRACTING = "extracting"
    TRANSFORMING = "transforming"
    VALIDATING = "validating"
    LOADING = "loading"
    FINALIZING = "finalizing"


class WorkflowStatus(str, Enum):
    """Workflow execution status"""
    DRAFT = "draft"
    CONFIGURED = "configured"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class WorkflowSourceInfo(BaseModel):
    """Source system information"""
    source_id: str
    source_name: str
    source_type: str  # teamcenter, windchill, catia, nx, creo
    
    class Config:
        example = {
            "source_id": "plm_001",
            "source_name": "Teamcenter Production",
            "source_type": "teamcenter"
        }


class WorkflowTargetInfo(BaseModel):
    """Target system information"""
    target_id: str
    target_name: str
    target_type: str  # neo4j, cloud_plm, opensearch, warehouse
    
    class Config:
        example = {
            "target_id": "neo4j_prod",
            "target_name": "Production Neo4j",
            "target_type": "neo4j"
        }


class WorkflowStats(BaseModel):
    """Workflow execution statistics"""
    total_records: int = 0
    processed_records: int = 0
    failed_records: int = 0
    quality_score: Optional[float] = None
    progress_percentage: float = 0.0
    
    class Config:
        example = {
            "total_records": 50000,
            "processed_records": 35000,
            "failed_records": 500,
            "quality_score": 92.5,
            "progress_percentage": 70.0
        }


class WorkflowContext(BaseModel):
    """
    Workflow execution context for chat processing.
    
    Provides agents with workflow state so they can:
    - Make step-aware recommendations
    - Reference previous migration runs
    - Suggest next steps based on current stage
    - Understand data volume and quality baseline
    """
    workflow_id: str = Field(..., description="Unique workflow identifier")
    workflow_name: str = Field(..., description="Human-readable workflow name")
    
    # Status and progress
    status: WorkflowStatus = Field(default=WorkflowStatus.CONFIGURED)
    current_stage: WorkflowStage = Field(default=WorkflowStage.IDLE)
    progress_percentage: float = Field(default=0.0, ge=0.0, le=100.0)
    
    # Source and target
    source: WorkflowSourceInfo
    target: WorkflowTargetInfo
    
    # Execution statistics
    stats: WorkflowStats = Field(default_factory=WorkflowStats)
    
    # Timing
    started_at: Optional[datetime] = None
    estimated_completion_at: Optional[datetime] = None
    
    # Additional context
    description: Optional[str] = None
    ai_agents_enabled: List[str] = Field(default_factory=list)
    error_message: Optional[str] = None  # Set if status is FAILED
    
    class Config:
        example = {
            "workflow_id": "workflow_abc123",
            "workflow_name": "Teamcenter to Neo4j Migration",
            "status": "running",
            "current_stage": "transforming",
            "progress_percentage": 65.0,
            "source": {
                "source_id": "plm_001",
                "source_name": "Teamcenter Production",
                "source_type": "teamcenter"
            },
            "target": {
                "target_id": "neo4j_prod",
                "target_name": "Production Neo4j",
                "target_type": "neo4j"
            },
            "stats": {
                "total_records": 50000,
                "processed_records": 32500,
                "failed_records": 250,
                "quality_score": 90.5,
                "progress_percentage": 65.0
            },
            "started_at": "2026-05-14T09:00:00Z",
            "estimated_completion_at": "2026-05-14T14:00:00Z",
            "ai_agents_enabled": ["data_discovery", "quality_monitor"]
        }


class EnhancedChatRequest(BaseModel):
    """
    Enhanced chat request with full workflow context support.
    
    Allows clients to send chat messages with workflow state information
    so agents can provide context-aware responses.
    """
    message: str = Field(..., description="User message")
    
    # Session and conversation
    session_id: Optional[str] = Field(None, description="Session identifier for conversation grouping")
    intent: Optional[str] = Field(None, description="Detected or specified intent (query, help, action, etc.)")
    
    # Workflow context
    workflow_context: Optional[WorkflowContext] = Field(
        None,
        description="Current workflow execution state and metadata"
    )
    
    # Generic context (backward compatible)
    context: Dict[str, Any] = Field(default_factory=dict, description="Generic context dict")
    
    # UI context (backward compatible)
    ui_context: Dict[str, Any] = Field(default_factory=dict, description="UI-provided context")
    
    class Config:
        example = {
            "message": "What should I do next with the validation failures?",
            "session_id": "session_abc123",
            "intent": "guidance",
            "workflow_context": {
                "workflow_id": "workflow_xyz",
                "workflow_name": "PLM Migration",
                "status": "running",
                "current_stage": "validating",
                "progress_percentage": 75.0,
                "source": {
                    "source_id": "teamcenter",
                    "source_name": "TC Prod",
                    "source_type": "teamcenter"
                },
                "target": {
                    "target_id": "neo4j",
                    "target_name": "Graph DB",
                    "target_type": "neo4j"
                },
                "stats": {
                    "total_records": 50000,
                    "processed_records": 37500,
                    "failed_records": 500,
                    "quality_score": 85.0,
                    "progress_percentage": 75.0
                }
            }
        }


class WorkflowContextResponse(BaseModel):
    """Response model for retrieving workflow context"""
    workflow_id: str
    workflow_name: str
    status: str
    current_stage: str
    progress_percentage: float
    source_id: str
    source_name: str
    target_id: str
    target_name: str
    total_records: int
    processed_records: int
    quality_score: Optional[float]
    started_at: Optional[str]
    estimated_completion_at: Optional[str]
    ai_agents_enabled: List[str] = []


class WorkflowContextList(BaseModel):
    """Response model for listing workflow contexts"""
    workflows: List[WorkflowContextResponse]
    total: int
    
    class Config:
        example = {
            "workflows": [
                {
                    "workflow_id": "workflow_1",
                    "workflow_name": "Teamcenter Migration",
                    "status": "running",
                    "current_stage": "validating",
                    "progress_percentage": 75.0,
                    "source_id": "teamcenter",
                    "source_name": "TC Prod",
                    "target_id": "neo4j",
                    "target_name": "Graph DB",
                    "total_records": 50000,
                    "processed_records": 37500,
                    "quality_score": 85.0,
                    "started_at": "2026-05-14T09:00:00Z",
                    "estimated_completion_at": "2026-05-14T14:00:00Z",
                    "ai_agents_enabled": ["data_discovery", "quality_monitor"]
                }
            ],
            "total": 1
        }
