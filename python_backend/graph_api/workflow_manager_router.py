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
from sqlalchemy.orm import Session
from starlette.responses import Response

from core.db_session import get_db
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

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/workflows", tags=["Workflows"])

# In-memory cache; DB is authoritative persistence.
WORKFLOWS_STORE: Dict[str, Dict[str, Any]] = {}
_WORKFLOWS_STORE_LOCK = asyncio.Lock()


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

    if action == "start":
        if status == WorkflowStatus.RUNNING:
            # Idempotent start: returning 200 avoids noisy UX when a user clicks
            # "Run" multiple times or the UI refreshes mid-run.
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
        # Minimal session id to support lineage capture.
        meta.setdefault("migration_session_id", f"ms_{uuid.uuid4().hex[:12]}")
        wf["execution_metadata"] = meta

        wf["last_execution_id"] = f"exec_{uuid.uuid4().hex[:10]}"
        message = "Workflow started"

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
