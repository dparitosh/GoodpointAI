from __future__ import annotations

import logging
import os

from core.db_session import DATABASE_URL, SessionLocal, init_db


logger = logging.getLogger(__name__)


def _is_production() -> bool:
    env = (os.getenv("ENVIRONMENT") or os.getenv("GRAPH_TRACE_ENVIRONMENT") or "").strip().lower()
    return env in {"prod", "production"}


def main() -> int:
    logging.basicConfig(level=logging.INFO)

    init_db()
    logger.info("DB schema ensured (create_all)")

    # If the encryption key has changed (common in local dev when env vars aren't persisted),
    # previously encrypted rows become undecryptable.
    # - For local SQLite only: reset encrypted tables and re-seed defaults.
    # - For Postgres/other DBs: fail-fast in production to avoid a half-broken install.
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
                        msg = (
                            "Encrypted config cannot be decrypted with current key and DB is not SQLite. "
                            "This usually means GRAPH_TRACE_CONFIG_ENCRYPTION_KEY changed between deployments."
                        )
                        if _is_production():
                            logger.error("%s Refusing to continue in production: %s", msg, exc)
                            return 5
                        logger.warning("%s Continuing (development mode only): %s", msg, exc)
        finally:
            db.close()
    except Exception as exc:  # pylint: disable=broad-exception-caught
        if _is_production():
            logger.error("Encrypted-config sanity check failed in production: %s", exc)
            return 5
        logger.warning("Encrypted-config sanity check skipped (non-fatal): %s", exc)

    try:
        from scripts.seed_db_config import seed_defaults

        seeded = seed_defaults(force=False)
        if seeded:
            logger.info("Seeded default config keys: %s", ", ".join(seeded))
        else:
            logger.info("No default config keys needed seeding")
    except Exception as exc:  # pylint: disable=broad-exception-caught
        if _is_production():
            logger.error("Required seeding failed in production: %s", exc)
            return 5
        logger.warning("Seeding skipped (non-fatal): %s", exc)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
