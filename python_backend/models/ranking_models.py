"""
Ranking Models - Data structures for ML-based search result ranking

Supports user feedback, ranking parameters, and performance analytics.
Integrates with OpenSearch and conversational search to improve ranking quality.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from enum import Enum

from sqlalchemy import Column, String, Integer, Float, DateTime, Boolean, JSON, Index, func
from sqlalchemy.orm import mapped_column
from pydantic import BaseModel, Field

from core.database import Base


# ============================================================================
# Enumerations
# ============================================================================

class FeedbackType(str, Enum):
    """Types of user feedback for ranking learning"""
    CLICK = "click"  # User clicked on result
    SKIP = "skip"  # User skipped result
    RATING = "rating"  # User rated result (1-5)
    DWELL_TIME = "dwell_time"  # Time spent on result (seconds)
    RELEVANT = "relevant"  # Explicit relevance judgment (binary)
    NOT_RELEVANT = "not_relevant"  # Explicit irrelevance judgment


class ABTestVariant(str, Enum):
    """A/B test variants for ranking parameter tuning"""
    CONTROL = "control"  # Current ranking model
    VARIANT_A = "variant_a"  # Alternative ranking A
    VARIANT_B = "variant_b"  # Alternative ranking B
    VARIANT_C = "variant_c"  # Alternative ranking C


class RankingMetricType(str, Enum):
    """Ranking performance metrics"""
    CTR = "ctr"  # Click-through rate (clicks / impressions)
    NDCG = "ndcg"  # Normalized discounted cumulative gain (0-1)
    MRR = "mrr"  # Mean reciprocal rank (1/rank of first relevant)
    MAP = "map"  # Mean average precision


# ============================================================================
# Pydantic Models (Request/Response)
# ============================================================================

class RankingFeedbackCreate(BaseModel):
    """Request model for recording user feedback"""
    query: str = Field(..., description="Search query text")
    result_id: str = Field(..., description="Unique result ID")
    feedback_type: FeedbackType = Field(..., description="Type of feedback")
    score: Optional[float] = Field(default=None, ge=0, le=5, description="Rating score 0-5")
    dwell_time_seconds: Optional[int] = Field(default=None, ge=0, description="Time spent on result")
    session_id: Optional[str] = Field(default=None, description="Search session ID")
    user_id: Optional[str] = Field(default=None, description="User ID (optional)")
    extra_metadata: Optional[Dict[str, Any]] = Field(default=None, description="Additional metadata")


class RankingFeedback(RankingFeedbackCreate):
    """Response model for feedback"""
    id: str
    created_at: datetime
    enabled: bool


class RankingParameterCreate(BaseModel):
    """Request model for creating ranking parameters"""
    model_name: str = Field(..., description="Name of ranking model")
    semantic_weight: float = Field(default=0.33, ge=0, le=1, description="Weight for semantic search (0-1)")
    vector_weight: float = Field(default=0.33, ge=0, le=1, description="Weight for vector search (0-1)")
    graph_weight: float = Field(default=0.33, ge=0, le=1, description="Weight for graph search (0-1)")
    feedback_boost: float = Field(default=0.1, ge=0, le=1, description="Feedback boost factor (0-1)")
    fresh_boost: float = Field(default=0.05, ge=0, le=1, description="Recency boost factor (0-1)")
    popularity_weight: float = Field(default=0.2, ge=0, le=1, description="Popularity signal weight (0-1)")
    ab_test_variant: ABTestVariant = Field(default=ABTestVariant.CONTROL, description="A/B test variant")
    enabled: bool = Field(default=True, description="Whether this model is active")
    extra_metadata: Optional[Dict[str, Any]] = Field(default=None, description="Additional configuration")


class RankingParameter(RankingParameterCreate):
    """Response model for ranking parameters"""
    id: str
    created_at: datetime
    updated_at: datetime
    usage_count: int = Field(default=0, description="Times this model was used")


class RankingAnalyticsCreate(BaseModel):
    """Request model for analytics data"""
    model_id: str = Field(..., description="Ranking model ID")
    metric_type: RankingMetricType = Field(..., description="Metric type")
    metric_value: float = Field(..., ge=0, le=1, description="Metric value (0-1 normalized)")
    query_count: int = Field(default=1, ge=1, description="Number of queries in measurement")
    feedback_count: int = Field(default=0, ge=0, description="Number of feedback signals")
    extra_metadata: Optional[Dict[str, Any]] = Field(default=None, description="Additional metadata")


class RankingAnalytics(RankingAnalyticsCreate):
    """Response model for ranking analytics"""
    id: str
    measured_at: datetime
    time_period: str = Field(default="daily", description="Time period for aggregation")


class SearchSessionCreate(BaseModel):
    """Request model for search session tracking"""
    session_id: str = Field(..., description="Unique session ID")
    user_id: Optional[str] = Field(default=None, description="User ID (optional)")
    query: str = Field(..., description="Search query")
    mode: str = Field(default="hybrid", description="Search mode (semantic/vector/hybrid)")
    results_shown: int = Field(default=10, ge=1, le=100, description="Number of results displayed")
    ranking_model_id: str = Field(..., description="Ranking model used")
    ab_variant: ABTestVariant = Field(default=ABTestVariant.CONTROL, description="A/B variant")


class SearchSession(SearchSessionCreate):
    """Response model for search session"""
    id: str
    created_at: datetime
    ended_at: Optional[datetime] = None
    feedback_count: int = Field(default=0, description="User feedback collected")
    clicks: int = Field(default=0, description="Results clicked")
    dwell_times: List[float] = Field(default_factory=list, description="Dwell times by result")


class RankingComparisonRequest(BaseModel):
    """Request to compare ranking models"""
    baseline_model_id: str = Field(..., description="Baseline model for comparison")
    candidate_model_id: str = Field(..., description="Candidate model to test")
    days: int = Field(default=7, ge=1, le=90, description="Days of data to compare")


class RankingComparisonResult(BaseModel):
    """Comparison results between two ranking models"""
    baseline_model_id: str
    candidate_model_id: str
    metrics: Dict[str, Dict[str, float]] = Field(description="Metrics for each model")
    statistical_significance: float = Field(ge=0, le=1, description="P-value for significance")
    recommendation: str = Field(description="Recommendation (better/worse/inconclusive)")


# ============================================================================
# SQLAlchemy ORM Models
# ============================================================================

class RankingFeedbackORM(Base):
    """Persistent storage for user feedback on search results"""
    __tablename__ = "ranking_feedback"

    id = mapped_column(String(50), primary_key=True, default=lambda: __import__('uuid').uuid4().hex)
    query = mapped_column(String(500), nullable=False)
    result_id = mapped_column(String(255), nullable=False, index=True)
    feedback_type = mapped_column(String(50), nullable=False, index=True)
    score = mapped_column(Float, nullable=True)  # Rating score 0-5
    dwell_time_seconds = mapped_column(Integer, nullable=True)
    session_id = mapped_column(String(50), nullable=True, index=True)
    user_id = mapped_column(String(50), nullable=True, index=True)
    extra_metadata = mapped_column(JSON, nullable=True)
    created_at = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    enabled = mapped_column(Integer, default=1, index=True)  # Soft delete

    __table_args__ = (
        Index('ix_ranking_feedback_query_result', 'query', 'result_id'),
        Index('ix_ranking_feedback_session_time', 'session_id', 'created_at'),
        Index('ix_ranking_feedback_user_time', 'user_id', 'created_at'),
    )

    def to_pydantic(self) -> RankingFeedback:
        """Convert ORM to Pydantic model"""
        return RankingFeedback(
            id=self.id,
            query=self.query,
            result_id=self.result_id,
            feedback_type=FeedbackType(self.feedback_type),
            score=self.score,
            dwell_time_seconds=self.dwell_time_seconds,
            session_id=self.session_id,
            user_id=self.user_id,
            extra_metadata=self.extra_metadata,
            created_at=self.created_at,
            enabled=bool(self.enabled),
        )


class RankingParameterORM(Base):
    """Stores ranking model parameters and configurations"""
    __tablename__ = "ranking_parameters"

    id = mapped_column(String(50), primary_key=True, default=lambda: __import__('uuid').uuid4().hex)
    model_name = mapped_column(String(255), nullable=False, unique=True, index=True)
    semantic_weight = mapped_column(Float, default=0.33)
    vector_weight = mapped_column(Float, default=0.33)
    graph_weight = mapped_column(Float, default=0.33)
    feedback_boost = mapped_column(Float, default=0.1)
    fresh_boost = mapped_column(Float, default=0.05)
    popularity_weight = mapped_column(Float, default=0.2)
    ab_test_variant = mapped_column(String(50), default=ABTestVariant.CONTROL.value, index=True)
    enabled = mapped_column(Integer, default=1, index=True)
    extra_metadata = mapped_column(JSON, nullable=True)
    created_at = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    usage_count = mapped_column(Integer, default=0)

    __table_args__ = (
        Index('ix_ranking_parameters_enabled', 'enabled'),
        Index('ix_ranking_parameters_variant', 'ab_test_variant'),
    )

    def to_pydantic(self) -> RankingParameter:
        """Convert ORM to Pydantic model"""
        return RankingParameter(
            id=self.id,
            model_name=self.model_name,
            semantic_weight=self.semantic_weight,
            vector_weight=self.vector_weight,
            graph_weight=self.graph_weight,
            feedback_boost=self.feedback_boost,
            fresh_boost=self.fresh_boost,
            popularity_weight=self.popularity_weight,
            ab_test_variant=ABTestVariant(self.ab_test_variant),
            enabled=bool(self.enabled),
            extra_metadata=self.extra_metadata,
            created_at=self.created_at,
            updated_at=self.updated_at,
            usage_count=self.usage_count,
        )


class RankingAnalyticsORM(Base):
    """Stores ranking performance metrics over time"""
    __tablename__ = "ranking_analytics"

    id = mapped_column(String(50), primary_key=True, default=lambda: __import__('uuid').uuid4().hex)
    model_id = mapped_column(String(50), nullable=False, index=True)
    metric_type = mapped_column(String(50), nullable=False, index=True)
    metric_value = mapped_column(Float, nullable=False)
    query_count = mapped_column(Integer, default=1)
    feedback_count = mapped_column(Integer, default=0)
    time_period = mapped_column(String(20), default="daily", index=True)
    extra_metadata = mapped_column(JSON, nullable=True)
    measured_at = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

    __table_args__ = (
        Index('ix_ranking_analytics_model_metric', 'model_id', 'metric_type'),
        Index('ix_ranking_analytics_model_time', 'model_id', 'measured_at'),
    )

    def to_pydantic(self) -> RankingAnalytics:
        """Convert ORM to Pydantic model"""
        return RankingAnalytics(
            id=self.id,
            model_id=self.model_id,
            metric_type=RankingMetricType(self.metric_type),
            metric_value=self.metric_value,
            query_count=self.query_count,
            feedback_count=self.feedback_count,
            measured_at=self.measured_at,
            time_period=self.time_period,
            extra_metadata=self.extra_metadata,
        )


class SearchSessionORM(Base):
    """Tracks search sessions for analytics and feedback correlation"""
    __tablename__ = "search_sessions"

    id = mapped_column(String(50), primary_key=True, default=lambda: __import__('uuid').uuid4().hex)
    session_id = mapped_column(String(50), nullable=False, unique=True, index=True)
    user_id = mapped_column(String(50), nullable=True, index=True)
    query = mapped_column(String(500), nullable=False)
    mode = mapped_column(String(50), default="hybrid")
    results_shown = mapped_column(Integer, default=10)
    ranking_model_id = mapped_column(String(50), nullable=False, index=True)
    ab_variant = mapped_column(String(50), default=ABTestVariant.CONTROL.value, index=True)
    feedback_count = mapped_column(Integer, default=0)
    clicks = mapped_column(Integer, default=0)
    dwell_times = mapped_column(JSON, nullable=True)  # List of dwell times per result
    created_at = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    ended_at = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index('ix_search_sessions_user_time', 'user_id', 'created_at'),
        Index('ix_search_sessions_model_time', 'ranking_model_id', 'created_at'),
    )

    def to_pydantic(self) -> SearchSession:
        """Convert ORM to Pydantic model"""
        return SearchSession(
            id=self.id,
            session_id=self.session_id,
            user_id=self.user_id,
            query=self.query,
            mode=self.mode,
            results_shown=self.results_shown,
            ranking_model_id=self.ranking_model_id,
            ab_variant=ABTestVariant(self.ab_variant),
            created_at=self.created_at,
            ended_at=self.ended_at,
            feedback_count=self.feedback_count,
            clicks=self.clicks,
            dwell_times=self.dwell_times or [],
        )
