"""
Test streaming quality scan endpoints

Run with:
    python -m pytest python_backend/tests/test_streaming_quality.py -v
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from core.streaming_validation import (
    SSEEventType,
    StreamingEvent,
    StreamingProgress,
    StreamingValidator,
    StreamingResponseGenerator,
    ScanMetricsCollector
)
from services.streaming_quality_service import (
    StreamingQualityScan,
    StreamingDataProfiler,
    create_streaming_quality_scan,
    create_streaming_data_profile
)


class TestSSEEventType:
    """Test SSE event type enumeration"""
    
    def test_all_event_types_present(self):
        """Verify all required event types exist"""
        assert SSEEventType.START.value == "start"
        assert SSEEventType.PROGRESS.value == "progress"
        assert SSEEventType.RESULT.value == "result"
        assert SSEEventType.METRICS.value == "metrics"
        assert SSEEventType.WARNING.value == "warning"
        assert SSEEventType.ERROR.value == "error"
        assert SSEEventType.COMPLETE.value == "complete"
        assert SSEEventType.CANCELLED.value == "cancelled"
    
    def test_event_type_string_conversion(self):
        """Verify event types convert to strings"""
        assert str(SSEEventType.PROGRESS) == "SSEEventType.PROGRESS"
        assert SSEEventType.PROGRESS.value == "progress"


class TestStreamingEvent:
    """Test StreamingEvent creation and formatting"""
    
    def test_event_creation(self):
        """Test creating a streaming event"""
        event = StreamingEvent(
            event_type=SSEEventType.PROGRESS,
            data={"processed": 100, "total": 1000},
            event_id="1"
        )
        assert event.event_type == SSEEventType.PROGRESS
        assert event.data["processed"] == 100
        assert event.event_id == "1"
    
    def test_sse_format(self):
        """Test SSE wire format"""
        event = StreamingEvent(
            event_type=SSEEventType.PROGRESS,
            data={"progress_percentage": 50.0},
            event_id="1"
        )
        sse_str = event.to_sse_format()
        
        # Should contain SSE format elements
        assert "id: 1" in sse_str
        assert "event: progress" in sse_str
        assert "data:" in sse_str
        assert "\n\n" in sse_str  # Blank line at end
    
    def test_event_dict_representation(self):
        """Test dictionary representation"""
        event = StreamingEvent(
            event_type=SSEEventType.RESULT,
            data={"issue": "null_value"}
        )
        event_dict = event.to_dict()
        
        assert event_dict["event"] == "result"
        assert event_dict["data"]["issue"] == "null_value"
        assert "timestamp" in event_dict


class TestStreamingProgress:
    """Test progress tracking"""
    
    def test_progress_initialization(self):
        """Test progress object creation"""
        progress = StreamingProgress(total_items=1000)
        
        assert progress.total_items == 1000
        assert progress.processed_items == 0
        assert progress.progress_percentage == 0.0
    
    def test_progress_percentage(self):
        """Test progress calculation"""
        progress = StreamingProgress(total_items=100)
        
        assert progress.progress_percentage == 0.0
        
        progress.increment_processed(50)
        assert progress.progress_percentage == 50.0
        
        progress.increment_processed(50)
        assert progress.progress_percentage == 100.0
    
    def test_progress_to_dict(self):
        """Test progress serialization"""
        progress = StreamingProgress(total_items=100)
        progress.increment_processed(25)
        
        data = progress.to_dict()
        assert data["processed"] == 25
        assert data["total"] == 100
        assert data["progress_percentage"] == 25.0
        assert "elapsed_seconds" in data
        assert "items_per_second" in data


class TestScanMetricsCollector:
    """Test metrics collection"""
    
    def test_metrics_initialization(self):
        """Test metrics collector creation"""
        collector = ScanMetricsCollector()
        
        assert collector.metrics["total_rows_scanned"] == 0
        assert collector.metrics["total_issues_found"] == 0
        assert collector.metrics["quality_score"] == 0.0
    
    def test_record_row_scanned(self):
        """Test recording scanned rows"""
        collector = ScanMetricsCollector()
        
        collector.record_row_scanned()
        collector.record_row_scanned()
        
        assert collector.metrics["total_rows_scanned"] == 2
    
    def test_record_issue(self):
        """Test recording issues"""
        collector = ScanMetricsCollector()
        
        collector.record_issue("null_value", "high")
        collector.record_issue("duplicate", "medium")
        
        assert collector.metrics["total_issues_found"] == 2
        assert collector.metrics["issue_type_counts"]["null_value"] == 1
        assert collector.metrics["issue_type_counts"]["duplicate"] == 1
        assert collector.metrics["issue_severity_distribution"]["high"] == 1
        assert collector.metrics["issue_severity_distribution"]["medium"] == 1
    
    def test_quality_score_calculation(self):
        """Test quality score calculation"""
        collector = ScanMetricsCollector()
        
        # No issues = 100% quality
        score = collector.calculate_quality_score(total_rows=100)
        assert score == 100.0
        
        # Add issues
        collector.record_issue("null_value", "high")
        collector.record_issue("duplicate", "medium")
        
        # 2 issues in 100 rows = 98% quality (2% deduction)
        score = collector.calculate_quality_score(total_rows=100)
        assert 97.0 <= score <= 99.0


class TestStreamingQualityScan:
    """Test quality scan validator"""
    
    def test_scan_initialization(self):
        """Test scan creation"""
        scan = StreamingQualityScan(
            scan_id="test-scan",
            table_name="my_table",
            total_rows=1000
        )
        
        assert scan.operation_id == "test-scan"
        assert scan.table_name == "my_table"
        assert scan.progress.total_items == 1000
    
    @pytest.mark.asyncio
    async def test_scan_streaming(self):
        """Test streaming quality scan"""
        scan = StreamingQualityScan(
            scan_id="test-scan",
            table_name="test_table",
            total_rows=100
        )
        
        events = []
        async for event in scan.validate_streaming():
            events.append(event)
        
        # Should have START, multiple PROGRESS, METRICS, COMPLETE
        assert len(events) > 0
        assert events[0].event_type == SSEEventType.START
        assert events[-1].event_type == SSEEventType.COMPLETE
        
        # Should have progress events
        progress_events = [e for e in events if e.event_type == SSEEventType.PROGRESS]
        assert len(progress_events) > 0


class TestStreamingDataProfiler:
    """Test data profiler validator"""
    
    def test_profiler_initialization(self):
        """Test profiler creation"""
        profiler = StreamingDataProfiler(
            profile_id="test-profile",
            table_name="my_table"
        )
        
        assert profiler.operation_id == "test-profile"
        assert profiler.table_name == "my_table"
    
    @pytest.mark.asyncio
    async def test_profiler_streaming(self):
        """Test streaming data profiling"""
        profiler = StreamingDataProfiler(
            profile_id="test-profile",
            table_name="test_table"
        )
        
        events = []
        async for event in profiler.validate_streaming():
            events.append(event)
        
        # Should have START, RESULT events for columns, COMPLETE
        assert len(events) > 0
        assert events[0].event_type == SSEEventType.START
        assert events[-1].event_type == SSEEventType.COMPLETE
        
        # Should have result events (one per column)
        result_events = [e for e in events if e.event_type == SSEEventType.RESULT]
        assert len(result_events) > 0


class TestFactoryFunctions:
    """Test factory function creation"""
    
    def test_create_quality_scan(self):
        """Test quality scan factory"""
        scan = create_streaming_quality_scan("my_table", 1000)
        
        assert isinstance(scan, StreamingQualityScan)
        assert scan.table_name == "my_table"
        assert scan.progress.total_items == 1000
        assert len(scan.operation_id) > 0  # UUID generated
    
    def test_create_data_profiler(self):
        """Test data profiler factory"""
        profiler = create_streaming_data_profile("my_table", 5000)
        
        assert isinstance(profiler, StreamingDataProfiler)
        assert profiler.table_name == "my_table"
        assert profiler.progress.total_items == 5000
        assert len(profiler.operation_id) > 0  # UUID generated


class TestStreamingResponseGenerator:
    """Test response generator"""
    
    @pytest.mark.asyncio
    async def test_generator_output(self):
        """Test SSE generation"""
        scan = StreamingQualityScan(
            scan_id="test",
            table_name="test",
            total_rows=10
        )
        
        generator = StreamingResponseGenerator(scan)
        
        events = []
        async for sse_str in generator.generate():
            events.append(sse_str)
        
        # Should get SSE-formatted strings
        assert len(events) > 0
        assert all(isinstance(e, str) for e in events)
        assert all("event:" in e for e in events)  # SSE format


# Integration tests
@pytest.mark.asyncio
async def test_full_streaming_flow():
    """Test complete streaming workflow"""
    scan = create_streaming_quality_scan("test_table", 50)
    generator = StreamingResponseGenerator(scan)
    
    event_types = []
    async for sse_str in generator.generate():
        # Parse event type from SSE format
        for line in sse_str.split("\n"):
            if line.startswith("event:"):
                event_types.append(line.split("event:")[1].strip())
    
    # Verify event sequence
    assert "start" in event_types
    assert "complete" in event_types
    assert "progress" in event_types


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])
