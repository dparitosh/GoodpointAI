"""
Rule Composition API Router - Advanced rule composition endpoints

Exposes:
- Composite rule management (CRUD)
- Rule template management
- Rule group management
- Rule composition validation and optimization
"""

import logging
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from core.db_session import get_db
from models.rule_composition_models import (
    CompositeRuleCreate, CompositeRuleUpdate, CompositeRule,
    RuleTemplateCreate, RuleTemplate, RuleTemplateInstance,
    RuleGroupCreate, RuleGroupUpdate, RuleGroup,
    RuleCompositionValidation, RuleOptimization,
    RuleOperator
)
from services.rule_composition_service import (
    CompositeRuleRepository, RuleTemplateRepository, RuleGroupRepository,
    RuleCompositionValidator, RuleComposer
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/rules/composition", tags=["Rules - Composition"])


# ============================================================================
# Composite Rule Endpoints
# ============================================================================

@router.post("/composite", response_model=CompositeRule)
async def create_composite_rule(
    request: CompositeRuleCreate,
    db: Session = Depends(get_db)
):
    """
    Create a composite rule combining multiple rules with logical operators
    
    Example:
    ```json
    {
        "id": "rule_group_1",
        "name": "Data Quality Group 1",
        "rule_ids": ["rule_1", "rule_2", "rule_3"],
        "operator": "and",
        "severity": "high"
    }
    ```
    
    Operators:
    - **and**: All rules must pass
    - **or**: At least one rule must pass
    - **not**: Single rule must fail
    - **xor**: Exactly one rule must pass
    """
    try:
        with CompositeRuleRepository(db) as repo:
            return repo.create(request)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating composite rule: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/composite/{rule_id}", response_model=CompositeRule)
async def get_composite_rule(
    rule_id: str,
    db: Session = Depends(get_db)
):
    """Get a composite rule by ID"""
    with CompositeRuleRepository(db) as repo:
        rule = repo.read(rule_id)
        if not rule:
            raise HTTPException(status_code=404, detail="Composite rule not found")
        return rule


@router.get("/composite", response_model=List[CompositeRule])
async def list_composite_rules(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    severity: Optional[str] = None,
    enabled_only: bool = False,
    db: Session = Depends(get_db)
):
    """List composite rules with optional filtering"""
    with CompositeRuleRepository(db) as repo:
        return repo.list(
            skip=skip,
            limit=limit,
            severity=severity,
            enabled_only=enabled_only
        )


@router.put("/composite/{rule_id}", response_model=CompositeRule)
async def update_composite_rule(
    rule_id: str,
    updates: CompositeRuleUpdate,
    db: Session = Depends(get_db)
):
    """Update a composite rule"""
    try:
        with CompositeRuleRepository(db) as repo:
            rule = repo.update(rule_id, updates)
            if not rule:
                raise HTTPException(status_code=404, detail="Composite rule not found")
            return rule
    except Exception as e:
        logger.error(f"Error updating composite rule: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/composite/{rule_id}")
async def delete_composite_rule(
    rule_id: str,
    db: Session = Depends(get_db)
):
    """Delete a composite rule"""
    try:
        with CompositeRuleRepository(db) as repo:
            if not repo.delete(rule_id):
                raise HTTPException(status_code=404, detail="Composite rule not found")
            return {"message": f"Composite rule '{rule_id}' deleted"}
    except Exception as e:
        logger.error(f"Error deleting composite rule: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Rule Template Endpoints
# ============================================================================

@router.post("/templates", response_model=RuleTemplate)
async def create_rule_template(
    request: RuleTemplateCreate,
    db: Session = Depends(get_db)
):
    """
    Create a reusable rule template
    
    Templates enable standardized rule patterns for common quality checks.
    
    Example:
    ```json
    {
        "id": "completeness_check",
        "name": "Completeness Check",
        "category": "data_quality",
        "rule_type": "completeness",
        "template_definition": {
            "condition": {
                "operator": "not_null",
                "field": "{field_name}"
            }
        },
        "parameters": ["field_name"],
        "example_config": {
            "field_name": "part_number"
        }
    }
    ```
    """
    try:
        with RuleTemplateRepository(db) as repo:
            return repo.create(request)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating template: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/templates/{template_id}", response_model=RuleTemplate)
async def get_rule_template(
    template_id: str,
    db: Session = Depends(get_db)
):
    """Get a rule template by ID"""
    with RuleTemplateRepository(db) as repo:
        template = repo.read(template_id)
        if not template:
            raise HTTPException(status_code=404, detail="Template not found")
        return template


@router.get("/templates/category/{category}", response_model=List[RuleTemplate])
async def list_templates_by_category(
    category: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db)
):
    """List rule templates by category"""
    with RuleTemplateRepository(db) as repo:
        return repo.list_by_category(category, skip, limit)


@router.get("/templates/type/{rule_type}", response_model=List[RuleTemplate])
async def list_templates_by_type(
    rule_type: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db)
):
    """List rule templates by type (completeness, validity, etc.)"""
    with RuleTemplateRepository(db) as repo:
        return repo.list_by_type(rule_type, skip, limit)


@router.get("/templates", response_model=List[RuleTemplate])
async def list_all_rule_templates(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db)
):
    """List all rule templates"""
    with RuleTemplateRepository(db) as repo:
        return repo.list_all(skip, limit)


# ============================================================================
# Rule Group Endpoints
# ============================================================================

@router.post("/groups", response_model=RuleGroup)
async def create_rule_group(
    request: RuleGroupCreate,
    db: Session = Depends(get_db)
):
    """
    Create a rule group for organizing related rules
    
    Groups enable executing multiple rules together with priority ordering.
    
    Example:
    ```json
    {
        "id": "data_quality_group",
        "name": "Data Quality Checks",
        "rule_ids": ["rule_1", "rule_2", "rule_3"],
        "priority": 100
    }
    ```
    """
    try:
        with RuleGroupRepository(db) as repo:
            return repo.create(request)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating rule group: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/groups/{group_id}", response_model=RuleGroup)
async def get_rule_group(
    group_id: str,
    db: Session = Depends(get_db)
):
    """Get a rule group by ID"""
    with RuleGroupRepository(db) as repo:
        group = repo.read(group_id)
        if not group:
            raise HTTPException(status_code=404, detail="Rule group not found")
        return group


@router.get("/groups", response_model=List[RuleGroup])
async def list_rule_groups(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    enabled_only: bool = False,
    order_by_priority: bool = True,
    db: Session = Depends(get_db)
):
    """List rule groups with optional filtering"""
    with RuleGroupRepository(db) as repo:
        return repo.list(
            skip=skip,
            limit=limit,
            enabled_only=enabled_only,
            order_by_priority=order_by_priority
        )


@router.put("/groups/{group_id}", response_model=RuleGroup)
async def update_rule_group(
    group_id: str,
    updates: RuleGroupUpdate,
    db: Session = Depends(get_db)
):
    """Update a rule group"""
    try:
        with RuleGroupRepository(db) as repo:
            group = repo.update(group_id, updates)
            if not group:
                raise HTTPException(status_code=404, detail="Rule group not found")
            return group
    except Exception as e:
        logger.error(f"Error updating rule group: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/groups/{group_id}")
async def delete_rule_group(
    group_id: str,
    db: Session = Depends(get_db)
):
    """Delete a rule group"""
    try:
        with RuleGroupRepository(db) as repo:
            if not repo.delete(group_id):
                raise HTTPException(status_code=404, detail="Rule group not found")
            return {"message": f"Rule group '{group_id}' deleted"}
    except Exception as e:
        logger.error(f"Error deleting rule group: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Validation & Optimization Endpoints
# ============================================================================

@router.post("/validate", response_model=RuleCompositionValidation)
async def validate_composition(
    rule_ids: List[str] = Query(..., description="IDs of rules to validate"),
    operator: RuleOperator = Query(RuleOperator.AND, description="Composition operator")
):
    """
    Validate rule composition logic
    
    Checks:
    - Rule count vs operator compatibility
    - No circular dependencies
    - Acceptable complexity level
    - Performance impact
    
    Returns validation errors, warnings, and recommendations.
    """
    validator = RuleCompositionValidator()
    return validator.validate_composite_rule(rule_ids, operator)


@router.post("/optimize", response_model=RuleOptimization)
async def optimize_composition(
    rule_ids: List[str] = Query(..., description="IDs of rules to optimize"),
    operator: RuleOperator = Query(RuleOperator.AND, description="Composition operator")
):
    """
    Optimize rule composition for performance
    
    Suggests optimizations like:
    - De Morgan's law simplifications
    - Short-circuit evaluation order
    - Rule reordering by selectivity
    
    Returns optimization suggestions with estimated performance gains.
    """
    composer = RuleComposer()
    return composer.optimize_composition(rule_ids, operator)


# ============================================================================
# Health Check
# ============================================================================

@router.get("/health")
async def composition_health():
    """Health check for rule composition module"""
    return {
        "status": "healthy",
        "module": "rule_composition",
        "features": [
            "composite_rules",
            "rule_templates",
            "rule_groups",
            "composition_validation",
            "rule_optimization"
        ]
    }
