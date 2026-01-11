from fastapi import HTTPException, Request, WebSocket
import neo4j

def get_driver(request: Request) -> neo4j.AsyncDriver:
    """Dependency to get the initialized Neo4j driver from application state (HTTP)."""
    driver = getattr(request.app.state, "driver", None)
    if not driver:
        raise HTTPException(status_code=503, detail="Neo4j driver not initialized or connection failed.")
    return driver


def get_ws_driver(websocket: WebSocket) -> neo4j.AsyncDriver:
    """Dependency to get the initialized Neo4j driver from application state (WebSocket)."""
    driver = getattr(websocket.app.state, "driver", None)
    if not driver:
        raise HTTPException(status_code=503, detail="Neo4j driver not initialized or connection failed.")
    return driver