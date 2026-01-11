"""Generic report persistence models.

Goal: store all report artifacts in the Postgres app DB so they can be reused
across Reporting, Analytics dashboards, and Spreadsheet exports.

This is intentionally generic (JSON payload) so new report kinds can be added
without schema migrations.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from core.database import Base


class PersistedReport(Base):
    __tablename__ = "reports"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)

    # e.g. plm_etl_run | quality_scan | quality_gate | custom
    report_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    # optional categorization for UI grouping
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # provenance
    source: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    schema_version: Mapped[str | None] = mapped_column(String(32), nullable=True)

    # optional linking fields (for filtering)
    run_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    external_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    table_name: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)

    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    summary: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # soft-delete support
    is_deleted: Mapped[int] = mapped_column(Integer, nullable=False, default=0, index=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False, index=True
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        server_default=text("CURRENT_TIMESTAMP"),
        server_onupdate=text("CURRENT_TIMESTAMP"),
        nullable=True,
    )

    __table_args__ = (
        Index("idx_reports_type_created", "report_type", "created_at"),
        Index("idx_reports_run_type", "run_id", "report_type"),
    )
