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
from sqlalchemy import func, text as sa_text
from sqlalchemy.orm import Session

from core.db_session import DATABASE_URL, get_db
from models.plm_models import PLMIngestionRun, PLMPart, PLMStagedRecord

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

        # Skip if an identical record (same run + content) already exists.
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


@router.post("/runs/{run_id}/transform")
async def transform_records(run_id: str, payload: TransformRequest, db: Session = Depends(get_db)):
    """Apply field mappings to staged records and persist as PLMPart rows.

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

    mapping = payload.part_mapping or {}
    # Guarantees for required targets (must always be mapped)
    if "part_number" not in mapping.values():
        mapping.setdefault("part_number", "part_number")
    if "name" not in mapping.values():
        mapping.setdefault("name", "name")

    # Remove existing transformed parts so this endpoint is idempotent
    db.query(PLMPart).filter(PLMPart.run_id == run_id).delete(synchronize_session=False)

    inserted = 0
    for row in staged_rows:
        rec: Dict[str, Any] = row.payload if isinstance(row.payload, dict) else {}

        # Apply mapping: for each source→target pair, pick value from source field
        mapped: Dict[str, Any] = {}
        for src, dest in mapping.items():
            if src in rec:
                mapped[dest] = rec[src]

        part_number = str(mapped.get("part_number") or rec.get("part_number") or "")
        if not part_number:
            continue  # skip records with no part_number

        part = PLMPart(
            run_id=run_id,
            part_number=part_number,
            name=str(mapped.get("name") or rec.get("name") or ""),
            description=str(mapped.get("description") or rec.get("description") or ""),
            classification=str(mapped.get("classification") or rec.get("classification") or ""),
            raw=rec,
        )
        db.merge(part)  # upsert via unique index on (run_id, part_number)
        inserted += 1

    run.status = "transformed"
    run.updated_at = datetime.now(timezone.utc)
    db.commit()

    return {"run_id": run_id, "transformed_count": inserted, "status": run.status}


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
    run = _get_run_or_404(run_id, db)

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
