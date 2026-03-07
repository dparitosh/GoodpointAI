"""PLM ETL persistence models.

These tables implement the "happy path" for (B):
- Source payloads staged in Postgres
- Canonical transformed PLM tables (Parts/BOM)
- Runs tracked by run_id so Neo4j lineage + validations can join consistently

No demo/sample data is inserted here.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, Index, Integer, String, Text, UniqueConstraint, text
from sqlalchemy.types import JSON
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from core.database import Base


class PLMIngestionRun(Base):
    __tablename__ = "plm_ingestion_runs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, index=True)
    source_system: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    target_system: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="created", index=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False
    )
    # R-11/DQ-05: use SQLAlchemy-side onupdate so PostgreSQL actually updates this column.
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("CURRENT_TIMESTAMP"),
        onupdate=func.now(),
        nullable=False,
    )


class PLMStagedRecord(Base):
    __tablename__ = "plm_staged_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    object_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)  # part | bom

    # Raw payload (dict/list) stored as JSON when supported.
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    source_object_id: Mapped[str | None] = mapped_column(String(256), nullable=True, index=True)
    # DQ-02: SHA-256 of canonical JSON payload for deduplication.
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False
    )

    __table_args__ = (
        # DQ-01: prevent duplicate records for the same run/content.
        UniqueConstraint("run_id", "content_hash", name="uq_staged_run_content_hash"),
    )


class PLMPart(Base):
    __tablename__ = "plm_parts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    part_number: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    name: Mapped[str | None] = mapped_column(String(512), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    classification: Mapped[str | None] = mapped_column(String(256), nullable=True, index=True)

    raw: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False
    )

    __table_args__ = (
        Index("idx_plm_parts_run_part", "run_id", "part_number", unique=True),
    )


class PLMBOMItem(Base):
    __tablename__ = "plm_bom_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    parent_part_number: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    child_part_number: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    quantity: Mapped[float | None] = mapped_column(Float, nullable=True)

    raw: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False
    )

    __table_args__ = (
        # DQ-04: enforce uniqueness; duplicate BOM edges corrupt quantity roll-ups.
        Index("idx_plm_bom_run_parent_child", "run_id", "parent_part_number", "child_part_number", unique=True),
    )
