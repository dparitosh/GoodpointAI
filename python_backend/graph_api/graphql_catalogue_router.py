"""
GraphQL Catalogue Router - CRUD operations for persisted queries and schema cache.
Manages query registry with unique name constraints.
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
import logging

from python_backend.services.graphql_catalogue_service import GraphQLCatalogueService

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


# Mock dependency - in production, use actual database session
def get_db_session():
    """
    Get database session dependency.
    In production, this should return SQLAlchemy session from connection pool.
    """
    # Mock session for now - replace with actual database integration
    class MockSession:
        def query(self, *args, **kwargs):
            return MockQuery()
        def add(self, *args, **kwargs):
            pass
        def commit(self):
            pass
        def rollback(self):
            pass
        def refresh(self, *args, **kwargs):
            pass
        def delete(self, *args, **kwargs):
            pass
    
    class MockQuery:
        def filter(self, *args, **kwargs):
            return self
        def order_by(self, *args, **kwargs):
            return self
        def limit(self, *args, **kwargs):
            return self
        def offset(self, *args, **kwargs):
            return self
        def first(self):
            return None
        def all(self):
            return []
    
    return MockSession()


def get_catalogue_service(db: Session = Depends(get_db_session)) -> GraphQLCatalogueService:
    """Dependency to get catalogue service instance."""
    return GraphQLCatalogueService(db)


@router.get("/queries", response_model=List[QueryResponse])
async def list_queries(
    limit: int = 100,
    offset: int = 0,
    format: Optional[str] = None,
    service: GraphQLCatalogueService = Depends(get_catalogue_service)
):
    """
    List persisted queries ordered by updated_at descending.
    
    - **limit**: Maximum queries to return (default: 100)
    - **offset**: Number of queries to skip (default: 0)
    - **format**: Optional filter by format ('xml' or 'json')
    """
    try:
        queries = service.list_queries(limit=limit, offset=offset, format=format)
        return queries
    except Exception as e:
        logger.error(f"List queries failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


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
        logger.error(f"Get query failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


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
        logger.error(f"Get query by name failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


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
            format=request.format,
            created_by=request.created_by,
            tags=request.tags
        )
        return query
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Create query failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


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
        updates = {k: v for k, v in request.dict().items() if v is not None}
        
        query = service.update_query(query_id, **updates)
        if not query:
            raise HTTPException(status_code=404, detail=f"Query with ID {query_id} not found")
        return query
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Update query failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


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
        logger.error(f"Delete query failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/schemas")
async def list_schemas(
    limit: int = 100,
    offset: int = 0,
    service: GraphQLCatalogueService = Depends(get_catalogue_service)
):
    """
    List cached schemas ordered by updated_at descending.
    """
    try:
        schemas = service.list_schemas(limit=limit, offset=offset)
        return {"schemas": schemas}
    except Exception as e:
        logger.error(f"List schemas failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


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
        logger.error(f"Delete schema failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
