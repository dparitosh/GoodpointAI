"""
PLM Data Profiling Reporting Agent
====================================
Standalone FastAPI microservice — port 8030.
Registered with MCP Server as AgentType.REPORTING_AGENT.

Role
----
Consumes aggregated profiling artifacts produced by the PLM DAG
(DataDiscovery, SchemaCorrelator, QualityMonitor, DataAnalyst,
ETLOrchestrator) and emits a single, **strict-JSON** PLM Data Profiling
Report aligned to the INTENT PROMPT output contract.

Additionally evaluates four dynamic scenarios *while* assembling the
report, adapting the pipeline without a full restart:

  1. New schema patterns detected
     → Create a new schema cluster; re-evaluate FK relationships.
  2. Schema drift detected
     → Mark affected files; invoke DataDiscovery re-profiling on
       impacted clusters only (capped at ``max_drift_files``).
  3. Unknown file type
     → Route those files to ETLOrchestrator for extraction;
       set a retry-profiling signal in the adaptation log.
  4. Data quality issues exceed threshold
     → Promote QualityMonitor tasks to the front of the action list
       before any ETL work begins.

Endpoints
---------
POST /execute  — standard AgentService envelope
POST /report   — direct invocation (accepts ``GenerateReportRequest``)
GET  /health   — inherited liveness probe
GET  /info     — inherited capability listing
"""

from __future__ import annotations

import logging
import os
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx
from dotenv import load_dotenv
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

env_path = Path(__file__).resolve().parent.parent.parent / "python_backend" / ".env"
load_dotenv(dotenv_path=env_path)

from agent_services.base.agent_service import AgentService
from agent_services.base.models import AgentCapability, AgentTaskRequest, AgentType

logger = logging.getLogger(__name__)

# ── Service URLs (overridable via env) ────────────────────────────────────────

_AGENT_URLS: Dict[str, str] = {
    "data_discovery":    os.getenv("DATA_DISCOVERY_URL",    "http://127.0.0.1:8026"),
    "schema_correlator": os.getenv("SCHEMA_CORRELATOR_URL", "http://127.0.0.1:8028"),
    "quality_monitor":   os.getenv("QUALITY_MONITOR_URL",   "http://127.0.0.1:8024"),
    "data_analyst":      os.getenv("DATA_ANALYST_URL",      "http://127.0.0.1:8020"),
    "etl_orchestrator":  os.getenv("ETL_ORCHESTRATOR_URL",  "http://127.0.0.1:8021"),
    "plm_director":      os.getenv("PLM_DIRECTOR_URL",      "http://127.0.0.1:8029"),
}

_AGENT_TIMEOUT = float(os.getenv("REPORTING_AGENT_TIMEOUT_S", "120"))

# Known tabular / structured file extensions — anything outside is "novel"
_KNOWN_TABULAR_EXTS: set = {
    ".csv", ".tsv", ".json", ".jsonl", ".xlsx", ".xls",
    ".parquet", ".orc", ".avro", ".feather",
}

# FK-candidate column suffixes for dynamic detection
_FK_SUFFIXES: Tuple[str, ...] = (
    "_id", "_fk", "_key", "_ref", "_code", "_no", "_num", "_pk",
)


# ── Pydantic models ────────────────────────────────────────────────────────────

class GenerateReportRequest(BaseModel):
    """Direct /report endpoint body.

    All artifact fields are optional — the agent composites what is supplied
    and generates stub sections for anything missing.
    """
    # Source metadata
    source_name:    Optional[str] = None
    folder_path:    Optional[str] = None
    migration_label: Optional[str] = None

    # Profiling artifacts from upstream agents
    file_profiles:        List[Dict[str, Any]] = Field(default_factory=list)
    schema_drift:         List[Dict[str, Any]] = Field(default_factory=list)
    fk_candidates:        List[Dict[str, Any]] = Field(default_factory=list)
    pk_candidates:        List[Dict[str, Any]] = Field(default_factory=list)
    schema_clusters:      List[Dict[str, Any]] = Field(default_factory=list)
    anomalies:            List[Dict[str, Any]] = Field(default_factory=list)
    quality_findings:     Dict[str, Any]        = Field(default_factory=dict)
    relationship_insights: Dict[str, Any]       = Field(default_factory=dict)
    etl_result:           Dict[str, Any]        = Field(default_factory=dict)
    column_corpus:        List[Dict[str, Any]]  = Field(default_factory=list)
    # LLM Tool Prompt output from DataProfilerAgent (Layer 2.5 in the profiling DAG)
    semantic_insights:    Dict[str, Any]        = Field(default_factory=dict)

    # Dynamic scenario thresholds & flags
    dq_threshold:                         float = 70.0
    max_drift_files_for_reprofiling:      int   = 30
    sample_rows:                          int   = Field(default=1000, ge=1, le=10_000)
    trigger_reprofiling:                  bool  = True
    route_unknown_types:                  bool  = True
    prioritize_quality_if_below_threshold: bool = True


# ── Low-level HTTP helper ─────────────────────────────────────────────────────

async def _invoke_agent(
    agent_key: str,
    task_type: str,
    payload: Dict[str, Any],
    timeout: float = _AGENT_TIMEOUT,
) -> Dict[str, Any]:
    """POST to an agent's /execute endpoint; return result dict or error envelope."""
    url = _AGENT_URLS.get(agent_key, "")
    if not url:
        return {"status": "error", "error": f"No URL configured for '{agent_key}'"}

    body = {
        "task_id":   f"rpt_{uuid.uuid4().hex[:10]}",
        "task_type": task_type,
        "payload":   payload,
        "priority":  8,
    }
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(f"{url}/execute", json=body)
            resp.raise_for_status()
            data = resp.json()
            if data.get("status") == "failed":
                return {"status": "error", "error": data.get("error", "unknown")}
            return data.get("result", data)
    except httpx.TimeoutException:
        logger.warning("Agent '%s' timed out after %.0fs", agent_key, timeout)
        return {"status": "error", "error": f"Timeout after {timeout:.0f}s"}
    except httpx.HTTPStatusError as exc:
        logger.warning("Agent '%s' HTTP %s", agent_key, exc.response.status_code)
        return {"status": "error", "error": f"HTTP {exc.response.status_code}"}
    except Exception as exc:
        logger.warning("Agent '%s' invocation failed: %s", agent_key, exc)
        return {"status": "error", "error": str(exc)}


def _now_iso() -> str:
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"


# ── Pure report-assembly helpers ──────────────────────────────────────────────

def _build_dataset_summary(
    file_profiles: List[Dict[str, Any]],
    column_corpus: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Compute dataset_summary from raw file profiles."""
    total_rows = sum(p.get("row_count") or 0 for p in file_profiles)
    total_size = sum(p.get("size_bytes") or 0 for p in file_profiles)
    total_cols = sum(p.get("column_count") or 0 for p in file_profiles)
    unique_col_names = len({
        (c.get("column_name") or c.get("canonical_name") or c.get("name") or "")
        for c in column_corpus
    })

    type_dist: Dict[str, int] = {}
    discovered_exts: set = set()
    for p in file_profiles:
        ft = p.get("file_type") or ""
        if ft:
            type_dist[ft] = type_dist.get(ft, 0) + 1
        name = p.get("file") or p.get("name") or ""
        if "." in name:
            discovered_exts.add("." + name.rsplit(".", 1)[-1].lower())

    novel_types = sorted(discovered_exts - _KNOWN_TABULAR_EXTS)

    most_common = sorted(
        column_corpus,
        key=lambda c: c.get("occurrences", 0),
        reverse=True,
    )[:10]

    return {
        "total_files":             len(file_profiles),
        "total_rows_estimate":     total_rows,
        "total_size_bytes":        total_size,
        "total_column_count":      total_cols,
        "unique_column_names":     unique_col_names,
        "file_types_distribution": type_dist,
        "most_common_columns": [
            {
                "name":        c.get("column_name") or c.get("canonical_name") or c.get("name", ""),
                "occurrences": c.get("occurrences", 0),
            }
            for c in most_common
        ],
        "novel_file_types":  novel_types,
        "dynamic_adaptation": len(novel_types) > 0,
    }


def _build_data_quality_summary(
    quality_findings: Dict[str, Any],
    file_profiles: List[Dict[str, Any]],
    anomalies: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Compute data_quality_summary from findings + anomalies."""
    empty_files     = [a.get("file", "") for a in anomalies if a.get("anomaly_type") == "empty_file"]
    high_null_files = [a.get("file", "") for a in anomalies if a.get("anomaly_type") == "high_null_rate"]
    no_schema_files = [a.get("file", "") for a in anomalies if a.get("anomaly_type") == "no_schema"]
    duplicate_files = [a.get("file", "") for a in anomalies if a.get("anomaly_type") == "duplicate_schema"]
    parse_fail_files = list(dict.fromkeys(empty_files + no_schema_files))

    null_rates = [p.get("null_rate", 0.0) for p in file_profiles if p.get("null_rate") is not None]
    avg_null = round(sum(null_rates) / len(null_rates), 4) if null_rates else 0.0

    dup_rates = [p.get("duplicate_rate", 0.0) for p in file_profiles if p.get("duplicate_rate") is not None]
    avg_dup = round(sum(dup_rates) / len(dup_rates), 4) if dup_rates else 0.0

    qf_issues  = quality_findings.get("issues") or quality_findings.get("findings") or []
    ri_issues  = [i for i in qf_issues if "referential" in str(i).lower() or "fk" in str(i).lower()]
    inconsistent_naming = [
        a for a in anomalies if a.get("anomaly_type") in ("naming_inconsistency", "mixed_case_columns")
    ]

    dq_score = 100.0
    dq_score -= min(len(empty_files)     * 5,  25)
    dq_score -= min(len(high_null_files) * 3,  15)
    dq_score -= min(len(parse_fail_files) * 2, 10)
    if quality_findings.get("status") == "error":
        dq_score -= 20
    dq_score = max(0.0, round(dq_score, 1))

    return {
        "overall_dq_score":             dq_score,
        "null_rates": {
            "average": avg_null,
            "high_null_files": high_null_files[:20],
        },
        "duplicate_rates": {
            "average": avg_dup,
            "duplicate_file_count": len(duplicate_files),
        },
        "integrity_issues": {
            "referential_integrity_issues": len(ri_issues),
            "inconsistent_naming_files":    [a.get("file", "") for a in inconsistent_naming][:20],
        },
        "high_risk_files":   sorted(set(empty_files + high_null_files))[:20],
        "dq_rule_failures":  quality_findings.get("rule_failures", 0) or len(qf_issues),
        "parse_failure_files": parse_fail_files[:20],
    }


def _build_anomaly_list(
    schema_drift: List[Dict[str, Any]],
    anomalies: List[Dict[str, Any]],
    file_profiles: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Merge structural anomalies into a unified list with type labels."""
    result: List[Dict[str, Any]] = list(anomalies)  # start from existing anomalies

    # Add schema-drift anomaly entries
    for drift in schema_drift:
        severity = drift.get("severity", "low")
        if severity in ("high", "medium"):
            affected: List[str] = []
            for file_list in drift.get("files_by_type", {}).values():
                affected.extend(file_list)
            result.append({
                "anomaly_type": "schema_drift",
                "severity":     severity,
                "description":  (
                    f"Column '{drift.get('column_name', '?')}' has inconsistent types "
                    f"across {drift.get('occurrences_across_files', '?')} files"
                ),
                "affected_files":    affected[:10],
                "column":            drift.get("column_name"),
                "type_distribution": drift.get("type_distribution", {}),
                "recommendation":    drift.get("recommendation", ""),
            })

    # Add missing-column anomaly for files with unusually few columns
    if file_profiles:
        col_counts = [p.get("column_count", 0) for p in file_profiles if p.get("column_count")]
        if col_counts:
            median_cols = sorted(col_counts)[len(col_counts) // 2]
            threshold = max(1, median_cols // 3)
            for p in file_profiles:
                cc = p.get("column_count", 0)
                if 0 < cc < threshold:
                    result.append({
                        "anomaly_type": "missing_columns",
                        "severity":     "medium",
                        "description":  (
                            f"File has only {cc} column(s) vs median {median_cols} "
                            f"— possibly truncated or schema-mismatched"
                        ),
                        "affected_files": [p.get("file") or p.get("name", "")],
                        "column_count":   cc,
                        "median_columns": median_cols,
                    })

    # Deduplicate by (anomaly_type, first affected file)
    seen: set = set()
    deduped: List[Dict[str, Any]] = []
    for a in result:
        key = (a.get("anomaly_type"), tuple((a.get("affected_files") or [])[:1]))
        if key not in seen:
            seen.add(key)
            deduped.append(a)

    return deduped


def _build_relationships(
    fk_candidates: List[Dict[str, Any]],
    relationship_insights: Dict[str, Any],
) -> Dict[str, Any]:
    """Merge FK candidates + analyst insights into the canonical relationships field."""
    cross_links      = (
        relationship_insights.get("cross_file_links")
        or relationship_insights.get("relationships")
        or []
    )
    entity_hierarchy = (
        relationship_insights.get("entity_hierarchy")
        or relationship_insights.get("hierarchy")
        or []
    )
    high_conf = [fk for fk in fk_candidates if fk.get("confidence", 0) >= 0.85]

    return {
        "fk_relationships":          fk_candidates,
        "cross_file_links":          cross_links,
        "entity_hierarchy":          entity_hierarchy,
        "relationship_count":        len(fk_candidates) + len(cross_links),
        "high_confidence_count":     len(high_conf),
        "has_referential_structure": len(fk_candidates) > 0,
    }


def _compute_migration_readiness_score(
    file_profiles: List[Dict[str, Any]],
    schema_drift: List[Dict[str, Any]],
    anomalies: List[Dict[str, Any]],
    quality_findings: Dict[str, Any],
    fk_candidates: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Score 0–100 with grade A–F.  Blockers list explains critical deductions."""
    high_drift   = [d for d in schema_drift if d.get("severity") == "high"]
    medium_drift = [d for d in schema_drift if d.get("severity") == "medium"]
    empty_files  = [a for a in anomalies if a.get("anomaly_type") == "empty_file"]
    high_null    = [a for a in anomalies if a.get("anomaly_type") == "high_null_rate"]
    no_schema    = [a for a in anomalies if a.get("anomaly_type") == "no_schema"]

    parse_fail_count = len(no_schema) + sum(
        1 for p in file_profiles if not p.get("parse_ok", True)
    )

    d_high    = min(len(high_drift)   * 5, 30)
    d_medium  = min(len(medium_drift) * 2, 10)
    d_empty   = min(len(empty_files)  * 3, 15)
    d_null    = min(len(high_null)    * 2, 10)
    d_parse   = min(parse_fail_count  * 2, 10)
    d_qual    = 15 if quality_findings.get("status") == "error" else 0

    score = max(0, 100 - (d_high + d_medium + d_empty + d_null + d_parse + d_qual))
    grade = (
        "A" if score >= 90 else
        "B" if score >= 75 else
        "C" if score >= 60 else
        "D" if score >= 45 else "F"
    )

    blockers: List[str] = []
    if empty_files:
        blockers.append(
            f"{len(empty_files)} empty file(s) will produce zero rows during migration"
        )
    if high_drift:
        blockers.append(
            f"{len(high_drift)} column(s) with high-severity type drift require normalisation"
        )
    if d_qual:
        blockers.append("QualityMonitor reported an error — manual review required")

    reasoning = (
        f"Score {score}/100 (grade {grade}). "
        f"High-drift deduction: -{d_high}, medium: -{d_medium}, "
        f"empty files: -{d_empty}, high-null: -{d_null}, "
        f"parse failures: -{d_parse}, quality error: -{d_qual}."
    )
    if blockers:
        reasoning += " Blockers: " + "; ".join(blockers)

    return {
        "score":               score,
        "grade":               grade,
        "reasoning":           reasoning,
        "breakdown": {
            "high_drift_deduction":      d_high,
            "medium_drift_deduction":    d_medium,
            "empty_file_deduction":      d_empty,
            "high_null_deduction":       d_null,
            "parse_failure_deduction":   d_parse,
            "quality_monitor_deduction": d_qual,
            "fk_candidate_count":        len(fk_candidates),
        },
        "blockers":            blockers,
        "ready_for_migration": score >= 60,
    }


_PRIORITY_ORDER: Dict[str, int] = {"critical": 0, "high": 1, "medium": 2, "low": 3}


def _build_recommended_agent_actions(
    schema_drift:         List[Dict[str, Any]],
    fk_candidates:        List[Dict[str, Any]],
    anomalies:            List[Dict[str, Any]],
    quality_findings:     Dict[str, Any],  # reserved for future rule-based checks
    etl_result:           Dict[str, Any],
    readiness_score:      Dict[str, Any],
    data_quality_summary: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """
    Build the canonical recommended_agent_actions list.

    Agents:
      - ETLOrchestrator   — schema coercion, ingestion, pipeline tasks
      - QualityMonitor    — DQ scans, integrity checks, anomaly resolution
      - DataTransformation — type normalisation, column alignment tasks
    """
    _ = quality_findings  # kept in signature for future rule-based extension
    actions: List[Dict[str, Any]] = []
    counter = 0

    def _emit(agent_name: str, action_type: str, priority: str,
              description: str, affected: List[str], params: Dict) -> None:
        nonlocal counter
        counter += 1
        actions.append({
            "action_id":      f"action_{counter:04d}",
            "agent":          agent_name,
            "action_type":    action_type,
            "priority":       priority,
            "description":    description,
            "affected_files": affected,
            "parameters":     params,
            "depends_on":     [],
        })

    # --- ETLOrchestrator — one action per high-severity drift column ----------
    for drift in schema_drift:
        if drift.get("severity") == "high":
            aff: List[str] = []
            for fl in drift.get("files_by_type", {}).values():
                aff.extend(fl)
            _emit(
                "etl_orchestrator", "type_coercion", "high",
                (
                    f"Coerce column '{drift.get('column_name', '?')}' to "
                    f"'{drift.get('recommended_target_type', 'VARCHAR(255)')}' across "
                    f"{drift.get('occurrences_across_files', '?')} file(s)"
                ),
                aff[:10],
                {
                    "column":      drift.get("column_name"),
                    "target_type": drift.get("recommended_target_type", "VARCHAR(255)"),
                },
            )

    # --- ETLOrchestrator — ingestion phases from ETL result ------------------
    etl_phases = etl_result.get("phases") or etl_result.get("plan", {}).get("phases", [])
    for phase in etl_phases[:5]:
        _emit(
            "etl_orchestrator", "ingest_phase", "medium",
            phase.get("name", f"Phase {phase.get('phase', '?')}"),
            [],
            {"phase": phase.get("phase"), "actions": phase.get("actions", [])[:5]},
        )

    # --- QualityMonitor — one action per anomaly type group ------------------
    anom_by_type: Dict[str, List[str]] = {}
    for a in anomalies:
        anom_type = a.get("anomaly_type", "unknown")
        anom_by_type.setdefault(anom_type, []).extend(
            a.get("affected_files", [a.get("file", "")])[:3]
        )

    for anom_type, aff_files in anom_by_type.items():
        priority = "critical" if anom_type in ("empty_file", "no_schema") else "medium"
        _emit(
            "quality_monitor", "resolve_anomaly", priority,
            f"Resolve {anom_type.replace('_', ' ')} anomaly in {len(aff_files)} file(s)",
            list(dict.fromkeys(aff_files))[:10],
            {"anomaly_type": anom_type},
        )

    # --- DataTransformation — FK wiring for high-confidence candidates --------
    high_conf_fk = [fk for fk in fk_candidates if fk.get("confidence", 0) >= 0.80]
    for fk in high_conf_fk[:10]:
        _emit(
            "data_transformation", "create_fk_constraint", "medium",
            (
                f"Wire FK {fk.get('from_file')}.{fk.get('from_column')} → "
                f"{fk.get('to_file')}.{fk.get('to_column')} "
                f"(confidence {fk.get('confidence', 0):.0%})"
            ),
            [fk.get("from_file", ""), fk.get("to_file", "")],
            {
                "from_file":   fk.get("from_file"),
                "from_column": fk.get("from_column"),
                "to_file":     fk.get("to_file"),
                "to_column":   fk.get("to_column"),
                "confidence":  fk.get("confidence"),
            },
        )

    # --- Blockers from readiness score ----------------------------------------
    for blocker in readiness_score.get("blockers", []):
        _emit(
            "plm_director", "resolve_blocker", "critical",
            blocker, [], {},
        )

    # --- Full DQ audit if score is below threshold ----------------------------
    dq_score = data_quality_summary.get("overall_dq_score", 100)
    if dq_score < 70:
        high_risk = data_quality_summary.get("high_risk_files", [])
        _emit(
            "quality_monitor", "full_dq_audit",
            "high" if dq_score >= 50 else "critical",
            (
                f"Overall DQ score is {dq_score:.0f}/100 — full data quality audit "
                f"required before migration proceeds"
            ),
            high_risk[:10],
            {"dq_score": dq_score},
        )

    # Sort: critical → high → medium → low
    return sorted(
        actions,
        key=lambda a: _PRIORITY_ORDER.get(a.get("priority", "low"), 3),
    )


# ── Dynamic scenario helpers ──────────────────────────────────────────────────

def _detect_dynamic_fk_candidates(
    file_profiles: List[Dict[str, Any]],
    new_col_names: set,
) -> List[Dict[str, Any]]:
    """Produce FK candidates for newly discovered column names."""
    candidates: List[Dict[str, Any]] = []
    for col_name in new_col_names:
        lower_name = col_name.lower()
        if not any(lower_name.endswith(sfx) for sfx in _FK_SUFFIXES):
            continue
        files_with_col: List[str] = []
        for p in file_profiles:
            for col in p.get("columns", []):
                name = (col if isinstance(col, str) else col.get("name", "")).lower()
                if name == lower_name:
                    files_with_col.append(p.get("file") or p.get("name", ""))
                    break
        if len(files_with_col) >= 2:
            from_file = files_with_col[0]
            for to_file in files_with_col[1:]:
                candidates.append({
                    "from_file":   from_file,
                    "from_column": col_name,
                    "to_file":     to_file,
                    "to_column":   col_name,
                    "confidence":  0.60,
                    "reason":      "dynamic_naming_pattern",
                    "dynamic":     True,
                })
    return candidates[:10]


async def _evaluate_dynamic_conditions(
    file_profiles:               List[Dict[str, Any]],
    schema_drift:                List[Dict[str, Any]],
    schema_clusters:             List[Dict[str, Any]],
    fk_candidates:               List[Dict[str, Any]],
    column_corpus:               List[Dict[str, Any]],
    dataset_summary:             Dict[str, Any],
    data_quality_summary:        Dict[str, Any],
    recommended_actions:         List[Dict[str, Any]],
    folder_path:                 str,
    sample_rows:                 int,
    dq_threshold:                float,
    max_drift_files:             int,
    trigger_reprofiling:         bool,
    route_unknown_types:         bool,
    prioritize_quality:          bool,
) -> Tuple[
    Dict[str, Any],          # adaptation_log
    List[Dict[str, Any]],    # file_profiles (possibly updated)
    List[Dict[str, Any]],    # schema_drift  (possibly annotated)
    List[Dict[str, Any]],    # schema_clusters (possibly extended)
    List[Dict[str, Any]],    # fk_candidates (possibly extended)
    List[Dict[str, Any]],    # recommended_actions (possibly reordered)
]:
    """
    Evaluate all four dynamic scenarios and return updated artifacts.
    No scenario failure prevents the report from being generated.
    """
    adaptation_log: Dict[str, Any] = {
        "new_schema_patterns_detected":        False,
        "new_clusters_added":                  0,
        "schema_drift_triggered_reprofiling":  False,
        "reprofiled_files":                    [],
        "unknown_file_types_routed":           False,
        "unknown_type_files":                  [],
        "etl_extraction_triggered":            False,
        "dq_threshold_exceeded":               False,
        "dq_score":                            data_quality_summary.get("overall_dq_score", 100),
        "actions_reordered":                   False,
    }

    # ── Scenario 1: New schema patterns ───────────────────────────────────────
    # A column is "new" only if it does not appear in either the SchemaCorrelator
    # column_corpus (comprehensive cross-file index) OR any existing cluster.
    # Using corpus as the primary reference avoids false positives when
    # schema_clusters is empty but SchemaCorrelator has already catalogued all cols.
    covered_cols: set = set()
    for c in column_corpus:
        name = (c.get("column_name") or c.get("canonical_name") or c.get("name") or "").lower()
        if name:
            covered_cols.add(name)
    for cluster in schema_clusters:
        for col in cluster.get("common_columns", []):
            covered_cols.add(
                (col if isinstance(col, str) else col.get("name", "")).lower()
            )

    new_cols: set = set()
    for p in file_profiles:
        for col in p.get("columns", []):
            name = (col if isinstance(col, str) else col.get("name", "")).lower()
            if name and name not in covered_cols:
                new_cols.add(name)

    if new_cols:
        new_cluster_files: List[str] = []
        for p in file_profiles:
            profile_cols = {
                (c if isinstance(c, str) else c.get("name", "")).lower()
                for c in p.get("columns", [])
            }
            if new_cols & profile_cols:
                new_cluster_files.append(p.get("file") or p.get("name", ""))

        new_cluster: Dict[str, Any] = {
            "cluster_id":     f"dynamic_{uuid.uuid4().hex[:6]}",
            "label":          "auto_detected_new_pattern",
            "common_columns": sorted(new_cols)[:20],
            "files":          new_cluster_files[:10],
            "file_count":     len(new_cluster_files),
            "auto_detected":  True,
        }
        schema_clusters = schema_clusters + [new_cluster]

        # Re-evaluate FK candidates for new column names
        dynamic_fks = _detect_dynamic_fk_candidates(file_profiles, new_cols)
        fk_candidates = fk_candidates + dynamic_fks

        adaptation_log["new_schema_patterns_detected"] = True
        adaptation_log["new_clusters_added"] = 1
        adaptation_log["dynamic_fk_candidates_added"] = len(dynamic_fks)
        logger.info(
            "Scenario 1: %d new column pattern(s) → cluster '%s', %d new FK candidates",
            len(new_cols), new_cluster["cluster_id"], len(dynamic_fks),
        )

    # ── Scenario 2: Schema drift → selective re-profiling ─────────────────────
    high_drift_files: List[str] = []
    for drift in schema_drift:
        if drift.get("severity") == "high":
            for file_list in drift.get("files_by_type", {}).values():
                high_drift_files.extend(file_list)
    high_drift_files = list(dict.fromkeys(high_drift_files))

    if trigger_reprofiling and 0 < len(high_drift_files) <= max_drift_files:
        rerun = await _invoke_agent(
            "data_discovery", "profile_files",
            {
                "folder_path":   folder_path,
                "file_paths":    high_drift_files,
                "sample_rows":   min(sample_rows * 2, 2000),
                "include_stats": True,
            },
        )
        if rerun.get("status") != "error":
            new_profiles = rerun.get("profiles", [])
            if new_profiles:
                reprofiled_names = {p.get("file") or p.get("name", "") for p in new_profiles}
                file_profiles = [
                    p for p in file_profiles
                    if (p.get("file") or p.get("name", "")) not in reprofiled_names
                ] + new_profiles
                adaptation_log["schema_drift_triggered_reprofiling"] = True
                adaptation_log["reprofiled_files"] = sorted(reprofiled_names)
                logger.info(
                    "Scenario 2: Re-profiled %d high-drift file(s)", len(reprofiled_names)
                )

    # Annotate drift entries to surface which were marked for re-profiling
    schema_drift = [
        {**d, "reprofiling_triggered": d.get("severity") == "high" and trigger_reprofiling}
        for d in schema_drift
    ]

    # ── Scenario 3: Unknown file types → ETL routing ──────────────────────────
    novel_types = dataset_summary.get("novel_file_types", [])
    if route_unknown_types and novel_types:
        novel_exts = {t.lstrip(".") for t in novel_types}
        unknown_files = [
            p.get("file") or p.get("name", "")
            for p in file_profiles
            if (p.get("file") or p.get("name", "")).rsplit(".", 1)[-1].lower() in novel_exts
        ]
        if unknown_files:
            etl_extract = await _invoke_agent(
                "etl_orchestrator", "file_batch_processing",
                {
                    "folder_path":        folder_path,
                    "file_paths":         unknown_files[:20],
                    "extraction_method":  "hybrid",
                    "retry_profiling":    True,
                },
            )
            adaptation_log["unknown_file_types_routed"] = True
            adaptation_log["unknown_type_files"]        = unknown_files[:20]
            adaptation_log["etl_extraction_triggered"]  = etl_extract.get("status") != "error"
            logger.info(
                "Scenario 3: Routed %d unknown-type file(s) to ETL", len(unknown_files)
            )

    # ── Scenario 4: DQ threshold exceeded → reprioritize actions ──────────────
    dq_score = data_quality_summary.get("overall_dq_score", 100)
    if prioritize_quality and dq_score < dq_threshold:
        quality_actions = [
            a for a in recommended_actions
            if a.get("agent") in ("quality_monitor",)
            or a.get("action_type") in ("full_dq_audit", "monitor_data_quality",
                                         "detect_anomalies", "resolve_anomaly")
        ]
        other_actions = [a for a in recommended_actions if a not in quality_actions]
        recommended_actions = quality_actions + other_actions
        adaptation_log["dq_threshold_exceeded"] = True
        adaptation_log["actions_reordered"]     = True
        logger.info(
            "Scenario 4: DQ score %.0f < threshold %.0f — %d quality action(s) promoted",
            dq_score, dq_threshold, len(quality_actions),
        )

    return (
        adaptation_log,
        file_profiles,
        schema_drift,
        schema_clusters,
        fk_candidates,
        recommended_actions,
    )


# ── Agent class ───────────────────────────────────────────────────────────────

class ReportingAgent(AgentService):
    """Composes PLM Data Profiling Reports and evaluates dynamic scenarios."""

    def __init__(self) -> None:
        super().__init__(
            agent_type=AgentType.REPORTING_AGENT,
            agent_name="PLM Reporting Agent",
            port=8030,
        )
        self._register_extra_routes()

    def _register_extra_routes(self) -> None:
        """Mount /report as a first-class endpoint (richer than /execute)."""

        @self.app.post("/report")
        async def generate_report_direct(req: GenerateReportRequest) -> JSONResponse:
            result = await self._generate_report_from_request(req)
            return JSONResponse(content=result)

    def get_capabilities(self) -> List[AgentCapability]:
        return [
            AgentCapability(
                name="generate_plm_report",
                description=(
                    "Consume PLM profiling artifacts and emit a strict-JSON "
                    "PLM Data Profiling Report (INTENT PROMPT contract)"
                ),
            ),
            AgentCapability(
                name="evaluate_dynamic_conditions",
                description=(
                    "Re-evaluate all four dynamic scenarios (new patterns, drift, "
                    "unknown types, DQ threshold) without restarting the full pipeline"
                ),
            ),
            AgentCapability(
                name="update_schema_cluster",
                description="Add a new auto-detected schema cluster and re-evaluate FK relationships",
            ),
            AgentCapability(
                name="trigger_reprofiling",
                description="Invoke selective re-profiling on files affected by high-severity schema drift",
            ),
            AgentCapability(
                name="route_unknown_files",
                description="Route files with unknown/unsupported types to ETLOrchestrator for extraction",
            ),
        ]

    # ── Capability router ─────────────────────────────────────────────────────

    async def process_task(self, task: AgentTaskRequest) -> Dict[str, Any]:
        logger.info("ReportingAgent received task %s (type=%s)", task.task_id, task.task_type)
        capability = task.payload.get("capability", task.task_type)

        if capability in ("trigger_reprofiling", "trigger_selective_reprofiling"):
            return await self._handle_trigger_reprofiling(task.payload)

        if capability in ("route_unknown_files", "route_unknown_file_types"):
            return await self._handle_route_unknown_files(task.payload)

        if capability in ("update_schema_cluster", "adapt_schema_clusters"):
            return await self._handle_update_schema_cluster(task.payload)

        if capability == "evaluate_dynamic_conditions":
            return await self._handle_evaluate_conditions(task.payload)

        # Default: generate_plm_report
        req = GenerateReportRequest(**{
            k: v for k, v in task.payload.items()
            if k in GenerateReportRequest.model_fields
        })
        return await self._generate_report_from_request(req)

    # ── Core report assembly ──────────────────────────────────────────────────

    async def _generate_report_from_request(
        self, req: GenerateReportRequest
    ) -> Dict[str, Any]:
        """
        Assemble the strict-JSON PLM Data Profiling Report:
          1. Build all report sections from supplied artifacts.
          2. Run dynamic scenario evaluation (may update file_profiles,
             schema_clusters, fk_candidates, recommended_actions).
          3. Return fully populated report dict — no explanation text.
        """
        report_id   = f"rpt_{uuid.uuid4().hex[:12]}"
        generated_at = _now_iso()

        # Working copies (may be mutated by dynamic scenarios)
        file_profiles   = list(req.file_profiles)
        schema_drift    = list(req.schema_drift)
        fk_candidates   = list(req.fk_candidates)
        pk_candidates   = list(req.pk_candidates)
        schema_clusters = list(req.schema_clusters)
        anomalies       = list(req.anomalies)
        quality_findings    = dict(req.quality_findings)
        relationship_insights = dict(req.relationship_insights)
        etl_result      = dict(req.etl_result)
        column_corpus   = list(req.column_corpus)
        semantic_insights   = dict(req.semantic_insights)
        folder_path     = req.folder_path or req.source_name or ""

        # ── Build static report sections ──────────────────────────────────────
        dataset_summary      = _build_dataset_summary(file_profiles, column_corpus)
        data_quality_summary = _build_data_quality_summary(quality_findings, file_profiles, anomalies)
        enriched_anomalies   = _build_anomaly_list(schema_drift, anomalies, file_profiles)
        relationships        = _build_relationships(fk_candidates, relationship_insights)
        readiness_score      = _compute_migration_readiness_score(
            file_profiles, schema_drift, enriched_anomalies,
            quality_findings, fk_candidates,
        )
        recommended_actions  = _build_recommended_agent_actions(
            schema_drift, fk_candidates, enriched_anomalies,
            quality_findings, etl_result, readiness_score, data_quality_summary,
        )

        # ── Dynamic scenario evaluation ────────────────────────────────────────
        (
            adaptation_log,
            file_profiles,
            schema_drift,
            schema_clusters,
            fk_candidates,
            recommended_actions,
        ) = await _evaluate_dynamic_conditions(
            file_profiles            = file_profiles,
            schema_drift             = schema_drift,
            schema_clusters          = schema_clusters,
            fk_candidates            = fk_candidates,
            column_corpus            = column_corpus,
            dataset_summary          = dataset_summary,
            data_quality_summary     = data_quality_summary,
            recommended_actions      = recommended_actions,
            folder_path              = folder_path,
            sample_rows              = req.sample_rows,
            dq_threshold             = req.dq_threshold,
            max_drift_files          = req.max_drift_files_for_reprofiling,
            trigger_reprofiling      = req.trigger_reprofiling,
            route_unknown_types      = req.route_unknown_types,
            prioritize_quality       = req.prioritize_quality_if_below_threshold,
        )

        # Rebuild sections that may have changed due to dynamic updates
        if adaptation_log.get("new_schema_patterns_detected") or adaptation_log.get("reprofiled_files"):
            dataset_summary  = _build_dataset_summary(file_profiles, column_corpus)
            relationships    = _build_relationships(fk_candidates, relationship_insights)
            readiness_score  = _compute_migration_readiness_score(
                file_profiles, schema_drift, enriched_anomalies,
                quality_findings, fk_candidates,
            )

        # ── Assemble strict-JSON output ────────────────────────────────────────
        report: Dict[str, Any] = {
            "report_id":    report_id,
            "generated_at": generated_at,
            "migration_label": req.migration_label,

            "dataset_summary": dataset_summary,

            "schema_clusters": [
                {
                    "cluster_id":      c.get("cluster_id"),
                    "label":           c.get("label"),
                    "file_count":      c.get("file_count", len(c.get("files", []))),
                    "files":           c.get("files", [])[:20],
                    "column_patterns": c.get("common_columns", [])[:30],
                    "auto_detected":   c.get("auto_detected", False),
                }
                for c in schema_clusters
            ],

            "key_candidates": [
                {
                    "file":              k.get("file"),
                    "column":            k.get("column"),
                    "dtype":             k.get("dtype"),
                    "confidence":        k.get("confidence"),
                    "reason":            k.get("reason"),
                    "cardinality_ratio": k.get("cardinality_ratio"),
                    "null_rate":         k.get("null_rate"),
                }
                for k in pk_candidates
            ],

            "relationships": relationships,

            "anomalies": [
                {
                    "anomaly_type":    a.get("anomaly_type"),
                    "severity":        a.get("severity", "low"),
                    "description":     a.get("description", ""),
                    "affected_files":  a.get("affected_files", [])[:10],
                    "recommendation":  a.get("recommendation", ""),
                }
                for a in enriched_anomalies
            ],

            "data_quality_summary": data_quality_summary,

            "migration_readiness_score": readiness_score,

            "recommended_agent_actions": recommended_actions,

            # LLM Tool Prompt output — column semantics, entity classifications,
            # cross-file relationships, and schema alignment groups from DataProfilerAgent
            "semantic_insights": {
                "column_semantics":
                    semantic_insights.get("column_semantics", [])[:100],
                "entity_classifications":
                    semantic_insights.get("entity_classifications", []),
                "cross_file_relationships":
                    semantic_insights.get("cross_file_relationships", [])[:50],
                "schema_alignment_groups":
                    semantic_insights.get("schema_alignment_groups", []),
                "summary":
                    semantic_insights.get("summary", {}),
            },

            # Internal — not part of strict output contract but useful for
            # downstream pipeline inspection
            "_adaptation_log": adaptation_log,
        }

        logger.info(
            "ReportingAgent assembled report %s: %d files, score=%s, %d actions, %d semantic columns",
            report_id,
            len(file_profiles),
            readiness_score.get("score"),
            len(recommended_actions),
            len(semantic_insights.get("column_semantics", [])),
        )

        # ── LLM executive-summary pass ─────────────────────────────────────────
        # Generate a human-readable executive narrative from the structured report.
        backend_url = os.getenv("GRAPH_TRACE_BACKEND_URL", "http://127.0.0.1:8011")
        _EXEC_SUMMARY_PROMPT = (
            "You are a PLM data migration expert. Based on the migration readiness score, "
            "data quality summary, top anomalies, and recommended actions provided, "
            "write a concise executive summary (3-5 sentences). "
            "Focus on: overall readiness, critical risks, and immediate next steps. "
            "Return a JSON object with a single key 'executive_summary' containing the narrative string."
        )
        try:
            import json as _json
            summary_input = {
                "readiness_score": readiness_score,
                "data_quality_summary": {
                    k: v for k, v in data_quality_summary.items()
                    if k in ("total_issues", "critical_issues", "overall_dq_score", "quality_level")
                },
                "top_anomalies": [
                    {"type": a.get("anomaly_type"), "severity": a.get("severity"), "description": a.get("description", "")[:120]}
                    for a in enriched_anomalies[:5]
                ],
                "top_actions": [
                    {"action": a.get("action"), "priority": a.get("priority"), "agent": a.get("agent")}
                    for a in recommended_actions[:5]
                ],
            }
            llm_result = await self._adaptive_llm_call(
                backend_url=backend_url,
                system_prompt=_EXEC_SUMMARY_PROMPT,
                user_content=_json.dumps(summary_input),
                temperature=0.3,
                max_tokens=400,
            )
            if isinstance(llm_result, dict) and "executive_summary" in llm_result:
                report["executive_summary"] = llm_result["executive_summary"]
                logger.info("ReportingAgent: LLM executive summary generated for report %s", report_id)
        except Exception as llm_err:
            logger.debug("ReportingAgent: LLM executive summary skipped: %s", llm_err)
        # ── End LLM executive-summary ──────────────────────────────────────────

        return report

    # ── Narrow capability handlers ────────────────────────────────────────────

    async def _handle_trigger_reprofiling(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Re-profile a specific set of high-drift files via DataDiscovery."""
        file_paths  = payload.get("file_paths", [])
        folder_path = payload.get("folder_path", "")
        sample_rows = int(payload.get("sample_rows", 1000))

        if not file_paths:
            return {"status": "skipped", "reason": "No file_paths provided"}

        result = await _invoke_agent(
            "data_discovery", "profile_files",
            {
                "folder_path":   folder_path,
                "file_paths":    file_paths[:30],
                "sample_rows":   min(sample_rows * 2, 2000),
                "include_stats": True,
            },
        )
        reprofiled = [p.get("file") or p.get("name", "") for p in result.get("profiles", [])]
        return {
            "status":          "ok" if result.get("status") != "error" else "error",
            "reprofiled_files": reprofiled,
            "profile_count":   len(reprofiled),
            "raw_result":      result,
        }

    async def _handle_route_unknown_files(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Route unknown-type files to ETLOrchestrator for extraction + retry."""
        file_paths  = payload.get("file_paths", [])
        folder_path = payload.get("folder_path", "")

        if not file_paths:
            return {"status": "skipped", "reason": "No file_paths provided"}

        result = await _invoke_agent(
            "etl_orchestrator", "file_batch_processing",
            {
                "folder_path":       folder_path,
                "file_paths":        file_paths[:20],
                "extraction_method": "hybrid",
                "retry_profiling":   True,
            },
        )
        return {
            "status":           "ok" if result.get("status") != "error" else "error",
            "routed_files":     file_paths[:20],
            "extraction_status": result.get("status"),
            "raw_result":       result,
        }

    async def _handle_update_schema_cluster(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Add a new schema cluster and return updated cluster list + new FK candidates."""
        existing_clusters = payload.get("schema_clusters", [])
        file_profiles     = payload.get("file_profiles", [])
        new_col_names     = set(payload.get("new_column_names", []))
        new_files         = payload.get("new_files", [])

        if not new_col_names and not new_files:
            return {"status": "skipped", "reason": "No new_column_names or new_files provided"}

        new_cluster: Dict[str, Any] = {
            "cluster_id":     f"dynamic_{uuid.uuid4().hex[:6]}",
            "label":          payload.get("cluster_label", "auto_detected_new_pattern"),
            "common_columns": sorted(new_col_names)[:20],
            "files":          new_files[:10],
            "file_count":     len(new_files),
            "auto_detected":  True,
        }
        dynamic_fks = _detect_dynamic_fk_candidates(file_profiles, new_col_names)
        return {
            "status":            "ok",
            "updated_clusters":  existing_clusters + [new_cluster],
            "new_cluster":       new_cluster,
            "new_fk_candidates": dynamic_fks,
        }

    async def _handle_evaluate_conditions(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Re-run all dynamic scenario checks against supplied artifacts."""
        req_fields = {k: v for k, v in payload.items() if k in GenerateReportRequest.model_fields}
        req = GenerateReportRequest(**req_fields)
        # Rebuild base sections
        dqs   = _build_data_quality_summary(req.quality_findings, req.file_profiles, req.anomalies)
        dsumm = _build_dataset_summary(req.file_profiles, req.column_corpus)
        recs  = _build_recommended_agent_actions(
            req.schema_drift, req.fk_candidates, req.anomalies,
            req.quality_findings, req.etl_result,
            {"blockers": [], "score": 100},
            dqs,
        )
        (adaptation_log, _fp, _sd, sc, fk, _ra) = await _evaluate_dynamic_conditions(
            file_profiles        = list(req.file_profiles),
            schema_drift         = list(req.schema_drift),
            schema_clusters      = list(req.schema_clusters),
            fk_candidates        = list(req.fk_candidates),
            column_corpus        = list(req.column_corpus),
            dataset_summary      = dsumm,
            data_quality_summary = dqs,
            recommended_actions  = recs,
            folder_path          = req.folder_path or "",
            sample_rows          = req.sample_rows,
            dq_threshold         = req.dq_threshold,
            max_drift_files      = req.max_drift_files_for_reprofiling,
            trigger_reprofiling  = req.trigger_reprofiling,
            route_unknown_types  = req.route_unknown_types,
            prioritize_quality   = req.prioritize_quality_if_below_threshold,
        )
        return {
            "status":         "ok",
            "adaptation_log": adaptation_log,
            "updated_schema_clusters": sc,
            "updated_fk_candidates":   fk,
            "reprofiled_files":        adaptation_log.get("reprofiled_files", []),
        }


# ── Module-level singleton ────────────────────────────────────────────────────

agent = ReportingAgent()
app   = agent.app

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8030)
