"""MCP Target Server (stdio).

This is a minimal MCP server that can stage records into an MCP migration run
via the backend HTTP API.

Run (example):
  python -m python_backend.mcp_servers.target_server

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


def _http_post_json(url: str, payload: dict, *, headers: Optional[Dict[str, str]] = None) -> Any:
    try:
        import httpx

        with httpx.Client(timeout=60.0) as client:
            r = client.post(url, json=payload, headers=headers)
            r.raise_for_status()
            return r.json()
    except ModuleNotFoundError:
        from urllib.request import Request, urlopen  # pylint: disable=import-outside-toplevel
        import json  # pylint: disable=import-outside-toplevel

        data = json.dumps(payload).encode("utf-8")
        merged_headers = {"Content-Type": "application/json"}
        for k, v in (headers or {}).items():
            if k and v is not None:
                merged_headers[str(k)] = str(v)
        req = Request(url, data=data, headers=merged_headers, method="POST")
        with urlopen(req, timeout=60.0) as resp:  # noqa: S310
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

    mcp = FastMCP("goodpoint-mcp-target")

    @mcp.tool()
    def ping() -> dict:
        """Health check for the MCP target server."""
        return {"ok": True, "backend": _backend_base_url()}

    @mcp.tool()
    def stage_records(run_id: str, entity: str, records: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Stage a batch of records into the backend run (stored as count + small sample)."""
        rid = (run_id or "").strip()
        if not rid:
            raise ValueError("run_id is required")
        ent = (entity or "").strip()
        if not ent:
            raise ValueError("entity is required")

        base = _backend_base_url().rstrip("/")
        payload = {"entity": ent, "records": list(records or [])}
        data = _http_post_json(f"{base}/api/migrations/runs/{rid}/stage", payload)
        return dict(data or {})

    # --- Minimal "target.*" contract (as tracked in MCP_MIGRATION_TASK_TRACKER.md) ---

    @mcp.tool()
    def get_schema() -> Dict[str, Any]:
        """Return a minimal schema description for the target.

        This backend slice stores staged records as JSON samples in an MCP migration run.
        """
        return {
            "target": "goodpoint-backend",
            "staging": {
                "endpoint": "/api/migrations/runs/{run_id}/stage",
                "record_limit_note": "Only count + first 5 records are persisted as a sample",
            },
        }

    @mcp.tool()
    def upsert_entity(run_id: str, entity: str, record: Dict[str, Any]) -> Dict[str, Any]:
        """Upsert a single entity by staging it into the run."""
        return stage_records(run_id=run_id, entity=entity, records=[dict(record or {})])

    @mcp.tool()
    def bulk_upsert(run_id: str, entity: str, records: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Upsert a batch of entities by staging it into the run."""
        return stage_records(run_id=run_id, entity=entity, records=list(records or []))

    @mcp.tool()
    def transition_migration_run(run_id: str, to_status: str, event: Optional[str] = None, note: Optional[str] = None) -> Dict[str, Any]:
        """Transition a run status via the backend."""
        rid = (run_id or "").strip()
        if not rid:
            raise ValueError("run_id is required")
        base = _backend_base_url().rstrip("/")
        payload = {"to_status": to_status, "event": event, "note": note}
        data = _http_post_json(f"{base}/api/migrations/runs/{rid}/transition", payload)
        return dict(data or {})

    @mcp.tool()
    def materialize_run(run_id: str, entities: Optional[List[str]] = None, batch_id: Optional[str] = None) -> Dict[str, Any]:
        """Write staged *sample* records into Neo4j for this run (via backend).

        Requires the backend to have a Neo4j driver initialized; otherwise returns an error.
        """
        rid = (run_id or "").strip()
        if not rid:
            raise ValueError("run_id is required")
        base = _backend_base_url().rstrip("/")
        payload = {"entities": entities, "batch_id": batch_id}
        data = _http_post_json(f"{base}/api/migrations/runs/{rid}/materialize", payload)
        return dict(data or {})

    @mcp.tool()
    def request_approval(
        run_id: str,
        action: str,
        summary: Optional[str] = None,
        requested_by: Optional[str] = None,
        impact: Optional[Dict[str, Any]] = None,
        sample: Optional[List[Dict[str, Any]]] = None,
        note: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create an approval request for a run action (e.g., materialize).

        Returns an approval record including an approval token.
        """
        rid = (run_id or "").strip()
        if not rid:
            raise ValueError("run_id is required")
        base = _backend_base_url().rstrip("/")
        payload = {
            "action": action,
            "summary": summary,
            "requested_by": requested_by,
            "impact": dict(impact or {}),
            "sample": list(sample or []),
            "note": note,
        }
        data = _http_post_json(f"{base}/api/migrations/runs/{rid}/approvals", payload)
        return dict(data or {})

    @mcp.tool()
    def materialize_run_with_approval(
        run_id: str,
        approval_token: str,
        entities: Optional[List[str]] = None,
        batch_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Materialize staged samples into Neo4j using an approval token.

        Sends the token via `X-MCP-Approval-Token` header.
        """
        rid = (run_id or "").strip()
        if not rid:
            raise ValueError("run_id is required")
        tok = (approval_token or "").strip()
        if not tok:
            raise ValueError("approval_token is required")
        base = _backend_base_url().rstrip("/")
        payload = {"entities": entities, "batch_id": batch_id}
        data = _http_post_json(
            f"{base}/api/migrations/runs/{rid}/materialize",
            payload,
            headers={"X-MCP-Approval-Token": tok},
        )
        return dict(data or {})

    mcp.run()
