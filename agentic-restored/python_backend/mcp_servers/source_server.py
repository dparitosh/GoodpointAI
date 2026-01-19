"""MCP Source Server (stdio).

This is a lightweight MCP server that exposes a few read-oriented tools.
It is intentionally decoupled from the FastAPI process: tools call the backend
HTTP API using GOODPOINT_BACKEND_URL (default http://127.0.0.1:8011).

Run (example):
  python -m python_backend.mcp_servers.source_server

Note: Requires the optional `mcp` Python package.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional


def _backend_base_url() -> str:
    return (
        (os.getenv("GOODPOINT_BACKEND_URL") or "").strip()
        or (os.getenv("BACKEND_URL") or "").strip()
        or "http://127.0.0.1:8011"
    )


def _http_get_json(url: str) -> Any:
    # Prefer httpx (already used elsewhere in this repo); fall back to urllib.
    try:
        import httpx

        with httpx.Client(timeout=20.0) as client:
            r = client.get(url)
            r.raise_for_status()
            return r.json()
    except ModuleNotFoundError:
        from urllib.request import urlopen  # pylint: disable=import-outside-toplevel
        import json  # pylint: disable=import-outside-toplevel

        with urlopen(url, timeout=20.0) as resp:  # noqa: S310
            return json.loads(resp.read().decode("utf-8"))


def _http_post_json(url: str, payload: dict) -> Any:
    try:
        import httpx

        with httpx.Client(timeout=30.0) as client:
            r = client.post(url, json=payload)
            r.raise_for_status()
            return r.json()
    except ModuleNotFoundError:
        from urllib.request import Request, urlopen  # pylint: disable=import-outside-toplevel
        import json  # pylint: disable=import-outside-toplevel

        data = json.dumps(payload).encode("utf-8")
        req = Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
        with urlopen(req, timeout=30.0) as resp:  # noqa: S310
            return json.loads(resp.read().decode("utf-8"))


def _require_mcp():
    try:
        import importlib

        mod = importlib.import_module("mcp.server.fastmcp")
        return getattr(mod, "FastMCP")
    except Exception as exc:  # pylint: disable=broad-exception-caught
        raise RuntimeError(
            "MCP Python SDK is not installed. Install optional deps (see requirements.txt)."
        ) from exc


if __name__ == "__main__":
    FastMCP = _require_mcp()

    mcp = FastMCP("goodpoint-mcp-source")

    @mcp.tool()
    def ping() -> dict:
        """Health check for the MCP source server."""
        return {"ok": True, "backend": _backend_base_url()}

    @mcp.tool()
    def list_configured_sources() -> List[Dict[str, Any]]:
        """Return the current configured data sources from the backend."""
        base = _backend_base_url().rstrip("/")
        data = _http_get_json(f"{base}/api/data-sources")
        if isinstance(data, dict) and "data" in data:
            # Some endpoints return {status,message,data}
            data = data.get("data")
        return list(data or [])

    # --- Minimal "source.*" contract (as tracked in MCP_MIGRATION_TASK_TRACKER.md) ---

    @mcp.tool()
    def list_entities() -> List[Dict[str, Any]]:
        """List available entity kinds exposed by this source server.

        This server is a thin wrapper around the backend configuration catalog.
        """
        return [
            {
                "entity": "configured_source",
                "description": "Admin-configured data sources (includes conn_<id> sources from Admin Config)",
            },
            {
                "entity": "migration_run",
                "description": "MCP migration run state snapshots (/api/migrations/runs)",
            },
        ]

    @mcp.tool()
    def sample_rows(entity: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Return a bounded sample for an entity kind."""
        ent = (entity or "").strip().lower()
        lim = max(1, min(int(limit or 10), 200))
        if ent in {"configured_source", "configured_sources", "sources"}:
            return list_configured_sources()[:lim]
        # Unknown entity types return empty sample (caller can adapt).
        return []

    @mcp.tool()
    def fetch_entity(entity: str, entity_id: str) -> Dict[str, Any]:
        """Fetch a single entity record by id (best-effort)."""
        ent = (entity or "").strip().lower()
        eid = (entity_id or "").strip()
        if not eid:
            raise ValueError("entity_id is required")

        if ent in {"configured_source", "source"}:
            base = _backend_base_url().rstrip("/")
            all_sources = _http_get_json(f"{base}/api/data-sources")
            if isinstance(all_sources, dict) and "data" in all_sources:
                all_sources = all_sources.get("data")
            for s in list(all_sources or []):
                if str(s.get("id") or "") == eid:
                    return dict(s)
            return {}

        if ent in {"migration_run", "run"}:
            return get_migration_run(eid)

        return {}

    @mcp.tool()
    def get_migration_run(run_id: str) -> Dict[str, Any]:
        """Fetch an MCP migration run from the backend (/api/migrations/runs/{run_id})."""
        rid = (run_id or "").strip()
        if not rid:
            raise ValueError("run_id is required")
        base = _backend_base_url().rstrip("/")
        data = _http_get_json(f"{base}/api/migrations/runs/{rid}")
        return dict(data or {})

    @mcp.tool()
    def transition_migration_run(run_id: str, to_status: str, event: Optional[str] = None, note: Optional[str] = None) -> Dict[str, Any]:
        """Transition a run status (best-effort state machine) via the backend."""
        rid = (run_id or "").strip()
        if not rid:
            raise ValueError("run_id is required")
        base = _backend_base_url().rstrip("/")
        payload = {"to_status": to_status, "event": event, "note": note}
        data = _http_post_json(f"{base}/api/migrations/runs/{rid}/transition", payload)
        return dict(data or {})

    mcp.run()
