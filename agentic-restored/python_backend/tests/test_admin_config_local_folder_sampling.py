import json

import pytest
from fastapi import FastAPI
from sqlalchemy.orm import sessionmaker
from starlette.testclient import TestClient

from core.database import Base

from test_db_utils import create_postgres_test_engine


@pytest.mark.filterwarnings("ignore:.*PydanticDeprecatedSince20.*")
def test_admin_config_local_folder_conn_can_be_sampled(tmp_path, monkeypatch) -> None:
    # Keep encryption available if any code path touches encrypt/decrypt helpers.
    monkeypatch.setenv("GRAPH_TRACE_CONFIG_ENCRYPTION_KEY", "test-key-should-be-32-bytes-minimum")

    # Allowlist the temporary folder for filesystem reads.
    monkeypatch.setenv("GRAPH_TRACE_ALLOWED_LOCAL_ROOTS", str(tmp_path))

    # Prepare a deterministic sample file.
    sample_path = tmp_path / "sample.json"
    sample_path.write_text(json.dumps([{"a": 1}, {"a": 2}]), encoding="utf-8")

    engine = create_postgres_test_engine()
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    # Register ORM models and create tables.
    from models.configuration_models import DataSourceConfigRecord
    from models.admin_config_models import ConnectionConfig

    _ = DataSourceConfigRecord

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    # Seed an Admin Config connection that points at the local folder.
    db = SessionLocal()
    try:
        db.add(
            ConnectionConfig(
                id="local_test",
                connection_type="local_folder",
                name="Local Import Folder",
                description="pytest",
                extra_options={"folder_path": str(tmp_path), "file_name": "sample.json"},
                status="active",
                is_default=False,
            )
        )
        db.commit()
    finally:
        db.close()

    def override_get_db():
        db2 = SessionLocal()
        try:
            yield db2
        finally:
            db2.close()

    import graph_api.data_sources_router as dsr

    app = FastAPI()
    app.include_router(dsr.router)
    app.dependency_overrides[dsr.get_db] = override_get_db

    try:
        with TestClient(app) as client:
            listed = client.get("/api/data-sources/")
            assert listed.status_code == 200, listed.text
            items = listed.json()

            conn_items = [x for x in items if x.get("id") == "conn_local_test"]
            assert conn_items, f"Expected conn_local_test in data sources, got ids={[x.get('id') for x in items]}"
            assert conn_items[0]["type"] == "local_folder"
            assert conn_items[0]["connection"].get("folder_path") == str(tmp_path)

            sampled = client.get("/api/data-sources/conn_local_test/sample?limit=10")
            assert sampled.status_code == 200, sampled.text
            payload = sampled.json()
            assert payload["source_id"] == "conn_local_test"
            assert payload["source_type"] == "local_folder"
            assert payload["format"] == "json"
            assert payload["count"] == 2
            assert payload["records"][0].get("a") == 1

            # If the allowlist is removed, sampling should be denied.
            monkeypatch.setenv("GRAPH_TRACE_ALLOWED_LOCAL_ROOTS", "")
            denied = client.get("/api/data-sources/conn_local_test/sample?limit=10")
            assert denied.status_code == 403, denied.text
    finally:
        Base.metadata.drop_all(bind=engine)
        engine.dispose()
