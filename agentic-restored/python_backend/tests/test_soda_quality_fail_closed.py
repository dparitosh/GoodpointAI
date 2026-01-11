import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from graph_api.quality_router import router as quality_router
import graph_api.quality_router as qr


def test_soda_scan_returns_503_when_soda_unavailable(monkeypatch: pytest.MonkeyPatch):
    app = FastAPI()
    app.include_router(quality_router)

    # Avoid needing a real Postgres DB in this unit test.
    monkeypatch.setattr(qr, "_require_postgres", lambda: None)

    def _raise_unavailable():
        raise HTTPException(
            status_code=503,
            detail="Soda Core is not installed. Install `soda-core-postgres` to use this endpoint.",
        )

    monkeypatch.setattr(qr, "_get_soda_scan_class", _raise_unavailable)

    client = TestClient(app)
    resp = client.post(
        "/api/analytics/quality/soda/scan/public.some_table",
        json={"checks_yaml": "- row_count > 0"},
    )

    assert resp.status_code == 503
    assert "Soda Core" in resp.json().get("detail", "")
