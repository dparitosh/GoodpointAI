import pytest
from fastapi import FastAPI
from sqlalchemy.orm import sessionmaker
from starlette.testclient import TestClient

from core.database import Base
from models.report_models import PersistedReport

from test_db_utils import create_postgres_test_engine


@pytest.mark.filterwarnings("ignore:.*PydanticDeprecatedSince20.*")
def test_mcp_migration_run_lifecycle_and_staging() -> None:
    engine = create_postgres_test_engine()
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    # Register ORM models
    _ = PersistedReport

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    import graph_api.mcp_migration_runs_router as mrr

    app = FastAPI()
    app.include_router(mrr.router)
    app.dependency_overrides[mrr.get_db] = override_get_db

    try:
        client = TestClient(app)
        try:
            # Create run directly in discovery
            created = client.post(
                "/api/migrations/runs",
                json={
                    "workflow_name": "pytest",
                    "source_id": "conn_abc",
                    "target_id": "conn_xyz",
                    "initial_status": "discovery",
                    "options": {"k": "v"},
                },
            )
            assert created.status_code == 200, created.text
            run = created.json()
            run_id = run.get("run_id")
            assert run_id
            assert run.get("status") == "discovery"
            assert isinstance(run.get("history"), list)
            assert len(run["history"]) == 1

        # Invalid transition: discovery -> executing (must go through proposal)
            bad = client.post(
                f"/api/migrations/runs/{run_id}/transition",
                json={"to_status": "executing", "event": "test"},
            )
            assert bad.status_code == 409

        # Valid transitions
            to_proposal = client.post(
                f"/api/migrations/runs/{run_id}/transition",
                json={"to_status": "proposal", "event": "test"},
            )
            assert to_proposal.status_code == 200
            assert to_proposal.json().get("status") == "proposal"

            to_exec = client.post(
                f"/api/migrations/runs/{run_id}/transition",
                json={"to_status": "executing", "event": "test"},
            )
            assert to_exec.status_code == 200
            assert to_exec.json().get("status") == "executing"

        # Staging stores only count + small sample
            staged = client.post(
                f"/api/migrations/runs/{run_id}/stage",
                json={"entity": "parts", "records": [{"i": i} for i in range(20)]},
            )
            assert staged.status_code == 200
            payload = staged.json()
            parts = payload.get("staged", {}).get("parts")
            assert parts["count"] == 20
            assert isinstance(parts.get("sample"), list)
            assert len(parts["sample"]) == 5

        # Materialize requires a Neo4j driver (app.state.driver). In this unit test app,
        # we don't initialize Neo4j, so it should be unavailable.
            mat = client.post(
                f"/api/migrations/runs/{run_id}/materialize",
                json={},
            )
            assert mat.status_code == 503

            done = client.post(
                f"/api/migrations/runs/{run_id}/transition",
                json={"to_status": "completed", "event": "test"},
            )
            assert done.status_code == 200
            assert done.json().get("status") == "completed"

        # Completed is terminal
            terminal = client.post(
                f"/api/migrations/runs/{run_id}/transition",
                json={"to_status": "failed", "event": "test"},
            )
            assert terminal.status_code == 409
        finally:
            client.close()
    finally:
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.mark.filterwarnings("ignore:.*PydanticDeprecatedSince20.*")
def test_mcp_migration_run_approvals_gate_materialize(monkeypatch) -> None:
    monkeypatch.setenv("GRAPH_TRACE_APPROVALS_REQUIRED", "true")

    engine = create_postgres_test_engine()
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    _ = PersistedReport
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    import graph_api.mcp_migration_runs_router as mrr

    app = FastAPI()
    app.include_router(mrr.router)
    app.dependency_overrides[mrr.get_db] = override_get_db

    try:
        client = TestClient(app)
        try:
            created = client.post(
                "/api/migrations/runs",
                json={"workflow_name": "pytest", "initial_status": "discovery"},
            )
            assert created.status_code == 200, created.text
            run_id = created.json().get("run_id")
            assert run_id

            # With approvals enabled, materialize should fail closed before any Neo4j dependency.
            mat = client.post(f"/api/migrations/runs/{run_id}/materialize", json={})
            assert mat.status_code == 403

            # Create + approve an approval request.
            req = client.post(
                f"/api/migrations/runs/{run_id}/approvals",
                json={"action": "materialize", "summary": "allow materialize", "requested_by": "pytest"},
            )
            assert req.status_code == 200, req.text
            approval = req.json()
            approval_id = approval.get("approval_id")
            token = approval.get("token")
            assert approval_id
            assert token

            approved = client.post(
                f"/api/migrations/runs/{run_id}/approvals/{approval_id}/approve",
                json={"decided_by": "pytest"},
            )
            assert approved.status_code == 200, approved.text
            assert approved.json().get("status") == "approved"

            # Now the approval gate should pass, and we should reach the Neo4j dependency (still missing in this test app).
            mat2 = client.post(
                f"/api/migrations/runs/{run_id}/materialize",
                json={},
                headers={"X-MCP-Approval-Token": str(token)},
            )
            assert mat2.status_code == 503
        finally:
            client.close()
    finally:
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.mark.filterwarnings("ignore:.*PydanticDeprecatedSince20.*")
def test_mcp_migration_run_publish_target_rules_and_approvals(monkeypatch) -> None:
    monkeypatch.setenv("GRAPH_TRACE_APPROVALS_REQUIRED", "true")

    engine = create_postgres_test_engine()
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    _ = PersistedReport
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    import graph_api.mcp_migration_runs_router as mrr

    app = FastAPI()
    app.include_router(mrr.router)
    app.dependency_overrides[mrr.get_db] = override_get_db

    try:
        client = TestClient(app)
        try:
            # Publish is only supported for OpenSearch targets.
            created = client.post(
                "/api/migrations/runs",
                json={"workflow_name": "pytest", "initial_status": "discovery", "target_id": "conn_xyz"},
            )
            assert created.status_code == 200, created.text
            run_id = created.json().get("run_id")
            assert run_id

            unsupported = client.post(f"/api/migrations/runs/{run_id}/publish", json={})
            assert unsupported.status_code == 409

            # Now create a run with an OpenSearch-looking target id.
            created2 = client.post(
                "/api/migrations/runs",
                json={
                    "workflow_name": "pytest",
                    "initial_status": "discovery",
                    "target_id": "conn_opensearch_primary",
                },
            )
            assert created2.status_code == 200, created2.text
            run2 = created2.json()
            run2_id = run2.get("run_id")
            assert run2_id

            # Stage at least one sample record so publish has something to index.
            staged = client.post(
                f"/api/migrations/runs/{run2_id}/stage",
                json={"entity": "Part", "records": [{"id": "p1", "name": "Widget"}]},
            )
            assert staged.status_code == 200, staged.text

            # With approvals enabled, publish should fail closed before OpenSearch/Neo4j checks.
            pub = client.post(f"/api/migrations/runs/{run2_id}/publish", json={})
            assert pub.status_code == 403

            # Create + approve an approval request for publish.
            req = client.post(
                f"/api/migrations/runs/{run2_id}/approvals",
                json={"action": "publish", "summary": "allow publish", "requested_by": "pytest"},
            )
            assert req.status_code == 200, req.text
            approval = req.json()
            approval_id = approval.get("approval_id")
            token = approval.get("token")
            assert approval_id
            assert token

            approved = client.post(
                f"/api/migrations/runs/{run2_id}/approvals/{approval_id}/approve",
                json={"decided_by": "pytest"},
            )
            assert approved.status_code == 200, approved.text
            assert approved.json().get("status") == "approved"

            # After approval, we should progress into runtime dependency checks.
            # In this unit test app, OpenSearch isn't configured, so publish should return 503.
            pub2 = client.post(
                f"/api/migrations/runs/{run2_id}/publish",
                json={},
                headers={"X-MCP-Approval-Token": str(token)},
            )
            assert pub2.status_code == 503
        finally:
            client.close()
    finally:
        Base.metadata.drop_all(bind=engine)
        engine.dispose()
