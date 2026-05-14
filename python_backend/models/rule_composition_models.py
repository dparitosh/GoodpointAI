"""
Advanced Rule Composition Models - Complex rule combinations and templates

Enables:
- Logical operators (AND, OR, NOT, XOR) for rule composition
- Rule templates for reusable patterns
- Conditional rules based on workflow context
- Rule groups for organization
- Rule composition optimization
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from sqlalchemy import String, Text, Integer, DateTime, Index, text, Float
from sqlalchemy.types import JSON
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from core.database import Base


# ============================================================================
# Enumerations
# ============================================================================

class RuleOperator(str, Enum):
    """Logical operators for rule composition"""
    AND = "and"              # All conditions must be true
    OR = "or"                # Any condition must be true
    NOT = "not"              # Negates the condition
    XOR = "xor"              # Exactly one condition must be true
    ALL = "all"              # Alias for AND
    ANY = "any"              # Alias for OR


class ConditionComparator(str, Enum):
    """Comparison operators for rule conditions"""
    EQUALS = "eq"
    NOT_EQUALS = "ne"
    GREATER_THAN = "gt"
    GREATER_THAN_EQUAL = "gte"
    LESS_THAN = "lt"
    LESS_THAN_EQUAL = "lte"
    IN = "in"                # Value in list
    NOT_IN = "nin"           # Value not in list
    CONTAINS = "contains"    # String contains
    NOT_CONTAINS = "not_contains"
    MATCHES_REGEX = "regex"  # Regex pattern match
    IS_NULL = "is_null"      # Check for null
    IS_NOT_NULL = "not_null" # Check for not null
    BETWEEN = "between"      # Range check (inclusive)


class CompositionStrategy(str, Enum):
    """Rule composition strategies"""
    SEQUENTIAL = "sequential"    # Apply rules in order
    PARALLEL = "parallel"        # Apply rules concurrently
    PRIORITIZED = "prioritized"  # Apply highest priority first
    CONDITIONAL = "conditional"  # Apply conditionally based on context


# ============================================================================
# Pydantic Models (Request/Response)
# ============================================================================

class RuleConditionValue(BaseModel):
    """A single condition in a rule"""
    field: str = Field(..., description="Field or attribute name")
    comparator: ConditionComparator = Field(..., description="Comparison operator")
    value: Optional[Any] = Field(None, description="Value to compare against")
    values: Optional[List[Any]] = Field(None, description="Multiple values for IN/NOT_IN")


class RuleConditionNode(BaseModel):
    """Recursive rule condition node (tree structure)"""
    operator: Optional[RuleOperator] = Field(None, description="Logical operator (AND/OR/NOT/XOR)")
    conditions: Optional[List[RuleConditionValue]] = Field(None, description="Leaf conditions")
    children: Optional[List[RuleConditionNode]] = Field(None, description="Child nodes for nesting")
    
    class Config:
        json_schema_extra = {
            "example": {
                "operator": "and",
                "conditions": [
                    {"field": "status", "comparator": "eq", "value": "active"},
                    {"field": "score", "comparator": "gt", "value": 75}
                ],
                "children": [
                    {
                        "operator": "or",
                        "conditions": [
                            {"field": "priority", "comparator": "eq", "value": "high"},
                            {"field": "priority", "comparator": "eq", "value": "critical"}
                        ]
                    }
                ]
            }
        }


class CompositeRuleCreate(BaseModel):
    """Create a composite rule"""
    id: str = Field(..., description="Unique rule ID")
    name: str = Field(..., description="Rule name")
    description: Optional[str] = Field(None, description="Rule description")
    rule_ids: List[str] = Field(..., description="IDs of rules to compose")
    operator: RuleOperator = Field(RuleOperator.AND, description="Composition operator")
    severity: str = Field("medium", description="Severity level")
    enabled: bool = Field(True, description="Is rule enabled")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")


class CompositeRuleUpdate(BaseModel):
    """Update a composite rule"""
    name: Optional[str] = None
    description: Optional[str] = None
    operator: Optional[RuleOperator] = None
    rule_ids: Optional[List[str]] = None
    severity: Optional[str] = None
    enabled: Optional[bool] = None
    metadata: Optional[Dict[str, Any]] = None


class CompositeRule(BaseModel):
    """Composite rule response model"""
    id: str
    name: str
    description: Optional[str]
    rule_ids: List[str]
    operator: RuleOperator
    severity: str
    enabled: bool
    metadata: Optional[Dict[str, Any]]
    created_at: datetime
    updated_at: datetime


class RuleTemplateCreate(BaseModel):
    """Create a rule template"""
    id: str = Field(..., description="Template ID")
    name: str = Field(..., description="Template name")
    description: Optional[str] = Field(None, description="Template description")
    category: str = Field("general", description="Template category")
    rule_type: str = Field(..., description="Type of rule (completeness, validity, etc.)")
    template_definition: Dict[str, Any] = Field(..., description="Template structure")
    parameters: List[str] = Field(..., description="Template parameters (e.g., ['field', 'threshold'])")
    example_config: Optional[Dict[str, Any]] = Field(None, description="Example configuration")
    enabled: bool = Field(True, description="Is template enabled")


class RuleTemplateInstance(BaseModel):
    """Rule instance created from template"""
    id: str
    template_id: str
    name: str
    parameters: Dict[str, Any]
    created_at: datetime


class RuleTemplate(BaseModel):
    """Rule template response model"""
    id: str
    name: str
    description: Optional[str]
    category: str
    rule_type: str
    template_definition: Dict[str, Any]
    parameters: List[str]
    example_config: Optional[Dict[str, Any]]
    enabled: bool
    created_at: datetime
    updated_at: datetime


class RuleGroupCreate(BaseModel):
    """Create a rule group"""
    id: str = Field(..., description="Group ID")
    name: str = Field(..., description="Group name")
    description: Optional[str] = Field(None, description="Group description")
    rule_ids: List[str] = Field(default_factory=list, description="IDs of rules in group")
    priority: int = Field(100, description="Group priority (higher = earlier)")
    enabled: bool = Field(True, description="Is group enabled")


class RuleGroupUpdate(BaseModel):
    """Update a rule group"""
    name: Optional[str] = None
    description: Optional[str] = None
    rule_ids: Optional[List[str]] = None
    priority: Optional[int] = None
    enabled: Optional[bool] = None


class RuleGroup(BaseModel):
    """Rule group response model"""
    id: str
    name: str
    description: Optional[str]
    rule_ids: List[str]
    priority: int
    enabled: bool
    rule_count: int
    created_at: datetime
    updated_at: datetime


class RuleCompositionValidation(BaseModel):
    """Result of validating rule composition logic"""
    is_valid: bool
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)
    complexity_score: float = Field(0.0, description="Composition complexity (0-100)")
    operator_count: int = Field(0)
    depth: int = Field(0, description="Max nesting depth")


class RuleOptimization(BaseModel):
    """Rule composition optimization suggestion"""
    current_expression: str
    optimized_expression: str
    improvement: str
    estimated_performance_gain: float = Field(0.0, description="Percentage improvement")


# ============================================================================
# SQLAlchemy Models (ORM)
# ============================================================================

class CompositeRuleORM(Base):
    """Composite rule combining multiple rules with logical operators"""
    __tablename__ = "composite_rules"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # Composition details
    rule_ids: Mapped[list] = mapped_column(JSON, nullable=False)  # List of rule IDs
    operator: Mapped[str] = mapped_column(String(16), nullable=False, default="and")  # and|or|not|xor
    
    # Rule metadata
    severity: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    enabled: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    
    # Additional metadata
    metadata: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("CURRENT_TIMESTAMP"),
        onupdate=func.now(),
        nullable=False,
    )

    __table_args__ = (
        Index("idx_composite_rules_operator", "operator"),
        Index("idx_composite_rules_severity", "severity"),
    )


class RuleTemplateORM(Base):
    """Reusable rule templates for common patterns"""
    __tablename__ = "rule_templates"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # Template details
    category: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    rule_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    
    # Template definition and parameters
    template_definition: Mapped[dict] = mapped_column(JSON, nullable=False)
    parameters: Mapped[list] = mapped_column(JSON, nullable=False)  # List of param names
    example_config: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    
    # Status
    enabled: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    usage_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("CURRENT_TIMESTAMP"),
        onupdate=func.now(),
        nullable=False,
    )

    __table_args__ = (
        Index("idx_rule_templates_category", "category"),
        Index("idx_rule_templates_type", "rule_type"),
    )


class RuleGroupORM(Base):
    """Groups of related rules for organization and execution"""
    __tablename__ = "rule_groups"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # Group membership
    rule_ids: Mapped[list] = mapped_column(JSON, nullable=False)  # List of rule IDs
    
    # Execution details
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    enabled: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    
    # Statistics
    rule_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("CURRENT_TIMESTAMP"),
        onupdate=func.now(),
        nullable=False,
    )

    __table_args__ = (
        Index("idx_rule_groups_priority", "priority"),
        Index("idx_rule_groups_enabled", "enabled"),
    )


class RuleCompositionHistoryORM(Base):
    """History of rule composition changes for audit"""
    __tablename__ = "rule_composition_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    rule_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    rule_type: Mapped[str] = mapped_column(String(32), nullable=False)  # composite|template|group
    
    # Change details
    operation: Mapped[str] = mapped_column(String(16), nullable=False)  # create|update|delete|execute
    previous_state: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    new_state: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    
    # Metadata
    changed_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False
    )

    __table_args__ = (
        Index("idx_rule_composition_history_rule", "rule_id", "rule_type"),
        Index("idx_rule_composition_history_operation", "operation"),
    )
