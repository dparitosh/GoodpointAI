"""
Rule Engine API Router

Endpoints for rule set management and rule execution.
"""

import logging
import re
import json
import uuid
import httpx
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.db_session import get_db
from models.rule_engine_models import RuleSet, Rule, RuleSetExecution
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
        # Bug 9 fix: persist execution history so run-level audit trail is written.
        # record_execution() is a best-effort operation — failure must not mask the result.
        execution_id = str(uuid.uuid4())
        try:
            service.record_execution(request.rule_set_id, execution_id, result)
        except Exception as persist_err:
            logger.warning("Could not persist rule execution record: %s", persist_err)
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
    # IS_NOT_UNIQUE: uses _related.get('all_records') consistent with the UNIQUE
    # system template; the execution context injects _related={}  so NameError
    # never surfaces even when no related records are supplied.
    "IS_NOT_UNIQUE":    "len([r for r in _related.get('all_records', []) if r.get('{field}') == record.get('{field}')]) > 1",
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
    val = rule.condition_value or ""
    field = rule.field or "*"

    # CUSTOM rules with an empty expression body are a no-op — use True so
    # eval() doesn't raise SyntaxError on an empty string.
    if rule.condition == "CUSTOM" and not val.strip():
        return "True"

    # Wildcard field (*) means "any field": generate a collection-level expression.
    if field == "*":
        if rule.condition in ("IS_NULL", "IS_EMPTY"):
            return "any(is_empty(v) for v in record.values())"
        if rule.condition in ("IS_NOT_NULL",):
            return "all(is_not_null(v) for v in record.values())"
        # Other conditions on * are not meaningful per-record; treat as passing.
        return "True"

    template = _CONDITION_EXPR_MAP.get(rule.condition, "True")

    # Handle OUT_OF_RANGE: value can be "0-100" or "-10-100" (negative min).
    # Use a regex to parse so that a leading minus on the min bound is captured
    # correctly (plain split("-", 1) would lose it).
    if rule.condition == "OUT_OF_RANGE":
        import re as _re_range
        m = _re_range.match(r'^(-?\d+(?:\.\d+)?)[-–](-?\d+(?:\.\d+)?)$', val.strip())
        if m:
            min_v, max_v = m.group(1), m.group(2)
        elif "-" in val:
            # Fallback: legacy split — works for non-negative min values
            parts = val.split("-", 1)
            min_v = parts[0].strip() or "0"
            max_v = parts[1].strip() or "9999999"
        else:
            # No range separator — fall through to placeholder-safety net below
            min_v, max_v = None, None
        if min_v is not None and max_v is not None:
            return template.replace("{field}", field).replace("{min}", min_v).replace("{max}", max_v)

    # For regex conditions, validate that the user-supplied value is a legal
    # regex pattern (catches typos and ReDoS attempts).  re.escape() must NOT
    # be applied here because it would destroy intentional regex metacharacters
    # like `^[A-Z]+$` — the user is deliberately writing a regex pattern.
    effective_val = val
    if rule.condition in ("MATCHES_REGEX", "FAILS_REGEX"):
        import re as _re
        try:
            _re.compile(val)        # validate syntax; raises re.error if invalid
        except _re.error:
            # Invalid regex — treat as a literal string match to avoid SyntaxError
            effective_val = _re.escape(val)
            logger.warning(
                "Rule '%s' has invalid regex pattern '%s'; treating as literal string",
                rule.name, val,
            )

    expr = template.replace("{field}", field).replace("{value}", effective_val)
    # Safety net: if any placeholder is still unreplaced (e.g. {min}, {max} for
    # OUT_OF_RANGE without a dash, or {value} for length checks with empty value)
    # the expression would cause a SyntaxError in eval(). Fall back to no-op.
    if "{" in expr:
        logger.warning(
            "Rule '%s' has unreplaced placeholder in expression — defaulting to True: %s",
            rule.condition, expr,
        )
        return "True"
    return expr


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
                RuleSet.context == context, RuleSet.is_active
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
                # quality rules flag/quarantine individual records (warning);
                # pre/post rules gate entry/exit of the pipeline (critical).
                severity="warning" if wr.phase == "quality" else "critical",
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


# ── NLP → Rule Engine ─────────────────────────────────────────────────────────

_NLP_RULE_SYSTEM_PROMPT = """\
You are a Rule Engine Configuration Assistant for a PLM/ETL data migration platform.
The user describes a data quality rule in natural language. Parse the description and \
produce a JSON array of one or more wizard rule objects.

Each rule object MUST have exactly these fields:
  name            : concise rule label (≤40 chars)
  phase           : "pre" | "quality" | "post"
  field           : field name from the available_fields list, or "*" for all fields
  condition       : one of the valid conditions for the phase (see below)
  condition_value : string value if the condition requires one (empty string otherwise)
  action          : one of the valid actions for the phase (see below)
  action_value    : string value if the action requires one (empty string otherwise)
  enabled         : true
  description     : one sentence explaining what this rule does

VALID CONDITIONS per phase:
  pre:     IS_NULL | IS_EMPTY | MATCHES_REGEX | NOT_IN_LIST | CUSTOM
  quality: IS_NULL | IS_NOT_UNIQUE | OUT_OF_RANGE | FAILS_REGEX | BELOW_MIN_LENGTH | ABOVE_MAX_LENGTH | CUSTOM
  post:    IS_NULL | OUT_OF_RANGE | MATCHES_REGEX | CUSTOM

VALID ACTIONS per phase:
  pre:     SET_DEFAULT | SKIP_RECORD | COERCE_TYPE | TRIM | TO_UPPER | TO_LOWER | REGEX_REPLACE
  quality: REJECT_RECORD | FLAG_WARNING | SET_DEFAULT | QUARANTINE
  post:    REJECT_RECORD | FLAG_WARNING | ROUTE_TO_DLQ | AUDIT_LOG | ASSERT

RULES:
- Match the field name exactly to one from available_fields (case-sensitive)
- "must not be empty/null/blank"  → condition=IS_NULL, phase=pre or quality
- "must be unique"                → condition=IS_NOT_UNIQUE, phase=quality
- "must be one of X, Y, Z"       → condition=NOT_IN_LIST, condition_value="X,Y,Z", phase=pre
- "must match pattern X"         → condition=MATCHES_REGEX, condition_value=<pattern>
- "must be between N and M"      → condition=OUT_OF_RANGE, condition_value="N-M"
- "must be at least N chars"     → condition=BELOW_MIN_LENGTH, condition_value="N"
- "must not exceed N chars"      → condition=ABOVE_MAX_LENGTH, condition_value="N"
- Compound sentences produce multiple rule objects (one per constraint)
- If no matching field is found, use "*" and note it in description
- Return ONLY a valid JSON array, no explanatory text outside the JSON
"""


class NlpToRuleRequest(BaseModel):
    description: str
    available_fields: Optional[List[str]] = None
    field_types: Optional[Dict[str, str]] = None
    context_hint: Optional[str] = None      # e.g. "PLM parts data, pre-transform phase"
    llm_provider: Optional[str] = "openai"


@router.post("/nlp-to-rule")
async def nlp_to_rule(request: NlpToRuleRequest):
    """Convert a natural language rule description into one or more wizard rule objects.

    The LLM interprets the description and maps it to valid condition/action pairs
    supported by the WizardRuleEngine.  Each returned object is ready to be appended
    directly to ``wizardData.rules`` in the frontend without further transformation.

    On LLM unavailability, falls back to a best-effort keyword parser so the endpoint
    always returns something useful.
    """
    import os
    backend_url = os.getenv("GRAPH_TRACE_BACKEND_URL", "http://127.0.0.1:8011")

    # Build context block for the LLM
    ctx_parts = []
    if request.available_fields:
        ctx_parts.append(f"available_fields: {json.dumps(request.available_fields)}")
    if request.field_types:
        ctx_parts.append(f"field_types: {json.dumps(request.field_types)}")
    if request.context_hint:
        ctx_parts.append(f"context: {request.context_hint}")

    user_content = request.description
    if ctx_parts:
        user_content = "\n".join(ctx_parts) + "\n\ndescription: " + request.description

    # ── Try LLM first ─────────────────────────────────────────────────────────
    rules_from_llm = None
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(
                f"{backend_url}/api/llm/chat",
                params={"provider": request.llm_provider or "openai"},
                json={
                    "messages": [
                        {"role": "system", "content": _NLP_RULE_SYSTEM_PROMPT},
                        {"role": "user",   "content": user_content},
                    ],
                    "temperature": 0.1,
                    "max_tokens": 800,
                },
            )
            if resp.is_success:
                raw = resp.json().get("response", "")
                raw = re.sub(r"```(?:json)?", "", raw).strip().strip("`").strip()
                m = re.search(r"\[.*\]", raw, re.DOTALL)
                if m:
                    parsed = json.loads(m.group(0))
                    if isinstance(parsed, list) and parsed:
                        rules_from_llm = parsed
    except Exception as exc:
        logger.debug("LLM nlp-to-rule unavailable: %s", exc)

    if rules_from_llm:
        # Assign stable IDs and ensure required fields are present
        sanitised = []
        for r in rules_from_llm:
            if not isinstance(r, dict):
                continue
            sanitised.append({
                "id":              f"nlp-{uuid.uuid4().hex[:10]}",
                "name":            str(r.get("name", "AI Rule"))[:80],
                "phase":           r.get("phase", "quality") if r.get("phase") in ("pre", "quality", "post") else "quality",
                "field":           r.get("field", "*"),
                "condition":       r.get("condition", "IS_NULL"),
                "condition_value": str(r.get("condition_value") or ""),
                "action":          r.get("action", "FLAG_WARNING"),
                "action_value":    str(r.get("action_value") or ""),
                "enabled":         True,
                "description":     str(r.get("description", "")),
                "source":          "ai",
            })
        return {
            "rules":          sanitised,
            "interpretation": f"AI parsed {len(sanitised)} rule(s) from your description.",
            "ai_powered":     True,
        }

    # ── Keyword fallback — always works without LLM ───────────────────────────
    fallback_rules = _keyword_parse_rule(
        request.description, request.available_fields or []
    )
    return {
        "rules":          fallback_rules,
        "interpretation": "Parsed using keyword matching (LLM unavailable).",
        "ai_powered":     False,
    }


def _keyword_parse_rule(description: str, available_fields: List[str]) -> List[Dict[str, Any]]:
    """Best-effort keyword parser — no LLM required.

    Handles the most common natural language patterns:
    - "X must not be empty/null"
    - "X must be unique"
    - "X must be one of A, B, C"
    - "X must match pattern /regex/"
    - "X must be between N and M"
    - "X must have at least N characters"
    - "X must not exceed N characters"
    """
    d = description.lower()
    rules: List[Dict[str, Any]] = []

    # Find field name — first token that matches an available field (case-insensitive)
    detected_field = "*"
    for f in available_fields:
        if f.lower() in d:
            detected_field = f
            break

    def _make(name: str, phase: str, condition: str, cond_val: str,
              action: str, action_val: str, desc: str) -> Dict[str, Any]:
        return {
            "id":              f"nlp-{uuid.uuid4().hex[:10]}",
            "name":            name,
            "phase":           phase,
            "field":           detected_field,
            "condition":       condition,
            "condition_value": cond_val,
            "action":          action,
            "action_value":    action_val,
            "enabled":         True,
            "description":     desc,
            "source":          "keyword_fallback",
        }

    if any(kw in d for kw in ("not be empty", "not be null", "not be blank", "must not be empty", "required", "non-null", "non-empty")):
        rules.append(_make(
            f"Completeness — {detected_field}", "quality", "IS_NULL", "",
            "REJECT_RECORD", "", f"Field '{detected_field}' must not be null or empty.",
        ))

    if any(kw in d for kw in ("unique", "must be unique", "no duplicate", "no duplicates")):
        rules.append(_make(
            f"Uniqueness — {detected_field}", "quality", "IS_NOT_UNIQUE", "",
            "REJECT_RECORD", "", f"Field '{detected_field}' must be unique across all records.",
        ))

    m_list = re.search(r"one of[:\s]+([a-zA-Z0-9_\s,|/]+)", d)
    if m_list:
        vals = ",".join(v.strip() for v in re.split(r"[,|]", m_list.group(1)) if v.strip())
        rules.append(_make(
            f"Allowed values — {detected_field}", "pre", "NOT_IN_LIST", vals,
            "SKIP_RECORD", "", f"Field '{detected_field}' must be one of: {vals}.",
        ))

    m_range = re.search(r"between\s+(-?[\d.]+)\s+and\s+(-?[\d.]+)", d)
    if m_range:
        rng = f"{m_range.group(1)}-{m_range.group(2)}"
        rules.append(_make(
            f"Range check — {detected_field}", "quality", "OUT_OF_RANGE", rng,
            "FLAG_WARNING", "", f"Field '{detected_field}' must be in range {rng}.",
        ))

    m_min_len = re.search(r"at least\s+(\d+)\s+char", d)
    if m_min_len:
        rules.append(_make(
            f"Min length — {detected_field}", "quality", "BELOW_MIN_LENGTH", m_min_len.group(1),
            "FLAG_WARNING", "", f"Field '{detected_field}' must be at least {m_min_len.group(1)} characters.",
        ))

    m_max_len = re.search(r"(?:not exceed|no more than|max(?:imum)?)\s+(\d+)\s+char", d)
    if m_max_len:
        rules.append(_make(
            f"Max length — {detected_field}", "quality", "ABOVE_MAX_LENGTH", m_max_len.group(1),
            "FLAG_WARNING", "", f"Field '{detected_field}' must not exceed {m_max_len.group(1)} characters.",
        ))

    m_regex = re.search(r"match(?:es)?\s+(?:pattern|regex|format)?\s*[:/]?\s*([^\s]+)", d)
    if m_regex and m_regex.group(1) not in ("the", "a", "an"):
        rules.append(_make(
            f"Pattern — {detected_field}", "quality", "FAILS_REGEX", m_regex.group(1),
            "FLAG_WARNING", "", f"Field '{detected_field}' must match pattern: {m_regex.group(1)}.",
        ))

    # Generic fallback if nothing matched
    if not rules:
        rules.append(_make(
            f"Custom rule — {detected_field}", "quality", "CUSTOM", "",
            "FLAG_WARNING", "", description,
        ))

    return rules
