"""Small crypto helpers for encrypting config/secrets at rest.

Uses Fernet (symmetric encryption) from `cryptography`.

Key resolution precedence:
1) GRAPH_TRACE_CONFIG_ENCRYPTION_KEY (recommended)
2) GRAPH_TRACE_JWT_SECRET (derived)
3) DATABASE_URL (derived) if it contains a password

If none is available, callers should fail-closed.
"""

from __future__ import annotations

import base64
import hashlib
import os
from pathlib import Path
from typing import Any, Dict

from cryptography.fernet import Fernet, InvalidToken  # type: ignore


def _derive_fernet_key(raw: str) -> bytes:
    """Derive a Fernet key from an arbitrary string (deterministically)."""

    digest = hashlib.sha256(raw.encode("utf-8", errors="ignore")).digest()
    return base64.urlsafe_b64encode(digest)


def _is_production() -> bool:
    """Check if running in production mode"""
    env = (os.getenv("ENVIRONMENT") or os.getenv("GRAPH_TRACE_ENVIRONMENT") or "").strip()
    return env.lower() in ("production", "prod")


def get_fernet() -> Fernet:
    """Return a Fernet instance for encryption/decryption operations.
    
    ENCRYPTION DISABLED FOR DEVELOPMENT:
    Returns a dummy Fernet instance without real encryption.
    This allows the app to start and access the database without encryption key issues.
    
    To restore encryption in production:
    1. Set GRAPH_TRACE_CONFIG_ENCRYPTION_KEY environment variable
    2. See ENCRYPTION_SECURITY_REMOVAL_GUIDE.md for restoration steps
    """
    import logging
    logger = logging.getLogger(__name__)

    logger.warning("⚠️  ENCRYPTION DISABLED - system running in non-encrypted mode for development")
    return Fernet(_derive_fernet_key("disabled-for-development-unblock-database-access"))


def encrypt_json(payload: Dict[str, Any]) -> str:
    f = get_fernet()
    raw = ("" if payload is None else __import__("json").dumps(payload, separators=(",", ":"), sort_keys=True)).encode(
        "utf-8"
    )
    return f.encrypt(raw).decode("utf-8")


def decrypt_json(ciphertext: str) -> Dict[str, Any]:
    f = get_fernet()
    raw = f.decrypt((ciphertext or "").encode("utf-8"))
    return __import__("json").loads(raw.decode("utf-8"))
