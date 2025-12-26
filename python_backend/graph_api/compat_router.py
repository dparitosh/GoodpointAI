from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List

from fastapi import APIRouter, Query, Request, Response
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/api", tags=["Compatibility"])


@router.get("/openapi.json")
async def openapi_json(request: Request):
    return JSONResponse(request.app.openapi())


@router.get("/docs")
async def swagger_ui_html():
    return get_swagger_ui_html(
        openapi_url="/api/openapi.json",
        title="GoodPoint AgenticAI API Docs",
    )


@router.get("/status")
async def get_status() -> Dict[str, Any]:
    # Lightweight status endpoint for clients that expect /api/status.
    return {
        "status": "ok",
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }


@router.get("/analytics/nodes")
async def analytics_nodes(
    response: Response,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    response.headers["X-Total-Count"] = str(len(items))
    return items[skip : skip + limit]


@router.get("/analytics/relationships")
async def analytics_relationships(
    response: Response,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    response.headers["X-Total-Count"] = str(len(items))
    return items[skip : skip + limit]


@router.get("/analytics/data-quality")
async def analytics_data_quality() -> Dict[str, Any]:
    return {
        "summary": {
            "total_tables_scanned": 0,
            "average_quality_score": 0,
            "critical_issues": 0,
            "total_issues": 0,
        },
        "recent_scans": [],
        "quality_trends": [],
        "top_issues": [],
    }


@router.get("/schema/discover")
async def schema_discover() -> Dict[str, Any]:
    return {
        "tables": [],
        "views": [],
        "schemas": [],
    }


@router.get("/schema/constraints")
async def schema_constraints(
    response: Response,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    response.headers["X-Total-Count"] = str(len(items))
    return items[skip : skip + limit]


@router.get("/user/preferences")
async def user_preferences() -> Dict[str, Any]:
    return {}


@router.get("/system/settings")
async def system_settings() -> Dict[str, Any]:
    return {}


@router.get("/dashboards")
async def dashboards(
    response: Response,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    response.headers["X-Total-Count"] = str(len(items))
    return items[skip : skip + limit]


@router.get("/pipelines")
async def pipelines(
    response: Response,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    response.headers["X-Total-Count"] = str(len(items))
    return items[skip : skip + limit]


@router.get("/reports")
async def reports(
    response: Response,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    response.headers["X-Total-Count"] = str(len(items))
    return items[skip : skip + limit]


@router.post("/reports/generate")
async def generate_report() -> Dict[str, Any]:
    return {"status": "queued"}


@router.get("/convert/templates")
async def convert_templates(
    response: Response,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    response.headers["X-Total-Count"] = str(len(items))
    return items[skip : skip + limit]


@router.get("/mappings/templates")
async def mapping_templates(
    response: Response,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    response.headers["X-Total-Count"] = str(len(items))
    return items[skip : skip + limit]


@router.get("/monitoring/health")
async def monitoring_health() -> Dict[str, Any]:
    return {"status": "healthy"}


@router.get("/monitoring/flow-metrics")
async def monitoring_flow_metrics() -> Dict[str, Any]:
    return {"metrics": []}


@router.get("/etl/metrics")
async def etl_metrics() -> Dict[str, Any]:
    return {"metrics": []}


@router.get("/migration/v2")
async def migration_v2() -> Dict[str, Any]:
    return {"version": "v2", "status": "available"}


@router.get("/data")
async def data_placeholder() -> Dict[str, Any]:
    return {"status": "ok"}


@router.get("/config/backup")
@router.post("/config/backup")
async def config_backup() -> Dict[str, Any]:
    return {"status": "not_implemented"}


@router.get("/config/restore")
@router.post("/config/restore")
async def config_restore() -> Dict[str, Any]:
    return {"status": "not_implemented"}


@router.get("/config/export")
@router.post("/config/export")
async def config_export() -> Dict[str, Any]:
    return {"status": "not_implemented"}
