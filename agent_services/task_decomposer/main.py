import sys
import os
import logging
from typing import Dict, Any, List, Optional
import uuid

# Add parent dir to path so we can import base module
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from agent_services.base.agent_service import AgentService
from agent_services.base.models import AgentTaskRequest, AgentType, AgentCapability

logger = logging.getLogger("task_decomposer")


# ── Goal template library ──────────────────────────────────────────────────
# Each entry: (keywords, builder_fn)
# builder_fn(task_id, payload) -> List[dict]  (raw subtask dicts)

def _st(parent_id: str, task_type: str, caps: list, payload: dict, deps: Optional[list] = None, priority: int = 5) -> dict:
    """Build a raw subtask dict."""
    return {
        "id": f"st_{uuid.uuid4().hex[:8]}",
        "parent_task_id": parent_id,
        "type": task_type,
        "required_capabilities": caps,
        "payload": payload,
        "dependencies": deps or [],
        "priority": priority,
    }


def _extract_source(payload: dict) -> dict:
    """Return a source dict with 'source_name' key extracted from goal/message text."""
    source_name = payload.get("source_name") or payload.get("source")
    if not source_name or source_name == "unknown":
        # Try to extract a quoted or parenthetical name from the goal text
        goal = payload.get("goal", payload.get("message", ""))
        import re
        # Match: 'from X', 'source X', 'named X' — capture word/phrase before optional qualifier
        m = re.search(r'\bfrom\s+["\']?([A-Za-z0-9_.\- ]+?)["\']?\s*(?:\(|$|\s)', goal, re.IGNORECASE)
        if not m:
            m = re.search(r'\bsource\s+["\']?([A-Za-z0-9_.\- ]+?)["\']?\s*(?:\(|$|\s)', goal, re.IGNORECASE)
        if m:
            source_name = m.group(1).strip()
    return {"source_name": source_name or ""} if source_name and source_name != "unknown" else {}


def _build_migration_dag(task_id: str, payload: dict) -> List[dict]:
    """Schema migration: discover → quality scan → ETL pipeline."""
    src = _extract_source(payload)
    disc = _st(task_id, "data_discovery",         ["discover_files", "profile_files"],  {**src, "include_profiling": True}, priority=8)
    qual = _st(task_id, "data_quality_scan",       ["monitor_data_quality"],             {**src}, [disc["id"]], priority=7)
    etl  = _st(task_id, "pipeline_orchestration",  ["manage_data_pipelines"],            {**src, "action": "build_migration"}, [qual["id"]], priority=6)
    return [disc, qual, etl]


def _build_analysis_dag(task_id: str, payload: dict) -> List[dict]:
    """Data analysis: discover → analyze → generate insights."""
    src = _extract_source(payload)
    disc = _st(task_id, "data_discovery", ["discover_files"],  {**src}, priority=7)
    anal = _st(task_id, "data_analysis",  ["data_analysis"],   {**src, "analysis_type": "simple_pattern"}, [disc["id"]], priority=6)
    return [disc, anal]


def _build_quality_dag(task_id: str, payload: dict) -> List[dict]:
    """Quality check: scan datasource → generate quality report."""
    src = _extract_source(payload)
    scan = _st(task_id, "data_quality_scan", ["monitor_data_quality"], {**src}, priority=8)
    rep  = _st(task_id, "data_analysis",     ["generate_insights"],    {**src, "analysis_type": "quality_summary"}, [scan["id"]], priority=5)
    return [scan, rep]


def _build_discovery_dag(task_id: str, payload: dict) -> List[dict]:
    """File discovery + profiling: single DataDiscovery agent task."""
    src = _extract_source(payload)
    return [
        _st(task_id, "data_discovery", ["discover_files", "profile_files", "infer_schema"],
            {**src, "include_profiling": True}, priority=8),
    ]


def _build_etl_dag(task_id: str, payload: dict) -> List[dict]:
    """ETL pipeline: discover + run pipeline."""
    src = _extract_source(payload)
    disc = _st(task_id, "data_discovery",         ["discover_files"],        {**src}, priority=7)
    pipe = _st(task_id, "pipeline_orchestration", ["manage_data_pipelines"], {**src}, [disc["id"]], priority=6)
    return [disc, pipe]


def _build_visualization_dag(task_id: str, payload: dict) -> List[dict]:
    """Visualize: query data → generate layout."""
    src = _extract_source(payload)
    data = _st(task_id, "data_analysis",            ["data_analysis"],           {**src, "analysis_type": "connectivity"}, priority=7)
    viz  = _st(task_id, "visualization_generation", ["generate_graph_layouts"],  {**src}, [data["id"]], priority=6)
    return [data, viz]


def _build_query_dag(task_id: str, payload: dict) -> List[dict]:
    """Cypher/graph query: plan → execute."""
    query = payload.get("query", payload.get("goal", ""))
    plan = _st(task_id, "graph_query",   ["optimize_graph_queries"],  {"query": query}, priority=7)
    exec_ = _st(task_id, "graph_query",  ["execute_cypher_queries"],  {"cypher_query": query}, [plan["id"]], priority=6)
    return [plan, exec_]


def _build_file_batch_dag(task_id: str, payload: dict) -> List[dict]:
    """Large-scale file batch processing via ETL Orchestrator."""
    src = _extract_source(payload)
    directory = payload.get("directory", src.get("source_name", ""))
    return [
        _st(task_id, "file_batch_processing", ["file_batch_processing"],
            {"directory": directory, "recursive": True, "extraction_method": "hybrid"}, priority=8),
    ]


def _build_plm_profiling_dag(task_id: str, payload: dict) -> List[dict]:
    """6-layer PLM deep-profiling DAG optimised for large heterogeneous corpora.

    Layer 1 — Parallel batch file discovery  (batch_count independent tasks)
    Layer 2 — Deep profiling per batch       (parallel, fan-out from L1)
    Layer 3 — Schema correlation             (parallel)
              Relationship detection         (parallel)
    Layer 4 — Data quality evaluation        (cross-file + within-file)
    Layer 5 — Schema intelligence / entity inference  (Part, BOM, Supplier, …)
    Layer 6 — Report generation

    Fault-tolerance policy:
    - L1/L2/L3b/L5: skip_on_max_retries=True  (non-blocking partial failure)
    - L3a/L4/L6:    skip_on_max_retries=False  (hard-stop if these fail)

    Payload keys recognised:
      folder_path, source_name, file_count (default 200), batch_size (default 25),
      sample_rows (default 1000), recursive (default True), migration_label
    """
    src             = _extract_source(payload)
    folder_path     = payload.get("folder_path", src.get("source_name", ""))
    file_count      = int(payload.get("file_count",   200))
    batch_size      = int(payload.get("batch_size",    25))
    sample_rows     = int(payload.get("sample_rows", 1000))
    recursive       = payload.get("recursive", True)
    migration_label = payload.get("migration_label")

    batch_count = max(1, (file_count + batch_size - 1) // batch_size)

    base = {**src, "folder_path": folder_path, "recursive": recursive}
    if migration_label:
        base["migration_label"] = migration_label

    # Fault-tolerance presets
    ft_skip    = {"retry_on_failure": True, "max_retries": 2, "skip_on_max_retries": True}
    ft_require = {"retry_on_failure": True, "max_retries": 3, "skip_on_max_retries": False}

    # ── Layer 1: Parallel batch file discovery ────────────────────────────
    l1_tasks = []
    for i in range(batch_count):
        t = _st(
            task_id, "file_discovery",
            ["discover_files", "batch_discover_segment"],
            {
                **base,
                "batch_index":   i,
                "batch_count":   batch_count,
                "batch_size":    batch_size,
                "file_patterns": ["*.csv", "*.json", "*.xml", "*.xlsx",
                                  "*.parquet", "*.tsv", "*.avro"],
            },
            priority=9,
        )
        t["dag_layer"]       = 1
        t["fault_tolerance"] = ft_skip   # a single batch failure is survivable
        l1_tasks.append(t)

    # ── Layer 2: Deep profiling per batch (parallel, one per L1) ─────────
    l2_tasks = []
    for i, disc in enumerate(l1_tasks):
        t = _st(
            task_id, "file_profiling",
            ["profile_files", "infer_schema"],
            {
                **base,
                "batch_index":     i,
                "batch_count":     batch_count,
                "sample_rows":     sample_rows,
                "include_stats":   True,
                "include_nulls":   True,
                "include_uniques": True,
            },
            [disc["id"]],
            priority=8,
        )
        t["dag_layer"]       = 2
        t["fault_tolerance"] = ft_skip   # skip failed batches; schema analysis handles gaps
        l2_tasks.append(t)

    l2_ids = [t["id"] for t in l2_tasks]

    # ── Layer 2.5: Semantic profiling — column semantics + entity inference ─
    # Runs in parallel with Schema Correlation (both depend on L2 outputs).
    # Implements the LLM TOOL PROMPT contract:
    #   - column semantic meaning (part_id, supplier_id, …)
    #   - entity classification (Part, BOM, Supplier, Document, ECO, Revision)
    #   - cross-file relationships via column name similarity
    sem_profile = _st(
        task_id, "semantic_profile",
        ["semantic_profile", "infer_column_semantics", "classify_entities",
         "detect_relationships", "align_schemas"],
        {
            **base,
            "capability":                    "semantic_profile",
            "enrich_from_schema_correlator": False,   # corpus fed from L2 output
            "min_relationship_similarity":   0.85,
            "entity_confidence_threshold":   0.30,
            "sample_rows":                   sample_rows,
        },
        l2_ids,
        priority=8,
    )
    sem_profile["dag_layer"]       = 3   # runs in parallel with schema_corr + rel_detect
    sem_profile["fault_tolerance"] = ft_skip   # enrichment — non-blocking

    # ── Layer 3: Schema correlation + Relationship detection (parallel) ───

    # 3a — Schema correlation: aggregates all batch profiles into corpus view
    schema_corr = _st(
        task_id, "schema_correlation",
        ["correlate_schemas", "detect_schema_drift", "detect_pk_candidates",
         "cluster_files_by_schema", "find_fk_candidates", "generate_corpus_report"],
        {
            **base,
            "include_pk_detection":      True,
            "include_clustering":        True,
            "include_fk_detection":      True,
            "drift_severity_threshold":  "medium",
        },
        l2_ids,
        priority=8,
    )
    schema_corr["dag_layer"]       = 3
    schema_corr["fault_tolerance"] = ft_require  # hard dependency for L4/L5

    # 3b — Relationship detection: FK/PK graph, runs in parallel with 3a
    rel_detect = _st(
        task_id, "relationship_detection",
        ["find_fk_candidates", "generate_insights", "statistical_analysis"],
        {
            **base,
            "analysis_type":     "relationship_graph",
            "include_hierarchy": True,
            "min_fk_confidence": 0.7,
        },
        l2_ids,
        priority=8,
    )
    rel_detect["dag_layer"]       = 3
    rel_detect["fault_tolerance"] = ft_skip   # non-blocking; report degrades gracefully

    # ── Layer 4: Data quality evaluation (cross-file + within-file) ───────
    dq_eval = _st(
        task_id, "data_quality_scan",
        ["monitor_data_quality", "detect_anomalies", "cross_file_quality"],
        {
            **base,
            "cross_file":                   True,
            "within_file":                  True,
            "check_referential_integrity":  True,
            "check_duplicates":             True,
            "check_completeness":           True,
        },
        [schema_corr["id"], rel_detect["id"], sem_profile["id"]],
        priority=7,
    )
    dq_eval["dag_layer"]       = 4
    dq_eval["fault_tolerance"] = ft_require  # DQ result is required for readiness score

    # ── Layer 5: Schema intelligence / entity inference ───────────────────
    entity_inf = _st(
        task_id, "schema_intelligence",
        ["correlate_schemas", "generate_insights", "statistical_analysis"],
        {
            **base,
            "analysis_type":       "entity_inference",
            "entity_types":        ["Part", "BOM", "Supplier",
                                    "Document", "ECO", "Revision"],
            "use_schema_clusters": True,
            "use_fk_graph":        True,
            # Wire in semantic insights from DataProfilerAgent (Layer 2.5)
            "semantic_profile_task_id": sem_profile["id"],
        },
        [schema_corr["id"], rel_detect["id"], dq_eval["id"], sem_profile["id"]],
        priority=7,
    )
    entity_inf["dag_layer"]       = 5
    entity_inf["fault_tolerance"] = ft_skip   # enrichment only; report still valid without it

    # ── Layer 6: Report generation ────────────────────────────────────────
    report = _st(
        task_id, "report_generation",
        ["generate_plm_report", "evaluate_dynamic_conditions"],
        {
            **base,
            "capability":                    "generate_plm_report",
            "trigger_reprofiling":           True,
            "route_unknown_types":           True,
            "prioritize_quality_if_below_threshold": True,
            "dq_threshold":                  70.0,
            "max_drift_files_for_reprofiling": 30,
            "sample_rows":                   sample_rows,
        },
        [entity_inf["id"]],
        priority=9,
    )
    report["dag_layer"]       = 6
    report["fault_tolerance"] = ft_require  # final output — must succeed

    return [*l1_tasks, *l2_tasks, sem_profile, schema_corr, rel_detect, dq_eval, entity_inf, report]


def _build_plm_migration_dag(task_id: str, payload: dict) -> List[dict]:
    """PLM Data Migration Director — two routing options:

    Option A (default): Delegate entirely to PLM Director (port 8029).
      Single subtask with capability 'orchestrate_plm_migration'.
      The Director internally runs the 3-wave DAG and returns a
      complete PLMMigrationReport.

    Option B (explicit_dag=True in payload): Emit the full 6-layer
      deep-profiling DAG for use by a generic DAG executor.
    """
    src = _extract_source(payload)

    if not payload.get("explicit_dag"):
        # Option A — single delegation to PLM Director
        t = _st(
            task_id, "plm_migration_orchestration",
            ["orchestrate_plm_migration"],
            {
                **src,
                "include_fk_detection": payload.get("include_fk_detection", True),
                "include_clustering":   payload.get("include_clustering", True),
                "recursive":            payload.get("recursive", True),
                "sample_rows":          payload.get("sample_rows", 500),
                "migration_label":      payload.get("migration_label"),
            },
            priority=9,
        )
        t["dag_layer"] = 1
        return [t]

    # Option B — full 6-layer profiling DAG
    return _build_plm_profiling_dag(task_id, payload)


def _build_semantic_profile_dag(task_id: str, payload: dict) -> List[dict]:
    """
    Standalone semantic profile DAG — implements the LLM TOOL PROMPT:
      Step 1: file_profiling  (if no file_profiles supplied — get raw stats)
      Step 2: semantic_profile (DataProfilerAgent — column semantics + entities + relationships)

    If file_profiles are already in the payload, only Step 2 is emitted.
    """
    src         = _extract_source(payload)
    has_profiles = bool(payload.get("file_profiles"))
    sample_rows  = int(payload.get("sample_rows", 500))
    ft_skip      = {"retry_on_failure": True, "max_retries": 2, "skip_on_max_retries": True}

    tasks: List[dict] = []
    step1_id: Optional[str] = None

    if not has_profiles:
        disc = _st(
            task_id, "file_profiling",
            ["profile_files", "infer_schema"],
            {
                **src,
                "folder_path":   payload.get("folder_path", src.get("source_name", "")),
                "sample_rows":   sample_rows,
                "include_stats": True,
                "include_nulls": True,
            },
            priority=8,
        )
        disc["dag_layer"]       = 1
        disc["fault_tolerance"] = ft_skip
        tasks.append(disc)
        step1_id = disc["id"]

    sem = _st(
        task_id, "semantic_profile",
        ["semantic_profile", "infer_column_semantics", "classify_entities",
         "detect_relationships", "align_schemas"],
        {
            **src,
            "capability":                    "semantic_profile",
            "folder_path":                   payload.get("folder_path", src.get("source_name", "")),
            "file_profiles":                 payload.get("file_profiles", []),
            "column_corpus":                 payload.get("column_corpus", []),
            "entity_inference":              payload.get("entity_inference", {}),
            "min_relationship_similarity":   payload.get("min_relationship_similarity", 0.85),
            "enrich_from_schema_correlator": payload.get("enrich_from_schema_correlator", False),
            "sample_rows":                   sample_rows,
        },
        [step1_id] if step1_id else [],
        priority=9,
    )
    sem["dag_layer"]       = 2 if step1_id else 1
    sem["fault_tolerance"] = ft_skip
    tasks.append(sem)
    return tasks


def _build_reporting_dag(task_id: str, payload: dict) -> List[dict]:
    """Single-task delegation to ReportingAgent for report composition."""
    src = _extract_source(payload)
    t = _st(
        task_id, "report_generation",
        ["generate_plm_report", "evaluate_dynamic_conditions"],
        {
            **src,
            **{k: v for k, v in payload.items() if k not in src},
            "capability": "generate_plm_report",
        },
        priority=9,
    )
    t["dag_layer"] = 1
    return [t]


# Keyword → builder mapping (order matters: more specific first)
_TEMPLATES = [
    # Explicit deep-profiling DAG (batch-aware, 6-layer) — checked first
    (["deep profile", "batch profile", "batch discover", "profiling dag",
      "parallel profile", "large corpus", "200 files", "heterogeneous files"],
     _build_plm_profiling_dag),
    # Report composition — forward to ReportingAgent
    (["generate report", "plm report", "profiling report", "report generation",
      "compile report", "assemble report"],
     _build_reporting_dag),
    # Semantic profiling — LLM Tool Prompt: column semantics + entity classification
    (["semantic profile", "infer column", "infer semantic", "column meaning",
      "entity classification", "classify entity", "column role",
      "detect relationships", "schema alignment", "column similarity"],
     _build_semantic_profile_dag),
    # PLM migration delegation (Option A by default; Option B if explicit_dag=True)
    (["plm", "product lifecycle", "schema correlation", "corpus", "heterogeneous",
      "plm migration", "migration corpus"],
     _build_plm_migration_dag),
    (["migrate", "migration", "schema migration"], _build_migration_dag),
    (["file batch", "bulk process", "batch process"], _build_file_batch_dag),
    (["visualize", "chart", "plot", "graph layout"], _build_visualization_dag),
    (["cypher", "neo4j query", "graph query"], _build_query_dag),
    (["quality", "dq scan", "data quality", "anomaly", "validate"], _build_quality_dag),
    (["discover", "profile files", "file catalog", "infer schema"], _build_discovery_dag),
    (["etl", "pipeline", "load data", "transform"], _build_etl_dag),
    (["analyze", "analysis", "pattern", "trend", "insight"], _build_analysis_dag),
]


class TaskDecomposerAgent(AgentService):
    """Decomposes high-level goals into dependency-ordered subtask DAGs."""

    def __init__(self):
        super().__init__(
            agent_type=AgentType.TASK_DECOMPOSER,
            agent_name="Task Decomposer Agent",
            port=8027,
        )

    def get_capabilities(self) -> List[AgentCapability]:
        return [
            AgentCapability(name="decompose_goal",  description="Decompose a high-level goal into a dependency-ordered subtask DAG"),
            AgentCapability(name="build_task_dag",  description="Produce subtask DAG with capability requirements and dependencies"),
            AgentCapability(name="decompose_task",  description="Break a complex task into atomic executable subtasks"),
        ]

    async def process_task(self, task: AgentTaskRequest) -> Dict[str, Any]:
        logger.info("TaskDecomposer received task %s", task.task_id)

        goal = task.payload.get("goal", task.payload.get("message", ""))
        if not goal:
            return {
                "decomposition_status": "failed",
                "error": "No 'goal' provided in payload",
                "subtasks": [],
            }

        goal_lower = goal.lower()
        builder = None
        matched_template = "default_analysis"

        for keywords, build_fn in _TEMPLATES:
            if any(kw in goal_lower for kw in keywords):
                builder = build_fn
                matched_template = keywords[0]
                break

        if builder is None:
            # Default: single data-analysis task
            builder = _build_analysis_dag
            matched_template = "default_analysis"

        subtasks = builder(task.task_id, task.payload)

        logger.info(
            "Decomposed goal '%s' via template '%s' into %d subtasks",
            goal[:80], matched_template, len(subtasks),
        )

        # Build a layer-grouped structure when subtasks carry dag_layer annotations
        dag_structure: Optional[Dict] = None
        if any("dag_layer" in st for st in subtasks):
            layers: Dict[int, List[str]] = {}
            for st in subtasks:
                layer = st.get("dag_layer", 0)
                layers.setdefault(layer, []).append(st["id"])
            dag_structure = {
                "layer_count":   max(layers.keys()),
                "batch_count":   sum(1 for st in subtasks if st.get("dag_layer") == 1),
                "layers":        {f"layer_{k}": v for k, v in sorted(layers.items())},
                "parallel_groups": [
                    {"layer": k, "task_ids": v, "parallelism": len(v)}
                    for k, v in sorted(layers.items())
                ],
            }

        result: Dict[str, Any] = {
            "decomposition_status": "success",
            "original_goal":        goal,
            "template_used":        matched_template,
            "subtask_count":        len(subtasks),
            "subtasks":             subtasks,
            "execution_order":      [st["id"] for st in subtasks],
        }
        if dag_structure:
            result["dag_structure"] = dag_structure
        return result


# Create singleton and export app
agent = TaskDecomposerAgent()
app = agent.app

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8027)

