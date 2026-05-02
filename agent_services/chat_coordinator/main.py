import sys
import os
import uuid
import httpx
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from contextlib import asynccontextmanager
from fastapi import FastAPI

# Add parent directory to path to allow importing base
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

# Load environment variables from backend .env
env_path = Path(__file__).resolve().parent.parent.parent / "python_backend" / ".env"
load_dotenv(dotenv_path=env_path)

from neo4j import AsyncGraphDatabase
from agent_services.base.agent_service import AgentService
from agent_services.base.models import AgentCapability, AgentTaskRequest, AgentType

import logging
logger = logging.getLogger(__name__)


# ── Intent → task type/capability mapping ─────────────────────────────────

_INTENT_MAP = [
    # (keywords, intent, task_type, required_capabilities, response_text)
    # PLM Director — highest priority; routes directly to PLM Director agent (port 8029)
    (
        [
            "plm", "product lifecycle", "deep profile", "schema correlation",
            "corpus", "heterogeneous", "cross-file", "cross file", "schema drift",
            "200 files", "fk candidates", "foreign key", "plm migration",
        ],
        "plm_migration",
        "plm_migration_orchestration",
        ["orchestrate_plm_migration"],
        "Launching PLM Data Migration Director — running 3-wave DAG (Discovery ‖ SchemaCorrelator → Quality ‖ Analysis → ETL)...",
    ),
    # DataProfiler — LLM Tool Prompt: semantic column analysis + entity classification
    (
        [
            "semantic profile", "infer column", "infer semantic", "column meaning",
            "entity classification", "classify entity", "part bom supplier",
            "column role", "identify columns", "semantic analysis",
            "detect relationships", "schema alignment", "column similarity",
        ],
        "semantic_profile",
        "semantic_profile",
        ["semantic_profile"],
        "Running DataProfilerAgent — inferring column semantics, entity classification, and cross-file relationships...",
    ),
    (
        [
            "migrate", "schema", "etl migration",
        ],
        "migration",
        "task_decomposition",
        ["decompose_goal"],
        "Decomposing migration into discovery → quality → ETL pipeline...",
    ),
    (
        ["analyze", "pattern", "trend", "distribution", "insight"],
        "data_analysis",
        "data_analysis",
        ["data_analysis"],
        "Running data analysis via the Data Analyst agent...",
    ),
    (
        ["quality", "dq", "scan", "anomaly", "validate"],
        "quality_check",
        "data_quality_scan",
        ["monitor_data_quality"],
        "Running data quality scan via the Quality Monitor agent...",
    ),
    (
        ["discover", "files", "profile", "catalog", "infer schema"],
        "data_discovery",
        "data_discovery",
        ["discover_files"],
        "Discovering and profiling files via the Data Discovery agent...",
    ),
    (
        ["pipeline", "etl", "load", "transform"],
        "etl_request",
        "pipeline_orchestration",
        ["manage_data_pipelines"],
        "Coordinating ETL pipeline via the ETL Orchestrator...",
    ),
    (
        ["chart", "plot", "visualize", "graph layout"],
        "visualization",
        "visualization_generation",
        ["generate_graph_layouts"],
        "Generating visualization via Data Analyst + Visualization agents...",
    ),
    (
        ["query", "cypher", "match", "neo4j"],
        "graph_query",
        "graph_query",
        ["execute_cypher_queries"],
        "Executing graph query via the Data Analyst agent...",
    ),
    (
        ["sql", "postgres", "table", "select"],
        "sql_query",
        "data_analysis",
        ["sql_query"],
        "Executing SQL query via the Data Analyst agent...",
    ),
]


class ChatCoordinatorAgent(AgentService):
    """Director agent: classifies user intent → decomposes goal → executes multi-agent DAG."""

    def __init__(self):
        super().__init__(
            agent_type=AgentType.CHAT_COORDINATOR,
            agent_name="Chat Coordination Agent",
            port=8025,
        )
        self.neo4j_uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        self.neo4j_user = os.getenv("NEO4J_USER", "neo4j")
        self.neo4j_password = os.getenv("NEO4J_PASSWORD", "password")
        self.driver = None

    @asynccontextmanager
    async def _lifespan(self, _app: FastAPI):
        try:
            self.driver = AsyncGraphDatabase.driver(
                self.neo4j_uri,
                auth=(self.neo4j_user, self.neo4j_password),
            )
            await self.driver.verify_connectivity()
            logger.info("ChatCoordinator: Neo4j connectivity verified.")
        except Exception as e:
            logger.warning("ChatCoordinator: Neo4j connectivity failed: %s", e)

        async with super()._lifespan(_app):
            yield

        if self.driver:
            await self.driver.close()

    def get_capabilities(self):
        return [
            AgentCapability(name="process_natural_language", description="Classify user intent from free-text messages"),
            AgentCapability(name="coordinate_agent_responses", description="Director: decompose goal and dispatch multi-agent DAG"),
            AgentCapability(name="manage_conversation_context", description="Maintain conversation history and context"),
            AgentCapability(name="route_user_requests", description="Route user requests to the correct specialist agent"),
        ]

    # ── Intent classification ──────────────────────────────────────────────

    def _classify_intent(self, message: str):
        """Return (intent, task_type, required_capabilities, response_text, needs_agents).

        Scans _INTENT_MAP in order; returns first keyword match.
        Falls back to a generic chat response.
        """
        msg_lower = message.lower()
        for keywords, intent, task_type, caps, text in _INTENT_MAP:
            if any(kw in msg_lower for kw in keywords):
                return intent, task_type, caps, text, True

        return (
            "general_chat",
            None,
            [],
            f"I received: '{message}'. How can I help with your graph data today?",
            False,
        )

    # ── Director helpers ───────────────────────────────────────────────────

    async def _call_mcp(self, task_payload: dict, timeout: float = 20.0) -> dict:
        """POST a task to the MCP server and return the AgenticTaskResult dict."""
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(
                f"{self.mcp_server_url}/mcp/v1/tasks",
                json=task_payload,
            )
            resp.raise_for_status()
            return resp.json()

    async def _decompose_goal(self, goal: str, parent_task_id: str) -> list:
        """Ask TaskDecomposer (via MCP) to break a goal into a subtask DAG.

        Returns the raw subtasks list (may be empty on failure).
        """
        decomp_id = f"decomp_{uuid.uuid4().hex[:8]}"
        try:
            result = await self._call_mcp(
                {
                    "id": decomp_id,
                    "type": "task_decomposition",
                    "required_capabilities": ["decompose_goal"],
                    "payload": {
                        "goal": goal,
                        "parent_task_id": parent_task_id,
                    },
                    "priority": 7,
                },
                timeout=15.0,
            )
            # result is an AgenticTaskResult; subtasks are in result.result.subtasks
            return result.get("result", {}).get("subtasks", [])
        except Exception as exc:
            logger.warning("Goal decomposition failed: %s", exc)
            return []

    async def _submit_dag(self, dag_task_id: str, goal: str, subtasks_raw: list) -> dict:
        """Submit pre-decomposed subtasks to MCP /mcp/v1/tasks/dag."""
        # Remap parent_task_id to our new dag_task_id wrapper
        remapped = []
        for st in subtasks_raw:
            remapped.append(
                {
                    "id": st.get("id", f"st_{uuid.uuid4().hex[:8]}"),
                    "type": st.get("type", "data_analysis"),
                    "required_capabilities": st.get("required_capabilities", []),
                    "payload": st.get("payload", {}),
                    "dependencies": st.get("dependencies", []),
                    "priority": st.get("priority", 5),
                }
            )
        try:
            async with httpx.AsyncClient(timeout=90.0) as client:
                resp = await client.post(
                    f"{self.mcp_server_url}/mcp/v1/tasks/dag",
                    json={
                        "parent_task_id": dag_task_id,
                        "goal": goal,
                        "subtasks": remapped,
                        "priority": 5,
                    },
                )
                resp.raise_for_status()
                return resp.json()
        except Exception as exc:
            logger.warning("DAG submission failed: %s", exc)
            return {"error": str(exc)}

    async def _dispatch_single(self, task_type: str, caps: list, goal: str, parent_task_id: str) -> dict:
        """Submit a single-agent task to MCP and return the result dict."""
        task_id = f"single_{uuid.uuid4().hex[:8]}"
        try:
            return await self._call_mcp(
                {
                    "id": task_id,
                    "type": task_type,
                    "required_capabilities": caps,
                    "payload": {"goal": goal, "message": goal, "coordinated_by": parent_task_id},
                    "priority": 5,
                },
                timeout=30.0,
            )
        except Exception as exc:
            logger.warning("Single-agent dispatch failed: %s", exc)
            return {"error": str(exc)}

    # ── Main entry point ───────────────────────────────────────────────────

    async def _call_plm_director(self, message: str, payload: dict, parent_task_id: str) -> dict:
        """Invoke PLM Director directly via MCP task dispatch."""
        task_id = f"plm_{uuid.uuid4().hex[:8]}"
        try:
            return await self._call_mcp(
                {
                    "id": task_id,
                    "type": "plm_migration_orchestration",
                    "required_capabilities": ["orchestrate_plm_migration"],
                    "payload": {
                        "goal": message,
                        "message": message,
                        "coordinated_by": parent_task_id,
                        # Pass any corpus-locating keys the caller may have embedded
                        "source_id":   payload.get("source_id"),
                        "source_name": payload.get("source_name"),
                        "folder_path": payload.get("folder_path"),
                        "recursive":   payload.get("recursive", True),
                        "sample_rows": payload.get("sample_rows", 500),
                        "include_fk_detection": payload.get("include_fk_detection", True),
                        "include_clustering":   payload.get("include_clustering", True),
                        "migration_label": payload.get("migration_label"),
                    },
                    "priority": 9,
                },
                timeout=600.0,   # PLM runs can be long for large corpora
            )
        except Exception as exc:
            logger.warning("PLM Director dispatch failed: %s", exc)
            return {"error": str(exc)}

    async def _call_data_profiler(self, message: str, payload: dict, parent_task_id: str) -> dict:
        """
        Invoke DataProfilerAgent (port 8031) via MCP task dispatch.

        LLM TOOL PROMPT — orchestration layer:
          Sends file_profiles + column_corpus to DataProfilerAgent which:
            - Infers column semantic meaning (part_id, supplier_id, …)
            - Detects cross-file relationships via column name similarity
            - Classifies each file as Part / BOM / Supplier / Document / ECO / Revision
        """
        task_id = f"dp_{uuid.uuid4().hex[:8]}"
        try:
            return await self._call_mcp(
                {
                    "id":   task_id,
                    "type": "semantic_profile",
                    "required_capabilities": ["semantic_profile"],
                    "payload": {
                        "goal":    message,
                        "message": message,
                        "coordinated_by": parent_task_id,
                        "source_name":  payload.get("source_name"),
                        "folder_path":  payload.get("folder_path"),
                        "file_profiles":  payload.get("file_profiles", []),
                        "column_corpus":  payload.get("column_corpus", []),
                        "entity_inference": payload.get("entity_inference", {}),
                        "min_relationship_similarity": payload.get("min_relationship_similarity", 0.85),
                        "enrich_from_schema_correlator": payload.get("enrich_from_schema_correlator", False),
                        "fetch_live_profiles": payload.get("fetch_live_profiles", False),
                        "sample_rows":  payload.get("sample_rows", 500),
                    },
                    "priority": 7,
                },
                timeout=120.0,
            )
        except Exception as exc:
            logger.warning("DataProfiler dispatch failed: %s", exc)
            return {"error": str(exc)}

    async def process_task(self, task: AgentTaskRequest):
        message = task.payload.get("message", task.payload.get("goal", ""))
        if not message:
            return {
                "status": "error",
                "task_id": task.task_id,
                "primaryResponse": "No message provided.",
                "timestamp": datetime.now().isoformat(),
            }

        intent, task_type, caps, response_text, needs_agents = self._classify_intent(message)

        # ── Simple chat — no agent dispatch ───────────────────────────────
        if not needs_agents:
            return {
                "status": "completed",
                "task_id": task.task_id,
                "primaryResponse": response_text,
                "intent": intent,
                "collaborationNeeded": False,
                "followupQuestions": ["Would you like to analyze your data?", "Would you like to run a quality scan?"],
                "timestamp": datetime.now().isoformat(),
            }

        # ── PLM Director — full three-wave corpus migration ────────────────
        if intent == "plm_migration":
            plm_result = await self._call_plm_director(message, task.payload, task.task_id)
            report = plm_result.get("result", plm_result)
            # Support both PLMDirector (dataset_summary) and ReportingAgent (dataset_summary) field names
            dataset_summary = report.get("dataset_summary", report.get("corpus_summary", {}))
            dag_log = report.get("dag_execution_log", {})
            return {
                "status": "completed",
                "task_id": task.task_id,
                "primaryResponse": response_text,
                "intent": intent,
                "collaborationNeeded": True,
                "plm_report": {
                    "report_id":       report.get("report_id"),
                    "generated_at":    report.get("generated_at"),
                    "dataset_summary": dataset_summary,
                    "schema_drift_count":          len(report.get("schema_drift", [])),
                    "fk_candidate_count":          len(report.get("fk_candidates", report.get("key_candidates", []))),
                    "schema_cluster_count":         len(report.get("schema_clusters", [])),
                    "anomaly_count":                len(report.get("anomalies", [])),
                    "migration_readiness_score":    report.get("migration_readiness_score", {}),
                    "recommended_agent_actions":    report.get("recommended_agent_actions", report.get("recommendations", {})),
                    "dag_execution_log": dag_log,
                    "_adaptation_log":  report.get("_adaptation_log"),
                },
                "full_report": report,
                "timestamp": datetime.now().isoformat(),
            }

        # ── DataProfiler — LLM Tool Prompt: semantic column analysis ───────
        if intent == "semantic_profile":
            dp_result = await self._call_data_profiler(message, task.payload, task.task_id)
            dp_data   = dp_result.get("result", dp_result)
            insights  = dp_data.get("semantic_insights", dp_data)
            summary   = insights.get("summary", {})
            return {
                "status": "completed",
                "task_id": task.task_id,
                "primaryResponse": response_text,
                "intent": intent,
                "collaborationNeeded": True,
                "semantic_profile": {
                    "source_name":               dp_data.get("source_name"),
                    "generated_at":              dp_data.get("generated_at"),
                    "total_columns_analysed":    summary.get("total_columns_analysed", 0),
                    "high_confidence_semantics": summary.get("high_confidence_semantics", 0),
                    "top_entity_class":          summary.get("top_entity_class"),
                    "entity_class_distribution": summary.get("entity_class_distribution", {}),
                    "relationship_count":        summary.get("relationship_count", 0),
                    "column_semantics":          insights.get("column_semantics", [])[:50],
                    "entity_classifications":    insights.get("entity_classifications", []),
                    "cross_file_relationships":  insights.get("cross_file_relationships", [])[:30],
                    "schema_alignment_groups":   insights.get("schema_alignment_groups", []),
                },
                "full_insights": insights,
                "timestamp": datetime.now().isoformat(),
            }

        # ── Director mode: complex goal needing TaskDecomposer ─────────────
        if intent == "migration":
            subtasks_raw = await self._decompose_goal(message, task.task_id)

            if subtasks_raw:
                dag_task_id = f"dag_{uuid.uuid4().hex[:8]}"
                dag_result = await self._submit_dag(dag_task_id, message, subtasks_raw)
                return {
                    "status": "completed",
                    "task_id": task.task_id,
                    "primaryResponse": response_text,
                    "intent": intent,
                    "collaborationNeeded": True,
                    "plan": {
                        "subtask_count": len(subtasks_raw),
                        "subtasks": [
                            {
                                "id": st.get("id"),
                                "type": st.get("type"),
                                "capabilities": st.get("required_capabilities", []),
                                "depends_on": st.get("dependencies", []),
                            }
                            for st in subtasks_raw
                        ],
                    },
                    "execution_result": dag_result,
                    "timestamp": datetime.now().isoformat(),
                }
            # Decomposition returned nothing — fall through to single dispatch

        # ── Single-agent dispatch ──────────────────────────────────────────
        agent_result = await self._dispatch_single(task_type, caps, message, task.task_id)

        return {
            "status": "completed",
            "task_id": task.task_id,
            "primaryResponse": response_text,
            "intent": intent,
            "collaborationNeeded": True,
            "agent_type": task_type,
            "capabilities_used": caps,
            "agent_result": agent_result,
            "timestamp": datetime.now().isoformat(),
        }


agent = ChatCoordinatorAgent()
app = agent.app

if __name__ == "__main__":
    agent.start()

