# CSV Data Discovery Fix - Customer Environment

**Issue**: Data discovery failed for CSV files in customer environment  
**Date**: April 20, 2026

---

## 🔍 Root Cause Analysis

CSV discovery can fail due to:
1. **Backend not running** (port 8011)
2. **File path/permission issues**
3. **CSV encoding problems** (expects UTF-8)
4. **MCP server offline** (degraded mode)
5. **Data source misconfiguration**

---

## ✅ SOLUTION 1: Quick Fix (Backend + CSV Path)

### Step 1: Ensure Backend is Running

```powershell
# Check if backend is running
curl http://localhost:8011/health

# If not running, start it:
cd D:\Download\GoodpointAI\python_backend
$env:GRAPH_TRACE_LOAD_DOTENV='true'
python -m uvicorn main:app --host 0.0.0.0 --port 8011 --reload
```

**Expected health response**:
```json
{
  "status": "ok" or "degraded",
  "dependencies": {
    "postgres": {"ok": true},
    "neo4j": {"ok": true}
  }
}
```

---

### Step 2: Verify CSV File Accessibility

The backend expects CSV files in:
- `./data/csv/input/` (default)
- Or configured path in `.env`: `CSV_INPUT_PATH`

**Check configuration**:
```powershell
# View CSV input path
cd python_backend
Get-Content .env | Select-String "CSV_INPUT_PATH"
```

**Common issues**:
- ❌ File path has spaces or special characters
- ❌ File is outside allowed data directories
- ❌ File permissions don't allow read access
- ❌ File encoding is not UTF-8

**Fix CSV encoding (if needed)**:
```powershell
# Convert to UTF-8
Get-Content "old_file.csv" | Set-Content "new_file.csv" -Encoding UTF8
```

---

### Step 3: Test CSV Discovery Endpoint Directly

```powershell
# Test sample endpoint (replace SOURCE_ID)
curl "http://localhost:8011/api/data-sources/SOURCE_ID/sample?limit=50"
```

**Expected success response**:
```json
{
  "source_id": "...",
  "format": "csv",
  "row_count": 50,
  "sample_records": [...],
  "warnings": []
}
```

**Common error responses**:

| Status | Error | Fix |
|--------|-------|-----|
| 404 | Data source not found | Check source ID in database |
| 403 | Path outside allowed directories | Update `CSV_INPUT_PATH` or move file |
| 400 | file_path required | Configure connection properly |
| 500 | Failed to read file | Check file permissions/encoding |

---

## ✅ SOLUTION 2: Frontend - Data Discovery Page

### Common Frontend Errors

**Error 1: "Failed to fetch" / Network error**
- **Cause**: Backend not running
- **Fix**: Start backend (see Solution 1, Step 1)

**Error 2: "500 Server Error"**
- **Cause**: Backend error (file not found, encoding issue)
- **Fix**: Check backend logs in PowerShell window

**Error 3: "MCP server unavailable"**
- **Cause**: MCP server offline (discovery still works in degraded mode)
- **Fix**: Use direct sample endpoint instead of agentic discovery

---

### How to Use Data Discovery

1. **Navigate to**: http://127.0.0.1:5173/#/data-discovery

2. **Select datasource**:
   - From dropdown (registered sources)
   - Or enter folder path

3. **Click "Run Discovery"**

4. **If fails**, check:
   - Browser console (F12 → Console tab)
   - Backend PowerShell window for errors
   - CSV file exists and is readable

---

## ✅ SOLUTION 3: Direct CSV Upload (Workaround)

If discovery fails, use Migration Wizard upload:

1. Go to: http://127.0.0.1:5173/#/migration

2. **Source System**:
   - Type: "File"
   - Upload CSV directly

3. **Target System**: Select target

4. Click "Run Discovery" - this uses simpler upload endpoint

---

## 🔧 Configuration Checklist

### Backend Configuration (.env)

```env
# Required
DATABASE_URL=postgresql://user:pass@localhost/graphtrace
GRAPH_TRACE_LOAD_DOTENV=true

# CSV paths (optional - has defaults)
CSV_INPUT_PATH=./data/csv/input
DATA_ROOT=./data

# Encoding (default: utf-8-sig handles BOM)
# CSV_ENCODING=utf-8-sig
```

### Allowed Data Directories

Backend only allows CSV files in these roots (for security):
- `./data/csv/`
- `./data/uploads/`
- `./data/temp/`
- Or paths in `DATA_ROOT`

**If file is elsewhere**:
```powershell
# Option A: Copy to allowed location
Copy-Item "C:\customer\data.csv" "D:\Download\GoodpointAI\data\csv\input\"

# Option B: Update DATA_ROOT in .env
# Add to python_backend/.env:
# DATA_ROOT=C:\customer
```

---

## 🐛 Debugging Steps

### 1. Check Backend Logs

```powershell
# Backend terminal should show:
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8011 (Press CTRL+C to quit)

# If you see errors like:
ERROR - FileNotFoundError: [Errno 2] No such file or directory: 'file.csv'
# → Fix file path

ERROR - UnicodeDecodeError: 'utf-8' codec can't decode byte
# → Fix CSV encoding
```

### 2. Check Browser Console

```javascript
// Press F12 → Console tab
// Look for:
Failed to fetch http://localhost:8011/api/agentic/discovery
// → Backend not running

Server error: 500
// → Check backend logs

TypeError: Cannot read property 'files' of undefined
// → Discovery response malformed
```

### 3. Test CSV Parsing Manually

```python
# In python_backend directory:
python

>>> import csv
>>> with open('data/csv/input/test.csv', encoding='utf-8-sig') as f:
...     reader = csv.DictReader(f)
...     print(list(reader)[:3])

# Should print first 3 rows
# If error → file path/encoding issue
```

---

## 📊 Customer Environment Setup

### Recommended Setup

```powershell
# 1. Ensure backend running
.\start-backend.ps1

# 2. Ensure frontend running  
cd e2etraceapp
npm run dev -- --host 127.0.0.1 --port 5173

# 3. Place CSV files in allowed location
New-Item -ItemType Directory -Path "data\csv\input" -Force
Copy-Item "path\to\customer.csv" "data\csv\input\"

# 4. Create data source via UI
# Go to: http://127.0.0.1:5173/#/data-discovery
# Or: http://127.0.0.1:5173/#/admin (Data Sources tab)
```

---

## 🔄 Alternative Approach: Use Admin Config

1. Navigate to: **http://127.0.0.1:5173/#/admin**

2. Go to **"Data Sources"** tab

3. Click **"Add Data Source"**

4. Configure:
   ```
   Name: Customer CSV
   Type: file
   Connection:
     file_path: ./data/csv/input/customer.csv
   ```

5. Click **"Test Connection"** (should succeed)

6. Click **"Save"**

7. Now discovery should work

---

## ✅ Success Indicators

**Discovery working correctly when**:
- ✅ Backend health shows postgres + neo4j connected
- ✅ CSV file is in allowed directory
- ✅ Sample endpoint returns JSON with records
- ✅ Frontend shows file list with column profiles
- ✅ No errors in browser console
- ✅ No errors in backend logs

---

## 📞 Need More Help?

**Provide these details**:
1. **Exact error message** (frontend + backend)
2. **Browser console output** (F12 → Console)
3. **Backend logs** (PowerShell window)
4. **CSV file location** and sample first few lines
5. **Data source configuration** (from Admin page)

---

**Last Updated**: April 20, 2026  
**Version**: 1.0  
**Status**: Ready for customer deployment
