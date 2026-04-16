import logging
import os
from datetime import datetime
from typing import Any, cast
from time import perf_counter

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.requests import Request
from starlette.responses import Response

from core.lifespan import lifespan_manager
from core.security_middleware import (
    InMemoryRateLimiter,
    enforce_api_key_if_configured,
    enforce_rate_limit,
)
from core.error_handlers import (
    http_exception_handler,
    unhandled_exception_handler,
    validation_exception_handler,
)
from graph_api.router import router as graph_router
from graph_api.data_analysis_router import router as data_analysis_router
from graph_api.monitoring_router import router as monitoring_router
from graph_api.config_router import router as config_router
from graph_api.data_sources_router import router as data_sources_router
from graph_api.data_sources_alias_router import router as data_sources_alias_router
from graph_api.data_mapping_router import router as data_mapping_router
from graph_api.migration_router import router as migration_router
from graph_api.analytics_router import router as analytics_router
from graph_api.reporting_services import router as reporting_router
from graph_api.graphql_router import router as graphql_router
from graph_api.graphql_catalogue_router import router as graphql_catalogue_router
from graph_api.neo4j_graphrag_router import router as neo4j_graphrag_router
from graph_api.agentic_router import router as agentic_router
from graph_api.report_hub_router import router as report_hub_router
from graph_api.quality_router import router as quality_router
from graph_api.agentic_config_router import router as agentic_config_router
from graph_api.plm_workflow_router import router as plm_workflow_router
from graph_api.plm_etl_router import router as plm_etl_router
from graph_api.etl_router import router as etl_router
from graph_api.workflow_manager_router import router as workflow_manager_router
from graph_api.azure_integration_router import router as azure_integration_router
from graph_api.aws_integration_router import router as aws_integration_router
from graph_api.odata_integration_router import router as odata_integration_router
from graph_api.llm_integration_router import router as llm_integration_router
from graph_api.plm_systems_integration_router import router as plm_systems_integration_router
from graph_api.filesystem_integration_router import router as filesystem_integration_router
from graph_api.api_gateway_router import router as api_gateway_router
from graph_api.lineage_router import router as lineage_router
from graph_api.self_healing_router import router as self_healing_router
from graph_api.multimodal_router import router as multimodal_router
from graph_api.compat_router import router as compat_router
from graph_api.auth_router import router as auth_router
from graph_api.opensearch_router import router as opensearch_router
from graph_api.reports_router import router as reports_router
from graph_api.rule_engine_router import router as rule_engine_router
from graph_api.rule_router import router as rule_router
from graph_api.export_router import router as export_router
from graph_api.workflow_router import router as workflow_router
from routers.pipeline_config_router import router as pipeline_config_router
from routers.conversational_search_router import router as conversational_search_router
from routers.admin_config_router import router as admin_config_router

from core.auth import auth_required, get_request_principal
from core.config_store import get_encrypted_config_payload
from services.mcp_client import mcp_client as _mcp_client

# --- Setup Logging ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

logger.info("Loaded FastAPI app module from %s", __file__)

# Load repo-local `.env` early (for local dev) when explicitly enabled.
# The VS Code tasks set GRAPH_TRACE_LOAD_DOTENV=true.
try:
    import core.external_config as _external_config  # noqa: F401
except Exception:  # pylint: disable=broad-exception-caught
    # Non-fatal: app can still start with environment/DB-backed config.
    pass


def _best_effort_seed_config() -> None:
    # Seeding is now done exclusively in the lifespan startup (after DB connectivity
    # is verified). The early import-time call was removed to avoid double-seeding
    # and to prevent synchronous DB access before the event loop is ready.
    pass


def _expand_localhost_origin_variants(origins: list[str]) -> list[str]:
    """Expand localhost/127.0.0.1 equivalents without broadening to new hosts.

    This prevents surprising dev-only CORS failures when one side uses
    http://localhost:* and the other uses http://127.0.0.1:*.
    """

    expanded: list[str] = []
    seen: set[str] = set()

    def _add(origin: str) -> None:
        o = origin.strip()
        if not o or o in seen:
            return
        seen.add(o)
        expanded.append(o)

    for origin in origins:
        o = str(origin).strip()
        if not o:
            continue

        _add(o)

        for scheme in ("http://", "https://"):
            if o.startswith(f"{scheme}localhost:"):
                _add(o.replace(f"{scheme}localhost:", f"{scheme}127.0.0.1:", 1))
            elif o.startswith(f"{scheme}127.0.0.1:"):
                _add(o.replace(f"{scheme}127.0.0.1:", f"{scheme}localhost:", 1))

    return expanded


def _get_allowed_origins() -> list[str]:
    cors_cfg = get_encrypted_config_payload("cors")
    if isinstance(cors_cfg, dict):
        origins = cors_cfg.get("allowed_origins")
        if isinstance(origins, list):
            cleaned = [str(o).strip() for o in origins if str(o).strip()]
            if cleaned:
                return _expand_localhost_origin_variants(cleaned)

    env_origins = [
        origin.strip()
        for origin in (os.getenv("ALLOWED_ORIGINS") or "").split(",")
        if origin.strip()
    ]
    if env_origins:
        return _expand_localhost_origin_variants(env_origins)

    return _expand_localhost_origin_variants([
        "http://localhost:3000",  # Replace with the origin of your frontend
        "http://127.0.0.1:3000",
        "http://localhost:8011",
        "http://127.0.0.1:8011",
        "http://localhost:5173",  # For Swagger UI/docs
        "http://127.0.0.1:5173",
        "http://localhost:5174",  # Updated Vite dev server port
        "http://127.0.0.1:5174",
        "http://localhost:5175",  # Additional Vite port
        "http://127.0.0.1:5175",
        "http://localhost:5176",  # Additional Vite port
        "http://127.0.0.1:5176",
    ])


_best_effort_seed_config()

app = FastAPI(
    title="GoodPoint AgenticAI API",
    description="AI-powered PLM data migration and graph visualization with multi-agent orchestration.",
    version="2.0.0",
    lifespan=lifespan_manager
)


_rate_limiter = InMemoryRateLimiter(
    limit_per_minute=int((os.getenv("RATE_LIMIT_PER_MINUTE") or "240").strip() or 240)
)


@app.middleware("http")
async def request_timing_middleware(request: Request, call_next):
    start = perf_counter()
    # Security and abuse-prevention (Pareto: prevents most outages/exposure).
    auth_response = enforce_api_key_if_configured(request)
    if auth_response is not None:
        return auth_response
    limited = enforce_rate_limit(request, _rate_limiter)
    if limited is not None:
        return limited

    # Canonical health endpoint: bypass routing so we don't get surprised by
    # duplicate /health handlers from included routers.
    if request.method == "GET" and request.url.path == "/health":
        db_ok = bool(getattr(app.state, "db_ok", False))
        neo4j_ok = bool(getattr(app.state, "neo4j_ok", False))
        
        # Check MCP Server Health
        mcp_ok = await _mcp_client.check_health()
        
        overall = "healthy" if (db_ok and neo4j_ok and mcp_ok) else "degraded"
        # Return 503 when degraded so load-balancers/k8s pull the instance.
        http_status = 200 if overall == "healthy" else 503
        response = JSONResponse(
            status_code=http_status,
            content={
                "status": overall,
                "service": "GoodPoint AgenticAI API",
                "timestamp": datetime.now().isoformat(),
                "dependencies": {
                    "postgres": {"ok": db_ok},
                    "neo4j": {"ok": neo4j_ok},
                    "mcp_server": {"ok": mcp_ok}
                },
            },
        )
        duration_ms = (perf_counter() - start) * 1000.0
        principal = get_request_principal(request)
        logger.info(
            "HTTP %s %s -> %s (%.2fms) user=%s auth=%s",
            request.method,
            request.url.path,
            getattr(response, "status_code", "?"),
            duration_ms,
            principal.subject if principal else "anonymous",
            principal.auth_type if principal else "none",
        )
        return response

    # Minimal RBAC (only when auth is enabled): require "admin" for mutating API calls.
    if auth_required() and request.url.path.startswith("/api") and request.method in {"POST", "PUT", "PATCH", "DELETE"}:
        # Allow login/token issuance without being logged in.
        if not request.url.path.startswith("/api/auth"):
            principal = get_request_principal(request)
            if principal is None:
                return JSONResponse(status_code=401, content={"detail": "Unauthorized"})
            if "admin" not in principal.roles:
                return JSONResponse(status_code=403, content={"detail": "Forbidden"})

    response = await call_next(request)
    duration_ms = (perf_counter() - start) * 1000.0
    principal = get_request_principal(request)
    logger.info(
        "HTTP %s %s -> %s (%.2fms) user=%s auth=%s",
        request.method,
        request.url.path,
        getattr(response, "status_code", "?"),
        duration_ms,
        principal.subject if principal else "anonymous",
        principal.auth_type if principal else "none",
    )
    return response

async def _http_exception_handler(request: Request, exc: Exception) -> Response:
    return await cast(Any, http_exception_handler)(request, exc)


async def _validation_exception_handler(request: Request, exc: Exception) -> Response:
    return await cast(Any, validation_exception_handler)(request, exc)


async def _unhandled_exception_handler(request: Request, exc: Exception) -> Response:
    return await cast(Any, unhandled_exception_handler)(request, exc)


app.add_exception_handler(StarletteHTTPException, _http_exception_handler)
app.add_exception_handler(RequestValidationError, _validation_exception_handler)
app.add_exception_handler(Exception, _unhandled_exception_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_get_allowed_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(graph_router)
app.include_router(data_analysis_router)
app.include_router(monitoring_router)
app.include_router(config_router)
app.include_router(reports_router)
app.include_router(data_sources_router)
app.include_router(data_sources_alias_router)
app.include_router(data_mapping_router)
app.include_router(migration_router)
app.include_router(analytics_router)
app.include_router(reporting_router)
app.include_router(graphql_router)
app.include_router(graphql_catalogue_router)
app.include_router(neo4j_graphrag_router)
app.include_router(agentic_router)
app.include_router(report_hub_router)
app.include_router(quality_router)
app.include_router(agentic_config_router)
app.include_router(plm_workflow_router)
app.include_router(plm_etl_router)
app.include_router(etl_router)
app.include_router(workflow_manager_router)
app.include_router(rule_router)
app.include_router(export_router)
app.include_router(workflow_router)
app.include_router(azure_integration_router)
app.include_router(aws_integration_router)
app.include_router(odata_integration_router)
app.include_router(llm_integration_router)
app.include_router(plm_systems_integration_router)
app.include_router(filesystem_integration_router)
app.include_router(api_gateway_router)
app.include_router(lineage_router)
app.include_router(self_healing_router)
app.include_router(multimodal_router)
app.include_router(compat_router)
app.include_router(auth_router)
app.include_router(opensearch_router)
app.include_router(rule_engine_router)
app.include_router(pipeline_config_router)
app.include_router(conversational_search_router)
app.include_router(admin_config_router)


@app.get("/health", tags=["Health"], summary="Health check endpoint")
async def root_health_check():
    db_ok = bool(getattr(app.state, "db_ok", False))
    neo4j_ok = bool(getattr(app.state, "neo4j_ok", False))
    mcp_ok = await _mcp_client.check_health()
    overall = "healthy" if (db_ok and neo4j_ok and mcp_ok) else "degraded"
    http_status = 200 if overall == "healthy" else 503
    return JSONResponse(
        status_code=http_status,
        content={
            "status": overall,
            "service": "GoodPoint AgenticAI API",
            "timestamp": datetime.now().isoformat(),
            "dependencies": {
                "postgres": {"ok": db_ok},
                "neo4j": {"ok": neo4j_ok},
                "mcp_server": {"ok": mcp_ok},
            },
        },
    )

if __name__ == "__main__":
    import uvicorn
    logger.info("Starting Uvicorn server for GraphTrace API...")
    uvicorn.run(app, host="0.0.0.0", port=8011)
