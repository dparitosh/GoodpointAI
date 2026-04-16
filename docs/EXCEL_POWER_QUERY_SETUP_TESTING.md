# Excel + Power Query: Setup & Testing Guide

## Prerequisites

- ✅ Windows 10/11
- ✅ Excel 2019 or newer (Desktop, not Online)
- ✅ GraphTrace backend running on port 8011
- ✅ Python 3.10+ with pandas/openpyxl installed
- ✅ 50MB free disk space for sample data

---

## Step 1: Start GraphTrace Backend

### Option A: Using PowerShell Script (Recommended)

```powershell
# From root directory
cd d:\Download\GoodpointAI

# Validate environment first
.\graphtrace.ps1 -Check

# Start backend and frontend
.\graphtrace.ps1 -Start
```

*Expected output:*
```
✓ Starting GraphTrace Backend...
✓ Backend running on http://localhost:8011
✓ Starting Frontend...
✓ Frontend running on http://localhost:5173
```

### Option B: Manual Start

```powershell
# Terminal 1: Backend
cd python_backend
python -m uvicorn main:app --reload --port 8011

# Terminal 2: Frontend (optional)
cd e2etraceapp
npm run dev -- --host 127.0.0.1 --port 5173
```

### Verify Backend is Running

```powershell
# In any PowerShell window
curl http://localhost:8011/health

# Expected response:
# {"health": "ok", "db_ok": true, "neo4j_ok": false, ...}
```

---

## Step 2: Prepare Sample Data

### Create Sample CSV/Excel File

Create a file: `C:\Users\YourUsername\Documents\SampleData.xlsx`

**Format (3 sheets):**

**Sheet 1: Customers**
```
CustomerID | Name        | Email              | Status   | Created
1          | John Doe    | john@example.com   | Active   | 2024-01-01
2          | Jane Smith  | jane@example.com   | Active   | 2024-01-02
3          | Bob Johnson | bob@example.com    | Inactive | 2024-01-03
4          | (null)      | alice@example.com  | Active   | 2024-01-04
5          | Eve Wilson  | (null)             | Inactive | 2024-01-05
```

**Sheet 2: Orders**
```
OrderID | CustomerID | Amount | OrderDate  | Status
1001    | 1          | 1500   | 2024-01-10 | Completed
1002    | 2          | 2300   | 2024-01-11 | Pending
1003    | 1          | 800    | 2024-01-12 | Completed
1004    | 3          | 500    | 2024-01-13 | Cancelled
1005    | 2          | 1200   | 2024-01-14 | Completed
```

**Sheet 3: Products**
```
ProductID | Name       | Category   | Price
101       | Laptop     | Electronics | 999.99
102       | Mouse      | Accessories | 29.99
103       | Keyboard   | Accessories | 79.99
104       | Monitor    | Electronics | 299.99
```

Save as `.xlsx` format.

---

## Step 3: Upload Data to GraphTrace

### Method 1: Via REST API

```powershell
# PowerShell: Upload Excel file
$FilePath = "C:\Users\YourUsername\Documents\SampleData.xlsx"
$UploadUrl = "http://localhost:8011/api/filesystem/upload"

$FileContent = [System.IO.File]::ReadAllBytes($FilePath)

$Response = Invoke-WebRequest -Uri $UploadUrl `
    -Method Post `
    -InFile $FilePath

$Response.Content | ConvertFrom-Json

# Response example:
# {
#   "file_id": "file_sample_001",
#   "filename": "SampleData.xlsx",
#   "datasource_id": "ds_temp_001",
#   "row_count": 13,
#   "status": "uploaded"
# }
```

**Save the `datasource_id`** — you'll need it in Power Query.

### Method 2: Via GraphTrace Admin UI

1. Go to `http://localhost:5173/#/admin`
2. Click "Upload Data File"
3. Select `SampleData.xlsx`
4. Click "Upload"
5. Note the datasource ID shown

---

## Step 4: Test Connection in Excel

### Create Test Query

1. **Open Excel** (Desktop version, not Online)
2. Go to `Data` → `Get Data` → `From Other Sources` → `From Web`
3. **Enter URL:** `http://localhost:8011/health`
4. Click `Load`

**Expected result:** A table with health status

```
health     | db_ok | neo4j_ok
ok         | TRUE  | FALSE
```

✅ **If successful:** Continue to next step
❌ **If error:** 
- Check backend is running: `curl http://localhost:8011/health`
- Check firewall allows port 8011
- Check Windows Defender doesn't block Python

---

## Step 5: Load Datasources List

### Test Case 1: List All Datasources

In Excel Power Query Editor:

```m
let
    ApiUrl = "http://localhost:8011/api/datasources",
    
    Response = Json.Document(Web.Contents(ApiUrl, [
        Headers = [#"Content-Type" = "application/json"],
        Timeout = #duration(0, 0, 30, 0)
    ])),
    
    DataArray = Response[data],
    Table = Table.FromList(DataArray, Splitter.SplitByNothing()),
    Expanded = Table.ExpandRecordColumn(Table, "Column1",
        {"id", "name", "type", "status", "record_count"},
        {"ID", "Name", "Type", "Status", "Records"})
in
    Expanded
```

**Expected result:**
| ID | Name | Type | Status | Records |
|----|------|------|--------|---------|
| ds_temp_001 | SampleData.xlsx | excel | active | 13 |
| ... | ... | ... | ... | ... |

---

## Step 6: Query Sample Data

### Test Case 2: Get Data from Uploaded File

Replace `YOUR_DATASOURCE_ID` with the ID from Step 3.

```m
let
    DatasourceId = "YOUR_DATASOURCE_ID",  // Replace with actual ID
    ApiUrl = "http://localhost:8011/api/datasources/" & DatasourceId & "/preview",
    
    Response = Json.Document(Web.Contents(ApiUrl, [
        Headers = [#"Content-Type" = "application/json"],
        Timeout = #duration(0, 0, 30, 0)
    ])),
    
    DataArray = Response[data],
    Table = Table.FromList(DataArray, Splitter.SplitByNothing()),
    Expanded = Table.ExpandRecordColumn(Table, "Column1",
        {"CustomerID", "Name", "Email", "Status"},
        {"ID", "Name", "Email", "Status"})
in
    Expanded
```

**Expected result:** Preview of your Customers sheet

---

## Step 7: Test Data Quality

### Test Case 3: Analyze Data for Issues

```m
let
    DatasourceId = "YOUR_DATASOURCE_ID",
    QualityUrl = "http://localhost:8011/api/data/quality/check",
    
    Body = Json.FromValue([
        datasource_id = DatasourceId,
        rules = ["completeness", "consistency"]
    ]),
    
    Response = Json.Document(Web.Contents(QualityUrl, [
        Headers = [#"Content-Type" = "application/json"],
        Content = Text.ToBinary(Body),
        Timeout = #duration(0, 0, 30, 0)
    ])),
    
    QualityData = Response[quality_metrics],
    Table = Table.FromList(QualityData, Splitter.SplitByNothing()),
    Expanded = Table.ExpandRecordColumn(Table, "Column1",
        {"metric", "score", "status", "issues_count"},
        {"Metric", "Score", "Status", "Issues"})
in
    Expanded
```

**Expected result:**
| Metric | Score | Status | Issues |
|--------|-------|--------|--------|
| completeness | 92.3 | warning | 2 |
| consistency | 98.5 | good | 0 |

---

## Step 8: Transform Data

### Test Case 4: Apply Business Rules

```m
let
    DatasourceId = "YOUR_DATASOURCE_ID",
    TransformUrl = "http://localhost:8011/api/data/transform",
    
    Body = Json.FromValue([
        datasource_id = DatasourceId,
        rules = [
            [field = "Name", operation = "trim"],
            [field = "Email", operation = "lowercase"],
            [field = "Status", operation = "uppercase"]
        ]
    ]),
    
    Response = Json.Document(Web.Contents(TransformUrl, [
        Headers = [#"Content-Type" = "application/json"],
        Content = Text.ToBinary(Body),
        Timeout = #duration(0, 0, 30, 0)
    ])),
    
    TransformedData = Response[transformed_data],
    Table = Table.FromList(TransformedData, Splitter.SplitByNothing()),
    Expanded = Table.ExpandRecordColumn(Table, "Column1",
        {"CustomerID", "Name", "Email", "Status"},
        {"ID", "Name", "Email", "Status"})
in
    Expanded
```

**Expected result:** Data with all transformations applied

---

## Step 9: Create a Dashboard

### Build 3-Query Dashboard

**Query 1: Data Summary**
```m
let
    Url = "http://localhost:8011/api/datasources",
    Data = Json.Document(Web.Contents(Url))
in
    Data
```

**Query 2: Quality Score**
```m
let
    Url = "http://localhost:8011/api/datasources/YOUR_DATASOURCE_ID",
    Data = Json.Document(Web.Contents(Url))
in
    Data
```

**Query 3: Preview Data**
```m
let
    Url = "http://localhost:8011/api/datasources/YOUR_DATASOURCE_ID/preview",
    Data = Json.Document(Web.Contents(Url))
in
    Data
```

### Add Visualizations

1. **For Query 1:** Create pivot table (Group by Type, Count)
2. **For Query 2:** Create KPI card showing status
3. **For Query 3:** Create table with conditional formatting

---

## Troubleshooting

### Problem: "Cannot reach the web resource"

**Cause:** Backend not running or port 8011 not accessible

**Fix:**
```powershell
# Check if backend is running
netstat -ano | findstr :8011

# If not running, start it:
cd python_backend
python -m uvicorn main:app --port 8011

# Check health:
curl http://localhost:8011/health
```

### Problem: "JSON Parse Error"

**Cause:** Wrong URL or API returned error

**Fix:**
```m
// Add error handling
let
    Response = try
        Json.Document(Web.Contents(Url))
    catch (error)
        error "API Error: " & error[Message]
in
    Response
```

### Problem: "Invalid table/column reference"

**Cause:** Field names don't match

**Fix:**
```powershell
# Check actual column names from preview
curl http://localhost:8011/api/datasources/YOUR_ID/preview

# Use exact column names in Expanded step
Table.ExpandRecordColumn(Table, "Column1", {"actual_column_name"})
```

### Problem: Timeout after 30 seconds

**Cause:** Too much data or slow query

**Fix:**
```m
// Increase timeout
Timeout = #duration(0, 1, 0, 0)  // 1 hour

// Or limit data
ApiUrl = Url & "?limit=1000"
```

### Problem: "401 Unauthorized"

**Cause:** Auth enabled but no API key

**Fix:**
```m
// Get API key from environment variables
Headers = [
    #"Authorization" = "Bearer YOUR_API_KEY",
    #"Content-Type" = "application/json"
]
```

---

## Performance Testing

### Test Large Dataset

1. Create Excel file with 100,000+ rows
2. Upload to GraphTrace
3. Query with different limits:

```m
// Test with limit parameter
Url = "http://localhost:8011/api/datasources/YOUR_ID/data?limit=100"  // 100 rows
Url = "http://localhost:8011/api/datasources/YOUR_ID/data?limit=10000"  // 10K rows
```

**Benchmark:**
- 100 rows: < 1 second
- 1,000 rows: < 2 seconds
- 10,000 rows: < 5 seconds
- > 50,000 rows: Use pagination or server-side aggregation

---

## Refresh Schedule Testing

### Set Up Auto-Refresh

1. In Excel: `Data` → `Queries & Connections`
2. Right-click query → `Properties`
3. Check "Refresh this connection on data refresh"
4. Set interval to **15 minutes**
5. Click OK

### Monitor Refreshes

Create a separate sheet to track refresh logs:

```m
let
    Timestamp = DateTime.LocalNow(),
    Status = "Success",
    RowsLoaded = 1000,
    ExecutionTime = "1.2s"
in
    Table.FromRows(
        {{Timestamp, Status, RowsLoaded, ExecutionTime}},
        {"Timestamp", "Status", "Rows", "Duration"}
    )
```

---

## Security Testing

### Test with API Key (If Configured)

```powershell
# Add API key to environment
$env:GRAPH_TRACE_API_KEY = "test-key-123"

# Restart backend
# Then test in Power Query:
```

```m
let
    ApiKey = "test-key-123",
    Response = Json.Document(Web.Contents(Url, [
        Headers = [#"Authorization" = "Bearer " & ApiKey]
    ]))
in
    Response
```

---

## Validation Checklist

- [ ] Backend running on port 8011
- [ ] `/health` endpoint returns OK
- [ ] Sample data uploaded successfully
- [ ] Test Case 1 (list datasources) works
- [ ] Test Case 2 (get data) works
- [ ] Test Case 3 (quality check) works
- [ ] Test Case 4 (transform) works
- [ ] Dashboard with 3 queries created
- [ ] Refresh schedule configured
- [ ] No timeout errors after refresh

---

## Next Steps

✅ **If all tests pass:**
1. Create production Excel workbook
2. Set up monitoring/alerting
3. Configure regular refresh schedule
4. Document custom queries and transformations
5. Train team members

📚 **Resources:**
- Full guide: `docs/EXCEL_POWER_QUERY_INTEGRATION.md`
- Examples: `docs/EXCEL_POWER_QUERY_QUICKSTART.md`
- API docs: `docs/EXCEL_POWER_QUERY_API_REFERENCE.md`
- GraphTrace docs: `docs/`

---

## Support

**Problem?** Check:
1. GraphTrace health: `curl http://localhost:8011/health`
2. API docs: `http://localhost:8011/docs`
3. Backend logs: `python_backend/*.log`
4. Power Query error message (copy exact text)

**Want to improve?**
- Report bugs: GitHub Issues
- Feature requests: GitHub Discussions
- Documentation improvements: Pull requests
