"""
Seed Admin Configurations

Seeds default LLM providers, embedding models, connections, and system configurations.
Run this script after database migration to populate initial configurations.
"""

import os
import sys
import logging
from datetime import datetime, timezone

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm import Session
from core.db_session import engine, SessionLocal
from core.database import Base
from models.admin_config_models import (
    SystemConfiguration,
    LLMProviderConfig,
    EmbeddingModelConfig,
    ConnectionConfig,
    FeatureFlag,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def seed_system_configurations(db: Session):
    """Seed default system configurations."""
    logger.info("Seeding system configurations...")
    
    configs = [
        # LLM Settings
        {"category": "llm", "key": "default_provider", "value": "openai", "value_type": "string",
         "description": "Default LLM provider to use", "is_secret": False, "is_required": True},
        {"category": "llm", "key": "max_retries", "value": "3", "value_type": "number",
         "description": "Maximum retry attempts for LLM API calls", "is_secret": False},
        {"category": "llm", "key": "timeout_seconds", "value": "60", "value_type": "number",
         "description": "Timeout for LLM API calls in seconds", "is_secret": False},
        {"category": "llm", "key": "enable_caching", "value": "true", "value_type": "boolean",
         "description": "Enable caching of LLM responses", "is_secret": False},
        {"category": "llm", "key": "cache_ttl_seconds", "value": "3600", "value_type": "number",
         "description": "Cache TTL for LLM responses", "is_secret": False},
        
        # Embedding Settings
        {"category": "embedding", "key": "default_model", "value": "sentence_transformers_minilm", "value_type": "string",
         "description": "Default embedding model to use", "is_secret": False, "is_required": True},
        {"category": "embedding", "key": "batch_size", "value": "32", "value_type": "number",
         "description": "Batch size for embedding generation", "is_secret": False},
        {"category": "embedding", "key": "normalize_embeddings", "value": "true", "value_type": "boolean",
         "description": "Normalize embedding vectors", "is_secret": False},
        
        # Search Settings
        {"category": "search", "key": "default_mode", "value": "hybrid", "value_type": "string",
         "description": "Default search mode: semantic, vector, or hybrid", "is_secret": False},
        {"category": "search", "key": "default_top_k", "value": "10", "value_type": "number",
         "description": "Default number of results to return", "is_secret": False},
        {"category": "search", "key": "similarity_threshold", "value": "0.7", "value_type": "number",
         "description": "Minimum similarity score for results", "is_secret": False},
        {"category": "search", "key": "enable_graphrag", "value": "true", "value_type": "boolean",
         "description": "Enable GraphRAG for hybrid search", "is_secret": False},
        {"category": "search", "key": "opensearch_index", "value": "documents", "value_type": "string",
         "description": "Default OpenSearch index name", "is_secret": False},
        
        # Pipeline Settings
        {"category": "pipeline", "key": "max_file_size_mb", "value": "100", "value_type": "number",
         "description": "Maximum file size for pipeline ingestion (MB)", "is_secret": False},
        {"category": "pipeline", "key": "supported_file_types", "value": '["pdf","docx","xlsx","csv","json","xml","txt"]', "value_type": "json",
         "description": "Supported file types for ingestion", "is_secret": False},
        {"category": "pipeline", "key": "enable_ocr", "value": "true", "value_type": "boolean",
         "description": "Enable OCR for image-based documents", "is_secret": False},
        {"category": "pipeline", "key": "parallel_workers", "value": "4", "value_type": "number",
         "description": "Number of parallel workers for processing", "is_secret": False},
        
        # UI Settings
        {"category": "ui", "key": "theme", "value": "light", "value_type": "string",
         "description": "Default UI theme: light or dark", "is_secret": False},
        {"category": "ui", "key": "page_size", "value": "25", "value_type": "number",
         "description": "Default page size for tables", "is_secret": False},
        {"category": "ui", "key": "enable_animations", "value": "true", "value_type": "boolean",
         "description": "Enable UI animations", "is_secret": False},
        
        # Monitoring Settings
        {"category": "monitoring", "key": "log_level", "value": "INFO", "value_type": "string",
         "description": "Application log level: DEBUG, INFO, WARNING, ERROR", "is_secret": False},
        {"category": "monitoring", "key": "enable_metrics", "value": "true", "value_type": "boolean",
         "description": "Enable Prometheus metrics collection", "is_secret": False},
        {"category": "monitoring", "key": "metrics_port", "value": "9090", "value_type": "number",
         "description": "Port for metrics endpoint", "is_secret": False},
        {"category": "monitoring", "key": "health_check_interval", "value": "60", "value_type": "number",
         "description": "Health check interval in seconds", "is_secret": False},
        
        # Security Settings
        {"category": "security", "key": "jwt_expiry_hours", "value": "24", "value_type": "number",
         "description": "JWT token expiry time in hours", "is_secret": False},
        {"category": "security", "key": "enable_cors", "value": "true", "value_type": "boolean",
         "description": "Enable CORS for API", "is_secret": False},
        {"category": "security", "key": "allowed_origins", "value": os.environ.get("GRAPH_TRACE_ALLOWED_ORIGINS", '["http://localhost:5173","http://localhost:3000"]'), "value_type": "json",
         "description": "Allowed CORS origins", "is_secret": False},
        {"category": "security", "key": "rate_limit_requests", "value": "100", "value_type": "number",
         "description": "Rate limit: requests per minute", "is_secret": False},
        {"category": "security", "key": "enable_audit_logging", "value": "true", "value_type": "boolean",
         "description": "Enable audit logging for config changes", "is_secret": False},
    ]
    
    created_count = 0
    for config in configs:
        existing = db.query(SystemConfiguration).filter(
            SystemConfiguration.category == config["category"],
            SystemConfiguration.key == config["key"]
        ).first()
        
        if not existing:
            db_config = SystemConfiguration(**config)
            db.add(db_config)
            created_count += 1
    
    db.commit()
    logger.info(f"Created {created_count} system configurations")


def seed_llm_providers(db: Session):
    """Seed default LLM provider configurations."""
    logger.info("Seeding LLM provider configurations...")
    
    providers = [
        {
            "id": "openai_default",
            "provider": "openai",
            "name": "OpenAI GPT-4",
            "description": "OpenAI GPT-4 Turbo for general AI tasks",
            "api_endpoint": "https://api.openai.com/v1",
            "default_chat_model": "gpt-4-turbo-preview",
            "default_completion_model": "gpt-3.5-turbo-instruct",
            "default_embedding_model": "text-embedding-3-small",
            "default_temperature": 0.7,
            "default_max_tokens": 4096,
            "default_top_p": 1.0,
            "rate_limit_rpm": 500,
            "rate_limit_tpm": 90000,
            "cost_per_1k_input_tokens": 0.01,
            "cost_per_1k_output_tokens": 0.03,
            "status": "active",
            "is_default": True,
            "priority": 100
        },
        {
            "id": "anthropic_default",
            "provider": "anthropic",
            "name": "Anthropic Claude 3",
            "description": "Anthropic Claude 3 Sonnet for advanced reasoning",
            "api_endpoint": "https://api.anthropic.com",
            "default_chat_model": "claude-3-sonnet-20240229",
            "default_max_tokens": 4096,
            "default_temperature": 0.7,
            "cost_per_1k_input_tokens": 0.003,
            "cost_per_1k_output_tokens": 0.015,
            "status": "inactive",
            "is_default": False,
            "priority": 90
        },
        {
            "id": "azure_openai_default",
            "provider": "azure_openai",
            "name": "Azure OpenAI",
            "description": "Azure OpenAI Service for enterprise deployments",
            "api_version": "2024-02-15-preview",
            "default_chat_model": "gpt-4",
            "default_max_tokens": 4096,
            "default_temperature": 0.7,
            "status": "inactive",
            "is_default": False,
            "priority": 80
        },
        {
            "id": "ollama_local",
            "provider": "ollama",
            "name": "Ollama Local",
            "description": "Local Ollama for offline/private deployments",
            "api_endpoint": "http://localhost:11434",
            "default_chat_model": "llama2",
            "default_max_tokens": 2048,
            "default_temperature": 0.7,
            "status": "inactive",
            "is_default": False,
            "priority": 50
        },
        {
            "id": "huggingface_hub",
            "provider": "huggingface",
            "name": "Hugging Face Hub",
            "description": "Hugging Face models via Inference API",
            "api_endpoint": "https://api-inference.huggingface.co",
            "default_chat_model": "meta-llama/Llama-2-70b-chat-hf",
            "default_max_tokens": 2048,
            "default_temperature": 0.7,
            "status": "inactive",
            "is_default": False,
            "priority": 40
        }
    ]
    
    created_count = 0
    for provider in providers:
        existing = db.query(LLMProviderConfig).filter(LLMProviderConfig.id == provider["id"]).first()
        if not existing:
            db_provider = LLMProviderConfig(**provider)
            db.add(db_provider)
            created_count += 1
    
    db.commit()
    logger.info(f"Created {created_count} LLM provider configurations")


def seed_embedding_models(db: Session):
    """Seed default embedding model configurations."""
    logger.info("Seeding embedding model configurations...")
    
    models = [
        {
            "id": "sentence_transformers_minilm",
            "provider": "sentence_transformers",
            "name": "MiniLM-L6-v2",
            "description": "Fast, lightweight sentence transformer for semantic search",
            "model_name": "sentence-transformers/all-MiniLM-L6-v2",
            "dimension": 384,
            "max_input_length": 512,
            "batch_size": 32,
            "normalize": True,
            "status": "active",
            "is_default": True
        },
        {
            "id": "sentence_transformers_mpnet",
            "provider": "sentence_transformers",
            "name": "MPNet Base v2",
            "description": "Higher quality sentence transformer",
            "model_name": "sentence-transformers/all-mpnet-base-v2",
            "dimension": 768,
            "max_input_length": 384,
            "batch_size": 16,
            "normalize": True,
            "status": "active",
            "is_default": False
        },
        {
            "id": "openai_embedding_small",
            "provider": "openai",
            "name": "OpenAI text-embedding-3-small",
            "description": "OpenAI's efficient embedding model",
            "model_name": "text-embedding-3-small",
            "dimension": 1536,
            "max_input_length": 8191,
            "llm_provider_id": "openai_default",
            "batch_size": 100,
            "normalize": True,
            "cost_per_1k_tokens": 0.00002,
            "status": "inactive",
            "is_default": False
        },
        {
            "id": "openai_embedding_large",
            "provider": "openai",
            "name": "OpenAI text-embedding-3-large",
            "description": "OpenAI's highest quality embedding model",
            "model_name": "text-embedding-3-large",
            "dimension": 3072,
            "max_input_length": 8191,
            "llm_provider_id": "openai_default",
            "batch_size": 100,
            "normalize": True,
            "cost_per_1k_tokens": 0.00013,
            "status": "inactive",
            "is_default": False
        },
        {
            "id": "cohere_embed_english",
            "provider": "cohere",
            "name": "Cohere Embed English v3",
            "description": "Cohere's English embedding model",
            "model_name": "embed-english-v3.0",
            "dimension": 1024,
            "max_input_length": 512,
            "batch_size": 96,
            "normalize": True,
            "status": "inactive",
            "is_default": False
        }
    ]
    
    created_count = 0
    for model in models:
        existing = db.query(EmbeddingModelConfig).filter(EmbeddingModelConfig.id == model["id"]).first()
        if not existing:
            db_model = EmbeddingModelConfig(**model)
            db.add(db_model)
            created_count += 1
    
    db.commit()
    logger.info(f"Created {created_count} embedding model configurations")


def seed_connections(db: Session):
    """Seed default connection configurations."""
    logger.info("Seeding connection configurations...")
    
    connections = [
        {
            "id": "postgres_primary",
            "connection_type": "postgres",
            "name": "Primary PostgreSQL",
            "description": "Primary PostgreSQL database for application data",
            "host": os.getenv("POSTGRES_HOST", "localhost"),
            "port": int(os.getenv("POSTGRES_PORT", "5433")),
            "database": os.getenv("POSTGRES_DATABASE", "graphtrace"),
            "username": os.getenv("POSTGRES_USER", "postgres"),
            "password": os.getenv("POSTGRES_PASSWORD", ""),
            "use_ssl": False,
            "pool_size": 5,
            "max_overflow": 10,
            "pool_timeout": 30,
            "status": "active",
            "is_default": True
        },
        {
            "id": "neo4j_primary",
            "connection_type": "neo4j",
            "name": "Primary Neo4j",
            "description": "Neo4j graph database for knowledge graph",
            "host": os.getenv("NEO4J_HOST", "localhost"),
            "port": int(os.getenv("NEO4J_PORT", "7687")),
            "database": os.getenv("NEO4J_DATABASE", "neo4j"),
            "username": os.getenv("NEO4J_USER", "neo4j"),
            "password": os.getenv("NEO4J_PASSWORD", ""),
            "use_ssl": False,
            "pool_size": 5,
            "max_overflow": 10,
            "status": "active",
            "is_default": True
        },
        {
            "id": "opensearch_primary",
            "connection_type": "opensearch",
            "name": "Primary OpenSearch",
            "description": "OpenSearch cluster for vector search",
            "host": os.getenv("OPENSEARCH_HOST", "localhost"),
            "port": int(os.getenv("OPENSEARCH_PORT", "9200")),
            "username": os.getenv("OPENSEARCH_USER", "admin"),
            "password": os.getenv("OPENSEARCH_PASSWORD", ""),
            "use_ssl": False,
            "extra_options": {
                "verify_certs": False,
                "ssl_show_warn": False
            },
            "status": "active",
            "is_default": True
        },
        {
            "id": "redis_cache",
            "connection_type": "redis",
            "name": "Redis Cache",
            "description": "Redis for caching and session management",
            "host": os.getenv("REDIS_HOST", "localhost"),
            "port": int(os.getenv("REDIS_PORT", "6379")),
            "database": os.getenv("REDIS_DB", "0"),
            "password": os.getenv("REDIS_PASSWORD", ""),
            "status": "inactive",
            "is_default": True
        }
    ]
    
    created_count = 0
    for conn in connections:
        existing = db.query(ConnectionConfig).filter(ConnectionConfig.id == conn["id"]).first()
        if not existing:
            db_conn = ConnectionConfig(**conn)
            db.add(db_conn)
            created_count += 1
    
    db.commit()
    logger.info(f"Created {created_count} connection configurations")


def seed_feature_flags(db: Session):
    """Seed default feature flags."""
    logger.info("Seeding feature flags...")
    
    flags = [
        {
            "id": "enable_llm_chat",
            "name": "Enable LLM Chat",
            "description": "Enable conversational AI chat feature",
            "enabled": True,
            "rollout_percentage": 100
        },
        {
            "id": "enable_vector_search",
            "name": "Enable Vector Search",
            "description": "Enable vector-based semantic search",
            "enabled": True,
            "rollout_percentage": 100
        },
        {
            "id": "enable_graphrag",
            "name": "Enable GraphRAG",
            "description": "Enable Graph-based Retrieval Augmented Generation",
            "enabled": True,
            "rollout_percentage": 100
        },
        {
            "id": "enable_pipeline_wizard",
            "name": "Enable Pipeline Wizard",
            "description": "Enable visual pipeline creation wizard",
            "enabled": True,
            "rollout_percentage": 100
        },
        {
            "id": "enable_admin_panel",
            "name": "Enable Admin Panel",
            "description": "Enable administrative configuration panel",
            "enabled": True,
            "rollout_percentage": 100
        },
        {
            "id": "enable_ocr_processing",
            "name": "Enable OCR Processing",
            "description": "Enable OCR for image-based documents",
            "enabled": False,
            "rollout_percentage": 0
        },
        {
            "id": "enable_realtime_updates",
            "name": "Enable Real-time Updates",
            "description": "Enable WebSocket-based real-time updates",
            "enabled": True,
            "rollout_percentage": 100
        },
        {
            "id": "enable_usage_analytics",
            "name": "Enable Usage Analytics",
            "description": "Track and analyze feature usage",
            "enabled": True,
            "rollout_percentage": 100
        },
        {
            "id": "enable_cost_tracking",
            "name": "Enable Cost Tracking",
            "description": "Track LLM API costs",
            "enabled": True,
            "rollout_percentage": 100
        },
        {
            "id": "enable_beta_features",
            "name": "Enable Beta Features",
            "description": "Enable experimental/beta features",
            "enabled": False,
            "rollout_percentage": 0
        }
    ]
    
    created_count = 0
    for flag in flags:
        existing = db.query(FeatureFlag).filter(FeatureFlag.id == flag["id"]).first()
        if not existing:
            db_flag = FeatureFlag(**flag)
            db.add(db_flag)
            created_count += 1
    
    db.commit()
    logger.info(f"Created {created_count} feature flags")


def create_tables():
    """Create all tables if they don't exist."""
    logger.info("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created successfully")


def main():
    """Main function to seed all configurations."""
    logger.info("Starting admin configuration seeding...")
    
    # Create tables
    create_tables()
    
    # Create session
    db = SessionLocal()
    
    try:
        # Seed all configurations
        seed_system_configurations(db)
        seed_llm_providers(db)
        seed_embedding_models(db)
        seed_connections(db)
        seed_feature_flags(db)
        
        logger.info("Admin configuration seeding completed successfully!")
        
    except Exception as e:
        logger.error(f"Error seeding configurations: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
