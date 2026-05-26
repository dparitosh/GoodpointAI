"""
Database Migration: Add Missing Indexes for Performance

This migration adds indexes to frequently queried and filtered columns
to improve query performance and reduce N+1 query patterns.

Performance targets:
- Configuration lookups: category, provider, status queries
- List operations: filtering by enabled, status
- Joins: foreign key fields
"""

from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session


def create_indexes(engine: Engine) -> None:
    """Create missing performance indexes."""
    
    with engine.connect() as conn:
        # Existing indexes (skip if already exist)
        indexes_to_create = [
            # SystemConfiguration table
            {
                "name": "ix_admin_system_settings_enabled",
                "table": "admin_system_settings",
                "columns": "enabled",
                "reason": "Filter configs by enabled status"
            },
            {
                "name": "ix_admin_system_settings_category_key",
                "table": "admin_system_settings",
                "columns": "category, key",
                "reason": "Compound lookup by category+key (already has unique, but query planner benefits)"
            },
            {
                "name": "ix_admin_system_settings_updated_at",
                "table": "admin_system_settings",
                "columns": "updated_at DESC",
                "reason": "Recent configs, audit trail sorting"
            },
            
            # LLMProviderConfig table
            {
                "name": "ix_llm_provider_configs_status",
                "table": "llm_provider_configs",
                "columns": "status",
                "reason": "Filter providers by status (active, testing, etc.)"
            },
            {
                "name": "ix_llm_provider_configs_is_default",
                "table": "llm_provider_configs",
                "columns": "is_default",
                "reason": "Quick lookup of default provider"
            },
            {
                "name": "ix_llm_provider_configs_provider_is_default",
                "table": "llm_provider_configs",
                "columns": "provider, is_default",
                "reason": "Find default provider of specific type"
            },
            {
                "name": "ix_llm_provider_configs_created_at",
                "table": "llm_provider_configs",
                "columns": "created_at DESC",
                "reason": "Recent configs, audit trail"
            },
            
            # EmbeddingModelConfig table
            {
                "name": "ix_embedding_model_configs_status",
                "table": "embedding_model_configs",
                "columns": "status",
                "reason": "Filter models by status"
            },
            {
                "name": "ix_embedding_model_configs_is_default",
                "table": "embedding_model_configs",
                "columns": "is_default",
                "reason": "Quick lookup of default embedding model"
            },
            {
                "name": "ix_embedding_model_configs_provider_is_default",
                "table": "embedding_model_configs",
                "columns": "provider, is_default",
                "reason": "Find default model of specific provider"
            },
            {
                "name": "ix_embedding_model_configs_llm_provider_id",
                "table": "embedding_model_configs",
                "columns": "llm_provider_id",
                "reason": "Foreign key lookup to LLMProviderConfig"
            },
            
            # ConnectionConfig table
            {
                "name": "ix_connection_configs_type",
                "table": "connection_configs",
                "columns": "type",
                "reason": "Filter connections by type"
            },
            {
                "name": "ix_connection_configs_status",
                "table": "connection_configs",
                "columns": "status",
                "reason": "Filter connections by status"
            },
            {
                "name": "ix_connection_configs_is_default",
                "table": "connection_configs",
                "columns": "is_default",
                "reason": "Quick lookup of default connection"
            },
            {
                "name": "ix_connection_configs_type_is_default",
                "table": "connection_configs",
                "columns": "type, is_default",
                "reason": "Find default connection of specific type"
            },
            
            # FeatureFlag table
            {
                "name": "ix_feature_flags_enabled",
                "table": "feature_flags",
                "columns": "enabled",
                "reason": "Filter flags by enabled status"
            },
            {
                "name": "ix_feature_flags_name_tenant_id",
                "table": "feature_flags",
                "columns": "name, tenant_id",
                "reason": "Compound lookup by name + tenant"
            },
            
            # AuditLog table (if present)
            {
                "name": "ix_audit_logs_config_type_id",
                "table": "audit_logs",
                "columns": "config_type, config_id",
                "reason": "Audit trail lookup by config"
            },
            {
                "name": "ix_audit_logs_created_at",
                "table": "audit_logs",
                "columns": "created_at DESC",
                "reason": "Recent audits sorting"
            },
            {
                "name": "ix_audit_logs_action",
                "table": "audit_logs",
                "columns": "action",
                "reason": "Filter audits by action (create, update, delete)"
            },
        ]
        
        for idx_config in indexes_to_create:
            try:
                # Check if index exists
                check_sql = f"""
                    SELECT 1 FROM pg_indexes
                    WHERE schemaname = 'public' AND indexname = '{idx_config['name']}'
                """
                result = conn.execute(text(check_sql))
                if result.scalar() is not None:
                    print(f"✓ Index {idx_config['name']} already exists")
                    continue
                
                # Create index
                create_sql = f"""
                    CREATE INDEX {idx_config['name']}
                    ON {idx_config['table']} ({idx_config['columns']})
                """
                conn.execute(text(create_sql))
                print(f"✓ Created index: {idx_config['name']}")
                print(f"  Table: {idx_config['table']}, Columns: {idx_config['columns']}")
                print(f"  Reason: {idx_config['reason']}")
                
            except Exception as e:
                print(f"⚠ Failed to create index {idx_config['name']}: {e}")
        
        conn.commit()


def analyze_indexes(engine: Engine) -> None:
    """Analyze index usage and performance."""
    
    with engine.connect() as conn:
        # Get index information
        query = """
            SELECT
                schemaname,
                tablename,
                indexname,
                indexdef
            FROM pg_indexes
            WHERE schemaname = 'public'
            ORDER BY tablename, indexname
        """
        
        result = conn.execute(text(query))
        indexes = result.fetchall()
        
        print("\n=== Current Indexes ===")
        for schema, table, idx_name, idx_def in indexes:
            print(f"\nTable: {table}")
            print(f"  Index: {idx_name}")
            print(f"  Definition: {idx_def}")


# Migration entry point
def migrate_up(engine: Engine) -> None:
    """Apply migration."""
    print("Creating missing performance indexes...")
    create_indexes(engine)
    print("\nAnalyzing indexes...")
    analyze_indexes(engine)


def migrate_down(engine: Engine) -> None:
    """Rollback migration."""
    print("Removing performance indexes would require manual cleanup.")
    print("To remove specific indexes, use: DROP INDEX IF EXISTS index_name;")
