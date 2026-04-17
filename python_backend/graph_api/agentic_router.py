"""
 AGENTIC BACKEND ORCHESTRATOR - FastAPI Multi-Agent Coordination
    
Implements Modular Cognition Pattern (MCP) with intelligent agent routing
Following AGENTIC_REFACTORING_GUIDE.md principles
"""

import logging
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any
from enum import Enum
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query, Response
from pydantic import BaseModel, Field
import neo4j
import httpx
from sqlalchemy.orm import Session

from .dependencies import get_driver
from core.db_session import get_db
from models.quality_models import DiscoveryReport
from models.report_hub_models import UnifiedReport
from models.configuration_models import DataSourceConfigRecord
from services.mcp_client import mcp_client

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/agentic", tags=["Agentic Orchestration"])

# ── Canonical enums (kept local so python_backend has no import dependency on mcp_server) ──

class AgentType(str, Enum):
    DATA_ANALYST = "data_analyst"
    ETL_ORCHESTRATOR = "etl_orchestrator"
    QUERY_PLANNER = "query_planner"
    VISUALIZATION_AGENT = "visualization_agent"
    QUALITY_MONITOR = "quality_monitor"
    DATA_DISCOVERY_AGENT = "data_discovery_agent"
    CHAT_COORDINATOR = "chat_coordinator"

class TaskType(str, Enum):
    DATA_ANALYSIS = "data_analysis"
    PIPELINE_ORCHESTRATION = "pipeline_orchestration"
    GRAPH_QUERY = "graph_query"
    VISUALIZATION_GENERATION = "visualization_generation"
    QUALITY_ASSESSMENT = "quality_assessment"
    CHAT_PROCESSING = "chat_processing"
    DATA_DISCOVERY = "data_discovery"
    DATA_QUALITY_SCAN = "data_quality_scan"
    FILE_BATCH_PROCESSING = "file_batch_processing"

# ── Pydantic models (local; mcp_server models are kept separate to avoid cross-process imports) ──

class AgentCapability(BaseModel):
    name: str
    description: str
    parameters: Dict[str, Any] = {}

class AgentDefinition(BaseModel):
    id: str
    type: AgentType
    name: str
    capabilities: List[AgentCapability]
    status: str = "ready"
    last_activity: datetime = Field(default_factory=datetime.now)
    performance_metrics: Dict[str, float] = {}

class AgenticTask(BaseModel):
    id: str = Field(default_factory=lambda: f"task_{int(datetime.now().timestamp() * 1000)}")
    type: TaskType
    required_capabilities: List[str]
    payload: Dict[str, Any]
    priority: int = 5
    timeout: int = 30
    created_at: datetime = Field(default_factory=datetime.now)

class AgenticTaskResult(BaseModel):
    task_id: str
    agent_id: str
    agent_type: AgentType
    success: bool
    result: Dict[str, Any] = {}
    error: Optional[str] = None
    execution_time: float
    timestamp: datetime = Field(default_factory=datetime.now)

class ChatRequest(BaseModel):
    message: str
    context: Dict[str, Any] = {}
    session_id: Optional[str] = None
    intent: Optional[str] = None

class ChatResponse(BaseModel):
    message: str
    agent_responses: List[Dict[str, Any]] = []
    suggested_actions: List[str] = []
    requires_followup: bool = False
    session_id: str

class SystemStatus(BaseModel):
    active_agents: List[AgentDefinition]
    task_queue_size: int
    system_health: str
    performance_metrics: Dict[str, Any]
    timestamp: datetime = Field(default_factory=datetime.now)

# ── MCP client singleton (shared with main.py and other consumers) ──


#  API ENDPOINTS

@router.post("/task", response_model=AgenticTaskResult)
async def process_agentic_task(
    task: AgenticTask,
    _background_tasks: BackgroundTasks,
    driver_instance: neo4j.AsyncDriver = Depends(get_driver)
):
    """Process a task with intelligent agent routing via MCP Server"""
    try:
        # Delegate to MCP Server
        result_dict = await mcp_client.submit_task(task.model_dump(mode="json"))
        return AgenticTaskResult(**result_dict)
    except Exception as e:
        logger.error("Task processing failed: %s", e)
        raise HTTPException(status_code=500, detail=f"Task processing failed: {str(e)}") from e

@router.post("/chat", response_model=ChatResponse)
async def process_chat_message(
    chat_request: ChatRequest,
    driver_instance: neo4j.AsyncDriver = Depends(get_driver)
):
    """Process chat message with multi-agent coordination"""
    try:
        session_id = chat_request.session_id or f"session_{int(datetime.now().timestamp())}"
        
        # Create chat processing task
        chat_task = AgenticTask(
            type=TaskType.CHAT_PROCESSING,
            required_capabilities=["process_natural_language", "coordinate_agent_responses"],
            payload={
                "message": chat_request.message,
                "context": chat_request.context,
                "session_id": session_id
            }
        )
        
        # Delegate to MCP Server
        result_dict = await mcp_client.submit_task(chat_task.model_dump(mode="json"))
        result = AgenticTaskResult(**result_dict)
        
        if result.success:
            chat_data = result.result
            return ChatResponse(
                message=chat_data.get("primaryResponse", "I understand your request."),
                agent_responses=[],
                suggested_actions=chat_data.get("followupQuestions", []),
                requires_followup=chat_data.get("collaborationNeeded", False),
                session_id=session_id
            )
        else:
            return ChatResponse(
                message="I'm sorry, I encountered an issue processing your message.",
                session_id=session_id
            )
    
    except Exception as e:
        logger.error("Chat processing failed: %s", e)
        raise HTTPException(status_code=500, detail=f"Chat processing failed: {str(e)}") from e

@router.get("/status", response_model=SystemStatus)
async def get_system_status():
    """Get current agentic system status"""
    status_data = await mcp_client.get_system_status()
    return SystemStatus(**status_data)

@router.get("/agents", response_model=List[AgentDefinition])
async def get_orchestrator_agents(
    response: Response,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
):
    """Get list of configured agents (paged)."""
    agents_data = await mcp_client.list_agents()
    agents = [AgentDefinition(**a) for a in agents_data]
    
    response.headers["X-Total-Count"] = str(len(agents))
    return agents[skip : skip + limit]

@router.post("/agents/{agent_id}/reset")
async def reset_agent(agent_id: str):
    """Reset agent status - Deprecated in MCP Architecture"""
    raise HTTPException(status_code=501, detail="Agent reset not supported in distributed MCP architecture")

@router.get("/metrics")
async def get_performance_metrics():
    """Get system performance metrics"""
    status = await mcp_client.get_system_status()
    # Extract metrics from status
    # MCP server status.performance_metrics matches
    
    active_agent_count = len([a for a in status["active_agents"] if a.get("status") == "ready"])
    
    return {
        "system_metrics": status["performance_metrics"],
        "agent_count": len(status["active_agents"]),
        "active_agents": active_agent_count,
        "timestamp": datetime.now()
    }

#  SYSTEM STATUS ENDPOINTS

@router.get("/system/status")
async def get_agentic_system_status():
    """Get overall agentic system status"""
    try:
        # Return real orchestrator status (no fabricated payloads)
        status_data = await mcp_client.get_system_status()
        return SystemStatus(**status_data)
    except Exception as e:
        logger.warning("Agentic system status unavailable: %s", e)
        return {
            "status": "unavailable",
            "agents": [],
            "mcp_server": {"connected": False},
            "error": str(e),
            "timestamp": datetime.now().isoformat(),
        }

@router.get("/agents/active")
async def get_active_agents_list(
    response: Response,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
):
    """Get list of currently active agents"""
    try:
        agents_data = await mcp_client.list_agents()
        active_agents = [
            AgentDefinition(**agent)
            for agent in agents_data
            if str(agent.get("status", "")).lower() in ("ready", "active", "running")
        ]

        response.headers["X-Total-Count"] = str(len(active_agents))
        return {
            "status": "success",
            "active_agents": active_agents[skip : skip + limit],
            "total_count": len(active_agents),
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        logger.error("Error getting active agents: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e

@router.get("/agents/metrics")
async def get_agent_metrics():
    """Get performance metrics for all agents"""
    try:
        status = await mcp_client.get_system_status()
        system_metrics = status["performance_metrics"]
        
        tasks_completed = int(system_metrics.get("tasks_completed", 0) or 0)
        tasks_failed = int(system_metrics.get("tasks_failed", 0) or 0)
        total_tasks = tasks_completed + tasks_failed
        success_rate = (tasks_completed / total_tasks) * 100.0 if total_tasks else 0.0
        error_rate = (tasks_failed / total_tasks) * 100.0 if total_tasks else 0.0

        return {
            "status": "success",
            "metrics": {
                "total_tasks_processed": total_tasks,
                "tasks_completed": tasks_completed,
                "tasks_failed": tasks_failed,
                "average_response_time": float(system_metrics.get("average_response_time", 0.0) or 0.0),
                "success_rate": round(success_rate, 2),
                "error_rate": round(error_rate, 2),
                "agent_utilization": system_metrics.get("agent_utilization", {}),
            },
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        logger.error("Error getting agent metrics: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


# ── Data Discovery via MCP ─────────────────────────────────────────────────

class DiscoveryRequest(BaseModel):
    source_id: Optional[str] = None
    folder_path: Optional[str] = None
    recursive: bool = True
    include_profiling: bool = True
    save_report: bool = True

@router.post("/discovery", summary="Discover and profile a folder data source via MCP")
async def discover_datasource(req: DiscoveryRequest, db: Session = Depends(get_db)):
    """
    Submit a DATA_DISCOVERY task to the MCP orchestrator.
    Routes to the DataDiscoveryAgent when registered, or falls back to the ETL Orchestrator agent.
    When save_report=True the result is persisted to discovery_reports and returned with report_id.
    """
    if not req.source_id and not req.folder_path:
        raise HTTPException(status_code=400, detail="Provide source_id or folder_path")
    task = AgenticTask(
        type=TaskType.DATA_DISCOVERY,
        required_capabilities=["discover_files", "profile_files"],
        payload={
            "source_id": req.source_id,
            "folder_path": req.folder_path,
            "recursive": req.recursive,
            "include_profiling": req.include_profiling,
        },
    )
    try:
        result_dict = await mcp_client.submit_task(task.model_dump(mode="json"))
    except (httpx.ConnectError, httpx.TimeoutException, httpx.ReadTimeout, Exception) as mcp_err:
        logger.error("Discovery task failed: %s", mcp_err)
        raise HTTPException(
            status_code=503,
            detail=(
                "MCP orchestrator is unavailable. Start the MCP server to run discovery scans. "
                f"Details: {mcp_err}"
            ),
        ) from mcp_err

    if req.save_report:
        try:
            inner = result_dict.get("result") or result_dict
            files = inner.get("files") or inner.get("discovered_files") or []
            total_size = sum(int(f.get("size_bytes") or 0) for f in files if isinstance(f, dict))
            label = (
                req.folder_path
                or req.source_id
                or inner.get("folder_path")
                or "unknown"
            )
            report = DiscoveryReport(
                report_id=str(uuid.uuid4()),
                label=label,
                source_id=req.source_id,
                folder_path=req.folder_path,
                total_files=len(files),
                total_size_bytes=total_size,
                result=result_dict,
            )
            db.add(report)
            # Also write to unified reports hub
            unified = UnifiedReport(
                report_id=str(uuid.uuid4()),
                report_type="discovery",
                title=f"Discovery: {label}",
                source_page="data-discovery",
                status="info",
                summary={
                    "total_files": len(files),
                    "total_size_bytes": total_size,
                    "folder_path": req.folder_path or req.source_id,
                },
                result=result_dict,
                tags=["discovery"],
            )
            db.add(unified)
            db.commit()
            result_dict["report_id"] = report.report_id
            logger.info("Discovery report saved: %s (%d files)", report.report_id, len(files))
        except Exception as persist_err:
            logger.warning("Failed to persist discovery report: %s", persist_err)
            db.rollback()

    return result_dict


@router.get("/discovery/reports", summary="List saved data discovery reports")
async def list_discovery_reports(
    limit: int = Query(50, ge=1, le=500),
    source_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """
    Return saved discovery reports in reverse-chronological order.
    Used by the Data Discovery page 'Past Runs' history panel.
    """
    q = db.query(DiscoveryReport)
    if source_id:
        q = q.filter(DiscoveryReport.source_id == source_id)
    rows = q.order_by(DiscoveryReport.created_at.desc()).limit(limit).all()
    return [
        {
            "report_id": r.report_id,
            "label": r.label,
            "source_id": r.source_id,
            "folder_path": r.folder_path,
            "total_files": r.total_files,
            "total_size_bytes": r.total_size_bytes,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "result": r.result,
        }
        for r in rows
    ]


# ── Data Quality Scan via MCP ──────────────────────────────────────────────

class QualityScanMCPRequest(BaseModel):
    source_id: Optional[str] = None
    folder_path: Optional[str] = None
    scan_type: str = "full"        # full | quick | sample
    save_report: bool = True
    entity_type: Optional[str] = None

@router.post("/quality-scan", summary="Run a data quality scan via MCP orchestration")
async def quality_scan_via_mcp(req: QualityScanMCPRequest, db: Session = Depends(get_db)):
    """
    Submit a DATA_QUALITY_SCAN task to the MCP orchestrator.
    Routes to the QualityMonitor agent which uses the Rule Engine
    and the backend quality scan endpoint.

    When MCP is unavailable (not running / network error) the endpoint falls back
    to the direct quality-scan path (/api/analytics/quality/scan or /scan) so that
    the UI stays functional without a running MCP cluster.
    """
    if not req.source_id and not req.folder_path:
        raise HTTPException(status_code=400, detail="Provide source_id or folder_path")
    task = AgenticTask(
        type=TaskType.DATA_QUALITY_SCAN,
        required_capabilities=["scan_datasource_quality", "generate_quality_reports"],
        payload={
            "source_id": req.source_id,
            "folder_path": req.folder_path,
            "scan_type": req.scan_type,
            "save_report": req.save_report,
            "entity_type": req.entity_type,
        },
    )
    try:
        result_dict = await mcp_client.submit_task(task.model_dump(mode="json"))
        return result_dict
    except (httpx.ConnectError, httpx.TimeoutException, httpx.ReadTimeout, Exception) as mcp_err:
        logger.warning(
            "MCP unavailable for quality-scan (%s). Falling back to direct scan.",
            mcp_err,
        )

    # ── Fallback: resolve target and call direct quality scan ─────────────────
    # Lazy import to avoid circular dependency at module load time.
    from graph_api.quality_router import (
        scan_table_quality,
        QualityScanRequest as DirectScanRequest,
    )

    # Resolve a scan target from source_id, folder_path, or entity_type.
    scan_target: Optional[str] = None
    data_source_path: Optional[str] = None

    if req.source_id:
        try:
            record = db.query(DataSourceConfigRecord).filter(
                DataSourceConfigRecord.id == req.source_id
            ).first()
            if record:
                scan_target = record.name
                # Attempt to retrieve a filesystem path from the connection payload.
                try:
                    from core.crypto import decrypt_json
                    conn = decrypt_json(record.connection_ciphertext) if record.connection_ciphertext else {}
                    data_source_path = (
                        conn.get("folder_path")
                        or conn.get("file_path")
                        or conn.get("path")
                        or None
                    )
                except Exception:  # noqa: BLE001
                    pass
        except Exception as db_err:
            logger.warning("Could not resolve source_id %s: %s", req.source_id, db_err)

    if not scan_target:
        # Fall back to folder_path, entity_type, or a safe default
        scan_target = (
            req.folder_path
            or req.entity_type
            or "workflows"
        )

    direct_request = DirectScanRequest(
        table_name=scan_target,
        data_source=data_source_path or req.folder_path or None,
    )

    try:
        result = await scan_table_quality(scan_target, direct_request, db)
        # Wrap in the agentic envelope so callers that inspect result.result still work.
        if isinstance(result, dict):
            result["_fallback"] = True
            result["_mcp_unavailable"] = True
        return result
    except Exception as fallback_err:
        logger.error("Quality scan fallback also failed: %s", fallback_err)
        raise HTTPException(
            status_code=503,
            detail=(
                "MCP orchestrator is not running and the direct scan fallback failed. "
                f"Start the MCP server or check the table name. Details: {fallback_err}"
            ),
        ) from fallback_err

