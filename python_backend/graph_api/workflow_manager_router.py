"""Workflow Instance Manager Router

Provides CRUD + execution lifecycle APIs for workflow instances.

Policy: NO demo/mock/sample workflows or templates in code.
- Workflows exist only if created by callers and persisted in the DB.
- Templates exist only if configured via GRAPH_TRACE_WORKFLOW_TEMPLATES_FILE.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import uuid
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, cast

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from starlette.responses import Response

from core.crypto import decrypt_json
from core.db_session import get_db
from core.db_session import SessionLocal
from models.configuration_models import DataSourceConfigRecord
from models.workflow_models import (
    WorkflowExecutionRequest,
    WorkflowExecutionResponse,
    WorkflowInstance,
    WorkflowInstanceCreate,
    WorkflowInstanceDetail,
    WorkflowInstanceResponse,
    WorkflowInstanceUpdate,
    WorkflowStage,
    WorkflowStatus,
)
from models.plm_models import PLMBOMItem, PLMIngestionRun, PLMPart, PLMStagedRecord
from models.quality_models import DataQualityGateResult, DataQualityResult, DataQualityRule
from models.report_models import PersistedReport

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/workflows", tags=["Workflows"])

# In-memory cache; DB is authoritative persistence.
WORKFLOWS_STORE: Dict[str, Dict[str, Any]] = {}
_WORKFLOWS_STORE_LOCK = asyncio.Lock()

# Background runner tasks keyed by workflow_id.
_WORKFLOW_RUN_TASKS: Dict[str, asyncio.Task] = {}
_WORKFLOW_RUN_TASKS_LOCK = asyncio.Lock()


def _safe_int(val: Any, default: int = 0) -> int:
    try:
        return int(val)
    except Exception:
        return default


def _safe_float(val: Any, default: float = 0.0) -> float:
    try:
        return float(val)
    except Exception:
        return default


def _json_safe(value: Any) -> Any:
    """Convert common Python objects into JSON-serializable primitives."""
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    # Fallback: best-effort stringification.
    return str(value)


def _redact_secrets(obj: Any) -> Any:
    """Redact likely secret fields in nested dict/list structures."""
    secret_keys = {
        "password",
        "api_key",
        "secret",
        "token",
        "account_key",
        "connection_string",
        "sas_token",
        "secret_access_key",
        "access_key",
        "session_token",
    }
    if isinstance(obj, dict):
        out: Dict[str, Any] = {}
        for k, v in obj.items():
            ks = str(k).lower()
            if ks in secret_keys:
                out[str(k)] = "***"
            else:
                out[str(k)] = _redact_secrets(v)
        return out
    if isinstance(obj, list):
        return [_redact_secrets(v) for v in obj]
    return obj


def _build_migration_factory_report(db: Session, wf: Dict[str, Any]) -> Dict[str, Any]:
    """Build a deterministic report for the Agentic Data Migration Factory.

    Policy:
    - No fabricated data.
    - If a piece of data isn't present/persisted, return null/empty.
    """
    meta = dict(wf.get("execution_metadata") or {})
    plm_run_id = str(meta.get("plm_run_id") or "").strip() or None

    etl_run: Optional[PLMIngestionRun] = None
    if plm_run_id:
        etl_run = db.get(PLMIngestionRun, plm_run_id)

    # Data quality (rules + results)
    rules: List[DataQualityRule] = (
        db.query(DataQualityRule)
        .filter(DataQualityRule.enabled == 1)
        .order_by(DataQualityRule.entity_type, DataQualityRule.severity, DataQualityRule.name)
        .all()
    )

    dq_results: List[DataQualityResult] = []
    dq_gates: List[DataQualityGateResult] = []
    if plm_run_id:
        dq_results = (
            db.query(DataQualityResult)
            .filter(DataQualityResult.run_id == plm_run_id)
            .order_by(DataQualityResult.id.desc())
            .limit(5000)
            .all()
        )
        dq_gates = (
            db.query(DataQualityGateResult)
            .filter(DataQualityGateResult.run_id == plm_run_id)
            .order_by(DataQualityGateResult.created_at.desc())
            .all()
        )

    # Summarize results per rule_id.
    per_rule: Dict[str, Dict[str, Any]] = {}
    for r in dq_results:
        rid = str(r.rule_id)
        bucket = per_rule.setdefault(rid, {"pass": 0, "fail": 0, "error": 0, "latest": None})
        status = str(r.status or "").lower()
        if status in bucket:
            bucket[status] += 1
        bucket["latest"] = {
            "status": status,
            "message": r.message,
            "entity_type": r.entity_type,
            "entity_key": r.entity_key,
            "created_at": getattr(r.created_at, "isoformat", lambda: None)(),
        }

    # Group rules into "rulesets" by entity_type (minimal, repo-aligned).
    rulesets: Dict[str, List[Dict[str, Any]]] = {}
    for rule in rules:
        rulesets.setdefault(str(rule.entity_type), []).append(
            {
                "id": rule.id,
                "name": rule.name,
                "severity": rule.severity,
                "rule_type": rule.rule_type,
                "condition": rule.condition,
                "results": per_rule.get(rule.id, {"pass": 0, "fail": 0, "error": 0, "latest": None}),
            }
        )

    gates_payload = [
        {
            "id": g.id,
            "stage": g.stage,
            "tool": g.tool,
            "table_name": g.table_name,
            "scan_id": g.scan_id,
            "status": g.status,
            "overall_score": g.overall_score,
            "issues_count": g.issues_count,
            "created_at": getattr(g.created_at, "isoformat", lambda: None)(),
            "details": g.details,
        }
        for g in dq_gates
    ]

    part_mapping = meta.get("part_mapping") if isinstance(meta.get("part_mapping"), dict) else None
    bom_mapping = meta.get("bom_mapping") if isinstance(meta.get("bom_mapping"), dict) else None

    extracted_records = _safe_int(meta.get("extracted_records"), default=_safe_int(wf.get("total_records")))
    sample_format = meta.get("sample_format")

    report: Dict[str, Any] = {
        "workflow": {
            "id": wf.get("id"),
            "name": wf.get("name"),
            "status": wf.get("status"),
            "current_stage": wf.get("current_stage"),
            "progress_percentage": _safe_float(wf.get("progress_percentage"), 0.0),
            "source": {
                "id": wf.get("source_id"),
                "name": wf.get("source_name"),
                "type": wf.get("source_type"),
            },
            "target": {
                "id": wf.get("target_id"),
                "name": wf.get("target_name"),
                "type": wf.get("target_type"),
            },
            "execution_id": wf.get("last_execution_id"),
            "started_at": wf.get("started_at"),
            "completed_at": wf.get("completed_at"),
        },
        "smart_discovery": {
            "sample_format": sample_format,
            "extracted_records": extracted_records,
            "source_id": meta.get("source_id"),
        },
        "translation": {
            "part_mapping": part_mapping,
            "bom_mapping": bom_mapping,
        },
        "etl": {
            "plm_run_id": plm_run_id,
            "run_status": getattr(etl_run, "status", None),
            "source_system": getattr(etl_run, "source_system", None),
            "target_system": getattr(etl_run, "target_system", None),
            "processed_records": wf.get("processed_records"),
            "failed_records": wf.get("failed_records"),
        },
        "data_quality": {
            "quality_score": wf.get("quality_score"),
            "soda_gate": meta.get("soda_gate"),
            "gates": gates_payload,
        },
        "rules": {
            "rulesets": rulesets,
            "total_rules": len(rules),
            "total_results": len(dq_results),
        },
    }

    return report


def _persist_migration_factory_report(db: Session, wf: Dict[str, Any]) -> Optional[PersistedReport]:
    """Persist a report snapshot in Postgres.

    Uses the generic `reports` table. This is best-effort and must never fail the workflow.
    """
    try:
        meta = dict(wf.get("execution_metadata") or {})
        plm_run_id = str(meta.get("plm_run_id") or "").strip() or None
        execution_id = str(wf.get("last_execution_id") or "").strip() or None
        workflow_id = str(wf.get("id") or "").strip() or None

        payload = cast(Dict[str, Any], _json_safe(_build_migration_factory_report(db, wf)))

        report_id = uuid.uuid4().hex
        title = f"Factory Report: {wf.get('name') or (workflow_id or 'workflow')}"
        summary = cast(
            Dict[str, Any],
            _json_safe(
                {
            "workflow_id": workflow_id,
            "execution_id": execution_id,
            "plm_run_id": plm_run_id,
            "status": wf.get("status"),
            "processed_records": wf.get("processed_records"),
            "failed_records": wf.get("failed_records"),
            "quality_score": wf.get("quality_score"),
                }
            ),
        )

        row = PersistedReport(
            id=report_id,
            report_type="migration_factory",
            title=title,
            description=None,
            source=workflow_id,
            schema_version="1",
            run_id=plm_run_id,
            external_id=execution_id,
            table_name=None,
            payload=payload,
            summary=summary,
            is_deleted=0,
        )

        db.add(row)
        db.commit()
        db.refresh(row)
        return row
    except SQLAlchemyError:
        try:
            db.rollback()
        except Exception:
            pass
        return None
    except Exception:
        return None


def _set_workflow_state(
    db: Session,
    workflow_id: str,
    *,
    status: Optional[WorkflowStatus] = None,
    stage: Optional[WorkflowStage] = None,
    progress: Optional[float] = None,
    meta_patch: Optional[Dict[str, Any]] = None,
    stats_patch: Optional[Dict[str, Any]] = None,
    started_at: Optional[datetime] = None,
    completed_at: Optional[datetime] = None,
) -> None:
    now = _now_utc()
    async def _update() -> None:
        async with _WORKFLOWS_STORE_LOCK:
            wf = WORKFLOWS_STORE.get(workflow_id)
            if wf is None:
                return

            if status is not None:
                wf["status"] = status
            if stage is not None:
                wf["current_stage"] = stage
            if progress is not None:
                try:
                    wf["progress_percentage"] = float(max(0.0, min(100.0, progress)))
                except Exception:  # pylint: disable=broad-exception-caught
                    pass

            if started_at is not None:
                wf["started_at"] = started_at
            if completed_at is not None:
                wf["completed_at"] = completed_at

            if meta_patch:
                meta = dict(wf.get("execution_metadata") or {})
                meta.update(meta_patch)
                wf["execution_metadata"] = meta

            if stats_patch:
                for k, v in stats_patch.items():
                    wf[k] = v

            wf["updated_at"] = now
            WORKFLOWS_STORE[workflow_id] = wf
            _upsert_workflow_model(db, wf)

    # Bridge sync caller -> async lock.
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_update())
    except RuntimeError:
        # No running loop; fall back to a best-effort synchronous update.
        # This path is primarily for tests/CLI calls.
        try:
            wf = WORKFLOWS_STORE.get(workflow_id)
            if wf is None:
                return
            if status is not None:
                wf["status"] = status
            if stage is not None:
                wf["current_stage"] = stage
            if progress is not None:
                wf["progress_percentage"] = float(max(0.0, min(100.0, progress)))
            if started_at is not None:
                wf["started_at"] = started_at
            if completed_at is not None:
                wf["completed_at"] = completed_at
            if meta_patch:
                meta = dict(wf.get("execution_metadata") or {})
                meta.update(meta_patch)
                wf["execution_metadata"] = meta
            if stats_patch:
                for k, v in stats_patch.items():
                    wf[k] = v
            wf["updated_at"] = now
            WORKFLOWS_STORE[workflow_id] = wf
            _upsert_workflow_model(db, wf)
        except (KeyError, TypeError, ValueError, RuntimeError, OSError):
            return


async def _set_workflow_state_async(
    db: Session,
    workflow_id: str,
    *,
    status: Optional[WorkflowStatus] = None,
    stage: Optional[WorkflowStage] = None,
    progress: Optional[float] = None,
    meta_patch: Optional[Dict[str, Any]] = None,
    stats_patch: Optional[Dict[str, Any]] = None,
    started_at: Optional[datetime] = None,
    completed_at: Optional[datetime] = None,
) -> None:
    """Async/awaitable variant used by async code paths (runner).

    The sync version queues a task; this variant updates deterministically.
    """
    now = _now_utc()
    async with _WORKFLOWS_STORE_LOCK:
        wf = WORKFLOWS_STORE.get(workflow_id)
        if wf is None:
            return

        if status is not None:
            wf["status"] = status
        if stage is not None:
            wf["current_stage"] = stage
        if progress is not None:
            try:
                wf["progress_percentage"] = float(max(0.0, min(100.0, progress)))
            except Exception:  # pylint: disable=broad-exception-caught
                pass

        if started_at is not None:
            wf["started_at"] = started_at
        if completed_at is not None:
            wf["completed_at"] = completed_at

        if meta_patch:
            meta = dict(wf.get("execution_metadata") or {})
            meta.update(meta_patch)
            wf["execution_metadata"] = meta

        if stats_patch:
            for k, v in stats_patch.items():
                wf[k] = v

        wf["updated_at"] = now
        WORKFLOWS_STORE[workflow_id] = wf

    _upsert_workflow_model(db, wf)


async def _get_workflow_snapshot(workflow_id: str) -> Optional[Dict[str, Any]]:
    async with _WORKFLOWS_STORE_LOCK:
        wf = WORKFLOWS_STORE.get(workflow_id)
        return dict(wf) if isinstance(wf, dict) else None


def _normalize_plm_records(records: List[Any], *, max_records: int = 200) -> List[Dict[str, Any]]:
    """Best-effort normalization for heterogeneous samples.

    Some file-based sources return a single wrapper object that contains many nested business
    records (e.g., ReqIF exports). The PLM ETL staging/transform expects a list of flat dict
    records. This function extracts likely "record" dicts from nested structures.
    """

    out: List[Dict[str, Any]] = []
    seen_ids: set[str] = set()
    stack: List[Any] = list(records or [])

    while stack and len(out) < max_records:
        cur = stack.pop()

        if isinstance(cur, dict):
            # Heuristic: treat spec-like objects as records.
            obj_type = cur.get("_type")
            identifier = cur.get("IDENTIFIER") or cur.get("identifier")
            long_name = cur.get("LONG-NAME") or cur.get("long-name") or cur.get("name")

            if obj_type == "SPEC-OBJECT" or (identifier and long_name):
                dedupe_key = str(identifier) if identifier is not None else json.dumps(cur, sort_keys=True)[:200]
                if dedupe_key not in seen_ids:
                    seen_ids.add(dedupe_key)
                    out.append(cur)
                continue

            # Walk nested containers.
            for v in cur.values():
                if isinstance(v, (dict, list)):
                    stack.append(v)
            continue

        if isinstance(cur, list):
            stack.extend(cur)

    return out


async def _run_plm_etl_for_workflow(workflow_id: str) -> None:
    """Execute the PLM ETL pipeline for a workflow instance.

    This is the real progression engine behind /api/workflows/{id}/execute(action=start).
    """

    db = SessionLocal()
    try:
        await _ensure_store_loaded(db)

        wf = await _get_workflow_snapshot(workflow_id)
        if wf is None:
            return

        # Always re-check status before doing work.
        if _normalize_status(wf.get("status")) != WorkflowStatus.RUNNING:
            return

        source_id = str(wf.get("source_id") or "").strip()
        target_name = str(wf.get("target_name") or "").strip() or str(wf.get("target_id") or "").strip()
        source_name = str(wf.get("source_name") or "").strip() or source_id

        if not source_id:
            raise ValueError("Workflow source_id is missing")

        # Late imports to avoid any router import-order surprises.
        from graph_api.data_sources_router import get_data_source_sample  # pylint: disable=import-outside-toplevel
        from graph_api.plm_etl_router import (  # pylint: disable=import-outside-toplevel
            CreateRunRequest,
            SodaGateScanRequest,
            StageRecordsRequest,
            TransformRequest,
            create_run,
            list_quality_gates_for_run,
            soda_gate_scan_for_run,
            stage_records,
            transform,
        )

        started_at = wf.get("started_at") or _now_utc()
        await _set_workflow_state_async(
            db,
            workflow_id,
            stage=WorkflowStage.EXTRACTING,
            progress=10.0,
            meta_patch={"source_id": source_id, "target": target_name, "pipeline": "plm_etl"},
            started_at=started_at,
        )

        sample = await get_data_source_sample(source_id=source_id, limit=200, db=db)
        sample_dict = sample.model_dump() if hasattr(sample, "model_dump") else cast(Dict[str, Any], sample)
        raw_records = sample_dict.get("records") or []
        if not isinstance(raw_records, list) or not raw_records:
            raise ValueError("No records returned from data source sample")

        # Normalize wrapper/nested formats into flat dict records when possible.
        normalized = _normalize_plm_records(raw_records, max_records=200)
        records: List[Any] = normalized if normalized else raw_records

        await _set_workflow_state_async(
            db,
            workflow_id,
            progress=20.0,
            meta_patch={"extracted_records": len(records), "sample_format": sample_dict.get("format")},
        )

        # Create run.
        run_resp = await create_run(CreateRunRequest(source_system=source_name, target_system=target_name), db=db)
        run_id = run_resp.run_id if hasattr(run_resp, "run_id") else cast(Dict[str, Any], run_resp).get("run_id")
        if not run_id:
            raise ValueError("Failed to create PLM ingestion run")

        await _set_workflow_state_async(db, workflow_id, progress=25.0, meta_patch={"plm_run_id": run_id})

        # Stage extracted records.
        await _set_workflow_state_async(db, workflow_id, stage=WorkflowStage.TRANSFORMING, progress=35.0)
        stage_resp = await stage_records(
            run_id=str(run_id),
            payload=StageRecordsRequest(object_type="part", records=records, source_object_id_field=None),
            db=db,
        )
        staged_count = int(cast(Dict[str, Any], stage_resp).get("staged") or 0)
        await _set_workflow_state_async(
            db,
            workflow_id,
            progress=45.0,
            stats_patch={"total_records": staged_count, "processed_records": 0, "failed_records": 0},
        )

        # Heuristic mapping based on observed keys.
        first = next((r for r in records if isinstance(r, dict)), {})
        keys = [k for k in first.keys() if isinstance(k, str)]
        keys_l = {k.lower(): k for k in keys}

        def _pick(*candidates: str) -> Optional[str]:
            for c in candidates:
                if c.lower() in keys_l:
                    return keys_l[c.lower()]
            return None

        part_mapping: Dict[str, str] = {}
        src_pn = _pick(
            "part_number",
            "partnumber",
            "pn",
            "number",
            "part no",
            "part_no",
            "part id",
            "part_id",
            "id",
            "identifier",
            "code",
        )
        if src_pn:
            part_mapping[src_pn] = "part_number"
        src_name = _pick("name", "part_name", "title", "long-name", "long_name", "long name", "longname")
        if src_name:
            part_mapping[src_name] = "name"
        src_desc = _pick("description", "desc")
        if src_desc:
            part_mapping[src_desc] = "description"
        src_class = _pick("classification", "class", "category")
        if src_class:
            part_mapping[src_class] = "classification"

        if not part_mapping:
            raise ValueError("Unable to infer a part_mapping from sampled records")

        await _set_workflow_state_async(db, workflow_id, progress=55.0, meta_patch={"part_mapping": part_mapping})

        # Transform.
        transform_resp = await transform(
            run_id=str(run_id),
            payload=TransformRequest(part_mapping=part_mapping, bom_mapping=None),
            db=db,
        )
        parts_written = int(cast(Dict[str, Any], transform_resp).get("parts_written") or 0)
        await _set_workflow_state_async(
            db,
            workflow_id,
            progress=70.0,
            stats_patch={"processed_records": parts_written},
        )

        # Validate (Soda).
        await _set_workflow_state_async(db, workflow_id, stage=WorkflowStage.VALIDATING, progress=80.0)
        soda_resp = await soda_gate_scan_for_run(
            run_id=str(run_id),
            table_name="public.plm_parts",
            payload=SodaGateScanRequest(stage="transformed", checks_yaml=None, data_source_name="postgres"),
            db=db,
        )
        soda_dict = soda_resp.model_dump() if hasattr(soda_resp, "model_dump") else cast(Dict[str, Any], soda_resp)

        gates = await list_quality_gates_for_run(run_id=str(run_id), db=db)
        gates_dict = gates if isinstance(gates, dict) else {"run_id": str(run_id), "gates": []}

        blocked = bool(soda_dict.get("blocked"))
        score = soda_dict.get("overall_score")
        await _set_workflow_state_async(
            db,
            workflow_id,
            progress=92.0,
            meta_patch={"soda_gate": soda_dict, "quality_gates": gates_dict},
            stats_patch={"quality_score": score},
        )

        # Finalize.
        now = _now_utc()
        if blocked:
            await _set_workflow_state_async(
                db,
                workflow_id,
                status=WorkflowStatus.FAILED,
                stage=WorkflowStage.FINALIZING,
                progress=100.0,
                meta_patch={"failure_reason": "Quality gate blocked"},
                completed_at=now,
            )
        else:
            await _set_workflow_state_async(
                db,
                workflow_id,
                status=WorkflowStatus.COMPLETED,
                stage=WorkflowStage.FINALIZING,
                progress=100.0,
                completed_at=now,
            )

        # Best-effort: persist a deterministic factory report snapshot.
        try:
            async with _WORKFLOWS_STORE_LOCK:
                wf_snapshot = WORKFLOWS_STORE.get(workflow_id)
            if wf_snapshot:
                _persist_migration_factory_report(db, wf_snapshot)
        except Exception:
            pass

    except Exception as exc:  # pylint: disable=broad-exception-caught
        try:
            now = _now_utc()
            await _set_workflow_state_async(
                db,
                workflow_id,
                status=WorkflowStatus.FAILED,
                stage=WorkflowStage.FINALIZING,
                progress=100.0,
                meta_patch={"error": f"{type(exc).__name__}: {exc}"},
                completed_at=now,
            )

            # Best-effort: persist a snapshot even on failure.
            async with _WORKFLOWS_STORE_LOCK:
                wf_snapshot = WORKFLOWS_STORE.get(workflow_id)
            if wf_snapshot:
                _persist_migration_factory_report(db, wf_snapshot)
        except (KeyError, TypeError, ValueError, RuntimeError, OSError):
            pass
        logger.exception("Workflow %s PLM ETL runner failed", workflow_id)
    finally:
        try:
            db.close()
        except (RuntimeError, OSError):
            pass
        async with _WORKFLOW_RUN_TASKS_LOCK:
            t = _WORKFLOW_RUN_TASKS.get(workflow_id)
            if t is not None and t.done():
                _WORKFLOW_RUN_TASKS.pop(workflow_id, None)


async def _ensure_runner_started(workflow_id: str) -> None:
    async with _WORKFLOW_RUN_TASKS_LOCK:
        existing = _WORKFLOW_RUN_TASKS.get(workflow_id)
        if existing is not None and not existing.done():
            return
        _WORKFLOW_RUN_TASKS[workflow_id] = asyncio.create_task(_run_plm_etl_for_workflow(workflow_id))


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_status(value: Any) -> WorkflowStatus:
    if isinstance(value, WorkflowStatus):
        return value
    raw = str(value or "").strip().lower()
    for s in WorkflowStatus:
        if s.value == raw:
            return s
    # Default to draft to avoid fabricating progress/state.
    return WorkflowStatus.DRAFT


def _normalize_stage(value: Any) -> Optional[WorkflowStage]:
    if value is None:
        return None
    if isinstance(value, WorkflowStage):
        return value
    raw = str(value or "").strip().lower()
    for st in WorkflowStage:
        if st.value == raw:
            return st
    return None


def _row_to_store_dict(row: WorkflowInstance) -> Dict[str, Any]:
    return {
        "id": row.id,
        "name": row.name,
        "description": row.description,
        "source_id": row.source_id,
        "source_name": row.source_name,
        "source_type": row.source_type,
        "source_config": row.source_config or {},
        "target_id": row.target_id,
        "target_name": row.target_name,
        "target_type": row.target_type,
        "target_config": row.target_config or {},
        "workflow_config": row.workflow_config or {"nodes": [], "edges": [], "ai_agents": []},
        "ai_agents_enabled": row.ai_agents_enabled or [],
        "status": _normalize_status(row.status),
        "current_stage": _normalize_stage(row.current_stage),
        "progress_percentage": float(row.progress_percentage or 0.0),
        "total_records": int(row.total_records or 0),
        "processed_records": int(row.processed_records or 0),
        "failed_records": int(row.failed_records or 0),
        "quality_score": row.quality_score,
        "execution_metadata": row.execution_metadata or {},
        "last_execution_id": row.last_execution_id,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
        "started_at": row.started_at,
        "completed_at": row.completed_at,
        "created_by": row.created_by,
        "schedule_enabled": bool(row.schedule_enabled),
        "schedule_cron": row.schedule_cron,
        "next_run_at": row.next_run_at,
    }


def _upsert_workflow_model(db: Session, store_row: Dict[str, Any]) -> None:
    workflow_id = str(store_row.get("id") or "").strip()
    if not workflow_id:
        return

    row: Optional[WorkflowInstance] = (
        db.query(WorkflowInstance).filter(WorkflowInstance.id == workflow_id).first()
    )
    creating = row is None
    if creating:
        row = WorkflowInstance(id=workflow_id)

    assert row is not None
    row_any = cast(Any, row)

    row_any.name = str(store_row.get("name") or "").strip() or row_any.name
    row_any.description = store_row.get("description")

    row_any.source_id = str(store_row.get("source_id") or "")
    row_any.source_name = str(store_row.get("source_name") or store_row.get("source_id") or "")
    row_any.source_type = str(store_row.get("source_type") or "")
    row_any.source_config = store_row.get("source_config") or {}

    row_any.target_id = str(store_row.get("target_id") or "")
    row_any.target_name = str(store_row.get("target_name") or store_row.get("target_id") or "")
    row_any.target_type = str(store_row.get("target_type") or "")
    row_any.target_config = store_row.get("target_config") or {}

    row_any.workflow_config = store_row.get("workflow_config") or {"nodes": [], "edges": [], "ai_agents": []}
    row_any.ai_agents_enabled = store_row.get("ai_agents_enabled") or []

    row_any.status = _normalize_status(store_row.get("status"))
    row_any.current_stage = _normalize_stage(store_row.get("current_stage"))
    row_any.progress_percentage = float(store_row.get("progress_percentage") or 0.0)

    row_any.total_records = int(store_row.get("total_records") or 0)
    row_any.processed_records = int(store_row.get("processed_records") or 0)
    row_any.failed_records = int(store_row.get("failed_records") or 0)
    row_any.quality_score = store_row.get("quality_score")

    row_any.execution_metadata = store_row.get("execution_metadata") or {}
    row_any.last_execution_id = store_row.get("last_execution_id")

    row_any.started_at = store_row.get("started_at")
    row_any.completed_at = store_row.get("completed_at")

    row_any.created_by = store_row.get("created_by")
    row_any.schedule_enabled = bool(store_row.get("schedule_enabled") or False)
    row_any.schedule_cron = store_row.get("schedule_cron")
    row_any.next_run_at = store_row.get("next_run_at")

    if creating:
        db.add(row)

    db.commit()


async def _ensure_store_loaded(db: Session) -> None:
    # If the in-memory store is empty (e.g. process restart), reload from DB.
    async with _WORKFLOWS_STORE_LOCK:
        if WORKFLOWS_STORE:
            return
        rows = db.query(WorkflowInstance).all()
        for row in rows:
            workflow_id = str(row.id)
            WORKFLOWS_STORE[workflow_id] = _row_to_store_dict(row)


def _make_workflow_id() -> str:
    timestamp = int(_now_utc().timestamp())
    return f"wf_{timestamp}_{uuid.uuid4().hex[:8]}"


def _templates_file_path() -> Optional[Path]:
    raw = (os.getenv("GRAPH_TRACE_WORKFLOW_TEMPLATES_FILE") or "").strip()
    if not raw:
        return None
    return Path(raw)


def _load_templates_or_503() -> List[Dict[str, Any]]:
    path = _templates_file_path()
    if path is None:
        raise HTTPException(
            status_code=503,
            detail="Workflow templates are not configured. Set GRAPH_TRACE_WORKFLOW_TEMPLATES_FILE to a JSON file.",
        )

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as e:
        raise HTTPException(status_code=503, detail=f"Workflow templates file not found: {path}") from e
    except (OSError, json.JSONDecodeError) as e:
        raise HTTPException(status_code=503, detail=f"Workflow templates file is invalid: {path}") from e

    if not isinstance(data, list) or not data:
        raise HTTPException(status_code=503, detail="Workflow templates are not configured (empty list).")

    templates: List[Dict[str, Any]] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        tid = str(item.get("id") or "").strip()
        name = str(item.get("name") or "").strip()
        if not tid or not name:
            continue
        templates.append(item)

    if not templates:
        raise HTTPException(status_code=503, detail="Workflow templates are not configured (no valid items).")

    return templates


def _load_templates_optional() -> List[Dict[str, Any]]:
    """Best-effort templates loader for UI listing endpoints.

    Workflow templates are optional in local/dev setups; listing should not fail-closed.
    """

    try:
        return _load_templates_or_503()
    except HTTPException as exc:
        if getattr(exc, "status_code", None) == 503:
            logger.info("Workflow templates unavailable for listing: %s", getattr(exc, "detail", exc))
            return []
        raise


@router.get("", response_model=List[WorkflowInstanceResponse], include_in_schema=False)
@router.get("/", response_model=List[WorkflowInstanceResponse])
async def list_workflows(
    response: Response,
    status: Optional[WorkflowStatus] = None,
    source_type: Optional[str] = None,
    target_type: Optional[str] = None,
    search: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    await _ensure_store_loaded(db)

    async with _WORKFLOWS_STORE_LOCK:
        workflows = list(WORKFLOWS_STORE.values())

    if status:
        workflows = [w for w in workflows if _normalize_status(w.get("status")).value == status.value]
    if source_type:
        workflows = [w for w in workflows if str(w.get("source_type") or "") == source_type]
    if target_type:
        workflows = [w for w in workflows if str(w.get("target_type") or "") == target_type]
    if search:
        s = search.lower()
        workflows = [
            w
            for w in workflows
            if s in str(w.get("name") or "").lower() or s in str(w.get("description") or "").lower()
        ]

    total_count = len(workflows)
    page_items = workflows[skip : skip + limit]

    if response is not None:
        response.headers["X-Total-Count"] = str(total_count)

    return page_items


@router.post("/", response_model=WorkflowInstanceResponse, status_code=201)
async def create_workflow(
    workflow: WorkflowInstanceCreate,
    db: Session = Depends(get_db),
):
    await _ensure_store_loaded(db)

    workflow_id = _make_workflow_id()
    created_at = _now_utc()

    store_row: Dict[str, Any] = {
        "id": workflow_id,
        "name": workflow.name,
        "description": workflow.description,
        "source_id": workflow.source.id,
        "source_name": workflow.source.name,
        "source_type": workflow.source.type,
        "source_config": {
            "connection_details": deepcopy(workflow.source.connection_details or {}),
            "extraction_config": deepcopy(workflow.source.extraction_config or {}),
        },
        "target_id": workflow.target.id,
        "target_name": workflow.target.name,
        "target_type": workflow.target.type,
        "target_config": {
            "connection_details": deepcopy(workflow.target.connection_details or {}),
            "load_config": deepcopy(workflow.target.load_config or {}),
        },
        "workflow_config": deepcopy(workflow.workflow_config.model_dump()),
        "ai_agents_enabled": list(workflow.ai_agents_enabled or []),
        "status": WorkflowStatus.CONFIGURED,
        "current_stage": WorkflowStage.IDLE,
        "progress_percentage": 0.0,
        "total_records": 0,
        "processed_records": 0,
        "failed_records": 0,
        "quality_score": None,
        "execution_metadata": {},
        "last_execution_id": None,
        "created_at": created_at,
        "updated_at": None,
        "started_at": None,
        "completed_at": None,
        "created_by": workflow.created_by,
        "schedule_enabled": bool(workflow.schedule_enabled),
        "schedule_cron": workflow.schedule_cron,
        "next_run_at": None,
    }

    async with _WORKFLOWS_STORE_LOCK:
        WORKFLOWS_STORE[workflow_id] = store_row

    _upsert_workflow_model(db, store_row)

    return store_row


@router.get("/{workflow_id}", response_model=WorkflowInstanceDetail)
async def get_workflow(
    workflow_id: str,
    db: Session = Depends(get_db),
):
    workflow_id = str(workflow_id or "").strip()
    if not workflow_id:
        raise HTTPException(status_code=404, detail="Workflow not found")

    await _ensure_store_loaded(db)

    async with _WORKFLOWS_STORE_LOCK:
        wf = WORKFLOWS_STORE.get(workflow_id)

    if wf is not None:
        return wf

    row = db.query(WorkflowInstance).filter(WorkflowInstance.id == workflow_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail=f"Workflow {workflow_id} not found")

    store_row = _row_to_store_dict(row)
    async with _WORKFLOWS_STORE_LOCK:
        WORKFLOWS_STORE[workflow_id] = store_row

    return store_row


@router.get("/{workflow_id}/graph", response_model=Dict[str, Any])
async def get_workflow_graph(
    workflow_id: str,
    db: Session = Depends(get_db),
):
    """Return the workflow's graph configuration (nodes/edges).

    The frontend's workflow detail view expects graph-shaped data even when the
    workflow instance itself is otherwise healthy.
    """

    workflow_id = str(workflow_id or "").strip()
    if not workflow_id:
        raise HTTPException(status_code=404, detail="Workflow not found")

    await _ensure_store_loaded(db)

    async with _WORKFLOWS_STORE_LOCK:
        wf = WORKFLOWS_STORE.get(workflow_id)

    if wf is None:
        row = db.query(WorkflowInstance).filter(WorkflowInstance.id == workflow_id).first()
        if row is None:
            raise HTTPException(status_code=404, detail=f"Workflow {workflow_id} not found")
        wf = _row_to_store_dict(row)
        async with _WORKFLOWS_STORE_LOCK:
            WORKFLOWS_STORE[workflow_id] = wf

    cfg = wf.get("workflow_config")
    if not isinstance(cfg, dict):
        cfg = {}

    nodes = cfg.get("nodes")
    edges = cfg.get("edges")
    ai_agents = cfg.get("ai_agents")

    return {
        "nodes": nodes if isinstance(nodes, list) else [],
        "edges": edges if isinstance(edges, list) else [],
        "ai_agents": ai_agents if isinstance(ai_agents, list) else [],
    }


@router.patch("/{workflow_id}", response_model=WorkflowInstanceDetail)
async def update_workflow(
    workflow_id: str,
    workflow_update: WorkflowInstanceUpdate,
    db: Session = Depends(get_db),
):
    await _ensure_store_loaded(db)

    async with _WORKFLOWS_STORE_LOCK:
        current = WORKFLOWS_STORE.get(workflow_id)

    if current is None:
        raise HTTPException(status_code=404, detail=f"Workflow {workflow_id} not found")

    if _normalize_status(current.get("status")) == WorkflowStatus.RUNNING:
        raise HTTPException(status_code=400, detail="Cannot update running workflow")

    updated = dict(current)
    if workflow_update.name is not None:
        updated["name"] = workflow_update.name
    if workflow_update.description is not None:
        updated["description"] = workflow_update.description
    if workflow_update.source is not None:
        updated["source_id"] = workflow_update.source.id
        updated["source_name"] = workflow_update.source.name
        updated["source_type"] = workflow_update.source.type
        updated["source_config"] = {
            "connection_details": deepcopy(workflow_update.source.connection_details or {}),
            "extraction_config": deepcopy(workflow_update.source.extraction_config or {}),
        }
    if workflow_update.target is not None:
        updated["target_id"] = workflow_update.target.id
        updated["target_name"] = workflow_update.target.name
        updated["target_type"] = workflow_update.target.type
        updated["target_config"] = {
            "connection_details": deepcopy(workflow_update.target.connection_details or {}),
            "load_config": deepcopy(workflow_update.target.load_config or {}),
        }
    if workflow_update.workflow_config is not None:
        updated["workflow_config"] = deepcopy(workflow_update.workflow_config.model_dump())
    if workflow_update.ai_agents_enabled is not None:
        updated["ai_agents_enabled"] = list(workflow_update.ai_agents_enabled or [])
    if workflow_update.schedule_enabled is not None:
        updated["schedule_enabled"] = bool(workflow_update.schedule_enabled)
    if workflow_update.schedule_cron is not None:
        updated["schedule_cron"] = workflow_update.schedule_cron

    updated["updated_at"] = _now_utc()

    async with _WORKFLOWS_STORE_LOCK:
        WORKFLOWS_STORE[workflow_id] = updated

    _upsert_workflow_model(db, updated)

    return updated


@router.delete("/{workflow_id}", status_code=204)
async def delete_workflow(
    workflow_id: str,
    db: Session = Depends(get_db),
):
    await _ensure_store_loaded(db)

    async with _WORKFLOWS_STORE_LOCK:
        existing = WORKFLOWS_STORE.get(workflow_id)

    if existing is None:
        raise HTTPException(status_code=404, detail=f"Workflow {workflow_id} not found")

    if _normalize_status(existing.get("status")) == WorkflowStatus.RUNNING:
        raise HTTPException(status_code=400, detail="Cannot delete running workflow. Stop it first.")

    async with _WORKFLOWS_STORE_LOCK:
        WORKFLOWS_STORE.pop(workflow_id, None)

    db.query(WorkflowInstance).filter(WorkflowInstance.id == workflow_id).delete()
    db.commit()

    return Response(status_code=204)


@router.post("/{workflow_id}/execute", response_model=WorkflowExecutionResponse)
async def execute_workflow(
    workflow_id: str,
    request: WorkflowExecutionRequest,
    db: Session = Depends(get_db),
):
    await _ensure_store_loaded(db)

    async with _WORKFLOWS_STORE_LOCK:
        wf = WORKFLOWS_STORE.get(workflow_id)

    if wf is None:
        raise HTTPException(status_code=404, detail=f"Workflow {workflow_id} not found")

    action = str(request.action or "").strip().lower()
    now = _now_utc()

    status = _normalize_status(wf.get("status"))
    message = ""

    if action == "start":
        if status == WorkflowStatus.RUNNING:
            # Idempotent start: returning 200 avoids noisy UX when a user clicks
            # "Run" multiple times or the UI refreshes mid-run.
            await _ensure_runner_started(workflow_id)
            return WorkflowExecutionResponse(
                workflow_id=workflow_id,
                execution_id=str(wf.get("last_execution_id") or ""),
                status=str(WorkflowStatus.RUNNING.value),
                message="Workflow already running",
                started_at=wf.get("started_at"),
            )
        wf["status"] = WorkflowStatus.RUNNING
        wf["current_stage"] = WorkflowStage.EXTRACTING
        wf["started_at"] = wf.get("started_at") or now
        wf["completed_at"] = None

        meta = dict(wf.get("execution_metadata") or {})
        # Clear stale error metadata from prior runs.
        meta.pop("error", None)
        meta.pop("failure_reason", None)
        # Minimal session id to support lineage capture.
        meta.setdefault("migration_session_id", f"ms_{uuid.uuid4().hex[:12]}")
        wf["execution_metadata"] = meta

        wf["last_execution_id"] = f"exec_{uuid.uuid4().hex[:10]}"
        message = "Workflow started"

        # Kick off a real PLM ETL progression in the background.
        await _ensure_runner_started(workflow_id)

    elif action == "pause":
        if status != WorkflowStatus.RUNNING:
            raise HTTPException(status_code=400, detail="Workflow is not running")
        wf["status"] = WorkflowStatus.PAUSED
        message = "Workflow paused"

    elif action == "resume":
        if status != WorkflowStatus.PAUSED:
            raise HTTPException(status_code=400, detail="Workflow is not paused")
        wf["status"] = WorkflowStatus.RUNNING
        message = "Workflow resumed"

    elif action in {"stop", "cancel"}:
        wf["status"] = WorkflowStatus.CANCELLED
        wf["current_stage"] = WorkflowStage.FINALIZING
        wf["completed_at"] = now
        message = "Workflow cancelled"

    else:
        raise HTTPException(status_code=400, detail="Unsupported action")

    wf["updated_at"] = now

    async with _WORKFLOWS_STORE_LOCK:
        WORKFLOWS_STORE[workflow_id] = wf

    _upsert_workflow_model(db, wf)

    return WorkflowExecutionResponse(
        workflow_id=workflow_id,
        execution_id=str(wf.get("last_execution_id") or ""),
        status=str(_normalize_status(wf.get("status")).value),
        message=message,
        started_at=wf.get("started_at"),
    )


@router.get("/{workflow_id}/report")
async def get_workflow_migration_report(
    workflow_id: str,
    db: Session = Depends(get_db),
):
    """Return a deterministic "Data Migration Factory" report for a workflow.

    Aggregates:
    - Smart discovery summary (sample + extracted counts)
    - Translation/mapping (inferred/selected mappings)
    - ETL run anchor (plm_run_id + run status)
    - Data quality (Soda gates + deterministic rule results)
    - Rules/rulesets (dq_rules grouped by entity_type)
    """
    await _ensure_store_loaded(db)

    async with _WORKFLOWS_STORE_LOCK:
        wf = WORKFLOWS_STORE.get(workflow_id)

    if wf is None:
        raise HTTPException(status_code=404, detail=f"Workflow {workflow_id} not found")

    return _build_migration_factory_report(db, wf)


@router.post("/{workflow_id}/report/snapshot")
async def snapshot_workflow_migration_report(
    workflow_id: str,
    db: Session = Depends(get_db),
):
    """Persist and return a snapshot of the workflow's factory report."""
    await _ensure_store_loaded(db)

    async with _WORKFLOWS_STORE_LOCK:
        wf = WORKFLOWS_STORE.get(workflow_id)

    if wf is None:
        raise HTTPException(status_code=404, detail=f"Workflow {workflow_id} not found")

    row = _persist_migration_factory_report(db, wf)
    if row is None:
        raise HTTPException(status_code=500, detail="Failed to persist report")

    return {
        "report_id": row.id,
        "created_at": getattr(row.created_at, "isoformat", lambda: None)(),
        "report": row.payload,
        "summary": row.summary,
    }


@router.get("/{workflow_id}/report/latest")
async def get_latest_workflow_migration_report_snapshot(
    workflow_id: str,
    db: Session = Depends(get_db),
):
    """Fetch the most recent persisted factory report snapshot for a workflow."""
    try:
        row = (
            db.query(PersistedReport)
            .filter(PersistedReport.is_deleted == 0)
            .filter(PersistedReport.report_type == "migration_factory")
            .filter(PersistedReport.source == workflow_id)
            .order_by(PersistedReport.created_at.desc())
            .first()
        )
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail=f"Database query failed: {exc}") from exc

    if row is None:
        raise HTTPException(status_code=404, detail="No persisted report snapshots found")

    return {
        "report_id": row.id,
        "created_at": getattr(row.created_at, "isoformat", lambda: None)(),
        "report": row.payload,
        "summary": row.summary,
    }


@router.get("/{workflow_id}/report/snapshots")
async def list_workflow_migration_report_snapshots(
    workflow_id: str,
    response: Response,
    execution_id: Optional[str] = Query(default=None, max_length=128),
    limit: int = Query(default=25, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    """List persisted factory report snapshots for a workflow.

    This is a thin workflow-scoped wrapper over the generic `reports` table.
    """
    try:
        q = (
            db.query(PersistedReport)
            .filter(PersistedReport.is_deleted == 0)
            .filter(PersistedReport.report_type == "migration_factory")
            .filter(PersistedReport.source == workflow_id)
        )
        if execution_id:
            q = q.filter(PersistedReport.external_id == execution_id)

        total = q.count()
        rows = q.order_by(PersistedReport.created_at.desc()).offset(offset).limit(limit).all()
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail=f"Database query failed: {exc}") from exc

    if response is not None:
        response.headers["X-Total-Count"] = str(total)

    return {
        "workflow_id": workflow_id,
        "total": total,
        "items": [
            {
                "report_id": r.id,
                "created_at": getattr(r.created_at, "isoformat", lambda: None)(),
                "execution_id": r.external_id,
                "plm_run_id": r.run_id,
                "summary": r.summary,
            }
            for r in rows
        ],
    }


@router.get("/{workflow_id}/archive")
async def get_workflow_archive(
    workflow_id: str,
    response: Response,
    limit_reports: int = Query(default=25, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """One-stop workflow archive/history.

    Returns all workflow-related datasets, reports, rulesets, and ETL outputs in one place.
    """
    await _ensure_store_loaded(db)

    async with _WORKFLOWS_STORE_LOCK:
        wf = WORKFLOWS_STORE.get(workflow_id)

    if wf is None:
        raise HTTPException(status_code=404, detail=f"Workflow {workflow_id} not found")

    # Source dataset (datasource), redacted.
    source_ds_id = str(wf.get("source_id") or "").strip() or None
    datasource_payload: Optional[Dict[str, Any]] = None
    datasource_warning: Optional[str] = None
    if source_ds_id:
        row = db.get(DataSourceConfigRecord, source_ds_id)
        if row is not None:
            try:
                conn = decrypt_json(row.connection_ciphertext)
                if not isinstance(conn, dict):
                    conn = {}
                datasource_payload = {
                    "id": row.id,
                    "name": row.name,
                    "type": row.type,
                    "description": row.description,
                    "status": row.status,
                    "connection": _redact_secrets(conn),
                }
            except Exception:
                datasource_warning = "Datasource connection could not be decrypted in this environment"
                datasource_payload = {
                    "id": row.id,
                    "name": row.name,
                    "type": row.type,
                    "description": row.description,
                    "status": row.status,
                    "connection": None,
                }

    # Persisted factory report snapshots.
    try:
        q = (
            db.query(PersistedReport)
            .filter(PersistedReport.is_deleted == 0)
            .filter(PersistedReport.report_type == "migration_factory")
            .filter(PersistedReport.source == workflow_id)
        )
        total_reports = q.count()
        report_rows = q.order_by(PersistedReport.created_at.desc()).limit(limit_reports).all()
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail=f"Database query failed: {exc}") from exc

    if response is not None:
        response.headers["X-Total-Count"] = str(total_reports)

    snapshots = [
        {
            "report_id": r.id,
            "created_at": getattr(r.created_at, "isoformat", lambda: None)(),
            "execution_id": r.external_id,
            "plm_run_id": r.run_id,
            "summary": r.summary,
        }
        for r in report_rows
    ]

    # Collect run_ids from workflow metadata + snapshots.
    run_ids: List[str] = []
    meta = wf.get("execution_metadata") or {}
    if isinstance(meta, dict):
        rid = str(meta.get("plm_run_id") or "").strip()
        if rid:
            run_ids.append(rid)
    for s in snapshots:
        rid = str(s.get("plm_run_id") or "").strip()
        if rid:
            run_ids.append(rid)
    run_ids = list(dict.fromkeys(run_ids))

    runs_payload: List[Dict[str, Any]] = []
    for run_id in run_ids:
        etl_run = db.get(PLMIngestionRun, run_id)
        staged_count = db.query(PLMStagedRecord).filter(PLMStagedRecord.run_id == run_id).count()
        parts_count = db.query(PLMPart).filter(PLMPart.run_id == run_id).count()
        bom_count = db.query(PLMBOMItem).filter(PLMBOMItem.run_id == run_id).count()
        dq_results_count = db.query(DataQualityResult).filter(DataQualityResult.run_id == run_id).count()
        dq_gates = (
            db.query(DataQualityGateResult)
            .filter(DataQualityGateResult.run_id == run_id)
            .order_by(DataQualityGateResult.created_at.desc())
            .all()
        )
        runs_payload.append(
            {
                "run_id": run_id,
                "status": getattr(etl_run, "status", None),
                "source_system": getattr(etl_run, "source_system", None),
                "target_system": getattr(etl_run, "target_system", None),
                "counts": {
                    "staged_records": staged_count,
                    "parts": parts_count,
                    "bom_items": bom_count,
                },
                "data_quality": {
                    "results_count": dq_results_count,
                    "gates": _json_safe(
                        [
                            {
                                "id": g.id,
                                "tool": g.tool,
                                "stage": g.stage,
                                "table_name": g.table_name,
                                "scan_id": g.scan_id,
                                "status": g.status,
                                "overall_score": g.overall_score,
                                "issues_count": g.issues_count,
                                "created_at": getattr(g.created_at, "isoformat", lambda: None)(),
                            }
                            for g in dq_gates
                        ]
                    ),
                },
            }
        )

    # Rulesets (dq_rules grouped by entity_type).
    rules: List[DataQualityRule] = (
        db.query(DataQualityRule)
        .filter(DataQualityRule.enabled == 1)
        .order_by(DataQualityRule.entity_type, DataQualityRule.severity, DataQualityRule.name)
        .all()
    )
    rulesets: Dict[str, List[Dict[str, Any]]] = {}
    for rule in rules:
        rulesets.setdefault(str(rule.entity_type), []).append(
            {
                "id": rule.id,
                "name": rule.name,
                "severity": rule.severity,
                "rule_type": rule.rule_type,
                "condition": _json_safe(rule.condition),
            }
        )

    return {
        "workflow": _json_safe(wf),
        "datasets": {
            "source": datasource_payload,
            "source_warning": datasource_warning,
            "target": {
                "id": wf.get("target_id"),
                "name": wf.get("target_name"),
                "type": wf.get("target_type"),
                "config": _redact_secrets(wf.get("target_config") or {}),
            },
        },
        "reports": {
            "factory_snapshots_total": total_reports,
            "factory_snapshots": snapshots,
        },
        "etl": {
            "runs": _json_safe(runs_payload),
        },
        "rulesets": rulesets,
    }


@router.get("/templates/list")
async def list_workflow_templates(
    response: Response,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
):
    templates = _load_templates_optional()

    total = len(templates)
    page = templates[skip : skip + limit]

    if response is not None:
        response.headers["X-Total-Count"] = str(total)

    # Ensure id/name/description exist; leave other fields as-configured.
    sanitized: List[Dict[str, Any]] = []
    for t in page:
        sanitized.append(
            {
                "id": str(t.get("id")),
                "name": str(t.get("name")),
                "description": t.get("description"),
                **{k: v for k, v in t.items() if k not in {"id", "name", "description"}},
            }
        )

    return sanitized


@router.post("/templates/{template_id}/instantiate", response_model=WorkflowInstanceResponse, status_code=201)
async def instantiate_workflow_from_template(
    template_id: str,
    source_id: str = Query(..., min_length=1),
    target_id: str = Query(..., min_length=1),
    name: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    templates = _load_templates_or_503()
    template = next((t for t in templates if str(t.get("id")) == str(template_id)), None)
    if template is None:
        raise HTTPException(status_code=404, detail=f"Template {template_id} not found")

    raw_source = template.get("source")
    raw_target = template.get("target")
    src_tpl: Dict[str, Any] = raw_source if isinstance(raw_source, dict) else {}
    tgt_tpl: Dict[str, Any] = raw_target if isinstance(raw_target, dict) else {}

    source_type = str(src_tpl.get("type") or template.get("source_type") or "").strip()
    target_type = str(tgt_tpl.get("type") or template.get("target_type") or "").strip()

    if not source_type or not target_type:
        raise HTTPException(status_code=400, detail="Template must define source_type and target_type")

    wf_name = (name or "").strip() or str(template.get("name") or "").strip() or f"{source_id} → {target_id}"

    created_at = _now_utc()
    workflow_id = _make_workflow_id()

    store_row: Dict[str, Any] = {
        "id": workflow_id,
        "name": wf_name,
        "description": template.get("description"),
        "source_id": source_id,
        "source_name": str(src_tpl.get("name") or source_id),
        "source_type": source_type,
        "source_config": {
            "connection_details": deepcopy(src_tpl.get("connection_details") or {}),
            "extraction_config": deepcopy(src_tpl.get("extraction_config") or {}),
        },
        "target_id": target_id,
        "target_name": str(tgt_tpl.get("name") or target_id),
        "target_type": target_type,
        "target_config": {
            "connection_details": deepcopy(tgt_tpl.get("connection_details") or {}),
            "load_config": deepcopy(tgt_tpl.get("load_config") or {}),
        },
        "workflow_config": deepcopy(template.get("workflow_config") or {"nodes": [], "edges": [], "ai_agents": []}),
        "ai_agents_enabled": list(template.get("ai_agents_enabled") or []),
        "status": WorkflowStatus.CONFIGURED,
        "current_stage": WorkflowStage.IDLE,
        "progress_percentage": 0.0,
        "total_records": 0,
        "processed_records": 0,
        "failed_records": 0,
        "quality_score": None,
        "execution_metadata": {},
        "last_execution_id": None,
        "created_at": created_at,
        "updated_at": None,
        "started_at": None,
        "completed_at": None,
        "created_by": "template",
        "schedule_enabled": False,
        "schedule_cron": None,
        "next_run_at": None,
    }

    async with _WORKFLOWS_STORE_LOCK:
        WORKFLOWS_STORE[workflow_id] = store_row

    _upsert_workflow_model(db, store_row)

    return store_row
