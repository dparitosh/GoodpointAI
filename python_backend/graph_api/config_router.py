import logging
import os
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import neo4j
from datetime import datetime

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/config", tags=["Configuration Management"])

class Neo4jConfig(BaseModel):
    uri: str
    username: str
    password: str
    database: str = "neo4j"

class ConfigResponse(BaseModel):
    status: str
    message: str
    timestamp: str

@router.get(
    "/neo4j",
    summary="Get Neo4j Configuration",
    description="Get current Neo4j connection configuration (without sensitive data)."
)
async def get_neo4j_config():
    """Get current Neo4j configuration"""
    return {
        "uri": os.getenv("NEO4J_URI", "neo4j://127.0.0.1:7687"),
        "username": os.getenv("NEO4J_USER") or os.getenv("NEO4J_USERNAME", "neo4j"),
        "database": os.getenv("NEO4J_DATABASE", "neo4j"),
        "connection_status": "connected" if await test_neo4j_connection() else "disconnected"
    }

@router.post(
    "/neo4j",
    response_model=ConfigResponse,
    summary="Update Neo4j Configuration",
    description="Update Neo4j connection settings and test the connection."
)
async def update_neo4j_config(config: Neo4jConfig):
    """Update Neo4j configuration and test connection"""
    try:
        # Test the connection first
        test_driver = neo4j.AsyncGraphDatabase.driver(
            config.uri,
            auth=(config.username, config.password),
            database=config.database
        )
        
        # Verify connection works
        async with test_driver.session() as session:
            result = await session.run("RETURN 1 as test")
            await result.single()
        
        await test_driver.close()
        
        # If test successful, update environment variables
        os.environ["NEO4J_URI"] = config.uri
        # Prefer NEO4J_USER across the codebase; keep NEO4J_USERNAME for compatibility.
        os.environ["NEO4J_USER"] = config.username
        os.environ["NEO4J_USERNAME"] = config.username
        os.environ["NEO4J_PASSWORD"] = config.password
        os.environ["NEO4J_DATABASE"] = config.database
        
        # Write to .env file for persistence
        # Quote password to avoid '#' being treated as a comment.
        env_content = (
            f"NEO4J_URI=\"{config.uri}\"\n"
            f"NEO4J_USER=\"{config.username}\"\n"
            f"NEO4J_PASSWORD=\"{config.password}\"\n"
            f"NEO4J_DATABASE=\"{config.database}\"\n"
        )
        
        with open(".env", "w", encoding="utf-8") as f:
            f.write(env_content)
        
        return ConfigResponse(
            status="success",
            message="Neo4j configuration updated and connection verified successfully",
            timestamp=datetime.now().isoformat()
        )
        
    except (neo4j.exceptions.Neo4jError, neo4j.exceptions.DriverError, OSError, ValueError, RuntimeError) as exc:
        logger.error("Failed to update Neo4j configuration: %s", exc)
        raise HTTPException(
            status_code=400,
            detail=f"Failed to connect to Neo4j with provided settings: {str(exc)}"
        ) from exc

@router.post(
    "/neo4j/test",
    response_model=ConfigResponse,
    summary="Test Neo4j Connection",
    description="Test Neo4j connection with provided settings without saving."
)
async def test_neo4j_config(config: Neo4jConfig):
    """Test Neo4j connection without saving configuration"""
    try:
        test_driver = neo4j.AsyncGraphDatabase.driver(
            config.uri,
            auth=(config.username, config.password),
            database=config.database
        )
        
        async with test_driver.session() as session:
            result = await session.run("RETURN 1 as test")
            await result.single()
            
            # Get some basic info
            info_result = await session.run("CALL dbms.components() YIELD versions RETURN versions[0] as version")
            version_record = await info_result.single()
            version = version_record["version"] if version_record else "unknown"
        
        await test_driver.close()
        
        return ConfigResponse(
            status="success",
            message=f"Connection successful. Neo4j version: {version}",
            timestamp=datetime.now().isoformat()
        )
        
    except (neo4j.exceptions.Neo4jError, neo4j.exceptions.DriverError, OSError, ValueError, RuntimeError) as exc:
        logger.error("Neo4j connection test failed: %s", exc)
        return ConfigResponse(
            status="failed",
            message=f"Connection failed: {str(exc)}",
            timestamp=datetime.now().isoformat()
        )

@router.get(
    "/environment",
    summary="Get Environment Status",
    description="Get current environment configuration status."
)
async def get_environment_status():
    """Get environment configuration status"""
    return {
        "neo4j": {
            "configured": bool(os.getenv("NEO4J_URI")),
            "uri": os.getenv("NEO4J_URI", "Not configured"),
            "database": os.getenv("NEO4J_DATABASE", "neo4j")
        }
    }

async def test_neo4j_connection() -> bool:
    """Internal helper to test current Neo4j connection"""
    try:
        uri = os.getenv("NEO4J_URI")
        username = os.getenv("NEO4J_USER") or os.getenv("NEO4J_USERNAME")
        password = os.getenv("NEO4J_PASSWORD")

        if not uri or not username or not password:
            return False

        uri_str: str = uri
        username_str: str = username
        password_str: str = password
            
        test_driver = neo4j.AsyncGraphDatabase.driver(
                uri_str, auth=(username_str, password_str)
        )
        
        async with test_driver.session() as session:
            await session.run("RETURN 1")
        
        await test_driver.close()
        return True
        
    except (neo4j.exceptions.Neo4jError, neo4j.exceptions.DriverError, OSError, ValueError, RuntimeError) as exc:
        logger.error("Neo4j connection test failed: %s", exc)
        return False
