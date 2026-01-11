"""Postgres configuration helpers.

Goal: ensure SQLAlchemy (app metadata) and asyncpg (bulk ETL) can use the same
DATABASE_URL so the system has exactly one Postgres database as the source of truth.
"""

from __future__ import annotations

from typing import Any, Dict

from sqlalchemy.engine.url import make_url


def is_postgres_database_url(database_url: str) -> bool:
    url = (database_url or "").strip().lower()
    # Accept SQLAlchemy driver URLs like postgresql+psycopg://...
    return url.startswith("postgres:") or url.startswith("postgresql:") or url.startswith("postgresql+")


def normalize_sqlalchemy_postgres_url(database_url: str) -> str:
    """Ensure SQLAlchemy Postgres URLs use the installed psycopg driver.

    SQLAlchemy's plain `postgresql://` historically targets psycopg2 by default.
    This project uses psycopg (v3). If the user provides `postgresql://...`,
    rewrite it to `postgresql+psycopg://...`.
    """
    raw = (database_url or "").strip()
    lower = raw.lower()
    if lower.startswith("postgresql+psycopg://"):
        return raw
    if lower.startswith("postgresql://"):
        return "postgresql+psycopg://" + raw[len("postgresql://") :]
    # Leave other schemes (sqlite, etc) unchanged.
    return raw


def asyncpg_params_from_database_url(database_url: str) -> Dict[str, Any]:
    """Convert a SQLAlchemy DATABASE_URL into asyncpg.create_pool params."""
    if not is_postgres_database_url(database_url):
        raise ValueError("DATABASE_URL must be a postgres URL")

    url = make_url(database_url)

    # SQLAlchemy URLs can be like postgresql+psycopg://user:pass@host:5432/db
    host = url.host or "localhost"
    port = int(url.port or 5432)
    database = (url.database or "").lstrip("/")
    username = url.username or ""
    password = url.password or ""

    if not database:
        raise ValueError("DATABASE_URL is missing a database name")

    return {
        "host": host,
        "port": port,
        "database": database,
        "user": username,
        "password": password,
    }
