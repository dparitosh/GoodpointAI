"""Test PLM ETL router fail-closed behaviour.

The plm_etl_router now only handles run creation.
Verify it returns 503 when Postgres is unavailable.
"""

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from graph_api.plm_etl_router import router as plm_etl_router
import graph_api.plm_etl_router as pr


def test_plm_etl_create_run_returns_503_when_postgres_unavailable(monkeypatch: pytest.MonkeyPatch):
    app = FastAPI()
    app.include_router(plm_etl_router)

    def _raise_unavailable():
        raise HTTPException(
            status_code=503,
            detail="Postgres is required for PLM ETL. Set DATABASE_URL to a Postgres connection string.",
        )

    monkeypatch.setattr(pr, "_require_postgres", _raise_unavailable)

    client = TestClient(app)
    resp = client.post(
        "/api/plm/etl/runs",
        json={"source_system": "test_src", "target_system": "test_tgt"},
    )

    assert resp.status_code == 503
    assert "Postgres" in resp.json().get("detail", "")
