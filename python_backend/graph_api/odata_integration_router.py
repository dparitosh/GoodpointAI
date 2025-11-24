"""
OData Integration Router
Handles OData services (SAP, Dynamics, generic OData endpoints)
"""
import logging
from typing import List, Dict, Optional, Any
from datetime import datetime
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
import requests
from requests.auth import HTTPBasicAuth
import json

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/odata", tags=["OData Integration"])


# ============================================================================
# MODELS
# ============================================================================

class ODataServiceConfig(BaseModel):
    service_url: str = Field(..., description="OData service root URL")
    auth_type: str = Field(default="basic", description="basic, oauth2, apikey")
    username: Optional[str] = None
    password: Optional[str] = None
    api_key: Optional[str] = None
    token: Optional[str] = None
    headers: Optional[Dict[str, str]] = {}


class ODataQueryRequest(BaseModel):
    service_url: str = Field(..., description="OData service URL")
    entity_set: str = Field(..., description="Entity set name")
    filter: Optional[str] = None
    select: Optional[str] = None
    expand: Optional[str] = None
    orderby: Optional[str] = None
    top: Optional[int] = None
    skip: Optional[int] = None


class ODataCreateRequest(BaseModel):
    service_url: str
    entity_set: str
    data: Dict[str, Any]


class ODataUpdateRequest(BaseModel):
    service_url: str
    entity_set: str
    key: str
    data: Dict[str, Any]


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_odata_auth(config: ODataServiceConfig):
    """Get authentication for OData request"""
    if config.auth_type == "basic":
        return HTTPBasicAuth(config.username, config.password)
    elif config.auth_type == "apikey":
        return None  # Handled in headers
    elif config.auth_type == "oauth2":
        return None  # Handled in headers
    return None


def get_odata_headers(config: ODataServiceConfig) -> Dict[str, str]:
    """Get headers for OData request"""
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        **config.headers
    }
    
    if config.auth_type == "apikey" and config.api_key:
        headers["Authorization"] = f"Bearer {config.api_key}"
    elif config.auth_type == "oauth2" and config.token:
        headers["Authorization"] = f"Bearer {config.token}"
    
    return headers


# ============================================================================
# ODATA SERVICE METADATA
# ============================================================================

@router.get("/metadata")
async def get_service_metadata(service_url: str):
    """Get OData service metadata ($metadata)"""
    try:
        from core.external_config import odata_config
        
        metadata_url = f"{service_url}/$metadata"
        
        config = ODataServiceConfig(
            service_url=service_url,
            auth_type=odata_config.odata_auth_type,
            username=odata_config.odata_username,
            password=odata_config.odata_password,
            api_key=odata_config.odata_api_key
        )
        
        response = requests.get(
            metadata_url,
            auth=get_odata_auth(config),
            headers=get_odata_headers(config),
            timeout=30
        )
        response.raise_for_status()
        
        return {
            "status": "success",
            "service_url": service_url,
            "metadata": response.text,
            "content_type": response.headers.get('Content-Type')
        }
        
    except Exception as e:
        logger.error(f"Error fetching OData metadata: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/entities")
async def list_entity_sets(service_url: str):
    """List all entity sets in OData service"""
    try:
        from core.external_config import odata_config
        
        config = ODataServiceConfig(
            service_url=service_url,
            auth_type=odata_config.odata_auth_type,
            username=odata_config.odata_username,
            password=odata_config.odata_password,
            api_key=odata_config.odata_api_key
        )
        
        response = requests.get(
            service_url,
            auth=get_odata_auth(config),
            headers=get_odata_headers(config),
            timeout=30
        )
        response.raise_for_status()
        
        data = response.json()
        entity_sets = []
        
        if 'value' in data:
            entity_sets = [
                {
                    "name": item.get('name'),
                    "url": item.get('url'),
                    "kind": item.get('kind')
                }
                for item in data['value']
            ]
        
        return {
            "status": "success",
            "service_url": service_url,
            "count": len(entity_sets),
            "entity_sets": entity_sets
        }
        
    except Exception as e:
        logger.error(f"Error listing entity sets: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# ODATA QUERY OPERATIONS
# ============================================================================

@router.post("/query")
async def query_odata_entity(request: ODataQueryRequest):
    """Query OData entity set with filters"""
    try:
        from core.external_config import odata_config
        
        # Build query URL
        url = f"{request.service_url}/{request.entity_set}"
        params = {}
        
        if request.filter:
            params['$filter'] = request.filter
        if request.select:
            params['$select'] = request.select
        if request.expand:
            params['$expand'] = request.expand
        if request.orderby:
            params['$orderby'] = request.orderby
        if request.top:
            params['$top'] = request.top
        if request.skip:
            params['$skip'] = request.skip
        
        config = ODataServiceConfig(
            service_url=request.service_url,
            auth_type=odata_config.odata_auth_type,
            username=odata_config.odata_username,
            password=odata_config.odata_password,
            api_key=odata_config.odata_api_key
        )
        
        response = requests.get(
            url,
            params=params,
            auth=get_odata_auth(config),
            headers=get_odata_headers(config),
            timeout=60
        )
        response.raise_for_status()
        
        data = response.json()
        
        return {
            "status": "success",
            "entity_set": request.entity_set,
            "count": data.get('@odata.count', len(data.get('value', []))),
            "data": data.get('value', []),
            "next_link": data.get('@odata.nextLink')
        }
        
    except Exception as e:
        logger.error(f"Error querying OData: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/entity/{entity_set}/{key}")
async def get_odata_entity_by_key(
    entity_set: str,
    key: str,
    service_url: str = Query(..., description="OData service URL")
):
    """Get single OData entity by key"""
    try:
        from core.external_config import odata_config
        
        url = f"{service_url}/{entity_set}({key})"
        
        config = ODataServiceConfig(
            service_url=service_url,
            auth_type=odata_config.odata_auth_type,
            username=odata_config.odata_username,
            password=odata_config.odata_password,
            api_key=odata_config.odata_api_key
        )
        
        response = requests.get(
            url,
            auth=get_odata_auth(config),
            headers=get_odata_headers(config),
            timeout=30
        )
        response.raise_for_status()
        
        return {
            "status": "success",
            "entity_set": entity_set,
            "key": key,
            "data": response.json()
        }
        
    except Exception as e:
        logger.error(f"Error getting OData entity: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# ODATA CREATE/UPDATE/DELETE
# ============================================================================

@router.post("/create")
async def create_odata_entity(request: ODataCreateRequest):
    """Create new OData entity"""
    try:
        from core.external_config import odata_config
        
        url = f"{request.service_url}/{request.entity_set}"
        
        config = ODataServiceConfig(
            service_url=request.service_url,
            auth_type=odata_config.odata_auth_type,
            username=odata_config.odata_username,
            password=odata_config.odata_password,
            api_key=odata_config.odata_api_key
        )
        
        response = requests.post(
            url,
            json=request.data,
            auth=get_odata_auth(config),
            headers=get_odata_headers(config),
            timeout=30
        )
        response.raise_for_status()
        
        return {
            "status": "success",
            "message": "Entity created",
            "entity_set": request.entity_set,
            "data": response.json()
        }
        
    except Exception as e:
        logger.error(f"Error creating OData entity: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/update")
async def update_odata_entity(request: ODataUpdateRequest):
    """Update existing OData entity"""
    try:
        from core.external_config import odata_config
        
        url = f"{request.service_url}/{request.entity_set}({request.key})"
        
        config = ODataServiceConfig(
            service_url=request.service_url,
            auth_type=odata_config.odata_auth_type,
            username=odata_config.odata_username,
            password=odata_config.odata_password,
            api_key=odata_config.odata_api_key
        )
        
        response = requests.patch(
            url,
            json=request.data,
            auth=get_odata_auth(config),
            headers=get_odata_headers(config),
            timeout=30
        )
        response.raise_for_status()
        
        return {
            "status": "success",
            "message": "Entity updated",
            "entity_set": request.entity_set,
            "key": request.key
        }
        
    except Exception as e:
        logger.error(f"Error updating OData entity: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/delete/{entity_set}/{key}")
async def delete_odata_entity(
    entity_set: str,
    key: str,
    service_url: str = Query(..., description="OData service URL")
):
    """Delete OData entity"""
    try:
        from core.external_config import odata_config
        
        url = f"{service_url}/{entity_set}({key})"
        
        config = ODataServiceConfig(
            service_url=service_url,
            auth_type=odata_config.odata_auth_type,
            username=odata_config.odata_username,
            password=odata_config.odata_password,
            api_key=odata_config.odata_api_key
        )
        
        response = requests.delete(
            url,
            auth=get_odata_auth(config),
            headers=get_odata_headers(config),
            timeout=30
        )
        response.raise_for_status()
        
        return {
            "status": "success",
            "message": "Entity deleted",
            "entity_set": entity_set,
            "key": key
        }
        
    except Exception as e:
        logger.error(f"Error deleting OData entity: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# SAP SPECIFIC ENDPOINTS
# ============================================================================

@router.get("/sap/entity-sets")
async def list_sap_entity_sets():
    """List SAP OData entity sets"""
    try:
        from core.external_config import odata_config
        
        if not odata_config.sap_odata_url:
            raise HTTPException(status_code=400, detail="SAP OData URL not configured")
        
        config = ODataServiceConfig(
            service_url=odata_config.sap_odata_url,
            auth_type="basic",
            username=odata_config.sap_username,
            password=odata_config.sap_password,
            headers={"sap-client": odata_config.sap_client}
        )
        
        response = requests.get(
            odata_config.sap_odata_url,
            auth=get_odata_auth(config),
            headers=get_odata_headers(config),
            timeout=30
        )
        response.raise_for_status()
        
        data = response.json()
        
        return {
            "status": "success",
            "service": "SAP OData",
            "client": odata_config.sap_client,
            "entity_sets": data.get('value', [])
        }
        
    except Exception as e:
        logger.error(f"Error listing SAP entities: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# HEALTH CHECK
# ============================================================================

@router.get("/health")
async def odata_health_check():
    """Check OData service connectivity"""
    from core.external_config import odata_config
    
    health = {
        "status": "healthy",
        "services": {
            "generic_odata": odata_config.odata_service_url != "",
            "sap_odata": odata_config.sap_odata_url != ""
        },
        "auth_type": odata_config.odata_auth_type,
        "timestamp": datetime.utcnow().isoformat()
    }
    
    return health
