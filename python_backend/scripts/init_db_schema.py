from __future__ import annotations

import logging

from core.db_session import DATABASE_URL, SessionLocal, init_db


logger = logging.getLogger(__name__)


def main() -> int:
    logging.basicConfig(level=logging.INFO)

    # Validate database configuration before attempting connection
    if not DATABASE_URL or DATABASE_URL == "sqlite:///:memory:":
        logger.error("DATABASE_URL is not configured!")
        logger.error("Please set DATABASE_URL in python_backend/.env")
        logger.error("Example: DATABASE_URL=postgresql://postgres:yourpassword@127.0.0.1:5433/graphtrace")
        return 1
    
    # Check for placeholder credentials that indicate incomplete configuration
    if "yourpassword" in DATABASE_URL or ":password@" in DATABASE_URL:
        logger.error("DATABASE_URL contains placeholder credentials!")
        logger.error("Please edit python_backend/.env and set your actual PostgreSQL password")
        logger.error("Current (redacted): Use actual credentials, not 'yourpassword' or 'password'")
        return 1

    init_db()
    logger.info("DB schema ensured (create_all)")

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
