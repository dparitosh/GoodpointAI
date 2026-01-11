"""
LLM Integration Router
Handles OpenAI, Anthropic Claude, Azure OpenAI, Ollama
"""
import logging
import os
import importlib
from typing import Any, Dict, List, Optional, cast
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Query, Response
from pydantic import BaseModel, Field


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/llm", tags=["LLM Integration"])


def _is_ollama_explicitly_configured() -> bool:
    # Avoid treating default config values as "configured".
    return bool((os.getenv("OLLAMA_BASE_URL") or "").strip() or (os.getenv("OLLAMA_HOST") or "").strip())


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

    if provider == "openai" and not llm_config.openai_api_key:
        raise HTTPException(status_code=503, detail="OpenAI is not configured")
    if provider == "anthropic" and not llm_config.anthropic_api_key:
        raise HTTPException(status_code=503, detail="Anthropic is not configured")
    if provider == "azure-openai" and not (llm_config.azure_openai_endpoint and llm_config.azure_openai_key):
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
        ollama = _require_module("ollama", install_hint="Install `ollama` (the Python client) and configure OLLAMA_BASE_URL/OLLAMA_HOST." )
        
        model = request.model or llm_config.ollama_model
        
        # Convert messages
        messages = [
            {"role": msg.role, "content": msg.content}
            for msg in request.messages
        ]
        
        response = ollama.chat(
            model=model,
            messages=messages,
            options={
                "temperature": request.temperature
            }
        )
        
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
    except Exception as e:
        logger.error("Error with Ollama chat: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/ollama/generate")
async def ollama_generate(request: LLMCompletionRequest):
    """Ollama Text Generation"""
    try:
        from core.external_config import llm_config
        _require_provider_configured("ollama")
        ollama = _require_module("ollama", install_hint="Install `ollama` (the Python client) and configure OLLAMA_BASE_URL/OLLAMA_HOST." )
        
        model = request.model or llm_config.ollama_model
        
        response = ollama.generate(
            model=model,
            prompt=request.prompt,
            options={
                "temperature": request.temperature
            }
        )
        
        return {
            "status": "success",
            "provider": "ollama",
            "model": model,
            "response": response['response'],
            "done": response.get('done', True)
        }
        
    except HTTPException:
        raise
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
        _require_provider_configured("ollama")
        ollama = _require_module("ollama", install_hint="Install `ollama` (the Python client) and configure OLLAMA_BASE_URL/OLLAMA_HOST." )
        
        ollama_resp = cast(Dict[str, Any], ollama.list())
        
        models = []
        for model in ollama_resp.get('models', []):
            models.append({
                "name": model.get('name'),
                "size": model.get('size'),
                "modified_at": model.get('modified_at'),
                "digest": model.get('digest')
            })
        
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
        ollama = _require_module("ollama", install_hint="Install `ollama` (the Python client) and configure OLLAMA_BASE_URL/OLLAMA_HOST." )
        
        model = request.model or llm_config.ollama_model
        
        response = ollama.embeddings(
            model=model,
            prompt=request.text
        )
        
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

@router.post("/chat")
async def unified_chat_completion(
    request: LLMChatRequest,
    provider: str = "openai"
):
    """Unified chat completion endpoint - routes to appropriate provider"""
    try:
        if provider == "openai":
            return await openai_chat_completion(request)
        elif provider == "anthropic":
            return await anthropic_chat_completion(request)
        elif provider == "azure-openai":
            return await azure_openai_chat_completion(request)
        elif provider == "ollama":
            return await ollama_chat_completion(request)
        else:
            raise HTTPException(status_code=400, detail=f"Unknown provider: {provider}")
            
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
        "openai": bool(llm_config.openai_api_key),
        "anthropic": bool(llm_config.anthropic_api_key),
        "azure_openai": bool(llm_config.azure_openai_endpoint and llm_config.azure_openai_key),
        "ollama": _is_ollama_explicitly_configured(),
    }
    configured_any = any(providers.values())
    status = "healthy" if configured_any else "unconfigured"

    return {
        "status": status,
        "providers": providers,
        "models": {
            "openai": llm_config.openai_model,
            "anthropic": llm_config.anthropic_model,
            "ollama": llm_config.ollama_model,
        },
        "timestamp": datetime.now(timezone.utc).replace(tzinfo=None).isoformat(),
    }
