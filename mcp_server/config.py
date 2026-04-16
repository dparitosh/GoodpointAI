from pathlib import Path
from pydantic_settings import BaseSettings
from functools import lru_cache


_REPO_ROOT = Path(__file__).resolve().parent.parent
_BACKEND_ENV_FILE = _REPO_ROOT / "python_backend" / ".env"

class Settings(BaseSettings):
    MCP_SERVER_ID: str = "mcp-server-01"
    MCP_SERVER_PORT: int = 8012
    MCP_SERVER_HOST: str = "0.0.0.0"
    
    # Database
    # Use empty defaults for passwords to ensure security. 
    # Valid values must be provided formatted in .env (see python_backend/.env.example)
    DATABASE_URL: str = ""  # Set via DATABASE_URL in python_backend/.env
    REDIS_URL: str = "redis://localhost:6379/0"
    NEO4J_URI: str = "neo4j://localhost:7687"
    NEO4J_USERNAME: str = "neo4j"
    NEO4J_PASSWORD: str = ""
    
    # Queue
    AZURE_SERVICE_BUS_CONNECTION_STRING: str = ""
    MCP_QUEUE_NAME: str = "mcp-tasks"
    
    # Logging
    LOG_LEVEL: str = "INFO"
    
    # Feature Flags
    ENABLE_METRICS: bool = True
    ENABLE_TRACING: bool = True
    
    model_config = {
        # Use the shared backend env file so the whole stack is configured from one place.
        "env_file": str(_BACKEND_ENV_FILE),
        "case_sensitive": True,
        "extra": "ignore"
    }

@lru_cache()
def get_settings():
    return Settings()
