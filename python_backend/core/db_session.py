import os
from pathlib import Path
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from core.database import Base
from core.external_config import database_config, filesystem_config


def _default_sqlite_url() -> str:
    # Prefer an explicit file path if provided via env/settings.
    sqlite_db_path = (database_config.sqlite_db_path or "").strip()
    if sqlite_db_path:
        db_path = Path(sqlite_db_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        return f"sqlite:///{db_path.as_posix()}"

    # Otherwise, derive from the centralized filesystem data root.
    data_root = (filesystem_config.data_root or "").strip() or "./data"
    filename = (database_config.sqlite_db_filename or "app.db").strip() or "app.db"
    db_path = Path(data_root) / filename
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{db_path.as_posix()}"


DATABASE_URL = (database_config.sqlalchemy_database_url or "").strip() or os.getenv("DATABASE_URL", "").strip() or _default_sqlite_url()

connect_args = {}
if DATABASE_URL.startswith("sqlite:"):
    connect_args = {"check_same_thread": False}

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db() -> None:
    # Ensure model modules are imported so Base.metadata is populated.
    import models.graphql_models  # noqa: F401
    import models.workflow_models  # noqa: F401

    Base.metadata.create_all(bind=engine)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
