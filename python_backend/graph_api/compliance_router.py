"""
Compliance & Audit API Router - REST endpoints for audit and compliance management

Provides complete API for audit trail access, compliance reporting, data
retention policy management, and access control administration.
"""

import logging
from datetime import datetime
from typing import List, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from core.db_session import get_db
from models.audit_models import (
    AuditEventCreate, AuditEvent, ComplianceEventCreate, ComplianceEvent,
    DataRetentionPolicyCreate, DataRetentionPolicy, AccessControlCreate, AccessControl,
    AuditEventType, ComplianceType, AuditReportRequest, ComplianceReportRequest
)
from services.audit_service import (
    AuditLogRepository, ComplianceRepository, DataRetentionRepository,
    AccessControlRepository, AuditAnalyticsService
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/compliance", tags=["compliance"])


# ============================================================================
# Audit Event Endpoints
# ============================================================================

@router.post("/audit/events", response_model=AuditEvent)
async def record_audit_event(request: AuditEventCreate, db: Session = Depends(get_db)):
    """Record an audit event"""
    try:
        with AuditLogRepository(db) as repo:
            return repo.create(request)
    except Exception as e:
        logger.error(f"Error recording audit event: {e}")
        raise HTTPException(status_code=500, detail="Failed to record audit event") from e


@router.get("/audit/events/{event_id}", response_model=AuditEvent)
async def get_audit_event(event_id: str, db: Session = Depends(get_db)):
    """Retrieve audit event by ID"""
    try:
        with AuditLogRepository(db) as repo:
            event = repo.read(event_id)
            if not event:
                raise HTTPException(status_code=404, detail="Audit event not found")
            return event
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving audit event: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve audit event") from e


@router.get("/audit/events", response_model=List[AuditEvent])
async def list_audit_events(
    resource_type: str = Query(None, description="Filter by resource type"),
    resource_id: str = Query(None, description="Filter by resource ID"),
    user_id: str = Query(None, description="Filter by user ID"),
    event_type: str = Query(None, description="Filter by event type"),
    start_date: datetime = Query(None, description="Filter by start date"),
    end_date: datetime = Query(None, description="Filter by end date"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db)
):
    """List audit events with optional filtering"""
    try:
        with AuditLogRepository(db) as repo:
            # Multi-filter query
            events = []
            if resource_type and resource_id:
                events = repo.list_by_resource(resource_type, resource_id, skip, limit)
            elif user_id:
                events = repo.list_by_user(user_id, skip, limit)
            elif event_type:
                try:
                    et = AuditEventType(event_type)
                    events = repo.list_by_event_type(et, skip, limit)
                except ValueError:
                    raise HTTPException(status_code=400, detail=f"Invalid event type: {event_type}")
            elif start_date and end_date:
                events = repo.list_by_date_range(start_date, end_date, skip, limit)
            
            return events if events else []
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing audit events: {e}")
        raise HTTPException(status_code=500, detail="Failed to list audit events") from e


@router.post("/audit/report", response_model=Dict[str, Any])
async def generate_audit_report(request: AuditReportRequest, db: Session = Depends(get_db)):
    """Generate audit report for date range"""
    try:
        with AuditLogRepository(db) as repo:
            events = repo.list_by_date_range(request.start_date, request.end_date, skip=0, limit=1000)
            
            # Filter by event types if specified
            if request.event_types:
                event_values = {et.value for et in request.event_types}
                events = [e for e in events if e.event_type.value in event_values]
            
            # Filter by resource types if specified
            if request.resource_types:
                events = [e for e in events if e.resource_type in request.resource_types]
            
            # Filter by users if specified
            if request.user_ids:
                events = [e for e in events if e.user_id in request.user_ids]
            
            return {
                "report_type": "audit_trail",
                "start_date": request.start_date.isoformat(),
                "end_date": request.end_date.isoformat(),
                "total_events": len(events),
                "events": [e.model_dump() for e in events],
                "generated_at": datetime.utcnow().isoformat(),
            }
    except Exception as e:
        logger.error(f"Error generating audit report: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate audit report") from e


# ============================================================================
# Compliance Event Endpoints
# ============================================================================

@router.post("/compliance/events", response_model=ComplianceEvent)
async def record_compliance_event(request: ComplianceEventCreate, db: Session = Depends(get_db)):
    """Record a compliance check event"""
    try:
        with ComplianceRepository(db) as repo:
            return repo.create(request)
    except Exception as e:
        logger.error(f"Error recording compliance event: {e}")
        raise HTTPException(status_code=500, detail="Failed to record compliance event") from e


@router.get("/compliance/events/{event_id}", response_model=ComplianceEvent)
async def get_compliance_event(event_id: str, db: Session = Depends(get_db)):
    """Retrieve compliance event by ID"""
    try:
        with ComplianceRepository(db) as repo:
            event = repo.read(event_id)
            if not event:
                raise HTTPException(status_code=404, detail="Compliance event not found")
            return event
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving compliance event: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve compliance event") from e


@router.post("/compliance/report", response_model=Dict[str, Any])
async def generate_compliance_report(request: ComplianceReportRequest, db: Session = Depends(get_db)):
    """Generate compliance status report"""
    try:
        results = []
        for compliance_type in request.compliance_types:
            status = AuditAnalyticsService.calculate_compliance_status(db, compliance_type)
            results.append(status)
        
        return {
            "report_type": "compliance_status",
            "report_date": datetime.utcnow().isoformat(),
            "compliance_frameworks": [ct.value for ct in request.compliance_types],
            "results": results,
            "overall_compliant": all(r["overall_status"] == "compliant" for r in results),
        }
    except Exception as e:
        logger.error(f"Error generating compliance report: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate compliance report") from e


# ============================================================================
# Data Retention Policy Endpoints
# ============================================================================

@router.post("/retention/policies", response_model=DataRetentionPolicy)
async def create_retention_policy(request: DataRetentionPolicyCreate, db: Session = Depends(get_db)):
    """Create data retention policy"""
    try:
        with DataRetentionRepository(db) as repo:
            return repo.create(request)
    except Exception as e:
        logger.error(f"Error creating retention policy: {e}")
        if "already exists" in str(e):
            raise HTTPException(status_code=409, detail=f"Policy for {request.data_type} already exists")
        raise HTTPException(status_code=500, detail="Failed to create retention policy") from e


@router.get("/retention/policies/{policy_id}", response_model=DataRetentionPolicy)
async def get_retention_policy(policy_id: str, db: Session = Depends(get_db)):
    """Retrieve retention policy by ID"""
    try:
        with DataRetentionRepository(db) as repo:
            policy = repo.read(policy_id)
            if not policy:
                raise HTTPException(status_code=404, detail="Retention policy not found")
            return policy
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving retention policy: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve retention policy") from e


@router.get("/retention/policies/type/{data_type}", response_model=DataRetentionPolicy)
async def get_retention_policy_by_type(data_type: str, db: Session = Depends(get_db)):
    """Retrieve retention policy by data type"""
    try:
        with DataRetentionRepository(db) as repo:
            policy = repo.read_by_type(data_type)
            if not policy:
                raise HTTPException(status_code=404, detail=f"No retention policy for data type: {data_type}")
            return policy
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving retention policy: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve retention policy") from e


@router.get("/retention/policies", response_model=List[DataRetentionPolicy])
async def list_retention_policies(skip: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=500), db: Session = Depends(get_db)):
    """List all retention policies"""
    try:
        with DataRetentionRepository(db) as repo:
            return repo.list_enabled(skip, limit)
    except Exception as e:
        logger.error(f"Error listing retention policies: {e}")
        raise HTTPException(status_code=500, detail="Failed to list retention policies") from e


@router.put("/retention/policies/{policy_id}", response_model=DataRetentionPolicy)
async def update_retention_policy(policy_id: str, request: DataRetentionPolicyCreate, db: Session = Depends(get_db)):
    """Update retention policy"""
    try:
        with DataRetentionRepository(db) as repo:
            updated = repo.update(policy_id, request.model_dump(exclude_unset=True))
            if not updated:
                raise HTTPException(status_code=404, detail="Retention policy not found")
            return updated
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating retention policy: {e}")
        raise HTTPException(status_code=500, detail="Failed to update retention policy") from e


# ============================================================================
# Access Control Endpoints
# ============================================================================

@router.post("/access-control", response_model=AccessControl)
async def create_access_rule(request: AccessControlCreate, db: Session = Depends(get_db)):
    """Create access control rule"""
    try:
        with AccessControlRepository(db) as repo:
            return repo.create(request)
    except Exception as e:
        logger.error(f"Error creating access rule: {e}")
        raise HTTPException(status_code=500, detail="Failed to create access rule") from e


@router.get("/access-control/{rule_id}", response_model=AccessControl)
async def get_access_rule(rule_id: str, db: Session = Depends(get_db)):
    """Retrieve access control rule"""
    try:
        with AccessControlRepository(db) as repo:
            rule = repo.read(rule_id)
            if not rule:
                raise HTTPException(status_code=404, detail="Access control rule not found")
            return rule
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving access rule: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve access rule") from e


@router.get("/access-control", response_model=List[AccessControl])
async def list_user_access(
    user_id: str = Query(..., description="User ID"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db)
):
    """List access rules for user"""
    try:
        with AccessControlRepository(db) as repo:
            return repo.list_by_user(user_id, skip, limit)
    except Exception as e:
        logger.error(f"Error listing access rules: {e}")
        raise HTTPException(status_code=500, detail="Failed to list access rules") from e


@router.get("/access-control/check", response_model=Dict[str, Any])
async def check_access(
    user_id: str = Query(..., description="User ID"),
    resource_type: str = Query(..., description="Resource type"),
    resource_id: str = Query(None, description="Specific resource ID (optional)"),
    db: Session = Depends(get_db)
):
    """Check if user has access to resource"""
    try:
        with AccessControlRepository(db) as repo:
            access_level = repo.check_access(user_id, resource_type, resource_id)
            return {
                "user_id": user_id,
                "resource_type": resource_type,
                "resource_id": resource_id,
                "has_access": access_level is not None,
                "access_level": access_level.value if access_level else None,
            }
    except Exception as e:
        logger.error(f"Error checking access: {e}")
        raise HTTPException(status_code=500, detail="Failed to check access") from e


@router.put("/access-control/{rule_id}", response_model=AccessControl)
async def update_access_rule(rule_id: str, request: AccessControlCreate, db: Session = Depends(get_db)):
    """Update access control rule"""
    try:
        with AccessControlRepository(db) as repo:
            updated = repo.update(rule_id, request.model_dump(exclude_unset=True))
            if not updated:
                raise HTTPException(status_code=404, detail="Access control rule not found")
            return updated
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating access rule: {e}")
        raise HTTPException(status_code=500, detail="Failed to update access rule") from e


# ============================================================================
# Analytics & Reporting Endpoints
# ============================================================================

@router.get("/analytics/summary", response_model=Dict[str, Any])
async def get_audit_summary(days: int = Query(7, ge=1, le=365), db: Session = Depends(get_db)):
    """Get audit event summary for period"""
    try:
        summary = AuditAnalyticsService.calculate_event_summary(db, days)
        return summary
    except Exception as e:
        logger.error(f"Error calculating audit summary: {e}")
        raise HTTPException(status_code=500, detail="Failed to calculate audit summary") from e


@router.get("/analytics/risks", response_model=List[Dict[str, Any]])
async def identify_risks(db: Session = Depends(get_db)):
    """Identify risk areas with suspicious activity"""
    try:
        risks = AuditAnalyticsService.identify_risk_areas(db)
        return risks
    except Exception as e:
        logger.error(f"Error identifying risks: {e}")
        raise HTTPException(status_code=500, detail="Failed to identify risks") from e


@router.get("/health", response_model=Dict[str, Any])
async def compliance_health(db: Session = Depends(get_db)):
    """Health check for compliance module"""
    try:
        audit_summary = AuditAnalyticsService.calculate_event_summary(db, days=1)
        return {
            "status": "healthy",
            "module": "compliance",
            "timestamp": datetime.utcnow().isoformat(),
            "recent_events": audit_summary["total_events"],
            "features": [
                "audit_logging",
                "compliance_reporting",
                "data_retention",
                "access_control",
                "analytics",
            ]
        }
    except Exception as e:
        logger.error(f"Error in compliance health check: {e}")
        raise HTTPException(status_code=500, detail="Compliance module unhealthy") from e
