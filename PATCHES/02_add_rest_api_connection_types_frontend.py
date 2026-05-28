"""
PATCH 02: Add REST API Connection Types to Frontend UI
========================================================

File: e2etraceapp/src/components/admin-config-manager.jsx

Description:
- Adds REST API connection type options to ConnectionForm dropdown
- Includes api, rest_api, webapi, openapi, odata types
- Adds conditional rendering for API-specific fields (endpoint, auth type, test path)
- Enables UI-driven configuration of external API connections

Deployment:
1. Apply this patch to admin-config-manager.jsx
2. Rebuild frontend: npm run build (in e2etraceapp directory)
3. Deploy updated bundle
4. No backend restart required
"""

# PATCH INSTRUCTIONS:

# 1. LOCATE THE CONNECTION FORM (around line 554)
# Find this section:
BEFORE = """
// Connection Form
function ConnectionForm({ connection, onChange }) {
  const type = (connection.connection_type || '').toLowerCase();
  const extra = connection.extra_options || {};

  const updateExtra = (key, value) => {
    onChange({
      ...connection,
      extra_options: {
        ...(connection.extra_options || {}),
        [key]: value
      }
    });
  };

  const isDbLike = ['postgres', 'neo4j', 'opensearch', 'redis'].includes(type);
"""

# 2. ADD API TYPE DETECTION:
AFTER_DETECTION = """
// Connection Form
function ConnectionForm({ connection, onChange }) {
  const type = (connection.connection_type || '').toLowerCase();
  const extra = connection.extra_options || {};

  const updateExtra = (key, value) => {
    onChange({
      ...connection,
      extra_options: {
        ...(connection.extra_options || {}),
        [key]: value
      }
    });
  };

  const isDbLike = ['postgres', 'neo4j', 'opensearch', 'redis'].includes(type);
  const isApiLike = ['api', 'rest_api', 'webapi', 'openapi', 'odata'].includes(type);
  const isSodaExternal = type === 'soda_external';
"""

# 3. LOCATE THE CONNECTION TYPE DROPDOWN (around line 588)
# Find this:
DROPDOWN_BEFORE = """
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
"""

# 4. REPLACE WITH THIS:
DROPDOWN_AFTER = """
      <div className="form-row">
        <div className="form-group">
          <label>Connection Type</label>
          <select value={connection.connection_type || ''} onChange={e => onChange({ ...connection, connection_type: e.target.value })}>
            <option value="">Select Type</option>
            
            {/* Database Connections */}
            <optgroup label="Databases">
              <option value="postgres">PostgreSQL</option>
              <option value="neo4j">Neo4j</option>
              <option value="opensearch">OpenSearch</option>
              <option value="redis">Redis</option>
            </optgroup>
            
            {/* External APIs */}
            <optgroup label="External APIs">
              <option value="api">API (Generic)</option>
              <option value="rest_api">REST API</option>
              <option value="webapi">Web API</option>
              <option value="openapi">OpenAPI/Swagger</option>
              <option value="odata">OData Service</option>
            </optgroup>
            
            {/* Cloud Storage */}
            <optgroup label="Cloud Storage">
              <option value="s3">AWS S3</option>
              <option value="azure_blob">Azure Blob</option>
            </optgroup>
            
            {/* File Systems */}
            <optgroup label="File Systems">
              <option value="local_folder">Local Folder</option>
              <option value="onedrive">OneDrive</option>
              <option value="google_drive">Google Drive</option>
            </optgroup>
            
            {/* Other */}
            <optgroup label="Other">
              <option value="powerquery">PowerQuery Editor</option>
            </optgroup>
          </select>
        </div>
"""

# 5. LOCATE THE SECTION AFTER "isDbLike" FIELDS (around line 650)
# Find conditional rendering for database fields and add API fields:
# After this section:
"""
      {isDbLike && (
        <>
          <div className="form-row">
            <div className="form-group">
              <label>Host</label>
              ...
"""

# 6. ADD THIS NEW SECTION FOR API CONNECTIONS:
API_FIELDS = """
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
"""

# 7. ALSO UPDATE THE isDbLike condition to fix it:
# The current code has isDbLike but should handle Storage, OneDriver, GoogleDrive, PowerQuery separately
# Update storage type detection if needed

# 8. TEST AFTER PATCHING:
# - Verify connection type dropdown shows all API types
# - Create new connection with type: rest_api
# - Fill in endpoint, auth type, token
# - Click "Test Connection" - should work
# - Verify in database: SELECT * FROM connection_configs WHERE connection_type = 'rest_api';
