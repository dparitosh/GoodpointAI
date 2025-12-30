import logging
import asyncio
from contextlib import asynccontextmanager
import neo4j
from fastapi import FastAPI
from services.advanced_migration_engine import migration_engine
from core.crypto import decrypt_json, encrypt_json
from core.db_session import SessionLocal, init_db, redacted_database_url, verify_database_connectivity
from models.configuration_models import EncryptedConfig, DataSourceConfigRecord
from .config import (
    NEO4J_URI,
    NEO4J_USER,
    NEO4J_PASSWORD,
    NEO4J_DATABASE,
    NEO4J_MAX_CONNECTION_POOL_SIZE,
    NEO4J_CONNECTION_ACQUISITION_TIMEOUT_S,
    NEO4J_CONNECTION_TIMEOUT_S,
    NEO4J_MAX_TRANSACTION_RETRY_TIME_S,
    NEO4J_MAX_CONNECTION_LIFETIME_S,
    NEO4J_HEALTHCHECK_INTERVAL_S,
)

# pylint: disable=broad-exception-caught

logger = logging.getLogger(__name__)


def _migrate_postgres_port_5432_to_5433() -> None:
    """One-time/idempotent migration for local dev: update saved data sources from 5432 -> 5433.

    Only touches data sources whose decrypted connection payload has port 5432, and only for
    SQL/Postgres-like source types.
    """
    db = SessionLocal()
    updated = 0
    try:
        rows = db.query(DataSourceConfigRecord).all()
        for row in rows:
            if (row.type or "").lower() not in {"database", "postgres", "postgresql"}:
                continue

            try:
                connection = decrypt_json(row.connection_ciphertext)
            except ValueError as exc:
                # Likely missing/invalid encryption key in this environment.
                logger.warning("Skipping port migration for data source %s: %s", row.id, exc)
                continue
            except Exception as exc:  # pylint: disable=broad-exception-caught
                logger.warning("Skipping port migration for data source %s: %s", row.id, exc)
                continue

            if not isinstance(connection, dict):
                continue

            port = connection.get("port")
            if str(port) != "5432":
                continue

            connection["port"] = "5433"
            try:
                row.connection_ciphertext = encrypt_json(connection)
            except ValueError as exc:
                logger.warning("Failed to re-encrypt migrated connection for %s: %s", row.id, exc)
                continue

            updated += 1

        if updated:
            db.commit()
            logger.info("Migrated %s data source(s) from port 5432 to 5433", updated)
    finally:
        db.close()


async def _neo4j_health_loop(driver: neo4j.AsyncDriver) -> None:
    while True:
        try:
            await asyncio.wait_for(driver.verify_connectivity(), timeout=5)
        except TimeoutError:
            logger.warning("Neo4j periodic connectivity verification timed out after 5s")
        except asyncio.CancelledError:
            return
        except Exception as exc:  # pylint: disable=broad-exception-caught
            logger.warning("Neo4j periodic connectivity verification failed: %s", exc)
        await asyncio.sleep(max(1.0, float(NEO4J_HEALTHCHECK_INTERVAL_S)))

@asynccontextmanager
async def lifespan_manager(app: FastAPI):
    """
    Manages the Neo4j driver lifecycle.
    The driver is created on startup and closed on shutdown.
    The driver instance is stored in `app.state.driver`.
    """
    temp_driver: neo4j.AsyncDriver | None = None
    health_task: asyncio.Task[None] | None = None
    try:
        # Default dependency readiness flags (populated during startup probes).
        app.state.db_ok = False
        app.state.neo4j_ok = False

        # DB tables for persistence-backed features.
        # Best-effort: allow API (and Neo4j) to start even if schema init fails.
        try:
            init_db()
        except Exception as exc:  # pylint: disable=broad-exception-caught
            logger.warning(
                "DB schema initialization failed; starting API with DB marked unhealthy until verified: %s",
                exc,
            )

        # Explicit DB connectivity verification (mirrors the Neo4j verify_connectivity logs).
        db_url_safe = redacted_database_url()
        logger.info("Attempting to verify database connectivity for %s...", db_url_safe)
        db_error = verify_database_connectivity(timeout_s=5.0)
        if db_error is None:
            logger.info("Successfully connected to database and verified connectivity.")
            app.state.db_ok = True
        else:
            logger.warning(
                "Database connectivity verification failed; starting API with DB marked unhealthy: %s",
                db_error,
            )
            app.state.db_ok = False

        # Seed install-friendly defaults into DB-backed config (best-effort).
        # This keeps .env optional and lets the UI manage configuration post-install.
        if app.state.db_ok:
            try:
                from scripts.seed_db_config import seed_defaults

                seeded = seed_defaults(force=False)
                if seeded:
                    logger.info("Seeded default DB configuration keys: %s", ", ".join(seeded))
            except Exception as exc:  # pylint: disable=broad-exception-caught
                logger.warning("DB config seeding failed (non-fatal): %s", exc)

        # Prefer DB-stored encrypted Neo4j config when available.
        neo4j_uri = NEO4J_URI
        neo4j_user = NEO4J_USER
        neo4j_password = NEO4J_PASSWORD
        neo4j_database = NEO4J_DATABASE

        if app.state.db_ok:
            try:
                db = SessionLocal()
                try:
                    row = db.get(EncryptedConfig, "neo4j")
                    if row is not None:
                        payload = decrypt_json(row.ciphertext)
                        if isinstance(payload, dict):
                            neo4j_uri = str(payload.get("uri") or neo4j_uri)
                            neo4j_user = str(payload.get("username") or neo4j_user)
                            neo4j_password = str(payload.get("password") or neo4j_password)
                            neo4j_database = str(payload.get("database") or neo4j_database)
                finally:
                    db.close()
            except ValueError as exc:
                logger.warning("Neo4j config exists but cannot be decrypted (encryption key missing?): %s", exc)
            except Exception as exc:  # pylint: disable=broad-exception-caught
                logger.warning("Failed to load Neo4j config from DB; falling back to env: %s", exc)

            # Dev-convenience migration: some environments run Postgres on 5433.
            try:
                _migrate_postgres_port_5432_to_5433()
            except Exception as exc:  # pylint: disable=broad-exception-caught
                logger.warning("Data source port migration failed (non-fatal): %s", exc)

        logger.info("Attempting to create Neo4j driver for %s as user %s...", neo4j_uri, neo4j_user)
        temp_driver = neo4j.AsyncGraphDatabase.driver(
            neo4j_uri,
            auth=neo4j.basic_auth(neo4j_user, neo4j_password),
            database=neo4j_database,
            max_connection_pool_size=NEO4J_MAX_CONNECTION_POOL_SIZE,
            connection_acquisition_timeout=NEO4J_CONNECTION_ACQUISITION_TIMEOUT_S,
            connection_timeout=NEO4J_CONNECTION_TIMEOUT_S,
            max_transaction_retry_time=NEO4J_MAX_TRANSACTION_RETRY_TIME_S,
            max_connection_lifetime=NEO4J_MAX_CONNECTION_LIFETIME_S,
        )
        logger.info("Neo4j driver object created. Attempting to verify connectivity...")

        try:
            await asyncio.wait_for(temp_driver.verify_connectivity(), timeout=5)
            logger.info("Successfully connected to Neo4j and verified connectivity.")
            app.state.driver = temp_driver
            app.state.neo4j_ok = True
            # Allow background services (outside request context) to emit lineage best-effort.
            migration_engine.set_neo4j_driver(temp_driver)
            health_task = asyncio.create_task(_neo4j_health_loop(temp_driver))
        except TimeoutError:
            logger.warning("Neo4j connectivity verification timed out after 5s; starting API without Neo4j driver.")
            await temp_driver.close()
            app.state.driver = None
            app.state.neo4j_ok = False
    except neo4j.exceptions.AuthError as auth_err:
        logger.error(
            "Neo4j Authentication Error: %s. Please check your NEO4J_USER and NEO4J_PASSWORD.",
            auth_err,
            exc_info=True,
        )
        app.state.driver = None
        app.state.neo4j_ok = False
    except neo4j.exceptions.ServiceUnavailable as su_err:
        logger.error(
            "Neo4j Service Unavailable: %s. Please check NEO4J_URI and network connectivity.",
            su_err,
            exc_info=True,
        )
        app.state.driver = None
        app.state.neo4j_ok = False
    except TypeError as te:
        logger.error("TypeError during Neo4j connection/verification: %s", te, exc_info=True)
        logger.error("This might indicate an issue with the driver call or an unexpected non-awaitable return if an await was used incorrectly elsewhere.")
        app.state.driver = None
        app.state.neo4j_ok = False
    except (neo4j.exceptions.Neo4jError, RuntimeError, OSError, ValueError) as e:
        logger.error(
            "An unexpected error occurred during Neo4j driver initialization: %s - %s",
            type(e).__name__,
            e,
            exc_info=True,
        )
        app.state.driver = None
        app.state.neo4j_ok = False

    yield

    if health_task is not None:
        health_task.cancel()
        try:
            await health_task
        except asyncio.CancelledError:
            pass

    driver = getattr(app.state, "driver", None)
    if driver:
        logger.info("Closing Neo4j driver...")
        await driver.close()
        logger.info("Neo4j driver closed.")