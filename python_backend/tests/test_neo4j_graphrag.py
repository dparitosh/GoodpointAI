"""
Tests for Neo4j GraphRAG Service functionality.
Tests hybrid search, health checks, and tool invocation.
"""

import pytest
from python_backend.services.neo4j_graphrag_service import Neo4jGraphRAGService


@pytest.fixture
def graphrag_service():
    """Fixture for GraphRAG service instance."""
    return Neo4jGraphRAGService()


class TestHealthCheck:
    """Tests for service health check."""
    
    def test_health_check_returns_status(self, graphrag_service):
        """Test health check returns proper structure."""
        health = graphrag_service.health_check()
        
        assert "status" in health
        assert "neo4j_connected" in health
        assert "embedding_dimension" in health
        assert "timestamp" in health
        assert health["embedding_dimension"] == 1536


class TestQuery:
    """Tests for GraphRAG query execution."""
    
    def test_run_query_basic(self, graphrag_service):
        """Test basic query execution."""
        result = graphrag_service.run_query(
            question="What is the meaning of life?",
            top_k=3
        )
        
        assert "answers" in result
        assert "sources" in result
        assert "tools_invoked" in result
        assert "latency_ms" in result
        assert "result_count" in result
        assert isinstance(result["answers"], list)
        assert isinstance(result["latency_ms"], int)
    
    def test_run_query_with_context(self, graphrag_service):
        """Test query with additional context."""
        result = graphrag_service.run_query(
            question="What is AI?",
            context="In the context of machine learning",
            top_k=5
        )
        
        assert "answers" in result
        assert len(result["answers"]) <= 5
    
    def test_run_query_with_tools(self, graphrag_service):
        """Test query with tool invocation."""
        result = graphrag_service.run_query(
            question="Summarize this document",
            tools=["summarize", "extract_entities"],
            top_k=3
        )
        
        assert "tools_invoked" in result
        assert len(result["tools_invoked"]) == 2
        assert result["tools_invoked"][0]["tool"] == "summarize"
        assert result["tools_invoked"][1]["tool"] == "extract_entities"
    
    def test_run_query_respects_top_k(self, graphrag_service):
        """Test that top_k parameter limits results."""
        result = graphrag_service.run_query(
            question="Test query",
            top_k=2
        )
        
        assert len(result["answers"]) <= 2
        assert result["result_count"] <= 2


class TestTools:
    """Tests for tool listing and invocation."""
    
    def test_list_tools(self, graphrag_service):
        """Test tool listing."""
        tools = graphrag_service.list_tools()
        
        assert isinstance(tools, list)
        assert len(tools) > 0
        
        for tool in tools:
            assert "name" in tool
            assert "description" in tool
            assert "parameters" in tool


class TestEmbedding:
    """Tests for embedding generation."""
    
    def test_generate_embedding(self, graphrag_service):
        """Test embedding generation."""
        embedding = graphrag_service._generate_embedding("test text")
        
        assert isinstance(embedding, list)
        assert len(embedding) == 1536  # Default dimension
        assert all(isinstance(x, float) for x in embedding)
    
    def test_embedding_deterministic(self, graphrag_service):
        """Test that same text produces same embedding."""
        text = "consistent text"
        embedding1 = graphrag_service._generate_embedding(text)
        embedding2 = graphrag_service._generate_embedding(text)
        
        assert embedding1 == embedding2
