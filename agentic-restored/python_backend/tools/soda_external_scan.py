"""Run a Soda Scan in an external Python environment.

This file is intentionally tiny and dependency-light so it can run inside a
separate venv (e.g., Python 3.11) even when the main backend runs on Python 3.12.

The backend invokes this script via a configured interpreter path and passes the
scan configuration over STDIN as JSON to avoid leaking secrets in process args.

Input JSON (stdin):
{
  "data_source_name": "postgres",
  "config_yaml": "...",
  "checks_yaml": "checks for public.table:\n  - row_count > 0\n"
}

Output JSON (stdout):
{
  "exit_code": 0,
  "scan_results": { ... }
}
"""

from __future__ import annotations

import json
import sys
from typing import Any, Dict


def _read_payload() -> Dict[str, Any]:
    try:
        raw = sys.stdin.read()
    except OSError:
        raw = ""
    raw = (raw or "").strip()
    if not raw:
        return {}
    try:
        value = json.loads(raw)
        return value if isinstance(value, dict) else {}
    except json.JSONDecodeError:
        return {}


def main() -> int:
    payload = _read_payload()
    data_source_name = str(payload.get("data_source_name") or "postgres").strip() or "postgres"
    config_yaml = str(payload.get("config_yaml") or "")
    checks_yaml = str(payload.get("checks_yaml") or "")

    try:
        from soda.scan import Scan  # type: ignore

        scan = Scan()
        scan.set_data_source_name(data_source_name)
        scan.add_configuration_yaml_str(config_yaml)
        scan.add_sodacl_yaml_str(checks_yaml)

        exit_code = scan.execute()
        scan_results: Dict[str, Any] = scan.get_scan_results() or {}

        sys.stdout.write(
            json.dumps(
                {"exit_code": int(exit_code), "scan_results": scan_results},
                ensure_ascii=False,
                default=str,
            )
        )
        sys.stdout.flush()
        return 0

    except Exception as exc:  # pylint: disable=broad-exception-caught  # noqa: BLE001
        # Always emit JSON so the backend can surface a deterministic error.
        sys.stdout.write(
            json.dumps(
                {"error": str(exc), "exit_code": 1, "scan_results": {}},
                ensure_ascii=False,
                default=str,
            )
        )
        sys.stdout.flush()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
