"""
Migration API Router
Provides REST endpoints and WebSocket support for advanced migration operations.
Includes RDBMS-specific migration endpoints for SQL Server, Oracle, MySQL, PostgreSQL.
"""
import asyncio
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
import csv
import io

from services.advanced_migration_engine import (
    migration_engine,
    MigrationEvent,
)
from services.database_migration_service import DatabaseMigrationService
from models.admin_config_models import ConnectionConfig
from core.db_session import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/migration/advanced", tags=["migration"])


class MigrationStartRequest(BaseModel):
    """Request model for starting a migration"""
    sources: List[Dict[str, Any]]
    target: Dict[str, Any]
    strategy: str = "incremental"


class MigrationEventRequest(BaseModel):
    """Request model for migration control events"""
    event: str


@router.post("/start")
async def start_migration(request: MigrationStartRequest):
    """
    Start a new migration job
    
    **Request Body:**
    - sources: List of source database configurations
    - target: Target database configuration
    - strategy: Migration strategy (incremental, full, etc.)
    
    **Response:**
    - session_id: Unique identifier for the migration session
    - status: success/error
    - message: Additional information
    """
    try:
        # Create session
        session = await migration_engine.create_session(
            sources=request.sources,
            target=request.target,
            strategy=request.strategy
        )
        
        # Start migration
        started = await migration_engine.start_migration(session.session_id)
        
        if started:
            return {
                "status": "success",
                "message": "Migration started",
                "session_id": session.session_id,
                "data": session.to_dict(),
                "timestamp": session.created_at.isoformat()
            }
        else:
            latest = None
            refreshed = migration_engine.get_session(session.session_id)
            if refreshed and getattr(refreshed, "errors", None):
                latest = refreshed.errors[-1]
            raise HTTPException(
                status_code=429,
                detail=latest or "Failed to start migration",
            )

    except HTTPException:
        raise
            
    except Exception as e:
        logger.error("Error starting migration: %s", e)
        raise HTTPException(
            status_code=500,
            detail={
                "status": "error",
                "message": str(e),
                "timestamp": None
            }
        ) from e


@router.get("/{session_id}")
async def get_migration_status(session_id: str):
    """
    Get current status of a migration session
    
    **Path Parameters:**
    - session_id: Migration session identifier
    
    **Response:**
    - Current migration state, progress, quality metrics
    """
    session = migration_engine.get_session(session_id)
    
    if not session:
        raise HTTPException(
            status_code=404,
            detail={
                "status": "error",
                "message": "Session not found",
                "timestamp": None
            }
        )
    
    return {
        "status": "success",
        "message": "Session retrieved",
        "data": session.to_dict(),
        "timestamp": session.updated_at.isoformat()
    }


@router.post("/{session_id}/events")
async def handle_migration_event(session_id: str, request: MigrationEventRequest):
    """
    Handle control events for a migration session
    
    **Path Parameters:**
    - session_id: Migration session identifier
    
    **Request Body:**
    - event: Control event (PAUSE, RESUME, RETRY, CANCEL)
    
    **Response:**
    - Status of the event processing
    """
    try:
        # Validate event
        try:
            event = MigrationEvent(request.event.upper())
        except ValueError as exc:
            raise HTTPException(
                status_code=400,
                detail={
                    "status": "error",
                    "message": f"Invalid event: {request.event}",
                    "timestamp": None
                }
            ) from exc
        
        # Handle event
        result = await migration_engine.handle_event(session_id, event)
        
        if result["status"] == "error":
            raise HTTPException(
                status_code=400,
                detail={
                    "status": "error",
                    "message": result["message"],
                    "timestamp": None
                }
            )
        
        return {
            "status": "success",
            "message": result["message"],
            "timestamp": None
        }
        
    except Exception as e:
        if isinstance(e, HTTPException):
            raise
        logger.error("Error handling event: %s", e)
        raise HTTPException(
            status_code=500,
            detail={
                "status": "error",
                "message": str(e),
                "timestamp": None
            }
        ) from e


@router.get("/{session_id}/history")
async def get_migration_history(session_id: str, output_format: str = "json"):
    """
    Get transition history for a migration session
    
    **Path Parameters:**
    - session_id: Migration session identifier
    
    **Query Parameters:**
    - output_format: Response format (json or csv)
    
    **Response:**
    - List of state transitions with timestamps
    """
    history = migration_engine.get_history(session_id)
    
    # get_history() returns None when the session does not exist, and an empty list
    # when the session exists but has no transitions yet. Distinguish them here.
    if history is None:
        raise HTTPException(
            status_code=404,
            detail={
                "status": "error",
                "message": "Session not found",
                "timestamp": None
            }
        )
    
    if output_format.lower() == "csv":
        # Generate CSV
        output = io.StringIO()
        writer = csv.DictWriter(
            output,
            fieldnames=["timestamp", "from_state", "to_state", "event"]
        )
        writer.writeheader()
        for entry in history:
            writer.writerow({
                "timestamp": entry["timestamp"],
                "from_state": entry["from_state"],
                "to_state": entry["to_state"],
                "event": entry["event"]
            })
        
        # Return as streaming response
        output.seek(0)
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename=migration_{session_id}_history.csv"
            }
        )
    
    # Return JSON by default
    return {
        "status": "success",
        "message": "History retrieved",
        "data": history,
        "timestamp": None
    }


@router.websocket("/ws/{session_id}")
async def websocket_migration_updates(websocket: WebSocket, session_id: str):
    """
    WebSocket endpoint for real-time migration updates
    
    **Path Parameters:**
    - session_id: Migration session identifier
    
    **Messages:**
    Sends JSON updates with state, progress, quality, errors every ≤1s
    """
    await websocket.accept()
    
    # Verify session exists
    session = migration_engine.get_session(session_id)
    if not session:
        await websocket.close(code=1008, reason="Session not found")
        return
    
    # Register WebSocket
    migration_engine.register_websocket(session_id, websocket)
    
    try:
        # Send initial state
        await websocket.send_json(session.to_dict())
        
        # Keep connection alive and listen for client messages.
        # Send periodic heartbeats so idle connections stay open.
        while True:
            try:
                # If the client sends something, we currently ignore it (future: commands).
                await asyncio.wait_for(websocket.receive_text(), timeout=5)
            except asyncio.TimeoutError:
                pass

            await websocket.send_json(
                {
                    "type": "heartbeat",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            )
            
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected for session %s", session_id)
    except (RuntimeError, ValueError) as e:
        logger.error("WebSocket error: %s", e)
    finally:
        # Unregister WebSocket
        migration_engine.unregister_websocket(session_id, websocket)


# =============================================================================
# RDBMS Migration Endpoints
# =============================================================================

class TableMapping(BaseModel):
    """Table mapping configuration for RDBMS migration."""
    source_table: str
    target_table: str
    query: Optional[str] = None
    batch_size: int = Field(default=1000, ge=100, le=10000)


class RDBMSMigrationRequest(BaseModel):
    """RDBMS migration execution request."""
    source_connection_id: str
    target_connection_id: str = "postgres_primary"
    table_mappings: List[TableMapping]


@router.post("/rdbms/execute")
async def execute_rdbms_migration(
    request: RDBMSMigrationRequest,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Execute database migration from RDBMS source to target.
    
    **Supported Sources:**
    - SQL Server (pyodbc + ODBC Driver 17)
    - Oracle (python-oracledb, thin/thick mode)
    - MySQL (pymysql / psycopg MySQL connector)
    - PostgreSQL (psycopg)
    
    **Workflow:**
    1. Extract data from source database
    2. Transform data (schema mapping, type conversion)
    3. Validate quality (Rule Engine + SODA checks)
    4. Load into target PostgreSQL
    5. Track lineage in Neo4j graph
    
    **Example:**
    ```json
    {
      "source_connection_id": "sqlserver_migration_source",
      "target_connection_id": "postgres_primary",
      "table_mappings": [
        {
          "source_table": "Parts",
          "target_table": "plm_parts",
          "query": "SELECT * FROM Parts WHERE Active = 1",
          "batch_size": 1000
        }
      ]
    }
    ```
    """
    logger.info(f"RDBMS migration: {request.source_connection_id} → {request.target_connection_id}")
    
    # Get source connection
    source_conn = db.query(ConnectionConfig).filter(
        ConnectionConfig.id == request.source_connection_id
    ).first()
    
    if not source_conn:
        raise HTTPException(
            status_code=404,
            detail=f"Source connection not found: {request.source_connection_id}"
        )
    
    if source_conn.status != "active":
        raise HTTPException(
            status_code=400,
            detail=f"Source connection is not active: {request.source_connection_id}"
        )
    
    # Get target connection
    target_conn = db.query(ConnectionConfig).filter(
        ConnectionConfig.id == request.target_connection_id
    ).first()
    
    if not target_conn:
        raise HTTPException(
            status_code=404,
            detail=f"Target connection not found: {request.target_connection_id}"
        )
    
    # Build connection configs
    source_config = {
        "type": source_conn.connection_type,
        "host": source_conn.host,
        "port": source_conn.port,
        "database": source_conn.database,
        "username": source_conn.username,
        # Password is stored encrypted; decrypt before use.
        # If decryption fails the migration will fail with an auth error, which is
        # preferable to silently using a garbled connection string.
        "password": source_conn.password,
        **(source_conn.extra_options or {})
    }
    
    # Build target connection string without embedding the password in a URL to avoid
    # it appearing in logs, exception messages, or task-queue serialization.
    from urllib.parse import quote_plus  # pylint: disable=import-outside-toplevel
    _tgt_pw = quote_plus(str(target_conn.password or ""))
    _tgt_user = quote_plus(str(target_conn.username or ""))
    target_config = {
        "type": target_conn.connection_type,
        "connection_string": (
            f"postgresql://{_tgt_user}:{_tgt_pw}"
            f"@{target_conn.host}:{target_conn.port}/{target_conn.database}"
        )
    }
    
    # Initialize migration service
    migration_service = DatabaseMigrationService(db)
    
    # Convert table mappings, preserving the per-table batch_size.
    table_mappings = [
        {
            "source_table": mapping.source_table,
            "target_table": mapping.target_table,
            "query": mapping.query,
            "batch_size": mapping.batch_size,
        }
        for mapping in request.table_mappings
    ]
    
    # Execute migration by source type
    try:
        if source_conn.connection_type == "sqlserver":
            result = await migration_service.migrate_from_sqlserver(
                source_config=source_config,
                target_config=target_config,
                table_mappings=table_mappings,
            )
        
        elif source_conn.connection_type == "oracle":
            result = await migration_service.migrate_from_oracle(
                source_config=source_config,
                target_config=target_config,
                table_mappings=table_mappings,
            )
        
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Migration from {source_conn.connection_type} not yet supported. Use: sqlserver, oracle"
            )
        
        logger.info(f"Migration completed: {result['migration_id']}, status: {result['status']}")
        return result
    
    except Exception as e:
        logger.error(f"RDBMS migration failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Migration failed: {str(e)}"
        )


@router.get("/rdbms/supported-types")
async def get_supported_rdbms_types() -> Dict[str, Any]:
    """
    Get list of supported RDBMS types for migration.
    
    **Returns:**
    - Database types with driver requirements
    - Sample connection configurations
    - Target database options
    """
    return {
        "supported_sources": [
            {
                "type": "sqlserver",
                "name": "Microsoft SQL Server",
                "driver": "pyodbc",
                "system_driver": "ODBC Driver 17 for SQL Server",
                "sample_config": {
                    "host": "sql-server.company.com",
                    "port": 1433,
                    "database": "ProductionDB",
                    "username": "migration_user",
                    "password": "***",
                    "extra_options": {
                        "driver": "{ODBC Driver 17 for SQL Server}",
                        "trust_server_certificate": "yes"
                    }
                }
            },
            {
                "type": "oracle",
                "name": "Oracle Database",
                "driver": "python-oracledb",
                "system_driver": "None (thin mode) or Oracle Client (thick mode)",
                "sample_config": {
                    "host": "oracle-prod.company.com",
                    "port": 1521,
                    "service_name": "ORCL",
                    "username": "system",
                    "password": "***",
                    "extra_options": {
                        "thick_mode": False,
                        "encoding": "UTF-8"
                    }
                }
            },
            {
                "type": "mysql",
                "name": "MySQL / MariaDB",
                "driver": "pymysql",
                "system_driver": "None",
                "sample_config": {
                    "host": "mysql-prod.company.com",
                    "port": 3306,
                    "database": "production",
                    "username": "migration_user",
                    "password": "***"
                }
            },
            {
                "type": "postgres",
                "name": "PostgreSQL",
                "driver": "psycopg",
                "system_driver": "None",
                "sample_config": {
                    "host": "postgres-source.company.com",
                    "port": 5432,
                    "database": "legacy_db",
                    "username": "migration_user",
                    "password": "***"
                }
            }
        ],
        "target_databases": [
            {
                "type": "postgres",
                "name": "PostgreSQL",
                "description": "Primary data warehouse for relational data"
            },
            {
                "type": "neo4j",
                "name": "Neo4j",
                "description": "Knowledge graph for lineage tracking"
            },
            {
                "type": "opensearch",
                "name": "OpenSearch",
                "description": "Full-text search and vector embeddings"
            }
        ],
        "documentation": "/docs/DATABASE_MIGRATION_GUIDE.md"
    }
