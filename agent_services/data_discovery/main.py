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
import csv
import json
import logging
import asyncio
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
import pandas as pd
from dotenv import load_dotenv
from fastapi import FastAPI

sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

env_path = Path(__file__).resolve().parent.parent.parent / "python_backend" / ".env"
load_dotenv(dotenv_path=env_path)

from agent_services.base.agent_service import AgentService
from agent_services.base.models import AgentCapability, AgentTaskRequest, AgentType

logger = logging.getLogger(__name__)

# Backend URL — all DB access goes through the FastAPI backend, not direct ORM
BACKEND_URL = os.getenv("GRAPH_TRACE_BACKEND_URL", "http://localhost:8011")


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
            # Try encodings for CSV
            for enc in ("utf-8-sig", "cp1252", "latin-1"):
                try:
                    df = pd.read_csv(str(path), encoding=enc, nrows=0)  # First check header
                    df = pd.read_csv(str(path), encoding=enc)
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
            except Exception as e:
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
                if isinstance(df, pd.Series):
                    df = df.to_frame().T
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
                
                # Distinct values
                distinct_values = df[col].dropna().unique()
                distinct_count = int(len(distinct_values))
                
                # Sample values (convert to native Python types)
                sample_values = [str(v) for v in distinct_values[:10]]
                
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
            "name": "missing_count < 100",
            "outcome": "pass" if missing_count < 100 else "fail",
            "fail": bool(missing_count >= 100),
            "pass": bool(missing_count < 100),
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
        ]

    async def process_task(self, task: AgentTaskRequest) -> Dict[str, Any]:
        caps = set(task.payload.get("required_capabilities", []))
        task_type = task.payload.get("type", "")

        # Route by capability or explicit type
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

    async def _resolve_folder_path(self, source_id: Optional[str], folder_path: Optional[str]) -> Optional[str]:
        """Resolve a folder path — either directly or by looking up a data source."""
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
        return None

    async def _handle_discovery(self, task: AgentTaskRequest) -> Dict[str, Any]:
        payload = task.payload
        source_id = payload.get("source_id")
        folder_path = payload.get("folder_path") or await self._resolve_folder_path(source_id, None)
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
            "discovered_at": datetime.now().isoformat(),
            "files": files,
        }

        if include_profiling and files:
            profiles = await loop.run_in_executor(
                None,
                lambda: [_profile_file(f) for f in files[:500]],  # cap at 500 for response size
            )
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

        return result

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
        profiles = await loop.run_in_executor(None, lambda: [_profile_file(m) for m in metas])

        return {
            "status": "completed",
            "profiled_files": len(profiles),
            "profiles": profiles,
            "profiled_at": datetime.now().isoformat(),
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


if __name__ == "__main__":
    agent = DataDiscoveryAgent()
    agent.start()
