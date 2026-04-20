"""Validation script for SODA Core integration and quality scanning.

This script tests:
1. SODA Core installation and compatibility with Python 3.12
2. Data discovery agent quality checks (SODA vs builtin fallback)
3. Quality scan persistence and report generation
"""

import sys
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


def check_soda_installation():
    """Check if SODA Core is properly installed and functional."""
    logger.info("Checking SODA Core installation...")
    
    try:
        from soda.scan import Scan
        logger.info("✓ SODA Core installed successfully")
        return True
    except ImportError as e:
        logger.warning(f"✗ SODA Core not installed: {e}")
        return False
    except Exception as e:
        logger.error(f"✗ SODA Core import failed: {e}")
        return False


def test_soda_pandas_scan():
    """Test SODA Core scan against a pandas DataFrame (optional - requires soda-core-pandas-dask)."""
    logger.info("Testing SODA Core with pandas DataFrame...")
    
    try:
        import pandas as pd
        from soda.scan import Scan
        
        # Create test DataFrame
        df = pd.DataFrame({
            "id": [1, 2, 3, 4, 5],
            "name": ["A", "B", None, "D", "E"],
            "value": [10, 20, 30, 40, 50]
        })
        
        # Run SODA scan
        scan = Scan()
        # SODA Core 3.x API: add_pandas_dataframe(dataset_name, pandas_df, data_source_name='dask')
        # Note: Requires soda-core-pandas-dask (needs Rust compiler on Python 3.12)
        scan.add_pandas_dataframe(dataset_name="test_data", pandas_df=df, data_source_name="pandas")
        
        sodacl = """
checks for test_data:
  - row_count > 0
  - missing_count < 10
  - duplicate_count = 0
"""
        scan.add_sodacl_yaml_str(sodacl)
        exit_code = scan.execute()
        
        # Get results
        results = scan.get_scan_results() or {}
        checks = results.get("checks", [])
        
        logger.info(f"✓ SODA scan completed with exit code {exit_code}")
        logger.info(f"  - {len(checks)} checks executed")
        
        for check in checks:
            check_name = check.get("name", "unknown")
            outcome = check.get("outcome", "unknown")
            logger.info(f"  - {check_name}: {outcome}")
        
        return True
        
    except ImportError:
        logger.warning("✗ SODA Core not available (expected if not installed)")
        return False
    except Exception as e:
        err_msg = str(e)
        if "soda-core-pandas-dask is not installed" in err_msg or "dask_sql" in err_msg:
            logger.warning("⚠ SODA pandas scan skipped (soda-core-pandas-dask not installed)")
            logger.info("  Note: Requires Rust compiler on Python 3.12 - builtin checks recommended")
            return True  # Not a failure - optional feature
        logger.error(f"✗ SODA pandas scan failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_builtin_quality_checks():
    """Test builtin quality checks (pandas-based fallback)."""
    logger.info("Testing builtin quality checks...")
    
    try:
        import pandas as pd
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from agent_services.data_discovery.main import _run_quality_checks
        
        # Create test DataFrame with quality issues
        df = pd.DataFrame({
            "id": [1, 2, 3, 3, 4],  # Duplicate row
            "name": ["A", "B", None, "D", "E"],  # Missing value
            "value": [10, 20, 30, 40, None]  # Missing value
        })
        
        checks = _run_quality_checks(df)
        
        logger.info(f"✓ Builtin quality checks completed")
        logger.info(f"  - {len(checks)} checks executed")
        
        for check in checks:
            check_name = check["name"]
            outcome = check["outcome"]
            value = check.get("value", "N/A")
            engine = check.get("engine", "unknown")
            logger.info(f"  - {check_name}: {outcome} (value={value}, engine={engine})")
        
        return True
        
    except Exception as e:
        logger.error(f"✗ Builtin quality checks failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_data_discovery_profiling():
    """Test data discovery file profiling with quality checks."""
    logger.info("Testing data discovery file profiling...")
    
    try:
        import pandas as pd
        import tempfile
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from agent_services.data_discovery.main import _profile_file
        
        # Create temporary CSV file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, newline='') as f:
            f.write("part_number,name,weight_kg\n")
            f.write("PN-001,Bolt,0.012\n")
            f.write("PN-002,Nut,0.008\n")
            f.write("PN-003,Washer,\n")  # Missing weight
            csv_path = Path(f.name)
        
        try:
            file_meta = {
                "path": str(csv_path),
                "file_type": "csv",
                "size_bytes": csv_path.stat().st_size,
            }
            
            profile = _profile_file(file_meta)
            
            logger.info(f"✓ File profiling completed")
            logger.info(f"  - Parse OK: {profile['parse_ok']}")
            logger.info(f"  - Rows: {profile['row_count']}")
            logger.info(f"  - Columns: {profile['column_count']}")
            logger.info(f"  - Null rate: {profile.get('null_rate', 'N/A')}")
            
            if "quality_checks" in profile:
                checks = profile["quality_checks"]
                logger.info(f"  - Quality checks: {len(checks)}")
                for check in checks:
                    logger.info(f"    • {check['name']}: {check['outcome']}")
            
            return True
            
        finally:
            csv_path.unlink(missing_ok=True)
        
    except Exception as e:
        logger.error(f"✗ File profiling failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def check_python_version():
    """Check Python version compatibility."""
    logger.info(f"Python version: {sys.version}")
    
    version_info = sys.version_info
    if version_info.major == 3 and version_info.minor >= 11:
        logger.info(f"✓ Python {version_info.major}.{version_info.minor} is supported")
        return True
    else:
        logger.warning(f"⚠ Python {version_info.major}.{version_info.minor} may not be fully compatible")
        return False


def check_setuptools():
    """Check if setuptools is installed (provides distutils compatibility)."""
    logger.info("Checking setuptools installation...")
    
    try:
        import setuptools
        logger.info(f"✓ setuptools {setuptools.__version__} installed")
        return True
    except ImportError:
        logger.warning("✗ setuptools not installed (required for Python 3.12 + SODA)")
        return False


def main():
    """Run all validation checks."""
    print("=" * 70)
    print("SODA Core & Quality Scanning Validation")
    print("=" * 70)
    print()
    
    results = {}
    
    # Python version check
    results["Python version"] = check_python_version()
    print()
    
    # Setuptools check
    results["setuptools"] = check_setuptools()
    print()
    
    # SODA installation check
    results["SODA installation"] = check_soda_installation()
    print()
    
    # SODA pandas scan test (if SODA is installed)
    if results["SODA installation"]:
        results["SODA pandas scan"] = test_soda_pandas_scan()
        print()
    
    # Builtin quality checks test
    results["Builtin quality checks"] = test_builtin_quality_checks()
    print()
    
    # File profiling test
    results["File profiling"] = test_data_discovery_profiling()
    print()
    
    # Summary
    print("=" * 70)
    print("Summary")
    print("=" * 70)
    
    for test_name, passed in results.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status:<10} {test_name}")
    
    print()
    
    all_passed = all(results.values())
    if all_passed:
        print("✓ All checks passed!")
        return 0
    else:
        failed_count = sum(1 for v in results.values() if not v)
        print(f"⚠ {failed_count} check(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
