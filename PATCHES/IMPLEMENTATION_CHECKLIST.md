# DETAILED IMPLEMENTATION CHECKLIST
## Exact Code Changes Required

---

## FILE 1: Backend Seed Script
**Path**: `agentic-restored/python_backend/scripts/seed_admin_configs.py`

### CHANGE 1.1: Add REST API Connection Templates

**Location**: After line 376 (after soda_external_runner connection definition)

**Find this code**:
```python
        {
            "id": "soda_external_runner",
            "connection_type": "soda_external",
            "name": "Soda External Runner",
            "description": "External Python interpreter used to run Soda scans (e.g., Python 3.11 venv)",
            "extra_options": {
                "python_path": soda_python or None,
                "timeout_s": soda_timeout_s,
            },
            "status": "active" if soda_python else "inactive",
            "is_default": True,
        }
    ]
    
    created_count = 0
```

**Replace with**:
```python
        {
            "id": "soda_external_runner",
            "connection_type": "soda_external",
            "name": "Soda External Runner",
            "description": "External Python interpreter used to run Soda scans (e.g., Python 3.11 venv)",
            "extra_options": {
                "python_path": soda_python or None,
                "timeout_s": soda_timeout_s,
            },
            "status": "active" if soda_python else "inactive",
            "is_default": True,
        },
        # REST API Connection Templates
        {
            "id": "generic_rest_api",
            "connection_type": "rest_api",
            "name": "Generic REST API Template",
            "description": "Template for connecting to generic REST API services",
            "connection_string": "https://api.example.com/v1",
            "extra_options": {
                "auth_type": "none",
                "test_path": "/health",
                "timeout_s": 10.0,
                "headers_json": "{}"
            },
            "status": "inactive",
            "is_default": False
        },
        {
            "id": "salesforce_api",
            "connection_type": "rest_api",
            "name": "Salesforce REST API",
            "description": "Salesforce REST API with Bearer token authentication",
            "connection_string": "https://yourdomain.salesforce.com/services/data/v59.0",
            "extra_options": {
                "auth_type": "bearer",
                "test_path": "/sobjects",
                "timeout_s": 15.0,
                "headers_json": "{\"Sforce-Call-Options\": \"client=MyApp\"}"
            },
            "status": "inactive",
            "is_default": False
        },
        {
            "id": "custom_api_key",
            "connection_type": "api",
            "name": "Custom API with API Key",
            "description": "Template for APIs using API Key authentication",
            "connection_string": "https://api.yourservice.com",
            "extra_options": {
                "auth_type": "api_key",
                "api_key_header": "X-API-Key",
                "test_path": "/api/health",
                "timeout_s": 10.0,
                "headers_json": "{}"
            },
            "status": "inactive",
            "is_default": False
        },
        {
            "id": "openapi_service",
            "connection_type": "openapi",
            "name": "OpenAPI/Swagger Service",
            "description": "OpenAPI specification endpoint (auto-discovers /openapi.json)",
            "connection_string": "https://api.example.com",
            "extra_options": {
                "auth_type": "none",
                "test_path": "/openapi.json",
                "timeout_s": 10.0,
                "headers_json": "{}"
            },
            "status": "inactive",
            "is_default": False
        },
        {
            "id": "odata_service",
            "connection_type": "odata",
            "name": "OData Service",
            "description": "OData protocol endpoint (auto-discovers /$metadata)",
            "connection_string": "https://services.odata.org/V4/Northwind",
            "extra_options": {
                "auth_type": "none",
                "test_path": "/$metadata",
                "timeout_s": 10.0,
                "headers_json": "{}"
            },
            "status": "inactive",
            "is_default": False
        },
        {
            "id": "oauth2_service",
            "connection_type": "rest_api",
            "name": "OAuth2 Protected API",
            "description": "REST API with OAuth2 bearer token",
            "connection_string": "https://api.oauth.example.com/v2",
            "extra_options": {
                "auth_type": "oauth2",
                "test_path": "/api/user",
                "timeout_s": 15.0,
                "headers_json": "{}"
            },
            "status": "inactive",
            "is_default": False
        },
        {
            "id": "basic_auth_api",
            "connection_type": "webapi",
            "name": "Web API with Basic Auth",
            "description": "Web API using Basic (username/password) authentication",
            "connection_string": "https://api.basicauth.example.com",
            "extra_options": {
                "auth_type": "basic",
                "test_path": "/api/status",
                "timeout_s": 10.0,
                "headers_json": "{}"
            },
            "status": "inactive",
            "is_default": False
        },
    ]
    
    created_count = 0
```

### CHANGE 1.2: Update Logging (line ~404)

**Find this**:
```python
    db.commit()
    logger.info(f"Created {created_count} connection configurations")
```

**Replace with**:
```python
    db.commit()
    logger.info(f"Created {created_count} core connection configurations")
    logger.info("✓ REST API connection templates seeded successfully")
```

---

## FILE 2: Frontend Component
**Path**: `e2etraceapp/src/components/admin-config-manager.jsx`

### CHANGE 2.1: Add API Type Detection (line ~554)

**Find this**:
```javascript
  const isDbLike = ['postgres', 'neo4j', 'opensearch', 'redis'].includes(type);

  return (
```

**Replace with**:
```javascript
  const isDbLike = ['postgres', 'neo4j', 'opensearch', 'redis'].includes(type);
  const isApiLike = ['api', 'rest_api', 'webapi', 'openapi', 'odata'].includes(type);
  const isSodaExternal = type === 'soda_external';

  return (
```

### CHANGE 2.2: Update Connection Type Dropdown (line ~588)

**Find this exact section**:
```jsx
      <div className="form-row">
        <div className="form-group">
          <label>Connection Type</label>
          <select value={connection.connection_type || ''} onChange={e => onChange({ ...connection, connection_type: e.target.value })}>
            <option value="">Select Type</option>
            <option value="postgres">PostgreSQL</option>
            <option value="neo4j">Neo4j</option>
            <option value="opensearch">OpenSearch</option>
            <option value="redis">Redis</option>
            <option value="s3">AWS S3</option>
            <option value="azure_blob">Azure Blob</option>
            <option value="local_folder">Local Folder</option>
            <option value="onedrive">OneDrive</option>
            <option value="google_drive">Google Drive</option>
            <option value="powerquery">PowerQuery Editor</option>
          </select>
        </div>
```

**Replace with**:
```jsx
      <div className="form-row">
        <div className="form-group">
          <label>Connection Type</label>
          <select value={connection.connection_type || ''} onChange={e => onChange({ ...connection, connection_type: e.target.value })}>
            <option value="">Select Type</option>
            
            <optgroup label="Databases">
              <option value="postgres">PostgreSQL</option>
              <option value="neo4j">Neo4j</option>
              <option value="opensearch">OpenSearch</option>
              <option value="redis">Redis</option>
            </optgroup>
            
            <optgroup label="External APIs">
              <option value="api">API (Generic)</option>
              <option value="rest_api">REST API</option>
              <option value="webapi">Web API</option>
              <option value="openapi">OpenAPI/Swagger</option>
              <option value="odata">OData Service</option>
            </optgroup>
            
            <optgroup label="Cloud Storage">
              <option value="s3">AWS S3</option>
              <option value="azure_blob">Azure Blob</option>
            </optgroup>
            
            <optgroup label="File Systems">
              <option value="local_folder">Local Folder</option>
              <option value="onedrive">OneDrive</option>
              <option value="google_drive">Google Drive</option>
            </optgroup>
            
            <optgroup label="Other">
              <option value="powerquery">PowerQuery Editor</option>
            </optgroup>
          </select>
        </div>
```

### CHANGE 2.3: Add API Connection Form Fields

**Find this section** (after the `isDbLike` form fields, around line ~650):
```jsx
      {isDbLike && (
        <>
          <div className="form-row">
            <div className="form-group">
              <label>Host</label>
```

**Add this BEFORE that section**:
```jsx
      {isApiLike && (
        <>
          <div className="form-row">
            <div className="form-group">
              <label>Base URL / Endpoint</label>
              <input 
                type="text" 
                value={connection.connection_string || ''} 
                onChange={e => onChange({ ...connection, connection_string: e.target.value })}
                placeholder="https://api.example.com/v1"
              />
            </div>
            <div className="form-group">
              <label>Authentication Type</label>
              <select 
                value={extra.auth_type || 'none'} 
                onChange={e => updateExtra('auth_type', e.target.value)}
              >
                <option value="none">None</option>
                <option value="bearer">Bearer Token</option>
                <option value="oauth2">OAuth2</option>
                <option value="api_key">API Key (Header)</option>
                <option value="basic">Basic Auth (Username/Password)</option>
              </select>
            </div>
          </div>

          {(extra.auth_type === 'bearer' || extra.auth_type === 'oauth2') && (
            <div className="form-row">
              <div className="form-group">
                <label>{extra.auth_type === 'oauth2' ? 'Access Token' : 'Bearer Token'}</label>
                <input 
                  type="password" 
                  value={connection.password || ''} 
                  onChange={e => onChange({ ...connection, password: e.target.value })}
                  placeholder="Paste token here (stored securely)"
                />
              </div>
            </div>
          )}

          {extra.auth_type === 'api_key' && (
            <div className="form-row">
              <div className="form-group">
                <label>API Key</label>
                <input 
                  type="password" 
                  value={connection.password || ''} 
                  onChange={e => onChange({ ...connection, password: e.target.value })}
                  placeholder="Your API Key"
                />
              </div>
              <div className="form-group">
                <label>Header Name</label>
                <input 
                  type="text" 
                  value={extra.api_key_header || 'X-API-Key'} 
                  onChange={e => updateExtra('api_key_header', e.target.value)}
                  placeholder="X-API-Key"
                />
              </div>
            </div>
          )}

          {extra.auth_type === 'basic' && (
            <div className="form-row">
              <div className="form-group">
                <label>Username</label>
                <input 
                  type="text" 
                  value={connection.username || ''} 
                  onChange={e => onChange({ ...connection, username: e.target.value })}
                  placeholder="Username"
                />
              </div>
              <div className="form-group">
                <label>Password</label>
                <input 
                  type="password" 
                  value={connection.password || ''} 
                  onChange={e => onChange({ ...connection, password: e.target.value })}
                  placeholder="Password"
                />
              </div>
            </div>
          )}

          <div className="form-row">
            <div className="form-group">
              <label>Test Endpoint Path (optional)</label>
              <input 
                type="text" 
                value={extra.test_path || ''} 
                onChange={e => updateExtra('test_path', e.target.value)}
                placeholder={
                  type === 'openapi' ? '/openapi.json' :
                  type === 'odata' ? '/$metadata' :
                  '/health'
                }
              />
            </div>
            <div className="form-group">
              <label>Timeout (seconds)</label>
              <input 
                type="number" 
                min="1" 
                max="60" 
                value={extra.timeout_s || 10} 
                onChange={e => updateExtra('timeout_s', parseFloat(e.target.value))}
              />
            </div>
          </div>

          <div className="form-group">
            <label>Custom Headers (JSON)</label>
            <textarea 
              value={extra.headers_json || '{}'} 
              onChange={e => updateExtra('headers_json', e.target.value)}
              placeholder='{"X-Custom-Header": "value", "X-Request-ID": "123"}'
              rows="3"
            />
          </div>
        </>
      )}

```

---

## FILE 3: Backend Model Documentation
**Path**: `agentic-restored/python_backend/models/admin_config_models.py`

### CHANGE 3.1: Add Supported Types Constant (after line 26, before Enums)

**Add this**:
```python
# ============================================================
# Supported Connection Types Registry
# ============================================================

SUPPORTED_CONNECTION_TYPES = {
    # Database Connections
    "postgres": {
        "name": "PostgreSQL",
        "category": "database",
        "description": "PostgreSQL relational database",
    },
    "neo4j": {
        "name": "Neo4j",
        "category": "database",
        "description": "Neo4j graph database",
    },
    "opensearch": {
        "name": "OpenSearch",
        "category": "database",
        "description": "OpenSearch vector search and analytics",
    },
    "redis": {
        "name": "Redis",
        "category": "database",
        "description": "Redis cache and session store",
    },
    
    # REST API Connections
    "api": {
        "name": "API (Generic)",
        "category": "api",
        "description": "Generic HTTP API endpoint",
    },
    "rest_api": {
        "name": "REST API",
        "category": "api",
        "description": "RESTful API service",
    },
    "webapi": {
        "name": "Web API",
        "category": "api",
        "description": "Web service/API endpoint",
    },
    "openapi": {
        "name": "OpenAPI/Swagger",
        "category": "api",
        "description": "OpenAPI specification endpoint",
    },
    "odata": {
        "name": "OData Service",
        "category": "api",
        "description": "OData protocol service endpoint",
    },
    
    # Cloud Storage
    "s3": {
        "name": "AWS S3",
        "category": "storage",
        "description": "Amazon S3 bucket",
    },
    "azure_blob": {
        "name": "Azure Blob Storage",
        "category": "storage",
        "description": "Azure Blob Storage container",
    },
    
    # File Systems
    "local_folder": {
        "name": "Local Folder",
        "category": "filesystem",
        "description": "Local file system directory",
    },
    "onedrive": {
        "name": "OneDrive",
        "category": "filesystem",
        "description": "Microsoft OneDrive",
    },
    "google_drive": {
        "name": "Google Drive",
        "category": "filesystem",
        "description": "Google Drive storage",
    },
    
    # Special Types
    "soda_external": {
        "name": "Soda External Runner",
        "category": "special",
        "description": "External Python interpreter for Soda scans",
    },
    "powerquery": {
        "name": "PowerQuery Editor",
        "category": "special",
        "description": "Power Query M Language editor",
    },
}
```

### CHANGE 3.2: Update ConnectionConfig Docstring (line ~220)

**Find this**:
```python
class ConnectionConfig(Base):
    """
    External service connection configuration.
    Stores connection settings for databases, APIs, etc.
    """
```

**Replace with**:
```python
class ConnectionConfig(Base):
    """
    External service connection configuration.
    Stores connection settings for databases, APIs, cloud storage, and file systems.
    
    Supported connection_type values (see SUPPORTED_CONNECTION_TYPES):
    
    DATABASE CONNECTIONS:
    - postgres: PostgreSQL database
    - neo4j: Neo4j graph database
    - opensearch: OpenSearch vector search
    - redis: Redis cache store
    
    EXTERNAL APIs:
    - api: Generic HTTP API
    - rest_api: RESTful API service
    - webapi: Web API endpoint
    - openapi: OpenAPI/Swagger specification
    - odata: OData protocol service
    
    CLOUD STORAGE:
    - s3: Amazon S3
    - azure_blob: Azure Blob Storage
    
    FILE SYSTEMS:
    - local_folder: Local file directory
    - onedrive: Microsoft OneDrive
    - google_drive: Google Drive
    
    SPECIAL:
    - soda_external: External Python interpreter
    - powerquery: Power Query M Language
    
    Authentication Support (in extra_options.auth_type):
    - none: No authentication
    - bearer: Bearer token (OAuth2/JWT)
    - oauth2: OAuth2 flow
    - api_key: Custom API key header
    - basic: HTTP Basic Auth (username/password)
    """
```

---

## SUMMARY OF CHANGES

| File | Type | Lines Added | Lines Removed | Lines Modified |
|------|------|-------------|----------------|----------------|
| seed_admin_configs.py | Code | 73 | 0 | 2 |
| admin-config-manager.jsx | Code | 150 | 15 | 10 |
| admin_config_models.py | Doc + Code | 80 | 0 | 1 |
| **TOTAL** | - | **303** | **15** | **13** |

---

## VERIFICATION COMMANDS

After applying patches:

```bash
# 1. Verify backend seed runs without errors
cd agentic-restored/python_backend
python -m scripts.seed_admin_configs

# 2. Verify REST API connections in database
psql -U postgres -d graphtrace -c "
SELECT id, connection_type, name FROM connection_configs 
WHERE connection_type IN ('api', 'rest_api', 'webapi', 'openapi', 'odata')
ORDER BY created_at;"

# 3. Rebuild frontend
cd e2etraceapp
npm run build

# 4. Test backend API
curl http://localhost:8011/api/admin/config/connections | jq '.[] | select(.connection_type | test("api|rest|web|openapi|odata"))'

# 5. Verify no errors in console/terminal
# - Check browser console (F12)
# - Check backend terminal for exceptions
# - Check VS Code debug output
```
