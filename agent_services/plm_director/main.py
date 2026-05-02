"""
PLM Data Migration Director
============================
Standalone FastAPI microservice — port 8029.
Registered with MCP Server as AgentType.PLM_DIRECTOR.

Role
----
End-to-end orchestration of PLM corpus migration via a three-wave DAG.
Invokes specialist agents directly over HTTP, tracks every wave in an
execution log, and emits a single machine-readable ``PLMMigrationReport``
that downstream agents (ETL, Quality, Transformation) can consume without
ambiguity.

DAG topology
------------
Wave 1  — parallel, no prior deps:
    [disc]  DataDiscovery    :8026   per-file profiling (row count, columns,
                                     null rates, semantic types)
    [corr]  SchemaCorrelator :8028   cross-file drift, FK candidates,
                                     Jaccard clusters, anomalies

Wave 2  — parallel, after Wave 1 fully completes:
    [qual]  QualityMonitor   :8024   rule-based quality scan using disc result
    [rel]   DataAnalyst      :8020   statistical / relationship insights from
                                     correlator output

Wave 3  — sequential, after Wave 2 fully completes:
    [etl]   ETLOrchestrator  :8021   builds the migration plan incorporating
                                     all Wave-1/2 findings

Output — PLMMigrationReport (full JSON):
    {
      "report_id":              <str>,
      "generated_at":           <ISO-8601>,
      "corpus_spec":            {source_name, folder_path, source_id},
      "corpus_summary":         {file_count, total_size_bytes,
                                  tabular_file_count, file_type_dist},
      "file_profiles":          [ {file, row_count, column_count, ...} ],
      "schema_drift":           [ {column, severity, types, recommendation} ],
      "fk_candidates":          [ {from_file, from_col, to_file, to_col, conf} ],
      "schema_clusters":        [ {cluster_id, files, common_columns} ],
      "anomalies":              [ {type, severity, description, affected_files} ],
      "quality_findings":       { ... },
      "relationship_insights":  { ... },
      "migration_plan":         { ... },
      "recommendations": {
          "etl":            [ ... ],
          "quality":        [ ... ],
          "transformation": [ ... ],
      },
      "dag_execution_log": {
          "wave_1": { agents, started_at, completed_at, duration_s, status },
          "wave_2": { ... },
          "wave_3": { ... },
      },
    }

Endpoints
---------
POST /execute           — standard AgentService envelope
POST /orchestrate       — direct PLM invocation (richer response, no envelope)
GET  /health            — inherited liveness probe
GET  /info              — inherited capability listing
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

env_path = Path(__file__).resolve().parent.parent.parent / "python_backend" / ".env"
load_dotenv(dotenv_path=env_path)

from agent_services.base.agent_service import AgentService
from agent_services.base.models import AgentCapability, AgentTaskRequest, AgentType

logger = logging.getLogger(__name__)

# ── Service URLs (overridable via env) ────────────────────────────────────────
BACKEND_URL = os.getenv("GRAPH_TRACE_BACKEND_URL", "http://localhost:8011")
_AGENT_URLS: Dict[str, str] = {
    "data_discovery":   os.getenv("DATA_DISCOVERY_URL",   "http://127.0.0.1:8026"),
    "schema_correlator": os.getenv("SCHEMA_CORRELATOR_URL", "http://127.0.0.1:8028"),
    "quality_monitor":  os.getenv("QUALITY_MONITOR_URL",  "http://127.0.0.1:8024"),
    "data_analyst":     os.getenv("DATA_ANALYST_URL",     "http://127.0.0.1:8020"),
    "etl_orchestrator": os.getenv("ETL_ORCHESTRATOR_URL", "http://127.0.0.1:8021"),
}

# Per-wave HTTP timeout (seconds).  Large corpora can take several minutes.
_WAVE_TIMEOUT = float(os.getenv("PLM_WAVE_TIMEOUT_S", "300"))


# ── Request / Response models ─────────────────────────────────────────────────

class PLMOrchestrateRequest(BaseModel):
    """Direct /orchestrate endpoint body."""
    source_id:    Optional[str] = None
    source_name:  Optional[str] = None
    folder_path:  Optional[str] = None
    recursive:    bool = True
    sample_rows:  int = Field(default=500, ge=1, le=10_000)
    include_fk_detection: bool = True
    include_clustering:   bool = True
    # Optional label for auditing
    migration_label: Optional[str] = None


class PLMMigrationReport(BaseModel):
    """Structured output — machine-readable (INTENT PROMPT contract)."""
    report_id:                  str
    generated_at:               str
    migration_label:            Optional[str]
    corpus_spec:                Dict[str, Any]
    # Renamed + expanded from corpus_summary
    dataset_summary:            Dict[str, Any]
    file_profiles:              List[Dict[str, Any]]
    schema_drift:               List[Dict[str, Any]]
    schema_clusters:            List[Dict[str, Any]]
    # PK candidates per file (NEW)
    key_candidates:             List[Dict[str, Any]]
    # Merged FK + relationship graph (NEW)
    relationships:              Dict[str, Any]
    anomalies:                  List[Dict[str, Any]]
    # Dedicated DQ summary (NEW)
    data_quality_summary:       Dict[str, Any]
    # Readiness score 0–100 with grade (NEW)
    migration_readiness_score:  Dict[str, Any]
    migration_plan:             Dict[str, Any]
    # Renamed + restructured from recommendations (NEW)
    recommended_agent_actions:  List[Dict[str, Any]]
    dag_execution_log:          Dict[str, Any]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _now_iso() -> str:
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"


def _make_task_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


async def _invoke_agent(
    agent_key: str,
    task_type: str,
    payload: Dict[str, Any],
    timeout: float = _WAVE_TIMEOUT,
) -> Dict[str, Any]:
    """
    POST to an agent's /execute endpoint.
    Returns the agent's ``result`` dict on success, or an error envelope.
    """
    url = _AGENT_URLS.get(agent_key, "")
    if not url:
        return {"status": "error", "error": f"No URL configured for agent '{agent_key}'"}

    body = {
        "task_id": _make_task_id(agent_key),
        "task_type": task_type,
        "payload": payload,
        "priority": 9,
    }
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(f"{url}/execute", json=body)
            resp.raise_for_status()
            data = resp.json()
            result = data.get("result", data)
            if "error" in data and data.get("status") == "failed":
                return {"status": "error", "error": data.get("error", "unknown")}
            return result
    except httpx.TimeoutException:
        logger.warning("Agent '%s' timed out after %.0fs", agent_key, timeout)
        return {"status": "error", "error": f"Timeout after {timeout:.0f}s"}
    except httpx.HTTPStatusError as exc:
        logger.warning("Agent '%s' returned HTTP %s", agent_key, exc.response.status_code)
        return {"status": "error", "error": f"HTTP {exc.response.status_code}"}
    except Exception as exc:
        logger.warning("Agent '%s' invocation failed: %s", agent_key, exc)
        return {"status": "error", "error": str(exc)}


async def _resolve_folder_path(
    source_id: Optional[str],
    source_name: Optional[str],
    folder_path: Optional[str],
) -> str:
    """
    Resolve a filesystem path from the various caller-supplied identifiers.
    Priority: folder_path > source_id > source_name.
    Falls back to backend API for source_id / source_name resolution.
    """
    if folder_path:
        return folder_path

    # Try backend data-source resolution
    for param_key, param_val in [("id", source_id), ("name", source_name)]:
        if not param_val:
            continue
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{BACKEND_URL}/api/datasources",
                    params={param_key: param_val},
                )
                if resp.status_code == 200:
                    sources = resp.json()
                    if isinstance(sources, list) and sources:
                        fp = sources[0].get("connection_string") or sources[0].get("folder_path") or ""
                        if fp:
                            return fp
                    elif isinstance(sources, dict):
                        fp = sources.get("connection_string") or sources.get("folder_path") or ""
                        if fp:
                            return fp
        except Exception as exc:
            logger.debug("Backend source resolution failed: %s", exc)

    return ""


def _wave_log_entry(
    agents: List[str],
    started_at: str,
    completed_at: str,
    results: Dict[str, Dict],
) -> Dict[str, Any]:
    """Build a structured wave execution log entry."""
    statuses = {a: ("ok" if r.get("status") != "error" else "error") for a, r in results.items()}
    errors = {a: r["error"] for a, r in results.items() if r.get("status") == "error"}
    started = datetime.fromisoformat(started_at.rstrip("Z"))
    completed = datetime.fromisoformat(completed_at.rstrip("Z"))
    return {
        "agents": agents,
        "started_at": started_at,
        "completed_at": completed_at,
        "duration_s": round((completed - started).total_seconds(), 2),
        "agent_status": statuses,
        "errors": errors,
        "overall_status": "failed" if errors else "ok",
    }


def _summarise_discovery(disc_result: Dict[str, Any]) -> Dict[str, Any]:
    """Extract a compact corpus_summary from DataDiscovery output."""
    profiles: List[Dict] = disc_result.get("profiles", [])
    if not profiles:
        # Fallback: DataDiscovery may return a flat file_count + totals
        return {
            "file_count": disc_result.get("file_count", 0),
            "total_size_bytes": disc_result.get("total_size_bytes", 0),
            "tabular_file_count": disc_result.get("tabular_file_count", 0),
            "file_type_distribution": disc_result.get("file_type_distribution", {}),
            "total_row_count": disc_result.get("total_row_count", 0),
            "avg_null_rate": disc_result.get("avg_null_rate", None),
            "parse_failure_count": disc_result.get("parse_failure_count", 0),
        }

    total_size = sum(p.get("size_bytes", 0) for p in profiles)
    total_rows = sum(p.get("row_count") or 0 for p in profiles)
    type_dist: Dict[str, int] = {}
    tabular_count = 0
    parse_failures = 0
    null_rates = []
    for p in profiles:
        ft = p.get("file_type", "other")
        type_dist[ft] = type_dist.get(ft, 0) + 1
        if ft in ("csv", "json", "xlsx", "parquet", "tsv"):
            tabular_count += 1
        if not p.get("parse_ok", True):
            parse_failures += 1
        nr = p.get("null_rate")
        if nr is not None:
            null_rates.append(nr)
    avg_null_rate = round(sum(null_rates) / len(null_rates), 4) if null_rates else None
    return {
        "file_count": len(profiles),
        "total_size_bytes": total_size,
        "tabular_file_count": tabular_count,
        "file_type_distribution": type_dist,
        "total_row_count": total_rows,
        "avg_null_rate": avg_null_rate,
        "parse_failure_count": parse_failures,
    }


def _merge_recommendations(
    corr_result: Dict[str, Any],
    qual_result: Dict[str, Any],
    etl_result: Dict[str, Any],
) -> Dict[str, List[Any]]:
    """
    Merge recommendation lists from multiple agents into a unified structure.
    Each source agent's recommendations are labelled by origin so downstream
    agents can trace provenance.
    """
    recs: Dict[str, List[Any]] = {"etl": [], "quality": [], "transformation": []}

    # From SchemaCorrelator
    corr_recs = corr_result.get("recommendations", {})
    for bucket, items in corr_recs.items():
        if bucket in recs and isinstance(items, list):
            for item in items:
                recs[bucket].append({**item, "_source": "schema_correlator"} if isinstance(item, dict) else {"text": item, "_source": "schema_correlator"})

    # From QualityMonitor — quality bucket
    qual_recs = qual_result.get("recommendations", [])
    if isinstance(qual_recs, list):
        for item in qual_recs:
            recs["quality"].append({**item, "_source": "quality_monitor"} if isinstance(item, dict) else {"text": item, "_source": "quality_monitor"})

    # From ETLOrchestrator — etl bucket
    etl_recs = etl_result.get("recommendations", [])
    if isinstance(etl_recs, list):
        for item in etl_recs:
            recs["etl"].append({**item, "_source": "etl_orchestrator"} if isinstance(item, dict) else {"text": item, "_source": "etl_orchestrator"})

    # Schema-drift driven transformation recommendations (synthesised here)
    schema_drift = corr_result.get("schema_drift", [])
    for drift in schema_drift[:20]:           # cap for readability
        if drift.get("severity") in ("high", "medium"):
            recs["transformation"].append({
                "type": "type_coercion",
                "column": drift.get("column_name"),
                "from_types": list(drift.get("type_distribution", {}).keys()),
                "to_type": drift.get("recommended_target_type", "VARCHAR(255)"),
                "affected_files": drift.get("occurrences_across_files", 0),
                "severity": drift.get("severity"),
                "recommendation": drift.get("recommendation", ""),
                "_source": "schema_correlator/drift",
            })

    return recs


def _build_fallback_migration_plan(
    corpus_summary: Dict[str, Any],
    schema_drift: List[Dict],
    fk_candidates: List[Dict],
    schema_clusters: List[Dict],
) -> Dict[str, Any]:
    """
    Generate a baseline migration plan from structural analysis alone,
    used when ETLOrchestrator is unavailable.
    """
    drift_high = [d for d in schema_drift if d.get("severity") == "high"]
    return {
        "plan_type": "structural_baseline",
        "status": "synthesised_without_etl_agent",
        "phases": [
            {
                "phase": 1,
                "name": "Pre-migration schema standardisation",
                "actions": [
                    {"action": "coerce_type", "column": d["column_name"],
                     "target_type": d.get("recommended_target_type", "VARCHAR(255)"),
                     "severity": "high", "affected_files": d.get("occurrences_across_files", "?")}
                    for d in drift_high[:15]
                ],
            },
            {
                "phase": 2,
                "name": "Parallel file ingestion by schema cluster",
                "actions": [
                    {"action": "ingest_cluster", "cluster_id": cl.get("cluster_id"),
                     "label": cl.get("label", f"Cluster {cl.get('cluster_id')}"),
                     "files": cl.get("files", [])[:10],
                     "file_count": cl.get("file_count", len(cl.get("files", [])))}
                    for cl in schema_clusters[:10]
                ],
            },
            {
                "phase": 3,
                "name": "FK relationship wiring",
                "actions": [
                    {"action": "create_fk",
                     "from": f"{c.get('from_file')}.{c.get('from_column')}",
                     "to": f"{c.get('to_file')}.{c.get('to_column')}",
                     "confidence": c.get("confidence")}
                    for c in fk_candidates[:20]
                ],
            },
        ],
        "estimated_files": corpus_summary.get("file_count", 0),
        "estimated_rows": corpus_summary.get("total_row_count", 0),
    }


# ── New report builder helpers ────────────────────────────────────────────────

_KNOWN_TABULAR_EXTS: set = {
    ".csv", ".tsv", ".json", ".jsonl", ".xlsx", ".xls", ".parquet",
    ".orc", ".avro", ".feather",
}


def _build_dataset_summary(
    corpus_summary: Dict[str, Any],
    file_profiles: List[Dict[str, Any]],
    corr_result: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Expand corpus_summary into the canonical dataset_summary output field.
    Adds total_column_count, unique_column_names, most_common_columns, and
    novel_file_types (extensions not in the known tabular/format set).
    """
    col_corpus = corr_result.get("column_corpus", [])
    total_col_count = sum(p.get("column_count", 0) for p in file_profiles)
    unique_col_names = len(col_corpus)
    most_common = sorted(col_corpus, key=lambda c: c.get("occurrences", 0), reverse=True)[:10]
    most_common_cols = [
        {"name": c.get("column_name") or c.get("canonical_name", ""), "occurrences": c.get("occurrences", 0)}
        for c in most_common
    ]

    # Detect novel extensions from actual file profile names
    discovered_exts: set = set()
    for p in file_profiles:
        name = p.get("name") or p.get("file", "")
        if "." in name:
            discovered_exts.add("." + name.rsplit(".", 1)[-1].lower())

    novel = sorted(discovered_exts - _KNOWN_TABULAR_EXTS)

    return {
        **corpus_summary,
        "total_column_count":  total_col_count,
        "unique_column_names": unique_col_names,
        "most_common_columns": most_common_cols,
        "novel_file_types":    novel,
        "dynamic_adaptation":  len(novel) > 0,
    }


def _compute_data_quality_summary(
    quality_findings: Dict[str, Any],
    file_profiles: List[Dict[str, Any]],
    anomalies: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Extract a structured DQ summary from QualityMonitor findings + anomaly list.
    """
    empty_files      = [a["file"] for a in anomalies if a.get("anomaly_type") == "empty_file"]
    high_null_files  = [a["file"] for a in anomalies if a.get("anomaly_type") == "high_null_rate"]
    no_schema_files  = [a["file"] for a in anomalies if a.get("anomaly_type") == "no_schema"]
    parse_fail_files = list(dict.fromkeys(empty_files + no_schema_files))

    null_rates = [p.get("null_rate", 0.0) for p in file_profiles if p.get("null_rate") is not None]
    avg_missing = round(sum(null_rates) / len(null_rates), 4) if null_rates else 0.0

    qf_issues  = quality_findings.get("issues") or quality_findings.get("findings") or []
    ri_issues  = [i for i in qf_issues if "referential" in str(i).lower() or "fk" in str(i).lower()]
    rule_fails = quality_findings.get("rule_failures", 0) or len(qf_issues)

    dq_score = 100.0
    dq_score -= min(len(empty_files)    * 5, 25)
    dq_score -= min(len(high_null_files) * 3, 15)
    dq_score -= min(len(parse_fail_files) * 2, 10)
    if quality_findings.get("status") == "error":
        dq_score -= 20
    dq_score = max(0.0, round(dq_score, 1))

    return {
        "overall_dq_score":              dq_score,
        "missing_value_rate":            avg_missing,
        "duplicate_file_count":          quality_findings.get("duplicate_count", 0),
        "referential_integrity_issues":  len(ri_issues),
        "high_risk_files":               sorted(set(empty_files + high_null_files))[:20],
        "dq_rule_failures":              rule_fails,
        "parse_failure_files":           parse_fail_files[:20],
    }


def _build_relationships(
    fk_candidates: List[Dict[str, Any]],
    rel_result: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Merge FK candidates from SchemaCorrelator with DataAnalyst relationship
    insights into a single unified relationships view.
    """
    cross_links      = rel_result.get("cross_file_links") or rel_result.get("relationships") or []
    entity_hierarchy = rel_result.get("entity_hierarchy") or rel_result.get("hierarchy") or []
    high_conf        = [fk for fk in fk_candidates if fk.get("confidence", 0) >= 0.85]

    return {
        "fk_relationships":        fk_candidates,
        "cross_file_links":        cross_links,
        "entity_hierarchy":        entity_hierarchy,
        "relationship_count":      len(fk_candidates) + len(cross_links),
        "high_confidence_count":   len(high_conf),
        "has_referential_structure": len(fk_candidates) > 0,
    }


def _compute_migration_readiness_score(
    corpus_summary: Dict[str, Any],
    schema_drift: List[Dict[str, Any]],
    anomalies: List[Dict[str, Any]],
    quality_findings: Dict[str, Any],
    fk_candidates: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Compute a migration readiness score 0–100 from corpus analysis.

    Deductions:
      High-severity drift   : -5 per issue  (max -30)
      Medium-severity drift : -2 per issue  (max -10)
      Empty files           : -3 per file   (max -15)
      High-null-rate files  : -2 per file   (max -10)
      Parse failures        : -2 per file   (max -10)
      QualityMonitor error  : -15 flat

    Grade: A ≥ 90, B ≥ 75, C ≥ 60, D ≥ 45, F < 45
    """
    high_drift   = [d for d in schema_drift if d.get("severity") == "high"]
    medium_drift = [d for d in schema_drift if d.get("severity") == "medium"]
    empty_files  = [a for a in anomalies if a.get("anomaly_type") == "empty_file"]
    high_null    = [a for a in anomalies if a.get("anomaly_type") == "high_null_rate"]
    no_schema    = [a for a in anomalies if a.get("anomaly_type") == "no_schema"]

    d_high_drift   = min(len(high_drift)   * 5, 30)
    d_med_drift    = min(len(medium_drift)  * 2, 10)
    d_empty        = min(len(empty_files)   * 3, 15)
    d_null         = min(len(high_null)     * 2, 10)
    d_parse        = min((len(no_schema) + corpus_summary.get("parse_failure_count", 0)) * 2, 10)
    d_qual         = 15 if quality_findings.get("status") == "error" else 0

    score = max(0, 100 - (d_high_drift + d_med_drift + d_empty + d_null + d_parse + d_qual))
    grade = "A" if score >= 90 else "B" if score >= 75 else "C" if score >= 60 else "D" if score >= 45 else "F"

    blockers: List[str] = []
    if empty_files:
        blockers.append(f"{len(empty_files)} empty file(s) will produce zero rows during migration")
    if high_drift:
        blockers.append(f"{len(high_drift)} column(s) with high-severity type drift require normalisation")
    if d_qual:
        blockers.append("QualityMonitor agent reported an error — manual review required")

    return {
        "score": score,
        "grade": grade,
        "breakdown": {
            "high_drift_deduction":      d_high_drift,
            "medium_drift_deduction":    d_med_drift,
            "empty_file_deduction":      d_empty,
            "high_null_deduction":       d_null,
            "parse_failure_deduction":   d_parse,
            "quality_monitor_deduction": d_qual,
            "fk_candidate_count":        len(fk_candidates),
        },
        "blockers":             blockers,
        "ready_for_migration":  score >= 60,
    }


_PRIORITY_ORDER: Dict[str, int] = {"critical": 0, "high": 1, "medium": 2, "low": 3}


def _build_recommended_agent_actions(
    recommendations: Dict[str, List[Any]],
    readiness_score: Dict[str, Any],
    data_quality_summary: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """
    Flatten and prioritise all recommendations into a canonical action list.
    Each entry carries: action_id, agent, action_type, priority,
    description, affected_files, parameters, depends_on.
    Blockers from the readiness score are prepended as critical entries.
    """
    _bucket_agent = {
        "etl":            "etl_orchestrator",
        "quality":        "quality_monitor",
        "transformation": "schema_correlator",
    }

    actions: List[Dict[str, Any]] = []
    counter = 0

    for bucket, items in recommendations.items():
        default_agent = _bucket_agent.get(bucket, bucket)
        for item in items:
            if not isinstance(item, dict):
                continue
            counter += 1
            aff = item.get("focus_files") or item.get("files") or []
            if isinstance(item.get("affected_files"), dict):
                aff = list(item["affected_files"].keys())
            elif isinstance(item.get("affected_files"), list):
                aff = item["affected_files"]
            actions.append({
                "action_id":    f"action_{counter:04d}",
                "agent":        item.get("_source", default_agent).split("/")[0],
                "action_type":  item.get("action") or item.get("type") or bucket,
                "priority":     item.get("priority", "medium"),
                "description":  item.get("rationale") or item.get("recommendation") or item.get("text", ""),
                "affected_files": aff,
                "parameters":   {k: v for k, v in item.items()
                                 if k not in ("action", "type", "priority", "rationale",
                                              "recommendation", "_source", "text",
                                              "focus_files", "files", "affected_files")},
                "depends_on":   [],
            })

    # Prepend critical blocker actions
    for blocker in readiness_score.get("blockers", []):
        counter += 1
        actions.append({
            "action_id":    f"action_{counter:04d}",
            "agent":        "plm_director",
            "action_type":  "resolve_blocker",
            "priority":     "critical",
            "description":  blocker,
            "affected_files": [],
            "parameters":   {},
            "depends_on":   [],
        })

    # Add a full DQ audit action if the overall DQ score is below 70
    dq_score = data_quality_summary.get("overall_dq_score", 100)
    if dq_score < 70:
        counter += 1
        high_risk = data_quality_summary.get("high_risk_files", [])
        actions.append({
            "action_id":    f"action_{counter:04d}",
            "agent":        "quality_monitor",
            "action_type":  "full_dq_audit",
            "priority":     "high" if dq_score >= 50 else "critical",
            "description":  (
                f"Overall DQ score is {dq_score:.0f}/100 — a full data quality audit "
                f"is recommended before proceeding with migration"
            ),
            "affected_files": high_risk[:10],
            "parameters":   {"dq_score": dq_score, "focus_files": high_risk[:10]},
            "depends_on":   [],
        })

    actions.sort(key=lambda a: _PRIORITY_ORDER.get(a.get("priority", "low"), 3))
    return actions


# ── Core orchestration ────────────────────────────────────────────────────────

async def _run_plm_dag(
    request: PLMOrchestrateRequest,
    folder_path: str,
) -> PLMMigrationReport:
    """
    Execute the three-wave PLM migration DAG and return a PLMMigrationReport.
    Every wave is timed and logged; agent failures are captured without
    aborting the pipeline — later waves receive whatever earlier waves produced.
    """
    report_id = _make_task_id("plm_report")
    source_spec: Dict[str, Any] = {
        "source_id":    request.source_id,
        "source_name":  request.source_name,
        "folder_path":  folder_path,
    }

    wave_log: Dict[str, Any] = {}

    # ── Shared payload base ───────────────────────────────────────────────────
    base_payload: Dict[str, Any] = {
        "folder_path":         folder_path,
        "source_name":         request.source_name or "",
        "source_id":           request.source_id or "",
        "recursive":           request.recursive,
        "sample_rows":         request.sample_rows,
        "include_profiling":   True,
        "include_fk_detection": request.include_fk_detection,
        "include_clustering":   request.include_clustering,
    }

    # ═══════════════════════════════════════════════════════════════════════
    # WAVE 1 — DataDiscovery ‖ SchemaCorrelator (parallel)
    # ═══════════════════════════════════════════════════════════════════════
    logger.info("[PLM Director] Wave 1 starting — DataDiscovery ‖ SchemaCorrelator")
    w1_start = _now_iso()

    disc_task = _invoke_agent(
        "data_discovery", "profile_files",
        {**base_payload, "capability": "profile_files"},
    )
    corr_task = _invoke_agent(
        "schema_correlator", "schema_correlation",
        {**base_payload,
         "capability": "generate_corpus_report",
         "include_fk_detection": request.include_fk_detection,
         "include_clustering":   request.include_clustering},
    )

    disc_result, corr_result = await asyncio.gather(disc_task, corr_task)

    w1_end = _now_iso()
    wave_log["wave_1"] = _wave_log_entry(
        ["data_discovery", "schema_correlator"],
        w1_start, w1_end,
        {"data_discovery": disc_result, "schema_correlator": corr_result},
    )
    logger.info("[PLM Director] Wave 1 done — status: %s", wave_log["wave_1"]["overall_status"])

    # Extract Wave-1 artifacts ──────────────────────────────────────────────
    file_profiles: List[Dict] = (
        disc_result.get("profiles") or
        disc_result.get("file_profiles") or
        []
    )
    corpus_summary = _summarise_discovery(disc_result)

    schema_drift:    List[Dict] = corr_result.get("schema_drift",    [])
    fk_candidates:   List[Dict] = corr_result.get("fk_candidates",   [])
    pk_candidates:   List[Dict] = corr_result.get("pk_candidates",   [])
    schema_clusters: List[Dict] = corr_result.get("schema_clusters", [])
    anomalies:       List[Dict] = corr_result.get("anomalies",       [])

    # ═══════════════════════════════════════════════════════════════════════
    # WAVE 1.5 — Selective re-profiling for high-severity drift (conditional)
    # Trigger: ≤30 files affected by high-severity schema drift → re-profile
    # with double sample size to improve type-inference accuracy.
    # ═══════════════════════════════════════════════════════════════════════
    affected_files: List[str] = []
    for drift in schema_drift:
        if drift.get("severity") == "high":
            for file_list in drift.get("files_by_type", {}).values():
                affected_files.extend(file_list)
    affected_files = list(dict.fromkeys(affected_files))   # deduplicate, preserve order

    if 0 < len(affected_files) <= 30:
        logger.info(
            "[PLM Director] Wave 1.5 — selective re-profiling %d high-drift files",
            len(affected_files),
        )
        rerun_result = await _invoke_agent(
            "data_discovery",
            "profile_files",
            {
                **base_payload,
                "capability": "profile_files",
                "file_paths": affected_files,
                "sample_rows": min(request.sample_rows * 2, 2000),
            },
        )
        rerun_profiles: List[Dict] = (
            rerun_result.get("profiles") or rerun_result.get("file_profiles") or []
        )
        if rerun_profiles:
            rerun_map = {p.get("name") or p.get("file", ""): p for p in rerun_profiles}
            file_profiles = [
                rerun_map.get(p.get("name") or p.get("file", ""), p)
                for p in file_profiles
            ]
            existing_names = {p.get("name") or p.get("file", "") for p in file_profiles}
            for p in rerun_profiles:
                pname = p.get("name") or p.get("file", "")
                if pname and pname not in existing_names:
                    file_profiles.append(p)
            logger.info("[PLM Director] Wave 1.5 merged %d re-profiled files", len(rerun_profiles))

        wave_log["wave_1.5"] = {
            "agents":               ["data_discovery"],
            "trigger":              "high_severity_drift",
            "affected_files_count": len(affected_files),
            "re_profiled_count":    len(rerun_profiles) if rerun_profiles else 0,
            "status":               "ok" if rerun_profiles else "skipped",
        }

    # ═══════════════════════════════════════════════════════════════════════
    # WAVE 2 — QualityMonitor ‖ DataAnalyst (parallel, depends Wave 1)
    # ═══════════════════════════════════════════════════════════════════════
    logger.info("[PLM Director] Wave 2 starting — QualityMonitor ‖ DataAnalyst")
    w2_start = _now_iso()

    qual_payload: Dict[str, Any] = {
        **base_payload,
        "capability": "monitor_data_quality",
        # Pass forward the discovery profiles so QualityMonitor can use
        # them without re-scanning the filesystem
        "file_profiles": file_profiles[:200],   # cap to keep payload reasonable
        "corpus_summary": corpus_summary,
    }
    rel_payload: Dict[str, Any] = {
        **base_payload,
        "capability": "statistical_analysis",
        "analysis_type": "plm_corpus",
        "column_corpus":  corr_result.get("column_corpus",  [])[:100],
        "schema_drift":   schema_drift[:50],
        "fk_candidates":  fk_candidates[:50],
        "schema_clusters": schema_clusters[:20],
    }

    qual_task = _invoke_agent("quality_monitor", "data_quality_scan", qual_payload)
    rel_task  = _invoke_agent("data_analyst",    "data_analysis",      rel_payload)

    qual_result, rel_result = await asyncio.gather(qual_task, rel_task)

    w2_end = _now_iso()
    wave_log["wave_2"] = _wave_log_entry(
        ["quality_monitor", "data_analyst"],
        w2_start, w2_end,
        {"quality_monitor": qual_result, "data_analyst": rel_result},
    )
    logger.info("[PLM Director] Wave 2 done — status: %s", wave_log["wave_2"]["overall_status"])

    # ── Build new report fields from Wave 1 & 2 artifacts ─────────────────
    dataset_summary      = _build_dataset_summary(corpus_summary, file_profiles, corr_result)
    data_quality_summary = _compute_data_quality_summary(qual_result, file_profiles, anomalies)
    relationships        = _build_relationships(fk_candidates, rel_result)

    # ═══════════════════════════════════════════════════════════════════════
    # WAVE 3 — ETLOrchestrator (sequential, depends Wave 2)
    # ═══════════════════════════════════════════════════════════════════════
    logger.info("[PLM Director] Wave 3 starting — ETLOrchestrator")
    w3_start = _now_iso()

    etl_payload: Dict[str, Any] = {
        **base_payload,
        "capability": "manage_data_pipelines",
        "action": "build_migration",
        # Structured handoff from Waves 1 & 2
        "corpus_summary":         corpus_summary,
        "schema_drift":           schema_drift[:50],
        "fk_candidates":          fk_candidates[:50],
        "schema_clusters":        schema_clusters[:20],
        "quality_findings":       qual_result,
        "relationship_insights":  rel_result,
    }

    etl_result = await _invoke_agent("etl_orchestrator", "pipeline_orchestration", etl_payload)

    w3_end = _now_iso()
    wave_log["wave_3"] = _wave_log_entry(
        ["etl_orchestrator"],
        w3_start, w3_end,
        {"etl_orchestrator": etl_result},
    )
    logger.info("[PLM Director] Wave 3 done — status: %s", wave_log["wave_3"]["overall_status"])

    # ── Assemble migration plan ───────────────────────────────────────────────
    if etl_result.get("status") == "error":
        migration_plan = _build_fallback_migration_plan(
            corpus_summary, schema_drift, fk_candidates, schema_clusters,
        )
    else:
        migration_plan = {
            "plan_type": "etl_agent",
            **{k: v for k, v in etl_result.items() if k not in ("status",)},
        }

    # ── Build readiness score and recommended actions ─────────────────────────
    raw_recommendations = _merge_recommendations(corr_result, qual_result, etl_result)
    readiness_score     = _compute_migration_readiness_score(
        corpus_summary, schema_drift, anomalies, qual_result, fk_candidates,
    )
    recommended_agent_actions = _build_recommended_agent_actions(
        raw_recommendations, readiness_score, data_quality_summary,
    )

    return PLMMigrationReport(
        report_id=report_id,
        generated_at=_now_iso(),
        migration_label=request.migration_label,
        corpus_spec=source_spec,
        dataset_summary=dataset_summary,
        file_profiles=file_profiles,
        schema_drift=schema_drift,
        schema_clusters=schema_clusters,
        key_candidates=pk_candidates,
        relationships=relationships,
        anomalies=anomalies,
        data_quality_summary=data_quality_summary,
        migration_readiness_score=readiness_score,
        migration_plan=migration_plan,
        recommended_agent_actions=recommended_agent_actions,
        dag_execution_log=wave_log,
    )


# ── Agent service class ───────────────────────────────────────────────────────

class PLMDirectorAgent(AgentService):
    """
    PLM Data Migration Director — orchestrates a multi-wave DAG over
    specialist agents and emits a complete, structured PLMMigrationReport.
    """

    def __init__(self) -> None:
        super().__init__(
            agent_type=AgentType.PLM_DIRECTOR,
            agent_name="PLM Data Migration Director",
            port=8029,
        )
        # Register the dedicated /orchestrate endpoint
        self._register_orchestrate_route()

    # ── Capabilities ──────────────────────────────────────────────────────────

    def get_capabilities(self) -> List[AgentCapability]:
        return [
            AgentCapability(
                name="orchestrate_plm_migration",
                description=(
                    "Run the full three-wave PLM corpus migration DAG: "
                    "DataDiscovery ‖ SchemaCorrelator → QualityMonitor ‖ DataAnalyst → ETLOrchestrator. "
                    "Returns a structured PLMMigrationReport."
                ),
            ),
            AgentCapability(
                name="generate_migration_plan",
                description=(
                    "Build a phased migration plan from schema drift, FK candidates, "
                    "and schema cluster analysis."
                ),
            ),
            AgentCapability(
                name="aggregate_corpus_report",
                description=(
                    "Merge per-file profiles (DataDiscovery) with cross-file corpus "
                    "analysis (SchemaCorrelator) into a unified report."
                ),
            ),
            AgentCapability(
                name="detect_cross_file_patterns",
                description=(
                    "Identify schema drift, FK relationships, and schema clusters "
                    "across 200+ heterogeneous PLM files."
                ),
            ),
        ]

    # ── Standard /execute route ───────────────────────────────────────────────

    async def process_task(self, task: AgentTaskRequest) -> Dict[str, Any]:
        """
        Handles calls routed via MCP Orchestrator's standard /execute envelope.
        Payload keys mirror PLMOrchestrateRequest fields.
        """
        p = task.payload
        req = PLMOrchestrateRequest(
            source_id=p.get("source_id"),
            source_name=p.get("source_name"),
            folder_path=p.get("folder_path"),
            recursive=bool(p.get("recursive", True)),
            sample_rows=int(p.get("sample_rows", 500)),
            include_fk_detection=bool(p.get("include_fk_detection", True)),
            include_clustering=bool(p.get("include_clustering", True)),
            migration_label=p.get("migration_label"),
        )

        folder_path = await _resolve_folder_path(
            req.source_id, req.source_name, req.folder_path
        )
        if not folder_path:
            return {
                "status": "error",
                "error": (
                    "Cannot resolve folder path — provide 'folder_path', "
                    "'source_id', or 'source_name' in payload."
                ),
            }

        report = await _run_plm_dag(req, folder_path)
        return report.model_dump()

    # ── Dedicated /orchestrate endpoint ──────────────────────────────────────

    def _register_orchestrate_route(self) -> None:
        """Add POST /orchestrate to the inherited FastAPI app."""

        @self.app.post(
            "/orchestrate",
            summary="Run full PLM migration DAG",
            response_model=PLMMigrationReport,
        )
        async def orchestrate(req: PLMOrchestrateRequest) -> JSONResponse:
            if not any([req.source_id, req.source_name, req.folder_path]):
                return JSONResponse(
                    status_code=422,
                    content={"error": "At least one of source_id, source_name, or folder_path is required."},
                )

            folder_path = await _resolve_folder_path(
                req.source_id, req.source_name, req.folder_path
            )
            if not folder_path:
                return JSONResponse(
                    status_code=422,
                    content={"error": "Cannot resolve corpus folder path from provided identifiers."},
                )

            report = await _run_plm_dag(req, folder_path)
            return JSONResponse(content=report.model_dump())

        @self.app.get(
            "/dag-topology",
            summary="Return the PLM DAG topology (static description)",
        )
        async def dag_topology() -> JSONResponse:
            return JSONResponse(content={
                "dag_id": "plm_migration_dag",
                "description": "Multi-wave parallel DAG for PLM corpus migration",
                "waves": [
                    {
                        "wave": 1,
                        "execution": "parallel",
                        "depends_on": [],
                        "agents": [
                            {
                                "agent": "data_discovery",
                                "url": _AGENT_URLS["data_discovery"],
                                "task_type": "profile_files",
                                "purpose": "Per-file profiling: row counts, column schema, null rates",
                            },
                            {
                                "agent": "schema_correlator",
                                "url": _AGENT_URLS["schema_correlator"],
                                "task_type": "schema_correlation",
                                "purpose": "Cross-file schema drift, FK candidates, Jaccard clusters",
                            },
                        ],
                    },
                    {
                        "wave": 2,
                        "execution": "parallel",
                        "depends_on": ["wave_1"],
                        "agents": [
                            {
                                "agent": "quality_monitor",
                                "url": _AGENT_URLS["quality_monitor"],
                                "task_type": "data_quality_scan",
                                "purpose": "Rule-based quality scan fed by Wave-1 profiles",
                            },
                            {
                                "agent": "data_analyst",
                                "url": _AGENT_URLS["data_analyst"],
                                "task_type": "data_analysis",
                                "purpose": "Statistical & relationship insights from correlator output",
                            },
                        ],
                    },
                    {
                        "wave": 3,
                        "execution": "sequential",
                        "depends_on": ["wave_1", "wave_2"],
                        "agents": [
                            {
                                "agent": "etl_orchestrator",
                                "url": _AGENT_URLS["etl_orchestrator"],
                                "task_type": "pipeline_orchestration",
                                "purpose": "Build migration plan from all prior wave findings",
                            },
                        ],
                    },
                ],
            })

    # ── Lifespan ──────────────────────────────────────────────────────────────

    @asynccontextmanager
    async def _lifespan(self, _app: FastAPI):
        logger.info(
            "[PLM Director] Starting on port 8029 — "
            "agents: %s",
            list(_AGENT_URLS.keys()),
        )
        async with super()._lifespan(_app):
            yield
        logger.info("[PLM Director] Shutdown complete.")


# ── Module-level singleton ────────────────────────────────────────────────────
agent = PLMDirectorAgent()
app   = agent.app

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8029, log_level="info")
