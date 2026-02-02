"""Postgres-only test DB helpers.

Repo requirement: persistence uses Postgres (no SQLite).

These helpers allow DB-backed tests to run when a disposable Postgres database is
provided via env vars, and to skip cleanly otherwise.

Environment variables (first match wins):
- GRAPH_TRACE_TEST_DATABASE_URL
- TEST_DATABASE_URL
- DATABASE_URL

The URL must be a Postgres SQLAlchemy URL, e.g.:
  postgresql+psycopg://user:pass@localhost:5432/graphtrace
"""

from __future__ import annotations

import os
from typing import Optional

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.engine.url import make_url


def _pick_database_url() -> Optional[str]:
    for key in ("GRAPH_TRACE_TEST_DATABASE_URL", "TEST_DATABASE_URL", "DATABASE_URL"):
        val = (os.getenv(key) or "").strip()
        if val:
            return val
    return None


def _masked_url(url: str) -> str:
    """Return a safe-to-log DB URL (password removed if present)."""

    try:
        parsed = make_url(url)
        return parsed.render_as_string(hide_password=True)
    except Exception:
        if "@" in url:
            return "***@" + url.split("@", 1)[1]
        return url


def create_postgres_test_engine(*, pool_pre_ping: bool = True) -> Engine:
    """Create a SQLAlchemy engine for Postgres tests or raise pytest.Skip."""

    # Import pytest lazily so this module is safe to import outside pytest.
    import pytest  # type: ignore

    url = _pick_database_url()
    if not url:
        pytest.skip(
            "Postgres test DB not configured. Set GRAPH_TRACE_TEST_DATABASE_URL (recommended) "
            "or TEST_DATABASE_URL/DATABASE_URL to a Postgres SQLAlchemy URL."
        )

    if not url.lower().startswith("postgres"):
        pytest.skip(f"Test DB must be Postgres (got {url.split(':', 1)[0]}).")

    engine = create_engine(
        url,
        pool_pre_ping=pool_pre_ping,
        connect_args={"connect_timeout": 3},
    )

    try:
        with engine.connect() as conn:
            conn.exec_driver_sql("SELECT 1")
    except OperationalError:
        pytest.skip(
            "Postgres test DB appears to be unreachable. "
            f"URL={_masked_url(url)}. "
            "Start Postgres, or unset DATABASE_URL / set GRAPH_TRACE_TEST_DATABASE_URL to a running disposable DB."
        )

    return engine
