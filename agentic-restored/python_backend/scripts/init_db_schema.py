from __future__ import annotations

import os
import logging

from core.db_session import SessionLocal, init_db


logger = logging.getLogger(__name__)


def main() -> int:
    logging.basicConfig(level=logging.INFO)

    init_db()
    logger.info("DB schema ensured (create_all)")

    # If the encryption key has changed (common in local dev when env vars aren't persisted),
    # previously encrypted rows become undecryptable.
    #
    # IMPORTANT: This project treats Postgres as the single source of truth for persistence.
    # We never auto-delete encrypted configuration rows unless the operator explicitly opts
    # into a destructive reset.
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
                    allow_reset = (os.getenv("GRAPH_TRACE_ALLOW_RESET_ENCRYPTED_CONFIG") or "").strip().lower() in {"1", "true", "yes"}
                    if allow_reset:
                        logger.warning(
                            "Encrypted config cannot be decrypted with current key; resetting encrypted tables due to GRAPH_TRACE_ALLOW_RESET_ENCRYPTED_CONFIG=true: %s",
                            exc,
                        )
                        db.query(DataSourceConfigRecord).delete()
                        db.query(EncryptedConfig).delete()
                        db.commit()
                    else:
                        logger.warning(
                            "Encrypted config cannot be decrypted with current key; NOT resetting automatically. "
                            "Set GRAPH_TRACE_ALLOW_RESET_ENCRYPTED_CONFIG=true if you intend to reset encrypted config tables: %s",
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
