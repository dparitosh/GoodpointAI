import pytest
from fastapi import FastAPI
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from starlette.testclient import TestClient

from core.database import Base
from models.workflow_models import WorkflowInstance


@pytest.mark.filterwarnings("ignore:.*asyncio_default_fixture_loop_scope.*:pytest.PytestDeprecationWarning")
def test_workflow_persists_via_db(tmp_path) -> None:
    """Ensure workflows survive in-memory store resets via DB persistence."""

    # Isolated SQLite DB per test.
    db_path = tmp_path / "test_app.db"
    engine = create_engine(
        f"sqlite:///{db_path.as_posix()}",
        connect_args={"check_same_thread": False},
        pool_pre_ping=True,
    )
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    # Ensure all ORM models are registered on Base.metadata.
    import models.graphql_models  # noqa: F401
    import models.workflow_models  # noqa: F401

    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    import graph_api.workflow_manager_router as wmr

    # Start from a clean in-memory state.
    wmr.WORKFLOWS_STORE.clear()

    app = FastAPI()
    app.include_router(wmr.router)
    app.dependency_overrides[wmr.get_db] = override_get_db

    payload = {
        "name": "Test Workflow",
        "description": "Persist me",
        "source": {
            "id": "src_001",
            "name": "Source",
            "type": "teamcenter",
            "connection_details": {},
            "extraction_config": {},
        },
        "target": {
            "id": "tgt_001",
            "name": "Target",
            "type": "neo4j",
            "connection_details": {},
            "load_config": {},
        },
        "workflow_config": {"nodes": [], "edges": [], "ai_agents": []},
        "ai_agents_enabled": [],
        "schedule_enabled": False,
        "schedule_cron": None,
        "created_by": "pytest",
    }

    with TestClient(app) as client:
        created = client.post("/api/workflows/", json=payload)
        assert created.status_code == 201, created.text
        workflow_id = created.json()["id"]

        # Verify it was persisted in the DB.
        db = SessionLocal()
        try:
            row = db.query(WorkflowInstance).filter(WorkflowInstance.id == workflow_id).first()
            assert row is not None
        finally:
            db.close()

        # Simulate a restart of the in-memory store.
        wmr.WORKFLOWS_STORE.clear()

        fetched = client.get(f"/api/workflows/{workflow_id}")
        assert fetched.status_code == 200, fetched.text
        assert fetched.json()["id"] == workflow_id

        listed = client.get("/api/workflows/")
        assert listed.status_code == 200
        assert any(item["id"] == workflow_id for item in listed.json())
