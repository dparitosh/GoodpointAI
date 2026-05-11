"""
PLM Rule Engine API Router

Provides REST endpoints for:
- Rule Set CRUD operations
- Rule CRUD operations
- Rule Template management
- Rule execution and results
- Quarantine management
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from core.db_session import get_db
from models.rule_engine_models import (
    RuleSet, Rule, RuleTemplate, RuleSetExecution, RuleExecution, QuarantineRecord,
    RuleStatus, ExecutionStatus
)
from services.rule_engine import RuleEngine, get_system_templates

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/rules", tags=["Rule Engine"])


# ============================================================================
# PYDANTIC SCHEMAS
# ============================================================================

class RuleSetCreate(BaseModel):
    """Schema for creating a rule set."""
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    version: str = "1.0.0"
    category: str = "general"
    context: Optional[str] = None  # e.g., "Engineering_BOM", "PLM_Items"
    target_entity_type: Optional[str] = None
    execution_mode: str = "sequential"  # sequential, parallel, dag
    stop_on_critical: bool = True
    timeout_seconds: int = 3600
    metadata: dict = Field(default_factory=dict)


class RuleSetUpdate(BaseModel):
    """Schema for updating a rule set."""
    name: Optional[str] = None
    description: Optional[str] = None
    version: Optional[str] = None
    category: Optional[str] = None
    context: Optional[str] = None
    target_entity_type: Optional[str] = None
    execution_mode: Optional[str] = None
    stop_on_critical: Optional[bool] = None
    timeout_seconds: Optional[int] = None
    is_active: Optional[bool] = None
    metadata: Optional[dict] = None


class RuleCreate(BaseModel):
    """Schema for creating a rule."""
    rule_set_id: str
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    level: str = "entity"  # attribute, entity, relationship
    severity: str = "warning"  # info, warning, critical, blocker
    expression: str = Field(..., min_length=1)
    expression_type: str = "python"  # python, sql, sparksql, cypher
    action_on_fail: str = "log"  # log, warn, quarantine, reject, transform, escalate
    transformation_expression: Optional[str] = None
    parent_rule_id: Optional[str] = None
    dependency_condition: str = "parent_pass"  # parent_pass, parent_fail, always
    sequence_order: int = 0
    parameters: dict = Field(default_factory=dict)
    metadata: dict = Field(default_factory=dict)


class RuleUpdate(BaseModel):
    """Schema for updating a rule."""
    name: Optional[str] = None
    description: Optional[str] = None
    level: Optional[str] = None
    severity: Optional[str] = None
    expression: Optional[str] = None
    expression_type: Optional[str] = None
    action_on_fail: Optional[str] = None
    transformation_expression: Optional[str] = None
    parent_rule_id: Optional[str] = None
    dependency_condition: Optional[str] = None
    sequence_order: Optional[int] = None
    status: Optional[str] = None
    parameters: Optional[dict] = None
    metadata: Optional[dict] = None


class RuleTemplateCreate(BaseModel):
    """Schema for creating a rule template."""
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    category: str = "general"
    level: str = "entity"
    expression_template: str
    parameter_schema: dict = Field(default_factory=dict)
    default_severity: str = "warning"
    default_action: str = "log"


class ExecuteRuleSetRequest(BaseModel):
    """Schema for executing a rule set."""
    rule_set_id: str
    records: List[dict] = Field(default_factory=list)
    parameters: dict = Field(default_factory=dict)
    stop_on_critical: Optional[bool] = None
    max_failure_samples: int = 100


class QuarantineResolutionRequest(BaseModel):
    """Schema for resolving quarantine records."""
    resolution_action: str  # release, transform, reject, delete
    resolution_notes: Optional[str] = None
    transformed_record: Optional[dict] = None


# ============================================================================
# RULE SET ENDPOINTS
# ============================================================================

@router.get("/sets", summary="List all rule sets")
async def list_rule_sets(
    category: Optional[str] = None,
    context: Optional[str] = None,
    is_active: Optional[bool] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """List all rule sets with optional filtering."""
    try:
        query = db.query(RuleSet)
        
        # Only filter by is_active if the column exists and value is provided
        try:
            if is_active is not None:
                query = query.filter(RuleSet.is_active == is_active)
        except Exception:
            pass  # Column doesn't exist yet
            
        if category:
            query = query.filter(RuleSet.category == category)
        if context:
            query = query.filter(RuleSet.context == context)
        
        total = query.count()
        rule_sets = query.order_by(RuleSet.created_at.desc()).offset(skip).limit(limit).all()
        
        return {
            "items": [
                {
                    "id": rs.id,
                    "name": rs.name,
                    "description": rs.description,
                    "version": rs.version,
                    "category": rs.category,
                    "context": rs.context,
                    "target_entity_type": rs.target_entity_type,
                    "execution_mode": rs.execution_mode,
                    "stop_on_critical": rs.stop_on_critical,
                    "is_active": getattr(rs, 'is_active', True),
                    "rule_count": len(rs.rules) if rs.rules else 0,
                    "created_at": rs.created_at.isoformat() if rs.created_at else None,
                    "updated_at": rs.updated_at.isoformat() if rs.updated_at else None
                }
                for rs in rule_sets
            ],
            "total": total,
            "skip": skip,
            "limit": limit
        }
    except Exception as e:
        logger.error("Failed to list rule sets: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sets", summary="Create a rule set")
async def create_rule_set(data: RuleSetCreate, db: Session = Depends(get_db)):
    """Create a new rule set."""
    try:
        rule_set = RuleSet(
            id=str(uuid.uuid4()),
            name=data.name,
            description=data.description,
            version=data.version,
            category=data.category,
            context=data.context,
            target_entity_type=data.target_entity_type,
            execution_mode=data.execution_mode,
            stop_on_critical=data.stop_on_critical,
            timeout_seconds=data.timeout_seconds,
            custom_metadata=data.metadata,
            is_active=True
        )
        
        db.add(rule_set)
        db.commit()
        db.refresh(rule_set)
        
        return {
            "id": rule_set.id,
            "name": rule_set.name,
            "version": rule_set.version,
            "message": "Rule set created successfully"
        }
    except Exception as e:
        db.rollback()
        logger.error("Failed to create rule set: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sets/{rule_set_id}", summary="Get rule set details")
async def get_rule_set(rule_set_id: str, db: Session = Depends(get_db)):
    """Get a rule set with all its rules."""
    try:
        rule_set = db.query(RuleSet).filter(RuleSet.id == rule_set_id).first()
        
        if not rule_set:
            raise HTTPException(status_code=404, detail="Rule set not found")
        
        rules = db.query(Rule).filter(
            Rule.rule_set_id == rule_set_id,
            Rule.status != RuleStatus.DELETED
        ).order_by(Rule.sequence_order).all()
        
        return {
            "id": rule_set.id,
            "name": rule_set.name,
            "description": rule_set.description,
            "version": rule_set.version,
            "category": rule_set.category,
            "context": rule_set.context,
            "target_entity_type": rule_set.target_entity_type,
            "execution_mode": rule_set.execution_mode,
            "stop_on_critical": rule_set.stop_on_critical,
            "timeout_seconds": rule_set.timeout_seconds,
            "is_active": rule_set.is_active,
            "metadata": rule_set.custom_metadata,
            "created_at": rule_set.created_at.isoformat() if rule_set.created_at else None,
            "updated_at": rule_set.updated_at.isoformat() if rule_set.updated_at else None,
            "rules": [
                {
                    "id": r.id,
                    "name": r.name,
                    "description": r.description,
                    "level": r.level,
                    "severity": r.severity,
                    "expression": r.expression,
                    "expression_type": r.expression_language,
                    "action_on_fail": r.action_on_fail,
                    "parent_rule_id": r.parent_rule_id,
                    "dependency_condition": r.dependency_condition,
                    "sequence_order": r.sequence_order,
                    "status": r.status,
                    "parameters": r.parameters
                }
                for r in rules
            ]
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get rule set: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/sets/{rule_set_id}", summary="Update a rule set")
async def update_rule_set(
    rule_set_id: str,
    data: RuleSetUpdate,
    db: Session = Depends(get_db)
):
    """Update a rule set."""
    try:
        rule_set = db.query(RuleSet).filter(RuleSet.id == rule_set_id).first()
        
        if not rule_set:
            raise HTTPException(status_code=404, detail="Rule set not found")
        
        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            # Map Pydantic 'metadata' to SQLAlchemy 'custom_metadata'
            db_key = "custom_metadata" if key == "metadata" else key
            setattr(rule_set, db_key, value)
        
        rule_set.updated_at = datetime.now(timezone.utc)
        db.commit()
        
        return {"message": "Rule set updated successfully", "id": rule_set_id}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error("Failed to update rule set: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/sets/{rule_set_id}", summary="Delete a rule set")
async def delete_rule_set(
    rule_set_id: str,
    hard_delete: bool = False,
    db: Session = Depends(get_db)
):
    """Delete a rule set (soft delete by default)."""
    try:
        rule_set = db.query(RuleSet).filter(RuleSet.id == rule_set_id).first()
        
        if not rule_set:
            raise HTTPException(status_code=404, detail="Rule set not found")
        
        if hard_delete:
            db.delete(rule_set)
        else:
            rule_set.is_active = False
            rule_set.updated_at = datetime.now(timezone.utc)
        
        db.commit()
        
        return {"message": "Rule set deleted successfully", "id": rule_set_id}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error("Failed to delete rule set: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# RULE ENDPOINTS
# ============================================================================

@router.get("/", summary="List all rules")
async def list_rules(
    rule_set_id: Optional[str] = None,
    level: Optional[str] = None,
    severity: Optional[str] = None,
    status: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """List all rules with optional filtering."""
    try:
        query = db.query(Rule)
        
        if rule_set_id:
            query = query.filter(Rule.rule_set_id == rule_set_id)
        if level:
            query = query.filter(Rule.level == level)
        if severity:
            query = query.filter(Rule.severity == severity)
        if status:
            query = query.filter(Rule.status == status)
        else:
            query = query.filter(Rule.status != RuleStatus.DELETED.value)
        
        total = query.count()
        rules = query.order_by(Rule.sequence_order, Rule.created_at).offset(skip).limit(limit).all()
        
        return {
            "items": [
                {
                    "id": r.id,
                    "rule_set_id": r.rule_set_id,
                    "name": r.name,
                    "description": r.description,
                    "level": r.level,
                    "severity": r.severity,
                    "expression": r.expression,
                    "action_on_fail": r.action_on_fail,
                    "parent_rule_id": r.parent_rule_id,
                    "sequence_order": r.sequence_order,
                    "status": r.status
                }
                for r in rules
            ],
            "total": total,
            "skip": skip,
            "limit": limit
        }
    except Exception as e:
        logger.error("Failed to list rules: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/", summary="Create a rule")
async def create_rule(data: RuleCreate, db: Session = Depends(get_db)):
    """Create a new rule."""
    try:
        # Verify rule set exists
        rule_set = db.query(RuleSet).filter(RuleSet.id == data.rule_set_id).first()
        if not rule_set:
            raise HTTPException(status_code=404, detail="Rule set not found")
        
        # Verify parent rule exists if specified
        if data.parent_rule_id:
            parent = db.query(Rule).filter(Rule.id == data.parent_rule_id).first()
            if not parent:
                raise HTTPException(status_code=404, detail="Parent rule not found")
        
        rule = Rule(
            id=str(uuid.uuid4()),
            rule_set_id=data.rule_set_id,
            name=data.name,
            description=data.description,
            level=data.level,
            severity=data.severity,
            expression=data.expression,
            expression_language=data.expression_type,
            action_on_fail=data.action_on_fail,
            transformation_logic=data.transformation_expression,
            parent_rule_id=data.parent_rule_id,
            dependency_condition=data.dependency_condition,
            sequence_order=data.sequence_order,
            parameters=data.parameters,
            status=RuleStatus.ACTIVE.value
        )
        
        db.add(rule)
        db.commit()
        db.refresh(rule)
        
        return {
            "id": rule.id,
            "name": rule.name,
            "message": "Rule created successfully"
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error("Failed to create rule: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# RULE TEMPLATE ENDPOINTS
# ============================================================================

@router.get("/templates/", summary="List rule templates")
async def list_templates(
    category: Optional[str] = None,
    level: Optional[str] = None,
    include_system: bool = True,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """List all rule templates."""
    try:
        templates = []
        
        # Get system templates
        if include_system:
            system_templates = get_system_templates()
            for t in system_templates:
                if category and t.get('category') != category:
                    continue
                if level and t.get('level') != level:
                    continue
                t['is_system'] = True
                templates.append(t)
        
        # Get custom templates from DB (skip if table doesn't exist)
        try:
            query = db.query(RuleTemplate)
            if category:
                query = query.filter(RuleTemplate.category == category)
            if level:
                query = query.filter(RuleTemplate.level == level)
            
            db_templates = query.all()
            for t in db_templates:
                templates.append({
                    "id": t.id,
                    "name": t.name,
                    "description": t.description,
                    "category": t.category,
                    "level": t.level,
                    "expression_template": t.expression_template,
                    "parameter_schema": t.parameter_schema,
                    "default_severity": t.default_severity,
                    "default_action": t.default_action,
                    "is_system": False
                })
        except Exception as db_err:
            logger.warning("Could not load custom templates from DB: %s", db_err)
        
        total = len(templates)
        templates = templates[skip:skip + limit]
        
        return {
            "items": templates,
            "total": total,
            "skip": skip,
            "limit": limit
        }
    except Exception as e:
        logger.error("Failed to list templates: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/templates/", summary="Create a rule template")
async def create_template(data: RuleTemplateCreate, db: Session = Depends(get_db)):
    """Create a custom rule template."""
    try:
        template = RuleTemplate(
            id=str(uuid.uuid4()),
            name=data.name,
            description=data.description,
            category=data.category,
            level=data.level,
            expression_template=data.expression_template,
            parameter_schema=data.parameter_schema,
            default_severity=data.default_severity,
            default_action=data.default_action
        )
        
        db.add(template)
        db.commit()
        
        return {
            "id": template.id,
            "name": template.name,
            "message": "Template created successfully"
        }
    except Exception as e:
        db.rollback()
        logger.error("Failed to create template: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/from-template", summary="Create rule from template")
async def create_rule_from_template(
    template_id: str = Query(...),
    rule_set_id: str = Query(...),
    name: str = Query(...),
    parameters: dict = Body(default={}),
    db: Session = Depends(get_db)
):
    """Create a rule by instantiating a template."""
    try:
        # Find template (check system templates first)
        template = None
        for t in get_system_templates():
            if t['id'] == template_id:
                template = t
                break
        
        if not template:
            template_db = db.query(RuleTemplate).filter(RuleTemplate.id == template_id).first()
            if template_db:
                template = {
                    'expression_template': template_db.expression_template,
                    'level': template_db.level,
                    'default_severity': template_db.default_severity,
                    'default_action': template_db.default_action,
                    'parameter_schema': template_db.parameter_schema
                }
        
        if not template:
            raise HTTPException(status_code=404, detail="Template not found")
        
        # Substitute parameters into expression template
        expression = template['expression_template']
        for key, value in parameters.items():
            placeholder = "{{" + key + "}}"
            if isinstance(value, str):
                expression = expression.replace(placeholder, value)
            elif isinstance(value, list):
                expression = expression.replace(placeholder, str(value))
            else:
                expression = expression.replace(placeholder, str(value))
        
        # Create rule
        rule = Rule(
            id=str(uuid.uuid4()),
            rule_set_id=rule_set_id,
            name=name,
            description=f"Created from template: {template_id}",
            level=template['level'],
            severity=template['default_severity'],
            expression=expression,
            expression_language="python",
            action_on_fail=template['default_action'],
            parameters=parameters,
            status=RuleStatus.ACTIVE.value
        )
        
        db.add(rule)
        db.commit()
        
        return {
            "id": rule.id,
            "name": rule.name,
            "expression": expression,
            "message": "Rule created from template"
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error("Failed to create rule from template: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# EXECUTION ENDPOINTS
# ============================================================================

@router.post("/execute", summary="Execute a rule set")
async def execute_rule_set(
    request: ExecuteRuleSetRequest,
    db: Session = Depends(get_db)
):
    """Execute a rule set against provided records."""
    try:
        # Get rule set
        rule_set = db.query(RuleSet).filter(RuleSet.id == request.rule_set_id).first()
        if not rule_set:
            raise HTTPException(status_code=404, detail="Rule set not found")
        
        # Get rules
        rules = db.query(Rule).filter(
            Rule.rule_set_id == request.rule_set_id,
            Rule.status == RuleStatus.ACTIVE.value
        ).order_by(Rule.sequence_order).all()
        
        if not rules:
            raise HTTPException(status_code=400, detail="Rule set has no active rules")
        
        # Convert to dict format for engine
        rule_set_dict = {
            "id": rule_set.id,
            "name": rule_set.name,
            "execution_mode": rule_set.execution_mode,
            "stop_on_critical": request.stop_on_critical or rule_set.stop_on_critical
        }
        
        rules_dict = [
            {
                "id": r.id,
                "name": r.name,
                "expression": r.expression,
                "level": r.level or "entity",
                "severity": r.severity or "warning",
                "action_on_fail": r.action_on_fail or "log",
                "parent_rule_id": r.parent_rule_id,
                "dependency_condition": r.dependency_condition,
                "sequence_order": r.sequence_order,
                "parameters": {**(r.parameters or {}), **request.parameters}
            }
            for r in rules
        ]
        
        # Execute
        engine = RuleEngine(db)
        result = engine.execute_rule_set(
            rule_set_dict,
            rules_dict,
            request.records,
            stop_on_critical=rule_set_dict['stop_on_critical']
        )
        
        # Save execution record
        execution = RuleSetExecution(
            id=result.execution_id,
            rule_set_id=request.rule_set_id,
            status=result.status,  # Already a string from the engine
            total_rules=result.total_rules,
            rules_passed=result.rules_passed,
            rules_failed=result.rules_failed,
            rules_skipped=result.rules_skipped,
            rules_error=result.rules_error,
            total_records_checked=result.total_records,
            total_failures=result.total_failures,
            overall_pass_rate=result.overall_pass_rate,
            duration_ms=result.duration_ms,
            started_at=result.started_at,
            completed_at=result.completed_at,
            error_message=result.error_message
        )
        db.add(execution)
        
        # Save individual rule executions
        for rr in result.rule_results:
            rule_exec = RuleExecution(
                id=str(uuid.uuid4()),
                set_execution_id=result.execution_id,
                rule_id=rr.rule_id,
                status=ExecutionStatus.COMPLETED.value if not rr.error else ExecutionStatus.ERROR.value,
                records_checked=rr.records_checked,
                records_passed=rr.records_checked - rr.records_failed,
                records_failed=rr.records_failed,
                pass_rate=(rr.records_checked - rr.records_failed) / rr.records_checked * 100 if rr.records_checked > 0 else 0,
                duration_ms=rr.duration_ms,
                error_message=rr.error
            )
            db.add(rule_exec)
        
        db.commit()
        
        # Build rule name lookup from rules_dict
        _rule_names = {r["id"]: r["name"] for r in rules_dict}

        return {
            "execution_id": result.execution_id,
            "rule_set_id": request.rule_set_id,
            "status": result.status,
            # Top-level convenience fields (mirrors summary for frontend)
            "total_records": result.total_records,
            "overall_pass_rate": round(result.overall_pass_rate, 2),
            "duration_ms": result.duration_ms,
            "duration_seconds": round(result.duration_ms / 1000.0, 3) if result.duration_ms else 0,
            "summary": {
                "total_rules": result.total_rules,
                "rules_passed": result.rules_passed,
                "rules_failed": result.rules_failed,
                "rules_skipped": result.rules_skipped,
                "rules_error": result.rules_error,
                "total_records": result.total_records,
                "total_failures": result.total_failures,
                "overall_pass_rate": round(result.overall_pass_rate, 2),
                "duration_ms": result.duration_ms
            },
            "rule_results": [
                {
                    "rule_id": rr.rule_id,
                    "rule_name": _rule_names.get(rr.rule_id, rr.rule_id),
                    "passed": rr.passed,
                    "records_checked": rr.records_checked,
                    "records_failed": rr.records_failed,
                    "passed_count": rr.records_checked - rr.records_failed,
                    "total_checked": rr.records_checked,
                    "error": rr.error,
                    "failure_sample_count": len(rr.failure_samples)
                }
                for rr in result.rule_results
            ]
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error("Failed to execute rule set: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/executions", summary="List executions")
async def list_executions(
    rule_set_id: Optional[str] = None,
    status: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    """List rule set executions."""
    try:
        query = db.query(RuleSetExecution)
        
        if rule_set_id:
            query = query.filter(RuleSetExecution.rule_set_id == rule_set_id)
        if status:
            try:
                normalized_status = ExecutionStatus(status).value
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=f"Invalid status: {status}") from exc
            query = query.filter(RuleSetExecution.status == normalized_status)
        
        total = query.count()
        executions = query.order_by(RuleSetExecution.created_at.desc()).offset(skip).limit(limit).all()
        
        return {
            "items": [
                {
                    "id": e.id,
                    "rule_set_id": e.rule_set_id,
                    "rule_set_name": e.rule_set.name if getattr(e, "rule_set", None) else None,
                    "status": e.status,
                    "total_rules": e.total_rules,
                    "rules_passed": e.rules_passed,
                    "rules_failed": e.rules_failed,
                    "total_records": (e.total_records_checked if e.total_records_checked is not None else e.record_count) or 0,
                    "total_failures": e.total_failures,
                    "pass_rate": float(e.overall_pass_rate or 0.0),
                    "overall_pass_rate": float(e.overall_pass_rate or 0.0),
                    "duration_ms": e.duration_ms,
                    "duration_seconds": (float(e.duration_ms) / 1000.0) if e.duration_ms is not None else None,
                    "started_at": (e.started_at or e.created_at).isoformat() if (e.started_at or e.created_at) else None,
                    "completed_at": e.completed_at.isoformat() if e.completed_at else None,
                    "error_message": e.error_message,
                }
                for e in executions
            ],
            "total": total,
            "skip": skip,
            "limit": limit
        }
    except Exception as e:
        logger.error("Failed to list executions: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/executions/{execution_id}", summary="Get execution details")
async def get_execution(execution_id: str, db: Session = Depends(get_db)):
    """Get execution details with rule results."""
    try:
        execution = db.query(RuleSetExecution).filter(RuleSetExecution.id == execution_id).first()
        
        if not execution:
            raise HTTPException(status_code=404, detail="Execution not found")
        
        rule_executions = db.query(RuleExecution).filter(RuleExecution.set_execution_id == execution_id).all()
        
        # Build rule name lookup
        _rule_name_map = {}
        rule_ids = [re.rule_id for re in rule_executions if re.rule_id]
        if rule_ids:
            _rules = db.query(Rule.id, Rule.name).filter(Rule.id.in_(rule_ids)).all()
            _rule_name_map = {r.id: r.name for r in _rules}

        _total_records = (execution.total_records_checked if execution.total_records_checked is not None
                          else getattr(execution, 'record_count', None)) or 0

        return {
            "id": execution.id,
            "rule_set_id": execution.rule_set_id,
            "rule_set_name": execution.rule_set.name if getattr(execution, "rule_set", None) else None,
            "status": execution.status,
            # Top-level convenience fields for frontend
            "total_records": _total_records,
            "pass_rate": float(execution.overall_pass_rate or 0.0),
            "overall_pass_rate": float(execution.overall_pass_rate or 0.0),
            "duration_ms": execution.duration_ms,
            "duration_seconds": round(float(execution.duration_ms) / 1000.0, 3) if execution.duration_ms else None,
            "summary": {
                "total_rules": execution.total_rules,
                "rules_passed": execution.rules_passed,
                "rules_failed": execution.rules_failed,
                "rules_skipped": execution.rules_skipped,
                "rules_error": execution.rules_error,
                "total_records": _total_records,
                "total_failures": execution.total_failures,
                "overall_pass_rate": float(execution.overall_pass_rate or 0.0),
                "duration_ms": execution.duration_ms
            },
            "started_at": (execution.started_at or execution.created_at).isoformat() if (execution.started_at or execution.created_at) else None,
            "completed_at": execution.completed_at.isoformat() if execution.completed_at else None,
            "error_message": execution.error_message,
            "rule_results": [
                {
                    "id": re.id,
                    "rule_id": re.rule_id,
                    "rule_name": _rule_name_map.get(re.rule_id, re.rule_id),
                    "status": re.status,
                    "passed": (re.records_failed or 0) == 0 and re.status != ExecutionStatus.ERROR.value,
                    "records_checked": re.records_checked,
                    "records_passed": re.records_passed,
                    "records_failed": re.records_failed,
                    "passed_count": re.records_passed or 0,
                    "failed_count": re.records_failed or 0,
                    "total_checked": re.records_checked or 0,
                    "pass_rate": re.pass_rate,
                    "duration_ms": re.duration_ms,
                    "error_message": re.error_message,
                    "failure_samples": re.failure_samples,
                    "failure_summary": re.failure_summary,
                }
                for re in rule_executions
            ]
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get execution: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# QUARANTINE ENDPOINTS
# ============================================================================

@router.get("/quarantine", summary="List quarantined records")
async def list_quarantine(
    rule_set_id: Optional[str] = None,
    rule_id: Optional[str] = None,
    resolved: Optional[bool] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """List quarantined records."""
    try:
        query = db.query(QuarantineRecord)

        # rule_set_id is accepted for API compatibility, but the current
        # QuarantineRecord model does not store it directly.
        _ = rule_set_id
        if rule_id:
            query = query.filter(QuarantineRecord.rule_id == rule_id)
        if resolved is not None:
            if resolved:
                query = query.filter(QuarantineRecord.resolved_at.isnot(None))
            else:
                query = query.filter(QuarantineRecord.resolved_at.is_(None))
        
        total = query.count()
        records = query.order_by(QuarantineRecord.created_at.desc()).offset(skip).limit(limit).all()
        
        return {
            "items": [
                {
                    "id": q.id,
                    "rule_id": q.rule_id,
                    "rule_name": q.rule.name if getattr(q, "rule", None) else None,
                    "record_id": q.source_record_id or q.id,
                    "entity_type": q.source_table,
                    "quarantine_reason": q.failure_reason,
                    "status": q.status,
                    "quarantined_at": (q.created_at or datetime.now(timezone.utc)).isoformat(),
                    "resolved_at": q.resolved_at.isoformat() if q.resolved_at else None,
                    "resolved_by": q.resolved_by,
                    "resolution_notes": q.resolution_notes,
                    "severity": q.severity,
                    "source_table": q.source_table,
                    "source_record_id": q.source_record_id,
                }
                for q in records
            ],
            "total": total,
            "skip": skip,
            "limit": limit
        }
    except Exception as e:
        logger.error("Failed to list quarantine: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/quarantine/{quarantine_id}/resolve", summary="Resolve quarantine record")
async def resolve_quarantine(
    quarantine_id: str,
    request: QuarantineResolutionRequest,
    resolved_by: str = "system",
    db: Session = Depends(get_db)
):
    """Resolve a quarantined record."""
    try:
        record = db.query(QuarantineRecord).filter(QuarantineRecord.id == quarantine_id).first()
        
        if not record:
            raise HTTPException(status_code=404, detail="Quarantine record not found")

        if record.resolved_at:
            raise HTTPException(status_code=400, detail="Record already resolved")

        # Minimal resolution implementation aligned to the current DB model.
        # Store the operator notes and mark the record resolved.
        record.resolution_notes = request.resolution_notes
        record.resolved_at = datetime.now(timezone.utc)
        record.resolved_by = resolved_by
        record.status = "resolved"
        
        db.commit()
        
        return {
            "id": quarantine_id,
            "message": "Quarantine record resolved"
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error("Failed to resolve quarantine: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# UTILITY ENDPOINTS
# ============================================================================

@router.post("/validate-expression", summary="Validate rule expression")
async def validate_expression(
    expression: str = Body(..., embed=True),
    expression_type: str = Body(default="python", embed=True),
    test_data: dict = Body(default={}, embed=True)
):
    """Validate a rule expression against test data."""
    try:
        # Today we only support validation of Python expressions.
        # The UI may show other languages for future roadmap; fail fast with a clear message.
        if (expression_type or "python").lower() != "python":
            return {
                "valid": False,
                "result": None,
                "error": f"Expression type '{expression_type}' is not supported for validation yet. Only 'python' is supported.",
                "expression": expression,
                "expression_type": expression_type,
            }

        engine = RuleEngine()
        from services.rule_engine import RuleContext
        
        ctx = RuleContext(record=test_data)
        success, result, error = engine.evaluator.evaluate(expression, ctx.to_eval_context())
        
        return {
            "valid": success,
            "result": result if success else None,
            "error": error,
            "expression": expression,
            "expression_type": expression_type,
        }
    except Exception as e:
        return {
            "valid": False,
            "result": None,
            "error": str(e),
            "expression": expression,
            "expression_type": expression_type,
        }


@router.get("/hierarchy/{rule_set_id}", summary="Get rule hierarchy")
async def get_rule_hierarchy(rule_set_id: str, db: Session = Depends(get_db)):
    """Get the hierarchical structure of rules in a rule set."""
    try:
        rules = db.query(Rule).filter(
            Rule.rule_set_id == rule_set_id,
            Rule.status != RuleStatus.DELETED.value
        ).order_by(Rule.sequence_order).all()
        
        # Build tree structure
        rule_map = {r.id: {
            "id": r.id,
            "name": r.name,
            "level": r.level,
            "severity": r.severity,
            "expression": r.expression[:50] + "..." if len(r.expression) > 50 else r.expression,
            "children": []
        } for r in rules}
        
        roots = []
        for r in rules:
            if r.parent_rule_id and r.parent_rule_id in rule_map:
                rule_map[r.parent_rule_id]["children"].append(rule_map[r.id])
            else:
                roots.append(rule_map[r.id])
        
        return {
            "rule_set_id": rule_set_id,
            "hierarchy": roots,
            "total_rules": len(rules)
        }
    except Exception as e:
        logger.error("Failed to get hierarchy: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{rule_id}", summary="Get rule details")
async def get_rule(rule_id: str, db: Session = Depends(get_db)):
    """Get a single rule by ID."""
    try:
        rule = db.query(Rule).filter(Rule.id == rule_id).first()

        if not rule:
            raise HTTPException(status_code=404, detail="Rule not found")

        return {
            "id": rule.id,
            "rule_set_id": rule.rule_set_id,
            "name": rule.name,
            "description": rule.description,
            "level": rule.level,
            "severity": rule.severity,
            "expression": rule.expression,
            "expression_type": rule.expression_language,
            "action_on_fail": rule.action_on_fail,
            "transformation_expression": rule.transformation_logic,
            "parent_rule_id": rule.parent_rule_id,
            "dependency_condition": rule.dependency_condition,
            "sequence_order": rule.sequence_order,
            "status": rule.status,
            "parameters": rule.parameters,
            "created_at": rule.created_at.isoformat() if rule.created_at else None,
            "updated_at": rule.updated_at.isoformat() if rule.updated_at else None,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get rule: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{rule_id}", summary="Update a rule")
async def update_rule(rule_id: str, data: RuleUpdate, db: Session = Depends(get_db)):
    """Update a rule."""
    try:
        rule = db.query(Rule).filter(Rule.id == rule_id).first()

        if not rule:
            raise HTTPException(status_code=404, detail="Rule not found")

        update_data = data.model_dump(exclude_unset=True)

        # Map Pydantic field names to SQLAlchemy model field names
        field_mapping = {
            'expression_type': 'expression_language',
            'transformation_expression': 'transformation_logic',
        }

        for key, value in update_data.items():
            db_key = field_mapping.get(key, key)
            setattr(rule, db_key, value)

        rule.updated_at = datetime.now(timezone.utc)
        db.commit()

        return {"message": "Rule updated successfully", "id": rule_id}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error("Failed to update rule: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{rule_id}", summary="Delete a rule")
async def delete_rule(
    rule_id: str,
    hard_delete: bool = False,
    db: Session = Depends(get_db)
):
    """Delete a rule (soft delete by default)."""
    try:
        rule = db.query(Rule).filter(Rule.id == rule_id).first()

        if not rule:
            raise HTTPException(status_code=404, detail="Rule not found")

        if hard_delete:
            db.delete(rule)
        else:
            rule.status = RuleStatus.DELETED.value
            rule.updated_at = datetime.now(timezone.utc)

        db.commit()

        return {"message": "Rule deleted successfully", "id": rule_id}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error("Failed to delete rule: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
