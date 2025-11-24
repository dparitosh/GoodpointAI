"""
LLM Integration Router
Handles OpenAI, Anthropic Claude, Azure OpenAI, Ollama
"""
import logging
from typing import List, Dict, Optional, Any
from datetime import datetime
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
import json

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/llm", tags=["LLM Integration"])


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
        from openai import OpenAI
        
        if not llm_config.openai_api_key:
            raise HTTPException(status_code=400, detail="OpenAI API key not configured")
        
        client = OpenAI(api_key=llm_config.openai_api_key)
        
        model = request.model or llm_config.openai_model
        
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": msg.role, "content": msg.content} for msg in request.messages],
            temperature=request.temperature,
            max_tokens=request.max_tokens
        )
        
        return {
            "status": "success",
            "provider": "openai",
            "model": model,
            "response": response.choices[0].message.content,
            "usage": {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens
            }
        }
        
    except Exception as e:
        logger.error(f"Error with OpenAI chat: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/openai/embedding")
async def openai_embedding(request: LLMEmbeddingRequest):
    """OpenAI Text Embedding"""
    try:
        from core.external_config import llm_config
        from openai import OpenAI
        
        if not llm_config.openai_api_key:
            raise HTTPException(status_code=400, detail="OpenAI API key not configured")
        
        client = OpenAI(api_key=llm_config.openai_api_key)
        
        model = request.model or llm_config.openai_embedding_model
        
        response = client.embeddings.create(
            model=model,
            input=request.text
        )
        
        return {
            "status": "success",
            "provider": "openai",
            "model": model,
            "embedding": response.data[0].embedding,
            "dimensions": len(response.data[0].embedding),
            "usage": {
                "prompt_tokens": response.usage.prompt_tokens,
                "total_tokens": response.usage.total_tokens
            }
        }
        
    except Exception as e:
        logger.error(f"Error with OpenAI embedding: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# ANTHROPIC CLAUDE ENDPOINTS
# ============================================================================

@router.post("/anthropic/chat")
async def anthropic_chat_completion(request: LLMChatRequest):
    """Anthropic Claude Chat Completion"""
    try:
        from core.external_config import llm_config
        from anthropic import Anthropic
        
        if not llm_config.anthropic_api_key:
            raise HTTPException(status_code=400, detail="Anthropic API key not configured")
        
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
        
        kwargs = {
            "model": model,
            "messages": messages,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens or 1024
        }
        
        if system_message:
            kwargs["system"] = system_message
        
        response = client.messages.create(**kwargs)
        
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
        
    except Exception as e:
        logger.error(f"Error with Anthropic chat: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# AZURE OPENAI ENDPOINTS
# ============================================================================

@router.post("/azure-openai/chat")
async def azure_openai_chat_completion(request: LLMChatRequest):
    """Azure OpenAI Chat Completion"""
    try:
        from core.external_config import llm_config
        from openai import AzureOpenAI
        
        if not llm_config.azure_openai_endpoint or not llm_config.azure_openai_key:
            raise HTTPException(status_code=400, detail="Azure OpenAI not configured")
        
        client = AzureOpenAI(
            api_key=llm_config.azure_openai_key,
            api_version=llm_config.azure_openai_api_version,
            azure_endpoint=llm_config.azure_openai_endpoint
        )
        
        deployment = request.model or llm_config.azure_openai_deployment
        
        response = client.chat.completions.create(
            model=deployment,
            messages=[{"role": msg.role, "content": msg.content} for msg in request.messages],
            temperature=request.temperature,
            max_tokens=request.max_tokens
        )
        
        return {
            "status": "success",
            "provider": "azure-openai",
            "deployment": deployment,
            "response": response.choices[0].message.content,
            "usage": {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens
            }
        }
        
    except Exception as e:
        logger.error(f"Error with Azure OpenAI chat: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# OLLAMA LOCAL LLM ENDPOINTS
# ============================================================================

@router.post("/ollama/chat")
async def ollama_chat_completion(request: LLMChatRequest):
    """Ollama Local LLM Chat Completion"""
    try:
        from core.external_config import llm_config
        import ollama
        
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
        
    except Exception as e:
        logger.error(f"Error with Ollama chat: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ollama/generate")
async def ollama_generate(request: LLMCompletionRequest):
    """Ollama Text Generation"""
    try:
        from core.external_config import llm_config
        import ollama
        
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
        
    except Exception as e:
        logger.error(f"Error with Ollama generate: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/ollama/models")
async def list_ollama_models():
    """List available Ollama models"""
    try:
        import ollama
        
        response = ollama.list()
        
        models = []
        for model in response.get('models', []):
            models.append({
                "name": model.get('name'),
                "size": model.get('size'),
                "modified_at": model.get('modified_at'),
                "digest": model.get('digest')
            })
        
        return {
            "status": "success",
            "provider": "ollama",
            "count": len(models),
            "models": models
        }
        
    except Exception as e:
        logger.error(f"Error listing Ollama models: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ollama/embedding")
async def ollama_embedding(request: LLMEmbeddingRequest):
    """Ollama Text Embedding"""
    try:
        from core.external_config import llm_config
        import ollama
        
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
        
    except Exception as e:
        logger.error(f"Error with Ollama embedding: {e}")
        raise HTTPException(status_code=500, detail=str(e))


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
            
    except Exception as e:
        logger.error(f"Error with unified chat: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# HEALTH CHECK
# ============================================================================

@router.get("/health")
async def llm_health_check():
    """Check LLM service connectivity"""
    from core.external_config import llm_config
    
    health = {
        "status": "healthy",
        "providers": {
            "openai": llm_config.openai_api_key != "",
            "anthropic": llm_config.anthropic_api_key != "",
            "azure_openai": llm_config.azure_openai_endpoint != "",
            "ollama": llm_config.ollama_base_url != ""
        },
        "models": {
            "openai": llm_config.openai_model,
            "anthropic": llm_config.anthropic_model,
            "ollama": llm_config.ollama_model
        },
        "timestamp": datetime.utcnow().isoformat()
    }
    
    return health
