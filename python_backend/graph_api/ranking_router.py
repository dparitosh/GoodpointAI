"""
Ranking Router - API endpoints for search result ranking and feedback

Provides endpoints for:
- Recording user feedback on search results
- Retrieving ranking performance analytics
- Tuning ranking model parameters
- A/B testing different ranking strategies
"""

import logging
from typing import List, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from core.db_session import get_db
from models.ranking_models import (
    RankingFeedbackCreate, RankingFeedback,
    RankingParameterCreate, RankingParameter,
    RankingAnalyticsCreate, RankingAnalytics,
    RankingMetricType, ABTestVariant,
    SearchSession,
)
from services.ranking_service import (
    RankingFeedbackRepository, RankingParameterRepository,
    RankingAnalyticsRepository, SearchSessionRepository,
    RankingAnalyticsService,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ranking", tags=["ranking"])


# ============================================================================
# Feedback Endpoints
# ============================================================================

@router.post("/feedback", response_model=RankingFeedback)
async def record_feedback(request: RankingFeedbackCreate, db: Session = Depends(get_db)):
    """Record user feedback on search result.
    
    Feedback types:
    - click: User clicked on result
    - skip: User skipped result
    - rating: User rated result (1-5)
    - dwell_time: Time spent on result (seconds)
    - relevant: User marked as relevant
    - not_relevant: User marked as irrelevant
    """
    try:
        with RankingFeedbackRepository(db) as repo:
            return repo.create(request)
    except Exception as e:
        logger.error("Error recording feedback: %s", e)
        raise HTTPException(status_code=500, detail="Failed to record feedback") from e


@router.get("/feedback/{feedback_id}", response_model=RankingFeedback)
async def get_feedback(feedback_id: str, db: Session = Depends(get_db)):
    """Retrieve feedback by ID"""
    try:
        with RankingFeedbackRepository(db) as repo:
            feedback = repo.read(feedback_id)
        if not feedback:
            raise HTTPException(status_code=404, detail="Feedback not found")
        return feedback
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error retrieving feedback: %s", e)
        raise HTTPException(status_code=500, detail="Failed to retrieve feedback") from e


@router.get("/feedback/session/{session_id}", response_model=List[RankingFeedback])
async def get_session_feedback(
    session_id: str,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=500),
    db: Session = Depends(get_db)
):
    """Get all feedback for a search session"""
    try:
        with RankingFeedbackRepository(db) as repo:
            return repo.list_by_session(session_id, skip, limit)
    except Exception as e:
        logger.error("Error retrieving session feedback: %s", e)
        raise HTTPException(status_code=500, detail="Failed to retrieve session feedback") from e


@router.get("/feedback/query", response_model=List[RankingFeedback])
async def get_query_feedback(
    query: str,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=500),
    db: Session = Depends(get_db)
):
    """Get feedback for a specific query"""
    try:
        with RankingFeedbackRepository(db) as repo:
            return repo.list_by_query(query, skip, limit)
    except Exception as e:
        logger.error("Error retrieving query feedback: %s", e)
        raise HTTPException(status_code=500, detail="Failed to retrieve query feedback") from e


@router.get("/feedback/recent", response_model=List[RankingFeedback])
async def get_recent_feedback(
    days: int = Query(default=7, ge=1, le=90),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db)
):
    """Get recent feedback within specified days"""
    try:
        with RankingFeedbackRepository(db) as repo:
            return repo.list_recent(days, skip, limit)
    except Exception as e:
        logger.error("Error retrieving recent feedback: %s", e)
        raise HTTPException(status_code=500, detail="Failed to retrieve recent feedback") from e


# ============================================================================
# Ranking Parameter Endpoints
# ============================================================================

@router.post("/parameters", response_model=RankingParameter)
async def create_ranking_model(request: RankingParameterCreate, db: Session = Depends(get_db)):
    """Create new ranking model with parameters"""
    try:
        with RankingParameterRepository(db) as repo:
            return repo.create(request)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    except Exception as e:
        logger.error("Error creating ranking model: %s", e)
        raise HTTPException(status_code=500, detail="Failed to create ranking model") from e


@router.get("/parameters/{model_id}", response_model=RankingParameter)
async def get_ranking_parameters(model_id: str, db: Session = Depends(get_db)):
    """Get ranking model parameters by ID"""
    try:
        with RankingParameterRepository(db) as repo:
            params = repo.read(model_id)
        if not params:
            raise HTTPException(status_code=404, detail="Ranking model not found")
        return params
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error retrieving ranking parameters: %s", e)
        raise HTTPException(status_code=500, detail="Failed to retrieve ranking parameters") from e


@router.get("/parameters/name/{model_name}", response_model=RankingParameter)
async def get_ranking_parameters_by_name(model_name: str, db: Session = Depends(get_db)):
    """Get ranking model parameters by name"""
    try:
        with RankingParameterRepository(db) as repo:
            params = repo.read_by_name(model_name)
        if not params:
            raise HTTPException(status_code=404, detail="Ranking model not found")
        return params
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error retrieving ranking parameters: %s", e)
        raise HTTPException(status_code=500, detail="Failed to retrieve ranking parameters") from e


@router.get("/parameters", response_model=List[RankingParameter])
async def list_ranking_models(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=500),
    db: Session = Depends(get_db)
):
    """List active ranking models"""
    try:
        with RankingParameterRepository(db) as repo:
            return repo.list_enabled(skip, limit)
    except Exception as e:
        logger.error("Error listing ranking models: %s", e)
        raise HTTPException(status_code=500, detail="Failed to list ranking models") from e


@router.put("/parameters/{model_id}", response_model=RankingParameter)
async def update_ranking_parameters(
    model_id: str,
    request: RankingParameterCreate,
    db: Session = Depends(get_db)
):
    """Update ranking model parameters"""
    try:
        updates = request.dict(exclude_unset=True)
        with RankingParameterRepository(db) as repo:
            updated = repo.update(model_id, updates)
        if not updated:
            raise HTTPException(status_code=404, detail="Ranking model not found")
        return updated
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error updating ranking parameters: %s", e)
        raise HTTPException(status_code=500, detail="Failed to update ranking parameters") from e


@router.get("/ab-tests", response_model=dict)
async def list_ab_test_variants(db: Session = Depends(get_db)):
    """List all A/B test variants and their models"""
    try:
        result = {}
        with RankingParameterRepository(db) as repo:
            for variant in ABTestVariant:
                models = repo.list_by_variant(variant)
                result[variant.value] = [m.dict() for m in models]
        return result
    except Exception as e:
        logger.error("Error listing A/B test variants: %s", e)
        raise HTTPException(status_code=500, detail="Failed to list A/B test variants") from e


# ============================================================================
# Analytics Endpoints
# ============================================================================

@router.get("/analytics/{model_id}", response_model=dict)
async def get_ranking_analytics(
    model_id: str,
    days: int = Query(default=7, ge=1, le=90),
    db: Session = Depends(get_db)
):
    """Get ranking analytics for a model"""
    try:
        with RankingAnalyticsRepository(db) as repo:
            metrics_by_type = {}
            for metric_type in RankingMetricType:
                analytics = repo.list_by_model(model_id, metric_type, days)
                if analytics:
                    metrics_by_type[metric_type.value] = [a.dict() for a in analytics]

            if not metrics_by_type:
                raise HTTPException(status_code=404, detail="No analytics found for model")

            return {
                "model_id": model_id,
                "period_days": days,
                "metrics": metrics_by_type
            }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error retrieving ranking analytics: %s", e)
        raise HTTPException(status_code=500, detail="Failed to retrieve ranking analytics") from e


@router.get("/analytics/{model_id}/latest", response_model=dict)
async def get_latest_ranking_metrics(model_id: str, db: Session = Depends(get_db)):
    """Get latest metric values for a model"""
    try:
        with RankingAnalyticsRepository(db) as repo:
            metrics = repo.get_latest_metrics(model_id)
        if not metrics:
            raise HTTPException(status_code=404, detail="No metrics found for model")
        return {
            "model_id": model_id,
            "latest_metrics": metrics
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error retrieving latest metrics: %s", e)
        raise HTTPException(status_code=500, detail="Failed to retrieve latest metrics") from e


@router.post("/analytics/record", response_model=RankingAnalytics)
async def record_ranking_metric(request: RankingAnalyticsCreate, db: Session = Depends(get_db)):
    """Record ranking performance metric"""
    try:
        with RankingAnalyticsRepository(db) as repo:
            return repo.create(request)
    except Exception as e:
        logger.error("Error recording ranking metric: %s", e)
        raise HTTPException(status_code=500, detail="Failed to record ranking metric") from e


@router.get("/analytics/ctr", response_model=dict)
async def calculate_click_through_rate(
    days: int = Query(default=7, ge=1, le=90),
    db: Session = Depends(get_db)
):
    """Calculate overall click-through rate"""
    try:
        with RankingFeedbackRepository(db) as repo:
            ctr = RankingAnalyticsService.calculate_ctr(repo, days)
        return {
            "metric": "ctr",
            "value": ctr,
            "period_days": days
        }
    except Exception as e:
        logger.error("Error calculating CTR: %s", e)
        raise HTTPException(status_code=500, detail="Failed to calculate CTR") from e


@router.get("/analytics/ndcg", response_model=dict)
async def calculate_normalized_discounted_cumulative_gain(
    days: int = Query(default=7, ge=1, le=90),
    db: Session = Depends(get_db)
):
    """Calculate NDCG (ranking quality metric)"""
    try:
        with RankingFeedbackRepository(db) as repo:
            ndcg = RankingAnalyticsService.calculate_ndcg(repo, days)
        return {
            "metric": "ndcg",
            "value": ndcg,
            "period_days": days
        }
    except Exception as e:
        logger.error("Error calculating NDCG: %s", e)
        raise HTTPException(status_code=500, detail="Failed to calculate NDCG") from e


@router.get("/analytics/mrr", response_model=dict)
async def calculate_mean_reciprocal_rank(
    days: int = Query(default=7, ge=1, le=90),
    db: Session = Depends(get_db)
):
    """Calculate MRR (ranking effectiveness metric)"""
    try:
        with RankingFeedbackRepository(db) as repo:
            mrr = RankingAnalyticsService.calculate_mrr(repo, days)
        return {
            "metric": "mrr",
            "value": mrr,
            "period_days": days
        }
    except Exception as e:
        logger.error("Error calculating MRR: %s", e)
        raise HTTPException(status_code=500, detail="Failed to calculate MRR") from e


# ============================================================================
# Health Check
# ============================================================================

@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "module": "ranking",
        "timestamp": datetime.utcnow().isoformat(),
        "features": [
            "feedback recording",
            "ranking parameters",
            "analytics calculation",
            "A/B testing support"
        ]
    }
