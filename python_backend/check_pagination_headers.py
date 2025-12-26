import json
import os
import sys
import urllib.error
import urllib.request


def _get_timeout_seconds() -> float:
    raw = os.environ.get("PAGINATION_CHECK_TIMEOUT", "2")
    try:
        value = float(raw)
    except ValueError:
        return 2.0
    return max(0.5, value)


def _urlopen(req: urllib.request.Request, timeout: float):
    return urllib.request.urlopen(req, timeout=timeout)  # noqa: S310


def _check_backend_up(base: str, timeout: float) -> bool:
    url = base + "/health"
    req = urllib.request.Request(url, method="GET")
    try:
        with _urlopen(req, timeout=timeout) as resp:
            return 200 <= getattr(resp, "status", 0) < 500
    except (urllib.error.URLError, TimeoutError, ValueError):
        return False


def main() -> None:
    base = "http://127.0.0.1:8000"
    timeout = _get_timeout_seconds()

    if not _check_backend_up(base, timeout=timeout):
        print(f"Backend not reachable at {base} (try starting the backend server).")
        sys.exit(2)

    checks = [
        ("GET", "/api/gateway/apigee/proxies?skip=0&limit=1", None),
        ("GET", "/api/data-mapping/rules?skip=0&limit=1", None),
        ("GET", "/api/data-mapping/templates?skip=0&limit=1", None),
        ("GET", "/api/_data-sources/?skip=0&limit=1", None),
        ("GET", "/api/agentic/agents?skip=0&limit=1", None),
        ("GET", "/api/agentic/agents/active?skip=0&limit=1", None),
        ("GET", "/api/analytics/nodes?skip=0&limit=1", None),
        ("GET", "/api/mappings/templates?skip=0&limit=1", None),
        ("GET", "/api/migration/plans?skip=0&limit=1", None),
        ("GET", "/api/mappings?skip=0&limit=1", None),
        ("GET", "/api/data-quality/rules?skip=0&limit=1", None),
        ("GET", "/api/target-apps?skip=0&limit=1", None),
        ("GET", "/api/export/history?skip=0&limit=1", None),
        ("GET", "/api/schema/properties?skip=0&limit=1", None),

        # Newly standardized endpoints (no Kong)
        ("GET", "/api/workflows/templates/list?skip=0&limit=1", None),
        ("GET", "/api/neo4j-graphrag/tools?skip=0&limit=1", None),
        ("POST", "/api/filesystem/list?skip=0&limit=1", {"path": ".", "recursive": False}),

        ("GET", "/api/self-healing/circuit-breakers?skip=0&limit=1", None),
        ("GET", "/api/self-healing/dead-letter-queue?skip=0&limit=1", None),
        ("GET", "/api/entities?skip=0&limit=1", None),
    ]

    try:
        for method, path, body in checks:
            url = base + path
            data = None
            headers = {}
            if body is not None:
                data = json.dumps(body).encode("utf-8")
                headers["Content-Type"] = "application/json"

            req = urllib.request.Request(url, data=data, headers=headers, method=method)
            try:
                with _urlopen(req, timeout=timeout) as resp:
                    header = resp.headers.get("X-Total-Count")
                    print(f"{method} {path} -> X-Total-Count={header}")
            except (urllib.error.URLError, TimeoutError, ValueError) as exc:
                print(f"{method} {path} -> ERROR: {exc}")
    except KeyboardInterrupt:
        print("Interrupted.")
        sys.exit(130)


if __name__ == "__main__":
    main()
