"""
Ranking Service - ML-based search result ranking with feedback learning

Provides repositories for ranking feedback, parameters, and analytics.
Includes ML ranker for scoring and parameter optimization.
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from statistics import mean, stdev
import math

from sqlalchemy import desc, func, and_
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from models.ranking_models import (
    RankingFeedbackORM, RankingParameterORM, RankingAnalyticsORM, SearchSessionORM,
    RankingFeedback, RankingParameter, RankingAnalytics, SearchSession,
    RankingFeedbackCreate, RankingParameterCreate, RankingAnalyticsCreate,
    FeedbackType, RankingMetricType, ABTestVariant
)

logger = logging.getLogger(__name__)


# ============================================================================
# Repositories
# ============================================================================

class RankingFeedbackRepository:
    """CRUD operations for ranking feedback"""

    def __init__(self, session: Session):
        self.session = session

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.session.close()

    def create(self, feedback: RankingFeedbackCreate) -> RankingFeedback:
        """Record user feedback"""
        orm = RankingFeedbackORM(
            query=feedback.query,
            result_id=feedback.result_id,
            feedback_type=feedback.feedback_type.value,
            score=feedback.score,
            dwell_time_seconds=feedback.dwell_time_seconds,
            session_id=feedback.session_id,
            user_id=feedback.user_id,
            metadata=feedback.metadata or {},
        )
        self.session.add(orm)
        self.session.commit()
        return orm.to_pydantic()

    def read(self, feedback_id: str) -> Optional[RankingFeedback]:
        """Get feedback by ID"""
        orm = self.session.query(RankingFeedbackORM).filter_by(id=feedback_id, enabled=1).first()
        return orm.to_pydantic() if orm else None

    def list_by_session(self, session_id: str, skip: int = 0, limit: int = 100) -> List[RankingFeedback]:
        """Get all feedback for a session"""
        orms = self.session.query(RankingFeedbackORM).filter_by(
            session_id=session_id, enabled=1
        ).offset(skip).limit(limit).all()
        return [orm.to_pydantic() for orm in orms]

    def list_by_query(self, query: str, skip: int = 0, limit: int = 100) -> List[RankingFeedback]:
        """Get feedback for a specific query"""
        orms = self.session.query(RankingFeedbackORM).filter_by(
            query=query, enabled=1
        ).order_by(desc(RankingFeedbackORM.created_at)).offset(skip).limit(limit).all()
        return [orm.to_pydantic() for orm in orms]

    def list_recent(self, days: int = 7, skip: int = 0, limit: int = 100) -> List[RankingFeedback]:
        """Get recent feedback"""
        cutoff = datetime.utcnow() - timedelta(days=days)
        orms = self.session.query(RankingFeedbackORM).filter(
            and_(RankingFeedbackORM.enabled == 1, RankingFeedbackORM.created_at >= cutoff)
        ).order_by(desc(RankingFeedbackORM.created_at)).offset(skip).limit(limit).all()
        return [orm.to_pydantic() for orm in orms]

    def count_by_type(self, feedback_type: FeedbackType) -> int:
        """Count feedback by type"""
        return self.session.query(RankingFeedbackORM).filter_by(
            feedback_type=feedback_type.value, enabled=1
        ).count()


class RankingParameterRepository:
    """CRUD operations for ranking models"""

    def __init__(self, session: Session):
        self.session = session

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.session.close()

    def create(self, params: RankingParameterCreate) -> RankingParameter:
        """Create ranking model"""
        orm = RankingParameterORM(
            model_name=params.model_name,
            semantic_weight=params.semantic_weight,
            vector_weight=params.vector_weight,
            graph_weight=params.graph_weight,
            feedback_boost=params.feedback_boost,
            fresh_boost=params.fresh_boost,
            popularity_weight=params.popularity_weight,
            ab_test_variant=params.ab_test_variant.value,
            enabled=1 if params.enabled else 0,
            metadata=params.metadata or {},
        )
        self.session.add(orm)
        try:
            self.session.commit()
        except IntegrityError as e:
            self.session.rollback()
            raise ValueError(f"Model name '{params.model_name}' already exists") from e
        return orm.to_pydantic()

    def read(self, model_id: str) -> Optional[RankingParameter]:
        """Get model by ID"""
        orm = self.session.query(RankingParameterORM).filter_by(id=model_id).first()
        return orm.to_pydantic() if orm else None

    def read_by_name(self, model_name: str) -> Optional[RankingParameter]:
        """Get model by name"""
        orm = self.session.query(RankingParameterORM).filter_by(model_name=model_name).first()
        return orm.to_pydantic() if orm else None

    def list_enabled(self, skip: int = 0, limit: int = 100) -> List[RankingParameter]:
        """List active models"""
        orms = self.session.query(RankingParameterORM).filter_by(
            enabled=1
        ).order_by(desc(RankingParameterORM.created_at)).offset(skip).limit(limit).all()
        return [orm.to_pydantic() for orm in orms]

    def list_by_variant(self, variant: ABTestVariant) -> List[RankingParameter]:
        """Get all models for AB test variant"""
        orms = self.session.query(RankingParameterORM).filter_by(
            ab_test_variant=variant.value, enabled=1
        ).all()
        return [orm.to_pydantic() for orm in orms]

    def update(self, model_id: str, updates: Dict[str, Any]) -> Optional[RankingParameter]:
        """Update model parameters"""
        orm = self.session.query(RankingParameterORM).filter_by(id=model_id).first()
        if not orm:
            return None

        for key, value in updates.items():
            if key == 'ab_test_variant' and isinstance(value, ABTestVariant):
                setattr(orm, key, value.value)
            elif hasattr(orm, key):
                setattr(orm, key, value)

        orm.updated_at = datetime.utcnow()
        self.session.commit()
        return orm.to_pydantic()

    def increment_usage(self, model_id: str) -> None:
        """Increment usage count"""
        orm = self.session.query(RankingParameterORM).filter_by(id=model_id).first()
        if orm:
            orm.usage_count += 1
            self.session.commit()


class RankingAnalyticsRepository:
    """CRUD operations for ranking analytics"""

    def __init__(self, session: Session):
        self.session = session

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.session.close()

    def create(self, analytics: RankingAnalyticsCreate) -> RankingAnalytics:
        """Record analytics metric"""
        orm = RankingAnalyticsORM(
            model_id=analytics.model_id,
            metric_type=analytics.metric_type.value,
            metric_value=analytics.metric_value,
            query_count=analytics.query_count,
            feedback_count=analytics.feedback_count,
            metadata=analytics.metadata or {},
        )
        self.session.add(orm)
        self.session.commit()
        return orm.to_pydantic()

    def list_by_model(self, model_id: str, metric_type: Optional[RankingMetricType] = None,
                      days: int = 7, skip: int = 0, limit: int = 100) -> List[RankingAnalytics]:
        """Get metrics for a model"""
        cutoff = datetime.utcnow() - timedelta(days=days)
        query = self.session.query(RankingAnalyticsORM).filter(
            and_(
                RankingAnalyticsORM.model_id == model_id,
                RankingAnalyticsORM.measured_at >= cutoff
            )
        )
        if metric_type:
            query = query.filter_by(metric_type=metric_type.value)
        orms = query.order_by(RankingAnalyticsORM.measured_at).offset(skip).limit(limit).all()
        return [orm.to_pydantic() for orm in orms]

    def get_latest_metrics(self, model_id: str) -> Dict[str, float]:
        """Get latest metric values for model"""
        orms = self.session.query(RankingAnalyticsORM).filter_by(
            model_id=model_id
        ).order_by(desc(RankingAnalyticsORM.measured_at)).limit(4).all()

        metrics = {}
        for orm in orms:
            metric_type = orm.metric_type
            if metric_type not in metrics:
                metrics[metric_type] = orm.metric_value
        return metrics


class SearchSessionRepository:
    """CRUD operations for search sessions"""

    def __init__(self, session: Session):
        self.session = session

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.session.close()

    def create(self, search_session) -> SearchSession:
        """Create search session"""
        orm = SearchSessionORM(
            session_id=search_session.session_id,
            user_id=search_session.user_id,
            query=search_session.query,
            mode=search_session.mode,
            results_shown=search_session.results_shown,
            ranking_model_id=search_session.ranking_model_id,
            ab_variant=search_session.ab_variant.value,
        )
        self.session.add(orm)
        self.session.commit()
        return orm.to_pydantic()

    def read(self, session_id: str) -> Optional[SearchSession]:
        """Get session by ID"""
        orm = self.session.query(SearchSessionORM).filter_by(session_id=session_id).first()
        return orm.to_pydantic() if orm else None

    def record_feedback(self, session_id: str, feedback_count: int) -> None:
        """Update session feedback count"""
        orm = self.session.query(SearchSessionORM).filter_by(session_id=session_id).first()
        if orm:
            orm.feedback_count = feedback_count
            self.session.commit()

    def record_clicks(self, session_id: str, clicks: int) -> None:
        """Record clicks in session"""
        orm = self.session.query(SearchSessionORM).filter_by(session_id=session_id).first()
        if orm:
            orm.clicks = clicks
            self.session.commit()

    def record_dwell_times(self, session_id: str, dwell_times: List[float]) -> None:
        """Record dwell times per result"""
        orm = self.session.query(SearchSessionORM).filter_by(session_id=session_id).first()
        if orm:
            orm.dwell_times = dwell_times
            self.session.commit()


# ============================================================================
# Analytics Service
# ============================================================================

class RankingAnalyticsService:
    """Calculate ranking performance metrics"""

    @staticmethod
    def calculate_ctr(feedback_repo: RankingFeedbackRepository, days: int = 7) -> float:
        """Calculate click-through rate"""
        recent = feedback_repo.list_recent(days)
        if not recent:
            return 0.0

        clicks = sum(1 for f in recent if f.feedback_type == FeedbackType.CLICK)
        impressions = len(recent)
        return clicks / impressions if impressions > 0 else 0.0

    @staticmethod
    def calculate_ndcg(feedback_repo: RankingFeedbackRepository, days: int = 7) -> float:
        """Calculate normalized discounted cumulative gain (simplified)"""
        recent = feedback_repo.list_recent(days)
        if not recent:
            return 0.0

        # Simplified NDCG: weight clicks by position
        dcg = 0.0
        idcg = 0.0
        for i, feedback in enumerate(recent[:10]):  # Top 10
            relevance = 1.0 if feedback.feedback_type == FeedbackType.CLICK else 0.0
            discount = 1.0 / math.log2(i + 2)  # Log discount
            dcg += relevance * discount
            idcg += discount  # Ideal is all clicks

        return dcg / idcg if idcg > 0 else 0.0

    @staticmethod
    def calculate_mrr(feedback_repo: RankingFeedbackRepository, days: int = 7) -> float:
        """Calculate mean reciprocal rank"""
        recent = feedback_repo.list_recent(days)
        if not recent:
            return 0.0

        # Find average position of first click
        positions = []
        for i, feedback in enumerate(recent[:20]):  # Check top 20
            if feedback.feedback_type == FeedbackType.CLICK:
                positions.append(1.0 / (i + 1))

        return mean(positions) if positions else 0.0


# ============================================================================
# ML Ranker
# ============================================================================

class MLRanker:
    """Machine learning-based result ranking"""

    def __init__(self, ranking_params: RankingParameter, feedback_repo: Optional[RankingFeedbackRepository] = None):
        self.params = ranking_params
        self.feedback_repo = feedback_repo

    def rank_results(self, results: List[Dict[str, Any]], query: str) -> List[Dict[str, Any]]:
        """
        Rank search results using ML model.

        Combines multiple signals:
        1. Base scores from semantic/vector/graph search
        2. User feedback boost (clicks, ratings)
        3. Freshness/recency boost
        4. Popularity signal
        """
        if not results:
            return results

        # Calculate feature vectors for each result
        ranked = []
        for result in results:
            score = self._compute_ml_score(result, query)
            result_copy = result.copy()
            result_copy['ml_score'] = score
            ranked.append(result_copy)

        # Sort by ML score
        ranked.sort(key=lambda x: x['ml_score'], reverse=True)
        return ranked

    def _compute_ml_score(self, result: Dict[str, Any], query: str) -> float:
        """Compute ML score for single result"""
        # Base score from search sources
        semantic_score = result.get('semantic_score', 0.0) or 0.0
        vector_score = result.get('vector_score', 0.0) or 0.0
        graph_score = result.get('graph_score', 0.0) or 0.0

        # Weighted combination
        base_score = (
            self.params.semantic_weight * semantic_score +
            self.params.vector_weight * vector_score +
            self.params.graph_weight * graph_score
        )

        # Feedback boost (if available)
        feedback_boost = 0.0
        if self.feedback_repo:
            feedback_boost = self._get_feedback_boost(result.get('id', ''))

        # Freshness boost
        freshness_boost = self._get_freshness_boost(result.get('created_at'))

        # Popularity signal
        popularity_boost = self._get_popularity_boost(result.get('popularity', 0.0))

        # Combine all signals
        final_score = (
            base_score +
            feedback_boost * self.params.feedback_boost +
            freshness_boost * self.params.fresh_boost +
            popularity_boost * self.params.popularity_weight
        )

        return min(1.0, max(0.0, final_score))  # Normalize to [0, 1]

    def _get_feedback_boost(self, result_id: str) -> float:
        """Calculate boost from feedback signals"""
        if not self.feedback_repo:
            return 0.0

        try:
            # Count positive feedback signals
            recent_feedback = self.feedback_repo.list_recent(days=30)
            result_feedback = [f for f in recent_feedback if f.result_id == result_id]

            if not result_feedback:
                return 0.0

            # Weighted feedback calculation
            click_count = sum(1 for f in result_feedback if f.feedback_type == FeedbackType.CLICK)
            rating_sum = sum(f.score or 0 for f in result_feedback if f.feedback_type == FeedbackType.RATING)
            positive_judgments = sum(1 for f in result_feedback if f.feedback_type == FeedbackType.RELEVANT)

            feedback_score = (
                0.5 * (click_count / len(result_feedback)) +  # Click ratio
                0.3 * (rating_sum / (5 * len(result_feedback)) if rating_sum > 0 else 0) +  # Average rating
                0.2 * (positive_judgments / len(result_feedback))  # Relevance ratio
            )

            return min(1.0, feedback_score)
        except Exception as e:
            logger.warning("Error calculating feedback boost: %s", e)
            return 0.0

    @staticmethod
    def _get_freshness_boost(created_at) -> float:
        """Boost score based on result freshness"""
        if not created_at:
            return 0.0

        try:
            if isinstance(created_at, str):
                created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00'))

            age_days = (datetime.utcnow() - created_at).days
            if age_days <= 7:
                return 1.0
            elif age_days <= 30:
                return 0.7
            elif age_days <= 90:
                return 0.4
            else:
                return 0.1
        except Exception:
            return 0.0

    @staticmethod
    def _get_popularity_boost(popularity: float) -> float:
        """Boost score based on popularity signal"""
        if not popularity:
            return 0.0
        return min(1.0, popularity / 100.0)  # Normalize popularity to [0, 1]
