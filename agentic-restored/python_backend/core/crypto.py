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

from cryptography.fernet import Fernet  # type: ignore


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
    
    In production mode, requires an explicit encryption key to be set.
    In development mode, allows fallback to derived keys.
    """
    import logging
    logger = logging.getLogger(__name__)

    raw = (os.getenv("GRAPH_TRACE_CONFIG_ENCRYPTION_KEY") or "").strip()
    if raw:
        # Accept either a proper Fernet key (urlsafe base64 32 bytes -> 44 chars)
        # or a passphrase (we'll derive a key deterministically).
        try:
            return Fernet(raw.encode("utf-8"))
        except Exception:  # pylint: disable=broad-exception-caught
            return Fernet(_derive_fernet_key(raw))

    # Local-dev fallback: load from a local key file (ignored by git).
    # This keeps the encrypted-config feature usable when running via VS Code tasks
    # or other shells where env vars are not consistently set.
    try:
        repo_backend_root = Path(__file__).resolve().parents[1]
        key_file = repo_backend_root / ".graphtrace.encryption_key"
        if key_file.exists():
            file_raw = key_file.read_text(encoding="utf-8").strip()
            if file_raw:
                try:
                    return Fernet(file_raw.encode("utf-8"))
                except Exception:  # pylint: disable=broad-exception-caught
                    return Fernet(_derive_fernet_key(file_raw))
    except Exception:  # pylint: disable=broad-exception-caught
        # Ignore file fallback errors and continue to other sources.
        pass

    # Security: In production, require explicit key - don't use fallbacks
    if _is_production():
        raise ValueError(
            "No encryption key configured. In production, set GRAPH_TRACE_CONFIG_ENCRYPTION_KEY explicitly."
        )

    jwt_secret = (os.getenv("GRAPH_TRACE_JWT_SECRET") or "").strip()
    if jwt_secret:
        logger.warning("Using JWT secret as encryption key fallback (development mode only)")
        return Fernet(_derive_fernet_key(jwt_secret))

    # Last-resort: derive from DATABASE_URL password (if present) so secrets are at
    # least encrypted-at-rest for single-machine/dev. If DB has no password, fail.
    db_url = (os.getenv("DATABASE_URL") or "").strip()
    if "://" in db_url and "@" in db_url and ":" in db_url.split("@", 1)[0]:
        logger.warning("Using DATABASE_URL as encryption key fallback (development mode only)")
        return Fernet(_derive_fernet_key(db_url))

    raise ValueError("No encryption key configured")


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
