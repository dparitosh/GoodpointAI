import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from graph_api.plm_etl_router import router as plm_etl_router
import graph_api.plm_etl_router as pr


def test_plm_etl_soda_gate_returns_503_when_soda_unavailable(monkeypatch: pytest.MonkeyPatch):
    app = FastAPI()
    app.include_router(plm_etl_router)

    # Avoid requiring a real Postgres DATABASE_URL for this unit test.
    monkeypatch.setattr(pr, "_require_postgres", lambda: None)

    def _raise_unavailable():
        raise HTTPException(
            status_code=503,
            detail="Soda Core is not installed. Install `soda-core-postgres` to use Soda gate endpoints.",
        )

    monkeypatch.setattr(pr, "_require_soda", _raise_unavailable)

    client = TestClient(app)
    resp = client.post(
        "/api/plm/etl/runs/some_run_id/dq/soda/scan/public.plm_parts",
        json={"stage": "transformed", "checks_yaml": "- row_count > 0"},
    )

    assert resp.status_code == 503
    assert "Soda Core" in resp.json().get("detail", "")
