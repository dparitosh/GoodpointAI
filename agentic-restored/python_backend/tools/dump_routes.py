from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from typing import Any


def _method_label(route) -> str:
    methods = getattr(route, "methods", None)
    if methods:
        return ",".join(sorted(methods))
    # WebSocket routes don't expose .methods
    if route.__class__.__name__.lower().find("websocket") != -1:
        return "WS"
    return "NA"


def main() -> None:
    backend_dir = Path(__file__).resolve().parents[1]
    main_py = backend_dir / "main.py"
    spec = spec_from_file_location("graphtrace_backend_main", main_py)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load backend main module from {main_py}")
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    app: Any = getattr(module, "app", None)
    if app is None:
        raise RuntimeError(f"Backend app not found in {main_py}")

    lines: set[tuple[str, str]] = set()
    for route in app.routes:
        path = getattr(route, "path", None)
        if not path:
            continue
        lines.add((path, _method_label(route)))

    for path, methods in sorted(lines):
        print(f"{methods} {path}")


if __name__ == "__main__":
    main()
