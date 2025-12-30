"""
Analytics API Router
Provides endpoints for metrics ingestion and retrieval.
"""
import logging
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timezone

from services.analytics_storage_service import analytics_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


class UploadMetricRequest(BaseModel):
    """Request model for recording upload metrics"""
    file_name: str
    file_size_mb: float
    upload_duration_sec: float
    status: str
    user: str
    source: str = "gateway"


class ServiceHealthRequest(BaseModel):
    """Request model for recording service health"""
    service_name: str
    status: str
    cpu_percent: float
    memory_percent: float
    response_time_ms: float
    error_rate: float


class MigrationQualityRequest(BaseModel):
    """Request model for recording migration quality"""
    session_id: str
    quality_score: float
    rows_migrated: int
    rows_failed: int
    schema_drift_issues: int = 0


@router.post("/upload-metric")
async def record_upload_metric(request: UploadMetricRequest):
    """
    Record upload metrics
    
    **Request Body:**
    - file_name: Name of uploaded file
    - file_size_mb: File size in megabytes
    - upload_duration_sec: Upload duration in seconds
    - status: success/failed
    - user: User identifier
    - source: Source system (default: gateway)
    
    **Response:**
    - Status and confirmation message
    """
    try:
        result = await analytics_service.record_upload_metric(
            file_name=request.file_name,
            file_size_mb=request.file_size_mb,
            upload_duration_sec=request.upload_duration_sec,
            status=request.status,
            user=request.user,
            source=request.source
        )
        
        return result
        
    except Exception as e:
        logger.error("Error recording upload metric: %s", e)
        detail = {
            "status": "error",
            "message": str(e),
            "timestamp": datetime.now(timezone.utc).replace(tzinfo=None).isoformat(),
        }
        raise HTTPException(status_code=500, detail=detail) from e


@router.post("/service-health")
async def record_service_health(request: ServiceHealthRequest):
    """
    Record service health metrics
    
    **Request Body:**
    - service_name: Name of the service
    - status: healthy/degraded/down
    - cpu_percent: CPU usage percentage
    - memory_percent: Memory usage percentage
    - response_time_ms: Response time in milliseconds
    - error_rate: Error rate percentage
    
    **Response:**
    - Status and confirmation message
    """
    try:
        result = await analytics_service.record_service_health(
            service_name=request.service_name,
            status=request.status,
            cpu_percent=request.cpu_percent,
            memory_percent=request.memory_percent,
            response_time_ms=request.response_time_ms,
            error_rate=request.error_rate
        )
        
        return result
        
    except Exception as e:
        logger.error("Error recording service health: %s", e)
        detail = {
            "status": "error",
            "message": str(e),
            "timestamp": datetime.now(timezone.utc).replace(tzinfo=None).isoformat(),
        }
        raise HTTPException(status_code=500, detail=detail) from e


@router.post("/migration-quality")
async def record_migration_quality(request: MigrationQualityRequest):
    """
    Record migration quality metrics
    
    **Request Body:**
    - session_id: Migration session identifier
    - quality_score: Quality score (0-100)
    - rows_migrated: Number of rows successfully migrated
    - rows_failed: Number of rows that failed
    - schema_drift_issues: Number of schema drift issues detected
    
    **Response:**
    - Status and confirmation message
    """
    try:
        result = await analytics_service.record_migration_quality(
            session_id=request.session_id,
            quality_score=request.quality_score,
            rows_migrated=request.rows_migrated,
            rows_failed=request.rows_failed,
            schema_drift_issues=request.schema_drift_issues
        )
        
        return result
        
    except Exception as e:
        logger.error("Error recording migration quality: %s", e)
        detail = {
            "status": "error",
            "message": str(e),
            "timestamp": datetime.now(timezone.utc).replace(tzinfo=None).isoformat(),
        }
        raise HTTPException(status_code=500, detail=detail) from e


@router.get("/uploads")
async def get_upload_metrics(
    limit: int = Query(100, ge=1, le=1000),
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
):
    """
    Get upload metrics for governance dashboard
    
    **Query Parameters:**
    - limit: Maximum number of records to return (default: 100)
    - start_date: Filter by start date (ISO 8601 format)
    - end_date: Filter by end date (ISO 8601 format)
    
    **Response:**
    - Upload metrics with aggregates (total, success rate, avg duration, etc.)
    """
    try:
        result = await analytics_service.get_upload_metrics(
            limit=limit,
            start_date=start_date,
            end_date=end_date
        )
        
        return result
        
    except Exception as e:
        logger.error("Error retrieving upload metrics: %s", e)
        detail = {
            "status": "error",
            "message": str(e),
            "timestamp": datetime.now(timezone.utc).replace(tzinfo=None).isoformat(),
        }
        raise HTTPException(status_code=500, detail=detail) from e


@router.get("/service-health")
async def get_service_health_metrics(
    service_name: Optional[str] = None,
    limit: int = Query(50, ge=1, le=500)
):
    """
    Get service health metrics
    
    **Query Parameters:**
    - service_name: Filter by specific service (optional)
    - limit: Maximum number of records to return (default: 50)
    
    **Response:**
    - Service health metrics with summary by service
    """
    try:
        result = await analytics_service.get_service_health_metrics(
            service_name=service_name,
            limit=limit
        )
        
        return result
        
    except Exception as e:
        logger.error("Error retrieving service health metrics: %s", e)
        detail = {
            "status": "error",
            "message": str(e),
            "timestamp": datetime.now(timezone.utc).replace(tzinfo=None).isoformat(),
        }
        raise HTTPException(status_code=500, detail=detail) from e


@router.get("/migration-quality")
async def get_migration_quality_metrics(
    session_id: Optional[str] = None,
    limit: int = Query(50, ge=1, le=500)
):
    """
    Get migration quality metrics
    
    **Query Parameters:**
    - session_id: Filter by specific migration session (optional)
    - limit: Maximum number of records to return (default: 50)
    
    **Response:**
    - Migration quality metrics with aggregates
    """
    try:
        result = await analytics_service.get_migration_quality_metrics(
            session_id=session_id,
            limit=limit
        )
        
        return result
        
    except Exception as e:
        logger.error("Error retrieving migration quality metrics: %s", e)
        detail = {
            "status": "error",
            "message": str(e),
            "timestamp": datetime.now(timezone.utc).replace(tzinfo=None).isoformat(),
        }
        raise HTTPException(status_code=500, detail=detail) from e


@router.get("/health")
async def analytics_health_check():
    """
    Health check endpoint for analytics service
    
    **Response:**
    - Service status and basic statistics
    """
    try:
        # Get basic stats
        await analytics_service.get_upload_metrics(limit=1)
        await analytics_service.get_service_health_metrics(limit=1)
        
        return {
            "status": "success",
            "message": "Analytics service is healthy",
            "data": {
                "service": "analytics_storage",
                "status": "operational",
                "total_upload_records": len(analytics_service.metrics_store["upload_metrics"]),
                "total_health_records": len(analytics_service.metrics_store["service_health"]),
                "total_quality_records": len(analytics_service.metrics_store["migration_quality"])
            },
            "timestamp": datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
        }
        
    except Exception as e:
        logger.error("Analytics health check failed: %s", e)
        detail = {
            "status": "error",
            "message": str(e),
            "timestamp": datetime.now(timezone.utc).replace(tzinfo=None).isoformat(),
        }
        raise HTTPException(status_code=500, detail=detail) from e
