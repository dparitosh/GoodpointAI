import pytest
from fastapi import FastAPI
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from starlette.testclient import TestClient

from core.database import Base


@pytest.mark.filterwarnings("ignore:.*PydanticDeprecatedSince20.*")
def test_data_sources_never_return_plaintext_secrets(tmp_path, monkeypatch) -> None:
    # Ensure encryption is available for encrypt_json/decrypt_json.
    monkeypatch.setenv("GRAPH_TRACE_CONFIG_ENCRYPTION_KEY", "test-key-should-be-32-bytes-minimum")

    # Isolated SQLite DB per test.
    db_path = tmp_path / "test_data_sources.db"
    engine = create_engine(
        f"sqlite:///{db_path.as_posix()}",
        connect_args={"check_same_thread": False},
        pool_pre_ping=True,
    )
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    # Register ORM models — import all models the router touches
    from models.configuration_models import DataSourceConfigRecord  # noqa: F401
    from models.admin_config_models import ConnectionConfig  # noqa: F401

    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    import graph_api.data_sources_router as dsr

    app = FastAPI()
    app.include_router(dsr.router)
    app.dependency_overrides[dsr.get_db] = override_get_db

    connection: dict[str, str] = {
        "host": "localhost",
        "port": "5432",
        "database": "graphtrace",
        "username": "postgres",
        "password": "secret",
    }
    payload: dict[str, object] = {
        "name": "pytest_ds",
        "type": "postgres",
        "connection": connection,
        "description": "test",
        "status": "disconnected",
    }

    with TestClient(app) as client:
        created = client.post("/api/data-sources/", json=payload)
        assert created.status_code == 200, created.text
        created_json = created.json()
        created_data = created_json.get("data") or created_json

        assert created_data["connection"].get("password") is None

        listed = client.get("/api/data-sources/")
        assert listed.status_code == 200, listed.text
        items = listed.json()
        assert len(items) == 1
        assert items[0]["connection"].get("password") is None

        # Update without re-sending the password (masked value) should preserve stored secret
        source_id = items[0]["id"]
        update_payload = {
            "id": source_id,
            "name": payload["name"],
            "type": payload["type"],
            "description": payload["description"],
            "status": payload["status"],
            "connection": {
                "host": connection["host"],
                "port": connection["port"],
                "database": connection["database"],
                "username": connection["username"],
                "password": "***",
            },
        }
        updated = client.put(f"/api/data-sources/{source_id}", json=update_payload)
        assert updated.status_code == 200, updated.text

        # Verify DB still contains original secret
        from core.crypto import decrypt_json
        db = SessionLocal()
        try:
            row = db.get(DataSourceConfigRecord, source_id)
            assert row is not None
            conn = decrypt_json(row.connection_ciphertext)
            assert conn.get("password") == "secret"
        finally:
            db.close()
