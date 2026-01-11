from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Optional, Tuple

from fastapi import HTTPException
from starlette.datastructures import Headers
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from core.auth import AuthPrincipal, auth_required, decode_token, jwt_secret


_ALLOWLIST_PREFIXES = (
    "/health",
    "/docs",
    "/openapi.json",
    "/api/docs",
    "/api/openapi.json",
    "/api/status",
    "/api/auth",
)


def _get_client_ip(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        # The left-most is original client.
        return forwarded_for.split(",")[0].strip()
    client = request.client
    return client.host if client else "unknown"


def _extract_api_key(request: Request) -> Optional[str]:
    # Prefer explicit header.
    api_key = request.headers.get("x-api-key")
    if api_key:
        return api_key.strip()

    auth = request.headers.get("authorization")
    if not auth:
        return None

    parts = auth.split(" ", 1)
    if len(parts) != 2:
        return None

    scheme, token = parts[0].strip().lower(), parts[1].strip()
    if scheme == "bearer" and token:
        return token
    return None


def _extract_bearer_token(headers: Headers) -> Optional[str]:
    auth = headers.get("authorization")
    if not auth:
        return None
    parts = auth.split(" ", 1)
    if len(parts) != 2:
        return None
    scheme, token = parts[0].strip().lower(), parts[1].strip()
    if scheme == "bearer" and token:
        return token
    return None


def _is_allowlisted_path(path: str) -> bool:
    return any(path.startswith(prefix) for prefix in _ALLOWLIST_PREFIXES)


def enforce_api_key_if_configured(request: Request) -> Optional[Response]:
    """Enforce API key auth when API_KEY (or GRAPH_TRACE_API_KEY) is set.

    This keeps local dev friction low while allowing deployments to enable auth
    simply by setting an env var.
    """

    if _is_allowlisted_path(request.url.path):
        return None

    if not request.url.path.startswith("/api"):
        return None

    expected_api_key = (os.getenv("GRAPH_TRACE_API_KEY") or os.getenv("API_KEY") or "").strip()

    # If API key is configured, accept either x-api-key or bearer token that matches.
    if expected_api_key:
        provided = _extract_api_key(request)
        if provided and provided == expected_api_key:
            request.state.principal = AuthPrincipal(subject="api_key", roles=("admin",), auth_type="api_key")
            return None

    # JWT bearer auth (optional; can be required when configured).
    bearer = _extract_bearer_token(request.headers)
    if bearer and jwt_secret():
        try:
            principal = decode_token(bearer)
        except HTTPException as exc:
            return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

        request.state.principal = principal
        return None

    # If auth is required, we didn't authenticate.
    if auth_required():
        return JSONResponse(
            status_code=401,
            content={"detail": "Unauthorized"},
            headers={"WWW-Authenticate": "Bearer"},
        )

    return None


@dataclass
class RateLimitDecision:
    allowed: bool
    retry_after_s: int = 0


class InMemoryRateLimiter:
    """Simple fixed-window per-IP limiter.

    Good enough for dev/single-process use; replace with Redis for multi-worker.
    """

    def __init__(self, limit_per_minute: int) -> None:
        self.limit_per_minute = max(1, int(limit_per_minute))
        self._state: dict[str, Tuple[float, int]] = {}

    def check(self, key: str) -> RateLimitDecision:
        now = time.monotonic()
        window_start, count = self._state.get(key, (now, 0))

        if now - window_start >= 60.0:
            window_start, count = now, 0

        count += 1
        self._state[key] = (window_start, count)

        if count <= self.limit_per_minute:
            return RateLimitDecision(allowed=True)

        retry_after = int(max(0.0, 60.0 - (now - window_start)))
        return RateLimitDecision(allowed=False, retry_after_s=retry_after)


def enforce_rate_limit(request: Request, limiter: InMemoryRateLimiter) -> Optional[Response]:
    if _is_allowlisted_path(request.url.path):
        return None

    if not request.url.path.startswith("/api"):
        return None

    client_ip = _get_client_ip(request)
    decision = limiter.check(client_ip)
    if decision.allowed:
        return None

    return JSONResponse(
        status_code=429,
        content={
            "detail": "Too Many Requests",
            "retry_after_seconds": decision.retry_after_s,
        },
        headers={"Retry-After": str(decision.retry_after_s)},
    )
