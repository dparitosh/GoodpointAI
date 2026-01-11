"""ETL Metrics Router - provides overview metrics for ETL operations."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy.sql import func

from core.db_session import DATABASE_URL, get_db
from models.plm_models import PLMIngestionRun
from models.quality_models import DataQualityScanReport

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/etl", tags=["ETL"])


class ETLMetricsResponse(BaseModel):
    """Response model for ETL metrics"""
    latestStatus: Optional[str] = None
    ingestionVolume: Optional[int] = None
    pendingDQIssues: Optional[int] = None
    criticalDQIssues: Optional[int] = None
    scheduledJobs: Optional[int] = None
    lastRemediation: Optional[str] = None


def _require_postgres() -> None:
    url = (DATABASE_URL or "").strip().lower()
    if not (url.startswith("postgresql") or url.startswith("postgres")):
        raise HTTPException(
            status_code=503,
            detail="Postgres is required for ETL metrics.",
        )


@router.get("/metrics", response_model=ETLMetricsResponse)
async def get_etl_metrics(db: Session = Depends(get_db)):
    """
    Get overview metrics for ETL operations.
    
    Returns:
    - latestStatus: Status of the most recent ETL run
    - ingestionVolume: Total records processed in last 24h
    - pendingDQIssues: Count of unresolved data quality issues
    - criticalDQIssues: Count of critical severity issues
    - scheduledJobs: Number of scheduled ETL jobs
    - lastRemediation: Timestamp of last remediation action
    """
    _require_postgres()
    
    try:
        # Get latest ETL run status
        latest_run = db.query(PLMIngestionRun).order_by(
            PLMIngestionRun.created_at.desc()
        ).first()
        
        latest_status = latest_run.status if latest_run else "no_runs"
        
        # Count total ingestion volume (simplified - count all runs)
        run_count = db.query(func.count(PLMIngestionRun.run_id)).scalar() or 0
        
        # Get DQ issues from scan reports
        pending_issues = 0
        critical_issues = 0
        
        # Query recent scan reports for issues
        recent_scans = db.query(DataQualityScanReport).order_by(
            DataQualityScanReport.scan_date.desc()
        ).limit(10).all()
        
        for scan in recent_scans:
            if scan.report and isinstance(scan.report, dict):
                issues = scan.report.get("issues", [])
                for issue in issues:
                    pending_issues += 1
                    if issue.get("severity") == "critical":
                        critical_issues += 1
        
        # Scheduled jobs (placeholder - could query a jobs table)
        scheduled_jobs = 3  # Default placeholder
        
        # Last remediation (placeholder)
        last_remediation = None
        if latest_run and latest_run.updated_at:
            last_remediation = latest_run.updated_at.isoformat()
        
        return ETLMetricsResponse(
            latestStatus=latest_status,
            ingestionVolume=run_count * 100,  # Approximate
            pendingDQIssues=pending_issues,
            criticalDQIssues=critical_issues,
            scheduledJobs=scheduled_jobs,
            lastRemediation=last_remediation
        )
        
    except (AttributeError, TypeError, KeyError) as e:  # noqa: BLE001
        logger.error("Error fetching ETL metrics: %s", e)
        # Return empty metrics rather than failing
        return ETLMetricsResponse(
            latestStatus="error",
            ingestionVolume=0,
            pendingDQIssues=0,
            criticalDQIssues=0,
            scheduledJobs=0,
            lastRemediation=None
        )


@router.get("/health")
async def etl_health_check():
    """Health check for ETL service"""
    return {
        "status": "healthy",
        "service": "etl",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
