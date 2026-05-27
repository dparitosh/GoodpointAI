# Manual UI Testing Guide - GoodPoint AgenticAI

## Services Status

| Service | URL | Status |
|---------|-----|--------|
| **Frontend** | http://localhost:5173 | ✅ Running |
| **Backend API** | http://localhost:8011 | ✅ Running |
| **API Docs** | http://localhost:8011/docs | ✅ Available |
| **Database** | PostgreSQL 5433 | ✅ Connected |

## Test Procedures

### 1. **Home Page / Dashboard**
**Steps:**
1. Open http://localhost:5173 in your browser
2. Verify the page loads without flickering
3. Check that graphs/charts render properly
4. Verify no console errors (F12 → Console tab)

**Expected Results:**
- ✅ Page loads smoothly in <3 seconds
- ✅ No excessive re-renders or flickering
- ✅ Graphs/visualizations visible
- ✅ No errors in console

---

### 2. **Admin Configuration Manager**
**Steps:**
1. Click "Admin Config" button/menu item
2. Wait for page to load completely
3. Verify all tabs are visible: LLM Providers, Embedding Models, Connections, System Settings, Feature Flags
4. Switch between tabs to ensure data loads properly

**Expected Results:**
- ✅ Page loads **without flickering** (FIXED!)
- ✅ All tabs populate with configuration data
- ✅ No "too many requests" errors
- ✅ Tab switching is smooth and responsive

**Test Features:**
- Add new configuration (click "Add" buttons)
- Edit existing configuration (click edit icon)
- Test connection (click "Test" button)
- Delete configuration (click delete icon)
- Toggle feature flags

---

### 3. **Data Source Management**
**Steps:**
1. Navigate to Connections/Data Sources section
2. Add a new data source:
   - Click "Add Connection"
   - Fill in connection details (varies by type)
   - Click "Test Connection"
   - Save configuration

**Expected Results:**
- ✅ Form submits without errors
- ✅ Connection test executes properly
- ✅ Configurations saved and displayed in table

---

### 4. **Graph Visualization (E2E Trace)**
**Steps:**
1. Navigate to trace graph view (if available)
2. Interact with graph:
   - Pan/drag the view
   - Zoom in/out
   - Click on nodes
   - Expand/collapse relationships

**Expected Results:**
- ✅ Graph renders without flickering
- ✅ Interactions are smooth and responsive
- ✅ No excessive API calls (monitor Network tab)

---

### 5. **API Health Check**
**Steps:**
1. Open http://localhost:8011/health in browser
2. Observe response:
```json
{
  "status": "degraded",
  "service": "GoodPoint AgenticAI API",
  "timestamp": "...",
  "dependencies": {
    "postgres": {
      "ok": true
    },
    "neo4j": {
      "ok": false
    }
  }
}
```

**Expected Results:**
- ✅ PostgreSQL dependency: `"ok": true` (required)
- ✅ Neo4j dependency: `"ok": false` (optional, expected)
- ✅ Status: "degraded" (due to missing Neo4j, normal)

---

### 6. **Browser Developer Tools Checks**

**Console Tab (F12):**
- ❌ Should have NO errors (red messages)
- ✅ Warnings are acceptable (yellow messages)
- Look for excessive network requests

**Network Tab (F12):**
1. Clear Network logs
2. Perform a UI action (e.g., navigate to Admin Config)
3. Monitor API calls:
   - Should see **specific requests** for needed data
   - NOT see **repeated identical requests** (that's the flickering issue)
   - All requests should return 200/201/204 or gracefully handle errors

**Performance Tab (F12):**
1. Record a time period while using the app
2. Check for:
   - ✅ Smooth FPS (60 FPS ideal, minimum 30 FPS)
   - ❌ Long tasks or jank
   - ❌ Excessive re-renders

---

## Common Issues & Solutions

### Issue: "Too Many Requests" (HTTP 429)
**Causes:**
- Backend rate limiter engaged
- Excessive API calls from frontend

**Solutions:**
- Verify fixes were applied:
  - `e2etrace-use-graph-data.js` dependency array: `[]`
  - `admin-config-manager/index.jsx` dependency: `[api.fetchData]`
- Refresh browser (Ctrl+Shift+R hard refresh)
- Clear browser cache

### Issue: Flickering When Loading Admin Config
**Status:** ✅ FIXED in commit `a7cc42e`

### Issue: Screen Flickering on Graph View
**Status:** ✅ FIXED in commit `138581b`

### Issue: Page Takes >5 seconds to Load
**Debug:**
1. Open Network tab (F12)
2. Check which API endpoint is slow
3. Test endpoint directly: `curl http://localhost:8011/api/admin/config/llm-providers`

---

## Automated Test Results

### Vitest Suite (Frontend)
```
Test Files:  1 passed (1)
Tests:       1 passed (1)
Duration:    29.27s
Status:      ✅ PASS
```

### Smoke Test (Backend)
```
Health Check:        ✅ PASS
PostgreSQL:          ✅ PASS
Neo4j:               ⚠️  SKIPPED (optional)
Query Builders:      ⚠️  WARNINGS (rate limiting)
Reports & Queries:   ⚠️  WARNINGS (rate limiting)
```

---

## Sign-Off Checklist

- [ ] Frontend loads without errors
- [ ] Admin Config page loads without flickering
- [ ] All tabs accessible and populated
- [ ] Configuration CRUD operations work
- [ ] No excessive API requests in Network tab
- [ ] Console shows no critical errors
- [ ] Graph visualizations render smoothly
- [ ] Backend health check returns postgres=true
- [ ] Refresh/reload doesn't cause flickering

---

## Additional Resources

- **Frontend Source:** `agentic-restored/e2etraceapp/src/`
- **Backend Source:** `agentic-restored/python_backend/`
- **API Documentation:** http://localhost:8011/docs
- **Test Files:** `agentic-restored/e2etraceapp/tests/`
- **Recent Fixes:** See commits 138581b and a7cc42e

---

**Testing completed:** May 27, 2026  
**Frontend:** Running  
**Backend:** Running  
**Database:** Connected
