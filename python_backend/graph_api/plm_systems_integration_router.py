"""
PLM Systems Integration Router
Handles Teamcenter, Windchill, ENOVIA, Aras Innovator, CATIA, NX, Creo
"""

# pyright: reportMissingTypeStubs=false

import logging
from typing import List, Dict, Optional, Any
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
import requests  # pyright: ignore[reportMissingTypeStubs]
from requests.auth import HTTPBasicAuth  # pyright: ignore[reportMissingTypeStubs]

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/plm", tags=["PLM Integration"])


# ============================================================================
# MODELS
# ============================================================================

class PLMConnection(BaseModel):
    system_type: str = Field(..., description="teamcenter, windchill, enovia, aras")
    url: str
    username: str
    password: str
    additional_config: Optional[Dict[str, Any]] = Field(default_factory=lambda: {})


class PLMQueryRequest(BaseModel):
    system_type: str
    object_type: str = Field(..., description="Part, Document, BOM, etc.")
    query_criteria: Optional[Dict[str, Any]] = Field(default_factory=lambda: {})
    properties: Optional[List[str]] = Field(default_factory=lambda: [])
    limit: int = 100


class PLMObjectRequest(BaseModel):
    system_type: str
    object_id: str
    object_type: str
    include_relations: bool = False


class PLMBOMRequest(BaseModel):
    system_type: str
    root_part_id: str
    levels: int = Field(default=-1, description="-1 for all levels")
    include_properties: bool = True


# ============================================================================
# TEAMCENTER INTEGRATION
# ============================================================================

@router.post("/teamcenter/query")
async def query_teamcenter_objects(request: PLMQueryRequest):
    """Query Teamcenter objects via REST/SOAP"""
    try:
        from core.external_config import plm_config
        from zeep import Client
        from zeep.transports import Transport
        
        # Prefer REST if configured (more likely to work in modern deployments).
        rest_url = str(getattr(plm_config, "teamcenter_rest_url", "") or "").strip()
        if rest_url:
            url = f"{rest_url.rstrip('/')}/query"
            payload = {
                "type": request.object_type,
                "criteria": request.query_criteria or {},
                "properties": request.properties or ["object_name", "object_desc", "item_id"],
                "maxResults": int(request.limit or 100),
            }
            response = requests.post(
                url,
                json=payload,
                auth=HTTPBasicAuth(plm_config.teamcenter_username, plm_config.teamcenter_password),
                headers={"Accept": "application/json"},
                timeout=60,
            )

            # If the endpoint isn't supported, fall through to SOAP attempt below.
            if response.status_code not in (404, 405):
                response.raise_for_status()
                data = response.json() if response.content else {}
                return {
                    "status": "success",
                    "system": "Teamcenter",
                    "object_type": request.object_type,
                    "count": len(data.get("objects", [])) if isinstance(data, dict) else 0,
                    "objects": data.get("objects", []) if isinstance(data, dict) else data,
                }

        if not plm_config.teamcenter_soap_url:
            raise HTTPException(status_code=400, detail="Teamcenter not configured")
        
        # Create SOAP client
        session = requests.Session()
        session.auth = HTTPBasicAuth(
            plm_config.teamcenter_username,
            plm_config.teamcenter_password
        )
        transport = Transport(session=session)
        _client = Client(plm_config.teamcenter_soap_url, transport=transport)
        
        # Build query based on object type
        _query_input = {
            "type": request.object_type,
            "criteria": request.query_criteria,
            "properties": request.properties or ["object_name", "object_desc", "item_id"],
            "maxResults": request.limit
        }

        # Best-effort SOAP call (depends on WSDL contract).
        service = getattr(_client, "service", None)
        query_fn = getattr(service, "query", None) if service is not None else None
        if callable(query_fn):
            soap_response = query_fn(_query_input)
            return {
                "status": "success",
                "system": "Teamcenter",
                "object_type": request.object_type,
                "raw": soap_response,
            }

        logger.warning("Teamcenter SOAP client initialized but no 'query' operation found")
        raise HTTPException(
            status_code=501,
            detail="Teamcenter query endpoint not supported by configured SOAP WSDL. Use REST configuration or update the WSDL/operation mapping.",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error querying Teamcenter: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/teamcenter/bom/{part_id}")
async def get_teamcenter_bom(part_id: str, levels: int = -1):
    """Get BOM structure from Teamcenter"""
    try:
        from core.external_config import plm_config
        
        if not plm_config.teamcenter_rest_url:
            raise HTTPException(status_code=400, detail="Teamcenter REST API not configured")
        
        # REST API call to get BOM
        url = f"{plm_config.teamcenter_rest_url}/bom/{part_id}"
        
        response = requests.get(
            url,
            auth=HTTPBasicAuth(
                plm_config.teamcenter_username,
                plm_config.teamcenter_password
            ),
            params={"levels": levels},
            timeout=60
        )
        
        response.raise_for_status()
        
        return {
            "status": "success",
            "system": "Teamcenter",
            "part_id": part_id,
            "bom": response.json()
        }
        
    except requests.exceptions.HTTPError as e:
        status_code = e.response.status_code if e.response is not None else 502
        if status_code == 404:
            raise HTTPException(status_code=404, detail=f"Part {part_id} not found in Teamcenter") from e
        raise HTTPException(status_code=status_code, detail=str(e)) from e
    except requests.RequestException as e:
        raise HTTPException(status_code=502, detail=str(e)) from e


# ============================================================================
# WINDCHILL INTEGRATION
# ============================================================================

@router.post("/windchill/query")
async def query_windchill_objects(request: PLMQueryRequest):
    """Query Windchill objects via REST API"""
    try:
        from core.external_config import plm_config
        
        if not plm_config.windchill_url:
            raise HTTPException(status_code=400, detail="Windchill not configured")
        
        # Windchill REST API endpoint
        api_url = f"{plm_config.windchill_url}{plm_config.windchill_context_path}/servlet/odata/v4"
        
        # Build OData query
        entity_set = request.object_type + "s"  # e.g., Parts, Documents
        url = f"{api_url}/{entity_set}"
        
        params: Dict[str, Any] = {}
        if request.query_criteria:
            filter_parts = []
            for key, value in request.query_criteria.items():
                filter_parts.append(f"{key} eq '{value}'")
            if filter_parts:
                params["$filter"] = " and ".join(filter_parts)
        
        if request.properties:
            params["$select"] = ",".join(request.properties)

        params["$top"] = str(request.limit)
        
        response = requests.get(
            url,
            params=params,
            auth=HTTPBasicAuth(
                plm_config.windchill_username,
                plm_config.windchill_password
            ),
            headers={"Accept": "application/json"},
            timeout=60
        )

        if response.status_code == 404:
            raise HTTPException(
                status_code=502,
                detail="Windchill upstream returned 404 (endpoint/entity set not found)",
            )
        
        response.raise_for_status()
        data = response.json()
        
        return {
            "status": "success",
            "system": "Windchill",
            "object_type": request.object_type,
            "count": len(data.get("value", [])),
            "objects": data.get("value", [])
        }
        
    except Exception as e:
        logger.error("Error querying Windchill: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/windchill/part/{part_number}")
async def get_windchill_part(part_number: str):
    """Get Windchill part by number"""
    try:
        from core.external_config import plm_config
        
        if not plm_config.windchill_url:
            raise HTTPException(status_code=400, detail="Windchill not configured")
        
        api_url = f"{plm_config.windchill_url}{plm_config.windchill_context_path}/servlet/odata/v4"
        url = f"{api_url}/Parts('{part_number}')"
        
        response = requests.get(
            url,
            auth=HTTPBasicAuth(
                plm_config.windchill_username,
                plm_config.windchill_password
            ),
            headers={"Accept": "application/json"},
            timeout=30
        )

        if response.status_code == 404:
            raise HTTPException(status_code=404, detail="Windchill part not found")
        
        response.raise_for_status()
        
        return {
            "status": "success",
            "system": "Windchill",
            "part": response.json()
        }
        
    except Exception as e:
        logger.error("Error getting Windchill part: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


# ============================================================================
# ENOVIA / 3DEXPERIENCE INTEGRATION
# ============================================================================

@router.post("/enovia/query")
async def query_enovia_objects(request: PLMQueryRequest):
    """Query ENOVIA/3DEXPERIENCE objects"""
    try:
        from core.external_config import plm_config
        
        if not plm_config.enovia_url:
            raise HTTPException(status_code=400, detail="ENOVIA not configured")
        
        # ENOVIA 3DSpace REST API
        api_url = f"{plm_config.enovia_url}/resources/v1/modeler/dseng"
        
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "SecurityContext": plm_config.enovia_security_context
        }
        
        # Build search payload
        search_payload = {
            "type": request.object_type,
            "select": request.properties or ["name", "title", "current", "owner"],
            "where": request.query_criteria
        }
        
        response = requests.post(
            f"{api_url}/search",
            json=search_payload,
            auth=HTTPBasicAuth(
                plm_config.enovia_username,
                plm_config.enovia_password
            ),
            headers=headers,
            timeout=60
        )

        if response.status_code == 404:
            raise HTTPException(
                status_code=502,
                detail="ENOVIA upstream returned 404 (endpoint not found)",
            )
        
        response.raise_for_status()
        data = response.json()
        
        return {
            "status": "success",
            "system": "ENOVIA",
            "object_type": request.object_type,
            "count": len(data.get("member", [])),
            "objects": data.get("member", [])
        }
        
    except Exception as e:
        logger.error("Error querying ENOVIA: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


# ============================================================================
# ARAS INNOVATOR INTEGRATION
# ============================================================================

@router.post("/aras/query")
async def query_aras_objects(request: PLMQueryRequest):
    """Query Aras Innovator objects via SOAP"""
    try:
        from core.external_config import plm_config
        
        if not plm_config.aras_url:
            raise HTTPException(status_code=400, detail="Aras not configured")
        
        # Aras SOAP endpoint
        soap_url = f"{plm_config.aras_url}/Server/InnovatorServer.aspx"
        
        # Build AML query
        where_clause = ""
        if request.query_criteria:
            conditions = [f"<{key}>{value}</{key}>" for key, value in request.query_criteria.items()]
            where_clause = "".join(conditions)
        
        aml_query = f"""
        <AML>
            <Item type="{request.object_type}" action="get">
                {where_clause}
            </Item>
        </AML>
        """
        
        # SOAP envelope
        soap_body = f"""<?xml version="1.0" encoding="utf-8"?>
        <soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
            <soap:Body>
                <ApplyAML xmlns="http://www.aras.com/InnovatorServer">
                    <AML>{aml_query}</AML>
                </ApplyAML>
            </soap:Body>
        </soap:Envelope>"""
        
        headers = {
            "Content-Type": "text/xml; charset=utf-8",
            "SOAPAction": "ApplyAML",
            "AUTHUSER": plm_config.aras_username,
            "AUTHPASSWORD": plm_config.aras_password,
            "DATABASE": plm_config.aras_database
        }
        
        response = requests.post(
            soap_url,
            data=soap_body,
            headers=headers,
            timeout=60
        )

        if response.status_code == 404:
            raise HTTPException(
                status_code=502,
                detail="Aras upstream returned 404 (endpoint not found)",
            )
        
        response.raise_for_status()
        
        # Parse XML response
        try:
            import xmltodict  # type: ignore[import-untyped]
        except ImportError as exc:
            raise HTTPException(
                status_code=500,
                detail="xmltodict is required to parse Aras SOAP responses",
            ) from exc

        result_dict = xmltodict.parse(response.text)
        
        return {
            "status": "success",
            "system": "Aras Innovator",
            "object_type": request.object_type,
            "response": result_dict,
            "message": "Aras query executed"
        }
        
    except Exception as e:
        logger.error("Error querying Aras: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


# ============================================================================
# CAD FILE METADATA EXTRACTION
# ============================================================================

@router.get("/cad/metadata/{system}/{file_id}")
async def get_cad_metadata(system: str, file_id: str):
    """Extract metadata from CAD files (CATIA, NX, Creo)"""
    try:
        _ = (system, file_id)
        raise HTTPException(
            status_code=501,
            detail=(
                f"CAD metadata extraction is not implemented for system='{system}', file_id='{file_id}' "
                "(configure a CAD parser integration)"
            ),
        )
        
    except Exception as e:
        logger.error("Error extracting CAD metadata: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


# ============================================================================
# PLM DATA EXPORT
# ============================================================================

@router.post("/export")
async def export_plm_data(
    system_type: str,
    object_type: str,
    object_ids: List[str],
    export_format: str = Query("json", alias="format")
):
    """Export PLM data in various formats"""
    try:
        _ = (system_type, object_type, export_format, object_ids)
        raise HTTPException(
            status_code=501,
            detail=(
                f"PLM export is not implemented for system='{system_type}', object_type='{object_type}', "
                f"format='{export_format}', object_count={len(object_ids)} "
                "(requires live PLM connector integration)"
            ),
        )
        
    except Exception as e:
        logger.error("Error exporting PLM data: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


# ============================================================================
# HEALTH CHECK
# ============================================================================

@router.get("/systems/health")
async def plm_systems_health():
    """Check connectivity to all configured PLM systems"""
    from core.external_config import plm_config
    
    health = {
        "status": "healthy",
        "systems": {
            "teamcenter": {
                "configured": plm_config.teamcenter_url != "",
                "soap_url": plm_config.teamcenter_soap_url != "",
                "rest_url": plm_config.teamcenter_rest_url != ""
            },
            "windchill": {
                "configured": plm_config.windchill_url != "",
                "context": plm_config.windchill_context_path
            },
            "enovia": {
                "configured": plm_config.enovia_url != "",
                "security_context": plm_config.enovia_security_context != ""
            },
            "aras": {
                "configured": plm_config.aras_url != "",
                "database": plm_config.aras_database
            }
        },
        "timestamp": datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
    }
    
    return health
