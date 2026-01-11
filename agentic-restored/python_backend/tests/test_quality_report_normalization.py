from datetime import datetime, timezone

import pytest

from graph_api.quality_router import DataQualityReport, _normalize_quality_report_payload


def test_normalize_quality_report_payload_backfills_missing_dimension_scores():
    legacy_payload = {
        "table_name": "soda_test_table",
        "scan_id": "scan-123",
        "overall_score": 0.75,
        "issues": [],
        "recommendations": ["No recommendations."],
        "scan_date": datetime.now(timezone.utc),
        "row_count": 2,
        "column_count": 2,
        # Older payloads may include extra keys that are not part of the current response model.
        "rule_results": [],
        "summary": {"soda_exit_code": 3, "errors": [], "warnings": []},
    }

    normalized = _normalize_quality_report_payload(legacy_payload)

    assert normalized["completeness_score"] == pytest.approx(0.75)
    assert normalized["accuracy_score"] == pytest.approx(0.75)
    assert normalized["consistency_score"] == pytest.approx(0.75)
    assert normalized["validity_score"] == pytest.approx(0.75)

    # Should validate against the response model (this is what previously triggered a 500).
    DataQualityReport(**normalized)


def test_normalize_quality_report_payload_uses_fallback_overall_score_when_missing():
    legacy_payload = {
        "table_name": "soda_test_table",
        "scan_id": "scan-456",
        "issues": [],
        "recommendations": [],
        "scan_date": datetime.now(timezone.utc),
        "row_count": 0,
        "column_count": 0,
    }

    normalized = _normalize_quality_report_payload(legacy_payload, fallback_overall_score=0.5)

    assert normalized["overall_score"] == pytest.approx(0.5)
    assert normalized["validity_score"] == pytest.approx(0.5)
    DataQualityReport(**normalized)
