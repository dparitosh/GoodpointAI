"""
Comprehensive tests for Audit & Compliance functionality

Tests audit logging, compliance reporting, data retention policies,
access control, and analytics calculations.
"""

import pytest
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from core.database import Base
from models.audit_models import (
    AuditLogORM, ComplianceLogORM, DataRetentionPolicyORM, AccessControlORM,
    AuditEventCreate, ComplianceEventCreate, DataRetentionPolicyCreate, AccessControlCreate,
    AuditEventType, ComplianceType, DataClassification, AccessLevel,
    ComplianceStatus as ComplianceStatusEnum
)
from services.audit_service import (
    AuditLogRepository, ComplianceRepository, DataRetentionRepository,
    AccessControlRepository, AuditAnalyticsService
)


@pytest.fixture
def test_db():
    """Create in-memory SQLite database for testing"""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    yield session
    session.close()


# ============================================================================
# AuditLogRepository Tests
# ============================================================================

class TestAuditLogRepository:
    """Test audit event logging"""

    def test_create_audit_event(self, test_db):
        """Test creating audit event"""
        request = AuditEventCreate(
            event_type=AuditEventType.CREATE,
            user_id="user1",
            resource_type="rule",
            resource_id="rule123",
            action="create_rule",
            status="success",
        )
        
        with AuditLogRepository(test_db) as repo:
            event = repo.create(request)
        
        assert event.id is not None
        assert event.event_type == AuditEventType.CREATE
        assert event.user_id == "user1"
        assert event.resource_id == "rule123"

    def test_read_audit_event(self, test_db):
        """Test retrieving audit event"""
        request = AuditEventCreate(
            event_type=AuditEventType.UPDATE,
            resource_type="query",
            resource_id="query456",
            action="update_query",
        )
        
        with AuditLogRepository(test_db) as repo:
            created = repo.create(request)
            retrieved = repo.read(created.id)
        
        assert retrieved is not None
        assert retrieved.id == created.id
        assert retrieved.resource_type == "query"

    def test_list_by_resource(self, test_db):
        """Test listing events by resource"""
        for i in range(3):
            request = AuditEventCreate(
                event_type=AuditEventType.DELETE if i == 0 else AuditEventType.READ,
                resource_type="conversation",
                resource_id="conv789",
                action=f"action_{i}",
            )
            with AuditLogRepository(test_db) as repo:
                repo.create(request)
        
        with AuditLogRepository(test_db) as repo:
            events = repo.list_by_resource("conversation", "conv789")
        
        assert len(events) == 3

    def test_list_by_user(self, test_db):
        """Test listing events by user"""
        for i in range(2):
            request = AuditEventCreate(
                event_type=AuditEventType.LOGIN,
                user_id="admin_user",
                resource_type="system",
                resource_id="login",
                action="user_login",
            )
            with AuditLogRepository(test_db) as repo:
                repo.create(request)
        
        with AuditLogRepository(test_db) as repo:
            events = repo.list_by_user("admin_user")
        
        assert len(events) == 2

    def test_count_by_type(self, test_db):
        """Test counting events by type"""
        for event_type in [AuditEventType.CREATE, AuditEventType.UPDATE, AuditEventType.CREATE]:
            request = AuditEventCreate(
                event_type=event_type,
                resource_type="test",
                resource_id="test1",
                action="test_action",
            )
            with AuditLogRepository(test_db) as repo:
                repo.create(request)
        
        with AuditLogRepository(test_db) as repo:
            create_count = repo.count_by_type(AuditEventType.CREATE)
            update_count = repo.count_by_type(AuditEventType.UPDATE)
        
        assert create_count == 2
        assert update_count == 1


# ============================================================================
# ComplianceRepository Tests
# ============================================================================

class TestComplianceRepository:
    """Test compliance event logging"""

    def test_create_compliance_event(self, test_db):
        """Test creating compliance event"""
        request = ComplianceEventCreate(
            compliance_type=ComplianceType.GDPR,
            event_id="audit_event_1",
            status=ComplianceStatusEnum.COMPLIANT,
            description="GDPR compliance check passed",
        )
        
        with ComplianceRepository(test_db) as repo:
            event = repo.create(request)
        
        assert event.id is not None
        assert event.compliance_type == ComplianceType.GDPR
        assert event.status == ComplianceStatusEnum.COMPLIANT

    def test_list_by_type(self, test_db):
        """Test listing compliance events by type"""
        for _ in range(2):
            request = ComplianceEventCreate(
                compliance_type=ComplianceType.SOC2,
                event_id="audit_1",
                status=ComplianceStatusEnum.WARNING,
                description="SOC2 check",
            )
            with ComplianceRepository(test_db) as repo:
                repo.create(request)
        
        with ComplianceRepository(test_db) as repo:
            events = repo.list_by_type(ComplianceType.SOC2)
        
        assert len(events) == 2

    def test_count_by_status(self, test_db):
        """Test counting by compliance status"""
        statuses = [ComplianceStatusEnum.COMPLIANT, ComplianceStatusEnum.COMPLIANT, ComplianceStatusEnum.WARNING]
        
        for status in statuses:
            request = ComplianceEventCreate(
                compliance_type=ComplianceType.HIPAA,
                event_id=f"audit_{status.value}",
                status=status,
                description="Health check",
            )
            with ComplianceRepository(test_db) as repo:
                repo.create(request)
        
        with ComplianceRepository(test_db) as repo:
            compliant = repo.count_by_status(ComplianceStatusEnum.COMPLIANT.value)
        
        assert compliant == 2


# ============================================================================
# DataRetentionRepository Tests
# ============================================================================

class TestDataRetentionRepository:
    """Test data retention policy management"""

    def test_create_retention_policy(self, test_db):
        """Test creating retention policy"""
        request = DataRetentionPolicyCreate(
            data_type="conversations",
            retention_days=365,
            classification=DataClassification.INTERNAL,
        )
        
        with DataRetentionRepository(test_db) as repo:
            policy = repo.create(request)
        
        assert policy.id is not None
        assert policy.data_type == "conversations"
        assert policy.retention_days == 365

    def test_read_by_type(self, test_db):
        """Test retrieving policy by data type"""
        request = DataRetentionPolicyCreate(
            data_type="logs",
            retention_days=90,
            classification=DataClassification.CONFIDENTIAL,
        )
        
        with DataRetentionRepository(test_db) as repo:
            repo.create(request)
            policy = repo.read_by_type("logs")
        
        assert policy is not None
        assert policy.retention_days == 90

    def test_duplicate_policy_error(self, test_db):
        """Test duplicate policy error"""
        request = DataRetentionPolicyCreate(
            data_type="analytics",
            retention_days=180,
            classification=DataClassification.INTERNAL,
        )
        
        with DataRetentionRepository(test_db) as repo:
            repo.create(request)
        
        with DataRetentionRepository(test_db) as repo:
            with pytest.raises(Exception):  # IntegrityError
                repo.create(request)

    def test_update_policy(self, test_db):
        """Test updating retention policy"""
        request = DataRetentionPolicyCreate(
            data_type="audit_logs",
            retention_days=730,
            classification=DataClassification.RESTRICTED,
        )
        
        with DataRetentionRepository(test_db) as repo:
            created = repo.create(request)
            updated = repo.update(created.id, {"retention_days": 1095})
        
        assert updated is not None
        assert updated.retention_days == 1095


# ============================================================================
# AccessControlRepository Tests
# ============================================================================

class TestAccessControlRepository:
    """Test access control management"""

    def test_create_access_rule(self, test_db):
        """Test creating access rule"""
        request = AccessControlCreate(
            user_id="user123",
            resource_type="conversation",
            resource_id="conv_abc",
            access_level=AccessLevel.EDIT,
        )
        
        with AccessControlRepository(test_db) as repo:
            rule = repo.create(request)
        
        assert rule.id is not None
        assert rule.user_id == "user123"
        assert rule.access_level == AccessLevel.EDIT

    def test_check_access(self, test_db):
        """Test checking user access"""
        request = AccessControlCreate(
            user_id="reviewer",
            resource_type="rule",
            resource_id="rule_xyz",
            access_level=AccessLevel.VIEW,
        )
        
        with AccessControlRepository(test_db) as repo:
            repo.create(request)
            access = repo.check_access("reviewer", "rule", "rule_xyz")
        
        assert access is not None
        assert access == AccessLevel.VIEW

    def test_no_access(self, test_db):
        """Test when user has no access"""
        with AccessControlRepository(test_db) as repo:
            access = repo.check_access("unknown_user", "query", "query_123")
        
        assert access is None

    def test_expired_access(self, test_db):
        """Test that expired access is not granted"""
        past_date = datetime.utcnow() - timedelta(days=1)
        
        request = AccessControlCreate(
            user_id="expired_user",
            resource_type="database",
            resource_id="db_prod",
            access_level=AccessLevel.ADMIN,
            expires_at=past_date,
        )
        
        with AccessControlRepository(test_db) as repo:
            repo.create(request)
            access = repo.check_access("expired_user", "database", "db_prod")
        
        assert access is None  # Expired, so no access

    def test_list_by_user(self, test_db):
        """Test listing access rules for user"""
        for i in range(3):
            request = AccessControlCreate(
                user_id="power_user",
                resource_type=f"resource_{i}",
                resource_id=f"res_{i}",
                access_level=AccessLevel.EDIT,
            )
            with AccessControlRepository(test_db) as repo:
                repo.create(request)
        
        with AccessControlRepository(test_db) as repo:
            rules = repo.list_by_user("power_user")
        
        assert len(rules) == 3


# ============================================================================
# AuditAnalyticsService Tests
# ============================================================================

class TestAuditAnalyticsService:
    """Test audit analytics and reporting"""

    def test_calculate_event_summary(self, test_db):
        """Test calculating audit event summary"""
        # Create mix of success and failure events
        for i in range(7):
            status = "success" if i < 5 else "failure"
            request = AuditEventCreate(
                event_type=AuditEventType.CREATE,
                resource_type="test",
                resource_id=f"test_{i}",
                action="test_action",
                status=status,
            )
            with AuditLogRepository(test_db) as repo:
                repo.create(request)
        
        summary = AuditAnalyticsService.calculate_event_summary(test_db, days=7)
        
        assert summary["total_events"] == 7
        assert summary["success_count"] == 5
        assert summary["failure_count"] == 2
        assert summary["success_rate"] == pytest.approx(71.43, rel=0.1)

    def test_calculate_compliance_status(self, test_db):
        """Test calculating compliance status"""
        # Create compliance events
        for status in [ComplianceStatusEnum.COMPLIANT, ComplianceStatusEnum.COMPLIANT, ComplianceStatusEnum.WARNING]:
            request = ComplianceEventCreate(
                compliance_type=ComplianceType.GDPR,
                event_id=f"audit_{status.value}",
                status=status,
                description="GDPR check",
            )
            with ComplianceRepository(test_db) as repo:
                repo.create(request)
        
        status_report = AuditAnalyticsService.calculate_compliance_status(test_db, ComplianceType.GDPR)
        
        assert status_report["total_checks"] == 3
        assert status_report["passed_checks"] == 2
        assert status_report["warnings"] == 1
        assert status_report["compliance_rate"] == pytest.approx(66.67, rel=0.1)

    def test_identify_risk_areas(self, test_db):
        """Test identifying risk areas"""
        # Create multiple failure events for same resource
        for _ in range(10):
            request = AuditEventCreate(
                event_type=AuditEventType.DELETE,
                resource_type="critical_resource",
                resource_id="resource_123",
                action="dangerous_operation",
                status="failure",
            )
            with AuditLogRepository(test_db) as repo:
                repo.create(request)
        
        risks = AuditAnalyticsService.identify_risk_areas(test_db)
        
        # Should identify this as high-risk
        assert any(r["type"] == "high_failure_rate" for r in risks)


# ============================================================================
# Integration Tests
# ============================================================================

class TestComplianceIntegration:
    """Integration tests for complete workflows"""

    def test_audit_to_compliance_workflow(self, test_db):
        """Test workflow from audit event to compliance check"""
        # Create audit event
        audit_request = AuditEventCreate(
            event_type=AuditEventType.CREATE,
            user_id="admin",
            resource_type="user_account",
            resource_id="user_new",
            action="create_user",
            status="success",
        )
        
        with AuditLogRepository(test_db) as repo:
            audit_event = repo.create(audit_request)
        
        # Record compliance check for that event
        compliance_request = ComplianceEventCreate(
            compliance_type=ComplianceType.GDPR,
            event_id=audit_event.id,
            status=ComplianceStatusEnum.COMPLIANT,
            description="User creation complies with GDPR",
        )
        
        with ComplianceRepository(test_db) as repo:
            compliance_event = repo.create(compliance_request)
        
        # Verify both were recorded
        with AuditLogRepository(test_db) as repo:
            retrieved_audit = repo.read(audit_event.id)
        
        with ComplianceRepository(test_db) as repo:
            retrieved_compliance = repo.read(compliance_event.id)
        
        assert retrieved_audit is not None
        assert retrieved_compliance is not None
        assert retrieved_compliance.event_id == retrieved_audit.id

    def test_full_compliance_workflow(self, test_db):
        """Test complete compliance workflow with policies and access"""
        # 1. Create retention policy
        policy_request = DataRetentionPolicyCreate(
            data_type="sensitive_data",
            retention_days=365,
            classification=DataClassification.RESTRICTED,
        )
        
        with DataRetentionRepository(test_db) as repo:
            policy = repo.create(policy_request)
        
        # 2. Grant access to user
        access_request = AccessControlCreate(
            user_id="compliance_officer",
            resource_type="sensitive_data",
            access_level=AccessLevel.VIEW,
        )
        
        with AccessControlRepository(test_db) as repo:
            access = repo.create(access_request)
            
            # 3. Verify access was granted
            check = repo.check_access("compliance_officer", "sensitive_data")
        
        # 4. Log the access grant as audit event
        audit_request = AuditEventCreate(
            event_type=AuditEventType.CONFIGURATION,
            user_id="admin",
            resource_type="access_control",
            resource_id=access.id,
            action="grant_access",
            status="success",
        )
        
        with AuditLogRepository(test_db) as repo:
            audit_event = repo.create(audit_request)
        
        assert check == AccessLevel.VIEW
        assert audit_event.action == "grant_access"
