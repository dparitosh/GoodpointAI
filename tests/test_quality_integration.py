"""Integration tests for data quality scanning workflow.

Tests the full quality scan pipeline:
1. Data discovery agent quality checks (pandas-based or SODA)
2. Backend quality scan endpoint (filesystem + Postgres tables)
3. Report persistence and retrieval
"""
import json
import tempfile
from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient

# These tests are designed to run against the full backend stack
# For isolated unit tests, see test_main.py in agent_services/data_discovery


@pytest.fixture
def sample_csv_file():
    """Create a temporary CSV file for testing."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, newline='') as f:
        f.write("part_number,name,weight_kg,supplier_id\n")
        f.write("PN-001,Bolt M8,0.012,SUP-001\n")
        f.write("PN-002,Nut M8,0.008,SUP-001\n")
        f.write("PN-003,Washer,0.003,\n")  # Missing supplier_id
        f.write("PN-004,Screw,0.009,SUP-002\n")
        f.write("PN-001,Bolt M8,0.012,SUP-001\n")  # Duplicate row
        path = Path(f.name)
    yield path
    path.unlink(missing_ok=True)


@pytest.fixture
def sample_json_file():
    """Create a temporary JSON file for testing."""
    data = [
        {"id": 1, "name": "Item 1", "value": 100},
        {"id": 2, "name": "Item 2", "value": 200},
        {"id": 3, "name": None, "value": 300},  # Missing name
    ]
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(data, f)
        path = Path(f.name)
    yield path
    path.unlink(missing_ok=True)


def test_quality_checks_csv_file(sample_csv_file):
    """Test quality checks on CSV file via pandas."""
    from agent_services.data_discovery.main import _run_quality_checks
    
    df = pd.read_csv(str(sample_csv_file))
    checks = _run_quality_checks(df)
    
    assert isinstance(checks, list)
    assert len(checks) >= 3  # At minimum: row_count, missing_count, duplicate_count
    
    # Verify row count check
    row_check = [c for c in checks if "row_count" in c["name"]][0]
    assert row_check["outcome"] == "pass"
    assert row_check["value"] == 5
    
    # Verify duplicate detection
    dup_check = [c for c in checks if "duplicate_count" in c["name"]][0]
    assert dup_check["outcome"] == "fail"
    assert dup_check["value"] == 1  # One duplicate row


def test_quality_checks_json_file(sample_json_file):
    """Test quality checks on JSON file via pandas."""
    from agent_services.data_discovery.main import _run_quality_checks
    
    df = pd.read_json(str(sample_json_file))
    checks = _run_quality_checks(df)
    
    assert isinstance(checks, list)
    
    # Verify missing data detection
    missing_check = [c for c in checks if "missing_count" in c["name"]][0]
    assert missing_check["value"] == 1  # One missing value in 'name' column


def test_profile_file_with_quality_checks(sample_csv_file):
    """Test full file profiling including quality checks."""
    from agent_services.data_discovery.main import _profile_file
    
    file_meta = {
        "path": str(sample_csv_file),
        "file_type": "csv",
        "size_bytes": sample_csv_file.stat().st_size,
    }
    
    profile = _profile_file(file_meta)
    
    # Verify profile structure
    assert profile["parse_ok"] is True
    assert profile["row_count"] == 5
    assert profile["column_count"] == 4
    assert len(profile["columns"]) == 4
    
    # Verify quality checks are included
    assert "quality_checks" in profile
    checks = profile["quality_checks"]
    assert isinstance(checks, list)
    assert len(checks) >= 3
    
    # Verify column profiling
    supplier_col = [c for c in profile["columns"] if c["name"] == "supplier_id"][0]
    assert supplier_col["null_count"] == 1
    assert supplier_col["null_rate"] > 0


def test_quality_report_structure():
    """Test that quality check results match expected report structure."""
    from agent_services.data_discovery.main import _run_quality_checks
    
    df = pd.DataFrame({
        "a": [1, 2, 3, 4, 5],
        "b": ["x", "y", "z", "w", "v"]
    })
    
    checks = _run_quality_checks(df)
    
    # Verify each check has required fields
    for check in checks:
        assert "name" in check
        assert "outcome" in check
        assert "fail" in check
        assert "pass" in check
        assert "engine" in check
        assert check["outcome"] in ["pass", "fail"]
        assert isinstance(check["fail"], bool)
        assert isinstance(check["pass"], bool)


def test_quality_checks_empty_dataframe():
    """Test quality checks handle empty DataFrames gracefully."""
    from agent_services.data_discovery.main import _run_quality_checks
    
    df = pd.DataFrame()
    checks = _run_quality_checks(df)
    
    assert isinstance(checks, list)
    # Empty df should fail row_count check
    row_check = [c for c in checks if "row_count" in c["name"]][0]
    assert row_check["outcome"] == "fail"


def test_quality_checks_all_nulls():
    """Test quality checks detect high null rates."""
    from agent_services.data_discovery.main import _run_quality_checks
    
    df = pd.DataFrame({
        "a": [None, None, None, None, None],
        "b": [None, None, None, None, None]
    })
    
    checks = _run_quality_checks(df)
    
    # Should detect high missing count
    missing_check = [c for c in checks if "missing_count" in c["name"]][0]
    assert missing_check["outcome"] == "fail"
    assert missing_check["value"] == 10  # 5 rows * 2 cols = 10 nulls
    
    # Should detect high max null rate
    null_rate_check = [c for c in checks if "max_null_rate" in c["name"]][0]
    assert null_rate_check["outcome"] == "fail"
    assert null_rate_check["value"] == 100.0  # 100% null rate


# Backend integration tests (require running backend + database)
@pytest.mark.integration
def test_backend_quality_scan_endpoint(sample_csv_file):
    """Test backend quality scan endpoint for filesystem sources."""
    from python_backend.main import app
    client = TestClient(app)
    
    # Note: This requires the backend to be running and DATABASE_URL configured
    response = client.post(
        "/api/analytics/quality/scan/test_table",
        json={
            "data_source": str(sample_csv_file),
            "rules": []
        }
    )
    
    # May return 503 if Postgres not configured in test environment
    if response.status_code == 503:
        pytest.skip("Postgres not configured")
    
    assert response.status_code == 200
    data = response.json()
    assert "scan_id" in data
    assert data["status"] == "completed"


@pytest.mark.integration
def test_backend_quality_report_retrieval():
    """Test retrieving quality reports from backend."""
    from python_backend.main import app
    client = TestClient(app)
    
    response = client.get("/api/analytics/quality/reports")
    
    if response.status_code == 503:
        pytest.skip("Postgres not configured")
    
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])
