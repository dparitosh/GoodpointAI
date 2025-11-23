"""
Migration API Router
Provides REST endpoints and WebSocket support for advanced migration operations.
"""
import logging
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Dict, Optional, Any
import csv
import io

from services.advanced_migration_engine import (
    migration_engine,
    MigrationEvent,
    MigrationState
)

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
            raise HTTPException(status_code=400, detail="Failed to start migration")
            
    except Exception as e:
        logger.error(f"Error starting migration: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "status": "error",
                "message": str(e),
                "timestamp": None
            }
        )


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
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail={
                    "status": "error",
                    "message": f"Invalid event: {request.event}",
                    "timestamp": None
                }
            )
        
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
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error handling event: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "status": "error",
                "message": str(e),
                "timestamp": None
            }
        )


@router.get("/{session_id}/history")
async def get_migration_history(session_id: str, format: str = "json"):
    """
    Get transition history for a migration session
    
    **Path Parameters:**
    - session_id: Migration session identifier
    
    **Query Parameters:**
    - format: Response format (json or csv)
    
    **Response:**
    - List of state transitions with timestamps
    """
    history = migration_engine.get_history(session_id)
    
    if not history:
        raise HTTPException(
            status_code=404,
            detail={
                "status": "error",
                "message": "Session not found or no history available",
                "timestamp": None
            }
        )
    
    if format.lower() == "csv":
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
        
        # Keep connection alive and listen for client messages
        while True:
            data = await websocket.receive_text()
            # Echo back for heartbeat
            await websocket.send_json({"type": "heartbeat", "timestamp": datetime.utcnow().isoformat()})
            
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for session {session_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        # Unregister WebSocket
        migration_engine.unregister_websocket(session_id, websocket)
