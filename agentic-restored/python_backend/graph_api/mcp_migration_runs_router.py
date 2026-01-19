"""MCP Migration Runs API.

This router provides a lightweight "vertical slice" run state machine that can be
controlled by the UI and by external MCP tools.

Persistence strategy:
- Best-effort persist run snapshots into the generic `reports` table
  (models.report_models.PersistedReport) using report_type `mcp_migration_run`.
- If DB writes fail (e.g., Postgres unavailable), keep an in-memory copy so the
  API remains usable for local demos/tests.

NOTE: This does not implement a full migration engine. It only tracks run state
and stores small staged payload samples.
"""

# pylint: disable=broad-exception-caught

from __future__ import annotations

import os
import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional

import json

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from core.db_session import get_db
 
from models.report_models import PersistedReport
from services.mcp_audit_log import append_audit_event
from services.mcp_approvals import (
    create_approval_request,
    decide_approval,
    get_approval_by_token,
    list_approvals,
)
from services.mcp_staging_graph_writer import MCPStagingGraphWriter, stable_record_key


def _is_opensearch_target(target_id: Optional[str]) -> bool:
    t = (target_id or "").strip().lower()
    return ("opensearch" in t) or t.startswith("conn_opensearch")


def _opensearch_default_index() -> str:
    # Keep deterministic index name to simplify ops. Can be extended later.
    return "mcp_migration_published"


def _try_get_admin_connection_extra_options(db: Session, *, conn_id: str) -> Dict[str, Any]:
    """Best-effort lookup of an Admin Config connection's extra_options.

    This allows publish/index behavior to use connection-specific settings
    (e.g., preferred OpenSearch index name) without leaking secrets.
    """
    cid = (conn_id or "").strip()
    if not cid:
        return {}

    try:
        from models.admin_config_models import ConnectionConfig  # pylint: disable=import-outside-toplevel

        try:
            row = db.query(ConnectionConfig).filter(ConnectionConfig.id == cid).first()
        except SQLAlchemyError:
            return {}

        extra = getattr(row, "extra_options", None)
        return dict(extra) if isinstance(extra, dict) else {}
    except Exception:
        return {}


def _publish_samples_to_opensearch(
    *,
    db: Session,
    run_payload: dict[str, Any],
    entities: Optional[List[str]] = None,
    index: Optional[str] = None,
) -> dict[str, Any]:
    """Index staged sample records into OpenSearch and return a publish summary."""

    try:
        from services.opensearch_service import OpenSearchService
    except Exception as exc:  # pylint: disable=broad-exception-caught
        raise HTTPException(status_code=503, detail="OpenSearch dependencies are not available") from exc

    service = OpenSearchService(db_session=db)
    index_name = (index or "").strip() or _opensearch_default_index()

    staged = run_payload.get("staged") or {}
    if not isinstance(staged, dict):
        staged = {}

    selected = [e for e in (entities or list(staged.keys())) if e in staged]

    written_entities: List[str] = []
    docs_indexed = 0
    docs_for_lineage: List[Dict[str, Any]] = []

    run_id = str(run_payload.get("run_id") or "").strip()
    workflow_name = str(run_payload.get("workflow_name") or "").strip()
    source_id = run_payload.get("source_id")
    target_id = run_payload.get("target_id")

    for entity in selected:
        entry = staged.get(entity) or {}
        sample = entry.get("sample") if isinstance(entry, dict) else None
        sample_records = sample if isinstance(sample, list) else []
        if not sample_records:
            continue

        for rec in sample_records:
            if not isinstance(rec, dict):
                continue

            rec_key = stable_record_key(entity, rec)
            doc_id = f"{run_id}:{entity}:{rec_key}"

            doc = {
                "run_id": run_id,
                "workflow_name": workflow_name,
                "source_id": source_id,
                "target_id": target_id,
                "entity": entity,
                "record_key": rec_key,
                "record": rec,
                "indexed_at": _utcnow_iso(),
            }
            try:
                service.index_document(index=index_name, document=doc, doc_id=doc_id, refresh=False)
                docs_indexed += 1
                docs_for_lineage.append({"entity": entity, "record_key": rec_key, "target_ref": doc_id})
            except RuntimeError as exc:
                raise HTTPException(status_code=503, detail=str(exc)) from exc
            except Exception as exc:  # pylint: disable=broad-exception-caught
                # Treat external dependency failures (timeouts/unreachable) as service unavailable.
                raise HTTPException(status_code=503, detail=f"OpenSearch unavailable: {exc}") from exc

        written_entities.append(entity)

    if docs_indexed <= 0:
        raise HTTPException(status_code=409, detail="Nothing to publish: no staged sample records")

    return {
        "run_id": run_id,
        "written_entities": written_entities,
        "sample_nodes": docs_indexed,
        "batch_id": None,
        "index": index_name,
        "documents": docs_for_lineage,
    }

router = APIRouter(prefix="/api/migrations", tags=["mcp-migrations"])


RunStatus = Literal["created", "discovery", "proposal", "executing", "completed", "failed"]

_ALLOWED_TRANSITIONS: dict[RunStatus, set[RunStatus]] = {
    "created": {"discovery", "proposal", "executing", "failed"},
    "discovery": {"proposal", "failed"},
    "proposal": {"executing", "failed"},
    "executing": {"completed", "failed"},
    "completed": set(),
    "failed": set(),
}


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_status(status: str) -> RunStatus:
    s = (status or "").strip().lower()
    if s not in _ALLOWED_TRANSITIONS:
        raise ValueError(f"Unknown status: {status}")
    return s  # type: ignore[return-value]


def _transition_allowed(from_status: RunStatus, to_status: RunStatus) -> bool:
    return to_status in _ALLOWED_TRANSITIONS.get(from_status, set())


_REPORT_TYPE = "mcp_migration_run"
_AUDIT_ACTOR_DEFAULT = "mcp"


def _approvals_required() -> bool:
    return (os.getenv("GRAPH_TRACE_APPROVALS_REQUIRED") or "").strip().lower() in {"1", "true", "yes"}


def _require_approval_token(
    *,
    run_id: str,
    action: str,
    approval_token: Optional[str],
    db: Session,
) -> None:
    if not _approvals_required():
        return

    tok = (approval_token or "").strip()
    if not tok:
        raise HTTPException(
            status_code=403,
            detail={
                "message": "Approval required",
                "run_id": run_id,
                "action": action,
            },
        )

    approval = get_approval_by_token(db, run_id=run_id, token=tok, action=action)
    if not approval or str(approval.get("status") or "").lower() != "approved":
        raise HTTPException(
            status_code=403,
            detail={
                "message": "Invalid or non-approved approval token",
                "run_id": run_id,
                "action": action,
            },
        )

# In-memory fallback store for local demo resiliency.
# payload schema matches MCPMigrationRunDetail.
_RUNS_MEM: dict[str, dict[str, Any]] = {}
_RUNS_LOCK = threading.Lock()


class MCPMigrationRunCreateRequest(BaseModel):
    workflow_name: str = Field(default="", max_length=256)

    # These refer to configured sources/targets (e.g., `conn_<id>` from /api/data-sources).
    source_id: Optional[str] = Field(default=None, max_length=128)
    target_id: Optional[str] = Field(default=None, max_length=128)

    # Optional initial state (defaults to "created").
    initial_status: Optional[str] = Field(default=None)

    # Free-form options to help downstream tools.
    options: Dict[str, Any] = Field(default_factory=dict)


class MCPMigrationRunTransitionRequest(BaseModel):
    to_status: str = Field(min_length=1)
    event: Optional[str] = Field(default=None, max_length=128)
    note: Optional[str] = Field(default=None, max_length=2048)


class MCPMigrationRunStageRequest(BaseModel):
    entity: str = Field(min_length=1, max_length=128)
    records: List[Dict[str, Any]] = Field(default_factory=list)


class MCPMigrationRunMaterializeRequest(BaseModel):
    """Materialize staged sample records into Neo4j."""

    # Optional: materialize only a subset of entities.
    entities: Optional[List[str]] = Field(default=None)
    # Optional: caller-provided batch identifier to group writes.
    batch_id: Optional[str] = Field(default=None, max_length=128)


class MCPMigrationRunPublishRequest(BaseModel):
    """Publish staged sample records into the selected target service."""

    entities: Optional[List[str]] = Field(default=None)
    batch_id: Optional[str] = Field(default=None, max_length=128)
    # Optional override for OpenSearch index name.
    opensearch_index: Optional[str] = Field(default=None, max_length=256)


class MCPApprovalCreateRequest(BaseModel):
    action: str = Field(min_length=1, max_length=64)
    summary: Optional[str] = Field(default=None, max_length=1024)
    requested_by: Optional[str] = Field(default=None, max_length=128)
    note: Optional[str] = Field(default=None, max_length=2048)
    impact: Dict[str, Any] = Field(default_factory=dict)
    sample: List[Dict[str, Any]] = Field(default_factory=list)


class MCPApprovalDecisionRequest(BaseModel):
    decided_by: Optional[str] = Field(default=None, max_length=128)
    note: Optional[str] = Field(default=None, max_length=2048)


class MCPApprovalRecord(BaseModel):
    approval_id: str
    run_id: str
    action: str
    status: str
    token: Optional[str] = None
    requested_at: Optional[str] = None
    requested_by: Optional[str] = None
    summary: Optional[str] = None
    impact: Dict[str, Any] = Field(default_factory=dict)
    sample: List[Dict[str, Any]] = Field(default_factory=list)
    note: Optional[str] = None
    decided_at: Optional[str] = None
    decided_by: Optional[str] = None
    decision_note: Optional[str] = None


def _require_materialize_approval(
    run_id: str,
    db: Session = Depends(get_db),
    approval_token: Optional[str] = Header(default=None, alias="X-MCP-Approval-Token"),
) -> None:
    _require_approval_token(run_id=run_id, action="materialize", approval_token=approval_token, db=db)


def _require_publish_approval(
    run_id: str,
    db: Session = Depends(get_db),
    approval_token: Optional[str] = Header(default=None, alias="X-MCP-Approval-Token"),
) -> None:
    _require_approval_token(run_id=run_id, action="publish", approval_token=approval_token, db=db)


class MCPMigrationRunMaterializeResponse(BaseModel):
    run_id: str
    written_entities: List[str] = Field(default_factory=list)
    sample_nodes: int = 0
    batch_id: Optional[str] = None


class MCPMigrationRunPublishResponse(BaseModel):
    run_id: str
    target_id: Optional[str] = None
    target_kind: str = ""
    published_entities: List[str] = Field(default_factory=list)
    documents_indexed: int = 0
    index: Optional[str] = None
    batch_id: Optional[str] = None


class MCPMigrationRunHistoryItem(BaseModel):
    at: str
    from_status: Optional[str] = None
    to_status: str
    event: Optional[str] = None
    note: Optional[str] = None


class MCPMigrationRunSummary(BaseModel):
    run_id: str
    workflow_name: str = ""
    status: str
    created_at: str
    updated_at: str
    source_id: Optional[str] = None
    target_id: Optional[str] = None


class MCPMigrationRunDetail(MCPMigrationRunSummary):
    history: List[MCPMigrationRunHistoryItem] = Field(default_factory=list)
    options: Dict[str, Any] = Field(default_factory=dict)

    # A small staging area for tool experiments. We only keep lightweight samples.
    staged: Dict[str, Any] = Field(default_factory=dict)


def _row_to_payload(row: PersistedReport) -> dict[str, Any]:
    payload = dict(row.payload or {})
    # Be defensive: ensure id consistency.
    payload.setdefault("run_id", row.id)
    payload.setdefault("status", "created")
    payload.setdefault("created_at", row.created_at.isoformat() if row.created_at else _utcnow_iso())
    payload.setdefault("updated_at", (row.updated_at.isoformat() if row.updated_at else payload.get("created_at")) or _utcnow_iso())
    payload.setdefault("workflow_name", row.title or "")
    return payload


def _persist_best_effort(db: Session, run_id: str, payload: dict[str, Any]) -> None:
    """Persist payload into `reports` if possible. Never raises (best-effort)."""
    try:
        row = db.query(PersistedReport).filter(PersistedReport.id == run_id).first()
        if row is None:
            row = PersistedReport(
                id=run_id,
                report_type=_REPORT_TYPE,
                title=str(payload.get("workflow_name") or "") or None,
                description=None,
                source="mcp",
                schema_version="1",
                run_id=run_id,
                external_id=None,
                table_name=None,
                payload=dict(payload),
                summary={
                    "status": payload.get("status"),
                    "source_id": payload.get("source_id"),
                    "target_id": payload.get("target_id"),
                },
                is_deleted=0,
            )
            db.add(row)
        else:
            row.title = str(payload.get("workflow_name") or "") or None
            row.payload = dict(payload)
            row.summary = {
                "status": payload.get("status"),
                "source_id": payload.get("source_id"),
                "target_id": payload.get("target_id"),
            }
            row.is_deleted = 0

        db.commit()
    except SQLAlchemyError:
        try:
            db.rollback()
        except Exception:  # pylint: disable=broad-exception-caught
            pass


def _get_run_payload(db: Session, run_id: str) -> Optional[dict[str, Any]]:
    # Prefer DB (source of truth), else in-memory.
    try:
        row = (
            db.query(PersistedReport)
            .filter(PersistedReport.id == run_id)
            .filter(PersistedReport.report_type == _REPORT_TYPE)
            .filter(PersistedReport.is_deleted == 0)
            .first()
        )
        if row is not None:
            return _row_to_payload(row)
    except SQLAlchemyError:
        # fall back to memory
        pass

    with _RUNS_LOCK:
        existing = _RUNS_MEM.get(run_id)
        return dict(existing) if isinstance(existing, dict) else None


def _store_mem(payload: dict[str, Any]) -> None:
    run_id = str(payload.get("run_id") or "").strip()
    if not run_id:
        return
    with _RUNS_LOCK:
        _RUNS_MEM[run_id] = dict(payload)


def _apply_transition(payload: dict[str, Any], to_status: RunStatus, event: Optional[str], note: Optional[str]) -> dict[str, Any]:
    from_status = str(payload.get("status") or "created")
    try:
        from_norm = _normalize_status(from_status)
    except ValueError:
        from_norm = "created"

    if not _transition_allowed(from_norm, to_status):
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Invalid status transition",
                "from": from_norm,
                "to": to_status,
                "allowed": sorted(_ALLOWED_TRANSITIONS.get(from_norm, set())),
            },
        )

    history = list(payload.get("history") or [])
    history.append(
        {
            "at": _utcnow_iso(),
            "from_status": from_norm,
            "to_status": to_status,
            "event": event or None,
            "note": note or None,
        }
    )

    payload = dict(payload)
    payload["status"] = to_status
    payload["updated_at"] = _utcnow_iso()
    payload["history"] = history
    return payload


@router.post("/runs", response_model=MCPMigrationRunDetail)
def create_run(request: MCPMigrationRunCreateRequest, db: Session = Depends(get_db)) -> MCPMigrationRunDetail:
    run_id = uuid.uuid4().hex

    initial: RunStatus = "created"
    if request.initial_status:
        try:
            initial = _normalize_status(request.initial_status)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    payload: dict[str, Any] = {
        "run_id": run_id,
        "workflow_name": (request.workflow_name or "").strip(),
        "source_id": (str(request.source_id).strip() if request.source_id else None),
        "target_id": (str(request.target_id).strip() if request.target_id else None),
        "status": initial,
        "created_at": _utcnow_iso(),
        "updated_at": _utcnow_iso(),
        "history": [
            {
                "at": _utcnow_iso(),
                "from_status": None,
                "to_status": initial,
                "event": "create",
                "note": None,
            }
        ],
        "options": dict(request.options or {}),
        "staged": {},
    }

    _persist_best_effort(db, run_id, payload)
    _store_mem(payload)

    append_audit_event(
        db,
        run_id=run_id,
        action="run.create",
        actor=_AUDIT_ACTOR_DEFAULT,
        details={
            "workflow_name": payload.get("workflow_name"),
            "source_id": payload.get("source_id"),
            "target_id": payload.get("target_id"),
            "status": payload.get("status"),
        },
    )

    return MCPMigrationRunDetail(**payload)


@router.get("/runs", response_model=List[MCPMigrationRunSummary])
def list_runs(
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> List[MCPMigrationRunSummary]:
    items: list[dict[str, Any]] = []

    try:
        rows = (
            db.query(PersistedReport)
            .filter(PersistedReport.report_type == _REPORT_TYPE)
            .filter(PersistedReport.is_deleted == 0)
            .order_by(PersistedReport.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
        for r in rows:
            payload = _row_to_payload(r)
            items.append(payload)
    except SQLAlchemyError:
        # fall back to memory
        with _RUNS_LOCK:
            mem = list(_RUNS_MEM.values())
        mem.sort(key=lambda p: str(p.get("created_at") or ""), reverse=True)
        items = mem[offset : offset + limit]

    return [
        MCPMigrationRunSummary(
            run_id=str(p.get("run_id") or ""),
            workflow_name=str(p.get("workflow_name") or ""),
            status=str(p.get("status") or "created"),
            created_at=str(p.get("created_at") or ""),
            updated_at=str(p.get("updated_at") or p.get("created_at") or ""),
            source_id=(p.get("source_id") if p.get("source_id") else None),
            target_id=(p.get("target_id") if p.get("target_id") else None),
        )
        for p in items
        if str(p.get("run_id") or "").strip()
    ]


@router.get("/runs/{run_id}", response_model=MCPMigrationRunDetail)
def get_run(run_id: str, db: Session = Depends(get_db)) -> MCPMigrationRunDetail:
    payload = _get_run_payload(db, run_id)
    if payload is None:
        raise HTTPException(status_code=404, detail="Run not found")

    # Ensure required keys exist even if older payload.
    payload = dict(payload)
    payload.setdefault("run_id", run_id)
    payload.setdefault("workflow_name", "")
    payload.setdefault("source_id", None)
    payload.setdefault("target_id", None)
    payload.setdefault("status", "created")
    payload.setdefault("created_at", _utcnow_iso())
    payload.setdefault("updated_at", payload.get("created_at") or _utcnow_iso())
    payload.setdefault("history", [])
    payload.setdefault("options", {})
    payload.setdefault("staged", {})

    return MCPMigrationRunDetail(**payload)


@router.get("/runs/{run_id}/approvals", response_model=List[MCPApprovalRecord])
def list_run_approvals(run_id: str, db: Session = Depends(get_db)) -> List[MCPApprovalRecord]:
    payload = _get_run_payload(db, run_id)
    if payload is None:
        raise HTTPException(status_code=404, detail="Run not found")

    items = list_approvals(db, run_id=run_id)
    return [MCPApprovalRecord(**dict(i or {})) for i in items]


@router.post("/runs/{run_id}/approvals", response_model=MCPApprovalRecord)
def create_run_approval(run_id: str, request: MCPApprovalCreateRequest, db: Session = Depends(get_db)) -> MCPApprovalRecord:
    payload = _get_run_payload(db, run_id)
    if payload is None:
        raise HTTPException(status_code=404, detail="Run not found")

    try:
        approval = create_approval_request(
            db,
            run_id=run_id,
            action=request.action,
            summary=request.summary,
            impact=request.impact,
            sample=request.sample,
            requested_by=request.requested_by,
            note=request.note,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    append_audit_event(
        db,
        run_id=run_id,
        action="approval.request",
        actor=request.requested_by or _AUDIT_ACTOR_DEFAULT,
        details={
            "approval_id": approval.get("approval_id"),
            "action": approval.get("action"),
            "status": approval.get("status"),
        },
    )

    return MCPApprovalRecord(**approval)


@router.post("/runs/{run_id}/approvals/{approval_id}/approve", response_model=MCPApprovalRecord)
def approve_run_approval(
    run_id: str,
    approval_id: str,
    request: MCPApprovalDecisionRequest,
    db: Session = Depends(get_db),
) -> MCPApprovalRecord:
    payload = _get_run_payload(db, run_id)
    if payload is None:
        raise HTTPException(status_code=404, detail="Run not found")

    try:
        approval = decide_approval(
            db,
            run_id=run_id,
            approval_id=approval_id,
            decision="approved",
            decided_by=request.decided_by,
            decision_note=request.note,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    append_audit_event(
        db,
        run_id=run_id,
        action="approval.approve",
        actor=request.decided_by or _AUDIT_ACTOR_DEFAULT,
        details={"approval_id": approval_id, "action": approval.get("action")},
    )

    return MCPApprovalRecord(**approval)


@router.post("/runs/{run_id}/approvals/{approval_id}/reject", response_model=MCPApprovalRecord)
def reject_run_approval(
    run_id: str,
    approval_id: str,
    request: MCPApprovalDecisionRequest,
    db: Session = Depends(get_db),
) -> MCPApprovalRecord:
    payload = _get_run_payload(db, run_id)
    if payload is None:
        raise HTTPException(status_code=404, detail="Run not found")

    try:
        approval = decide_approval(
            db,
            run_id=run_id,
            approval_id=approval_id,
            decision="rejected",
            decided_by=request.decided_by,
            decision_note=request.note,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    append_audit_event(
        db,
        run_id=run_id,
        action="approval.reject",
        actor=request.decided_by or _AUDIT_ACTOR_DEFAULT,
        details={"approval_id": approval_id, "action": approval.get("action")},
    )

    return MCPApprovalRecord(**approval)


@router.post("/runs/{run_id}/transition", response_model=MCPMigrationRunDetail)
def transition_run(run_id: str, request: MCPMigrationRunTransitionRequest, db: Session = Depends(get_db)) -> MCPMigrationRunDetail:
    payload = _get_run_payload(db, run_id)
    if payload is None:
        raise HTTPException(status_code=404, detail="Run not found")

    try:
        to_status = _normalize_status(request.to_status)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    payload2 = _apply_transition(payload, to_status, request.event, request.note)

    _persist_best_effort(db, run_id, payload2)
    _store_mem(payload2)

    append_audit_event(
        db,
        run_id=run_id,
        action="run.transition",
        actor=_AUDIT_ACTOR_DEFAULT,
        details={
            "from": payload.get("status"),
            "to": payload2.get("status"),
            "event": request.event,
        },
    )

    return MCPMigrationRunDetail(**payload2)


@router.post("/runs/{run_id}/stage", response_model=MCPMigrationRunDetail)
def stage_records(run_id: str, request: MCPMigrationRunStageRequest, db: Session = Depends(get_db)) -> MCPMigrationRunDetail:
    payload = _get_run_payload(db, run_id)
    if payload is None:
        raise HTTPException(status_code=404, detail="Run not found")

    entity = (request.entity or "").strip()
    if not entity:
        raise HTTPException(status_code=422, detail="entity is required")

    records = list(request.records or [])

    # Keep payload bounded: store count + a tiny sample only.
    sample = records[:5]

    staged = dict(payload.get("staged") or {})
    staged[entity] = {
        "count": len(records),
        "sample": sample,
        "staged_at": _utcnow_iso(),
    }

    payload2 = dict(payload)
    payload2["staged"] = staged
    payload2["updated_at"] = _utcnow_iso()

    _persist_best_effort(db, run_id, payload2)
    _store_mem(payload2)

    append_audit_event(
        db,
        run_id=run_id,
        action="run.stage",
        actor=_AUDIT_ACTOR_DEFAULT,
        details={"entity": entity, "count": len(records)},
    )

    return MCPMigrationRunDetail(**payload2)


@router.post("/runs/{run_id}/materialize", response_model=MCPMigrationRunMaterializeResponse)
async def materialize_staged_samples(
    run_id: str,
    body: MCPMigrationRunMaterializeRequest,
    http_request: Request,
    db: Session = Depends(get_db),
    _: None = Depends(_require_materialize_approval),
) -> MCPMigrationRunMaterializeResponse:
    """Materialize staged *sample* records into the configured target.

    Default behavior materializes to Neo4j. If the run target looks like OpenSearch,
    we index staged sample records into OpenSearch instead.

    Notes:
    - Best-effort: only writes the staged sample (count is kept in SQL, but not written here).
    - Idempotent: MERGE-based upserts.
    """
    payload = _get_run_payload(db, run_id)
    if payload is None:
        raise HTTPException(status_code=404, detail="Run not found")

    # Canonical lineage store: always materialize to Neo4j.
    driver = getattr(http_request.app.state, "driver", None)
    if not driver:
        raise HTTPException(status_code=503, detail="Neo4j driver not initialized or connection failed.")

    writer = MCPStagingGraphWriter(driver)
    summary = await writer.materialize_run_samples(
        run_payload=dict(payload),
        entities=body.entities,
        batch_id=body.batch_id,
    )

    append_audit_event(
        db,
        run_id=run_id,
        action="run.materialize",
        actor=_AUDIT_ACTOR_DEFAULT,
        details={
            "written_entities": summary.get("written_entities"),
            "sample_nodes": summary.get("sample_nodes"),
            "batch_id": summary.get("batch_id"),
            "approvals_required": _approvals_required(),
        },
    )

    # Append an audit history event (status unchanged).
    try:
        payload2 = dict(payload)
        history = list(payload2.get("history") or [])
        history.append(
            {
                "at": _utcnow_iso(),
                "from_status": str(payload2.get("status") or "created"),
                "to_status": str(payload2.get("status") or "created"),
                "event": "materialize",
                "note": json.dumps(
                    {
                        "written_entities": summary.get("written_entities"),
                        "sample_nodes": summary.get("sample_nodes"),
                        "batch_id": summary.get("batch_id"),
                    },
                    ensure_ascii=False,
                ),
            }
        )
        payload2["history"] = history
        payload2["updated_at"] = _utcnow_iso()
        _persist_best_effort(db, run_id, payload2)
        _store_mem(payload2)
    except Exception:
        # Non-fatal: graph write already occurred.
        pass

    return MCPMigrationRunMaterializeResponse(
        run_id=str(summary.get("run_id") or run_id),
        written_entities=list(summary.get("written_entities") or []),
        sample_nodes=int(summary.get("sample_nodes") or 0),
        batch_id=(summary.get("batch_id") if summary.get("batch_id") else None),
    )


@router.post("/runs/{run_id}/publish", response_model=MCPMigrationRunPublishResponse)
async def publish_staged_samples(
    run_id: str,
    body: MCPMigrationRunPublishRequest,
    http_request: Request,
    db: Session = Depends(get_db),
    approval_token: Optional[str] = Header(default=None, alias="X-MCP-Approval-Token"),
) -> MCPMigrationRunPublishResponse:
    """Publish staged *sample* records to the configured target service.

    Architecture intent:
    - Neo4j remains the canonical lineage/traceability store.
    - This endpoint publishes to the selected target (OpenSearch for now) and
      records publish events back into Neo4j.
    """
    payload = _get_run_payload(db, run_id)
    if payload is None:
        raise HTTPException(status_code=404, detail="Run not found")

    target_id = payload.get("target_id")
    if not _is_opensearch_target(target_id):
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Publish is only supported for OpenSearch targets in this slice",
                "target_id": target_id,
            },
        )

    # Only enforce approvals once we know the action is applicable.
    _require_approval_token(run_id=run_id, action="publish", approval_token=approval_token, db=db)

    # Determine OpenSearch index name (best-effort from connection extra_options).
    index_name = (body.opensearch_index or "").strip()
    if not index_name and isinstance(target_id, str) and target_id.startswith("conn_"):
        conn_id = target_id[len("conn_") :]
        extra = _try_get_admin_connection_extra_options(db, conn_id=conn_id)
        idx = extra.get("index") or extra.get("opensearch_index") or extra.get("default_index")
        if idx:
            index_name = str(idx).strip()
    if not index_name:
        index_name = _opensearch_default_index()

    # Publish to OpenSearch.
    publish_summary = _publish_samples_to_opensearch(db=db, run_payload=dict(payload), entities=body.entities, index=index_name)

    # Record publish events in Neo4j for traceability.
    driver = getattr(http_request.app.state, "driver", None)
    if not driver:
        raise HTTPException(status_code=503, detail="Neo4j driver not initialized or connection failed.")

    writer = MCPStagingGraphWriter(driver)
    lineage_docs = list(publish_summary.get("documents") or [])
    await writer.record_published_documents(
        run_id=str(payload.get("run_id") or run_id),
        target_id=(str(target_id).strip() if target_id else None),
        target_kind="opensearch",
        index=str(publish_summary.get("index") or index_name),
        documents=lineage_docs,
        batch_id=body.batch_id,
    )

    append_audit_event(
        db,
        run_id=run_id,
        action="run.publish",
        actor=_AUDIT_ACTOR_DEFAULT,
        details={
            "target_kind": "opensearch",
            "index": publish_summary.get("index") or index_name,
            "published_entities": publish_summary.get("written_entities"),
            "documents_indexed": publish_summary.get("sample_nodes"),
            "approvals_required": _approvals_required(),
        },
    )

    # Append a history event (status unchanged).
    try:
        payload2 = dict(payload)
        history = list(payload2.get("history") or [])
        history.append(
            {
                "at": _utcnow_iso(),
                "from_status": str(payload2.get("status") or "created"),
                "to_status": str(payload2.get("status") or "created"),
                "event": "publish",
                "note": json.dumps(
                    {
                        "target_kind": "opensearch",
                        "index": publish_summary.get("index") or index_name,
                        "published_entities": publish_summary.get("written_entities"),
                        "documents_indexed": publish_summary.get("sample_nodes"),
                    },
                    ensure_ascii=False,
                ),
            }
        )
        payload2["history"] = history
        payload2["updated_at"] = _utcnow_iso()
        _persist_best_effort(db, run_id, payload2)
        _store_mem(payload2)
    except Exception:
        pass

    return MCPMigrationRunPublishResponse(
        run_id=str(publish_summary.get("run_id") or run_id),
        target_id=(str(target_id).strip() if target_id else None),
        target_kind="opensearch",
        published_entities=list(publish_summary.get("written_entities") or []),
        documents_indexed=int(publish_summary.get("sample_nodes") or 0),
        index=str(publish_summary.get("index") or index_name),
        batch_id=(body.batch_id if body.batch_id else None),
    )
