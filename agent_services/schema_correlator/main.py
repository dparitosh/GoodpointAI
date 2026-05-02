"""
Schema Correlator Agent
=======================
Standalone FastAPI microservice (port 8028).
Registered with MCP Server as AgentType.SCHEMA_CORRELATOR.

Capabilities
------------
- correlate_schemas       : cross-file column frequency & type-consistency analysis
- detect_schema_drift     : same column name with different types across files
- find_fk_candidates      : FK relationship candidates based on naming patterns
- cluster_files_by_schema : group files by Jaccard schema similarity
- generate_corpus_report  : full structured JSON report with downstream recommendations

Design intent
-------------
This agent operates INDEPENDENTLY of DataDiscovery — it resolves the same source
folder itself and performs its own sampling.  This allows both agents to run in
PARALLEL as Wave-1 branches of a PLM migration DAG, maximising throughput.

Input payload keys (all optional; at least one source locator is required):
  source_id         : registered data-source ID (resolved via backend API)
  source_name       : display name (fuzzy-matched via backend API)
  folder_path       : direct filesystem path
  sample_rows       : max rows to load per file for FK/type analysis  (default 500)
  recursive         : recurse sub-directories (default true)
  include_fk_detection   : run FK-candidate analysis (default true)
  include_clustering     : run Jaccard schema clustering (default true)

Output structure
----------------
{
  "status": "completed",
  "corpus_summary": { ... },
  "column_corpus": [ ... ],
  "schema_drift": [ ... ],
  "fk_candidates": [ ... ],
  "schema_clusters": [ ... ],
  "anomalies": [ ... ],
  "recommendations": { "etl": [...], "quality": [...], "transformation": [...] },
  "file_schemas": [ ... ]
}
"""

from __future__ import annotations

import asyncio
import logging
import math
import os
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import httpx
import pandas as pd
from dotenv import load_dotenv

sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

env_path = Path(__file__).resolve().parent.parent.parent / "python_backend" / ".env"
load_dotenv(dotenv_path=env_path)

from agent_services.base.agent_service import AgentService
from agent_services.base.models import AgentCapability, AgentTaskRequest, AgentType

logger = logging.getLogger(__name__)

BACKEND_URL = os.getenv("GRAPH_TRACE_BACKEND_URL", "http://localhost:8011")

# ── File-type helpers ────────────────────────────────────────────────────────

_TABULAR_EXT: Set[str] = {".csv", ".tsv", ".json", ".jsonl", ".xlsx", ".xls", ".parquet"}

_EXT_MAP: Dict[str, str] = {
    ".csv": "csv", ".tsv": "csv",
    ".json": "json", ".jsonl": "json",
    ".xml": "xml",
    ".xlsx": "xlsx", ".xls": "xlsx",
    ".parquet": "parquet",
    ".pdf": "pdf", ".txt": "text", ".log": "text",
    ".step": "cad", ".stp": "cad", ".igs": "cad", ".iges": "cad",
}


def _classify_ext(ext: str) -> str:
    return _EXT_MAP.get(ext.lower(), "other")


def _is_tabular(ext: str) -> bool:
    return ext.lower() in _TABULAR_EXT


# ── Semantic type helpers ────────────────────────────────────────────────────

def _infer_semantic(col_name: str, dtype_str: str, cardinality_ratio: float) -> str:
    """Lightweight semantic type inference (name + dtype + cardinality only)."""
    name_l = col_name.lower()
    id_hints = ("_id", "id", "_no", "_num", "_seq", "_code", "_key", "_ref")

    if dtype_str.startswith(("int", "uint")):
        if cardinality_ratio > 0.95 or any(name_l.endswith(h) or name_l == h for h in id_hints):
            return "identifier"
        return "integer"

    if dtype_str.startswith("float"):
        return "decimal"

    if "datetime" in dtype_str or "timestamp" in dtype_str:
        return "timestamp"

    if dtype_str == "bool":
        return "boolean"

    if dtype_str == "object":
        if any(name_l.endswith(h) or name_l == h for h in id_hints):
            return "identifier"
        if cardinality_ratio < 0.05:
            return "categorical"
        if cardinality_ratio < 0.50:
            return "semi-categorical"
        return "text"

    return "unknown"


# ── Per-file schema extractor (runs in thread-pool) ─────────────────────────

def _extract_schema_sync(
    path: str,
    name: str,
    stem: str,
    ext: str,
    file_type: str,
    size_bytes: int,
    sample_rows: int,
) -> Optional[Dict[str, Any]]:
    """
    Load up to *sample_rows* rows and return a column-schema dict.
    Returns None if the file cannot be parsed or has no columns.
    """
    try:
        df: Optional[pd.DataFrame] = None
        if ext in (".csv", ".tsv"):
            sep = "\t" if ext == ".tsv" else ","
            for enc in ("utf-8-sig", "cp1252", "latin-1"):
                try:
                    df = pd.read_csv(path, sep=sep, nrows=sample_rows, encoding=enc, low_memory=False)
                    break
                except (UnicodeDecodeError, Exception):
                    continue
        elif ext in (".xlsx", ".xls"):
            try:
                df = pd.read_excel(path, nrows=sample_rows, engine="openpyxl")
            except Exception:
                try:
                    df = pd.read_excel(path, nrows=sample_rows)
                except Exception:
                    pass
        elif ext in (".json", ".jsonl"):
            try:
                df = pd.read_json(path, lines=(ext == ".jsonl"), nrows=sample_rows)
            except Exception:
                pass
        elif ext == ".parquet":
            try:
                df = pd.read_parquet(path).head(sample_rows)
            except Exception:
                pass

        if df is None or df.empty or len(df.columns) == 0:
            return None

        n_rows = len(df)
        columns: List[Dict[str, Any]] = []
        for col in df.columns:
            dtype_str = str(df[col].dtype)
            non_null = df[col].dropna()
            n_null = int(df[col].isnull().sum())
            n_distinct = int(non_null.nunique()) if len(non_null) > 0 else 0
            card_ratio = round(n_distinct / n_rows, 4) if n_rows > 0 else 0.0
            sem_type = _infer_semantic(str(col), dtype_str, card_ratio)
            sample_vals = [str(v) for v in non_null.head(10).tolist()]
            columns.append({
                "name": str(col),
                "name_lower": str(col).lower().strip(),
                "dtype": dtype_str,
                "semantic_type": sem_type,
                "null_rate": round(n_null / n_rows, 4) if n_rows > 0 else 0.0,
                "cardinality_ratio": card_ratio,
                "sample_values": sample_vals,
            })

        return {
            "file": name,
            "path": path,
            "stem": stem.lower(),
            "file_type": file_type,
            "size_bytes": size_bytes,
            "row_count": n_rows,
            "column_count": len(columns),
            "columns": columns,
            "column_names_lower": [c["name_lower"] for c in columns],
        }
    except Exception as exc:
        logger.debug("Schema extraction skipped for %s: %s", name, exc)
        return None


# ── Analysis functions (pure-Python, no I/O) ────────────────────────────────

def _build_column_corpus(schemas: List[Dict]) -> Dict[str, Dict]:
    """
    Aggregate per-file column info into a cross-file corpus dict.
    Key: normalised column name (lower, stripped).
    """
    corpus: Dict[str, Dict] = {}
    for schema in schemas:
        for col in schema["columns"]:
            key = col["name_lower"]
            if key not in corpus:
                corpus[key] = {
                    "column_name": col["name"],
                    "canonical_name": key,
                    "occurrences": 0,
                    "files": [],
                    "file_dtype_map": {},    # file → dtype
                    "dtypes": defaultdict(int),
                    "semantic_types": defaultdict(int),
                    "null_rates": [],
                    "cardinality_ratios": [],
                }
            e = corpus[key]
            e["occurrences"] += 1
            e["files"].append(schema["file"])
            e["file_dtype_map"][schema["file"]] = col["dtype"]
            e["dtypes"][col["dtype"]] += 1
            e["semantic_types"][col["semantic_type"]] += 1
            e["null_rates"].append(col["null_rate"])
            e["cardinality_ratios"].append(col["cardinality_ratio"])
    return corpus


def _detect_schema_drift(corpus: Dict[str, Dict]) -> List[Dict]:
    """
    Identify columns that appear in ≥2 files with inconsistent data types.
    Severity:
      high   — numeric vs text  (int/float vs object)
      medium — different numeric subtypes (int vs float)
      low    — everything else
    """
    drifts = []
    for col_key, entry in corpus.items():
        if entry["occurrences"] < 2 or len(entry["dtypes"]) <= 1:
            continue

        dtype_keys = list(entry["dtypes"].keys())
        has_numeric = any(d.startswith(("int", "uint", "float")) for d in dtype_keys)
        has_text = any(d == "object" for d in dtype_keys)

        if has_numeric and has_text:
            severity = "high"
        elif not has_text and len(set(d.split("6")[0].split("3")[0].split("1")[0] for d in dtype_keys)) > 1:
            # mixed int / float variants
            severity = "medium"
        else:
            severity = "low"

        # Build per-dtype file lists
        files_by_dtype: Dict[str, List[str]] = defaultdict(list)
        for fname, dtype in entry["file_dtype_map"].items():
            files_by_dtype[dtype].append(fname)

        target_type = "VARCHAR(255)" if has_text else "FLOAT"
        drifts.append({
            "column_name": entry["column_name"],
            "canonical_name": col_key,
            "occurrences_across_files": entry["occurrences"],
            "type_distribution": dict(entry["dtypes"]),
            "files_by_type": {k: v for k, v in files_by_dtype.items()},
            "severity": severity,
            "is_type_inconsistent": True,
            "recommended_target_type": target_type,
            "recommendation": (
                f"Standardize '{col_key}' to {target_type} before migration — "
                f"found in {entry['occurrences']} files with {len(entry['dtypes'])} different types"
            ),
        })

    severity_order = {"high": 0, "medium": 1, "low": 2}
    drifts.sort(key=lambda x: severity_order.get(x["severity"], 3))
    return drifts


def _find_fk_candidates(schemas: List[Dict]) -> List[Dict]:
    """
    Detect potential FK relationships using naming conventions.
    Pattern: column `X_id` / `X_no` / `X_code` in File-A  →  PK column in File-B whose stem ≈ X.
    Confidence is purely heuristic (name similarity), not value-based.
    """
    # Build stem → schema index
    stem_index: Dict[str, Dict] = {}
    for s in schemas:
        stem_index[s["stem"]] = s

    id_suffixes = ("_id", "_key", "_no", "_num", "_code", "_ref", "_fk", "_pk")
    candidates = []
    seen: Set[tuple] = set()

    for schema in schemas:
        for col in schema["columns"]:
            col_name = col["name_lower"]
            for suffix in id_suffixes:
                if not col_name.endswith(suffix) or len(col_name) <= len(suffix):
                    continue
                base = col_name[: -len(suffix)]
                if len(base) < 2:
                    continue

                # Look for a file whose stem shares the base
                for target_stem, target_schema in stem_index.items():
                    if target_schema["file"] == schema["file"]:
                        continue
                    if not (base in target_stem or target_stem.startswith(base) or base.startswith(target_stem)):
                        continue

                    # Find PK column in target
                    pk_cols = [
                        c for c in target_schema["columns"]
                        if c["name_lower"] in ("id", "pk", "key", f"{target_stem}_id")
                        or c["semantic_type"] == "identifier"
                    ]
                    if not pk_cols:
                        continue

                    pk_col = pk_cols[0]
                    confidence = 0.90 if base == target_stem else 0.70

                    pair_key = tuple(sorted([
                        f"{schema['file']}.{col['name']}",
                        f"{target_schema['file']}.{pk_col['name']}",
                    ]))
                    if pair_key in seen:
                        continue
                    seen.add(pair_key)

                    candidates.append({
                        "from_file": schema["file"],
                        "from_column": col["name"],
                        "to_file": target_schema["file"],
                        "to_column": pk_col["name"],
                        "pattern": f"{col_name} → {target_stem}.{pk_col['name_lower']}",
                        "confidence": confidence,
                        "detection_method": "naming_pattern",
                        "recommendation": (
                            f"Create FK: {schema['file']}.{col['name']} "
                            f"→ {target_schema['file']}.{pk_col['name']}"
                        ),
                    })

    candidates.sort(key=lambda x: x["confidence"], reverse=True)
    return candidates[:60]   # cap response size


def _detect_pk_candidates(schemas: List[Dict]) -> List[Dict]:
    """
    Per-file primary key candidate detection.

    Scoring criteria (highest confidence first):
    - High (0.95): semantic_type == "identifier", cardinality >= 95%, null_rate == 0
    - Good (0.85): integer type, cardinality >= 90%, null_rate == 0
    - Name-based (0.75): PK-hinting column name, cardinality >= 80%, null_rate <= 1%

    Returns: [{file, column, dtype, semantic_type, cardinality_ratio,
               null_rate, confidence, reason}]
    """
    pk_name_hints = ("id", "_id", "_pk", "_key", "_seq", "_no", "_num")
    seen: Dict[tuple, Dict] = {}

    for schema in schemas:
        for col in schema["columns"]:
            name_l   = col["name_lower"]
            card     = col["cardinality_ratio"]
            null     = col["null_rate"]
            dtype    = col["dtype"]
            sem      = col["semantic_type"]

            if sem == "identifier" and card >= 0.95 and null == 0.0:
                confidence = 0.95
                reason = "identifier semantic type, ≥95% cardinality, zero nulls"
            elif (sem in ("identifier", "integer")
                  and dtype.startswith(("int", "uint"))
                  and card >= 0.90 and null == 0.0):
                confidence = 0.85
                reason = f"integer column with {card:.0%} cardinality and no nulls"
            elif (any(name_l == h or name_l.endswith(h) for h in pk_name_hints)
                  and card >= 0.80 and null <= 0.01):
                confidence = 0.75
                reason = f"PK-like name pattern, {card:.0%} cardinality, {null:.1%} null rate"
            else:
                continue

            key = (schema["file"], col["name"])
            if key not in seen or confidence > seen[key]["confidence"]:
                seen[key] = {
                    "file":              schema["file"],
                    "column":            col["name"],
                    "dtype":             dtype,
                    "semantic_type":     sem,
                    "cardinality_ratio": card,
                    "null_rate":         null,
                    "confidence":        confidence,
                    "reason":            reason,
                }

    return sorted(seen.values(), key=lambda x: (-x["confidence"], x["file"]))


def _cluster_files_by_schema(schemas: List[Dict], threshold: float = 0.40) -> List[Dict]:
    """
    Group files whose column-name sets share Jaccard similarity ≥ threshold.
    Uses greedy single-pass clustering (O(n²) but manageable for ≤500 files).
    """
    if len(schemas) < 2:
        return [{
            "cluster_id": 0,
            "label": "All Files",
            "file_count": len(schemas),
            "files": [s["file"] for s in schemas],
            "common_columns": [],
            "common_column_count": 0,
        }]

    col_sets: Dict[str, Set[str]] = {s["file"]: set(s["column_names_lower"]) for s in schemas}
    clusters: List[Set[str]] = []
    assigned: Set[str] = set()

    for schema in schemas:
        fname = schema["file"]
        if fname in assigned:
            continue
        cluster: Set[str] = {fname}
        assigned.add(fname)
        base_set = col_sets[fname]

        for other in schemas:
            oname = other["file"]
            if oname in assigned:
                continue
            other_set = col_sets[oname]
            union = base_set | other_set
            if not union:
                continue
            jaccard = len(base_set & other_set) / len(union)
            if jaccard >= threshold:
                cluster.add(oname)
                assigned.add(oname)

        clusters.append(cluster)

    result = []
    for idx, cluster_files in enumerate(clusters):
        c_schemas = [s for s in schemas if s["file"] in cluster_files]
        if not c_schemas:
            continue
        # Intersection of all column sets in this cluster
        col_intersect: Optional[Set[str]] = None
        for cs in c_schemas:
            cs_set = set(cs["column_names_lower"])
            col_intersect = cs_set if col_intersect is None else col_intersect & cs_set

        # Auto-label from file-name keywords
        joined = " ".join(cluster_files).lower()
        if any(w in joined for w in ("part", "component", "bom", "assembly")):
            label = "Part / Component Files"
        elif any(w in joined for w in ("order", "sales", "invoice", "purchase")):
            label = "Order / Transaction Files"
        elif any(w in joined for w in ("customer", "contact", "user", "person", "employee")):
            label = "Master Data / Entity Files"
        elif any(w in joined for w in ("config", "setting", "param", "ref", "lookup")):
            label = "Configuration / Reference Files"
        elif any(w in joined for w in ("product", "item", "sku", "catalog")):
            label = "Product / Catalogue Files"
        else:
            label = f"Schema Group {idx + 1}"

        result.append({
            "cluster_id": idx,
            "label": label,
            "file_count": len(cluster_files),
            "files": sorted(cluster_files),
            "common_columns": sorted(col_intersect or []),
            "common_column_count": len(col_intersect or []),
        })

    return result


def _detect_corpus_anomalies(schemas: List[Dict]) -> List[Dict]:
    """
    Statistical outlier detection across the file corpus:
      - Column-count outliers  (> 2 σ from mean)
      - Empty files            (0 rows)
      - Sparse files           (< 5 rows)
      - High null-rate files   (average null rate > 50 %)
      - Schema-less files      (0 columns parsed)
    """
    if not schemas:
        return []

    col_counts = [s["column_count"] for s in schemas]
    mean_cols = sum(col_counts) / len(col_counts)
    variance = sum((c - mean_cols) ** 2 for c in col_counts) / len(col_counts)
    std_cols = math.sqrt(variance) if variance > 0 else 0.0

    anomalies = []
    for s in schemas:
        # Column-count outlier
        if std_cols > 0 and abs(s["column_count"] - mean_cols) > 2 * std_cols:
            anomalies.append({
                "file": s["file"],
                "anomaly_type": "column_count_outlier",
                "detail": (
                    f"Column count {s['column_count']} vs corpus mean "
                    f"{mean_cols:.1f} ± {std_cols:.1f}"
                ),
                "severity": "warning",
                "value": s["column_count"],
                "corpus_mean": round(mean_cols, 1),
            })

        # Empty / sparse
        if s["row_count"] == 0:
            anomalies.append({
                "file": s["file"],
                "anomaly_type": "empty_file",
                "detail": "File contains no data rows",
                "severity": "high",
                "value": 0,
            })
        elif s["row_count"] < 5:
            anomalies.append({
                "file": s["file"],
                "anomaly_type": "sparse_data",
                "detail": f"File contains only {s['row_count']} rows",
                "severity": "medium",
                "value": s["row_count"],
            })

        # High null rate
        if s["columns"]:
            avg_null = sum(c["null_rate"] for c in s["columns"]) / len(s["columns"])
            if avg_null > 0.50:
                anomalies.append({
                    "file": s["file"],
                    "anomaly_type": "high_null_rate",
                    "detail": f"Average null rate {avg_null:.1%} across all columns",
                    "severity": "high" if avg_null > 0.80 else "medium",
                    "value": round(avg_null, 4),
                })

        # No schema
        if s["column_count"] == 0:
            anomalies.append({
                "file": s["file"],
                "anomaly_type": "no_schema",
                "detail": "No columns extracted — file may be binary or corrupted",
                "severity": "high",
                "value": 0,
            })

    return anomalies


def _generate_recommendations(
    drift_alerts: List[Dict],
    fk_candidates: List[Dict],
    anomalies: List[Dict],
    clusters: List[Dict],
    corpus: Dict[str, Dict],
) -> Dict[str, List[Dict]]:
    """
    Produce actionable JSON recommendations for ETL, Quality, and Transformation agents.
    Each recommendation entry has: action, priority, rationale, and agent-specific fields.
    """
    etl: List[Dict] = []
    quality: List[Dict] = []
    transformation: List[Dict] = []

    # ── ETL: Schema-drift → type normalisation ────────────────────────────
    for drift in drift_alerts:
        if drift["severity"] in ("high", "medium"):
            etl.append({
                "action": "normalize_column_type",
                "column": drift["column_name"],
                "target_type": drift["recommended_target_type"],
                "type_distribution": drift["type_distribution"],
                "affected_files": drift.get("files_by_type", {}),
                "priority": "critical" if drift["severity"] == "high" else "high",
                "rationale": drift["recommendation"],
            })

    # ── ETL: FK candidates → constraint creation ─────────────────────────
    for fk in fk_candidates:
        if fk["confidence"] >= 0.80:
            etl.append({
                "action": "create_fk_constraint",
                "from_table": fk["from_file"],
                "from_column": fk["from_column"],
                "to_table": fk["to_file"],
                "to_column": fk["to_column"],
                "confidence": fk["confidence"],
                "priority": "medium",
                "rationale": fk["recommendation"],
            })

    # ── Quality: High-null files ──────────────────────────────────────────
    high_null = [a["file"] for a in anomalies if a["anomaly_type"] == "high_null_rate"]
    if high_null:
        quality.append({
            "action": "scan_null_rates",
            "focus_files": high_null,
            "threshold": 0.50,
            "priority": "high",
            "rationale": "Files with >50% null rates detected in corpus analysis",
        })

    # ── Quality: Empty files removal ─────────────────────────────────────
    empty = [a["file"] for a in anomalies if a["anomaly_type"] == "empty_file"]
    if empty:
        quality.append({
            "action": "remove_or_investigate_empty_files",
            "files": empty,
            "priority": "critical",
            "rationale": "Empty files will produce zero rows during migration",
        })

    # ── Quality: PK uniqueness validation ────────────────────────────────
    id_cols = [k for k, v in corpus.items()
               if any(st.startswith("identifier") for st in v["semantic_types"])]
    if id_cols:
        quality.append({
            "action": "validate_pk_uniqueness",
            "identifier_columns": sorted(id_cols)[:15],
            "priority": "high",
            "rationale": "Identifier-typed columns must be unique before FK constraints can be created",
        })

    # ── Transformation: Date format standardisation ───────────────────────
    date_cols = sorted(set(
        k for k, v in corpus.items()
        if "timestamp" in v["semantic_types"]
        or "date/timestamp (as text)" in v["semantic_types"]
        or any(w in k for w in ("date", "time", "created", "modified", "updated"))
    ))
    if date_cols:
        transformation.append({
            "action": "standardize_date_format",
            "target_format": "ISO 8601 (YYYY-MM-DDTHH:MM:SSZ)",
            "columns": date_cols[:15],
            "priority": "medium",
            "rationale": "Inconsistent date formats across files require normalisation before loading",
        })

    # ── Transformation: Cluster-level schema unification ─────────────────
    multi_file_clusters = [c for c in clusters if c["file_count"] > 1]
    if multi_file_clusters:
        transformation.append({
            "action": "unify_schema_per_cluster",
            "clusters": [
                {
                    "cluster_id": c["cluster_id"],
                    "label": c["label"],
                    "files": c["files"],
                    "shared_columns": c["common_columns"],
                }
                for c in multi_file_clusters
            ],
            "priority": "medium",
            "rationale": (
                "Files within each schema cluster share column sets and can be "
                "merged into a unified target table, reducing migration complexity"
            ),
        })

    # ── Transformation: Cast high-drift columns before loading ────────────
    high_drift = [d for d in drift_alerts if d["severity"] == "high"]
    if high_drift:
        transformation.append({
            "action": "pre_load_type_casting",
            "columns": [d["column_name"] for d in high_drift],
            "priority": "critical",
            "rationale": (
                "Columns with mixed numeric/text types will cause type errors "
                "during database COPY / INSERT unless cast beforehand"
            ),
        })

    return {"etl": etl, "quality": quality, "transformation": transformation}


# ── SchemaCorrelatorAgent ────────────────────────────────────────────────────

class SchemaCorrelatorAgent(AgentService):
    """
    Cross-file schema intelligence agent for PLM data migration.

    Runs the five-stage corpus analysis pipeline:
      1. Source resolution → folder path
      2. File enumeration (tabular only)
      3. Parallel schema extraction (asyncio + thread-pool)
      4. Cross-file analysis (drift, FK candidates, clustering, anomalies)
      5. Structured JSON report with downstream recommendations
    """

    def __init__(self) -> None:
        super().__init__(
            agent_type=AgentType.SCHEMA_CORRELATOR,
            agent_name="Schema Correlator Agent",
            port=8028,
        )

    def get_capabilities(self) -> List[AgentCapability]:
        return [
            AgentCapability(
                name="correlate_schemas",
                description="Cross-file column frequency and type-consistency analysis",
            ),
            AgentCapability(
                name="detect_schema_drift",
                description="Detect the same column name with different types across files",
            ),
            AgentCapability(
                name="find_fk_candidates",
                description="Detect potential foreign-key relationships between files using naming patterns",
            ),
            AgentCapability(
                name="cluster_files_by_schema",
                description="Group files by Jaccard schema similarity for unified-schema migration",
            ),
            AgentCapability(
                name="generate_corpus_report",
                description=(
                    "Generate a complete machine-readable corpus profiling report "
                    "with ETL, Quality, and Transformation recommendations"
                ),
            ),
        ]

    # ── Source resolution ────────────────────────────────────────────────────

    async def _resolve_folder_path(
        self,
        source_id: Optional[str],
        folder_path: Optional[str],
        source_name: Optional[str],
    ) -> Optional[str]:
        """Resolve any combination of source locators to a local filesystem path."""
        if folder_path:
            return folder_path

        def _extract_path(ds: Dict) -> Optional[str]:
            conn = ds.get("connection") or {}
            if isinstance(conn, dict):
                return (
                    conn.get("folder_path")
                    or conn.get("file_path")
                    or conn.get("connection_string")
                    or conn.get("uri")
                )
            return None

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                if source_id:
                    r = await client.get(f"{BACKEND_URL}/api/data-sources/{source_id}")
                    if r.status_code == 200:
                        return _extract_path(r.json())

                if source_name:
                    r = await client.get(f"{BACKEND_URL}/api/data-sources?limit=200")
                    if r.status_code == 200:
                        raw = r.json()
                        items = raw if isinstance(raw, list) else raw.get("items", [])
                        name_l = source_name.lower()
                        for ds in items:
                            ds_name = (ds.get("name") or ds.get("display_name") or "").lower()
                            if name_l in ds_name or ds_name in name_l:
                                p = _extract_path(ds)
                                if p:
                                    return p
        except Exception as exc:
            logger.warning("SchemaCorrelator: source resolution failed: %s", exc)
        return None

    # ── Main analysis pipeline ───────────────────────────────────────────────

    async def process_task(self, task: AgentTaskRequest) -> Dict[str, Any]:
        logger.info(
            "SchemaCorrelator received task %s (caps=%s)",
            task.task_id,
            task.context.get("required_capabilities", []),
        )
        return await self._run_corpus_analysis(task)

    async def _run_corpus_analysis(self, request: AgentTaskRequest) -> Dict[str, Any]:
        payload = request.payload
        source_id = payload.get("source_id") or None
        source_name = (payload.get("source_name") or payload.get("source") or "").strip() or None
        folder_path = payload.get("folder_path") or None
        sample_rows = int(payload.get("sample_rows", 500))
        recursive = bool(payload.get("recursive", True))

        t0 = datetime.now()

        # ── 1. Resolve source ──────────────────────────────────────────────
        resolved = await self._resolve_folder_path(source_id, folder_path, source_name)
        if not resolved:
            return {
                "status": "failed",
                "task_id": request.task_id,
                "error": (
                    f"Could not resolve source folder. "
                    f"source_id={source_id!r}, source_name={source_name!r}"
                ),
                "recommendations": {"etl": [], "quality": [], "transformation": []},
            }

        root = Path(resolved)
        if not root.is_dir():
            return {
                "status": "failed",
                "task_id": request.task_id,
                "error": f"Resolved path is not a directory: {resolved}",
                "recommendations": {"etl": [], "quality": [], "transformation": []},
            }

        # ── 2. Enumerate files ─────────────────────────────────────────────
        pattern = "**/*" if recursive else "*"
        all_file_metas = []
        for p in root.glob(pattern):
            if p.is_file():
                try:
                    all_file_metas.append({
                        "path": str(p),
                        "name": p.name,
                        "stem": p.stem,
                        "ext": p.suffix.lower(),
                        "file_type": _classify_ext(p.suffix),
                        "is_tabular": _is_tabular(p.suffix),
                        "size_bytes": p.stat().st_size,
                    })
                except OSError:
                    pass

        tabular = [m for m in all_file_metas if m["is_tabular"]]
        non_tabular = [m for m in all_file_metas if not m["is_tabular"]]

        if not tabular:
            return {
                "status": "completed",
                "task_id": request.task_id,
                "warning": "No tabular files found — schema correlation skipped",
                "source_name": source_name,
                "folder_path": resolved,
                "corpus_summary": {
                    "total_files": len(all_file_metas),
                    "tabular_files_analyzed": 0,
                    "non_tabular_files": len(non_tabular),
                },
                "recommendations": {"etl": [], "quality": [], "transformation": []},
            }

        # ── 3. Parallel schema extraction (thread-pool) ────────────────────
        # Use a semaphore to limit max parallelism on large corpora (avoids
        # overwhelming pandas on 200+ concurrent file reads).
        sem = asyncio.Semaphore(min(32, len(tabular)))
        loop = asyncio.get_running_loop()

        async def _extract_with_sem(meta: Dict) -> Optional[Dict]:
            async with sem:
                return await loop.run_in_executor(
                    None,
                    _extract_schema_sync,
                    meta["path"], meta["name"], meta["stem"],
                    meta["ext"], meta["file_type"], meta["size_bytes"],
                    sample_rows,
                )

        raw_results = await asyncio.gather(
            *[_extract_with_sem(m) for m in tabular],
            return_exceptions=True,
        )

        schemas: List[Dict] = []
        failed_count = 0
        for r in raw_results:
            if isinstance(r, BaseException):
                logger.debug("Schema extraction exception: %s", r)
                failed_count += 1
            elif r is not None:
                schemas.append(r)
            else:
                failed_count += 1

        if not schemas:
            return {
                "status": "completed",
                "task_id": request.task_id,
                "warning": "All tabular files failed schema extraction",
                "folder_path": resolved,
                "corpus_summary": {
                    "total_files": len(all_file_metas),
                    "tabular_files_analyzed": 0,
                    "failed_extractions": failed_count,
                },
                "recommendations": {"etl": [], "quality": [], "transformation": []},
            }

        # ── 4. Cross-file analysis (pure-Python, non-blocking) ────────────
        corpus = _build_column_corpus(schemas)
        drift_alerts = _detect_schema_drift(corpus)
        fk_candidates = _find_fk_candidates(schemas)
        pk_candidates = _detect_pk_candidates(schemas)
        clusters = _cluster_files_by_schema(schemas)
        anomalies = _detect_corpus_anomalies(schemas)
        recommendations = _generate_recommendations(
            drift_alerts, fk_candidates, anomalies, clusters, corpus
        )

        elapsed = round((datetime.now() - t0).total_seconds(), 2)

        # ── 5. Build serialisable column corpus list ───────────────────────
        column_corpus_list = []
        for col_key, entry in corpus.items():
            avg_null = (
                round(sum(entry["null_rates"]) / len(entry["null_rates"]), 4)
                if entry["null_rates"]
                else 0.0
            )
            column_corpus_list.append({
                "column_name": entry["column_name"],
                "canonical_name": col_key,
                "occurrences": entry["occurrences"],
                "files": entry["files"],
                "dtypes": dict(entry["dtypes"]),
                "semantic_types": dict(entry["semantic_types"]),
                "is_consistent": len(entry["dtypes"]) == 1,
                "avg_null_rate": avg_null,
            })
        column_corpus_list.sort(key=lambda x: x["occurrences"], reverse=True)

        # ── 6. Compact per-file schema for response ────────────────────────
        file_schemas_out = [
            {
                "file": s["file"],
                "file_type": s["file_type"],
                "size_bytes": s["size_bytes"],
                "row_count": s["row_count"],
                "column_count": s["column_count"],
                "columns": [
                    {
                        "name": c["name"],
                        "dtype": c["dtype"],
                        "semantic_type": c["semantic_type"],
                        "null_rate": c["null_rate"],
                    }
                    for c in s["columns"]
                ],
            }
            for s in schemas
        ]

        return {
            "status": "completed",
            "task_id": request.task_id,
            "source_name": source_name,
            "folder_path": resolved,
            "corpus_summary": {
                "total_files": len(all_file_metas),
                "tabular_files_analyzed": len(schemas),
                "non_tabular_files": len(non_tabular),
                "failed_extractions": failed_count,
                "unique_column_names": len(corpus),
                "schema_groups": len(clusters),
                "drift_alerts": len(drift_alerts),
                "fk_candidates": len(fk_candidates),
                "anomalies": len(anomalies),
                "high_severity_drift": sum(1 for d in drift_alerts if d["severity"] == "high"),
                "processing_time_s": elapsed,
            },
            "column_corpus": column_corpus_list,
            "schema_drift": drift_alerts,
            "fk_candidates": fk_candidates,
            "pk_candidates": pk_candidates,
            "schema_clusters": clusters,
            "anomalies": anomalies,
            "recommendations": recommendations,
            "file_schemas": file_schemas_out,
        }


# ── Module-level app export (required for uvicorn ASGI discovery) ────────────
agent = SchemaCorrelatorAgent()
app = agent.app

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8028)
