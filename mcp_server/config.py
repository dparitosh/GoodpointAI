import os
from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    MCP_SERVER_ID: str = "mcp-server-01"
    MCP_SERVER_PORT: int = 8012
    MCP_SERVER_HOST: str = "0.0.0.0"
    
    # Database
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/graphtrace"
    REDIS_URL: str = "redis://localhost:6379/0"
    NEO4J_URI: str = "neo4j://localhost:7687"
    NEO4J_USERNAME: str = "neo4j"
    NEO4J_PASSWORD: str = "password"
    
    # Queue
    AZURE_SERVICE_BUS_CONNECTION_STRING: str = ""
    MCP_QUEUE_NAME: str = "mcp-tasks"
    
    # Logging
    LOG_LEVEL: str = "INFO"
    
    # Feature Flags
    ENABLE_METRICS: bool = True
    ENABLE_TRACING: bool = True
    
    model_config = {
        "env_file": ".env",
        "case_sensitive": True,
        "extra": "ignore"
    }

@lru_cache()
def get_settings():
    return Settings()
