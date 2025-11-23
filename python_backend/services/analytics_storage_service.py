"""
Analytics Storage Service
Handles metrics ingestion, storage, and retrieval for governance dashboards.
"""
import logging
import json
from datetime import datetime
from typing import Dict, List, Optional, Any
from enum import Enum

logger = logging.getLogger(__name__)


class MetricType(str, Enum):
    """Types of metrics tracked"""
    UPLOAD = "upload"
    PROCESSING = "processing"
    SERVICE_HEALTH = "service_health"
    MIGRATION_QUALITY = "migration_quality"
    ERROR = "error"


class AnalyticsStorageService:
    """
    Service for collecting and storing analytics metrics.
    In production, this would interface with PostgreSQL analytics schema.
    For now, using in-memory storage with proper structure.
    """
    
    def __init__(self):
        self.metrics_store: Dict[str, List[Dict]] = {
            "upload_metrics": [],
            "service_health": [],
            "migration_quality": [],
            "processing_metrics": [],
            "error_logs": []
        }
        self._initialize_sample_data()
    
    def _initialize_sample_data(self):
        """Initialize with sample data for demonstration"""
        # Sample upload metrics
        for i in range(10):
            self.metrics_store["upload_metrics"].append({
                "id": f"upload_{i}",
                "timestamp": datetime.utcnow().isoformat(),
                "file_name": f"plm_data_{i}.xml",
                "file_size_mb": 50 + (i * 10),
                "upload_duration_sec": 5 + (i * 2),
                "status": "success" if i % 5 != 0 else "failed",
                "user": "user@example.com",
                "source": "gateway"
            })
        
        # Sample service health metrics
        services = ["backend_gateway", "plm_xml_service", "migration_engine", "neo4j"]
        for service in services:
            self.metrics_store["service_health"].append({
                "service_name": service,
                "timestamp": datetime.utcnow().isoformat(),
                "status": "healthy",
                "cpu_percent": 45.5,
                "memory_percent": 62.3,
                "response_time_ms": 120,
                "error_rate": 0.5
            })
    
    async def record_upload_metric(
        self,
        file_name: str,
        file_size_mb: float,
        upload_duration_sec: float,
        status: str,
        user: str,
        source: str = "gateway"
    ) -> Dict[str, Any]:
        """Record upload metrics"""
        metric = {
            "id": f"upload_{len(self.metrics_store['upload_metrics'])}",
            "timestamp": datetime.utcnow().isoformat(),
            "file_name": file_name,
            "file_size_mb": file_size_mb,
            "upload_duration_sec": upload_duration_sec,
            "status": status,
            "user": user,
            "source": source
        }
        
        self.metrics_store["upload_metrics"].append(metric)
        logger.info(f"Recorded upload metric: {file_name} - {status}")
        
        return {
            "status": "success",
            "message": "Upload metric recorded",
            "data": metric
        }
    
    async def record_service_health(
        self,
        service_name: str,
        status: str,
        cpu_percent: float,
        memory_percent: float,
        response_time_ms: float,
        error_rate: float
    ) -> Dict[str, Any]:
        """Record service health metrics"""
        metric = {
            "service_name": service_name,
            "timestamp": datetime.utcnow().isoformat(),
            "status": status,
            "cpu_percent": cpu_percent,
            "memory_percent": memory_percent,
            "response_time_ms": response_time_ms,
            "error_rate": error_rate
        }
        
        # Keep only last 100 health records per service
        self.metrics_store["service_health"] = [
            m for m in self.metrics_store["service_health"]
            if m.get("service_name") != service_name
        ][-99:] + [metric]
        
        logger.debug(f"Recorded health metric for {service_name}")
        
        return {
            "status": "success",
            "message": "Health metric recorded",
            "data": metric
        }
    
    async def record_migration_quality(
        self,
        session_id: str,
        quality_score: float,
        rows_migrated: int,
        rows_failed: int,
        schema_drift_issues: int
    ) -> Dict[str, Any]:
        """Record migration quality metrics"""
        metric = {
            "session_id": session_id,
            "timestamp": datetime.utcnow().isoformat(),
            "quality_score": quality_score,
            "rows_migrated": rows_migrated,
            "rows_failed": rows_failed,
            "schema_drift_issues": schema_drift_issues,
            "success_rate": (rows_migrated / (rows_migrated + rows_failed) * 100) if (rows_migrated + rows_failed) > 0 else 0
        }
        
        self.metrics_store["migration_quality"].append(metric)
        logger.info(f"Recorded migration quality for session {session_id}")
        
        return {
            "status": "success",
            "message": "Migration quality metric recorded",
            "data": metric
        }
    
    async def get_upload_metrics(
        self,
        limit: int = 100,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """Retrieve upload metrics"""
        metrics = self.metrics_store["upload_metrics"]
        
        # Filter by date range if provided
        if start_date:
            metrics = [m for m in metrics if m["timestamp"] >= start_date]
        if end_date:
            metrics = [m for m in metrics if m["timestamp"] <= end_date]
        
        # Apply limit
        metrics = metrics[-limit:]
        
        # Calculate aggregates
        total_uploads = len(metrics)
        successful_uploads = len([m for m in metrics if m["status"] == "success"])
        failed_uploads = len([m for m in metrics if m["status"] == "failed"])
        total_size_mb = sum(m["file_size_mb"] for m in metrics)
        avg_duration_sec = sum(m["upload_duration_sec"] for m in metrics) / total_uploads if total_uploads > 0 else 0
        
        return {
            "status": "success",
            "message": "Upload metrics retrieved",
            "data": {
                "metrics": metrics,
                "aggregates": {
                    "total_uploads": total_uploads,
                    "successful_uploads": successful_uploads,
                    "failed_uploads": failed_uploads,
                    "success_rate": (successful_uploads / total_uploads * 100) if total_uploads > 0 else 0,
                    "total_size_mb": total_size_mb,
                    "avg_duration_sec": avg_duration_sec
                }
            },
            "timestamp": datetime.utcnow().isoformat()
        }
    
    async def get_service_health_metrics(
        self,
        service_name: Optional[str] = None,
        limit: int = 50
    ) -> Dict[str, Any]:
        """Retrieve service health metrics"""
        metrics = self.metrics_store["service_health"]
        
        # Filter by service if specified
        if service_name:
            metrics = [m for m in metrics if m.get("service_name") == service_name]
        
        # Apply limit
        metrics = metrics[-limit:]
        
        # Group by service for aggregates
        services_summary = {}
        for metric in metrics:
            svc = metric["service_name"]
            if svc not in services_summary:
                services_summary[svc] = {
                    "service_name": svc,
                    "current_status": metric["status"],
                    "avg_cpu_percent": 0,
                    "avg_memory_percent": 0,
                    "avg_response_time_ms": 0,
                    "count": 0
                }
            
            services_summary[svc]["avg_cpu_percent"] += metric["cpu_percent"]
            services_summary[svc]["avg_memory_percent"] += metric["memory_percent"]
            services_summary[svc]["avg_response_time_ms"] += metric["response_time_ms"]
            services_summary[svc]["count"] += 1
        
        # Calculate averages
        for svc in services_summary.values():
            if svc["count"] > 0:
                svc["avg_cpu_percent"] /= svc["count"]
                svc["avg_memory_percent"] /= svc["count"]
                svc["avg_response_time_ms"] /= svc["count"]
        
        return {
            "status": "success",
            "message": "Service health metrics retrieved",
            "data": {
                "metrics": metrics,
                "summary": list(services_summary.values())
            },
            "timestamp": datetime.utcnow().isoformat()
        }
    
    async def get_migration_quality_metrics(
        self,
        session_id: Optional[str] = None,
        limit: int = 50
    ) -> Dict[str, Any]:
        """Retrieve migration quality metrics"""
        metrics = self.metrics_store["migration_quality"]
        
        # Filter by session if specified
        if session_id:
            metrics = [m for m in metrics if m.get("session_id") == session_id]
        
        # Apply limit
        metrics = metrics[-limit:]
        
        # Calculate aggregates
        if metrics:
            avg_quality = sum(m["quality_score"] for m in metrics) / len(metrics)
            total_rows = sum(m["rows_migrated"] for m in metrics)
            total_failed = sum(m["rows_failed"] for m in metrics)
            total_drift_issues = sum(m["schema_drift_issues"] for m in metrics)
        else:
            avg_quality = 0
            total_rows = 0
            total_failed = 0
            total_drift_issues = 0
        
        return {
            "status": "success",
            "message": "Migration quality metrics retrieved",
            "data": {
                "metrics": metrics,
                "aggregates": {
                    "avg_quality_score": avg_quality,
                    "total_rows_migrated": total_rows,
                    "total_rows_failed": total_failed,
                    "total_schema_drift_issues": total_drift_issues,
                    "overall_success_rate": (total_rows / (total_rows + total_failed) * 100) if (total_rows + total_failed) > 0 else 0
                }
            },
            "timestamp": datetime.utcnow().isoformat()
        }


# Global instance
analytics_service = AnalyticsStorageService()
