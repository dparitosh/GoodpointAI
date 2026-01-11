import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


def http_request(method: str, url: str, *, headers: dict[str, str] | None = None, data: bytes | None = None):
    req = urllib.request.Request(url, method=method, headers=headers or {})
    if data is not None:
        req.data = data
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            return resp.status, body
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
        return exc.code, body


def json_request(method: str, url: str, *, headers: dict[str, str] | None = None, payload: object | None = None):
    local_headers = dict(headers or {})
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        local_headers.setdefault("Content-Type", "application/json")
    status, body = http_request(method, url, headers=local_headers, data=data)
    parsed = None
    if body:
        try:
            parsed = json.loads(body)
        except Exception:
            parsed = body
    return status, parsed


def form_request(method: str, url: str, *, form: dict[str, str], headers: dict[str, str] | None = None):
    local_headers = dict(headers or {})
    local_headers.setdefault("Content-Type", "application/x-www-form-urlencoded")
    data = urllib.parse.urlencode(form).encode("utf-8")
    status, body = http_request(method, url, headers=local_headers, data=data)
    parsed = None
    if body:
        try:
            parsed = json.loads(body)
        except Exception:
            parsed = body
    return status, parsed


def build_workflow_payload(name: str):
    return {
        "name": name,
        "description": "verification",
        "source": {
            "id": "src123",
            "name": "Source",
            "type": "teamcenter",
            "connection_details": {},
            "extraction_config": {},
        },
        "target": {
            "id": "tgt123",
            "name": "Target",
            "type": "neo4j",
            "connection_details": {},
            "load_config": {},
        },
        "workflow_config": {"nodes": [], "edges": [], "ai_agents": []},
        "ai_agents_enabled": [],
        "schedule_enabled": False,
        "schedule_cron": None,
        "created_by": "verify",
    }


def verify_auth(base_url: str):
    results: dict[str, object] = {"base_url": base_url}

    # allowlisted
    s, _ = json_request("GET", f"{base_url}/api/status")
    results["allowlisted_/api/status"] = s

    # protected unauth
    s, body = json_request("GET", f"{base_url}/api/workflows/")
    results["protected_/api/workflows_unauth"] = s
    results["protected_unauth_body"] = body

    # token
    admin_user = os.getenv("GRAPH_TRACE_ADMIN_USERNAME", "admin")
    admin_pass = os.getenv("GRAPH_TRACE_ADMIN_PASSWORD", "admin")
    s, token_body = form_request(
        "POST",
        f"{base_url}/api/auth/token",
        form={"username": admin_user, "password": admin_pass},
    )
    results["token_status"] = s
    results["token_body"] = token_body
    token = token_body.get("access_token") if isinstance(token_body, dict) else None
    results["token_present"] = bool(token)

    # protected auth
    if token:
        s, _ = json_request("GET", f"{base_url}/api/workflows/", headers={"Authorization": f"Bearer {token}"})
        results["protected_/api/workflows_auth"] = s

        # non-admin token should 403 on POST (mutating)
        try:
            from core.auth import create_access_token

            user_token = create_access_token(subject="bob", roles=["user"], expires_in_minutes=5)
            s, _ = json_request(
                "POST",
                f"{base_url}/api/workflows/",
                headers={"Authorization": f"Bearer {user_token}"},
                payload=build_workflow_payload("rbac-nonadmin-should-fail"),
            )
            results["nonadmin_post_status"] = s
        except Exception as exc:
            results["nonadmin_post_status"] = f"error: {exc}"

    return results, token


def verify_saga_compensation(base_url: str, *, token: str | None = None):
    """Verify saga compensation via concurrency-based failure.

    Run the backend with `MIGRATION_MAX_CONCURRENT_SESSIONS=1`.
    Start workflow A (should go running), then immediately start workflow B.
    Workflow B should fail with 429, and should not be left in RUNNING state.
    """

    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    # create and start workflow A
    s_a, wf_a = json_request("POST", f"{base_url}/api/workflows/", headers=headers, payload=build_workflow_payload("saga-test-a"))
    if s_a != 201 or not isinstance(wf_a, dict) or "id" not in wf_a:
        return {"create_a_status": s_a, "create_a_body": wf_a}
    workflow_a_id = str(wf_a["id"])

    s_a_start, start_a_body = json_request(
        "POST",
        f"{base_url}/api/workflows/{workflow_a_id}/execute",
        headers=headers,
        payload={"action": "start", "execution_params": {}},
    )

    # create and attempt to start workflow B (expected 429)
    s_b, wf_b = json_request("POST", f"{base_url}/api/workflows/", headers=headers, payload=build_workflow_payload("saga-test-b"))
    if s_b != 201 or not isinstance(wf_b, dict) or "id" not in wf_b:
        return {"create_b_status": s_b, "create_b_body": wf_b}
    workflow_b_id = str(wf_b["id"])

    s_b_start, start_b_body = json_request(
        "POST",
        f"{base_url}/api/workflows/{workflow_b_id}/execute",
        headers=headers,
        payload={"action": "start", "execution_params": {}},
    )

    time.sleep(0.2)

    s_b_get, wf_b_get = json_request("GET", f"{base_url}/api/workflows/{workflow_b_id}", headers=headers)
    status_b = wf_b_get.get("status") if isinstance(wf_b_get, dict) else None

    return {
        "workflow_a_id": workflow_a_id,
        "start_a_status": s_a_start,
        "start_a_body": start_a_body,
        "workflow_b_id": workflow_b_id,
        "start_b_status": s_b_start,
        "start_b_body": start_b_body,
        "get_b_after_start_status": s_b_get,
        "status_b_after_start_attempt": status_b,
    }


def main():
    base = os.getenv("VERIFY_BASE_URL", "http://127.0.0.1:8011").rstrip("/")

    auth_results, admin_token = verify_auth(base)
    out = {"auth": auth_results}

    # Optional saga verification (expects backend started with MIGRATION_MAX_CONCURRENT_SESSIONS=0)
    saga_base = os.getenv("VERIFY_SAGA_BASE_URL")
    if saga_base:
        saga_base = saga_base.rstrip("/")
        out["saga"] = verify_saga_compensation(saga_base, token=admin_token)

    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    sys.exit(main())
