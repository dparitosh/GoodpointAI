"""
Admin Configuration Router

API endpoints for managing LLM providers, embedding models,
API keys, and all system configurations centrally.
"""

# pylint: disable=broad-exception-caught

import logging
import re
import subprocess
import uuid
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, Query, status, Request
from sqlalchemy.orm import Session

from core.db_session import get_db
from models.error_models import (
    ResourceNotFoundError,
    ResourceAlreadyExistsError,
    InvalidRequestError,
    ConflictError,
    DependencyError,
)
from models.admin_config_models import (
    # ORM Models
    SystemConfiguration,
    LLMProviderConfig,
    EmbeddingModelConfig,
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


def _slugify(value: str, max_len: int) -> str:
    """Conservative slugify for IDs (letters/numbers/underscore).

    Keeps IDs stable-ish across environments while staying within DB column limits.
    """
    raw = (value or "").strip().lower()
    raw = re.sub(r"[^a-z0-9]+", "_", raw)
    raw = raw.strip("_")
    if not raw:
        return ""
    return raw[:max_len]


def _generate_config_id(prefix: str, max_len: int = 50) -> str:
    """Generate a short unique ID that fits within the configured DB column size."""
    token = uuid.uuid4().hex[:12]
    # Leave room for '_' + token
    base_max = max(1, max_len - (len(token) + 1))
    base = _slugify(prefix, base_max) or "cfg"
    return f"{base}_{token}"[:max_len]


def _workspace_root() -> Path:
    # python_backend/routers -> python_backend -> agentic-restored
    return Path(__file__).resolve().parents[2]


def _allowed_local_roots() -> List[Path]:
    root = _workspace_root()
    candidates = [root / "data", root / "python_backend" / "data", root.parent / "data"]

    # Admin/server-controlled allowlist (stored encrypted in DB).
    # This matches the logic used by /api/data-sources/* sampling.
    try:
        from core.config_store import get_encrypted_config_payload

        sys_cfg = get_encrypted_config_payload("system_configuration")
        allowed_list: list[object] = []
        if isinstance(sys_cfg, dict):
            roots_val = sys_cfg.get("allowed_local_roots")
            if isinstance(roots_val, list):
                allowed_list = roots_val
            else:
                fs_cfg = sys_cfg.get("filesystem")
                if isinstance(fs_cfg, dict):
                    roots_val2 = fs_cfg.get("allowed_local_roots")
                    if isinstance(roots_val2, list):
                        allowed_list = roots_val2

        for item in allowed_list:
            p = str(item).strip().strip('"')
            if not p:
                continue
            try:
                candidates.append(Path(p))
            except Exception:
                continue
    except Exception:
        # Non-fatal: fall back to env + repo-local defaults.
        pass

    # Environment allowlist (Windows-friendly delimiter).
    import os

    extra_raw = (os.getenv("GRAPH_TRACE_ALLOWED_LOCAL_ROOTS") or "").strip()
    if extra_raw:
        for item in extra_raw.split(";"):
            p = item.strip().strip('"')
            if not p:
                continue
            try:
                candidates.append(Path(p))
            except Exception:
                continue

    return [p.resolve() for p in candidates if p.exists()]


def _is_under_allowed_root(path: Path) -> bool:
    try:
        resolved = path.resolve()
    except OSError:
        return False
    for root in _allowed_local_roots():
        try:
            resolved.relative_to(root)
            return True
        except ValueError:
            continue
    return False


def _get_extra_options(conn: ConnectionConfig) -> Dict[str, Any]:
    return conn.extra_options if isinstance(conn.extra_options, dict) else {}


_PUBLIC_CONNECTION_STRING_TYPES = {"api", "rest_api", "webapi", "openapi", "odata"}


def _connection_string_for_response(conn: ConnectionConfig) -> Optional[str]:
    """Return connection_string for API response.

    For API-like integrations, connection_string is typically a base URL and should
    be viewable/editable. For DB-like connections, connection_string may include
    credentials, so we keep masking.
    """
    raw = getattr(conn, "connection_string", None)
    if not raw:
        return None
    ctype = (getattr(conn, "connection_type", "") or "").lower().strip()
    if ctype in _PUBLIC_CONNECTION_STRING_TYPES:
        return raw
    return mask_secret(raw)


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


@router.get("/meta", response_model=Dict[str, Any])
async def get_admin_config_meta() -> Dict[str, Any]:
    """Return metadata used to render admin config UIs dynamically.

    This endpoint is intentionally value-free (no secrets, no configured instances).
    It provides JSON schema for create/update payloads and option lists for enums.
    """
    return {
        "schemas": {
            "llm_provider": {
                "create": LLMProviderCreate.model_json_schema(),
                "update": LLMProviderUpdate.model_json_schema(),
            },
            "embedding_model": {
                "create": EmbeddingModelCreate.model_json_schema(),
                "update": EmbeddingModelUpdate.model_json_schema(),
            },
            "connection": {
                "create": ConnectionConfigCreate.model_json_schema(),
                "update": ConnectionConfigUpdate.model_json_schema(),
            },
            "feature_flag": {
                "create": FeatureFlagCreate.model_json_schema(),
                "update": FeatureFlagUpdate.model_json_schema(),
            },
            "system_setting": {
                "create": SystemConfigCreate.model_json_schema(),
                "update": SystemConfigUpdate.model_json_schema(),
            },
        },
        "enums": {
            "llm_providers": [p.value for p in LLMProvider],
            "embedding_providers": [p.value for p in EmbeddingProvider],
            "config_categories": [c.value for c in ConfigCategory],
        },
        "ui_hints": {
            "llm_provider": {"secret_fields": ["api_key"], "id_required": False},
            "embedding_model": {"secret_fields": ["custom_api_key"], "id_required": False},
            "connection": {"secret_fields": ["password", "connection_string"], "id_required": False},
            "feature_flag": {"secret_fields": [], "id_required": False},
            "system_setting": {"secret_fields": ["value"], "id_required": False},
        },
    }


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
    result: List[SystemConfigResponse] = []
    for config in configs:
        config_dict: Dict[str, Any] = {
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
        # model_validate keeps static type-checkers happy with dynamic dicts.
        result.append(SystemConfigResponse.model_validate(config_dict))
    
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
        raise ResourceNotFoundError("SystemConfiguration", str(config_id))
    return config


@router.get("/system/by-key/{category}/{key}", response_model=SystemConfigResponse)
async def get_system_config_by_key(category: str, key: str, db: Session = Depends(get_db)):
    """Get a system configuration by category and key."""
    config = db.query(SystemConfiguration).filter(
        SystemConfiguration.category == category,
        SystemConfiguration.key == key
    ).first()
    if not config:
        raise ResourceNotFoundError("SystemConfiguration", f"{category}.{key}")
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
        raise ResourceAlreadyExistsError(
            "SystemConfiguration",
            f"{config.category}.{config.key}"
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
        raise ResourceNotFoundError("LLMProvider", provider_id)
    
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
    provider_id = (provider.id or "").strip() or _generate_config_id(f"llm_{provider.provider}")

    existing = db.query(LLMProviderConfig).filter(LLMProviderConfig.id == provider_id).first()
    if existing:
        raise ResourceAlreadyExistsError("LLMProvider", provider_id)
    
    # If setting as default, unset other defaults
    if provider.is_default:
        db.query(LLMProviderConfig).filter(
            LLMProviderConfig.provider == provider.provider,
            LLMProviderConfig.is_default == True
        ).update({"is_default": False})
    
    payload = provider.model_dump()
    payload["id"] = provider_id
    db_provider = LLMProviderConfig(**payload)
    db.add(db_provider)
    
    # Log audit (mask API key)
    audit_data = payload.copy()
    if audit_data.get("api_key"):
        audit_data["api_key"] = "[REDACTED]"
    log_audit(
        db, "llm_provider", provider_id, "create",
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
    model_id = (model.id or "").strip() or _generate_config_id(f"emb_{model.provider}")

    existing = db.query(EmbeddingModelConfig).filter(EmbeddingModelConfig.id == model_id).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Embedding model '{model_id}' already exists")
    
    # If setting as default, unset other defaults
    if model.is_default:
        db.query(EmbeddingModelConfig).filter(EmbeddingModelConfig.is_default == True).update({"is_default": False})
    
    payload = model.model_dump()
    payload["id"] = model_id
    db_model = EmbeddingModelConfig(**payload)
    db.add(db_model)
    
    log_audit(
        db, "embedding_model", model_id, "create",
        new_value=payload,
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
            connection_string=_connection_string_for_response(conn),
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
        connection_string=_connection_string_for_response(conn),
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
    conn_id = (connection.id or "").strip() or _generate_config_id(f"conn_{connection.connection_type}")

    existing = db.query(ConnectionConfig).filter(ConnectionConfig.id == conn_id).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Connection '{conn_id}' already exists")
    
    # If setting as default, unset other defaults for same type
    if connection.is_default:
        db.query(ConnectionConfig).filter(
            ConnectionConfig.connection_type == connection.connection_type,
            ConnectionConfig.is_default == True
        ).update({"is_default": False})
    
    payload = connection.model_dump()
    payload["id"] = conn_id
    db_conn = ConnectionConfig(**payload)
    db.add(db_conn)
    
    # Log audit (mask secrets)
    audit_data = payload.copy()
    if audit_data.get("password"):
        audit_data["password"] = "[REDACTED]"
    if audit_data.get("connection_string"):
        audit_data["connection_string"] = "[REDACTED]"
    log_audit(
        db, "connection", conn_id, "create",
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
        connection_string=_connection_string_for_response(db_conn),
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
    # Secret-safe update: allow UI to omit/blank out without overwriting stored secret.
    if "password" in update_data:
        pw = update_data.get("password")
        if pw is None or str(pw).strip() == "" or str(pw).strip() == "********":
            update_data.pop("password", None)
    
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
        connection_string=_connection_string_for_response(db_conn),
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
    # Feature-flag IDs are often referenced in code, so prefer a stable slug from the name.
    base_id = (flag.id or "").strip() or _slugify(flag.name, 100)
    if not base_id:
        base_id = _generate_config_id("flag", max_len=100)
    flag_id = base_id

    existing = db.query(FeatureFlag).filter(FeatureFlag.id == flag_id).first()
    if existing:
        # Avoid collision by appending a suffix.
        flag_id = _generate_config_id(base_id, max_len=100)
        existing2 = db.query(FeatureFlag).filter(FeatureFlag.id == flag_id).first()
        if existing2:
            raise HTTPException(status_code=400, detail=f"Feature flag '{base_id}' already exists")
    
    payload = flag.model_dump()
    payload["id"] = flag_id
    db_flag = FeatureFlag(**payload)
    db.add(db_flag)
    
    log_audit(
        db, "feature_flag", flag_id, "create",
        new_value=payload,
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
        ct = (getattr(c, "connection_type", "") or "").lower().strip()
        if c.health_status:
            conn_status[c.id] = c.health_status
        elif ct == "soda_external":
            extra = _get_extra_options(c)
            python_path = str(extra.get("python_path") or extra.get("python") or "").strip()
            if python_path:
                conn_status[c.id] = "configured"
            else:
                conn_status[c.id] = "incomplete"
                warnings.append(f"Connection '{c.name}' is missing extra_options.python_path")
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
            engine = create_engine(url, pool_pre_ping=True, connect_args={"connect_timeout": 5})
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
            from services.opensearch_service import OpenSearchService

            # Prefer connection_string when present, else build from host/port/ssl.
            cfg = {
                "url": (conn.connection_string or "").strip() or None,
                "host": conn.host,
                "port": conn.port,
                "ssl_enabled": bool(getattr(conn, "use_ssl", False)),
                "username": conn.username,
                "password": conn.password,
                "verify_certs": True,
                "timeout_s": 5,
            }
            os_service = OpenSearchService(config=cfg)
            info = os_service.info()
            result["success"] = True
            result["message"] = f"OpenSearch connected (v{info.get('version', {}).get('number', '?')})"
            
        elif conn_type == "redis":
            try:
                import redis  # type: ignore

                r = redis.Redis(
                    host=conn.host,
                    port=conn.port,
                    password=conn.password,
                    socket_timeout=5,
                )
                r.ping()
                result["success"] = True
                result["message"] = "Redis connection successful"
            except ImportError:
                result["message"] = "redis is not installed. Install: pip install redis"

        elif conn_type == "soda_external":
            python_path = str(extra.get("python_path") or extra.get("python") or extra.get("python_exe") or "").strip()
            timeout_s_raw = extra.get("timeout_s")
            try:
                timeout_s_i = int(timeout_s_raw) if timeout_s_raw is not None and str(timeout_s_raw).strip() != "" else 10
            except (TypeError, ValueError):
                timeout_s_i = 10

            if not python_path:
                result["message"] = "Missing required field: extra_options.python_path"
            else:
                try:
                    proc = subprocess.run(
                        [python_path, "-c", "from soda.scan import Scan; print('ok')"],
                        text=True,
                        capture_output=True,
                        timeout=max(1, min(60, timeout_s_i)),
                        check=False,
                    )
                    if proc.returncode == 0 and "ok" in (proc.stdout or ""):
                        result["success"] = True
                        result["message"] = "External Soda runner is configured"
                    else:
                        stderr = (proc.stderr or "").strip()
                        result["message"] = f"External Soda runner failed (exit {proc.returncode}): {stderr[:300]}"
                except FileNotFoundError:
                    result["message"] = f"Python not found: {python_path}"
                except subprocess.TimeoutExpired:
                    result["message"] = f"External Soda runner test timed out after {timeout_s_i}s"

        elif conn_type == "local_folder":
            folder_path = str(extra.get("folder_path") or "").strip()
            if not folder_path:
                result["message"] = "Missing required field: extra_options.folder_path"
            else:
                path = Path(folder_path)
                if not _is_under_allowed_root(path):
                    result["message"] = (
                        "Folder path is outside allowed data directories. "
                        "Configure GRAPH_TRACE_ALLOWED_LOCAL_ROOTS (Windows: ';' separated) "
                        "or system_configuration.allowed_local_roots."
                    )
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
                        blob_service = BlobServiceClient.from_connection_string(connection_string)
                    else:
                        # Fall back to key-based auth.
                        account_key = str(extra.get("account_key") or "").strip() or None
                        if not account_key:
                            result["message"] = "Missing required field: extra_options.account_key"
                            raise RuntimeError("missing account_key")
                        url = f"https://{account_name}.blob.core.windows.net"
                        blob_service = BlobServiceClient(account_url=url, credential=account_key)

                    container_client = blob_service.get_container_client(container)
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
            gd_access_token: str = str(conn.password or "").strip()
            if not gd_access_token:
                result["message"] = "Access token not configured (stored in password)"
            else:
                try:
                    import httpx

                    async with httpx.AsyncClient(timeout=10.0) as client:
                        resp = await client.get(
                            "https://www.googleapis.com/drive/v3/about",
                            params={"fields": "user,storageQuota"},
                            headers={"Authorization": "Bearer " + gd_access_token},
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

        elif conn_type in {"api", "rest_api", "webapi", "openapi", "odata"}:
            endpoint = str(conn.connection_string or "").strip()
            if not endpoint:
                result["message"] = "Missing endpoint: connection_string must be set"
            else:
                try:
                    import httpx

                    auth_type = str(extra.get("auth_type") or "none").strip().lower()
                    api_test_path = str(extra.get("test_path") or "").strip()
                    timeout_s_raw = extra.get("timeout_s")
                    try:
                        timeout_s = float(timeout_s_raw) if timeout_s_raw is not None and timeout_s_raw != "" else 10.0
                    except (TypeError, ValueError):
                        timeout_s = 10.0

                    # OData default: verify $metadata
                    if conn_type == "odata" and not api_test_path:
                        api_test_path = "/$metadata"

                    # OpenAPI default: try openapi.json
                    if conn_type == "openapi" and not api_test_path:
                        api_test_path = "/openapi.json"

                    # Generic API default: /health
                    if conn_type in {"api", "rest_api", "webapi"} and not api_test_path:
                        api_test_path = "/health"

                    # Build full URL
                    base = endpoint.rstrip("/")
                    api_path_str: str = api_test_path
                    if api_path_str and not api_path_str.startswith("/"):
                        api_path_str = "/" + api_path_str
                    url = base + (api_path_str or "")

                    headers: Dict[str, str] = {}

                    # Optional custom headers (stored by UI in extra_options.headers_json)
                    headers_json = str(extra.get("headers_json") or "").strip()
                    if headers_json:
                        try:
                            import json as _json
                            parsed = _json.loads(headers_json)
                            if isinstance(parsed, dict):
                                for k, v in parsed.items():
                                    if k is None:
                                        continue
                                    headers[str(k)] = str(v)
                        except Exception:
                            # Ignore invalid json; UI will warn
                            pass

                    auth = None

                    if auth_type in {"bearer", "oauth2"}:
                        token = str(conn.password or "").strip()
                        if token:
                            headers["Authorization"] = "Bearer " + token
                    elif auth_type == "api_key":
                        api_key = str(conn.password or "").strip()
                        header_name = str(extra.get("api_key_header") or "X-API-Key").strip() or "X-API-Key"
                        if api_key:
                            headers[header_name] = api_key
                    elif auth_type == "basic":
                        # Basic auth uses username/password
                        if conn.username and conn.password:
                            auth = (str(conn.username), str(conn.password))

                    async with httpx.AsyncClient(timeout=timeout_s, follow_redirects=True) as http_client:
                        resp = await http_client.get(url, headers=headers, auth=auth)

                    if 200 <= resp.status_code < 300:
                        result["success"] = True
                        result["message"] = f"HTTP {resp.status_code} OK"
                    else:
                        result["message"] = f"HTTP {resp.status_code} from {url}"
                except Exception as e:
                    result["message"] = f"API test failed: {str(e)}"
            
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
            api_key = str(provider.api_key or "")
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{provider.api_endpoint or 'https://api.openai.com/v1'}/models",
                    headers={"Authorization": f"Bearer {api_key}"},
                )
                if response.status_code == 200:
                    result["success"] = True
                    result["message"] = "OpenAI API connection successful"
                else:
                    result["error"] = f"API returned status {response.status_code}"
                    
        elif provider.provider == "anthropic":
            import httpx
            api_key = str(provider.api_key or "")
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    f"{provider.api_endpoint or 'https://api.anthropic.com'}/v1/messages",
                    headers={
                        "x-api-key": api_key,
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
            base_url = (provider.api_endpoint or "http://localhost:11434").rstrip("/")
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.get(f"{base_url}/api/tags")
                if response.status_code == 200:
                    models = response.json().get("models", [])
                    result["success"] = True
                    result["message"] = f"Ollama connected ({len(models)} models available)"
                else:
                    result["error"] = f"Ollama returned status {response.status_code}"
            except httpx.RequestError as e:
                # Most common cause: Ollama isn't running locally.
                result["error"] = f"Cannot connect to Ollama at {base_url} ({type(e).__name__}: {str(e)}). Ensure Ollama is running (e.g. start the Ollama app or run 'ollama serve')."
                    
        elif provider.provider == "azure_openai":
            if not provider.azure_resource_name:
                result["error"] = "Azure resource name not configured"
                return result
            import httpx
            api_key = str(provider.api_key or "")
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"https://{provider.azure_resource_name}.openai.azure.com/openai/deployments?api-version={provider.api_version or '2024-02-15-preview'}",
                    headers={"api-key": api_key},
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
                import importlib
                importlib.import_module("sentence_transformers")  # pyright: ignore[reportMissingImports]
                result["success"] = True
                result["message"] = f"SentenceTransformers available (model: {model.model_name})"
            except ImportError:
                result["error"] = "sentence-transformers not installed (install with: pip install sentence-transformers)"
                
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


# ============================================================
# Maintenance Endpoints (Admin Only)
# ============================================================

@router.post("/maintenance/migrate-database", response_model=Dict[str, Any])
async def migrate_database(db: Session = Depends(get_db)):
    """
    Run database migrations to ensure schema consistency and
    performance optimizations are applied (e.g., add missing indexes).
    
    This is an admin-only endpoint that should only be called during
    maintenance windows or when explicitly requested.
    """
    result = {
        "success": False,
        "message": "Migration not completed",
        "details": {}
    }
    
    try:
        from services.migration_runner import MigrationRunner
        from core.database import DATABASE_URL
        
        runner = MigrationRunner(DATABASE_URL)
        
        # Run migrations
        logger.info("Starting database migrations...")
        runner.run_migrations()
        
        # Check schema health
        schema_check = runner.check_schema()
        
        result["success"] = True
        result["message"] = "Database migrations completed successfully"
        result["details"] = {
            "tables_count": len(schema_check["tables"]),
            "indexes_created": sum(len(v) for v in schema_check["indexes"].values()),
            "constraints": sum(len(v) for v in schema_check["constraints"].values()),
        }
        
        logger.info("✓ Database migration completed: %s", result)
        
    except ImportError as e:
        result["error"] = f"Migration module not found: {str(e)}"
        logger.error("Migration import error: %s", e)
    except Exception as e:
        result["error"] = f"Migration failed: {str(e)}"
        logger.error("Migration error: %s", e)
    
    return result


@router.get("/maintenance/schema-health", response_model=Dict[str, Any])
async def check_schema_health(db: Session = Depends(get_db)):
    """
    Check database schema health: tables, indexes, and constraints.
    
    This endpoint provides diagnostics about the database schema state
    and can help identify missing optimizations.
    """
    result = {
        "status": "unknown",
        "schema": {}
    }
    
    try:
        from services.migration_runner import MigrationRunner
        from core.database import DATABASE_URL
        
        runner = MigrationRunner(DATABASE_URL)
        schema_check = runner.check_schema()
        
        result["status"] = "healthy"
        result["schema"] = {
            "tables": schema_check["tables"],
            "indexes_by_table": schema_check["indexes"],
            "constraints_by_table": schema_check["constraints"],
            "summary": {
                "total_tables": len(schema_check["tables"]),
                "total_indexes": sum(len(v) for v in schema_check["indexes"].values()),
                "total_constraints": sum(len(v) for v in schema_check["constraints"].values()),
            }
        }
        
    except Exception as e:
        result["status"] = "error"
        result["error"] = str(e)
        logger.error("Schema health check error: %s", e)
    
    return result
