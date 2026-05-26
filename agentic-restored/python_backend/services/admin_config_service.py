"""
Admin Configuration Service

Provides centralized access to database-stored configurations.
All services should use this to retrieve LLM, embedding, and system configs
instead of hardcoding values or directly reading environment variables.

Features:
- Caching for performance
- Automatic fallback to environment variables
- Type-safe access to configurations
- Change notifications (optional)
"""

# pylint: disable=broad-exception-caught

from __future__ import annotations

import os
import logging
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta

from sqlalchemy.orm import Session
from sqlalchemy import and_
from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger(__name__)


# ============================================================================
# Configuration Cache
# ============================================================================

class ConfigCache:
    """In-memory cache for configurations with TTL support."""
    
    def __init__(self, ttl_seconds: int = 300):
        self._cache: Dict[str, Any] = {}
        self._timestamps: Dict[str, datetime] = {}
        self._ttl = timedelta(seconds=ttl_seconds)
    
    def get(self, key: str) -> Optional[Any]:
        """Get cached value if not expired."""
        if key in self._cache:
            if datetime.utcnow() - self._timestamps.get(key, datetime.min) < self._ttl:
                return self._cache[key]
            else:
                del self._cache[key]
                del self._timestamps[key]
        return None
    
    def set(self, key: str, value: Any) -> None:
        """Set cached value with current timestamp."""
        self._cache[key] = value
        self._timestamps[key] = datetime.utcnow()
    
    def invalidate(self, key: Optional[str] = None) -> None:
        """Invalidate cache entry or entire cache."""
        if key:
            self._cache.pop(key, None)
            self._timestamps.pop(key, None)
        else:
            self._cache.clear()
            self._timestamps.clear()


# Global cache instance (5 minute TTL)
_config_cache = ConfigCache(ttl_seconds=300)


# ============================================================================
# Admin Config Service
# ============================================================================

class AdminConfigService:
    """
    Service for accessing centralized admin configurations.
    
    Reads from database with caching, falls back to environment variables
    when database configs are not available.
    """
    
    def __init__(self, db: Optional[Session] = None):
        self.db = db
    
    # ------------------------------------------------------------------
    # LLM Provider Configuration
    # ------------------------------------------------------------------
    
    def get_llm_provider_config(self, provider: str) -> Dict[str, Any]:
        """
        Get configuration for a specific LLM provider.
        
        Args:
            provider: Provider name (openai, anthropic, azure_openai, ollama)
        
        Returns:
            Dict with provider configuration including api_key, model, endpoint, etc.
        """
        cache_key = f"llm_provider:{provider}"
        cached = _config_cache.get(cache_key)
        if cached:
            return cached
        
        config: Dict[str, Any] = {}

        db = self.db
        if db is not None:
            try:
                from models.admin_config_models import LLMProviderConfig, ConfigStatus
                
                db_config = db.query(LLMProviderConfig).filter(
                    and_(
                        LLMProviderConfig.provider == provider,
                        LLMProviderConfig.status == ConfigStatus.ACTIVE
                    )
                ).first()
                
                if db_config:
                    config = {
                        "provider": db_config.provider,
                        "api_key": db_config.api_key,
                        "model": db_config.default_chat_model or "",
                        "endpoint": db_config.api_endpoint or "",
                        "api_version": db_config.api_version,
                        "max_tokens": db_config.default_max_tokens,
                        "temperature": db_config.default_temperature,
                        "top_p": db_config.default_top_p,
                        "rate_limit_rpm": db_config.rate_limit_rpm,
                        "rate_limit_tpm": db_config.rate_limit_tpm,
                        "extra_settings": db_config.extra_config or {},
                    }
                    _config_cache.set(cache_key, config)
                    return config
            except (SQLAlchemyError, AttributeError) as e:
                logger.warning("Failed to load LLM config from DB: %s", e)
        
        # Fallback to environment variables
        config = self._get_llm_config_from_env(provider)
        _config_cache.set(cache_key, config)
        return config
    
    def _get_llm_config_from_env(self, provider: str) -> Dict[str, Any]:
        """Get LLM config from environment variables (fallback)."""
        provider_lower = provider.lower()
        
        if provider_lower == "openai":
            return {
                "provider": "openai",
                "api_key": os.getenv("OPENAI_API_KEY", ""),
                "model": os.getenv("OPENAI_MODEL", "gpt-4-turbo-preview"),
                "endpoint": "https://api.openai.com/v1",
                "organization": os.getenv("OPENAI_ORG_ID", ""),
                "max_tokens": int(os.getenv("OPENAI_MAX_TOKENS", "4096")),
                "temperature": float(os.getenv("OPENAI_TEMPERATURE", "0.7")),
            }
        elif provider_lower == "anthropic":
            return {
                "provider": "anthropic",
                "api_key": os.getenv("ANTHROPIC_API_KEY", ""),
                "model": os.getenv("ANTHROPIC_MODEL", "claude-3-sonnet-20240229"),
                "endpoint": "https://api.anthropic.com",
                "max_tokens": int(os.getenv("ANTHROPIC_MAX_TOKENS", "4096")),
                "temperature": float(os.getenv("ANTHROPIC_TEMPERATURE", "0.7")),
            }
        elif provider_lower in ("azure_openai", "azure-openai"):
            return {
                "provider": "azure_openai",
                "api_key": os.getenv("AZURE_OPENAI_KEY", ""),
                "model": os.getenv("AZURE_OPENAI_DEPLOYMENT", ""),
                "endpoint": os.getenv("AZURE_OPENAI_ENDPOINT", ""),
                "api_version": os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview"),
                "max_tokens": int(os.getenv("AZURE_OPENAI_MAX_TOKENS", "4096")),
            }
        elif provider_lower == "ollama":
            return {
                "provider": "ollama",
                "api_key": "",  # Ollama doesn't require API key
                "model": os.getenv("OLLAMA_MODEL", "llama2"),
                "endpoint": os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
            }
        else:
            return {"provider": provider, "api_key": "", "model": ""}
    
    def get_active_llm_provider(self) -> Dict[str, Any]:
        """
        Get the currently active/default LLM provider configuration.
        
        Returns:
            Dict with the active provider's configuration
        """
        cache_key = "llm_provider:active"
        cached = _config_cache.get(cache_key)
        if cached:
            return cached
        
        db = self.db
        if db is not None:
            try:
                from models.admin_config_models import LLMProviderConfig, ConfigStatus
                
                # Try to get primary provider first
                db_config = db.query(LLMProviderConfig).filter(
                    and_(
                        LLMProviderConfig.status == ConfigStatus.ACTIVE,
                        LLMProviderConfig.is_default == True
                    )
                ).first()
                
                # Fall back to any active provider
                if not db_config:
                    db_config = db.query(LLMProviderConfig).filter(
                        LLMProviderConfig.status == ConfigStatus.ACTIVE
                    ).first()
                
                if db_config:
                    config = self.get_llm_provider_config(db_config.provider)
                    _config_cache.set(cache_key, config)
                    return config
            except (SQLAlchemyError, AttributeError) as e:
                logger.warning("Failed to load active LLM provider from DB: %s", e)
        
        # Fallback: check environment for available providers
        for provider in ["openai", "anthropic", "azure_openai", "ollama"]:
            config = self._get_llm_config_from_env(provider)
            if config.get("api_key") or provider == "ollama":
                _config_cache.set(cache_key, config)
                return config
        
        return {"provider": "none", "api_key": "", "model": ""}
    
    def get_all_llm_providers(self) -> List[Dict[str, Any]]:
        """Get all configured LLM providers."""
        cache_key = "llm_providers:all"
        cached = _config_cache.get(cache_key)
        if cached:
            return cached
        
        providers: List[Dict[str, Any]] = []

        db = self.db
        if db is not None:
            try:
                from models.admin_config_models import LLMProviderConfig
                
                db_configs = db.query(LLMProviderConfig).all()
                for cfg in db_configs:
                    providers.append({
                        "id": cfg.id,
                        "name": cfg.name,
                        "provider": cfg.provider,
                        "model": cfg.default_chat_model or "",
                        "status": cfg.status,
                        "is_default": cfg.is_default,
                    })
                if providers:
                    _config_cache.set(cache_key, providers)
                    return providers
            except (SQLAlchemyError, AttributeError) as e:
                logger.warning("Failed to load LLM providers from DB: %s", e)
        
        # Fallback to checking env vars
        for provider in ["openai", "anthropic", "azure_openai", "ollama"]:
            config = self._get_llm_config_from_env(provider)
            if config.get("api_key") or provider == "ollama":
                providers.append({
                    "name": provider.replace("_", " ").title(),
                    "provider": provider,
                    "model": config.get("model", ""),
                    "status": "active",
                    "is_primary": len(providers) == 0,
                })
        
        _config_cache.set(cache_key, providers)
        return providers
    
    # ------------------------------------------------------------------
    # Embedding Model Configuration
    # ------------------------------------------------------------------
    
    def get_embedding_config(self, provider: Optional[str] = None) -> Dict[str, Any]:
        """
        Get embedding model configuration.
        
        Args:
            provider: Optional provider name. If None, returns the active/default.
        
        Returns:
            Dict with embedding configuration
        """
        cache_key = f"embedding:{provider or 'active'}"
        cached = _config_cache.get(cache_key)
        if cached:
            return cached
        
        db = self.db
        if db is not None:
            try:
                from models.admin_config_models import EmbeddingModelConfig, ConfigStatus
                
                query = db.query(EmbeddingModelConfig).filter(
                    EmbeddingModelConfig.status == ConfigStatus.ACTIVE
                )
                if provider:
                    query = query.filter(EmbeddingModelConfig.provider == provider)
                else:
                    query = query.filter(EmbeddingModelConfig.is_default == True)
                
                db_config = query.first()
                
                # Fallback to any active embedding
                if not db_config and not provider:
                    db_config = db.query(EmbeddingModelConfig).filter(
                        EmbeddingModelConfig.status == ConfigStatus.ACTIVE
                    ).first()
                
                if db_config:
                    config: Dict[str, Any] = {
                        "provider": db_config.provider,
                        "model": db_config.model_name,
                        "dimension": db_config.dimension,
                        # Keep these keys stable for callers even though the DB columns
                        # are named custom_*.
                        "api_key": db_config.custom_api_key or "",
                        "endpoint": db_config.custom_endpoint or "",
                        # Use max_input_length as the closest meaning to token/input limit.
                        "max_tokens": getattr(db_config, "max_input_length", 512),
                        "batch_size": db_config.batch_size,
                        "normalize": bool(getattr(db_config, "normalize", True)),
                        "extra_settings": {},
                    }
                    _config_cache.set(cache_key, config)
                    return config
            except (SQLAlchemyError, AttributeError) as e:
                logger.warning("Failed to load embedding config from DB: %s", e)
        
        # Fallback to environment variables
        config = self._get_embedding_config_from_env()
        _config_cache.set(cache_key, config)
        return config
    
    def _get_embedding_config_from_env(self) -> Dict[str, Any]:
        """Get embedding config from environment variables (fallback)."""
        # Check OpenAI embedding first
        openai_key = os.getenv("OPENAI_API_KEY", "")
        if openai_key:
            return {
                "provider": "openai",
                "model": os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small"),
                "dimension": int(os.getenv("OPENAI_EMBEDDING_DIMENSION", "1536")),
                "api_key": openai_key,
                "endpoint": "https://api.openai.com/v1",
                "max_tokens": 8191,
                "batch_size": 100,
            }
        
        # Default to sentence-transformers (local, no API key needed)
        return {
            "provider": "sentence_transformers",
            "model": os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2"),
            "dimension": int(os.getenv("EMBEDDING_DIMENSION", "384")),
            "api_key": "",
            "endpoint": "",
            "max_tokens": 512,
            "batch_size": 32,
        }
    
    # ------------------------------------------------------------------
    # Connection Configuration (Databases, Services)
    # ------------------------------------------------------------------
    
    def get_connection_config(self, connection_type: str) -> Dict[str, Any]:
        """
        Get connection configuration for a specific type.
        
        Args:
            connection_type: Type of connection (postgresql, neo4j, opensearch, redis, etc.)
        
        Returns:
            Dict with connection configuration
        """
        cache_key = f"connection:{connection_type}"
        cached = _config_cache.get(cache_key)
        if cached:
            return cached
        
        db = self.db
        if db is not None:
            try:
                from models.admin_config_models import ConnectionConfig, ConfigStatus
                
                db_config = db.query(ConnectionConfig).filter(
                    and_(
                        ConnectionConfig.connection_type == connection_type,
                        ConnectionConfig.status == ConfigStatus.ACTIVE
                    )
                ).first()
                
                if db_config:
                    config = {
                        "type": db_config.connection_type,
                        "name": db_config.name,
                        "host": db_config.host,
                        "port": db_config.port,
                        "database": db_config.database,
                        "username": db_config.username,
                        "password": db_config.password,
                        "ssl_enabled": db_config.use_ssl,
                        "connection_string": db_config.connection_string,
                        "pool_size": db_config.pool_size,
                        "pool_timeout": db_config.pool_timeout,
                        "extra_settings": db_config.extra_options or {},
                    }
                    _config_cache.set(cache_key, config)
                    return config
            except (SQLAlchemyError, AttributeError) as e:
                logger.warning("Failed to load connection config from DB: %s", e)
        
        # Fallback to environment variables
        config = self._get_connection_config_from_env(connection_type)
        _config_cache.set(cache_key, config)
        return config
    
    def _get_connection_config_from_env(self, connection_type: str) -> Dict[str, Any]:
        """Get connection config from environment variables (fallback)."""
        conn_type = connection_type.lower()
        
        if conn_type in ("postgresql", "postgres"):
            return {
                "type": "postgresql",
                "host": os.getenv("POSTGRES_HOST", "localhost"),
                "port": int(os.getenv("POSTGRES_PORT", "5433")),
                "database": os.getenv("POSTGRES_DB", "graphtrace"),
                "username": os.getenv("POSTGRES_USER", "postgres"),
                "password": os.getenv("POSTGRES_PASSWORD", "postgres"),
                "ssl_enabled": os.getenv("POSTGRES_SSL", "false").lower() == "true",
                "pool_size": int(os.getenv("POSTGRES_POOL_SIZE", "10")),
            }
        elif conn_type == "neo4j":
            return {
                "type": "neo4j",
                "host": os.getenv("NEO4J_HOST", "localhost"),
                "port": int(os.getenv("NEO4J_PORT", "7687")),
                "database": os.getenv("NEO4J_DATABASE", "neo4j"),
                "username": os.getenv("NEO4J_USER", "neo4j"),
                "password": os.getenv("NEO4J_PASSWORD", "password"),
                "ssl_enabled": os.getenv("NEO4J_SSL", "false").lower() == "true",
            }
        elif conn_type == "opensearch":
            return {
                "type": "opensearch",
                "host": os.getenv("OPENSEARCH_HOST", "localhost"),
                "port": int(os.getenv("OPENSEARCH_PORT", "9200")),
                "username": os.getenv("OPENSEARCH_USER", "admin"),
                "password": os.getenv("OPENSEARCH_PASSWORD", "admin"),
                "ssl_enabled": os.getenv("OPENSEARCH_SSL", "false").lower() == "true",
            }
        elif conn_type == "redis":
            return {
                "type": "redis",
                "host": os.getenv("REDIS_HOST", "localhost"),
                "port": int(os.getenv("REDIS_PORT", "6379")),
                "password": os.getenv("REDIS_PASSWORD", ""),
                "database": int(os.getenv("REDIS_DB", "0")),
            }
        else:
            return {"type": connection_type}
    
    # ------------------------------------------------------------------
    # System Configuration (Key-Value Store)
    # ------------------------------------------------------------------
    
    def get_system_config(self, category: str, key: str, default: Any = None) -> Any:
        """
        Get a system configuration value.
        
        Args:
            category: Configuration category
            key: Configuration key
            default: Default value if not found
        
        Returns:
            Configuration value
        """
        cache_key = f"system:{category}:{key}"
        cached = _config_cache.get(cache_key)
        if cached is not None:
            return cached
        
        db = self.db
        if db is not None:
            try:
                from models.admin_config_models import SystemConfiguration
                
                db_config = db.query(SystemConfiguration).filter(
                    and_(
                        SystemConfiguration.category == category,
                        SystemConfiguration.key == key,
                        SystemConfiguration.enabled == True
                    )
                ).first()
                
                if db_config:
                    value = self._parse_config_value(
                        db_config.value,
                        db_config.value_type
                    )
                    _config_cache.set(cache_key, value)
                    return value
            except (SQLAlchemyError, AttributeError) as e:
                logger.warning("Failed to load system config from DB: %s", e)
        
        _config_cache.set(cache_key, default)
        return default
    
    def get_system_configs_by_category(self, category: str) -> Dict[str, Any]:
        """Get all system configurations for a category."""
        cache_key = f"system_category:{category}"
        cached = _config_cache.get(cache_key)
        if cached:
            return cached
        
        configs: Dict[str, Any] = {}

        db = self.db
        if db is not None:
            try:
                from models.admin_config_models import SystemConfiguration
                
                db_configs = db.query(SystemConfiguration).filter(
                    and_(
                        SystemConfiguration.category == category,
                        SystemConfiguration.enabled == True
                    )
                ).all()
                
                for cfg in db_configs:
                    configs[cfg.key] = self._parse_config_value(cfg.value, cfg.value_type)
                
                if configs:
                    _config_cache.set(cache_key, configs)
                    return configs
            except (SQLAlchemyError, AttributeError) as e:
                logger.warning("Failed to load system configs from DB: %s", e)
        
        _config_cache.set(cache_key, configs)
        return configs
    
    def _parse_config_value(self, value: str, value_type: str) -> Any:
        """Parse configuration value based on its type."""
        if value is None:
            return None
        
        if value_type == "number":
            try:
                return float(value) if "." in value else int(value)
            except (ValueError, TypeError):
                return value
        elif value_type == "boolean":
            return value.lower() in ("true", "1", "yes", "on")
        elif value_type == "json":
            import json
            try:
                return json.loads(value)
            except (json.JSONDecodeError, TypeError):
                return value
        else:
            return value
    
    # ------------------------------------------------------------------
    # Feature Flags
    # ------------------------------------------------------------------
    
    def is_feature_enabled(self, feature_key: str) -> bool:
        """
        Check if a feature flag is enabled.
        
        Args:
            feature_key: The feature flag key
        
        Returns:
            True if feature is enabled, False otherwise
        """
        cache_key = f"feature:{feature_key}"
        cached = _config_cache.get(cache_key)
        if cached is not None:
            return cached
        
        db = self.db
        if db is not None:
            try:
                from models.admin_config_models import FeatureFlag
                
                flag = db.query(FeatureFlag).filter(FeatureFlag.id == feature_key).first()
                
                if flag:
                    enabled = flag.enabled
                    _config_cache.set(cache_key, enabled)
                    return enabled
            except (SQLAlchemyError, AttributeError) as e:
                logger.warning("Failed to load feature flag from DB: %s", e)
        
        # Default to False for unknown flags
        _config_cache.set(cache_key, False)
        return False
    
    def get_all_feature_flags(self) -> Dict[str, bool]:
        """Get all feature flags."""
        cache_key = "features:all"
        cached = _config_cache.get(cache_key)
        if cached:
            return cached
        
        flags: Dict[str, bool] = {}

        db = self.db
        if db is not None:
            try:
                from models.admin_config_models import FeatureFlag
                
                db_flags = db.query(FeatureFlag).all()
                for flag in db_flags:
                    flags[flag.id] = flag.enabled
                
                if flags:
                    _config_cache.set(cache_key, flags)
                    return flags
            except (SQLAlchemyError, AttributeError) as e:
                logger.warning("Failed to load feature flags from DB: %s", e)
        
        _config_cache.set(cache_key, flags)
        return flags
    
    # ------------------------------------------------------------------
    # API Keys
    # ------------------------------------------------------------------
    
    def get_api_key(self, service: str) -> Optional[str]:
        """
        Get API key for a specific service.
        
        Args:
            service: Service name (e.g., 'openai', 'anthropic', 'github')
        
        Returns:
            API key string or None
        """
        cache_key = f"api_key:{service}"
        cached = _config_cache.get(cache_key)
        if cached:
            return cached
        
        db = self.db
        if db is not None:
            try:
                from models.admin_config_models import APIKeyConfig, ConfigStatus
                
                db_config = db.query(APIKeyConfig).filter(
                    and_(
                        APIKeyConfig.service_name == service,
                        APIKeyConfig.status == ConfigStatus.ACTIVE
                    )
                ).first()
                
                if db_config and db_config.api_key:
                    _config_cache.set(cache_key, db_config.api_key)
                    return db_config.api_key
            except (SQLAlchemyError, AttributeError) as e:
                logger.warning("Failed to load API key from DB: %s", e)
        
        # Fallback to environment variable
        env_key = f"{service.upper()}_API_KEY"
        api_key = os.getenv(env_key, "")
        if api_key:
            _config_cache.set(cache_key, api_key)
        return api_key or None
    
    # ------------------------------------------------------------------
    # Cache Management
    # ------------------------------------------------------------------
    
    def invalidate_cache(self, key: Optional[str] = None) -> None:
        """
        Invalidate configuration cache.
        
        Args:
            key: Specific cache key to invalidate. If None, clears all cache.
        """
        _config_cache.invalidate(key)
        logger.info("Configuration cache invalidated: %s", key or "ALL")
    
    def refresh_config(self) -> None:
        """Refresh all configurations from database."""
        self.invalidate_cache()


# ============================================================================
# Dependency Injection Helper
# ============================================================================

def get_admin_config_service(db: Optional[Session] = None):
    """
    Get AdminConfigService instance.
    
    Can be used as a FastAPI dependency:
    
        @router.get("/example")
        def example(config: AdminConfigService = Depends(get_admin_config_service)):
            llm_config = config.get_active_llm_provider()
            ...
    
    Or instantiated directly with a session.
    """
    return AdminConfigService(db)


# ============================================================================
# Convenience Functions (Module-Level)
# ============================================================================

def get_llm_config(provider: str, db: Optional[Session] = None) -> Dict[str, Any]:
    """Get LLM provider configuration."""
    return AdminConfigService(db).get_llm_provider_config(provider)


def get_active_llm(db: Optional[Session] = None) -> Dict[str, Any]:
    """Get active LLM provider configuration."""
    return AdminConfigService(db).get_active_llm_provider()


def get_embedding(db: Optional[Session] = None) -> Dict[str, Any]:
    """Get embedding model configuration."""
    return AdminConfigService(db).get_embedding_config()


def get_connection(connection_type: str, db: Optional[Session] = None) -> Dict[str, Any]:
    """Get connection configuration."""
    return AdminConfigService(db).get_connection_config(connection_type)


def is_feature_enabled(feature_key: str, db: Optional[Session] = None) -> bool:
    """Check if feature flag is enabled."""
    return AdminConfigService(db).is_feature_enabled(feature_key)


def invalidate_config_cache() -> None:
    """Invalidate all configuration cache."""
    _config_cache.invalidate()
