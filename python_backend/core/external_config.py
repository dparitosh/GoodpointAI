"""
External Integration Configuration
Manages all external service connections and credentials
"""
import logging
import os
from pathlib import Path
from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from typing import List, Optional

# Load environment variables
# In installed/service deployments, configuration should be stored in the DB.
# Allow opting into repo-local `.env` loading for local development only.
dotenv_path = Path(__file__).resolve().parent.parent / '.env'
_LOAD_DOTENV = (os.getenv("GRAPH_TRACE_LOAD_DOTENV") or "").strip().lower() in {"1", "true", "yes"}
if _LOAD_DOTENV:
    load_dotenv(dotenv_path=dotenv_path, override=True)
logger = logging.getLogger(__name__)


def reload_dotenv(*, override: bool = True) -> str:
    """Reload variables from the repo-local `.env` file.

    This is useful for endpoints that want to pick up integration configuration
    changes without requiring a full process restart.
    """
    if not _LOAD_DOTENV:
        return str(dotenv_path)

    load_dotenv(dotenv_path=dotenv_path, override=override)
    return str(dotenv_path)


class AzureConfig(BaseSettings):
    """Azure Cloud Services Configuration"""
    model_config = SettingsConfigDict(env_prefix="", extra="ignore")
    # Storage
    storage_account_name: str = Field(default="", validation_alias="AZURE_STORAGE_ACCOUNT")
    storage_account_key: str = Field(default="", validation_alias="AZURE_STORAGE_KEY")
    storage_connection_string: str = Field(default="", validation_alias="AZURE_STORAGE_CONNECTION_STRING")
    blob_container_name: str = Field(default="plm-data", validation_alias="AZURE_BLOB_CONTAINER")
    datalake_container_name: str = Field(default="raw-data", validation_alias="AZURE_DATALAKE_CONTAINER")
    
    # Cosmos DB
    cosmos_endpoint: str = Field(default="", validation_alias="AZURE_COSMOS_ENDPOINT")
    cosmos_key: str = Field(default="", validation_alias="AZURE_COSMOS_KEY")
    cosmos_database: str = Field(default="graphtrace", validation_alias="AZURE_COSMOS_DATABASE")
    
    # Service Bus
    servicebus_connection_string: str = Field(default="", validation_alias="AZURE_SERVICEBUS_CONNECTION")
    servicebus_queue_name: str = Field(default="workflow-queue", validation_alias="AZURE_SERVICEBUS_QUEUE")
    
    # Event Hub
    eventhub_connection_string: str = Field(default="", validation_alias="AZURE_EVENTHUB_CONNECTION")
    eventhub_name: str = Field(default="plm-events", validation_alias="AZURE_EVENTHUB_NAME")
    
    # Key Vault
    keyvault_url: str = Field(default="", validation_alias="AZURE_KEYVAULT_URL")
    
    # Authentication
    tenant_id: str = Field(default="", validation_alias="AZURE_TENANT_ID")
    client_id: str = Field(default="", validation_alias="AZURE_CLIENT_ID")
    client_secret: str = Field(default="", validation_alias="AZURE_CLIENT_SECRET")


class AWSConfig(BaseSettings):
    """AWS Cloud Services Configuration"""
    model_config = SettingsConfigDict(env_prefix="", extra="ignore")
    # General
    access_key_id: str = Field(default="", validation_alias="AWS_ACCESS_KEY_ID")
    secret_access_key: str = Field(default="", validation_alias="AWS_SECRET_ACCESS_KEY")
    region: str = Field(default="us-east-1", validation_alias="AWS_REGION")
    
    # S3
    s3_bucket_name: str = Field(default="plm-data-bucket", validation_alias="AWS_S3_BUCKET")
    s3_prefix: str = Field(default="raw/", validation_alias="AWS_S3_PREFIX")
    
    # DynamoDB
    dynamodb_table_name: str = Field(default="workflow-state", validation_alias="AWS_DYNAMODB_TABLE")
    
    # SQS
    sqs_queue_url: str = Field(default="", validation_alias="AWS_SQS_QUEUE_URL")
    
    # Lambda
    lambda_function_arn: str = Field(default="", validation_alias="AWS_LAMBDA_FUNCTION_ARN")
    
    # API Gateway
    api_gateway_url: str = Field(default="", validation_alias="AWS_API_GATEWAY_URL")


class ODataConfig(BaseSettings):
    """OData Service Configuration"""
    model_config = SettingsConfigDict(env_prefix="", extra="ignore")
    # SAP OData
    sap_odata_url: str = Field(default="", validation_alias="SAP_ODATA_URL")
    sap_username: str = Field(default="", validation_alias="SAP_USERNAME")
    sap_password: str = Field(default="", validation_alias="SAP_PASSWORD")
    sap_client: str = Field(default="100", validation_alias="SAP_CLIENT")
    
    # Generic OData
    odata_service_url: str = Field(default="", validation_alias="ODATA_SERVICE_URL")
    odata_auth_type: str = Field(default="basic", validation_alias="ODATA_AUTH_TYPE")  # basic, oauth2, apikey
    odata_username: str = Field(default="", validation_alias="ODATA_USERNAME")
    odata_password: str = Field(default="", validation_alias="ODATA_PASSWORD")
    odata_api_key: str = Field(default="", validation_alias="ODATA_API_KEY")
    odata_token_url: str = Field(default="", validation_alias="ODATA_TOKEN_URL")


class LLMConfig(BaseSettings):
    """LLM Service Configuration"""
    model_config = SettingsConfigDict(env_prefix="", extra="ignore")
    # OpenAI
    openai_api_key: str = Field(default="", validation_alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4-turbo-preview", validation_alias="OPENAI_MODEL")
    openai_embedding_model: str = Field(default="text-embedding-3-small", validation_alias="OPENAI_EMBEDDING_MODEL")
    
    # Anthropic Claude
    anthropic_api_key: str = Field(default="", validation_alias="ANTHROPIC_API_KEY")
    anthropic_model: str = Field(default="claude-3-sonnet-20240229", validation_alias="ANTHROPIC_MODEL")
    
    # Azure OpenAI
    azure_openai_endpoint: str = Field(default="", validation_alias="AZURE_OPENAI_ENDPOINT")
    azure_openai_key: str = Field(default="", validation_alias="AZURE_OPENAI_KEY")
    azure_openai_deployment: str = Field(default="", validation_alias="AZURE_OPENAI_DEPLOYMENT")
    azure_openai_api_version: str = Field(default="2024-02-15-preview", validation_alias="AZURE_OPENAI_API_VERSION")
    
    # Ollama Local
    ollama_base_url: str = Field(default="http://localhost:11434", validation_alias="OLLAMA_BASE_URL")
    ollama_model: str = Field(default="llama2", validation_alias="OLLAMA_MODEL")


class PLMConfig(BaseSettings):
    """PLM System Configuration"""
    model_config = SettingsConfigDict(env_prefix="", extra="ignore")
    # Teamcenter
    teamcenter_url: str = Field(default="", validation_alias="TEAMCENTER_URL")
    teamcenter_username: str = Field(default="", validation_alias="TEAMCENTER_USERNAME")
    teamcenter_password: str = Field(default="", validation_alias="TEAMCENTER_PASSWORD")
    teamcenter_soap_url: str = Field(default="", validation_alias="TEAMCENTER_SOAP_URL")
    teamcenter_rest_url: str = Field(default="", validation_alias="TEAMCENTER_REST_URL")
    
    # Windchill
    windchill_url: str = Field(default="", validation_alias="WINDCHILL_URL")
    windchill_username: str = Field(default="", validation_alias="WINDCHILL_USERNAME")
    windchill_password: str = Field(default="", validation_alias="WINDCHILL_PASSWORD")
    windchill_context_path: str = Field(default="/Windchill", validation_alias="WINDCHILL_CONTEXT_PATH")
    
    # ENOVIA/3DEXPERIENCE
    enovia_url: str = Field(default="", validation_alias="ENOVIA_URL")
    enovia_username: str = Field(default="", validation_alias="ENOVIA_USERNAME")
    enovia_password: str = Field(default="", validation_alias="ENOVIA_PASSWORD")
    enovia_security_context: str = Field(default="", validation_alias="ENOVIA_SECURITY_CONTEXT")
    
    # Aras Innovator
    aras_url: str = Field(default="", validation_alias="ARAS_URL")
    aras_database: str = Field(default="", validation_alias="ARAS_DATABASE")
    aras_username: str = Field(default="", validation_alias="ARAS_USERNAME")
    aras_password: str = Field(default="", validation_alias="ARAS_PASSWORD")


class FileSystemConfig(BaseSettings):
    """File System Configuration"""
    model_config = SettingsConfigDict(env_prefix="", extra="ignore")
    # Data directories
    data_root: str = Field(default="./data", validation_alias="DATA_ROOT_PATH")
    upload_dir: str = Field(default="./data/uploads", validation_alias="UPLOAD_DIR")
    temp_dir: str = Field(default="./data/temp", validation_alias="TEMP_DIR")
    export_dir: str = Field(default="./data/exports", validation_alias="EXPORT_DIR")
    log_dir: str = Field(default="./logs", validation_alias="LOG_DIR")
    
    # File locations
    xml_input_path: str = Field(default="./data/xml/input", validation_alias="XML_INPUT_PATH")
    json_input_path: str = Field(default="./data/json/input", validation_alias="JSON_INPUT_PATH")
    csv_input_path: str = Field(default="./data/csv/input", validation_alias="CSV_INPUT_PATH")
    
    # Folder monitoring
    watch_folders: List[str] = Field(default_factory=lambda: ["./data/watch"], validation_alias="WATCH_FOLDERS")
    
    # File size limits (in MB)
    max_upload_size_mb: int = Field(default=100, validation_alias="MAX_UPLOAD_SIZE_MB")
    max_batch_size_mb: int = Field(default=500, validation_alias="MAX_BATCH_SIZE_MB")


class DatabaseConfig(BaseSettings):
    """Database Configuration"""
    model_config = SettingsConfigDict(env_prefix="", extra="ignore")
    # SQLAlchemy (primary app DB)
    sqlalchemy_database_url: str = Field(default="", validation_alias="DATABASE_URL")
    sqlite_db_path: str = Field(default="", validation_alias="SQLITE_DB_PATH")
    sqlite_db_filename: str = Field(default="app.db", validation_alias="SQLITE_DB_FILENAME")

    # PostgreSQL
    postgres_host: str = Field(default="localhost", validation_alias="POSTGRES_HOST")
    postgres_port: int = Field(default=5433, validation_alias="POSTGRES_PORT")
    postgres_database: str = Field(default="graphtrace", validation_alias="POSTGRES_DATABASE")
    postgres_user: str = Field(default="postgres", validation_alias="POSTGRES_USER")
    postgres_password: str = Field(default="", validation_alias="POSTGRES_PASSWORD")
    
    # Neo4j (already in config.py, but included for completeness)
    neo4j_uri: str = Field(default="neo4j://127.0.0.1:7687", validation_alias="NEO4J_URI")
    neo4j_user: str = Field(default="neo4j", validation_alias="NEO4J_USER")
    neo4j_password: str = Field(default="", validation_alias="NEO4J_PASSWORD")
    neo4j_database: str = Field(default="neo4j", validation_alias="NEO4J_DATABASE")
    
    # Redis
    redis_host: str = Field(default="localhost", validation_alias="REDIS_HOST")
    redis_port: int = Field(default=6379, validation_alias="REDIS_PORT")
    redis_password: str = Field(default="", validation_alias="REDIS_PASSWORD")
    redis_db: int = Field(default=0, validation_alias="REDIS_DB")


class APIGatewayConfig(BaseSettings):
    """API Gateway Configuration"""
    model_config = SettingsConfigDict(env_prefix="", extra="ignore")
    # Generic API Gateway
    gateway_url: str = Field(default="", validation_alias="API_GATEWAY_URL")
    gateway_api_key: str = Field(default="", validation_alias="API_GATEWAY_KEY")
    gateway_secret: str = Field(default="", validation_alias="API_GATEWAY_SECRET")
    
    # Kong
    kong_admin_url: str = Field(default="http://localhost:8001", validation_alias="KONG_ADMIN_URL")
    kong_gateway_url: str = Field(default="http://localhost:8000", validation_alias="KONG_GATEWAY_URL")
    kong_api_key: str = Field(default="", validation_alias="KONG_API_KEY")
    
    # Apigee
    apigee_org: str = Field(default="", validation_alias="APIGEE_ORG")
    apigee_env: str = Field(default="", validation_alias="APIGEE_ENV")
    apigee_username: str = Field(default="", validation_alias="APIGEE_USERNAME")
    apigee_password: str = Field(default="", validation_alias="APIGEE_PASSWORD")


# Initialize all configurations
azure_config = AzureConfig()
aws_config = AWSConfig()
odata_config = ODataConfig()
llm_config = LLMConfig()
plm_config = PLMConfig()
filesystem_config = FileSystemConfig()
database_config = DatabaseConfig()
api_gateway_config = APIGatewayConfig()


# ============================================================================
# Admin Config Integration
# ============================================================================

def get_llm_config_with_db_fallback(provider: "Optional[str]" = None, db_session=None) -> dict:
    """
    Get LLM configuration with database-first fallback to environment.
    
    This function checks the admin config database first, then falls back
    to the environment-based LLMConfig class.
    
    Args:
        provider: Optional provider name. If None, returns active provider.
        db_session: Optional SQLAlchemy session for database access.
    
    Returns:
        Dict with LLM configuration
    """
    # Try database first
    if db_session is not None:
        try:
            from services.admin_config_service import AdminConfigService
            config_service = AdminConfigService(db_session)
            
            if provider:
                return config_service.get_llm_provider_config(provider)
            else:
                return config_service.get_active_llm_provider()
        except Exception as e:
            logger.debug("DB LLM config not available: %s", e)
    
    # Fall back to environment-based config
    if provider == "openai" or (not provider and llm_config.openai_api_key):
        return {
            "provider": "openai",
            "api_key": llm_config.openai_api_key,
            "model": llm_config.openai_model,
            "embedding_model": llm_config.openai_embedding_model,
        }
    elif provider == "anthropic" or (not provider and llm_config.anthropic_api_key):
        return {
            "provider": "anthropic",
            "api_key": llm_config.anthropic_api_key,
            "model": llm_config.anthropic_model,
        }
    elif provider in ("azure_openai", "azure-openai") or (not provider and llm_config.azure_openai_key):
        return {
            "provider": "azure_openai",
            "api_key": llm_config.azure_openai_key,
            "endpoint": llm_config.azure_openai_endpoint,
            "model": llm_config.azure_openai_deployment,
            "api_version": llm_config.azure_openai_api_version,
        }
    elif provider == "ollama":
        return {
            "provider": "ollama",
            "api_key": "",
            "endpoint": llm_config.ollama_base_url,
            "model": llm_config.ollama_model,
        }
    
    return {"provider": "none", "api_key": "", "model": ""}


def get_embedding_config_with_db_fallback(db_session=None) -> dict:
    """
    Get embedding configuration with database-first fallback to environment.
    
    Args:
        db_session: Optional SQLAlchemy session for database access.
    
    Returns:
        Dict with embedding configuration
    """
    # Try database first
    if db_session is not None:
        try:
            from services.admin_config_service import AdminConfigService
            config_service = AdminConfigService(db_session)
            return config_service.get_embedding_config()
        except Exception as e:
            logger.debug("DB embedding config not available: %s", e)
    
    # Fall back to environment-based config
    if llm_config.openai_api_key:
        return {
            "provider": "openai",
            "model": llm_config.openai_embedding_model,
            "api_key": llm_config.openai_api_key,
            "dimension": 1536,
        }
    
    return {
        "provider": "sentence_transformers",
        "model": "all-MiniLM-L6-v2",
        "api_key": "",
        "dimension": 384,
    }


def get_database_config_with_db_fallback(db_type: str, db_session=None) -> dict:
    """
    Get database connection configuration with database-first fallback.
    
    Args:
        db_type: Type of database (postgresql, neo4j, redis)
        db_session: Optional SQLAlchemy session for database access.
    
    Returns:
        Dict with database configuration
    """
    # Try database first
    if db_session is not None:
        try:
            from services.admin_config_service import AdminConfigService
            config_service = AdminConfigService(db_session)
            return config_service.get_connection_config(db_type)
        except Exception as e:
            logger.debug("DB connection config not available: %s", e)
    
    # Fall back to environment-based config
    if db_type in ("postgresql", "postgres"):
        return {
            "type": "postgresql",
            "host": database_config.postgres_host,
            "port": database_config.postgres_port,
            "database": database_config.postgres_database,
            "username": database_config.postgres_user,
            "password": database_config.postgres_password,
        }
    elif db_type == "neo4j":
        return {
            "type": "neo4j",
            "uri": database_config.neo4j_uri,
            "username": database_config.neo4j_user,
            "password": database_config.neo4j_password,
            "database": database_config.neo4j_database,
        }
    elif db_type == "redis":
        return {
            "type": "redis",
            "host": database_config.redis_host,
            "port": database_config.redis_port,
            "password": database_config.redis_password,
            "database": database_config.redis_db,
        }
    
    return {"type": db_type}


def ensure_directories():
    """Create necessary directories if they don't exist"""
    directories = [
        filesystem_config.data_root,
        filesystem_config.upload_dir,
        filesystem_config.temp_dir,
        filesystem_config.export_dir,
        filesystem_config.log_dir,
        filesystem_config.xml_input_path,
        filesystem_config.json_input_path,
        filesystem_config.csv_input_path,
    ]
    
    for directory in directories:
        Path(directory).mkdir(parents=True, exist_ok=True)
        logger.info("Ensured directory exists: %s", directory)


# Create directories on module import
try:
    ensure_directories()
except OSError as e:
    logger.warning("Could not create all directories: %s", e)
