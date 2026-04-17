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
    ".xlsx": "excel", ".xls": "excel",
    ".parquet": "parquet", ".avro": "avro",
    ".pdf": "pdf", ".txt": "text", ".log": "text",
    ".png": "image", ".jpg": "image", ".jpeg": "image",
    ".step": "cad", ".stp": "cad", ".igs": "cad", ".iges": "cad",
}

def _classify(ext: str) -> str:
    return _EXT_MAP.get(ext.lower(), "other")


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
    """Profile a single file — row count, column count, null rates, type hints."""
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

    try:
        if ftype == "csv":
            # utf-8-sig strips Excel BOM (\ufeff); fall back to cp1252 for Windows-ANSI exports
            for enc in ("utf-8-sig", "cp1252", "latin-1"):
                try:
                    with path.open("r", encoding=enc, newline="") as f:
                        sample = f.read(4096)
                        f.seek(0)
                        try:
                            dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
                        except csv.Error:
                            dialect = csv.excel  # fallback: comma
                        reader = csv.DictReader(f, dialect=dialect)
                        cols = [c for c in (reader.fieldnames or []) if c is not None]
                        profile["column_count"] = len(cols)
                        rows = list(reader)
                        profile["row_count"] = len(rows)
                    break  # successfully parsed
                except (UnicodeDecodeError, LookupError):
                    continue
            if rows and cols:
                col_stats = []
                for col in cols:
                    vals = [r.get(col) for r in rows]
                    nulls = sum(1 for v in vals if v is None or str(v).strip() == "")
                    unique_sample = list({str(v) for v in vals[:200] if v})[:5]
                    col_stats.append({
                        "name": col,
                        "null_count": nulls,
                        "null_rate": round(nulls / len(rows), 4) if rows else 0,
                        "sample_values": unique_sample,
                    })
                profile["columns"] = col_stats
                total_cells = len(rows) * len(cols)
                total_nulls = sum(c["null_count"] for c in col_stats)
                profile["null_rate"] = round(total_nulls / total_cells, 4) if total_cells else 0

        elif ftype == "json":
            with path.open("r", encoding="utf-8", errors="replace") as f:
                data = json.load(f)
            if isinstance(data, list):
                profile["row_count"] = len(data)
                if data and isinstance(data[0], dict):
                    cols = list(data[0].keys())
                    profile["column_count"] = len(cols)
                    profile["columns"] = [{"name": c} for c in cols]
            elif isinstance(data, dict):
                profile["row_count"] = 1
                profile["column_count"] = len(data)
                profile["columns"] = [{"name": k} for k in data.keys()]

        elif ftype == "xml":
            import xml.etree.ElementTree as ET
            tree = ET.parse(str(path))
            root_el = tree.getroot()
            children = list(root_el)
            profile["row_count"] = len(children)
            if children:
                profile["column_count"] = len(list(children[0]))
                profile["columns"] = [{"name": ch.tag} for ch in children[0]]

        elif ftype == "excel":
            import openpyxl
            wb = openpyxl.load_workbook(str(path), read_only=True, data_only=True)
            ws = wb.active
            rows = list(ws.iter_rows(values_only=True))
            wb.close()
            if rows:
                header = [str(c) if c is not None else f"col_{i}" for i, c in enumerate(rows[0])]
                data_rows = rows[1:]
                profile["column_count"] = len(header)
                profile["row_count"] = len(data_rows)
                col_stats = []
                for idx, col in enumerate(header):
                    vals = [r[idx] if idx < len(r) else None for r in data_rows]
                    nulls = sum(1 for v in vals if v is None or str(v).strip() == "")
                    unique_sample = list({str(v) for v in vals[:200] if v is not None})[:5]
                    col_stats.append({
                        "name": col,
                        "null_count": nulls,
                        "null_rate": round(nulls / len(data_rows), 4) if data_rows else 0,
                        "sample_values": unique_sample,
                    })
                profile["columns"] = col_stats
                total_cells = len(data_rows) * len(header)
                total_nulls = sum(c["null_count"] for c in col_stats)
                profile["null_rate"] = round(total_nulls / total_cells, 4) if total_cells else 0

    except Exception as exc:
        profile["parse_ok"] = False
        profile["parse_error"] = str(exc)

    return profile


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
            result["profiles"] = profiles
            parse_errors = [p for p in profiles if not p["parse_ok"]]
            result["parse_errors"] = len(parse_errors)
            result["profiled_files"] = len(profiles)

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
