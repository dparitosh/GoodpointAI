import os
import sys
import types

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client():
    from main import app

    return TestClient(app)


def test_llm_health_unconfigured_when_no_providers_configured(client):
    r = client.get("/api/llm/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] in {"unconfigured", "healthy"}
    # In CI/dev without any LLM env, should be unconfigured
    if os.getenv("OPENAI_API_KEY") is None and os.getenv("AZURE_OPENAI_API_KEY") is None:
        assert body["status"] == "unconfigured"


def test_odata_connect_requires_service_url(client):
    r = client.post("/api/odata/connect", json={})
    assert r.status_code in {400, 422}


def test_filesystem_watch_start_is_not_implemented(client):
    r = client.post(
        "/api/filesystem/watch/start",
        json={"watch_path": ".", "action": "process"},
    )
    assert r.status_code == 501


def test_aws_connect_fail_closed_without_boto3(monkeypatch, client):
    # Ensure import boto3 fails regardless of environment
    real_import = __import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "boto3":
            raise ImportError("boto3 missing")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr("builtins.__import__", fake_import)

    r = client.post("/api/aws/connect", json={})
    assert r.status_code == 503


def test_azure_blob_list_fail_closed_when_sdk_missing(monkeypatch, client):
    # Ensure azure sdk imports fail regardless of environment
    real_import = __import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name.startswith("azure"):
            raise ImportError("azure sdk missing")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr("builtins.__import__", fake_import)

    r = client.get("/api/azure/blob/list/test-container")
    assert r.status_code == 503
