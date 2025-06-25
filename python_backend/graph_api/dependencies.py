from fastapi import Request, HTTPException
import neo4j

def get_driver(request: Request) -> neo4j.AsyncDriver:
    """Dependency to get the initialized Neo4j driver from application state."""
    driver = getattr(request.app.state, "driver", None)
    if not driver:
        raise HTTPException(status_code=503, detail="Neo4j driver not initialized or connection failed.")
    return driver