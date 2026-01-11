"""
Tests for Analytics Storage Service
"""
import pytest
from services.analytics_storage_service import (
    AnalyticsStorageService
)


@pytest.fixture
def analytics_service():
    """Create analytics service instance for testing"""
    return AnalyticsStorageService()


@pytest.mark.asyncio
async def test_record_upload_metric(analytics_service):
    """Test recording upload metrics"""
    result = await analytics_service.record_upload_metric(
        file_name="test_file.xml",
        file_size_mb=100.0,
        upload_duration_sec=30.5,
        status="success",
        user="test@example.com",
        source="gateway"
    )
    
    assert result["status"] == "success"
    assert "data" in result
    assert result["data"]["file_name"] == "test_file.xml"
    assert result["data"]["file_size_mb"] == 100.0


@pytest.mark.asyncio
async def test_record_service_health(analytics_service):
    """Test recording service health metrics"""
    result = await analytics_service.record_service_health(
        service_name="test_service",
        status="healthy",
        cpu_percent=45.5,
        memory_percent=62.3,
        response_time_ms=120.0,
        error_rate=0.5
    )
    
    assert result["status"] == "success"
    assert result["data"]["service_name"] == "test_service"
    assert result["data"]["cpu_percent"] == 45.5


@pytest.mark.asyncio
async def test_record_migration_quality(analytics_service):
    """Test recording migration quality metrics"""
    result = await analytics_service.record_migration_quality(
        session_id="test-session-123",
        quality_score=98.5,
        rows_migrated=10000,
        rows_failed=50,
        schema_drift_issues=2
    )
    
    assert result["status"] == "success"
    assert result["data"]["session_id"] == "test-session-123"
    assert result["data"]["quality_score"] == 98.5
    assert result["data"]["success_rate"] > 99.0


@pytest.mark.asyncio
async def test_get_upload_metrics(analytics_service):
    """Test retrieving upload metrics"""
    # Add some test data
    await analytics_service.record_upload_metric(
        file_name="test1.xml",
        file_size_mb=50.0,
        upload_duration_sec=10.0,
        status="success",
        user="test@example.com",
        source="gateway"
    )
    
    await analytics_service.record_upload_metric(
        file_name="test2.xml",
        file_size_mb=75.0,
        upload_duration_sec=15.0,
        status="failed",
        user="test@example.com",
        source="gateway"
    )
    
    result = await analytics_service.get_upload_metrics(limit=100)
    
    assert result["status"] == "success"
    assert "data" in result
    assert "metrics" in result["data"]
    assert "aggregates" in result["data"]
    
    aggregates = result["data"]["aggregates"]
    assert "total_uploads" in aggregates
    assert "successful_uploads" in aggregates
    assert "failed_uploads" in aggregates
    assert "success_rate" in aggregates


@pytest.mark.asyncio
async def test_get_service_health_metrics(analytics_service):
    """Test retrieving service health metrics"""
    # Add some test data
    await analytics_service.record_service_health(
        service_name="test_svc",
        status="healthy",
        cpu_percent=50.0,
        memory_percent=60.0,
        response_time_ms=100.0,
        error_rate=0.1
    )
    
    result = await analytics_service.get_service_health_metrics(
        service_name="test_svc",
        limit=50
    )
    
    assert result["status"] == "success"
    assert "data" in result
    assert "metrics" in result["data"]
    assert "summary" in result["data"]


@pytest.mark.asyncio
async def test_get_migration_quality_metrics(analytics_service):
    """Test retrieving migration quality metrics"""
    # Add some test data
    session_id = "test-session-456"
    await analytics_service.record_migration_quality(
        session_id=session_id,
        quality_score=95.0,
        rows_migrated=5000,
        rows_failed=25,
        schema_drift_issues=1
    )
    
    result = await analytics_service.get_migration_quality_metrics(
        session_id=session_id,
        limit=50
    )
    
    assert result["status"] == "success"
    assert "data" in result
    assert "metrics" in result["data"]
    assert "aggregates" in result["data"]
    
    # Check that we got the specific session
    metrics = result["data"]["metrics"]
    assert any(m["session_id"] == session_id for m in metrics)


@pytest.mark.asyncio
async def test_upload_metrics_aggregation(analytics_service):
    """Test upload metrics aggregation calculations"""
    # Clear existing data
    analytics_service.metrics_store["upload_metrics"] = []
    
    # Add test data with known values
    for i in range(10):
        await analytics_service.record_upload_metric(
            file_name=f"test_{i}.xml",
            file_size_mb=100.0,
            upload_duration_sec=10.0,
            status="success" if i < 8 else "failed",
            user="test@example.com",
            source="gateway"
        )
    
    result = await analytics_service.get_upload_metrics(limit=100)
    aggregates = result["data"]["aggregates"]
    
    assert aggregates["total_uploads"] == 10
    assert aggregates["successful_uploads"] == 8
    assert aggregates["failed_uploads"] == 2
    assert aggregates["success_rate"] == 80.0
    assert aggregates["total_size_mb"] == 1000.0
    assert aggregates["avg_duration_sec"] == 10.0


@pytest.mark.asyncio
async def test_service_health_limit(analytics_service):
    """Test that service health records are limited"""
    # Add many records for a service
    for i in range(150):
        await analytics_service.record_service_health(
            service_name="test_limited",
            status="healthy",
            cpu_percent=50.0,
            memory_percent=60.0,
            response_time_ms=100.0,
            error_rate=0.1
        )
    
    # Check that only 100 records are kept
    health_records = [
        m for m in analytics_service.metrics_store["service_health"]
        if m["service_name"] == "test_limited"
    ]
    assert len(health_records) == 100


@pytest.mark.asyncio
async def test_migration_quality_aggregates(analytics_service):
    """Test migration quality aggregates calculation"""
    # Clear existing data
    analytics_service.metrics_store["migration_quality"] = []
    
    # Add test data
    await analytics_service.record_migration_quality(
        session_id="session1",
        quality_score=95.0,
        rows_migrated=1000,
        rows_failed=50,
        schema_drift_issues=2
    )
    
    await analytics_service.record_migration_quality(
        session_id="session2",
        quality_score=98.0,
        rows_migrated=2000,
        rows_failed=20,
        schema_drift_issues=1
    )
    
    result = await analytics_service.get_migration_quality_metrics(limit=100)
    aggregates = result["data"]["aggregates"]
    
    assert aggregates["total_rows_migrated"] == 3000
    assert aggregates["total_rows_failed"] == 70
    assert aggregates["total_schema_drift_issues"] == 3
    assert aggregates["avg_quality_score"] == 96.5
