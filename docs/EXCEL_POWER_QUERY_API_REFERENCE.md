# GraphTrace API Reference for Excel Integration

## Quick API Reference

All endpoints return JSON, compatible with Excel Power Query.

Base URL: `http://localhost:8011`

---

## 1️⃣ Datasources APIs

### List All Datasources
```
GET /api/datasources
GET /api/datasources?status=active&limit=100&offset=0
GET /api/datasources?type=database
GET /api/datasources?search=customer
```

**Response:**
```json
{
  "data": [
    {
      "id": "ds_001",
      "name": "CustomerDB",
      "type": "postgres",
      "status": "active",
      "record_count": 50000,
      "created_at": "2024-01-01T10:00:00Z",
      "updated_at": "2024-01-15T09:45:00Z"
    }
  ],
  "total": 1,
  "limit": 100,
  "offset": 0
}
```

**Power Query Formula:**
```m
let
    Url = "http://localhost:8011/api/datasources?status=active",
    Data = Json.Document(Web.Contents(Url))
in
    Table.FromList(Data[data], Splitter.SplitByNothing())
```

---

### Get Datasource Details
```
GET /api/datasources/{datasource_id}
GET /api/datasources/{datasource_id}/schema
GET /api/datasources/{datasource_id}/tables
GET /api/datasources/{datasource_id}/preview
```

**Response (Details):**
```json
{
  "id": "ds_001",
  "name": "CustomerDB",
  "type": "postgres",
  "connection_string": "postgres://...",
  "tables": ["customers", "orders", "products"],
  "status": "connected",
  "last_sync": "2024-01-15T09:00:00Z"
}
```

**Response (Preview):**
```json
{
  "data": [
    {"id": 1, "name": "John", "email": "john@example.com"},
    {"id": 2, "name": "Jane", "email": "jane@example.com"}
  ],
  "columns": ["id", "name", "email"],
  "row_count": 1000
}
```

---

## 2️⃣ Data Query APIs

### Execute Query on Datasource
```
POST /api/datasources/{datasource_id}/query
Content-Type: application/json

{
  "sql": "SELECT * FROM customers WHERE status = 'active' LIMIT 100"
}
```

**Response:**
```json
{
  "data": [
    {"id": 1, "name": "John", "status": "active"},
    {"id": 2, "name": "Jane", "status": "active"}
  ],
  "columns": ["id", "name", "status"],
  "row_count": 2,
  "execution_time_ms": 125
}
```

**Power Query Formula:**
```m
let
    Url = "http://localhost:8011/api/datasources/ds_001/query",
    QueryBody = Json.FromValue([
        sql = "SELECT * FROM customers WHERE status = 'active' LIMIT 100"
    ]),
    Response = Json.Document(Web.Contents(Url, [
        Headers = [#"Content-Type" = "application/json"],
        Content = Text.ToBinary(QueryBody)
    ])),
    Data = Response[data],
    Table = Table.FromList(Data, Splitter.SplitByNothing()),
    Expanded = Table.ExpandRecordColumn(Table, "Column1",
        {"id", "name", "status"},
        {"ID", "Name", "Status"})
in
    Expanded
```

---

### List Tables in Datasource
```
GET /api/datasources/{datasource_id}/tables
GET /api/datasources/{datasource_id}/tables?filter=customer
```

**Response:**
```json
{
  "tables": [
    {
      "name": "customers",
      "row_count": 50000,
      "column_count": 15,
      "columns": ["id", "name", "email", "status"]
    },
    {
      "name": "orders",
      "row_count": 250000,
      "column_count": 8
    }
  ]
}
```

---

## 3️⃣ Data Quality APIs

### Check Data Quality
```
POST /api/data/quality/check
Content-Type: application/json

{
  "datasource_id": "ds_001",
  "table": "customers",
  "rules": ["completeness", "consistency", "format_valid", "uniqueness"],
  "sample_size": 1000
}
```

**Response:**
```json
{
  "datasource": "ds_001",
  "table": "customers",
  "quality_metrics": [
    {
      "metric": "completeness",
      "score": 98.5,
      "status": "good",
      "issues_count": 15,
      "message": "15 null values found in 'email' column"
    },
    {
      "metric": "consistency",
      "score": 95.2,
      "status": "warning",
      "issues_count": 48,
      "message": "48 inconsistent date formats detected"
    },
    {
      "metric": "format_valid",
      "score": 99.1,
      "status": "good",
      "issues_count": 9
    },
    {
      "metric": "uniqueness",
      "score": 100.0,
      "status": "good",
      "issues_count": 0
    }
  ],
  "overall_score": 97.7,
  "overall_status": "good",
  "timestamp": "2024-01-15T10:00:00Z"
}
```

**Power Query:**
```m
let
    Url = "http://localhost:8011/api/data/quality/check",
    Body = Json.FromValue([
        datasource_id = "ds_001",
        table = "customers",
        rules = ["completeness", "consistency"]
    ]),
    Response = Json.Document(Web.Contents(Url, [
        Headers = [#"Content-Type" = "application/json"],
        Content = Text.ToBinary(Body)
    ])),
    Metrics = Response[quality_metrics],
    Table = Table.FromList(Metrics, Splitter.SplitByNothing()),
    Expanded = Table.ExpandRecordColumn(Table, "Column1",
        {"metric", "score", "status", "issues_count"},
        {"Metric", "Score", "Status", "Issues"})
in
    Expanded
```

---

### Get Quality Issues
```
GET /api/data/quality/issues
GET /api/datasources/{datasource_id}/quality/issues
GET /api/datasources/{datasource_id}/quality/issues?severity=high&limit=50
```

**Response:**
```json
{
  "issues": [
    {
      "id": "issue_001",
      "datasource_id": "ds_001",
      "table": "customers",
      "column": "email",
      "issue_type": "null_values",
      "severity": "high",
      "count": 15,
      "affected_rows": [1, 5, 12, 23, ...],
      "recommended_action": "Fill null values with valid email"
    }
  ],
  "total": 42,
  "high": 5,
  "medium": 20,
  "low": 17
}
```

---

## 4️⃣ Data Transformation APIs

### Transform Data
```
POST /api/data/transform
Content-Type: application/json

{
  "datasource_id": "ds_001",
  "table": "customers",
  "rules": [
    {
      "field": "email",
      "operation": "lowercase"
    },
    {
      "field": "name",
      "operation": "trim"
    },
    {
      "field": "created_date",
      "operation": "parse_date",
      "format": "yyyy-MM-dd"
    },
    {
      "field": "revenue",
      "operation": "multiply",
      "value": 1.1
    }
  ]
}
```

**Response:**
```json
{
  "transformed_data": [
    {
      "id": 1,
      "name": "John Doe",
      "email": "john@example.com",
      "created_date": "2024-01-01",
      "revenue": 11000.00
    }
  ],
  "transformation_applied": 4,
  "errors": [],
  "timestamp": "2024-01-15T10:05:00Z"
}
```

---

### Validate Data
```
POST /api/data/validate
Content-Type: application/json

{
  "data": [
    {"id": 1, "email": "john@example.com", "age": 30},
    {"id": 2, "email": "invalid-email", "age": -5}
  ],
  "rules": [
    {
      "field": "email",
      "type": "email"
    },
    {
      "field": "age",
      "type": "integer",
      "min": 0,
      "max": 150
    }
  ]
}
```

**Response:**
```json
{
  "valid": 1,
  "invalid": 1,
  "validation_errors": [
    {
      "row_index": 1,
      "field": "email",
      "error": "Invalid email format: 'invalid-email'"
    },
    {
      "row_index": 1,
      "field": "age",
      "error": "Value -5 is outside allowed range [0, 150]"
    }
  ]
}
```

---

## 5️⃣ Data Lineage APIs

### Trace Data Lineage
```
GET /api/lineage/trace?source=datasource_id&target=datasource_id
GET /api/lineage/trace?table=customers&depth=full
```

**Response:**
```json
{
  "lineage_path": [
    {
      "system": "CustomerDB",
      "table": "raw_customers",
      "columns": ["id", "name", "email"],
      "timestamp": "2024-01-01T00:00:00Z"
    },
    {
      "system": "ETL_Pipeline",
      "operation": "clean_emails",
      "rule": "lowercase, trim, validate",
      "timestamp": "2024-01-01T01:00:00Z"
    },
    {
      "system": "WarehouseDB",
      "table": "dim_customers",
      "columns": ["customer_id", "email", "status"],
      "timestamp": "2024-01-01T02:00:00Z"
    }
  ],
  "source": "CustomerDB.raw_customers",
  "target": "WarehouseDB.dim_customers",
  "depth": "full",
  "transformation_count": 1
}
```

---

### Get Lineage Impact
```
GET /api/lineage/impact?table=dim_customers
```

**Response:**
```json
{
  "upstream_systems": ["CustomerDB", "ETL_Pipeline"],
  "downstream_systems": ["ReportingDB", "Dashboard_API", "Excel_Reports"],
  "affected_tables": ["fact_sales", "vw_customer_summary"],
  "impact_count": 12
}
```

---

## 6️⃣ Data Catalog APIs

### Search Data Catalog
```
GET /api/catalog/search?q=customer
GET /api/catalog/search?field=name&value=revenue
GET /api/catalog/search?tags=pii,sensitive
```

**Response:**
```json
{
  "results": [
    {
      "id": "table_001",
      "name": "customers",
      "datasource": "CustomerDB",
      "type": "table",
      "description": "Customer master data",
      "columns": [
        {
          "name": "id",
          "type": "integer",
          "nullable": false,
          "pii": false
        },
        {
          "name": "email",
          "type": "string",
          "nullable": false,
          "pii": true
        }
      ],
      "tags": ["core", "pii"],
      "last_modified": "2024-01-15T09:00:00Z"
    }
  ],
  "total": 24
}
```

---

### Get Table Metadata
```
GET /api/catalog/tables/{table_id}
GET /api/catalog/tables/{table_id}/schema
GET /api/catalog/tables/{table_id}/statistics
```

**Response (Schema):**
```json
{
  "table": "customers",
  "datasource": "CustomerDB",
  "columns": [
    {
      "name": "id",
      "type": "integer",
      "nullable": false,
      "primary_key": true,
      "indexed": true
    },
    {
      "name": "name",
      "type": "varchar(255)",
      "nullable": false,
      "indexed": false
    },
    {
      "name": "email",
      "type": "varchar(255)",
      "nullable": true,
      "indexed": true,
      "pii": true
    }
  ],
  "row_count": 50000,
  "size_mb": 8.5,
  "created_at": "2024-01-01T00:00:00Z"
}
```

---

## 7️⃣ OData Service APIs

### OData Metadata
```
GET /api/odata/$metadata
```

**Response:** CSDL (XML metadata for schema discovery)

```xml
<?xml version="1.0" encoding="utf-8"?>
<edmx:Edmx Version="4.0">
  <edmx:DataServices>
    <Schema Namespace="GraphTrace.OData">
      <EntityType Name="Customer">
        <Key>
          <PropertyRef Name="ID"/>
        </Key>
        <Property Name="ID" Type="Edm.Int32" Nullable="false"/>
        <Property Name="Name" Type="Edm.String"/>
        <Property Name="Email" Type="Edm.String"/>
      </EntityType>
      <EntityContainer Name="Container">
        <EntitySet Name="Customers" EntityType="GraphTrace.OData.Customer"/>
      </EntityContainer>
    </Schema>
  </edmx:DataServices>
</edmx:Edmx>
```

### OData Query
```
GET /api/odata/Customers
GET /api/odata/Customers?$filter=Status eq 'active'
GET /api/odata/Customers?$select=ID,Name,Email
GET /api/odata/Customers?$top=100&$skip=0
GET /api/odata/Customers?$orderby=Name asc
```

---

## 8️⃣ Analytics APIs

### Statistical Analysis
```
POST /api/analyze/statistics
Content-Type: application/json

{
  "datasource_id": "ds_001",
  "table": "customers",
  "column": "revenue",
  "metrics": ["min", "max", "mean", "median", "stddev", "percentiles"]
}
```

**Response:**
```json
{
  "column": "revenue",
  "statistics": {
    "count": 50000,
    "min": 0,
    "max": 1000000,
    "mean": 45000,
    "median": 32000,
    "stddev": 52000,
    "percentiles": {
      "25": 10000,
      "50": 32000,
      "75": 75000,
      "90": 120000,
      "95": 180000
    }
  }
}
```

---

### Distribution Analysis
```
POST /api/analyze/distribution
Content-Type: application/json

{
  "datasource_id": "ds_001",
  "table": "orders",
  "column": "status",
  "bucket_size": 10
}
```

**Response:**
```json
{
  "column": "status",
  "distribution": [
    {"value": "pending", "count": 15000, "percentage": 6.0},
    {"value": "completed", "count": 200000, "percentage": 80.0},
    {"value": "cancelled", "count": 35000, "percentage": 14.0}
  ]
}
```

---

## 9️⃣ File Operations APIs

### Upload File
```
POST /api/filesystem/upload
Content-Type: multipart/form-data

file: [Excel file content]
datasource_name: "ImportedData"
```

**Response:**
```json
{
  "file_id": "file_001",
  "filename": "customers.xlsx",
  "datasource_id": "ds_temp_001",
  "status": "uploaded",
  "row_count": 1000,
  "columns": ["id", "name", "email"]
}
```

---

### Read Excel File
```
GET /api/files/{file_id}/preview
GET /api/files/{file_id}/data?sheet=Sheet1&limit=100
```

**Response:**
```json
{
  "file_id": "file_001",
  "sheets": ["Sheet1", "Sheet2"],
  "data": [
    {"id": 1, "name": "John", "email": "john@example.com"},
    {"id": 2, "name": "Jane", "email": "jane@example.com"}
  ],
  "row_count": 1000
}
```

---

## 🔟 Health & Monitoring APIs

### Health Check
```
GET /health
```

**Response:**
```json
{
  "health": "ok",
  "db_ok": true,
  "neo4j_ok": false,
  "components": {
    "database": "connected",
    "cache": "connected",
    "search": "disconnected"
  },
  "timestamp": "2024-01-15T10:15:00Z"
}
```

---

### API Documentation
```
GET /docs                    # Interactive Swagger UI
GET /openapi.json           # OpenAPI 3.0 spec
```

---

## Common Power Query Patterns

### Pattern 1: Simple Get Request
```m
let
    Url = "http://localhost:8011/api/datasources",
    Response = Json.Document(Web.Contents(Url)),
    Data = if Type.Is(Response[data], type list)
           then Response[data]
           else error "Expected data array"
in
    Table.FromList(Data, Splitter.SplitByNothing())
```

### Pattern 2: POST Request
```m
let
    Url = "http://localhost:8011/api/data/quality/check",
    Body = Json.FromValue([
        datasource_id = "ds_001",
        table = "customers"
    ]),
    Response = Json.Document(Web.Contents(Url, [
        Headers = [#"Content-Type" = "application/json"],
        Content = Text.ToBinary(Body)
    ]))
in
    Response
```

### Pattern 3: Pagination
```m
let
    Url = "http://localhost:8011/api/datasources",
    FetchPage = (pageNum) => 
        let
            PageUrl = Url & "?offset=" & Text.From(pageNum * 100) & "&limit=100",
            Response = Json.Document(Web.Contents(PageUrl))
        in
            Response[data],
    AllPages = List.Generate(
        () => [page = 0, data = FetchPage(0), hasmore = true],
        each [hasmore] and List.Count([data]) = 100,
        each [
            page = [page] + 1,
            data = FetchPage([page]),
            hasmore = List.Count([data]) = 100
        ]
    ),
    Combined = Table.Combine(List.Transform(AllPages, (x) => Table.FromList(x[data], Splitter.SplitByNothing())))
in
    Combined
```

---

## Authentication (Optional)

If GraphTrace is configured with authentication:

```m
let
    ApiKey = "your-api-key-here",
    Url = "http://localhost:8011/api/datasources",
    Response = Json.Document(Web.Contents(Url, [
        Headers = [
            #"Authorization" = "Bearer " & ApiKey,
            #"Content-Type" = "application/json"
        ]
    ]))
in
    Response
```

---

## Error Codes

| Code | Meaning | Solution |
|------|---------|----------|
| 200 | OK | Success |
| 400 | Bad Request | Check parameters |
| 401 | Unauthorized | Check API key |
| 404 | Not Found | Check datasource_id |
| 429 | Rate Limited | Wait before retry |
| 500 | Server Error | Check GraphTrace logs |

---

## Tips

✅ **Always** include `Timeout` in Power Query to prevent hangs
✅ **Always** handle errors (Example: wrap in try-catch)
✅ **Always** test with `/health` first
✅ **Always** use error handling for production

❌ **Don't** hardcode URLs - use parameters instead
❌ **Don't** store API keys in Power Query files
❌ **Don't** request unlimited data - use `limit` parameter
