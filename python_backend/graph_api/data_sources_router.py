import logging
import json
import os
from typing import List, Dict, Optional, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field, field_serializer
from datetime import datetime
import neo4j
from sqlalchemy.orm import Session

from core.crypto import decrypt_json, encrypt_json
from core.db_session import get_db
from models.configuration_models import DataSourceConfigRecord

# pylint: disable=broad-exception-caught

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

    @field_serializer("password", "api_key", "connection_string", when_used="json")
    def _hide_secrets_in_api(self, value):  # pylint: disable=unused-argument
        return None

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
    data: Optional[DataSource] = None

class TestConnectionResponse(BaseModel):
    success: bool
    message: str
    details: Optional[Dict] = None

# In-memory storage for data sources (in production, use a database)
DATA_SOURCES_FILE = "data_sources.json"

def _load_data_sources_legacy_file() -> List[Dict]:
    """Legacy loader for data_sources.json (migration fallback)."""
    try:
        if os.path.exists(DATA_SOURCES_FILE):
            with open(DATA_SOURCES_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, list) else []
        return []
    except (OSError, json.JSONDecodeError) as e:
        logger.error("Error loading legacy data sources: %s", e)
        return []

def _allowed_connection_keys() -> set[str]:
    if hasattr(DataSourceConnection, "model_fields"):
        return set(DataSourceConnection.model_fields.keys())
    return set(getattr(DataSourceConnection, "__fields__", {}).keys())


def _filter_connection_fields(connection: Dict[str, Any]) -> Dict[str, Any]:
    allowed = _allowed_connection_keys()
    return {k: v for k, v in (connection or {}).items() if k in allowed}


def _redact_connection(connection: Dict[str, Any]) -> Dict[str, Any]:
    """Return a sanitized copy of connection data."""
    redacted: Dict[str, Any] = {}
    sensitive_exact = {
        "password",
        "secret",
        "token",
        "api_key",
        "access_key",
        "sas",
        "connection_string",
    }
    sensitive_substrings = [
        "password",
        "secret",
        "token",
        "api_key",
        "access_key",
        "connection_string",
        "sas",
    ]
    for k, v in (connection or {}).items():
        key_lower = str(k).lower()
        if key_lower in sensitive_exact or any(s in key_lower for s in sensitive_substrings):
            redacted[k] = None
        else:
            redacted[k] = v
    return redacted


def _merge_connection_secrets(incoming: Dict[str, Any], existing: Dict[str, Any]) -> Dict[str, Any]:
    """Preserve existing secrets when the client sends empty or masked values."""
    merged = dict(incoming or {})
    for secret_key in ("password", "api_key", "connection_string"):
        incoming_val = merged.get(secret_key)
        if incoming_val in (None, "", "***"):
            existing_val = (existing or {}).get(secret_key)
            if existing_val:
                merged[secret_key] = existing_val
            else:
                merged.pop(secret_key, None)
    return merged


def _record_to_api(record: DataSourceConfigRecord, connection: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": record.id,
        "name": record.name,
        "type": record.type,
        "connection": _redact_connection(_filter_connection_fields(connection)),
        "description": record.description or "",
        "status": record.status,
        "created_at": record.created_at.isoformat() if record.created_at else None,
        "updated_at": record.updated_at.isoformat() if record.updated_at else None,
        "last_tested": record.last_tested.isoformat() if record.last_tested else None,
        "test_result": record.test_result,
    }

@router.get(
    "/",
    response_model=List[DataSource],
    summary="Get All Data Sources",
    description="Retrieve all configured data sources."
)
async def get_data_sources(
    response: Response,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=5000),
    db: Session = Depends(get_db),
):
    """Get all data sources (paged)."""
    try:
        total_count = db.query(DataSourceConfigRecord).count()
        response.headers["X-Total-Count"] = str(total_count)

        rows = (
            db.query(DataSourceConfigRecord)
            .order_by(DataSourceConfigRecord.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

        if not rows:
            legacy = _load_data_sources_legacy_file()
            # best-effort redaction for legacy payloads
            for item in legacy:
                if isinstance(item, dict) and isinstance(item.get("connection"), dict):
                    item["connection"] = _redact_connection(_filter_connection_fields(item["connection"]))
            response.headers["X-Total-Count"] = str(len(legacy))
            return legacy[skip : skip + limit]

        result: List[Dict[str, Any]] = []
        for row in rows:
            try:
                connection = decrypt_json(row.connection_ciphertext)
                if not isinstance(connection, dict):
                    connection = {}
            except ValueError as e:
                raise HTTPException(status_code=503, detail=str(e)) from e
            except Exception:
                connection = {}
            result.append(_record_to_api(row, connection))
        return result
    except (OSError, json.JSONDecodeError, ValueError, TypeError) as e:
        logger.error("Error fetching data sources: %s", e)
        raise HTTPException(status_code=500, detail="Failed to fetch data sources") from e


@router.get(
    "",
    response_model=List[DataSource],
    summary="Get All Data Sources (No Slash)",
    include_in_schema=False,
)
async def get_data_sources_no_slash(
    response: Response,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=5000),
    db: Session = Depends(get_db),
):
    # Avoid relying on redirect-slashes behavior when running behind proxies.
    return await get_data_sources(response=response, skip=skip, limit=limit, db=db)

@router.get(
    "/{source_id}",
    response_model=DataSource,
    summary="Get Data Source by ID",
    description="Retrieve a specific data source by its ID."
)
async def get_data_source(source_id: str, db: Session = Depends(get_db)):
    """Get a specific data source by ID"""
    try:
        row = db.get(DataSourceConfigRecord, source_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Data source not found")

        try:
            connection = decrypt_json(row.connection_ciphertext)
            if not isinstance(connection, dict):
                connection = {}
        except ValueError as e:
            raise HTTPException(status_code=503, detail=str(e)) from e
        except Exception:
            connection = {}

        return _record_to_api(row, connection)
    except (OSError, json.JSONDecodeError, ValueError, TypeError, KeyError) as e:
        logger.error("Error fetching data source %s: %s", source_id, e)
        raise HTTPException(status_code=500, detail="Failed to fetch data source") from e

@router.post(
    "/",
    response_model=DataSourceResponse,
    summary="Create Data Source",
    description="Create a new data source configuration."
)
async def create_data_source(source: DataSource, db: Session = Depends(get_db)):
    """Create a new data source"""
    try:
        # Generate ID if not provided
        if not source.id:
            source.id = f"ds_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{source.name.strip().replace(' ', '_')[:24]}"
        
        # Reject duplicates by id or name
        existing_by_id = db.get(DataSourceConfigRecord, source.id)
        if existing_by_id is not None:
            raise HTTPException(status_code=400, detail="Data source ID already exists")

        existing_by_name = (
            db.query(DataSourceConfigRecord)
            .filter(DataSourceConfigRecord.name == source.name)
            .first()
        )
        if existing_by_name is not None:
            raise HTTPException(status_code=400, detail="Data source name already exists")

        # Encrypt connection payload
        connection_payload = (
            source.connection.model_dump(mode="python", exclude_none=True)
            if hasattr(source.connection, "model_dump")
            else source.connection.dict(exclude_none=True)
        )

        try:
            ciphertext = encrypt_json(connection_payload)
        except ValueError as e:
            raise HTTPException(status_code=503, detail=str(e)) from e

        record = DataSourceConfigRecord(
            id=source.id,
            name=source.name,
            type=source.type,
            description=source.description,
            status=source.status or "inactive",
            connection_ciphertext=ciphertext,
        )
        db.add(record)
        db.commit()
        db.refresh(record)
        
        return DataSourceResponse(
            status="success",
            message="Data source created successfully",
            data=DataSource(**_record_to_api(record, connection_payload))
        )
    except (OSError, json.JSONDecodeError, ValueError, TypeError, KeyError) as e:
        logger.error("Error creating data source: %s", e)
        raise HTTPException(status_code=500, detail="Failed to create data source") from e


@router.post(
    "",
    response_model=DataSourceResponse,
    summary="Create Data Source (No Slash)",
    include_in_schema=False,
)
async def create_data_source_no_slash(source: DataSource, db: Session = Depends(get_db)):
    # Avoid relying on redirect-slashes behavior when running behind proxies.
    return await create_data_source(source=source, db=db)

@router.put(
    "/{source_id}",
    response_model=DataSourceResponse,
    summary="Update Data Source",
    description="Update an existing data source configuration."
)
async def update_data_source(source_id: str, source: DataSource, db: Session = Depends(get_db)):
    """Update an existing data source"""
    try:
        record = db.get(DataSourceConfigRecord, source_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Data source not found")

        # Enforce unique name (excluding this record)
        name_conflict = (
            db.query(DataSourceConfigRecord)
            .filter(DataSourceConfigRecord.name == source.name)
            .filter(DataSourceConfigRecord.id != source_id)
            .first()
        )
        if name_conflict is not None:
            raise HTTPException(status_code=400, detail="Data source name already exists")

        incoming_payload = (
            source.connection.model_dump(mode="python", exclude_none=True)
            if hasattr(source.connection, "model_dump")
            else source.connection.dict(exclude_none=True)
        )

        try:
            existing_connection = decrypt_json(record.connection_ciphertext)
            if not isinstance(existing_connection, dict):
                existing_connection = {}
        except Exception:
            existing_connection = {}

        connection_payload = _merge_connection_secrets(incoming_payload, existing_connection)

        record.name = source.name
        record.type = source.type
        record.description = source.description
        record.status = source.status or record.status
        try:
            record.connection_ciphertext = encrypt_json(connection_payload)
        except ValueError as e:
            raise HTTPException(status_code=503, detail=str(e)) from e
        db.commit()
        db.refresh(record)
        
        return DataSourceResponse(
            status="success",
            message="Data source updated successfully",
            data=DataSource(**_record_to_api(record, connection_payload))
        )
    except (OSError, json.JSONDecodeError, ValueError, TypeError, KeyError) as e:
        logger.error("Error updating data source %s: %s", source_id, e)
        raise HTTPException(status_code=500, detail="Failed to update data source") from e

@router.delete(
    "/{source_id}",
    response_model=DataSourceResponse,
    summary="Delete Data Source",
    description="Delete a data source configuration."
)
async def delete_data_source(source_id: str, db: Session = Depends(get_db)):
    """Delete a data source"""
    try:
        record = db.get(DataSourceConfigRecord, source_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Data source not found")

        db.delete(record)
        db.commit()
        
        return DataSourceResponse(
            status="success",
            message="Data source deleted successfully"
        )
    except (OSError, json.JSONDecodeError, ValueError, TypeError) as e:
        logger.error("Error deleting data source %s: %s", source_id, e)
        raise HTTPException(status_code=500, detail="Failed to delete data source") from e

@router.post(
    "/{source_id}/test",
    response_model=TestConnectionResponse,
    summary="Test Data Source Connection",
    description="Test the connection to a data source."
)
async def test_data_source_connection(source_id: str, db: Session = Depends(get_db)):
    """Test connection to a data source"""
    try:
        logger.info("Testing connection for data source: %s", source_id)
        record = db.get(DataSourceConfigRecord, source_id)
        if record is None:
            logger.error("Data source not found: %s", source_id)
            raise HTTPException(status_code=404, detail="Data source not found")

        try:
            connection = decrypt_json(record.connection_ciphertext)
            if not isinstance(connection, dict):
                connection = {}
        except ValueError as e:
            raise HTTPException(status_code=503, detail=str(e)) from e
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to decrypt data source connection: {str(e)}") from e

        source = {
            "id": record.id,
            "name": record.name,
            "type": record.type,
            "connection": connection,
        }

        logger.info("Found data source: %s, type: %s", source.get('name'), source.get('type'))
        
        # Test connection based on source type
        test_result = await _test_connection(source)
        logger.info("Connection test result: %s, message: %s", test_result.success, test_result.message)
        
        # Update source with test results
        record.last_tested = datetime.now()
        record.test_result = "success" if test_result.success else "failed"
        record.status = "active" if test_result.success else "error"
        db.commit()
        
        return test_result
    except (OSError, json.JSONDecodeError, ValueError, TypeError, KeyError, RuntimeError) as e:
        logger.error("Error testing data source %s: %s", source_id, e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to test data source connection: {str(e)}") from e

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
    except (ValueError, TypeError, KeyError, OSError, RuntimeError, neo4j.exceptions.Neo4jError) as e:
        return TestConnectionResponse(
            success=False,
            message=f"Connection test failed: {str(e)}"
        )

async def _test_neo4j_connection(connection: Dict) -> TestConnectionResponse:
    """Test Neo4j connection"""
    try:
        uri = connection.get('uri') or f"neo4j://{connection.get('host', 'localhost')}:{connection.get('port', '7687')}"
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
    except (ValueError, TypeError, KeyError, OSError, RuntimeError, neo4j.exceptions.Neo4jError) as e:
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
    except (ValueError, TypeError, KeyError) as e:
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
    except (ValueError, TypeError, KeyError) as e:
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
    except (ValueError, TypeError, KeyError) as e:
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
    except (ValueError, TypeError, KeyError, OSError) as e:
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
            "default_port": "5433",
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
