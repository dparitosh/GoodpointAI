#!/usr/bin/env python3
"""
Test script to verify WATCH_FOLDERS environment variable handling.

This tests the fix for: pydantic_settings.exceptions.SettingsError: 
error parsing value for field "watch_folders"

The issue occurred when WATCH_FOLDERS environment variable was unset or empty,
causing JSON decode errors instead of falling back to the default.
"""

import os
import sys
import json
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent.parent / "agentic-restored" / "python_backend"
sys.path.insert(0, str(backend_path))

def test_watch_folders():
    """Test various WATCH_FOLDERS configuration scenarios."""
    
    test_cases = [
        {
            "name": "Unset environment variable (should use default)",
            "env_value": None,
            "expected": ["./data/watch"],
            "should_pass": True
        },
        {
            "name": "Empty environment variable (should use default)",
            "env_value": "",
            "expected": ["./data/watch"],
            "should_pass": True
        },
        {
            "name": "JSON array format (recommended)",
            "env_value": '["./data/watch","./uploads"]',
            "expected": ["./data/watch", "./uploads"],
            "should_pass": True
        },
        {
            "name": "Semicolon-separated (Windows)",
            "env_value": "./data/watch;./uploads",
            "expected": ["./data/watch", "./uploads"],
            "should_pass": True
        },
        {
            "name": "Comma-separated (Unix)",
            "env_value": "./data/watch,./uploads",
            "expected": ["./data/watch", "./uploads"],
            "should_pass": True
        },
        {
            "name": "Single path",
            "env_value": "./data/watch",
            "expected": ["./data/watch"],
            "should_pass": True
        },
        {
            "name": "Whitespace around JSON",
            "env_value": '  ["./data/watch"]  ',
            "expected": ["./data/watch"],
            "should_pass": True
        },
    ]
    
    passed = 0
    failed = 0
    
    print("=" * 80)
    print("TESTING: WATCH_FOLDERS Environment Variable Handling")
    print("=" * 80)
    
    for i, test in enumerate(test_cases, 1):
        # Save original environment
        original_env = os.environ.get("WATCH_FOLDERS")
        
        try:
            # Set test environment
            if test["env_value"] is None:
                if "WATCH_FOLDERS" in os.environ:
                    del os.environ["WATCH_FOLDERS"]
            else:
                os.environ["WATCH_FOLDERS"] = test["env_value"]
            
            # Need to reload the module to pick up environment changes
            # For now, just test the field_validator directly
            from core.external_config import FileSystemConfig
            
            print(f"\n[Test {i}] {test['name']}")
            print(f"  Environment: WATCH_FOLDERS={repr(test['env_value'])}")
            
            try:
                config = FileSystemConfig()
                result = config.watch_folders
                
                if result == test["expected"]:
                    print(f"  ✓ PASS: Got expected result: {result}")
                    passed += 1
                else:
                    print(f"  ✗ FAIL: Expected {test['expected']}, got {result}")
                    failed += 1
                    
            except Exception as e:
                if test["should_pass"]:
                    print(f"  ✗ FAIL: Unexpected error: {e}")
                    failed += 1
                else:
                    print(f"  ✓ PASS: Got expected error: {type(e).__name__}")
                    passed += 1
        
        finally:
            # Restore original environment
            if original_env is None:
                if "WATCH_FOLDERS" in os.environ:
                    del os.environ["WATCH_FOLDERS"]
            else:
                os.environ["WATCH_FOLDERS"] = original_env
    
    print("\n" + "=" * 80)
    print(f"Results: {passed} passed, {failed} failed out of {len(test_cases)} tests")
    print("=" * 80)
    
    return failed == 0


if __name__ == "__main__":
    try:
        success = test_watch_folders()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
