import sys
import os
import uuid
import json
import re
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


# ── PLM Migration Assistant — LLM system prompt template ──────────────────
# Filled at runtime with UI context; sent to backend LLM before keyword fallback.

_MIGRATION_ASSISTANT_PROMPT = """\
You are an intelligent PLM Data Migration Assistant.

The user is interacting via a UI (not technical). Your job is to:
- Understand intent
- Ask for missing inputs if required
- Convert the request into an agentic execution plan

Context:
- The system uses multiple agents (Discovery, Profiling, Quality, ETL, Reporting)
- Execution happens as a DAG (parallel + sequential tasks)
- Data may be large, inconsistent, and dynamic

User Input:
{user_message}

UI Context (if available):
- selected_data_source: {source_name}
- file_count: {file_count}
- file_types: {file_types}
- previous_runs: {previous_runs}
- user_role: {user_role}

Your Tasks:

1. Classify intent — MUST be one of:
   - data_discovery
   - data_profiling
   - data_quality
   - migration
   - analysis

2. Enrich missing context:
   - If source not defined → ask user
   - If large dataset → enable batch processing
   - If multiple file types → enable adaptive parsing

3. Generate execution plan:
   - Define DAG stages
   - Identify parallel tasks
   - Assign required agent capabilities

4. Output STRICT JSON (no markdown, no explanation — raw JSON only):

{{
  "intent": "...",
  "confidence": 0.0,
  "requires_user_input": false,
  "questions": [],
  "execution_plan": {{
    "mode": "parallel | sequential | hybrid",
    "stages": [
      {{
        "stage": 1,
        "name": "Data Discovery",
        "parallel": true,
        "tasks": []
      }}
    ]
  }},
  "ui_response": {{
    "summary": "...",
    "next_steps": [],
    "estimated_time": "...",
    "complexity": "low | medium | high"
  }}
}}
"""

# ── Smart Guidance — LLM system prompt template ───────────────────────────
# Returns a business-friendly, one-step recommendation when the user is unsure
# what to do with their data. Output is strict JSON — no markdown.

_SMART_GUIDANCE_PROMPT = """\
You are a friendly data assistant helping a business user who is unsure what to do next with their data.

Their context:
- Data source: {source_name}
- Number of files / records: {file_count}
- File types detected: {file_types}
- Has run any profiling or discovery before: {previous_runs}
- User role: {user_role}

Based on this context, recommend the SINGLE best first step from:
  - "discovery"   — scan and map what files/data exist (best when user has never scanned before)
  - "profiling"   — understand columns, data patterns, and quality (best after discovery)
  - "quality"     — run data-quality checks and fix issues (best before migrating)

Rules:
- If no profiling or discovery has been done yet → recommend "discovery"
- If discovery was done but no profiling → recommend "profiling"
- If both done but data quality unknown → recommend "quality"
- Use plain, jargon-free language that a business analyst would understand
- Be positive and encouraging; keep "reason" under 2 sentences
- "expected_outcome" must say concretely what the user will see or get

Output STRICT JSON only (no markdown, no explanation):

{{
  "recommendation": "discovery | profiling | quality",
  "headline": "Short action title, e.g. Start with Discovery",
  "reason": "One or two plain sentences explaining why this step first.",
  "expected_outcome": "What the user will see or achieve after this step.",
  "next_steps": ["Step 1 plain action", "Step 2 plain action", "Step 3 plain action"],
  "complexity": "low | medium | high",
  "estimated_time": "e.g. 2-5 minutes",
  "tips": ["Optional short tip 1", "Optional short tip 2"]
}}
"""

_OLLAMA_MIGRATION_ASSISTANT_PROMPT = """\
You are a PLM data migration assistant.

Classify the user intent as exactly one of:
- data_discovery
- data_profiling
- data_quality
- migration
- analysis
- smart_guidance

Return compact JSON only:
{
  "intent": "...",
  "confidence": 0.0,
  "requires_user_input": false,
  "questions": [],
  "ui_response": {
    "summary": "...",
    "next_steps": [],
    "estimated_time": "...",
    "complexity": "low | medium | high"
  }
}
"""

_OLLAMA_SMART_GUIDANCE_PROMPT = """\
You are a friendly data assistant. Choose one first step: discovery, profiling, or quality.
Return compact JSON only with keys recommendation, headline, reason, expected_outcome,
next_steps, complexity, estimated_time, tips.
Keep reason short and next_steps to at most 3 items.
"""


# LLM Provider Registry - Extensible provider configuration
class _LLMProviderRegistry:
    """Registry for LLM provider-specific configurations"""
    
    def __init__(self):
        self.providers = {
            "ollama": {
                "classification": {
                    "timeout": float(os.getenv("OLLAMA_CLASSIFIER_TIMEOUT_SECONDS", "20")),
                    "max_tokens": int(os.getenv("OLLAMA_CLASSIFIER_MAX_TOKENS", "160")),
                    "system_prompt": _OLLAMA_MIGRATION_ASSISTANT_PROMPT,
                },
                "guidance": {
                    "timeout": float(os.getenv("OLLAMA_GUIDANCE_TIMEOUT_SECONDS", "20")),
                    "max_tokens": int(os.getenv("OLLAMA_GUIDANCE_MAX_TOKENS", "192")),
                    "system_prompt": _OLLAMA_SMART_GUIDANCE_PROMPT,
                },
            },
            "openai": {
                "classification": {
                    "timeout": 20.0,
                    "max_tokens": 1024,
                    "system_prompt": _MIGRATION_ASSISTANT_PROMPT,
                },
                "guidance": {
                    "timeout": 15.0,
                    "max_tokens": 512,
                    "system_prompt": _SMART_GUIDANCE_PROMPT,
                },
            },
        }
    
    def get_settings(self, provider: str, purpose: str) -> dict:
        """Get settings for a provider and purpose (classification/guidance)"""
        normalized_provider = str(provider).strip().lower()
        
        if normalized_provider not in self.providers:
            logger.warning(f"Unknown LLM provider: {provider}, using OpenAI defaults")
            normalized_provider = "openai"
        
        settings = self.providers[normalized_provider].get(purpose)
        if not settings:
            logger.error(f"No {purpose} settings for provider {normalized_provider}")
            raise ValueError(f"Unsupported purpose: {purpose}")
        
        return settings
    
    def register_provider(self, provider_name: str, config: dict):
        """Register a new LLM provider configuration"""
        self.providers[str(provider_name).lower()] = config
        logger.info(f"Registered LLM provider: {provider_name}")


_provider_registry = _LLMProviderRegistry()


def _get_llm_request_settings(provider: str, purpose: str) -> dict:
    """Get LLM request settings for a provider and purpose"""
    return _provider_registry.get_settings(provider, purpose)

# Maps LLM intent labels → internal (intent, task_type, required_capabilities)
_LLM_INTENT_MAP: dict[str, tuple[str, str, list[str]]] = {
    "data_discovery": (
        "data_discovery",
        "data_discovery",
        ["discover_files", "profile_files"],
    ),
    "data_profiling": (
        "semantic_profile",
        "semantic_profile",
        ["semantic_profile", "infer_column_semantics", "classify_entities"],
    ),
    "data_quality": (
        "quality_check",
        "data_quality_scan",
        ["monitor_data_quality", "scan_datasource_quality"],
    ),
    "migration": (
        "migration",
        "task_decomposition",
        ["decompose_goal"],
    ),
    # LLM may classify PLM-specific requests as migration; map to PLM Director path
    "plm_migration": (
        "plm_migration",
        "plm_migration_orchestration",
        ["orchestrate_plm_migration"],
    ),
    "analysis": (
        "data_analysis",
        "data_analysis",
        ["data_analysis"],
    ),
    # User is unsure what to do → return a business-friendly recommendation
    "smart_guidance": (
        "smart_guidance",
        "smart_guidance",
        [],
    ),
}


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
    # Smart Guidance — user is unsure what to do; return a business-friendly recommendation
    (
        [
            "not sure", "unsure", "where to start", "what should i do", "help me decide",
            "guide me", "what's next", "what to do", "how to begin", "smart guidance",
            "suggest", "recommend", "best approach", "where do i start",
        ],
        "smart_guidance",
        "smart_guidance",
        [],
        "Let me help you figure out the best next step for your data...",
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

    async def _classify_intent_with_llm(self, message: str, payload: dict) -> dict | None:
        """
        Call the backend LLM integration endpoint with the PLM Migration Assistant
        system prompt to classify intent and generate a structured execution plan.

        Returns parsed JSON plan dict on success, or None when LLM is unavailable /
        not configured (caller falls back to keyword _classify_intent).
        """
        source_name   = payload.get("source_name") or payload.get("source_id") or "Not selected"
        file_count    = payload.get("file_count", "Unknown")
        file_types    = payload.get("file_types", "Unknown")
        previous_runs = payload.get("previous_runs", "None")
        user_role     = payload.get("user_role", "business")
        llm_provider  = payload.get("llm_provider", "openai")
        llm_settings  = _get_llm_request_settings(llm_provider, "classification")

        # Prevent prompt injection by escaping user input properly
        safe_message = json.dumps(message)  # Escapes special characters and braces
        filled = llm_settings["system_prompt"].format(
            user_message=safe_message,
            source_name=source_name,
            file_count=file_count,
            file_types=file_types,
            previous_runs=previous_runs,
            user_role=user_role,
        )

        try:
            backend_url = os.getenv("GRAPH_TRACE_BACKEND_URL", "http://127.0.0.1:8011")
            async with httpx.AsyncClient(timeout=llm_settings["timeout"]) as client:
                resp = await client.post(
                    f"{backend_url}/api/llm/chat",
                    params={"provider": llm_provider},
                    json={
                        "messages": [
                            {"role": "system", "content": filled},
                            {"role": "user",   "content": message},
                        ],
                        "temperature": 0.1,
                        "max_tokens": llm_settings["max_tokens"],
                    },
                )
                if not resp.is_success:
                    logger.debug("LLM classifier returned %d — falling back to keywords", resp.status_code)
                    return None

                raw = resp.json().get("response", "")
                # Strip markdown code fences if present
                raw = re.sub(r"```(?:json)?", "", raw).strip().strip("`").strip()
                # Extract first {...} JSON block
                m = re.search(r"\{.*\}", raw, re.DOTALL)
                if not m:
                    return None
                plan: dict = json.loads(m.group(0))
                # Validate required keys
                if "intent" not in plan:
                    return None
                logger.info(
                    "LLM classifier: intent=%s confidence=%.2f requires_input=%s",
                    plan.get("intent"),
                    plan.get("confidence", 0),
                    plan.get("requires_user_input", False),
                )
                return plan
        except Exception as exc:
            logger.debug("LLM classifier unavailable: %s", exc)
            return None

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

    async def _generate_smart_guidance(self, payload: dict) -> dict:
        """
        Call the backend LLM with _SMART_GUIDANCE_PROMPT to produce a business-friendly,
        one-step recommendation tailored to the user's dataset context.

        Returns a dict with keys: recommendation, headline, reason, expected_outcome,
        next_steps, complexity, estimated_time, tips.
        Falls back to a rule-based recommendation when LLM is unavailable.
        """
        source_name   = payload.get("source_name") or payload.get("source_id") or "Not specified"
        file_count    = payload.get("file_count", "Unknown")
        file_types    = payload.get("file_types", "Unknown")
        previous_runs = payload.get("previous_runs", False)
        user_role     = payload.get("user_role", "business")
        llm_provider  = payload.get("llm_provider", "openai")
        llm_settings  = _get_llm_request_settings(llm_provider, "guidance")

        filled = llm_settings["system_prompt"].format(
            source_name=source_name,
            file_count=file_count,
            file_types=file_types,
            previous_runs="Yes" if previous_runs else "No",
            user_role=user_role,
        )

        try:
            backend_url = os.getenv("GRAPH_TRACE_BACKEND_URL", "http://127.0.0.1:8011")
            async with httpx.AsyncClient(timeout=llm_settings["timeout"]) as client:
                resp = await client.post(
                    f"{backend_url}/api/llm/chat",
                    params={"provider": llm_provider},
                    json={
                        "messages": [
                            {"role": "system", "content": filled},
                            {"role": "user", "content": "What should I do first with my data?"},
                        ],
                        "temperature": 0.2,
                        "max_tokens": llm_settings["max_tokens"],
                    },
                )
                if resp.is_success:
                    raw = resp.json().get("response", "")
                    raw = re.sub(r"```(?:json)?", "", raw).strip().strip("`").strip()
                    m = re.search(r"\{.*\}", raw, re.DOTALL)
                    if m:
                        guidance = json.loads(m.group(0))
                        if "recommendation" in guidance and "headline" in guidance:
                            return guidance
        except Exception as exc:
            logger.debug("Smart guidance LLM call failed: %s", exc)

        # ── Rule-based fallback ────────────────────────────────────────────
        had_runs = bool(previous_runs) if isinstance(previous_runs, bool) else (
            str(previous_runs).lower() not in ("false", "no", "none", "0", "")
        )
        if not had_runs:
            return {
                "recommendation": "discovery",
                "headline": "Start with Discovery",
                "reason": (
                    "Your data hasn't been scanned yet. Discovery gives you a quick, "
                    "safe look at what files you have and flags any obvious problems."
                ),
                "expected_outcome": (
                    "A clear summary of your files, record counts, and an initial list "
                    "of data issues to be aware of."
                ),
                "next_steps": [
                    "Click 'Run Discovery' to scan your data",
                    "Review the insights that appear",
                    "Accept discovery and move to Profiling",
                ],
                "complexity": "low",
                "estimated_time": "2-5 minutes",
                "tips": [
                    "Discovery is read-only — it won't change your data",
                    "You can re-run it any time to refresh the results",
                ],
            }
        return {
            "recommendation": "profiling",
            "headline": "Run Data Profiling",
            "reason": (
                "Discovery has already mapped your files. "
                "Profiling goes deeper — it understands each column and checks for "
                "patterns, blanks, and unexpected values."
            ),
            "expected_outcome": (
                "A column-by-column quality report and an automatic classification "
                "of your data (e.g. Parts, BOMs, Suppliers)."
            ),
            "next_steps": [
                "Click 'Run Semantic Analysis' to start profiling",
                "Review the column quality report",
                "Proceed to Field Mapping",
            ],
            "complexity": "low",
            "estimated_time": "3-8 minutes",
            "tips": [
                "Profiling uses your existing discovery results — no extra setup needed",
                "High-confidence columns are automatically matched for you",
            ],
        }

    async def process_task(self, task: AgentTaskRequest):
        message = task.payload.get("message", task.payload.get("goal", ""))
        if not message:
            return {
                "status": "error",
                "task_id": task.task_id,
                "primaryResponse": "No message provided.",
                "timestamp": datetime.now().isoformat(),
            }

        # ── Try LLM-based intent classification first ──────────────────────
        llm_plan = await self._classify_intent_with_llm(message, task.payload)

        # ── Handle: LLM says more user input is needed ─────────────────────
        if llm_plan and llm_plan.get("requires_user_input"):
            ui = llm_plan.get("ui_response", {})
            return {
                "status": "awaiting_input",
                "task_id": task.task_id,
                "primaryResponse": ui.get("summary", "I need a bit more information before I can proceed."),
                "intent": llm_plan.get("intent", "general_chat"),
                "collaborationNeeded": False,
                "requires_user_input": True,
                "questions": llm_plan.get("questions", []),
                "complexity": ui.get("complexity", "medium"),
                "execution_plan": llm_plan.get("execution_plan"),
                "timestamp": datetime.now().isoformat(),
            }

        # ── Map LLM intent → internal dispatch params ──────────────────────
        if llm_plan and llm_plan.get("intent") in _LLM_INTENT_MAP:
            llm_intent_key = llm_plan["intent"]
            intent, task_type, caps = _LLM_INTENT_MAP[llm_intent_key]
            ui = llm_plan.get("ui_response", {})
            # Prefer LLM-generated summary as the user-facing response text;
            # fall back to keyword map text.
            response_text = ui.get("summary") or self._classify_intent(message)[3]
            needs_agents = True
            llm_next_steps   = ui.get("next_steps", [])
            llm_complexity    = ui.get("complexity", "medium")
            llm_est_time      = ui.get("estimated_time", "")
            llm_execution_plan = llm_plan.get("execution_plan")
            logger.info("LLM intent=%s → internal intent=%s task_type=%s", llm_intent_key, intent, task_type)
        else:
            # ── Keyword fallback ───────────────────────────────────────────
            if llm_plan is None:
                logger.debug("LLM classifier unavailable — using keyword fallback")
            else:
                logger.debug("LLM returned unknown intent '%s' — using keyword fallback", llm_plan.get("intent"))
            intent, task_type, caps, response_text, needs_agents = self._classify_intent(message)
            llm_next_steps    = []
            llm_complexity    = "medium"
            llm_est_time      = ""
            llm_execution_plan = None

        # ── Simple chat — no agent dispatch ───────────────────────────────
        if not needs_agents:
            return {
                "status": "completed",
                "task_id": task.task_id,
                "primaryResponse": response_text,
                "intent": intent,
                "collaborationNeeded": False,
                "followupQuestions": llm_next_steps or ["Would you like to analyze your data?", "Would you like to run a quality scan?"],
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
                "next_steps":       llm_next_steps,
                "complexity":       llm_complexity,
                "estimated_time":   llm_est_time,
                "llm_execution_plan": llm_execution_plan,
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
                "next_steps":       llm_next_steps,
                "complexity":       llm_complexity,
                "estimated_time":   llm_est_time,
                "llm_execution_plan": llm_execution_plan,
                "timestamp": datetime.now().isoformat(),
            }

        # ── Smart Guidance — business-friendly "what should I do?" ─────────
        if intent == "smart_guidance":
            guidance = await self._generate_smart_guidance(task.payload)
            return {
                "status": "completed",
                "task_id": task.task_id,
                "primaryResponse": guidance.get("headline", response_text),
                "intent": intent,
                "collaborationNeeded": False,
                "smart_guidance": guidance,
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
                    "next_steps":       llm_next_steps,
                    "complexity":       llm_complexity,
                    "estimated_time":   llm_est_time,
                    "llm_execution_plan": llm_execution_plan,
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
            "next_steps":       llm_next_steps,
            "complexity":       llm_complexity,
            "estimated_time":   llm_est_time,
            "llm_execution_plan": llm_execution_plan,
            "timestamp": datetime.now().isoformat(),
        }


agent = ChatCoordinatorAgent()
app = agent.app

if __name__ == "__main__":
    agent.start()

