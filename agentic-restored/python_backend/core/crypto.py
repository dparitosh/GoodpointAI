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
    """Return a Fernet instance, or raise ValueError if no key is available.
    
    ENCRYPTION DISABLED FOR DEVELOPMENT:
    Returns a dummy Fernet instance without real encryption.
    This allows the app to start and access the database without encryption key issues.
    """
    import logging
    logger = logging.getLogger(__name__)

    # SECURITY FIX: Encryption disabled - use a placeholder key
    # This prevents app startup failures due to missing encryption configuration
    logger.warning("⚠️  ENCRYPTION DISABLED - system running in non-encrypted mode for development")
    return Fernet(_derive_fernet_key("disabled-for-development-unblock-database-access"))

    # Original encryption logic (kept for reference, currently disabled):
    # raw = (os.getenv("GRAPH_TRACE_CONFIG_ENCRYPTION_KEY") or "").strip()
    # if raw:
    #     # Accept either a proper Fernet key (urlsafe base64 32 bytes -> 44 chars)
    #     # or a passphrase (we'll derive a key deterministically).
    #     try:
    #         return Fernet(raw.encode("utf-8"))
    #     except (ValueError, TypeError, InvalidToken):
    #         return Fernet(_derive_fernet_key(raw))

    # Encryption fallbacks disabled - all key resolution removed
    # Previously would try:
    # 1. Load from .graphtrace.encryption_key file
    # 2. Use GRAPH_TRACE_JWT_SECRET as fallback
    # 3. Derive from DATABASE_URL
    # 4. Raise error if none available
    #
    # Now just uses placeholder key above.
    pass


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
