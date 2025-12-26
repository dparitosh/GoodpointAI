"""Validate that frontend-referenced /api/* routes exist in the FastAPI app.

This is a lightweight safety net to catch 404s caused by route mismatches.
It scans the frontend src tree for string literals that start with /api/ and
then checks whether each path is registered in the backend.

Usage:
  python tools/check_frontend_api_routes.py
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence, Set, Tuple


@dataclass(frozen=True)
class Occurrence:
    file: Path
    line: int


_API_LITERAL_RE = re.compile(r"(?P<q>['\"])(?P<path>/api/[^'\"\n\r]*)\1")


def _iter_frontend_files(frontend_src: Path) -> Iterable[Path]:
    for path in frontend_src.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() not in {".js", ".jsx", ".ts", ".tsx"}:
            continue
        yield path


def _strip_query(path: str) -> str:
    return path.split("?", 1)[0]


def _route_pattern_to_regex(route: str) -> re.Pattern[str]:
    # FastAPI uses {param} placeholders.
    # Convert to a conservative regex that matches one segment per param.
    escaped = ""
    i = 0
    while i < len(route):
        ch = route[i]
        if ch == "{":
            end = route.find("}", i + 1)
            if end == -1:
                escaped += re.escape(ch)
                i += 1
                continue
            escaped += r"[^/]+"
            i = end + 1
            continue
        escaped += re.escape(ch)
        i += 1
    return re.compile(r"^" + escaped + r"$")


def _build_backend_route_matchers(paths: Sequence[str]) -> Tuple[Set[str], List[re.Pattern[str]]]:
    exact = set(paths)
    patterns: List[re.Pattern[str]] = []
    for p in paths:
        if "{" in p and "}" in p:
            patterns.append(_route_pattern_to_regex(p))
    return exact, patterns


def _path_exists(path: str, exact: Set[str], patterns: List[re.Pattern[str]]) -> bool:
    if path in exact:
        return True
    # Allow trailing slash mismatch.
    if path.endswith("/"):
        if path.rstrip("/") in exact:
            return True
    else:
        if (path + "/") in exact:
            return True

    for pat in patterns:
        if pat.match(path):
            return True
    return False


def main() -> int:
    backend_dir = Path(__file__).resolve().parents[1]
    repo_root = backend_dir.parent
    frontend_src = repo_root / "e2etraceapp" / "src"

    if not frontend_src.exists():
        print(f"Frontend src not found: {frontend_src}")
        return 2

    # Load backend app without relying on import resolution.
    main_py = backend_dir / "main.py"
    spec = spec_from_file_location("graphtrace_backend_main", main_py)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load backend main module from {main_py}")
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    app: Any = getattr(module, "app", None)
    if app is None:
        raise RuntimeError(f"Backend app not found in {main_py}")

    backend_paths = sorted(
        {
            getattr(r, "path")
            for r in app.routes
            if getattr(r, "path", None) and isinstance(getattr(r, "path"), str)
        }
    )
    exact, patterns = _build_backend_route_matchers(backend_paths)

    occurrences: Dict[str, List[Occurrence]] = {}

    for file_path in _iter_frontend_files(frontend_src):
        try:
            text = file_path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue

        for match in _API_LITERAL_RE.finditer(text):
            raw = match.group("path")
            if "${" in raw:
                continue
            path = _strip_query(raw)
            # Ignore obvious non-http paths (e.g., /api/:id placeholders in comments)
            if not path.startswith("/api/"):
                continue

            # Record occurrences with line numbers
            line_no = text.count("\n", 0, match.start()) + 1
            occurrences.setdefault(path, []).append(Occurrence(file=file_path, line=line_no))

    missing: List[str] = []
    for path in sorted(occurrences.keys()):
        if not _path_exists(path, exact, patterns):
            missing.append(path)

    print(f"Backend routes: {len(backend_paths)}")
    print(f"Frontend /api literals found: {len(occurrences)}")
    print(f"Missing routes: {len(missing)}")

    if missing:
        for path in missing:
            print(f"\nMISSING {path}")
            for occ in occurrences[path][:10]:
                rel = occ.file.relative_to(repo_root)
                print(f"  - {rel}:{occ.line}")
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
