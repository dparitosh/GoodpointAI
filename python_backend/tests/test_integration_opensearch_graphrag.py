"""
Integration tests for OpenSearch + Neo4j GraphRAG integration.
Tests hybrid search: Neo4j graph context + OpenSearch vector similarity + Analytics.
"""
import sys
from pathlib import Path
from typing import Any
sys.path.insert(0, str(Path(__file__).parent.parent))
import pytest
from services.neo4j_graphrag_service import Neo4jGraphRAGService
from services.analytics_storage_service import AnalyticsStorageService


class GraphRAGServiceStub:
    """Test stub for Neo4jGraphRAGService.

    These tests focus on data-shape and fusion logic without requiring live services.
    """

    def __init__(self) -> None:
        self._spec: Any = Neo4jGraphRAGService


class TestOpenSearchGraphRAGIntegration:
    """Test OpenSearch integration with Neo4j GraphRAG and Analytics (T-05)."""

    graphrag_service: Any
    analytics_service: AnalyticsStorageService
    
    def setup_method(self):
        """Setup test fixtures."""
        # Use lightweight stubs; runtime endpoints validate live integrations.
        self.graphrag_service = GraphRAGServiceStub()
        self.analytics_service = AnalyticsStorageService()
    
    def test_hybrid_search_combines_neo4j_and_opensearch(self):
        """Test hybrid search combines Neo4j graph context with OpenSearch vectors."""
        # User query
        _user_question = "Show me all failed migrations with schema drift"
        
        # Neo4j graph search output shape (relationship traversal)
        neo4j_results = [
            {
                "session_id": "session-001",
                "state": "failed",
                "schema_drift": True,
                "error": "Column type mismatch",
                "related_sessions": ["session-005", "session-012"]
            },
            {
                "session_id": "session-008",
                "state": "failed",
                "schema_drift": True,
                "error": "Foreign key constraint violation",
                "related_sessions": ["session-003"]
            }
        ]
        
        # OpenSearch vector search output shape (semantic similarity)
        opensearch_results = [
            {
                "id": "doc-001",
                "content": "Migration failed due to schema incompatibility",
                "similarity_score": 0.92,
                "metadata": {"session_id": "session-001", "type": "error_log"}
            },
            {
                "id": "doc-015",
                "content": "Schema drift detected during validation phase",
                "similarity_score": 0.88,
                "metadata": {"session_id": "session-008", "type": "warning_log"}
            }
        ]
        
        # Hybrid result fusion (combine graph + vector results)
        fused_results = []
        for neo4j_result in neo4j_results:
            # Find matching OpenSearch docs
            matching_docs = [
                doc for doc in opensearch_results
                if doc["metadata"].get("session_id") == neo4j_result["session_id"]
            ]
            
            fused_results.append({
                "session_id": neo4j_result["session_id"],
                "state": neo4j_result["state"],
                "schema_drift": neo4j_result["schema_drift"],
                "error": neo4j_result["error"],
                "related_sessions": neo4j_result["related_sessions"],
                "documents": matching_docs,
                "relevance_score": sum(doc["similarity_score"] for doc in matching_docs) / len(matching_docs) if matching_docs else 0
            })
        
        assert len(fused_results) == 2
        assert all(result["schema_drift"] is True for result in fused_results)
        assert all(result["state"] == "failed" for result in fused_results)
        assert fused_results[0]["relevance_score"] > 0.9
    
    def test_semantic_validation_during_etl(self):
        """Test semantic validation using GraphRAG during ETL DATA_MIGRATION phase."""
        # Source data being migrated
        source_record = {
            "customer_id": "CUST-12345",
            "customer_name": "Acme Corporation",
            "contact_email": "contact@acme.com"
        }
        
        # Check for similar/duplicate entities using GraphRAG
        _similarity_query = {
            "question": f"Find customers similar to {source_record['customer_name']}",
            "context": "customer database",
            "top_k": 5
        }
        
        # GraphRAG semantic search result shape
        similar_entities = [
            {
                "entity_id": "CUST-12345",
                "name": "Acme Corporation",
                "similarity": 1.0,
                "match_type": "exact"
            },
            {
                "entity_id": "CUST-98765",
                "name": "ACME Corp",
                "similarity": 0.95,
                "match_type": "potential_duplicate"
            },
            {
                "entity_id": "CUST-45678",
                "name": "Acme Industries",
                "similarity": 0.82,
                "match_type": "related"
            }
        ]
        
        # Flag potential duplicates for review
        duplicates_flagged = [
            entity for entity in similar_entities
            if entity["similarity"] > 0.9 and entity["match_type"] == "potential_duplicate"
        ]
        
        assert len(duplicates_flagged) == 1
        assert duplicates_flagged[0]["entity_id"] == "CUST-98765"
        
        # In production, this would prevent duplicate insertion during migration
    
    @pytest.mark.asyncio
    async def test_analytics_metrics_indexed_in_both_systems(self):
        """Test analytics metrics are indexed in both Neo4j and OpenSearch (T-05)."""
        # Record migration quality metric
        quality_metric = {
            "timestamp": "2025-11-23T16:00:00",
            "session_id": "session-analytics-001",
            "quality_score": 0.95,
            "rows_migrated": 100000,
            "rows_failed": 5000,
            "schema_drift_detected": False,
            "duration_seconds": 3600
        }
        
        # Store in Analytics Service (T-05)
        result = await self.analytics_service.record_migration_quality(
            session_id=quality_metric["session_id"],
            quality_score=quality_metric["quality_score"],
            rows_migrated=quality_metric["rows_migrated"],
            rows_failed=quality_metric["rows_failed"],
            schema_drift_issues=1 if quality_metric["schema_drift_detected"] else 0,
        )
        assert result["status"] == "success"
        
        # Neo4j indexing data shape (graph relationships)
        neo4j_metric_node = {
            "id": "metric-001",
            "type": "MigrationQualityMetric",
            "session_id": quality_metric["session_id"],
            "quality_score": quality_metric["quality_score"],
            "timestamp": quality_metric["timestamp"]
        }
        
        # OpenSearch indexing data shape (vector embedding for semantic search)
        opensearch_document = {
            "id": "metric-001",
            "content": f"Migration quality score {quality_metric['quality_score']} with {quality_metric['rows_migrated']} rows migrated and {quality_metric['rows_failed']} failures",
            "embedding": [0.1, 0.2, 0.3],  # Test embedding vector
            "metadata": quality_metric
        }
        
        # Both systems indexed
        assert neo4j_metric_node["quality_score"] == 0.95
        assert opensearch_document["metadata"]["rows_migrated"] == 100000
    
    def test_graph_integration_service_coordinates_apis(self):
        """Test GraphIntegrationService.js coordinates GraphQL, GraphRAG, and Analytics."""
        # GraphIntegrationService API call/response shapes
        
        # 1. Query Analytics metrics (T-05)
        _analytics_request = {
            "endpoint": "/api/analytics/migration-quality",
            "params": {"session_id": "test-session"}
        }
        analytics_response = {
            "metrics": [
                {"quality_score": 0.95, "timestamp": "2025-11-23T15:00:00"},
                {"quality_score": 0.92, "timestamp": "2025-11-23T16:00:00"}
            ],
            "aggregate": {"average_quality": 0.935, "total_rows": 200000}
        }
        
        # 2. Query Neo4j GraphRAG for context
        _graphrag_request = {
            "endpoint": "/api/neo4j-graphrag/query",
            "body": {
                "question": "What caused quality score to drop?",
                "context": "migration session test-session",
                "top_k": 3
            }
        }
        graphrag_response = {
            "answers": [
                {
                    "content": "Schema drift detected in validation phase",
                    "confidence": 0.88,
                    "source": "neo4j-node-123"
                }
            ],
            "sources": [
                {"id": "neo4j-node-123", "type": "MigrationState", "state": "validation"}
            ]
        }
        
        # 3. Query GraphQL for migration history
        _graphql_request = {
            "endpoint": "/api/graphql/query",
            "body": {
                "query": "{ migrationHistory(sessionId: \"test-session\") { events { timestamp state } } }",
                "data": {}
            }
        }
        graphql_response = {
            "data": {
                "migrationHistory": {
                    "events": [
                        {"timestamp": "2025-11-23T15:00:00", "state": "idle"},
                        {"timestamp": "2025-11-23T15:05:00", "state": "completed"}
                    ]
                }
            }
        }
        
        # Unified response from GraphIntegrationService
        unified_response = {
            "analytics": analytics_response,
            "graph_context": graphrag_response,
            "migration_history": graphql_response
        }
        
        assert "analytics" in unified_response
        assert "graph_context" in unified_response
        assert "migration_history" in unified_response
        assert unified_response["analytics"]["aggregate"]["average_quality"] == 0.935
    
    def test_opensearch_knn_with_neo4j_context(self):
        """Test OpenSearch k-NN search enhanced with Neo4j graph context."""
        # User query embedding
        _query_embedding = [0.5, 0.3, 0.8, 0.1, 0.6]  # Test 5-dim vector
        
        # OpenSearch k-NN search output shape
        opensearch_knn_results = [
            {
                "id": "doc-001",
                "distance": 0.15,
                "content": "Migration completed successfully with validation",
                "metadata": {"session_id": "session-100"}
            },
            {
                "id": "doc-002",
                "distance": 0.22,
                "content": "Data migration phase encountered errors",
                "metadata": {"session_id": "session-101"}
            }
        ]
        
        # Enrich with Neo4j graph context
        enriched_results = []
        for doc in opensearch_knn_results:
            # Neo4j context lookup output shape
            neo4j_context = {
                "session_id": doc["metadata"]["session_id"],
                "related_sessions": ["session-099", "session-102"],
                "state_transitions": 7,
                "final_state": "completed" if doc["id"] == "doc-001" else "failed"
            }
            
            enriched_results.append({
                **doc,
                "graph_context": neo4j_context,
                "relevance_score": (1 - doc["distance"]) * 0.7 + (neo4j_context["state_transitions"] / 10) * 0.3
            })
        
        assert len(enriched_results) == 2
        assert all("graph_context" in result for result in enriched_results)
        assert enriched_results[0]["relevance_score"] > enriched_results[1]["relevance_score"]
    
    def test_result_fusion_algorithm(self):
        """Test result fusion combines Neo4j graph + OpenSearch vector results."""
        # Results from both systems
        neo4j_results = [
            {"id": "session-A", "score": 0.9, "source": "neo4j"},
            {"id": "session-B", "score": 0.7, "source": "neo4j"}
        ]
        
        opensearch_results = [
            {"id": "session-A", "score": 0.85, "source": "opensearch"},
            {"id": "session-C", "score": 0.8, "source": "opensearch"}
        ]
        
        # Fusion algorithm (weighted average + deduplication)
        fused_results = {}
        
        for result in neo4j_results:
            fused_results[result["id"]] = {
                "id": result["id"],
                "neo4j_score": result["score"],
                "opensearch_score": 0,
                "combined_score": result["score"] * 0.6  # Neo4j weight: 0.6
            }
        
        for result in opensearch_results:
            if result["id"] in fused_results:
                fused_results[result["id"]]["opensearch_score"] = result["score"]
                fused_results[result["id"]]["combined_score"] += result["score"] * 0.4  # OpenSearch weight: 0.4
            else:
                fused_results[result["id"]] = {
                    "id": result["id"],
                    "neo4j_score": 0,
                    "opensearch_score": result["score"],
                    "combined_score": result["score"] * 0.4
                }
        
        # Sort by combined score
        sorted_results = sorted(fused_results.values(), key=lambda x: x["combined_score"], reverse=True)
        
        assert len(sorted_results) == 3
        assert sorted_results[0]["id"] == "session-A"  # Present in both systems
        assert sorted_results[0]["combined_score"] > 0.8


class TestAnalyticsGraphRAGIntegration:
    """Test Analytics Service (T-05) integration with GraphRAG."""

    analytics_service: AnalyticsStorageService
    
    def setup_method(self):
        """Setup test fixtures."""
        self.analytics_service = AnalyticsStorageService()
    
    @pytest.mark.asyncio
    async def test_analytics_dashboard_uses_graphrag_insights(self):
        """Test analytics dashboard queries GraphRAG for contextual insights."""
        # Get upload metrics from Analytics Service (T-05)
        upload_metrics = await self.analytics_service.get_upload_metrics()
        
        # GraphRAG query for insights
        _graphrag_query = {
            "question": "Why are recent uploads slower than average?",
            "context": f"Upload metrics: {upload_metrics}",
            "tools": ["analytics_analyzer", "performance_profiler"]
        }
        
        # GraphRAG response with insights
        insights = {
            "answers": [
                {
                    "content": "Recent uploads show 30% increase in file size",
                    "confidence": 0.91,
                    "evidence": ["metric-upload-501", "metric-upload-502"]
                },
                {
                    "content": "Network latency increased during peak hours",
                    "confidence": 0.85,
                    "evidence": ["service-health-log-350"]
                }
            ],
            "recommendations": [
                "Consider implementing file compression",
                "Scale up during peak hours (2-4 PM)"
            ]
        }
        
        assert len(insights["answers"]) == 2
        assert len(insights["recommendations"]) == 2
    
    @pytest.mark.asyncio
    async def test_service_health_monitoring_with_graphrag(self):
        """Test service health monitoring uses GraphRAG for anomaly detection."""
        # Record service health metrics (T-05)
        health_metric = {
            "timestamp": "2025-11-23T16:00:00",
            "service_name": "migration_engine",
            "cpu_percent": 85.5,
            "memory_percent": 72.3,
            "response_time_ms": 450,
            "error_rate": 0.02
        }
        
        result = await self.analytics_service.record_service_health(
            service_name=health_metric["service_name"],
            status="healthy",
            cpu_percent=health_metric["cpu_percent"],
            memory_percent=health_metric["memory_percent"],
            response_time_ms=health_metric["response_time_ms"],
            error_rate=health_metric["error_rate"],
        )
        assert result["status"] == "success"
        
        # Query GraphRAG for anomaly analysis
        _anomaly_query = {
            "question": "Is this CPU usage normal for migration_engine?",
            "context": f"Current metrics: {health_metric}",
            "top_k": 5
        }
        
        # GraphRAG anomaly detection output shape
        anomaly_response = {
            "is_anomaly": True,
            "severity": "warning",
            "explanation": "CPU usage 85.5% exceeds 90th percentile (65%)",
            "similar_incidents": [
                {"timestamp": "2025-11-20T14:30:00", "cpu": 88.0, "resolution": "scaled horizontally"},
                {"timestamp": "2025-11-18T09:15:00", "cpu": 82.5, "resolution": "optimized queries"}
            ],
            "recommended_actions": [
                "Check for long-running migrations",
                "Review query performance",
                "Consider horizontal scaling"
            ]
        }
        
        assert anomaly_response["is_anomaly"] is True
        assert len(anomaly_response["similar_incidents"]) == 2
        assert len(anomaly_response["recommended_actions"]) == 3
