"""
Test ranking functionality

Run with:
    python -m pytest python_backend/tests/test_ranking.py -v
"""

import pytest
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.database import Base
from models.ranking_models import (
    RankingFeedbackORM, RankingParameterORM, RankingAnalyticsORM, SearchSessionORM,
    RankingFeedbackCreate, RankingParameterCreate, RankingAnalyticsCreate,
    FeedbackType, RankingMetricType, ABTestVariant
)
from services.ranking_service import (
    RankingFeedbackRepository, RankingParameterRepository,
    RankingAnalyticsRepository, SearchSessionRepository,
    RankingAnalyticsService, MLRanker
)


# Setup test database
@pytest.fixture
def test_db():
    """Create test database session"""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    yield session
    session.close()


# ============================================================================
# Feedback Repository Tests
# ============================================================================

class TestRankingFeedbackRepository:
    """Test feedback storage and retrieval"""
    
    def test_create_feedback(self, test_db):
        """Test creating feedback"""
        repo = RankingFeedbackRepository(test_db)
        
        request = RankingFeedbackCreate(
            query="machine learning",
            result_id="doc_123",
            feedback_type=FeedbackType.CLICK,
            session_id="session_1"
        )
        
        feedback = repo.create(request)
        
        assert feedback.query == "machine learning"
        assert feedback.result_id == "doc_123"
        assert feedback.feedback_type == FeedbackType.CLICK
    
    def test_create_feedback_with_rating(self, test_db):
        """Test feedback with rating"""
        repo = RankingFeedbackRepository(test_db)
        
        request = RankingFeedbackCreate(
            query="test query",
            result_id="doc_456",
            feedback_type=FeedbackType.RATING,
            score=4.5,
            session_id="session_2"
        )
        
        feedback = repo.create(request)
        
        assert feedback.score == 4.5
        assert feedback.feedback_type == FeedbackType.RATING
    
    def test_read_feedback(self, test_db):
        """Test reading feedback"""
        repo = RankingFeedbackRepository(test_db)
        
        created = repo.create(RankingFeedbackCreate(
            query="test",
            result_id="doc_789",
            feedback_type=FeedbackType.CLICK
        ))
        
        read = repo.read(created.id)
        
        assert read is not None
        assert read.id == created.id
    
    def test_list_by_session(self, test_db):
        """Test listing feedback by session"""
        repo = RankingFeedbackRepository(test_db)
        
        session_id = "session_abc"
        for i in range(3):
            repo.create(RankingFeedbackCreate(
                query=f"query_{i}",
                result_id=f"doc_{i}",
                feedback_type=FeedbackType.CLICK,
                session_id=session_id
            ))
        
        feedbacks = repo.list_by_session(session_id)
        
        assert len(feedbacks) == 3
    
    def test_list_by_query(self, test_db):
        """Test listing feedback by query"""
        repo = RankingFeedbackRepository(test_db)
        
        query = "same query"
        for i in range(2):
            repo.create(RankingFeedbackCreate(
                query=query,
                result_id=f"doc_{i}",
                feedback_type=FeedbackType.CLICK
            ))
        
        feedbacks = repo.list_by_query(query)
        
        assert len(feedbacks) == 2
        assert all(f.query == query for f in feedbacks)
    
    def test_count_by_type(self, test_db):
        """Test counting feedback by type"""
        repo = RankingFeedbackRepository(test_db)
        
        for i in range(3):
            repo.create(RankingFeedbackCreate(
                query="test",
                result_id=f"doc_{i}",
                feedback_type=FeedbackType.CLICK
            ))
        
        count = repo.count_by_type(FeedbackType.CLICK)
        
        assert count == 3


# ============================================================================
# Ranking Parameter Repository Tests
# ============================================================================

class TestRankingParameterRepository:
    """Test ranking model parameter management"""
    
    def test_create_model(self, test_db):
        """Test creating ranking model"""
        repo = RankingParameterRepository(test_db)
        
        request = RankingParameterCreate(
            model_name="default_v1",
            semantic_weight=0.4,
            vector_weight=0.3,
            graph_weight=0.3
        )
        
        model = repo.create(request)
        
        assert model.model_name == "default_v1"
        assert model.semantic_weight == 0.4
    
    def test_read_model(self, test_db):
        """Test reading model by ID"""
        repo = RankingParameterRepository(test_db)
        
        created = repo.create(RankingParameterCreate(
            model_name="test_model",
            semantic_weight=0.5
        ))
        
        read = repo.read(created.id)
        
        assert read is not None
        assert read.model_name == "test_model"
    
    def test_read_by_name(self, test_db):
        """Test reading model by name"""
        repo = RankingParameterRepository(test_db)
        
        repo.create(RankingParameterCreate(
            model_name="unique_model"
        ))
        
        model = repo.read_by_name("unique_model")
        
        assert model is not None
        assert model.model_name == "unique_model"
    
    def test_create_duplicate_name(self, test_db):
        """Test duplicate model name raises error"""
        repo = RankingParameterRepository(test_db)
        
        repo.create(RankingParameterCreate(model_name="duplicate"))
        
        with pytest.raises(ValueError):
            repo.create(RankingParameterCreate(model_name="duplicate"))
    
    def test_list_enabled(self, test_db):
        """Test listing enabled models"""
        repo = RankingParameterRepository(test_db)
        
        for i in range(3):
            repo.create(RankingParameterCreate(
                model_name=f"model_{i}",
                enabled=True
            ))
        
        models = repo.list_enabled()
        
        assert len(models) == 3
    
    def test_update_model(self, test_db):
        """Test updating model parameters"""
        repo = RankingParameterRepository(test_db)
        
        created = repo.create(RankingParameterCreate(
            model_name="to_update",
            semantic_weight=0.3
        ))
        
        updated = repo.update(created.id, {"semantic_weight": 0.6})
        
        assert updated is not None
        assert updated.semantic_weight == 0.6
    
    def test_increment_usage(self, test_db):
        """Test incrementing model usage"""
        repo = RankingParameterRepository(test_db)
        
        created = repo.create(RankingParameterCreate(model_name="usage_test"))
        
        repo.increment_usage(created.id)
        repo.increment_usage(created.id)
        
        updated = repo.read(created.id)
        
        assert updated.usage_count == 2


# ============================================================================
# Analytics Repository Tests
# ============================================================================

class TestRankingAnalyticsRepository:
    """Test analytics storage and retrieval"""
    
    def test_create_analytics(self, test_db):
        """Test creating analytics record"""
        repo = RankingAnalyticsRepository(test_db)
        
        request = RankingAnalyticsCreate(
            model_id="model_1",
            metric_type=RankingMetricType.CTR,
            metric_value=0.25,
            query_count=100
        )
        
        analytics = repo.create(request)
        
        assert analytics.metric_type == RankingMetricType.CTR
        assert analytics.metric_value == 0.25
    
    def test_list_by_model(self, test_db):
        """Test listing analytics by model"""
        repo = RankingAnalyticsRepository(test_db)
        
        model_id = "model_x"
        for metric_type in [RankingMetricType.CTR, RankingMetricType.NDCG, RankingMetricType.MRR]:
            repo.create(RankingAnalyticsCreate(
                model_id=model_id,
                metric_type=metric_type,
                metric_value=0.5
            ))
        
        analytics = repo.list_by_model(model_id)
        
        assert len(analytics) == 3
    
    def test_get_latest_metrics(self, test_db):
        """Test getting latest metrics"""
        repo = RankingAnalyticsRepository(test_db)
        
        model_id = "model_y"
        repo.create(RankingAnalyticsCreate(
            model_id=model_id,
            metric_type=RankingMetricType.CTR,
            metric_value=0.20
        ))
        repo.create(RankingAnalyticsCreate(
            model_id=model_id,
            metric_type=RankingMetricType.NDCG,
            metric_value=0.75
        ))
        
        latest = repo.get_latest_metrics(model_id)
        
        assert RankingMetricType.CTR.value in latest
        assert RankingMetricType.NDCG.value in latest


# ============================================================================
# Analytics Service Tests
# ============================================================================

class TestRankingAnalyticsService:
    """Test analytics calculations"""
    
    def test_calculate_ctr(self, test_db):
        """Test CTR calculation"""
        feedback_repo = RankingFeedbackRepository(test_db)
        
        # Create mixed feedback
        for i in range(3):
            feedback_repo.create(RankingFeedbackCreate(
                query="test",
                result_id=f"doc_{i}",
                feedback_type=FeedbackType.CLICK
            ))
        
        for i in range(2):
            feedback_repo.create(RankingFeedbackCreate(
                query="test",
                result_id=f"doc_skip_{i}",
                feedback_type=FeedbackType.SKIP
            ))
        
        ctr = RankingAnalyticsService.calculate_ctr(feedback_repo)
        
        assert 0 < ctr <= 1
        assert ctr == 0.6  # 3 clicks / 5 total
    
    def test_calculate_ndcg(self, test_db):
        """Test NDCG calculation"""
        feedback_repo = RankingFeedbackRepository(test_db)
        
        feedback_repo.create(RankingFeedbackCreate(
            query="test",
            result_id="doc_1",
            feedback_type=FeedbackType.CLICK
        ))
        
        ndcg = RankingAnalyticsService.calculate_ndcg(feedback_repo)
        
        assert 0 <= ndcg <= 1
    
    def test_calculate_mrr(self, test_db):
        """Test MRR calculation"""
        feedback_repo = RankingFeedbackRepository(test_db)
        
        feedback_repo.create(RankingFeedbackCreate(
            query="test",
            result_id="doc_1",
            feedback_type=FeedbackType.CLICK
        ))
        
        mrr = RankingAnalyticsService.calculate_mrr(feedback_repo)
        
        assert 0 <= mrr <= 1


# ============================================================================
# ML Ranker Tests
# ============================================================================

class TestMLRanker:
    """Test ML-based ranking"""
    
    def test_rank_results(self, test_db):
        """Test ranking results"""
        params = RankingParameterCreate(
            model_name="test_ranker",
            semantic_weight=0.4,
            vector_weight=0.3,
            graph_weight=0.3
        )
        param_repo = RankingParameterRepository(test_db)
        created_params = param_repo.create(params)
        
        ranker = MLRanker(created_params)
        
        results = [
            {"id": "1", "title": "Result 1", "semantic_score": 0.8, "vector_score": 0.6},
            {"id": "2", "title": "Result 2", "semantic_score": 0.6, "vector_score": 0.8},
        ]
        
        ranked = ranker.rank_results(results, "test query")
        
        assert len(ranked) == 2
        assert "ml_score" in ranked[0]
        assert ranked[0]["ml_score"] >= ranked[1]["ml_score"]
    
    def test_rank_with_freshness(self, test_db):
        """Test ranking with freshness boost"""
        params = RankingParameterCreate(
            model_name="test_fresh",
            fresh_boost=0.2
        )
        param_repo = RankingParameterRepository(test_db)
        created_params = param_repo.create(params)
        
        ranker = MLRanker(created_params)
        
        recent_date = datetime.utcnow().isoformat()
        old_date = (datetime.utcnow() - timedelta(days=60)).isoformat()
        
        results = [
            {"id": "1", "semantic_score": 0.5, "vector_score": 0.5, "created_at": recent_date},
            {"id": "2", "semantic_score": 0.5, "vector_score": 0.5, "created_at": old_date},
        ]
        
        ranked = ranker.rank_results(results, "test")
        
        # Recent result should score higher
        assert ranked[0]["id"] == "1"
    
    def test_empty_results(self, test_db):
        """Test ranking with empty results"""
        params = RankingParameterCreate(model_name="test_empty")
        param_repo = RankingParameterRepository(test_db)
        created_params = param_repo.create(params)
        
        ranker = MLRanker(created_params)
        
        ranked = ranker.rank_results([], "test query")
        
        assert ranked == []


# ============================================================================
# Integration Tests
# ============================================================================

@pytest.mark.integration
class TestRankingIntegration:
    """Integration tests for ranking workflow"""
    
    def test_feedback_to_analytics_workflow(self, test_db):
        """Test workflow from feedback to analytics"""
        feedback_repo = RankingFeedbackRepository(test_db)
        analytics_repo = RankingAnalyticsRepository(test_db)
        
        # Create feedback
        for i in range(5):
            feedback_repo.create(RankingFeedbackCreate(
                query="integration test",
                result_id=f"doc_{i}",
                feedback_type=FeedbackType.CLICK if i < 3 else FeedbackType.SKIP
            ))
        
        # Calculate metrics
        ctr = RankingAnalyticsService.calculate_ctr(feedback_repo)
        
        # Record analytics
        analytics_repo.create(RankingAnalyticsCreate(
            model_id="integration_model",
            metric_type=RankingMetricType.CTR,
            metric_value=ctr,
            query_count=5
        ))
        
        # Verify
        assert ctr == 0.6
        metrics = analytics_repo.get_latest_metrics("integration_model")
        assert RankingMetricType.CTR.value in metrics
    
    def test_model_feedback_ranking_workflow(self, test_db):
        """Test complete ranking workflow"""
        param_repo = RankingParameterRepository(test_db)
        feedback_repo = RankingFeedbackRepository(test_db)
        
        # Create ranking model
        params = param_repo.create(RankingParameterCreate(
            model_name="workflow_test"
        ))
        
        # Create ranker
        ranker = MLRanker(params, feedback_repo)
        
        # Rank results
        results = [
            {"id": "1", "semantic_score": 0.7, "vector_score": 0.7},
            {"id": "2", "semantic_score": 0.5, "vector_score": 0.5},
        ]
        
        ranked = ranker.rank_results(results, "test")
        
        # Record feedback on top result
        feedback_repo.create(RankingFeedbackCreate(
            query="test",
            result_id=ranked[0]["id"],
            feedback_type=FeedbackType.CLICK
        ))
        
        # Verify workflow completed
        assert len(ranked) == 2
        assert ranked[0]["ml_score"] > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
