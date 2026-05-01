"""
Rule Engine API Router

Endpoints for rule set management and rule execution.
"""

import logging
import uuid
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.db_session import get_db
from models.rule_engine_models import RuleSet, Rule, RuleSetExecution, ExecutionStatus
from models.quality_models import DataQualityRule
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


# ── Wizard → Backend rule persistence ─────────────────────────────────────

class WizardRuleItem(BaseModel):
    """Single rule from WizardRuleEngine (frontend shape)."""
    id: str
    phase: str                          # pre | quality | post
    name: str = ""
    field: str = "*"
    condition: str = ""
    condition_value: str = ""
    action: str = ""
    action_value: str = ""
    enabled: bool = True


class WizardRuleSaveRequest(BaseModel):
    """Persist a set of wizard rules as a backend rule_set."""
    workflow_name: str = "Wizard Rules"
    workflow_id: Optional[str] = None
    rules: List[WizardRuleItem]


# Mapping from wizard condition strings to Python expression templates.
# `{field}` and `{value}` are placeholders filled at save time.
_CONDITION_EXPR_MAP: Dict[str, str] = {
    "IS_NULL":          "is_empty(record.get('{field}'))",
    "IS_NOT_NULL":      "not is_empty(record.get('{field}'))",
    "IS_EMPTY":         "is_empty(str(record.get('{field}', '')))",
    "IS_NOT_UNIQUE":    "len([r for r in dataset if r.get('{field}') == record.get('{field}')]) > 1",
    "MATCHES_REGEX":    "matches_regex(str(record.get('{field}', '')), r'{value}')",
    "FAILS_REGEX":      "not matches_regex(str(record.get('{field}', '')), r'{value}')",
    "NOT_IN_LIST":      "record.get('{field}') not in [{value}]",
    "OUT_OF_RANGE":     "not in_range(record.get('{field}'), {min}, {max})",
    "BELOW_MIN_LENGTH": "len(str(record.get('{field}', ''))) < {value}",
    "ABOVE_MAX_LENGTH": "len(str(record.get('{field}', ''))) > {value}",
    "CUSTOM":           "{value}",
}

_PHASE_TO_LEVEL: Dict[str, str] = {
    "pre":     "attribute",
    "quality": "entity",
    "post":    "attribute",
}

_PHASE_TO_ACTION: Dict[str, str] = {
    "pre":     "transform",
    "quality": "quarantine",
    "post":    "reject",
}

_WIZARD_ACTION_TO_BACKEND: Dict[str, str] = {
    "SET_DEFAULT":   "transform",
    "SKIP_RECORD":   "reject",
    "COERCE_TYPE":   "transform",
    "TRIM":          "transform",
    "TO_UPPER":      "transform",
    "TO_LOWER":      "transform",
    "REGEX_REPLACE": "transform",
    "REJECT_RECORD": "reject",
    "FLAG_WARNING":  "warn",
    "QUARANTINE":    "quarantine",
    "ROUTE_TO_DLQ":  "quarantine",
    "AUDIT_LOG":     "log",
    "ASSERT":        "reject",
}


def _wizard_rule_to_expression(rule: WizardRuleItem) -> str:
    """Compile a WizardRule condition into a Python expression string."""
    template = _CONDITION_EXPR_MAP.get(rule.condition, "True")
    val = rule.condition_value or ""
    # Handle OUT_OF_RANGE: value should be "min-max" e.g. "0-100"
    if rule.condition == "OUT_OF_RANGE" and "-" in val:
        parts = val.split("-", 1)
        min_v = parts[0].strip() or "0"
        max_v = parts[1].strip() or "9999999"
        return template.replace("{field}", rule.field).replace("{min}", min_v).replace("{max}", max_v)
    return template.replace("{field}", rule.field).replace("{value}", val)


@router.post("/from-wizard", summary="Save wizard rules to backend rule engine")
async def save_wizard_rules(
    request: WizardRuleSaveRequest,
    db: Session = Depends(get_db),
):
    """
    Persist a Migration Wizard's WizardRuleEngine rules as a proper backend
    RuleSet + Rule rows so they survive session reloads and can be executed
    via POST /api/rules/v1/execute.

    Called by the Migration Wizard when entering Step 4 (Validate) so that
    the backend rule engine validates the actual data.

    Returns:
        rule_set_id: str — use this with POST /api/rules/v1/execute
        rules_saved: int
    """
    if not request.rules:
        raise HTTPException(status_code=400, detail="No rules provided")

    rule_set_id = f"wizard_{request.workflow_id or uuid.uuid4().hex[:8]}_{uuid.uuid4().hex[:6]}"
    category = "data_quality"
    context = f"wizard:{request.workflow_name}"

    try:
        # Upsert rule set — if one already exists for this workflow_id reuse it
        existing = None
        if request.workflow_id:
            existing = db.query(RuleSet).filter(
                RuleSet.context == context, RuleSet.is_active == True
            ).first()

        if existing:
            rule_set_id = existing.id
            # Remove old rules so we re-apply the latest wizard state
            for old_rule in (existing.rules or []):
                db.delete(old_rule)
            db.flush()
            rule_set = existing
        else:
            rule_set = RuleSet(
                id=rule_set_id,
                name=f"Wizard: {request.workflow_name}",
                description="Auto-saved from Migration Wizard step 3 rule engine",
                category=category,
                context=context,
                stop_on_critical=True,
                is_active=True,
            )
            db.add(rule_set)
            db.flush()

        saved_count = 0
        for idx, wr in enumerate(request.rules):
            if not wr.enabled:
                continue
            expression = _wizard_rule_to_expression(wr)
            rule = Rule(
                id=f"{rule_set_id}_r{idx:03d}_{wr.id[-6:]}",
                rule_set_id=rule_set_id,
                name=wr.name or f"{wr.phase}:{wr.condition}:{wr.field}",
                description=f"Phase={wr.phase} field={wr.field} action={wr.action}",
                level=_PHASE_TO_LEVEL.get(wr.phase, "attribute"),
                target_field=wr.field if wr.field != "*" else None,
                expression=expression,
                expression_language="python",
                severity="critical" if wr.phase == "quality" else "warning",
                action_on_fail=_WIZARD_ACTION_TO_BACKEND.get(wr.action, _PHASE_TO_ACTION.get(wr.phase, "log")),
                sequence_order=idx,
                enabled=True,
            )
            db.add(rule)
            saved_count += 1

        db.commit()
        logger.info(
            "Saved %d wizard rules as rule_set %s (workflow=%s)",
            saved_count, rule_set_id, request.workflow_name,
        )
        return {"rule_set_id": rule_set_id, "rules_saved": saved_count}

    except Exception as exc:
        db.rollback()
        logger.error("Error saving wizard rules: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


# ── DQ rules → SodaCL checks.yml export ───────────────────────────────────

# Maps dq_rules condition op → SodaCL check template
_SODA_TEMPLATES: Dict[str, str] = {
    "not_null":        "  - missing_count({field}) = 0:\n      name: \"{name}\"\n      fail:\n        when > 0\n",
    "unique":          "  - duplicate_count({field}) = 0:\n      name: \"{name}\"\n      fail:\n        when > 0\n",
    "completeness_pct":"  - missing_percent({field}) < {missing_pct}:\n      name: \"{name}\"\n      fail:\n        when >= {missing_pct}\n",
    "regex":           "  - invalid_count({field}):\n      valid regex: \"{pattern}\"\n      name: \"{name}\"\n      fail:\n        when > 0\n",
    "row_count_gt":    "  - row_count > {min}:\n      name: \"{name}\"\n      fail:\n        when < {min}\n",
    "in_range":        "  - invalid_count({field}):\n      valid min: {min}\n      valid max: {max}\n      name: \"{name}\"\n      fail:\n        when > 0\n",
    "max_length":      "  - max_length({field}) < {max}:\n      name: \"{name}\"\n      warn:\n        when >= {max}\n",
}


def _dq_rule_to_sodacl(rule: DataQualityRule) -> Optional[str]:
    """Convert a single DataQualityRule to a SodaCL check string. Returns None if unsupported."""
    cond = rule.condition or {}
    op = cond.get("op", "")
    field = cond.get("field", "")
    tmpl = _SODA_TEMPLATES.get(op)
    if not tmpl or not field:
        return None

    check = tmpl.replace("{field}", field).replace("{name}", rule.name or rule.id)

    if op == "completeness_pct":
        threshold = float(cond.get("threshold") or 80)
        missing_pct = round(100.0 - threshold, 2)
        check = check.replace("{missing_pct}", str(missing_pct))

    elif op == "regex":
        check = check.replace("{pattern}", str(cond.get("pattern") or ".*"))

    elif op == "row_count_gt":
        check = check.replace("{min}", str(int(cond.get("min") or 1)))

    elif op == "in_range":
        check = check.replace("{min}", str(cond.get("min") or 0))
        check = check.replace("{max}", str(cond.get("max") or 9999999))

    elif op == "max_length":
        check = check.replace("{max}", str(int(cond.get("max") or 8000)))

    return check


@router.get(
    "/dq-rules/checks-yaml",
    response_class=PlainTextResponse,
    summary="Export enabled dq_rules as SodaCL checks.yml",
)
async def export_dq_rules_as_sodacl(
    entity_type: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """
    Generate SodaCL ``checks.yml`` content from the enabled rows in
    the ``dq_rules`` table.  Bridges the custom rule engine and Soda Core.

    Query param:
        entity_type  — filter to a single entity type (part | bom | table).
                       Omit to export all enabled rules.

    Returns:
        Plain-text SodaCL YAML that can be saved as ``scripts/checks.yml``
        and executed with ``soda scan -d graphtrace_pg -c soda_config.yml``.
    """
    q = db.query(DataQualityRule).filter(DataQualityRule.enabled == 1)
    if entity_type:
        q = q.filter(DataQualityRule.entity_type == entity_type)
    rules = q.order_by(DataQualityRule.entity_type, DataQualityRule.id).all()

    if not rules:
        raise HTTPException(status_code=404, detail="No enabled dq_rules found")

    # Group by entity_type → table name
    _ENTITY_TO_TABLE: Dict[str, str] = {
        "part":  "plm_parts",
        "bom":   "plm_bom_items",
        "table": "plm_staged_records",
    }

    lines: list[str] = [
        "# Auto-generated SodaCL checks from dq_rules table",
        "# Generated by GET /api/rules/v1/dq-rules/checks-yaml",
        "# Run: soda scan -d graphtrace_pg -c soda_config.yml checks.yml",
        "",
    ]

    # Group rules by table
    by_table: Dict[str, list[DataQualityRule]] = {}
    for rule in rules:
        table = _ENTITY_TO_TABLE.get(rule.entity_type, f"unknown_{rule.entity_type}")
        by_table.setdefault(table, []).append(rule)

    for table_name, table_rules in by_table.items():
        lines.append(f"checks for {table_name}:")
        lines.append("")
        for rule in table_rules:
            check = _dq_rule_to_sodacl(rule)
            if check:
                lines.append(f"  # Rule id={rule.id} severity={rule.severity}")
                lines.append(check)
            else:
                lines.append(f"  # Skipped (unsupported op): id={rule.id} op={rule.condition.get('op')}")
                lines.append("")

    return "\n".join(lines)
