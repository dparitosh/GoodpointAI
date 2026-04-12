# Excel as UI with Power Query Editor: Integration Guide

## TL;DR

✅ **YES, absolutely possible.** GraphTrace has:
- REST APIs (37 routers)
- OData support (SAP, Dynamics, generic)
- Excel adapter (openpyxl integration)
- Data transformation endpoints

**Approach:** Use Power Query's REST connector to call GraphTrace APIs → Load data into Excel → Refresh data from Power Query Editor

---

## Architecture: Excel + Power Query → GraphTrace API

```
Excel Workbook
    ↓
Power Query Editor (M Language)
    ↓
REST Connector → GraphTrace API
    ↓
Response (JSON)
    ↓
Tables in Excel
    ↓
Pivot Tables, Charts, Analysis
```

---

## What GraphTrace Already Has

### ✅ OData Integration Router
**Location:** `python_backend/graph_api/odata_integration_router.py`

```python
# Already built: 8+ OData endpoints
@router.get("/metadata")          # Schema discovery
@router.post("/query")             # Query OData service
@router.get("/entities")           # List entities
@router.post("/filter")            # Filter data
@router.get("/related")            # Navigate relationships
```

**Supports:**
- SAP OData endpoints
- Dynamics OData
- Generic OData services

### ✅ Excel File Adapter
**Location:** `python_backend/graph_api/database_adapters/excel_adapter.py`

```python
# Already built: Excel CRUD operations
ExcelAdapter:
  - read_excel_file()
  - write_excel_file()
  - query_excel_data()
  - update_excel_data()
```

### ✅ Multimodal Processing
**Location:** `python_backend/graph_api/multimodal_router.py`

```python
# Already built: Extract data from Excel files
extract_excel_data()  # Supports .xlsx, .xls, .xlsm
```

### ✅ Data Transformation APIs
**Available endpoints:**
- `/api/data/transform` — Transform data with mapping rules
- `/api/data/convert` — Convert between formats
- `/api/data/validate` — Validate data quality
- `/api/analyze` — Statistical analysis

---

## Implementation Path 1: Power Query REST API

**Use Case:** Real-time data from GraphTrace APIs into Excel

### Step 1: Enable GraphTrace API

Your system already runs on port 8011:
```bash
./graphtrace.ps1 -Start

# Backend listening at:
http://localhost:8011
```

### Step 2: Create Power Query Connector

In Excel, use `Data` → `Get Data` → `From Other Sources` → `From Web`:

**Power Query M Code:**

```m
let
    // API Endpoint
    ApiUrl = "http://localhost:8011/api/datasources",
    
    // Make REST call
    Response = Json.Document(Web.Contents(ApiUrl, [
        Headers = [
            #"Content-Type" = "application/json",
            #"Authorization" = "Bearer YOUR_API_KEY"  // Optional
        ],
        Timeout = #duration(0, 0, 30, 0)
    ])),
    
    // Transform response
    Data = Table.FromList(Response[data], Splitter.SplitByNothing(), null, null, ExtraValues.Error),
    
    // Expand columns
    Expanded = Table.ExpandRecordColumn(Data, "Column1", {"id", "name", "type", "status"}, {"ID", "Name", "Type", "Status"})
    
in
    Expanded
```

### Step 3: Set Up Refresh Schedule

**In Excel:**
- `Data` → `Refresh All`
- Set to refresh every 15 minutes (configurable)
- Or refresh manually

---

## Implementation Path 2: OData Endpoint

**Use Case:** If you want strict OData v4 compliance

### Enable OData Service

GraphTrace exposes OData-compatible endpoints:

```bash
# Configure in python_backend/.env:
ODATA_SERVICE_URL=http://localhost:8011/api/odata
```

### Connect Excel to OData

**In Excel Power Query:**
```m
let
    ODataUrl = "http://localhost:8011/api/odata",
    
    ODataFeed = OData.Feed(ODataUrl, null, [
        Implementation = "2.0"
    ])
in
    ODataFeed
```

Then select available entities and load into Excel.

---

## Implementation Path 3: Hybrid Approach (Recommended)

**Best balancing flexibility + ease:**

### 1. Transform Data in GraphTrace

```
User Input (Excel)
    ↓
GraphTrace API Transform Endpoint
    ↓
Transformed Data
    ↓
Power Query REST API
    ↓
Results in Excel
```

**Step 1: Upload to GraphTrace**
```m
// Power Query: Upload Excel to GraphTrace for processing
let
    FilePath = "C:\Data\MyData.xlsx",
    File = File.Contents(FilePath),
    
    UploadUrl = "http://localhost:8011/api/filesystem/upload",
    Upload = Json.Document(Web.Contents(UploadUrl, [
        Headers = ["Content-Type" = "multipart/form-data"],
        Content = File
    ])),
    
    FileId = Upload[file_id]
in
    FileId
```

**Step 2: Transform in GraphTrace**
```m
// Power Query: Request transformation
let
    TransformUrl = "http://localhost:8011/api/data/transform",
    
    TransformRequest = Json.FromValue([
        source_file = FileId,
        rules = [
            [field = "Amount", operation = "multiply", value = 1.1],
            [field = "Status", operation = "uppercase"]
        ]
    ]),
    
    Response = Json.Document(Web.Contents(TransformUrl, [
        Headers = ["Content-Type" = "application/json"],
        Content = Text.ToBinary(TransformRequest)
    ])),
    
    Results = Response[data]
in
    Results
```

**Step 3: Load Results into Excel**
```m
// Power Query: Load transformed data into Excel table
let
    Data = Results,
    Table = Table.FromList(Data, Splitter.SplitByNothing(), null, null, ExtraValues.Error),
    Expanded = Table.ExpandRecordColumn(Table, "Column1", {"name", "amount", "status"})
in
    Expanded
```

---

## Real Examples You Can Build

### Example 1: Data Quality Dashboard

**Excel → GraphTrace → Stats → Excel**

```m
let
    // Your data in Excel
    SourceTable = Excel.CurrentWorkbook(){[Name="DataTable"]}[Content],
    
    // Send to GraphTrace for quality check
    QualityUrl = "http://localhost:8011/api/data/quality/analyze",
    
    Quality = Json.Document(Web.Contents(QualityUrl, [
        Headers = ["Content-Type" = "application/json"],
        Content = Text.ToBinary(Json.FromValue([
            data = SourceTable,
            rules = ["completeness", "consistency", "uniqueness"]
        ]))
    ])),
    
    // Get results: overall_score, issues, recommendations
    Results = Quality[results]
in
    Results
```

**Excel Visualization:**
- Pie chart: Data quality score
- Table: Issues found
- Bar chart: Quality improvements over time

---

### Example 2: ETL Pipeline Execution

**Excel Input → GraphTrace Transform → Excel Output**

```m
let
    // Source data from Excel
    InputData = Excel.CurrentWorkbook(){[Name="Input"]}[Content],
    
    // Execute ETL in GraphTrace
    EtlUrl = "http://localhost:8011/api/etl/execute",
    
    ExecutedPipeline = Json.Document(Web.Contents(EtlUrl, [
        Headers = ["Content-Type" = "application/json"],
        Content = Text.ToBinary(Json.FromValue([
            pipeline_id = "etl_001",
            input_data = InputData,
            mappings = [
                [source = "CustomerID", target = "Cust_ID"],
                [source = "OrderDate", target = "Date", format = "yyyy-MM-dd"]
            ]
        ]))
    ])),
    
    OutputData = ExecutedPipeline[output_data]
in
    OutputData
```

---

### Example 3: Lineage Tracking

**Excel Data → GraphTrace Lineage → Visual in Excel**

```m
let
    // Track where this data came from
    LineageUrl = "http://localhost:8011/api/lineage/trace",
    
    Lineage = Json.Document(Web.Contents(LineageUrl, [
        Headers = ["Content-Type" = "application/json"],
        Content = Text.ToBinary(Json.FromValue([
            source = "CustomerData",
            target = "SalesReport",
            depth = "full"
        ]))
    ])),
    
    // Convert to table format
    LineageTable = Table.FromList(Lineage[lineage_path], Splitter.SplitByNothing()),
    
    // Columns: Source, Transformation, Target
    Columns = Table.ExpandRecordColumn(LineageTable, "Column1", 
        {"source", "operation", "target", "timestamp"})
in
    Columns
```

---

## Advantages of This Approach

| Advantage | Benefit | Use Case |
|-----------|---------|----------|
| **No Coding Required** | Business users can use Power Query Editor | Non-technical team members |
| **Real-Time Data** | Refresh button in Excel gets latest data | Dashboards, reports |
| **Familiar Interface** | Everyone knows Excel | Reduced training time |
| **Built-in Analytics** | Pivot tables, charts, formulas | Data exploration |
| **Audit Trail** | Power Query logs transformation steps | Compliance, transparency |
| **Offline Capable** | Excel works without network | Access data offline |
| **Version Control** | Excel file version history | Track changes over time |

---

## Limitations & Considerations

| Limitation | Workaround | Impact |
|-----------|-----------|--------|
| **Scale** | Millions of rows slow in Excel | Aggregate data server-side first |
| **Refresh Timing** | Manual or scheduled (not real-time) | Good for hourly/daily, not tick-by-tick |
| **Complex Logic** | Power Query M is limited | Use GraphTrace APIs for heavy logic |
| **Authentication** | API key in Power Query visible | Use service account or OAuth in real deployments |
| **Network Required** | Can't refresh without network | Cache data locally for offline work |

---

## Setup Instructions

### 1. Prepare GraphTrace

**Ensure APIs are running:**
```bash
./graphtrace.ps1 -Start

# Verify:
curl http://localhost:8011/health
# Response: {"db_ok": true, "neo4j_ok": false, "health": "ok"}
```

**Configure APIs (if needed):**
```bash
# Edit python_backend/.env for API credentials
GRAPH_TRACE_API_KEY=your-api-key-here  # Optional, for auth
```

### 2. Set Up Excel

**Create a query to test:**

Open Excel → `Data` → `Get Data` → `From Other Sources` → `From Web`

```
URL: http://localhost:8011/api/datasources
Method: GET
Headers: Authorization: Bearer YOUR_KEY (if using auth)
```

### 3. Test Connection

**In Power Query Editor:**
- Click "Invoke" or "Load"
- If successful: See data in preview
- If failed: Check /health endpoint first

### 4. Create Refresh Schedule

**In Excel:**
- `Data` → `Queries & Connections`
- Right-click query → `Properties`
- Set `Refresh every X minutes`

---

## Security Considerations

### For Development:
```m
let
    ApiUrl = "http://localhost:8011/api/datasources",
    // No auth needed for local testing
in
    ...
```

### For Production:
```m
let
    ApiUrl = "https://api.yourcompany.com/graphtrace",
    
    // Use Azure Key Vault for secrets (not in .pq file!)
    ApiKey = "***STORED_IN_KEY_VAULT***",
    
    Response = Json.Document(Web.Contents(ApiUrl, [
        Headers = [
            "Authorization" = "Bearer " & ApiKey,
            "Content-Type" = "application/json"
        ],
        ManualStatusHandling = {400, 401, 403, 404, 500}
    ])),
    
    // Handle errors gracefully
    SafeResponse = if Response[status] = 200 
                   then Response[data]
                   else error Response[error]
in
    SafeResponse
```

---

## Performance Tips

### 1. **Filter Server-Side**
```m
// ✅ GOOD: Filter in GraphTrace
let
    Url = "http://localhost:8011/api/datasources?status=active&limit=1000"
in
    Json.Document(Web.Contents(Url))

// ❌ BAD: Download 1M rows then filter
let
    All = Json.Document(Web.Contents("http://localhost:8011/api/datasources")),
    Filtered = Table.SelectRows(All, each [status] = "active")
in
    Filtered
```

### 2. **Use Pagination**
```m
let
    Url = "http://localhost:8011/api/datasources?skip=0&limit=100",
    // Fetch 100 rows at a time, then combine
    AllPages = List.Generate(
        () => [page = 0, url = Url, data = null, hasmore = true],
        each [hasmore],
        each [
            page = [page] + 1,
            url = "http://localhost:8011/api/datasources?skip=" & ([page] * 100) & "&limit=100",
            data = Json.Document(Web.Contents([url])),
            hasmore = List.Count([data]) = 100
        ]
    )
in
    Table.Combine(List.Transform(AllPages, each [data]))
```

### 3. **Cache Results**
```m
let
    // Only refresh every 24 hours
    CacheUrl = "http://localhost:8011/api/datasources?cache=24h",
    Data = Json.Document(Web.Contents(CacheUrl))
in
    Data
```

---

## Excel Templates You Can Create

### Template 1: Data Quality Dashboard
**Columns:** Field, Completeness, Distinctness, Format_Valid, Overall_Score

```
Dashboard
├─ Source Data (from API)
├─ Quality Metrics (from /api/data/quality/analyze)
├─ Issues List (from API response)
└─ Charts (pivot table + conditional formatting)
```

### Template 2: ETL Monitoring
**Columns:** Pipeline, Status, Records_Processed, Errors, Warnings, Duration

```
Monitoring
├─ Pipeline Status (from /api/etl/status)
├─ Error Log (from API)
├─ Performance Metrics (from /api/monitoring)
└─ Alerts (conditional formatting)
```

### Template 3: Data Lineage Visualizer
**Columns:** System, Table, Column, Origin, Transforms, Target

```
Lineage
├─ Source Systems (from /api/lineage/sources)
├─ Transformation Steps (from API)
├─ Target Systems (from API)
└─ Visual Graph (using SmartArt or custom shapes)
```

---

## Summary

✅ **Excel as UI with Power Query:** Fully possible  
✅ **GraphTrace APIs:** Ready to connect  
✅ **OData support:** Built-in  
✅ **Excel adapter:** Already implemented  
✅ **No coding:** Just use Power Query M language  

**Recommend:** Start with REST connector (Path 1), upgrade to OData (Path 2) if you need schema discovery.

The codebase supports this architecture already. You're ready to go!
