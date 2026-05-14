"""
Server-Sent Events (SSE) Streaming Framework for Real-Time Data Processing

Enables streaming of large dataset validation results, progress updates, and 
real-time feedback without timeout limitations.

Features:
- Chunked result streaming via SSE
- Real-time progress updates
- Error recovery within streams
- Resource-efficient processing
- Client reconnection support
"""

import asyncio
import json
import logging
from typing import AsyncGenerator, Dict, Any, Optional, List, Callable
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class SSEEventType(str, Enum):
    """Server-Sent Event types"""
    START = "start"                # Scan/validation started
    PROGRESS = "progress"          # Progress update (rows processed, %)
    RESULT = "result"              # Individual validation result
    METRICS = "metrics"            # Aggregated metrics update
    WARNING = "warning"            # Non-fatal warning
    ERROR = "error"                # Error occurred (may continue)
    COMPLETE = "complete"          # Scan completed successfully
    CANCELLED = "cancelled"        # Scan was cancelled


class StreamingEvent:
    """Server-Sent Event with typed payload"""
    
    def __init__(
        self,
        event_type: SSEEventType,
        data: Dict[str, Any],
        event_id: Optional[str] = None,
        retry_ms: Optional[int] = None
    ):
        self.event_type = event_type
        self.data = data
        self.event_id = event_id
        self.retry_ms = retry_ms
        self.timestamp = datetime.utcnow()
    
    def to_sse_format(self) -> str:
        """Convert to SSE wire format"""
        lines = []
        
        if self.event_id:
            lines.append(f"id: {self.event_id}")
        
        lines.append(f"event: {self.event_type.value}")
        
        if self.retry_ms:
            lines.append(f"retry: {self.retry_ms}")
        
        # Serialize data as JSON
        json_data = json.dumps(self.data)
        lines.append(f"data: {json_data}")
        
        # SSE format: each field on its own line, blank line at end
        return "\n".join(lines) + "\n\n"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation"""
        return {
            "event": self.event_type.value,
            "data": self.data,
            "timestamp": self.timestamp.isoformat(),
            **({"id": self.event_id} if self.event_id else {})
        }


class StreamingProgress:
    """Track streaming operation progress"""
    
    def __init__(self, total_items: Optional[int] = None):
        self.total_items = total_items
        self.processed_items = 0
        self.failed_items = 0
        self.warnings = 0
        self.start_time = datetime.utcnow()
        self.last_update = self.start_time
    
    @property
    def progress_percentage(self) -> float:
        """Get progress as percentage (0-100)"""
        if self.total_items is None or self.total_items == 0:
            return 0.0
        return min(100.0, (self.processed_items / self.total_items) * 100)
    
    @property
    def elapsed_seconds(self) -> float:
        """Get elapsed time in seconds"""
        return (datetime.utcnow() - self.start_time).total_seconds()
    
    @property
    def items_per_second(self) -> float:
        """Get processing rate"""
        elapsed = self.elapsed_seconds
        if elapsed == 0:
            return 0.0
        return self.processed_items / elapsed
    
    @property
    def estimated_remaining_seconds(self) -> Optional[float]:
        """Estimate time remaining based on current rate"""
        if self.total_items is None or self.items_per_second == 0:
            return None
        remaining = self.total_items - self.processed_items
        return remaining / self.items_per_second
    
    def increment_processed(self, count: int = 1):
        """Record processed items"""
        self.processed_items += count
        self.last_update = datetime.utcnow()
    
    def increment_failed(self, count: int = 1):
        """Record failed items"""
        self.failed_items += count
    
    def increment_warnings(self, count: int = 1):
        """Record warnings"""
        self.warnings += count
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert progress to dictionary"""
        return {
            "processed": self.processed_items,
            "total": self.total_items,
            "failed": self.failed_items,
            "warnings": self.warnings,
            "progress_percentage": self.progress_percentage,
            "elapsed_seconds": self.elapsed_seconds,
            "items_per_second": round(self.items_per_second, 2),
            "estimated_remaining_seconds": (
                round(self.estimated_remaining_seconds, 1)
                if self.estimated_remaining_seconds else None
            )
        }


class StreamingValidator:
    """Base class for streaming validators"""
    
    def __init__(self, operation_id: str, total_items: Optional[int] = None):
        self.operation_id = operation_id
        self.progress = StreamingProgress(total_items)
        self.is_cancelled = False
        self.error: Optional[str] = None
    
    async def validate_streaming(
        self
    ) -> AsyncGenerator[StreamingEvent, None]:
        """
        Main streaming validation method
        Override in subclasses
        
        Yields: StreamingEvent for each result, progress update, and completion
        """
        raise NotImplementedError("Subclasses must implement validate_streaming()")
    
    async def cancel(self):
        """Cancel the streaming operation"""
        self.is_cancelled = True
        logger.info(f"Streaming operation {self.operation_id} cancelled")
    
    def emit_start(self, details: Dict[str, Any]) -> StreamingEvent:
        """Emit start event"""
        return StreamingEvent(
            event_type=SSEEventType.START,
            data={
                "operation_id": self.operation_id,
                "timestamp": datetime.utcnow().isoformat(),
                **details
            },
            event_id="1"
        )
    
    def emit_progress(self) -> StreamingEvent:
        """Emit progress event"""
        return StreamingEvent(
            event_type=SSEEventType.PROGRESS,
            data=self.progress.to_dict()
        )
    
    def emit_result(
        self,
        result: Dict[str, Any],
        event_id: Optional[str] = None
    ) -> StreamingEvent:
        """Emit validation result event"""
        return StreamingEvent(
            event_type=SSEEventType.RESULT,
            data=result,
            event_id=event_id
        )
    
    def emit_metrics(self, metrics: Dict[str, Any]) -> StreamingEvent:
        """Emit aggregated metrics event"""
        return StreamingEvent(
            event_type=SSEEventType.METRICS,
            data=metrics
        )
    
    def emit_warning(self, message: str, details: Optional[Dict] = None) -> StreamingEvent:
        """Emit warning event"""
        self.progress.increment_warnings()
        return StreamingEvent(
            event_type=SSEEventType.WARNING,
            data={
                "message": message,
                **(details or {})
            }
        )
    
    def emit_error(self, message: str, details: Optional[Dict] = None) -> StreamingEvent:
        """Emit error event"""
        self.error = message
        return StreamingEvent(
            event_type=SSEEventType.ERROR,
            data={
                "message": message,
                "operation_id": self.operation_id,
                **(details or {})
            }
        )
    
    def emit_complete(self, summary: Dict[str, Any]) -> StreamingEvent:
        """Emit completion event"""
        return StreamingEvent(
            event_type=SSEEventType.COMPLETE,
            data={
                "operation_id": self.operation_id,
                "timestamp": datetime.utcnow().isoformat(),
                **self.progress.to_dict(),
                **summary
            }
        )
    
    def emit_cancelled(self) -> StreamingEvent:
        """Emit cancellation event"""
        return StreamingEvent(
            event_type=SSEEventType.CANCELLED,
            data={
                "operation_id": self.operation_id,
                "timestamp": datetime.utcnow().isoformat(),
                "progress": self.progress.to_dict()
            }
        )


class StreamingResponseGenerator:
    """Generate SSE response stream from validator"""
    
    def __init__(
        self,
        validator: StreamingValidator,
        progress_update_interval: int = 100,
        heartbeat_interval: Optional[float] = 30.0
    ):
        self.validator = validator
        self.progress_update_interval = progress_update_interval
        self.heartbeat_interval = heartbeat_interval
        self.event_counter = 0
    
    async def generate(self) -> AsyncGenerator[str, None]:
        """
        Generate SSE stream from validator results
        
        Yields: SSE-formatted strings ready for response
        """
        try:
            # Stream from validator (validate_streaming is async generator)
            async for event in self.validator.validate_streaming():
                self.event_counter += 1
                yield event.to_sse_format()
                
                # Allow task switching for responsiveness
                await asyncio.sleep(0)
        
        except asyncio.CancelledError:
            logger.info(f"Streaming cancelled for {self.validator.operation_id}")
            event = self.emit_cancelled()
            yield event.to_sse_format()
        
        except Exception as e:
            logger.error(f"Streaming error: {str(e)}")
            event = self.validator.emit_error(str(e))
            yield event.to_sse_format()
    
    def emit_cancelled(self) -> StreamingEvent:
        """Emit cancellation event"""
        return StreamingEvent(
            event_type=SSEEventType.CANCELLED,
            data={
                "operation_id": self.validator.operation_id,
                "timestamp": datetime.utcnow().isoformat()
            }
        )


class ScanMetricsCollector:
    """Collect and aggregate metrics during streaming scan"""
    
    def __init__(self):
        self.metrics = {
            "total_rows_scanned": 0,
            "total_issues_found": 0,
            "issue_severity_distribution": {
                "critical": 0,
                "high": 0,
                "medium": 0,
                "low": 0,
                "info": 0
            },
            "issue_type_counts": {},
            "quality_score": 0.0,
            "data_completeness": 0.0,
            "data_accuracy": 0.0
        }
    
    def record_row_scanned(self):
        """Record a scanned row"""
        self.metrics["total_rows_scanned"] += 1
    
    def record_issue(
        self,
        issue_type: str,
        severity: str = "medium"
    ):
        """Record a found issue"""
        self.metrics["total_issues_found"] += 1
        
        # Track by severity
        if severity in self.metrics["issue_severity_distribution"]:
            self.metrics["issue_severity_distribution"][severity] += 1
        
        # Track by type
        if issue_type not in self.metrics["issue_type_counts"]:
            self.metrics["issue_type_counts"][issue_type] = 0
        self.metrics["issue_type_counts"][issue_type] += 1
    
    def calculate_quality_score(self, total_rows: int) -> float:
        """Calculate overall quality score (0-100)"""
        if total_rows == 0:
            return 100.0
        
        # Simple formula: deduct points based on issue count
        issue_ratio = self.metrics["total_issues_found"] / total_rows
        score = max(0.0, 100.0 - (issue_ratio * 100.0))
        self.metrics["quality_score"] = round(score, 1)
        return self.metrics["quality_score"]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert metrics to dictionary"""
        return self.metrics.copy()
