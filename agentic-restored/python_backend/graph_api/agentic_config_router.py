"""
Agentic Configuration API Router
===============================

FastAPI router that provides REST API endpoints for the agentic configuration manager.
Includes WebSocket support for real-time updates and deployment triggers.
"""

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect, BackgroundTasks
from typing import Dict, Any, Optional
import logging
import json
from datetime import datetime

from core.agentic_config_manager import config_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/orchestration/config", tags=["Orchestration - Configuration"])

@router.get("/")
async def get_configuration() -> Dict[str, Any]:
    """Get current configuration"""
    try:
        config = await config_manager.get_configuration()
        return {
            "status": "success",
            "data": config
        }
    except Exception as e:
        logger.error("Error getting configuration: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e

@router.post("/")
async def update_configuration(
    config_update: Dict[str, Any],
    trigger_deployment: bool = True,
    _background_tasks: BackgroundTasks = BackgroundTasks()
) -> Dict[str, Any]:
    """Update configuration with optional deployment trigger"""
    try:
        result = await config_manager.update_configuration(
            config_update, 
            trigger_deployment=trigger_deployment
        )
        return result
    except Exception as e:
        logger.error("Error updating configuration: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e

@router.get("/schema")
async def get_configuration_schema() -> Dict[str, Any]:
    """Get the JSON schema for configuration validation"""
    try:
        return {
            "status": "success",
            "schema": config_manager.schema
        }
    except Exception as e:
        logger.error("Error getting schema: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e

@router.post("/validate")
async def validate_configuration(config_data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate configuration against schema without saving"""
    try:
        try:
            import jsonschema  # type: ignore[import-untyped]
        except ImportError:
            return {
                "status": "error",
                "message": "jsonschema package not installed",
                "valid": False
            }
        
        # Wrap in configuration object if needed
        if "configuration" not in config_data:
            config_data = {"configuration": config_data}
        
        # Validate against schema
        jsonschema.validate(config_data, config_manager.schema)
        
        return {
            "status": "success",
            "message": "Configuration is valid",
            "valid": True
        }
    except jsonschema.ValidationError as e:
        return {
            "status": "error",
            "message": f"Validation failed: {e.message}",
            "valid": False,
            "error_path": list(e.path) if e.path else [],
            "error_value": e.instance
        }
    except Exception as e:
        logger.error("Error validating configuration: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e

@router.get("/deployment/status")
async def get_deployment_status() -> Dict[str, Any]:
    """Get current deployment status"""
    try:
        status = await config_manager.get_deployment_status()
        return {
            "status": "success",
            "data": status
        }
    except Exception as e:
        logger.error("Error getting deployment status: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e

@router.post("/deployment/trigger")
async def trigger_deployment_endpoint(
    deployment_config: Optional[Dict[str, Any]] = None,
    _background_tasks: BackgroundTasks = BackgroundTasks()
) -> Dict[str, Any]:
    """Manually trigger deployment"""
    try:
        return await config_manager.trigger_deployment(deployment_config or {}, _background_tasks)
    except Exception as e:
        logger.error("Error triggering deployment: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e

@router.post("/deploy")
async def trigger_deployment_legacy(
    deployment_config: Optional[Dict[str, Any]] = None,
    _background_tasks: BackgroundTasks = BackgroundTasks()
) -> Dict[str, Any]:
    """Trigger deployment with current configuration"""
    try:
        return await config_manager.trigger_deployment(deployment_config or {}, _background_tasks)
    except Exception as e:
        logger.error("Error triggering deployment: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e

@router.get("/analytics")
async def get_configuration_analytics() -> Dict[str, Any]:
    """Get analytics and insights about current configuration"""
    try:
        analytics = await config_manager.get_analytics()
        return {
            "status": "success",
            "data": analytics
        }
    except Exception as e:
        logger.error("Error getting analytics: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e

# ============= DATA SOURCE MANAGEMENT =============

@router.get("/data-sources")
async def get_data_sources() -> Dict[str, Any]:
    """Get all configured data sources"""
    try:
        data_sources = await config_manager.get_data_sources()
        return {
            "status": "success",
            "data": data_sources
        }
    except Exception as e:
        logger.error("Error getting data sources: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e

@router.post("/data-sources")
async def add_data_source(data_source_config: Dict[str, Any]) -> Dict[str, Any]:
    """Add a new data source"""
    try:
        result = await config_manager.add_data_source(data_source_config)
        return result
    except Exception as e:
        logger.error("Error adding data source: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e

@router.put("/data-sources/{source_id}")
async def update_data_source(
    source_id: str, 
    data_source_config: Dict[str, Any]
) -> Dict[str, Any]:
    """Update an existing data source"""
    try:
        result = await config_manager.update_data_source(source_id, data_source_config)
        return result
    except Exception as e:
        logger.error("Error updating data source: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e

@router.delete("/data-sources/{source_id}")
async def delete_data_source(source_id: str) -> Dict[str, Any]:
    """Delete a data source"""
    try:
        result = await config_manager.delete_data_source(source_id)
        return result
    except Exception as e:
        logger.error("Error deleting data source: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e

@router.post("/data-sources/{source_id}/test")
async def test_data_source_connection(source_id: str) -> Dict[str, Any]:
    """Test connection for a specific data source"""
    try:
        result = await config_manager.test_data_source_connection(source_id)
        return result
    except Exception as e:
        logger.error("Error testing data source connection: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e

# ============= CONFIGURATION EXPORT/IMPORT =============

@router.get("/export")
async def export_configuration() -> Dict[str, Any]:
    """Export current configuration"""
    try:
        config_data = await config_manager.export_configuration()
        return {
            "status": "success",
            "data": config_data,
            "timestamp": config_data.get("exported_at")
        }
    except Exception as e:  # pylint: disable=broad-except
        logger.error("Error exporting configuration: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e  # noqa: BLE001

@router.post("/import")
async def import_configuration(config_data: Dict[str, Any]) -> Dict[str, Any]:
    """Import configuration from uploaded data"""
    try:
        result = await config_manager.import_configuration(config_data)
        return result
    except Exception as e:
        logger.error("Error importing configuration: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e  # noqa: BLE001

@router.get("/health")
async def health_check() -> Dict[str, Any]:
    """Health check for agentic configuration service"""
    try:
        health_status = await config_manager.health_check()
        return {
            "status": "success",
            "health": health_status,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:  # pylint: disable=broad-except
        logger.error("Health check failed: %s", e)
        return {
            "status": "error",
            "message": str(e),
            "timestamp": datetime.now().isoformat()
        }

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time configuration updates"""
    await config_manager.add_websocket_connection(websocket)
    
    try:
        while True:
            # Keep connection alive and listen for messages
            message = await websocket.receive_text()
            
            # Handle incoming WebSocket messages if needed
            try:
                data = json.loads(message)
                if data.get("type") == "ping":
                    await websocket.send_text(json.dumps({"type": "pong"}))
                elif data.get("type") == "get_status":
                    status = await config_manager.get_deployment_status()
                    await websocket.send_text(json.dumps({
                        "type": "deployment_status",
                        "data": status
                    }))
            except json.JSONDecodeError:
                logger.warning("Invalid JSON received via WebSocket")
                
    except WebSocketDisconnect:
        config_manager.remove_websocket_connection(websocket)
    except Exception as e:  # pylint: disable=broad-except
        logger.error("WebSocket error: %s", e)
        config_manager.remove_websocket_connection(websocket)
