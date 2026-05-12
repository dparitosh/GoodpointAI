"""
 AGENTIC BACKEND ORCHESTRATOR - FastAPI Multi-Agent Coordination
    
Implements Modular Cognition Pattern (MCP) with intelligent agent routing
Following AGENTIC_REFACTORING_GUIDE.md principles
"""

import logging
import uuid
import re
import json as _json
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
from models.quality_models import DiscoveryReport, DataQualityRule
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
    SCHEMA_CORRELATOR = "schema_correlator"
    PLM_DIRECTOR = "plm_director"
    REPORTING_AGENT = "reporting_agent"
    DATA_PROFILER = "data_profiler"

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
    SEMANTIC_PROFILE = "semantic_profile"
    SCHEMA_CORRELATION = "schema_correlation"
    PLM_MIGRATION_ORCHESTRATION = "plm_migration_orchestration"
    REPORT_GENERATION = "report_generation"
    SMART_GUIDANCE = "smart_guidance"
    DATA_HEALTH_REPORT = "data_health_report"
    # ── Unified AI Workflow steps ──────────────────────────────────────────
    PROFILING = "profiling"
    QUALITY_SCAN = "quality_scan"
    ETL_PIPELINE = "etl_pipeline"
    WORKFLOW_RUN = "workflow_run"

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
    ui_context: Dict[str, Any] = {}


class SmartGuidanceRequest(BaseModel):
    """Dataset context used to generate a business-friendly first-step recommendation."""
    source_name: Optional[str] = None
    source_id: Optional[str] = None
    file_count: Optional[int] = None
    file_types: Optional[List[str]] = None
    previous_runs: bool = False
    user_role: str = "business"  # "business" | "technical"
    llm_provider: Optional[str] = None
    nlp_query: Optional[str] = None  # free-text question from the NLP input bar


class SmartGuidanceResponse(BaseModel):
    """Business-friendly recommendation for what to do first with the data."""
    recommendation: str          # "discovery" | "profiling" | "quality"
    headline: str
    reason: str
    expected_outcome: str
    next_steps: List[str] = []
    complexity: str = "low"      # "low" | "medium" | "high"
    estimated_time: str = ""
    tips: List[str] = []
    llm_powered: bool = True

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


@router.post("/smart-guidance", response_model=SmartGuidanceResponse)
async def get_smart_guidance(req: SmartGuidanceRequest):
    """
    Return a business-friendly first-step recommendation based on the user's dataset context.

    Routes through ChatCoordinator (MCP) when available; falls back to direct LLM call
    so the endpoint is useful even if the agent cluster isn't running.
    """
    guidance_payload: Dict[str, Any] = {
        "message": "What should I do first with my data?",
        "source_name":   req.source_name or req.source_id or "Not specified",
        "source_id":     req.source_id,
        "file_count":    req.file_count,
        "file_types":    ", ".join(req.file_types) if req.file_types else "Unknown",
        "previous_runs": req.previous_runs,
        "user_role":     req.user_role,
        **({"llm_provider": req.llm_provider} if req.llm_provider else {}),
        **({"nlp_query": req.nlp_query} if req.nlp_query else {}),
    }

    # ── Try ChatCoordinator via MCP ────────────────────────────────────────
    try:
        chat_task = AgenticTask(
            type=TaskType.SMART_GUIDANCE,
            required_capabilities=["process_natural_language"],
            payload=guidance_payload,
        )
        result_dict = await mcp_client.submit_task(chat_task.model_dump(mode="json"))
        result = AgenticTaskResult(**result_dict)
        if result.success and result.result.get("smart_guidance"):
            g = result.result["smart_guidance"]
            return SmartGuidanceResponse(
                recommendation=g.get("recommendation", "discovery"),
                headline=g.get("headline", "Start with Discovery"),
                reason=g.get("reason", ""),
                expected_outcome=g.get("expected_outcome", ""),
                next_steps=g.get("next_steps", []),
                complexity=g.get("complexity", "low"),
                estimated_time=g.get("estimated_time", ""),
                tips=g.get("tips", []),
                llm_powered=True,
            )
    except (httpx.ConnectError, httpx.TimeoutException, httpx.ReadTimeout):
        pass  # fall through to direct LLM
    except Exception as e:
        logger.warning("Smart guidance via MCP failed: %s", e)

    # ── Direct LLM fallback (no MCP required) ─────────────────────────────
    _GUIDANCE_PROMPT = (
        "You are a friendly data assistant. "
        "Given a user's dataset context, recommend the single best first step "
        "from: discovery (scan files), profiling (understand columns), quality (fix issues). "
        "If the user asks a specific question, tailor your recommendation to address it. "
        "Use plain business language. Output strict JSON only:\n"
        '{"recommendation":"discovery|profiling|quality","headline":"...","reason":"...","expected_outcome":"...",'
        '"next_steps":[],"complexity":"low|medium|high","estimated_time":"...","tips":[]}'
    )
    user_msg = (
        f"Source: {req.source_name or 'not specified'}. "
        f"File count: {req.file_count or 'unknown'}. "
        f"File types: {', '.join(req.file_types) if req.file_types else 'unknown'}. "
        f"Previous runs: {'yes' if req.previous_runs else 'no'}."
        + (f" User question: {req.nlp_query}" if req.nlp_query else "")
    )

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            provider = req.llm_provider or "openai"
            resp = await client.post(
                "http://127.0.0.1:8011/api/llm/chat",
                params={"provider": provider},
                json={
                    "messages": [
                        {"role": "system", "content": _GUIDANCE_PROMPT},
                        {"role": "user",   "content": user_msg},
                    ],
                    "temperature": 0.2,
                    "max_tokens": 512,
                },
            )
            if resp.is_success:
                raw = resp.json().get("response", "")
                raw = re.sub(r"```(?:json)?", "", raw).strip().strip("`").strip()
                m = re.search(r"\{.*\}", raw, re.DOTALL)
                if m:
                    g = _json.loads(m.group(0))
                    return SmartGuidanceResponse(
                        recommendation=g.get("recommendation", "discovery"),
                        headline=g.get("headline", "Start with Discovery"),
                        reason=g.get("reason", ""),
                        expected_outcome=g.get("expected_outcome", ""),
                        next_steps=g.get("next_steps", []),
                        complexity=g.get("complexity", "low"),
                        estimated_time=g.get("estimated_time", ""),
                        tips=g.get("tips", []),
                        llm_powered=True,
                    )
    except Exception as e:
        logger.warning("Smart guidance LLM fallback failed: %s", e)

    # ── Rule-based last-resort fallback ───────────────────────────────────
    if not req.previous_runs:
        return SmartGuidanceResponse(
            recommendation="discovery",
            headline="Start with Discovery",
            reason=(
                "Your data hasn't been scanned yet. Discovery gives you a quick, "
                "safe look at what files you have and flags any obvious issues."
            ),
            expected_outcome=(
                "A clear summary of your files, record counts, and initial data issues."
            ),
            next_steps=[
                "Click 'Run Discovery' to scan your data",
                "Review the insights that appear",
                "Accept discovery and move to Profiling",
            ],
            complexity="low",
            estimated_time="2-5 minutes",
            tips=[
                "Discovery is read-only — it won't change your data",
                "You can re-run it any time to refresh the results",
            ],
            llm_powered=False,
        )
    return SmartGuidanceResponse(
        recommendation="profiling",
        headline="Run Data Profiling",
        reason=(
            "Discovery is done. Profiling goes deeper — it reads each column "
            "and checks for patterns, blanks, and unexpected values."
        ),
        expected_outcome=(
            "A column-by-column quality report and automatic classification of your data."
        ),
        next_steps=[
            "Click 'Run Semantic Analysis'",
            "Review the column quality report",
            "Proceed to Field Mapping",
        ],
        complexity="low",
        estimated_time="3-8 minutes",
        tips=["Profiling uses your existing discovery results — no extra setup needed"],
        llm_powered=False,
    )


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

#  AGENT ACTIVE / METRICS ENDPOINTS

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


# ── Semantic Profile via DataProfilerAgent (MCP) ───────────────────────────

# ---------------------------------------------------------------------------
# Heuristic column-name rules used as a fallback when the MCP agent cluster
# (DataProfilerAgent port 8031) is not reachable.
# ---------------------------------------------------------------------------
_ROLE_PATTERNS: list[tuple[str, str]] = [
    # Identifiers
    (r"(^|_)(id|key|pk|code|num|number|ref|sku|serial|uuid|guid)($|_)", "identifier"),
    # Timestamps / dates
    (r"(^|_)(date|datetime|timestamp|time|at|on|created|updated|modified|deleted)($|_)", "timestamp"),
    # Measures / quantities
    (r"(^|_)(qty|quantity|count|cnt|amount|total|sum|weight|size|length|width|height|volume|price|cost|value)($|_)", "measure"),
    # Categorical / status
    (r"(^|_)(type|kind|category|class|status|state|flag|level|grade|tier|priority)($|_)", "category"),
    # Textual labels
    (r"(^|_)(name|title|label|description|desc|text|notes|remarks|comment|summary)($|_)", "label"),
    # Relationships / foreign keys  (must come after identifier)
    (r"(^|_)(parent|child|owner|source|target|from|to|relation|link|ref_id|fk)($|_)", "relationship"),
    # File / path / URL
    (r"(^|_)(path|url|uri|file|filename|dir|folder|location|endpoint)($|_)", "path"),
    # Boolean flags
    (r"(^|_)(is_|has_|can_|allow|enable|active|deleted|archived)", "flag"),
    # Currency
    (r"(^|_)(price|cost|revenue|budget|charge|fee|rate|discount|tax|profit|loss)($|_)", "currency"),
]

_ENTITY_PATTERNS: list[tuple[str, str]] = [
    (r"(^|_)(part|component|item|article|product|assembly|assy)($|_)", "Part"),
    (r"(^|_)(bom|bill|structure|breakdown)($|_)", "BOM"),
    (r"(^|_)(supplier|vendor|manufacturer|mfr|mfg|sourcing)($|_)", "Supplier"),
    (r"(^|_)(doc|document|drawing|spec|specification|attachment|file)($|_)", "Document"),
    (r"(^|_)(eco|ecn|change|cr|deviation|waiver|rfc)($|_)", "ECO"),
    (r"(^|_)(rev|revision|version|ver|release|lifecycle|phase)($|_)", "Revision"),
    (r"(^|_)(test|result|measurement|inspection|defect|failure|pass|fail)($|_)", "TestResult"),
    (r"(^|_)(workflow|task|process|step|stage|activity|job|work)($|_)", "Workflow"),
]

# Well-known canonical names (source column → PLM canonical)
_CANONICAL: dict[str, str] = {
    "part_number": "part_id", "partnum": "part_id", "pn": "part_id",
    "component_id": "part_id", "item_id": "part_id", "item_number": "part_id",
    "bom_id": "bom_id", "bill_of_materials_id": "bom_id",
    "parent_part": "parent_part_id", "parent_id": "parent_part_id",
    "child_part": "child_part_id", "child_id": "child_part_id",
    "supplier_id": "supplier_id", "vendor_id": "supplier_id",
    "rev": "revision", "revision_code": "revision",
    "created": "created_at", "created_date": "created_at",
    "updated": "updated_at", "modified": "updated_at", "modified_date": "updated_at",
    "qty": "quantity", "quant": "quantity",
    "desc": "description",
}


def _classify_column(col: str) -> tuple[str, str | None, float]:
    """Return (semantic_role, entity_hint, confidence) for a column name."""
    lower = col.lower()
    role = "unknown"
    role_conf = 0.45
    for pattern, candidate_role in _ROLE_PATTERNS:
        if re.search(pattern, lower):
            role = candidate_role
            role_conf = 0.78
            break

    entity_hint: str | None = None
    for pattern, entity in _ENTITY_PATTERNS:
        if re.search(pattern, lower):
            entity_hint = entity
            break

    canonical = _CANONICAL.get(lower)
    # Slightly boost confidence when we have a known canonical mapping
    if canonical:
        role_conf = min(role_conf + 0.10, 0.92)

    return role, entity_hint, role_conf


def _heuristic_semantic_profile(req: "SemanticProfileRequest") -> dict:
    """
    Local heuristic fallback for semantic-profile.
    Derives column semantics purely from column-name pattern rules so the
    wizard gets meaningful results even when the MCP agent cluster is offline.
    """
    column_semantics: list[dict] = []
    seen: set[str] = set()

    # Collect columns from file_profiles
    for fp in req.file_profiles:
        for col_info in fp.get("columns", []):
            col = col_info.get("name") or col_info.get("column") or ""
            if not col or col in seen:
                continue
            seen.add(col)
            role, entity_hint, conf = _classify_column(col)
            entry: dict = {
                "column": col,
                "semantic_role": role,
                "confidence": round(conf, 2),
                "source": "heuristic",
            }
            canonical = _CANONICAL.get(col.lower())
            if canonical:
                entry["canonical_name"] = canonical
            if entity_hint:
                entry["entity_hint"] = entity_hint
            column_semantics.append(entry)

    # Also collect columns from column_corpus if no file_profiles
    if not column_semantics:
        for cc in req.column_corpus:
            col = cc.get("name") or cc.get("column") or ""
            if not col or col in seen:
                continue
            seen.add(col)
            role, entity_hint, conf = _classify_column(col)
            entry = {"column": col, "semantic_role": role, "confidence": round(conf, 2), "source": "heuristic"}
            canonical = _CANONICAL.get(col.lower())
            if canonical:
                entry["canonical_name"] = canonical
            if entity_hint:
                entry["entity_hint"] = entity_hint
            column_semantics.append(entry)

    # Derive top entity class from the most frequent entity_hint
    entity_counts: dict[str, int] = {}
    for cs in column_semantics:
        if cs.get("entity_hint"):
            entity_counts[cs["entity_hint"]] = entity_counts.get(cs["entity_hint"], 0) + 1
    top_entity = max(entity_counts, key=entity_counts.get) if entity_counts else None

    high_conf = sum(1 for cs in column_semantics if cs["confidence"] >= 0.75)

    semantic_insights = {
        "column_semantics": column_semantics,
        "entity_classifications": [
            {"entity_class": k, "column_count": v, "confidence": round(0.6 + 0.1 * min(v, 4), 2)}
            for k, v in sorted(entity_counts.items(), key=lambda x: -x[1])
        ],
        "cross_file_relationships": [],
        "summary": {
            "total_columns_analysed": len(column_semantics),
            "high_confidence_semantics": high_conf,
            "top_entity_class": top_entity,
            "relationship_count": 0,
            "source": "heuristic",
        },
    }
    return {"result": {"semantic_insights": semantic_insights}, "source": "heuristic"}


class SemanticProfileRequest(BaseModel):
    """
    Request body for POST /api/agentic/semantic-profile.

    Accepts either pre-computed file_profiles (from a prior DataDiscovery run)
    or a folder_path / source_name for the DataProfilerAgent to resolve itself.
    The column_corpus and entity_inference fields are optional enrichment inputs
    that can be piped from an upstream SchemaCorrelator result.
    """
    source_name: Optional[str] = None
    folder_path: Optional[str] = None
    file_profiles: List[Dict[str, Any]] = Field(default_factory=list)
    column_corpus: List[Dict[str, Any]] = Field(default_factory=list)
    entity_inference: Dict[str, Any] = Field(default_factory=dict)
    min_relationship_similarity: float = Field(default=0.85, ge=0.5, le=1.0)
    entity_confidence_threshold: float = Field(default=0.30, ge=0.0, le=1.0)
    enrich_from_schema_correlator: bool = False
    fetch_live_profiles: bool = False
    sample_rows: int = Field(default=500, ge=1, le=10_000)
    save_report: bool = True

    # Discovery run linkage (optional — ties results to a wizard session)
    discovery_run_id: Optional[str] = None


@router.post(
    "/semantic-profile",
    summary="Infer column semantics and entity classifications via DataProfilerAgent",
)
async def semantic_profile(
    req: SemanticProfileRequest,
    db: Session = Depends(get_db),
):
    """
    Submit a SEMANTIC_PROFILE task to the MCP orchestrator.

    Routes to DataProfilerAgent (port 8031) which implements the LLM Tool Prompt:
      • Column semantic meaning (part_id → identifier / Part, etc.)
      • Entity classification (Part, BOM, Supplier, Document, ECO, Revision)
      • Cross-file relationship detection via column name similarity
      • Schema alignment grouping

    Returns structured insights with confidence scores.
    When save_report=True the insights are persisted to the unified reports hub.
    """
    if not req.source_name and not req.folder_path and not req.file_profiles:
        raise HTTPException(
            status_code=400,
            detail="Provide source_name, folder_path, or file_profiles",
        )

    task = AgenticTask(
        type=TaskType.SEMANTIC_PROFILE,
        required_capabilities=["semantic_profile", "infer_column_semantics", "classify_entities"],
        payload={
            "source_name":                   req.source_name,
            "folder_path":                   req.folder_path,
            "file_profiles":                 req.file_profiles,
            "column_corpus":                 req.column_corpus,
            "entity_inference":              req.entity_inference,
            "min_relationship_similarity":   req.min_relationship_similarity,
            "entity_confidence_threshold":   req.entity_confidence_threshold,
            "enrich_from_schema_correlator": req.enrich_from_schema_correlator,
            "fetch_live_profiles":           req.fetch_live_profiles,
            "sample_rows":                   req.sample_rows,
        },
    )

    try:
        result_dict = await mcp_client.submit_task(task.model_dump(mode="json"))
    except (httpx.ConnectError, httpx.TimeoutException, httpx.ReadTimeout, Exception) as mcp_err:
        logger.warning(
            "MCP agent unavailable for semantic-profile, using heuristic fallback: %s", mcp_err
        )
        result_dict = _heuristic_semantic_profile(req)

    # Persist to unified reports hub if requested
    if req.save_report:
        try:
            inner = result_dict.get("result") or result_dict
            insights = inner.get("semantic_insights") or inner
            summary = insights.get("summary") or {}
            label = req.source_name or req.folder_path or "semantic-profile"
            unified = UnifiedReport(
                report_id=str(uuid.uuid4()),
                report_type="semantic_profile",
                title=f"Semantic Profile: {label}",
                source_page="data-discovery",
                status="info",
                summary={
                    "source_name":               req.source_name,
                    "folder_path":               req.folder_path,
                    "total_columns_analysed":    summary.get("total_columns_analysed", 0),
                    "high_confidence_semantics": summary.get("high_confidence_semantics", 0),
                    "top_entity_class":          summary.get("top_entity_class"),
                    "relationship_count":        summary.get("relationship_count", 0),
                    "discovery_run_id":          req.discovery_run_id,
                },
                result=result_dict,
                tags=["semantic_profile", "data_profiler"],
            )
            db.add(unified)
            db.commit()
            result_dict["report_id"] = unified.report_id
            logger.info("Semantic profile report saved: %s", unified.report_id)
        except Exception as persist_err:
            logger.warning("Failed to persist semantic profile report: %s", persist_err)
            db.rollback()

    return result_dict


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


# ── Agent Director: recommended actions from discovery state ──────────────

def _compute_recommended_actions(
    *,
    staged_from: str,
    soda: dict,
    dq_violations: list,
    field_count: int,
    issues_count: int,  # reserved for future threshold logic
) -> list[dict]:
    """
    Derive prioritised, actionable recommendations from the discovery result.

    Rules are evaluated purely in-process (no MCP required) so the wizard
    always gets a concrete action plan regardless of agent-cluster availability.

    Returns a list sorted by ascending priority (1 = highest urgency):
      { priority, action, label, reason, detail, severity }
    """
    actions: list[dict] = []

    # ── Source-registration / reachability issues ──────────────────────────
    if staged_from == "not_registered":
        actions.append({
            "priority": 1,
            "action": "register_source",
            "label": "Register data source",
            "reason": "Source is not registered — no sample data was collected.",
            "detail": (
                "Go to Admin → Data Sources and add this source, then re-run discovery "
                "to collect a live sample."
            ),
            "severity": "warning",
        })
    elif staged_from == "unreachable":
        actions.append({
            "priority": 1,
            "action": "fix_connection",
            "label": "Fix source connection",
            "reason": "Source could not be reached during sampling.",
            "detail": "Check Admin → Data Sources → connection settings and re-run.",
            "severity": "warning",
        })

    # ── No schema / no fields ─────────────────────────────────────────────
    if field_count == 0:
        actions.append({
            "priority": 2,
            "action": "check_source_schema",
            "label": "No fields discovered",
            "reason": "Schema could not be inferred — no records were sampled.",
            "detail": "Ensure the source has data and is accessible, then re-run discovery.",
            "severity": "warning",
        })

    # ── DQ rule violations ────────────────────────────────────────────────
    critical = [v for v in dq_violations if v.get("severity") in ("critical", "error")]
    warnings_ = [v for v in dq_violations if v.get("severity") not in ("critical", "error")]
    if critical:
        names = ", ".join(v["rule_name"] for v in critical[:3])
        actions.append({
            "priority": 2,
            "action": "resolve_dq_violations",
            "label": f"Fix {len(critical)} critical DQ violation(s)",
            "reason": f"Failed rules: {names}.",
            "detail": "Resolve data quality violations before mapping to avoid migration failures.",
            "severity": "error",
        })
    if warnings_:
        actions.append({
            "priority": 3,
            "action": "review_dq_warnings",
            "label": f"Review {len(warnings_)} DQ warning(s)",
            "reason": "Some quality rules are at warning level.",
            "detail": "Address warnings for a cleaner migration.",
            "severity": "warning",
        })

    # ── SODA completeness below threshold ────────────────────────────────
    overall_score = float(soda.get("overall_score") or 0)
    soda_status = str(soda.get("status") or "")
    if soda_status == "warn" or (soda_status and overall_score < 0.7):
        actions.append({
            "priority": 3,
            "action": "improve_completeness",
            "label": "Improve data completeness",
            "reason": f"Quality score {round(overall_score * 100)}% is below the 70% threshold.",
            "detail": "Fill missing required fields in the source before executing migration.",
            "severity": "warning",
        })

    # ── Happy-path: proceed to mapping ────────────────────────────────────
    if staged_from == "source" and field_count > 0 and not critical:
        actions.append({
            "priority": 4,
            "action": "proceed_to_mapping",
            "label": "Proceed to Field Mapping",
            "reason": (
                f"{field_count} field(s) discovered with pre-populated AI mapping suggestions."
            ),
            "detail": "Accept discovery and fine-tune field mappings in the next step.",
            "severity": "success",
        })

    actions.sort(key=lambda a: a["priority"])
    return actions


# ── Discovery Ingest: agent-director endpoint (works without MCP) ─────────

class DiscoveryIngestRequest(BaseModel):
    """Payload from the Migration Wizard after its local discovery pass."""
    run_id: str
    source_id: Optional[str] = None
    source_system_name: Optional[str] = None
    staged_from: str = "none"   # source | not_registered | unreachable | none
    inferred_source_fields: List[str] = Field(default_factory=list)
    soda_result: Optional[Dict[str, Any]] = None
    issues_count: int = 0
    issues_preview: List[Dict[str, Any]] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)


@router.post(
    "/discovery/ingest",
    summary="Persist wizard discovery results and return agent-directed actions + insights",
)
async def ingest_discovery_results(
    req: DiscoveryIngestRequest,
    db: Session = Depends(get_db),
):
    """
    The 'Agent Director' endpoint for the Migration Wizard.

    Works entirely without MCP (heuristic profiling + local DQ rule evaluation).
    Called at the end of runDiscovery so the wizard gets:
      - report_id — referenced later by acceptDiscovery → infer-mappings
      - semantic_insights — column roles, entity classifications (heuristic)
      - mapping_suggestions — canonical field mappings enriched by profiler
      - dq_violations — DB-backed DQ rules evaluated against the profile
      - recommended_actions — prioritised, actionable next steps
    """
    # ── 1. Heuristic semantic profile from field list ─────────────────────
    file_profiles: list[dict] = []
    if req.inferred_source_fields:
        file_profiles = [{
            "file": req.source_system_name or "source",
            "columns": [{"name": f} for f in req.inferred_source_fields],
        }]

    profile_req = SemanticProfileRequest(
        source_name=req.source_system_name or req.source_id or "wizard-discovery",
        file_profiles=file_profiles,
        save_report=False,
    )
    profile_result = _heuristic_semantic_profile(profile_req)
    semantic_insights: dict = (
        profile_result.get("result", {}).get("semantic_insights", {})
    )
    column_semantics: list[dict] = semantic_insights.get("column_semantics", [])

    # ── 2. Mapping suggestions enriched with canonical names ──────────────
    canon_map = {
        cs["column"]: cs["canonical_name"]
        for cs in column_semantics
        if cs.get("canonical_name")
    }
    mapping_suggestions: list[dict] = []
    for sf in req.inferred_source_fields:
        suggestion = _infer_mapping_for_field(sf)
        # Boost target field with profiler's canonical name when PLM synonym didn't match
        if sf in canon_map and suggestion.get("confidence") != "High":
            suggestion["targetField"] = canon_map[sf]
            suggestion["confidence"] = "Medium"
            suggestion["_source"] = "heuristic_canonical"
        mapping_suggestions.append(suggestion)

    # ── 3. DQ rule evaluation against a synthetic profile ─────────────────
    soda = req.soda_result or {}
    col_stats: dict[str, dict] = {
        cs["column"]: {"null_rate": 0.05, "semantic_role": cs.get("semantic_role")}
        for cs in column_semantics
    }
    synthetic_result: dict = {
        "result": {
            "files": [{
                "file": req.source_system_name or "source",
                "row_count": int(soda.get("total") or 0),
                "profile": col_stats,
            }]
        }
    }
    dq_violations = _evaluate_dq_rules_on_profile(synthetic_result, db)

    # ── 4. Agent director: compute recommended actions ─────────────────────
    recommended_actions = _compute_recommended_actions(
        staged_from=req.staged_from,
        soda=soda,
        dq_violations=dq_violations,
        field_count=len(req.inferred_source_fields),
        issues_count=req.issues_count,
    )

    # ── 5. Persist DiscoveryReport so infer-mappings can use it ───────────
    label = req.source_system_name or req.source_id or f"wizard-{req.run_id}"
    report_id: Optional[str] = None
    try:
        report = DiscoveryReport(
            report_id=str(uuid.uuid4()),
            label=label,
            source_id=req.source_id,
            folder_path=None,
            total_files=1 if req.inferred_source_fields else 0,
            total_size_bytes=0,
            result={
                "run_id": req.run_id,
                "staged_from": req.staged_from,
                "result": {
                    "inferred_schema": {f: "string" for f in req.inferred_source_fields},
                    "files": synthetic_result["result"]["files"],
                },
                "soda_result": soda,
            },
        )
        db.add(report)
        db.commit()
        db.refresh(report)
        report_id = report.report_id
        logger.info("Discovery ingest report saved: %s (run=%s)", report_id, req.run_id)
    except Exception as persist_err:
        logger.warning("Failed to persist discovery ingest report: %s", persist_err)
        db.rollback()

    return {
        "report_id": report_id,
        "run_id": req.run_id,
        "semantic_insights": semantic_insights,
        "mapping_suggestions": mapping_suggestions,
        "dq_violations": dq_violations,
        "dq_violations_count": len(dq_violations),
        "recommended_actions": recommended_actions,
    }


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


# ═══════════════════════════════════════════════════════════════════════════
#  UNIFIED AI WORKFLOW ORCHESTRATION
#  Drives all tools/capabilities through MCP agents in sequence:
#   Discover → Profile → Quality → ETL → Report
# ═══════════════════════════════════════════════════════════════════════════

_WORKFLOW_STEPS = ["discover", "profile", "quality", "etl", "report"]

# Maps each workflow step to the AgentType + required capabilities
_STEP_AGENT_MAP: Dict[str, Dict[str, Any]] = {
    "discover": {
        "task_type": TaskType.DATA_DISCOVERY,
        "required_capabilities": ["discover_files", "profile_files", "data_health_report"],
        "description": "Discover and enumerate files, infer schemas, collect stats",
    },
    "profile": {
        "task_type": TaskType.PROFILING,
        "required_capabilities": ["semantic_profile", "infer_column_semantics", "classify_entities"],
        "description": "Semantic profiling: column roles, entity classification, relationship detection",
    },
    "quality": {
        "task_type": TaskType.QUALITY_SCAN,
        "required_capabilities": ["quality_scan", "scan_datasource_quality", "recommend_rules"],
        "description": "Quality scan: DQ rules, anomaly detection, completeness scoring",
    },
    "etl": {
        "task_type": TaskType.ETL_PIPELINE,
        "required_capabilities": ["etl_pipeline", "manage_data_pipelines", "run_workflow"],
        "description": "ETL pipeline: extract, transform, load with rule validation and lineage",
    },
    "report": {
        "task_type": TaskType.REPORT_GENERATION,
        "required_capabilities": ["report_generation", "generate_plm_report", "generate_report"],
        "description": "Generate comprehensive report from all pipeline artifacts",
    },
}


class WorkflowStepRequest(BaseModel):
    """Request body for a single AI workflow step."""
    source_id: Optional[str] = None
    folder_path: Optional[str] = None
    run_id: Optional[str] = None
    workflow_id: Optional[str] = None
    file_profiles: List[Dict[str, Any]] = Field(default_factory=list)
    records: List[Dict[str, Any]] = Field(default_factory=list)
    prior_results: Dict[str, Any] = Field(default_factory=dict)
    params: Dict[str, Any] = Field(default_factory=dict)


class WorkflowStepResult(BaseModel):
    step: str
    status: str          # "completed" | "failed" | "skipped"
    agent_id: Optional[str] = None
    agent_type: Optional[str] = None
    success: bool = False
    result: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None
    execution_time: float = 0.0


class WorkflowRunRequest(BaseModel):
    """Request body for POST /api/agentic/workflow/run — runs all 5 AI steps."""
    source_id: Optional[str] = None
    folder_path: Optional[str] = None
    run_id: Optional[str] = None
    workflow_name: Optional[str] = None
    steps: List[str] = Field(
        default_factory=lambda: list(_WORKFLOW_STEPS),
        description="Ordered list of steps to run. Defaults to all 5.",
    )
    params: Dict[str, Any] = Field(default_factory=dict)
    stop_on_failure: bool = False


class WorkflowRunResult(BaseModel):
    workflow_run_id: str
    source_id: Optional[str]
    folder_path: Optional[str]
    steps_requested: List[str]
    steps_completed: List[str]
    steps_failed: List[str]
    overall_success: bool
    step_results: Dict[str, WorkflowStepResult]
    summary: Dict[str, Any] = Field(default_factory=dict)
    started_at: datetime = Field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    total_execution_time: float = 0.0


def _build_step_payload(
    step: str,
    req_source_id: Optional[str],
    folder_path: Optional[str],
    run_id: Optional[str],
    prior_results: Dict[str, Any],
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """Build the MCP task payload for a given workflow step, forwarding prior step outputs."""
    base: Dict[str, Any] = {
        "source_id": req_source_id,
        "folder_path": folder_path,
        "run_id": run_id,
        **params,
    }
    # Forward file profiles from discover step to profile/quality/report
    if step in ("profile", "quality", "report"):
        discover = prior_results.get("discover", {})
        file_profiles = (
            discover.get("file_profiles")
            or discover.get("discovered_files")
            or discover.get("files")
            or []
        )
        if file_profiles:
            base["file_profiles"] = file_profiles
        records = discover.get("sample_records") or discover.get("records") or []
        if records:
            base["records"] = records

    # Forward profile insights to quality/report
    if step in ("quality", "report"):
        profile = prior_results.get("profile", {})
        if profile:
            base["profile_summary"] = profile
            base["column_corpus"] = profile.get("column_corpus") or profile.get("semantic_insights", {}).get("columns") or []

    # Forward quality results to etl/report
    if step in ("etl", "report"):
        quality = prior_results.get("quality", {})
        if quality:
            base["quality_summary"] = quality
            base["dq_violations"] = quality.get("violations") or quality.get("rule_validation", {}).get("violations") or []

    # Forward ETL results to report
    if step == "report":
        etl = prior_results.get("etl", {})
        if etl:
            base["etl_summary"] = etl

    return base


@router.post(
    "/workflow/step/{step_name}",
    response_model=WorkflowStepResult,
    summary="Run a single AI workflow step via the MCP agent cluster",
)
async def run_workflow_step(
    step_name: str,
    req: WorkflowStepRequest,
):
    """
    Run one step of the AI-driven workflow via MCP:
      - **discover** → DataDiscoveryAgent
      - **profile**  → DataProfilerAgent
      - **quality**  → QualityMonitorAgent
      - **etl**      → ETLOrchestrator
      - **report**   → ReportingAgent

    Returns the agent's result for that step.
    """
    step_name = step_name.lower().strip()
    if step_name not in _STEP_AGENT_MAP:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown step '{step_name}'. Valid steps: {list(_STEP_AGENT_MAP.keys())}",
        )

    cfg = _STEP_AGENT_MAP[step_name]
    payload = _build_step_payload(
        step=step_name,
        req_source_id=req.source_id,
        folder_path=req.folder_path,
        run_id=req.run_id,
        prior_results=req.prior_results,
        params=req.params,
    )
    # Merge in any explicit file_profiles / records supplied by caller
    if req.file_profiles:
        payload["file_profiles"] = req.file_profiles
    if req.records:
        payload["records"] = req.records

    start = datetime.now()
    task = AgenticTask(
        type=cfg["task_type"],
        required_capabilities=cfg["required_capabilities"],
        payload=payload,
    )

    try:
        result_dict = await mcp_client.submit_task(task.model_dump(mode="json"))
        ar = AgenticTaskResult(**result_dict)
        return WorkflowStepResult(
            step=step_name,
            status="completed" if ar.success else "failed",
            agent_id=ar.agent_id,
            agent_type=str(ar.agent_type),
            success=ar.success,
            result=ar.result,
            error=ar.error,
            execution_time=(datetime.now() - start).total_seconds(),
        )
    except (httpx.ConnectError, httpx.TimeoutException, httpx.ReadTimeout) as e:
        raise HTTPException(
            status_code=503,
            detail=f"MCP agent cluster unavailable for step '{step_name}': {e}",
        ) from e
    except Exception as e:
        logger.error("Workflow step '%s' failed: %s", step_name, e)
        raise HTTPException(
            status_code=500,
            detail=f"Workflow step '{step_name}' failed: {e}",
        ) from e


@router.post(
    "/workflow/run",
    response_model=WorkflowRunResult,
    summary="Run the full AI workflow: Discover → Profile → Quality → ETL → Report",
)
async def run_full_workflow(req: WorkflowRunRequest):
    """
    Orchestrate the complete 5-step AI workflow through MCP agents:

    1. **Discover**  — DataDiscoveryAgent: enumerate files, infer schemas
    2. **Profile**   — DataProfilerAgent: semantic column analysis, entity classification
    3. **Quality**   — QualityMonitorAgent: DQ rules, anomaly detection, scoring
    4. **ETL**       — ETLOrchestrator: extract → transform → load with lineage
    5. **Report**    — ReportingAgent: assemble comprehensive pipeline report

    Each step receives the outputs of previous steps as context.
    Set `stop_on_failure=true` to abort on the first failing step.
    """
    if not req.source_id and not req.folder_path:
        raise HTTPException(
            status_code=400,
            detail="Provide source_id or folder_path",
        )

    run_id = req.run_id or f"wfrun_{int(datetime.now().timestamp()*1000)}"
    workflow_run_id = f"wr_{int(datetime.now().timestamp()*1000)}"
    started_at = datetime.now()

    # Validate requested steps
    steps_to_run: List[str] = []
    for s in req.steps:
        sl = s.lower().strip()
        if sl not in _STEP_AGENT_MAP:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown step '{sl}'. Valid: {list(_STEP_AGENT_MAP.keys())}",
            )
        steps_to_run.append(sl)

    step_results: Dict[str, WorkflowStepResult] = {}
    prior_results: Dict[str, Any] = {}
    completed: List[str] = []
    failed: List[str] = []

    for step_name in steps_to_run:
        cfg = _STEP_AGENT_MAP[step_name]
        payload = _build_step_payload(
            step=step_name,
            req_source_id=req.source_id,
            folder_path=req.folder_path,
            run_id=run_id,
            prior_results=prior_results,
            params=req.params,
        )

        step_start = datetime.now()
        task = AgenticTask(
            type=cfg["task_type"],
            required_capabilities=cfg["required_capabilities"],
            payload=payload,
        )

        try:
            result_dict = await mcp_client.submit_task(task.model_dump(mode="json"))
            ar = AgenticTaskResult(**result_dict)
            sr = WorkflowStepResult(
                step=step_name,
                status="completed" if ar.success else "failed",
                agent_id=ar.agent_id,
                agent_type=str(ar.agent_type),
                success=ar.success,
                result=ar.result,
                error=ar.error,
                execution_time=(datetime.now() - step_start).total_seconds(),
            )
            step_results[step_name] = sr
            if ar.success:
                completed.append(step_name)
                # Forward result as context to the next step
                prior_results[step_name] = ar.result
            else:
                failed.append(step_name)
                if req.stop_on_failure:
                    break

        except (httpx.ConnectError, httpx.TimeoutException, httpx.ReadTimeout) as e:
            sr = WorkflowStepResult(
                step=step_name,
                status="failed",
                success=False,
                error=f"MCP agent cluster unavailable: {e}",
                execution_time=(datetime.now() - step_start).total_seconds(),
            )
            step_results[step_name] = sr
            failed.append(step_name)
            if req.stop_on_failure:
                break
        except Exception as e:
            logger.error("Workflow step '%s' error: %s", step_name, e)
            sr = WorkflowStepResult(
                step=step_name,
                status="failed",
                success=False,
                error=str(e),
                execution_time=(datetime.now() - step_start).total_seconds(),
            )
            step_results[step_name] = sr
            failed.append(step_name)
            if req.stop_on_failure:
                break

    completed_at = datetime.now()
    total_time = (completed_at - started_at).total_seconds()
    overall_success = len(failed) == 0 and len(completed) > 0

    # Build workflow summary
    summary: Dict[str, Any] = {
        "run_id": run_id,
        "steps_run": len(steps_to_run),
        "steps_completed": len(completed),
        "steps_failed": len(failed),
        "total_execution_time_s": round(total_time, 2),
    }
    # Pull key metrics from each step result
    if "discover" in prior_results:
        d = prior_results["discover"]
        summary["files_discovered"] = (
            len(d.get("discovered_files") or d.get("files") or [])
            or d.get("file_count", 0)
        )
    if "quality" in prior_results:
        q = prior_results["quality"]
        summary["quality_score"] = q.get("quality_score") or q.get("overall_score")
        summary["dq_violations"] = q.get("anomalies_found") or q.get("total_violations", 0)
    if "profile" in prior_results:
        p = prior_results["profile"]
        si = p.get("semantic_insights") or {}
        summary["columns_profiled"] = si.get("total_columns_analysed") or len(si.get("columns") or [])
    if "report" in prior_results:
        r = prior_results["report"]
        summary["report_id"] = r.get("report_id") or r.get("id")

    return WorkflowRunResult(
        workflow_run_id=workflow_run_id,
        source_id=req.source_id,
        folder_path=req.folder_path,
        steps_requested=steps_to_run,
        steps_completed=completed,
        steps_failed=failed,
        overall_success=overall_success,
        step_results=step_results,
        summary=summary,
        started_at=started_at,
        completed_at=completed_at,
        total_execution_time=total_time,
    )

