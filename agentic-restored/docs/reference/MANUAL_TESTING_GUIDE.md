# Manual End-to-End Testing Guide
## PLM Data Integration & UI/UX Verification

**Test Data Location**: 
```
D:\FileHistory\Paritosh\DESKTOP-6V68C8J\Data\D\graphdb\DesktopDB\relate-data\dbmss\dbms-319603fc-d69d-4cf5-b4a4-9fbb86278426\import\SPLM
```

**Contents**: Induction Motor Assembly PLM data
- 50+ files including STEP CAD files (.stp), XML metadata, assembly logs
- Parts: Bearings, Stator Core, Fan, Rotor Shaft, Terminal Box, etc.
- Assembly: INDUCTION MOTOR ASSEMBLY 5HP

---

## Prerequisites Checklist

Before testing, ensure these services are running:

| Service | Port | Status Command |
|---------|------|----------------|
| PostgreSQL | 5433 | `Test-NetConnection localhost -Port 5433` |
| Neo4j | 7687 | `Test-NetConnection localhost -Port 7687` |
| Backend API | 8011 | `Invoke-WebRequest http://localhost:8011/health` |
| Frontend | 5173 | `Invoke-WebRequest http://localhost:5173` |

---

## Phase 1: Start Services

### Step 1.1: Start Backend Server
```powershell
cd D:\Download\graphTrace-feature-xstate-agentic-integration\agentic-restored\python_backend
python -m uvicorn main:app --host 0.0.0.0 --port 8011 --reload
```

**Expected**: Server starts with no errors, shows "Uvicorn running on http://0.0.0.0:8011"

### Step 1.2: Start Frontend Server
```powershell
cd D:\Download\graphTrace-feature-xstate-agentic-integration\agentic-restored\e2etraceapp
npm run dev -- --host 127.0.0.1 --port 5173
```

**Expected**: Vite server starts, shows "Local: http://127.0.0.1:5173/"

### Step 1.3: Verify Health Endpoints
```powershell
# Backend health
Invoke-WebRequest http://localhost:8011/health -UseBasicParsing | Select-Object StatusCode

# API docs available
Start-Process "http://localhost:8011/docs"
```

---

## Phase 2: Admin Configuration Testing (NEW)

### Step 2.1: Open Admin Configuration Panel
**URL**: http://127.0.0.1:5173/#/admin

**Expected UI Elements**:
- [ ] Header: "⚙️ Admin Configuration Center"
- [ ] 5 Tabs: LLM Providers, Embedding Models, Connections, System Settings, Feature Flags
- [ ] Health Overview section
- [ ] Footer with "Refresh Data" and "Clear Config Cache" buttons

### Step 2.2: Test LLM Providers Tab
1. Click "LLM Providers" tab
2. Click "➕ Add Provider" button
3. Fill form:
   - Provider: OpenAI
   - Display Name: "OpenAI GPT-4"
   - API Key: (your key or test value)
   - Default Chat Model: gpt-4-turbo-preview
   - Status: Active
4. Click Save

**Expected**:
- [ ] New provider card appears
- [ ] Status badge shows "active"
- [ ] API key is masked (shows ****...)

### Step 2.3: Test Connections Tab
1. Click "Connections" tab
2. Verify existing connections display
3. Click "Test Connection" (🔌) on PostgreSQL connection

**Expected**:
- [ ] Connection cards show host:port
- [ ] Test button triggers connection test
- [ ] Status updates to healthy/failed

### Step 2.4: Test Feature Flags Tab
1. Click "Feature Flags" tab
2. Toggle a feature flag switch

**Expected**:
- [ ] Toggle animation works
- [ ] Flag state persists on refresh

### Step 2.5: Test Cache Invalidation
1. Click "🗑️ Clear Config Cache" button

**Expected**:
- [ ] Alert shows "Configuration cache cleared successfully"

---

## Phase 3: File System Integration Testing

### Step 3.1: Test File System Health
```powershell
$response = Invoke-WebRequest -Uri "http://localhost:8011/api/filesystem/health" -UseBasicParsing
$response.Content | ConvertFrom-Json | Format-List
```

**Expected**: Returns health status with directory info

### Step 3.2: List PLM Test Data Directory
```powershell
$testPath = "D:\FileHistory\Paritosh\DESKTOP-6V68C8J\Data\D\graphdb\DesktopDB\relate-data\dbmss\dbms-319603fc-d69d-4cf5-b4a4-9fbb86278426\import\SPLM"
$body = @{ path = $testPath } | ConvertTo-Json
$response = Invoke-WebRequest -Uri "http://localhost:8011/api/filesystem/list" -Method POST -Body $body -ContentType "application/json" -UseBasicParsing
$response.Content | ConvertFrom-Json | Select-Object -First 10
```

**Expected**: List of 50+ files with names, sizes, extensions

### Step 3.3: Parse XML Metadata File
```powershell
$xmlFile = "D:\FileHistory\Paritosh\DESKTOP-6V68C8J\Data\D\graphdb\DesktopDB\relate-data\dbmss\dbms-319603fc-d69d-4cf5-b4a4-9fbb86278426\import\SPLM\000687_A_1-INDUCTIONMOTORASSY5 (2023_02_05 08_36_29 UTC).xml"
$body = @{ file_path = $xmlFile } | ConvertTo-Json
$response = Invoke-WebRequest -Uri "http://localhost:8011/api/filesystem/xml/parse" -Method POST -Body $body -ContentType "application/json" -UseBasicParsing
$response.Content | ConvertFrom-Json
```

**Expected**: Parsed XML structure with PLM metadata

---

## Phase 4: PLM ETL Pipeline Testing

### Step 4.1: Create New ETL Run
```powershell
$body = @{
    name = "Induction Motor PLM Import"
    description = "Testing PLM data import from SPLM directory"
    source_type = "filesystem"
    source_path = "D:\FileHistory\Paritosh\DESKTOP-6V68C8J\Data\D\graphdb\DesktopDB\relate-data\dbmss\dbms-319603fc-d69d-4cf5-b4a4-9fbb86278426\import\SPLM"
} | ConvertTo-Json

$response = Invoke-WebRequest -Uri "http://localhost:8011/api/plm/etl/runs" -Method POST -Body $body -ContentType "application/json" -UseBasicParsing
$run = $response.Content | ConvertFrom-Json
$runId = $run.run_id
Write-Host "Created Run ID: $runId"
```

**Expected**: Returns `run_id` (UUID), status "created"

### Step 4.2: Stage PLM Data
```powershell
# Use the run_id from Step 4.1
$body = @{
    file_patterns = @("*.xml", "*.stp")
    extract_metadata = $true
} | ConvertTo-Json

$response = Invoke-WebRequest -Uri "http://localhost:8011/api/plm/etl/runs/$runId/stage" -Method POST -Body $body -ContentType "application/json" -UseBasicParsing
$response.Content | ConvertFrom-Json
```

**Expected**: Returns staged record count, file list

### Step 4.3: Transform PLM Data
```powershell
$body = @{
    mapping_rules = @{
        part_number = "ItemId"
        part_name = "ItemName"
        revision = "ItemRevision"
    }
} | ConvertTo-Json

$response = Invoke-WebRequest -Uri "http://localhost:8011/api/plm/etl/runs/$runId/transform" -Method POST -Body $body -ContentType "application/json" -UseBasicParsing
$response.Content | ConvertFrom-Json
```

**Expected**: Returns transformed record count, mapping summary

### Step 4.4: Validate PLM Data
```powershell
$response = Invoke-WebRequest -Uri "http://localhost:8011/api/plm/etl/runs/$runId/validate" -Method POST -ContentType "application/json" -UseBasicParsing
$response.Content | ConvertFrom-Json
```

**Expected**: Validation results with pass/fail counts

### Step 4.5: Get ETL Run Results
```powershell
$response = Invoke-WebRequest -Uri "http://localhost:8011/api/plm/etl/runs/$runId/results" -UseBasicParsing
$response.Content | ConvertFrom-Json | Format-List
```

**Expected**: Complete run summary with all stages

---

## Phase 5: Data Quality Testing

### Step 5.1: Run Data Quality Scan
```powershell
$body = @{
    data_source = "D:\FileHistory\Paritosh\DESKTOP-6V68C8J\Data\D\graphdb\DesktopDB\relate-data\dbmss\dbms-319603fc-d69d-4cf5-b4a4-9fbb86278426\import\SPLM"
} | ConvertTo-Json

$response = Invoke-WebRequest -Uri "http://localhost:8011/api/analytics/quality/scan/plm_parts" -Method POST -Body $body -ContentType "application/json" -UseBasicParsing
$scan = $response.Content | ConvertFrom-Json
$scanId = $scan.scan_id
Write-Host "Scan ID: $scanId"
```

**Expected**: Returns scan_id, initial metrics

### Step 5.2: Get Quality Report
```powershell
$response = Invoke-WebRequest -Uri "http://localhost:8011/api/analytics/quality/reports/$scanId" -UseBasicParsing
$response.Content | ConvertFrom-Json | Format-List
```

**Expected**: Quality report with metrics, issues list

---

## Phase 6: Search & Retrieval Testing

### Step 6.1: Test Search Configuration
```powershell
$response = Invoke-WebRequest -Uri "http://localhost:8011/api/search/config" -UseBasicParsing
$response.Content | ConvertFrom-Json | Format-List
```

**Expected**: Shows available search modes (semantic, vector, hybrid)

### Step 6.2: Test Hybrid Search
```powershell
$body = @{
    query = "Induction Motor bearing assembly"
    mode = "hybrid"
    top_k = 10
} | ConvertTo-Json

$response = Invoke-WebRequest -Uri "http://localhost:8011/api/search/query" -Method POST -Body $body -ContentType "application/json" -UseBasicParsing
$response.Content | ConvertFrom-Json | Format-List
```

**Expected**: Search results with relevance scores

### Step 6.3: Test Semantic Search
```powershell
$body = @{
    query = "SKF bearing part number"
    mode = "semantic"
    top_k = 5
} | ConvertTo-Json

$response = Invoke-WebRequest -Uri "http://localhost:8011/api/search/query" -Method POST -Body $body -ContentType "application/json" -UseBasicParsing
$response.Content | ConvertFrom-Json
```

---

## Phase 7: Neo4j Graph Sync Testing

### Step 7.1: Trigger Neo4j Sync (requires completed ETL run)
```powershell
# Use run_id from Phase 4
$response = Invoke-WebRequest -Uri "http://localhost:8011/api/plm/etl/runs/$runId/sync/neo4j" -Method POST -ContentType "application/json" -UseBasicParsing
$job = $response.Content | ConvertFrom-Json
$jobId = $job.job_id
Write-Host "Sync Job ID: $jobId"
```

**Expected**: Returns job_id for tracking

### Step 7.2: Check Sync Job Status
```powershell
$response = Invoke-WebRequest -Uri "http://localhost:8011/api/plm/etl/sync/neo4j/jobs/$jobId" -UseBasicParsing
$response.Content | ConvertFrom-Json | Format-List
```

**Expected**: Job status (pending/running/completed/failed)

---

## Phase 8: UI/UX End-to-End Testing

### Step 8.1: Data Lineage Page
**URL**: http://127.0.0.1:5173/#/data-lineage

**Test Actions**:
1. [ ] Page loads without errors
2. [ ] Can see lineage graph visualization
3. [ ] Can click on nodes to see details
4. [ ] Search/filter works

### Step 8.2: ETL Pipeline Page
**URL**: http://127.0.0.1:5173/#/etl-pipeline (or equivalent)

**Test Actions**:
1. [ ] Can create new ETL run
2. [ ] Can browse to SPLM directory
3. [ ] Progress indicators update
4. [ ] Results display correctly

### Step 8.3: Data Quality Dashboard
**URL**: http://127.0.0.1:5173/#/data-quality (or equivalent)

**Test Actions**:
1. [ ] Dashboard shows scan history
2. [ ] Can drill into quality reports
3. [ ] Charts/visualizations render

### Step 8.4: XState Visualizer
**URL**: http://127.0.0.1:5173/#/xstate-visualizer

**Test Actions**:
1. [ ] State machine diagram renders
2. [ ] Can select different machines
3. [ ] Transitions animate correctly
4. [ ] History timeline works

---

## Phase 9: Integration Health Verification

### Step 9.1: Check All Integration Health
```powershell
# LLM Health
Invoke-WebRequest -Uri "http://localhost:8011/api/llm/health" -UseBasicParsing | % { $_.Content }

# Neo4j Health  
Invoke-WebRequest -Uri "http://localhost:8011/api/neo4j/health" -UseBasicParsing | % { $_.Content }

# Admin Config Health
Invoke-WebRequest -Uri "http://localhost:8011/api/admin/config/health" -UseBasicParsing | % { $_.Content }
```

### Step 9.2: Verify Database Tables Created
```powershell
# Check if admin config tables exist
$body = @{
    query = "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' AND table_name LIKE '%config%'"
} | ConvertTo-Json

# This requires a direct DB query endpoint or psql
```

---

## Test Results Checklist

### Backend API Tests
| Test | Status | Notes |
|------|--------|-------|
| Backend starts | ⬜ | |
| Health endpoint | ⬜ | |
| File system list | ⬜ | |
| XML parse | ⬜ | |
| ETL run create | ⬜ | |
| ETL stage | ⬜ | |
| ETL transform | ⬜ | |
| ETL validate | ⬜ | |
| Quality scan | ⬜ | |
| Search query | ⬜ | |
| Neo4j sync | ⬜ | |
| Admin config CRUD | ⬜ | |

### UI/UX Tests
| Test | Status | Notes |
|------|--------|-------|
| Frontend starts | ⬜ | |
| Admin panel loads | ⬜ | |
| LLM config works | ⬜ | |
| Connections work | ⬜ | |
| Feature flags work | ⬜ | |
| Data lineage page | ⬜ | |
| ETL pipeline page | ⬜ | |
| Quality dashboard | ⬜ | |
| XState visualizer | ⬜ | |

---

## Troubleshooting

### Common Issues

1. **Backend won't start**
   - Check Python environment: `python --version`
   - Check dependencies: `pip install -r requirements.txt`
   - Check port not in use: `netstat -ano | findstr :8011`

2. **Database connection failed**
   - Verify PostgreSQL running on port 5433
   - Check `.env` file for correct credentials

3. **Admin config not loading**
   - Run seed script: `python scripts/seed_admin_configs.py`
   - Check database tables exist

4. **File not found errors**
   - Verify test data path exists
   - Check path escaping in JSON (use forward slashes or double backslashes)

5. **Neo4j sync fails**
   - Verify Neo4j running on port 7687
   - Check credentials in admin config or `.env`
