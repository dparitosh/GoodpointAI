import os
from urllib.parse import quote_plus
from typing import Generator, Optional

from sqlalchemy import create_engine
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.engine.url import make_url

from core.database import Base
from core.external_config import database_config
from core.postgres_config import normalize_sqlalchemy_postgres_url

def _default_postgres_url() -> str:
    """Build a Postgres DATABASE_URL from POSTGRES_* settings.

    This makes Postgres the default app DB.
    """

    host = f"{database_config.postgres_host or 'localhost'}" or "localhost"
    port = int(database_config.postgres_port or 5432)
    database = f"{database_config.postgres_database or 'graphtrace'}" or "graphtrace"
    user = f"{database_config.postgres_user or 'postgres'}" or "postgres"
    password = f"{database_config.postgres_password or ''}"

    if password:
        return f"postgresql+psycopg://{user}:{quote_plus(password)}@{host}:{port}/{database}"
    return f"postgresql+psycopg://{user}@{host}:{port}/{database}"


DATABASE_URL = (
    f"{database_config.sqlalchemy_database_url or ''}"
    or os.getenv("DATABASE_URL", "")
    or _default_postgres_url()
)

DATABASE_URL = normalize_sqlalchemy_postgres_url(DATABASE_URL)

connect_args: dict[str, object] = {}
if DATABASE_URL.startswith("sqlite:"):
    # Product requirement: Postgres is the single source of truth for persistence.
    raise RuntimeError(
        "SQLite is not supported. Configure Postgres via DATABASE_URL or POSTGRES_* environment variables."
    )

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
    """Return DATABASE_URL with credentials removed (safe for logs)."""
    try:
        url = make_url(DATABASE_URL)
        # keep username visible, redact password
        return str(url.set(password="***"))
    except Exception:  # pylint: disable=broad-exception-caught
        return "(unavailable)"


def verify_database_connectivity(timeout_s: float = 5.0) -> Optional[str]:
    """Verify the configured DB is reachable.

    Returns:
      - None on success
      - error message string on failure
    """
    # Engine connect is lazy; force a real round-trip.
    try:
        with engine.connect() as connection:
            # lightweight connectivity probe
            connection.execution_options(timeout=timeout_s)
            connection.execute(text("SELECT 1"))
        return None
    except Exception as exc:  # pylint: disable=broad-exception-caught
        return f"{type(exc).__name__}: {exc}"


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
