"""
Admin Configuration Models for Central Management

Stores all LLM, embedding, API keys, and system configurations
in PostgreSQL for UI-driven management.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional, Dict, Any, List
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

class ConfigCategory(str, Enum):
    """Configuration categories"""
    LLM = "llm"
    EMBEDDING = "embedding"
    SEARCH = "search"
    DATABASE = "database"
    STORAGE = "storage"
    API_GATEWAY = "api_gateway"
    PLM = "plm"
    MONITORING = "monitoring"
    SECURITY = "security"
    SYSTEM = "system"


class LLMProvider(str, Enum):
    """Supported LLM providers"""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    AZURE_OPENAI = "azure_openai"
    OLLAMA = "ollama"
    GOOGLE = "google"
    HUGGINGFACE = "huggingface"
    COHERE = "cohere"
    CUSTOM = "custom"


class EmbeddingProvider(str, Enum):
    """Supported embedding providers"""
    OPENAI = "openai"
    AZURE_OPENAI = "azure_openai"
    HUGGINGFACE = "huggingface"
    SENTENCE_TRANSFORMERS = "sentence_transformers"
    COHERE = "cohere"
    CUSTOM = "custom"


class ConfigStatus(str, Enum):
    """Configuration status"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    TESTING = "testing"
    DEPRECATED = "deprecated"


# ============================================================
# SQLAlchemy ORM Models
# ============================================================

class SystemConfiguration(Base):
    """
    Central system configuration store.
    Generic key-value configuration with categories.
    NOTE: Using admin_system_settings to avoid conflict with existing system_configurations table
    """
    __tablename__ = "admin_system_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    category: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    key: Mapped[str] = mapped_column(String(100), nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=True)
    value_type: Mapped[str] = mapped_column(String(20), nullable=False, default="string")  # string, number, boolean, json
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_secret: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    default_value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    validation_regex: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), onupdate=text("CURRENT_TIMESTAMP"), server_default=text("CURRENT_TIMESTAMP")
    )
    created_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    updated_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    __table_args__ = (
        UniqueConstraint('category', 'key', name='uq_category_key'),
        Index('ix_system_config_category_enabled', 'category', 'enabled'),
    )


class LLMProviderConfig(Base):
    """
    LLM Provider configuration.
    Stores API keys, endpoints, and model settings.
    """
    __tablename__ = "llm_provider_configs"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    provider: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Connection settings
    api_key: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # Encrypted in production
    api_endpoint: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    api_version: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    
    # Azure OpenAI specific
    azure_deployment: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    azure_resource_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    
    # Default models
    default_chat_model: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    default_completion_model: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    default_embedding_model: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    
    # Model parameters
    default_temperature: Mapped[float] = mapped_column(Float, default=0.7, nullable=False)
    default_max_tokens: Mapped[int] = mapped_column(Integer, default=2048, nullable=False)
    default_top_p: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    
    # Rate limits
    rate_limit_rpm: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # Requests per minute
    rate_limit_tpm: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # Tokens per minute
    
    # Cost tracking
    cost_per_1k_input_tokens: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    cost_per_1k_output_tokens: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    
    # Status
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=0, nullable=False)  # For fallback ordering
    
    # Metadata
    extra_config: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), onupdate=text("CURRENT_TIMESTAMP"), server_default=text("CURRENT_TIMESTAMP")
    )
    created_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    __table_args__ = (
        Index('ix_llm_provider_status', 'provider', 'status'),
    )


class EmbeddingModelConfig(Base):
    """
    Embedding model configuration.
    Stores embedding model settings for vector search.
    """
    __tablename__ = "embedding_model_configs"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    provider: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Model details
    model_name: Mapped[str] = mapped_column(String(200), nullable=False)
    dimension: Mapped[int] = mapped_column(Integer, nullable=False)
    max_input_length: Mapped[int] = mapped_column(Integer, default=512, nullable=False)
    
    # Connection (uses LLM provider config or custom)
    llm_provider_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    custom_endpoint: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    custom_api_key: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Performance settings
    batch_size: Mapped[int] = mapped_column(Integer, default=32, nullable=False)
    normalize: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    
    # Cost
    cost_per_1k_tokens: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    
    # Status
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), onupdate=text("CURRENT_TIMESTAMP"), server_default=text("CURRENT_TIMESTAMP")
    )

    __table_args__ = (
        Index('ix_embedding_provider_status', 'provider', 'status'),
    )


class APIKeyConfig(Base):
    """
    External API key management.
    Stores API keys for various services.
    """
    __tablename__ = "api_key_configs"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    service_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    key_name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # The key itself (encrypted in production)
    api_key: Mapped[str] = mapped_column(Text, nullable=False)
    
    # Optional associated endpoint
    endpoint: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    
    # Expiration tracking
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # Usage tracking
    usage_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_used_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # Status
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), onupdate=text("CURRENT_TIMESTAMP"), server_default=text("CURRENT_TIMESTAMP")
    )
    created_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    __table_args__ = (
        UniqueConstraint('service_name', 'key_name', name='uq_service_key_name'),
    )


class ConnectionConfig(Base):
    """
    External service connection configuration.
    Stores connection settings for databases, APIs, etc.
    """
    __tablename__ = "connection_configs"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    connection_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)  # postgres, neo4j, opensearch, etc.
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Connection string or components
    connection_string: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    host: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    port: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    database: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    username: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    password: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # Encrypted
    
    # SSL/TLS
    use_ssl: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    ssl_cert_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    
    # Pool settings
    pool_size: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    max_overflow: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    pool_timeout: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    
    # Additional options (JSON):
    # - auth_method: "basic" | "bearer" | "oauth"
    # - oauth_client_id: OAuth client ID
    # - oauth_client_secret: OAuth client secret
    # - oauth_token_url: Token endpoint URL
    # - oauth_scope: OAuth scope (optional)
    # - oauth_token_cached: Cached token data (managed by oauth_service)
    extra_options: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    
    # Status
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    
    # Health check
    last_health_check: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    health_status: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), onupdate=text("CURRENT_TIMESTAMP"), server_default=text("CURRENT_TIMESTAMP")
    )

    __table_args__ = (
        Index('ix_connection_type_status', 'connection_type', 'status'),
    )


class FeatureFlag(Base):
    """
    Feature flag configuration for enabling/disabling features.
    """
    __tablename__ = "feature_flags"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    
    # Targeting rules (JSON for complex conditions)
    targeting_rules: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    
    # Rollout percentage (0-100)
    rollout_percentage: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), onupdate=text("CURRENT_TIMESTAMP"), server_default=text("CURRENT_TIMESTAMP")
    )
    created_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)


class AuditLog(Base):
    """
    Audit log for configuration changes.
    """
    __tablename__ = "config_audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False, index=True
    )
    
    config_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    config_id: Mapped[str] = mapped_column(String(100), nullable=False)
    action: Mapped[str] = mapped_column(String(20), nullable=False)  # create, update, delete
    
    # Change details
    old_value: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    new_value: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    changed_fields: Mapped[Optional[List[str]]] = mapped_column(JSON, nullable=True)
    
    # Who made the change
    user_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    user_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    
    # Additional context
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index('ix_audit_config_type_id', 'config_type', 'config_id'),
    )


# ============================================================
# Pydantic Models for API
# ============================================================

class SystemConfigBase(BaseModel):
    """Base model for system configuration"""
    category: str = Field(..., description="Configuration category")
    key: str = Field(..., description="Configuration key")
    value: Optional[str] = Field(None, description="Configuration value")
    value_type: str = Field(default="string", description="Value type: string, number, boolean, json")
    description: Optional[str] = None
    is_secret: bool = False
    is_required: bool = False
    default_value: Optional[str] = None
    validation_regex: Optional[str] = None
    enabled: bool = True


class SystemConfigCreate(SystemConfigBase):
    """Create system configuration"""
    pass


class SystemConfigUpdate(BaseModel):
    """Update system configuration"""
    value: Optional[str] = None
    description: Optional[str] = None
    enabled: Optional[bool] = None
    validation_regex: Optional[str] = None


class SystemConfigResponse(SystemConfigBase):
    """System configuration response"""
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    created_by: Optional[str] = None
    updated_by: Optional[str] = None
    
    model_config = ConfigDict(from_attributes=True)


class LLMProviderBase(BaseModel):
    """Base model for LLM provider"""
    provider: str = Field(..., description="Provider type: openai, anthropic, azure_openai, ollama")
    name: str = Field(..., description="Display name")
    description: Optional[str] = None
    api_key: Optional[str] = None
    api_endpoint: Optional[str] = None
    api_version: Optional[str] = None
    azure_deployment: Optional[str] = None
    azure_resource_name: Optional[str] = None
    default_chat_model: Optional[str] = None
    default_completion_model: Optional[str] = None
    default_embedding_model: Optional[str] = None
    default_temperature: float = 0.7
    default_max_tokens: int = 2048
    default_top_p: float = 1.0
    rate_limit_rpm: Optional[int] = None
    rate_limit_tpm: Optional[int] = None
    cost_per_1k_input_tokens: Optional[float] = None
    cost_per_1k_output_tokens: Optional[float] = None
    status: str = "active"
    is_default: bool = False
    priority: int = 0
    extra_config: Optional[Dict[str, Any]] = None


class LLMProviderCreate(LLMProviderBase):
    """Create LLM provider"""
    id: str = Field(..., description="Unique identifier")


class LLMProviderUpdate(BaseModel):
    """Update LLM provider"""
    name: Optional[str] = None
    description: Optional[str] = None
    api_key: Optional[str] = None
    api_endpoint: Optional[str] = None
    api_version: Optional[str] = None
    azure_deployment: Optional[str] = None
    default_chat_model: Optional[str] = None
    default_temperature: Optional[float] = None
    default_max_tokens: Optional[int] = None
    rate_limit_rpm: Optional[int] = None
    rate_limit_tpm: Optional[int] = None
    status: Optional[str] = None
    is_default: Optional[bool] = None
    priority: Optional[int] = None
    extra_config: Optional[Dict[str, Any]] = None


class LLMProviderResponse(LLMProviderBase):
    """LLM provider response"""
    id: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    created_by: Optional[str] = None
    api_key_masked: Optional[str] = None  # Show masked version
    
    model_config = ConfigDict(from_attributes=True)


class EmbeddingModelBase(BaseModel):
    """Base model for embedding model"""
    provider: str = Field(..., description="Provider: openai, huggingface, sentence_transformers")
    name: str = Field(..., description="Display name")
    description: Optional[str] = None
    model_name: str = Field(..., description="Model identifier")
    dimension: int = Field(..., description="Vector dimension")
    max_input_length: int = 512
    llm_provider_id: Optional[str] = None
    custom_endpoint: Optional[str] = None
    custom_api_key: Optional[str] = None
    batch_size: int = 32
    normalize: bool = True
    cost_per_1k_tokens: Optional[float] = None
    status: str = "active"
    is_default: bool = False


class EmbeddingModelCreate(EmbeddingModelBase):
    """Create embedding model"""
    id: str = Field(..., description="Unique identifier")


class EmbeddingModelUpdate(BaseModel):
    """Update embedding model"""
    name: Optional[str] = None
    description: Optional[str] = None
    max_input_length: Optional[int] = None
    batch_size: Optional[int] = None
    normalize: Optional[bool] = None
    status: Optional[str] = None
    is_default: Optional[bool] = None


class EmbeddingModelResponse(EmbeddingModelBase):
    """Embedding model response"""
    id: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    model_config = ConfigDict(from_attributes=True)


class ConnectionConfigBase(BaseModel):
    """Base model for connection configuration"""
    connection_type: str = Field(..., description="Type: postgres, neo4j, opensearch, redis, etc.")
    name: str = Field(..., description="Display name")
    description: Optional[str] = None
    connection_string: Optional[str] = None
    host: Optional[str] = None
    port: Optional[int] = None
    database: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    use_ssl: bool = False
    ssl_cert_path: Optional[str] = None
    pool_size: int = 5
    max_overflow: int = 10
    pool_timeout: int = 30
    extra_options: Optional[Dict[str, Any]] = None
    status: str = "active"
    is_default: bool = False


class ConnectionConfigCreate(ConnectionConfigBase):
    """Create connection configuration"""
    id: str = Field(..., description="Unique identifier")


class ConnectionConfigUpdate(BaseModel):
    """Update connection configuration"""
    name: Optional[str] = None
    description: Optional[str] = None
    connection_string: Optional[str] = None
    host: Optional[str] = None
    port: Optional[int] = None
    database: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    use_ssl: Optional[bool] = None
    ssl_cert_path: Optional[str] = None
    pool_size: Optional[int] = None
    max_overflow: Optional[int] = None
    pool_timeout: Optional[int] = None
    extra_options: Optional[Dict[str, Any]] = None
    status: Optional[str] = None
    is_default: Optional[bool] = None


class ConnectionConfigResponse(ConnectionConfigBase):
    """Connection configuration response"""
    id: str
    last_health_check: Optional[datetime] = None
    health_status: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    password_masked: Optional[str] = None
    
    model_config = ConfigDict(from_attributes=True)


class FeatureFlagBase(BaseModel):
    """Base model for feature flag"""
    name: str
    description: Optional[str] = None
    enabled: bool = False
    targeting_rules: Optional[Dict[str, Any]] = None
    rollout_percentage: int = 100


class FeatureFlagCreate(FeatureFlagBase):
    """Create feature flag"""
    id: str


class FeatureFlagUpdate(BaseModel):
    """Update feature flag"""
    name: Optional[str] = None
    description: Optional[str] = None
    enabled: Optional[bool] = None
    targeting_rules: Optional[Dict[str, Any]] = None
    rollout_percentage: Optional[int] = None


class FeatureFlagResponse(FeatureFlagBase):
    """Feature flag response"""
    id: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    created_by: Optional[str] = None
    
    model_config = ConfigDict(from_attributes=True)


class AuditLogResponse(BaseModel):
    """Audit log response"""
    id: int
    timestamp: datetime
    config_type: str
    config_id: str
    action: str
    old_value: Optional[Dict[str, Any]] = None
    new_value: Optional[Dict[str, Any]] = None
    changed_fields: Optional[List[str]] = None
    user_id: Optional[str] = None
    user_name: Optional[str] = None
    ip_address: Optional[str] = None
    notes: Optional[str] = None
    
    model_config = ConfigDict(from_attributes=True)


# ============================================================
# Aggregated Response Models
# ============================================================

class AllAdminConfigsResponse(BaseModel):
    """All admin configurations response"""
    system_configs: List[SystemConfigResponse]
    llm_providers: List[LLMProviderResponse]
    embedding_models: List[EmbeddingModelResponse]
    connections: List[ConnectionConfigResponse]
    feature_flags: List[FeatureFlagResponse]
    config_counts: Dict[str, int]


class ConfigHealthResponse(BaseModel):
    """Configuration health check response"""
    status: str
    llm_providers: Dict[str, str]
    embedding_models: Dict[str, str]
    connections: Dict[str, str]
    warnings: List[str]
    timestamp: datetime


# ============================================================
# OAuth Configuration Models
# ============================================================

class OAuthConfig(BaseModel):
    """OAuth 2.0 configuration for connection authentication.
    
    Supports client credentials flow for service-to-service authentication
    (common for Azure API Gateway, Azure AD, etc.).
    """
    auth_method: str = Field(default="oauth", description="Authentication method")
    oauth_client_id: str = Field(..., description="OAuth client ID")
    oauth_client_secret: str = Field(..., description="OAuth client secret")
    oauth_token_url: str = Field(..., description="Token endpoint URL")
    oauth_scope: Optional[str] = Field(None, description="OAuth scope (optional)")
    
    class Config:
        json_schema_extra = {
            "example": {
                "auth_method": "oauth",
                "oauth_client_id": "your-client-id",
                "oauth_client_secret": "your-client-secret",
                "oauth_token_url": "https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token",
                "oauth_scope": "https://graph.microsoft.com/.default"
            }
        }


class OAuthTokenResponse(BaseModel):
    """OAuth token response"""
    access_token: str
    token_type: str = "Bearer"
    expires_in: int
    scope: Optional[str] = None


class OAuthTokenRefreshRequest(BaseModel):
    """Request to refresh OAuth token"""
    connection_id: str = Field(..., description="Connection ID to refresh")
    force_refresh: bool = Field(default=False, description="Force token refresh even if cached")
