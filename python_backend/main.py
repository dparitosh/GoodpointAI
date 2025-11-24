import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.lifespan import lifespan_manager
from graph_api.router import router as graph_router
from graph_api.data_analysis_router import router as data_analysis_router
from graph_api.monitoring_router import router as monitoring_router
from graph_api.config_router import router as config_router
from graph_api.data_sources_router import router as data_sources_router
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

# --- Setup Logging ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = FastAPI(
    title="GoodPoint AgenticAI API",
    description="AI-powered PLM data migration and graph visualization with multi-agent orchestration.",
    version="2.0.0",
    lifespan=lifespan_manager
)

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

if __name__ == "__main__":
    import uvicorn
    logger.info("Starting Uvicorn server for GraphTrace API...")
    uvicorn.run(app, host="0.0.0.0", port=8000)
