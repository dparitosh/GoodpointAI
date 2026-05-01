"""MCP cluster diagnostics.

Checks every component of the agentic stack, prints a root-cause sentence for
each failure, and lists the exact recovery steps.

Run from repo root:
    python -m scripts.diagnose_mcp            (inside python_backend/)
    python python_backend/scripts/diagnose_mcp.py
"""

from __future__ import annotations

import asyncio
import io
import json
import os
import socket
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Force UTF-8 on stdout/stderr so Unicode characters work correctly in
# PowerShell 5, cmd.exe, and any terminal using a legacy code page (cp1252 etc.).
if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "buffer"):
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import httpx

# -- repo paths ----------------------------------------------------------------
_SCRIPT_DIR = Path(__file__).resolve().parent
_BACKEND_DIR = _SCRIPT_DIR.parent
_REPO_ROOT = _BACKEND_DIR.parent

if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# -- load .env early so DATABASE_URL etc. are visible --------------------------
os.environ.setdefault("GRAPH_TRACE_LOAD_DOTENV", "true")
_env_file = _BACKEND_DIR / ".env"
if _env_file.exists():
    try:
        from dotenv import load_dotenv
        load_dotenv(dotenv_path=_env_file, override=False)
    except ImportError:
        for _raw in _env_file.read_text(encoding="utf-8").splitlines():
            _line = _raw.strip()
            if not _line or _line.startswith("#") or "=" not in _line:
                continue
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip().strip('"').strip("'"))

# -- port / service map --------------------------------------------------------
MCP_SERVER_PORT = int(os.getenv("MCP_SERVER_PORT", "8012"))
BACKEND_PORT    = int(os.getenv("BACKEND_PORT", "8011"))
REDIS_URL       = os.getenv("REDIS_URL", "redis://localhost:6379/0")
AZURE_SB_CONN   = os.getenv("AZURE_SERVICE_BUS_CONNECTION_STRING", "")

AGENT_PORTS: Dict[str, int] = {
    "data_analyst":        8020,
    "etl_orchestrator":    8021,
    "visualization_agent": 8022,
    "query_planner":       8023,
    "quality_monitor":     8024,
    "chat_coordinator":    8025,
    "data_discovery":      8026,
    "task_decomposer":     8027,
}

TIMEOUT = 3.0  # seconds per probe


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------

class Result:
    def __init__(self, ok: bool, label: str, root_cause: str = "", steps: Optional[List[str]] = None):
        self.ok = ok
        self.label = label
        self.root_cause = root_cause
        self.steps: List[str] = steps or []

    def print(self) -> None:
        icon = "\033[92m[OK]\033[0m   " if self.ok else "\033[91m[FAIL]\033[0m "
        print(f"  {icon} {self.label}")
        if not self.ok:
            if self.root_cause:
                print(f"         \033[93mCause:\033[0m  {self.root_cause}")
            for step in self.steps:
                print(f"         \033[96mFix:\033[0m    {step}")


def _tcp_open(host: str, port: int, timeout: float = TIMEOUT) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


async def _http_get(url: str, timeout: float = TIMEOUT) -> Tuple[bool, Any]:
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await client.get(url)
            return r.status_code < 400, r.json() if r.headers.get("content-type", "").startswith("application/json") else r.text
    except Exception as exc:
        return False, str(exc)


# -----------------------------------------------------------------------------
# Individual checks
# -----------------------------------------------------------------------------

def check_venv() -> Result:
    """Warn if not running inside the project venv."""
    exe = sys.executable
    venv_dir = str(_REPO_ROOT / ".venv")
    ok = exe.startswith(venv_dir) or "venv" in exe.lower() or "virtualenv" in exe.lower()
    if ok:
        return Result(True, f"Python interpreter: {exe}")
    return Result(
        False,
        f"Python interpreter: {exe}",
        root_cause="System Python is active, not the project venv. "
                   "SQLAlchemy / mcp / agent deps may be missing.",
        steps=[
            rf"Activate venv:  {_REPO_ROOT}\\.venv\\Scripts\\Activate.ps1",
            "Then re-run this script.",
        ],
    )


def check_required_packages() -> List[Result]:
    results: List[Result] = []
    packages = {
        "fastapi":    ("fastapi", "pip install fastapi==0.115.0"),
        "uvicorn":    ("uvicorn", "pip install uvicorn[standard]==0.32.0"),
        "httpx":      ("httpx",   "pip install httpx==0.27.2"),
        "sqlalchemy": ("sqlalchemy", "pip install sqlalchemy==2.0.35"),
        "pydantic":   ("pydantic", "pip install pydantic==2.9.2"),
        "mcp":        ("mcp",     "pip install 'mcp[cli]>=1.2.0,<2.0.0'"),
        "redis":      ("redis",   "pip install redis==5.1.1"),
    }
    for display, (mod, fix_cmd) in packages.items():
        try:
            __import__(mod)
            results.append(Result(True, f"Package present: {display}"))
        except ImportError:
            results.append(Result(
                False,
                f"Package missing: {display}",
                root_cause=f"'{mod}' is not installed in the active Python environment ({sys.executable}).",
                steps=[
                    f"Run:  {fix_cmd}",
                    f"Or:   pip install -r {_REPO_ROOT / 'requirements.txt'}",
                ],
            ))
    return results


def check_env_vars() -> List[Result]:
    results: List[Result] = []

    db_url = (os.getenv("DATABASE_URL") or "").strip()
    if not db_url:
        results.append(Result(
            False, "Env: DATABASE_URL",
            root_cause="DATABASE_URL is not set. Backend and MCP server cannot connect to Postgres.",
            steps=[
                f"Edit  {_BACKEND_DIR / '.env'}",
                "Set DATABASE_URL=postgresql+psycopg://postgres:<password>@127.0.0.1:5432/graphtrace",
            ],
        ))
    elif "yourpassword" in db_url or ":password@" in db_url:
        results.append(Result(
            False, "Env: DATABASE_URL",
            root_cause="DATABASE_URL still contains placeholder credentials.",
            steps=[f"Edit  {_BACKEND_DIR / '.env'}  and replace the placeholder password."],
        ))
    else:
        results.append(Result(True, f"Env: DATABASE_URL = ...{db_url[-20:]}"))

    enc_key = (os.getenv("GRAPH_TRACE_CONFIG_ENCRYPTION_KEY") or "").strip()
    if not enc_key:
        results.append(Result(
            False, "Env: GRAPH_TRACE_CONFIG_ENCRYPTION_KEY",
            root_cause="Encryption key missing  -  DB-backed config cannot be decrypted on startup.",
            steps=[
                "Run:  python -m scripts.init_db_schema   (auto-generates a key)",
                f"Or add GRAPH_TRACE_CONFIG_ENCRYPTION_KEY=<base64-key> to  {_BACKEND_DIR / '.env'}",
            ],
        ))
    else:
        results.append(Result(True, "Env: GRAPH_TRACE_CONFIG_ENCRYPTION_KEY is set"))

    mcp_url = os.getenv("MCP_SERVER_URL", f"http://localhost:{MCP_SERVER_PORT}")
    results.append(Result(True, f"Env: MCP_SERVER_URL = {mcp_url}  (default OK)"))

    if AZURE_SB_CONN:
        results.append(Result(True, "Env: AZURE_SERVICE_BUS_CONNECTION_STRING is set (queue enabled)"))
    else:
        results.append(Result(
            True,
            "Env: AZURE_SERVICE_BUS_CONNECTION_STRING not set (in-memory queue fallback  -  OK for local dev)",
        ))

    return results


async def check_backend() -> Result:
    ok, data = await _http_get(f"http://localhost:{BACKEND_PORT}/health")
    if not _tcp_open("localhost", BACKEND_PORT):
        return Result(
            False, f"Backend unreachable  (port {BACKEND_PORT})",
            root_cause="Port is closed  -  the backend process is not running or crashed on startup.",
            steps=[
                f"Start manually:  cd {_BACKEND_DIR} && python -m uvicorn main:app --port {BACKEND_PORT}",
                "Check for import errors in the terminal output.",
                "Verify all packages are installed:  pip install -r requirements.txt",
                "Run the DB init script first:  python -m scripts.init_db_schema",
            ],
        )
    if not isinstance(data, dict):
        return Result(True, f"Backend /health  (port {BACKEND_PORT})  [non-JSON response]")

    deps = data.get("dependencies", {})
    postgres_ok = deps.get("postgres", {}).get("ok", True) if isinstance(deps, dict) else True
    mcp_only_degraded = (
        data.get("status") == "degraded"
        and not postgres_ok is False
        and isinstance(deps, dict)
        and not deps.get("postgres", {}).get("ok") is False
    )

    if not postgres_ok:
        return Result(
            False, f"Backend /health  -  Postgres dependency down  (port {BACKEND_PORT})",
            root_cause="Backend reports postgres=false. DB may be down or DATABASE_URL is wrong.",
            steps=[
                "Start Postgres and verify DATABASE_URL in python_backend/.env.",
                "Run:  python -m scripts.diagnose_db_config",
            ],
        )

    # Degraded only because MCP is not running  -  that is reported separately in section 3.
    if data.get("status") in ("degraded", "healthy") or ok:
        suffix = "  (MCP down  -  see section 3)" if data.get("status") == "degraded" else ""
        return Result(True, f"Backend /health  (port {BACKEND_PORT}){suffix}")

    return Result(
        False, f"Backend /health returned error  (port {BACKEND_PORT})",
        root_cause=f"Backend is listening but /health returned an unexpected status: {data.get('status')}",
        steps=[
            "Check backend logs for startup exceptions.",
            "Run:  python -m scripts.diagnose_db_config",
        ],
    )


async def check_mcp_server() -> Result:
    ok, data = await _http_get(f"http://localhost:{MCP_SERVER_PORT}/health")
    if ok:
        return Result(True, f"MCP Server /health  (port {MCP_SERVER_PORT})")
    if not _tcp_open("localhost", MCP_SERVER_PORT):
        return Result(
            False, f"MCP Server unreachable  (port {MCP_SERVER_PORT})",
            root_cause="MCP server process is not running. Agentic discovery/quality-scan calls "
                       "will 503 (backend falls back to direct scan where possible).",
            steps=[
                f"Start MCP server:  cd {_REPO_ROOT} && python -m uvicorn mcp_server.main:app --port {MCP_SERVER_PORT}",
                "Or start the full stack:  python scripts/start.py",
                "Ensure azure-servicebus is installed if AZURE_SERVICE_BUS_CONNECTION_STRING is set.",
            ],
        )
    return Result(
        False, f"MCP Server /health returned error  (port {MCP_SERVER_PORT})",
        root_cause=f"MCP server is listening but /health failed: {data}",
        steps=[
            "Check MCP server logs for startup exceptions.",
            "Common cause: Redis unreachable  -  MCP falls back to in-memory, but may log errors.",
            "Verify NEO4J_URI / NEO4J_PASSWORD in .env if Neo4j is configured.",
        ],
    )


async def check_redis() -> Result:
    host = "localhost"
    port = 6379
    try:
        import redis.asyncio as redis_async
        r: Any = redis_async.from_url(REDIS_URL, socket_connect_timeout=TIMEOUT)
        await r.ping()
        await r.aclose()
        return Result(True, f"Redis  ({REDIS_URL})")
    except Exception as exc:
        msg = str(exc)
        if not _tcp_open(host, port):
            return Result(
                False, f"Redis unreachable  ({REDIS_URL})",
                root_cause="Redis is not running. MCP StateManager falls back to in-memory storage "
                           "(task state is lost on restart; no impact for stateless single-node dev).",
                steps=[
                    "Optional for local dev  -  MCP works without Redis.",
                    "To enable: start Redis  (docker run -p 6379:6379 redis:alpine).",
                    f"Or set REDIS_URL=  in  {_BACKEND_DIR / '.env'}  to suppress the warning.",
                ],
            )
        return Result(
            False, f"Redis error  ({REDIS_URL}): {msg}",
            root_cause="Redis is reachable but ping failed.",
            steps=["Check Redis authentication / TLS config.", f"REDIS_URL in .env: {REDIS_URL}"],
        )


async def check_agents() -> List[Result]:
    results: List[Result] = []
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        for name, port in AGENT_PORTS.items():
            url = f"http://localhost:{port}/health"
            try:
                r = await client.get(url)
                ok = r.status_code < 400
                if ok:
                    results.append(Result(True, f"Agent [{name}]  (port {port})"))
                else:
                    results.append(Result(
                        False, f"Agent [{name}]  (port {port})",
                        root_cause=f"/health returned HTTP {r.status_code}.",
                        steps=[
                            f"Restart:  python -m agent_services.{name}.main",
                            "Check agent logs for import or startup errors.",
                        ],
                    ))
            except Exception:
                if _tcp_open("localhost", port, timeout=1.0):
                    results.append(Result(
                        False, f"Agent [{name}]  (port {port})",
                        root_cause="Port open but /health did not respond in time.",
                        steps=[f"Restart:  python -m agent_services.{name}.main"],
                    ))
                else:
                    results.append(Result(
                        False, f"Agent [{name}] not running  (port {port})",
                        root_cause=f"Process not started. Tasks requiring '{name}' capabilities "
                                   "will be routed to other registered agents or fail with 503.",
                        steps=[
                            f"Start:  cd {_REPO_ROOT} && python -m agent_services.{name}.main",
                            "Or start full cluster:  python scripts/start.py",
                        ],
                    ))
    return results


async def check_mcp_registered_agents() -> Result:
    """Ask the MCP server which agents are currently registered."""
    ok, data = await _http_get(f"http://localhost:{MCP_SERVER_PORT}/agents")
    if not ok:
        if not _tcp_open("localhost", MCP_SERVER_PORT):
            return Result(False, "MCP agent registry  (skipped  -  MCP server not running)")
        return Result(
            False, "MCP agent registry",
            root_cause=f"Could not reach /agents endpoint: {data}",
            steps=["Ensure MCP server is running and healthy."],
        )
    count = len(data) if isinstance(data, list) else (len(data.get("agents", [])) if isinstance(data, dict) else 0)
    if count == 0:
        return Result(
            False, "MCP agent registry: 0 agents registered",
            root_cause="No agents have registered with the MCP server. "
                       "Task routing will fail for all capability-based requests.",
            steps=[
                "Start agent services:  python scripts/start.py",
                "Or individually:  python -m agent_services.<name>.main  for each agent.",
                f"Agents self-register at startup by POSTing to http://localhost:{MCP_SERVER_PORT}/agents/register.",
            ],
        )
    return Result(True, f"MCP agent registry: {count} agent(s) registered")


# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------

async def _run_all() -> int:
    print("\n\033[1m================================================\033[0m")
    print("\033[1m   GraphTrace MCP Cluster Diagnostics\033[0m")
    print("\033[1m================================================\033[0m\n")

    all_results: List[Result] = []

    # 1. Python / venv
    print("\033[1m[1] Python Environment\033[0m")
    r = check_venv()
    r.print()
    all_results.append(r)
    for r in check_required_packages():
        r.print()
        all_results.append(r)

    # 2. Environment variables
    print("\n\033[1m[2] Environment Variables\033[0m")
    for r in check_env_vars():
        r.print()
        all_results.append(r)

    # 3. Core services
    print("\n\033[1m[3] Core Services\033[0m")
    for coro in [check_backend(), check_mcp_server(), check_redis()]:
        r = await coro
        r.print()
        all_results.append(r)

    # 4. Agent processes
    print("\n\033[1m[4] Agent Services\033[0m")
    for r in await check_agents():
        r.print()
        all_results.append(r)

    # 5. MCP registration
    print("\n\033[1m[5] MCP Agent Registry\033[0m")
    r = await check_mcp_registered_agents()
    r.print()
    all_results.append(r)

    # Summary
    failures = [r for r in all_results if not r.ok]
    print(f"\n{'=' * 48}")
    if not failures:
        print("\033[92m[OK]  All checks passed. MCP cluster is healthy.\033[0m\n")
        return 0

    print(f"\033[91m[FAIL]  {len(failures)} issue(s) found:\033[0m")
    for i, r in enumerate(failures, 1):
        print(f"\n  \033[93m{i}. {r.label}\033[0m")
        if r.root_cause:
            print(f"     Cause:  {r.root_cause}")
        for step in r.steps:
            print(f"     Fix:    {step}")

    print()
    # Summarise what still works
    passing = len(all_results) - len(failures)
    print(f"  {passing}/{len(all_results)} checks passed.")
    print()
    return 1


def main() -> int:
    return asyncio.run(_run_all())


if __name__ == "__main__":
    raise SystemExit(main())
