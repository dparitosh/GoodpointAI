import logging
from fastapi import APIRouter, HTTPException
from .client import NiFiClient
from .models import NiFiProcessGroupListResponse, NiFiFlowResponse, NiFiStatusResponse
from ..core.config import NIFI_BASE_URL, NIFI_USERNAME, NIFI_PASSWORD

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