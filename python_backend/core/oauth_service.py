"""OAuth Token Management Service.

Handles OAuth 2.0 token lifecycle for PLM connections through Azure API Gateway:
- Client credentials flow for service-to-service auth
- Automatic token refresh before expiration
- Token caching to minimize auth requests
- Support for Azure AD and generic OAuth providers
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class OAuthToken:
    """OAuth access token with metadata."""
    access_token: str
    token_type: str = "Bearer"
    expires_in: int = 3600  # seconds
    expires_at: Optional[datetime] = None
    refresh_token: Optional[str] = None
    scope: Optional[str] = None
    
    def __post_init__(self):
        """Calculate expiration time on init."""
        if self.expires_at is None and self.expires_in:
            # Set expiration with 5-minute buffer for refresh
            self.expires_at = datetime.now(timezone.utc) + timedelta(seconds=self.expires_in - 300)
    
    def is_expired(self) -> bool:
        """Check if token is expired or will expire soon."""
        if self.expires_at is None:
            return False
        return datetime.now(timezone.utc) >= self.expires_at
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dict for storage."""
        return {
            "access_token": self.access_token,
            "token_type": self.token_type,
            "expires_in": self.expires_in,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "refresh_token": self.refresh_token,
            "scope": self.scope,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "OAuthToken":
        """Deserialize from dict."""
        return cls(
            access_token=data.get("access_token", ""),
            token_type=data.get("token_type", "Bearer"),
            expires_in=data.get("expires_in", 3600),
            expires_at=datetime.fromisoformat(data["expires_at"]) if data.get("expires_at") else None,
            refresh_token=data.get("refresh_token"),
            scope=data.get("scope"),
        )


class OAuthTokenManager:
    """Manages OAuth token lifecycle with caching and auto-refresh."""
    
    def __init__(self):
        """Initialize token cache."""
        self._token_cache: Dict[str, OAuthToken] = {}
    
    async def get_token(
        self,
        connection_id: str,
        client_id: str,
        client_secret: str,
        token_url: str,
        scope: Optional[str] = None,
        force_refresh: bool = False,
    ) -> Optional[str]:
        """Get valid access token, refreshing if needed.
        
        Args:
            connection_id: Unique ID for caching
            client_id: OAuth client ID
            client_secret: OAuth client secret
            token_url: Token endpoint URL
            scope: OAuth scope (optional)
            force_refresh: Force token refresh even if cached
            
        Returns:
            Access token string or None on failure
        """
        # Check cache
        if not force_refresh and connection_id in self._token_cache:
            cached = self._token_cache[connection_id]
            if not cached.is_expired():
                logger.debug("Using cached OAuth token for connection %s", connection_id)
                return cached.access_token
        
        # Acquire new token
        logger.info("Acquiring OAuth token for connection %s", connection_id)
        token = await self._acquire_token(
            client_id=client_id,
            client_secret=client_secret,
            token_url=token_url,
            scope=scope,
        )
        
        if token:
            self._token_cache[connection_id] = token
            return token.access_token
        
        return None
    
    async def _acquire_token(
        self,
        client_id: str,
        client_secret: str,
        token_url: str,
        scope: Optional[str] = None,
    ) -> Optional[OAuthToken]:
        """Acquire token using client credentials flow.
        
        Args:
            client_id: OAuth client ID
            client_secret: OAuth client secret
            token_url: Token endpoint URL
            scope: OAuth scope
            
        Returns:
            OAuthToken or None on failure
        """
        try:
            import httpx
            
            # Client credentials grant
            data = {
                "grant_type": "client_credentials",
                "client_id": client_id,
                "client_secret": client_secret,
            }
            
            if scope:
                data["scope"] = scope
            
            headers = {
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json",
            }
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(token_url, data=data, headers=headers)
            
            if response.status_code != 200:
                logger.error(
                    "OAuth token request failed: HTTP %d - %s",
                    response.status_code,
                    response.text[:200],
                )
                return None
            
            token_data = response.json()
            
            return OAuthToken(
                access_token=token_data.get("access_token", ""),
                token_type=token_data.get("token_type", "Bearer"),
                expires_in=token_data.get("expires_in", 3600),
                refresh_token=token_data.get("refresh_token"),
                scope=token_data.get("scope"),
            )
            
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("OAuth token acquisition failed: %s", e)
            return None
    
    def invalidate_token(self, connection_id: str) -> None:
        """Remove cached token for a connection."""
        self._token_cache.pop(connection_id, None)
        logger.debug("Invalidated OAuth token cache for connection %s", connection_id)
    
    def clear_cache(self) -> None:
        """Clear all cached tokens."""
        self._token_cache.clear()
        logger.info("Cleared OAuth token cache")


# Global token manager instance
_token_manager: Optional[OAuthTokenManager] = None


def get_oauth_token_manager() -> OAuthTokenManager:
    """Get global OAuth token manager instance."""
    global _token_manager  # pylint: disable=global-statement
    if _token_manager is None:
        _token_manager = OAuthTokenManager()
    return _token_manager


async def get_connection_oauth_token(
    connection_id: str,
    oauth_config: Dict[str, Any],
    force_refresh: bool = False,
) -> Optional[str]:
    """Helper to get OAuth token for a connection.
    
    Args:
        connection_id: Connection ID
        oauth_config: Dict with client_id, client_secret, token_url, scope
        force_refresh: Force token refresh
        
    Returns:
        Access token or None
    """
    client_id = oauth_config.get("oauth_client_id", "").strip()
    client_secret = oauth_config.get("oauth_client_secret", "").strip()
    token_url = oauth_config.get("oauth_token_url", "").strip()
    scope = oauth_config.get("oauth_scope", "").strip() or None
    
    if not all([client_id, client_secret, token_url]):
        logger.warning("Incomplete OAuth config for connection %s", connection_id)
        return None
    
    manager = get_oauth_token_manager()
    return await manager.get_token(
        connection_id=connection_id,
        client_id=client_id,
        client_secret=client_secret,
        token_url=token_url,
        scope=scope,
        force_refresh=force_refresh,
    )
