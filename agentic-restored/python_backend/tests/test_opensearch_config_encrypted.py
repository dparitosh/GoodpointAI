import pytest
from fastapi import FastAPI
from sqlalchemy.orm import sessionmaker
from starlette.testclient import TestClient

from core.database import Base

from test_db_utils import create_postgres_test_engine


@pytest.mark.filterwarnings("ignore:.*PydanticDeprecatedSince20.*")
def test_opensearch_config_is_encrypted_and_password_preserved(monkeypatch) -> None:
    # Ensure encryption is available for encrypt_json/decrypt_json.
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

    async def _always_ok(*_args, **_kwargs):
        return True

    monkeypatch.setattr(cr, "test_opensearch_connection", _always_ok)

    app = FastAPI()
    app.include_router(cr.router)
    app.dependency_overrides[cr.get_db] = override_get_db

    try:
        with TestClient(app) as client:
            create_payload = {
                "url": "http://localhost:9200",
                "username": "admin",
                "password": "secret",
                "verify_certs": True,
                "timeout_s": 5,
            }
            created = client.post("/api/config/opensearch", json=create_payload)
            assert created.status_code == 200, created.text
            assert created.json()["status"] == "success"

            got = client.get("/api/config/opensearch")
            assert got.status_code == 200, got.text
            got_json = got.json()
            assert got_json.get("url") == "http://localhost:9200"
            assert got_json.get("username") == "admin"
            assert got_json.get("verify_certs") is True
            assert "password" not in got_json

            # Update with masked password should preserve stored secret
            update_payload = {
                "url": "http://localhost:9200",
                "username": "admin",
                "password": "***",
                "verify_certs": True,
                "timeout_s": 5,
            }
            updated = client.post("/api/config/opensearch", json=update_payload)
            assert updated.status_code == 200, updated.text

            # Verify DB still contains original secret
            from core.crypto import decrypt_json
            db = SessionLocal()
            try:
                row = db.get(cr.EncryptedConfig, "opensearch")
                assert row is not None
                payload = decrypt_json(row.ciphertext)
                assert payload.get("password") == "secret"
            finally:
                db.close()
    finally:
        Base.metadata.drop_all(bind=engine)
        engine.dispose()
