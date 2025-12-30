"""
Tests for GraphQL Service functionality.
Tests schema introspection, query execution, and data transformation.
"""

import pytest
from services.graphql_service import GraphQLService


@pytest.fixture
def graphql_service():
    """Fixture for GraphQL service instance."""
    return GraphQLService()


@pytest.fixture
def test_json():
    """Example JSON data for testing."""
    return '''
    {
        "user": {
            "id": 123,
            "name": "John Doe",
            "email": "john@example.com",
            "profile": {
                "age": 30,
                "city": "New York"
            }
        }
    }
    '''


@pytest.fixture
def test_xml():
    """Example XML data for testing."""
    return '''
    <user>
        <id>123</id>
        <name>John Doe</name>
        <email>john@example.com</email>
        <profile>
            <age>30</age>
            <city>New York</city>
        </profile>
    </user>
    '''


class TestSchemaIntrospection:
    """Tests for schema introspection functionality."""
    
    def test_introspect_json_schema(self, graphql_service, test_json):
        """Test JSON schema introspection."""
        result = graphql_service.introspect_schema(
            content=test_json,
            format="json",
            name="test_schema"
        )
        
        assert result["name"] == "test_schema"
        assert result["format"] == "json"
        assert "schema_hash" in result
        assert "fields" in result
        assert "types" in result
        assert "user.id" in result["fields"]
        assert "user.name" in result["fields"]
    
    def test_introspect_xml_schema(self, graphql_service, test_xml):
        """Test XML schema introspection."""
        result = graphql_service.introspect_schema(
            content=test_xml,
            format="xml",
            name="xml_schema"
        )
        
        assert result["name"] == "xml_schema"
        assert result["format"] == "xml"
        assert "schema_hash" in result
        assert "fields" in result
    
    def test_invalid_format_raises_error(self, graphql_service, test_json):
        """Test that invalid format raises ValueError."""
        with pytest.raises(ValueError, match="Invalid format"):
            graphql_service.introspect_schema(
                content=test_json,
                format="yaml",
                name="test",
            )
    
    def test_invalid_json_raises_error(self, graphql_service):
        """Test that invalid JSON raises ValueError."""
        with pytest.raises(ValueError, match="Invalid JSON"):
            graphql_service.introspect_schema(
                content="{ invalid json }",
                format="json",
                name="test"
            )
    
    def test_invalid_xml_raises_error(self, graphql_service):
        """Test that invalid XML raises ValueError."""
        with pytest.raises(ValueError, match="Invalid XML"):
            graphql_service.introspect_schema(
                content="<invalid><xml>",
                format="xml",
                name="test"
            )


class TestQueryExecution:
    """Tests for query execution functionality."""
    
    def test_simple_query(self, graphql_service):
        """Test simple field selection."""
        data = {
            "user": {
                "name": "John",
                "age": 30
            }
        }
        
        result = graphql_service.execute_query(
            query="user.name\nuser.age",
            data=data
        )
        
        assert result["data"]["user"]["name"] == "John"
        assert result["data"]["user"]["age"] == 30
        assert len(result["errors"]) == 0
    
    def test_nested_query(self, graphql_service):
        """Test nested field selection."""
        data = {
            "user": {
                "profile": {
                    "address": {
                        "city": "New York"
                    }
                }
            }
        }
        
        result = graphql_service.execute_query(
            query="user.profile.address.city",
            data=data
        )
        
        assert result["data"]["user"]["profile"]["address"]["city"] == "New York"
    
    def test_query_with_errors(self, graphql_service):
        """Test query error handling."""
        # Query with invalid selector should be handled gracefully
        result = graphql_service.execute_query(
            query="nonexistent.field",
            data={"user": {"name": "John"}}
        )
        
        # Should return data with None values, not raise exception
        assert result["data"] is not None or len(result["errors"]) > 0


class TestDataTransformation:
    """Tests for data transformation functionality."""
    
    def test_simple_transform(self, graphql_service):
        """Test simple field mapping."""
        source = {"firstName": "John", "lastName": "Doe"}
        target = {}
        mappings = [
            {"source_field": "firstName", "target_field": "first_name"},
            {"source_field": "lastName", "target_field": "last_name"}
        ]
        
        result = graphql_service.transform_data(source, target, mappings)
        
        assert result["transformed_data"]["first_name"] == "John"
        assert result["transformed_data"]["last_name"] == "Doe"
        assert result["mappings_applied"] == 2
        assert result["mappings_failed"] == 0
    
    def test_transform_with_uppercase(self, graphql_service):
        """Test transformation with uppercase conversion."""
        source = {"name": "john"}
        target = {}
        mappings = [
            {"source_field": "name", "target_field": "NAME", "transformation": "uppercase"}
        ]
        
        result = graphql_service.transform_data(source, target, mappings)
        
        assert result["transformed_data"]["NAME"] == "JOHN"
    
    def test_transform_with_type_conversion(self, graphql_service):
        """Test transformation with type conversion."""
        source = {"age": "30", "score": "95.5"}
        target = {}
        mappings = [
            {"source_field": "age", "target_field": "age_int", "transformation": "int"},
            {"source_field": "score", "target_field": "score_float", "transformation": "float"}
        ]
        
        result = graphql_service.transform_data(source, target, mappings)
        
        assert result["transformed_data"]["age_int"] == 30
        assert result["transformed_data"]["score_float"] == 95.5
    
    def test_transform_with_errors(self, graphql_service):
        """Test transformation error handling."""
        source = {"value": "not_a_number"}
        target = {}
        mappings = [
            {"source_field": "value", "target_field": "number", "transformation": "int"}
        ]
        
        result = graphql_service.transform_data(source, target, mappings)
        
        assert result["mappings_applied"] == 0
        assert result["mappings_failed"] == 1
        assert len(result["errors"]) > 0
    
    def test_transform_partial_success(self, graphql_service):
        """Test transformation with some successful and some failed mappings."""
        source = {"name": "John", "age": "invalid"}
        target = {}
        mappings = [
            {"source_field": "name", "target_field": "name_upper", "transformation": "uppercase"},
            {"source_field": "age", "target_field": "age_int", "transformation": "int"}
        ]
        
        result = graphql_service.transform_data(source, target, mappings)
        
        assert result["transformed_data"]["name_upper"] == "JOHN"
        assert result["mappings_applied"] == 1
        assert result["mappings_failed"] == 1
