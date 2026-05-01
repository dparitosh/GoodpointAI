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
from models.quality_models import DiscoveryReport, DataQualityRule, DataQualityResult
from models.report_hub_models import UnifiedReport
from models.workflow_models import WorkflowExecution, MigrationStage
from services.mcp_workflow_adapter import MCPWorkflowAdapter, MCPIntegrationHelper
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
    TASK_DECOMPOSER = "task_decomposer"

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
    WORKFLOW_DECOMPOSITION = "workflow_decomposition"

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


class GoalToWorkflowRequest(BaseModel):
    goal: str
    source_id: str
    target_id: str
    workflow_name: Optional[str] = None
    auto_start: bool = True
    execution_params: Dict[str, Any] = Field(default_factory=dict)


def _build_plm_agentic_phase_plan(
    *,
    req: GoalToWorkflowRequest,
    decomposition_payload: Dict[str, Any],
) -> Dict[str, Any]:
    """Build a UI-consumable, phase-by-phase agent/task plan for PLM migration orchestration."""
    default_phases = ["connect", "discover", "profile", "map", "validate", "execute"]
    requested_phases = req.execution_params.get("migration_phases")
    phases = requested_phases if isinstance(requested_phases, list) and requested_phases else default_phases

    phase_map: Dict[str, Dict[str, Any]] = {
        "connect": {
            "agent": AgentType.ETL_ORCHESTRATOR.value,
            "task": TaskType.PIPELINE_ORCHESTRATION.value,
            "capabilities": ["resolve_source_target", "prepare_connectors"],
            "description": "Bind source/target systems and initialize migration context.",
        },
        "discover": {
            "agent": AgentType.DATA_DISCOVERY_AGENT.value,
            "task": TaskType.DATA_DISCOVERY.value,
            "capabilities": ["discover_files", "profile_files"],
            "description": "Discover datasets and gather source metadata.",
        },
        "profile": {
            "agent": AgentType.DATA_ANALYST.value,
            "task": TaskType.DATA_ANALYSIS.value,
            "capabilities": ["infer_schema", "compute_data_profile", "evaluate_profile_rules"],
            "description": "Generate schema/distribution profile and run rule-engine profiling checks.",
            "rule_engine": {
                "enabled": True,
                "scope": "profiling",
                "checks": ["schema_drift", "required_fields", "value_distribution"],
            },
        },
        "map": {
            "agent": AgentType.TASK_DECOMPOSER.value,
            "task": TaskType.WORKFLOW_DECOMPOSITION.value,
            "capabilities": ["decompose_goal", "build_task_dag"],
            "description": "Convert migration goal into executable subtasks and mapping plan.",
        },
        "validate": {
            "agent": AgentType.QUALITY_MONITOR.value,
            "task": TaskType.DATA_QUALITY_SCAN.value,
            "capabilities": ["scan_datasource_quality", "generate_quality_reports"],
            "description": "Run DQ gates and quality assertions before execution.",
            "rule_engine": {
                "enabled": True,
                "scope": "validation",
                "checks": ["quality_rules", "business_rules", "referential_integrity"],
            },
        },
        "execute": {
            "agent": AgentType.ETL_ORCHESTRATOR.value,
            "task": TaskType.PIPELINE_ORCHESTRATION.value,
            "capabilities": ["run_workflow", "track_progress"],
            "description": "Execute migration workflow and persist run state.",
        },
    }

    decomposition_status = decomposition_payload.get("decomposition_status")
    subtasks = decomposition_payload.get("subtasks", [])

    planned_phases: List[Dict[str, Any]] = []
    for idx, raw_phase in enumerate(phases, start=1):
        phase_key = str(raw_phase).strip().lower()
        base = phase_map.get(
            phase_key,
            {
                "agent": AgentType.ETL_ORCHESTRATOR.value,
                "task": TaskType.PIPELINE_ORCHESTRATION.value,
                "capabilities": ["run_workflow"],
                "description": f"Execute custom phase '{raw_phase}'.",
            },
        )
        planned_phases.append(
            {
                "order": idx,
                "phase": phase_key,
                **base,
                "status": "planned",
            }
        )

    return {
        "standard": req.execution_params.get("migration_standard") or "plm-governed-sequenced-v1",
        "source_id": req.source_id,
        "target_id": req.target_id,
        "decomposition_status": decomposition_status,
        "subtasks_count": len(subtasks) if isinstance(subtasks, list) else 0,
        "phases": planned_phases,
    }


def _extract_mcp_decomposition(result_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize various MCP task result envelope shapes into decomposition payload."""
    if not isinstance(result_dict, dict):
        raise ValueError("MCP response is not a JSON object")

    candidates: List[Dict[str, Any]] = [result_dict]

    first = result_dict.get("result")
    if isinstance(first, dict):
        candidates.append(first)
        nested = first.get("result")
        if isinstance(nested, dict):
            candidates.append(nested)

    for item in candidates:
        if not isinstance(item, dict):
            continue
        if "subtasks" in item and "decomposition_status" in item:
            return item

    raise ValueError("MCP response does not contain a valid decomposition payload")


def _create_workflow_execution_record(
    *,
    db: Session,
    workflow_id: str,
    execution_params: Optional[Dict[str, Any]] = None,
) -> WorkflowExecution:
    execution_id = f"wexec_{uuid.uuid4().hex[:12]}"
    execution = WorkflowExecution(
        id=execution_id,
        workflow_id=workflow_id,
        status="pending",
        current_stage=MigrationStage.IDLE.value,
        progress_percentage=0.0,
        execution_context=execution_params or {},
        created_by="agentic_orchestrator",
    )
    db.add(execution)
    db.commit()
    db.refresh(execution)
    return execution

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
    except (httpx.ConnectError, httpx.TimeoutException, httpx.ReadTimeout) as e:
        logger.warning("MCP unavailable for /task: %s", e)
        raise HTTPException(
            status_code=503,
            detail="MCP agent cluster is not running. Start the MCP server to process agentic tasks.",
        ) from e
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
    
    except (httpx.ConnectError, httpx.TimeoutException, httpx.ReadTimeout) as e:
        logger.warning("MCP unavailable for /chat: %s", e)
        session_id = chat_request.session_id or f"session_{int(datetime.now().timestamp())}"
        return ChatResponse(
            message="The AI agent cluster is currently unavailable. Start the MCP server to enable chat.",
            session_id=session_id,
        )
    except Exception as e:
        logger.error("Chat processing failed: %s", e)
        raise HTTPException(status_code=500, detail=f"Chat processing failed: {str(e)}") from e

@router.get("/status", response_model=SystemStatus)
async def get_system_status():
    """Get current agentic system status"""
    try:
        status_data = await mcp_client.get_system_status()
        return SystemStatus(**status_data)
    except Exception as e:
        logger.warning("MCP unavailable for /status: %s", e)
        return SystemStatus(
            active_agents=[],
            task_queue_size=0,
            system_health="unavailable",
            performance_metrics={"mcp_unavailable": True},
        )

@router.get("/agents", response_model=List[AgentDefinition])
async def get_orchestrator_agents(
    response: Response,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
):
    """Get list of configured agents (paged)."""
    try:
        agents_data = await mcp_client.list_agents()
        agents = [AgentDefinition(**a) for a in agents_data]
    except Exception as e:
        logger.warning("MCP unavailable for /agents: %s", e)
        agents = []
    response.headers["X-Total-Count"] = str(len(agents))
    return agents[skip : skip + limit]

@router.post("/agents/{agent_id}/reset")
async def reset_agent(agent_id: str):
    """Reset agent status - Deprecated in MCP Architecture"""
    raise HTTPException(status_code=501, detail="Agent reset not supported in distributed MCP architecture")

@router.get("/metrics")
async def get_performance_metrics():
    """Get system performance metrics"""
    try:
        status = await mcp_client.get_system_status()
        active_agent_count = len([a for a in status["active_agents"] if a.get("status") == "ready"])
        return {
            "system_metrics": status["performance_metrics"],
            "agent_count": len(status["active_agents"]),
            "active_agents": active_agent_count,
            "timestamp": datetime.now(),
        }
    except Exception as e:
        logger.warning("MCP unavailable for /metrics: %s", e)
        return {
            "system_metrics": {"mcp_unavailable": True},
            "agent_count": 0,
            "active_agents": 0,
            "timestamp": datetime.now(),
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
        logger.warning("MCP unavailable for /agents/active: %s", e)
        response.headers["X-Total-Count"] = "0"
        return {
            "status": "unavailable",
            "active_agents": [],
            "total_count": 0,
            "timestamp": datetime.now().isoformat(),
        }

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
        logger.warning("MCP unavailable for /agents/metrics: %s", e)
        return {
            "status": "unavailable",
            "metrics": {
                "total_tasks_processed": 0,
                "tasks_completed": 0,
                "tasks_failed": 0,
                "average_response_time": 0.0,
                "success_rate": 0.0,
                "error_rate": 0.0,
                "agent_utilization": {},
            },
            "timestamp": datetime.now().isoformat(),
        }


# ── Data Discovery via MCP ─────────────────────────────────────────────────

class DiscoveryRequest(BaseModel):
    source_id: Optional[str] = None
    folder_path: Optional[str] = None
    recursive: bool = True
    include_profiling: bool = True
    save_report: bool = True
    # When True, enabled dq_rules from the DB are evaluated against the profiled data
    # and a violation summary is included in the response under "dq_rule_violations".
    evaluate_dq_rules: bool = False

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

    # ── Post-discovery DQ rule evaluation ─────────────────────────────────
    # When evaluate_dq_rules=True, run enabled dq_rules from the DB against
    # the profile data returned by the agent and attach a summary to the response.
    if req.evaluate_dq_rules:
        try:
            violations = _evaluate_dq_rules_on_profile(result_dict, db)
            result_dict["dq_rule_violations"] = violations
            result_dict["dq_rule_violations_count"] = len(violations)
            result_dict["dq_rules_evaluated"] = True
        except Exception as dq_err:
            logger.warning("DQ rule evaluation post-discovery failed: %s", dq_err)
            result_dict["dq_rules_evaluated"] = False
            result_dict["dq_rule_violations"] = []

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


# ── Discovery → field mapping inference ───────────────────────────────────

# PLM canonical target field registry used by infer-mappings.
# Keys are the canonical target field name; values are synonym lists (lowercase).
_PLM_FIELD_SYNONYMS: dict[str, list[str]] = {
    "part_number":    ["part_number", "partno", "part_no", "pn", "item_number", "item_no", "id", "part_id"],
    "name":           ["name", "part_name", "title", "label", "description_short"],
    "description":    ["description", "desc", "long_description", "notes"],
    "classification": ["classification", "category", "class", "type", "part_type", "group"],
    "revision":       ["revision", "rev", "version", "ver"],
    "status":         ["status", "state", "lifecycle_state", "maturity"],
    "unit_of_measure":["unit_of_measure", "uom", "unit", "measure"],
    "weight":         ["weight", "mass", "weight_kg", "weight_lb"],
    "material":       ["material", "material_type", "raw_material"],
    "created_by":     ["created_by", "author", "creator", "owner"],
    "created_at":     ["created_at", "created_date", "date_created", "creation_date"],
}

_TRANSFORM_HINTS: dict[str, str] = {
    "name": "TRIM",
    "description": "TRIM",
    "classification": "TRIM",
    "part_number": "TRIM",
    "weight": "NUMBER",
    "created_at": "TIMESTAMP",
}


def _infer_mapping_for_field(source_field: str) -> dict:
    """Return the best PLM target field + confidence for a single source field."""
    lf = source_field.strip().lower().replace(" ", "_").replace("-", "_")
    for target, synonyms in _PLM_FIELD_SYNONYMS.items():
        if lf == target or lf in synonyms:
            return {
                "sourceField": source_field,
                "targetField": target,
                "transformation": _TRANSFORM_HINTS.get(target),
                "confidence": "High",
                "match_type": "synonym",
            }
    # Partial / substring match
    for target, synonyms in _PLM_FIELD_SYNONYMS.items():
        if any(s in lf or lf in s for s in synonyms):
            return {
                "sourceField": source_field,
                "targetField": target,
                "transformation": _TRANSFORM_HINTS.get(target),
                "confidence": "Medium",
                "match_type": "partial",
            }
    # No match — map to itself
    return {
        "sourceField": source_field,
        "targetField": source_field,
        "transformation": None,
        "confidence": "Low",
        "match_type": "identity",
    }


def _evaluate_dq_rules_on_profile(result_dict: dict, db: Session) -> list[dict]:
    """
    Evaluate enabled dq_rules from the DB against the column profile data
    returned by the discovery agent.

    Returns a list of violation dicts for rules that failed based on the
    profile statistics (null_rate, uniqueness, row_count, etc.).
    """
    inner = result_dict.get("result") or result_dict
    files = inner.get("files") or inner.get("discovered_files") or []

    # Build a flat column-profile dict from all profiled files
    # Structure: { column_name: { null_rate, type, sample, ... } }
    col_profiles: dict[str, dict] = {}
    total_row_count = 0
    for f in files:
        if not isinstance(f, dict):
            continue
        total_row_count += int(f.get("row_count") or 0)
        profile = f.get("profile") or {}
        for col, stats in profile.items():
            if col not in col_profiles:
                col_profiles[col] = stats if isinstance(stats, dict) else {}

    rules = db.query(DataQualityRule).filter(DataQualityRule.enabled == 1).all()
    violations: list[dict] = []

    for rule in rules:
        cond = rule.condition or {}
        op = cond.get("op", "")
        field = cond.get("field", "")
        stats = col_profiles.get(field, {})

        violated = False
        detail = ""

        if op == "not_null":
            null_rate = float(stats.get("null_rate") or 0)
            if null_rate > 0:
                violated = True
                detail = f"null_rate={null_rate:.1f}% for field '{field}'"

        elif op == "completeness_pct":
            threshold = float(cond.get("threshold") or 80)
            null_rate = float(stats.get("null_rate") or 0)
            completeness = 100.0 - null_rate
            if completeness < threshold:
                violated = True
                detail = f"completeness={completeness:.1f}% < threshold={threshold}% for field '{field}'"

        elif op == "row_count_gt":
            minimum = int(cond.get("min") or 1)
            if total_row_count <= minimum:
                violated = True
                detail = f"row_count={total_row_count} <= min={minimum}"

        elif op == "unique":
            if field and field not in col_profiles:
                # Can't evaluate uniqueness without stats
                pass

        if violated:
            violations.append({
                "rule_id": rule.id,
                "rule_name": rule.name,
                "entity_type": rule.entity_type,
                "severity": rule.severity,
                "detail": detail,
            })

    return violations


@router.get(
    "/discovery/{report_id}/infer-mappings",
    summary="Infer field mappings from a saved discovery report",
)
async def infer_mappings_from_discovery(
    report_id: str,
    db: Session = Depends(get_db),
):
    """
    Read a saved discovery report and return field mapping suggestions.

    Each suggestion maps a discovered source column to the best-matching
    PLM canonical target field with a confidence level and optional
    built-in transformation hint.

    Used by Migration Wizard step 2 → step 3 to pre-populate field mappings.
    """
    report = db.query(DiscoveryReport).filter(DiscoveryReport.report_id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Discovery report not found")

    inner = (report.result or {}).get("result") or report.result or {}
    files = inner.get("files") or inner.get("discovered_files") or []

    # Collect all unique column names across all discovered files
    source_fields: list[str] = []
    seen: set[str] = set()
    for f in files:
        if not isinstance(f, dict):
            continue
        profile = f.get("profile") or {}
        for col in profile:
            if col not in seen:
                source_fields.append(col)
                seen.add(col)

    # Fallback: use inferred_schema if profile is absent
    if not source_fields:
        inferred = inner.get("inferred_schema") or {}
        source_fields = list(inferred.keys())

    suggestions = [_infer_mapping_for_field(sf) for sf in source_fields]

    # Also run DQ rule evaluation on the profile so the caller gets a quality signal
    dq_violations = _evaluate_dq_rules_on_profile(report.result or {}, db)

    return {
        "report_id": report_id,
        "source_fields_count": len(source_fields),
        "mappings": suggestions,
        "dq_violations": dq_violations,
        "dq_violations_count": len(dq_violations),
    }


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
        run_generic_quality_scan,
        QualityScanRequest as DirectScanRequest,
        GenericScanRequest as DirectGenericRequest,
    )

    # Resolve the scan target from source_id, folder_path, or entity_type.
    # Also detect whether we are dealing with a filesystem source vs a DB table.
    scan_target: Optional[str] = None
    data_source_path: Optional[str] = None
    is_folder_source: bool = False

    if req.source_id:
        try:
            record = db.query(DataSourceConfigRecord).filter(
                DataSourceConfigRecord.id == req.source_id
            ).first()
            if record:
                scan_target = record.name
                # Detect filesystem sources by type or connection payload.
                if str(getattr(record, "source_type", "") or "").lower() in (
                    "folder", "filesystem", "file", "csv", "local"
                ):
                    is_folder_source = True
                try:
                    from core.crypto import decrypt_json
                    conn = decrypt_json(record.connection_ciphertext) if record.connection_ciphertext else {}
                    data_source_path = (
                        conn.get("folder_path")
                        or conn.get("file_path")
                        or conn.get("path")
                        or None
                    )
                    if data_source_path:
                        is_folder_source = True
                except Exception:  # noqa: BLE001
                    pass
        except Exception as db_err:
            logger.warning("Could not resolve source_id %s: %s", req.source_id, db_err)

    if not scan_target:
        scan_target = req.folder_path or req.entity_type or "workflows"

    # A folder_path that was sent explicitly (no source_id) is always a filesystem scan.
    if req.folder_path and not req.source_id:
        is_folder_source = True
        data_source_path = data_source_path or req.folder_path

    # Detect paths that slipped through: any target with a path separator or known
    # file-extension is not a valid Postgres table name — route to folder scan.
    import os as _os
    if not is_folder_source and (
        _os.sep in scan_target
        or "/" in scan_target
        or "\\" in scan_target
        or any(scan_target.lower().endswith(ext) for ext in (".csv", ".json", ".xml", ".parquet", ".xlsx"))
    ):
        is_folder_source = True
        data_source_path = data_source_path or scan_target

    try:
        if is_folder_source:
            # Route to the generic filesystem scan path.
            generic_request = DirectGenericRequest(
                datasource="folder",
                scan_type=req.scan_type or "full",
                table_name=data_source_path or scan_target,
            )
            result = await run_generic_quality_scan(generic_request, db)
        else:
            direct_request = DirectScanRequest(
                table_name=scan_target,
                data_source=data_source_path or req.folder_path or None,
            )
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
                f"Start the MCP server or check the target source. Details: {fallback_err}"
            ),
        ) from fallback_err


@router.post("/workflows/from-goal", summary="Canonical goal → decomposition → workflow definition (→ optional execution)")
async def create_workflow_from_goal_via_mcp(req: GoalToWorkflowRequest, db: Session = Depends(get_db)):
    """
    Canonical orchestration endpoint for goal-driven workflow creation.

    Flow:
    1) Submit a decomposition task to MCP (Task Decomposer capabilities)
    2) Convert decomposition subtasks into workflow definition/steps
    3) Optionally create a workflow execution record
    """
    if not req.goal or not req.goal.strip():
        raise HTTPException(status_code=400, detail="goal is required")
    if not req.source_id or not req.source_id.strip():
        raise HTTPException(status_code=400, detail="source_id is required")
    if not req.target_id or not req.target_id.strip():
        raise HTTPException(status_code=400, detail="target_id is required")

    task = AgenticTask(
        type=TaskType.WORKFLOW_DECOMPOSITION,
        required_capabilities=["decompose_goal", "build_task_dag"],
        payload={
            "goal": req.goal,
            "source": req.source_id,
            "source_id": req.source_id,
            "target_id": req.target_id,
        },
    )

    try:
        mcp_result = await mcp_client.submit_task(task.model_dump(mode="json"))
    except Exception as e:
        logger.error("Goal decomposition task failed: %s", e)
        raise HTTPException(status_code=500, detail=f"Goal decomposition failed: {e}") from e

    try:
        decomposition_payload = _extract_mcp_decomposition(mcp_result)
    except ValueError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e

    if not MCPIntegrationHelper.validate_mcp_response(decomposition_payload):
        raise HTTPException(
            status_code=502,
            detail="Decomposition payload from MCP is invalid",
        )

    agentic_plan = _build_plm_agentic_phase_plan(
        req=req,
        decomposition_payload=decomposition_payload,
    )

    try:
        adapter = MCPWorkflowAdapter(db)
        workflow = await adapter.create_workflow_from_mcp_decomposition(
            mcp_response=decomposition_payload,
            source_id=req.source_id,
            target_id=req.target_id,
            workflow_name=req.workflow_name,
        )
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error("Workflow creation from decomposition failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to create workflow from decomposition") from e

    execution_payload: Optional[Dict[str, Any]] = None
    if req.auto_start:
        try:
            workflow_id_value = str(getattr(workflow, "id", ""))
            execution = _create_workflow_execution_record(
                db=db,
                workflow_id=workflow_id_value,
                execution_params=req.execution_params,
            )
            execution_payload = {
                "execution_id": execution.id,
                "status": execution.status,
                "current_stage": execution.current_stage,
                "progress_percentage": execution.progress_percentage,
            }
        except Exception as e:
            db.rollback()
            logger.error("Workflow execution record creation failed: %s", e, exc_info=True)
            raise HTTPException(status_code=500, detail="Workflow created but execution start failed") from e

    return {
        "status": "success",
        "goal": req.goal,
        "mcp_task_id": mcp_result.get("task_id") if isinstance(mcp_result, dict) else None,
        "workflow": {
            "workflow_id": workflow.id,
            "workflow_name": workflow.name,
            "source_id": workflow.source_id,
            "target_id": workflow.target_id,
            "steps_created": len(decomposition_payload.get("subtasks", [])),
        },
        "execution": execution_payload,
        "agentic_plan": agentic_plan,
        "decomposition": {
            "decomposition_status": decomposition_payload.get("decomposition_status"),
            "original_goal": decomposition_payload.get("original_goal"),
            "complexity": MCPIntegrationHelper.estimate_workflow_complexity(
                decomposition_payload.get("subtasks", [])
            ),
            "subtasks_count": len(decomposition_payload.get("subtasks", [])),
        },
    }

