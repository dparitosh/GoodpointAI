"""GraphQL Tools Router.

This project already has a "GraphQL toolkit" surface under `/api/graphql/*`.
Those endpoints are not a full GraphQL server; they provide GraphQL-like
introspection/query helpers.

This router extends that toolkit with *tooling* endpoints that agents can use to
orchestrate workflow steps using a single, consistent API surface.

Key goals:
- Provide OpenSearch and Soda "tools" behind a stable interface.
- Avoid leaking secrets (never return raw passwords/connection strings).
- Reuse existing backend implementations for Soda scans and OpenSearch queries.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from core.db_session import get_db
from services.admin_config_service import AdminConfigService
from services.opensearch_service import OpenSearchService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/graphql/tools", tags=["graphql-tools"])


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class ConnectorSummary(BaseModel):
    """A safe view of a connector (no secrets)."""

    id: str
    connection_type: str
    name: str
    description: Optional[str] = None
    host: Optional[str] = None
    port: Optional[int] = None
    database: Optional[str] = None
    username: Optional[str] = None
    use_ssl: bool = False
    status: str
    is_default: bool = False
    extra_options: Dict[str, Any] = Field(default_factory=dict)


class OpenSearchSearchToolRequest(BaseModel):
    index: str = Field(..., description="Index name")
    query: Dict[str, Any] = Field(..., description="OpenSearch Query DSL body")
    connection_id: Optional[str] = Field(
        default=None,
        description=(
            "Optional connection_config id to use. If omitted, the default 'opensearch' connector is used."  # noqa: E501
        ),
    )


class SodaScanToolRequest(BaseModel):
    checks_yaml: str = Field(..., description="SodaCL checks YAML")
    data_source_name: str = Field(default="postgres", description="Soda data source name")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mask_secret(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    raw = str(value)
    if not raw:
        return raw
    return "***"


def _safe_extra_options(raw: Any) -> Dict[str, Any]:
    if isinstance(raw, dict):
        # Best-effort: remove common secret keys.
        filtered: Dict[str, Any] = {}
        for k, v in raw.items():
            lk = str(k).lower()
            if lk in {"password", "secret", "token", "api_key", "apikey", "connection_string"}:
                filtered[k] = "[REDACTED]"
            else:
                filtered[k] = v
        return filtered
    return {}


def _get_connector_row(db: Session, connection_id: str):
    try:
        from models.admin_config_models import ConnectionConfig
    except ImportError as exc:  # pragma: no cover
        raise HTTPException(status_code=503, detail="Admin config models not available") from exc

    row = db.query(ConnectionConfig).filter(ConnectionConfig.id == connection_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Connector not found")
    return row


def _opensearch_service_for_connector(db: Session, connection_id: Optional[str]) -> OpenSearchService:
    if not connection_id:
        return OpenSearchService(db_session=db)

    row = _get_connector_row(db, connection_id)
    if (row.connection_type or "").lower().strip() != "opensearch":
        raise HTTPException(status_code=400, detail="connection_id is not an opensearch connector")

    cfg: Dict[str, Any] = {}
    # Match OpenSearchService expectations (url/endpoint/connection_string + host/port + username/password + ssl).
    if getattr(row, "connection_string", None):
        cfg["connection_string"] = row.connection_string
    if getattr(row, "host", None):
        cfg["host"] = row.host
    if getattr(row, "port", None):
        cfg["port"] = row.port
    if getattr(row, "username", None):
        cfg["username"] = row.username
    if getattr(row, "password", None):
        cfg["password"] = row.password

    # The admin model uses use_ssl.
    cfg["ssl_enabled"] = bool(getattr(row, "use_ssl", False))

    extra = getattr(row, "extra_options", None)
    if isinstance(extra, dict):
        # Allow `verify_certs` and `timeout_s` from extra_options.
        if "verify_certs" in extra:
            cfg["verify_certs"] = extra.get("verify_certs")
        if "timeout_s" in extra:
            cfg["timeout_s"] = extra.get("timeout_s")

    return OpenSearchService(config=cfg, db_session=db)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/connectors", response_model=List[ConnectorSummary])
async def list_connectors(
    connection_type: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """List configured connectors (safe view).

    This is a convenience endpoint for agent orchestration so it can discover
    which connectors exist without calling the admin config API.

    Note: Secrets are never returned.
    """

    try:
        from models.admin_config_models import ConnectionConfig
    except ImportError as exc:  # pragma: no cover
        raise HTTPException(status_code=503, detail="Admin config models not available") from exc

    q = db.query(ConnectionConfig)
    if connection_type:
        q = q.filter(ConnectionConfig.connection_type == connection_type)

    try:
        rows = q.order_by(ConnectionConfig.connection_type, ConnectionConfig.name).all()
    except SQLAlchemyError as exc:
        # In lightweight CI / developer machines, Postgres might not be running.
        # This endpoint should still respond with a structured payload.
        logger.warning("DB unavailable while listing connectors: %s", exc)
        return []

    out: List[ConnectorSummary] = []
    for row in rows:
        out.append(
            ConnectorSummary(
                id=str(row.id),
                connection_type=str(row.connection_type),
                name=str(row.name),
                description=getattr(row, "description", None),
                host=getattr(row, "host", None),
                port=getattr(row, "port", None),
                database=getattr(row, "database", None),
                username=getattr(row, "username", None),
                use_ssl=bool(getattr(row, "use_ssl", False)),
                status=str(getattr(row, "status", "active")),
                is_default=bool(getattr(row, "is_default", False)),
                extra_options=_safe_extra_options(getattr(row, "extra_options", None)),
            )
        )

    return out


@router.get("/connectors/default/{connection_type}")
async def get_default_connector(connection_type: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Get the resolved (masked) default connector config for a connection type."""

    cfg = AdminConfigService(db).get_connection_config(connection_type)

    # Ensure we never return secrets.
    out = dict(cfg or {})
    for key in ["password", "connection_string"]:
        if key in out:
            out[key] = _mask_secret(out.get(key))

    # Normalize the extra settings key so callers can rely on it.
    extra = out.get("extra_settings")
    if isinstance(extra, dict):
        out["extra_settings"] = _safe_extra_options(extra)
    return out


@router.post("/opensearch/search")
async def opensearch_search_tool(request: OpenSearchSearchToolRequest, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """OpenSearch search tool.

    This is intended for agent orchestration.
    It uses the same OpenSearch wrapper as the rest of the backend.
    """

    service = _opensearch_service_for_connector(db, request.connection_id)
    try:
        # Fail closed if the cluster isn't reachable.
        _ = service.info()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=f"OpenSearch unreachable: {exc}") from exc

    try:
        return service.search(index=request.index, query=request.query)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        logger.error("OpenSearch search tool failed: %s", exc)
        raise HTTPException(status_code=500, detail="OpenSearch search failed") from exc


@router.post("/soda/scan/{table_name}")
async def soda_scan_tool(
    table_name: str,
    payload: SodaScanToolRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Soda scan tool (GraphQL toolkit surface).

    This delegates to the existing Soda scan implementation under
    `/api/analytics/quality/soda/scan/{table_name}` so the report contract stays
    consistent.
    """

    try:
        from graph_api.quality_router import SodaScanRequest, soda_scan_table_quality
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Quality subsystem unavailable: {exc}") from exc

    req = SodaScanRequest(checks_yaml=payload.checks_yaml, data_source_name=payload.data_source_name)
    return await soda_scan_table_quality(table_name=table_name, scan_request=req, db=db)


@router.post("/opensearch-ad/gate/{result_index}")
async def opensearch_ad_gate_tool(
    result_index: str,
    payload: Optional[Dict[str, Any]] = None,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """OpenSearch AD gate tool.

    Delegates to the existing gatekeeper endpoint under
    `/api/analytics/quality/opensearch-ad/gate/{result_index}` but keeps it
    available on the GraphQL toolkit surface for orchestration agents.

    Body is optional; defaults are applied by the underlying model.
    """

    try:
        from graph_api.quality_router import OpenSearchAnomalyGateRequest, opensearch_ad_gate
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Quality subsystem unavailable: {exc}") from exc

    req = OpenSearchAnomalyGateRequest(**(payload or {}))
    return await opensearch_ad_gate(result_index=result_index, request=req, db=db)
