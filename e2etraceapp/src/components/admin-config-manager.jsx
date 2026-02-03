/**
 * Admin Configuration Manager
 * 
 * TCS-styled centralized configuration management UI
 * Row-based layout with test connection support
 */

import React, { useState, useEffect, useCallback } from 'react';

const API_BASE = 'http://localhost:8011/api/admin/config';

// Tab Navigation Component
function TabNavigation({ tabs, activeTab, onTabChange }) {
  return (
    <div className="admin-tab-nav">
      {tabs.map(tab => (
        <button
          key={tab.id}
          className={`admin-tab-btn ${activeTab === tab.id ? 'active' : ''}`}
          onClick={() => onTabChange(tab.id)}
        >
          <span className="tab-icon"><i className={tab.icon}></i></span>
          <span className="tab-label">{tab.label}</span>
          {tab.count > 0 && <span className="tab-count">{tab.count}</span>}
        </button>
      ))}
    </div>
  );
}

// Status Badge Component
function StatusBadge({ status }) {
  const statusClass = {
    'active': 'status-active',
    'inactive': 'status-inactive',
    'testing': 'status-testing',
    'deprecated': 'status-deprecated',
    'healthy': 'status-healthy',
    'degraded': 'status-degraded',
    'configured': 'status-configured',
    'unconfigured': 'status-unconfigured',
    'missing_api_key': 'status-inactive'
  }[status] || 'status-inactive';

  const displayStatus = status === 'missing_api_key' ? 'No API Key' : status;
  
  return <span className={`status-badge ${statusClass}`}>{displayStatus}</span>;
}

// Modal Component
function Modal({ isOpen, onClose, title, children, footer }) {
  if (!isOpen) return null;
  
  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <h3>{title}</h3>
          <button className="modal-close" onClick={onClose}>
            <i className="fas fa-times"></i>
          </button>
        </div>
        <div className="modal-body">{children}</div>
        {footer && <div className="modal-footer">{footer}</div>}
      </div>
    </div>
  );
}

// LLM Providers Table
function LLMProvidersTable({ providers, onEdit, onDelete, onTest, testingId }) {
  if (!providers.length) {
    return (
      <div className="empty-state">
        <i className="fas fa-brain"></i>
        <p>No LLM providers configured</p>
      </div>
    );
  }

  return (
    <table className="config-table">
      <thead>
        <tr>
          <th>Provider</th>
          <th>Name</th>
          <th>Endpoint</th>
          <th>Model</th>
          <th>API Key</th>
          <th>Status</th>
          <th>Actions</th>
        </tr>
      </thead>
      <tbody>
        {providers.map(p => (
          <tr key={p.id}>
            <td className="provider-cell">
              {p.provider.toUpperCase()}
              {p.is_default && <span className="default-badge">Default</span>}
            </td>
            <td className="name-cell">{p.name}</td>
            <td className="endpoint-cell" title={p.api_endpoint}>{p.api_endpoint || '-'}</td>
            <td className="model-cell">{p.default_chat_model || '-'}</td>
            <td>
              {p.api_key_masked ? (
                <span className="api-key-display masked">
                  <i className="fas fa-check-circle"></i> {p.api_key_masked}
                </span>
              ) : (
                <span className="api-key-display missing">
                  <i className="fas fa-exclamation-circle"></i> Not set
                </span>
              )}
            </td>
            <td><StatusBadge status={p.status} /></td>
            <td className="actions-cell">
              <button 
                className="btn-action btn-test" 
                onClick={() => onTest(p.id)}
                disabled={testingId === p.id}
                title="Test Connection"
              >
                {testingId === p.id ? <i className="fas fa-spinner fa-spin"></i> : <i className="fas fa-plug"></i>}
              </button>
              <button className="btn-action btn-edit" onClick={() => onEdit(p)} title="Edit">
                <i className="fas fa-edit"></i>
              </button>
              <button className="btn-action btn-delete" onClick={() => onDelete(p.id)} title="Delete">
                <i className="fas fa-trash"></i>
              </button>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

// Embedding Models Table
function EmbeddingModelsTable({ models, onEdit, onDelete, onTest, testingId }) {
  if (!models.length) {
    return (
      <div className="empty-state">
        <i className="fas fa-vector-square"></i>
        <p>No embedding models configured</p>
      </div>
    );
  }

  return (
    <table className="config-table">
      <thead>
        <tr>
          <th>Provider</th>
          <th>Name</th>
          <th>Model</th>
          <th>Dimensions</th>
          <th>API Key</th>
          <th>Status</th>
          <th>Actions</th>
        </tr>
      </thead>
      <tbody>
        {models.map(m => (
          <tr key={m.id}>
            <td className="provider-cell">
              {m.provider.toUpperCase()}
              {m.is_default && <span className="default-badge">Default</span>}
            </td>
            <td className="name-cell">{m.name}</td>
            <td className="model-cell">{m.model_name}</td>
            <td>{m.dimensions || '-'}</td>
            <td>
              {m.api_key_masked ? (
                <span className="api-key-display masked">
                  <i className="fas fa-check-circle"></i> {m.api_key_masked}
                </span>
              ) : m.provider === 'sentence_transformers' ? (
                <span className="api-key-display" style={{ color: 'var(--text-muted)' }}>
                  N/A (Local)
                </span>
              ) : (
                <span className="api-key-display missing">
                  <i className="fas fa-exclamation-circle"></i> Not set
                </span>
              )}
            </td>
            <td><StatusBadge status={m.status} /></td>
            <td className="actions-cell">
              <button 
                className="btn-action btn-test" 
                onClick={() => onTest(m.id)}
                disabled={testingId === m.id}
                title="Test Model"
              >
                {testingId === m.id ? <i className="fas fa-spinner fa-spin"></i> : <i className="fas fa-plug"></i>}
              </button>
              <button className="btn-action btn-edit" onClick={() => onEdit(m)} title="Edit">
                <i className="fas fa-edit"></i>
              </button>
              <button className="btn-action btn-delete" onClick={() => onDelete(m.id)} title="Delete">
                <i className="fas fa-trash"></i>
              </button>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

// Connections Table
function ConnectionsTable({ connections, onEdit, onDelete, onTest, testingId, testResults }) {
  const getHostDisplay = (c) => {
    const opts = c.extra_options || {};
    switch ((c.connection_type || '').toLowerCase()) {
      case 's3':
        return opts.bucket || '-';
      case 'azure_blob':
        return opts.account_name || '-';
      case 'local_folder':
        return opts.folder_path || '-';
      case 'onedrive':
        return opts.root_path || '-';
      case 'google_drive':
        return opts.folder_id || opts.root_path || '-';
      case 'powerquery':
        return 'PowerQuery';
      default:
        return c.host || '-';
    }
  };

  const getPortDisplay = (c) => {
    const type = (c.connection_type || '').toLowerCase();
    if (['s3', 'azure_blob', 'local_folder', 'onedrive', 'google_drive', 'powerquery'].includes(type)) {
      return '-';
    }
    return c.port ?? '-';
  };

  const getDatabaseDisplay = (c) => {
    const opts = c.extra_options || {};
    switch ((c.connection_type || '').toLowerCase()) {
      case 's3':
        return opts.prefix || '-';
      case 'azure_blob':
        return opts.container || '-';
      case 'local_folder':
        return '-';
      case 'onedrive':
        return opts.drive_id || '-';
      case 'google_drive':
        return opts.shared_drive_id || '-';
      case 'powerquery':
        return (opts.query_name || opts.data_source_name || '-')
      default:
        return c.database || c.index_name || '-';
    }
  };

  if (!connections.length) {
    return (
      <div className="empty-state">
        <i className="fas fa-plug"></i>
        <p>No connections configured</p>
      </div>
    );
  }

  return (
    <table className="config-table">
      <thead>
        <tr>
          <th>Type</th>
          <th>Name</th>
          <th>Host</th>
          <th>Port</th>
          <th>Database</th>
          <th>Status</th>
          <th>Test Result</th>
          <th>Actions</th>
        </tr>
      </thead>
      <tbody>
        {connections.map(c => (
          <tr key={c.id}>
            <td className="provider-cell">
              {c.connection_type.toUpperCase()}
              {c.is_default && <span className="default-badge">Default</span>}
            </td>
            <td className="name-cell">{c.name}</td>
            <td className="endpoint-cell">{getHostDisplay(c)}</td>
            <td>{getPortDisplay(c)}</td>
            <td>{getDatabaseDisplay(c)}</td>
            <td><StatusBadge status={c.status} /></td>
            <td>
              {testResults[c.id] && (
                <span className={`test-result ${testResults[c.id].success ? 'success' : 'failure'}`}>
                  {testResults[c.id].success ? (
                    <><i className="fas fa-check"></i> Connected</>
                  ) : (
                    <><i className="fas fa-times"></i> {testResults[c.id].error || 'Failed'}</>
                  )}
                </span>
              )}
            </td>
            <td className="actions-cell">
              <button 
                className="btn-action btn-test" 
                onClick={() => onTest(c.id)}
                disabled={testingId === c.id}
                title="Test Connection"
              >
                {testingId === c.id ? <i className="fas fa-spinner fa-spin"></i> : <i className="fas fa-plug"></i>}
              </button>
              <button className="btn-action btn-edit" onClick={() => onEdit(c)} title="Edit">
                <i className="fas fa-edit"></i>
              </button>
              <button className="btn-action btn-delete" onClick={() => onDelete(c.id)} title="Delete">
                <i className="fas fa-trash"></i>
              </button>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

// System Settings Table
function SystemSettingsTable({ settings, onEdit, onDelete }) {
  if (!settings.length) {
    return (
      <div className="empty-state">
        <i className="fas fa-cog"></i>
        <p>No system settings configured</p>
      </div>
    );
  }

  // Group by category
  const grouped = settings.reduce((acc, s) => {
    const cat = s.category || 'general';
    if (!acc[cat]) acc[cat] = [];
    acc[cat].push(s);
    return acc;
  }, {});

  return (
    <div>
      {Object.entries(grouped).map(([category, items]) => (
        <div key={category} style={{ marginBottom: '24px' }}>
          <h4 style={{ 
            margin: '0 0 12px 0', 
            textTransform: 'uppercase', 
            fontSize: '12px', 
            color: 'var(--text-muted)',
            letterSpacing: '0.5px'
          }}>
            {category}
          </h4>
          <table className="config-table">
            <thead>
              <tr>
                <th>Key</th>
                <th>Value</th>
                <th>Type</th>
                <th>Status</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {items.map(s => (
                <tr key={s.id}>
                  <td className="name-cell">{s.key}</td>
                  <td className="endpoint-cell">
                    {s.is_secret ? '********' : (s.value || s.default_value || '-')}
                  </td>
                  <td><span className="type-badge">{s.value_type}</span></td>
                  <td><StatusBadge status={s.enabled ? 'active' : 'inactive'} /></td>
                  <td className="actions-cell">
                    <button className="btn-action btn-edit" onClick={() => onEdit(s)} title="Edit">
                      <i className="fas fa-edit"></i>
                    </button>
                    <button className="btn-action btn-delete" onClick={() => onDelete(s.id)} title="Delete">
                      <i className="fas fa-trash"></i>
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ))}
    </div>
  );
}

// Feature Flags Table
function FeatureFlagsTable({ flags, onToggle, onEdit, onDelete }) {
  if (!flags.length) {
    return (
      <div className="empty-state">
        <i className="fas fa-flag"></i>
        <p>No feature flags configured</p>
      </div>
    );
  }

  return (
    <table className="config-table">
      <thead>
        <tr>
          <th>Flag</th>
          <th>Description</th>
          <th>Category</th>
          <th>Enabled</th>
          <th>Actions</th>
        </tr>
      </thead>
      <tbody>
        {flags.map(f => (
          <tr key={f.id}>
            <td className="name-cell">{f.flag_name}</td>
            <td style={{ maxWidth: '300px' }}>{f.description || '-'}</td>
            <td><span className="type-badge">{f.category || 'general'}</span></td>
            <td>
              <label className="toggle-switch">
                <input 
                  type="checkbox" 
                  checked={f.is_enabled} 
                  onChange={() => onToggle(f)}
                />
                <span className="toggle-slider"></span>
              </label>
            </td>
            <td className="actions-cell">
              <button className="btn-action btn-edit" onClick={() => onEdit(f)} title="Edit">
                <i className="fas fa-edit"></i>
              </button>
              <button className="btn-action btn-delete" onClick={() => onDelete(f.id)} title="Delete">
                <i className="fas fa-trash"></i>
              </button>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

// LLM Provider Form
function LLMProviderForm({ provider, onChange }) {
  return (
    <>
      <div className="form-row">
        <div className="form-group">
          <label>Provider</label>
          <select value={provider.provider || ''} onChange={e => onChange({ ...provider, provider: e.target.value })}>
            <option value="">Select Provider</option>
            <option value="openai">OpenAI</option>
            <option value="anthropic">Anthropic</option>
            <option value="azure_openai">Azure OpenAI</option>
            <option value="ollama">Ollama</option>
            <option value="huggingface">Hugging Face</option>
          </select>
        </div>
        <div className="form-group">
          <label>Display Name</label>
          <input 
            type="text" 
            value={provider.name || ''} 
            onChange={e => onChange({ ...provider, name: e.target.value })}
            placeholder="e.g., OpenAI GPT-4"
          />
        </div>
      </div>
      <div className="form-group">
        <label>API Key</label>
        <input 
          type="password" 
          value={provider.api_key || ''} 
          onChange={e => onChange({ ...provider, api_key: e.target.value })}
          placeholder="Enter API key"
        />
      </div>
      <div className="form-row">
        <div className="form-group">
          <label>API Endpoint</label>
          <input 
            type="text" 
            value={provider.api_endpoint || ''} 
            onChange={e => onChange({ ...provider, api_endpoint: e.target.value })}
            placeholder="https://api.openai.com/v1"
          />
        </div>
        <div className="form-group">
          <label>Default Chat Model</label>
          <input 
            type="text" 
            value={provider.default_chat_model || ''} 
            onChange={e => onChange({ ...provider, default_chat_model: e.target.value })}
            placeholder="gpt-4-turbo-preview"
          />
        </div>
      </div>
      {provider.provider === 'azure_openai' && (
        <div className="form-row">
          <div className="form-group">
            <label>Azure Deployment</label>
            <input 
              type="text" 
              value={provider.azure_deployment || ''} 
              onChange={e => onChange({ ...provider, azure_deployment: e.target.value })}
            />
          </div>
          <div className="form-group">
            <label>Azure Resource Name</label>
            <input 
              type="text" 
              value={provider.azure_resource_name || ''} 
              onChange={e => onChange({ ...provider, azure_resource_name: e.target.value })}
            />
          </div>
        </div>
      )}
      <div className="form-row">
        <div className="form-group">
          <label>Status</label>
          <select value={provider.status || 'inactive'} onChange={e => onChange({ ...provider, status: e.target.value })}>
            <option value="active">Active</option>
            <option value="inactive">Inactive</option>
            <option value="testing">Testing</option>
            <option value="deprecated">Deprecated</option>
          </select>
        </div>
        <div className="form-group">
          <label>Default Provider</label>
          <select value={provider.is_default ? 'true' : 'false'} onChange={e => onChange({ ...provider, is_default: e.target.value === 'true' })}>
            <option value="false">No</option>
            <option value="true">Yes</option>
          </select>
        </div>
      </div>
    </>
  );
}

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

  return (
    <>
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
        <div className="form-group">
          <label>Name</label>
          <input 
            type="text" 
            value={connection.name || ''} 
            onChange={e => onChange({ ...connection, name: e.target.value })}
            placeholder="e.g., Primary PostgreSQL"
          />
        </div>
      </div>

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
              value={connection.password || ''}
              onChange={e => onChange({ ...connection, password: e.target.value })}
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

// Main Admin Config Manager Component
export default function AdminConfigManager() {
  const [activeTab, setActiveTab] = useState('llm');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);
  const [data, setData] = useState({
    llmProviders: [],
    embeddingModels: [],
    connections: [],
    systemConfigs: [],
    featureFlags: []
  });
  const [health, setHealth] = useState(null);
  const [modalOpen, setModalOpen] = useState(false);
  const [modalType, setModalType] = useState(null);
  const [editItem, setEditItem] = useState(null);
  const [testingId, setTestingId] = useState(null);
  const [testResults, setTestResults] = useState({});
  
  const tabs = [
    { id: 'llm', label: 'LLM Providers', icon: 'fas fa-brain', count: data.llmProviders.length },
    { id: 'embedding', label: 'Embedding Models', icon: 'fas fa-vector-square', count: data.embeddingModels.length },
    { id: 'connections', label: 'Connections', icon: 'fas fa-plug', count: data.connections.length },
    { id: 'settings', label: 'System Settings', icon: 'fas fa-cog', count: data.systemConfigs.length },
    { id: 'flags', label: 'Feature Flags', icon: 'fas fa-flag', count: data.featureFlags.length }
  ];
  
  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [llmRes, embRes, connRes, sysRes, flagRes, healthRes] = await Promise.all([
        fetch(`${API_BASE}/llm-providers`),
        fetch(`${API_BASE}/embedding-models`),
        fetch(`${API_BASE}/connections`),
        fetch(`${API_BASE}/system`),
        fetch(`${API_BASE}/feature-flags`),
        fetch(`${API_BASE}/health`)
      ]);
      
      // Check if any response failed
      const responses = [
        { name: 'LLM Providers', res: llmRes },
        { name: 'Embedding Models', res: embRes },
        { name: 'Connections', res: connRes },
        { name: 'System Config', res: sysRes },
        { name: 'Feature Flags', res: flagRes },
        { name: 'Health', res: healthRes }
      ];
      
      const failedResponses = responses.filter(r => !r.res.ok);
      if (failedResponses.length > 0) {
        const failedNames = failedResponses.map(r => r.name).join(', ');
        const firstError = failedResponses[0];
        let errorDetail = `Status ${firstError.res.status}`;
        try {
          const errorBody = await firstError.res.text();
          if (errorBody) {
            const parsed = JSON.parse(errorBody);
            errorDetail = parsed.detail || parsed.message || errorDetail;
          }
        } catch {
          // Ignore parse errors
        }
        throw new Error(`Failed to load: ${failedNames}. ${errorDetail}`);
      }
      
      const [llm, emb, conn, sys, flags, health] = await Promise.all([
        llmRes.json(),
        embRes.json(),
        connRes.json(),
        sysRes.json(),
        flagRes.json(),
        healthRes.json()
      ]);
      
      setData({
        llmProviders: llm,
        embeddingModels: emb,
        connections: conn,
        systemConfigs: sys,
        featureFlags: flags
      });
      setHealth(health);
    } catch (err) {
      const errorMsg = err.message || 'Failed to load configuration data';
      // Provide more helpful message for common errors
      if (errorMsg.includes('Status 500')) {
        setError('Backend error: Database may not be running or tables not created. Run: python -m scripts.init_db_schema');
      } else if (errorMsg.includes('Failed to fetch')) {
        setError('Cannot connect to backend. Ensure the server is running on port 8011.');
      } else {
        setError(errorMsg);
      }
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, []);
  
  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const showMessage = (msg, isError = false) => {
    if (isError) {
      setError(msg);
      setSuccess(null);
    } else {
      setSuccess(msg);
      setError(null);
    }
    setTimeout(() => {
      setError(null);
      setSuccess(null);
    }, 5000);
  };

  // Test Connection
  const handleTestConnection = async (id, _type) => {
    setTestingId(id);
    try {
      const res = await fetch(`${API_BASE}/connections/${id}/test`, { method: 'POST' });
      const result = await res.json();
      setTestResults(prev => ({ ...prev, [id]: result }));
      if (result.success) {
        showMessage(`Connection test successful`);
      } else {
        showMessage(`Connection test failed: ${result.error || 'Unknown error'}`, true);
      }
    } catch (err) {
      setTestResults(prev => ({ ...prev, [id]: { success: false, error: err.message } }));
      showMessage(`Connection test failed: ${err.message}`, true);
    } finally {
      setTestingId(null);
    }
  };

  // Test LLM Provider
  const handleTestLLM = async (id) => {
    setTestingId(id);
    try {
      const res = await fetch(`${API_BASE}/llm-providers/${id}/test`, { method: 'POST' });
      const result = await res.json();
      if (result.success) {
        showMessage(`LLM provider test successful`);
      } else {
        showMessage(`LLM test failed: ${result.error || 'Check API key and endpoint'}`, true);
      }
    } catch (err) {
      showMessage(`LLM test failed: ${err.message}`, true);
    } finally {
      setTestingId(null);
    }
  };

  // Test Embedding Model
  const handleTestEmbedding = async (id) => {
    setTestingId(id);
    try {
      const res = await fetch(`${API_BASE}/embedding-models/${id}/test`, { method: 'POST' });
      const result = await res.json();
      if (result.success) {
        showMessage(`Embedding model test successful`);
      } else {
        showMessage(`Embedding test failed: ${result.error || 'Check configuration'}`, true);
      }
    } catch (err) {
      showMessage(`Embedding test failed: ${err.message}`, true);
    } finally {
      setTestingId(null);
    }
  };

  // Open modal for add/edit
  const openModal = (type, item = null) => {
    setModalType(type);
    if (type === 'connection' && item) {
      const sanitized = { ...item };
      // Avoid accidentally persisting masked secrets back to the server
      if (typeof sanitized.connection_string === 'string' && sanitized.connection_string.includes('*')) {
        sanitized.connection_string = '';
      }
      setEditItem(sanitized);
    } else {
      setEditItem(item || {});
    }
    setModalOpen(true);
  };

  // Save item
  const handleSave = async () => {
    try {
      let endpoint, method;
      
      switch (modalType) {
        case 'llm':
          endpoint = editItem.id ? `${API_BASE}/llm-providers/${editItem.id}` : `${API_BASE}/llm-providers`;
          break;
        case 'embedding':
          endpoint = editItem.id ? `${API_BASE}/embedding-models/${editItem.id}` : `${API_BASE}/embedding-models`;
          break;
        case 'connection':
          endpoint = editItem.id ? `${API_BASE}/connections/${editItem.id}` : `${API_BASE}/connections`;
          break;
        case 'setting':
          endpoint = editItem.id ? `${API_BASE}/system/${editItem.id}` : `${API_BASE}/system`;
          break;
        case 'flag':
          endpoint = editItem.id ? `${API_BASE}/feature-flags/${editItem.id}` : `${API_BASE}/feature-flags`;
          break;
        default:
          return;
      }
      
      method = editItem.id ? 'PUT' : 'POST';
      
      const res = await fetch(endpoint, {
        method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(editItem)
      });
      
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Save failed');
      }
      
      setModalOpen(false);
      showMessage('Configuration saved successfully');
      fetchData();
    } catch (err) {
      showMessage(`Save failed: ${err.message}`, true);
    }
  };

  // Delete item
  const handleDelete = async (type, id) => {
    if (!confirm('Are you sure you want to delete this configuration?')) return;
    
    try {
      let endpoint;
      switch (type) {
        case 'llm': endpoint = `${API_BASE}/llm-providers/${id}`; break;
        case 'embedding': endpoint = `${API_BASE}/embedding-models/${id}`; break;
        case 'connection': endpoint = `${API_BASE}/connections/${id}`; break;
        case 'setting': endpoint = `${API_BASE}/system/${id}`; break;
        case 'flag': endpoint = `${API_BASE}/feature-flags/${id}`; break;
        default: return;
      }
      
      await fetch(endpoint, { method: 'DELETE' });
      showMessage('Configuration deleted');
      fetchData();
    } catch (err) {
      showMessage(`Delete failed: ${err.message}`, true);
    }
  };

  // Toggle feature flag
  const handleToggleFlag = async (flag) => {
    try {
      await fetch(`${API_BASE}/feature-flags/${flag.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...flag, is_enabled: !flag.is_enabled })
      });
      fetchData();
    } catch (err) {
      showMessage(`Toggle failed: ${err.message}`, true);
    }
  };

  // Clear cache
  const handleClearCache = async () => {
    try {
      await fetch(`${API_BASE}/cache/invalidate`, { method: 'POST' });
      showMessage('Configuration cache cleared');
    } catch (err) {
      showMessage(`Cache clear failed: ${err.message}`, true);
    }
  };

  // Render content based on active tab
  const renderContent = () => {
    switch (activeTab) {
      case 'llm':
        return (
          <div className="admin-config-content">
            <div className="config-section-header">
              <h3>LLM Provider Configurations</h3>
              <button className="btn-primary" onClick={() => openModal('llm')}>
                <i className="fas fa-plus"></i> Add Provider
              </button>
            </div>
            <LLMProvidersTable 
              providers={data.llmProviders} 
              onEdit={(p) => openModal('llm', p)}
              onDelete={(id) => handleDelete('llm', id)}
              onTest={handleTestLLM}
              testingId={testingId}
            />
          </div>
        );
        
      case 'embedding':
        return (
          <div className="admin-config-content">
            <div className="config-section-header">
              <h3>Embedding Model Configurations</h3>
              <button className="btn-primary" onClick={() => openModal('embedding')}>
                <i className="fas fa-plus"></i> Add Model
              </button>
            </div>
            <EmbeddingModelsTable 
              models={data.embeddingModels}
              onEdit={(m) => openModal('embedding', m)}
              onDelete={(id) => handleDelete('embedding', id)}
              onTest={handleTestEmbedding}
              testingId={testingId}
            />
          </div>
        );
        
      case 'connections':
        return (
          <div className="admin-config-content">
            <div className="config-section-header">
              <h3>Connection Configurations</h3>
              <button className="btn-primary" onClick={() => openModal('connection')}>
                <i className="fas fa-plus"></i> Add Connection
              </button>
            </div>
            <ConnectionsTable 
              connections={data.connections}
              onEdit={(c) => openModal('connection', c)}
              onDelete={(id) => handleDelete('connection', id)}
              onTest={(id) => handleTestConnection(id)}
              testingId={testingId}
              testResults={testResults}
            />
          </div>
        );
        
      case 'settings':
        return (
          <div className="admin-config-content">
            <div className="config-section-header">
              <h3>System Settings</h3>
              <button className="btn-primary" onClick={() => openModal('setting')}>
                <i className="fas fa-plus"></i> Add Setting
              </button>
            </div>
            <div style={{ padding: '16px 24px' }}>
              <SystemSettingsTable 
                settings={data.systemConfigs}
                onEdit={(s) => openModal('setting', s)}
                onDelete={(id) => handleDelete('setting', id)}
              />
            </div>
          </div>
        );
        
      case 'flags':
        return (
          <div className="admin-config-content">
            <div className="config-section-header">
              <h3>Feature Flags</h3>
              <button className="btn-primary" onClick={() => openModal('flag')}>
                <i className="fas fa-plus"></i> Add Flag
              </button>
            </div>
            <FeatureFlagsTable 
              flags={data.featureFlags}
              onToggle={handleToggleFlag}
              onEdit={(f) => openModal('flag', f)}
              onDelete={(id) => handleDelete('flag', id)}
            />
          </div>
        );
        
      default:
        return null;
    }
  };

  // Render modal content
  const renderModalContent = () => {
    switch (modalType) {
      case 'llm':
        return <LLMProviderForm provider={editItem} onChange={setEditItem} />;
      case 'connection':
        return <ConnectionForm connection={editItem} onChange={setEditItem} />;
      default:
        return <p>Form not implemented for this type</p>;
    }
  };

  if (loading) {
    return (
      <div className="admin-config-manager">
        <div className="loading-overlay">
          <div className="loading-spinner"></div>
          <span>Loading configuration...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="admin-config-manager">
      {/* Header */}
      <div className="admin-config-header">
        <h2><i className="fas fa-cog"></i> Admin Configuration Center</h2>
        <div className="header-actions">
          <button className="btn-secondary" onClick={fetchData}>
            <i className="fas fa-sync-alt"></i> Refresh
          </button>
          <button className="btn-secondary" onClick={handleClearCache}>
            <i className="fas fa-trash"></i> Clear Cache
          </button>
        </div>
      </div>

      {/* Messages */}
      {error && <div className="alert alert-error"><i className="fas fa-exclamation-circle"></i> {error}</div>}
      {success && <div className="alert alert-success"><i className="fas fa-check-circle"></i> {success}</div>}

      {/* Health Overview */}
      {health && (
        <div className="health-overview">
          <div className={`health-card ${health.status}`}>
            <div className="health-card-title">Overall Status</div>
            <div className="health-card-value">{health.status.toUpperCase()}</div>
          </div>
          <div className="health-card">
            <div className="health-card-title">LLM Providers</div>
            <div className="health-card-value">{data.llmProviders.filter(p => p.status === 'active').length} Active</div>
          </div>
          <div className="health-card">
            <div className="health-card-title">Connections</div>
            <div className="health-card-value">{data.connections.filter(c => c.status === 'active').length} Active</div>
          </div>
          <div className="health-card">
            <div className="health-card-title">Feature Flags</div>
            <div className="health-card-value">{data.featureFlags.filter(f => f.is_enabled).length} Enabled</div>
          </div>
        </div>
      )}

      {/* Tab Navigation */}
      <TabNavigation tabs={tabs} activeTab={activeTab} onTabChange={setActiveTab} />

      {/* Content */}
      {renderContent()}

      {/* Footer */}
      <div className="admin-config-footer">
        <div className="footer-info">
          Last updated: {new Date().toLocaleString()}
        </div>
      </div>

      {/* Modal */}
      <Modal
        isOpen={modalOpen}
        onClose={() => setModalOpen(false)}
        title={editItem?.id ? `Edit ${modalType}` : `Add ${modalType}`}
        footer={
          <>
            <button className="btn-secondary" onClick={() => setModalOpen(false)}>Cancel</button>
            <button className="btn-primary" onClick={handleSave}>Save</button>
          </>
        }
      >
        {renderModalContent()}
      </Modal>
    </div>
  );
}
