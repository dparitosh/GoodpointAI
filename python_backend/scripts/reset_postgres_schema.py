"""Reset (drop & recreate) the app's Postgres tables.

This is a destructive operation intended for local/dev environments when you want
to remove all test data.

What it does:
  - Connects using the same DATABASE_URL as the backend (`core.db_session`).
  - Drops all SQLAlchemy-managed tables (Base.metadata).
  - Drops the known Soda smoke-test table: public.soda_test_table.
  - Recreates all SQLAlchemy-managed tables (empty).

Safety:
  - Requires `--yes`.
  - Optionally requires `--confirm-db <dbname>` to match the target database.
  - Supports `--dry-run`.

After reset, you may need to re-seed DB-backed configuration.
See: scripts/init_db_schema.py and scripts/seed_db_config.py
"""

from __future__ import annotations

import argparse
import sys

from sqlalchemy import text
from sqlalchemy.engine.url import make_url

from core.database import Base
from core.db_session import DATABASE_URL, engine, init_db, redacted_database_url


def _import_models() -> None:
    """Ensure ORM models are imported so Base.metadata is populated."""
    import importlib

    for module_name in (
        "models.configuration_models",
        "models.graphql_models",
        "models.workflow_models",
        "models.plm_models",
        "models.quality_models",
        "models.report_models",
        "models.pipeline_config_models",
        "models.admin_config_models",
        "models.rule_engine_models",
    ):
        importlib.import_module(module_name)


def _target_db_name() -> str:
    try:
        url = make_url(DATABASE_URL)
        return (url.database or "").lstrip("/")
    except Exception:
        return ""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Drop & recreate app Postgres tables (dev only).")
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Actually perform the reset (required).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would happen without changing anything.",
    )
    parser.add_argument(
        "--confirm-db",
        default="",
        help="Require the DB name to match this value (recommended).",
    )
    parser.add_argument(
        "--drop-soda-test-table",
        action="store_true",
        default=True,
        help="Drop public.soda_test_table if it exists (default: true).",
    )
    parser.add_argument(
        "--no-drop-soda-test-table",
        action="store_false",
        dest="drop_soda_test_table",
        help="Do not drop public.soda_test_table.",
    )

    args = parser.parse_args(argv)

    db_name = _target_db_name()
    safe_url = redacted_database_url()

    _import_models()
    table_names = [t.name for t in Base.metadata.sorted_tables]

    print("Target DATABASE_URL:", safe_url)
    if db_name:
        print("Target database:", db_name)
    print(f"ORM tables to drop/recreate ({len(table_names)}):", ", ".join(table_names) or "(none)")
    if args.drop_soda_test_table:
        print("Also dropping: public.soda_test_table (if exists)")

    if args.confirm_db:
        if not db_name or db_name != args.confirm_db:
            print(
                f"Refusing to run: --confirm-db {args.confirm_db!r} does not match target database {db_name!r}.",
                file=sys.stderr,
            )
            return 2

    if args.dry_run:
        print("DRY RUN: no changes made.")
        return 0

    if not args.yes:
        print("Refusing to run without --yes (destructive operation).", file=sys.stderr)
        return 2

    # Drop all app tables.
    Base.metadata.drop_all(bind=engine)

    # Drop known smoke-test table (not part of ORM metadata).
    if args.drop_soda_test_table:
        with engine.begin() as conn:
            conn.execute(text("DROP TABLE IF EXISTS public.soda_test_table"))

    # Recreate all tables.
    init_db()

    print("OK: schema reset complete (tables recreated, data removed).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
