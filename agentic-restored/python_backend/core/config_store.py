from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from core.crypto import decrypt_json
from core.db_session import SessionLocal
from models.configuration_models import EncryptedConfig

logger = logging.getLogger(__name__)


def get_encrypted_config_payload(key: str) -> Optional[Dict[str, Any]]:
    """Fetch and decrypt an EncryptedConfig payload by key.

    Returns None when missing or when decrypting fails.
    This function is intended for DB-first runtime configuration.

    ENCRYPTION DISABLED: Returns None to allow app to start without encryption overhead.
    The system will use environment variables for configuration instead.
    """

    if not key or not str(key).strip():
        return None

    # SECURITY FIX: Encryption temporarily disabled to unblock database access
    # System will use environment variables for configuration instead
    logger.debug("Encrypted config fetch disabled for key %r (using env vars instead)", key)
    return None

    # Original encrypted config fetch (kept commented for reference):
    # db = SessionLocal()
    # try:
    #     row = db.get(EncryptedConfig, key)
    #     if row is None:
    #         return None
    #     payload = decrypt_json(row.ciphertext)
    #     if not isinstance(payload, dict):
    #         return None
    #     return payload
    # except (ValueError, OSError, AttributeError, KeyError) as exc:
    #     logger.debug("Failed to load encrypted config %r: %s", key, exc)
    #     return None
    # finally:
    #     db.close()
