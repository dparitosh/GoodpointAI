import logging
from datetime import datetime
from typing import Any, cast
from time import perf_counter

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.requests import Request
from starlette.responses import Response

from core.lifespan import lifespan_manager
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
from graph_api.quality_router import router as quality_router
from graph_api.agentic_graph_router import router as agentic_graph_router
from graph_api.agentic_config_router import router as agentic_config_router
from graph_api.plm_workflow_router import router as plm_workflow_router
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

# --- Setup Logging ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = FastAPI(
    title="GoodPoint AgenticAI API",
    description="AI-powered PLM data migration and graph visualization with multi-agent orchestration.",
    version="2.0.0",
    lifespan=lifespan_manager
)


@app.middleware("http")
async def request_timing_middleware(request: Request, call_next):
    start = perf_counter()
    response = await call_next(request)
    duration_ms = (perf_counter() - start) * 1000.0
    logger.info(
        "HTTP %s %s -> %s (%.2fms)",
        request.method,
        request.url.path,
        getattr(response, "status_code", "?"),
        duration_ms,
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
    allow_origins=[
        "http://localhost:3000",  # Replace with the origin of your frontend
        "http://localhost:8000", 
        "http://localhost:5173", # For Swagger UI/docs
        "http://localhost:5174", # Updated Vite dev server port
        "http://localhost:5175", # Additional Vite port
        "http://localhost:5176", # Additional Vite port
        "https://your-frontend-domain.com",  # Add other origins as needed
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(graph_router)
app.include_router(data_analysis_router)
app.include_router(monitoring_router)
app.include_router(config_router)
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
app.include_router(quality_router)
app.include_router(agentic_graph_router)
app.include_router(agentic_config_router)
app.include_router(plm_workflow_router)
app.include_router(workflow_manager_router)
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


@app.get("/health", tags=["Health"], summary="Health check endpoint")
async def root_health_check():
    # Keep a simple top-level health alias for clients that expect /health.
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "service": "GoodPoint AgenticAI API",
    }

if __name__ == "__main__":
    import uvicorn
    logger.info("Starting Uvicorn server for GraphTrace API...")
    uvicorn.run(app, host="0.0.0.0", port=8000)
