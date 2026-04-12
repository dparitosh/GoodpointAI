# Excel + Power Query: Quick Start Examples

## Get Started in 5 Minutes

### Step 1: Open Excel Power Query Editor

In Excel:
1. Go to `Data` → `Get Data` → `From Other Sources` → `From Web`
2. Enter URL: `http://localhost:8011/health`
3. Click `OK`
4. In preview, click `Load`

**Expected result:** A table with health status.

---

## Example 1: Load Datasources List

**Copy-paste this directly into Power Query:**

```m
let
    // Step 1: Define the API endpoint
    ApiUrl = "http://localhost:8011/api/datasources",
    
    // Step 2: Make the REST call
    Response = Json.Document(Web.Contents(ApiUrl, [
        Headers = [
            #"Content-Type" = "application/json"
        ],
        Timeout = #duration(0, 0, 30, 0)
    ])),
    
    // Step 3: Extract the data array
    DataArray = if Type.Is(Response, type list) 
                then Response 
                else if Type.Is(Response[data], type list)
                then Response[data]
                else error "Expected array of datasources",
    
    // Step 4: Convert to table
    Table = Table.FromList(DataArray, Splitter.SplitByNothing(), null, null, ExtraValues.Error),
    
    // Step 5: Expand all columns
    Expanded = Table.ExpandRecordColumn(Table, "Column1", 
        {"id", "name", "type", "status", "created_at", "updated_at"}, 
        {"ID", "Name", "Type", "Status", "Created", "Updated"})
in
    Expanded
```

**What it does:**
- Fetches all datasources from GraphTrace
- Converts JSON response to Excel table
- Ready for filtering, sorting, pivot tables

---

## Example 2: Filter Data Server-Side

**Get only active datasources:**

```m
let
    // Request only active datasources from API
    ApiUrl = "http://localhost:8011/api/datasources?status=active&limit=100",
    
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

**Key difference:** The `?status=active&limit=100` filters server-side, not client-side.

---

## Example 3: Analyze Data Quality

**Get quality metrics for your data:**

```m
let
    // Define the quality analysis API
    QualityUrl = "http://localhost:8011/api/data/quality/check",
    
    // Parameters for the quality check
    QualityRequest = Json.FromValue([
        datasource_id = "your_datasource_id",  // Replace with real ID
        rules = ["completeness", "consistency", "format_valid", "uniqueness"]
    ]),
    
    // Make the request
    Response = Json.Document(Web.Contents(QualityUrl, [
        Headers = [#"Content-Type" = "application/json"],
        Content = Text.ToBinary(QualityRequest),
        ManualStatusHandling = {400, 404, 500}
    ])),
    
    // Extract results
    QualityMetrics = Response[quality_metrics],
    
    // Convert to table
    Table = Table.FromList(QualityMetrics, Splitter.SplitByNothing()),
    Expanded = Table.ExpandRecordColumn(Table, "Column1",
        {"metric", "score", "status", "issues_count"},
        {"Metric", "Score", "Status", "Issues"})
in
    Expanded
```

**In Excel:**
- Create a chart: Quality scores over time
- Conditional formatting: Red if score < 80%, green if > 95%
- Refresh daily to track improvements

---

## Example 4: Transform Data

**Apply business rules in GraphTrace, get results back:**

```m
let
    // Your source data (already in Excel)
    SourceTable = Excel.CurrentWorkbook(){[Name="RawData"]}[Content],
    
    // API to transform data
    TransformUrl = "http://localhost:8011/api/data/transform",
    
    // Define transformations
    TransformRequest = Json.FromValue([
        operation = "batch_transform",
        rules = [
            [
                field = "Amount",
                type = "number",
                operations = [
                    [type = "multiply", value = 1.1],  // Add 10%
                    [type = "round", decimals = 2]
                ]
            ],
            [
                field = "CustomerName",
                type = "text",
                operations = [
                    [type = "trim"],
                    [type = "uppercase"]
                ]
            ],
            [
                field = "OrderDate",
                type = "date",
                operations = [
                    [type = "format", format = "yyyy-MM-dd"]
                ]
            ]
        ]
    ]),
    
    // Execute transformation
    Response = Json.Document(Web.Contents(TransformUrl, [
        Headers = [#"Content-Type" = "application/json"],
        Content = Text.ToBinary(TransformRequest),
        ManualStatusHandling = {400, 500}
    ])),
    
    // Get transformed data
    TransformedData = Response[transformed_data],
    
    // Convert to table
    Table = Table.FromList(TransformedData, Splitter.SplitByNothing()),
    Expanded = Table.ExpandRecordColumn(Table, "Column1",
        {"CustomerName", "Amount", "OrderDate", "Status"},
        {"Customer", "Amount", "Date", "Status"})
in
    Expanded
```

**Use case:**
- Apply business logic (tax rules, discounts, formatting)
- Audit trail: Who applied which rule
- Reproducible: Always same rules applied

---

## Example 5: Load OData Service

**If using OData endpoint (SAP, Dynamics, generic):**

```m
let
    // OData service URL
    ODataUrl = "http://localhost:8011/api/odata",
    
    // Connect to OData feed
    ODataFeed = OData.Feed(ODataUrl, null, [
        Implementation = "2.0",
        UseFormula = false
    ]),
    
    // Select the entity you want (e.g., "Customers")
    Customers = ODataFeed{[Name="Customers"]}[Data]
in
    Customers
```

**What you get:**
- Full schema discovery
- Related tables (Customers → Orders)
- Automatic relationship mapping

---

## Example 6: Combine Multiple DataSources

**Blend data from two GraphTrace APIs:**

```m
let
    // Source 1: Customers
    CustomersUrl = "http://localhost:8011/api/datasources/customers",
    Customers = Table.FromValue(Json.Document(Web.Contents(CustomersUrl))),
    CustomersExpanded = Table.ExpandRecordColumn(Customers, "Column1",
        {"id", "name", "status"},
        {"CustomerID", "CustomerName", "Status"}),
    
    // Source 2: Orders
    OrdersUrl = "http://localhost:8011/api/datasources/orders",
    Orders = Table.FromValue(Json.Document(Web.Contents(OrdersUrl))),
    OrdersExpanded = Table.ExpandRecordColumn(Orders, "Column1",
        {"id", "customer_id", "amount", "date"},
        {"OrderID", "CustomerID", "Amount", "OrderDate"}),
    
    // Step 3: Left join on CustomerID
    Merged = Table.NestedJoin(
        CustomersExpanded, {"CustomerID"},
        OrdersExpanded, {"CustomerID"},
        "Orders", JoinKind.LeftOuter),
    
    // Step 4: Expand joined data
    Expanded = Table.ExpandTableColumn(Merged, "Orders",
        {"OrderID", "Amount", "OrderDate"},
        {"OrderID", "Amount", "OrderDate"})
in
    Expanded
```

**Result:**
- Customer | CustomerName | Status | OrderID | Amount | OrderDate
- One row per order, with customer details

---

## Example 7: Error Handling

**Make queries robust to API failures:**

```m
let
    ApiUrl = "http://localhost:8011/api/datasources",
    
    // Try-catch pattern in Power Query
    Response = try
        Json.Document(Web.Contents(ApiUrl, [
            Headers = [#"Content-Type" = "application/json"],
            Timeout = #duration(0, 0, 30, 0),
            ManualStatusHandling = {429, 500, 503}  // Handle rate limits and server errors
        ]))
    catch (error) error [
        Message = error[Message],
        Detail = error[Detail],
        Timestamp = DateTime.LocalNow()
    ],
    
    // Check if successful
    IsSuccess = Response[HttpStatusCode] = 200,
    
    // Extract data or return empty table
    Data = if IsSuccess
           then Response[data]
           else Table.FromRows({}),
    
    // Convert to table
    Table = if List.IsEmpty(Data)
            then Table.FromRows({}, {"Error", "No data returned from API"})
            else Table.FromList(Data, Splitter.SplitByNothing())
in
    Table
```

**Features:**
- Handles HTTP errors (429 rate limit, 500 server error)
- Returns blank table instead of error
- Logs timestamp for troubleshooting

---

## Example 8: Refresh Schedule

**Set up automatic data refresh in Excel:**

1. **In Power Query Editor:**
   - Right-click your query
   - Click `Properties`

2. **In Properties dialog:**
   - Check "Enable refresh"
   - Set refresh interval: `15` minutes (adjust as needed)
   - Click `OK`

3. **In Excel workbook:**
   - Go to `Data` → `Queries & Connections`
   - For each query, right-click → `Refresh`

**Tip:** Use a separate worksheet to manage refresh timestamps
```excel
Refresh Log
Timestamp          | Query Name     | Status
2024-01-15 9:15 AM | Datasources    | Success
2024-01-15 9:30 AM | QualityMetrics | Success
2024-01-15 9:45 AM | Datasources    | Error (timeout)
```

---

## Example 9: Create a Dashboard

**Combine queries into a single dashboard:**

1. **Create separate queries:**
   - `DatasourcesQuery` (Example 1)
   - `QualityMetricsQuery` (Example 3)
   - `TransformedDataQuery` (Example 4)

2. **Create pivot tables for each:**
   - Insert → Pivot Table → Select query → OK

3. **Create charts:**
   - Insert → Chart → Line/Bar/Pie
   - Bind to pivot table

4. **Arrange on dashboard sheet:**

```
┌─────────────────────────────────────┐
│  GraphTrace Data Dashboard          │
│  Last Refresh: 2024-01-15 09:45 AM  │
├─────────────────────────────────────┤
│  Datasources Summary  │  Quality Score │
│  (Pivot Table)        │  (Gauge Chart) │
│                       │                │
│                       │  ●═════●       │
│                       │  85% - Good    │
├─────────────────────────────────────┤
│  Transformation Results              │
│  (Data Table with conditional fmt)   │
└─────────────────────────────────────┘
```

---

## Troubleshooting

### Problem: "Invalid URL"
**Solution:** Verify GraphTrace is running:
```powershell
curl http://localhost:8011/health
# Should return: {"health": "ok", ...}
```

### Problem: JSON Parse Error
**Solution:** Add error handling (Example 7)

### Problem: Timeout After 30 Seconds
**Solution:** Increase timeout in query:
```m
Timeout = #duration(0, 1, 0, 0)  // 1 hour
```

### Problem: "Access Denied" (401)
**Solution:** Add authentication header:
```m
Headers = [
    #"Authorization" = "Bearer YOUR_API_KEY",
    #"Content-Type" = "application/json"
]
```

### Problem: Rate Limit (429)
**Solution:** Add retry logic:
```m
let
    Retry = try
        Json.Document(Web.Contents(Url))
    catch (error) 
        if error[Message] = "429"
        then [retry after 60 seconds]
        else error
in
    Retry
```

---

## Keyboard Shortcuts in Power Query

| Action | Shortcut |
|--------|----------|
| Open query editor | Ctrl+Shift+X |
| Refresh query | Ctrl+Shift+R |
| Apply query | Ctrl+Enter |
| Undo | Ctrl+Z |
| Close editor | Alt+F4 |

---

## Next Steps

1. **Import Example 1** → Verify connection works
2. **Add Example 3** → Check your data quality
3. **Create pivot table** → Analyze by datasource type
4. **Set up refresh** → Run nightly
5. **Build dashboard** → Combine multiple queries

**Need help?**
- Check GraphTrace `/health` endpoint
- Review API documentation: `http://localhost:8011/docs`
- Check Power Query function reference: https://learn.microsoft.com/en-us/powerquery-m/
