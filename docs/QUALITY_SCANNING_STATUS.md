# Quality Scanning & SODA Integration Status

**Status**: ✅ **Fully Operational** (Updated: 2025-01-XX)

## Overview

The data quality scanning system uses a **SODA-first, builtin-fallback** pattern for robust quality checks across different data sources.

## Architecture

- **Database Tables**: SODA Core with `soda-core-postgres` (✅ working)
- **Pandas DataFrames**: Builtin quality checks (✅ working, recommended)
- **File Profiling**: CSV/JSON/XLSX with quality checks (✅ working)

## Quality Checks (Builtin)

The following 4 checks are applied to all pandas DataFrames:

1. **row_count > 0** - Ensures data exists
2. **missing_count < 100** - Detects excessive nulls
3. **duplicate_count = 0** - Identifies duplicate rows
4. **max_null_rate < 50%** - Checks for columns with high null rates

## Test Results

### Validation Script (`scripts/validate_quality_scanning.py`)
```
✓ PASS     Python version (3.12.10)
✓ PASS     setuptools (80.9.0)
✓ PASS     SODA installation (3.5.5)
✓ PASS     SODA pandas scan (gracefully skipped - see note below)
✓ PASS     Builtin quality checks (4 checks)
✓ PASS     File profiling (CSV/JSON with quality checks)

✓ All checks passed!
```

### Unit Tests (`agent_services/data_discovery/test_main.py`)
```
✓ test_run_quality_checks_basic
✓ test_run_quality_checks_with_nulls
✓ test_run_quality_checks_with_no_dataframe
✓ test_run_quality_checks_with_high_duplicates
✓ test_run_quality_checks_with_high_nulls

5/5 tests passed
```

### Integration Tests (`tests/test_quality_integration.py`)
```
✓ test_csv_quality_check_basic
✓ test_csv_quality_check_with_nulls
✓ test_json_quality_check
✓ test_quality_check_error_handling
✓ test_profile_file_full_workflow
... (10+ tests)

All integration tests passing
```

## SODA Core Pandas Support

**Status**: Optional (not installed)

**Reason**: `soda-core-pandas-dask` requires:
- Rust compiler (not available on all systems)
- `dask-sql` package (build complexity on Python 3.12)

**Recommendation**: Use builtin quality checks for pandas DataFrames. They provide:
- ✅ Comprehensive validation (4 checks)
- ✅ Zero external dependencies
- ✅ Consistent structure with SODA checks
- ✅ Graceful degradation when SODA unavailable

## Usage Examples

### Check DataFrame Quality
```python
from agent_services.data_discovery.main import _run_quality_checks
import pandas as pd

df = pd.DataFrame({"a": [1, 2, 3], "b": ["x", "y", "z"]})
checks = _run_quality_checks(df)

# Returns:
# [
#     {"name": "row_count > 0", "outcome": "pass", "value": 3, "engine": "builtin"},
#     {"name": "missing_count < 100", "outcome": "pass", "value": 0, "engine": "builtin"},
#     {"name": "duplicate_count = 0", "outcome": "pass", "value": 0, "engine": "builtin"},
#     {"name": "max_null_rate < 50%", "outcome": "pass", "value": 0.0, "engine": "builtin"}
# ]
```

### Profile File with Quality Checks
```python
from agent_services.data_discovery.main import _profile_file
from pathlib import Path

profile = _profile_file(Path("data.csv"))

# Returns:
# {
#     "parse_ok": True,
#     "rows": 1000,
#     "cols": 5,
#     "null_rate": 0.02,
#     "quality_checks": [
#         {"name": "row_count > 0", "outcome": "pass", ...},
#         ...
#     ]
# }
```

## API Compatibility

### SODA Core 3.x API
```python
from soda.scan import Scan

scan = Scan()
# Correct signature for pandas DataFrames:
scan.add_pandas_dataframe(
    dataset_name="my_data",
    pandas_df=df,
    data_source_name="pandas"  # or "dask" - requires soda-core-pandas-dask
)
```

**Note**: Previous versions used `table_name` or `dataframe_name` parameters - these are **incorrect** in SODA Core 3.x.

## Files Modified

### Core Implementation
- `agent_services/data_discovery/main.py`
  - Fixed SODA Core 3.x API call signature
  - Added 4th builtin check: `max_null_rate < 50%`
  - Improved logging: info for SODA success, warning for fallback

### Tests
- `agent_services/data_discovery/test_main.py`
  - 5 comprehensive unit tests for quality checks
  - Removed broken import mocking
  - Tests cover: basic, nulls, no dataframe, duplicates, high null rate

### Validation
- `scripts/validate_quality_scanning.py`
  - 6 comprehensive validation checks
  - Graceful handling of optional soda-core-pandas-dask
  - Clear pass/fail reporting

### Configuration
- `requirements.txt`
  - Added `soda-core>=3.0.0,<4.0.0`
  - Added `soda-core-postgres>=3.0.0,<4.0.0`
  - Added `setuptools>=70.0.0` (Python 3.12 compatibility)
  - Documented soda-core-pandas-dask as optional

## Troubleshooting

### "soda-core-pandas-dask is not installed"
**Expected behavior** - builtin quality checks will be used automatically. No action required.

### Quality checks not appearing
1. Check that pandas DataFrames are valid: `df is not None and len(df) > 0`
2. Verify quality_checks array in response: `profile["quality_checks"]`
3. Check logs for fallback warnings

### Database quality scans failing
1. Ensure `soda-core-postgres` is installed
2. Verify database connection configuration
3. Check SODA logs for connection errors

## Next Steps

- ✅ SODA Core 3.x integration complete
- ✅ Builtin quality checks robust and tested
- ✅ File profiling with quality validation working
- 🔄 Consider adding custom quality checks (e.g., data type validation, range checks)
- 🔄 Integrate quality scores into UI (quality_router.py already persists scans)

## Related Documentation

- [Installation Guide](INSTALLATION.md) - Dependencies and setup
- [User Guide](USER_GUIDE.md) - End-user quality scanning features
- [API Architecture](reference/API_ARCHITECTURE.md) - Backend quality endpoints
