import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .core.lifespan import lifespan_manager
from .graph_api.router import router as graph_router
from .nifi_api.router import router as nifi_router
from .graph_api.reporting_services import router as reporting_router

# --- Setup Logging ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = FastAPI(
    title="GraphTrace API",
    description="API for interacting with a Neo4j graph database and visualizing trace data.",
    version="0.1.0",
    lifespan=lifespan_manager
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # Replace with the origin of your frontend
        "http://localhost:8000", 
        "http://localhost:5173", # For Swagger UI/docs
        "https://your-frontend-domain.com",  # Add other origins as needed
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(graph_router)
app.include_router(nifi_router)
app.include_router(reporting_router)

if __name__ == "__main__":
    import uvicorn
    logger.info("Starting Uvicorn server for GraphTrace API...")
    uvicorn.run(app, host="0.0.0.0", port=8000)
