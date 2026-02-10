"""
Neo4j GraphRAG Router - REST API for hybrid search and semantic queries.
Bridges Neo4j graph context with OpenSearch vector similarity.
"""

from datetime import datetime
from fastapi import APIRouter, HTTPException, Query, Response
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from functools import lru_cache
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/neo4j-graphrag", tags=["neo4j-graphrag"])


@lru_cache(maxsize=1)
def _get_service_cached() -> Any:
    from services.neo4j_graphrag_service import Neo4jGraphRAGService

    return Neo4jGraphRAGService()


def get_service() -> Any:
    """Get or create Neo4j GraphRAG service instance."""
    try:
        return _get_service_cached()
    except ImportError:
        raise
    except Exception as e:
        logger.error("Failed to initialize Neo4j GraphRAG service: %s", e)
        raise HTTPException(status_code=500, detail="Service initialization failed") from e


# Pydantic Models

class GraphRAGQueryRequest(BaseModel):
    question: str = Field(..., description="User question or query")
    context: Optional[str] = Field(default=None, description="Optional context to enhance query")
    tools: Optional[List[str]] = Field(default=None, description="Optional tools to invoke")
    top_k: int = Field(default=5, ge=1, le=50, description="Number of top results (1-50)")
    include_paths: bool = Field(default=False, description="Include graph paths in results")
    embedding: Optional[List[float]] = Field(default=None, description="Optional embedding vector for the query")


class GraphRAGQueryResponse(BaseModel):
    answers: List[str]
    sources: List[Dict[str, Any]]
    tools_invoked: List[Dict[str, Any]]
    latency_ms: int
    result_count: int
    timestamp: str
    error: Optional[str] = None


class HealthResponse(BaseModel):
    status: str
    neo4j_connected: bool
    embedding_dimension: int
    timestamp: str


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Check Neo4j GraphRAG service health.
    
    Returns connection status and configuration.
    Handles import errors gracefully if neo4j driver not installed.
    """
    try:
        service = get_service()
        health_data = service.health_check()
        return health_data
    
    except ImportError as e:
        logger.warning("Neo4j driver import error: %s", e)
        return {
            "status": "degraded",
            "neo4j_connected": False,
            "embedding_dimension": 0,
            "timestamp": datetime.now().isoformat(),
            "error": "Neo4j driver not installed"
        }
    
    except Exception as e:
        logger.warning("Neo4j GraphRAG health check unavailable: %s", e)
        return {
            "status": "unavailable",
            "neo4j_connected": False,
            "embedding_dimension": 0,
            "timestamp": datetime.now().isoformat(),
            "error": str(e),
        }


@router.post("/query", response_model=GraphRAGQueryResponse)
async def execute_graphrag_query(request: GraphRAGQueryRequest):
    """
    Execute hybrid GraphRAG query.
    
    Combines:
    - Vector similarity search on Neo4j embeddings
    - Metadata-based filtering
    - Optional graph path traversal
    - Tool invocation for post-processing
    
    Args:
    - **question**: User question (required)
    - **context**: Additional context to enhance search
    - **tools**: List of tools to invoke (e.g., ['summarize', 'extract_entities'])
    - **top_k**: Number of results to return (default: 5, max: 50)
    - **include_paths**: Whether to include graph relationship paths
    
    Returns structured response with answers, sources, and metrics.
    Includes latency measurement for observability.
    """
    try:
        service = get_service()
        
        result = service.run_query(
            question=request.question,
            context=request.context,
            tools=request.tools,
            top_k=request.top_k,
            include_paths=request.include_paths,
            embedding=request.embedding,
        )
        
        return result
    
    except Exception as e:
        logger.error("GraphRAG query execution failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/tools")
async def list_tools(
    response: Response,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
):
    """
    List available tools for GraphRAG queries.

    Returns metadata about available post-processing tools
    that can be invoked via the tools[] parameter in queries.
    """
    try:
        service = get_service()
        tools = service.list_tools()
        response.headers["X-Total-Count"] = str(len(tools))
        return {"tools": tools[skip : skip + limit]}
    except Exception as e:
        logger.error("List tools failed: %s", str(e))
        raise HTTPException(status_code=500, detail=str(e)) from e
