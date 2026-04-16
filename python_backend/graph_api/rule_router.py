"""
Rule Engine API Router

Endpoints for rule set management and rule execution.
"""

import logging
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.db_session import get_db
from models.rule_engine_models import RuleSet, Rule, RuleSetExecution, ExecutionStatus
from services.rule_execution_service import RuleExecutionService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/rules/v1", tags=["rules-legacy"])


class RuleSetCreateRequest(BaseModel):
    """Create rule set request"""
    id: str
    name: str
    description: Optional[str] = None
    category: str = "general"
    context: Optional[str] = None
    stop_on_critical: bool = True


class RuleCreateRequest(BaseModel):
    """Create rule request"""
    id: str
    rule_set_id: str
    name: str
    description: Optional[str] = None
    level: str = "attribute"
    expression: str
    expression_language: str = "python"
    severity: str = "warning"
    action_on_fail: str = "log"


class RuleExecutionRequest(BaseModel):
    """Execute rule request"""
    rule_set_id: str
    entity_data: Dict[str, Any]
    entity_id: Optional[str] = None


@router.post("/ruleset")
async def create_rule_set(
    request: RuleSetCreateRequest,
    db: Session = Depends(get_db)
):
    """Create a new rule set"""
    try:
        rule_set = RuleSet(
            id=request.id,
            name=request.name,
            description=request.description,
            category=request.category,
            context=request.context,
            stop_on_critical=request.stop_on_critical,
            is_active=True
        )
        db.add(rule_set)
        db.commit()
        logger.info("Created rule set: %s", request.id)
        return {"id": rule_set.id, "name": rule_set.name}
    except Exception as e:
        db.rollback()
        logger.error("Error creating rule set: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/rulesets")
async def list_rule_sets(
    category: Optional[str] = None,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    """List rule sets"""
    try:
        query = db.query(RuleSet)
        if category:
            query = query.filter(RuleSet.category == category)
        rule_sets = query.order_by(RuleSet.created_at.desc()).limit(limit).all()
        return [
            {
                "id": rs.id,
                "name": rs.name,
                "category": rs.category,
                "rule_count": len(rs.rules) if rs.rules else 0,
                "is_active": rs.is_active
            }
            for rs in rule_sets
        ]
    except Exception as e:
        logger.error("Error listing rule sets: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/rule")
async def create_rule(
    request: RuleCreateRequest,
    db: Session = Depends(get_db)
):
    """Create a new rule"""
    try:
        # Validate rule set exists
        rule_set = db.query(RuleSet).filter(RuleSet.id == request.rule_set_id).first()
        if not rule_set:
            raise HTTPException(status_code=404, detail="Rule set not found")

        rule = Rule(
            id=request.id,
            rule_set_id=request.rule_set_id,
            name=request.name,
            description=request.description,
            level=request.level,
            expression=request.expression,
            expression_language=request.expression_language,
            severity=request.severity,
            action_on_fail=request.action_on_fail,
            enabled=True
        )
        db.add(rule)
        db.commit()
        logger.info("Created rule: %s in ruleset %s", request.id, request.rule_set_id)
        return {"id": rule.id, "name": rule.name}
    except Exception as e:
        db.rollback()
        logger.error("Error creating rule: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/execute")
async def execute_rules(
    request: RuleExecutionRequest,
    db: Session = Depends(get_db)
):
    """Execute a rule set against entity data"""
    try:
        service = RuleExecutionService(db)
        result = await service.execute_rule_set(
            rule_set_id=request.rule_set_id,
            entity_data=request.entity_data,
            entity_id=request.entity_id
        )
        return result.to_dict()
    except Exception as e:
        logger.error("Error executing rules: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/ruleset/{rule_set_id}")
async def get_rule_set(
    rule_set_id: str,
    db: Session = Depends(get_db)
):
    """Get rule set details"""
    try:
        rule_set = db.query(RuleSet).filter(RuleSet.id == rule_set_id).first()
        if not rule_set:
            raise HTTPException(status_code=404, detail="Rule set not found")

        return {
            "id": rule_set.id,
            "name": rule_set.name,
            "description": rule_set.description,
            "category": rule_set.category,
            "is_active": rule_set.is_active,
            "rule_count": len(rule_set.rules) if rule_set.rules else 0,
            "rules": [
                {
                    "id": r.id,
                    "name": r.name,
                    "level": r.level,
                    "severity": r.severity,
                    "action_on_fail": r.action_on_fail
                }
                for r in (rule_set.rules or [])
            ]
        }
    except Exception as e:
        logger.error("Error fetching rule set: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/executions/{rule_set_id}")
async def get_rule_executions(
    rule_set_id: str,
    limit: int = 20,
    db: Session = Depends(get_db)
):
    """Get execution history for a rule set"""
    try:
        executions = db.query(RuleSetExecution).filter(
            RuleSetExecution.rule_set_id == rule_set_id
        ).order_by(
            RuleSetExecution.started_at.desc()
        ).limit(limit).all()

        return [
            {
                "id": e.id,
                "started_at": e.started_at.isoformat() if e.started_at else None,
                "completed_at": e.completed_at.isoformat() if e.completed_at else None,
                "status": e.status,
                "passed_count": e.rules_passed,
                "failed_count": e.rules_failed,
                "duration_ms": e.duration_ms
            }
            for e in executions
        ]
    except Exception as e:
        logger.error("Error fetching executions: %s", e)
        raise HTTPException(status_code=500, detail=str(e))
