"""
Audit & Compliance Service - Business logic for audit trails and compliance

Provides repositories for audit/compliance management and analytics service
for generating compliance reports and audit statistics.
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from statistics import mean

from sqlalchemy import Session, desc, and_, or_, func, ColumnElement
from sqlalchemy.exc import IntegrityError

from models.audit_models import (
    AuditLogORM, ComplianceLogORM, DataRetentionPolicyORM, AccessControlORM,
    AuditEventCreate, AuditEvent, ComplianceEventCreate, ComplianceEvent,
    DataRetentionPolicyCreate, DataRetentionPolicy, AccessControlCreate, AccessControl,
    AuditEventType, ComplianceType, DataClassification, AccessLevel,
    ComplianceStatus as ComplianceStatusEnum
)

logger = logging.getLogger(__name__)


# ============================================================================
# Repositories
# ============================================================================

class AuditLogRepository:
    """Repository for audit log operations"""

    def __init__(self, session: Session):
        self.session = session

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.session.close()

    def create(self, audit_event: AuditEventCreate) -> AuditEvent:
        """Record an audit event"""
        try:
            orm = AuditLogORM(
                event_type=audit_event.event_type.value,
                user_id=audit_event.user_id,
                resource_type=audit_event.resource_type,
                resource_id=audit_event.resource_id,
                action=audit_event.action,
                status=audit_event.status,
                details=audit_event.details,
                source_ip=audit_event.source_ip,
                user_agent=audit_event.user_agent,
                metadata=audit_event.metadata,
            )
            self.session.add(orm)
            self.session.commit()
            logger.info(f"Audit event recorded: {audit_event.event_type} for {audit_event.resource_type}:{audit_event.resource_id}")
            return orm.to_pydantic()
        except IntegrityError as e:
            self.session.rollback()
            logger.error(f"Integrity error recording audit event: {e}")
            raise

    def read(self, audit_id: str) -> Optional[AuditEvent]:
        """Retrieve audit event by ID"""
        orm = self.session.query(AuditLogORM).filter(
            and_(AuditLogORM.id == audit_id, AuditLogORM.enabled == 1)
        ).first()
        return orm.to_pydantic() if orm else None

    def list_by_resource(self, resource_type: str, resource_id: str, skip: int = 0, limit: int = 50) -> List[AuditEvent]:
        """List audit events for a resource"""
        limit = min(limit, 500)  # Cap at 500
        orms = self.session.query(AuditLogORM).filter(
            and_(
                AuditLogORM.resource_type == resource_type,
                AuditLogORM.resource_id == resource_id,
                AuditLogORM.enabled == 1
            )
        ).order_by(desc(AuditLogORM.created_at)).offset(skip).limit(limit).all()
        return [orm.to_pydantic() for orm in orms]

    def list_by_user(self, user_id: str, skip: int = 0, limit: int = 50) -> List[AuditEvent]:
        """List audit events by user"""
        limit = min(limit, 500)
        orms = self.session.query(AuditLogORM).filter(
            and_(AuditLogORM.user_id == user_id, AuditLogORM.enabled == 1)
        ).order_by(desc(AuditLogORM.created_at)).offset(skip).limit(limit).all()
        return [orm.to_pydantic() for orm in orms]

    def list_by_event_type(self, event_type: AuditEventType, skip: int = 0, limit: int = 50) -> List[AuditEvent]:
        """List audit events by type"""
        limit = min(limit, 500)
        orms = self.session.query(AuditLogORM).filter(
            and_(AuditLogORM.event_type == event_type.value, AuditLogORM.enabled == 1)
        ).order_by(desc(AuditLogORM.created_at)).offset(skip).limit(limit).all()
        return [orm.to_pydantic() for orm in orms]

    def list_by_date_range(self, start_date: datetime, end_date: datetime, skip: int = 0, limit: int = 50) -> List[AuditEvent]:
        """List audit events within date range"""
        limit = min(limit, 500)
        orms = self.session.query(AuditLogORM).filter(
            and_(
                AuditLogORM.created_at >= start_date,
                AuditLogORM.created_at <= end_date,
                AuditLogORM.enabled == 1
            )
        ).order_by(desc(AuditLogORM.created_at)).offset(skip).limit(limit).all()
        return [orm.to_pydantic() for orm in orms]

    def count_by_type(self, event_type: AuditEventType) -> int:
        """Count audit events by type"""
        return self.session.query(func.count(AuditLogORM.id)).filter(
            and_(AuditLogORM.event_type == event_type.value, AuditLogORM.enabled == 1)
        ).scalar() or 0

    def count_by_status(self, status: str) -> int:
        """Count audit events by status"""
        return self.session.query(func.count(AuditLogORM.id)).filter(
            and_(AuditLogORM.status == status, AuditLogORM.enabled == 1)
        ).scalar() or 0


class ComplianceRepository:
    """Repository for compliance event logging"""

    def __init__(self, session: Session):
        self.session = session

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.session.close()

    def create(self, compliance_event: ComplianceEventCreate) -> ComplianceEvent:
        """Record a compliance event"""
        try:
            orm = ComplianceLogORM(
                compliance_type=compliance_event.compliance_type.value,
                event_id=compliance_event.event_id,
                status=compliance_event.status.value,
                description=compliance_event.description,
                requirement=compliance_event.requirement,
                severity=compliance_event.severity,
                metadata=compliance_event.metadata,
            )
            self.session.add(orm)
            self.session.commit()
            logger.info(f"Compliance event recorded: {compliance_event.compliance_type} - {compliance_event.status}")
            return orm.to_pydantic()
        except IntegrityError as e:
            self.session.rollback()
            logger.error(f"Integrity error recording compliance event: {e}")
            raise

    def read(self, compliance_id: str) -> Optional[ComplianceEvent]:
        """Retrieve compliance event by ID"""
        orm = self.session.query(ComplianceLogORM).filter(
            ComplianceLogORM.id == compliance_id
        ).first()
        return orm.to_pydantic() if orm else None

    def list_by_type(self, compliance_type: ComplianceType, skip: int = 0, limit: int = 50) -> List[ComplianceEvent]:
        """List compliance events by type"""
        limit = min(limit, 500)
        orms = self.session.query(ComplianceLogORM).filter(
            ComplianceLogORM.compliance_type == compliance_type.value
        ).order_by(desc(ComplianceLogORM.created_at)).offset(skip).limit(limit).all()
        return [orm.to_pydantic() for orm in orms]

    def count_by_status(self, status: str) -> int:
        """Count compliance events by status"""
        return self.session.query(func.count(ComplianceLogORM.id)).filter(
            ComplianceLogORM.status == status
        ).scalar() or 0


class DataRetentionRepository:
    """Repository for data retention policy management"""

    def __init__(self, session: Session):
        self.session = session

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.session.close()

    def create(self, policy: DataRetentionPolicyCreate) -> DataRetentionPolicy:
        """Create data retention policy"""
        try:
            orm = DataRetentionPolicyORM(
                data_type=policy.data_type,
                retention_days=policy.retention_days,
                classification=policy.classification.value,
                auto_delete=int(policy.auto_delete),
                reason=policy.reason,
                approved_by=policy.approved_by,
            )
            self.session.add(orm)
            self.session.commit()
            logger.info(f"Retention policy created: {policy.data_type} - {policy.retention_days} days")
            return orm.to_pydantic()
        except IntegrityError as e:
            self.session.rollback()
            logger.error(f"Retention policy already exists: {policy.data_type}")
            raise

    def read(self, policy_id: str) -> Optional[DataRetentionPolicy]:
        """Retrieve retention policy by ID"""
        orm = self.session.query(DataRetentionPolicyORM).filter(
            and_(DataRetentionPolicyORM.id == policy_id, DataRetentionPolicyORM.enabled == 1)
        ).first()
        return orm.to_pydantic() if orm else None

    def read_by_type(self, data_type: str) -> Optional[DataRetentionPolicy]:
        """Retrieve retention policy by data type"""
        orm = self.session.query(DataRetentionPolicyORM).filter(
            and_(DataRetentionPolicyORM.data_type == data_type, DataRetentionPolicyORM.enabled == 1)
        ).first()
        return orm.to_pydantic() if orm else None

    def list_enabled(self, skip: int = 0, limit: int = 50) -> List[DataRetentionPolicy]:
        """List enabled retention policies"""
        limit = min(limit, 500)
        orms = self.session.query(DataRetentionPolicyORM).filter(
            DataRetentionPolicyORM.enabled == 1
        ).offset(skip).limit(limit).all()
        return [orm.to_pydantic() for orm in orms]

    def update(self, policy_id: str, updates: Dict[str, Any]) -> Optional[DataRetentionPolicy]:
        """Update retention policy"""
        orm = self.session.query(DataRetentionPolicyORM).filter(
            DataRetentionPolicyORM.id == policy_id
        ).first()
        if not orm:
            return None
        
        for key, value in updates.items():
            if key == 'classification' and isinstance(value, DataClassification):
                setattr(orm, key, value.value)
            elif key in ('auto_delete',):
                setattr(orm, key, int(value))
            else:
                setattr(orm, key, value)
        
        self.session.commit()
        logger.info(f"Retention policy updated: {policy_id}")
        return orm.to_pydantic()


class AccessControlRepository:
    """Repository for access control management"""

    def __init__(self, session: Session):
        self.session = session

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.session.close()

    def create(self, access_rule: AccessControlCreate) -> AccessControl:
        """Create access control rule"""
        try:
            orm = AccessControlORM(
                user_id=access_rule.user_id,
                resource_type=access_rule.resource_type,
                resource_id=access_rule.resource_id,
                access_level=access_rule.access_level.value,
                reason=access_rule.reason,
                granted_by="system",  # Would be actual user in production
                expires_at=access_rule.expires_at,
                metadata=access_rule.metadata,
            )
            self.session.add(orm)
            self.session.commit()
            logger.info(f"Access rule created: {access_rule.user_id} -> {access_rule.resource_type}")
            return orm.to_pydantic()
        except IntegrityError as e:
            self.session.rollback()
            logger.error(f"Error creating access rule: {e}")
            raise

    def read(self, rule_id: str) -> Optional[AccessControl]:
        """Retrieve access control rule"""
        orm = self.session.query(AccessControlORM).filter(
            and_(AccessControlORM.id == rule_id, AccessControlORM.enabled == 1)
        ).first()
        return orm.to_pydantic() if orm else None

    def list_by_user(self, user_id: str, skip: int = 0, limit: int = 50) -> List[AccessControl]:
        """List access rules for user"""
        limit = min(limit, 500)
        orms = self.session.query(AccessControlORM).filter(
            and_(AccessControlORM.user_id == user_id, AccessControlORM.enabled == 1)
        ).order_by(desc(AccessControlORM.created_at)).offset(skip).limit(limit).all()
        return [orm.to_pydantic() for orm in orms]

    def check_access(self, user_id: str, resource_type: str, resource_id: Optional[str] = None) -> Optional[AccessLevel]:
        """Check if user has access to resource"""
        query = self.session.query(AccessControlORM).filter(
            and_(
                AccessControlORM.user_id == user_id,
                AccessControlORM.resource_type == resource_type,
                AccessControlORM.enabled == 1,
                or_(AccessControlORM.expires_at.is_(None), AccessControlORM.expires_at > datetime.utcnow())
            )
        )
        
        if resource_id:
            query = query.filter(or_(AccessControlORM.resource_id.is_(None), AccessControlORM.resource_id == resource_id))
        
        orm = query.first()
        return AccessLevel(orm.access_level) if orm else None

    def update(self, rule_id: str, updates: Dict[str, Any]) -> Optional[AccessControl]:
        """Update access control rule"""
        orm = self.session.query(AccessControlORM).filter(
            AccessControlORM.id == rule_id
        ).first()
        if not orm:
            return None
        
        for key, value in updates.items():
            if key == 'access_level' and isinstance(value, AccessLevel):
                setattr(orm, key, value.value)
            else:
                setattr(orm, key, value)
        
        self.session.commit()
        logger.info(f"Access rule updated: {rule_id}")
        return orm.to_pydantic()


# ============================================================================
# Analytics Service
# ============================================================================

class AuditAnalyticsService:
    """Service for audit analytics and compliance reporting"""

    @staticmethod
    def calculate_event_summary(session: Session, days: int = 7) -> Dict[str, Any]:
        """Calculate summary of audit events for period"""
        start_date = datetime.utcnow() - timedelta(days=days)
        
        total_events = session.query(func.count(AuditLogORM.id)).filter(
            and_(AuditLogORM.created_at >= start_date, AuditLogORM.enabled == 1)
        ).scalar() or 0
        
        success_count = session.query(func.count(AuditLogORM.id)).filter(
            and_(
                AuditLogORM.created_at >= start_date,
                AuditLogORM.status == "success",
                AuditLogORM.enabled == 1
            )
        ).scalar() or 0
        
        failure_count = total_events - success_count
        success_rate = (success_count / total_events * 100) if total_events > 0 else 100.0
        
        event_types = session.query(
            AuditLogORM.event_type,
            func.count(AuditLogORM.id)
        ).filter(
            and_(AuditLogORM.created_at >= start_date, AuditLogORM.enabled == 1)
        ).group_by(AuditLogORM.event_type).all()
        
        return {
            "period_days": days,
            "total_events": total_events,
            "success_count": success_count,
            "failure_count": failure_count,
            "success_rate": round(success_rate, 2),
            "events_by_type": {event_type: count for event_type, count in event_types},
        }

    @staticmethod
    def calculate_compliance_status(session: Session, compliance_type: ComplianceType) -> Dict[str, Any]:
        """Calculate compliance status"""
        total_checks = session.query(func.count(ComplianceLogORM.id)).filter(
            ComplianceLogORM.compliance_type == compliance_type.value
        ).scalar() or 0
        
        compliant_count = session.query(func.count(ComplianceLogORM.id)).filter(
            and_(
                ComplianceLogORM.compliance_type == compliance_type.value,
                ComplianceLogORM.status == ComplianceStatusEnum.COMPLIANT.value
            )
        ).scalar() or 0
        
        non_compliant_count = session.query(func.count(ComplianceLogORM.id)).filter(
            and_(
                ComplianceLogORM.compliance_type == compliance_type.value,
                ComplianceLogORM.status == ComplianceStatusEnum.NON_COMPLIANT.value
            )
        ).scalar() or 0
        
        warnings_count = session.query(func.count(ComplianceLogORM.id)).filter(
            and_(
                ComplianceLogORM.compliance_type == compliance_type.value,
                ComplianceLogORM.status == ComplianceStatusEnum.WARNING.value
            )
        ).scalar() or 0
        
        overall_status = ComplianceStatusEnum.COMPLIANT if non_compliant_count == 0 else ComplianceStatusEnum.WARNING if warnings_count > 0 else ComplianceStatusEnum.NON_COMPLIANT
        
        return {
            "compliance_type": compliance_type.value,
            "overall_status": overall_status.value,
            "total_checks": total_checks,
            "passed_checks": compliant_count,
            "failed_checks": non_compliant_count,
            "warnings": warnings_count,
            "compliance_rate": round((compliant_count / total_checks * 100) if total_checks > 0 else 100, 2),
        }

    @staticmethod
    def identify_risk_areas(session: Session) -> List[Dict[str, Any]]:
        """Identify areas with high error rates or suspicious activity"""
        risks = []
        
        # Find resources with high failure rates
        failing_resources = session.query(
            AuditLogORM.resource_type,
            AuditLogORM.resource_id,
            func.count(AuditLogORM.id).label('total'),
            func.sum((AuditLogORM.status == "failure").cast(__import__('sqlalchemy').Integer)).label('failures')
        ).filter(AuditLogORM.enabled == 1).group_by(
            AuditLogORM.resource_type,
            AuditLogORM.resource_id
        ).having(
            func.sum((AuditLogORM.status == "failure").cast(__import__('sqlalchemy').Integer)) > 5
        ).all()
        
        for resource_type, resource_id, total, failures in failing_resources:
            failure_rate = (failures / total * 100) if total > 0 else 0
            if failure_rate > 20:
                risks.append({
                    "type": "high_failure_rate",
                    "resource_type": resource_type,
                    "resource_id": resource_id,
                    "failure_rate": round(failure_rate, 2),
                    "failure_count": failures,
                })
        
        return risks
