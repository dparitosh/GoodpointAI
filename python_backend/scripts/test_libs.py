import io
import sys

# PowerShell 5 / cp1252 compatibility
if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "buffer"):
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

print(f"Python: {sys.version}")

_PIP_INSTALL = {
    "PyMuPDF":       "pip install PyMuPDF",
    "openpyxl":      "pip install openpyxl",
    "python-docx":   "pip install python-docx",
    "opencv-python": "pip install opencv-python-headless",
    "pytesseract":   "pip install pytesseract  (also install tesseract-ocr binary: https://github.com/tesseract-ocr/tesseract)",
    "sqlalchemy":    "pip install sqlalchemy==2.0.35",
    "psycopg":       "pip install psycopg[binary]==3.2.3",
    "fastapi":       "pip install fastapi==0.115.0",
    "uvicorn":       "pip install uvicorn[standard]==0.32.0",
}

results = {}

# Test PyMuPDF (fitz)
try:
    import fitz
    results["PyMuPDF"] = f"OK (Version: {fitz.__doc__})"
except ImportError as e:
    results["PyMuPDF"] = f"FAIL: {e}"
except Exception as e:
    results["PyMuPDF"] = f"FAIL (Runtime): {e}"

# Test openpyxl
try:
    import openpyxl
    wb = openpyxl.Workbook()
    results["openpyxl"] = f"OK (Version: {openpyxl.__version__})"
except ImportError as e:
    results["openpyxl"] = f"FAIL: {e}"
except Exception as e:
    results["openpyxl"] = f"FAIL (Runtime): {e}"

# Test python-docx
try:
    import importlib.util as _iutil
    if _iutil.find_spec("docx") is not None:
        import docx as _docx  # noqa: F401
        results["python-docx"] = "OK"
    else:
        results["python-docx"] = "FAIL: not installed"
except ImportError as e:
    results["python-docx"] = f"FAIL: {e}"
except Exception as e:
    results["python-docx"] = f"FAIL (Runtime): {e}"

# Test OpenCV
try:
    import cv2
    results["opencv-python"] = f"OK (Version: {cv2.__version__})"
except ImportError as e:
    results["opencv-python"] = f"FAIL: {e}"
except Exception as e:
    results["opencv-python"] = f"FAIL (Runtime): {e}"

# Test pytesseract
try:
    import pytesseract
    # Check if tesseract is in path or configured
    # This might fail on windows if not in PATH, but import should work
    try:
        pytesseract.get_tesseract_version()
        results["pytesseract"] = "OK (Binary found)"
    except pytesseract.TesseractNotFoundError:
        results["pytesseract"] = "PARTIAL (Import OK, but tesseract.exe not in PATH)"
    except Exception as e:
        results["pytesseract"] = f"PARTIAL (Import OK, Binary check failed: {e})"
except ImportError as e:
    results["pytesseract"] = f"FAIL: {e}"

# ---- Core backend libraries ----
for _lib, _mod in [("sqlalchemy", "sqlalchemy"), ("psycopg", "psycopg"), ("fastapi", "fastapi"), ("uvicorn", "uvicorn")]:
    try:
        __import__(_mod)
        results[_lib] = "OK"
    except ImportError as _e:
        results[_lib] = f"FAIL: {_e}"

print("-" * 40)
print("LIBRARY STATUS REPORT")
print("-" * 40)
failures = 0
for lib, status in results.items():
    ok = status.startswith("OK") or status.startswith("PARTIAL")
    tag = "[OK]    " if status.startswith("OK") else ("[WARN]  " if status.startswith("PARTIAL") else "[FAIL]  ")
    print(f"{tag}{lib:<20}: {status}")
    if status.startswith("FAIL"):
        failures += 1
        hint = _PIP_INSTALL.get(lib)
        if hint:
            print(f"         Fix: {hint}")
print("-" * 40)
if failures:
    print(f"{failures} library/libraries failed. Install missing packages with the Fix commands above.")
    sys.exit(1)
else:
    print("All libraries OK.")
    sys.exit(0)
