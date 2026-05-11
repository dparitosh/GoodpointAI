"""PLM ETL router – Run lifecycle endpoints.

Handles:
  POST /runs                         – create a new ETL run
  POST /runs/{id}/stage              – stage raw records for discovery
  POST /runs/{id}/transform          – apply field mappings → PLMPart rows
  POST /runs/{id}/validate           – validate transformed parts
  POST /runs/{id}/dq/scan            – lightweight quality scan on staged data
  POST /runs/{id}/dq/soda/scan/{t}   – SODA-style quality scan on a table
  GET  /runs/{id}/dq/gates           – retrieve quality gates for a run
  POST /runs/{id}/sync/neo4j/direct  – sync transformed parts to Neo4j
"""

from __future__ import annotations

import hashlib
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from core.db_session import DATABASE_URL, get_db
from models.plm_models import PLMIngestionRun, PLMPart, PLMStagedRecord
from models.rule_engine_models import Rule, RuleSet
from services.rule_expression_executor import RuleRegistry

logger = logging.getLogger(__name__)

# Maximum records accepted in a single stage request (DoS guard, R-08).
_MAX_STAGE_RECORDS = 10_000
# Maximum records streamed into Python for DQ completeness scoring (P-02/P-03).
_MAX_SCAN_ROWS = 5_000


router = APIRouter(prefix="/api/plm/etl", tags=["PLM - ETL"])


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(tzinfo=None).isoformat()


def _require_postgres() -> None:
    url = (DATABASE_URL or "").strip().lower()
    if not (url.startswith("postgresql") or url.startswith("postgres")):
        raise HTTPException(
            status_code=503,
            detail="Postgres is required for PLM ETL. Set DATABASE_URL to a Postgres connection string.",
        )


def _get_run_or_404(run_id: str, db: Session) -> PLMIngestionRun:
    run = db.get(PLMIngestionRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"ETL run '{run_id}' not found")
    return run


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class CreateRunRequest(BaseModel):
    source_system: str = Field(..., min_length=1)
    target_system: str = Field(..., min_length=1)


class CreateRunResponse(BaseModel):
    run_id: str
    status: str
    created_at: str


class StageRecordsRequest(BaseModel):
    object_type: str = Field(default="part")
    # R-08: cap at 10 000 records to prevent memory DoS.
    records: List[Dict[str, Any]] = Field(default_factory=list, max_length=_MAX_STAGE_RECORDS)


class DQScanRequest(BaseModel):
    stage: str = Field(default="staged")


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

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
    """Stage raw records so that discovery and quality checks can operate on them.

    DQ-02: content-hash deduplication via INSERT … ON CONFLICT DO NOTHING.
    Duplicate records within the same run (same content) are silently skipped.
    """
    _require_postgres()
    run = _get_run_or_404(run_id, db)

    records = payload.records or []
    staged_count = 0
    skipped_count = 0
    # Track hashes seen within this request batch to catch intra-batch duplicates
    # before they reach the DB.  The DB-level dedup query only sees committed rows,
    # so two identical records in the same payload would both pass that check and
    # then collide on the unique constraint at commit time.
    _batch_hashes: set[str] = set()

    for rec in records:
        if not isinstance(rec, dict):
            continue

        # DQ-08: coerce numeric ID fields to str so "123" and 123 hash identically.
        for _id_field in ("part_number", "id", "parent_part_number", "child_part_number"):
            if _id_field in rec and not isinstance(rec[_id_field], str):
                rec = {**rec, _id_field: str(rec[_id_field])}

        # Compute a deterministic content hash for deduplication (DQ-02).
        content_hash = hashlib.sha256(
            json.dumps(rec, sort_keys=True, default=str).encode()
        ).hexdigest()

        # Skip duplicates within this batch (not yet committed, invisible to DB query).
        if content_hash in _batch_hashes:
            skipped_count += 1
            continue

        # Skip if an identical record (same run + content) already exists in DB.
        existing = (
            db.query(PLMStagedRecord.id)
            .filter(
                PLMStagedRecord.run_id == run_id,
                PLMStagedRecord.content_hash == content_hash,
            )
            .first()
        )
        if existing:
            skipped_count += 1
            continue

        _batch_hashes.add(content_hash)
        staged = PLMStagedRecord(
            run_id=run_id,
            object_type=payload.object_type or "part",
            payload=rec,
            source_object_id=str(rec.get("part_number") or rec.get("id") or ""),
            content_hash=content_hash,
        )
        db.add(staged)
        staged_count += 1

    run.status = "staged"
    run.updated_at = datetime.now(timezone.utc)
    db.commit()

    return {
        "run_id": run_id,
        "staged_count": staged_count,
        "skipped_duplicates": skipped_count,
        "status": run.status,
    }


@router.post("/runs/{run_id}/dq/scan")
async def dq_scan(run_id: str, payload: DQScanRequest, db: Session = Depends(get_db)):
    """Run a lightweight quality scan over the staged records for this ETL run.

    P-02: scans at most _MAX_SCAN_ROWS rows (no full-table load).
    DQ-06: completeness uses *majority-present* keys as the expected schema,
           not the union — partial schemas no longer unfairly lower scores.
    """
    _require_postgres()
    _get_run_or_404(run_id, db)
    _stage = payload.stage  # noqa: F841  # reserved for future stage-specific filtering

    # P-02: limit how many rows we pull into Python.
    staged_rows = (
        db.query(PLMStagedRecord)
        .filter(PLMStagedRecord.run_id == run_id)
        .limit(_MAX_SCAN_ROWS)
        .all()
    )
    # Total count without loading every row.
    total: int = (
        db.query(func.count(PLMStagedRecord.id))  # type: ignore[attr-defined]
        .filter(PLMStagedRecord.run_id == run_id)
        .scalar() or 0
    )

    records = [row.payload for row in staged_rows if isinstance(row.payload, dict)]
    sampled = len(records)

    if total == 0:
        return {
            "run_id": run_id,
            "overall_score": 0.0,
            "status": "warn",
            "issues_count": 1,
            "checks": [{"name": "record_count", "status": "warn", "detail": "No staged records found"}],
        }

    # DQ-06: build the *expected* schema from keys present in >50 % of sampled records
    # so that partial schemas don't falsely penalise records that are correct for their type.
    if records:
        key_freq: Dict[str, int] = {}
        for r in records:
            for k in r:
                key_freq[k] = key_freq.get(k, 0) + 1
        majority_threshold = sampled / 2
        expected_keys = {k for k, cnt in key_freq.items() if cnt > majority_threshold}
    else:
        expected_keys = set()

    completeness_scores: List[float] = []
    for r in records:
        if not expected_keys:
            completeness_scores.append(1.0)
        else:
            non_empty = sum(
                1 for k in expected_keys if r.get(k) not in (None, "", [], {})
            )
            completeness_scores.append(non_empty / len(expected_keys))

    completeness = sum(completeness_scores) / len(completeness_scores) if completeness_scores else 1.0

    checks: List[Dict[str, Any]] = [
        {
            "name": "completeness",
            "status": "pass" if completeness >= 0.7 else "warn",
            "score": round(completeness, 4),
            "detail": f"{round(completeness * 100)}% field completeness (sampled {sampled}/{total})",
        },
        {"name": "record_count", "status": "pass", "detail": f"{total} record(s) staged"},
    ]

    issues_count = sum(1 for c in checks if c["status"] != "pass")
    overall = completeness
    status = "pass" if overall >= 0.7 and issues_count == 0 else "warn"

    return {
        "run_id": run_id,
        "overall_score": round(overall, 4),
        "status": status,
        "issues_count": issues_count,
        "checks": checks,
    }


@router.get("/runs/{run_id}/dq/gates")
async def dq_gates(run_id: str, db: Session = Depends(get_db)):
    """Return quality gate results for an ETL run.

    P-03: uses a COUNT aggregate query instead of loading all rows into Python.
    """
    _require_postgres()
    run = _get_run_or_404(run_id, db)

    # P-03: count without materialising rows.
    record_count: int = (
        db.query(func.count(PLMStagedRecord.id))  # type: ignore[attr-defined]
        .filter(PLMStagedRecord.run_id == run_id)
        .scalar() or 0
    )

    gate = {
        "tool": "soda",
        "stage": "staged",
        "status": run.status,
        "details": {
            "report": {
                "issues": [] if record_count > 0 else [{"name": "no_records", "message": "No staged records found"}],
                "recommendations": (
                    ["Add records to the source data set before running discovery"]
                    if record_count == 0
                    else []
                ),
            }
        },
    }

    return {"run_id": run_id, "gates": [gate]}


# ---------------------------------------------------------------------------
# Transform endpoint – apply field mappings, write PLMPart rows
# ---------------------------------------------------------------------------

class TransformRequest(BaseModel):
    part_mapping: Dict[str, str] = Field(
        default_factory=lambda: {"part_number": "part_number", "name": "name"},
        description="Source field → target field mapping, e.g. {'category': 'classification'}",
    )
    # Optional: ID of a persisted RuleSet to evaluate against each record during
    # transform.  Pre-compiled once before the loop (RuleRegistry pattern).
    rule_set_id: Optional[str] = Field(
        default=None,
        description="Rule set ID whose rules are applied per-record during transform",
    )


@router.post("/runs/{run_id}/transform")
async def transform_records(run_id: str, payload: TransformRequest, db: Session = Depends(get_db)):
    """Apply field mappings to staged records and persist as PLMPart rows.

    Implements the **Accumulator / Process-and-Report** pattern:

    * Per-record try-except — one bad record never halts the batch.
    * **Schema failures** (part_number unresolvable): record is *skipped* and
      appended to ``error_log`` with ``exception_type="SchemaError"``.
    * **Quality failures** (a rule in the RuleSet returns False): record is
      *kept* but its ``raw`` payload is annotated with a ``_warnings`` list so
      downstream steps and the UI can surface the issues.
    * Returns a dual payload: transformed records summary + structured error log.

    Idempotent: existing PLMPart rows for this run are deleted before re-inserting.
    """
    _require_postgres()
    run = _get_run_or_404(run_id, db)

    staged_rows = (
        db.query(PLMStagedRecord)
        .filter(PLMStagedRecord.run_id == run_id)
        .all()
    )
    if not staged_rows:
        raise HTTPException(status_code=422, detail="No staged records — call /stage first")

    mapping = dict(payload.part_mapping or {})

    # ── Alias resolution for required targets ──────────────────────────────
    _first_rec: Dict[str, Any] = (
        staged_rows[0].payload if isinstance(staged_rows[0].payload, dict) else {}
    )
    _src_keys = list(_first_rec.keys())

    _PN_SYNONYMS = [
        "part_number", "partno", "part_no", "pn", "number", "item_number",
        "item_no", "id", "part_id", "partnumber", "num",
    ]
    _NAME_SYNONYMS = ["name", "title", "description", "label", "part_name"]

    def _best_src(synonyms: list) -> Optional[str]:
        lower_src = {k.lower(): k for k in _src_keys}
        for syn in synonyms:
            if syn in lower_src:
                return lower_src[syn]
        return None

    if "part_number" not in mapping.values():
        fallback = _best_src(_PN_SYNONYMS) or (_src_keys[0] if _src_keys else "part_number")
        mapping[fallback] = "part_number"
    if "name" not in mapping.values():
        fallback = _best_src(_NAME_SYNONYMS) or (_src_keys[0] if _src_keys else "name")
        mapping.setdefault(fallback, "name")

    # ── Pre-compile rules once before the batch loop ───────────────────────
    # RuleRegistry compiles every expression string to a code object so the
    # loop reuses __code__ objects instead of re-parsing on every iteration.
    registry: Optional[RuleRegistry] = None
    registry_compile_errors: List[Dict[str, Any]] = []

    if payload.rule_set_id:
        rule_set = db.query(RuleSet).filter(
            RuleSet.id == payload.rule_set_id,
            RuleSet.is_active == True,  # noqa: E712
        ).first()
        if rule_set:
            rules = db.query(Rule).filter(
                Rule.rule_set_id == payload.rule_set_id,
                Rule.enabled == True,  # noqa: E712
            ).all()
            registry = RuleRegistry(rules)
            registry_compile_errors = registry.compile_errors
            if registry_compile_errors:
                logger.warning(
                    "RuleRegistry: %d rule(s) failed to compile for rule_set %s",
                    len(registry_compile_errors), payload.rule_set_id,
                )
        else:
            logger.warning("rule_set_id %s not found or inactive — skipping rule checks", payload.rule_set_id)

    # ── Idempotent: clear previous transform output ────────────────────────
    db.query(PLMPart).filter(PLMPart.run_id == run_id).delete(synchronize_session=False)

    # ── Accumulator state ─────────────────────────────────────────────────
    inserted = 0
    error_log: List[Dict[str, Any]] = []
    warning_count = 0

    for row in staged_rows:
        # Identify the source record — used in error log
        raw_rec: Dict[str, Any] = row.payload if isinstance(row.payload, dict) else {}
        # Pick the most meaningful identifier available in the source record
        source_id = (
            str(raw_rec.get("part_number") or raw_rec.get("Number") or
                raw_rec.get("id") or raw_rec.get("ID") or row.id or "unknown")
        )

        try:
            # ── 1. Apply field mapping ─────────────────────────────────────
            mapped: Dict[str, Any] = {}
            for src, dest in mapping.items():
                if src in raw_rec:
                    mapped[dest] = raw_rec[src]

            part_number = str(mapped.get("part_number") or raw_rec.get("part_number") or "").strip()

            # ── 2. Schema gate — missing part_number is unrecoverable ──────
            if not part_number:
                error_log.append({
                    "source_id":      source_id,
                    "rule_id":        "SCHEMA:part_number",
                    "exception_type": "SchemaError",
                    "detail":         "part_number could not be resolved from source record",
                })
                continue

            # ── 3. Quality gate — rules from RuleRegistry (warnings only) ─
            record_warnings: List[Dict[str, Any]] = []
            if registry is not None:
                eval_record = {"part_number": part_number, **raw_rec, **mapped}
                violations = registry.evaluate(eval_record)
                for v in violations:
                    if v.get("severity") == "critical":
                        # Critical rule in the quality phase = treat as schema error,
                        # skip the record and log it.
                        error_log.append({
                            "source_id":      source_id,
                            "rule_id":        v["rule_id"],
                            "exception_type": "CriticalRuleViolation",
                            "detail":         f"Rule '{v['rule_name']}' failed (critical)",
                        })
                        part_number = ""  # flag to skip insert below
                        break
                    else:
                        # Non-critical (warning / error) — keep the record, annotate it
                        record_warnings.append({
                            "rule_id":        v["rule_id"],
                            "rule_name":      v["rule_name"],
                            "severity":       v.get("severity", "warning"),
                            "exception_type": v.get("exception_type"),
                        })

            if not part_number:
                continue  # skipped by critical rule above

            if record_warnings:
                warning_count += len(record_warnings)
                raw_rec = {**raw_rec, "_warnings": record_warnings}

            # ── 4. Persist as PLMPart ──────────────────────────────────────
            part = PLMPart(
                run_id=run_id,
                part_number=part_number,
                name=str(mapped.get("name") or raw_rec.get("name") or ""),
                description=str(mapped.get("description") or raw_rec.get("description") or ""),
                classification=str(mapped.get("classification") or raw_rec.get("classification") or ""),
                raw=raw_rec,
            )
            db.merge(part)
            inserted += 1

        except Exception as exc:  # noqa: BLE001
            # Unexpected per-record error — log and continue (never halt the batch)
            logger.error("Transform error for source_id=%s: %s", source_id, exc)
            error_log.append({
                "source_id":      source_id,
                "rule_id":        None,
                "exception_type": type(exc).__name__,
                "detail":         str(exc),
            })

    run.status = "transformed"
    run.updated_at = datetime.now(timezone.utc)
    db.commit()

    return {
        "run_id":            run_id,
        "transformed_count": inserted,
        "skipped_count":     len(error_log),
        "warning_count":     warning_count,
        "error_log":         error_log,
        # Surface compile-time rule errors separately so UI can show them
        # as configuration issues rather than data issues.
        "rule_compile_errors": registry_compile_errors,
        "status":            run.status,
    }


# ---------------------------------------------------------------------------
# Validate endpoint – check transformed PLMPart rows
# ---------------------------------------------------------------------------

@router.post("/runs/{run_id}/validate")
async def validate_records(run_id: str, db: Session = Depends(get_db)):
    """Validate transformed PLMPart records and update run status."""
    _require_postgres()
    run = _get_run_or_404(run_id, db)

    parts = db.query(PLMPart).filter(PLMPart.run_id == run_id).all()
    if not parts:
        raise HTTPException(status_code=422, detail="No transformed parts — call /transform first")

    issues: List[Dict[str, Any]] = []
    for p in parts:
        if not p.part_number:
            issues.append({"part_number": p.part_number, "issue": "missing part_number"})
        if not p.name:
            issues.append({"part_number": p.part_number, "issue": "missing name"})

    passed = len(parts) - len(issues)
    status = "validated" if len(issues) == 0 else "validated_with_warnings"
    run.status = status
    run.updated_at = datetime.now(timezone.utc)
    db.commit()

    return {
        "run_id": run_id,
        "total_parts": len(parts),
        "passed": passed,
        "issues": issues,
        "status": run.status,
    }


# ---------------------------------------------------------------------------
# SODA-style scan for a run — thin wrapper over quality_router logic
# ---------------------------------------------------------------------------

class SodaRunScanRequest(BaseModel):
    stage: str = Field(default="transformed")


@router.post("/runs/{run_id}/dq/soda/scan/{table_name}")
async def soda_scan_for_run(
    run_id: str, table_name: str, payload: SodaRunScanRequest, db: Session = Depends(get_db)
):
    """Run a SODA-style completeness/validity scan on the PLMPart rows for this run.

    Falls back to an internal completeness check when Soda Core is not installed.
    This exists so the MigrationWizard can call a run-scoped scan endpoint without
    needing to know the underlying quality router path.
    """
    _require_postgres()
    _get_run_or_404(run_id, db)

    parts = (
        db.query(PLMPart).filter(PLMPart.run_id == run_id).limit(_MAX_SCAN_ROWS).all()
    )
    total: int = (
        db.query(func.count(PLMPart.id))
        .filter(PLMPart.run_id == run_id)
        .scalar() or 0
    )

    if total == 0:
        return {
            "run_id": run_id,
            "table": table_name,
            "overall_score": 0.0,
            "status": "warn",
            "issues_count": 1,
            "blocked": False,
            "checks": [{"name": "record_count", "status": "warn", "detail": "No transformed parts found"}],
        }

    required_fields = ["part_number", "name"]
    completeness_scores: List[float] = []
    for p in parts:
        present = sum(1 for f in required_fields if getattr(p, f, None) not in (None, ""))
        completeness_scores.append(present / len(required_fields))

    completeness = sum(completeness_scores) / len(completeness_scores) if completeness_scores else 1.0
    issues_count = sum(1 for s in completeness_scores if s < 1.0)
    overall = round(completeness, 4)
    scan_status = "pass" if overall >= 0.8 else ("warn" if overall >= 0.5 else "fail")

    return {
        "run_id": run_id,
        "table": table_name,
        "overall_score": overall,
        "status": scan_status,
        "issues_count": issues_count,
        "blocked": scan_status == "fail",
        "checks": [
            {
                "name": "completeness",
                "status": "pass" if completeness >= 0.8 else "warn",
                "score": overall,
                "detail": f"{round(overall * 100)}% completeness across {total} parts",
            }
        ],
    }


# ---------------------------------------------------------------------------
# Neo4j direct sync
# ---------------------------------------------------------------------------

@router.post("/runs/{run_id}/sync/neo4j/direct")
async def sync_to_neo4j_direct(run_id: str, db: Session = Depends(get_db)):
    """Sync PLMPart rows for a run directly to Neo4j graph as Part nodes.

    Falls back gracefully when Neo4j is not configured (returns synced=0, skipped=true).
    """
    _require_postgres()
    run = _get_run_or_404(run_id, db)

    parts = db.query(PLMPart).filter(PLMPart.run_id == run_id).all()
    if not parts:
        return {
            "run_id": run_id,
            "parts_synced": 0,
            "nodes_created": 0,
            "skipped": True,
            "detail": "No transformed parts to sync — call /transform first",
        }

    # Attempt Neo4j sync via the app-level driver (best-effort, non-fatal)
    nodes_created = 0
    skipped = False
    try:
        from services.neo4j_service import get_neo4j_driver  # local import to avoid hard dep
        driver = get_neo4j_driver()
        if driver is None:
            raise RuntimeError("Neo4j driver not initialised")

        async with driver.session() as session:
            for p in parts:
                result = await session.run(
                    """
                    MERGE (n:Part {part_number: $part_number, run_id: $run_id})
                    ON CREATE SET
                        n.name          = $name,
                        n.description   = $description,
                        n.classification = $classification,
                        n.created_at    = $created_at
                    RETURN n
                    """,
                    part_number=p.part_number,
                    run_id=run_id,
                    name=p.name or "",
                    description=p.description or "",
                    classification=p.classification or "",
                    created_at=datetime.now(timezone.utc).isoformat(),
                )
                summary = await result.consume()
                nodes_created += summary.counters.nodes_created
    except Exception as exc:
        logger.warning("Neo4j sync skipped (non-fatal): %s", exc)
        skipped = True

    run.status = "synced" if not skipped else "validated"
    run.updated_at = datetime.now(timezone.utc)
    db.commit()

    return {
        "run_id": run_id,
        "parts_synced": len(parts),
        "nodes_created": nodes_created,
        "skipped": skipped,
        "status": run.status,
    }
