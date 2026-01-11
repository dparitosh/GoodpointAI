"""Configuration models persisted in the app DB.

These tables hold encrypted configuration payloads (secrets encrypted at rest)
for integrations and migration data sources.

Note: The backend still needs a bootstrap DATABASE_URL to start and access this
DB; once running, the UI can manage integration configs stored here.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String, Text, Index, text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class EncryptedConfig(Base):
    """Generic encrypted config blob stored by key."""

    __tablename__ = "app_encrypted_configs"

    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    ciphertext: Mapped[str] = mapped_column(Text, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        server_default=text("CURRENT_TIMESTAMP"),
        server_onupdate=text("CURRENT_TIMESTAMP"),
        nullable=True,
    )


class DataSourceConfigRecord(Base):
    """Migration data source configuration.

    Connection details (including credentials) are stored in `connection_ciphertext`.
    """

    __tablename__ = "data_source_configs"

    id: Mapped[str] = mapped_column(String(96), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)

    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="inactive", index=True)

    # Encrypted JSON payload of connection fields.
    connection_ciphertext: Mapped[str] = mapped_column(Text, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        server_default=text("CURRENT_TIMESTAMP"),
        server_onupdate=text("CURRENT_TIMESTAMP"),
        nullable=True,
    )

    last_tested: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    test_result: Mapped[str | None] = mapped_column(String(32), nullable=True)

    __table_args__ = (
        Index("idx_data_source_type_status", "type", "status"),
        UniqueConstraint("name", name="uq_data_source_name"),
    )
