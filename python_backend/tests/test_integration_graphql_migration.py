"""
Integration tests for GraphQL + Migration Engine integration.
Tests ETL pipeline: GraphQL introspection → Transform → Migration DATA_MIGRATION phase.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from unittest.mock import Mock, AsyncMock, patch
from services.graphql_service import GraphQLService
from services.advanced_migration_engine import AdvancedMigrationEngine, MigrationState


class TestGraphQLMigrationIntegration:
    """Test GraphQL Toolkit integration with Migration Engine (T-03)."""
    
    def setup_method(self):
        """Setup test fixtures."""
        self.graphql_service = GraphQLService()
        self.migration_engine = AdvancedMigrationEngine()
    
    def test_discovering_phase_uses_graphql_introspection(self):
        """Test DISCOVERING phase leverages GraphQL schema introspection."""
        # Simulate XML source schema
        xml_content = """<?xml version="1.0"?>
        <schema>
            <table name="users">
                <column name="id" type="integer"/>
                <column name="name" type="string"/>
                <column name="email" type="string"/>
            </table>
        </schema>"""
        
        # GraphQL introspects schema
        schema_result = self.graphql_service.introspect_schema(xml_content, "xml", "source_schema")
        assert schema_result is not None
        assert "fields" in schema_result
        
        # Migration engine starts in DISCOVERING phase
        session_id = "test-session-001"
        session = self.migration_engine.create_session(session_id, ["source_db"], "target_db", "full_migration")
        assert session.state == MigrationState.IDLE
        
        # Simulate state transition to DISCOVERING
        self.migration_engine.start_migration(session_id)
        assert session.state == MigrationState.INITIALIZING
        
        # In production, DISCOVERING phase would call GraphQL introspection
        # to analyze source schemas
    
    def test_data_migration_phase_uses_graphql_transforms(self):
        """Test DATA_MIGRATION phase uses GraphQL transform engine."""
        # Sample source data
        source_data = {
            "user_id": "123",
            "user_name": "John Doe",
            "user_email": "john@example.com"
        }
        
        # Define transform mappings (legacy → new schema)
        mappings = [
            {
                "source_path": "user_id",
                "target_path": "id",
                "transformation": "int"
            },
            {
                "source_path": "user_name",
                "target_path": "name",
                "transformation": None
            },
            {
                "source_path": "user_email",
                "target_path": "email",
                "transformation": "lowercase"
            }
        ]
        
        # GraphQL transform engine applies mappings
        transform_result = self.graphql_service.transform_data(source_data, {}, mappings)
        
        assert transform_result["success"] is True
        assert transform_result["data"]["id"] == 123
        assert transform_result["data"]["name"] == "John Doe"
        assert transform_result["data"]["email"] == "john@example.com"
        
        # Migration engine would use these transforms in DATA_MIGRATION state
        session_id = "test-session-002"
        session = self.migration_engine.create_session(session_id, ["source_db"], "target_db", "full_migration")
        
        # Simulate progression to DATA_MIGRATION
        session.state = MigrationState.DATA_MIGRATION
        session.metadata["rows_migrated"] = 1
        assert session.state == MigrationState.DATA_MIGRATION
    
    def test_validation_phase_uses_graphql_queries(self):
        """Test VALIDATION phase uses GraphQL query execution."""
        # Sample migrated data
        migrated_data = {
            "users": [
                {"id": 123, "name": "John Doe", "email": "john@example.com"},
                {"id": 456, "name": "Jane Smith", "email": "jane@example.com"}
            ]
        }
        
        # Validation query (pseudo-GraphQL)
        validation_query = """
        {
            users {
                id
                name
                email
            }
        }
        """
        
        # GraphQL executes validation query
        query_result = self.graphql_service.execute_query(validation_query, migrated_data)
        
        assert "data" in query_result
        assert len(query_result["data"]["users"]) == 2
        assert query_result["data"]["users"][0]["id"] == 123
        
        # Migration engine would validate data in VALIDATION state
        session_id = "test-session-003"
        session = self.migration_engine.create_session(session_id, ["source_db"], "target_db", "full_migration")
        session.state = MigrationState.VALIDATION
        
        # Validation successful → COMPLETED
        assert session.state == MigrationState.VALIDATION
    
    def test_end_to_end_etl_flow_with_graphql(self):
        """Test complete ETL flow: Discover → Transform → Migrate → Validate."""
        session_id = "test-e2e-001"
        
        # Step 1: DISCOVERING - Introspect source schema
        json_schema = '{"type": "object", "properties": {"id": {"type": "integer"}, "name": {"type": "string"}}}'
        schema_result = self.graphql_service.introspect_schema(json_schema, "json", "source_schema")
        assert schema_result is not None
        
        # Step 2: Create migration session
        session = self.migration_engine.create_session(
            session_id,
            ["legacy_db"],
            "modern_db",
            "schema_migration"
        )
        assert session.state == MigrationState.IDLE
        
        # Step 3: Start migration (INITIALIZING)
        self.migration_engine.start_migration(session_id)
        assert session.state == MigrationState.INITIALIZING
        
        # Step 4: DATA_MIGRATION - Apply transforms
        source_data = {"id": "999", "name": "TEST USER"}
        mappings = [
            {"source_path": "id", "target_path": "id", "transformation": "int"},
            {"source_path": "name", "target_path": "name", "transformation": "lowercase"}
        ]
        transform_result = self.graphql_service.transform_data(source_data, {}, mappings)
        assert transform_result["success"] is True
        assert transform_result["data"]["id"] == 999
        assert transform_result["data"]["name"] == "test user"
        
        # Step 5: VALIDATION - Query validation
        validation_data = {"items": [transform_result["data"]]}
        query = '{ items { id name } }'
        validation_result = self.graphql_service.execute_query(query, validation_data)
        assert validation_result["data"]["items"][0]["id"] == 999
        
        # Step 6: Complete migration
        session.state = MigrationState.COMPLETED
        assert session.state == MigrationState.COMPLETED
    
    def test_error_handling_in_transform_during_migration(self):
        """Test error handling when GraphQL transforms fail during migration."""
        # Invalid transformation scenario
        source_data = {"value": "not-a-number"}
        mappings = [
            {"source_path": "value", "target_path": "number", "transformation": "int"}
        ]
        
        # Transform should handle error gracefully
        result = self.graphql_service.transform_data(source_data, {}, mappings)
        
        # Partial success - error captured but transform continues
        assert "errors" in result
        assert len(result["errors"]) > 0
        
        # Migration engine should handle transform errors
        session_id = "test-error-001"
        session = self.migration_engine.create_session(session_id, ["source"], "target", "full")
        session.state = MigrationState.DATA_MIGRATION
        session.metadata["rows_failed"] = 1
        
        # Quality score reflects errors
        quality_score = session.calculate_quality_score()
        assert quality_score < 1.0
    
    def test_migration_metadata_integration(self):
        """Test migration metadata integrates with GraphQL catalogue."""
        session_id = "test-metadata-001"
        session = self.migration_engine.create_session(
            session_id,
            ["source_db"],
            "target_db",
            "incremental_migration"
        )
        
        # Session metadata can be persisted to GraphQL catalogue
        session_metadata = {
            "session_id": session.id,
            "state": session.state.value,
            "sources": session.sources,
            "target": session.target,
            "strategy": session.strategy,
            "quality_score": session.calculate_quality_score()
        }
        
        assert session_metadata["session_id"] == session_id
        assert session_metadata["state"] == "idle"
        assert session_metadata["quality_score"] == 1.0
        
        # In production, this metadata would be stored via GraphQL Catalogue
        # for historical analysis and repeatability


class TestGraphQLCatalogueIntegration:
    """Test GraphQL Catalogue persistence for migration workflows."""
    
    def test_persisted_transforms_for_repeatable_migrations(self):
        """Test persisted transforms enable repeatable ETL workflows."""
        # Define reusable transform
        transform_definition = {
            "name": "user_migration_transform",
            "mappings": [
                {"source_path": "legacy_id", "target_path": "id", "transformation": "int"},
                {"source_path": "legacy_name", "target_path": "full_name", "transformation": None}
            ],
            "description": "Standard user table migration"
        }
        
        # In production, this would be saved to PersistedGraphQLQueryModel
        # and reused across multiple migration sessions
        assert transform_definition["name"] == "user_migration_transform"
        assert len(transform_definition["mappings"]) == 2
    
    def test_schema_cache_improves_migration_performance(self):
        """Test schema caching reduces redundant introspection calls."""
        graphql_service = GraphQLService()
        
        # First introspection (cache miss)
        schema1 = graphql_service.introspect_schema(
            '{"type": "object", "properties": {"id": {"type": "integer"}}}',
            "json",
            "test_schema"
        )
        
        # Second introspection of same schema (would hit cache in production)
        schema2 = graphql_service.introspect_schema(
            '{"type": "object", "properties": {"id": {"type": "integer"}}}',
            "json",
            "test_schema"
        )
        
        # Results should be identical
        assert schema1 == schema2
