import logging
import asyncio
from contextlib import asynccontextmanager
import neo4j
from fastapi import FastAPI
from services.advanced_migration_engine import migration_engine
from core.db_session import init_db
from .config import (
    NEO4J_URI,
    NEO4J_USER,
    NEO4J_PASSWORD,
    NEO4J_MAX_CONNECTION_POOL_SIZE,
    NEO4J_CONNECTION_ACQUISITION_TIMEOUT_S,
    NEO4J_CONNECTION_TIMEOUT_S,
    NEO4J_MAX_TRANSACTION_RETRY_TIME_S,
    NEO4J_MAX_CONNECTION_LIFETIME_S,
    NEO4J_HEALTHCHECK_INTERVAL_S,
)

# pylint: disable=broad-exception-caught

logger = logging.getLogger(__name__)


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
        # DB tables (SQLite by default) for persistence-backed features.
        init_db()

        logger.info("Attempting to create Neo4j driver for %s as user %s...", NEO4J_URI, NEO4J_USER)
        temp_driver = neo4j.AsyncGraphDatabase.driver(
            NEO4J_URI,
            auth=neo4j.basic_auth(NEO4J_USER, NEO4J_PASSWORD),
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
            # Allow background services (outside request context) to emit lineage best-effort.
            migration_engine.set_neo4j_driver(temp_driver)
            health_task = asyncio.create_task(_neo4j_health_loop(temp_driver))
        except TimeoutError:
            logger.warning("Neo4j connectivity verification timed out after 5s; starting API without Neo4j driver.")
            await temp_driver.close()
            app.state.driver = None
    except neo4j.exceptions.AuthError as auth_err:
        logger.error(
            "Neo4j Authentication Error: %s. Please check your NEO4J_USER and NEO4J_PASSWORD.",
            auth_err,
            exc_info=True,
        )
        app.state.driver = None
    except neo4j.exceptions.ServiceUnavailable as su_err:
        logger.error(
            "Neo4j Service Unavailable: %s. Please check NEO4J_URI and network connectivity.",
            su_err,
            exc_info=True,
        )
        app.state.driver = None
    except TypeError as te:
        logger.error("TypeError during Neo4j connection/verification: %s", te, exc_info=True)
        logger.error("This might indicate an issue with the driver call or an unexpected non-awaitable return if an await was used incorrectly elsewhere.")
        app.state.driver = None
    except (neo4j.exceptions.Neo4jError, RuntimeError, OSError, ValueError) as e:
        logger.error(
            "An unexpected error occurred during Neo4j driver initialization: %s - %s",
            type(e).__name__,
            e,
            exc_info=True,
        )
        app.state.driver = None

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