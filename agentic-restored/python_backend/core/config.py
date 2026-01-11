import logging
import os

logger = logging.getLogger(__name__)

# NOTE:
# - The installed application should use DB-backed configuration (EncryptedConfig).
# - We keep environment variables as a *bootstrap/fallback* only.
# - Do not auto-load a repo-local .env here.

NEO4J_URI = os.getenv("NEO4J_URI", "neo4j://127.0.0.1:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
# No insecure/hardcoded default password.
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE", "neo4j")


def _get_int_env(name: str, default: int) -> int:

    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw)
    except ValueError:
        logger.warning("Invalid int for %s=%r; using default %s", name, raw, default)
        return default


def _get_float_env(name: str, default: float) -> float:

    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        return float(raw)
    except ValueError:
        logger.warning("Invalid float for %s=%r; using default %s", name, raw, default)
        return default


# Neo4j driver tuning (optional)
NEO4J_MAX_CONNECTION_POOL_SIZE = _get_int_env("NEO4J_MAX_CONNECTION_POOL_SIZE", 50)
NEO4J_CONNECTION_ACQUISITION_TIMEOUT_S = _get_float_env("NEO4J_CONNECTION_ACQUISITION_TIMEOUT_S", 30.0)
NEO4J_CONNECTION_TIMEOUT_S = _get_float_env("NEO4J_CONNECTION_TIMEOUT_S", 10.0)
NEO4J_MAX_TRANSACTION_RETRY_TIME_S = _get_float_env("NEO4J_MAX_TRANSACTION_RETRY_TIME_S", 30.0)
NEO4J_MAX_CONNECTION_LIFETIME_S = _get_float_env("NEO4J_MAX_CONNECTION_LIFETIME_S", 3600.0)
NEO4J_HEALTHCHECK_INTERVAL_S = _get_float_env("NEO4J_HEALTHCHECK_INTERVAL_S", 60.0)

