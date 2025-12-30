from __future__ import annotations

import json
import logging

from core.crypto import decrypt_json
from core.db_session import SessionLocal, redacted_database_url, verify_database_connectivity


logger = logging.getLogger(__name__)


def main() -> int:
    logging.basicConfig(level=logging.INFO)

    logger.info("DATABASE_URL=%s", redacted_database_url())
    err = verify_database_connectivity(timeout_s=5.0)
    if err is not None:
        logger.error("DB connectivity: FAIL (%s)", err)
        return 2

    logger.info("DB connectivity: OK")

    # Basic table/config checks (do not print secrets)
    from models.configuration_models import EncryptedConfig  # ensure model import

    db = SessionLocal()
    try:
        keys = [r.key for r in db.query(EncryptedConfig).all()]
        logger.info("EncryptedConfig keys present: %s", ", ".join(sorted(keys)) if keys else "(none)")

        # Verify decrypt works for non-secret payloads; avoid dumping plaintext.
        for key in ("system_configuration", "cors", "workflow_defaults"):
            row = db.get(EncryptedConfig, key)
            if row is None:
                logger.warning("Missing key: %s", key)
                continue
            try:
                payload = decrypt_json(row.ciphertext)
                logger.info("Decrypt OK: %s (type=%s)", key, type(payload).__name__)
            except Exception as exc:  # pylint: disable=broad-exception-caught
                logger.error("Decrypt FAIL: %s (%s)", key, exc)
                return 3

        # Neo4j/OpenSearch exist check (do not decrypt/print secrets)
        for key in ("neo4j", "opensearch"):
            row = db.get(EncryptedConfig, key)
            logger.info("%s present: %s", key, bool(row))

    finally:
        db.close()

    # Emit a compact JSON summary for tools.
    print(
        json.dumps(
            {
                "db_ok": True,
                "database_url_redacted": redacted_database_url(),
            },
            indent=2,
        )
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
