"""
LLM Integration Router
Handles OpenAI, Anthropic Claude, Azure OpenAI, Ollama
"""
import logging
import asyncio
import os
import importlib
from typing import Any, Dict, List, Optional, cast
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Query, Response
from pydantic import BaseModel, Field


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/llm", tags=["LLM Integration"])

_PLACEHOLDER_SECRET_MARKERS = (
    "your_api_key",
    "your-api-key",
    "your key",
    "placeholder",
    "changeme",
    "change_me",
    "replace_me",
    "replace-with",
    "replace this",
    "example",
    "dummy",
    "test-key",
    "sk-your_",
)


def _is_ollama_explicitly_configured() -> bool:
    # Avoid treating default config values as "configured".
    return bool((os.getenv("OLLAMA_BASE_URL") or "").strip() or (os.getenv("OLLAMA_HOST") or "").strip())


def _has_real_config_value(value: Optional[str]) -> bool:
    """Return True when a config value is present and not an obvious placeholder."""
    raw = (value or "").strip()
    if not raw:
        return False
    lowered = raw.lower()
    return not any(marker in lowered for marker in _PLACEHOLDER_SECRET_MARKERS)


def _make_ollama_client(ollama_mod: Any, base_url: str) -> Any:
    """Return an ollama.Client bound to *base_url*.

    The `ollama` Python SDK reads OLLAMA_HOST from env by default, which does NOT
    respect OLLAMA_BASE_URL.  Always pass an explicit host so our config is honoured.
    """
    return ollama_mod.Client(host=base_url)


def _extract_ollama_models(ollama_resp: Any) -> List[Dict[str, Any]]:
    """Normalize model metadata returned by the Ollama Python SDK."""
    raw_models = []
    if isinstance(ollama_resp, dict):
        raw_models = cast(List[Any], ollama_resp.get("models", []))
    elif hasattr(ollama_resp, "models"):
        raw_models = cast(List[Any], getattr(ollama_resp, "models"))

    models: List[Dict[str, Any]] = []
    for model in raw_models:
        if isinstance(model, dict):
            name = model.get("name") or model.get("model")
            size = model.get("size")
            modified_at = model.get("modified_at")
            digest = model.get("digest")
        else:
            name = getattr(model, "name", None) or getattr(model, "model", None)
            size = getattr(model, "size", None)
            modified_at = getattr(model, "modified_at", None)
            digest = getattr(model, "digest", None)
        if not name:
            continue
        models.append(
            {
                "name": str(name),
                "size": size,
                "modified_at": modified_at,
                "digest": digest,
            }
        )
    return models


def _resolve_ollama_model_name(requested_model: Optional[str], available_models: List[str]) -> Optional[str]:
    """Resolve a requested Ollama model against the installed model list."""
    candidate = (requested_model or "").strip()
    if not candidate:
        return None
    if candidate in available_models:
        return candidate

    if ":" not in candidate:
        tagged_candidate = f"{candidate}:latest"
        if tagged_candidate in available_models:
            return tagged_candidate

    return None


def _get_ollama_num_predict(*, requested_max_tokens: Optional[int], default_max_tokens: int, max_tokens_cap: int) -> int:
    """Return a bounded Ollama generation budget for responsive local inference."""
    fallback_budget = max(32, int(default_max_tokens))
    hard_cap = max(32, int(max_tokens_cap))
    if requested_max_tokens is not None:
        return max(1, min(int(requested_max_tokens), hard_cap))
    return min(fallback_budget, hard_cap)


def _get_ollama_timeout_seconds(timeout_seconds: float) -> float:
    """Normalize Ollama timeout configuration to a safe positive value."""
    return max(5.0, float(timeout_seconds))


async def _fetch_ollama_model_catalog(base_url: str) -> List[Dict[str, Any]]:
    """Return the installed Ollama model catalog for *base_url*."""
    ollama = _require_module(
        "ollama",
        install_hint="Install `ollama` (the Python client) and configure OLLAMA_BASE_URL/OLLAMA_HOST.",
    )
    client = _make_ollama_client(ollama, base_url)
    ollama_resp = await asyncio.to_thread(client.list)
    return _extract_ollama_models(ollama_resp)


async def _resolve_requested_ollama_model(
    *,
    requested_model: Optional[str],
    configured_model: str,
    base_url: str,
) -> str:
    """Resolve the effective Ollama model or raise a clear HTTP error."""
    candidate = (requested_model or configured_model or "").strip()
    if not candidate:
        raise HTTPException(
            status_code=503,
            detail="Ollama default model is not configured. Set OLLAMA_MODEL or pass a model in the request.",
        )

    catalog = await _fetch_ollama_model_catalog(base_url)
    available_models = [entry["name"] for entry in catalog if entry.get("name")]
    resolved_model = _resolve_ollama_model_name(candidate, available_models)
    if resolved_model:
        return resolved_model

    model_source = "request" if requested_model else "configured default"
    preview = ", ".join(available_models[:10]) if available_models else "none"
    raise HTTPException(
        status_code=503,
        detail=(
            f"Ollama {model_source} model '{candidate}' is not installed. "
            f"Available models: {preview}"
        ),
    )


def _require_module(module_name: str, *, install_hint: str) -> Any:
    try:
        return importlib.import_module(module_name)
    except ModuleNotFoundError as e:
        raise HTTPException(
            status_code=503,
            detail=f"{module_name} dependency is not installed. {install_hint}",
        ) from e


def _require_provider_configured(provider: str) -> None:
    from core.external_config import llm_config

    if provider == "openai" and not _has_real_config_value(llm_config.openai_api_key):
        raise HTTPException(status_code=503, detail="OpenAI is not configured")
    if provider == "anthropic" and not _has_real_config_value(llm_config.anthropic_api_key):
        raise HTTPException(status_code=503, detail="Anthropic is not configured")
    if provider == "azure-openai" and not (
        _has_real_config_value(llm_config.azure_openai_endpoint)
        and _has_real_config_value(llm_config.azure_openai_key)
    ):
        raise HTTPException(status_code=503, detail="Azure OpenAI is not configured")
    if provider == "ollama" and not _is_ollama_explicitly_configured():
        raise HTTPException(status_code=503, detail="Ollama is not configured")


# ============================================================================
# MODELS
# ============================================================================

class ChatMessage(BaseModel):
    role: str = Field(..., description="user, assistant, system")
    content: str = Field(..., description="Message content")


class LLMChatRequest(BaseModel):
    messages: List[ChatMessage]
    model: Optional[str] = None
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: Optional[int] = None
    stream: bool = False


class LLMEmbeddingRequest(BaseModel):
    text: str = Field(..., description="Text to embed")
    model: Optional[str] = None


class LLMCompletionRequest(BaseModel):
    prompt: str
    model: Optional[str] = None
    temperature: float = 0.7
    max_tokens: Optional[int] = 1000


# ============================================================================
# OPENAI ENDPOINTS
# ============================================================================

@router.post("/openai/chat")
async def openai_chat_completion(request: LLMChatRequest):
    """OpenAI Chat Completion"""
    try:
        from core.external_config import llm_config
        _require_provider_configured("openai")
        openai_mod = _require_module("openai", install_hint="Install `openai`." )
        OpenAI = getattr(openai_mod, "OpenAI")
        
        client = OpenAI(api_key=llm_config.openai_api_key)
        
        model = request.model or llm_config.openai_model
        
        messages: Any = [{"role": msg.role, "content": msg.content} for msg in request.messages]

        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=request.temperature,
            max_tokens=request.max_tokens
        )

        usage = response.usage
        
        return {
            "status": "success",
            "provider": "openai",
            "model": model,
            "response": response.choices[0].message.content,
            "usage": {
                "prompt_tokens": usage.prompt_tokens if usage is not None else None,
                "completion_tokens": usage.completion_tokens if usage is not None else None,
                "total_tokens": usage.total_tokens if usage is not None else None,
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error with OpenAI chat: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/openai/embedding")
async def openai_embedding(request: LLMEmbeddingRequest):
    """OpenAI Text Embedding"""
    try:
        from core.external_config import llm_config
        _require_provider_configured("openai")
        openai_mod = _require_module("openai", install_hint="Install `openai`." )
        OpenAI = getattr(openai_mod, "OpenAI")
        
        client = OpenAI(api_key=llm_config.openai_api_key)
        
        model = request.model or llm_config.openai_embedding_model
        
        response = client.embeddings.create(
            model=model,
            input=request.text
        )
        
        usage = response.usage

        return {
            "status": "success",
            "provider": "openai",
            "model": model,
            "embedding": response.data[0].embedding,
            "dimensions": len(response.data[0].embedding),
            "usage": {
                "prompt_tokens": usage.prompt_tokens if usage is not None else None,
                "total_tokens": usage.total_tokens if usage is not None else None,
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error with OpenAI embedding: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


# ============================================================================
# ANTHROPIC CLAUDE ENDPOINTS
# ============================================================================

@router.post("/anthropic/chat")
async def anthropic_chat_completion(request: LLMChatRequest):
    """Anthropic Claude Chat Completion"""
    try:
        from core.external_config import llm_config
        _require_provider_configured("anthropic")
        anthropic_mod = _require_module("anthropic", install_hint="Install `anthropic`." )
        Anthropic = getattr(anthropic_mod, "Anthropic")
        
        client = Anthropic(api_key=llm_config.anthropic_api_key)
        
        model = request.model or llm_config.anthropic_model
        
        # Convert messages format
        system_message = None
        messages = []
        for msg in request.messages:
            if msg.role == "system":
                system_message = msg.content
            else:
                messages.append({"role": msg.role, "content": msg.content})
        
        kwargs: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens or 1024
        }
        
        if system_message:
            kwargs["system"] = system_message
        
        response = client.messages.create(**cast(Any, kwargs))
        
        return {
            "status": "success",
            "provider": "anthropic",
            "model": model,
            "response": response.content[0].text,
            "usage": {
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error with Anthropic chat: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


# ============================================================================
# AZURE OPENAI ENDPOINTS
# ============================================================================

@router.post("/azure-openai/chat")
async def azure_openai_chat_completion(request: LLMChatRequest):
    """Azure OpenAI Chat Completion"""
    try:
        from core.external_config import llm_config
        _require_provider_configured("azure-openai")
        openai_mod = _require_module("openai", install_hint="Install `openai`." )
        AzureOpenAI = getattr(openai_mod, "AzureOpenAI")
        
        client = AzureOpenAI(
            api_key=llm_config.azure_openai_key,
            api_version=llm_config.azure_openai_api_version,
            azure_endpoint=llm_config.azure_openai_endpoint
        )
        
        deployment = request.model or llm_config.azure_openai_deployment
        
        messages: Any = [{"role": msg.role, "content": msg.content} for msg in request.messages]

        response = client.chat.completions.create(
            model=deployment,
            messages=messages,
            temperature=request.temperature,
            max_tokens=request.max_tokens
        )

        usage = response.usage
        
        return {
            "status": "success",
            "provider": "azure-openai",
            "deployment": deployment,
            "response": response.choices[0].message.content,
            "usage": {
                "prompt_tokens": usage.prompt_tokens if usage is not None else None,
                "completion_tokens": usage.completion_tokens if usage is not None else None,
                "total_tokens": usage.total_tokens if usage is not None else None,
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error with Azure OpenAI chat: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


# ============================================================================
# OLLAMA LOCAL LLM ENDPOINTS
# ============================================================================

@router.post("/ollama/chat")
async def ollama_chat_completion(request: LLMChatRequest):
    """Ollama Local LLM Chat Completion"""
    try:
        from core.external_config import llm_config
        _require_provider_configured("ollama")
        model = await _resolve_requested_ollama_model(
            requested_model=request.model,
            configured_model=llm_config.ollama_model,
            base_url=llm_config.ollama_base_url,
        )
        ollama = _require_module("ollama", install_hint="Install `ollama` (the Python client) and configure OLLAMA_BASE_URL/OLLAMA_HOST." )
        client = _make_ollama_client(ollama, llm_config.ollama_base_url)
        num_predict = _get_ollama_num_predict(
            requested_max_tokens=request.max_tokens,
            default_max_tokens=llm_config.ollama_default_max_tokens,
            max_tokens_cap=llm_config.ollama_max_tokens_cap,
        )
        timeout_seconds = _get_ollama_timeout_seconds(llm_config.ollama_request_timeout_seconds)

        # Convert messages
        messages = [
            {"role": msg.role, "content": msg.content}
            for msg in request.messages
        ]

        # Wrap sync client call in a thread so the event loop is not blocked.
        def _call() -> Any:
            options: Dict[str, Any] = {
                "temperature": request.temperature,
                "num_predict": num_predict,
            }
            return client.chat(
                model=model,
                messages=messages,
                stream=False,  # stream=True not yet supported; honour False explicitly
                options=options,
            )

        response = await asyncio.wait_for(asyncio.to_thread(_call), timeout=timeout_seconds)

        return {
            "status": "success",
            "provider": "ollama",
            "model": model,
            "response": response['message']['content'],
            "created_at": response.get('created_at'),
            "done": response.get('done', True)
        }

    except HTTPException:
        raise
    except asyncio.TimeoutError as e:
        logger.warning("Ollama chat timed out after %.1fs", timeout_seconds)
        raise HTTPException(
            status_code=504,
            detail=(
                "Ollama chat timed out before producing a response. "
                "Reduce the prompt size or lower OLLAMA_DEFAULT_MAX_TOKENS / OLLAMA_MAX_TOKENS_CAP for faster local inference."
            ),
        ) from e
    except Exception as e:
        logger.error("Error with Ollama chat: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/ollama/generate")
async def ollama_generate(request: LLMCompletionRequest):
    """Ollama Text Generation"""
    try:
        from core.external_config import llm_config
        _require_provider_configured("ollama")
        model = await _resolve_requested_ollama_model(
            requested_model=request.model,
            configured_model=llm_config.ollama_model,
            base_url=llm_config.ollama_base_url,
        )
        ollama = _require_module("ollama", install_hint="Install `ollama` (the Python client) and configure OLLAMA_BASE_URL/OLLAMA_HOST." )
        client = _make_ollama_client(ollama, llm_config.ollama_base_url)
        num_predict = _get_ollama_num_predict(
            requested_max_tokens=request.max_tokens,
            default_max_tokens=llm_config.ollama_default_max_tokens,
            max_tokens_cap=llm_config.ollama_max_tokens_cap,
        )
        timeout_seconds = _get_ollama_timeout_seconds(llm_config.ollama_request_timeout_seconds)

        def _call() -> Any:
            options: Dict[str, Any] = {
                "temperature": request.temperature,
                "num_predict": num_predict,
            }
            return client.generate(
                model=model,
                prompt=request.prompt,
                options=options,
            )

        response = await asyncio.wait_for(asyncio.to_thread(_call), timeout=timeout_seconds)

        return {
            "status": "success",
            "provider": "ollama",
            "model": model,
            "response": response['response'],
            "done": response.get('done', True)
        }

    except HTTPException:
        raise
    except asyncio.TimeoutError as e:
        logger.warning("Ollama generate timed out after %.1fs", timeout_seconds)
        raise HTTPException(
            status_code=504,
            detail=(
                "Ollama text generation timed out before completion. "
                "Reduce the prompt size or lower OLLAMA_DEFAULT_MAX_TOKENS / OLLAMA_MAX_TOKENS_CAP for faster local inference."
            ),
        ) from e
    except Exception as e:
        logger.error("Error with Ollama generate: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/ollama/models")
async def list_ollama_models(
    http_response: Response,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
):
    """List available Ollama models"""
    try:
        from core.external_config import llm_config
        _require_provider_configured("ollama")
        models = await _fetch_ollama_model_catalog(llm_config.ollama_base_url)

        total_count = len(models)
        http_response.headers["X-Total-Count"] = str(total_count)
        models_page = models[skip : skip + limit]

        return {
            "status": "success",
            "provider": "ollama",
            "count": len(models_page),
            "models": models_page,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error listing Ollama models: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/ollama/embedding")
async def ollama_embedding(request: LLMEmbeddingRequest):
    """Ollama Text Embedding"""
    try:
        from core.external_config import llm_config
        _require_provider_configured("ollama")
        model = await _resolve_requested_ollama_model(
            requested_model=request.model,
            configured_model=llm_config.ollama_model,
            base_url=llm_config.ollama_base_url,
        )
        ollama = _require_module("ollama", install_hint="Install `ollama` (the Python client) and configure OLLAMA_BASE_URL/OLLAMA_HOST." )
        client = _make_ollama_client(ollama, llm_config.ollama_base_url)

        def _call() -> Any:
            return client.embeddings(model=model, prompt=request.text)

        response = await asyncio.to_thread(_call)

        return {
            "status": "success",
            "provider": "ollama",
            "model": model,
            "embedding": response['embedding'],
            "dimensions": len(response['embedding'])
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error with Ollama embedding: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


# ============================================================================
# UNIFIED LLM ENDPOINT
# ============================================================================

async def dispatch_chat_completion(
    request: LLMChatRequest,
    provider: str = "openai",
):
    """Dispatch a chat completion request to the configured provider without self-HTTP."""
    if provider == "openai":
        return await openai_chat_completion(request)
    if provider == "anthropic":
        return await anthropic_chat_completion(request)
    if provider == "azure-openai":
        return await azure_openai_chat_completion(request)
    if provider == "ollama":
        return await ollama_chat_completion(request)
    raise HTTPException(status_code=400, detail=f"Unknown provider: {provider}")

@router.post("/chat")
async def unified_chat_completion(
    request: LLMChatRequest,
    provider: str = "openai"
):
    """Unified chat completion endpoint - routes to appropriate provider"""
    try:
        return await dispatch_chat_completion(request, provider=provider)
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error with unified chat: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


# ============================================================================
# HEALTH CHECK
# ============================================================================

@router.get("/health")
async def llm_health_check():
    """Check LLM service connectivity"""
    from core.external_config import llm_config

    providers = {
        "openai": _has_real_config_value(llm_config.openai_api_key),
        "anthropic": _has_real_config_value(llm_config.anthropic_api_key),
        "azure_openai": _has_real_config_value(llm_config.azure_openai_endpoint) and _has_real_config_value(llm_config.azure_openai_key),
        "ollama": _is_ollama_explicitly_configured(),
    }
    usable_providers = dict(providers)
    provider_health: Dict[str, Any] = {}

    if providers["ollama"]:
        configured_ollama_model = str(getattr(llm_config, "ollama_model", "") or "")
        ollama_health: Dict[str, Any] = {
            "configured": True,
            "reachable": False,
            "default_model": configured_ollama_model,
            "default_model_available": False,
            "resolved_default_model": None,
            "available_models": [],
        }
        try:
            catalog = await _fetch_ollama_model_catalog(llm_config.ollama_base_url)
            available_models = [entry["name"] for entry in catalog if entry.get("name")]
            resolved_default_model = _resolve_ollama_model_name(
                configured_ollama_model,
                available_models,
            )
            ollama_health.update(
                {
                    "reachable": True,
                    "available_models": available_models,
                    "default_model_available": resolved_default_model is not None,
                    "resolved_default_model": resolved_default_model,
                }
            )
            if not configured_ollama_model.strip():
                ollama_health["message"] = "Set OLLAMA_MODEL to one of the installed Ollama models."
                usable_providers["ollama"] = False
            elif resolved_default_model is None:
                ollama_health["message"] = (
                    f"Configured model '{configured_ollama_model}' is not installed in Ollama."
                )
                usable_providers["ollama"] = False
            else:
                usable_providers["ollama"] = True
        except HTTPException as e:
            ollama_health["message"] = str(e.detail)
            usable_providers["ollama"] = False
        except (AttributeError, ImportError, OSError, RuntimeError, TypeError, ValueError) as e:
            ollama_health["message"] = str(e)
            usable_providers["ollama"] = False
        provider_health["ollama"] = ollama_health

    configured_any = any(providers.values())
    usable_any = any(usable_providers.values())
    if usable_any:
        status = "healthy"
    elif configured_any:
        status = "degraded"
    else:
        status = "unconfigured"

    return {
        "status": status,
        "providers": providers,
        "usable_providers": usable_providers,
        "provider_health": provider_health,
        "models": {
            "openai": llm_config.openai_model,
            "anthropic": llm_config.anthropic_model,
            "ollama": llm_config.ollama_model,
        },
        "timestamp": datetime.now(timezone.utc).replace(tzinfo=None).isoformat(),
    }
