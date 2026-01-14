"""
Pipeline Configuration Models for Central Management

Stores workflow pipeline configurations, file patterns, and search settings
in PostgreSQL for UI-driven management.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum

from sqlalchemy import (
    String, Integer, DateTime, JSON, Text, Float, Boolean,
    Index, UniqueConstraint
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import text

from core.database import Base
from pydantic import BaseModel, Field, ConfigDict


# ============================================================
# Enums
# ============================================================

class DataType(str, Enum):
    """Pipeline data type"""
    STRUCTURED = "structured"
    UNSTRUCTURED = "unstructured"


class PipelineType(str, Enum):
    """Pipeline purpose"""
    SEARCH_INDEX = "search_index"
    KNOWLEDGE_GRAPH = "knowledge_graph"
    DATABASE_MIGRATION = "database_migration"
    PLM_GRAPH_SYNC = "plm_graph_sync"


class FileCategory(str, Enum):
    """File pattern categories"""
    DOCUMENT = "document"
    CAD = "cad"
    SIMULATION = "simulation"
    DATA = "data"
    IMAGE = "image"
    VIDEO = "video"
    ARCHIVE = "archive"
    BINARY = "binary"
    OTHER = "other"


class SearchMode(str, Enum):
    """Supported search modes"""
    SEMANTIC = "semantic"
    VECTOR = "vector"
    HYBRID = "hybrid"


# ============================================================
# SQLAlchemy ORM Models
# ============================================================

class FilePatternConfig(Base):
    """
    File pattern configuration for pipeline ingestion.
    Defines which file types each category supports.
    """
    __tablename__ = "file_pattern_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    category: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    pattern: Mapped[str] = mapped_column(String(50), nullable=False)  # e.g., "*.pdf"
    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    mime_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    parser_hint: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # Parser to use
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), onupdate=text("CURRENT_TIMESTAMP"), server_default=text("CURRENT_TIMESTAMP")
    )
    created_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    __table_args__ = (
        UniqueConstraint('category', 'pattern', name='uq_category_pattern'),
        Index('ix_file_pattern_category_enabled', 'category', 'enabled'),
    )


class PipelineTemplate(Base):
    """
    Pipeline template configuration.
    Defines reusable workflow templates for data pipelines.
    """
    __tablename__ = "pipeline_templates"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Pipeline classification
    data_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)  # structured/unstructured
    pipeline_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    
    # Source configuration template
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    source_config_schema: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    
    # Target configuration template
    target_type: Mapped[str] = mapped_column(String(50), nullable=False)
    target_config_schema: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    
    # File patterns for this pipeline (JSON array of pattern IDs or direct patterns)
    file_patterns: Mapped[List[str]] = mapped_column(JSON, nullable=True, default=list)
    
    # Additional metadata
    extra_metadata: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    icon: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # Icon identifier
    color: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # UI color
    
    # Status
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)  # System templates can't be deleted
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), onupdate=text("CURRENT_TIMESTAMP"), server_default=text("CURRENT_TIMESTAMP")
    )
    created_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    __table_args__ = (
        Index('ix_pipeline_data_type', 'data_type', 'enabled'),
    )


class SearchConfiguration(Base):
    """
    Search configuration settings.
    Defines semantic, vector, and hybrid search parameters.
    """
    __tablename__ = "search_configurations"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    
    # Search mode
    search_mode: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    
    # Configuration parameters (flexible JSON)
    config: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    
    # Model settings (for semantic/vector)
    model_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    vector_dimension: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    similarity_threshold: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), onupdate=text("CURRENT_TIMESTAMP"), server_default=text("CURRENT_TIMESTAMP")
    )
    created_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)


class IndexConfiguration(Base):
    """
    OpenSearch/Elasticsearch index configuration.
    Stores index settings and mappings.
    """
    __tablename__ = "index_configurations"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Index settings
    settings: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    mappings: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    
    # KNN/Vector settings
    knn_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    vector_field: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    vector_dimension: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    # Status
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), onupdate=text("CURRENT_TIMESTAMP"), server_default=text("CURRENT_TIMESTAMP")
    )


class Neo4jSchemaConfig(Base):
    """
    Neo4j schema configuration.
    Stores constraints and indexes for graph database.
    """
    __tablename__ = "neo4j_schema_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    schema_type: Mapped[str] = mapped_column(String(20), nullable=False)  # constraint, index
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    cypher_statement: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), onupdate=text("CURRENT_TIMESTAMP"), server_default=text("CURRENT_TIMESTAMP")
    )


# ============================================================
# Pydantic Models for API
# ============================================================

class FilePatternBase(BaseModel):
    """Base model for file pattern"""
    category: str = Field(..., description="Category: document, cad, simulation, data, image, video, archive, binary")
    pattern: str = Field(..., description="File pattern like *.pdf, *.step")
    description: Optional[str] = None
    mime_type: Optional[str] = None
    parser_hint: Optional[str] = None
    enabled: bool = True


class FilePatternCreate(FilePatternBase):
    """Create file pattern request"""


class FilePatternUpdate(BaseModel):
    """Update file pattern request"""
    category: Optional[str] = None
    pattern: Optional[str] = None
    description: Optional[str] = None
    mime_type: Optional[str] = None
    parser_hint: Optional[str] = None
    enabled: Optional[bool] = None


class FilePatternResponse(FilePatternBase):
    """File pattern response"""
    id: int
    created_at: datetime
    updated_at: Optional[datetime]
    created_by: Optional[str]
    
    model_config = ConfigDict(from_attributes=True)


class PipelineTemplateBase(BaseModel):
    """Base model for pipeline template"""
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    data_type: str = Field(..., description="structured or unstructured")
    pipeline_type: str
    source_type: str
    source_config_schema: Dict[str, Any] = Field(default_factory=dict)
    target_type: str
    target_config_schema: Dict[str, Any] = Field(default_factory=dict)
    file_patterns: Optional[List[str]] = None
    extra_metadata: Optional[Dict[str, Any]] = None
    icon: Optional[str] = None
    color: Optional[str] = None
    enabled: bool = True


class PipelineTemplateCreate(PipelineTemplateBase):
    """Create pipeline template request"""
    id: str = Field(..., min_length=1, max_length=100)


class PipelineTemplateUpdate(BaseModel):
    """Update pipeline template request"""
    name: Optional[str] = None
    description: Optional[str] = None
    data_type: Optional[str] = None
    pipeline_type: Optional[str] = None
    source_type: Optional[str] = None
    source_config_schema: Optional[Dict[str, Any]] = None
    target_type: Optional[str] = None
    target_config_schema: Optional[Dict[str, Any]] = None
    file_patterns: Optional[List[str]] = None
    extra_metadata: Optional[Dict[str, Any]] = None
    icon: Optional[str] = None
    color: Optional[str] = None
    enabled: Optional[bool] = None


class PipelineTemplateResponse(PipelineTemplateBase):
    """Pipeline template response"""
    id: str
    is_system: bool
    created_at: datetime
    updated_at: Optional[datetime]
    created_by: Optional[str]
    
    model_config = ConfigDict(from_attributes=True)


class SearchConfigBase(BaseModel):
    """Base model for search configuration"""
    model_config = ConfigDict(protected_namespaces=())
    name: str
    description: Optional[str] = None
    search_mode: str
    enabled: bool = True
    is_default: bool = False
    config: Dict[str, Any] = Field(default_factory=dict)
    model_name: Optional[str] = None
    vector_dimension: Optional[int] = None
    similarity_threshold: Optional[float] = None


class SearchConfigCreate(SearchConfigBase):
    """Create search configuration request"""
    id: str


class SearchConfigUpdate(BaseModel):
    """Update search configuration request"""
    model_config = ConfigDict(protected_namespaces=())
    name: Optional[str] = None
    description: Optional[str] = None
    search_mode: Optional[str] = None
    enabled: Optional[bool] = None
    is_default: Optional[bool] = None
    config: Optional[Dict[str, Any]] = None
    model_name: Optional[str] = None
    vector_dimension: Optional[int] = None
    similarity_threshold: Optional[float] = None


class SearchConfigResponse(SearchConfigBase):
    """Search configuration response"""
    id: str
    created_at: datetime
    updated_at: Optional[datetime]
    created_by: Optional[str]
    
    model_config = ConfigDict(from_attributes=True)


class IndexConfigBase(BaseModel):
    """Base model for index configuration"""
    name: str
    description: Optional[str] = None
    settings: Dict[str, Any] = Field(default_factory=dict)
    mappings: Dict[str, Any] = Field(default_factory=dict)
    knn_enabled: bool = False
    vector_field: Optional[str] = None
    vector_dimension: Optional[int] = None
    enabled: bool = True


class IndexConfigCreate(IndexConfigBase):
    """Create index configuration request"""
    id: str


class IndexConfigUpdate(BaseModel):
    """Update index configuration request"""
    name: Optional[str] = None
    description: Optional[str] = None
    settings: Optional[Dict[str, Any]] = None
    mappings: Optional[Dict[str, Any]] = None
    knn_enabled: Optional[bool] = None
    vector_field: Optional[str] = None
    vector_dimension: Optional[int] = None
    enabled: Optional[bool] = None


class IndexConfigResponse(IndexConfigBase):
    """Index configuration response"""
    id: str
    is_system: bool
    created_at: datetime
    updated_at: Optional[datetime]
    
    model_config = ConfigDict(from_attributes=True)


# ============================================================
# Aggregated Response Models
# ============================================================

class AllConfigurationsResponse(BaseModel):
    """Response containing all configurations"""
    file_patterns: List[FilePatternResponse]
    pipeline_templates: List[PipelineTemplateResponse]
    search_configs: List[SearchConfigResponse]
    index_configs: List[IndexConfigResponse]


class FilePatternsByCategory(BaseModel):
    """File patterns grouped by category"""
    category: str
    patterns: List[FilePatternResponse]
    count: int
