# Customer UAT Checklist — GoodpointAI

**Date:** April 11, 2026  
**Branch:** `docs-and-scripts-restructure`  
**Customer:** (TBD)  
**Test Environment:** (TBD)  
**Duration Estimate:** 5-7 business days

---

## Pre-UAT Setup

Before starting UAT, ensure the following are complete:

- [ ] Test environment provisioned (servers, Postgres, Neo4j, OpenSearch if needed)
- [ ] Database initialized (`python -m scripts.init_db_schema` ran successfully)
- [ ] All services started (`./graphtrace.ps1 -Start`)
- [ ] Frontend accessible at configured URL
- [ ] Backend API responding at `/health`
- [ ] Customer team has login credentials (if auth enabled)
- [ ] Test data prepared (sample PLM files, OData sources, etc.)

---

## Section 1: System Installation & Deployment

**Estimated Time:** 4-6 hours  
**Owner:** DevOps / Customer IT

| # | Test Case | Steps | Expected Result | Pass/Fail | Notes |
|---|-----------|-------|-----------------|-----------|-------|
| **1.1** | Clone and bootstrap | `git clone ...` → `./graphtrace.ps1 -Check` | All checks pass (Python, Node, Postgres, encryption key) | ☐ | |
| **1.2** | Virtual environment | Activate `.venv` → verify `pip list` shows backend deps | All dependencies listed (sqlalchemy, neo4j, etc.) | ☐ | |
| **1.3** | Database initialization | Run `python -m scripts.init_db_schema` | Schema created, seeding completes, no errors | ☐ | |
| **1.4** | Full-stack startup | `./graphtrace.ps1 -Start` | All services up, no crash in 5 minutes | ☐ | |
| **1.5** | Service health checks | GET `/health`, `/api/health`, `/api/llm/health` | All return 200 OK | ☐ | |
| **1.6** | Admin dashboard | Navigate to `http://localhost:5173/#/admin` | Page loads, no console errors | ☐ | |

---

## Section 2: Authentication & Authorization

**Estimated Time:** 2-3 hours  
**Owner:** Customer Security / QA

| # | Test Case | Steps | Expected Result | Pass/Fail | Notes |
|---|-----------|-------|-----------------|-----------|-------|
| **2.1** | Login with valid credentials | Enter username/password (or SSO if configured) | Redirect to dashboard, session token created | ☐ | |
| **2.2** | Login with invalid credentials | Enter wrong password | Error message shown, no access granted | ☐ | |
| **2.3** | Session expiration | Log in, wait 30 min without activity | Auto-logout, redirect to login | ☐ | |
| **2.4** | Admin role access | Log in as admin, navigate to Settings → Admin Panel | Admin features visible and functional | ☐ | |
| **2.5** | User role restrictions | Log in as non-admin user | Cannot access admin-only endpoints | ☐ | |
| **2.6** | Logout | Click logout button | Session cleared, redirected to login | ☐ | |

---

## Section 3: Data Source Integration

**Estimated Time:** 6-8 hours  
**Owner:** QA / Integration Specialist

### 3a. File System Data Source

| # | Test Case | Steps | Expected Result | Pass/Fail | Notes |
|---|-----------|-------|-----------------|-----------|-------|
| **3.1** | Add filesystem source | Create data source, select "Filesystem", point to folder | Source created, status "Active" | ☐ | |
| **3.2** | Discover schema | Run "Discover Schema" on filesystem source | Detects CSV/JSON/XML files, shows column names | ☐ | |
| **3.3** | Ingest small file | Ingest 100-row CSV file | File processed, rows visible in data preview | ☐ | |
| **3.4** | Ingest large file | Ingest 100k+ row CSV file | Processes without timeout, shows progress | ☐ | |
| **3.5** | File format support | Test CSV, JSON, XML, Excel | All formats recognized and parsed | ☐ | |

### 3b. Database Data Source

| # | Test Case | Steps | Expected Result | Pass/Fail | Notes |
|---|-----------|-------|-----------------|-----------|-------|
| **3.6** | Add database source | Create source, select "PostgreSQL", enter connection string | Source created, connection tested | ☐ | |
| **3.7** | Schema discovery | Run discover on database source | Tables and columns listed | ☐ | |
| **3.8** | Query execution | Execute SELECT query on source table | Results returned correctly | ☐ | |

### 3c. PLM Integration (if applicable)

| # | Test Case | Steps | Expected Result | Pass/Fail | Notes |
|---|-----------|-------|-----------------|-----------|-------|
| **3.9** | Add PLM source | Create source, select "Teamcenter"/"Windchill", enter credentials | Connection tested successfully | ☐ | |
| **3.10** | PLM sync | Run initial sync | Parts/documents imported, record count > 0 | ☐ | |

### 3d. OData Integration (if applicable)

| # | Test Case | Steps | Expected Result | Pass/Fail | Notes |
|---|-----------|-------|-----------------|-----------|-------|
| **3.11** | Add OData source | Create source, select "OData", enter service URL | Connection tested | ☐ | |
| **3.12** | OData query | Run query on OData source | Data retrieved, format correct | ☐ | |

---

## Section 4: Data Quality & Validation

**Estimated Time:** 4-6 hours  
**Owner:** QA / Data Steward

| # | Test Case | Steps | Expected Result | Pass/Fail | Notes |
|---|-----------|-------|-----------------|-----------|-------|
| **4.1** | Data Quality Dashboard | Navigate to Data Quality → Dashboard | Dashboard loads, shows metrics | ☐ | |
| **4.2** | Quality scan (completeness) | Run quality scan on ingested data | Completeness % calculated (null %, missing %) | ☐ | |
| **4.3** | Quality scan (uniqueness) | Check for duplicate rows | Duplicates identified, count reported | ☐ | |
| **4.4** | Quality scan (validity) | Check data type conformance | Invalid values flagged (e.g., non-numeric in numeric column) | ☐ | |
| **4.5** | Rule engine | Create custom validation rule | Rule applied during scan, violations reported | ☐ | |
| **4.6** | Cross-table referential integrity | Check foreign key relationships | Orphan records identified | ☐ | |
| **4.7** | Quality report export | Export quality report as PDF/CSV | File downloads, contains all metrics | ☐ | |

---

## Section 5: Data Pipelines & Transformation

**Estimated Time:** 8-10 hours  
**Owner:** QA / ETL Specialist

| # | Test Case | Steps | Expected Result | Pass/Fail | Notes |
|---|-----------|-------|-----------------|-----------|-------|
| **5.1** | Create simple pipeline | Pipeline Wizard → source → destination | Pipeline created, saved | ☐ | |
| **5.2** | Field mapping | Map source columns to target columns | Mapping rules saved | ☐ | |
| **5.3** | Data transformation | Apply transformation (e.g., uppercase, trim, concatenate) | Transformation correctly applied to test data | ☐ | |
| **5.4** | Filtering | Add WHERE clause (e.g., status = "Active") | Only matching records processed | ☐ | |
| **5.5** | Aggregation** | Add GROUP BY, SUM, COUNT | Aggregations correct | ☐ | |
| **5.6** | Pipeline execution | Run pipeline | Completes without errors, row counts match | ☐ | |
| **5.7** | Parallel execution | Run multiple pipelines concurrently | All complete without interference | ☐ | |
| **5.8** | Error handling | Run pipeline with bad data | Errors logged, partial success possible, clear error message | ☐ | |
| **5.9** | Pipeline scheduling | Set pipeline to run daily at 2 AM | Scheduling saved, runs at correct time | ☐ | |
| **5.10** | Pipeline history/logs | View past pipeline runs | Execution history and logs visible | ☐ | |

---

## Section 6: Data Lineage & Visualization

**Estimated Time:** 3-4 hours  
**Owner:** QA / Business Analyst

| # | Test Case | Steps | Expected Result | Pass/Fail | Notes |
|---|-----------|-------|-----------------|-----------|-------|
| **6.1** | Lineage visualization | Open lineage viewer, select workflow | Lineage graph displays, shows source → transform → target | ☐ | |
| **6.2** | Node details | Click on lineage node | Shows metadata (column name, data type, record count) | ☐ | |
| **6.3** | Impact analysis | Select a transformation node, check downstream impact | Downstream dependencies highlighted | ☐ | |
| **6.4** | Lineage export | Export lineage diagram as image/PDF | File downloads, quality acceptable | ☐ | |
| **6.5** | Neo4j graph | Query Neo4j directly for relationships | Relationships match lineage view | ☐ | If Neo4j enabled |

---

## Section 7: Analytics & Reporting

**Estimated Time:** 4-5 hours  
**Owner:** QA / Business Analyst

| # | Test Case | Steps | Expected Result | Pass/Fail | Notes |
|---|-----------|-------|-----------------|-----------|-------|
| **7.1** | SQL Query Builder | Write SQL query via UI | Query executes, results display | ☐ | |
| **7.2** | SQL Query performance | Run complex query with large dataset | Completes in < 30 seconds | ☐ | |
| **7.3** | GraphQL query | Execute GraphQL query (if available) | Results match SQL results | ☐ | |
| **7.4** | Natural Language Query (NLQ)** | Ask "Show me workflows from last 30 days" | System generates and executes query, shows results | ☐ | If LLM configured |
| **7.5** | Dashboard creation | Create custom dashboard with widgets | Dashboard saves, displays data correctly | ☐ | |
| **7.6** | Report generation | Generate PDF report | PDF downloads, contains all requested data | ☐ | |
| **7.7** | Export to Excel | Export query results to Excel | Excel file downloads, data formatted correctly | ☐ | |

---

## Section 8: Search & Filtering

**Estimated Time:** 2-3 hours  
**Owner:** QA

| # | Test Case | Steps | Expected Result | Pass/Fail | Notes |
|---|-----------|-------|-----------------|-----------|-------|
| **8.1** | Full-text search | Search for keyword in data | Matching records returned | ☐ | |
| **8.2** | Filter by column** | Filter records by status/date/category | Only matching records shown | ☐ | |
| **8.3** | Multi-filter | Apply 3+ filters simultaneously | All filters applied correctly | ☐ | |
| **8.4** | Save search** | Save filter criteria | Search can be re-run without re-entering criteria | ☐ | |
| **8.5** | Vector search (if enabled) | Semantic search for similar documents | Relevant results returned | ☐ | If OpenSearch enabled |

---

## Section 9: Configuration Management

**Estimated Time:** 3-4 hours  
**Owner:** DevOps / System Admin

| # | Test Case | Steps | Expected Result | Pass/Fail | Notes |
|---|-----------|-------|-----------------|-----------|-------|
| **9.1** | Admin panel access | Navigate to Settings → Admin | Admin panel loads, no permission errors | ☐ | |
| **9.2** | LLM provider config | Configure OpenAI API key | Configuration saved securely (encrypted in DB) | ☐ | |
| **9.3** | Neo4j config | Configure Neo4j connection | Connection tested, status shows "Connected" | ☐ | |
| **9.4** | Encryption key management | View/rotate encryption key | Key operations secure, no exposure in logs | ☐ | |
| **9.5** | CORS configuration | Set allowed origins | Requests from configured origins allowed, others blocked | ☐ | |
| **9.6** | Rate limiting | Set API rate limit to 10/min, test with 15 requests | 11th request blocked, proper error returned | ☐ | |

---

## Section 10: Performance & Load Testing

**Estimated Time:** 4-6 hours  
**Owner:** QA / Performance Engineer

| # | Test Case | Steps | Expected Result | Pass/Fail | Notes |
|---|-----------|-------|-----------------|-----------|-------|
| **10.1** | API response time (healthy load) | Run 10 concurrent API requests | All complete in < 2 seconds | ☐ | |
| **10.2** | API response time (heavy load) | Run 100 concurrent API requests | 95% complete in < 5 seconds, no 500 errors | ☐ | |
| **10.3** | Large file ingestion | Ingest 500MB+ file | Completes without timeout, memory usage reasonable | ☐ | |
| **10.4** | Query on large dataset** | Query 10M+ rows | Completes in < 30 seconds with pagination | ☐ | |
| **10.5** | Concurrent pipeline execution | Run 5 pipelines simultaneously | All complete without deadlocks or data corruption | ☐ | |
| **10.6** | Memory usage** | Monitor memory during peak operations | Usage stays < 80% of available | ☐ | |
| **10.7** | CPU usage** | Monitor CPU during peak operations | Usage stays < 80% of available | ☐ | |

---

## Section 11: Disaster Recovery & Backup

**Estimated Time:** 2-3 hours  
**Owner:** DevOps / System Admin

| # | Test Case | Steps | Expected Result | Pass/Fail | Notes |
|---|-----------|-------|-----------------|-----------|-------|
| **11.1** | Database backup | Run backup script | Backup file created, size > 0 | ☐ | |
| **11.2** | Database restore | Restore from backup file | Data restored completely, no corruption | ☐ | |
| **11.3** | Configuration backup | Export configuration | Config file downloads, all settings present | ☐ | |
| **11.4** | Configuration restore | Restore from config file | Settings restored, system operational | ☐ | |

---

## Section 12: Security & Compliance

**Estimated Time:** 3-4 hours  
**Owner:** Customer Security / QA

| # | Test Case | Steps | Expected Result | Pass/Fail | Notes |
|---|-----------|-------|-----------------|-----------|-------|
| **12.1** | SQL injection prevention | Enter SQL payload in search box | Payload escaped, no SQL injection, safe message shown | ☐ | |
| **12.2** | XSS prevention | Enter JavaScript in text field | Script not executed, displayed as text | ☐ | |
| **12.3** | CSRF protection | Try POST without CSRF token | Request rejected with 403 Forbidden | ☐ | |
| **12.4** | Password security | Check password policy (length, complexity) | Policy enforced, weak passwords rejected | ☐ | |
| **12.5** | Secrets in logs | Search logs for passwords/API keys | No secrets found in application logs | ☐ | |
| **12.6** | HTTPS enforcement (prod) | Access system via HTTP | Redirects to HTTPS or refused | ☐ | If HTTPS configured |
| **12.7** | Audit logging | Perform action (create/delete/update) | Action logged with user, timestamp, details | ☐ | |
| **12.8** | Data encryption at rest | Verify DB-backed config is encrypted | Ciphertext in DB, decrypts correctly | ☐ | |

---

## Section 13: Integrations & Extensibility

**Estimated Time:** 3-5 hours  
**Owner:** Customer / Integration Specialist

| # | Test Case | Steps | Expected Result | Pass/Fail | Notes |
|---|-----------|-------|-----------------|-----------|-------|
| **13.1** | REST API availability | Check `/docs` (Swagger) | API documentation loads, all endpoints listed | ☐ | |
| **13.2** | GraphQL API** | Query `/graphql` with sample query | Results returned | ☐ | If GraphQL enabled |
| **13.3** | Webhook delivery** | Configure webhook, trigger event | Webhook called at configured URL | ☐ | If webhooks enabled |
| **13.4** | Custom agent registration** | Register custom agent service | Agent appears in agents list, can accept tasks | ☐ | If agents enabled |
| **13.5** | Third-party plugin** | Install/enable third-party extension | Plugin loads, functions work | ☐ | If applicable |

---

## Section 14: Documentation & Support

**Estimated Time:** 2-3 hours  
**Owner:** QA / Customer Success

| # | Test Case | Steps | Expected Result | Pass/Fail | Notes |
|---|-----------|-------|-----------------|-----------|-------|
| **14.1** | Installation guide accuracy | Follow docs step-by-step | System installs and runs successfully | ☐ | |
| **14.2** | User guide completeness | Find answers to 5 common questions in docs | All answers clear and correct | ☐ | |
| **14.3** | API documentation** | Use Swagger docs to make API call | Call succeeds with expected response | ☐ | |
| **14.4** | Troubleshooting guide** | Follow troubleshooting steps for common error | Issue resolved | ☐ | |
| **14.5** | Video tutorials (if available)** | Follow tutorial walkthrough | Tutorial is clear, system behaves as shown | ☐ | Optional |

---

## Section 15: Browser Compatibility

**Estimated Time:** 1-2 hours  
**Owner:** QA

| # | Test Case | Steps | Expected Result | Pass/Fail | Notes |
|---|-----------|-------|-----------------|-----------|-------|
| **15.1** | Chrome** | Open app in Chrome 120+, navigate | All features work, no console errors | ☐ | |
| **15.2** | Firefox** | Open app in Firefox 121+, navigate | All features work, no console errors | ☐ | |
| **15.3** | Safari** | Open app in Safari 17+, navigate | All features work, no console errors | ☐ | |
| **15.4** | Edge** | Open app in Edge 121+, navigate | All features work, no console errors | ☐ | |
| **15.5** | Mobile (optional)** | Open app on tablet/phone | Responsive, navigable (if responsive design supported) | ☐ | Optional |

---

## Regression Testing

**Estimated Time:** 3-4 hours  
**Owner:** QA

After all main features are tested, run regression tests on:

| Area | Test | Pass/Fail |
|------|------|-----------|
| **Data pipeline** | Run same pipeline 3x, verify consistent results | ☐ |
| **API endpoints** | Call same API endpoint 10x, all return 200 OK | ☐ |
| **Dashboard** | Refresh dashboard 5x, no data inconsistencies | ☐ |
| **Search/Filter** | Search for same term after 2 restarts, results consistent | ☐ |

---

## Sign-Off & Approval

### UAT Summary

| Metric | Target | Actual | Status |
|--------|--------|--------|--------|
| **Pass Rate** | 100% | ___ % | ☐ |
| **Critical Bugs** | 0 | ___  | ☐ |
| **High Bugs** | 0-2 | ___  | ☐ |
| **Duration** | 5-7 days | ___ days | ☐ |

### Issues Found

| ID | Severity | Component | Description | Resolution | Status |
|----|----------|-----------|-------------|-----------|--------|
| 1 | | | | | ☐ |
| 2 | | | | | ☐ |
| 3 | | | | | ☐ |

---

## Sign-Off

| Role | Name | Organization | Date | Signature | Status |
|------|------|--------------|------|-----------|--------|
| **QA Lead** | | | | | ☐ Approved |
| **Customer** | | | | | ☐ Approved |
| **Product Owner** | | | | | ☐ Approved |

---

## Go/No-Go Decision

**Date:** ___________  
**Decision:** ☐ **GO** (Ready for Production) / ☐ **NO-GO** (Issues Must Be Resolved)  
**Comments:** 

---

## Post-Deployment

After deployment, monitor:
- [ ] Error logs clean (no 500 errors)
- [ ] Performance metrics normal
- [ ] Users can log in and access features
- [ ] No database corruption
- [ ] Scheduled jobs running on time

**Contact for Support:** (TBD)  
**SLA Response Time:** (TBD)
