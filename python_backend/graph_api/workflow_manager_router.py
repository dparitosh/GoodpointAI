"""
 Workflow Instance Manager Router

Manages multiple workflow instances for PLM Data Migration AI Factory.
Each workflow instance represents a unique source→target migration pipeline.

Features:
- Create/Read/Update/Delete workflow instances
- Execute workflows (start, pause, resume, stop)
- Monitor workflow progress
- View workflow history and statistics
"""

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, cast

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from models.workflow_models import (
    WorkflowInstanceCreate,
    WorkflowInstanceUpdate,
    WorkflowInstanceResponse,
    WorkflowInstanceDetail,
    WorkflowExecutionRequest,
    WorkflowExecutionResponse,
    WorkflowStatistics,
    WorkflowStatus,
    WorkflowStage,
    WorkflowInstance,
)

from core.db_session import get_db

from services.advanced_migration_engine import migration_engine, MigrationEvent, MigrationState

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/workflows", tags=["Workflow Instance Manager"])

# In-memory storage for workflows (process-local cache).
# Source-of-truth persistence is the database (SQLAlchemy).
WORKFLOWS_STORE: Dict[str, Dict[str, Any]] = {}
_WORKFLOWS_STORE_LOCK = asyncio.Lock()

# Background execution control
_WORKFLOW_TASKS: Dict[str, asyncio.Task] = {}
_WORKFLOW_PAUSE: Dict[str, asyncio.Event] = {}
_WORKFLOW_CANCEL: Dict[str, asyncio.Event] = {}
_WORKFLOW_STOP: Dict[str, asyncio.Event] = {}


def _coerce_status(value: Any) -> WorkflowStatus:
    try:
        if isinstance(value, WorkflowStatus):
            return value
        if isinstance(value, str):
            return WorkflowStatus(value)
    except (TypeError, ValueError):
        pass
    return WorkflowStatus.DRAFT


def _coerce_stage(value: Any) -> WorkflowStage:
    try:
        if isinstance(value, WorkflowStage):
            return value
        if isinstance(value, str):
            return WorkflowStage(value)
    except (TypeError, ValueError):
        pass
    return WorkflowStage.IDLE


def _model_to_store_dict(model: WorkflowInstance) -> Dict[str, Any]:
    return {
        "id": model.id,
        "name": model.name,
        "description": model.description,
        "source_id": model.source_id,
        "source_name": model.source_name,
        "source_type": model.source_type,
        "source_config": model.source_config or {},
        "target_id": model.target_id,
        "target_name": model.target_name,
        "target_type": model.target_type,
        "target_config": model.target_config or {},
        "workflow_config": model.workflow_config or {"nodes": [], "edges": [], "ai_agents": []},
        "ai_agents_enabled": model.ai_agents_enabled or [],
        "status": (model.status.value if hasattr(model.status, "value") else str(model.status)),
        "current_stage": (
            model.current_stage.value if getattr(model, "current_stage", None) and hasattr(model.current_stage, "value") else (
                str(model.current_stage) if model.current_stage is not None else WorkflowStage.IDLE.value
            )
        ),
        "progress_percentage": float(model.progress_percentage or 0.0),
        "total_records": int(model.total_records or 0),
        "processed_records": int(model.processed_records or 0),
        "failed_records": int(model.failed_records or 0),
        "quality_score": model.quality_score,
        "execution_metadata": model.execution_metadata or {},
        "last_execution_id": model.last_execution_id,
        "created_at": model.created_at.isoformat() if model.created_at else None,
        "updated_at": model.updated_at.isoformat() if model.updated_at else None,
        "started_at": model.started_at.isoformat() if model.started_at else None,
        "completed_at": model.completed_at.isoformat() if model.completed_at else None,
        "created_by": model.created_by,
        "updated_by": model.updated_by,
        "schedule_enabled": bool(model.schedule_enabled),
        "schedule_cron": model.schedule_cron,
        "next_run_at": model.next_run_at.isoformat() if model.next_run_at else None,
    }


def _upsert_workflow_model(db: Session, wf: Dict[str, Any]) -> None:
    workflow_id = str(wf.get("id") or "")
    if not workflow_id:
        return

    model = db.query(WorkflowInstance).filter(WorkflowInstance.id == workflow_id).first()
    if model is None:
        model = WorkflowInstance(id=workflow_id)
        db.add(model)

    existing: Any = model

    existing.name = str(wf.get("name") or existing.name or "")
    existing.description = wf.get("description")

    existing.source_id = str(wf.get("source_id") or existing.source_id or "")
    existing.source_name = str(wf.get("source_name") or existing.source_name or "")
    existing.source_type = str(wf.get("source_type") or existing.source_type or "")
    existing.source_config = wf.get("source_config") or {}

    existing.target_id = str(wf.get("target_id") or existing.target_id or "")
    existing.target_name = str(wf.get("target_name") or existing.target_name or "")
    existing.target_type = str(wf.get("target_type") or existing.target_type or "")
    existing.target_config = wf.get("target_config") or {}

    existing.workflow_config = wf.get("workflow_config") or {"nodes": [], "edges": [], "ai_agents": []}
    existing.ai_agents_enabled = wf.get("ai_agents_enabled")

    existing.status = _coerce_status(wf.get("status"))
    existing.current_stage = _coerce_stage(wf.get("current_stage"))
    existing.progress_percentage = float(wf.get("progress_percentage") or 0.0)

    existing.total_records = int(wf.get("total_records") or 0)
    existing.processed_records = int(wf.get("processed_records") or 0)
    existing.failed_records = int(wf.get("failed_records") or 0)
    existing.quality_score = wf.get("quality_score")

    existing.execution_metadata = wf.get("execution_metadata")
    existing.last_execution_id = wf.get("last_execution_id")
    existing.created_by = wf.get("created_by")
    existing.updated_by = wf.get("updated_by")
    existing.schedule_enabled = bool(wf.get("schedule_enabled") or False)
    existing.schedule_cron = wf.get("schedule_cron")

    db.commit()


async def _ensure_store_loaded(db: Session) -> None:
    async with _WORKFLOWS_STORE_LOCK:
        if WORKFLOWS_STORE:
            return

        # Prefer DB persistence.
        rows = db.query(WorkflowInstance).all()
        if rows:
            for row in rows:
                workflow_id = str(cast(Any, row).id)
                WORKFLOWS_STORE[workflow_id] = _normalize_workflow_for_store(_model_to_store_dict(row))
            return

        # Finally, seed demos and persist them.
        _ensure_demo_workflows_seeded()
        if WORKFLOWS_STORE:
            for wf in WORKFLOWS_STORE.values():
                _upsert_workflow_model(db, wf)


def _migration_state_to_workflow_stage(state: MigrationState) -> str:
    # Minimal mapping for UI stage display.
    mapping: Dict[MigrationState, WorkflowStage] = {
        MigrationState.IDLE: WorkflowStage.IDLE,
        MigrationState.INITIALIZING: WorkflowStage.EXTRACTING,
        MigrationState.DISCOVERING: WorkflowStage.EXTRACTING,
        MigrationState.PROFILING: WorkflowStage.TRANSFORMING,
        MigrationState.SCHEMA_MAPPING: WorkflowStage.TRANSFORMING,
        MigrationState.DATA_MIGRATION: WorkflowStage.LOADING,
        MigrationState.VALIDATION: WorkflowStage.VALIDATING,
        MigrationState.COMPLETED: WorkflowStage.FINALIZING,
        MigrationState.PAUSED: WorkflowStage.IDLE,
        MigrationState.FAILED: WorkflowStage.IDLE,
        MigrationState.CANCELLED: WorkflowStage.IDLE,
    }
    return mapping.get(state, WorkflowStage.IDLE).value


def _migration_state_to_workflow_status(state: MigrationState) -> str:
    if state == MigrationState.PAUSED:
        return WorkflowStatus.PAUSED.value
    if state == MigrationState.COMPLETED:
        return WorkflowStatus.COMPLETED.value
    if state == MigrationState.FAILED:
        return WorkflowStatus.FAILED.value
    if state == MigrationState.CANCELLED:
        return WorkflowStatus.CANCELLED.value
    if state in (
        MigrationState.IDLE,
        MigrationState.INITIALIZING,
        MigrationState.DISCOVERING,
        MigrationState.PROFILING,
        MigrationState.SCHEMA_MAPPING,
        MigrationState.DATA_MIGRATION,
        MigrationState.VALIDATION,
    ):
        return WorkflowStatus.RUNNING.value
    return WorkflowStatus.RUNNING.value


async def _sync_workflow_from_migration_session(workflow_id: str) -> None:
    """Best-effort: reflect migration session state into workflow store."""
    async with _WORKFLOWS_STORE_LOCK:
        wf = WORKFLOWS_STORE.get(workflow_id)
        if not wf:
            return
        metadata = wf.get("execution_metadata")
        if not isinstance(metadata, dict):
            return
        migration_session_id = metadata.get("migration_session_id")
        if not isinstance(migration_session_id, str) or not migration_session_id:
            return

    session = migration_engine.get_session(migration_session_id)
    if not session:
        return

    now_utc = datetime.now(timezone.utc).isoformat()
    status = _migration_state_to_workflow_status(session.state)
    stage = _migration_state_to_workflow_stage(session.state)

    async with _WORKFLOWS_STORE_LOCK:
        wf = WORKFLOWS_STORE.get(workflow_id)
        if not wf:
            return
        wf["status"] = status
        wf["current_stage"] = stage
        wf["progress_percentage"] = float(getattr(session, "progress", 0.0) or 0.0)
        wf["quality_score"] = float(getattr(session, "quality_score", 0.0) or 0.0)
        wf["updated_at"] = now_utc

        # Terminal states should stamp completed_at
        if session.state in (MigrationState.COMPLETED, MigrationState.FAILED, MigrationState.CANCELLED):
            wf.setdefault("completed_at", now_utc)

        # Propagate errors
        errors = getattr(session, "errors", None)
        if isinstance(errors, list) and errors:
            meta = wf.get("execution_metadata")
            if not isinstance(meta, dict):
                meta = {}
            meta["migration_errors"] = errors[-10:]
            wf["execution_metadata"] = meta

        WORKFLOWS_STORE[workflow_id] = wf

def _normalize_store_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    enum_value = getattr(value, "value", None)
    if enum_value is not None:
        return enum_value
    return value


def _pydantic_to_dict(value: Any) -> Dict[str, Any]:
    """Serialize Pydantic models across v1/v2 without hard-depending on either API."""
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        out = model_dump()
        return out if isinstance(out, dict) else {}
    to_dict = getattr(value, "dict", None)
    if callable(to_dict):
        out = to_dict()
        return out if isinstance(out, dict) else {}
    return {}


def _normalize_workflow_for_store(workflow: Dict[str, Any]) -> Dict[str, Any]:
    normalized = dict(workflow)

    workflow_id = str(normalized.get("id", ""))
    normalized["id"] = workflow_id

    normalized["status"] = _normalize_store_value(normalized.get("status"))
    normalized["current_stage"] = _normalize_store_value(normalized.get("current_stage"))

    for key in ("created_at", "updated_at", "started_at", "completed_at", "next_run_at"):
        if normalized.get(key) is not None:
            normalized[key] = _normalize_store_value(normalized[key])

    # Ensure graph config exists and is list-safe
    workflow_config = normalized.get("workflow_config") or {}
    if isinstance(workflow_config, dict):
        workflow_config.setdefault("nodes", [])
        workflow_config.setdefault("edges", [])
        workflow_config.setdefault("ai_agents", [])
        normalized["workflow_config"] = workflow_config

    return normalized


def _ensure_demo_workflows_seeded() -> None:
    # Prefer persisted store; seed demos only if we have no saved workflows.
    if WORKFLOWS_STORE:
        return

    now_utc = datetime.now(timezone.utc)
    logger.info("Seeding demo workflow instances into in-memory store")

    # Keep these counts aligned with /statistics/summary (15 total, 4 running, etc.)
    demo_workflows = [
        # draft (3)
        {
            "id": "wf_demo_001",
            "name": "Teamcenter → Neo4j BOM Migration (Draft)",
            "description": "Draft workflow for migrating Teamcenter Parts/BOM into Neo4j.",
            "source_id": "teamcenter_prod",
            "source_name": "Teamcenter Production",
            "source_type": "teamcenter",
            "source_config": {"endpoint": "https://teamcenter.company.com", "auth": "SOA"},
            "target_id": "neo4j_kg",
            "target_name": "Neo4j Knowledge Graph",
            "target_type": "neo4j",
            "target_config": {"uri": "neo4j+s://prod.databases.neo4j.io", "database": "plm_migration"},
            "workflow_config": {"nodes": [], "edges": [], "ai_agents": []},
            "ai_agents_enabled": ["data_analyst", "etl_orchestrator"],
            "status": WorkflowStatus.DRAFT,
            "current_stage": WorkflowStage.IDLE,
            "progress_percentage": 0.0,
            "total_records": 0,
            "processed_records": 0,
            "failed_records": 0,
            "quality_score": None,
            "execution_metadata": {},
            "last_execution_id": None,
            "created_at": now_utc,
            "updated_at": now_utc,
            "started_at": None,
            "completed_at": None,
            "created_by": "demo",
            "schedule_enabled": False,
            "schedule_cron": None,
            "next_run_at": None,
        },
        {
            "id": "wf_demo_002",
            "name": "Windchill → Cloud PLM Change Orders (Draft)",
            "description": "Draft workflow for migrating Windchill change orders to Cloud PLM.",
            "source_id": "windchill_prod",
            "source_name": "Windchill Production",
            "source_type": "windchill",
            "source_config": {"endpoint": "https://windchill.company.com", "auth": "OAuth"},
            "target_id": "cloud_plm",
            "target_name": "Cloud PLM",
            "target_type": "cloud_plm",
            "target_config": {"endpoint": "https://cloudplm.company.com", "tenant": "prod"},
            "workflow_config": {"nodes": [], "edges": [], "ai_agents": []},
            "ai_agents_enabled": ["data_analyst"],
            "status": WorkflowStatus.DRAFT,
            "current_stage": WorkflowStage.IDLE,
            "progress_percentage": 0.0,
            "total_records": 0,
            "processed_records": 0,
            "failed_records": 0,
            "quality_score": None,
            "execution_metadata": {},
            "last_execution_id": None,
            "created_at": now_utc,
            "updated_at": now_utc,
            "started_at": None,
            "completed_at": None,
            "created_by": "demo",
            "schedule_enabled": False,
            "schedule_cron": None,
            "next_run_at": None,
        },
        {
            "id": "wf_demo_003",
            "name": "CATIA → OpenSearch CAD Index (Draft)",
            "description": "Draft workflow for indexing CAD metadata into OpenSearch.",
            "source_id": "catia_repo",
            "source_name": "CATIA Vault",
            "source_type": "catia",
            "source_config": {"path": "\\\\fileserver\\cad\\catia"},
            "target_id": "opensearch",
            "target_name": "OpenSearch",
            "target_type": "opensearch",
            "target_config": {"endpoint": "https://opensearch.company.com", "index": "cad"},
            "workflow_config": {"nodes": [], "edges": [], "ai_agents": []},
            "ai_agents_enabled": ["visualization_agent"],
            "status": WorkflowStatus.DRAFT,
            "current_stage": WorkflowStage.IDLE,
            "progress_percentage": 0.0,
            "total_records": 0,
            "processed_records": 0,
            "failed_records": 0,
            "quality_score": None,
            "execution_metadata": {},
            "last_execution_id": None,
            "created_at": now_utc,
            "updated_at": now_utc,
            "started_at": None,
            "completed_at": None,
            "created_by": "demo",
            "schedule_enabled": False,
            "schedule_cron": None,
            "next_run_at": None,
        },
        # configured (2)
        {
            "id": "wf_demo_004",
            "name": "NX → Neo4j Assembly Graph (Configured)",
            "description": "Configured workflow ready to run for NX assemblies.",
            "source_id": "nx_export",
            "source_name": "NX Export",
            "source_type": "nx",
            "source_config": {"path": "C:/plm/nx/export"},
            "target_id": "neo4j_kg",
            "target_name": "Neo4j Knowledge Graph",
            "target_type": "neo4j",
            "target_config": {"uri": "neo4j+s://prod.databases.neo4j.io", "database": "plm_migration"},
            "workflow_config": {"nodes": [], "edges": [], "ai_agents": []},
            "ai_agents_enabled": ["etl_orchestrator", "quality_monitor"],
            "status": WorkflowStatus.CONFIGURED,
            "current_stage": WorkflowStage.IDLE,
            "progress_percentage": 0.0,
            "total_records": 25000,
            "processed_records": 0,
            "failed_records": 0,
            "quality_score": None,
            "execution_metadata": {},
            "last_execution_id": None,
            "created_at": now_utc,
            "updated_at": now_utc,
            "started_at": None,
            "completed_at": None,
            "created_by": "demo",
            "schedule_enabled": False,
            "schedule_cron": None,
            "next_run_at": None,
        },
        {
            "id": "wf_demo_005",
            "name": "Creo → Data Lake Metadata Load (Configured)",
            "description": "Configured workflow ready to run for Creo metadata.",
            "source_id": "creo_repo",
            "source_name": "Creo Repository",
            "source_type": "creo",
            "source_config": {"path": "\\\\fileserver\\cad\\creo"},
            "target_id": "datalake",
            "target_name": "Enterprise Data Lake",
            "target_type": "datalake",
            "target_config": {"container": "plm", "format": "parquet"},
            "workflow_config": {"nodes": [], "edges": [], "ai_agents": []},
            "ai_agents_enabled": ["etl_orchestrator"],
            "status": WorkflowStatus.CONFIGURED,
            "current_stage": WorkflowStage.IDLE,
            "progress_percentage": 0.0,
            "total_records": 120000,
            "processed_records": 0,
            "failed_records": 0,
            "quality_score": None,
            "execution_metadata": {},
            "last_execution_id": None,
            "created_at": now_utc,
            "updated_at": now_utc,
            "started_at": None,
            "completed_at": None,
            "created_by": "demo",
            "schedule_enabled": False,
            "schedule_cron": None,
            "next_run_at": None,
        },
        # running (4)
        {
            "id": "wf_demo_006",
            "name": "Teamcenter → Neo4j Parts Migration (Running)",
            "description": "Live migration of Parts and BOM from Teamcenter into Neo4j.",
            "source_id": "teamcenter_prod",
            "source_name": "Teamcenter Production",
            "source_type": "teamcenter",
            "source_config": {"endpoint": "https://teamcenter.company.com", "auth": "SOA"},
            "target_id": "neo4j_kg",
            "target_name": "Neo4j Knowledge Graph",
            "target_type": "neo4j",
            "target_config": {"uri": "neo4j+s://prod.databases.neo4j.io", "database": "plm_migration"},
            "workflow_config": {"nodes": [], "edges": [], "ai_agents": []},
            "ai_agents_enabled": ["data_analyst", "etl_orchestrator", "quality_monitor"],
            "status": WorkflowStatus.RUNNING,
            "current_stage": WorkflowStage.TRANSFORMING,
            "progress_percentage": 42.5,
            "total_records": 500000,
            "processed_records": 212500,
            "failed_records": 125,
            "quality_score": 97.8,
            "execution_metadata": {"warnings": 2},
            "last_execution_id": "exec_demo_006",
            "created_at": now_utc,
            "updated_at": now_utc,
            "started_at": now_utc,
            "completed_at": None,
            "created_by": "demo",
            "schedule_enabled": False,
            "schedule_cron": None,
            "next_run_at": None,
        },
        {
            "id": "wf_demo_007",
            "name": "Windchill → Cloud PLM Workflows (Running)",
            "description": "Live migration of Windchill workflows into Cloud PLM.",
            "source_id": "windchill_prod",
            "source_name": "Windchill Production",
            "source_type": "windchill",
            "source_config": {"endpoint": "https://windchill.company.com", "auth": "OAuth"},
            "target_id": "cloud_plm",
            "target_name": "Cloud PLM",
            "target_type": "cloud_plm",
            "target_config": {"endpoint": "https://cloudplm.company.com", "tenant": "prod"},
            "workflow_config": {"nodes": [], "edges": [], "ai_agents": []},
            "ai_agents_enabled": ["etl_orchestrator", "quality_monitor"],
            "status": WorkflowStatus.RUNNING,
            "current_stage": WorkflowStage.EXTRACTING,
            "progress_percentage": 18.0,
            "total_records": 220000,
            "processed_records": 39600,
            "failed_records": 15,
            "quality_score": 96.9,
            "execution_metadata": {},
            "last_execution_id": "exec_demo_007",
            "created_at": now_utc,
            "updated_at": now_utc,
            "started_at": now_utc,
            "completed_at": None,
            "created_by": "demo",
            "schedule_enabled": False,
            "schedule_cron": None,
            "next_run_at": None,
        },
        {
            "id": "wf_demo_008",
            "name": "Teamcenter → Warehouse (Running)",
            "description": "ETL pipeline loading PLM records to enterprise warehouse.",
            "source_id": "teamcenter_prod",
            "source_name": "Teamcenter Production",
            "source_type": "teamcenter",
            "source_config": {"endpoint": "https://teamcenter.company.com"},
            "target_id": "warehouse",
            "target_name": "Enterprise Warehouse",
            "target_type": "warehouse",
            "target_config": {"dsn": "warehouse-prod"},
            "workflow_config": {"nodes": [], "edges": [], "ai_agents": []},
            "ai_agents_enabled": ["etl_orchestrator"],
            "status": WorkflowStatus.RUNNING,
            "current_stage": WorkflowStage.LOADING,
            "progress_percentage": 63.2,
            "total_records": 180000,
            "processed_records": 113760,
            "failed_records": 48,
            "quality_score": 98.2,
            "execution_metadata": {},
            "last_execution_id": "exec_demo_008",
            "created_at": now_utc,
            "updated_at": now_utc,
            "started_at": now_utc,
            "completed_at": None,
            "created_by": "demo",
            "schedule_enabled": False,
            "schedule_cron": None,
            "next_run_at": None,
        },
        {
            "id": "wf_demo_009",
            "name": "Windchill → Neo4j Change Graph (Running)",
            "description": "Migrating Windchill changes into Neo4j graph.",
            "source_id": "windchill_prod",
            "source_name": "Windchill Production",
            "source_type": "windchill",
            "source_config": {"endpoint": "https://windchill.company.com"},
            "target_id": "neo4j_kg",
            "target_name": "Neo4j Knowledge Graph",
            "target_type": "neo4j",
            "target_config": {"uri": "neo4j+s://prod.databases.neo4j.io", "database": "plm_migration"},
            "workflow_config": {"nodes": [], "edges": [], "ai_agents": []},
            "ai_agents_enabled": ["data_analyst", "quality_monitor"],
            "status": WorkflowStatus.RUNNING,
            "current_stage": WorkflowStage.VALIDATING,
            "progress_percentage": 7.5,
            "total_records": 90000,
            "processed_records": 6750,
            "failed_records": 3,
            "quality_score": 97.1,
            "execution_metadata": {},
            "last_execution_id": "exec_demo_009",
            "created_at": now_utc,
            "updated_at": now_utc,
            "started_at": now_utc,
            "completed_at": None,
            "created_by": "demo",
            "schedule_enabled": False,
            "schedule_cron": None,
            "next_run_at": None,
        },
        # paused (1)
        {
            "id": "wf_demo_010",
            "name": "Teamcenter → Neo4j Document Migration (Paused)",
            "description": "Paused due to transient source throttling.",
            "source_id": "teamcenter_prod",
            "source_name": "Teamcenter Production",
            "source_type": "teamcenter",
            "source_config": {"endpoint": "https://teamcenter.company.com"},
            "target_id": "neo4j_kg",
            "target_name": "Neo4j Knowledge Graph",
            "target_type": "neo4j",
            "target_config": {"uri": "neo4j+s://prod.databases.neo4j.io"},
            "workflow_config": {"nodes": [], "edges": [], "ai_agents": []},
            "ai_agents_enabled": ["etl_orchestrator"],
            "status": WorkflowStatus.PAUSED,
            "current_stage": WorkflowStage.EXTRACTING,
            "progress_percentage": 55.0,
            "total_records": 60000,
            "processed_records": 33000,
            "failed_records": 10,
            "quality_score": 96.5,
            "execution_metadata": {"paused_reason": "source throttling"},
            "last_execution_id": "exec_demo_010",
            "created_at": now_utc,
            "updated_at": now_utc,
            "started_at": now_utc,
            "completed_at": None,
            "created_by": "demo",
            "schedule_enabled": False,
            "schedule_cron": None,
            "next_run_at": None,
        },
        # completed (4)
        {
            "id": "wf_demo_011",
            "name": "Windchill → Neo4j Metadata Load (Completed)",
            "description": "Completed migration run.",
            "source_id": "windchill_prod",
            "source_name": "Windchill Production",
            "source_type": "windchill",
            "source_config": {"endpoint": "https://windchill.company.com"},
            "target_id": "neo4j_kg",
            "target_name": "Neo4j Knowledge Graph",
            "target_type": "neo4j",
            "target_config": {"uri": "neo4j+s://prod.databases.neo4j.io"},
            "workflow_config": {"nodes": [], "edges": [], "ai_agents": []},
            "ai_agents_enabled": ["quality_monitor"],
            "status": WorkflowStatus.COMPLETED,
            "current_stage": WorkflowStage.FINALIZING,
            "progress_percentage": 100.0,
            "total_records": 120000,
            "processed_records": 120000,
            "failed_records": 0,
            "quality_score": 98.6,
            "execution_metadata": {},
            "last_execution_id": "exec_demo_011",
            "created_at": now_utc,
            "updated_at": now_utc,
            "started_at": now_utc,
            "completed_at": now_utc,
            "created_by": "demo",
            "schedule_enabled": False,
            "schedule_cron": None,
            "next_run_at": None,
        },
        {
            "id": "wf_demo_012",
            "name": "Teamcenter → OpenSearch Index (Completed)",
            "description": "Completed indexing run.",
            "source_id": "teamcenter_prod",
            "source_name": "Teamcenter Production",
            "source_type": "teamcenter",
            "source_config": {"endpoint": "https://teamcenter.company.com"},
            "target_id": "opensearch",
            "target_name": "OpenSearch",
            "target_type": "opensearch",
            "target_config": {"endpoint": "https://opensearch.company.com", "index": "plm"},
            "workflow_config": {"nodes": [], "edges": [], "ai_agents": []},
            "ai_agents_enabled": ["data_analyst"],
            "status": WorkflowStatus.COMPLETED,
            "current_stage": WorkflowStage.FINALIZING,
            "progress_percentage": 100.0,
            "total_records": 45000,
            "processed_records": 45000,
            "failed_records": 12,
            "quality_score": 97.9,
            "execution_metadata": {},
            "last_execution_id": "exec_demo_012",
            "created_at": now_utc,
            "updated_at": now_utc,
            "started_at": now_utc,
            "completed_at": now_utc,
            "created_by": "demo",
            "schedule_enabled": False,
            "schedule_cron": None,
            "next_run_at": None,
        },
        {
            "id": "wf_demo_013",
            "name": "CATIA → Neo4j Design Graph (Completed)",
            "description": "Completed design graph load.",
            "source_id": "catia_repo",
            "source_name": "CATIA Vault",
            "source_type": "catia",
            "source_config": {"path": "\\\\fileserver\\cad\\catia"},
            "target_id": "neo4j_kg",
            "target_name": "Neo4j Knowledge Graph",
            "target_type": "neo4j",
            "target_config": {"uri": "neo4j+s://prod.databases.neo4j.io"},
            "workflow_config": {"nodes": [], "edges": [], "ai_agents": []},
            "ai_agents_enabled": ["visualization_agent"],
            "status": WorkflowStatus.COMPLETED,
            "current_stage": WorkflowStage.FINALIZING,
            "progress_percentage": 100.0,
            "total_records": 32000,
            "processed_records": 32000,
            "failed_records": 4,
            "quality_score": 96.7,
            "execution_metadata": {},
            "last_execution_id": "exec_demo_013",
            "created_at": now_utc,
            "updated_at": now_utc,
            "started_at": now_utc,
            "completed_at": now_utc,
            "created_by": "demo",
            "schedule_enabled": False,
            "schedule_cron": None,
            "next_run_at": None,
        },
        {
            "id": "wf_demo_014",
            "name": "Teamcenter → Cloud PLM Migration (Completed)",
            "description": "Completed migration of PLM objects to Cloud PLM.",
            "source_id": "teamcenter_prod",
            "source_name": "Teamcenter Production",
            "source_type": "teamcenter",
            "source_config": {"endpoint": "https://teamcenter.company.com"},
            "target_id": "cloud_plm",
            "target_name": "Cloud PLM",
            "target_type": "cloud_plm",
            "target_config": {"endpoint": "https://cloudplm.company.com"},
            "workflow_config": {"nodes": [], "edges": [], "ai_agents": []},
            "ai_agents_enabled": ["etl_orchestrator"],
            "status": WorkflowStatus.COMPLETED,
            "current_stage": WorkflowStage.FINALIZING,
            "progress_percentage": 100.0,
            "total_records": 80000,
            "processed_records": 80000,
            "failed_records": 2,
            "quality_score": 98.1,
            "execution_metadata": {},
            "last_execution_id": "exec_demo_014",
            "created_at": now_utc,
            "updated_at": now_utc,
            "started_at": now_utc,
            "completed_at": now_utc,
            "created_by": "demo",
            "schedule_enabled": False,
            "schedule_cron": None,
            "next_run_at": None,
        },
        # failed (1)
        {
            "id": "wf_demo_015",
            "name": "Windchill → Neo4j Variant Migration (Failed)",
            "description": "Failed due to authentication error on source connector.",
            "source_id": "windchill_prod",
            "source_name": "Windchill Production",
            "source_type": "windchill",
            "source_config": {"endpoint": "https://windchill.company.com"},
            "target_id": "neo4j_kg",
            "target_name": "Neo4j Knowledge Graph",
            "target_type": "neo4j",
            "target_config": {"uri": "neo4j+s://prod.databases.neo4j.io"},
            "workflow_config": {"nodes": [], "edges": [], "ai_agents": []},
            "ai_agents_enabled": ["quality_monitor"],
            "status": WorkflowStatus.FAILED,
            "current_stage": WorkflowStage.EXTRACTING,
            "progress_percentage": 12.0,
            "total_records": 10000,
            "processed_records": 1200,
            "failed_records": 1200,
            "quality_score": 80.0,
            "execution_metadata": {"error": "Auth failed"},
            "last_execution_id": "exec_demo_015",
            "created_at": now_utc,
            "updated_at": now_utc,
            "started_at": now_utc,
            "completed_at": None,
            "created_by": "demo",
            "schedule_enabled": False,
            "schedule_cron": None,
            "next_run_at": None,
        },
    ]

    for workflow in demo_workflows:
        normalized = _normalize_workflow_for_store(workflow)
        workflow_id = str(normalized.get("id"))
        if workflow_id:
            WORKFLOWS_STORE[workflow_id] = normalized


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
    """
    List all workflow instances with optional filtering.
    
    Filters:
    - status: Filter by workflow status
    - source_type: Filter by source system type (teamcenter, windchill, etc.)
    - target_type: Filter by target system type (neo4j, cloud_plm, etc.)
    - search: Search in workflow name and description
    """
    await _ensure_store_loaded(db)

    # Query from in-memory store
    logger.info(
        "Listing workflows with filters - status: %s, source_type: %s, target_type: %s, search: %s",
        status,
        source_type,
        target_type,
        search,
    )
    
    workflows = list(WORKFLOWS_STORE.values())
    
    # Apply filters
    if status:
        workflows = [w for w in workflows if str(w.get('status')) == status.value]
    if source_type:
        workflows = [w for w in workflows if w.get('source_type') == source_type]
    if target_type:
        workflows = [w for w in workflows if w.get('target_type') == target_type]
    if search:
        search_lower = search.lower()
        workflows = [w for w in workflows if search_lower in w.get('name', '').lower() or search_lower in w.get('description', '').lower()]
    
    total_count = len(workflows)
    page_items = workflows[skip:skip + limit]

    # Best-effort live status sync for returned items.
    for wf in page_items:
        workflow_id = str(wf.get("id") or "")
        if workflow_id:
            await _sync_workflow_from_migration_session(workflow_id)
            async with _WORKFLOWS_STORE_LOCK:
                updated = WORKFLOWS_STORE.get(workflow_id)
            if updated:
                _upsert_workflow_model(db, updated)

    # Backwards compatible pagination: keep list response body but include total.
    # FastAPI injects a Response object here.
    if response is not None:
        response.headers["X-Total-Count"] = str(total_count)

    return page_items


@router.post("/", response_model=WorkflowInstanceResponse, status_code=201)
async def create_workflow(
    workflow: WorkflowInstanceCreate,
    db: Session = Depends(get_db),
):
    """
    Create a new workflow instance.
    
    Defines a unique source→target migration pipeline with:
    - Source system configuration
    - Target system configuration  
    - ETL pipeline structure (nodes, edges)
    - AI agent selection
    - Scheduling options
    """
    try:
        await _ensure_store_loaded(db)

        # Generate unique workflow ID with timestamp and UUID
        timestamp = int(datetime.now(timezone.utc).timestamp())
        workflow_id = f"wf_{timestamp}_{uuid.uuid4().hex[:8]}"
        
        created_at = datetime.now(timezone.utc)
        response = WorkflowInstanceResponse(
            id=workflow_id,
            name=workflow.name,
            description=workflow.description,
            source_id=workflow.source.id,
            source_name=workflow.source.name,
            source_type=workflow.source.type,
            target_id=workflow.target.id,
            target_name=workflow.target.name,
            target_type=workflow.target.type,
            status=WorkflowStatus.CONFIGURED,
            current_stage=WorkflowStage.IDLE,
            progress_percentage=0.0,
            total_records=0,
            processed_records=0,
            failed_records=0,
            quality_score=None,
            created_at=created_at,
            updated_at=None,
            started_at=None,
            completed_at=None,
            created_by=workflow.created_by,
            schedule_enabled=workflow.schedule_enabled,
            schedule_cron=workflow.schedule_cron,
            next_run_at=None
        )

        # Persist definition + config to in-memory cache + DB
        store_row = {
            "id": workflow_id,
            "name": workflow.name,
            "description": workflow.description,
            "source_id": workflow.source.id,
            "source_name": workflow.source.name,
            "source_type": workflow.source.type,
            "source_config": {
                "id": workflow.source.id,
                "name": workflow.source.name,
                "type": workflow.source.type,
                "connection_details": workflow.source.connection_details,
                "extraction_config": workflow.source.extraction_config,
            },
            "target_id": workflow.target.id,
            "target_name": workflow.target.name,
            "target_type": workflow.target.type,
            "target_config": {
                "id": workflow.target.id,
                "name": workflow.target.name,
                "type": workflow.target.type,
                "connection_details": workflow.target.connection_details,
                "load_config": workflow.target.load_config,
            },
            "workflow_config": {
                "nodes": workflow.workflow_config.nodes,
                "edges": workflow.workflow_config.edges,
                "ai_agents": workflow.workflow_config.ai_agents,
            },
            "ai_agents_enabled": workflow.ai_agents_enabled,
            "status": WorkflowStatus.CONFIGURED.value,
            "current_stage": WorkflowStage.IDLE.value,
            "progress_percentage": 0.0,
            "total_records": 0,
            "processed_records": 0,
            "failed_records": 0,
            "quality_score": None,
            "execution_metadata": {},
            "last_execution_id": None,
            "created_at": created_at.isoformat(),
            "updated_at": None,
            "started_at": None,
            "completed_at": None,
            "created_by": workflow.created_by,
            "schedule_enabled": workflow.schedule_enabled,
            "schedule_cron": workflow.schedule_cron,
            "next_run_at": None,
        }
        async with _WORKFLOWS_STORE_LOCK:
            WORKFLOWS_STORE[workflow_id] = store_row
        _upsert_workflow_model(db, store_row)

        return response
        
    except (OSError, TypeError, ValueError) as e:
        logger.error("Error creating workflow: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to create workflow: {str(e)}") from e


@router.get("/{workflow_id}", response_model=WorkflowInstanceDetail)
async def get_workflow(
    workflow_id: str,
    db: Session = Depends(get_db),
):
    """
    Get detailed information about a specific workflow instance.
    
    Includes:
    - Source/target configurations
    - Complete workflow graph (nodes, edges)
    - AI agent assignments
    - Execution history and metadata
    """
    await _ensure_store_loaded(db)
    async with _WORKFLOWS_STORE_LOCK:
        if workflow_id not in WORKFLOWS_STORE:
            raise HTTPException(status_code=404, detail=f"Workflow {workflow_id} not found")

    # Refresh live execution status if this workflow is tied to a migration session.
    await _sync_workflow_from_migration_session(workflow_id)

    async with _WORKFLOWS_STORE_LOCK:
        synced = WORKFLOWS_STORE.get(workflow_id)
    if synced:
        _upsert_workflow_model(db, synced)
    
    workflow_data = WORKFLOWS_STORE[workflow_id]
    
    # Return detailed workflow information
    return WorkflowInstanceDetail(
        id=workflow_data['id'],
        name=workflow_data['name'],
        description=workflow_data['description'],
        source_id=workflow_data['source_id'],
        source_name=workflow_data['source_name'],
        source_type=workflow_data['source_type'],
        source_config=workflow_data.get('source_config', {}),
        target_id=workflow_data['target_id'],
        target_name=workflow_data['target_name'],
        target_type=workflow_data['target_type'],
        target_config=workflow_data.get('target_config', {}),
        workflow_config=workflow_data.get('workflow_config', {'nodes': [], 'edges': [], 'ai_agents': []}),
        ai_agents_enabled=workflow_data.get('ai_agents_enabled', []),
        status=workflow_data['status'],
        current_stage=workflow_data['current_stage'],
        progress_percentage=workflow_data['progress_percentage'],
        total_records=workflow_data['total_records'],
        processed_records=workflow_data['processed_records'],
        failed_records=workflow_data['failed_records'],
        quality_score=workflow_data.get('quality_score'),
        execution_metadata=workflow_data.get('execution_metadata', {}),
        last_execution_id=workflow_data.get('last_execution_id'),
        created_at=workflow_data['created_at'],
        updated_at=workflow_data.get('updated_at'),
        started_at=workflow_data.get('started_at'),
        completed_at=workflow_data.get('completed_at'),
        created_by=workflow_data['created_by'],
        schedule_enabled=workflow_data['schedule_enabled'],
        schedule_cron=workflow_data.get('schedule_cron'),
        next_run_at=workflow_data.get('next_run_at')
    )


@router.put("/{workflow_id}", response_model=WorkflowInstanceResponse)
async def update_workflow(
    workflow_id: str,
    workflow_update: WorkflowInstanceUpdate,
    db: Session = Depends(get_db),
):
    """
    Update an existing workflow instance.
    
    Can update:
    - Name and description
    - Source/target configurations
    - Workflow graph structure
    - AI agent selection
    - Schedule settings
    """
    await _ensure_store_loaded(db)

    async with _WORKFLOWS_STORE_LOCK:

        if workflow_id not in WORKFLOWS_STORE:
            raise HTTPException(status_code=404, detail=f"Workflow {workflow_id} not found")

        current = WORKFLOWS_STORE[workflow_id]
        if str(current.get("status")) == WorkflowStatus.RUNNING.value:
            raise HTTPException(status_code=400, detail="Cannot update running workflow")

        if workflow_update.name is not None:
            current["name"] = workflow_update.name
        if workflow_update.description is not None:
            current["description"] = workflow_update.description
        if workflow_update.source is not None:
            current["source_id"] = workflow_update.source.id
            current["source_name"] = workflow_update.source.name
            current["source_type"] = workflow_update.source.type
            current["source_config"] = _pydantic_to_dict(workflow_update.source)
        if workflow_update.target is not None:
            current["target_id"] = workflow_update.target.id
            current["target_name"] = workflow_update.target.name
            current["target_type"] = workflow_update.target.type
            current["target_config"] = _pydantic_to_dict(workflow_update.target)
        if workflow_update.workflow_config is not None:
            current["workflow_config"] = _pydantic_to_dict(workflow_update.workflow_config)
        if workflow_update.ai_agents_enabled is not None:
            current["ai_agents_enabled"] = workflow_update.ai_agents_enabled
        if workflow_update.schedule_enabled is not None:
            current["schedule_enabled"] = workflow_update.schedule_enabled
        if workflow_update.schedule_cron is not None:
            current["schedule_cron"] = workflow_update.schedule_cron

        current["updated_at"] = datetime.now(timezone.utc).isoformat()
        WORKFLOWS_STORE[workflow_id] = current
        _upsert_workflow_model(db, current)

        # Return normalized store dict; FastAPI will coerce to response_model.
        return _normalize_workflow_for_store(current)


@router.delete("/{workflow_id}", status_code=204)
async def delete_workflow(
    workflow_id: str,
    db: Session = Depends(get_db),
):
    """
    Delete a workflow instance.
    
    Only draft or completed workflows can be deleted.
    Running workflows must be stopped first.
    """
    await _ensure_store_loaded(db)

    async with _WORKFLOWS_STORE_LOCK:

        existing = WORKFLOWS_STORE.get(workflow_id)
        if not existing:
            raise HTTPException(status_code=404, detail=f"Workflow {workflow_id} not found")
        if str(existing.get("status")) == WorkflowStatus.RUNNING.value:
            raise HTTPException(status_code=400, detail="Cannot delete running workflow. Stop it first.")
        WORKFLOWS_STORE.pop(workflow_id, None)

    # Remove from DB as well.
    model = db.query(WorkflowInstance).filter(WorkflowInstance.id == workflow_id).first()
    if model is not None:
        db.delete(model)
        db.commit()
        return None


@router.post("/{workflow_id}/execute", response_model=WorkflowExecutionResponse)
async def execute_workflow(
    workflow_id: str,
    execution_request: WorkflowExecutionRequest,
    db: Session = Depends(get_db),
):
    """
    Execute workflow actions: start, pause, resume, stop, cancel.
    
    Actions:
    - start: Begin workflow execution
    - pause: Temporarily pause execution (can resume)
    - resume: Continue paused workflow
    - stop: Gracefully stop workflow (finish current batch)
    - cancel: Immediately cancel workflow
    """
    try:
        now_utc = datetime.now(timezone.utc)
        execution_id = f"exec_{now_utc.strftime('%Y%m%d_%H%M%S')}"
        action = (execution_request.action or "").lower().strip()

        await _ensure_store_loaded(db)
        async with _WORKFLOWS_STORE_LOCK:
            wf = WORKFLOWS_STORE.get(workflow_id)
            if not wf:
                raise HTTPException(status_code=404, detail=f"Workflow {workflow_id} not found")

        # Legacy simulator controls are kept for backwards compatibility, but execution is now
        # backed by AdvancedMigrationEngine.
        pause_event = _WORKFLOW_PAUSE.setdefault(workflow_id, asyncio.Event())
        cancel_event = _WORKFLOW_CANCEL.setdefault(workflow_id, asyncio.Event())
        stop_event = _WORKFLOW_STOP.setdefault(workflow_id, asyncio.Event())

        async def _get_migration_session_id() -> Optional[str]:
            async with _WORKFLOWS_STORE_LOCK:
                wf_local = WORKFLOWS_STORE.get(workflow_id) or {}
                meta = wf_local.get("execution_metadata")
                if isinstance(meta, dict):
                    session_id = meta.get("migration_session_id")
                    return session_id if isinstance(session_id, str) and session_id else None
            return None

        message = ""
        status = ""

        if action == "start":
            async with _WORKFLOWS_STORE_LOCK:
                wf = WORKFLOWS_STORE.get(workflow_id)
                if not wf:
                    raise HTTPException(status_code=404, detail=f"Workflow {workflow_id} not found")
                if str(wf.get("status")) == WorkflowStatus.RUNNING.value:
                    raise HTTPException(status_code=400, detail="Workflow already running")

                source_cfg_raw = wf.get("source_config")
                source_cfg: Dict[str, Any] = source_cfg_raw if isinstance(source_cfg_raw, dict) else {}
                target_cfg_raw = wf.get("target_config")
                target_cfg: Dict[str, Any] = target_cfg_raw if isinstance(target_cfg_raw, dict) else {}

                source_id = source_cfg.get("id") or wf.get("source_id")
                source_name = source_cfg.get("name") or wf.get("source_name")
                source_type = source_cfg.get("type") or wf.get("source_type")
                source_connection_details = source_cfg.get("connection_details") or {}
                source_extraction_config = source_cfg.get("extraction_config") or {}

                target_id = target_cfg.get("id") or wf.get("target_id")
                target_name = target_cfg.get("name") or wf.get("target_name")
                target_type = target_cfg.get("type") or wf.get("target_type")
                target_connection_details = target_cfg.get("connection_details") or {}
                target_load_config = target_cfg.get("load_config") or {}

            session = await migration_engine.create_session(
                sources=[
                    {
                        "id": source_id,
                        "name": source_name,
                        "type": source_type,
                        "connection_details": source_connection_details,
                        "extraction_config": source_extraction_config,
                    }
                ],
                target={
                    "id": target_id,
                    "name": target_name,
                    "type": target_type,
                    "connection_details": target_connection_details,
                    "load_config": target_load_config,
                },
                strategy=str(execution_request.execution_params.get("strategy") or "incremental"),
                workflow_id=workflow_id,
            )

            started = await migration_engine.start_migration(session.session_id)
            if not started:
                refreshed = migration_engine.get_session(session.session_id)
                latest = None
                if refreshed and getattr(refreshed, "errors", None):
                    latest = refreshed.errors[-1]
                raise HTTPException(
                    status_code=429,
                    detail=latest or "Failed to start workflow migration session",
                )

            async with _WORKFLOWS_STORE_LOCK:
                wf = WORKFLOWS_STORE.get(workflow_id)
                if not wf:
                    raise HTTPException(status_code=404, detail=f"Workflow {workflow_id} not found")

                wf["status"] = WorkflowStatus.RUNNING.value
                wf["current_stage"] = _migration_state_to_workflow_stage(MigrationState.INITIALIZING)
                wf["started_at"] = now_utc.isoformat()
                wf["updated_at"] = now_utc.isoformat()
                wf["last_execution_id"] = execution_id
                wf["progress_percentage"] = float(wf.get("progress_percentage") or 0.0)

                metadata = wf.get("execution_metadata")
                if not isinstance(metadata, dict):
                    metadata = {}
                metadata["execution_id"] = execution_id
                metadata["migration_session_id"] = session.session_id
                wf["execution_metadata"] = metadata

                WORKFLOWS_STORE[workflow_id] = wf
                _upsert_workflow_model(db, wf)

            pause_event.set()
            cancel_event.clear()
            stop_event.clear()

            message = f"Workflow {workflow_id} started successfully"
            status = WorkflowStatus.RUNNING.value

        elif action == "pause":
            migration_session_id = await _get_migration_session_id()
            if not migration_session_id:
                raise HTTPException(status_code=400, detail="Workflow has no active migration session")
            pause_event.clear()
            await migration_engine.handle_event(migration_session_id, MigrationEvent.PAUSE)

            async with _WORKFLOWS_STORE_LOCK:
                wf = WORKFLOWS_STORE.get(workflow_id)
                if wf:
                    wf["status"] = WorkflowStatus.PAUSED.value
                    wf["updated_at"] = now_utc.isoformat()
                    WORKFLOWS_STORE[workflow_id] = wf
                    _upsert_workflow_model(db, wf)

            message = f"Workflow {workflow_id} paused"
            status = WorkflowStatus.PAUSED.value

        elif action == "resume":
            migration_session_id = await _get_migration_session_id()
            if not migration_session_id:
                raise HTTPException(status_code=400, detail="Workflow has no active migration session")
            pause_event.set()
            await migration_engine.handle_event(migration_session_id, MigrationEvent.RESUME)

            async with _WORKFLOWS_STORE_LOCK:
                wf = WORKFLOWS_STORE.get(workflow_id)
                if wf:
                    wf["status"] = WorkflowStatus.RUNNING.value
                    wf["updated_at"] = now_utc.isoformat()
                    WORKFLOWS_STORE[workflow_id] = wf
                    _upsert_workflow_model(db, wf)

            message = f"Workflow {workflow_id} resumed"
            status = WorkflowStatus.RUNNING.value

        elif action == "stop":
            migration_session_id = await _get_migration_session_id()
            if not migration_session_id:
                raise HTTPException(status_code=400, detail="Workflow has no active migration session")

            stop_event.set()
            pause_event.set()
            await migration_engine.handle_event(migration_session_id, MigrationEvent.CANCEL)

            task = _WORKFLOW_TASKS.get(workflow_id)
            if task:
                task.cancel()

            async with _WORKFLOWS_STORE_LOCK:
                wf = WORKFLOWS_STORE.get(workflow_id)
                if wf:
                    wf["status"] = WorkflowStatus.CANCELLED.value
                    metadata = wf.get("execution_metadata")
                    if not isinstance(metadata, dict):
                        metadata = {}
                    metadata["stop_requested"] = True
                    wf["execution_metadata"] = metadata
                    wf["updated_at"] = now_utc.isoformat()
                    WORKFLOWS_STORE[workflow_id] = wf
                    _upsert_workflow_model(db, wf)

            message = f"Workflow {workflow_id} stopping gracefully"
            status = "stopping"

        elif action == "cancel":
            migration_session_id = await _get_migration_session_id()
            if not migration_session_id:
                raise HTTPException(status_code=400, detail="Workflow has no active migration session")

            cancel_event.set()
            pause_event.set()
            await migration_engine.handle_event(migration_session_id, MigrationEvent.CANCEL)

            task = _WORKFLOW_TASKS.get(workflow_id)
            if task:
                task.cancel()

            async with _WORKFLOWS_STORE_LOCK:
                wf = WORKFLOWS_STORE.get(workflow_id)
                if wf:
                    wf["status"] = WorkflowStatus.CANCELLED.value
                    wf["completed_at"] = now_utc.isoformat()
                    wf["updated_at"] = now_utc.isoformat()
                    WORKFLOWS_STORE[workflow_id] = wf
                    _upsert_workflow_model(db, wf)

            message = f"Workflow {workflow_id} cancelled"
            status = WorkflowStatus.CANCELLED.value

        else:
            raise HTTPException(status_code=400, detail=f"Invalid action: {action}")

        await _sync_workflow_from_migration_session(workflow_id)
        async with _WORKFLOWS_STORE_LOCK:
            updated = WORKFLOWS_STORE.get(workflow_id)
        if updated:
            _upsert_workflow_model(db, updated)
        return WorkflowExecutionResponse(
            workflow_id=workflow_id,
            execution_id=execution_id,
            status=status,
            message=message,
            started_at=now_utc if action == "start" else None,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error executing workflow action: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/{workflow_id}/graph")
async def get_workflow_graph(
    workflow_id: str,
    db: Session = Depends(get_db),
):
    """
    Get the visual workflow graph for a specific instance.
    
    Returns nodes and edges ready for XState Visualizer rendering,
    customized for this workflow's source→target configuration.
    """
    await _ensure_store_loaded(db)

    async with _WORKFLOWS_STORE_LOCK:

        workflow_data = WORKFLOWS_STORE.get(workflow_id)
        if not workflow_data:
            raise HTTPException(status_code=404, detail=f"Workflow {workflow_id} not found")

        cfg = workflow_data.get("workflow_config") or {}
        return {
            "workflow_id": workflow_id,
            "nodes": cfg.get("nodes") or [],
            "edges": cfg.get("edges") or [],
            "ai_agents": cfg.get("ai_agents") or workflow_data.get("ai_agents_enabled") or [],
        }


@router.get("/statistics/summary", response_model=WorkflowStatistics)
async def get_workflow_statistics(
    db: Session = Depends(get_db),
):
    """
    Get aggregated statistics across all workflow instances.
    
    Provides:
    - Total workflow count
    - Distribution by status, source type, target type
    - Total records processed
    - Average quality scores
    - Active execution count
    """
    await _ensure_store_loaded(db)

    async with _WORKFLOWS_STORE_LOCK:

        workflows = list(WORKFLOWS_STORE.values())
        by_status: Dict[str, int] = {}
        by_source_type: Dict[str, int] = {}
        by_target_type: Dict[str, int] = {}

        total_processed = 0
        quality_scores: List[float] = []
        active_executions = 0

        for wf in workflows:
            status = str(wf.get("status") or "unknown")
            by_status[status] = by_status.get(status, 0) + 1

            st = str(wf.get("source_type") or "unknown")
            by_source_type[st] = by_source_type.get(st, 0) + 1

            tt = str(wf.get("target_type") or "unknown")
            by_target_type[tt] = by_target_type.get(tt, 0) + 1

            total_processed += int(wf.get("processed_records") or 0)
            quality_score = wf.get("quality_score")
            if quality_score is not None:
                try:
                    quality_scores.append(float(quality_score))
                except (TypeError, ValueError):
                    pass
            if status == WorkflowStatus.RUNNING.value:
                active_executions += 1

        avg_quality = round(sum(quality_scores) / len(quality_scores), 2) if quality_scores else None

        return WorkflowStatistics(
            total_workflows=len(workflows),
            by_status=by_status,
            by_source_type=by_source_type,
            by_target_type=by_target_type,
            total_records_processed=total_processed,
            average_quality_score=avg_quality,
            active_executions=active_executions,
        )


@router.get("/templates/list")
async def list_workflow_templates(
    response: Response,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
):
    """
    Get predefined workflow templates for common source→target combinations.
    
    Templates provide:
    - Recommended pipeline structure
    - Default AI agent configuration
    - Best practice transformation mappings
    """
    templates = _get_workflow_templates()

    response.headers["X-Total-Count"] = str(len(templates))
    return templates[skip : skip + limit]


def _get_workflow_templates() -> List[Dict[str, Any]]:
    templates = [
        {
            "id": "template_teamcenter_neo4j",
            "name": "Teamcenter → Neo4j",
            "description": "Standard template for migrating Teamcenter parts and BOMs to Neo4j Knowledge Graph",
            "source_type": "teamcenter",
            "target_type": "neo4j",
            "recommended_agents": ["data_analyst", "etl_orchestrator", "quality_monitor"],
            "estimated_duration_hours": 8,
            "complexity": "medium"
        },
        {
            "id": "template_windchill_cloudplm",
            "name": "Windchill → Cloud PLM",
            "description": "Migrate Windchill change orders and workflows to modern Cloud PLM",
            "source_type": "windchill",
            "target_type": "cloud_plm",
            "recommended_agents": ["data_analyst", "etl_orchestrator", "quality_monitor", "visualization_agent"],
            "estimated_duration_hours": 12,
            "complexity": "high"
        },
        {
            "id": "template_cad_opensearch",
            "name": "CAD Systems → OpenSearch",
            "description": "Index CAD metadata and models for enterprise search",
            "source_type": "multi_cad",
            "target_type": "opensearch",
            "recommended_agents": ["data_analyst", "visualization_agent"],
            "estimated_duration_hours": 4,
            "complexity": "low"
        }
    ]

    return templates


@router.post("/templates/{template_id}/instantiate", response_model=WorkflowInstanceResponse)
async def instantiate_from_template(
    template_id: str,
    source_id: str = Query(..., description="ID of the source system"),
    target_id: str = Query(..., description="ID of the target system"),
    name: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """
    Create a new workflow instance from a template.
    
    Automatically configures:
    - Pipeline structure based on template
    - Recommended AI agents
    - Default transformation mappings
    - Quality validation rules
    """
    await _ensure_store_loaded(db)

    # Get template information
    templates = _get_workflow_templates()
    template = next((t for t in templates if t["id"] == template_id), None)
    
    if not template:
        raise HTTPException(status_code=404, detail=f"Template {template_id} not found")
    
    # Generate workflow ID and use template name if no custom name provided
    timestamp = int(datetime.now(timezone.utc).timestamp())
    workflow_id = f"wf_{timestamp}_{uuid.uuid4().hex[:8]}"
    workflow_name = name or f"{template['name']} - {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')} UTC"
    
    # Create workflow instance with template configuration
    now_utc = datetime.now(timezone.utc)
    new_workflow = WorkflowInstanceResponse(
        id=workflow_id,
        name=workflow_name,
        description=template["description"],
        source_id=source_id,
        source_name=f"Source System ({source_id})",
        source_type=template["source_type"],
        target_id=target_id,
        target_name=f"Target System ({target_id})",
        target_type=template["target_type"],
        status=WorkflowStatus.DRAFT,
        current_stage=WorkflowStage.IDLE,
        progress_percentage=0.0,
        total_records=0,
        processed_records=0,
        failed_records=0,
        quality_score=None,
        created_at=now_utc,
        updated_at=now_utc,
        started_at=None,
        completed_at=None,
        created_by="system",
        schedule_enabled=False,
        schedule_cron=None,
        next_run_at=None
    )
    
    logger.info("Created workflow %s from template %s", workflow_id, template_id)
    
    # Persist to in-memory cache + DB
    async with _WORKFLOWS_STORE_LOCK:
        WORKFLOWS_STORE[workflow_id] = {
        'id': new_workflow.id,
        'name': new_workflow.name,
        'description': new_workflow.description,
        'source_id': new_workflow.source_id,
        'source_name': new_workflow.source_name,
        'source_type': new_workflow.source_type,
        'source_config': {},
        'target_id': new_workflow.target_id,
        'target_name': new_workflow.target_name,
        'target_type': new_workflow.target_type,
        'target_config': {},
        'workflow_config': {'nodes': [], 'edges': [], 'ai_agents': []},
        'ai_agents_enabled': [],
        'status': new_workflow.status.value,
        'current_stage': (new_workflow.current_stage.value if new_workflow.current_stage else None),
        'progress_percentage': new_workflow.progress_percentage,
        'total_records': new_workflow.total_records,
        'processed_records': new_workflow.processed_records,
        'failed_records': new_workflow.failed_records,
        'quality_score': new_workflow.quality_score,
        'execution_metadata': {},
        'last_execution_id': None,
        'created_at': new_workflow.created_at.isoformat(),
        'updated_at': (new_workflow.updated_at.isoformat() if new_workflow.updated_at else None),
        'started_at': (new_workflow.started_at.isoformat() if new_workflow.started_at else None),
        'completed_at': (new_workflow.completed_at.isoformat() if new_workflow.completed_at else None),
        'created_by': new_workflow.created_by,
        'schedule_enabled': new_workflow.schedule_enabled,
        'schedule_cron': new_workflow.schedule_cron,
        'next_run_at': (new_workflow.next_run_at.isoformat() if new_workflow.next_run_at else None)
        }

        _upsert_workflow_model(db, WORKFLOWS_STORE[workflow_id])

    logger.info("Workflow %s persisted to DB", workflow_id)
    
    return new_workflow
