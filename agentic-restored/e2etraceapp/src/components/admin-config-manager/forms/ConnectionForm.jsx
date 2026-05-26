/**
 * Connection Form Component (Data Sources)
 * Very complex form supporting multiple connection types with conditional fields
 */
import React from 'react';

export function ConnectionForm({ connection, onChange }) {
  const isEdit = connection?._isNew === false;
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

  const authType = (extra.auth_type || 'none').toLowerCase();

  const parseJsonOrEmpty = (value) => {
    const raw = String(value || '').trim();
    if (!raw) return {};
    try {
      const parsed = JSON.parse(raw);
      return (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) ? parsed : {};
    } catch {
      return null;
    }
  };

  const getRequirements = () => {
    const saveRequired = ['Connection Type', 'Name'];
    const testRequired = [];

    if (isApiLike) {
      saveRequired.push(type === 'odata' ? 'Service URL (Base URL)' : 'Base URL / Endpoint');
      const at = authType;
      if (at === 'bearer' || at === 'oauth2') testRequired.push('Access Token');
      if (at === 'api_key') testRequired.push('API Key');
      if (at === 'basic') testRequired.push('Username', 'Password');
    }

    if (type === 'postgres') {
      saveRequired.push('Connection String OR (Host, Port, Database, Username)');
    }
    if (type === 'neo4j') {
      saveRequired.push('Connection String/URI OR (Host, Port)');
    }
    if (type === 'opensearch') {
      saveRequired.push('Connection String OR (Host, Port)');
    }
    if (type === 'redis') {
      saveRequired.push('Connection String OR (Host, Port)');
    }

    if (type === 'local_folder') {
      saveRequired.push('Folder Path');
    }

    if (type === 'soda_external') {
      saveRequired.push('Python Interpreter Path');
    }

    if (type === 's3') {
      saveRequired.push('Bucket', 'Region');
    }

    if (type === 'azure_blob') {
      saveRequired.push('Container', 'Connection String/SAS OR Account Name');
      testRequired.push('Connection String/SAS OR Account Key');
    }

    if (type === 'onedrive') {
      testRequired.push('Access Token');
    }

    if (type === 'google_drive') {
      testRequired.push('Access Token');
    }

    if (type === 'powerquery') {
      testRequired.push('extra_options.m_query OR extra_options.query_name');
    }

    return { saveRequired, testRequired };
  };

  const requirements = getRequirements();

  return (
    <>
      <div className="form-row">
        <div className="form-group">
          <label>ID (optional)</label>
          <input
            type="text"
            value={connection.id || ''}
            onChange={e => onChange({ ...connection, id: e.target.value })}
            placeholder="e.g., postgres_primary"
            disabled={isEdit}
          />
        </div>
        <div className="form-group">
          <label>Connection Type <span style={{ color: 'var(--danger)', fontWeight: 700 }}>*</span></label>
          <select
            value={connection.connection_type || ''}
            onChange={e => onChange({ ...connection, connection_type: e.target.value })}
            disabled={isEdit}
          >
            <option value="">Select Type</option>
            <option value="postgres">PostgreSQL</option>
            <option value="neo4j">Neo4j</option>
            <option value="opensearch">OpenSearch</option>
            <option value="redis">Redis</option>
            <option value="soda_external">Soda External Runner</option>
            <option value="api">API (Generic)</option>
            <option value="rest_api">REST API</option>
            <option value="webapi">Web API</option>
            <option value="openapi">OpenAPI</option>
            <option value="odata">OData</option>
            <option value="s3">AWS S3</option>
            <option value="azure_blob">Azure Blob</option>
            <option value="local_folder">Local Folder</option>
            <option value="onedrive">OneDrive</option>
            <option value="google_drive">Google Drive</option>
            <option value="powerquery">PowerQuery Editor</option>
          </select>
        </div>
        <div className="form-group">
          <label>Name <span style={{ color: 'var(--danger)', fontWeight: 700 }}>*</span></label>
          <input
            type="text"
            value={connection.name || ''}
            onChange={e => onChange({ ...connection, name: e.target.value })}
            placeholder="e.g., Primary PostgreSQL"
          />
        </div>
      </div>

      <div className="form-group">
        <label>Description (optional)</label>
        <input
          type="text"
          value={connection.description || ''}
          onChange={e => onChange({ ...connection, description: e.target.value })}
          placeholder="What is this connection used for?"
        />
      </div>

      {(requirements.saveRequired.length > 0 || requirements.testRequired.length > 0) && (
        <div style={{
          background: 'rgba(0,0,0,0.08)',
          border: '1px solid rgba(255,255,255,0.08)',
          borderRadius: '10px',
          padding: '10px 12px',
          marginBottom: '12px',
          fontSize: '12px',
          color: 'var(--text-muted)'
        }}>
          <div><strong>Required to save:</strong> {requirements.saveRequired.join(', ')}</div>
          {requirements.testRequired.length > 0 && (
            <div style={{ marginTop: '6px' }}>
              <strong>Required to successfully test:</strong> {requirements.testRequired.join(', ')}
            </div>
          )}
        </div>
      )}

      {isApiLike && (
        <>
          <div className="form-row">
            <div className="form-group">
              <label>
                {type === 'odata' ? 'Service URL' : 'Base URL / Endpoint'}{' '}
                <span style={{ color: 'var(--danger)', fontWeight: 700 }}>*</span>
              </label>
              <input
                type="text"
                value={connection.connection_string || ''}
                onChange={e => onChange({ ...connection, connection_string: e.target.value })}
                placeholder={type === 'odata' ? 'https://example.com/odata' : 'https://api.example.com'}
              />
              <div style={{ color: 'var(--text-muted)', fontSize: '12px', marginTop: '6px' }}>
                This is not treated as a secret; store tokens/keys in the secret field below.
              </div>
            </div>
            <div className="form-group">
              <label>Auth Type</label>
              <select
                value={authType}
                onChange={e => updateExtra('auth_type', e.target.value)}
              >
                <option value="none">None</option>
                <option value="bearer">Bearer Token</option>
                <option value="api_key">API Key (Header)</option>
                <option value="basic">Basic (Username/Password)</option>
                <option value="oauth2">OAuth2 (use Access Token)</option>
              </select>
            </div>
          </div>

          {(authType === 'bearer' || authType === 'oauth2') && (
            <div className="form-group">
              <label>Access Token (stored as secret)</label>
              <input
                type="password"
                value={connection.password || ''}
                onChange={e => onChange({ ...connection, password: e.target.value })}
                placeholder="eyJhbGciOi..."
              />
            </div>
          )}

          {authType === 'api_key' && (
            <>
              <div className="form-row">
                <div className="form-group">
                  <label>API Key Header</label>
                  <input
                    type="text"
                    value={extra.api_key_header || 'X-API-Key'}
                    onChange={e => updateExtra('api_key_header', e.target.value)}
                    placeholder="X-API-Key"
                  />
                </div>
                <div className="form-group">
                  <label>API Key (stored as secret)</label>
                  <input
                    type="password"
                    value={connection.password || ''}
                    onChange={e => onChange({ ...connection, password: e.target.value })}
                  />
                </div>
              </div>
            </>
          )}

          {authType === 'basic' && (
            <>
              <div className="form-row">
                <div className="form-group">
                  <label>Username</label>
                  <input
                    type="text"
                    value={connection.username || ''}
                    onChange={e => onChange({ ...connection, username: e.target.value })}
                  />
                </div>
                <div className="form-group">
                  <label>Password (stored as secret)</label>
                  <input
                    type="password"
                    value={connection.password || ''}
                    onChange={e => onChange({ ...connection, password: e.target.value })}
                  />
                </div>
              </div>
            </>
          )}

          <div className="form-row">
            <div className="form-group">
              <label>Test Path (optional)</label>
              <input
                type="text"
                value={extra.test_path || ''}
                onChange={e => updateExtra('test_path', e.target.value)}
                placeholder={type === 'odata' ? '/$metadata' : '/health'}
              />
            </div>
            <div className="form-group">
              <label>Timeout Seconds (optional)</label>
              <input
                type="number"
                value={extra.timeout_s ?? ''}
                onChange={e => updateExtra('timeout_s', parseFloat(e.target.value) || '')}
                placeholder="10"
              />
            </div>
          </div>

          {type === 'openapi' && (
            <div className="form-group">
              <label>OpenAPI Spec URL (optional)</label>
              <input
                type="text"
                value={extra.spec_url || ''}
                onChange={e => updateExtra('spec_url', e.target.value)}
                placeholder="https://api.example.com/openapi.json"
              />
            </div>
          )}

          <div className="form-group">
            <label>Extra Headers (JSON, optional)</label>
            <textarea
              value={extra.headers_json || ''}
              onChange={e => updateExtra('headers_json', e.target.value)}
              placeholder='{"X-Custom-Header": "value"}'
              rows={4}
            />
            {extra.headers_json && parseJsonOrEmpty(extra.headers_json) === null && (
              <div style={{ color: 'var(--danger)', fontSize: '12px', marginTop: '6px' }}>
                Headers JSON is invalid. It will be ignored until fixed.
              </div>
            )}
          </div>
        </>
      )}

      {isSodaExternal && (
        <>
          <div className="form-row">
            <div className="form-group">
              <label>
                Python Interpreter Path{' '}
                <span style={{ color: 'var(--danger)', fontWeight: 700 }}>*</span>
              </label>
              <input
                type="text"
                value={extra.python_path || ''}
                onChange={e => updateExtra('python_path', e.target.value)}
                placeholder="C:\\path\\to\\soda-venv\\Scripts\\python.exe"
              />
              <div style={{ color: 'var(--text-muted)', fontSize: '12px', marginTop: '6px' }}>
                Point this at a separate Python (typically 3.11) where <code>soda-core-postgres</code> is installed.
              </div>
            </div>
            <div className="form-group">
              <label>Timeout (seconds)</label>
              <input
                type="number"
                value={extra.timeout_s ?? ''}
                onChange={e => updateExtra('timeout_s', parseInt(e.target.value) || '')}
                placeholder="60"
              />
            </div>
          </div>
        </>
      )}

      {isDbLike && (
        <>
          <div className="form-row">
            <div className="form-group">
              <label>Host</label>
              <input
                type="text"
                value={connection.host || ''}
                onChange={e => onChange({ ...connection, host: e.target.value })}
                placeholder="localhost"
              />
            </div>
            <div className="form-group">
              <label>Port</label>
              <input
                type="number"
                value={connection.port || ''}
                onChange={e => onChange({ ...connection, port: parseInt(e.target.value) || '' })}
                placeholder="5432"
              />
            </div>
          </div>
          <div className="form-row">
            <div className="form-group">
              <label>Database / Index</label>
              <input
                type="text"
                value={connection.database || connection.index_name || ''}
                onChange={e => onChange({ ...connection, database: e.target.value })}
                placeholder="graphtrace"
              />
            </div>
            <div className="form-group">
              <label>Username</label>
              <input
                type="text"
                value={connection.username || ''}
                onChange={e => onChange({ ...connection, username: e.target.value })}
              />
            </div>
          </div>
          <div className="form-group">
            <label>Password</label>
            <input
              type="password"
              value={connection.password || ''}
              onChange={e => onChange({ ...connection, password: e.target.value })}
            />
          </div>
        </>
      )}

      {type === 's3' && (
        <>
          <div className="form-row">
            <div className="form-group">
              <label>Bucket</label>
              <input
                type="text"
                value={extra.bucket || ''}
                onChange={e => updateExtra('bucket', e.target.value)}
                placeholder="my-bucket"
              />
            </div>
            <div className="form-group">
              <label>Region</label>
              <input
                type="text"
                value={extra.region || ''}
                onChange={e => updateExtra('region', e.target.value)}
                placeholder="us-east-1"
              />
            </div>
          </div>
          <div className="form-group">
            <label>Prefix (optional)</label>
            <input
              type="text"
              value={extra.prefix || ''}
              onChange={e => updateExtra('prefix', e.target.value)}
              placeholder="folder/subfolder/"
            />
          </div>
          <div className="form-row">
            <div className="form-group">
              <label>Access Key ID (optional)</label>
              <input
                type="text"
                value={connection.username || ''}
                onChange={e => onChange({ ...connection, username: e.target.value })}
                placeholder="AKIA..."
              />
            </div>
            <div className="form-group">
              <label>Secret Access Key (optional)</label>
              <input
                type="password"
                value={connection.password || ''}
                onChange={e => onChange({ ...connection, password: e.target.value })}
              />
            </div>
          </div>
        </>
      )}

      {type === 'azure_blob' && (
        <>
          <div className="form-row">
            <div className="form-group">
              <label>Account Name</label>
              <input
                type="text"
                value={extra.account_name || ''}
                onChange={e => updateExtra('account_name', e.target.value)}
                placeholder="mystorageaccount"
              />
            </div>
            <div className="form-group">
              <label>Container</label>
              <input
                type="text"
                value={extra.container || ''}
                onChange={e => updateExtra('container', e.target.value)}
                placeholder="my-container"
              />
            </div>
          </div>
          <div className="form-group">
            <label>Blob Prefix (optional)</label>
            <input
              type="text"
              value={extra.prefix || ''}
              onChange={e => updateExtra('prefix', e.target.value)}
              placeholder="folder/subfolder/"
            />
          </div>
          <div className="form-group">
            <label>Connection String / SAS (stored as secret)</label>
            <input
              type="password"
              value={connection.connection_string || ''}
              onChange={e => onChange({ ...connection, connection_string: e.target.value })}
              placeholder="DefaultEndpointsProtocol=..."
            />
          </div>
        </>
      )}

      {type === 'local_folder' && (
        <>
          <div className="form-group">
            <label>Folder Path</label>
            <input
              type="text"
              value={extra.folder_path || ''}
              onChange={e => updateExtra('folder_path', e.target.value)}
              placeholder="C:\\data\\imports"
            />
          </div>
        </>
      )}

      {type === 'onedrive' && (
        <>
          <div className="form-row">
            <div className="form-group">
              <label>Root Path</label>
              <input
                type="text"
                value={extra.root_path || ''}
                onChange={e => updateExtra('root_path', e.target.value)}
                placeholder="/Documents"
              />
            </div>
            <div className="form-group">
              <label>Drive ID (optional)</label>
              <input
                type="text"
                value={extra.drive_id || ''}
                onChange={e => updateExtra('drive_id', e.target.value)}
              />
            </div>
          </div>
          <div className="form-group">
            <label>Access Token (optional, stored as secret)</label>
            <input
              type="password"
              value={connection.password || ''}
              onChange={e => onChange({ ...connection, password: e.target.value })}
            />
          </div>
        </>
      )}

      {type === 'google_drive' && (
        <>
          <div className="form-row">
            <div className="form-group">
              <label>Folder ID</label>
              <input
                type="text"
                value={extra.folder_id || ''}
                onChange={e => updateExtra('folder_id', e.target.value)}
              />
            </div>
            <div className="form-group">
              <label>Shared Drive ID (optional)</label>
              <input
                type="text"
                value={extra.shared_drive_id || ''}
                onChange={e => updateExtra('shared_drive_id', e.target.value)}
              />
            </div>
          </div>
          <div className="form-group">
            <label>Access Token (optional, stored as secret)</label>
            <input
              type="password"
              value={connection.password || ''}
              onChange={e => onChange({ ...connection, password: e.target.value })}
            />
          </div>
        </>
      )}

      {type === 'powerquery' && (
        <>
          <div className="form-group">
            <label>Query Name (optional)</label>
            <input
              type="text"
              value={extra.query_name || ''}
              onChange={e => updateExtra('query_name', e.target.value)}
              placeholder="MyQuery"
            />
          </div>
          <div className="form-group">
            <label>M Query</label>
            <textarea
              value={extra.m_query || ''}
              onChange={e => updateExtra('m_query', e.target.value)}
              placeholder="let\n  Source = ...\nin\n  Source"
              rows={6}
            />
          </div>
        </>
      )}

      <div className="form-row">
        <div className="form-group">
          <label>Status</label>
          <select value={connection.status || 'inactive'} onChange={e => onChange({ ...connection, status: e.target.value })}>
            <option value="active">Active</option>
            <option value="inactive">Inactive</option>
          </select>
        </div>
        <div className="form-group">
          <label>Default Connection</label>
          <select value={connection.is_default ? 'true' : 'false'} onChange={e => onChange({ ...connection, is_default: e.target.value === 'true' })}>
            <option value="false">No</option>
            <option value="true">Yes</option>
          </select>
        </div>
      </div>
    </>
  );
}

export default ConnectionForm;
