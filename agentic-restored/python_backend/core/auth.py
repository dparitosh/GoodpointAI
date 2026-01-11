from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from fastapi import HTTPException
from jose import JWTError, jwt
from passlib.context import CryptContext
from starlette.requests import Request


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


@dataclass(frozen=True)
class AuthPrincipal:
    subject: str
    roles: tuple[str, ...]
    auth_type: str  # "jwt" | "api_key"


def _get_env(name: str) -> str:
    return (os.getenv(name) or "").strip()


def jwt_secret() -> str:
    return _get_env("GRAPH_TRACE_JWT_SECRET") or _get_env("JWT_SECRET")


def jwt_algorithm() -> str:
    return _get_env("GRAPH_TRACE_JWT_ALGORITHM") or "HS256"


def auth_required() -> bool:
    # If a secret is set, default to requiring auth unless explicitly disabled.
    v = _get_env("GRAPH_TRACE_AUTH_REQUIRED")
    if v:
        return v.lower() in ("1", "true", "yes", "on")
    return bool(jwt_secret() or _get_env("GRAPH_TRACE_API_KEY") or _get_env("API_KEY"))


def admin_username() -> str:
    return _get_env("GRAPH_TRACE_ADMIN_USERNAME") or _get_env("ADMIN_USERNAME") or "admin"


def admin_password_hash() -> str:
    return _get_env("GRAPH_TRACE_ADMIN_PASSWORD_HASH")


def admin_password_plain() -> str:
    return _get_env("GRAPH_TRACE_ADMIN_PASSWORD") or _get_env("ADMIN_PASSWORD")


def _is_production() -> bool:
    """Check if running in production mode"""
    env = _get_env("ENVIRONMENT") or _get_env("GRAPH_TRACE_ENVIRONMENT")
    return env.lower() in ("production", "prod")


def verify_admin_credentials(username: str, password: str) -> bool:
    if username != admin_username():
        return False

    expected_hash = admin_password_hash()
    if expected_hash:
        return pwd_context.verify(password, expected_hash)

    expected_plain = admin_password_plain()
    if expected_plain:
        # Security: Only allow plain-text password in non-production environments
        if _is_production():
            import logging
            logging.getLogger(__name__).warning(
                "Plain-text admin password rejected in production. Use GRAPH_TRACE_ADMIN_PASSWORD_HASH instead."
            )
            return False
        # Dev-friendly fallback (non-production only)
        return password == expected_plain

    # No credentials configured.
    return False


def create_access_token(
    *,
    subject: str,
    roles: list[str],
    expires_in_minutes: int = 60,
) -> str:
    secret = jwt_secret()
    if not secret:
        raise RuntimeError("JWT secret not configured (set GRAPH_TRACE_JWT_SECRET)")

    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": subject,
        "roles": roles,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=expires_in_minutes)).timestamp()),
    }

    return jwt.encode(payload, secret, algorithm=jwt_algorithm())


def decode_token(token: str) -> AuthPrincipal:
    try:
        payload = jwt.decode(token, jwt_secret(), algorithms=[jwt_algorithm()])
    except JWTError as exc:
        raise HTTPException(status_code=401, detail="Invalid token") from exc

    sub = payload.get("sub")
    if not sub or not isinstance(sub, str):
        raise HTTPException(status_code=401, detail="Invalid token")

    roles_raw = payload.get("roles")
    roles: list[str]
    if isinstance(roles_raw, list):
        roles = [str(r) for r in roles_raw]
    elif isinstance(roles_raw, str):
        roles = [roles_raw]
    else:
        roles = []

    return AuthPrincipal(subject=sub, roles=tuple(roles), auth_type="jwt")


def get_request_principal(request: Request) -> Optional[AuthPrincipal]:
    principal = getattr(request.state, "principal", None)
    if principal is None:
        return None
    if isinstance(principal, AuthPrincipal):
        return principal
    return None


def require_principal(request: Request) -> AuthPrincipal:
    principal = get_request_principal(request)
    if principal is None:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return principal


def require_admin(request: Request) -> AuthPrincipal:
    principal = require_principal(request)
    if "admin" not in principal.roles:
        raise HTTPException(status_code=403, detail="Forbidden")
    return principal
