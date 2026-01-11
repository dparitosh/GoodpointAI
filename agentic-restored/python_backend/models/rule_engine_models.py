"""
PLM Rule Engine Models - Hierarchical Rule Structure for ETL & Data Quality

Supports three rule levels:
- Level 1: Attribute Rules (Atomic) - Single field validation
- Level 2: Entity Rules (Contextual) - Row/Object validation  
- Level 3: Relationship Rules (Topological) - Graph/BOM validation

Rule execution follows a DAG (Directed Acyclic Graph) structure with parent-child dependencies.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy import (
    Column, String, Integer, Float, Boolean, DateTime, Text, JSON, ForeignKey,
    Index, Enum as SQLEnum, UniqueConstraint
)
from sqlalchemy.orm import relationship
from enum import Enum
from core.database import Base


class RuleLevel(str, Enum):
    """Rule hierarchy levels"""
    ATTRIBUTE = "attribute"      # Level 1: Single field
    ENTITY = "entity"            # Level 2: Row/Object
    RELATIONSHIP = "relationship" # Level 3: Graph/BOM


class RuleSeverity(str, Enum):
    """Rule severity levels"""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    BLOCKER = "blocker"


class RuleActionOnFail(str, Enum):
    """Actions to take when rule fails"""
    LOG = "log"                  # Just log the failure
    WARN = "warn"                # Log warning, continue
    QUARANTINE = "quarantine"    # Move to quarantine table
    REJECT = "reject"            # Reject the record
    TRANSFORM = "transform"      # Apply transformation
    ESCALATE = "escalate"        # Escalate for review


class RuleStatus(str, Enum):
    """Rule lifecycle status"""
    DRAFT = "draft"
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    ARCHIVED = "archived"
    DELETED = "deleted"


class ExecutionStatus(str, Enum):
    """Rule execution status"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    ERROR = "error"


# ============================================================================
# RULE SET - Container for related rules
# ============================================================================

class RuleSet(Base):
    """
    Rule Set - A logical grouping of related rules.
    Example: BOM_VALIDATION_V1, CAD_QUALITY_CHECKS, MATERIAL_COMPLIANCE
    """
    __tablename__ = "rule_sets"
    
    id = Column(String(64), primary_key=True)
    name = Column(String(256), nullable=False)
    description = Column(Text, nullable=True)
    version = Column(String(32), default="1.0.0")
    category = Column(String(64), default="general")  # e.g., "data_quality", "compliance", "plm_validation"
    context = Column(String(128), nullable=True)  # e.g., "Engineering_BOM", "CAD_Import", "Material_ETL"
    target_entity_type = Column(String(128), nullable=True)  # e.g., "Item", "BOM", "CADModel"
    
    # Execution settings
    execution_mode = Column(String(32), default="sequential")  # sequential, parallel, dag
    stop_on_critical = Column(Boolean, default=True)
    max_parallel_rules = Column(Integer, default=10)
    timeout_seconds = Column(Integer, default=3600)
    
    # Metadata
    status = Column(String(32), default=RuleStatus.DRAFT.value)
    is_active = Column(Boolean, default=True)
    owner = Column(String(128), nullable=True)
    tags = Column(JSON, default=list)
    custom_metadata = Column(JSON, default=dict)  # Additional custom metadata (named custom_metadata to avoid SQLAlchemy conflict)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(String(128), nullable=True)
    
    # Relationships
    rules = relationship("Rule", back_populates="rule_set", cascade="all, delete-orphan")
    executions = relationship("RuleSetExecution", back_populates="rule_set", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index("idx_rule_sets_context", "context"),
        Index("idx_rule_sets_status", "status"),
    )


# ============================================================================
# RULE - Individual rule definition
# ============================================================================

class Rule(Base):
    """
    Individual Rule - Defines a single validation/transformation rule.
    Supports hierarchical dependencies via parent_rule_id.
    """
    __tablename__ = "rules"
    
    id = Column(String(64), primary_key=True)
    rule_set_id = Column(String(64), ForeignKey("rule_sets.id", ondelete="CASCADE"), nullable=False)
    parent_rule_id = Column(String(64), ForeignKey("rules.id", ondelete="SET NULL"), nullable=True)
    
    # Rule definition
    name = Column(String(256), nullable=False)
    description = Column(Text, nullable=True)
    level = Column(String(32), default=RuleLevel.ATTRIBUTE.value)
    
    # Target specification
    target_entity = Column(String(128), nullable=True)  # e.g., "plm_parts", "plm_bom_items"
    target_field = Column(String(128), nullable=True)   # For attribute rules
    target_relationship = Column(String(128), nullable=True)  # For relationship rules
    
    # Expression & Logic
    expression = Column(Text, nullable=False)  # The rule expression (SQL, Python, SparkSQL)
    expression_language = Column(String(32), default="python")  # python, sql, sparksql, cypher
    parameters = Column(JSON, default=dict)  # Dynamic parameters for expression
    
    # Validation settings
    severity = Column(String(32), default=RuleSeverity.WARNING.value)
    action_on_fail = Column(String(32), default=RuleActionOnFail.LOG.value)
    transformation_logic = Column(Text, nullable=True)  # Applied if action_on_fail is 'transform'
    
    # Execution order
    sequence_order = Column(Integer, default=0)
    dependency_condition = Column(String(32), default="all_pass")  # all_pass, any_pass, parent_pass
    
    # Thresholds
    error_threshold_percent = Column(Float, default=100.0)  # % of failures before blocking
    warning_threshold_percent = Column(Float, default=10.0)
    sample_size = Column(Integer, nullable=True)  # For sampling large datasets
    
    # Metadata
    status = Column(String(32), default=RuleStatus.DRAFT.value)
    enabled = Column(Boolean, default=True)
    tags = Column(JSON, default=list)
    documentation_url = Column(String(512), nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    rule_set = relationship("RuleSet", back_populates="rules")
    parent_rule = relationship("Rule", remote_side=[id], backref="child_rules")
    executions = relationship("RuleExecution", back_populates="rule", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index("idx_rules_rule_set", "rule_set_id"),
        Index("idx_rules_parent", "parent_rule_id"),
        Index("idx_rules_level", "level"),
        Index("idx_rules_sequence", "rule_set_id", "sequence_order"),
    )


# ============================================================================
# RULE TEMPLATES - Reusable rule patterns
# ============================================================================

class RuleTemplate(Base):
    """
    Rule Template - Predefined, reusable rule patterns.
    Examples: NOT_NULL, UNIQUE, REGEX_MATCH, RANGE_CHECK, FK_EXISTS
    """
    __tablename__ = "rule_templates"
    
    id = Column(String(64), primary_key=True)
    name = Column(String(256), nullable=False)
    description = Column(Text, nullable=True)
    category = Column(String(64), nullable=False)  # data_quality, business_logic, compliance
    
    # Template definition
    level = Column(String(32), default=RuleLevel.ATTRIBUTE.value)
    expression_template = Column(Text, nullable=False)  # Expression with {{placeholders}}
    expression_language = Column(String(32), default="python")
    
    # Parameter schema
    parameter_schema = Column(JSON, nullable=False)  # JSON Schema for parameters
    default_parameters = Column(JSON, default=dict)
    
    # Defaults
    default_severity = Column(String(32), default=RuleSeverity.WARNING.value)
    default_action = Column(String(32), default=RuleActionOnFail.LOG.value)
    
    # Metadata
    is_system = Column(Boolean, default=False)  # Built-in vs user-created
    is_active = Column(Boolean, default=True)  # For soft-delete
    usage_count = Column(Integer, default=0)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        Index("idx_rule_templates_category", "category"),
        Index("idx_rule_templates_level", "level"),
    )


# ============================================================================
# EXECUTION TRACKING
# ============================================================================

class RuleSetExecution(Base):
    """
    Rule Set Execution - Tracks execution of a complete rule set.
    """
    __tablename__ = "rule_set_executions"
    
    id = Column(String(64), primary_key=True)
    rule_set_id = Column(String(64), ForeignKey("rule_sets.id", ondelete="CASCADE"), nullable=False)
    
    # Execution context
    execution_context = Column(JSON, default=dict)  # Input parameters, filters
    data_source = Column(String(256), nullable=True)  # Source table/file
    record_count = Column(Integer, default=0)
    
    # Status
    status = Column(String(32), default=ExecutionStatus.PENDING.value)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    duration_ms = Column(Integer, nullable=True)
    
    # Results summary
    total_rules = Column(Integer, default=0)
    rules_passed = Column(Integer, default=0)
    rules_failed = Column(Integer, default=0)
    rules_skipped = Column(Integer, default=0)
    rules_error = Column(Integer, default=0)
    
    # Aggregated metrics
    total_records_checked = Column(Integer, default=0)
    total_failures = Column(Integer, default=0)
    overall_pass_rate = Column(Float, default=0.0)
    
    # Error tracking
    error_message = Column(Text, nullable=True)
    error_stack = Column(Text, nullable=True)
    
    # Execution metadata
    triggered_by = Column(String(128), nullable=True)  # user, scheduler, pipeline
    spark_app_id = Column(String(128), nullable=True)  # For Spark executions
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    rule_set = relationship("RuleSet", back_populates="executions")
    rule_executions = relationship("RuleExecution", back_populates="set_execution", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index("idx_rule_set_exec_status", "status"),
        Index("idx_rule_set_exec_date", "created_at"),
    )


class RuleExecution(Base):
    """
    Individual Rule Execution - Tracks execution of a single rule.
    """
    __tablename__ = "rule_executions"
    
    id = Column(String(64), primary_key=True)
    set_execution_id = Column(String(64), ForeignKey("rule_set_executions.id", ondelete="CASCADE"), nullable=False)
    rule_id = Column(String(64), ForeignKey("rules.id", ondelete="CASCADE"), nullable=False)
    
    # Execution details
    sequence_executed = Column(Integer, default=0)
    status = Column(String(32), default=ExecutionStatus.PENDING.value)
    
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    duration_ms = Column(Integer, nullable=True)
    
    # Results
    records_checked = Column(Integer, default=0)
    records_passed = Column(Integer, default=0)
    records_failed = Column(Integer, default=0)
    pass_rate = Column(Float, default=0.0)
    
    # Failure details
    failure_samples = Column(JSON, default=list)  # Sample of failed records
    failure_summary = Column(JSON, default=dict)  # Aggregated failure stats
    
    # Actions taken
    action_taken = Column(String(32), nullable=True)
    records_quarantined = Column(Integer, default=0)
    records_transformed = Column(Integer, default=0)
    
    # Error tracking
    error_message = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    set_execution = relationship("RuleSetExecution", back_populates="rule_executions")
    rule = relationship("Rule", back_populates="executions")
    
    __table_args__ = (
        Index("idx_rule_exec_status", "status"),
        Index("idx_rule_exec_rule", "rule_id"),
    )


# ============================================================================
# QUARANTINE - Failed records storage
# ============================================================================

class QuarantineRecord(Base):
    """
    Quarantine Record - Stores records that failed validation.
    """
    __tablename__ = "quarantine_records"
    
    id = Column(String(64), primary_key=True)
    rule_execution_id = Column(String(64), ForeignKey("rule_executions.id", ondelete="SET NULL"), nullable=True)
    rule_id = Column(String(64), nullable=False)
    
    # Source information
    source_table = Column(String(128), nullable=False)
    source_record_id = Column(String(256), nullable=True)
    
    # Failed record data
    record_data = Column(JSON, nullable=False)
    failure_reason = Column(Text, nullable=False)
    severity = Column(String(32), default=RuleSeverity.WARNING.value)
    
    # Resolution tracking
    status = Column(String(32), default="pending")  # pending, reviewed, resolved, ignored
    resolution_notes = Column(Text, nullable=True)
    resolved_by = Column(String(128), nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        Index("idx_quarantine_status", "status"),
        Index("idx_quarantine_source", "source_table"),
        Index("idx_quarantine_rule", "rule_id"),
    )
