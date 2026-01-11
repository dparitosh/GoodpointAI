from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, cast

import json
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, Response, UploadFile
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import JSONResponse

from core.db_session import get_db
from core.external_config import filesystem_config
from models.workflow_models import WorkflowInstance
from sqlalchemy.orm import Session

router = APIRouter(prefix="/api", tags=["Compatibility"])


@router.get("/openapi.json")
async def openapi_json(request: Request):
    return JSONResponse(request.app.openapi())


@router.get("/docs")
async def swagger_ui_html():
    return get_swagger_ui_html(
        openapi_url="/api/openapi.json",
        title="GoodPoint AgenticAI API Docs",
    )


@router.get("/status")
async def get_status() -> Dict[str, Any]:
    # Lightweight status endpoint for clients that expect /api/status.
    return {
        "status": "ok",
        "timestamp": datetime.now(timezone.utc).replace(tzinfo=None).isoformat() + "Z",
    }


@router.get("/analytics/nodes")
async def analytics_nodes(
    response: Response,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    response.headers["X-Total-Count"] = str(len(items))
    return items[skip : skip + limit]


@router.get("/analytics/relationships")
async def analytics_relationships(
    response: Response,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    response.headers["X-Total-Count"] = str(len(items))
    return items[skip : skip + limit]


@router.get("/analytics/data-quality")
async def analytics_data_quality() -> Dict[str, Any]:
    return {
        "summary": {
            "total_tables_scanned": 0,
            "average_quality_score": 0,
            "critical_issues": 0,
            "total_issues": 0,
        },
        "recent_scans": [],
        "quality_trends": [],
        "top_issues": [],
    }


@router.get("/schema/discover")
async def schema_discover() -> Dict[str, Any]:
    return {
        "tables": [],
        "views": [],
        "schemas": [],
    }


@router.get("/schema/constraints")
async def schema_constraints(
    response: Response,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    response.headers["X-Total-Count"] = str(len(items))
    return items[skip : skip + limit]


@router.get("/user/preferences")
async def user_preferences() -> Dict[str, Any]:
    return {}


@router.get("/system/settings")
async def system_settings() -> Dict[str, Any]:
    return {}


@router.get("/dashboards")
async def dashboards(
    response: Response,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    response.headers["X-Total-Count"] = str(len(items))
    return items[skip : skip + limit]


@router.get("/pipelines")
async def pipelines(
    response: Response,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    response.headers["X-Total-Count"] = str(len(items))
    return items[skip : skip + limit]


@router.get("/reports")
async def reports(
    response: Response,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    response.headers["X-Total-Count"] = str(len(items))
    return items[skip : skip + limit]


@router.post("/reports/generate")
async def generate_report() -> Dict[str, Any]:
    return {"status": "queued"}


@router.get("/convert/templates")
async def convert_templates(
    response: Response,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    response.headers["X-Total-Count"] = str(len(items))
    return items[skip : skip + limit]


@router.get("/mappings/templates")
async def mapping_templates(
    response: Response,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    response.headers["X-Total-Count"] = str(len(items))
    return items[skip : skip + limit]


@router.get("/monitoring/health")
async def monitoring_health() -> Dict[str, Any]:
    return {"status": "healthy"}


@router.get("/monitoring/flow-metrics")
async def monitoring_flow_metrics() -> Dict[str, Any]:
    return {"metrics": []}


@router.get("/etl/metrics")
async def etl_metrics(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Compatibility ETL metrics endpoint.

    Returns real, database-derived operational metrics when available.
    If no workflows exist yet, fields will be null rather than fabricated.
    """

    workflows: List[WorkflowInstance] = db.query(WorkflowInstance).all()
    if not workflows:
        return {
            "latestStatus": None,
            "ingestionVolume": None,
            "pendingDQIssues": None,
            "criticalDQIssues": None,
            "scheduledJobs": None,
            "lastRemediation": None,
        }

    def _ts(wf: WorkflowInstance) -> datetime:
        # Prefer updated_at, then created_at, then epoch.
        return cast(datetime, wf.updated_at or wf.created_at or datetime(1970, 1, 1, tzinfo=timezone.utc))

    latest = max(workflows, key=_ts)
    total_processed = sum(int(w.processed_records or 0) for w in workflows)
    failed_workflows = sum(1 for w in workflows if str(getattr(w.status, "value", w.status)) == "failed")
    scheduled = sum(1 for w in workflows if bool(getattr(w, "schedule_enabled", False)))

    return {
        "latestStatus": str(getattr(latest.status, "value", latest.status)),
        "ingestionVolume": total_processed,
        # No reliable cross-source definition available here; avoid inventing counts.
        "pendingDQIssues": None,
        "criticalDQIssues": failed_workflows,
        "scheduledJobs": scheduled,
        "lastRemediation": None,
    }


@router.get("/migration/v2")
async def migration_v2() -> Dict[str, Any]:
    return {"version": "v2", "status": "available"}


@router.get("/data")
async def data_placeholder() -> Dict[str, Any]:
    return {"status": "ok"}


@router.get("/config/backup")
@router.post("/config/backup")
async def config_backup(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Create a lightweight backup of core configuration.

    Includes workflow instances (DB) and selected JSON config files.
    """

    workflows: List[Dict[str, Any]] = []
    for row in db.query(WorkflowInstance).all():
        workflows.append(
            {
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
                "workflow_config": row.workflow_config or {},
                "ai_agents_enabled": row.ai_agents_enabled or [],
                "status": getattr(row.status, "value", str(row.status)),
                "current_stage": getattr(row.current_stage, "value", str(row.current_stage)),
                "progress_percentage": float(row.progress_percentage or 0.0),
                "total_records": int(row.total_records or 0),
                "processed_records": int(row.processed_records or 0),
                "failed_records": int(row.failed_records or 0),
                "quality_score": row.quality_score,
                "execution_metadata": row.execution_metadata or {},
                "last_execution_id": row.last_execution_id,
                "created_at": row.created_at.isoformat() if row.created_at else None,
                "updated_at": row.updated_at.isoformat() if row.updated_at else None,
            }
        )

    def _read_json(path: Path) -> Any:
        try:
            if not path.exists():
                return None
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None

    return {
        "version": 1,
        "workflows": workflows,
        "data_sources": _read_json(Path("data_sources.json")),
        "agentic_config": _read_json(Path("agentic_config.json")),
    }


@router.get("/config/restore")
@router.post("/config/restore")
async def config_restore(payload: Dict[str, Any], db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Restore a backup created by /api/config/backup.

    This is intentionally conservative (best-effort upsert for workflows + writes JSON config files).
    """

    workflows = payload.get("workflows")
    if workflows is not None and not isinstance(workflows, list):
        raise HTTPException(status_code=400, detail="Invalid backup: workflows must be a list")

    restored_workflows = 0

    # Stage config file writes first (best-effort saga): write to temp files and only
    # replace the real files after DB commit succeeds.
    staged_files: List[tuple[Path, Path]] = []
    for key, filename in (
        ("data_sources", "data_sources.json"),
        ("agentic_config", "agentic_config.json"),
    ):
        obj = payload.get(key)
        if obj is None:
            continue

        tmp_path = Path(f"{filename}.tmp")
        try:
            tmp_path.write_text(json.dumps(obj, indent=2), encoding="utf-8")
        except (OSError, TypeError, ValueError) as e:
            raise HTTPException(status_code=400, detail=f"Invalid {key} payload: {e}") from e

        staged_files.append((tmp_path, Path(filename)))

    try:
        if isinstance(workflows, list):
            for wf in workflows:
                if not isinstance(wf, dict):
                    continue
                wf_id = str(wf.get("id") or "").strip()
                if not wf_id:
                    continue

                row = db.query(WorkflowInstance).filter(WorkflowInstance.id == wf_id).first()
                if row is None:
                    row = WorkflowInstance(id=wf_id)
                    db.add(row)

                model: Any = cast(Any, row)
                model.name = str(wf.get("name") or model.name or "")
                model.description = wf.get("description")
                model.source_id = str(wf.get("source_id") or model.source_id or "")
                model.source_name = str(wf.get("source_name") or model.source_name or "")
                model.source_type = str(wf.get("source_type") or model.source_type or "")
                model.source_config = wf.get("source_config") or {}
                model.target_id = str(wf.get("target_id") or model.target_id or "")
                model.target_name = str(wf.get("target_name") or model.target_name or "")
                model.target_type = str(wf.get("target_type") or model.target_type or "")
                model.target_config = wf.get("target_config") or {}
                model.workflow_config = wf.get("workflow_config") or {}
                model.ai_agents_enabled = wf.get("ai_agents_enabled") or []

                restored_workflows += 1

        db.commit()
    except Exception as e:
        db.rollback()
        for tmp_path, _final_path in staged_files:
            try:
                if tmp_path.exists():
                    tmp_path.unlink()
            except OSError:
                pass
        raise HTTPException(status_code=500, detail=f"Restore failed: {e}") from e

    # Apply staged config writes after DB commit.
    for tmp_path, final_path in staged_files:
        try:
            tmp_path.replace(final_path)
        except OSError as e:
            raise HTTPException(status_code=500, detail=f"Failed writing {final_path.name}: {e}") from e

    return {"status": "success", "restored_workflows": restored_workflows}


@router.get("/config/export")
@router.post("/config/export")
async def config_export(db: Session = Depends(get_db)) -> Dict[str, Any]:
    # Alias to backup for compatibility.
    return await config_backup(db)


@router.post("/data/upload")
async def data_upload(file: UploadFile = File(...)) -> Dict[str, Any]:
    """Compatibility alias for file upload.

    Writes into the configured uploads directory.
    """

    if not file.filename:
        raise HTTPException(status_code=400, detail="Missing upload filename")

    upload_dir = Path(filesystem_config.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    dest = upload_dir / file.filename

    content = await file.read()
    max_mb = float(getattr(filesystem_config, "max_upload_size_mb", 50) or 50)
    size_mb = len(content) / (1024 * 1024)
    if size_mb > max_mb:
        raise HTTPException(status_code=413, detail=f"File too large: {size_mb:.2f}MB (max: {max_mb}MB)")

    dest.write_bytes(content)
    return {"status": "success", "file_name": file.filename, "file_path": str(dest), "size": len(content)}
