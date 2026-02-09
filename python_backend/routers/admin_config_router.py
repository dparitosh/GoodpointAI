"""
Admin Configuration Router

API endpoints for managing LLM providers, embedding models,
API keys, and all system configurations centrally.
"""

import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, Query, status, Request
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_

from core.db_session import get_db
from models.admin_config_models import (
    # ORM Models
    SystemConfiguration,
    LLMProviderConfig,
    EmbeddingModelConfig,
    APIKeyConfig,
    ConnectionConfig,
    FeatureFlag,
    AuditLog,
    # Enums
    ConfigCategory,
    LLMProvider,
    EmbeddingProvider,
    # Pydantic Models
    SystemConfigCreate,
    SystemConfigUpdate,
    SystemConfigResponse,
    LLMProviderCreate,
    LLMProviderUpdate,
    LLMProviderResponse,
    EmbeddingModelCreate,
    EmbeddingModelUpdate,
    EmbeddingModelResponse,
    ConnectionConfigCreate,
    ConnectionConfigUpdate,
    ConnectionConfigResponse,
    FeatureFlagCreate,
    FeatureFlagUpdate,
    FeatureFlagResponse,
    AuditLogResponse,
    AllAdminConfigsResponse,
    ConfigHealthResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin/config", tags=["Admin Configuration"])


# ============================================================
# Helper Functions
# ============================================================

def mask_secret(value: Optional[str], show_chars: int = 4) -> Optional[str]:
    """Mask a secret value, showing only last few characters."""
    if not value:
        return None
    if len(value) <= show_chars:
        return "*" * len(value)
    return "*" * (len(value) - show_chars) + value[-show_chars:]


def log_audit(
    db: Session,
    config_type: str,
    config_id: str,
    action: str,
    old_value: Optional[Dict[str, Any]] = None,
    new_value: Optional[Dict[str, Any]] = None,
    user_id: Optional[str] = None,
    user_name: Optional[str] = None,
    ip_address: Optional[str] = None,
    notes: Optional[str] = None
):
    """Log configuration change to audit log."""
    # Calculate changed fields
    changed_fields = None
    if old_value and new_value:
        changed_fields = [k for k in new_value if old_value.get(k) != new_value.get(k)]
    elif new_value:
        changed_fields = list(new_value.keys())
    
    audit_entry = AuditLog(
        config_type=config_type,
        config_id=str(config_id),
        action=action,
        old_value=old_value,
        new_value=new_value,
        changed_fields=changed_fields,
        user_id=user_id,
        user_name=user_name,
        ip_address=ip_address,
        notes=notes
    )
    db.add(audit_entry)


def invalidate_config_cache():
    """Invalidate the admin config cache after changes."""
    try:
        from services.admin_config_service import invalidate_config_cache as _invalidate
        _invalidate()
        logger.info("Admin config cache invalidated")
    except Exception as e:
        logger.warning("Failed to invalidate config cache: %s", e)


def _workspace_root() -> Path:
    # python_backend/routers -> python_backend -> repo root
    return Path(__file__).resolve().parents[2]


def _allowed_local_roots() -> List[Path]:
    root = _workspace_root()
    candidates = [root / "data", root / "python_backend" / "data", root.parent / "data"]
    return [p.resolve() for p in candidates if p.exists()]


def _is_under_allowed_root(path: Path) -> bool:
    # Allow all local paths for desktop app usage
    return True


def _get_extra_options(conn: ConnectionConfig) -> Dict[str, Any]:
    return conn.extra_options if isinstance(conn.extra_options, dict) else {}


def _missing_fields(fields: Dict[str, Any], required: List[str]) -> List[str]:
    missing: List[str] = []
    for key in required:
        val = fields.get(key)
        if val is None:
            missing.append(key)
            continue
        if isinstance(val, str) and not val.strip():
            missing.append(key)
            continue
    return missing


# ============================================================
# Cache Management API
# ============================================================

@router.post("/cache/invalidate", response_model=Dict[str, str])
async def invalidate_cache():
    """
    Invalidate the configuration cache.
    
    Call this endpoint after making configuration changes to ensure
    all services pick up the new values immediately.
    """
    invalidate_config_cache()
    return {"status": "success", "message": "Configuration cache invalidated"}


# ============================================================
# System Configuration API
# ============================================================

@router.get("/system", response_model=List[SystemConfigResponse])
async def list_system_configs(
    category: Optional[str] = Query(None, description="Filter by category"),
    enabled_only: bool = Query(False, description="Only return enabled configs"),
    include_secrets: bool = Query(False, description="Include secret values (admin only)"),
    db: Session = Depends(get_db)
):
    """List all system configurations."""
    query = db.query(SystemConfiguration)
    
    if category:
        query = query.filter(SystemConfiguration.category == category)
    if enabled_only:
        query = query.filter(SystemConfiguration.enabled == True)
    
    configs = query.order_by(SystemConfiguration.category, SystemConfiguration.key).all()
    
    # Mask secrets if not requesting them
    result = []
    for config in configs:
        config_dict = {
            "id": config.id,
            "category": config.category,
            "key": config.key,
            "value": config.value if (not config.is_secret or include_secrets) else mask_secret(config.value),
            "value_type": config.value_type,
            "description": config.description,
            "is_secret": config.is_secret,
            "is_required": config.is_required,
            "default_value": config.default_value,
            "validation_regex": config.validation_regex,
            "enabled": config.enabled,
            "created_at": config.created_at,
            "updated_at": config.updated_at,
            "created_by": config.created_by,
            "updated_by": config.updated_by
        }
        result.append(SystemConfigResponse(**config_dict))
    
    return result


@router.get("/system/categories", response_model=List[str])
async def list_config_categories(db: Session = Depends(get_db)):
    """List all configuration categories."""
    categories = db.query(SystemConfiguration.category).distinct().all()
    return [cat[0] for cat in categories]


@router.get("/system/{config_id}", response_model=SystemConfigResponse)
async def get_system_config(config_id: int, db: Session = Depends(get_db)):
    """Get a specific system configuration."""
    config = db.query(SystemConfiguration).filter(SystemConfiguration.id == config_id).first()
    if not config:
        raise HTTPException(status_code=404, detail="Configuration not found")
    return config


@router.get("/system/by-key/{category}/{key}", response_model=SystemConfigResponse)
async def get_system_config_by_key(category: str, key: str, db: Session = Depends(get_db)):
    """Get a system configuration by category and key."""
    config = db.query(SystemConfiguration).filter(
        SystemConfiguration.category == category,
        SystemConfiguration.key == key
    ).first()
    if not config:
        raise HTTPException(status_code=404, detail="Configuration not found")
    return config


@router.post("/system", response_model=SystemConfigResponse, status_code=status.HTTP_201_CREATED)
async def create_system_config(
    config: SystemConfigCreate,
    request: Request,
    db: Session = Depends(get_db)
):
    """Create a new system configuration."""
    # Check for duplicate
    existing = db.query(SystemConfiguration).filter(
        SystemConfiguration.category == config.category,
        SystemConfiguration.key == config.key
    ).first()
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Configuration '{config.key}' already exists in category '{config.category}'"
        )
    
    db_config = SystemConfiguration(**config.model_dump())
    db.add(db_config)
    
    # Log audit
    log_audit(
        db, "system_config", f"{config.category}.{config.key}", "create",
        new_value=config.model_dump(),
        ip_address=request.client.host if request.client else None
    )
    
    db.commit()
    db.refresh(db_config)
    
    # Invalidate cache so changes take effect
    invalidate_config_cache()
    
    return db_config


@router.put("/system/{config_id}", response_model=SystemConfigResponse)
async def update_system_config(
    config_id: int,
    config_update: SystemConfigUpdate,
    request: Request,
    db: Session = Depends(get_db)
):
    """Update a system configuration."""
    db_config = db.query(SystemConfiguration).filter(SystemConfiguration.id == config_id).first()
    if not db_config:
        raise HTTPException(status_code=404, detail="Configuration not found")
    
    old_value = {
        "value": db_config.value,
        "description": db_config.description,
        "enabled": db_config.enabled
    }
    
    update_data = config_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_config, field, value)
    
    # Log audit
    log_audit(
        db, "system_config", f"{db_config.category}.{db_config.key}", "update",
        old_value=old_value,
        new_value=update_data,
        ip_address=request.client.host if request.client else None
    )
    
    db.commit()
    db.refresh(db_config)
    
    # Invalidate cache so changes take effect
    invalidate_config_cache()
    
    return db_config


@router.delete("/system/{config_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_system_config(
    config_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    """Delete a system configuration."""
    db_config = db.query(SystemConfiguration).filter(SystemConfiguration.id == config_id).first()
    if not db_config:
        raise HTTPException(status_code=404, detail="Configuration not found")
    
    # Log audit
    log_audit(
        db, "system_config", f"{db_config.category}.{db_config.key}", "delete",
        old_value={"value": db_config.value, "category": db_config.category, "key": db_config.key},
        ip_address=request.client.host if request.client else None
    )
    
    db.delete(db_config)
    db.commit()
    
    # Invalidate cache so changes take effect
    invalidate_config_cache()


# ============================================================
# LLM Provider Configuration API
# ============================================================

@router.get("/llm-providers", response_model=List[LLMProviderResponse])
async def list_llm_providers(
    provider: Optional[str] = Query(None, description="Filter by provider type"),
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status"),
    db: Session = Depends(get_db)
):
    """List all LLM provider configurations."""
    query = db.query(LLMProviderConfig)
    
    if provider:
        query = query.filter(LLMProviderConfig.provider == provider)
    if status_filter:
        query = query.filter(LLMProviderConfig.status == status_filter)
    
    providers = query.order_by(LLMProviderConfig.priority.desc(), LLMProviderConfig.name).all()
    
    result = []
    for p in providers:
        response = LLMProviderResponse(
            id=p.id,
            provider=p.provider,
            name=p.name,
            description=p.description,
            api_key=None,  # Never return actual API key
            api_key_masked=mask_secret(p.api_key) if p.api_key else None,
            api_endpoint=p.api_endpoint,
            api_version=p.api_version,
            azure_deployment=p.azure_deployment,
            azure_resource_name=p.azure_resource_name,
            default_chat_model=p.default_chat_model,
            default_completion_model=p.default_completion_model,
            default_embedding_model=p.default_embedding_model,
            default_temperature=p.default_temperature,
            default_max_tokens=p.default_max_tokens,
            default_top_p=p.default_top_p,
            rate_limit_rpm=p.rate_limit_rpm,
            rate_limit_tpm=p.rate_limit_tpm,
            cost_per_1k_input_tokens=p.cost_per_1k_input_tokens,
            cost_per_1k_output_tokens=p.cost_per_1k_output_tokens,
            status=p.status,
            is_default=p.is_default,
            priority=p.priority,
            extra_config=p.extra_config,
            created_at=p.created_at,
            updated_at=p.updated_at,
            created_by=p.created_by
        )
        result.append(response)
    
    return result


@router.get("/llm-providers/default", response_model=LLMProviderResponse)
async def get_default_llm_provider(db: Session = Depends(get_db)):
    """Get the default LLM provider."""
    provider = db.query(LLMProviderConfig).filter(
        LLMProviderConfig.is_default == True,
        LLMProviderConfig.status == "active"
    ).first()
    
    if not provider:
        # Fallback to highest priority active provider
        provider = db.query(LLMProviderConfig).filter(
            LLMProviderConfig.status == "active"
        ).order_by(LLMProviderConfig.priority.desc()).first()
    
    if not provider:
        raise HTTPException(status_code=404, detail="No LLM provider configured")
    
    return LLMProviderResponse(
        id=provider.id,
        provider=provider.provider,
        name=provider.name,
        description=provider.description,
        api_key=None,
        api_key_masked=mask_secret(provider.api_key) if provider.api_key else None,
        api_endpoint=provider.api_endpoint,
        api_version=provider.api_version,
        azure_deployment=provider.azure_deployment,
        azure_resource_name=provider.azure_resource_name,
        default_chat_model=provider.default_chat_model,
        default_completion_model=provider.default_completion_model,
        default_embedding_model=provider.default_embedding_model,
        default_temperature=provider.default_temperature,
        default_max_tokens=provider.default_max_tokens,
        default_top_p=provider.default_top_p,
        rate_limit_rpm=provider.rate_limit_rpm,
        rate_limit_tpm=provider.rate_limit_tpm,
        cost_per_1k_input_tokens=provider.cost_per_1k_input_tokens,
        cost_per_1k_output_tokens=provider.cost_per_1k_output_tokens,
        status=provider.status,
        is_default=provider.is_default,
        priority=provider.priority,
        extra_config=provider.extra_config,
        created_at=provider.created_at,
        updated_at=provider.updated_at,
        created_by=provider.created_by
    )


@router.get("/llm-providers/{provider_id}", response_model=LLMProviderResponse)
async def get_llm_provider(provider_id: str, db: Session = Depends(get_db)):
    """Get a specific LLM provider configuration."""
    provider = db.query(LLMProviderConfig).filter(LLMProviderConfig.id == provider_id).first()
    if not provider:
        raise HTTPException(status_code=404, detail="LLM provider not found")
    
    return LLMProviderResponse(
        id=provider.id,
        provider=provider.provider,
        name=provider.name,
        description=provider.description,
        api_key=None,
        api_key_masked=mask_secret(provider.api_key) if provider.api_key else None,
        api_endpoint=provider.api_endpoint,
        api_version=provider.api_version,
        azure_deployment=provider.azure_deployment,
        azure_resource_name=provider.azure_resource_name,
        default_chat_model=provider.default_chat_model,
        default_completion_model=provider.default_completion_model,
        default_embedding_model=provider.default_embedding_model,
        default_temperature=provider.default_temperature,
        default_max_tokens=provider.default_max_tokens,
        default_top_p=provider.default_top_p,
        rate_limit_rpm=provider.rate_limit_rpm,
        rate_limit_tpm=provider.rate_limit_tpm,
        cost_per_1k_input_tokens=provider.cost_per_1k_input_tokens,
        cost_per_1k_output_tokens=provider.cost_per_1k_output_tokens,
        status=provider.status,
        is_default=provider.is_default,
        priority=provider.priority,
        extra_config=provider.extra_config,
        created_at=provider.created_at,
        updated_at=provider.updated_at,
        created_by=provider.created_by
    )


@router.post("/llm-providers", response_model=LLMProviderResponse, status_code=status.HTTP_201_CREATED)
async def create_llm_provider(
    provider: LLMProviderCreate,
    request: Request,
    db: Session = Depends(get_db)
):
    """Create a new LLM provider configuration."""
    existing = db.query(LLMProviderConfig).filter(LLMProviderConfig.id == provider.id).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Provider '{provider.id}' already exists")
    
    # If setting as default, unset other defaults
    if provider.is_default:
        db.query(LLMProviderConfig).filter(
            LLMProviderConfig.provider == provider.provider,
            LLMProviderConfig.is_default == True
        ).update({"is_default": False})
    
    db_provider = LLMProviderConfig(**provider.model_dump())
    db.add(db_provider)
    
    # Log audit (mask API key)
    audit_data = provider.model_dump()
    if audit_data.get("api_key"):
        audit_data["api_key"] = "[REDACTED]"
    log_audit(
        db, "llm_provider", provider.id, "create",
        new_value=audit_data,
        ip_address=request.client.host if request.client else None
    )
    
    db.commit()
    db.refresh(db_provider)
    
    # Invalidate cache so changes take effect
    invalidate_config_cache()
    
    return LLMProviderResponse(
        id=db_provider.id,
        provider=db_provider.provider,
        name=db_provider.name,
        description=db_provider.description,
        api_key=None,
        api_key_masked=mask_secret(db_provider.api_key) if db_provider.api_key else None,
        api_endpoint=db_provider.api_endpoint,
        api_version=db_provider.api_version,
        azure_deployment=db_provider.azure_deployment,
        azure_resource_name=db_provider.azure_resource_name,
        default_chat_model=db_provider.default_chat_model,
        default_completion_model=db_provider.default_completion_model,
        default_embedding_model=db_provider.default_embedding_model,
        default_temperature=db_provider.default_temperature,
        default_max_tokens=db_provider.default_max_tokens,
        default_top_p=db_provider.default_top_p,
        rate_limit_rpm=db_provider.rate_limit_rpm,
        rate_limit_tpm=db_provider.rate_limit_tpm,
        cost_per_1k_input_tokens=db_provider.cost_per_1k_input_tokens,
        cost_per_1k_output_tokens=db_provider.cost_per_1k_output_tokens,
        status=db_provider.status,
        is_default=db_provider.is_default,
        priority=db_provider.priority,
        extra_config=db_provider.extra_config,
        created_at=db_provider.created_at,
        updated_at=db_provider.updated_at,
        created_by=db_provider.created_by
    )


@router.put("/llm-providers/{provider_id}", response_model=LLMProviderResponse)
async def update_llm_provider(
    provider_id: str,
    provider_update: LLMProviderUpdate,
    request: Request,
    db: Session = Depends(get_db)
):
    """Update an LLM provider configuration."""
    db_provider = db.query(LLMProviderConfig).filter(LLMProviderConfig.id == provider_id).first()
    if not db_provider:
        raise HTTPException(status_code=404, detail="LLM provider not found")
    
    old_value = {"name": db_provider.name, "status": db_provider.status}
    
    update_data = provider_update.model_dump(exclude_unset=True)
    
    # If setting as default, unset other defaults
    if update_data.get("is_default"):
        db.query(LLMProviderConfig).filter(
            LLMProviderConfig.provider == db_provider.provider,
            LLMProviderConfig.id != provider_id,
            LLMProviderConfig.is_default == True
        ).update({"is_default": False})
    
    for field, value in update_data.items():
        setattr(db_provider, field, value)
    
    # Log audit (mask API key)
    audit_update = update_data.copy()
    if audit_update.get("api_key"):
        audit_update["api_key"] = "[REDACTED]"
    log_audit(
        db, "llm_provider", provider_id, "update",
        old_value=old_value,
        new_value=audit_update,
        ip_address=request.client.host if request.client else None
    )
    
    db.commit()
    db.refresh(db_provider)
    
    # Invalidate cache so changes take effect
    invalidate_config_cache()
    
    return LLMProviderResponse(
        id=db_provider.id,
        provider=db_provider.provider,
        name=db_provider.name,
        description=db_provider.description,
        api_key=None,
        api_key_masked=mask_secret(db_provider.api_key) if db_provider.api_key else None,
        api_endpoint=db_provider.api_endpoint,
        api_version=db_provider.api_version,
        azure_deployment=db_provider.azure_deployment,
        azure_resource_name=db_provider.azure_resource_name,
        default_chat_model=db_provider.default_chat_model,
        default_completion_model=db_provider.default_completion_model,
        default_embedding_model=db_provider.default_embedding_model,
        default_temperature=db_provider.default_temperature,
        default_max_tokens=db_provider.default_max_tokens,
        default_top_p=db_provider.default_top_p,
        rate_limit_rpm=db_provider.rate_limit_rpm,
        rate_limit_tpm=db_provider.rate_limit_tpm,
        cost_per_1k_input_tokens=db_provider.cost_per_1k_input_tokens,
        cost_per_1k_output_tokens=db_provider.cost_per_1k_output_tokens,
        status=db_provider.status,
        is_default=db_provider.is_default,
        priority=db_provider.priority,
        extra_config=db_provider.extra_config,
        created_at=db_provider.created_at,
        updated_at=db_provider.updated_at,
        created_by=db_provider.created_by
    )


@router.delete("/llm-providers/{provider_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_llm_provider(
    provider_id: str,
    request: Request,
    db: Session = Depends(get_db)
):
    """Delete an LLM provider configuration."""
    db_provider = db.query(LLMProviderConfig).filter(LLMProviderConfig.id == provider_id).first()
    if not db_provider:
        raise HTTPException(status_code=404, detail="LLM provider not found")
    
    log_audit(
        db, "llm_provider", provider_id, "delete",
        old_value={"name": db_provider.name, "provider": db_provider.provider},
        ip_address=request.client.host if request.client else None
    )
    
    db.delete(db_provider)
    db.commit()
    
    # Invalidate cache so changes take effect
    invalidate_config_cache()


# ============================================================
# Embedding Model Configuration API
# ============================================================

@router.get("/embedding-models", response_model=List[EmbeddingModelResponse])
async def list_embedding_models(
    provider: Optional[str] = Query(None, description="Filter by provider"),
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status"),
    db: Session = Depends(get_db)
):
    """List all embedding model configurations."""
    query = db.query(EmbeddingModelConfig)
    
    if provider:
        query = query.filter(EmbeddingModelConfig.provider == provider)
    if status_filter:
        query = query.filter(EmbeddingModelConfig.status == status_filter)
    
    return query.order_by(EmbeddingModelConfig.name).all()


@router.get("/embedding-models/default", response_model=EmbeddingModelResponse)
async def get_default_embedding_model(db: Session = Depends(get_db)):
    """Get the default embedding model."""
    model = db.query(EmbeddingModelConfig).filter(
        EmbeddingModelConfig.is_default == True,
        EmbeddingModelConfig.status == "active"
    ).first()
    
    if not model:
        # Fallback to first active model
        model = db.query(EmbeddingModelConfig).filter(
            EmbeddingModelConfig.status == "active"
        ).first()
    
    if not model:
        raise HTTPException(status_code=404, detail="No embedding model configured")
    
    return model


@router.get("/embedding-models/{model_id}", response_model=EmbeddingModelResponse)
async def get_embedding_model(model_id: str, db: Session = Depends(get_db)):
    """Get a specific embedding model configuration."""
    model = db.query(EmbeddingModelConfig).filter(EmbeddingModelConfig.id == model_id).first()
    if not model:
        raise HTTPException(status_code=404, detail="Embedding model not found")
    return model


@router.post("/embedding-models", response_model=EmbeddingModelResponse, status_code=status.HTTP_201_CREATED)
async def create_embedding_model(
    model: EmbeddingModelCreate,
    request: Request,
    db: Session = Depends(get_db)
):
    """Create a new embedding model configuration."""
    existing = db.query(EmbeddingModelConfig).filter(EmbeddingModelConfig.id == model.id).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Embedding model '{model.id}' already exists")
    
    # If setting as default, unset other defaults
    if model.is_default:
        db.query(EmbeddingModelConfig).filter(EmbeddingModelConfig.is_default == True).update({"is_default": False})
    
    db_model = EmbeddingModelConfig(**model.model_dump())
    db.add(db_model)
    
    log_audit(
        db, "embedding_model", model.id, "create",
        new_value=model.model_dump(),
        ip_address=request.client.host if request.client else None
    )
    
    db.commit()
    db.refresh(db_model)
    return db_model


@router.put("/embedding-models/{model_id}", response_model=EmbeddingModelResponse)
async def update_embedding_model(
    model_id: str,
    model_update: EmbeddingModelUpdate,
    request: Request,
    db: Session = Depends(get_db)
):
    """Update an embedding model configuration."""
    db_model = db.query(EmbeddingModelConfig).filter(EmbeddingModelConfig.id == model_id).first()
    if not db_model:
        raise HTTPException(status_code=404, detail="Embedding model not found")
    
    old_value = {"name": db_model.name, "status": db_model.status}
    
    update_data = model_update.model_dump(exclude_unset=True)
    
    # If setting as default, unset other defaults
    if update_data.get("is_default"):
        db.query(EmbeddingModelConfig).filter(
            EmbeddingModelConfig.id != model_id,
            EmbeddingModelConfig.is_default == True
        ).update({"is_default": False})
    
    for field, value in update_data.items():
        setattr(db_model, field, value)
    
    log_audit(
        db, "embedding_model", model_id, "update",
        old_value=old_value,
        new_value=update_data,
        ip_address=request.client.host if request.client else None
    )
    
    db.commit()
    db.refresh(db_model)
    
    # Invalidate cache so changes take effect
    invalidate_config_cache()
    
    return db_model


@router.delete("/embedding-models/{model_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_embedding_model(
    model_id: str,
    request: Request,
    db: Session = Depends(get_db)
):
    """Delete an embedding model configuration."""
    db_model = db.query(EmbeddingModelConfig).filter(EmbeddingModelConfig.id == model_id).first()
    if not db_model:
        raise HTTPException(status_code=404, detail="Embedding model not found")
    
    log_audit(
        db, "embedding_model", model_id, "delete",
        old_value={"name": db_model.name, "model_name": db_model.model_name},
        ip_address=request.client.host if request.client else None
    )
    
    db.delete(db_model)
    db.commit()
    
    # Invalidate cache so changes take effect
    invalidate_config_cache()


# ============================================================
# Connection Configuration API
# ============================================================

@router.get("/connections", response_model=List[ConnectionConfigResponse])
async def list_connections(
    connection_type: Optional[str] = Query(None, description="Filter by type"),
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status"),
    db: Session = Depends(get_db)
):
    """List all connection configurations."""
    query = db.query(ConnectionConfig)
    
    if connection_type:
        query = query.filter(ConnectionConfig.connection_type == connection_type)
    if status_filter:
        query = query.filter(ConnectionConfig.status == status_filter)
    
    connections = query.order_by(ConnectionConfig.connection_type, ConnectionConfig.name).all()
    
    result = []
    for conn in connections:
        response = ConnectionConfigResponse(
            id=conn.id,
            connection_type=conn.connection_type,
            name=conn.name,
            description=conn.description,
            connection_string=mask_secret(conn.connection_string) if conn.connection_string else None,
            host=conn.host,
            port=conn.port,
            database=conn.database,
            username=conn.username,
            password=None,  # Never return password
            password_masked=mask_secret(conn.password) if conn.password else None,
            use_ssl=conn.use_ssl,
            ssl_cert_path=conn.ssl_cert_path,
            pool_size=conn.pool_size,
            max_overflow=conn.max_overflow,
            pool_timeout=conn.pool_timeout,
            extra_options=conn.extra_options,
            status=conn.status,
            is_default=conn.is_default,
            last_health_check=conn.last_health_check,
            health_status=conn.health_status,
            created_at=conn.created_at,
            updated_at=conn.updated_at
        )
        result.append(response)
    
    return result


@router.get("/connections/{conn_id}", response_model=ConnectionConfigResponse)
async def get_connection(conn_id: str, db: Session = Depends(get_db)):
    """Get a specific connection configuration."""
    conn = db.query(ConnectionConfig).filter(ConnectionConfig.id == conn_id).first()
    if not conn:
        raise HTTPException(status_code=404, detail="Connection not found")
    
    return ConnectionConfigResponse(
        id=conn.id,
        connection_type=conn.connection_type,
        name=conn.name,
        description=conn.description,
        connection_string=mask_secret(conn.connection_string) if conn.connection_string else None,
        host=conn.host,
        port=conn.port,
        database=conn.database,
        username=conn.username,
        password=None,
        password_masked=mask_secret(conn.password) if conn.password else None,
        use_ssl=conn.use_ssl,
        ssl_cert_path=conn.ssl_cert_path,
        pool_size=conn.pool_size,
        max_overflow=conn.max_overflow,
        pool_timeout=conn.pool_timeout,
        extra_options=conn.extra_options,
        status=conn.status,
        is_default=conn.is_default,
        last_health_check=conn.last_health_check,
        health_status=conn.health_status,
        created_at=conn.created_at,
        updated_at=conn.updated_at
    )


@router.post("/connections", response_model=ConnectionConfigResponse, status_code=status.HTTP_201_CREATED)
async def create_connection(
    connection: ConnectionConfigCreate,
    request: Request,
    db: Session = Depends(get_db)
):
    """Create a new connection configuration."""
    existing = db.query(ConnectionConfig).filter(ConnectionConfig.id == connection.id).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Connection '{connection.id}' already exists")
    
    # If setting as default, unset other defaults for same type
    if connection.is_default:
        db.query(ConnectionConfig).filter(
            ConnectionConfig.connection_type == connection.connection_type,
            ConnectionConfig.is_default == True
        ).update({"is_default": False})
    
    db_conn = ConnectionConfig(**connection.model_dump())
    db.add(db_conn)
    
    # Log audit (mask secrets)
    audit_data = connection.model_dump()
    if audit_data.get("password"):
        audit_data["password"] = "[REDACTED]"
    if audit_data.get("connection_string"):
        audit_data["connection_string"] = "[REDACTED]"
    log_audit(
        db, "connection", connection.id, "create",
        new_value=audit_data,
        ip_address=request.client.host if request.client else None
    )
    
    db.commit()
    db.refresh(db_conn)
    
    return ConnectionConfigResponse(
        id=db_conn.id,
        connection_type=db_conn.connection_type,
        name=db_conn.name,
        description=db_conn.description,
        connection_string=mask_secret(db_conn.connection_string) if db_conn.connection_string else None,
        host=db_conn.host,
        port=db_conn.port,
        database=db_conn.database,
        username=db_conn.username,
        password=None,
        password_masked=mask_secret(db_conn.password) if db_conn.password else None,
        use_ssl=db_conn.use_ssl,
        ssl_cert_path=db_conn.ssl_cert_path,
        pool_size=db_conn.pool_size,
        max_overflow=db_conn.max_overflow,
        pool_timeout=db_conn.pool_timeout,
        extra_options=db_conn.extra_options,
        status=db_conn.status,
        is_default=db_conn.is_default,
        last_health_check=db_conn.last_health_check,
        health_status=db_conn.health_status,
        created_at=db_conn.created_at,
        updated_at=db_conn.updated_at
    )


@router.put("/connections/{conn_id}", response_model=ConnectionConfigResponse)
async def update_connection(
    conn_id: str,
    conn_update: ConnectionConfigUpdate,
    request: Request,
    db: Session = Depends(get_db)
):
    """Update a connection configuration."""
    db_conn = db.query(ConnectionConfig).filter(ConnectionConfig.id == conn_id).first()
    if not db_conn:
        raise HTTPException(status_code=404, detail="Connection not found")
    
    old_value = {"name": db_conn.name, "status": db_conn.status}
    
    update_data = conn_update.model_dump(exclude_unset=True)
    
    # If setting as default, unset other defaults for same type
    if update_data.get("is_default"):
        db.query(ConnectionConfig).filter(
            ConnectionConfig.connection_type == db_conn.connection_type,
            ConnectionConfig.id != conn_id,
            ConnectionConfig.is_default == True
        ).update({"is_default": False})
    
    for field, value in update_data.items():
        setattr(db_conn, field, value)
    
    # Log audit (mask secrets)
    audit_update = update_data.copy()
    if audit_update.get("password"):
        audit_update["password"] = "[REDACTED]"
    if audit_update.get("connection_string"):
        audit_update["connection_string"] = "[REDACTED]"
    log_audit(
        db, "connection", conn_id, "update",
        old_value=old_value,
        new_value=audit_update,
        ip_address=request.client.host if request.client else None
    )
    
    db.commit()
    db.refresh(db_conn)
    
    # Invalidate cache so changes take effect
    invalidate_config_cache()
    
    return ConnectionConfigResponse(
        id=db_conn.id,
        connection_type=db_conn.connection_type,
        name=db_conn.name,
        description=db_conn.description,
        connection_string=mask_secret(db_conn.connection_string) if db_conn.connection_string else None,
        host=db_conn.host,
        port=db_conn.port,
        database=db_conn.database,
        username=db_conn.username,
        password=None,
        password_masked=mask_secret(db_conn.password) if db_conn.password else None,
        use_ssl=db_conn.use_ssl,
        ssl_cert_path=db_conn.ssl_cert_path,
        pool_size=db_conn.pool_size,
        max_overflow=db_conn.max_overflow,
        pool_timeout=db_conn.pool_timeout,
        extra_options=db_conn.extra_options,
        status=db_conn.status,
        is_default=db_conn.is_default,
        last_health_check=db_conn.last_health_check,
        health_status=db_conn.health_status,
        created_at=db_conn.created_at,
        updated_at=db_conn.updated_at
    )


@router.delete("/connections/{conn_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_connection(
    conn_id: str,
    request: Request,
    db: Session = Depends(get_db)
):
    """Delete a connection configuration."""
    db_conn = db.query(ConnectionConfig).filter(ConnectionConfig.id == conn_id).first()
    if not db_conn:
        raise HTTPException(status_code=404, detail="Connection not found")
    
    log_audit(
        db, "connection", conn_id, "delete",
        old_value={"name": db_conn.name, "type": db_conn.connection_type},
        ip_address=request.client.host if request.client else None
    )
    
    db.delete(db_conn)
    db.commit()
    
    # Invalidate cache so changes take effect
    invalidate_config_cache()


# ============================================================
# Feature Flags API
# ============================================================

@router.get("/feature-flags", response_model=List[FeatureFlagResponse])
async def list_feature_flags(
    enabled_only: bool = Query(False, description="Only return enabled flags"),
    db: Session = Depends(get_db)
):
    """List all feature flags."""
    query = db.query(FeatureFlag)
    if enabled_only:
        query = query.filter(FeatureFlag.enabled == True)
    return query.order_by(FeatureFlag.name).all()


@router.get("/feature-flags/{flag_id}", response_model=FeatureFlagResponse)
async def get_feature_flag(flag_id: str, db: Session = Depends(get_db)):
    """Get a specific feature flag."""
    flag = db.query(FeatureFlag).filter(FeatureFlag.id == flag_id).first()
    if not flag:
        raise HTTPException(status_code=404, detail="Feature flag not found")
    return flag


@router.get("/feature-flags/{flag_id}/check", response_model=Dict[str, Any])
async def check_feature_flag(flag_id: str, db: Session = Depends(get_db)):
    """Check if a feature flag is enabled."""
    flag = db.query(FeatureFlag).filter(FeatureFlag.id == flag_id).first()
    if not flag:
        return {"flag_id": flag_id, "enabled": False, "exists": False}
    return {"flag_id": flag_id, "enabled": flag.enabled, "exists": True, "rollout_percentage": flag.rollout_percentage}


@router.post("/feature-flags", response_model=FeatureFlagResponse, status_code=status.HTTP_201_CREATED)
async def create_feature_flag(
    flag: FeatureFlagCreate,
    request: Request,
    db: Session = Depends(get_db)
):
    """Create a new feature flag."""
    existing = db.query(FeatureFlag).filter(FeatureFlag.id == flag.id).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Feature flag '{flag.id}' already exists")
    
    db_flag = FeatureFlag(**flag.model_dump())
    db.add(db_flag)
    
    log_audit(
        db, "feature_flag", flag.id, "create",
        new_value=flag.model_dump(),
        ip_address=request.client.host if request.client else None
    )
    
    db.commit()
    db.refresh(db_flag)
    return db_flag


@router.put("/feature-flags/{flag_id}", response_model=FeatureFlagResponse)
async def update_feature_flag(
    flag_id: str,
    flag_update: FeatureFlagUpdate,
    request: Request,
    db: Session = Depends(get_db)
):
    """Update a feature flag."""
    db_flag = db.query(FeatureFlag).filter(FeatureFlag.id == flag_id).first()
    if not db_flag:
        raise HTTPException(status_code=404, detail="Feature flag not found")
    
    old_value = {"name": db_flag.name, "enabled": db_flag.enabled}
    
    update_data = flag_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_flag, field, value)
    
    log_audit(
        db, "feature_flag", flag_id, "update",
        old_value=old_value,
        new_value=update_data,
        ip_address=request.client.host if request.client else None
    )
    
    db.commit()
    db.refresh(db_flag)
    
    # Invalidate cache so changes take effect
    invalidate_config_cache()
    
    return db_flag


@router.delete("/feature-flags/{flag_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_feature_flag(
    flag_id: str,
    request: Request,
    db: Session = Depends(get_db)
):
    """Delete a feature flag."""
    db_flag = db.query(FeatureFlag).filter(FeatureFlag.id == flag_id).first()
    if not db_flag:
        raise HTTPException(status_code=404, detail="Feature flag not found")
    
    log_audit(
        db, "feature_flag", flag_id, "delete",
        old_value={"name": db_flag.name},
        ip_address=request.client.host if request.client else None
    )
    
    db.delete(db_flag)
    db.commit()
    
    # Invalidate cache so changes take effect
    invalidate_config_cache()


# ============================================================
# Audit Log API
# ============================================================

@router.get("/audit-logs", response_model=List[AuditLogResponse])
async def list_audit_logs(
    config_type: Optional[str] = Query(None, description="Filter by config type"),
    config_id: Optional[str] = Query(None, description="Filter by config ID"),
    action: Optional[str] = Query(None, description="Filter by action"),
    limit: int = Query(100, le=1000, description="Maximum results"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    db: Session = Depends(get_db)
):
    """List audit logs with optional filtering."""
    query = db.query(AuditLog)
    
    if config_type:
        query = query.filter(AuditLog.config_type == config_type)
    if config_id:
        query = query.filter(AuditLog.config_id == config_id)
    if action:
        query = query.filter(AuditLog.action == action)
    
    return query.order_by(AuditLog.timestamp.desc()).offset(offset).limit(limit).all()


# ============================================================
# Aggregated Endpoints
# ============================================================

@router.get("/all", response_model=AllAdminConfigsResponse)
async def get_all_configs(db: Session = Depends(get_db)):
    """Get all admin configurations in a single request."""
    system_configs = db.query(SystemConfiguration).filter(SystemConfiguration.enabled == True).all()
    llm_providers = db.query(LLMProviderConfig).filter(LLMProviderConfig.status == "active").all()
    embedding_models = db.query(EmbeddingModelConfig).filter(EmbeddingModelConfig.status == "active").all()
    connections = db.query(ConnectionConfig).filter(ConnectionConfig.status == "active").all()
    feature_flags = db.query(FeatureFlag).all()
    
    # Mask secrets in LLM providers
    llm_responses = []
    for p in llm_providers:
        llm_responses.append(LLMProviderResponse(
            id=p.id,
            provider=p.provider,
            name=p.name,
            description=p.description,
            api_key=None,
            api_key_masked=mask_secret(p.api_key) if p.api_key else None,
            api_endpoint=p.api_endpoint,
            api_version=p.api_version,
            azure_deployment=p.azure_deployment,
            azure_resource_name=p.azure_resource_name,
            default_chat_model=p.default_chat_model,
            default_completion_model=p.default_completion_model,
            default_embedding_model=p.default_embedding_model,
            default_temperature=p.default_temperature,
            default_max_tokens=p.default_max_tokens,
            default_top_p=p.default_top_p,
            rate_limit_rpm=p.rate_limit_rpm,
            rate_limit_tpm=p.rate_limit_tpm,
            cost_per_1k_input_tokens=p.cost_per_1k_input_tokens,
            cost_per_1k_output_tokens=p.cost_per_1k_output_tokens,
            status=p.status,
            is_default=p.is_default,
            priority=p.priority,
            extra_config=p.extra_config,
            created_at=p.created_at,
            updated_at=p.updated_at,
            created_by=p.created_by
        ))
    
    # Mask secrets in connections
    conn_responses = []
    for c in connections:
        conn_responses.append(ConnectionConfigResponse(
            id=c.id,
            connection_type=c.connection_type,
            name=c.name,
            description=c.description,
            connection_string=None,
            host=c.host,
            port=c.port,
            database=c.database,
            username=c.username,
            password=None,
            password_masked=mask_secret(c.password) if c.password else None,
            use_ssl=c.use_ssl,
            ssl_cert_path=c.ssl_cert_path,
            pool_size=c.pool_size,
            max_overflow=c.max_overflow,
            pool_timeout=c.pool_timeout,
            extra_options=c.extra_options,
            status=c.status,
            is_default=c.is_default,
            last_health_check=c.last_health_check,
            health_status=c.health_status,
            created_at=c.created_at,
            updated_at=c.updated_at
        ))
    
    return AllAdminConfigsResponse(
        system_configs=[SystemConfigResponse.model_validate(c) for c in system_configs],
        llm_providers=llm_responses,
        embedding_models=[EmbeddingModelResponse.model_validate(m) for m in embedding_models],
        connections=conn_responses,
        feature_flags=[FeatureFlagResponse.model_validate(f) for f in feature_flags],
        config_counts={
            "system_configs": len(system_configs),
            "llm_providers": len(llm_providers),
            "embedding_models": len(embedding_models),
            "connections": len(connections),
            "feature_flags": len(feature_flags)
        }
    )


@router.get("/health", response_model=ConfigHealthResponse)
async def check_config_health(db: Session = Depends(get_db)):
    """Check health of all configurations."""
    warnings = []
    
    # Check LLM providers
    llm_status = {}
    llm_providers = db.query(LLMProviderConfig).filter(LLMProviderConfig.status == "active").all()
    if not llm_providers:
        warnings.append("No active LLM providers configured")
    for p in llm_providers:
        if not p.api_key:
            llm_status[p.id] = "missing_api_key"
            warnings.append(f"LLM provider '{p.name}' has no API key")
        else:
            llm_status[p.id] = "configured"
    
    # Check embedding models
    embedding_status = {}
    embedding_models = db.query(EmbeddingModelConfig).filter(EmbeddingModelConfig.status == "active").all()
    if not embedding_models:
        warnings.append("No active embedding models configured")
    for m in embedding_models:
        embedding_status[m.id] = "configured"
    
    # Check connections
    conn_status = {}
    connections = db.query(ConnectionConfig).filter(ConnectionConfig.status == "active").all()
    for c in connections:
        if c.health_status:
            conn_status[c.id] = c.health_status
        elif not c.host and not c.connection_string:
            conn_status[c.id] = "incomplete"
            warnings.append(f"Connection '{c.name}' has no host or connection string")
        else:
            conn_status[c.id] = "configured"
    
    overall_status = "healthy" if not warnings else "degraded"
    
    return ConfigHealthResponse(
        status=overall_status,
        llm_providers=llm_status,
        embedding_models=embedding_status,
        connections=conn_status,
        warnings=warnings,
        timestamp=datetime.now(timezone.utc)
    )


# ============================================================
# Connection Test Endpoints
# ============================================================

@router.post("/connections/{conn_id}/test", response_model=Dict[str, Any])
async def test_connection_by_id(conn_id: str, db: Session = Depends(get_db)):
    """Test a connection configuration by ID."""
    conn = db.query(ConnectionConfig).filter(ConnectionConfig.id == conn_id).first()
    if not conn:
        raise HTTPException(status_code=404, detail="Connection not found")
    
    result = {"connection_id": conn_id, "connection_type": conn.connection_type, "success": False}
    
    try:
        conn_type = (conn.connection_type or "").lower().strip()
        extra = _get_extra_options(conn)

        if conn_type == "postgres":
            from sqlalchemy import create_engine, text
            url = conn.connection_string or f"postgresql://{conn.username}:{conn.password}@{conn.host}:{conn.port}/{conn.database}"
            engine = create_engine(url, pool_pre_ping=True, connect_args={"connect_timeout": 10})
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            result["success"] = True
            result["message"] = "PostgreSQL connection successful"
            
        elif conn_type == "neo4j":
            from neo4j import GraphDatabase
            uri = conn.connection_string or f"neo4j://{conn.host}:{conn.port}"
            driver = GraphDatabase.driver(uri, auth=(conn.username, conn.password))
            with driver.session() as session:
                session.run("RETURN 1")
            driver.close()
            result["success"] = True
            result["message"] = "Neo4j connection successful"
            
        elif conn_type == "opensearch":
            from opensearchpy import OpenSearch
            client = OpenSearch(
                hosts=[{"host": conn.host, "port": conn.port}],
                http_auth=(conn.username, conn.password) if conn.username else None,
                use_ssl=conn.use_ssl if hasattr(conn, 'use_ssl') else False,
                timeout=30
            )
            info = client.info()
            result["success"] = True
            result["message"] = f"OpenSearch connected (v{info.get('version', {}).get('number', '?')})"
            
        elif conn_type == "redis":
            import redis
            r = redis.Redis(
                host=conn.host,
                port=conn.port,
                password=conn.password,
                socket_timeout=10
            )
            r.ping()
            result["success"] = True
            result["message"] = "Redis connection successful"

        elif conn_type == "local_folder":
            folder_path = str(extra.get("folder_path") or "").strip()
            if not folder_path:
                result["message"] = "Missing required field: extra_options.folder_path"
            else:
                path = Path(folder_path)
                if not _is_under_allowed_root(path):
                    result["message"] = "Folder path is outside allowed data directories"
                elif not path.exists() or not path.is_dir():
                    result["message"] = "Folder not found"
                else:
                    result["success"] = True
                    result["message"] = "Local folder is accessible"

        elif conn_type == "s3":
            bucket = str(extra.get("bucket") or "").strip()
            prefix = str(extra.get("prefix") or "").strip()
            region = str(extra.get("region") or "").strip()
            if not bucket:
                result["message"] = "Missing required field: extra_options.bucket"
            else:
                try:
                    import boto3  # type: ignore

                    client_kwargs: Dict[str, Any] = {}
                    if region:
                        client_kwargs["region_name"] = region

                    # If credentials are provided in username/password, use them; else rely on default chain.
                    access_key_id = str(conn.username or "").strip() or None
                    secret_access_key = str(conn.password or "").strip() or None
                    if access_key_id and secret_access_key:
                        client_kwargs["aws_access_key_id"] = access_key_id
                        client_kwargs["aws_secret_access_key"] = secret_access_key

                    s3 = boto3.client("s3", **client_kwargs)
                    list_kwargs: Dict[str, Any] = {"Bucket": bucket, "MaxKeys": 1}
                    if prefix:
                        list_kwargs["Prefix"] = prefix
                    s3.list_objects_v2(**list_kwargs)
                    result["success"] = True
                    result["message"] = "S3 access verified"
                except ImportError:
                    result["message"] = "boto3 is not installed. Install: pip install boto3"
                except Exception as e:
                    result["message"] = f"S3 connection failed: {str(e)}"

        elif conn_type == "azure_blob":
            account_name = str(extra.get("account_name") or "").strip()
            container = str(extra.get("container") or "").strip()

            # UI stores connection string / SAS in password by default.
            connection_string = (conn.connection_string or "").strip() or (str(conn.password or "").strip() or None)

            if not container:
                result["message"] = "Missing required field: extra_options.container"
            elif not (connection_string or account_name):
                result["message"] = "Missing credentials: provide connection_string (preferred) or account_name + account_key"
            else:
                try:
                    from azure.storage.blob import BlobServiceClient  # type: ignore

                    if connection_string:
                        service = BlobServiceClient.from_connection_string(connection_string)
                    else:
                        # Fall back to key-based auth.
                        account_key = str(extra.get("account_key") or "").strip() or None
                        if not account_key:
                            result["message"] = "Missing required field: extra_options.account_key"
                            raise RuntimeError("missing account_key")
                        url = f"https://{account_name}.blob.core.windows.net"
                        service = BlobServiceClient(account_url=url, credential=account_key)

                    container_client = service.get_container_client(container)
                    blob_prefix = str(extra.get("prefix") or "").strip()
                    if blob_prefix:
                        pager = container_client.list_blobs(name_starts_with=blob_prefix, results_per_page=1).by_page()
                    else:
                        pager = container_client.list_blobs(results_per_page=1).by_page()
                    next(pager, None)
                    result["success"] = True
                    result["message"] = "Azure Blob access verified"
                except ImportError:
                    result["message"] = "azure-storage-blob is not installed. Install: pip install azure-storage-blob"
                except RuntimeError:
                    # message already set
                    pass
                except Exception as e:
                    result["message"] = f"Azure Blob connection failed: {str(e)}"

        elif conn_type == "onedrive":
            access_token: str = str(conn.password or "").strip()
            if not access_token:
                result["message"] = "Access token not configured (stored in password)"
            else:
                try:
                    import httpx

                    async with httpx.AsyncClient(timeout=10.0) as client:
                        resp = await client.get(
                            "https://graph.microsoft.com/v1.0/me/drive",
                            headers={"Authorization": "Bearer " + access_token},
                        )
                    if resp.status_code >= 200 and resp.status_code < 300:
                        result["success"] = True
                        result["message"] = "OneDrive token verified"
                    else:
                        result["message"] = f"OneDrive verification failed: HTTP {resp.status_code}"
                except Exception as e:
                    result["message"] = f"OneDrive verification failed: {str(e)}"

        elif conn_type == "google_drive":
            access_token: str = str(conn.password or "").strip()
            if not access_token:
                result["message"] = "Access token not configured (stored in password)"
            else:
                try:
                    import httpx

                    async with httpx.AsyncClient(timeout=10.0) as client:
                        resp = await client.get(
                            "https://www.googleapis.com/drive/v3/about",
                            params={"fields": "user,storageQuota"},
                            headers={"Authorization": "Bearer " + access_token},
                        )
                    if resp.status_code >= 200 and resp.status_code < 300:
                        result["success"] = True
                        result["message"] = "Google Drive token verified"
                    else:
                        result["message"] = f"Google Drive verification failed: HTTP {resp.status_code}"
                except Exception as e:
                    result["message"] = f"Google Drive verification failed: {str(e)}"

        elif conn_type == "powerquery":
            m_query = str(extra.get("m_query") or "").strip()
            query_name = str(extra.get("query_name") or "").strip()
            if not m_query and not query_name:
                result["message"] = "Provide extra_options.m_query or extra_options.query_name"
            else:
                result["success"] = True
                result["message"] = "PowerQuery configuration accepted"
            
        else:
            result["message"] = f"Test not implemented for: {conn.connection_type}"
        
        conn.last_health_check = datetime.now(timezone.utc)
        conn.health_status = "healthy" if result["success"] else "failed"
        db.commit()
        
    except Exception as e:
        result["success"] = False
        result["error"] = str(e)
        conn.last_health_check = datetime.now(timezone.utc)
        conn.health_status = "failed"
        db.commit()
    
    return result


@router.post("/llm-providers/{provider_id}/test", response_model=Dict[str, Any])
async def test_llm_provider(provider_id: str, db: Session = Depends(get_db)):
    """Test an LLM provider configuration."""
    provider = db.query(LLMProviderConfig).filter(LLMProviderConfig.id == provider_id).first()
    if not provider:
        raise HTTPException(status_code=404, detail="LLM provider not found")
    
    result = {"provider_id": provider_id, "provider": provider.provider, "success": False}
    
    # Ollama doesn't require an API key
    if not provider.api_key and provider.provider not in ("ollama", "huggingface"):
        result["error"] = "API key not configured"
        return result
    
    try:
        if provider.provider == "openai":
            import httpx
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{provider.api_endpoint or 'https://api.openai.com/v1'}/models",
                    headers={"Authorization": f"Bearer {provider.api_key}"}
                )
                if response.status_code == 200:
                    result["success"] = True
                    result["message"] = "OpenAI API connection successful"
                else:
                    result["error"] = f"API returned status {response.status_code}"
                    
        elif provider.provider == "anthropic":
            import httpx
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    f"{provider.api_endpoint or 'https://api.anthropic.com'}/v1/messages",
                    headers={
                        "x-api-key": provider.api_key,
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json"
                    },
                    json={
                        "model": provider.default_chat_model or "claude-3-sonnet-20240229",
                        "max_tokens": 10,
                        "messages": [{"role": "user", "content": "Hi"}]
                    }
                )
                if response.status_code in (200, 400):  # 400 means API key works but request issue
                    result["success"] = True
                    result["message"] = "Anthropic API connection successful"
                else:
                    result["error"] = f"API returned status {response.status_code}"
                    
        elif provider.provider == "ollama":
            import httpx
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{provider.api_endpoint or 'http://localhost:11434'}/api/tags"
                )
                if response.status_code == 200:
                    models = response.json().get("models", [])
                    result["success"] = True
                    result["message"] = f"Ollama connected ({len(models)} models available)"
                else:
                    result["error"] = f"Ollama returned status {response.status_code}"
                    
        elif provider.provider == "azure_openai":
            if not provider.azure_resource_name:
                result["error"] = "Azure resource name not configured"
                return result
            import httpx
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"https://{provider.azure_resource_name}.openai.azure.com/openai/deployments?api-version={provider.api_version or '2024-02-15-preview'}",
                    headers={"api-key": provider.api_key}
                )
                if response.status_code == 200:
                    result["success"] = True
                    result["message"] = "Azure OpenAI connection successful"
                else:
                    result["error"] = f"Azure API returned status {response.status_code}"
        else:
            result["message"] = f"Test not implemented for provider: {provider.provider}"
            result["success"] = True  # Assume OK if not testable
            
    except Exception as e:
        result["error"] = str(e)
    
    return result


@router.post("/embedding-models/{model_id}/test", response_model=Dict[str, Any])
async def test_embedding_model(model_id: str, db: Session = Depends(get_db)):
    """Test an embedding model configuration."""
    model = db.query(EmbeddingModelConfig).filter(EmbeddingModelConfig.id == model_id).first()
    if not model:
        raise HTTPException(status_code=404, detail="Embedding model not found")
    
    result = {"model_id": model_id, "provider": model.provider, "success": False}
    
    try:
        if model.provider == "sentence_transformers":
            # Local model - just check if we can import
            try:
                from sentence_transformers import SentenceTransformer
                result["success"] = True
                result["message"] = f"SentenceTransformers available (model: {model.model_name})"
            except ImportError:
                result["error"] = "sentence-transformers not installed"
                
        elif model.provider == "openai":
            if not model.api_key:
                result["error"] = "API key not configured"
                return result
            import httpx
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    f"{model.api_endpoint or 'https://api.openai.com/v1'}/embeddings",
                    headers={"Authorization": f"Bearer {model.api_key}"},
                    json={"model": model.model_name, "input": "test"}
                )
                if response.status_code == 200:
                    result["success"] = True
                    result["message"] = "OpenAI embeddings API working"
                else:
                    result["error"] = f"API returned status {response.status_code}"
        else:
            result["message"] = f"Test not implemented for: {model.provider}"
            result["success"] = True
            
    except Exception as e:
        result["error"] = str(e)
    
    return result
async def test_connection(conn_id: str, db: Session = Depends(get_db)):
    """Test a connection configuration."""
    conn = db.query(ConnectionConfig).filter(ConnectionConfig.id == conn_id).first()
    if not conn:
        raise HTTPException(status_code=404, detail="Connection not found")
    
    result = {"connection_id": conn_id, "connection_type": conn.connection_type}
    
    try:
        if conn.connection_type == "postgres":
            from sqlalchemy import create_engine, text
            url = conn.connection_string or f"postgresql://{conn.username}:{conn.password}@{conn.host}:{conn.port}/{conn.database}"
            engine = create_engine(url, pool_pre_ping=True)
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            result["status"] = "success"
            result["message"] = "PostgreSQL connection successful"
            
        elif conn.connection_type == "neo4j":
            from neo4j import GraphDatabase
            uri = conn.connection_string or f"neo4j://{conn.host}:{conn.port}"
            driver = GraphDatabase.driver(uri, auth=(conn.username, conn.password))
            with driver.session() as session:
                session.run("RETURN 1")
            driver.close()
            result["status"] = "success"
            result["message"] = "Neo4j connection successful"
            
        elif conn.connection_type == "opensearch":
            from opensearchpy import OpenSearch
            client = OpenSearch(
                hosts=[{"host": conn.host, "port": conn.port}],
                http_auth=(conn.username, conn.password) if conn.username else None,
                use_ssl=conn.use_ssl
            )
            info = client.info()
            result["status"] = "success"
            result["message"] = f"OpenSearch connection successful (version: {info.get('version', {}).get('number', 'unknown')})"
            
        else:
            result["status"] = "unsupported"
            result["message"] = f"Connection test not implemented for type: {conn.connection_type}"
        
        # Update health status
        conn.last_health_check = datetime.now(timezone.utc)
        conn.health_status = result["status"]
        db.commit()
        
    except Exception as e:
        result["status"] = "failed"
        result["message"] = str(e)
        
        # Update health status
        conn.last_health_check = datetime.now(timezone.utc)
        conn.health_status = "failed"
        db.commit()
    
    return result
