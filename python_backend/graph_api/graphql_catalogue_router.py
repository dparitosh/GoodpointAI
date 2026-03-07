"""
GraphQL Catalogue Router - CRUD operations for persisted queries and schema cache.
Manages query registry with unique name constraints.
"""

from fastapi import APIRouter, HTTPException, Depends, Query, Response
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
import logging

from services.graphql_catalogue_service import GraphQLCatalogueService
from core.db_session import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/graphql/catalogue", tags=["graphql-catalogue"])


# Pydantic Models

class CreateQueryRequest(BaseModel):
    name: str = Field(..., description="Unique query name")
    query: str = Field(..., description="Query string")
    description: Optional[str] = Field(default=None, description="Query description")
    variables: Optional[Dict[str, Any]] = Field(default=None, description="Query variables")
    format: str = Field(default="json", description="Query format: 'xml' or 'json'")
    created_by: Optional[str] = Field(default=None, description="Creator identifier")
    tags: Optional[List[str]] = Field(default=None, description="Tags for categorization")


class UpdateQueryRequest(BaseModel):
    query: Optional[str] = None
    description: Optional[str] = None
    variables: Optional[Dict[str, Any]] = None
    format: Optional[str] = None
    tags: Optional[List[str]] = None


class QueryResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    query: str
    variables: Dict[str, Any]
    format: str
    created_at: str
    updated_at: str
    created_by: Optional[str]
    tags: List[str]


def get_catalogue_service(db: Session = Depends(get_db)) -> GraphQLCatalogueService:
    """Dependency to get catalogue service instance."""
    return GraphQLCatalogueService(db)


@router.get("/queries", response_model=List[QueryResponse])
async def list_queries(
    response: Response,
    # Keep existing params for compatibility; also accept skip/limit.
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    skip: int = Query(0, ge=0),
    query_format: Optional[str] = Query(None, alias="format"),
    service: GraphQLCatalogueService = Depends(get_catalogue_service)
):
    """
    List persisted queries ordered by updated_at descending.
    
    - **limit**: Maximum queries to return (default: 100)
    - **offset**: Number of queries to skip (default: 0)
    - **format**: Optional filter by format ('xml' or 'json')
    """
    try:
        # Prefer skip if provided; keep offset for backward compatibility.
        effective_offset = skip if skip else offset
        queries = service.list_queries(limit=limit, offset=effective_offset, query_format=query_format)

        # Service doesn't expose total counts yet; emit best-effort header.
        response.headers["X-Total-Count"] = str(len(queries))

        return queries
    except Exception as e:
        logger.error("List queries failed: %s", str(e))
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/queries/{query_id}", response_model=QueryResponse)
async def get_query(
    query_id: int,
    service: GraphQLCatalogueService = Depends(get_catalogue_service)
):
    """
    Get a specific persisted query by ID.
    """
    try:
        query = service.get_query(query_id=query_id)
        if not query:
            raise HTTPException(status_code=404, detail=f"Query with ID {query_id} not found")
        return query
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Get query failed: %s", str(e))
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/queries/by-name/{name}", response_model=QueryResponse)
async def get_query_by_name(
    name: str,
    service: GraphQLCatalogueService = Depends(get_catalogue_service)
):
    """
    Get a specific persisted query by name.
    """
    try:
        query = service.get_query(name=name)
        if not query:
            raise HTTPException(status_code=404, detail=f"Query '{name}' not found")
        return query
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Get query by name failed: %s", str(e))
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/queries", response_model=QueryResponse, status_code=201)
async def create_query(
    request: CreateQueryRequest,
    service: GraphQLCatalogueService = Depends(get_catalogue_service)
):
    """
    Create a new persisted query.
    
    Name must be unique. Returns 400 if name already exists.
    """
    try:
        query = service.create_query(
            name=request.name,
            query=request.query,
            description=request.description,
            variables=request.variables,
            query_format=request.format,
            created_by=request.created_by,
            tags=request.tags
        )
        return query
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.error("Create query failed: %s", str(e))
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.patch("/queries/{query_id}", response_model=QueryResponse)
async def update_query(
    query_id: int,
    request: UpdateQueryRequest,
    service: GraphQLCatalogueService = Depends(get_catalogue_service)
):
    """
    Update an existing persisted query.
    
    Only provided fields will be updated.
    Returns 404 if query not found.
    """
    try:
        # Filter out None values
        updates = {k: v for k, v in request.model_dump().items() if v is not None}
        
        query = service.update_query(query_id, **updates)
        if not query:
            raise HTTPException(status_code=404, detail=f"Query with ID {query_id} not found")
        return query
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Update query failed: %s", str(e))
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.delete("/queries/{query_id}", status_code=204)
async def delete_query(
    query_id: int,
    service: GraphQLCatalogueService = Depends(get_catalogue_service)
):
    """
    Delete a persisted query.
    
    Returns 204 on success, 404 if not found.
    """
    try:
        deleted = service.delete_query(query_id)
        if not deleted:
            raise HTTPException(status_code=404, detail=f"Query with ID {query_id} not found")
        return None
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Delete query failed: %s", str(e))
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/schemas")
async def list_schemas(
    response: Response,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    skip: int = Query(0, ge=0),
    service: GraphQLCatalogueService = Depends(get_catalogue_service)
):
    """
    List cached schemas ordered by updated_at descending.
    """
    try:
        effective_offset = skip if skip else offset
        schemas = service.list_schemas(limit=limit, offset=effective_offset)

        # Service doesn't expose total counts yet; emit best-effort header.
        response.headers["X-Total-Count"] = str(len(schemas))
        return {"schemas": schemas}
    except Exception as e:
        logger.error("List schemas failed: %s", str(e))
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.delete("/schemas/{schema_id}", status_code=204)
async def delete_schema(
    schema_id: int,
    service: GraphQLCatalogueService = Depends(get_catalogue_service)
):
    """
    Delete a cached schema.
    """
    try:
        deleted = service.delete_schema(schema_id)
        if not deleted:
            raise HTTPException(status_code=404, detail=f"Schema with ID {schema_id} not found")
        return None
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Delete schema failed: %s", str(e))
        raise HTTPException(status_code=500, detail=str(e)) from e
