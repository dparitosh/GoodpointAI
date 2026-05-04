"""
API Gateway Integration Router
Handles Kong, Apigee, and generic API Gateway management
"""
import logging
from typing import List, Dict, Optional, Any
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Query, Response
from pydantic import BaseModel, Field
import requests  # type: ignore[import-untyped]
from requests.auth import HTTPBasicAuth  # type: ignore[import-untyped]

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/gateway", tags=["API Gateway"])


# ============================================================================
# MODELS
# ============================================================================

class APIRoute(BaseModel):
    name: str
    path: str
    methods: List[str] = Field(default_factory=lambda: ["GET", "POST", "PUT", "DELETE"])
    upstream_url: str
    plugins: Optional[List[Dict[str, Any]]] = Field(default_factory=list)


class APIConsumer(BaseModel):
    username: str
    custom_id: Optional[str] = None
    tags: Optional[List[str]] = Field(default_factory=list)


class RateLimitConfig(BaseModel):
    requests_per_minute: int = 100
    requests_per_hour: int = 1000


class GenericRouteConfig(BaseModel):
    """Route configuration for generic API gateway"""
    path: str
    method: str = "GET"
    target_url: str
    rate_limit: Optional[int] = None
    auth_required: bool = False
    transformation: Optional[Dict[str, Any]] = None


class ProxyRequest(BaseModel):
    """Proxy request configuration"""
    method: str = "GET"
    path: str
    headers: Optional[Dict[str, str]] = Field(default_factory=dict)
    body: Optional[Any] = None
    query_params: Optional[Dict[str, str]] = Field(default_factory=dict)


class RateLimitSetting(BaseModel):
    """Rate limit setting for an endpoint"""
    endpoint: str
    requests_per_minute: int = 60
    burst_size: int = 10


class TransformationConfig(BaseModel):
    """Request/response transformation configuration"""
    route_pattern: str
    type: str = Field(..., description="'request' or 'response'")
    transformation: Dict[str, Any]


# In-memory storage for generic gateway (in production, use database)
_gateway_routes: Dict[str, Dict[str, Any]] = {}
_rate_limits: Dict[str, Dict[str, Any]] = {}
_transformations: List[Dict[str, Any]] = []


# ============================================================================
# GENERIC GATEWAY ENDPOINTS (Frontend-compatible)
# ============================================================================

@router.get("/routes")
async def list_routes(
    response: Response,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
):
    """List all registered routes (generic gateway)"""
    routes = list(_gateway_routes.values())
    total_count = len(routes)
    response.headers["X-Total-Count"] = str(total_count)
    routes_page = routes[skip : skip + limit]
    
    return {
        "status": "success",
        "routes": routes_page,
        "count": len(routes_page),
        "total": total_count
    }


@router.post("/routes")
async def register_route(config: GenericRouteConfig):
    """Register a new route in the generic gateway"""
    import uuid
    
    route_id = str(uuid.uuid4())
    route_data = {
        "id": route_id,
        "path": config.path,
        "method": config.method,
        "target_url": config.target_url,
        "rate_limit": config.rate_limit,
        "auth_required": config.auth_required,
        "transformation": config.transformation,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "active"
    }
    
    _gateway_routes[route_id] = route_data
    logger.info("Registered route: %s %s -> %s", config.method, config.path, config.target_url)
    
    return {
        "status": "success",
        "message": "Route registered",
        "route": route_data
    }


@router.delete("/routes/{route_id}")
async def delete_route(route_id: str):
    """Delete a route from the gateway"""
    if route_id not in _gateway_routes:
        raise HTTPException(status_code=404, detail="Route not found")
    
    del _gateway_routes[route_id]
    return {"status": "success", "message": "Route deleted"}


@router.post("/proxy")
async def proxy_request(request: ProxyRequest):
    """Proxy a request through the gateway"""
    import httpx
    
    # Find matching route
    matching_route = None
    for route in _gateway_routes.values():
        if route["path"] == request.path or request.path.startswith(route["path"]):
            matching_route = route
            break
    
    if not matching_route:
        # If no route registered, allow passthrough with warning
        logger.warning("No route found for path: %s, allowing passthrough", request.path)
    
    target_url = matching_route["target_url"] if matching_route else request.path
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.request(
                method=request.method,
                url=target_url,
                headers=request.headers or {},
                params=request.query_params or {},
                json=request.body if request.body else None
            )
            
            return {
                "status": "success",
                "request": {
                    "method": request.method,
                    "path": request.path,
                    "target": target_url
                },
                "response": {
                    "status_code": response.status_code,
                    "headers": dict(response.headers),
                    "body": response.text[:1000] if response.text else None
                }
            }
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Gateway timeout") from None
    except httpx.ConnectError as e:
        raise HTTPException(status_code=502, detail=f"Bad gateway: {str(e)}") from e
    except Exception as e:
        logger.error("Proxy request failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/rate-limits")
async def get_rate_limits():
    """Get all rate limit configurations"""
    return {
        "status": "success",
        "rate_limits": _rate_limits
    }


@router.post("/rate-limit")
async def set_rate_limit(config: RateLimitSetting):
    """Set rate limit for an endpoint"""
    _rate_limits[config.endpoint] = {
        "endpoint": config.endpoint,
        "requests_per_minute": config.requests_per_minute,
        "burst_size": config.burst_size,
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    
    return {
        "status": "success",
        "message": "Rate limit configured",
        "endpoint": config.endpoint,
        "limit": _rate_limits[config.endpoint]
    }


@router.post("/transformation")
async def add_transformation(config: TransformationConfig):
    """Add request/response transformation rule"""
    if config.type not in ("request", "response"):
        raise HTTPException(status_code=400, detail="Type must be 'request' or 'response'")
    
    transformation_data = {
        "id": len(_transformations) + 1,
        "route_pattern": config.route_pattern,
        "type": config.type,
        "transformation": config.transformation,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    _transformations.append(transformation_data)
    
    return {
        "status": "success",
        "message": "Transformation added",
        **transformation_data
    }


@router.get("/transformations")
async def list_transformations():
    """List all transformations"""
    return {
        "status": "success",
        "transformations": _transformations
    }


@router.get("/metrics")
async def get_gateway_metrics(
    time_range: str = Query("1h", description="Time range for metrics")
):
    """Get gateway metrics based on registered routes, rate limits, and transformations."""
    return {
        "status": "success",
        "time_range": time_range,
        "metrics": {
            "routes_count": len(_gateway_routes),
            "rate_limits_active": len(_rate_limits),
            "transformations_active": len(_transformations)
        },
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


# ============================================================================
# KONG API GATEWAY ENDPOINTS
# ============================================================================

@router.post("/kong/services")
async def create_kong_service(name: str, url: str):
    """Create Kong service"""
    try:
        from core.external_config import api_gateway_config
        
        if not api_gateway_config.kong_admin_url:
            raise HTTPException(status_code=400, detail="Kong not configured")
        
        service_data = {
            "name": name,
            "url": url
        }
        
        response = requests.post(
            f"{api_gateway_config.kong_admin_url}/services",
            json=service_data,
            timeout=30
        )
        response.raise_for_status()
        
        return {
            "status": "success",
            "message": "Kong service created",
            "service": response.json()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error creating Kong service: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/kong/routes")
async def create_kong_route(route: APIRoute):
    """Create Kong route"""
    try:
        from core.external_config import api_gateway_config

        if not api_gateway_config.kong_admin_url:
            raise HTTPException(status_code=400, detail="Kong not configured")
        
        # First, ensure service exists
        service_name = route.name + "-service"
        
        route_data = {
            "name": route.name,
            "paths": [route.path],
            "methods": route.methods,
            "service": {"name": service_name}
        }
        
        response = requests.post(
            f"{api_gateway_config.kong_admin_url}/routes",
            json=route_data,
            timeout=30
        )
        response.raise_for_status()
        
        return {
            "status": "success",
            "message": "Kong route created",
            "route": response.json()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error creating Kong route: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/kong/services")
async def list_kong_services(
    response: Response,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
):
    """List all Kong services"""
    try:
        from core.external_config import api_gateway_config
        
        kong_resp = requests.get(
            f"{api_gateway_config.kong_admin_url}/services",
            timeout=30
        )
        kong_resp.raise_for_status()
        
        data = kong_resp.json()
        services = data.get("data", [])
        total_count = len(services)
        response.headers["X-Total-Count"] = str(total_count)
        services_page = services[skip : skip + limit]
        
        return {
            "status": "success",
            "count": len(services_page),
            "services": services_page,
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error listing Kong services: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/kong/plugins/rate-limiting")
async def add_kong_rate_limiting(service_name: str, config: RateLimitConfig):
    """Add rate limiting plugin to Kong service"""
    try:
        from core.external_config import api_gateway_config
        
        plugin_data = {
            "name": "rate-limiting",
            "service": {"name": service_name},
            "config": {
                "minute": config.requests_per_minute,
                "hour": config.requests_per_hour,
                "policy": "local"
            }
        }
        
        response = requests.post(
            f"{api_gateway_config.kong_admin_url}/plugins",
            json=plugin_data,
            timeout=30
        )
        response.raise_for_status()
        
        return {
            "status": "success",
            "message": "Rate limiting enabled",
            "plugin": response.json()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error adding Kong rate limiting: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/kong/consumers")
async def create_kong_consumer(consumer: APIConsumer):
    """Create Kong consumer"""
    try:
        from core.external_config import api_gateway_config
        
        consumer_data = {
            "username": consumer.username,
            "custom_id": consumer.custom_id,
            "tags": consumer.tags
        }
        
        response = requests.post(
            f"{api_gateway_config.kong_admin_url}/consumers",
            json=consumer_data,
            timeout=30
        )
        response.raise_for_status()
        
        return {
            "status": "success",
            "message": "Kong consumer created",
            "consumer": response.json()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error creating Kong consumer: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


# ============================================================================
# APIGEE ENDPOINTS
# ============================================================================

@router.post("/apigee/proxies")
async def create_apigee_proxy(name: str, base_path: str, target_url: str):
    """Create Apigee API proxy"""
    try:
        from core.external_config import api_gateway_config
        
        if not api_gateway_config.apigee_org:
            raise HTTPException(status_code=400, detail="Apigee not configured")
        
        # Apigee Management API
        apigee_url = f"https://api.enterprise.apigee.com/v1/organizations/{api_gateway_config.apigee_org}/apis"
        
        proxy_config = {
            "name": name,
            "basepaths": [base_path],
            "targetEndpoint": {
                "url": target_url
            }
        }
        
        response = requests.post(
            apigee_url,
            json=proxy_config,
            auth=HTTPBasicAuth(
                api_gateway_config.apigee_username,
                api_gateway_config.apigee_password
            ),
            headers={"Content-Type": "application/json"},
            timeout=30
        )

        if response.status_code == 404:
            raise HTTPException(
                status_code=502,
                detail="Apigee upstream returned 404 (org or endpoint not found)",
            )
        
        response.raise_for_status()
        
        return {
            "status": "success",
            "message": "Apigee proxy created",
            "proxy": response.json()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error creating Apigee proxy: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/apigee/proxies")
async def list_apigee_proxies(
    response: Response,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
):
    """List Apigee API proxies"""
    try:
        from core.external_config import api_gateway_config

        # If Apigee isn't configured, don't attempt any outbound calls.
        if not api_gateway_config.apigee_org or not api_gateway_config.apigee_username or not api_gateway_config.apigee_password:
            raise HTTPException(status_code=400, detail="Apigee not configured")
        
        apigee_url = f"https://api.enterprise.apigee.com/v1/organizations/{api_gateway_config.apigee_org}/apis"
        
        apigee_resp = requests.get(
            apigee_url,
            auth=HTTPBasicAuth(
                api_gateway_config.apigee_username,
                api_gateway_config.apigee_password
            ),
            timeout=30
        )
        
        if apigee_resp.status_code == 404:
            raise HTTPException(
                status_code=502,
                detail="Apigee upstream returned 404 (org or endpoint not found)",
            )
        
        apigee_resp.raise_for_status()

        proxies = apigee_resp.json()
        if not isinstance(proxies, list):
            proxies = []

        total_count = len(proxies)
        response.headers["X-Total-Count"] = str(total_count)
        proxies_page = proxies[skip : skip + limit]
        
        return {
            "status": "success",
            "proxies": proxies_page,
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error listing Apigee proxies: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/apigee/products")
async def create_apigee_product(
    name: str,
    display_name: str,
    proxies: List[str],
    environments: List[str]
):
    """Create Apigee API product"""
    try:
        from core.external_config import api_gateway_config

        if not api_gateway_config.apigee_org or not api_gateway_config.apigee_username or not api_gateway_config.apigee_password:
            raise HTTPException(status_code=400, detail="Apigee not configured")
        
        apigee_url = f"https://api.enterprise.apigee.com/v1/organizations/{api_gateway_config.apigee_org}/apiproducts"
        
        product_config = {
            "name": name,
            "displayName": display_name,
            "apiResources": ["/"],
            "approvalType": "auto",
            "proxies": proxies,
            "environments": environments
        }
        
        response = requests.post(
            apigee_url,
            json=product_config,
            auth=HTTPBasicAuth(
                api_gateway_config.apigee_username,
                api_gateway_config.apigee_password
            ),
            headers={"Content-Type": "application/json"},
            timeout=30
        )

        if response.status_code == 404:
            raise HTTPException(
                status_code=502,
                detail="Apigee upstream returned 404 (org or endpoint not found)",
            )
        
        response.raise_for_status()
        
        return {
            "status": "success",
            "message": "Apigee product created",
            "product": response.json()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error creating Apigee product: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


# ============================================================================
# GENERIC API GATEWAY ENDPOINTS
# ============================================================================

@router.post("/generic/register")
async def register_api_endpoint(route: APIRoute):
    """Register API endpoint with generic gateway"""
    try:
        from core.external_config import api_gateway_config
        
        if not api_gateway_config.gateway_url:
            raise HTTPException(status_code=400, detail="Generic gateway not configured")
        
        headers = {"Content-Type": "application/json"}
        if api_gateway_config.gateway_api_key:
            headers["Authorization"] = f"Bearer {api_gateway_config.gateway_api_key}"

        # Generic gateway registration
        response = requests.post(
            f"{api_gateway_config.gateway_url}/api/routes",
            json=route.model_dump(),
            headers=headers,
            timeout=30
        )
        response.raise_for_status()
        
        return {
            "status": "success",
            "message": "API endpoint registered",
            "route": response.json()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error registering API endpoint: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


# ============================================================================
# MONITORING & ANALYTICS
# ============================================================================

@router.get("/analytics/traffic")
async def get_api_traffic_analytics(
    gateway: str = Query("kong", description="API gateway type"),
    timeframe: str = Query("1h", description="Analytics timeframe"),
):
    """Get API traffic analytics from gateway"""
    raise HTTPException(
        status_code=501,
        detail=(
            "Gateway traffic analytics is not implemented (requires gateway metrics integration); "
            f"requested gateway={gateway}, timeframe={timeframe}."
        ),
    )


# ============================================================================
# HEALTH CHECK
# ============================================================================

@router.get("/health")
async def gateway_health_check():
    """Check API gateway connectivity"""
    from core.external_config import api_gateway_config
    
    health = {
        "status": "healthy",
        "gateways": {
            "kong": {
                "configured": api_gateway_config.kong_admin_url != "",
                "admin_url": api_gateway_config.kong_admin_url
            },
            "apigee": {
                "configured": api_gateway_config.apigee_org != "",
                "organization": api_gateway_config.apigee_org
            },
            "generic": {
                "configured": api_gateway_config.gateway_url != ""
            }
        },
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    
    return health
