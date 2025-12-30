from __future__ import annotations

import logging

from core.db_session import DATABASE_URL, SessionLocal, init_db


logger = logging.getLogger(__name__)


def main() -> int:
    logging.basicConfig(level=logging.INFO)

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

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
