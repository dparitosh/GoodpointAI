"""Unit tests for data_discovery agent quality checks."""
import pandas as pd
import pytest

from agent_services.data_discovery.main import _run_quality_checks


def test_run_quality_checks_basic():
    """Test builtin quality checks with valid data."""
    df = pd.DataFrame({"a": [1, 2, 3], "b": ["x", "y", "z"]})

    checks = _run_quality_checks(df)

    assert isinstance(checks, list)
    assert len(checks) >= 4  # At minimum: row_count, missing_count, duplicate_count, max_null_rate
    
    # Verify all checks have required fields
    for check in checks:
        assert "name" in check
        assert "outcome" in check
        assert "pass" in check
        assert "fail" in check
        assert "engine" in check


def test_run_quality_checks_with_nulls():
    """Test quality checks correctly detect nulls."""
    df = pd.DataFrame({"a": [1, None, 3], "b": [None, "x", "y"]})

    checks = _run_quality_checks(df)

    assert isinstance(checks, list)
    assert len(checks) >= 4
    
    # Check for missing_count check
    missing_check = next((c for c in checks if "missing_count" in c["name"]), None)
    assert missing_check is not None
    assert missing_check["value"] == 2  # 2 null values total


def test_run_quality_checks_with_no_dataframe():
    """Test quality checks with None dataframe."""
    checks = _run_quality_checks(None)
    
    assert isinstance(checks, list)
    assert len(checks) == 1
    assert "error" in checks[0]
    assert checks[0]["error"] == "No dataframe to evaluate"


def test_run_quality_checks_with_high_duplicates():
    """Test quality checks detect high duplicate counts."""
    df = pd.DataFrame({
        "a": [1, 1, 1, 2, 2],
        "b": ["x", "x", "x", "y", "y"]
    })
    
    checks = _run_quality_checks(df)
    
    duplicate_check = [c for c in checks if "duplicate_count" in c["name"]][0]
    assert duplicate_check["outcome"] == "fail"
    assert duplicate_check["value"] == 3  # 3 duplicate rows


def test_run_quality_checks_with_high_nulls():
    """Test quality checks detect high null rates."""
    df = pd.DataFrame({
        "a": [1, None, None, None, None],
        "b": [None, "x", None, None, None]
    })
    
    checks = _run_quality_checks(df)
    
    max_null_check = [c for c in checks if "max_null_rate" in c["name"]][0]
    assert max_null_check["outcome"] == "fail"  # 80% null rate in column 'a'
    assert max_null_check["value"] >= 50.0
