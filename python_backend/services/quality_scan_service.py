"""
Quality Scan Service

Orchestrates data quality scanning and reporting.
- Scan tables for quality metrics
- Calculate completeness, uniqueness, validity, freshness, consistency
- Generate quality reports
-Track quality trends over time
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func, text as sql_text

from models.quality_models import DataQualityScanReport, DataQualityIssue, FieldQualityMetric

logger = logging.getLogger(__name__)


class QualityMetrics:
    """Container for quality metric calculations"""

    def __init__(self):
        self.completeness: float = 0.0  # % non-null
        self.uniqueness: float = 0.0  # % unique
        self.validity: float = 0.0  # % matching validation rules
        self.consistency: float = 0.0  # % consistent with standards
        self.accuracy: float = 0.0  # % accurate vs reference
        self.timeliness: float = 0.0  # freshness score (0-100)
        self.issues: List[Dict[str, Any]] = []

    def to_dict(self) -> Dict[str, float]:
        return {
            "completeness": self.completeness,
            "uniqueness": self.uniqueness,
            "validity": self.validity,
            "consistency": self.consistency,
            "accuracy": self.accuracy,
            "timeliness": self.timeliness
        }

    def overall_score(self) -> float:
        """Calculate weighted overall quality score (0-100)"""
        weights = {
            "completeness": 0.25,
            "uniqueness": 0.15,
            "validity": 0.25,
            "consistency": 0.15,
            "accuracy": 0.15,
            "timeliness": 0.05
        }
        return sum(
            getattr(self, metric) * weight
            for metric, weight in weights.items()
        )


class QualityScanService:
    """Service for running quality scans and generating reports"""

    def __init__(self, db: Session):
        self.db = db

    async def scan_table(
        self,
        table_name: str,
        field_list: Optional[List[str]] = None,
        sample_size: int = 10000
    ) -> Optional[DataQualityScanReport]:
        """
        Scan a table and generate quality report.

        Args:
            table_name: SQL table to scan
            field_list: Specific fields to scan (None = all)
            sample_size: Number of records to sample

        Returns:
            DataQualityScanReport with metrics and issues
        """
        try:
            logger.info("Starting quality scan: table=%s, sample_size=%d", table_name, sample_size)

            # Get table metadata
            table_info = await self._get_table_info(table_name, field_list)
            if not table_info:
                logger.warning("Could not get table info: %s", table_name)
                return None

            fields, total_row_count = table_info

            # Calculate metrics for each field
            field_metrics: Dict[str, FieldQualityMetric] = {}
            overall_metrics = QualityMetrics()

            for field in fields:
                metrics = await self._analyze_field(table_name, field, sample_size)
                field_metrics[field] = metrics

            # Aggregate field metrics to overall metrics
            overall_metrics = self._aggregate_metrics(field_metrics)

            # Create quality report
            report = DataQualityScanReport(
                scanned_table=table_name,
                total_records=total_row_count,
                sampled_records=min(sample_size, total_row_count),
                scanned_fields=len(field_metrics),
                completeness=overall_metrics.completeness,
                uniqueness=overall_metrics.uniqueness,
                validity=overall_metrics.validity,
                consistency=overall_metrics.consistency,
                accuracy=overall_metrics.accuracy,
                timeliness=overall_metrics.timeliness,
                overall_score=overall_metrics.overall_score(),
                field_metrics=[
                    {
                        "field_name": field,
                        "completeness": metrics.get("completeness", 0),
                        "uniqueness": metrics.get("uniqueness", 0),
                        "validity": metrics.get("validity", 0)
                    }
                    for field, metrics in field_metrics.items()
                ],
                issues_found=len(overall_metrics.issues),
                issues=overall_metrics.issues,
                scanned_at=datetime.now(timezone.utc)
            )

            # Persist report
            self.db.add(report)
            self.db.commit()

            logger.info(
                "Quality scan completed: table=%s, score=%.1f, issues=%d",
                table_name, report.overall_score, report.issues_found
            )
            return report

        except Exception as e:
            logger.error("Error scanning table %s: %s", table_name, e)
            self.db.rollback()
            return None

    async def _get_table_info(
        self,
        table_name: str,
        field_list: Optional[List[str]] = None
    ) -> Optional[Tuple[List[str], int]]:
        """Get table column names and row count"""

        try:
            # Get row count
            count_query = f"SELECT COUNT(*) FROM {table_name}"
            total_rows = self.db.execute(sql_text(count_query)).scalar() or 0

            # Get column names
            info_query = f"SELECT column_name FROM information_schema.columns WHERE table_name = :table"
            columns = [
                row[0] for row in self.db.execute(
                    sql_text(info_query), {"table": table_name}
                ).fetchall()
            ]

            # Filter to requested fields
            if field_list:
                columns = [c for c in columns if c in field_list]

            return columns, total_rows

        except Exception as e:
            logger.error("Error getting table info for %s: %s", table_name, e)
            return None

    async def _analyze_field(
        self,
        table_name: str,
        field_name: str,
        sample_size: int
    ) -> Dict[str, float]:
        """Analyze a single field for quality metrics"""

        try:
            # Sample data
            sample_query = f"SELECT {field_name} FROM {table_name} LIMIT :limit"
            values = [
                row[0] for row in self.db.execute(
                    sql_text(sample_query), {"limit": sample_size}
                ).fetchall()
            ]

            if not values:
                return {
                    "completeness": 0.0,
                    "uniqueness": 0.0,
                    "validity": 0.0
                }

            # Calculate metrics
            non_null_count = sum(1 for v in values if v is not None)
            unique_count = len(set(str(v) for v in values if v is not None))

            completeness = (non_null_count / len(values)) * 100 if values else 0
            uniqueness = (unique_count / non_null_count) * 100 if non_null_count > 0 else 0

            # Simple validity check (non-empty for text fields)
            valid_count = sum(
                1 for v in values
                if v is not None and str(v).strip() != ""
            )
            validity = (valid_count / len(values)) * 100 if values else 0

            return {
                "completeness": round(completeness, 2),
                "uniqueness": round(uniqueness, 2),
                "validity": round(validity, 2)
            }

        except Exception as e:
            logger.error("Error analyzing field %s.%s: %s", table_name, field_name, e)
            return {
                "completeness": 0.0,
                "uniqueness": 0.0,
                "validity": 0.0
            }

    def _aggregate_metrics(self, field_metrics: Dict[str, Dict[str, float]]) -> QualityMetrics:
        """Aggregate field-level metrics to table-level metrics"""

        metrics = QualityMetrics()

        if not field_metrics:
            return metrics

        # Average field metrics
        metric_names = ["completeness", "uniqueness", "validity"]
        for metric_name in metric_names:
            values = [
                m.get(metric_name, 0)
                for m in field_metrics.values()
            ]
            avg_value = sum(values) / len(values) if values else 0
            setattr(metrics, metric_name, round(avg_value, 2))

        # Identify issues
        for field_name, field_metrics_dict in field_metrics.items():
            completeness = field_metrics_dict.get("completeness", 100)
            uniqueness = field_metrics_dict.get("uniqueness", 100)
            validity = field_metrics_dict.get("validity", 100)

            if completeness < 95:
                metrics.issues.append({
                    "field": field_name,
                    "type": "completeness",
                    "severity": "warning" if completeness > 80 else "critical",
                    "message": f"Field {field_name} has {completeness:.1f}% completeness"
                })

            if uniqueness < 95 and uniqueness < 100:
                metrics.issues.append({
                    "field": field_name,
                    "type": "uniqueness",
                    "severity": "info",
                    "message": f"Field {field_name} has duplicates ({uniqueness:.1f}% unique)"
                })

            if validity < 95:
                metrics.issues.append({
                    "field": field_name,
                    "type": "validity",
                    "severity": "warning",
                    "message": f"Field {field_name} has {validity:.1f}% valid values"
                })

        return metrics

    async def get_scan_history(
        self,
        table_name: str,
        limit: int = 10
    ) -> List[DataQualityScanReport]:
        """Get recent quality scans for a table"""

        try:
            reports = self.db.query(DataQualityScanReport).filter(
                DataQualityScanReport.scanned_table == table_name
            ).order_by(
                DataQualityScanReport.scanned_at.desc()
            ).limit(limit).all()

            return reports

        except Exception as e:
            logger.error("Error fetching scan history: %s", e)
            return []

    async def compare_scans(
        self,
        table_name: str,
        limit: int = 2
    ) -> Optional[Dict[str, Any]]:
        """Compare recent scans to identify trends"""

        try:
            scans = await self.get_scan_history(table_name, limit)
            if len(scans) < 2:
                return None

            latest = scans[0]
            previous = scans[1]

            return {
                "table_name": table_name,
                "latest_scan": latest.scanned_at,
                "previous_scan": previous.scanned_at,
                "completeness_change": latest.completeness - previous.completeness,
                "uniqueness_change": latest.uniqueness - previous.uniqueness,
                "overall_score_change": latest.overall_score - previous.overall_score,
                "trend": "improving" if (latest.overall_score - previous.overall_score) > 0 else "declining"
            }

        except Exception as e:
            logger.error("Error comparing scans: %s", e)
            return None

    async def get_quality_issues(
        self,
        table_name: str,
        severity: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get quality issues from latest scan"""

        try:
            report = self.db.query(DataQualityScanReport).filter(
                DataQualityScanReport.scanned_table == table_name
            ).order_by(
                DataQualityScanReport.scanned_at.desc()
            ).first()

            if not report or not report.issues:
                return []

            issues = report.issues
            if severity:
                issues = [i for i in issues if i.get("severity") == severity]

            return issues[:limit]

        except Exception as e:
            logger.error("Error getting quality issues: %s", e)
            return []
