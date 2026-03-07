from fastapi import HTTPException, Request, WebSocketException
import neo4j

def get_driver(request: Request) -> neo4j.AsyncDriver:
    """Dependency to get the initialized Neo4j driver from application state (HTTP)."""
    driver = getattr(request.app.state, "driver", None)
    if not driver:
        raise HTTPException(status_code=503, detail="Neo4j driver not initialized or connection failed.")
    return driver


def get_ws_driver(websocket) -> neo4j.AsyncDriver:
    """Dependency to get the initialized Neo4j driver from application state (WebSocket)."""
    driver = getattr(websocket.app.state, "driver", None)
    if not driver:
        # WebSocketException properly closes the WS connection with a close frame.
        raise WebSocketException(code=1011, reason="Neo4j driver not initialized or connection failed.")
    return driver