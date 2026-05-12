"""
Data Discovery Agent
====================
Standalone FastAPI microservice (port 8026).
Registered with MCP Server as AgentType.DATA_DISCOVERY_AGENT.

Capabilities
------------
- discover_files       : enumerate all files in a folder-type data source
- profile_files        : per-file row count, column count, null rates, schema
- catalog_datasource   : build a data catalog entry via the FastAPI backend
- scan_folder_quality  : delegate DQ scan to the backend quality endpoint
- infer_schema         : infer column types from CSV/JSON/XML samples
"""

import sys
import os
import json
import logging
import asyncio
import re
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
import pandas as pd
from dotenv import load_dotenv

sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

env_path = Path(__file__).resolve().parent.parent.parent / "python_backend" / ".env"
load_dotenv(dotenv_path=env_path)

from agent_services.base.agent_service import AgentService
from agent_services.base.models import AgentCapability, AgentTaskRequest, AgentType

logger = logging.getLogger(__name__)

MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "http://localhost:8012")
# Backend URL — all DB access goes through the FastAPI backend, not direct ORM
BACKEND_URL = os.getenv("GRAPH_TRACE_BACKEND_URL", "http://localhost:8011")
# Maximum rows to read when profiling a single file (prevents OOM on huge files)
MAX_PROFILE_ROWS = int(os.getenv("MAX_PROFILE_ROWS", "10000"))


# ── File type helpers ──────────────────────────────────────────────────────

_EXT_MAP: Dict[str, str] = {
    ".csv": "csv", ".tsv": "csv",
    ".json": "json", ".jsonl": "json",
    ".xml": "xml",
    ".xlsx": "xlsx", ".xls": "xlsx",
    ".parquet": "parquet", ".avro": "avro",
    ".pdf": "pdf", ".txt": "text", ".log": "text",
    ".png": "image", ".jpg": "image", ".jpeg": "image",
    ".step": "cad", ".stp": "cad", ".igs": "cad", ".iges": "cad",
}

def _classify(ext: str) -> str:
    return _EXT_MAP.get(ext.lower(), "other")


def _infer_semantic_type(series: pd.Series, dtype_str: str) -> str:
    """Infer semantic/business type from a pandas Series."""
    if series.empty or series.isnull().all():
        return "empty"
    
    # Numeric types
    if dtype_str.startswith("int") or dtype_str.startswith("uint"):
        # Check if looks like an ID (high cardinality, sequential)
        if series.nunique() / len(series) > 0.95:
            return "identifier"
        return "integer"
    
    if dtype_str.startswith("float"):
        # Check if all values are actually integers stored as float
        if (series.dropna() % 1 == 0).all():
            return "integer (stored as float)"
        return "decimal"
    
    # Date/time types
    if dtype_str.startswith("datetime"):
        return "timestamp"
    
    # Boolean
    if dtype_str == "bool":
        return "boolean"
    
    # String/object types - try to infer semantic meaning
    if dtype_str == "object":
        non_null = series.dropna()
        if len(non_null) == 0:
            return "text"
        
        # Sample values for pattern detection
        sample = non_null.head(100).astype(str)
        
        # Check for dates
        try:
            pd.to_datetime(sample, errors='raise')
            return "date/timestamp (as text)"
        except (ValueError, TypeError):
            pass
        
        # Check for numeric
        try:
            pd.to_numeric(sample, errors='raise')
            return "numeric (as text)"
        except (ValueError, TypeError):
            pass
        
        # Check cardinality for categorical vs free text
        cardinality_ratio = series.nunique() / len(series)
        if cardinality_ratio < 0.05:
            return "categorical"
        elif cardinality_ratio < 0.5:
            return "semi-categorical"
        else:
            return "text"
    
    return dtype_str


def _discover_files(folder: str, recursive: bool = True) -> List[Dict[str, Any]]:
    """Enumerate all files under *folder*, returning lightweight metadata."""
    root = Path(folder)
    if not root.exists():
        return []
    pattern = "**/*" if recursive else "*"
    files = []
    for p in root.glob(pattern):
        if p.is_file():
            try:
                stat = p.stat()
                files.append({
                    "path": str(p),
                    "name": p.name,
                    "ext": p.suffix.lower(),
                    "file_type": _classify(p.suffix),
                    "size_bytes": stat.st_size,
                    "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                })
            except OSError:
                pass
    return files


def _profile_file(file_meta: Dict[str, Any]) -> Dict[str, Any]:
    """Profile a single file — row count, column count, null rates, type hints using pandas DataFrame."""
    path = Path(file_meta["path"])
    ftype = file_meta["file_type"]
    profile: Dict[str, Any] = {
        "path": str(path),
        "file_type": ftype,
        "size_bytes": file_meta["size_bytes"],
        "row_count": None,
        "column_count": None,
        "columns": [],
        "null_rate": None,
        "parse_ok": True,
        "parse_error": None,
    }

    df = None
    try:
        if ftype == "csv":
            # Try encodings for CSV; read only up to MAX_PROFILE_ROWS to prevent OOM
            for enc in ("utf-8-sig", "cp1252", "latin-1"):
                try:
                    df = pd.read_csv(str(path), encoding=enc, nrows=MAX_PROFILE_ROWS)
                    break
                except (UnicodeDecodeError, pd.errors.ParserError):
                    continue
        elif ftype == "xlsx":
            try:
                # Try openpyxl engine first (modern .xlsx)
                df = pd.read_excel(str(path), engine='openpyxl')
            except ImportError:
                profile["parse_error"] = "openpyxl not installed - cannot read .xlsx files"
                profile["parse_ok"] = False
            except Exception:
                # Try without specifying engine (fallback to xlrd for .xls)
                try:
                    df = pd.read_excel(str(path))
                except Exception as e2:
                    profile["parse_error"] = f"Excel read failed: {str(e2)}"
                    profile["parse_ok"] = False
                    df = None
        elif ftype == "json":
            try:
                df = pd.read_json(str(path))
            except Exception as e:
                profile["parse_error"] = f"pd.read_json failed: {str(e)}"
                profile["parse_ok"] = False
                df = None
        elif ftype == "parquet":
            df = pd.read_parquet(str(path))
        elif ftype == "xml":
            df = pd.read_xml(str(path))
        # Add more formats as needed

        if df is not None and not df.empty:
            profile["row_count"] = int(len(df))
            profile["column_count"] = int(len(df.columns))
            col_stats = []
            for col in df.columns:
                # Basic stats
                null_count = int(df[col].isnull().sum())
                valid_count = int(len(df) - null_count)
                null_rate = round(float(null_count) / len(df), 4) if len(df) > 0 else 0
                
                # Distinct values — use nunique() to avoid materialising full unique array
                distinct_count = int(df[col].nunique())

                # Sample values — only materialize unique array when cardinality is manageable
                if distinct_count <= 50:
                    sample_values = [str(v) for v in df[col].dropna().unique()[:10]]
                else:
                    sample_values = [str(v) for v in df[col].dropna().head(10)]
                
                # Infer semantic type
                col_dtype = str(df[col].dtype)
                semantic_type = _infer_semantic_type(df[col], col_dtype)
                
                # Distinct data types within the column (for mixed-type columns)
                distinct_types = set()
                for val in df[col].dropna().head(100):  # Sample first 100 non-null values
                    distinct_types.add(type(val).__name__)
                
                # Statistics for numeric columns
                stats = {}
                if col_dtype.startswith(('int', 'uint', 'float')):
                    try:
                        stats["min"] = float(df[col].min())
                        stats["max"] = float(df[col].max())
                        stats["mean"] = float(round(df[col].mean(), 4))
                        stats["median"] = float(df[col].median())
                        stats["std_dev"] = float(round(df[col].std(), 4))
                        stats["quartile_25"] = float(df[col].quantile(0.25))
                        stats["quartile_75"] = float(df[col].quantile(0.75))
                    except Exception:
                        pass
                
                # Cardinality metrics
                cardinality_ratio = round(float(distinct_count) / len(df), 4) if len(df) > 0 else 0
                
                # Top 5 most frequent values
                try:
                    value_counts = df[col].value_counts().head(5)
                    top_values = [
                        {"value": str(val), "count": int(count), "percentage": round(float(count) / len(df) * 100, 2)}
                        for val, count in value_counts.items()
                    ]
                except Exception:
                    top_values = []
                
                col_stats.append({
                    "name": str(col),
                    "null_count": null_count,
                    "valid_count": valid_count,
                    "null_rate": null_rate,
                    "null_percentage": round(null_rate * 100, 2),
                    "completeness": round((1 - null_rate) * 100, 2),
                    "distinct_count": distinct_count,
                    "cardinality_ratio": cardinality_ratio,
                    "distinct_values": sample_values if distinct_count <= 10 else sample_values[:10],
                    "sample_values": sample_values[:5],  # Backward compat
                    "top_values": top_values,
                    "type": col_dtype,
                    "semantic_type": semantic_type,
                    "python_types": sorted(list(distinct_types)),
                    "statistics": stats,
                })
            profile["columns"] = col_stats
            total_nulls = sum(c["null_count"] for c in col_stats)
            total_cells = len(df) * len(df.columns)
            profile["null_rate"] = round(float(total_nulls) / total_cells, 4) if total_cells > 0 else 0
            profile["completeness"] = round((1 - profile["null_rate"]) * 100, 2)

        profile["quality_checks"] = _run_quality_checks(df)

    except Exception as exc:
        profile["parse_ok"] = False
        profile["parse_error"] = str(exc)

    return profile


def _run_quality_checks(df: Optional[pd.DataFrame]) -> List[Dict[str, Any]]:
    """Run quality checks on a DataFrame — SODA Core if available, otherwise builtin checks.
    
    Returns a list of check results, each with:
    - name: check description
    - outcome: 'pass' or 'fail'
    - fail: bool
    - pass: bool
    - value: int/float metric (optional)
    - engine: 'soda' or 'builtin'
    """
    if df is None:
        return [{"name": "quality_checks", "error": "No dataframe to evaluate"}]

    # Try SODA Core first (fail gracefully if unavailable)
    try:
        from soda.scan import Scan  # type: ignore[import-untyped]
        
        scan = Scan()
        # SODA Core 3.x API: add_pandas_dataframe(dataset_name, pandas_df, data_source_name='dask')
        scan.add_pandas_dataframe(dataset_name="data", pandas_df=df, data_source_name="pandas")
        sodacl = """
checks for data:
  - row_count > 0
  - missing_count < 100
  - duplicate_count = 0
"""
        scan.add_sodacl_yaml_str(sodacl)
        exit_code = scan.execute()
        
        # Extract check results from SODA scan
        checks = []
        scan_results = scan.get_scan_results() or {}
        for check in scan_results.get("checks", []):
            checks.append({
                "name": str(check.get("name") or check.get("identity", "unknown")),
                "outcome": str(check.get("outcome", "unknown")).lower(),
                "fail": bool(check.get("outcome", "").lower() == "fail"),
                "pass": bool(check.get("outcome", "").lower() == "pass"),
                "engine": "soda",
            })
        
        if checks:
            logger.info("SODA quality checks completed: %d checks, exit_code=%d", len(checks), exit_code)
            return checks
        
        logger.warning("SODA scan returned no checks; falling back to builtin")
    except ImportError:
        logger.debug("SODA Core not installed; using builtin quality checks")
    except Exception as exc:
        logger.warning("SODA quality check failed (%s); using fallback checks", exc)

    # Builtin quality checks (pandas-based)
    total_rows = len(df)
    missing_count = int(df.isnull().sum().sum())
    duplicate_count = int(df.duplicated().sum())
    # Use 5% of rows as the missing-count threshold, with a floor of 100.
    _missing_threshold = max(100, int(total_rows * 0.05))
    
    # Column-level nulls for reporting
    max_null_rate = 0.0
    if total_rows > 0:
        for col in df.columns:
            null_rate = df[col].isnull().sum() / total_rows
            max_null_rate = max(max_null_rate, null_rate)

    checks = [
        {
            "name": "row_count > 0",
            "outcome": "pass" if total_rows > 0 else "fail",
            "fail": bool(total_rows == 0),
            "pass": bool(total_rows > 0),
            "value": int(total_rows),
            "engine": "builtin",
        },
        {
            "name": f"missing_count < {_missing_threshold}",
            "outcome": "pass" if missing_count < _missing_threshold else "fail",
            "fail": bool(missing_count >= _missing_threshold),
            "pass": bool(missing_count < _missing_threshold),
            "value": int(missing_count),
            "engine": "builtin",
        },
        {
            "name": "duplicate_count = 0",
            "outcome": "pass" if duplicate_count == 0 else "fail",
            "fail": bool(duplicate_count != 0),
            "pass": bool(duplicate_count == 0),
            "value": int(duplicate_count),
            "engine": "builtin",
        },
        {
            "name": "max_null_rate < 50%",
            "outcome": "pass" if max_null_rate < 0.5 else "fail",
            "fail": bool(max_null_rate >= 0.5),
            "pass": bool(max_null_rate < 0.5),
            "value": float(round(max_null_rate * 100, 2)),
            "engine": "builtin",
        },
    ]
    
    logger.info("Builtin quality checks completed: %d checks", len(checks))
    return checks


def _build_profile_summary(profiles: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Build a compact, quality-focused summary from a list of _profile_file() results.

    The summary is passed in the DQ handoff payload so the quality_monitor agent
    can recommend context-aware rules without re-reading any files.

    Structure returned::

        {
          "total_files":  int,
          "parseable_files": int,
          "total_rows": int,
          "file_types": {"csv": 3, "json": 1, ...},
          "columns": {
              "<col_name>": {
                  "occurrences": int,          # how many files contain this column
                  "null_rate_avg": float,      # 0.0-1.0
                  "null_rate_max": float,
                  "semantic_types": list[str], # distinct semantic types seen
                  "dtypes": list[str],         # distinct pandas dtypes seen
                  "cardinality_ratio_avg": float,
                  "is_identifier": bool,
                  "has_mixed_types": bool,
                  "sample_values": list[str],
              }
          },
          "signals": [
              {"type": "high_null", "column": ..., "null_rate": ...},
              {"type": "mixed_type", "column": ..., "dtypes": [...]},
              {"type": "low_cardinality", "column": ..., "ratio": ...},
              {"type": "identifier_non_unique", "column": ..., "ratio": ...},
              {"type": "datetime_as_text", "column": ...},
              {"type": "empty_file", "file": ...},
          ]
        }
    """
    summary: Dict[str, Any] = {
        "total_files": len(profiles),
        "parseable_files": sum(1 for p in profiles if p.get("parse_ok")),
        "total_rows": sum(p.get("row_count") or 0 for p in profiles),
        "file_types": {},
        "columns": {},
        "signals": [],
    }

    # Aggregate per-column stats across all files
    col_agg: Dict[str, Dict[str, Any]] = {}

    for p in profiles:
        ft = p.get("file_type", "other")
        summary["file_types"][ft] = summary["file_types"].get(ft, 0) + 1

        if not p.get("parse_ok"):
            continue

        if p.get("row_count", 0) == 0:
            summary["signals"].append({"type": "empty_file", "file": p.get("path", "")})

        for col in p.get("columns", []):
            name = col.get("name", "")
            if not name:
                continue
            entry = col_agg.setdefault(name, {
                "occurrences": 0,
                "null_rates": [],
                "semantic_types": set(),
                "dtypes": set(),
                "cardinality_ratios": [],
                "sample_values": [],
            })
            entry["occurrences"] += 1
            nr = col.get("null_rate", 0) or 0
            entry["null_rates"].append(nr)
            st = col.get("semantic_type")
            if st:
                entry["semantic_types"].add(st)
            dt = col.get("type")
            if dt:
                entry["dtypes"].add(dt)
            cr = col.get("cardinality_ratio", 0) or 0
            entry["cardinality_ratios"].append(cr)
            # Keep up to 5 distinct sample values per column
            for v in col.get("sample_values", []):
                if v not in entry["sample_values"] and len(entry["sample_values"]) < 5:
                    entry["sample_values"].append(v)

    # Flatten col_agg → summary["columns"] and emit signals
    for name, agg in col_agg.items():
        null_avg = sum(agg["null_rates"]) / len(agg["null_rates"]) if agg["null_rates"] else 0
        null_max = max(agg["null_rates"]) if agg["null_rates"] else 0
        cr_avg   = sum(agg["cardinality_ratios"]) / len(agg["cardinality_ratios"]) if agg["cardinality_ratios"] else 0
        dtypes   = sorted(agg["dtypes"])
        semtypes = sorted(agg["semantic_types"])
        is_id    = "identifier" in semtypes
        mixed    = len(dtypes) > 1

        summary["columns"][name] = {
            "occurrences":        agg["occurrences"],
            "null_rate_avg":      round(null_avg, 4),
            "null_rate_max":      round(null_max, 4),
            "semantic_types":     semtypes,
            "dtypes":             dtypes,
            "cardinality_ratio_avg": round(cr_avg, 4),
            "is_identifier":      is_id,
            "has_mixed_types":    mixed,
            "sample_values":      agg["sample_values"],
        }

        # Emit quality signals for the quality_monitor to act on
        if null_max > 0.05:
            summary["signals"].append({
                "type": "high_null", "column": name,
                "null_rate": round(null_max, 4),
                "severity": "critical" if null_max > 0.5 else "high" if null_max > 0.2 else "medium",
            })
        if mixed:
            summary["signals"].append({"type": "mixed_type", "column": name, "dtypes": dtypes})
        if cr_avg < 0.01 and not is_id:
            summary["signals"].append({"type": "low_cardinality", "column": name, "ratio": round(cr_avg, 4)})
        if is_id and cr_avg < 0.99:
            summary["signals"].append({"type": "identifier_non_unique", "column": name, "cardinality_ratio": round(cr_avg, 4)})
        if any("datetime" in s or "date/timestamp" in s for s in semtypes):
            summary["signals"].append({"type": "datetime_as_text", "column": name})

    return summary


# ── Agent Class ───────────────────────────────────────────────────────────


class DataDiscoveryAgent(AgentService):
    def __init__(self):
        super().__init__(
            agent_type=AgentType.DATA_DISCOVERY_AGENT,
            agent_name="Data Discovery Agent",
            port=8026,
        )

    def get_capabilities(self) -> List[AgentCapability]:
        return [
            AgentCapability(
                name="discover_files",
                description="Enumerate all files in a folder-type data source",
            ),
            AgentCapability(
                name="profile_files",
                description="Per-file row count, column count, null rates, parse validity",
            ),
            AgentCapability(
                name="catalog_datasource",
                description="Build a data catalog entry for a registered data source",
            ),
            AgentCapability(
                name="scan_folder_quality",
                description="Run quality checks across all files in a folder data source",
            ),
            AgentCapability(
                name="infer_schema",
                description="Infer column types and schema from CSV/JSON/XML samples",
            ),
            AgentCapability(
                name="batch_discover_segment",
                description=(
                    "Discover and profile a named offset/limit segment of files — "
                    "enables parallel Wave-1 batches for corpora with 200+ files"
                ),
            ),
            AgentCapability(
                name="semantic_header_analysis",
                description="Map cryptic legacy column headers to human-readable business names using LLM semantic analysis",
            ),
            AgentCapability(
                name="data_health_report",
                description=(
                    "Generate a comprehensive Data Health Report with Readiness Score, "
                    "Trust Score, inferred rules, distribution anomalies, and semantic header map"
                ),
            ),
        ]

    async def process_task(self, task: AgentTaskRequest) -> Dict[str, Any]:
        caps = set(task.payload.get("required_capabilities", []))
        # Check both the legacy payload "type" field and the canonical task_type field
        task_type = task.payload.get("type", "") or task.task_type

        # Route by capability or explicit type
        if "data_health_report" in caps or task_type == "data_health_report":
            return await self._generate_data_health_report(task)

        if "semantic_header_analysis" in caps or task_type == "semantic_header_analysis":
            return await self._handle_semantic_header_analysis(task)
        if "discover_files" in caps or task_type == "data_discovery":
            return await self._handle_discovery(task)
        if "profile_files" in caps:
            return await self._handle_profiling(task)
        if "scan_folder_quality" in caps or "scan_datasource_quality" in caps:
            return await self._handle_quality_scan(task)
        if "catalog_datasource" in caps:
            return await self._handle_catalog(task)

        # Default: full discovery + profiling
        return await self._handle_discovery(task)

    # ── Handlers ──────────────────────────────────────────────────────────

    async def _resolve_folder_path(self, source_id: Optional[str], folder_path: Optional[str], source_name: Optional[str] = None) -> Optional[str]:
        """Resolve a folder path — either directly, by source_id, or by matching source name."""
        if folder_path:
            return folder_path
        if source_id:
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    resp = await client.get(f"{BACKEND_URL}/api/data-sources/{source_id}")
                    if resp.status_code == 200:
                        ds = resp.json()
                        conn = ds.get("connection") or {}
                        return (
                            conn.get("folder_path")
                            or conn.get("file_path")
                            or conn.get("connection_string")
                            or conn.get("uri")
                        )
            except Exception as exc:
                logger.warning("Could not resolve source_id %s: %s", source_id, exc)
        if source_name:
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    resp = await client.get(f"{BACKEND_URL}/api/data-sources", params={"limit": 200})
                    if resp.status_code == 200:
                        sources = resp.json()
                        if isinstance(sources, dict):
                            sources = sources.get("items", sources.get("data", []))
                        name_lower = source_name.lower()
                        for ds in sources:
                            ds_name = (ds.get("name") or ds.get("source_name") or "").lower()
                            if name_lower in ds_name or ds_name in name_lower:
                                conn = ds.get("connection") or {}
                                path = (
                                    conn.get("folder_path")
                                    or conn.get("file_path")
                                    or conn.get("connection_string")
                                    or conn.get("uri")
                                )
                                if path:
                                    logger.info("Resolved source name '%s' to folder: %s", source_name, path)
                                    return path
            except Exception as exc:
                logger.warning("Could not resolve source_name %s: %s", source_name, exc)
        return None

    async def _dispatch_dq_handoff(
        self,
        source_id: Optional[str],
        folder_path: str,
        parent_task_id: str,
        profiles: Optional[List[Dict[str, Any]]] = None,
    ) -> Optional[str]:
        """Fire-and-forget: submit a DATA_QUALITY_SCAN task to the quality_monitor
        agent via the MCP server.  Returns the new task_id, or None if MCP is
        not reachable (non-blocking — discovery result is returned regardless).

        ``profiles`` (optional): list of per-file profile dicts from _profile_file().
        A compact ``profile_summary`` is derived and passed in the payload so the
        quality_monitor can recommend context-aware rules without re-reading the files.
        """
        dq_task_id = f"task_dq_{int(time.time() * 1000)}"

        # Build a compact profile summary from the profiling results so the
        # quality_monitor agent can recommend rules without re-reading the files.
        profile_summary: Dict[str, Any] = {}
        if profiles:
            profile_summary = _build_profile_summary(profiles)

        task_payload = {
            "id": dq_task_id,
            "type": "data_quality_scan",
            "required_capabilities": ["scan_datasource_quality"],
            "payload": {
                "source_id": source_id,
                "folder_path": folder_path,
                "scan_type": "full",
                "triggered_by": "data_discovery_handoff",
                "parent_task_id": parent_task_id,
                "profile_summary": profile_summary,   # ← AI rule recommendation input
            },
            "priority": 5,
            "timeout": 120,
        }
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.post(
                    f"{MCP_SERVER_URL}/mcp/v1/tasks",
                    json=task_payload,
                )
                if resp.status_code in (200, 201):
                    logger.info(
                        "DQ handoff dispatched: task_id=%s source_id=%s folder=%s",
                        dq_task_id, source_id, folder_path,
                    )
                    return dq_task_id
                logger.warning(
                    "DQ handoff failed: MCP returned %s — %s",
                    resp.status_code, resp.text[:200],
                )
        except Exception as exc:
            logger.warning("DQ handoff skipped (MCP not reachable): %s", exc)
        return None

    async def _handle_discovery(self, task: AgentTaskRequest) -> Dict[str, Any]:
        payload = task.payload
        source_id = payload.get("source_id")
        source_name = payload.get("source_name") or payload.get("source") or None
        # Ignore generic placeholder values
        if source_name in ("unknown", "", None):
            source_name = None
        folder_path = (
            payload.get("folder_path")
            or await self._resolve_folder_path(source_id, None, source_name)
        )
        recursive = bool(payload.get("recursive", True))
        include_profiling = bool(payload.get("include_profiling", True))

        if not folder_path:
            return {"status": "error", "error": "Could not resolve folder path from source_id or folder_path"}

        loop = asyncio.get_running_loop()

        # File discovery (sync I/O in thread pool)
        files = await loop.run_in_executor(None, _discover_files, folder_path, recursive)

        # Type breakdown
        by_type: Dict[str, int] = {}
        for f in files:
            by_type[f["file_type"]] = by_type.get(f["file_type"], 0) + 1

        total_size = sum(f["size_bytes"] for f in files)

        result: Dict[str, Any] = {
            "status": "completed",
            "source_id": source_id,
            "folder_path": folder_path,
            "total_files": len(files),
            "total_size_bytes": total_size,
            "by_type": by_type,
            "discovered_at": datetime.now(timezone.utc).isoformat(),
            "files": files,
        }

        if include_profiling and files:
            # Parallel profiling: one thread-pool task per file (capped at 500 files).
            # A semaphore limits concurrent pandas reads to avoid memory pressure on large corpora.
            _PROFILE_CONCURRENCY = min(32, len(files))
            _sem = asyncio.Semaphore(_PROFILE_CONCURRENCY)

            async def _profile_one(f: Dict[str, Any]) -> Dict[str, Any]:
                async with _sem:
                    return await loop.run_in_executor(None, _profile_file, f)

            profiles = list(await asyncio.gather(
                *[_profile_one(f) for f in files[:500]],
                return_exceptions=False,
            ))
            # Merge profile data directly into file entries for frontend compatibility.
            # Also convert null_rate from 0-1 decimal fraction to 0-100 percent.
            profile_by_path = {p["path"]: p for p in profiles}
            for f in files:
                p = profile_by_path.get(f["path"])
                if not p:
                    continue
                f["row_count"] = p.get("row_count")
                f["column_count"] = p.get("column_count")
                nr = p.get("null_rate")
                f["null_rate"] = round(nr * 100, 2) if nr is not None else None
                f["profile"] = {}
                for col in p.get("columns", []):
                    col_nr = col.get("null_rate")
                    f["profile"][col["name"]] = {
                        "type": col.get("type"),
                        "null_rate": round(col_nr * 100, 2) if col_nr is not None else None,
                        "sample": col.get("sample_values", []),
                    }
                f["quality_checks"] = p.get("quality_checks", [])
            result["profiles"] = profiles  # keep for backwards compat
            parse_errors = [p for p in profiles if not p["parse_ok"]]
            result["parse_errors"] = len(parse_errors)
            result["profiled_files"] = len(profiles)

        # Compute catalog summary (avg row count for KPI card)
        row_counts = [f["row_count"] for f in files if f.get("row_count") is not None]
        result["catalog"] = {
            "avg_row_count": round(sum(row_counts) / len(row_counts), 1) if row_counts else None,
        }

        # Hand off to quality_monitor agent now that discovery is complete.
        # Fire-and-forget via MCP — the DQ scan runs asynchronously; we include
        # the dq_task_id in the result so the caller can poll for it.
        # Pass the profiles so quality_monitor can recommend context-aware DQ rules.
        dq_task_id = await self._dispatch_dq_handoff(
            source_id=source_id,
            folder_path=folder_path,
            parent_task_id=task.task_id,
            profiles=profiles if include_profiling and files else None,
        )

        # ── AI-powered discovery insights ────────────────────────────────────
        # Call the LLM to generate actionable insights from the profile summary.
        # This is non-blocking: if LLM is unavailable the result just lacks ai_insights.
        ai_insights = await self._generate_data_insights_with_llm(result, task.payload)
        if ai_insights:
            result["ai_insights"] = ai_insights
        result["dq_task_id"] = dq_task_id
        result["dq_status"] = "dispatched" if dq_task_id else "skipped_mcp_unavailable"

        return result

    # ── AI-powered discovery insights ─────────────────────────────────────────

    async def _generate_data_insights_with_llm(
        self, discovery_result: Dict[str, Any], payload: Dict[str, Any]
    ) -> Optional[List[Dict[str, Any]]]:
        """Call the backend LLM to generate actionable data insights from discovery.

        Uses _adaptive_llm_call (Marker 1) for error-adaptive retries.
        Returns list of insight dicts, or None when LLM unavailable.
        """
        profile_summary = _build_profile_summary(
            discovery_result.get("profiles", [])
        ) if discovery_result.get("profiles") else {}

        context = {
            "total_files": discovery_result.get("total_files", 0),
            "total_size_bytes": discovery_result.get("total_size_bytes", 0),
            "by_type": discovery_result.get("by_type", {}),
            "total_rows": profile_summary.get("total_rows", 0),
            "parse_errors": discovery_result.get("parse_errors", 0),
            "column_count": len(profile_summary.get("columns", {})),
            "signals": profile_summary.get("signals", [])[:20],
            "high_null_columns": [
                s for s in profile_summary.get("signals", [])
                if s.get("type") == "high_null"
            ][:10],
            "identifier_columns": [
                name for name, meta in profile_summary.get("columns", {}).items()
                if meta.get("is_identifier")
            ][:10],
            "mixed_type_columns": [
                s["column"] for s in profile_summary.get("signals", [])
                if s.get("type") == "mixed_type"
            ][:10],
        }

        system_prompt = (
            "You are a Data Migration Advisor analyzing PLM/ETL data discovery results. "
            "Based on the discovery statistics provided, generate a JSON array of actionable insights. "
            "Each insight must have: type (risk|opportunity|recommendation|observation), "
            "title (≤10 words), detail (1-2 sentences, concrete and specific), "
            "severity (critical|high|medium|low), action (imperative verb + object, ≤8 words). "
            "Focus on: data quality risks, schema anomalies, migration readiness, "
            "recommended DQ rules, and field mapping challenges. "
            "Output ONLY a valid JSON array, no other text."
        )

        backend_url = os.getenv("GRAPH_TRACE_BACKEND_URL", "http://127.0.0.1:8011")
        result = await self._adaptive_llm_call(
            backend_url=backend_url,
            system_prompt=system_prompt,
            user_content=json.dumps(context),
            llm_provider=payload.get("llm_provider", "openai"),
            max_tokens=1200,
        )
        if isinstance(result, list):
            valid = [i for i in result if isinstance(i, dict) and i.get("title") and i.get("type")]
            logger.info("LLM generated %d discovery insights", len(valid))
            return valid or None
        return None

    # ── Semantic Header Analysis ────────────────────────────────────────────────

    _SEMANTIC_HEADER_PROMPT = (
        "You are a Data Schema Expert for PLM/ERP/legacy systems. "
        "Given column names (often cryptic abbreviations or coded names) and their sample values, "
        "map each to a human-readable business name. "
        "Examples: C_DATE_01 → 'Creation Date', PRT_NR_V2 → 'Part Number', "
        "REL_DT_V3 → 'Release Date', CRBY_USR → 'Created By', "
        "STAT_CD → 'Status Code', MATL_GRP → 'Material Group'. "
        "Output ONLY a valid JSON object mapping original_column_name → human_readable_name."
    )

    async def _semantic_header_analysis(
        self,
        column_names: List[str],
        sample_values: Dict[str, List[str]],
        payload: Dict[str, Any],
    ) -> Dict[str, str]:
        """LLM-powered semantic mapping of cryptic column names to business names.

        Handles legacy ERP/PLM column naming like C_DATE_01 → 'Creation Date'.
        Returns dict of {original_name: human_readable_name}.
        """
        if not column_names:
            return {}
        context = {
            "columns": column_names[:60],  # cap for LLM context
            "sample_values": {col: vals[:3] for col, vals in sample_values.items()},
        }
        backend_url = os.getenv("GRAPH_TRACE_BACKEND_URL", "http://127.0.0.1:8011")
        result = await self._adaptive_llm_call(
            backend_url=backend_url,
            system_prompt=self._SEMANTIC_HEADER_PROMPT,
            user_content=json.dumps(context),
            llm_provider=payload.get("llm_provider", "openai"),
            max_tokens=800,
        )
        if isinstance(result, dict):
            return {k: v for k, v in result.items() if k in column_names and isinstance(v, str)}
        return {}

    async def _handle_semantic_header_analysis(self, task: AgentTaskRequest) -> Dict[str, Any]:
        """Task handler: run semantic header analysis on provided column list."""
        payload = task.payload
        column_names = payload.get("column_names", [])
        sample_values = payload.get("sample_values", {})
        if not column_names:
            return {"status": "error", "error": "column_names required"}
        mapping = await self._semantic_header_analysis(column_names, sample_values, payload)
        return {
            "status": "Semantic header analysis completed",
            "task_id": task.task_id,
            "semantic_header_map": mapping,
            "columns_mapped": len(mapping),
            "ai_powered": True,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    # ── Distribution Anomaly Detection ─────────────────────────────────────────

    _DATE_FORMAT_PATTERNS = [
        (re.compile(r'^\d{4}-\d{2}-\d{2}'),      'YYYY-MM-DD'),
        (re.compile(r'^\d{2}/\d{2}/\d{4}'),      'DD/MM/YYYY'),
        (re.compile(r'^\d{2}/\d{2}/\d{2}$'),     'DD/MM/YY'),
        (re.compile(r'^\d{2}-\d{2}-\d{4}'),      'DD-MM-YYYY'),
        (re.compile(r'^\d{1,2}/\d{1,2}/\d{4}'), 'M/D/YYYY'),
        (re.compile(r'^\d{4}/\d{2}/\d{2}'),      'YYYY/MM/DD'),
        (re.compile(r'^\d{4}\d{2}\d{2}$'),       'YYYYMMDD'),
    ]

    def _detect_distribution_anomalies(self, profiles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Detect distribution anomalies such as mixed date formats within a column.

        Example: a 'Release Date' column where 98% of values follow YYYY-MM-DD
        but 2% follow DD/MM/YY — flagged as a Distribution Anomaly rather than
        failing the entire transformation.
        """
        anomalies: List[Dict[str, Any]] = []
        for profile in profiles:
            if not profile.get("parse_ok"):
                continue
            for col in profile.get("columns", []):
                col_name = col.get("name", "")
                semantic = col.get("semantic_type", "")
                samples = col.get("distinct_values") or col.get("sample_values", [])

                # Only analyse date-like columns
                is_date_col = (
                    any(kw in col_name.lower() for kw in ("date", "dt", "time", "ts", "created", "modified", "release", "expir"))
                    or any(kw in semantic.lower() for kw in ("date", "time"))
                )
                if not is_date_col or not samples:
                    continue

                fmt_counts: Dict[str, int] = {}
                for val in samples:
                    sv = str(val).strip()
                    if not sv or sv in ("None", "nan", ""):
                        continue
                    for pattern, fmt_name in self._DATE_FORMAT_PATTERNS:
                        if pattern.match(sv):
                            fmt_counts[fmt_name] = fmt_counts.get(fmt_name, 0) + 1
                            break
                    else:
                        fmt_counts["other"] = fmt_counts.get("other", 0) + 1

                if len(fmt_counts) <= 1:
                    continue  # uniform format, no anomaly

                total = sum(fmt_counts.values())
                dominant = max(fmt_counts, key=fmt_counts.__getitem__)
                dominant_pct = round(fmt_counts[dominant] / total * 100, 1)
                minority = {k: v for k, v in fmt_counts.items() if k != dominant}

                anomalies.append({
                    "type": "distribution_anomaly",
                    "subtype": "mixed_date_format",
                    "column": col_name,
                    "file": profile.get("path", ""),
                    "dominant_format": dominant,
                    "dominant_pct": dominant_pct,
                    "minority_formats": minority,
                    "severity": "high" if dominant_pct < 95 else "medium",
                    "description": (
                        f"Column '{col_name}' has mixed date formats: "
                        f"{dominant_pct:.0f}% follow {dominant}, "
                        f"but also found: {', '.join(minority.keys())}."
                    ),
                    "recommendation": f"Normalise '{col_name}' to {dominant} before migration.",
                })
        return anomalies

    # ── Dummy Data Detection & Trust Score ──────────────────────────────────

    _DUMMY_MARKERS = frozenset({
        "admin", "test", "user", "demo", "sample", "example", "placeholder",
        "foo", "bar", "n/a", "na", "none", "null", "unknown", "temp", "tmp",
        "123", "000", "test123", "testuser", "noreply", "dummy", "fake",
        "anonymous", "system", "default", "guest", "noname", "tbd",
    })

    def _detect_dummy_data_trust_score(self, profiles: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Detect dummy/placeholder values and compute a per-column Trust Score.

        Trust Score (0–100 per column, higher = more trustworthy):
          -30 for high null rate (>50%)
          -15 for moderate null rate (>10%)
          -40 for high dummy value ratio (>30% of samples are dummy)
          -20 for moderate dummy ratio (>10%)
          -10 if any dummy values present
          -10 for mixed types

        Overall trust = mean of all column trust scores.
        """
        column_trust: Dict[str, Dict[str, Any]] = {}
        total_flagged = 0

        for profile in profiles:
            if not profile.get("parse_ok"):
                continue
            for col in profile.get("columns", []):
                col_name = col.get("name", "")
                samples = col.get("distinct_values") or col.get("sample_values", [])
                null_rate = col.get("null_rate", 0) or 0

                dummy_hits = [v for v in samples if str(v).strip().lower() in self._DUMMY_MARKERS]
                dummy_ratio = len(dummy_hits) / len(samples) if samples else 0

                score = 100
                flags: List[str] = []

                if null_rate > 0.5:
                    score -= 30
                    flags.append(f"high_null:{null_rate*100:.0f}%")
                elif null_rate > 0.1:
                    score -= 15
                    flags.append(f"moderate_null:{null_rate*100:.0f}%")

                if dummy_ratio > 0.3:
                    score -= 40
                    flags.append(f"high_dummy_ratio:{dummy_ratio*100:.0f}%")
                elif dummy_ratio > 0.1:
                    score -= 20
                    flags.append(f"moderate_dummy_ratio:{dummy_ratio*100:.0f}%")
                elif dummy_hits:
                    score -= 10
                    flags.append(f"some_dummy_values:{len(dummy_hits)}")

                pytypes = col.get("python_types", [])
                if len(pytypes) > 2:
                    score -= 10
                    flags.append("mixed_types")

                score = max(0, min(100, score))
                if flags:
                    total_flagged += 1

                # Keep worst-case score across files for same column
                existing = column_trust.get(col_name)
                if not existing or existing["trust_score"] > score:
                    column_trust[col_name] = {
                        "trust_score": score,
                        "flags": flags,
                        "dummy_values_found": dummy_hits[:5],
                    }

        overall = (
            round(sum(v["trust_score"] for v in column_trust.values()) / len(column_trust), 1)
            if column_trust else 100.0
        )
        return {
            "overall_trust_score": overall,
            "columns_with_issues": total_flagged,
            "column_trust_scores": column_trust,
            "trust_level": (
                "high" if overall >= 80
                else "medium" if overall >= 60
                else "low"
            ),
        }

    # ── Data Health Report ───────────────────────────────────────────────────────

    _INFER_RULES_PROMPT = (
        "You are a Data Governance Expert analysing a PLM/ERP dataset. "
        "Based on the column statistics, anomalies, and sample values provided, "
        "infer specific business rules that this data follows or should follow. "
        "Examples: 'Part Numbers must be unique and follow P-XXXX format', "
        "'Release Date must be ISO 8601 YYYY-MM-DD', "
        "'Status must be one of: Active, Inactive, Pending'. "
        "Output a JSON array of rule objects with fields: "
        "rule_name (string), rule_description (string), column (string or '*'), "
        "rule_type (uniqueness|format|allowed_values|range|completeness|referential_integrity), "
        "inferred_pattern (regex or plain-English description), "
        "confidence (0.0–1.0), evidence (what pattern led to this rule). "
        "Output ONLY valid JSON, no other text."
    )

    async def _infer_rules_from_patterns(
        self,
        profile_summary: Dict[str, Any],
        distribution_anomalies: List[Dict[str, Any]],
        payload: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """Use LLM to infer business rules autonomously from discovered data patterns."""
        context = {
            "column_stats": [
                {
                    "name": name,
                    "null_rate_max": meta.get("null_rate_max", 0),
                    "cardinality_ratio": meta.get("cardinality_ratio_avg", 0),
                    "semantic_types": meta.get("semantic_types", []),
                    "dtypes": meta.get("dtypes", []),
                    "is_identifier": meta.get("is_identifier", False),
                    "sample_values": meta.get("sample_values", [])[:5],
                }
                for name, meta in list(profile_summary.get("columns", {}).items())[:25]
            ],
            "distribution_anomalies": distribution_anomalies[:10],
            "signals": profile_summary.get("signals", [])[:15],
        }
        backend_url = os.getenv("GRAPH_TRACE_BACKEND_URL", "http://127.0.0.1:8011")
        result = await self._adaptive_llm_call(
            backend_url=backend_url,
            system_prompt=self._INFER_RULES_PROMPT,
            user_content=json.dumps(context),
            llm_provider=payload.get("llm_provider", "openai"),
            max_tokens=1500,
        )
        if isinstance(result, list):
            return [
                r for r in result
                if isinstance(r, dict) and r.get("rule_name") and r.get("column")
            ]
        return []

    def _calculate_readiness_score(
        self,
        profile_summary: Dict[str, Any],
        distribution_anomalies: List[Dict[str, Any]],
        trust_analysis: Dict[str, Any],
    ) -> int:
        """Calculate a migration Readiness Score (0–100).

        Weighted factors:
          Parse success rate    20 pts
          Column completeness   25 pts
          Distribution anomalies 20 pts
          Trust score           25 pts
          Mixed-type signals    10 pts
        """
        score = 100
        total = profile_summary.get("total_files", 1)
        parseable = profile_summary.get("parseable_files", 0)
        parse_rate = parseable / total if total > 0 else 1.0
        score -= round((1 - parse_rate) * 20)

        columns = profile_summary.get("columns", {})
        if columns:
            avg_null = sum(m.get("null_rate_avg", 0) for m in columns.values()) / len(columns)
            score -= round(avg_null * 25)

        critical_anomalies = sum(1 for a in distribution_anomalies if a.get("severity") == "high")
        score -= min(20, critical_anomalies * 5)

        trust = trust_analysis.get("overall_trust_score", 100)
        score -= round((100 - trust) * 0.25)

        mixed_signals = sum(1 for s in profile_summary.get("signals", []) if s.get("type") == "mixed_type")
        score -= min(10, mixed_signals * 2)

        return max(0, min(100, score))

    async def _generate_data_health_report(self, task: AgentTaskRequest) -> Dict[str, Any]:
        """Generate a comprehensive Data Health Report.

        Output includes:
          readiness_score    — migration readiness (0–100)
          trust_score        — data trustworthiness (0–100)
          semantic_header_map — cryptic column → human-readable name
          distribution_anomalies — mixed-format fields flagged as anomalies (not hard failures)
          column_trust_scores  — per-column trust breakdown
          inferred_rules     — business rules the agent discovered autonomously
          profile_summary    — aggregated column statistics
        """
        payload = task.payload
        folder_path = payload.get("folder_path")
        if not folder_path:
            folder_path = await self._resolve_folder_path(payload.get("source_id"), None)
        if not folder_path:
            return {"status": "error", "error": "Provide folder_path or source_id"}

        # Discover + profile the dataset
        disc_task = AgentTaskRequest(
            task_id=task.task_id + "_health_disc",
            task_type="data_discovery",
            payload={**payload, "folder_path": folder_path, "include_profiling": True},
        )
        discovery_result = await self._handle_discovery(disc_task)
        profiles: List[Dict[str, Any]] = discovery_result.get("profiles", [])
        if not profiles:
            return {"status": "error", "error": "No files discovered or profiling failed", "detail": discovery_result}

        profile_summary = _build_profile_summary(profiles)

        # Semantic header analysis (LLM maps cryptic names → business names)
        all_columns = list(profile_summary.get("columns", {}).keys())
        sample_values_map: Dict[str, List[str]] = {
            name: meta.get("sample_values", [])
            for name, meta in profile_summary.get("columns", {}).items()
        }
        semantic_header_map = await self._semantic_header_analysis(all_columns, sample_values_map, payload)

        # Distribution anomaly detection (mixed formats flagged as anomalies)
        distribution_anomalies = self._detect_distribution_anomalies(profiles)

        # Dummy data detection + Trust Score
        trust_analysis = self._detect_dummy_data_trust_score(profiles)

        # Autonomous rule inference from patterns (LLM)
        inferred_rules = await self._infer_rules_from_patterns(profile_summary, distribution_anomalies, payload)

        # Readiness Score
        readiness_score = self._calculate_readiness_score(profile_summary, distribution_anomalies, trust_analysis)

        return {
            "status": "Data Health Report generated",
            "task_id": task.task_id,
            "readiness_score": readiness_score,
            "readiness_level": (
                "ready" if readiness_score >= 80
                else "needs_attention" if readiness_score >= 60
                else "not_ready"
            ),
            "trust_score": trust_analysis["overall_trust_score"],
            "trust_level": trust_analysis["trust_level"],
            "column_trust_scores": trust_analysis["column_trust_scores"],
            "semantic_header_map": semantic_header_map,
            "distribution_anomalies": distribution_anomalies,
            "inferred_rules": inferred_rules,
            "profile_summary": profile_summary,
            "ai_powered": True,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    async def _handle_profiling(self, task: AgentTaskRequest) -> Dict[str, Any]:
        payload = task.payload
        file_paths = payload.get("file_paths", [])
        if not file_paths:
            folder_path = payload.get("folder_path") or await self._resolve_folder_path(
                payload.get("source_id"), None
            )
            if folder_path:
                loop = asyncio.get_running_loop()
                files = await loop.run_in_executor(
                    None, _discover_files, folder_path, bool(payload.get("recursive", True))
                )
                file_paths = [f["path"] for f in files]

        if not file_paths:
            return {"status": "error", "error": "No files to profile"}

        loop = asyncio.get_running_loop()
        metas = [{"path": p, "file_type": _classify(Path(p).suffix), "size_bytes": Path(p).stat().st_size if Path(p).exists() else 0} for p in file_paths]

        # Profile files in parallel (same semaphore pattern as _handle_discovery)
        _sem = asyncio.Semaphore(min(32, len(metas)))

        async def _profile_one(m: Dict[str, Any]) -> Dict[str, Any]:
            async with _sem:
                return await loop.run_in_executor(None, _profile_file, m)

        profiles = list(await asyncio.gather(*[_profile_one(m) for m in metas]))

        return {
            "status": "completed",
            "profiled_files": len(profiles),
            "profiles": profiles,
            "profiled_at": datetime.now(timezone.utc).isoformat(),
        }

    async def _handle_quality_scan(self, task: AgentTaskRequest) -> Dict[str, Any]:
        """Delegate to the backend quality endpoint — no direct DB access."""
        payload = task.payload
        source_id = payload.get("source_id")
        folder_path = payload.get("folder_path") or await self._resolve_folder_path(source_id, None)

        if not folder_path:
            return {"status": "error", "error": "Could not resolve folder path"}

        # Call backend quality scan endpoint
        scan_request = {
            "datasource": "folder",
            "table_name": folder_path,
            "scan_type": payload.get("scan_type", "full"),
            "data_source": folder_path,
        }
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(
                    f"{BACKEND_URL}/api/analytics/quality/scan",
                    json=scan_request,
                )
                if resp.status_code == 200:
                    scan_result = resp.json()
                    scan_result["routed_via"] = "data_discovery_agent"
                    return scan_result
                return {
                    "status": "error",
                    "error": f"Backend quality scan returned {resp.status_code}: {resp.text[:200]}",
                }
        except Exception as exc:
            return {"status": "error", "error": str(exc)}

    async def _handle_catalog(self, task: AgentTaskRequest) -> Dict[str, Any]:
        """Run discovery then return a catalog-style summary."""
        result = await self._handle_discovery(task)
        if result.get("status") != "completed":
            return result

        catalog_entry = {
            "catalog_id": str(uuid.uuid4()),
            "source_id": task.payload.get("source_id"),
            "folder_path": result["folder_path"],
            "total_files": result["total_files"],
            "total_size_bytes": result["total_size_bytes"],
            "file_type_breakdown": result["by_type"],
            "cataloged_at": datetime.now().isoformat(),
            "format": "data_catalog_v1",
        }
        if "profiles" in result:
            parseable = [p for p in result["profiles"] if p["parse_ok"]]
            catalog_entry["profiled_files"] = len(parseable)
            catalog_entry["avg_row_count"] = (
                sum(p["row_count"] or 0 for p in parseable) / len(parseable)
                if parseable else 0
            )
        return {"status": "completed", "catalog_entry": catalog_entry}


# Module-level singleton so uvicorn can find `app`
agent = DataDiscoveryAgent()
app = agent.app

if __name__ == "__main__":
    agent.start()
