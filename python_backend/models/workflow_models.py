"""
Workflow Instance Models for PLM Data Migration AI Factory

Each workflow instance represents a unique source-target migration pipeline
with its own configuration, state, and execution history.
"""

from sqlalchemy import Column, String, Integer, DateTime, JSON, Enum as SQLEnum, Text, Float, Boolean
from sqlalchemy.sql import func
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, validator

from core.database import Base


class WorkflowStatus(str, Enum):
    """Workflow execution status"""
    DRAFT = "draft"
    CONFIGURED = "configured"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class WorkflowStage(str, Enum):
    """Current stage in the workflow pipeline"""
    IDLE = "idle"
    EXTRACTING = "extracting"
    TRANSFORMING = "transforming"
    VALIDATING = "validating"
    LOADING = "loading"
    FINALIZING = "finalizing"


# SQLAlchemy ORM Model
class WorkflowInstance(Base):
    """
    Database model for workflow instances.
    Each record represents a unique source→target migration pipeline.
    """
    __tablename__ = "workflow_instances"

    # Primary identification
    id = Column(String(100), primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    
    # Source configuration
    source_id = Column(String(100), nullable=False, index=True)
    source_name = Column(String(255), nullable=False)
    source_type = Column(String(50), nullable=False)  # teamcenter, windchill, catia, etc.
    source_config = Column(JSON, nullable=False)
    
    # Target configuration
    target_id = Column(String(100), nullable=False, index=True)
    target_name = Column(String(255), nullable=False)
    target_type = Column(String(50), nullable=False)  # neo4j, cloud_plm, opensearch, etc.
    target_config = Column(JSON, nullable=False)
    
    # Workflow configuration
    workflow_config = Column(JSON, nullable=False)  # nodes, edges, ai_agents, stages
    ai_agents_enabled = Column(JSON, nullable=True)  # list of enabled agent IDs
    
    # Execution state
    status = Column(SQLEnum(WorkflowStatus), default=WorkflowStatus.DRAFT, nullable=False, index=True)
    current_stage = Column(SQLEnum(WorkflowStage), default=WorkflowStage.IDLE, nullable=True)
    progress_percentage = Column(Float, default=0.0)
    
    # Statistics
    total_records = Column(Integer, default=0)
    processed_records = Column(Integer, default=0)
    failed_records = Column(Integer, default=0)
    quality_score = Column(Float, nullable=True)
    
    # Execution metadata
    execution_metadata = Column(JSON, nullable=True)  # runtime info, errors, warnings
    last_execution_id = Column(String(100), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    
    # User tracking
    created_by = Column(String(100), nullable=True)
    updated_by = Column(String(100), nullable=True)
    
    # Schedule configuration
    schedule_enabled = Column(Boolean, default=False)
    schedule_cron = Column(String(100), nullable=True)
    next_run_at = Column(DateTime(timezone=True), nullable=True)


# Pydantic Models for API
class WorkflowSourceConfig(BaseModel):
    """Source system configuration"""
    id: str
    name: str
    type: str  # teamcenter, windchill, catia, nx, creo
    connection_details: Dict[str, Any]
    extraction_config: Dict[str, Any] = {}


class WorkflowTargetConfig(BaseModel):
    """Target system configuration"""
    id: str
    name: str
    type: str  # neo4j, cloud_plm, opensearch, warehouse, datalake
    connection_details: Dict[str, Any]
    load_config: Dict[str, Any] = {}


class WorkflowGraphConfig(BaseModel):
    """Workflow graph structure (nodes and edges)"""
    nodes: List[Dict[str, Any]]
    edges: List[Dict[str, Any]]
    ai_agents: List[str] = []  # Enabled AI agent IDs


class WorkflowInstanceCreate(BaseModel):
    """Request model for creating a new workflow instance"""
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    source: WorkflowSourceConfig
    target: WorkflowTargetConfig
    workflow_config: WorkflowGraphConfig
    ai_agents_enabled: List[str] = []
    schedule_enabled: bool = False
    schedule_cron: Optional[str] = None
    created_by: Optional[str] = "system"
    
    @validator('name')
    def validate_name(cls, v):
        if not v or not v.strip():
            raise ValueError('Workflow name cannot be empty')
        return v.strip()
    
    @validator('source')
    def validate_source(cls, v):
        if not v.id or len(v.id) < 3:
            raise ValueError('Source system ID must be at least 3 characters')
        if not v.type:
            raise ValueError('Source system type is required')
        return v
    
    @validator('target')
    def validate_target(cls, v):
        if not v.id or len(v.id) < 3:
            raise ValueError('Target system ID must be at least 3 characters')
        if not v.type:
            raise ValueError('Target system type is required')
        return v


class WorkflowInstanceUpdate(BaseModel):
    """Request model for updating a workflow instance"""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    source: Optional[WorkflowSourceConfig] = None
    target: Optional[WorkflowTargetConfig] = None
    workflow_config: Optional[WorkflowGraphConfig] = None
    ai_agents_enabled: Optional[List[str]] = None
    schedule_enabled: Optional[bool] = None
    schedule_cron: Optional[str] = None
    updated_by: Optional[str] = "system"


class WorkflowInstanceResponse(BaseModel):
    """Response model for workflow instance"""
    id: str
    name: str
    description: Optional[str]
    source_id: str
    source_name: str
    source_type: str
    target_id: str
    target_name: str
    target_type: str
    status: WorkflowStatus
    current_stage: Optional[WorkflowStage]
    progress_percentage: float
    total_records: int
    processed_records: int
    failed_records: int
    quality_score: Optional[float]
    created_at: datetime
    updated_at: Optional[datetime]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    created_by: Optional[str]
    schedule_enabled: bool
    schedule_cron: Optional[str]
    next_run_at: Optional[datetime]
    
    class Config:
        from_attributes = True


class WorkflowInstanceDetail(WorkflowInstanceResponse):
    """Detailed response including full configuration"""
    source_config: Dict[str, Any]
    target_config: Dict[str, Any]
    workflow_config: Dict[str, Any]
    ai_agents_enabled: Optional[List[str]]
    execution_metadata: Optional[Dict[str, Any]]
    last_execution_id: Optional[str]


class WorkflowExecutionRequest(BaseModel):
    """Request to start/stop workflow execution"""
    action: str  # start, pause, resume, stop, cancel
    execution_params: Dict[str, Any] = {}


class WorkflowExecutionResponse(BaseModel):
    """Response for workflow execution action"""
    workflow_id: str
    execution_id: str
    status: str
    message: str
    started_at: Optional[datetime]


class WorkflowStatistics(BaseModel):
    """Aggregated statistics for workflow instances"""
    total_workflows: int
    by_status: Dict[str, int]
    by_source_type: Dict[str, int]
    by_target_type: Dict[str, int]
    total_records_processed: int
    average_quality_score: Optional[float]
    active_executions: int
