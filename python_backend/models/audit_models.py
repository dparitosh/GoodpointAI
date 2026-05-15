"""
Audit & Compliance Models - Data structures for system audit trails and compliance

Tracks all system changes, compliance events, data retention policies,
and access control for regulatory adherence and security auditing.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from enum import Enum

from sqlalchemy import Column, String, Integer, DateTime, Boolean, JSON, Index, func, Text
from sqlalchemy.orm import mapped_column
from pydantic import BaseModel, Field

from core.database import Base


# ============================================================================
# Enumerations
# ============================================================================

class AuditEventType(str, Enum):
    """Types of audit events"""
    CREATE = "create"  # Resource created
    READ = "read"  # Resource read/accessed
    UPDATE = "update"  # Resource modified
    DELETE = "delete"  # Resource deleted (soft or hard)
    LOGIN = "login"  # User login
    LOGOUT = "logout"  # User logout
    EXPORT = "export"  # Data exported
    IMPORT = "import"  # Data imported
    SEARCH = "search"  # Search performed
    FILTER = "filter"  # Filter applied
    QUERY = "query"  # Query executed
    CONFIGURATION = "configuration"  # System config changed
    AUTHENTICATION = "authentication"  # Auth attempt
    AUTHORIZATION = "authorization"  # Permission check
    ERROR = "error"  # System error occurred


class ComplianceType(str, Enum):
    """Types of compliance requirements"""
    GDPR = "gdpr"  # GDPR (EU data protection)
    CCPA = "ccpa"  # CCPA (California privacy)
    HIPAA = "hipaa"  # HIPAA (Healthcare)
    SOC2 = "soc2"  # SOC 2 (Service organization controls)
    PCI_DSS = "pci_dss"  # PCI DSS (Payment card)
    ISO_27001 = "iso_27001"  # ISO 27001 (Information security)
    INTERNAL = "internal"  # Internal policy


class DataClassification(str, Enum):
    """Data sensitivity classifications"""
    PUBLIC = "public"  # No restrictions
    INTERNAL = "internal"  # Internal use only
    CONFIDENTIAL = "confidential"  # Restricted access
    RESTRICTED = "restricted"  # Highly sensitive
    PERSONAL = "personal"  # Personal/PII data
    FINANCIAL = "financial"  # Financial data
    HEALTH = "health"  # Health/HIPAA data


class AccessLevel(str, Enum):
    """Access control levels"""
    NONE = "none"  # No access
    VIEW = "view"  # Read-only
    EDIT = "edit"  # Read and write
    DELETE = "delete"  # Read, write, delete
    ADMIN = "admin"  # Full access


class ComplianceStatus(str, Enum):
    """Compliance check status"""
    COMPLIANT = "compliant"  # Meets requirements
    WARNING = "warning"  # Potential issue
    NON_COMPLIANT = "non_compliant"  # Violates requirements
    UNKNOWN = "unknown"  # Unable to determine


# ============================================================================
# Pydantic Models (Request/Response)
# ============================================================================

class AuditEventCreate(BaseModel):
    """Request model for logging audit event"""
    event_type: AuditEventType = Field(..., description="Type of event")
    user_id: Optional[str] = Field(default=None, description="User ID (if applicable)")
    resource_type: str = Field(..., description="Type of resource (rule, query, etc)")
    resource_id: str = Field(..., description="ID of resource affected")
    action: str = Field(..., description="Action performed")
    status: str = Field(default="success", description="Event status (success/failure)")
    details: Optional[Dict[str, Any]] = Field(default=None, description="Event details")
    source_ip: Optional[str] = Field(default=None, description="Client IP address")
    user_agent: Optional[str] = Field(default=None, description="User agent string")
    extra_metadata: Optional[Dict[str, Any]] = Field(default=None, description="Additional metadata")


class AuditEvent(AuditEventCreate):
    """Response model for audit event"""
    id: str
    created_at: datetime
    enabled: bool


class ComplianceEventCreate(BaseModel):
    """Request model for logging compliance event"""
    compliance_type: ComplianceType = Field(..., description="Compliance framework")
    event_id: str = Field(..., description="Associated audit event ID")
    status: ComplianceStatus = Field(..., description="Compliance status")
    description: str = Field(..., description="Compliance check description")
    requirement: Optional[str] = Field(default=None, description="Compliance requirement")
    severity: str = Field(default="info", description="Severity: info/warning/critical")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Additional data")


class ComplianceEvent(ComplianceEventCreate):
    """Response model for compliance event"""
    id: str
    created_at: datetime


class DataRetentionPolicyCreate(BaseModel):
    """Request model for data retention policy"""
    data_type: str = Field(..., description="Type of data (conversations, logs, etc)")
    retention_days: int = Field(..., ge=1, le=3650, description="Days to retain (1-10 years)")
    classification: DataClassification = Field(..., description="Data sensitivity")
    auto_delete: bool = Field(default=True, description="Auto-delete after retention")
    reason: Optional[str] = Field(default=None, description="Policy rationale")
    approved_by: Optional[str] = Field(default=None, description="Policy approver")


class DataRetentionPolicy(DataRetentionPolicyCreate):
    """Response model for retention policy"""
    id: str
    created_at: datetime
    updated_at: datetime
    enabled: bool


class AccessControlCreate(BaseModel):
    """Request model for access control rule"""
    user_id: str = Field(..., description="User ID")
    resource_type: str = Field(..., description="Resource type")
    resource_id: Optional[str] = Field(default=None, description="Specific resource (optional)")
    access_level: AccessLevel = Field(..., description="Access permission level")
    reason: Optional[str] = Field(default=None, description="Reason for access")
    expires_at: Optional[datetime] = Field(default=None, description="Access expiration")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Additional data")


class AccessControl(AccessControlCreate):
    """Response model for access control"""
    id: str
    granted_by: str
    created_at: datetime
    updated_at: datetime
    enabled: bool


class AuditReportRequest(BaseModel):
    """Request for audit report generation"""
    start_date: datetime = Field(..., description="Report start date")
    end_date: datetime = Field(..., description="Report end date")
    event_types: Optional[List[AuditEventType]] = Field(default=None, description="Filter by event types")
    resource_types: Optional[List[str]] = Field(default=None, description="Filter by resource types")
    user_ids: Optional[List[str]] = Field(default=None, description="Filter by users")
    include_compliance: bool = Field(default=True, description="Include compliance events")


class ComplianceReportRequest(BaseModel):
    """Request for compliance report"""
    compliance_types: List[ComplianceType] = Field(..., description="Compliance frameworks to check")
    start_date: Optional[datetime] = Field(default=None, description="Report start date")
    end_date: Optional[datetime] = Field(default=None, description="Report end date")


class ComplianceStatus(BaseModel):
    """Compliance status summary"""
    compliance_type: ComplianceType
    overall_status: str  # compliant/warning/non_compliant
    total_checks: int
    passed_checks: int
    failed_checks: int
    warnings: int
    last_checked: datetime


# ============================================================================
# SQLAlchemy ORM Models
# ============================================================================

class AuditLogORM(Base):
    """Comprehensive audit trail for all system events"""
    __tablename__ = "audit_logs"

    id = mapped_column(String(50), primary_key=True, default=lambda: __import__('uuid').uuid4().hex)
    event_type = mapped_column(String(50), nullable=False, index=True)
    user_id = mapped_column(String(50), nullable=True, index=True)
    resource_type = mapped_column(String(100), nullable=False, index=True)
    resource_id = mapped_column(String(255), nullable=False, index=True)
    action = mapped_column(String(255), nullable=False)
    status = mapped_column(String(50), default="success", index=True)
    details = mapped_column(JSON, nullable=True)
    source_ip = mapped_column(String(50), nullable=True)
    user_agent = mapped_column(String(500), nullable=True)
    extra_metadata = mapped_column(JSON, nullable=True)
    created_at = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    enabled = mapped_column(Integer, default=1, index=True)  # Soft delete

    __table_args__ = (
        Index('ix_audit_logs_resource', 'resource_type', 'resource_id'),
        Index('ix_audit_logs_user_time', 'user_id', 'created_at'),
        Index('ix_audit_logs_event_time', 'event_type', 'created_at'),
        Index('ix_audit_logs_action', 'action', 'created_at'),
    )

    def to_pydantic(self) -> AuditEvent:
        """Convert ORM to Pydantic model"""
        return AuditEvent(
            id=self.id,
            event_type=AuditEventType(self.event_type),
            user_id=self.user_id,
            resource_type=self.resource_type,
            resource_id=self.resource_id,
            action=self.action,
            status=self.status,
            details=self.details,
            source_ip=self.source_ip,
            user_agent=self.user_agent,
            extra_metadata=self.extra_metadata,
            created_at=self.created_at,
            enabled=bool(self.enabled),
        )


class ComplianceLogORM(Base):
    """Compliance check and event logging"""
    __tablename__ = "compliance_logs"

    id = mapped_column(String(50), primary_key=True, default=lambda: __import__('uuid').uuid4().hex)
    compliance_type = mapped_column(String(50), nullable=False, index=True)
    event_id = mapped_column(String(50), nullable=False, index=True)
    status = mapped_column(String(50), nullable=False, index=True)
    description = mapped_column(String(500), nullable=False)
    requirement = mapped_column(String(255), nullable=True)
    severity = mapped_column(String(50), default="info", index=True)
    extra_metadata = mapped_column(JSON, nullable=True)
    created_at = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

    __table_args__ = (
        Index('ix_compliance_logs_type_time', 'compliance_type', 'created_at'),
        Index('ix_compliance_logs_status', 'status', 'created_at'),
    )

    def to_pydantic(self) -> ComplianceEvent:
        """Convert ORM to Pydantic model"""
        return ComplianceEvent(
            id=self.id,
            compliance_type=ComplianceType(self.compliance_type),
            event_id=self.event_id,
            status=ComplianceStatus(self.status),
            description=self.description,
            requirement=self.requirement,
            severity=self.severity,
            metadata=self.metadata,
            created_at=self.created_at,
        )


class DataRetentionPolicyORM(Base):
    """Data retention policies for compliance"""
    __tablename__ = "data_retention_policies"

    id = mapped_column(String(50), primary_key=True, default=lambda: __import__('uuid').uuid4().hex)
    data_type = mapped_column(String(100), nullable=False, unique=True, index=True)
    retention_days = mapped_column(Integer, nullable=False)
    classification = mapped_column(String(50), nullable=False, index=True)
    auto_delete = mapped_column(Integer, default=1)
    reason = mapped_column(String(500), nullable=True)
    approved_by = mapped_column(String(50), nullable=True)
    created_at = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    enabled = mapped_column(Integer, default=1, index=True)

    def to_pydantic(self) -> DataRetentionPolicy:
        """Convert ORM to Pydantic model"""
        return DataRetentionPolicy(
            id=self.id,
            data_type=self.data_type,
            retention_days=self.retention_days,
            classification=DataClassification(self.classification),
            auto_delete=bool(self.auto_delete),
            reason=self.reason,
            approved_by=self.approved_by,
            created_at=self.created_at,
            updated_at=self.updated_at,
            enabled=bool(self.enabled),
        )


class AccessControlORM(Base):
    """Access control and permission management"""
    __tablename__ = "access_control"

    id = mapped_column(String(50), primary_key=True, default=lambda: __import__('uuid').uuid4().hex)
    user_id = mapped_column(String(50), nullable=False, index=True)
    resource_type = mapped_column(String(100), nullable=False, index=True)
    resource_id = mapped_column(String(255), nullable=True, index=True)
    access_level = mapped_column(String(50), nullable=False, index=True)
    reason = mapped_column(String(500), nullable=True)
    granted_by = mapped_column(String(50), nullable=False)
    expires_at = mapped_column(DateTime(timezone=True), nullable=True)
    extra_metadata = mapped_column(JSON, nullable=True)
    created_at = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    enabled = mapped_column(Integer, default=1, index=True)

    __table_args__ = (
        Index('ix_access_control_user_resource', 'user_id', 'resource_type'),
        Index('ix_access_control_expiry', 'expires_at'),
    )

    def to_pydantic(self) -> AccessControl:
        """Convert ORM to Pydantic model"""
        return AccessControl(
            id=self.id,
            user_id=self.user_id,
            resource_type=self.resource_type,
            resource_id=self.resource_id,
            access_level=AccessLevel(self.access_level),
            reason=self.reason,
            granted_by=self.granted_by,
            expires_at=self.expires_at,
            metadata=self.metadata,
            created_at=self.created_at,
            updated_at=self.updated_at,
            enabled=bool(self.enabled),
        )
