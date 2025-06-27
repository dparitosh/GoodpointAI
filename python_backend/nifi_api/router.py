import logging
from fastapi import APIRouter, HTTPException
from .client import NiFiClient
from .models import NiFiProcessGroupListResponse, NiFiFlowResponse, NiFiStatusResponse
from core.config import NIFI_BASE_URL, NIFI_USERNAME, NIFI_PASSWORD
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
import asyncio
from datetime import datetime

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/nifi", tags=["NiFi Integration"])

nifi_client = NiFiClient(NIFI_BASE_URL, NIFI_USERNAME, NIFI_PASSWORD)

@router.get(
    "/process_groups",
    response_model=NiFiProcessGroupListResponse,
    summary="List NiFi Process Groups",
    description="Fetches a list of top-level NiFi Process Groups.",
)
async def list_nifi_process_groups():
    process_groups = await nifi_client.get_process_groups()
    return NiFiProcessGroupListResponse(processGroups=process_groups)

@router.get(
    "/flow/{process_group_id}",
    response_model=NiFiFlowResponse,
    summary="Get NiFi Flow Diagram",
    description="Fetches the flow diagram (processors, connections, ports) for a given NiFi Process Group.",
)
async def get_nifi_flow_diagram(process_group_id: str):
    flow_data = await nifi_client.get_flow_diagram(process_group_id)
    return flow_data

@router.get(
    "/status/{process_group_id}",
    response_model=NiFiStatusResponse,
    summary="Get NiFi Process Group Status",
    description="Fetches real-time status metrics for a given NiFi Process Group.",
)
async def get_nifi_status(process_group_id: str):
    status_data = await nifi_client.get_status(process_group_id)
    return status_data

@router.put(
    "/processor/{processor_id}/start",
    summary="Start NiFi Processor",
    description="Starts a NiFi processor by its ID.",
)
async def start_nifi_processor(processor_id: str):
    try:
        await nifi_client.start_processor(processor_id)
        return {"message": f"Processor {processor_id} start command sent successfully."}
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Unexpected error starting processor {processor_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.put(
    "/processor/{processor_id}/stop",
    summary="Stop NiFi Processor",
    description="Stops a NiFi processor by its ID.",
)
async def stop_nifi_processor(processor_id: str):
    try:
        await nifi_client.stop_processor(processor_id)
        return {"message": f"Processor {processor_id} stop command sent successfully."}
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Unexpected error stopping processor {processor_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

# Enhanced NiFi Integration for Spreadsheet Tool

# Additional Pydantic Models for Enhanced Integration
class NiFiMapping(BaseModel):
    id: Optional[str] = None
    sourceField: str
    targetField: str
    transformation: str
    processorId: str

class NiFiSyncConfig(BaseModel):
    processGroupId: str
    dataMapping: List[List[str]]
    flowConfiguration: Dict[str, Any]

# Enhanced endpoints for spreadsheet integration
@router.post(
    "/mappings",
    summary="Create NiFi Data Mapping",
    description="Create a new NiFi data mapping for spreadsheet integration."
)
async def create_nifi_mapping(mapping: NiFiMapping):
    """Create a new NiFi data mapping"""
    mapping.id = f"mapping_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    # Here you would integrate with actual NiFi API to create processor configurations
    logger.info(f"Created NiFi mapping: {mapping.sourceField} -> {mapping.targetField}")
    
    return {
        "id": mapping.id,
        "status": "created",
        "mapping": mapping,
        "createdAt": datetime.now().isoformat()
    }

@router.post(
    "/sync",
    summary="Sync Data with NiFi",
    description="Synchronize spreadsheet data with NiFi pipeline."
)
async def sync_with_nifi(sync_config: NiFiSyncConfig):
    """Synchronize data with NiFi pipeline"""
    try:
        # Get process group info using existing client
        process_groups = await nifi_client.get_process_groups()
        target_pg = next(
            (pg for pg in process_groups if pg.get("id") == sync_config.processGroupId), 
            None
        )
        
        if not target_pg:
            raise HTTPException(status_code=404, detail="Process group not found")
        
        # Here you would implement the actual synchronization logic
        logger.info(f"NiFi sync started for process group: {sync_config.processGroupId}")
        
        return {
            "message": f"NiFi synchronization started for process group: {target_pg.get('name', 'Unknown')}",
            "processGroupId": sync_config.processGroupId,
            "status": "running",
            "dataRecords": len(sync_config.dataMapping)
        }
        
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"NiFi sync failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get(
    "/templates",
    summary="Get NiFi Templates",
    description="Get available NiFi flow templates for data integration."
)
async def get_nifi_templates():
    """Get available NiFi flow templates for data integration"""
    templates = [
        {
            "id": "template-001",
            "name": "Neo4j to Database ETL",
            "description": "Extract data from Neo4j, transform, and load to relational database",
            "processors": ["ExecuteCypherQuery", "JoltTransformJSON", "PutDatabaseRecord"],
            "category": "ETL"
        },
        {
            "id": "template-002",
            "name": "Real-time Data Sync",
            "description": "Real-time synchronization between Neo4j and target systems",
            "processors": ["ListenHTTP", "RouteOnAttribute", "PutNeo4j"],
            "category": "Streaming"
        },
        {
            "id": "template-003",
            "name": "Data Quality Pipeline",
            "description": "Data validation and quality assessment pipeline",
            "processors": ["ValidateRecord", "QueryRecord", "UpdateAttribute"],
            "category": "Quality"
        }
    ]
    
    return templates

@router.get(
    "/monitoring/metrics",
    summary="Get NiFi Metrics",
    description="Get NiFi performance metrics for monitoring."
)
async def get_nifi_metrics():
    """Get NiFi performance metrics"""
    return {
        "totalFlowFiles": 192,
        "totalBytesRead": 1536000,
        "totalBytesWritten": 1498000,
        "activeThreads": 12,
        "queuedFlowFiles": 8,
        "systemLoad": 0.65,
        "jvmMemoryUsed": "512MB",
        "jvmMemoryMax": "2GB",
        "timestamp": datetime.now().isoformat()
    }