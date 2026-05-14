from fastapi import HTTPException
import pytest


def test_resolve_ollama_model_name_supports_latest_alias():
    from graph_api.llm_integration_router import _resolve_ollama_model_name

    assert _resolve_ollama_model_name("llama3", ["llama3:latest"]) == "llama3:latest"
    assert _resolve_ollama_model_name("llama3:latest", ["llama3:latest"]) == "llama3:latest"
    assert _resolve_ollama_model_name("llama2", ["llama3:latest"]) is None


def test_get_ollama_num_predict_uses_default_and_cap():
    from graph_api.llm_integration_router import _get_ollama_num_predict

    assert _get_ollama_num_predict(requested_max_tokens=None, default_max_tokens=192, max_tokens_cap=256) == 192
    assert _get_ollama_num_predict(requested_max_tokens=999, default_max_tokens=192, max_tokens_cap=256) == 256
    assert _get_ollama_num_predict(requested_max_tokens=12, default_max_tokens=192, max_tokens_cap=256) == 12


@pytest.mark.asyncio
async def test_ollama_health_is_degraded_when_default_model_missing(monkeypatch):
    from core.external_config import llm_config
    from graph_api import llm_integration_router as router

    async def fake_catalog(_base_url: str):
        return [{"name": "llama3:latest"}]

    monkeypatch.setattr(router, "_is_ollama_explicitly_configured", lambda: True)
    monkeypatch.setattr(router, "_fetch_ollama_model_catalog", fake_catalog)
    monkeypatch.setattr(llm_config, "ollama_base_url", "http://localhost:11434")
    monkeypatch.setattr(llm_config, "ollama_model", "llama2")
    monkeypatch.setattr(llm_config, "openai_api_key", "")
    monkeypatch.setattr(llm_config, "anthropic_api_key", "")
    monkeypatch.setattr(llm_config, "azure_openai_endpoint", "")
    monkeypatch.setattr(llm_config, "azure_openai_key", "")

    body = await router.llm_health_check()

    assert body["status"] == "degraded"
    assert body["providers"]["ollama"] is True
    assert body["usable_providers"]["ollama"] is False
    assert body["provider_health"]["ollama"]["default_model_available"] is False
    assert "llama2" in body["provider_health"]["ollama"]["message"]


@pytest.mark.asyncio
async def test_ollama_chat_fails_closed_when_default_model_missing(monkeypatch):
    from core.external_config import llm_config
    from graph_api import llm_integration_router as router

    async def fake_catalog(_base_url: str):
        return [{"name": "llama3:latest"}]

    monkeypatch.setattr(router, "_is_ollama_explicitly_configured", lambda: True)
    monkeypatch.setattr(router, "_fetch_ollama_model_catalog", fake_catalog)
    monkeypatch.setattr(llm_config, "ollama_base_url", "http://localhost:11434")
    monkeypatch.setattr(llm_config, "ollama_model", "llama2")

    with pytest.raises(HTTPException) as exc_info:
        await router.ollama_chat_completion(
            router.LLMChatRequest(messages=[router.ChatMessage(role="user", content="hello")])
        )

    assert exc_info.value.status_code == 503
    detail = str(exc_info.value.detail)
    assert "llama2" in detail
    assert "llama3:latest" in detail


@pytest.mark.asyncio
async def test_ollama_chat_accepts_shorthand_model_alias(monkeypatch):
    from core.external_config import llm_config
    from graph_api import llm_integration_router as router

    async def fake_catalog(_base_url: str):
        return [{"name": "llama3:latest"}]

    class FakeClient:
        def __init__(self, *, host: str):
            self.host = host

        def chat(self, *, model, messages, stream, options):
            assert self.host == "http://localhost:11434"
            assert model == "llama3:latest"
            assert messages[0]["content"] == "hello"
            assert stream is False
            assert options["temperature"] == 0.7
            assert options["num_predict"] == 30
            return {
                "message": {"content": "ok"},
                "created_at": "2026-05-13T00:00:00Z",
                "done": True,
            }

    class FakeOllamaModule:
        Client = FakeClient

    real_import_module = router.importlib.import_module

    def fake_import_module(name: str):
        if name == "ollama":
            return FakeOllamaModule
        return real_import_module(name)

    monkeypatch.setattr(router, "_is_ollama_explicitly_configured", lambda: True)
    monkeypatch.setattr(router, "_fetch_ollama_model_catalog", fake_catalog)
    monkeypatch.setattr(router.importlib, "import_module", fake_import_module)
    monkeypatch.setattr(llm_config, "ollama_base_url", "http://localhost:11434")
    monkeypatch.setattr(llm_config, "ollama_model", "")

    body = await router.ollama_chat_completion(
        router.LLMChatRequest(
            messages=[router.ChatMessage(role="user", content="hello")],
            model="llama3",
            max_tokens=30,
        )
    )

    assert body["status"] == "success"
    assert body["model"] == "llama3:latest"
    assert body["response"] == "ok"


@pytest.mark.asyncio
async def test_ollama_chat_uses_default_max_tokens_when_request_omits_it(monkeypatch):
    from core.external_config import llm_config
    from graph_api import llm_integration_router as router

    async def fake_catalog(_base_url: str):
        return [{"name": "llama3.1:8b"}]

    class FakeClient:
        def __init__(self, *, host: str):
            self.host = host

        def chat(self, *, model, messages, stream, options):
            assert model == "llama3.1:8b"
            assert stream is False
            assert options["temperature"] == 0.7
            assert options["num_predict"] == 192
            return {
                "message": {"content": "ok"},
                "created_at": "2026-05-13T00:00:00Z",
                "done": True,
            }

    class FakeOllamaModule:
        Client = FakeClient

    real_import_module = router.importlib.import_module

    def fake_import_module(name: str):
        if name == "ollama":
            return FakeOllamaModule
        return real_import_module(name)

    monkeypatch.setattr(router, "_is_ollama_explicitly_configured", lambda: True)
    monkeypatch.setattr(router, "_fetch_ollama_model_catalog", fake_catalog)
    monkeypatch.setattr(router.importlib, "import_module", fake_import_module)
    monkeypatch.setattr(llm_config, "ollama_base_url", "http://localhost:11434")
    monkeypatch.setattr(llm_config, "ollama_model", "llama3.1:8b")
    monkeypatch.setattr(llm_config, "ollama_default_max_tokens", 192)
    monkeypatch.setattr(llm_config, "ollama_max_tokens_cap", 256)
    monkeypatch.setattr(llm_config, "ollama_request_timeout_seconds", 75.0)

    body = await router.ollama_chat_completion(
        router.LLMChatRequest(messages=[router.ChatMessage(role="user", content="hello")])
    )

    assert body["status"] == "success"
    assert body["model"] == "llama3.1:8b"
    assert body["response"] == "ok"
