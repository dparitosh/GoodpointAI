import pytest
from fastapi import FastAPI
from sqlalchemy.orm import sessionmaker
from starlette.testclient import TestClient

from core.database import Base

from test_db_utils import create_postgres_test_engine


@pytest.mark.filterwarnings("ignore:.*PydanticDeprecatedSince20.*")
def test_cors_and_system_config_roundtrip(monkeypatch) -> None:
    monkeypatch.setenv("GRAPH_TRACE_CONFIG_ENCRYPTION_KEY", "test-key-should-be-32-bytes-minimum")

    engine = create_postgres_test_engine()
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    # Register ORM models
    from models.configuration_models import EncryptedConfig

    _ = EncryptedConfig

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    import graph_api.config_router as cr

    app = FastAPI()
    app.include_router(cr.router)
    app.dependency_overrides[cr.get_db] = override_get_db

    try:
        with TestClient(app) as client:
            cors_payload = {"allowed_origins": ["http://a", "http://b", "http://a", "  "]}
            saved_cors = client.post("/api/config/cors", json=cors_payload)
            assert saved_cors.status_code == 200, saved_cors.text

            got_cors = client.get("/api/config/cors")
            assert got_cors.status_code == 200, got_cors.text
            assert got_cors.json()["allowed_origins"] == ["http://a", "http://b"]

            system_payload = {"databases": {"postgresql": {"main_port": 5433}}, "cors": cors_payload}
            saved_system = client.post("/api/config/system", json=system_payload)
            assert saved_system.status_code == 200, saved_system.text

            got_system = client.get("/api/config/system")
            assert got_system.status_code == 200, got_system.text
            assert got_system.json()["databases"]["postgresql"]["main_port"] == 5433

            runtime = client.get("/api/config/runtime")
            assert runtime.status_code == 200, runtime.text
            runtime_json = runtime.json()
            assert "password" not in runtime_json.get("neo4j", {})
            assert "password" not in runtime_json.get("opensearch", {})
            assert runtime_json["cors"]["allowed_origins"] == ["http://a", "http://b"]
    finally:
        Base.metadata.drop_all(bind=engine)
        engine.dispose()
