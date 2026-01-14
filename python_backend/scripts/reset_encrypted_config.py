"""Reset encrypted configuration rows (DANGEROUS).

This is intended for deployment recovery when the encryption key has changed
and existing EncryptedConfig rows cannot be decrypted.

It deletes the encrypted config rows so the system can be re-seeded using the
current GRAPH_TRACE_CONFIG_ENCRYPTION_KEY.

Safety:
- Requires --yes
- Optional --confirm-db <dbname>
- Supports --dry-run

After running:
  python -m scripts.seed_db_config --force
  python -m scripts.install_seeded_schema
"""

from __future__ import annotations

import argparse
import sys

from sqlalchemy.engine.url import make_url

from core.db_session import DATABASE_URL, SessionLocal


def _target_db_name() -> str:
    try:
        url = make_url(DATABASE_URL)
        return (url.database or "").lstrip("/")
    except Exception:
        return ""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Delete encrypted config rows so they can be re-seeded")
    parser.add_argument("--yes", action="store_true", help="Actually perform deletion (required)")
    parser.add_argument("--dry-run", action="store_true", help="Print what would happen without deleting")
    parser.add_argument("--confirm-db", default="", help="Require target DB name to match")

    args = parser.parse_args(argv)

    db_name = _target_db_name()
    if args.confirm_db and db_name != args.confirm_db:
        print(
            f"Refusing: --confirm-db {args.confirm_db!r} does not match target database {db_name!r}.",
            file=sys.stderr,
        )
        return 2

    try:
        from models.configuration_models import EncryptedConfig, DataSourceConfigRecord
    except Exception as exc:  # pylint: disable=broad-exception-caught
        print(f"Failed to import models: {exc}", file=sys.stderr)
        return 2

    print("Target DATABASE_URL:", DATABASE_URL)
    if db_name:
        print("Target database:", db_name)
    print("Will delete from: EncryptedConfig, DataSourceConfigRecord")

    if args.dry_run:
        print("DRY RUN: no changes made.")
        return 0

    if not args.yes:
        print("Refusing to run without --yes (destructive).", file=sys.stderr)
        return 2

    db = SessionLocal()
    try:
        # Delete dependent records first.
        deleted_ds = db.query(DataSourceConfigRecord).delete()
        deleted_enc = db.query(EncryptedConfig).delete()
        db.commit()
        print(f"OK: deleted DataSourceConfigRecord={deleted_ds}, EncryptedConfig={deleted_enc}")
    finally:
        db.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
