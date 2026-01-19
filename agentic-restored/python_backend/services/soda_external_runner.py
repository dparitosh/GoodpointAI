"""External Soda runner.

Why this exists:
- Soda Core currently isn't reliably importable under Python 3.12 in some
  environments.
- We still want the FastAPI backend to run on 3.12, while executing Soda scans
  using a separate Python (typically 3.11) where `soda-core-postgres` is
  installed.

How it works:
- The backend spawns an external interpreter configured via an env var.
- Scan configuration is passed over STDIN (JSON) to avoid leaking secrets in
  process arguments.
- The external process prints a single JSON document to STDOUT.

Configuration:
- GRAPH_TRACE_SODA_EXTERNAL_PYTHON: absolute path to python.exe in the Soda venv.
- GRAPH_TRACE_SODA_EXTERNAL_TIMEOUT_S: optional timeout (default 60s).
"""

# pylint: disable=broad-exception-caught

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any, Dict, Tuple

from fastapi import HTTPException

try:
    from sqlalchemy.orm import Session
except ImportError:  # pragma: no cover
    Session = Any  # type: ignore

ENV_SODA_PYTHON = "GRAPH_TRACE_SODA_EXTERNAL_PYTHON"
ENV_SODA_TIMEOUT_S = "GRAPH_TRACE_SODA_EXTERNAL_TIMEOUT_S"

DEFAULT_TIMEOUT_S = 60


def is_soda_external_runner_configured(db: Session | None = None) -> bool:
    """Return True if an external Soda runner is configured.

    Configuration sources (in order of preference):
    - Admin Connection Settings: connection_type='soda_external', extra_options.python_path
    - Environment: GRAPH_TRACE_SODA_EXTERNAL_PYTHON
    """

    env_python = (os.getenv(ENV_SODA_PYTHON) or "").strip()
    if env_python:
        return True

    cfg = _load_runner_config_from_db(db)
    return bool(str(cfg.get("python_path") or "").strip())


def _load_runner_config_from_db(db: Session | None) -> Dict[str, Any]:
    """Best-effort: read external Soda runner config from Admin Connection Settings.

    Looks for an active, default connection with:
      - connection_type == 'soda_external'
      - extra_options.python_path
      - optional extra_options.timeout_s

    Returns an empty dict if unavailable.
    """

    if db is None:
        return {}

    try:
        # Local import keeps this module usable in minimal/test contexts.
        from models.admin_config_models import ConnectionConfig  # pylint: disable=import-outside-toplevel
        from sqlalchemy.exc import SQLAlchemyError  # pylint: disable=import-outside-toplevel

        try:
            rows = (
                db.query(ConnectionConfig)
                .filter(ConnectionConfig.connection_type == "soda_external")
                .filter(ConnectionConfig.status == "active")
                .order_by(ConnectionConfig.is_default.desc(), ConnectionConfig.updated_at.desc())
                .all()
            )
        except SQLAlchemyError:
            return {}

        if not rows:
            return {}

        row = rows[0]
        extra = getattr(row, "extra_options", None)
        if not isinstance(extra, dict):
            extra = {}

        python_path = str(extra.get("python_path") or extra.get("python") or extra.get("python_exe") or "").strip()
        timeout_raw = extra.get("timeout_s")
        timeout_s: int | None = None
        if timeout_raw is not None and str(timeout_raw).strip() != "":
            try:
                timeout_s = int(timeout_raw)
            except (TypeError, ValueError):
                timeout_s = None

        out: Dict[str, Any] = {}
        if python_path:
            out["python_path"] = python_path
        if timeout_s is not None:
            out["timeout_s"] = timeout_s
        return out
    except (ImportError, AttributeError, TypeError, ValueError, RuntimeError):
        return {}


def _get_timeout_s() -> int:
    raw = (os.getenv(ENV_SODA_TIMEOUT_S) or "").strip()
    if not raw:
        return DEFAULT_TIMEOUT_S
    try:
        value = int(raw)
        return max(1, min(600, value))
    except ValueError:
        return DEFAULT_TIMEOUT_S


def run_soda_scan_external(
    *,
    data_source_name: str,
    config_yaml: str,
    checks_yaml: str,
    db: Session | None = None,
) -> Tuple[int, Dict[str, Any]]:
    """Run Soda Scan in an external Python interpreter.

    Returns:
        (exit_code, scan_results_dict)

    Raises:
        HTTPException(503) if the external runner is not configured or fails.
    """

    db_cfg = _load_runner_config_from_db(db)

    python_exe = str(db_cfg.get("python_path") or "").strip() or (os.getenv(ENV_SODA_PYTHON) or "").strip()
    if not python_exe:
        raise HTTPException(
            status_code=503,
            detail=(
                "Soda Core is not available in this environment. "
                "To enable Soda scans, configure an active 'soda_external' connection in Admin "
                "Connection Settings (extra_options.python_path), or set "
                f"{ENV_SODA_PYTHON} to a Python interpreter (typically 3.11) with `soda-core-postgres` installed."
            ),
        )

    script_path = Path(__file__).resolve().parents[1] / "tools" / "soda_external_scan.py"
    if not script_path.exists():
        raise HTTPException(
            status_code=500,
            detail="Soda external runner script is missing (tools/soda_external_scan.py)",
        )

    payload = {
        "data_source_name": str(data_source_name or "postgres").strip() or "postgres",
        "config_yaml": str(config_yaml or ""),
        "checks_yaml": str(checks_yaml or ""),
    }

    timeout_s = _get_timeout_s()
    if db_cfg.get("timeout_s") is not None:
        try:
            timeout_val = db_cfg.get("timeout_s")
            timeout_s = max(1, min(600, int(str(timeout_val).strip())))
        except (TypeError, ValueError):
            timeout_s = _get_timeout_s()

    try:
        proc = subprocess.run(
            [python_exe, str(script_path)],
            input=json.dumps(payload, ensure_ascii=False),
            text=True,
            capture_output=True,
            timeout=timeout_s,
            check=False,
        )
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"External Soda python not found: {python_exe}",
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise HTTPException(
            status_code=503,
            detail=f"External Soda scan timed out after {timeout_s}s",
        ) from exc

    stdout = (proc.stdout or "").strip()
    stderr = (proc.stderr or "").strip()

    if proc.returncode != 0:
        # Do not echo secrets; stderr should not contain secrets if we passed config via stdin.
        suffix = f" (stderr: {stderr[:400]})" if stderr else ""
        raise HTTPException(
            status_code=503,
            detail=f"External Soda runner failed with exit code {proc.returncode}{suffix}",
        )

    try:
        doc = json.loads(stdout or "{}")
    except json.JSONDecodeError as exc:
        suffix = f" (stderr: {stderr[:400]})" if stderr else ""
        raise HTTPException(
            status_code=503,
            detail=f"External Soda runner returned invalid JSON{suffix}",
        ) from exc

    if not isinstance(doc, dict):
        raise HTTPException(status_code=503, detail="External Soda runner returned unexpected output")

    exit_code_raw = doc.get("exit_code")
    try:
        exit_code = int(exit_code_raw) if exit_code_raw is not None else 1
    except (TypeError, ValueError):
        exit_code = 1

    scan_results = doc.get("scan_results")
    if not isinstance(scan_results, dict):
        scan_results = {}

    # If the external script reported an error, surface it deterministically.
    if doc.get("error") and not scan_results:
        raise HTTPException(status_code=503, detail=f"External Soda runner error: {str(doc.get('error'))}")

    return exit_code, scan_results
