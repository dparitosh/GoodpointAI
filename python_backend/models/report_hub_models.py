"""
Unified Reporting Hub — ORM model
===================================
Collects reports/outputs from every page:
  migration | lineage | analytics | dq_scan | discovery | observability | self_healing
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Index, JSON, String
from core.database import Base


class UnifiedReport(Base):
    __tablename__ = "unified_reports"

    report_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    # which page / agent produced this report
    report_type = Column(String, nullable=False, index=True)
    # human-readable title
    title = Column(String, nullable=False)

    # optional linkage
    workflow_id = Column(String, nullable=True, index=True)
    run_id = Column(String, nullable=True)
    source_page = Column(String, nullable=True)   # e.g. 'migration', 'data-discovery'

    # top-level status: pass | fail | warning | info | running
    status = Column(String, nullable=True, default="info")

    # compact KPIs for the hub list view (file count, score, record count …)
    summary = Column(JSON, nullable=True)

    # full agent / page payload
    result = Column(JSON, nullable=True)

    # comma-separated tags for quick filtering
    tags = Column(JSON, nullable=True)        # list[str]

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        Index("idx_unified_reports_type_date", "report_type", "created_at"),
        Index("idx_unified_reports_workflow",  "workflow_id", "created_at"),
    )
