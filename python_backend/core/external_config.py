"""
External Integration Configuration
Manages all external service connections and credentials
"""
import os
import logging
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv
from pydantic_settings import BaseSettings
from pydantic import Field

# Load environment variables
dotenv_path = Path(__file__).resolve().parent.parent / '.env'
load_dotenv(dotenv_path=dotenv_path)
logger = logging.getLogger(__name__)


class AzureConfig(BaseSettings):
    """Azure Cloud Services Configuration"""
    # Storage
    storage_account_name: str = Field(default="", env="AZURE_STORAGE_ACCOUNT")
    storage_account_key: str = Field(default="", env="AZURE_STORAGE_KEY")
    storage_connection_string: str = Field(default="", env="AZURE_STORAGE_CONNECTION_STRING")
    blob_container_name: str = Field(default="plm-data", env="AZURE_BLOB_CONTAINER")
    datalake_container_name: str = Field(default="raw-data", env="AZURE_DATALAKE_CONTAINER")
    
    # Cosmos DB
    cosmos_endpoint: str = Field(default="", env="AZURE_COSMOS_ENDPOINT")
    cosmos_key: str = Field(default="", env="AZURE_COSMOS_KEY")
    cosmos_database: str = Field(default="graphtrace", env="AZURE_COSMOS_DATABASE")
    
    # Service Bus
    servicebus_connection_string: str = Field(default="", env="AZURE_SERVICEBUS_CONNECTION")
    servicebus_queue_name: str = Field(default="workflow-queue", env="AZURE_SERVICEBUS_QUEUE")
    
    # Event Hub
    eventhub_connection_string: str = Field(default="", env="AZURE_EVENTHUB_CONNECTION")
    eventhub_name: str = Field(default="plm-events", env="AZURE_EVENTHUB_NAME")
    
    # Key Vault
    keyvault_url: str = Field(default="", env="AZURE_KEYVAULT_URL")
    
    # Authentication
    tenant_id: str = Field(default="", env="AZURE_TENANT_ID")
    client_id: str = Field(default="", env="AZURE_CLIENT_ID")
    client_secret: str = Field(default="", env="AZURE_CLIENT_SECRET")


class AWSConfig(BaseSettings):
    """AWS Cloud Services Configuration"""
    # General
    access_key_id: str = Field(default="", env="AWS_ACCESS_KEY_ID")
    secret_access_key: str = Field(default="", env="AWS_SECRET_ACCESS_KEY")
    region: str = Field(default="us-east-1", env="AWS_REGION")
    
    # S3
    s3_bucket_name: str = Field(default="plm-data-bucket", env="AWS_S3_BUCKET")
    s3_prefix: str = Field(default="raw/", env="AWS_S3_PREFIX")
    
    # DynamoDB
    dynamodb_table_name: str = Field(default="workflow-state", env="AWS_DYNAMODB_TABLE")
    
    # SQS
    sqs_queue_url: str = Field(default="", env="AWS_SQS_QUEUE_URL")
    
    # Lambda
    lambda_function_arn: str = Field(default="", env="AWS_LAMBDA_FUNCTION_ARN")
    
    # API Gateway
    api_gateway_url: str = Field(default="", env="AWS_API_GATEWAY_URL")


class ODataConfig(BaseSettings):
    """OData Service Configuration"""
    # SAP OData
    sap_odata_url: str = Field(default="", env="SAP_ODATA_URL")
    sap_username: str = Field(default="", env="SAP_USERNAME")
    sap_password: str = Field(default="", env="SAP_PASSWORD")
    sap_client: str = Field(default="100", env="SAP_CLIENT")
    
    # Generic OData
    odata_service_url: str = Field(default="", env="ODATA_SERVICE_URL")
    odata_auth_type: str = Field(default="basic", env="ODATA_AUTH_TYPE")  # basic, oauth2, apikey
    odata_username: str = Field(default="", env="ODATA_USERNAME")
    odata_password: str = Field(default="", env="ODATA_PASSWORD")
    odata_api_key: str = Field(default="", env="ODATA_API_KEY")
    odata_token_url: str = Field(default="", env="ODATA_TOKEN_URL")


class LLMConfig(BaseSettings):
    """LLM Service Configuration"""
    # OpenAI
    openai_api_key: str = Field(default="", env="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4-turbo-preview", env="OPENAI_MODEL")
    openai_embedding_model: str = Field(default="text-embedding-3-small", env="OPENAI_EMBEDDING_MODEL")
    
    # Anthropic Claude
    anthropic_api_key: str = Field(default="", env="ANTHROPIC_API_KEY")
    anthropic_model: str = Field(default="claude-3-sonnet-20240229", env="ANTHROPIC_MODEL")
    
    # Azure OpenAI
    azure_openai_endpoint: str = Field(default="", env="AZURE_OPENAI_ENDPOINT")
    azure_openai_key: str = Field(default="", env="AZURE_OPENAI_KEY")
    azure_openai_deployment: str = Field(default="", env="AZURE_OPENAI_DEPLOYMENT")
    azure_openai_api_version: str = Field(default="2024-02-15-preview", env="AZURE_OPENAI_API_VERSION")
    
    # Ollama Local
    ollama_base_url: str = Field(default="http://localhost:11434", env="OLLAMA_BASE_URL")
    ollama_model: str = Field(default="llama2", env="OLLAMA_MODEL")


class PLMConfig(BaseSettings):
    """PLM System Configuration"""
    # Teamcenter
    teamcenter_url: str = Field(default="", env="TEAMCENTER_URL")
    teamcenter_username: str = Field(default="", env="TEAMCENTER_USERNAME")
    teamcenter_password: str = Field(default="", env="TEAMCENTER_PASSWORD")
    teamcenter_soap_url: str = Field(default="", env="TEAMCENTER_SOAP_URL")
    teamcenter_rest_url: str = Field(default="", env="TEAMCENTER_REST_URL")
    
    # Windchill
    windchill_url: str = Field(default="", env="WINDCHILL_URL")
    windchill_username: str = Field(default="", env="WINDCHILL_USERNAME")
    windchill_password: str = Field(default="", env="WINDCHILL_PASSWORD")
    windchill_context_path: str = Field(default="/Windchill", env="WINDCHILL_CONTEXT_PATH")
    
    # ENOVIA/3DEXPERIENCE
    enovia_url: str = Field(default="", env="ENOVIA_URL")
    enovia_username: str = Field(default="", env="ENOVIA_USERNAME")
    enovia_password: str = Field(default="", env="ENOVIA_PASSWORD")
    enovia_security_context: str = Field(default="", env="ENOVIA_SECURITY_CONTEXT")
    
    # Aras Innovator
    aras_url: str = Field(default="", env="ARAS_URL")
    aras_database: str = Field(default="", env="ARAS_DATABASE")
    aras_username: str = Field(default="", env="ARAS_USERNAME")
    aras_password: str = Field(default="", env="ARAS_PASSWORD")


class FileSystemConfig(BaseSettings):
    """File System Configuration"""
    # Data directories
    data_root: str = Field(default="./data", env="DATA_ROOT_PATH")
    upload_dir: str = Field(default="./data/uploads", env="UPLOAD_DIR")
    temp_dir: str = Field(default="./data/temp", env="TEMP_DIR")
    export_dir: str = Field(default="./data/exports", env="EXPORT_DIR")
    log_dir: str = Field(default="./logs", env="LOG_DIR")
    
    # File locations
    xml_input_path: str = Field(default="./data/xml/input", env="XML_INPUT_PATH")
    json_input_path: str = Field(default="./data/json/input", env="JSON_INPUT_PATH")
    csv_input_path: str = Field(default="./data/csv/input", env="CSV_INPUT_PATH")
    
    # Folder monitoring
    watch_folders: list = Field(default=["./data/watch"], env="WATCH_FOLDERS")
    
    # File size limits (in MB)
    max_upload_size_mb: int = Field(default=100, env="MAX_UPLOAD_SIZE_MB")
    max_batch_size_mb: int = Field(default=500, env="MAX_BATCH_SIZE_MB")


class DatabaseConfig(BaseSettings):
    """Database Configuration"""
    # PostgreSQL
    postgres_host: str = Field(default="localhost", env="POSTGRES_HOST")
    postgres_port: int = Field(default=5432, env="POSTGRES_PORT")
    postgres_database: str = Field(default="graphtrace", env="POSTGRES_DATABASE")
    postgres_user: str = Field(default="postgres", env="POSTGRES_USER")
    postgres_password: str = Field(default="", env="POSTGRES_PASSWORD")
    
    # Neo4j (already in config.py, but included for completeness)
    neo4j_uri: str = Field(default="neo4j+s://2cccd05b.databases.neo4j.io", env="NEO4J_URI")
    neo4j_user: str = Field(default="neo4j", env="NEO4J_USER")
    neo4j_password: str = Field(default="", env="NEO4J_PASSWORD")
    neo4j_database: str = Field(default="neo4j", env="NEO4J_DATABASE")
    
    # MongoDB
    mongodb_uri: str = Field(default="mongodb://localhost:27017", env="MONGODB_URI")
    mongodb_database: str = Field(default="graphtrace", env="MONGODB_DATABASE")
    
    # Redis
    redis_host: str = Field(default="localhost", env="REDIS_HOST")
    redis_port: int = Field(default=6379, env="REDIS_PORT")
    redis_password: str = Field(default="", env="REDIS_PASSWORD")
    redis_db: int = Field(default=0, env="REDIS_DB")


class APIGatewayConfig(BaseSettings):
    """API Gateway Configuration"""
    # Generic API Gateway
    gateway_url: str = Field(default="", env="API_GATEWAY_URL")
    gateway_api_key: str = Field(default="", env="API_GATEWAY_KEY")
    gateway_secret: str = Field(default="", env="API_GATEWAY_SECRET")
    
    # Kong
    kong_admin_url: str = Field(default="http://localhost:8001", env="KONG_ADMIN_URL")
    kong_gateway_url: str = Field(default="http://localhost:8000", env="KONG_GATEWAY_URL")
    kong_api_key: str = Field(default="", env="KONG_API_KEY")
    
    # Apigee
    apigee_org: str = Field(default="", env="APIGEE_ORG")
    apigee_env: str = Field(default="", env="APIGEE_ENV")
    apigee_username: str = Field(default="", env="APIGEE_USERNAME")
    apigee_password: str = Field(default="", env="APIGEE_PASSWORD")


# Initialize all configurations
azure_config = AzureConfig()
aws_config = AWSConfig()
odata_config = ODataConfig()
llm_config = LLMConfig()
plm_config = PLMConfig()
filesystem_config = FileSystemConfig()
database_config = DatabaseConfig()
api_gateway_config = APIGatewayConfig()


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
        logger.info(f"Ensured directory exists: {directory}")


# Create directories on module import
try:
    ensure_directories()
except Exception as e:
    logger.warning(f"Could not create all directories: {e}")
