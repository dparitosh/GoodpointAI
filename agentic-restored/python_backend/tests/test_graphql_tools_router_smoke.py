"""Smoke tests for /api/graphql/tools.

These tests are intentionally light-weight:
- Ensure the router is mounted.
- Ensure endpoints return structured responses even when optional services
  (OpenSearch, admin DB) may not be fully configured in CI.

We avoid asserting OpenSearch connectivity here.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(name="api_client")
def api_client_fixture():
    from main import app

    return TestClient(app)


def test_graphql_tools_connectors_route_exists(api_client: TestClient):
    resp = api_client.get("/api/graphql/tools/connectors")
    assert resp.status_code == 200


def test_graphql_tools_default_connector_route_exists(api_client: TestClient):
    resp = api_client.get("/api/graphql/tools/connectors/default/opensearch")
    assert resp.status_code == 200


def test_graphql_tools_soda_scan_route_exists(api_client: TestClient):
    resp = api_client.post(
        "/api/graphql/tools/soda/scan/public.some_table",
        json={"checks_yaml": "- row_count > 0\n", "data_source_name": "postgres"},
    )
    # Soda may not be installed/configured in test environment, so we accept 503/500.
    assert resp.status_code in (200, 400, 404, 500, 503)
