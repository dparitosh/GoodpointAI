import logging
import json
import os
from typing import List, Dict, Optional, Any
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from datetime import datetime
import neo4j
import asyncio

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/data-sources", tags=["Data Sources"])

class DataSourceConnection(BaseModel):
    host: Optional[str] = None
    port: Optional[str] = None
    database: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    uri: Optional[str] = None
    api_key: Optional[str] = None
    endpoint: Optional[str] = None
    file_path: Optional[str] = None
    connection_string: Optional[str] = None

class DataSource(BaseModel):
    id: Optional[str] = None
    name: str
    type: str = Field(..., description="Type of data source: database, neo4j, mongodb, api, file, etc.")
    connection: DataSourceConnection
    description: Optional[str] = ""
    status: str = "inactive"
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    last_tested: Optional[str] = None
    test_result: Optional[str] = None

class DataSourceResponse(BaseModel):
    status: str
    message: str
    data: Optional[Any] = None

class TestConnectionResponse(BaseModel):
    success: bool
    message: str
    details: Optional[Dict] = None

# In-memory storage for data sources (in production, use a database)
DATA_SOURCES_FILE = "data_sources.json"

def load_data_sources() -> List[Dict]:
    """Load data sources from JSON file"""
    try:
        if os.path.exists(DATA_SOURCES_FILE):
            with open(DATA_SOURCES_FILE, 'r') as f:
                return json.load(f)
        return []
    except Exception as e:
        logger.error(f"Error loading data sources: {e}")
        return []

def save_data_sources(sources: List[Dict]):
    """Save data sources to JSON file"""
    try:
        with open(DATA_SOURCES_FILE, 'w') as f:
            json.dump(sources, f, indent=2, default=str)
    except Exception as e:
        logger.error(f"Error saving data sources: {e}")
        raise HTTPException(status_code=500, detail="Failed to save data sources")

@router.get(
    "/",
    response_model=List[DataSource],
    summary="Get All Data Sources",
    description="Retrieve all configured data sources."
)
async def get_data_sources():
    """Get all data sources"""
    try:
        sources = load_data_sources()
        return sources
    except Exception as e:
        logger.error(f"Error fetching data sources: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch data sources")

@router.get(
    "/{source_id}",
    response_model=DataSource,
    summary="Get Data Source by ID",
    description="Retrieve a specific data source by its ID."
)
async def get_data_source(source_id: str):
    """Get a specific data source by ID"""
    try:
        sources = load_data_sources()
        source = next((s for s in sources if s.get('id') == source_id), None)
        if not source:
            raise HTTPException(status_code=404, detail="Data source not found")
        return source
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching data source {source_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch data source")

@router.post(
    "/",
    response_model=DataSourceResponse,
    summary="Create Data Source",
    description="Create a new data source configuration."
)
async def create_data_source(source: DataSource):
    """Create a new data source"""
    try:
        sources = load_data_sources()
        
        # Generate ID if not provided
        if not source.id:
            source.id = f"ds_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{len(sources)}"
        
        # Check if ID already exists
        if any(s.get('id') == source.id for s in sources):
            raise HTTPException(status_code=400, detail="Data source ID already exists")
        
        # Set timestamps
        source.created_at = datetime.now().isoformat()
        source.updated_at = datetime.now().isoformat()
        
        # Convert to dict and add to sources
        source_dict = source.dict()
        sources.append(source_dict)
        
        # Save to file
        save_data_sources(sources)
        
        return DataSourceResponse(
            status="success",
            message="Data source created successfully",
            data=source_dict
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating data source: {e}")
        raise HTTPException(status_code=500, detail="Failed to create data source")

@router.put(
    "/{source_id}",
    response_model=DataSourceResponse,
    summary="Update Data Source",
    description="Update an existing data source configuration."
)
async def update_data_source(source_id: str, source: DataSource):
    """Update an existing data source"""
    try:
        sources = load_data_sources()
        
        # Find the source to update
        source_index = next((i for i, s in enumerate(sources) if s.get('id') == source_id), None)
        if source_index is None:
            raise HTTPException(status_code=404, detail="Data source not found")
        
        # Update the source
        source.id = source_id
        source.updated_at = datetime.now().isoformat()
        # Preserve created_at if it exists
        if 'created_at' in sources[source_index]:
            source.created_at = sources[source_index]['created_at']
        
        sources[source_index] = source.dict()
        
        # Save to file
        save_data_sources(sources)
        
        return DataSourceResponse(
            status="success",
            message="Data source updated successfully",
            data=sources[source_index]
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating data source {source_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to update data source")

@router.delete(
    "/{source_id}",
    response_model=DataSourceResponse,
    summary="Delete Data Source",
    description="Delete a data source configuration."
)
async def delete_data_source(source_id: str):
    """Delete a data source"""
    try:
        sources = load_data_sources()
        
        # Find and remove the source
        original_count = len(sources)
        sources = [s for s in sources if s.get('id') != source_id]
        
        if len(sources) == original_count:
            raise HTTPException(status_code=404, detail="Data source not found")
        
        # Save updated sources
        save_data_sources(sources)
        
        return DataSourceResponse(
            status="success",
            message="Data source deleted successfully"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting data source {source_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete data source")

@router.post(
    "/{source_id}/test",
    response_model=TestConnectionResponse,
    summary="Test Data Source Connection",
    description="Test the connection to a data source."
)
async def test_data_source_connection(source_id: str):
    """Test connection to a data source"""
    try:
        logger.info(f"Testing connection for data source: {source_id}")
        sources = load_data_sources()
        source = next((s for s in sources if s.get('id') == source_id), None)
        
        if not source:
            logger.error(f"Data source not found: {source_id}")
            raise HTTPException(status_code=404, detail="Data source not found")
        
        logger.info(f"Found data source: {source.get('name')}, type: {source.get('type')}")
        
        # Test connection based on source type
        test_result = await _test_connection(source)
        logger.info(f"Connection test result: {test_result.success}, message: {test_result.message}")
        
        # Update source with test results
        for i, s in enumerate(sources):
            if s.get('id') == source_id:
                sources[i]['last_tested'] = datetime.now().isoformat()
                sources[i]['test_result'] = 'success' if test_result.success else 'failed'
                sources[i]['status'] = 'active' if test_result.success else 'error'
                break
        
        save_data_sources(sources)
        
        return test_result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error testing data source {source_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to test data source connection: {str(e)}")

async def _test_connection(source: Dict) -> TestConnectionResponse:
    """Test connection based on source type"""
    source_type = source.get('type', '').lower()
    connection = source.get('connection', {})
    
    try:
        if source_type == 'neo4j':
            return await _test_neo4j_connection(connection)
        elif source_type == 'database':
            return await _test_database_connection(connection)
        elif source_type == 'mongodb':
            return await _test_mongodb_connection(connection)
        elif source_type == 'api':
            return await _test_api_connection(connection)
        elif source_type == 'file':
            return await _test_file_connection(connection)
        else:
            return TestConnectionResponse(
                success=False,
                message=f"Unsupported data source type: {source_type}"
            )
    except Exception as e:
        return TestConnectionResponse(
            success=False,
            message=f"Connection test failed: {str(e)}"
        )

async def _test_neo4j_connection(connection: Dict) -> TestConnectionResponse:
    """Test Neo4j connection"""
    try:
        uri = connection.get('uri') or f"bolt://{connection.get('host', 'localhost')}:{connection.get('port', '7687')}"
        username = connection.get('username', 'neo4j')
        password = connection.get('password', '')
        database = connection.get('database', 'neo4j')
        
        driver = neo4j.AsyncGraphDatabase.driver(uri, auth=(username, password))
        
        async with driver.session(database=database) as session:
            result = await session.run("RETURN 1 as test")
            await result.single()
        
        await driver.close()
        
        return TestConnectionResponse(
            success=True,
            message="Neo4j connection successful",
            details={"database": database, "uri": uri}
        )
    except Exception as e:
        return TestConnectionResponse(
            success=False,
            message=f"Neo4j connection failed: {str(e)}"
        )

async def _test_database_connection(connection: Dict) -> TestConnectionResponse:
    """Test SQL database connection (basic validation)"""
    try:
        # Basic validation of required fields
        required_fields = ['host', 'database', 'username']
        missing_fields = [field for field in required_fields if not connection.get(field)]
        
        if missing_fields:
            return TestConnectionResponse(
                success=False,
                message=f"Missing required fields: {', '.join(missing_fields)}"
            )
        
        # In a real implementation, you would test the actual database connection
        # For now, we'll just validate the configuration
        return TestConnectionResponse(
            success=True,
            message="Database configuration validated (connection test would require database driver)",
            details={"host": connection.get('host'), "database": connection.get('database')}
        )
    except Exception as e:
        return TestConnectionResponse(
            success=False,
            message=f"Database validation failed: {str(e)}"
        )

async def _test_mongodb_connection(connection: Dict) -> TestConnectionResponse:
    """Test MongoDB connection (basic validation)"""
    try:
        required_fields = ['host', 'database']
        missing_fields = [field for field in required_fields if not connection.get(field)]
        
        if missing_fields:
            return TestConnectionResponse(
                success=False,
                message=f"Missing required fields: {', '.join(missing_fields)}"
            )
        
        return TestConnectionResponse(
            success=True,
            message="MongoDB configuration validated (connection test would require MongoDB driver)",
            details={"host": connection.get('host'), "database": connection.get('database')}
        )
    except Exception as e:
        return TestConnectionResponse(
            success=False,
            message=f"MongoDB validation failed: {str(e)}"
        )

async def _test_api_connection(connection: Dict) -> TestConnectionResponse:
    """Test API connection"""
    try:
        endpoint = connection.get('endpoint')
        if not endpoint:
            return TestConnectionResponse(
                success=False,
                message="API endpoint is required"
            )
        
        # In a real implementation, you would make an HTTP request to test the API
        return TestConnectionResponse(
            success=True,
            message="API endpoint configuration validated (actual test would require HTTP client)",
            details={"endpoint": endpoint}
        )
    except Exception as e:
        return TestConnectionResponse(
            success=False,
            message=f"API validation failed: {str(e)}"
        )

async def _test_file_connection(connection: Dict) -> TestConnectionResponse:
    """Test file connection"""
    try:
        file_path = connection.get('file_path')
        if not file_path:
            return TestConnectionResponse(
                success=False,
                message="File path is required"
            )
        
        if os.path.exists(file_path):
            return TestConnectionResponse(
                success=True,
                message="File exists and is accessible",
                details={"file_path": file_path, "size": os.path.getsize(file_path)}
            )
        else:
            return TestConnectionResponse(
                success=False,
                message="File not found or not accessible"
            )
    except Exception as e:
        return TestConnectionResponse(
            success=False,
            message=f"File validation failed: {str(e)}"
        )

@router.get(
    "/types/supported",
    summary="Get Supported Data Source Types",
    description="Get list of supported data source types and their configuration requirements."
)
async def get_supported_types():
    """Get supported data source types"""
    return {
        "database": {
            "name": "SQL Database",
            "fields": ["host", "port", "database", "username", "password"],
            "default_port": "5432",
            "description": "PostgreSQL, MySQL, SQL Server, etc."
        },
        "neo4j": {
            "name": "Neo4j Graph Database",
            "fields": ["uri", "username", "password", "database"],
            "default_port": "7687",
            "description": "Neo4j graph database"
        },
        "mongodb": {
            "name": "MongoDB",
            "fields": ["host", "port", "database", "username", "password"],
            "default_port": "27017",
            "description": "MongoDB document database"
        },
        "api": {
            "name": "REST API",
            "fields": ["endpoint", "api_key"],
            "description": "REST API endpoint"
        },
        "file": {
            "name": "File System",
            "fields": ["file_path"],
            "description": "CSV, JSON, XML, Excel files"
        }
    }
