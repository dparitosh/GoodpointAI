import sys
import os

print(f"Python: {sys.version}")

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
    import docx
    results["python-docx"] = "OK"
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
        results["pytesseract"] = f"OK (Binary found)"
    except pytesseract.TesseractNotFoundError:
        results["pytesseract"] = "PARTIAL (Import OK, but tesseract.exe not in PATH)"
    except Exception as e:
        results["pytesseract"] = f"PARTIAL (Import OK, Binary check failed: {e})"
except ImportError as e:
    results["pytesseract"] = f"FAIL: {e}"

print("-" * 40)
print("LIBRARY STATUS REPORT")
print("-" * 40)
for lib, status in results.items():
    print(f"{lib:<15}: {status}")
print("-" * 40)
