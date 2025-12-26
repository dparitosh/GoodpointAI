"""
SQLAlchemy models for GraphQL toolkit persistence.
Supports persisted queries and schema cache storage.
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, JSON, Index
from core.database import Base


class PersistedGraphQLQueryModel(Base):
    """
    Stores persisted GraphQL queries for reuse across the platform.
    Used by report_indexing_service and other consumers.
    """
    __tablename__ = "persisted_graphql_queries"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), unique=True, nullable=False, index=True)
    description = Column(Text, nullable=True)
    query = Column(Text, nullable=False)
    variables = Column(JSON, nullable=True, default={})
    format = Column(String(50), nullable=False, default="json")  # 'xml' or 'json'
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    created_by = Column(String(255), nullable=True)
    tags = Column(JSON, nullable=True, default=[])
    
    __table_args__ = (
        Index('idx_query_updated_at', 'updated_at'),
        Index('idx_query_format', 'format'),
    )
    
    def to_dict(self):
        """Convert model to dictionary for API responses."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "query": self.query,
            "variables": self.variables,
            "format": self.format,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "created_by": self.created_by,
            "tags": self.tags or []
        }


class SchemaCacheModel(Base):
    """
    Caches introspected schemas to avoid re-parsing.
    Stores schema structure and metadata.
    """
    __tablename__ = "schema_cache"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), unique=True, nullable=False, index=True)
    format = Column(String(50), nullable=False)  # 'xml' or 'json'
    schema_hash = Column(String(64), nullable=False, index=True)  # SHA-256 of content
    fields = Column(JSON, nullable=False, default={})
    types = Column(JSON, nullable=False, default={})
    schema_metadata = Column(JSON, nullable=True, default={})  # Renamed from metadata to avoid SQLAlchemy conflict
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    access_count = Column(Integer, default=0, nullable=False)
    last_accessed_at = Column(DateTime, nullable=True)
    
    __table_args__ = (
        Index('idx_schema_hash', 'schema_hash'),
        Index('idx_schema_updated_at', 'updated_at'),
    )
    
    def to_dict(self):
        """Convert model to dictionary for API responses."""
        return {
            "id": self.id,
            "name": self.name,
            "format": self.format,
            "schema_hash": self.schema_hash,
            "fields": self.fields,
            "types": self.types,
            "metadata": self.schema_metadata,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "access_count": self.access_count,
            "last_accessed_at": self.last_accessed_at.isoformat() if self.last_accessed_at else None
        }
