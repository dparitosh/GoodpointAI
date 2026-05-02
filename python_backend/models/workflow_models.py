"""
Workflow Instance Models for PLM Data Migration AI Factory

Each workflow instance represents a unique source-target migration pipeline
with its own configuration, state, and execution history.
"""

from sqlalchemy import Column, String, Integer, DateTime, JSON, Enum as SQLEnum, Text, Float, Boolean, Index, CheckConstraint
from sqlalchemy.sql import func
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, ConfigDict, field_validator

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
    
    # Table constraints for data integrity
    __table_args__ = (
        # Composite index for source-target pair lookups
        Index('ix_workflow_source_target', 'source_id', 'target_id'),
        # Check constraint to ensure source and target are different
        CheckConstraint('source_id != target_id', name='ck_different_source_target'),
        # Check constraint for progress percentage
        CheckConstraint('progress_percentage >= 0 AND progress_percentage <= 100', name='ck_valid_progress'),
    )


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
    
    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Workflow name cannot be empty")
        return v.strip()
    
    @field_validator("source")
    @classmethod
    def validate_source(cls, v: "WorkflowSourceConfig") -> "WorkflowSourceConfig":
        if not v.id or len(v.id) < 3:
            raise ValueError("Source system ID must be at least 3 characters")
        if not v.type:
            raise ValueError("Source system type is required")
        return v
    
    @field_validator("target")
    @classmethod
    def validate_target(cls, v: "WorkflowTargetConfig") -> "WorkflowTargetConfig":
        if not v.id or len(v.id) < 3:
            raise ValueError("Target system ID must be at least 3 characters")
        if not v.type:
            raise ValueError("Target system type is required")
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
    
    model_config = ConfigDict(from_attributes=True)


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


class WorkflowActionResponse(BaseModel):
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


# ============================================================================
# WORKFLOW DEFINITION & EXECUTION (FOR DAG-BASED WORKFLOWS)
# ============================================================================

class MigrationStage(str, Enum):
    """PLM migration stages (aligned with frontend state machine)"""
    IDLE = "idle"
    INITIALIZING = "initializing"
    DISCOVERING = "discovering"
    PROFILING = "profiling"
    SCHEMA_MAPPING = "schema_mapping"
    DATA_MIGRATION = "data_migration"
    VALIDATION = "validation"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class WorkflowStepType(str, Enum):
    """Workflow step types for execution"""
    SQL = "sql"
    PYTHON = "python"
    API = "api"
    DISCOVERY = "discovery"          # DISCOVERING stage
    PROFILING = "profiling"          # PROFILING stage
    SCHEMA_MAPPING = "schema_mapping" # SCHEMA_MAPPING stage
    ETL_EXECUTION = "etl_execution"  # DATA_MIGRATION stage
    VALIDATION = "validation"        # VALIDATION stage


class WorkflowStepStatus(str, Enum):
    """Individual workflow step execution status"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    RETRYING = "retrying"


# SQLAlchemy ORM Models for DAG-based workflows
class WorkflowDefinition(Base):
    """
    Defines a reusable workflow with steps and dependencies.
    Can be instantiated multiple times for different executions.
    """
    __tablename__ = "workflow_definitions"
    
    id = Column(String(100), primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    
    # Source → Target mapping
    source_id = Column(String(100), nullable=False, index=True)
    target_id = Column(String(100), nullable=False, index=True)
    
    # Workflow metadata
    definition_config = Column(JSON, nullable=False)  # Full workflow graph
    mcp_decomposition_id = Column(String(100), nullable=True)  # Links to MCP TaskDecomposer output
    
    # Status & versioning
    is_active = Column(Boolean, default=True)
    version = Column(String(32), default="1.0.0")
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())
    created_by = Column(String(100), nullable=True)


class WorkflowStep(Base):
    """
    Individual step within a workflow definition.
    Steps are executed in DAG order with dependency resolution.
    """
    __tablename__ = "workflow_steps"
    
    id = Column(String(100), primary_key=True, index=True)
    workflow_id = Column(String(100), nullable=False, index=True)
    
    # Step identity
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    
    # Execution type (maps to migration stage)
    step_type = Column(String(32), default=WorkflowStepType.SQL.value, nullable=False)
    stage = Column(String(32), nullable=True)  # DISCOVERING, PROFILING, SCHEMA_MAPPING, DATA_MIGRATION, VALIDATION
    
    # Execution logic
    expression = Column(Text, nullable=False)  # SQL, Python, or API endpoint
    expression_language = Column(String(32), default="sql")
    parameters = Column(JSON, default=dict)
    
    # Dependencies (for DAG)
    depends_on = Column(JSON, default=list)  # List of step_ids this depends on
    sequence_order = Column(Integer, default=0)
    
    # Execution settings
    retries = Column(Integer, default=1)
    timeout_seconds = Column(Integer, default=3600)
    allow_failure = Column(Boolean, default=False)  # Continue on failure?
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())
    
    __table_args__ = (
        Index("idx_workflow_steps_workflow", "workflow_id"),
        Index("idx_workflow_steps_stage", "stage"),
    )


class WorkflowExecution(Base):
    """
    Tracks execution of a workflow definition.
    One definition can have multiple executions.
    """
    __tablename__ = "workflow_executions"
    
    id = Column(String(100), primary_key=True, index=True)
    workflow_id = Column(String(100), nullable=False, index=True)
    
    # Execution state
    status = Column(String(32), default=WorkflowStepStatus.PENDING.value, nullable=False)
    current_stage = Column(String(32), default=MigrationStage.IDLE.value)
    progress_percentage = Column(Float, default=0.0)
    
    # Timing
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    duration_ms = Column(Integer, nullable=True)
    
    # Execution context
    execution_context = Column(JSON, default=dict)  # Input parameters
    execution_metadata = Column(JSON, default=dict)  # Runtime info, errors
    
    # Statistics
    total_steps = Column(Integer, default=0)
    completed_steps = Column(Integer, default=0)
    failed_steps = Column(Integer, default=0)
    
    # Results
    final_result = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    created_by = Column(String(100), nullable=True)
    
    __table_args__ = (
        Index("idx_workflow_executions_workflow", "workflow_id"),
        Index("idx_workflow_executions_status", "status"),
    )


class WorkflowStepExecution(Base):
    """
    Tracks execution of individual steps within a workflow execution.
    """
    __tablename__ = "workflow_step_executions"
    
    id = Column(String(100), primary_key=True, index=True)
    execution_id = Column(String(100), nullable=False, index=True)
    step_id = Column(String(100), nullable=False, index=True)
    
    # Execution state
    status = Column(String(32), default=WorkflowStepStatus.PENDING.value)
    retry_count = Column(Integer, default=0)
    
    # Timing
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    duration_ms = Column(Integer, nullable=True)
    
    # Results
    result = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)
    output_data = Column(JSON, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    __table_args__ = (
        Index("idx_workflow_step_executions_execution", "execution_id"),
        Index("idx_workflow_step_executions_step", "step_id"),
    )


# Pydantic models for API
class WorkflowStepDefinition(BaseModel):
    """API model for workflow step definition"""
    id: str
    name: str
    description: Optional[str]
    step_type: WorkflowStepType
    stage: Optional[str]
    expression: str
    expression_language: str
    parameters: Dict[str, Any] = {}
    depends_on: List[str] = []
    sequence_order: int = 0
    retries: int = 1
    timeout_seconds: int = 3600
    allow_failure: bool = False


class WorkflowDefinitionCreate(BaseModel):
    """Request to create a new workflow definition"""
    name: str
    description: Optional[str]
    source_id: str
    target_id: str
    steps: List[WorkflowStepDefinition]
    mcp_decomposition_id: Optional[str] = None


class WorkflowExecutionResponse(BaseModel):
    """Response for workflow execution"""
    id: str
    workflow_id: str
    status: str
    current_stage: str
    progress_percentage: float
    completed_steps: int
    total_steps: int
    failed_steps: int
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    duration_ms: Optional[int]
    error_message: Optional[str]
    
    model_config = ConfigDict(from_attributes=True)
