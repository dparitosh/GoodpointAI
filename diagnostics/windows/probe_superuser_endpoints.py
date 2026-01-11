import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[2] / "python_backend"
sys.path.insert(0, str(BACKEND_DIR))

from main import app  # noqa: E402
from starlette.testclient import TestClient  # noqa: E402


def main() -> None:
    client = TestClient(app)

    paths = [
        ("GET", "/api/data-sources"),
        ("GET", "/api/data-sources/"),
        ("GET", "/api/data-mapping/rules"),
        ("GET", "/api/data-mapping/templates"),
        ("GET", "/api/entities"),
        ("GET", "/api/analytics/quality/reports"),
        ("GET", "/api/reports"),
    ]

    for method, path in paths:
        resp = client.request(method, path)
        print(f"{method} {path} -> {resp.status_code}")
        if path.startswith("/api/reports") and resp.status_code != 200:
            try:
                print("  ", resp.json())
            except Exception:
                print("  ", resp.text[:250])


if __name__ == "__main__":
    main()
