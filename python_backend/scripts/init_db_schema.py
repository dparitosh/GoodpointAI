from __future__ import annotations

import logging
import sys
from pathlib import Path

# Allow running as a script directly (e.g. .\init_db_schema.py) in addition to
# the canonical `python -m scripts.init_db_schema` invocation from python_backend/.
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.db_session import DATABASE_URL, SessionLocal, init_db, redacted_database_url, verify_database_connectivity


logger = logging.getLogger(__name__)


def main() -> int:
    logging.basicConfig(level=logging.INFO)

    # Validate database configuration before attempting connection
    if not DATABASE_URL or DATABASE_URL == "sqlite:///:memory:":
        logger.error("DATABASE_URL is not configured!")
        logger.error("Please set DATABASE_URL in python_backend/.env")
        logger.error("Example: DATABASE_URL=postgresql://postgres:yourpassword@127.0.0.1:5432/graphtrace")
        return 1
    
    # Check for placeholder credentials that indicate incomplete configuration
    if "yourpassword" in DATABASE_URL or ":password@" in DATABASE_URL:
        logger.error("DATABASE_URL contains placeholder credentials!")
        logger.error("Please edit python_backend/.env and set your actual PostgreSQL password")
        logger.error("Current (redacted): Use actual credentials, not 'yourpassword' or 'password'")
        return 1

    # Fail fast if Postgres isn't reachable; avoids long hangs later during create_all/seed.
    logger.info("DATABASE_URL=%s", redacted_database_url())
    conn_err = verify_database_connectivity(timeout_s=5.0)
    if conn_err is not None:
        logger.error("Database connectivity check failed: %s", conn_err)
        logger.error("Is PostgreSQL running, and is DATABASE_URL correct in python_backend/.env?")
        return 2

    init_db()
    logger.info("DB schema ensured (create_all)")

    # ---- Migrate plm_staged_records – add columns that were introduced after
    # the table was first created (CREATE TABLE IF NOT EXISTS won't add them).
    try:
        from sqlalchemy import create_engine as _ce, text as _text

        _mg_engine = _ce(DATABASE_URL)
        _ALTER_STMTS = [
            # DQ-02: content hash for deduplication
            "ALTER TABLE plm_staged_records ADD COLUMN IF NOT EXISTS content_hash VARCHAR(64)",
            "ALTER TABLE plm_staged_records ADD COLUMN IF NOT EXISTS source_object_id VARCHAR(256)",
            # ensure index exists (idempotent)
            "CREATE INDEX IF NOT EXISTS ix_plm_staged_records_content_hash ON plm_staged_records (content_hash)",
            "CREATE INDEX IF NOT EXISTS ix_plm_staged_records_source_object_id ON plm_staged_records (source_object_id)",
            # DQ-01: unique constraint on (run_id, content_hash)
            """DO $$ BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_constraint WHERE conname = 'uq_staged_run_content_hash'
                ) THEN
                    ALTER TABLE plm_staged_records
                        ADD CONSTRAINT uq_staged_run_content_hash UNIQUE (run_id, content_hash);
                END IF;
            END $$""",
            # updated_at on plm_ingestion_runs
            "ALTER TABLE plm_ingestion_runs ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP",
        ]
        with _mg_engine.connect() as _conn:
            for _stmt in _ALTER_STMTS:
                try:
                    _conn.execute(_text(_stmt))
                except Exception as _col_exc:  # pylint: disable=broad-exception-caught
                    logger.debug("PLM migration stmt skipped (likely already applied): %s", _col_exc)
            _conn.commit()
        _mg_engine.dispose()
        logger.info("PLM schema migrations applied")
    except Exception as exc:  # pylint: disable=broad-exception-caught
        logger.warning("PLM schema migration skipped (non-fatal): %s", exc)

    try:
        from sqlalchemy import create_engine as _create_engine
        from services.file_batch_processor import ensure_schema as _ensure_batch_schema

        _batch_engine = _create_engine(DATABASE_URL)
        _ensure_batch_schema(_batch_engine)
        _batch_engine.dispose()
        logger.info("File batch processing tables ensured")
    except Exception as exc:  # pylint: disable=broad-exception-caught
        logger.warning("File batch schema init skipped (non-fatal): %s", exc)

    # ---- Seed admin configurations (LLM providers, connections, feature flags, etc.)
    # These populate default settings needed for the app to run.
    try:
        from scripts.seed_admin_configs import main as seed_admin_main
        seed_admin_main()
        logger.info("Admin configurations seeded")
    except Exception as exc:  # pylint: disable=broad-exception-caught
        logger.warning("Admin config seeding skipped (non-fatal): %s", exc)

    # ---- Seed encrypted database configurations (system settings, neo4j, opensearch, cors)
    # These are stored in EncryptedConfig and loaded via decrypt at runtime.
    try:
        from scripts.seed_db_config import seed_defaults as seed_db_main
        seed_db_main()
        logger.info("Encrypted database configurations seeded")
    except Exception as exc:  # pylint: disable=broad-exception-caught
        logger.warning("Database config seeding skipped (non-fatal): %s", exc)

    # If the encryption key has changed (common in local dev when env vars aren't persisted),
    # previously encrypted rows become undecryptable. For local SQLite only, reset encrypted
    # tables and re-seed defaults so the app can start cleanly.
    try:
        from core.crypto import decrypt_json
        from models.configuration_models import DataSourceConfigRecord, EncryptedConfig

        db = SessionLocal()
        try:
            sample = db.query(EncryptedConfig).filter(EncryptedConfig.key == "system_configuration").first()
            if sample is not None:
                try:
                    decrypt_json(sample.ciphertext)
                except Exception as exc:  # pylint: disable=broad-exception-caught
                    if DATABASE_URL.startswith("sqlite:"):
                        logger.warning(
                            "Encrypted config cannot be decrypted with current key; resetting local encrypted tables (SQLite only): %s",
                            exc,
                        )
                        db.query(DataSourceConfigRecord).delete()
                        db.query(EncryptedConfig).delete()
                        db.commit()
                    else:
                        logger.warning(
                            "Encrypted config cannot be decrypted with current key; NOT resetting because DB is not SQLite: %s",
                            exc,
                        )
        finally:
            db.close()
    except Exception as exc:  # pylint: disable=broad-exception-caught
        logger.warning("Encrypted-config sanity check skipped (non-fatal): %s", exc)

    try:
        from scripts.seed_db_config import seed_defaults

        seeded = seed_defaults(force=False)
        if seeded:
            logger.info("Seeded default config keys: %s", ", ".join(seeded))
        else:
            logger.info("No default config keys needed seeding")
    except Exception as exc:  # pylint: disable=broad-exception-caught
        logger.warning("Seeding skipped (non-fatal): %s", exc)

    # ---- Seed admin configurations (connections, LLM providers, feature flags) ----
    try:
        from scripts.seed_admin_configs import (
            seed_connections,
            seed_llm_providers,
            seed_embedding_models,
            seed_feature_flags,
            seed_system_configurations,
        )

        db = SessionLocal()
        try:
            seed_system_configurations(db)
            seed_llm_providers(db)
            seed_embedding_models(db)
            seed_connections(db)
            seed_feature_flags(db)
            logger.info("Admin configurations seeded")
        finally:
            db.close()
    except Exception as exc:  # pylint: disable=broad-exception-caught
        logger.warning("Admin config seeding skipped (non-fatal): %s", exc)

    # ---- Seed pipeline configurations (file patterns, templates, Neo4j schema) ----
    try:
        from scripts.seed_pipeline_configs import seed_all as seed_pipeline_all

        seed_pipeline_all(force=False)
        logger.info("Pipeline configurations seeded")
    except Exception as exc:  # pylint: disable=broad-exception-caught
        logger.warning("Pipeline config seeding skipped (non-fatal): %s", exc)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
