# pyright: reportMissingImports=false

"""Audit frontend-to-backend wiring.

Generates a report for:
- Frontend referenced /api endpoints (string literals + API_CONFIG.ENDPOINTS.* references)
- Backend registered routes (imports FastAPI app)
- Mismatches (frontend references missing in backend)
- Frontend navigation targets not defined in router

Run from repo root (or anywhere):
  python agentic-restored/diagnostics/windows/audit_frontend_backend.py

Notes:
- This is a best-effort static scan; dynamic endpoint construction may not be detected.
"""

from __future__ import annotations

import json
import re
import sys
import importlib.util
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


REPO_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_SRC = REPO_ROOT / "e2etraceapp" / "src"
BACKEND_ROOT = REPO_ROOT / "python_backend"
REPORT_PATH = REPO_ROOT / "diagnostics" / "windows" / "audit_frontend_backend_report.md"


@dataclass(frozen=True)
class BackendRoute:
    path: str
    methods: tuple[str, ...]


def _iter_source_files(root: Path) -> Iterable[Path]:
    for ext in ("*.js", "*.jsx", "*.ts", "*.tsx"):
        yield from root.rglob(ext)


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _normalize_api_path(p: str) -> str:
    # strip scheme/host if present
    p = re.sub(r"^https?://[^/]+", "", p)
    # strip query/hash
    p = p.split("?", 1)[0].split("#", 1)[0]
    # normalize multiple slashes
    p = re.sub(r"//+", "/", p)
    # ensure leading slash
    if not p.startswith("/"):
        p = "/" + p
    # normalize template literals placeholders -> {param}
    p = re.sub(r"\$\{[^}]+\}", "{param}", p)
    # normalize path parameters -> {param} (FastAPI uses {name})
    p = re.sub(r"\{[^}]+\}", "{param}", p)
    return p


def _extract_string_api_paths(text: str) -> set[str]:
    # Match '/api/..' or "/api/.." or `.../api/...`
    # Keep it conservative; avoid swallowing whitespace/newlines.
    pattern = re.compile(r"(?P<q>['\"`])(?P<path>/api/[^'\"`\s]+)(?P=q)")
    return {_normalize_api_path(m.group("path")) for m in pattern.finditer(text)}


def _parse_api_config_endpoints(api_config_text: str) -> dict[str, str]:
    """Best-effort parse of API_CONFIG.ENDPOINTS keys -> path pattern.

    Handles:
      KEY: '/api/foo'
      KEY: (id) => `/api/foo/${id}/bar`
    """

    # Locate the ENDPOINTS: { ... } block by brace counting
    m = re.search(r"\bENDPOINTS\s*:\s*\{", api_config_text)
    if not m:
        return {}

    i = m.end()  # position after '{'
    depth = 1
    block_chars: list[str] = []
    while i < len(api_config_text) and depth > 0:
        ch = api_config_text[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                break
        block_chars.append(ch)
        i += 1

    block = "".join(block_chars)

    endpoints: dict[str, str] = {}

    # Simple string entries
    for km in re.finditer(r"\b([A-Z0-9_]+)\s*:\s*(['\"])(/api/[^'\"\n]+)\2", block):
        key = km.group(1)
        endpoints[key] = _normalize_api_path(km.group(3))

    # Arrow functions returning template literals or strings
    for km in re.finditer(
        r"\b([A-Z0-9_]+)\s*:\s*\([^)]*\)\s*=>\s*(?P<q>['\"`])(?P<val>/api/[^'\"`\n]+)(?P=q)",
        block,
    ):
        key = km.group(1)
        endpoints[key] = _normalize_api_path(km.group("val"))

    return endpoints


def _extract_endpoint_key_references(text: str) -> set[str]:
    # Match API_CONFIG.ENDPOINTS.KEY and ENDPOINTS.KEY
    pattern = re.compile(r"\b(?:API_CONFIG\.)?ENDPOINTS\.([A-Z0-9_]+)\b")
    return {m.group(1) for m in pattern.finditer(text)}


def _extract_frontend_api_paths() -> tuple[set[str], dict[str, set[str]]]:
    api_config_path = FRONTEND_SRC / "config" / "api-config.js"
    api_config_text = _read_text(api_config_path)
    endpoints_map = _parse_api_config_endpoints(api_config_text)

    found: set[str] = set()
    provenance: dict[str, set[str]] = {}

    def add(path: str, src: Path) -> None:
        found.add(path)
        provenance.setdefault(path, set()).add(str(src.relative_to(REPO_ROOT)))

    for file_path in _iter_source_files(FRONTEND_SRC):
        # Avoid treating config constants as "used" endpoints
        if file_path == api_config_path:
            continue

        text = _read_text(file_path)

        for p in _extract_string_api_paths(text):
            add(p, file_path)

        keys = _extract_endpoint_key_references(text)
        for key in keys:
            endpoint_path = endpoints_map.get(key)
            if endpoint_path:
                add(endpoint_path, file_path)

    return found, provenance


def _extract_router_paths() -> set[str]:
    router_path = FRONTEND_SRC / "routes" / "index.jsx"
    text = _read_text(router_path)
    # Very simple parse: path: '...'
    paths = set(re.findall(r"\bpath\s*:\s*['\"]([^'\"]+)['\"]", text))

    # normalize to leading slash (router uses child paths without leading slash)
    normalized: set[str] = set()
    for p in paths:
        if p == "*":
            continue
        if p.startswith("/"):
            normalized.add(p)
        else:
            normalized.add("/" + p)

    # Index route exists at '/'
    normalized.add("/")
    return normalized


def _extract_frontend_nav_targets() -> tuple[set[str], dict[str, set[str]]]:
    targets: set[str] = set()
    provenance: dict[str, set[str]] = {}

    # Matches:
    #   to="/path" / to='/path'
    #   navigate('/path')
    to_prop = re.compile(r"\bto\s*=\s*{?\s*['\"](/[^'\"]+)['\"]\s*}?\b")
    nav_call = re.compile(r"\bnavigate\(\s*['\"](/[^'\"]+)['\"]")

    for file_path in _iter_source_files(FRONTEND_SRC):
        text = _read_text(file_path)
        for m in to_prop.finditer(text):
            p = m.group(1).split("?", 1)[0].split("#", 1)[0]
            targets.add(p)
            provenance.setdefault(p, set()).add(str(file_path.relative_to(REPO_ROOT)))
        for m in nav_call.finditer(text):
            p = m.group(1).split("?", 1)[0].split("#", 1)[0]
            targets.add(p)
            provenance.setdefault(p, set()).add(str(file_path.relative_to(REPO_ROOT)))

    return targets, provenance


def _load_backend_routes() -> list[BackendRoute]:
    """Import FastAPI app and list registered routes.

    This expects backend dependencies in `python_backend/requirements.txt` to be installed.
    """

    sys.path.insert(0, str(BACKEND_ROOT))
    try:
        main_path = BACKEND_ROOT / "main.py"
        spec = importlib.util.spec_from_file_location("graphtrace_backend_main", main_path)
        if spec is None or spec.loader is None:
            raise RuntimeError(f"Unable to load backend module spec from {main_path}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        app = getattr(module, "app")
    except Exception as exc:  # pylint: disable=broad-exception-caught
        raise RuntimeError(
            "Failed to import backend app. Ensure deps installed and run from repo root. "
            f"Import error: {exc}"
        ) from exc

    routes: list[BackendRoute] = []
    for r in getattr(app, "routes", []):
        path = getattr(r, "path", None)
        if not isinstance(path, str):
            continue

        # skip docs/static; keep /api and /health
        if not (path.startswith("/api") or path in {"/health"}):
            continue

        # Normalize param style
        norm_path = _normalize_api_path(path)

        route_cls = str(getattr(r, "__class__", type("x", (), {})).__name__ or "").lower()
        if "websocket" in route_cls:
            routes.append(BackendRoute(path=norm_path, methods=("WS",)))
            continue

        methods = getattr(r, "methods", None)
        if not methods:
            continue

        methods_tuple = tuple(sorted(m for m in methods if m not in {"HEAD", "OPTIONS"}))
        routes.append(BackendRoute(path=norm_path, methods=methods_tuple))

    # de-dup by (path, methods)
    uniq: dict[tuple[str, tuple[str, ...]], BackendRoute] = {}
    for r in routes:
        uniq[(r.path, r.methods)] = r

    return list(sorted(uniq.values(), key=lambda x: x.path))


def _write_report(
    *,
    frontend_api_paths: set[str],
    frontend_api_provenance: dict[str, set[str]],
    backend_routes: list[BackendRoute],
    bad_nav_targets: set[str],
    bad_nav_provenance: dict[str, set[str]],
) -> None:
    backend_paths = {r.path for r in backend_routes}

    missing_in_backend = sorted(p for p in frontend_api_paths if p not in backend_paths)

    lines: list[str] = []
    lines.append("# Frontend/Backend Audit Report")
    lines.append("")
    lines.append(f"Repo root: `{REPO_ROOT}`")
    lines.append(f"Generated: `{REPORT_PATH}`")
    lines.append("")

    lines.append("## Summary")
    lines.append(f"- Frontend API paths detected: **{len(frontend_api_paths)}**")
    lines.append(f"- Backend routes detected: **{len(backend_routes)}**")
    lines.append(f"- Frontend API paths missing in backend: **{len(missing_in_backend)}**")
    lines.append(f"- Navigation targets missing in router: **{len(bad_nav_targets)}**")
    lines.append("")

    if bad_nav_targets:
        lines.append("## Navigation targets not defined in router")
        for p in sorted(bad_nav_targets):
            lines.append(f"- `{p}`")
            for src in sorted(bad_nav_provenance.get(p, set()))[:10]:
                lines.append(f"  - {src}")
        lines.append("")

    if missing_in_backend:
        lines.append("## Frontend API paths missing in backend")
        for p in missing_in_backend:
            lines.append(f"- `{p}`")
            for src in sorted(frontend_api_provenance.get(p, set()))[:10]:
                lines.append(f"  - {src}")
        lines.append("")

    lines.append("## Backend routes (for reference)")
    for r in backend_routes:
        methods = ",".join(r.methods) if r.methods else "?"
        lines.append(f"- `{r.path}` [{methods}]")

    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    if not FRONTEND_SRC.exists():
        print(f"Frontend src not found at: {FRONTEND_SRC}")
        return 2
    if not BACKEND_ROOT.exists():
        print(f"Backend not found at: {BACKEND_ROOT}")
        return 2

    frontend_api_paths, frontend_api_provenance = _extract_frontend_api_paths()

    router_paths = _extract_router_paths()
    nav_targets, nav_provenance = _extract_frontend_nav_targets()

    # Targets are hash-router relative; normalize '/foo' against router children.
    bad_nav_targets = {p for p in nav_targets if p not in router_paths}

    backend_routes = _load_backend_routes()

    _write_report(
        frontend_api_paths=frontend_api_paths,
        frontend_api_provenance=frontend_api_provenance,
        backend_routes=backend_routes,
        bad_nav_targets=bad_nav_targets,
        bad_nav_provenance=nav_provenance,
    )

    backend_paths = {r.path for r in backend_routes}
    missing_in_backend = sorted(p for p in frontend_api_paths if p not in backend_paths)

    print(f"Wrote report: {REPORT_PATH}")
    print(f"Frontend API paths: {len(frontend_api_paths)}")
    print(f"Backend routes: {len(backend_routes)}")
    print(f"Missing in backend: {len(missing_in_backend)}")
    print(f"Bad nav targets: {len(bad_nav_targets)}")

    # Also write machine-readable JSON for tooling
    out_json = REPORT_PATH.with_suffix(".json")
    out_json.write_text(
        json.dumps(
            {
                "frontend_api_paths": sorted(frontend_api_paths),
                "backend_routes": [
                    {"path": r.path, "methods": list(r.methods)} for r in backend_routes
                ],
                "missing_in_backend": missing_in_backend,
                "bad_nav_targets": sorted(bad_nav_targets),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
