import os
import logging
from urllib.parse import quote_plus
from typing import Generator, Optional

from sqlalchemy import create_engine
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.engine.url import make_url
from sqlalchemy.exc import SQLAlchemyError

from core.database import Base
from core.external_config import database_config
from core.postgres_config import normalize_sqlalchemy_postgres_url

logger = logging.getLogger(__name__)

def _default_postgres_url() -> str:
    """Build PostgreSQL connection URL from POSTGRES_* environment variables.

    Priority order:
      1. DATABASE_URL (if set)
      2. POSTGRES_* environment variables (recommended)
      3. Hardcoded defaults

    Returns:
        postgresql+psycopg:// connection string

    Raises:
        ValueError: If configuration is invalid

    Environment Variables:
        POSTGRES_HOST: PostgreSQL server hostname (default: localhost)
        POSTGRES_PORT: PostgreSQL server port (default: 5432)
        POSTGRES_USER: PostgreSQL username (default: postgres)
        POSTGRES_PASSWORD: PostgreSQL password (required if postgres user)
        POSTGRES_DATABASE: Database name (default: graphtrace)
    """
    # Get configuration values (use first non-empty value)
    host = database_config.postgres_host or "localhost"
    database = database_config.postgres_database or "graphtrace"
    user = database_config.postgres_user or "postgres"
    password = database_config.postgres_password or ""

    # Validate and convert port
    try:
        port_str = str(database_config.postgres_port or 5432)
        port = int(port_str)
        if port < 1 or port > 65535:
            raise ValueError(f"Port must be 1-65535, got {port}")
    except (ValueError, TypeError) as e:
        logger.error(
            "Invalid POSTGRES_PORT. Expected 1-65535, got: %s. "
            "Check environment variable POSTGRES_PORT.",
            port_str
        )
        raise ValueError(
            f"Invalid POSTGRES_PORT={port_str}: {e}. Expected integer 1-65535."
        ) from e

    # Validate host
    if not isinstance(host, str) or not host:
        logger.error("Invalid POSTGRES_HOST: %s. Expected non-empty string.", repr(host))
        raise ValueError(f"Invalid POSTGRES_HOST: expected non-empty string, got {repr(host)}")

    # Validate database
    if not isinstance(database, str) or not database:
        logger.error("Invalid POSTGRES_DATABASE: %s. Expected non-empty string.", repr(database))
        raise ValueError(f"Invalid POSTGRES_DATABASE: expected non-empty string, got {repr(database)}")

    logger.info(
        "Building PostgreSQL connection: host=%s port=%d database=%s user=%s password=%s",
        host, port, database, user, "***" if password else "<empty>"
    )

    try:
        if password:
            encoded_pwd = quote_plus(password)
            return f"postgresql+psycopg://{user}:{encoded_pwd}@{host}:{port}/{database}"
        return f"postgresql+psycopg://{user}@{host}:{port}/{database}"
    except Exception as e:
        logger.error("Failed to build PostgreSQL URL: %s", str(e))
        raise ValueError("Failed to build PostgreSQL connection URL.") from e


DATABASE_URL = (
    f"{database_config.sqlalchemy_database_url or ''}"
    or os.getenv("DATABASE_URL", "")
    or _default_postgres_url()
)

DATABASE_URL = normalize_sqlalchemy_postgres_url(DATABASE_URL)

# Validate configuration
if DATABASE_URL.startswith("sqlite:"):
    error_msg = (
        "SQLite is not supported as configured. "
        "GraphTrace requires PostgreSQL for data persistence. "
        "Configure via DATABASE_URL or POSTGRES_* environment variables. "
        "See INSTALLATION.md and POSTGRESQL_CONNECTION_TROUBLESHOOTING.md"
    )
    logger.error(error_msg)
    raise RuntimeError(error_msg)

if not DATABASE_URL or not DATABASE_URL.startswith(("postgresql://", "postgresql+psycopg://")):
    error_msg = (
        f"Invalid database configuration: {redacted_database_url()}. "
        f"Expected postgresql:// connection string. "
        f"Check DATABASE_URL or POSTGRES_* environment variables."
    )
    logger.error(error_msg)
    raise RuntimeError(error_msg)

logger.info("Database URL configured: %s", redacted_database_url())

connect_args: dict[str, object] = {}

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db() -> None:
    # Ensure model modules are imported so Base.metadata is populated.
    import importlib

    for module_name in (
        "models.configuration_models",
        "models.graphql_models",
        "models.workflow_models",
        "models.plm_models",
        "models.quality_models",
        "models.report_models",
        "models.pipeline_config_models",
        "models.admin_config_models",
        "models.rule_engine_models",
    ):
        importlib.import_module(module_name)

    Base.metadata.create_all(bind=engine)


def redacted_database_url() -> str:
    """Return DATABASE_URL with credentials removed (safe for logs).
    
    Returns a human-readable connection string with password redacted.
    Useful for logging without exposing sensitive credentials.
    
    Returns:
        Redacted connection string or error description
    """
    try:
        url = make_url(DATABASE_URL)
        # Keep username visible, redact password for security
        return str(url.set(password="***"))
    except (ValueError, TypeError) as e:
        logger.warning("Failed to parse DATABASE_URL for redaction: %s", e)
        return "(unavailable - invalid connection string)"


def verify_database_connectivity(timeout_s: float = 5.0) -> Optional[str]:
    """Verify the configured PostgreSQL database is reachable.

    This function performs a simple connectivity test by executing
    a lightweight query. Useful for startup validation and health checks.

    Args:
        timeout_s: Connection timeout in seconds (default: 5.0, range: 1-60)

    Returns:
        None if connection successful
        Error message string if connection failed

    Example:
        error = verify_database_connectivity(timeout_s=10)
        if error:
            logger.error(f"Database unavailable: {error}")
            sys.exit(1)
    """
    # Validate timeout range
    if not (1 <= timeout_s <= 60):
        return f"Invalid timeout value: {timeout_s}. Expected 1-60 seconds."
    
    logger.info("Testing database connectivity (timeout: %.1fs)...", timeout_s)
    
    try:
        # Force a real database round-trip (engine connect is lazy)
        with engine.connect() as connection:
            connection.execution_options(timeout=timeout_s)
            connection.execute(text("SELECT 1"))
        
        logger.info("✓ Database connection verified. Connected to: %s", redacted_database_url())
        return None
        
    except TimeoutError as e:
        error_msg = (
            f"Database connection timeout ({timeout_s}s). "
            f"Server may be unresponsive. Check POSTGRES_HOST and POSTGRES_PORT."
        )
        logger.error(error_msg)
        return error_msg
        
    except ConnectionError as e:
        error_msg = (
            f"Cannot connect to PostgreSQL server. "
            f"Check POSTGRES_HOST and POSTGRES_PORT are correct. Error: {e}"
        )
        logger.error(error_msg)
        return error_msg
        
    except Exception as e:
        error_msg = f"{type(e).__name__}: {e}"
        logger.error(
            "Database connectivity check failed: %s. Configuration: %s",
            error_msg,
            redacted_database_url()
        )
        return error_msg


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
