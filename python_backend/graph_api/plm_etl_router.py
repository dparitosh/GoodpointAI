"""PLM ETL router (happy path) backed by a single Postgres database.

Design goals:
- No mock/sample/demo data.
- If Postgres isn't configured, return 503.
- Provide a concrete execution path: create run -> stage -> transform -> validate.
- Persist outcomes in Postgres so UI can render real status.
"""

from __future__ import annotations

import json
import os
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from neo4j.exceptions import Neo4jError
from sqlalchemy import text

from core.db_session import DATABASE_URL, get_db
from models.plm_models import PLMBOMItem, PLMIngestionRun, PLMPart, PLMStagedRecord
from models.quality_models import DataQualityResult, DataQualityRule, DataQualityScanReport, DataQualityGateResult

def get_optional_driver(request: Request) -> Any:
    # Optional dependency: do not fail the request if Neo4j isn't configured.
    return getattr(request.app.state, "driver", None)


router = APIRouter(prefix="/api/plm/etl", tags=["PLM - ETL"])


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(tzinfo=None).isoformat()


def _require_postgres() -> None:
    url = (DATABASE_URL or "").strip().lower()
    if not (url.startswith("postgresql:") or url.startswith("postgres:")):
        raise HTTPException(
            status_code=503,
            detail="Postgres is required for PLM ETL. Set DATABASE_URL to a Postgres connection string.",
        )


def _as_str(val: Any) -> Optional[str]:
    if val is None:
        return None
    s = str(val).strip()
    return s or None


def _require_soda() -> Any:
    try:
        from soda.scan import Scan  # type: ignore

        return Scan
    except Exception as exc:  # pylint: disable=broad-exception-caught
        raise HTTPException(
            status_code=503,
            detail="Soda Core is not installed. Install `soda-core-postgres` to use Soda gate endpoints.",
        ) from exc


def _table_exists(db: Session, schema: str, table: str) -> bool:
    row = db.execute(
        text(
            """
            SELECT 1
            FROM information_schema.tables
            WHERE table_schema = :schema
              AND table_name = :table
            LIMIT 1
            """
        ),
        {"schema": schema, "table": table},
    ).fetchone()
    return row is not None


def _qualified_table(schema: str, table: str) -> str:
    # Identifiers validated upstream.
    return f"{schema}.{table}"


def _list_columns(db: Session, schema: str, table: str) -> List[str]:
    rows = db.execute(
        text(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = :schema
              AND table_name = :table
            ORDER BY ordinal_position
            """
        ),
        {"schema": schema, "table": table},
    ).fetchall()
    return [str(r[0]) for r in rows if r and r[0]]


def _count_rows_for_run(db: Session, qualified_table: str, run_id: str) -> int:
    try:
        row = db.execute(
            text(f"SELECT COUNT(*) FROM {qualified_table} WHERE run_id = :run_id"),
            {"run_id": run_id},
        ).fetchone()
        return int(row[0]) if row else 0
    except Exception:
        # Some tables may not be run-scoped; fall back to total row count.
        row = db.execute(text(f"SELECT COUNT(*) FROM {qualified_table}")).fetchone()
        return int(row[0]) if row else 0


def _issues_from_soda_checks(checks: Any) -> List[Dict[str, Any]]:
    if not isinstance(checks, list):
        return []
    issues: List[Dict[str, Any]] = []
    for c in checks:
        if not isinstance(c, dict):
            continue
        outcome = str(c.get("outcome") or "").strip().lower()
        if outcome in {"fail", "warn"}:
            name = str(c.get("name") or c.get("check") or c.get("definition") or "Soda check").strip()
            severity = str(c.get("severity") or ("high" if outcome == "fail" else "medium")).strip().lower()
            failures = c.get("failures")
            try:
                affected_rows = int(failures) if failures is not None else 0
            except (TypeError, ValueError):
                affected_rows = 0
            issues.append(
                {
                    "issue_id": uuid.uuid4().hex,
                    "rule_id": name,
                    "severity": severity,
                    "description": name,
                    "affected_rows": affected_rows,
                    "affected_columns": [],
                    "sample_values": [],
                    "suggestion": "Review failed Soda checks and fix upstream data",
                }
            )
    return issues


def _score_from_soda_checks(checks: Any) -> float:
    if not isinstance(checks, list) or not checks:
        return 0.0
    passed = 0
    total = 0
    for c in checks:
        if not isinstance(c, dict):
            continue
        total += 1
        outcome = str(c.get("outcome") or "").strip().lower()
        if outcome == "pass":
            passed += 1
    if total <= 0:
        return 0.0
    return float(max(0.0, min(1.0, passed / total)))


def _wrap_sodacl_checks(schema: str, table: str, checks_yaml: str) -> str:
    raw = (checks_yaml or "").rstrip() + "\n"
    if "checks for" in raw:
        return raw
    indented = "\n".join(("  " + line if line.strip() else line) for line in raw.splitlines()).rstrip() + "\n"
    return f"checks for {schema}.{table}:\n{indented}"


def _default_soda_checks_for_table(table: str, run_id: str) -> Optional[str]:
    t = (table or "").strip().lower()
    if t == "plm_parts":
        return (
            "- row_count > 0:\n"
            f"    filter: run_id = '{run_id}'\n"
            "- missing_count(part_number) = 0:\n"
            f"    filter: run_id = '{run_id}'\n"
        )
    if t == "plm_bom_items":
        return (
            "- row_count >= 0:\n"
            f"    filter: run_id = '{run_id}'\n"
            "- missing_count(parent_part_number) = 0:\n"
            f"    filter: run_id = '{run_id}'\n"
            "- missing_count(child_part_number) = 0:\n"
            f"    filter: run_id = '{run_id}'\n"
        )
    return None


class SodaGateScanRequest(BaseModel):
    """Run-scoped Soda gate.

    If checks_yaml is omitted, a minimal deterministic default is used for known PLM tables.
    """

    stage: str = Field(default="transformed", min_length=1)
    checks_yaml: Optional[str] = None
    data_source_name: str = Field(default="postgres", min_length=1)


class SodaGateScanResponse(BaseModel):
    gate_id: str
    run_id: str
    stage: str
    table_name: str
    scan_id: str
    status: str
    overall_score: float
    issues_count: int
    blocked: bool
    timestamp: str


class CreateRunRequest(BaseModel):
    source_system: str = Field(..., min_length=1)
    target_system: str = Field(..., min_length=1)


class CreateRunResponse(BaseModel):
    run_id: str
    status: str
    created_at: str


class StageRecordsRequest(BaseModel):
    object_type: str = Field(..., description="part or bom")
    records: List[Dict[str, Any]] = Field(..., description="Extracted source records")
    source_object_id_field: Optional[str] = Field(
        default=None,
        description="Optional field in each record to store as source_object_id",
    )


class TransformRequest(BaseModel):
    """Define how source payload keys map into canonical tables.

    No default mappings are provided (no demo data). The caller must supply.

    For parts mapping, supported canonical keys:
      part_number, name, description, classification

    For bom mapping, supported canonical keys:
      parent_part_number, child_part_number, quantity
    """

    part_mapping: Optional[Dict[str, str]] = None
    bom_mapping: Optional[Dict[str, str]] = None


class ValidationRunResponse(BaseModel):
    run_id: str
    results_written: int
    timestamp: str


@router.post("/runs", response_model=CreateRunResponse)
async def create_run(payload: CreateRunRequest, db: Session = Depends(get_db)):
    _require_postgres()

    run_id = uuid.uuid4().hex
    row = PLMIngestionRun(
        id=run_id,
        source_system=payload.source_system.strip(),
        target_system=payload.target_system.strip(),
        status="created",
    )
    db.add(row)
    db.commit()

    return CreateRunResponse(run_id=run_id, status=row.status, created_at=_utcnow_iso())


@router.post("/runs/{run_id}/stage")
async def stage_records(run_id: str, payload: StageRecordsRequest, db: Session = Depends(get_db)):
    _require_postgres()

    run = db.get(PLMIngestionRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")

    object_type = payload.object_type.strip().lower()
    if object_type not in {"part", "bom"}:
        raise HTTPException(status_code=400, detail="object_type must be 'part' or 'bom'")

    if not payload.records:
        raise HTTPException(status_code=400, detail="records cannot be empty")

    source_field = (payload.source_object_id_field or "").strip() or None

    rows: List[PLMStagedRecord] = []
    for rec in payload.records:
        if not isinstance(rec, dict):
            continue
        source_object_id = None
        if source_field and source_field in rec:
            source_object_id = _as_str(rec.get(source_field))
        rows.append(
            PLMStagedRecord(
                run_id=run_id,
                object_type=object_type,
                payload=rec,
                source_object_id=source_object_id,
            )
        )

    if not rows:
        raise HTTPException(status_code=400, detail="No valid dict records provided")

    db.add_all(rows)
    run.status = "staged"
    db.commit()

    return {
        "run_id": run_id,
        "staged": len(rows),
        "object_type": object_type,
        "status": run.status,
        "timestamp": _utcnow_iso(),
    }


def _map_record(rec: Dict[str, Any], mapping: Dict[str, str]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for src_key, dest_key in mapping.items():
        if not isinstance(src_key, str) or not isinstance(dest_key, str):
            continue
        val = rec.get(src_key)
        out[dest_key] = val
    return out


@router.post("/runs/{run_id}/transform")
async def transform(run_id: str, payload: TransformRequest, db: Session = Depends(get_db)):
    _require_postgres()

    run = db.get(PLMIngestionRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")

    part_mapping = payload.part_mapping
    bom_mapping = payload.bom_mapping

    if not part_mapping and not bom_mapping:
        raise HTTPException(
            status_code=400,
            detail="Provide part_mapping and/or bom_mapping; no default mappings are provided.",
        )

    staged_parts: List[PLMStagedRecord] = []
    staged_bom: List[PLMStagedRecord] = []
    if part_mapping:
        staged_parts = (
            db.query(PLMStagedRecord)
            .filter(PLMStagedRecord.run_id == run_id, PLMStagedRecord.object_type == "part")
            .all()
        )
    if bom_mapping:
        staged_bom = (
            db.query(PLMStagedRecord)
            .filter(PLMStagedRecord.run_id == run_id, PLMStagedRecord.object_type == "bom")
            .all()
        )

    parts_written = 0
    bom_written = 0

    if part_mapping:
        for row in staged_parts:
            rec_part: Dict[str, Any] = row.payload if isinstance(row.payload, dict) else {}
            mapped = _map_record(rec_part, part_mapping)

            part_number = _as_str(mapped.get("part_number"))
            if not part_number:
                # Skip invalid part rows; validations will catch missing keys on staged data if rule is defined.
                continue

            part = PLMPart(
                run_id=run_id,
                part_number=part_number,
                name=_as_str(mapped.get("name")),
                description=_as_str(mapped.get("description")),
                classification=_as_str(mapped.get("classification")),
                raw=rec_part,
            )
            db.add(part)
            parts_written += 1

        try:
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            # If duplicates exist, we keep the run usable; caller can fix mappings/data and retry.
            raise HTTPException(status_code=409, detail="Duplicate part_number detected for this run") from exc

    if bom_mapping:
        for row in staged_bom:
            rec_bom: Dict[str, Any] = row.payload if isinstance(row.payload, dict) else {}
            mapped = _map_record(rec_bom, bom_mapping)

            parent_pn = _as_str(mapped.get("parent_part_number"))
            child_pn = _as_str(mapped.get("child_part_number"))
            qty_raw = mapped.get("quantity")
            qty = None
            if qty_raw is not None:
                try:
                    qty = float(qty_raw)
                except (TypeError, ValueError):
                    qty = None

            if not parent_pn or not child_pn:
                continue

            item = PLMBOMItem(
                run_id=run_id,
                parent_part_number=parent_pn,
                child_part_number=child_pn,
                quantity=qty,
                raw=rec_bom,
            )
            db.add(item)
            bom_written += 1

        db.commit()

    run.status = "transformed"
    db.commit()

    return {
        "run_id": run_id,
        "parts_written": parts_written,
        "bom_items_written": bom_written,
        "status": run.status,
        "timestamp": _utcnow_iso(),
    }


def _emit_validation_to_neo4j_best_effort(driver: Any, run_id: str, results: List[Dict[str, Any]]) -> None:
    # Best-effort emission; failures must not break API.
    # Keep the payload minimal and deterministic.
    if not driver:
        return

    async def _do() -> None:
        try:
            async with driver.session(database="neo4j") as s:
                await s.run(
                    """
                    MERGE (m:LineageNode {id: $mid})
                    ON CREATE SET m.created_at = $ts
                    SET m.type = 'transformation', m.name = $name
                    """,
                    mid=f"mig:{run_id}",
                    ts=_utcnow_iso(),
                    name=f"Migration {run_id}",
                )

                for r in results:
                    await s.run(
                        """
                        MATCH (m:LineageNode {id: $mid})
                        CREATE (v:ValidationIssue)
                        SET v.run_id = $run_id,
                            v.rule_id = $rule_id,
                            v.status = $status,
                            v.entity_type = $entity_type,
                            v.entity_key = $entity_key,
                            v.message = $message,
                            v.created_at = $ts
                        CREATE (m)-[:HAS_VALIDATION]->(v)
                        """,
                        mid=f"mig:{run_id}",
                        run_id=run_id,
                        rule_id=r.get("rule_id"),
                        status=r.get("status"),
                        entity_type=r.get("entity_type"),
                        entity_key=r.get("entity_key"),
                        message=r.get("message"),
                        ts=_utcnow_iso(),
                    )
        except Neo4jError:
            return

    try:
        import asyncio
        loop = asyncio.get_running_loop()
        loop.create_task(_do())
    except RuntimeError:
        # No loop; ignore.
        return


@router.post("/runs/{run_id}/validate", response_model=ValidationRunResponse)
async def validate_run(
    run_id: str,
    db: Session = Depends(get_db),
    driver: Any = Depends(get_optional_driver),
):
    _require_postgres()

    run = db.get(PLMIngestionRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")

    # Load enabled rules
    rules = db.query(DataQualityRule).filter(DataQualityRule.enabled == 1).all()

    # If no rules are defined, do not fabricate results.
    if not rules:
        run.status = "validated"
        db.commit()
        return ValidationRunResponse(run_id=run_id, results_written=0, timestamp=_utcnow_iso())

    results_written = 0
    emitted_payload: List[Dict[str, Any]] = []

    # Preload parts for referential checks.
    part_numbers = {
        pn for (pn,) in db.query(PLMPart.part_number).filter(PLMPart.run_id == run_id).all() if pn
    }

    for rule in rules:
        cond: Dict[str, Any] = rule.condition if isinstance(rule.condition, dict) else {}
        op = str(cond.get("op") or "").strip().lower()
        field = str(cond.get("field") or "").strip()
        entity_type = (rule.entity_type or "").strip().lower()

        if entity_type not in {"part", "bom"}:
            continue

        if op == "not_null" and field:
            if entity_type == "part":
                rows = db.query(PLMPart).filter(PLMPart.run_id == run_id).all()
                for row in rows:
                    value = getattr(row, field, None)
                    ok = value is not None and str(value).strip() != ""
                    if not ok:
                        res = DataQualityResult(
                            run_id=run_id,
                            rule_id=rule.id,
                            entity_type="part",
                            entity_key=row.part_number,
                            status="fail",
                            message=f"{field} is required",
                            details={"field": field},
                        )
                        db.add(res)
                        results_written += 1
                        emitted_payload.append(
                            {
                                "rule_id": rule.id,
                                "entity_type": "part",
                                "entity_key": row.part_number,
                                "status": "fail",
                                "message": f"{field} is required",
                            }
                        )
            else:
                rows = db.query(PLMBOMItem).filter(PLMBOMItem.run_id == run_id).all()
                for row in rows:
                    value = getattr(row, field, None)
                    ok = value is not None and str(value).strip() != ""
                    if not ok:
                        key = f"{row.parent_part_number}->{row.child_part_number}"
                        res = DataQualityResult(
                            run_id=run_id,
                            rule_id=rule.id,
                            entity_type="bom",
                            entity_key=key,
                            status="fail",
                            message=f"{field} is required",
                            details={"field": field},
                        )
                        db.add(res)
                        results_written += 1
                        emitted_payload.append(
                            {
                                "rule_id": rule.id,
                                "entity_type": "bom",
                                "entity_key": key,
                                "status": "fail",
                                "message": f"{field} is required",
                            }
                        )

        elif op == "bom_refs_parts":
            # Ensure all BOM parent/child part_numbers exist in parts table.
            rows = db.query(PLMBOMItem).filter(PLMBOMItem.run_id == run_id).all()
            for row in rows:
                missing: List[str] = []
                if row.parent_part_number not in part_numbers:
                    missing.append("parent")
                if row.child_part_number not in part_numbers:
                    missing.append("child")
                if missing:
                    key = f"{row.parent_part_number}->{row.child_part_number}"
                    res = DataQualityResult(
                        run_id=run_id,
                        rule_id=rule.id,
                        entity_type="bom",
                        entity_key=key,
                        status="fail",
                        message="BOM references missing part(s)",
                        details={"missing": missing},
                    )
                    db.add(res)
                    results_written += 1
                    emitted_payload.append(
                        {
                            "rule_id": rule.id,
                            "entity_type": "bom",
                            "entity_key": key,
                            "status": "fail",
                            "message": "BOM references missing part(s)",
                        }
                    )
        else:
            # Unsupported rule op: record an error result so it's visible.
            res = DataQualityResult(
                run_id=run_id,
                rule_id=rule.id,
                entity_type=entity_type,
                entity_key=None,
                status="error",
                message="Unsupported rule operation",
                details={"condition": json.loads(json.dumps(cond))},
            )
            db.add(res)
            results_written += 1
            emitted_payload.append(
                {
                    "rule_id": rule.id,
                    "entity_type": entity_type,
                    "entity_key": None,
                    "status": "error",
                    "message": "Unsupported rule operation",
                }
            )

    db.commit()

    # Best-effort semantic emission to Neo4j.
    _emit_validation_to_neo4j_best_effort(driver, run_id, emitted_payload)

    run.status = "validated"
    db.commit()

    return ValidationRunResponse(run_id=run_id, results_written=results_written, timestamp=_utcnow_iso())


class RuleCreateRequest(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    entity_type: str
    rule_type: str
    severity: str
    enabled: bool = True
    condition: Dict[str, Any]


@router.get("/rules")
async def list_rules(db: Session = Depends(get_db)):
    _require_postgres()
    rules = db.query(DataQualityRule).order_by(DataQualityRule.id.asc()).all()
    return [
        {
            "id": r.id,
            "name": r.name,
            "description": r.description,
            "entity_type": r.entity_type,
            "rule_type": r.rule_type,
            "severity": r.severity,
            "enabled": bool(r.enabled),
            "condition": r.condition,
                "created_at": str(r.created_at) if r.created_at else None,
                "updated_at": str(r.updated_at) if r.updated_at else None,
        }
        for r in rules
    ]


@router.post("/rules")
async def upsert_rule(payload: RuleCreateRequest, db: Session = Depends(get_db)):
    _require_postgres()

    rule_id = payload.id.strip()
    if not rule_id:
        raise HTTPException(status_code=400, detail="Rule id is required")

    row = db.get(DataQualityRule, rule_id)
    if row is None:
        row = DataQualityRule(id=rule_id)
        db.add(row)

    row.name = payload.name.strip()
    row.description = payload.description
    row.entity_type = payload.entity_type.strip().lower()
    row.rule_type = payload.rule_type.strip().lower()
    row.severity = payload.severity.strip().lower()
    row.enabled = 1 if payload.enabled else 0
    row.condition = payload.condition

    db.commit()

    return {"status": "success", "id": row.id}


@router.get("/runs/{run_id}/results")
async def get_results(run_id: str, db: Session = Depends(get_db)):
    _require_postgres()

    run = db.get(PLMIngestionRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")

    rows = db.query(DataQualityResult).filter(DataQualityResult.run_id == run_id).all()
    return {
        "run_id": run_id,
        "status": run.status,
        "results": [
            {
                "id": r.id,
                "rule_id": r.rule_id,
                "entity_type": r.entity_type,
                "entity_key": r.entity_key,
                "status": r.status,
                "message": r.message,
                "details": r.details,
                "created_at": str(r.created_at) if r.created_at else None,
            }
            for r in rows
        ],
    }


@router.post("/runs/{run_id}/dq/soda/scan/{table_name}", response_model=SodaGateScanResponse)
async def soda_gate_scan_for_run(
    run_id: str,
    table_name: str,
    payload: SodaGateScanRequest,
    db: Session = Depends(get_db),
):
    """Run Soda Core checks for a run_id and persist a gate result.

    Fail-closed behavior:
    - Postgres is required for PLM ETL (503 if not configured)
    - Soda is required for this endpoint (503 if not installed)
    """

    _require_postgres()
    Scan = _require_soda()

    run = db.get(PLMIngestionRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")

    raw = (table_name or "").strip()
    if not raw:
        raise HTTPException(status_code=400, detail="Missing table_name")
    if "." in raw:
        schema, table = raw.split(".", 1)
    else:
        schema, table = "public", raw

    if not schema.replace("_", "a").isalnum() or not table.replace("_", "a").isalnum():
        raise HTTPException(status_code=400, detail="Invalid table identifier")

    if not _table_exists(db, schema, table):
        raise HTTPException(status_code=404, detail=f"Table {schema}.{table} not found")

    stage = (payload.stage or "").strip().lower() or "transformed"
    if stage not in {"staged", "transformed", "validated", "graph_sync"}:
        raise HTTPException(status_code=400, detail="Invalid stage")

    checks_yaml = (payload.checks_yaml or "").strip()
    if not checks_yaml:
        default_checks = _default_soda_checks_for_table(table, run_id)
        if not default_checks:
            raise HTTPException(status_code=400, detail="checks_yaml is required for this table")
        checks_yaml = default_checks

    scan_id = uuid.uuid4().hex
    now = datetime.now(timezone.utc)
    qualified = _qualified_table(schema, table)
    columns = _list_columns(db, schema, table)
    row_count = _count_rows_for_run(db, qualified, run_id)
    column_count = len(columns)

    try:
        from sqlalchemy.engine.url import make_url

        url = make_url(DATABASE_URL)
        if not url.host or not url.database:
            raise HTTPException(status_code=503, detail="DATABASE_URL must include host and database")

        user = url.username or ""
        password = url.password or ""
        port = int(url.port or 5432)

        config_yaml = (
            f"data_source {payload.data_source_name}:\n"
            f"  type: postgres\n"
            f"  connection:\n"
            f"    host: {url.host}\n"
            f"    port: {port}\n"
            f"    username: {user}\n"
            f"    password: {password}\n"
            f"    database: {url.database}\n"
        )

        checks_yaml_wrapped = _wrap_sodacl_checks(schema, table, checks_yaml)

        scan = Scan()
        scan.set_data_source_name(str(payload.data_source_name or "postgres").strip() or "postgres")
        scan.add_configuration_yaml_str(config_yaml)
        scan.add_sodacl_yaml_str(checks_yaml_wrapped)

        exit_code = scan.execute()
        scan_results: Dict[str, Any] = scan.get_scan_results() or {}
        checks = scan_results.get("checks") or []

        issues = _issues_from_soda_checks(checks)
        overall_score = round(_score_from_soda_checks(checks), 3)
        logs = scan_results.get("logs") or []
        if not isinstance(logs, list):
            logs = []

        errors = scan_results.get("errors") or []
        warnings = scan_results.get("warnings") or []
        if not errors:
            errors = [l for l in logs if str((l or {}).get("level") or "").upper() == "ERROR"]
        if not warnings:
            warnings = [l for l in logs if str((l or {}).get("level") or "").upper() == "WARNING"]

        report_payload: Dict[str, Any] = {
            "run_id": run_id,
            "stage": stage,
            "table_name": table,
            "scan_id": scan_id,
            "overall_score": overall_score,
            "issues": issues,
            "recommendations": ["Review failed Soda checks and fix upstream data"] if issues else ["No recommendations."],
            "scan_date": now.isoformat(),
            "row_count": int(row_count),
            "column_count": int(column_count),
            "rule_results": checks,
            "summary": {
                "soda_exit_code": exit_code,
                "errors": errors,
                "warnings": warnings,
            },
        }

        db.add(
            DataQualityScanReport(
                scan_id=scan_id,
                table_name=table,
                data_source="soda",
                report=report_payload,
                overall_score=float(report_payload["overall_score"]),
                issues_count=len(issues),
                scan_date=now,
                row_count=int(row_count),
                column_count=int(column_count),
            )
        )

        passed = (len(issues) == 0) and (exit_code == 0)
        status = "pass" if passed else "fail"

        gate_id = uuid.uuid4().hex
        db.add(
            DataQualityGateResult(
                id=gate_id,
                run_id=run_id,
                stage=stage,
                tool="soda",
                table_name=table,
                scan_id=scan_id,
                status=status,
                overall_score=float(report_payload["overall_score"]),
                issues_count=len(issues),
                details={
                    "qualified_table": qualified,
                    "checks_yaml": checks_yaml_wrapped,
                    "report": report_payload,
                },
            )
        )
        db.commit()

        return SodaGateScanResponse(
            gate_id=gate_id,
            run_id=run_id,
            stage=stage,
            table_name=table,
            scan_id=scan_id,
            status=status,
            overall_score=float(report_payload["overall_score"]),
            issues_count=len(issues),
            blocked=not passed,
            timestamp=_utcnow_iso(),
        )
    except HTTPException:
        raise
    except Exception as exc:  # pylint: disable=broad-exception-caught
        gate_id = uuid.uuid4().hex
        db.add(
            DataQualityGateResult(
                id=gate_id,
                run_id=run_id,
                stage=stage,
                tool="soda",
                table_name=table,
                scan_id=None,
                status="error",
                overall_score=None,
                issues_count=0,
                details={"message": str(exc)},
            )
        )
        db.commit()
        raise HTTPException(status_code=500, detail="Soda scan failed") from exc


@router.get("/runs/{run_id}/dq/gates")
async def list_quality_gates_for_run(run_id: str, db: Session = Depends(get_db)):
    _require_postgres()

    run = db.get(PLMIngestionRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")

    rows = (
        db.query(DataQualityGateResult)
        .filter(DataQualityGateResult.run_id == run_id)
        .order_by(DataQualityGateResult.created_at.desc())
        .all()
    )

    return {
        "run_id": run_id,
        "gates": [
            {
                "id": r.id,
                "stage": r.stage,
                "tool": r.tool,
                "table_name": r.table_name,
                "scan_id": r.scan_id,
                "status": r.status,
                "overall_score": r.overall_score,
                "issues_count": r.issues_count,
                "created_at": str(r.created_at) if r.created_at else None,
                "details": r.details,
            }
            for r in rows
        ],
    }


def _spark_jobs_dir() -> Path:
    # python_backend/graph_api -> python_backend -> agentic-restored
    return Path(__file__).resolve().parents[2] / "spark_jobs"


def _tail_text_file(path: Path, *, max_lines: int = 200, max_bytes: int = 64 * 1024) -> str:
    max_lines = max(1, min(int(max_lines), 2000))
    max_bytes = max(1024, min(int(max_bytes), 512 * 1024))

    try:
        size = path.stat().st_size
    except OSError:
        return ""

    start = max(0, size - max_bytes)
    try:
        with open(path, "rb") as fp:
            fp.seek(start)
            chunk = fp.read()
    except OSError:
        return ""

    text = chunk.decode("utf-8", errors="replace")
    lines = text.splitlines()
    if len(lines) <= max_lines:
        return "\n".join(lines)
    return "\n".join(lines[-max_lines:])


def _find_spark_sync_log(logs_dir: Path, job_id: str) -> Optional[Path]:
    if not job_id:
        return None

    # File naming: spark-sync-{run_id}-{job_id}.log
    pattern = f"spark-sync-*-{job_id}.log"
    matches = sorted(logs_dir.glob(pattern), key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True)
    return matches[0] if matches else None


def _require_env(name: str) -> str:
    val = (os.getenv(name) or "").strip()
    if not val:
        raise HTTPException(status_code=503, detail=f"{name} is required")
    return val


def _resolve_spark_submit() -> str:
    configured = (os.getenv("SPARK_SUBMIT") or "").strip()
    candidate = configured or "spark-submit"
    if configured:
        return candidate
    if shutil.which(candidate) is None:
        raise HTTPException(
            status_code=503,
            detail="spark-submit not found on PATH (install Spark or set SPARK_SUBMIT)",
        )
    return candidate


@router.post("/runs/{run_id}/sync/neo4j")
async def spark_sync_run_to_neo4j(
    run_id: str,
    request: Request,
    wait: bool = False,
    db: Session = Depends(get_db),
):
    """Trigger Spark job to sync a PLM ETL run (Postgres truth) into Neo4j (derived).

    Fail-closed:
    - Requires Postgres (DATABASE_URL)
    - Requires Neo4j creds (NEO4J_URI/NEO4J_USERNAME/NEO4J_PASSWORD)
    - Requires spark-submit installed (or SPARK_SUBMIT)
    """

    _require_postgres()

    run = db.get(PLMIngestionRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")

    # Ensure there is something to sync (no fabricated graph output).
    parts_count = db.query(PLMPart).filter(PLMPart.run_id == run_id).count()
    bom_count = db.query(PLMBOMItem).filter(PLMBOMItem.run_id == run_id).count()
    if parts_count == 0 and bom_count == 0:
        raise HTTPException(
            status_code=409,
            detail="Nothing to sync: no plm_parts or plm_bom_items rows for this run_id",
        )

    # Require env vars the Spark job needs.
    _require_env("DATABASE_URL")
    _require_env("NEO4J_URI")
    _require_env("NEO4J_USERNAME")
    _require_env("NEO4J_PASSWORD")

    spark_jobs_dir = _spark_jobs_dir()
    script_path = spark_jobs_dir / "sync_plm_run_to_neo4j.py"
    if not script_path.exists():
        raise HTTPException(status_code=500, detail="Spark sync script not found")

    spark_submit = _resolve_spark_submit()
    spark_master = (os.getenv("SPARK_MASTER") or "").strip()

    cmd: List[str] = [
        spark_submit,
    ]
    if spark_master:
        cmd.extend(["--master", spark_master])
    cmd.extend(
        [
            "--conf",
            "spark.sql.session.timeZone=UTC",
            str(script_path),
            "--run-id",
            run_id,
        ]
    )

    logs_dir = Path(getattr(request.app.state, "logs_dir", Path(__file__).resolve().parents[1] / "logs"))
    logs_dir.mkdir(parents=True, exist_ok=True)
    job_id = uuid4().hex
    log_path = logs_dir / f"spark-sync-{run_id}-{job_id}.log"

    try:
        import asyncio
        with open(log_path, "wb") as log_fp:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=str(spark_jobs_dir),
                stdout=log_fp,
                stderr=log_fp,
            )

            if wait:
                return_code = await proc.wait()
                if return_code != 0:
                    raise HTTPException(
                        status_code=500,
                        detail={
                            "message": "Spark sync failed",
                            "return_code": return_code,
                            "log_path": str(log_path),
                        },
                    )

                st = log_path.stat() if log_path.exists() else None
                updated_at = (
                    datetime.fromtimestamp(st.st_mtime, tz=timezone.utc).replace(tzinfo=None).isoformat()
                    if st
                    else None
                )
                return {
                    "status": "completed",
                    "job_id": job_id,
                    "return_code": return_code,
                    "log_path": str(log_path),
                    "log_found": bool(st),
                    "size_bytes": st.st_size if st else 0,
                    "updated_at": updated_at,
                    "command": cmd,
                }

            st = log_path.stat() if log_path.exists() else None
            updated_at = (
                datetime.fromtimestamp(st.st_mtime, tz=timezone.utc).replace(tzinfo=None).isoformat()
                if st
                else None
            )

            return {
                "status": "started",
                "job_id": job_id,
                "pid": proc.pid,
                "log_path": str(log_path),
                "log_found": bool(st),
                "size_bytes": st.st_size if st else 0,
                "updated_at": updated_at,
                "command": cmd,
            }
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=f"Executable not found: {exc}") from exc


@router.get("/sync/neo4j/jobs/{job_id}")
async def get_spark_sync_job_log(job_id: str, request: Request, tail_lines: int = 200):
    """Fetch recent Spark sync job log output.

    This is best-effort observability for local/dev. It does not infer whether the
    Spark process is still running; it only returns log tail + timestamps.
    """

    logs_dir = Path(getattr(request.app.state, "logs_dir", Path(__file__).resolve().parents[1] / "logs"))
    logs_dir.mkdir(parents=True, exist_ok=True)

    log_path = _find_spark_sync_log(logs_dir, job_id)
    if log_path is None:
        raise HTTPException(status_code=404, detail="Job log not found")

    tail = _tail_text_file(log_path, max_lines=tail_lines)
    try:
        st = log_path.stat()
        updated_at = datetime.fromtimestamp(st.st_mtime, tz=timezone.utc).replace(tzinfo=None).isoformat()
        size_bytes = st.st_size
    except OSError:
        updated_at = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
        size_bytes = 0

    return {
        "job_id": job_id,
        "log_path": str(log_path),
        "size_bytes": size_bytes,
        "updated_at": updated_at,
        "tail": tail,
        "timestamp": datetime.now(timezone.utc).replace(tzinfo=None).isoformat(),
    }
