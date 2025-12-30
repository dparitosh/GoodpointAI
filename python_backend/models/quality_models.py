"""Data-quality models persisted in the app DB.

This replaces in-memory quality storage so rules/results survive restarts and can
be joined to ETL runs.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, Index, Float, text
from sqlalchemy.types import JSON
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class DataQualityRule(Base):
    __tablename__ = "dq_rules"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    entity_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)  # part | bom | table
    rule_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)  # completeness|validity|...
    severity: Mapped[str] = mapped_column(String(16), nullable=False, index=True)  # low|medium|high|critical
    enabled: Mapped[int] = mapped_column(Integer, nullable=False, default=1)  # 1/0 for portability

    # Structured condition; interpretation happens in validation service.
    # Example: {"op": "not_null", "field": "part_number"}
    condition: Mapped[dict] = mapped_column(JSON, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        server_default=text("CURRENT_TIMESTAMP"),
        server_onupdate=text("CURRENT_TIMESTAMP"),
        nullable=True,
    )


class DataQualityResult(Base):
    __tablename__ = "dq_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    rule_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    entity_key: Mapped[str | None] = mapped_column(String(256), nullable=True, index=True)

    status: Mapped[str] = mapped_column(String(16), nullable=False, index=True)  # pass|fail|error
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    details: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False
    )

    __table_args__ = (
        Index("idx_dq_results_run_rule", "run_id", "rule_id"),
    )


class DataQualityScanReport(Base):
    """Persisted analytics-quality scan outputs.

    This replaces the previous in-memory report store. The stored `report` JSON
    matches the UI contract consumed by DataQualityDashboard.
    """

    __tablename__ = "dq_scan_reports"

    scan_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    table_name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    data_source: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # UI contract payload (scores/issues/recommendations/etc.)
    report: Mapped[dict] = mapped_column(JSON, nullable=False)

    overall_score: Mapped[float] = mapped_column(Float, nullable=False, index=True)
    issues_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    scan_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False, index=True
    )
    row_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    column_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    __table_args__ = (
        Index("idx_dq_scan_reports_table_date", "table_name", "scan_date"),
    )


class DataQualityGateResult(Base):
    """Run-scoped quality gate outcomes.

    Purpose:
    - Attach quality decisions to a specific PLM ETL run_id + stage.
    - Support fail-closed gating in the UI without relying on transient scan output.

    This intentionally does NOT change the existing dq_scan_reports schema so existing
    installs don't require in-place ALTER migrations (create_all() adds new tables only).
    """

    __tablename__ = "dq_gate_results"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    run_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    # e.g. staged | transformed | validated | graph_sync
    stage: Mapped[str] = mapped_column(String(32), nullable=False, index=True)

    # e.g. soda | deterministic
    tool: Mapped[str] = mapped_column(String(32), nullable=False, index=True)

    table_name: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    scan_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)

    # pass | fail | error
    status: Mapped[str] = mapped_column(String(16), nullable=False, index=True)

    overall_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    issues_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    details: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False, index=True
    )

    __table_args__ = (
        Index("idx_dq_gate_results_run_stage", "run_id", "stage"),
    )
