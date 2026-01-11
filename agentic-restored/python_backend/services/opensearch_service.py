"""
OpenSearch Service - Best-effort OpenSearch client wrapper.

Configuration is loaded from the admin config database with fallback to
environment variables for backward compatibility.

- Uses admin config DB first, then env vars for configuration.
- Degrades gracefully when OpenSearch is not configured or unreachable.
"""

import os
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional, List

logger = logging.getLogger(__name__)


def _get_opensearch_config_from_admin(db_session=None) -> Dict[str, Any]:
    """Load OpenSearch configuration from admin config service."""
    try:
        from services.admin_config_service import AdminConfigService
        config_service = AdminConfigService(db_session)
        return config_service.get_connection_config("opensearch")
    except Exception as e:
        logger.debug("Admin config not available for OpenSearch: %s", e)
        return {}


class OpenSearchService:
    """Best-effort OpenSearch client wrapper.

    - Uses admin config DB first, then env vars for configuration.
    - Degrades gracefully when OpenSearch is not configured or unreachable.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None, db_session=None):
        cfg = config or {}
        
        # Try to load from admin config first
        if not cfg and db_session:
            admin_config = _get_opensearch_config_from_admin(db_session)
            if admin_config:
                cfg = admin_config

        # Prefer explicit config; fall back to environment variables.
        self.endpoint = str(
            cfg.get("url") or cfg.get("endpoint") 
            or cfg.get("connection_string")
            or os.getenv("OPENSEARCH_URL") 
            or ""
        ).strip()
        
        # Build endpoint from host/port if not directly provided
        if not self.endpoint and cfg.get("host"):
            protocol = "https" if cfg.get("ssl_enabled") else "http"
            self.endpoint = f"{protocol}://{cfg.get('host')}:{cfg.get('port', 9200)}"
        
        self.hosts_env = str(cfg.get("hosts") or os.getenv("OPENSEARCH_HOSTS") or "").strip()
        self.username = str(cfg.get("username") or os.getenv("OPENSEARCH_USERNAME") or "").strip()
        self.password = str(cfg.get("password") or os.getenv("OPENSEARCH_PASSWORD") or "").strip()

        verify_raw = cfg.get("verify_certs")
        if verify_raw is None:
            self.verify_certs = (os.getenv("OPENSEARCH_VERIFY_CERTS") or "true").strip().lower() not in {
                "0",
                "false",
                "no",
            }
        else:
            self.verify_certs = bool(verify_raw)

        timeout_raw = cfg.get("timeout_s") or cfg.get("pool_timeout")
        if timeout_raw is None:
            self.timeout_s = float((os.getenv("OPENSEARCH_TIMEOUT_S") or "5").strip() or 5)
        else:
            self.timeout_s = float(timeout_raw or 5)

        self._client = None

    def _parse_hosts(self) -> List[Dict[str, Any]]:
        """Parse OPENSEARCH_HOSTS or OPENSEARCH_URL into OpenSearch client hosts.

        Supported:
        - OPENSEARCH_HOSTS="https://host:9200,https://host2:9200"
        - OPENSEARCH_URL="https://host:9200"
        """

        raw = self.hosts_env or self.endpoint
        raw = (raw or "").strip()
        if not raw:
            return []

        hosts: List[Dict[str, Any]] = []
        for token in [t.strip() for t in raw.split(",") if t.strip()]:
            use_ssl = token.startswith("https://")
            hostport = token
            if hostport.startswith("http://"):
                hostport = hostport[len("http://") :]
            elif hostport.startswith("https://"):
                hostport = hostport[len("https://") :]

            if "/" in hostport:
                hostport = hostport.split("/", 1)[0]

            if ":" in hostport:
                host, port_str = hostport.rsplit(":", 1)
                port = int(port_str)
            else:
                host = hostport
                port = 443 if use_ssl else 9200

            hosts.append({"host": host, "port": port, "use_ssl": use_ssl})

        return hosts

    def _build_client(self):
        if self._client is not None:
            return self._client

        hosts = self._parse_hosts()
        if not hosts:
            return None

        try:
            from opensearchpy import OpenSearch  # type: ignore
        except ImportError:
            logger.warning("opensearch-py not installed; OpenSearch features disabled")
            return None

        http_auth = None
        if self.username or self.password:
            http_auth = (self.username, self.password)

        # OpenSearch client supports per-host 'use_ssl'. Avoid mixing by picking True if any host is https.
        use_ssl = any(h.get("use_ssl") for h in hosts)
        host_defs = [{"host": h["host"], "port": h["port"]} for h in hosts]

        self._client = OpenSearch(
            hosts=host_defs,
            http_auth=http_auth,
            use_ssl=use_ssl,
            verify_certs=self.verify_certs,
            ssl_show_warn=not self.verify_certs,
            timeout=self.timeout_s,
        )
        return self._client

    def health(self) -> Dict[str, Any]:
        client = self._build_client()
        if client is None:
            return {
                "status": "degraded",
                "connected": False,
                "endpoint": self.endpoint or None,
                "timestamp": datetime.now(timezone.utc).replace(tzinfo=None).isoformat(),
                "error": "OpenSearch not configured",
            }

        try:
            info = client.info()
            return {
                "status": "healthy",
                "connected": True,
                "endpoint": self.endpoint,
                "cluster_name": info.get("cluster_name"),
                "version": (info.get("version") or {}).get("number"),
                "timestamp": datetime.now(timezone.utc).replace(tzinfo=None).isoformat(),
            }
        except Exception as exc:  # pylint: disable=broad-exception-caught
            return {
                "status": "degraded",
                "connected": False,
                "endpoint": self.endpoint,
                "timestamp": datetime.now(timezone.utc).replace(tzinfo=None).isoformat(),
                "error": str(exc),
            }

    def index_document(self, index: str, document: Dict[str, Any], doc_id: Optional[str] = None, refresh: bool = False) -> Dict[str, Any]:
        client = self._build_client()
        if client is None:
            raise RuntimeError("OpenSearch not configured")

        kwargs: Dict[str, Any] = {"index": index, "body": document}
        if doc_id:
            kwargs["id"] = doc_id
        if refresh:
            kwargs["refresh"] = True

        return client.index(**kwargs)

    def search(self, index: str, query: Dict[str, Any]) -> Dict[str, Any]:
        client = self._build_client()
        if client is None:
            raise RuntimeError("OpenSearch not configured")

        return client.search(index=index, body=query)
