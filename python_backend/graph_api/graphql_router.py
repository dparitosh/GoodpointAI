"""
GraphQL Router - REST API endpoints for GraphQL toolkit.
Provides schema introspection, query execution, and data transformation endpoints.
"""

from fastapi import APIRouter, HTTPException, UploadFile, File, Depends
from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any
import logging

from services.graphql_service import GraphQLService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/graphql", tags=["graphql"])

# Pydantic Models for API

class SchemaIntrospectionRequest(BaseModel):
    content: str = Field(..., description="Schema content (XML or JSON)")
    format: str = Field(..., description="Format type: 'xml' or 'json'")
    name: str = Field(..., description="Schema name for identification")


class SchemaIntrospectionResponse(BaseModel):
    name: str
    format: str
    schema_hash: str
    fields: Dict[str, Any]
    types: Dict[str, Any]
    metadata: Dict[str, Any]


class QueryRequest(BaseModel):
    query: str = Field(..., description="GraphQL-like query string")
    data: Dict[str, Any] = Field(..., description="Source data to query")
    variables: Optional[Dict[str, Any]] = Field(default=None, description="Query variables")


class QueryResponse(BaseModel):
    data: Optional[Dict[str, Any]]
    errors: List[Dict[str, Any]]


class MappingDefinition(BaseModel):
    source_field: str = Field(..., description="Source field path (dot notation)")
    target_field: str = Field(..., description="Target field path (dot notation)")
    transformation: Optional[str] = Field(default=None, description="Optional transformation")


class TransformRequest(BaseModel):
    source_data: Dict[str, Any] = Field(..., description="Source data dictionary")
    target_data: Dict[str, Any] = Field(default_factory=dict, description="Target data dictionary")
    mappings: List[MappingDefinition] = Field(..., description="Field mapping definitions")


class TransformResponse(BaseModel):
    transformed_data: Dict[str, Any]
    errors: List[Dict[str, Any]]
    mappings_applied: int
    mappings_failed: int


# Dependency for service
def get_graphql_service() -> GraphQLService:
    """Dependency to get GraphQL service instance."""
    return GraphQLService()


@router.post("/introspect", response_model=SchemaIntrospectionResponse)
async def introspect_schema(
    request: SchemaIntrospectionRequest,
    service: GraphQLService = Depends(get_graphql_service)
):
    """
    Introspect schema from XML or JSON content.
    
    - **content**: Schema content as string
    - **format**: Must be 'xml' or 'json'
    - **name**: Identifier for the schema
    
    Returns deterministic schema structure with fields and types mapping.
    """
    try:
        result = service.introspect_schema(
            content=request.content,
            data_format=request.format,
            name=request.name
        )
        return result
    
    except ValueError as e:
        logger.error("Schema introspection failed: %s", e)
        raise HTTPException(status_code=400, detail=str(e)) from e
    
    except Exception as e:
        logger.error("Unexpected error during introspection: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error") from e


@router.post("/upload-schema", response_model=SchemaIntrospectionResponse)
async def upload_schema(
    file: UploadFile = File(...),
    name: Optional[str] = None,
    service: GraphQLService = Depends(get_graphql_service)
):
    """
    Upload and introspect schema file (XML or JSON).
    
    - **file**: Schema file (.xml or .json)
    - **name**: Optional schema name (defaults to filename)
    
    Auto-detects format by file extension.
    Rejects non-XML/JSON files with 400 error.
    """
    # Determine format from filename
    if not file.filename:
        raise HTTPException(status_code=400, detail="Missing uploaded filename")

    filename = file.filename.lower()
    
    if filename.endswith('.xml'):
        format_type = 'xml'
    elif filename.endswith('.json'):
        format_type = 'json'
    else:
        raise HTTPException(
            status_code=400,
            detail="Invalid file type. Only .xml and .json files are supported."
        )
    
    # Use filename as name if not provided
    schema_name = name or file.filename.rsplit('.', 1)[0]
    
    try:
        # Read file content
        content = await file.read()
        content_str = content.decode('utf-8')
        
        # Introspect schema
        result = service.introspect_schema(
            content=content_str,
            data_format=format_type,
            name=schema_name
        )
        return result

    except UnicodeDecodeError as e:
        raise HTTPException(status_code=400, detail="File encoding must be UTF-8") from e

    except ValueError as e:
        logger.error("Schema upload failed: %s", e)
        raise HTTPException(status_code=400, detail=str(e)) from e
    
    except Exception as e:
        logger.error("Unexpected error during upload: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error") from e


@router.post("/query", response_model=QueryResponse)
async def execute_query(
    request: QueryRequest,
    service: GraphQLService = Depends(get_graphql_service)
):
    """
    Execute pseudo-GraphQL query against JSON data.
    
    - **query**: GraphQL-like query string with field selectors
    - **data**: Source JSON data payload
    - **variables**: Optional query variables (not yet implemented)
    
    Returns HTTP 200 with data or errors.
    Logical errors appear in errors[] array with data=null.
    Unexpected exceptions return HTTP 500.
    """
    try:
        result = service.execute_query(
            query=request.query,
            data=request.data,
            variables=request.variables
        )
        return result
    
    except Exception as e:
        logger.error("Query execution error: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error") from e


@router.post("/transform", response_model=TransformResponse)
async def transform_data(
    request: TransformRequest,
    service: GraphQLService = Depends(get_graphql_service)
):
    """
    Transform data using field mappings.
    
    - **source_data**: Source data dictionary
    - **target_data**: Target data dictionary (optional, defaults to empty)
    - **mappings**: Array of mapping definitions
    
    Each mapping specifies:
    - source_field: Field path in source data (dot notation)
    - target_field: Field path in target data (dot notation)
    - transformation: Optional inline transformation (uppercase, lowercase, trim, int, float, bool)
    
    Errors encountered per mapping append to response errors[] but do not abort entire transform.
    Returns statistics on mappings applied vs failed.
    """
    try:
        # Convert Pydantic models to dicts for service
        mappings_list = [m.dict() for m in request.mappings]
        
        result = service.transform_data(
            source_data=request.source_data,
            target_data=request.target_data,
            mappings=mappings_list
        )
        return result
    
    except Exception as e:
        logger.error("Transform error: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error") from e


@router.get("/health")
async def health_check():
    """
    Health check endpoint for GraphQL service.
    """
    return {
        "status": "healthy",
        "service": "graphql",
        "timestamp": "2025-11-23T16:30:00Z"
    }
