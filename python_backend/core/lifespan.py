import logging
from contextlib import asynccontextmanager
from anyio import to_thread
import neo4j
from fastapi import FastAPI
from .config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan_manager(app: FastAPI):
    """
    Manages the Neo4j driver lifecycle.
    The driver is created on startup and closed on shutdown.
    The driver instance is stored in `app.state.driver`.
    """
    temp_driver: neo4j.AsyncDriver | None = None
    try:
        logger.info(f"Attempting to create Neo4j driver for {NEO4J_URI} as user {NEO4J_USER}...")
        temp_driver = neo4j.AsyncGraphDatabase.driver(NEO4J_URI, auth=neo4j.basic_auth(NEO4J_USER, NEO4J_PASSWORD))
        logger.info("Neo4j driver object created. Attempting to verify connectivity...")

        await to_thread.run_sync(temp_driver.verify_connectivity)

        logger.info("Successfully connected to Neo4j and verified connectivity.")
        app.state.driver = temp_driver
    except neo4j.exceptions.AuthError as auth_err:
        logger.error(f"Neo4j Authentication Error: {auth_err}. Please check your NEO4J_USER and NEO4J_PASSWORD.", exc_info=True)
        app.state.driver = None
    except neo4j.exceptions.ServiceUnavailable as su_err:
        logger.error(f"Neo4j Service Unavailable: {su_err}. Please check NEO4J_URI and network connectivity.", exc_info=True)
        app.state.driver = None
    except TypeError as te:
        logger.error(f"TypeError during Neo4j connection/verification: {te}", exc_info=True)
        logger.error("This might indicate an issue with the driver call or an unexpected non-awaitable return if an await was used incorrectly elsewhere.")
        app.state.driver = None
    except Exception as e:
        logger.error(f"An unexpected error occurred during Neo4j driver initialization: {type(e).__name__} - {e}", exc_info=True)
        app.state.driver = None

    yield

    driver = getattr(app.state, "driver", None)
    if driver:
        logger.info("Closing Neo4j driver...")
        await driver.close()
        logger.info("Neo4j driver closed.")