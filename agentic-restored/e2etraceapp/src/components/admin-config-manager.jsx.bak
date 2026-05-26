/**
 * Admin Configuration Manager
 * 
 * TCS-styled centralized configuration management UI
 * Row-based layout with test connection support
 */

import React, { useState, useEffect, useCallback } from 'react';

import { API_CONFIG } from '../config/api-config.js';

// Use same-origin by default (Vite proxies `/api` in dev). Can be overridden via VITE_API_BASE_URL.
const API_BASE = `${API_CONFIG?.API_BASE_URL || ''}/api/admin/config`;

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
            <td>{m.dimension ?? '-'}</td>
            <td>
              {m.provider === 'sentence_transformers' ? (
                <span className="api-key-display" style={{ color: 'var(--text-muted)' }}>
                  N/A (Local)
                </span>
              ) : m.custom_api_key ? (
                <span className="api-key-display masked">
                  <i className="fas fa-check-circle"></i> Configured
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

// Embedding Model Form
function EmbeddingModelForm({ model, onChange }) {
  // Treat as edit only when we opened the modal for an existing item.
  // New items will get an id as the user types; that should not flip the form into "edit" mode.
  const isEdit = model?._isNew === false;
  const provider = model?.provider || '';
  const customApiKeyIsMasked = typeof model?.custom_api_key === 'string' && model.custom_api_key.includes('*');

  const setField = (field, value) => {
    onChange({
      ...(model || {}),
      [field]: value,
    });
  };

  const handleProviderChange = (nextProvider) => {
    const next = { ...(model || {}), provider: nextProvider };

    // Friendly defaults for common providers
    if (!isEdit) {
      if (nextProvider === 'sentence_transformers') {
        if (!next.model_name) next.model_name = 'all-MiniLM-L6-v2';
        if (next.dimension == null || next.dimension === '') next.dimension = 384;
        if (!next.name) next.name = 'Local SentenceTransformers';
      }
      if (nextProvider === 'ollama') {
        if (!next.model_name) next.model_name = 'nomic-embed-text';
        if (next.dimension == null || next.dimension === '') next.dimension = 768;
        if (!next.custom_endpoint) next.custom_endpoint = 'http://localhost:11434';
        if (!next.name) next.name = 'Ollama Nomic Embeddings';
      }
      if (nextProvider === 'openai') {
        if (!next.model_name) next.model_name = 'text-embedding-3-small';
        if (next.dimension == null || next.dimension === '') next.dimension = 1536;
        if (!next.custom_endpoint) next.custom_endpoint = 'https://api.openai.com/v1';
        if (!next.name) next.name = 'OpenAI Embeddings';
      }
    }

    onChange(next);
  };

  return (
    <>
      <div className="form-row">
        <div className="form-group">
          <label>ID (optional)</label>
          <input
            type="text"
            value={model.id || ''}
            onChange={e => setField('id', e.target.value)}
            placeholder="e.g., ollama_nomic"
            disabled={isEdit}
          />
        </div>
        <div className="form-group">
          <label>Provider</label>
          <select
            value={provider}
            onChange={e => handleProviderChange(e.target.value)}
            disabled={isEdit}
          >
            <option value="">Select Provider</option>
            <option value="ollama">Ollama</option>
            <option value="sentence_transformers">SentenceTransformers (Local)</option>
            <option value="openai">OpenAI</option>
            <option value="azure_openai">Azure OpenAI</option>
            <option value="huggingface">Hugging Face</option>
            <option value="cohere">Cohere</option>
            <option value="custom">Custom</option>
          </select>
        </div>
      </div>

      <div className="form-row">
        <div className="form-group">
          <label>Display Name</label>
          <input
            type="text"
            value={model.name || ''}
            onChange={e => setField('name', e.target.value)}
            placeholder="e.g., Ollama Nomic Embeddings"
          />
        </div>
        <div className="form-group">
          <label>Status</label>
          <select value={model.status || 'active'} onChange={e => setField('status', e.target.value)}>
            <option value="active">Active</option>
            <option value="inactive">Inactive</option>
            <option value="testing">Testing</option>
            <option value="deprecated">Deprecated</option>
          </select>
        </div>
      </div>

      <div className="form-group">
        <label>Description</label>
        <input
          type="text"
          value={model.description || ''}
          onChange={e => setField('description', e.target.value)}
          placeholder="Optional notes"
        />
      </div>

      <div className="form-row">
        <div className="form-group">
          <label>Model Name</label>
          <input
            type="text"
            value={model.model_name || ''}
            onChange={e => setField('model_name', e.target.value)}
            placeholder={provider === 'ollama' ? 'nomic-embed-text' : 'all-MiniLM-L6-v2'}
            disabled={isEdit}
          />
        </div>
        <div className="form-group">
          <label>Dimension</label>
          <input
            type="number"
            value={model.dimension ?? ''}
            onChange={e => setField('dimension', parseInt(e.target.value, 10) || '')}
            placeholder="e.g., 768"
            disabled={isEdit}
          />
        </div>
      </div>

      <div className="form-row">
        <div className="form-group">
          <label>Max Input Length</label>
          <input
            type="number"
            value={model.max_input_length ?? 512}
            onChange={e => setField('max_input_length', parseInt(e.target.value, 10) || 0)}
          />
        </div>
        <div className="form-group">
          <label>Batch Size</label>
          <input
            type="number"
            value={model.batch_size ?? 32}
            onChange={e => setField('batch_size', parseInt(e.target.value, 10) || 0)}
          />
        </div>
      </div>

      <div className="form-row">
        <div className="form-group">
          <label>Normalize Embeddings</label>
          <select
            value={model.normalize === false ? 'false' : 'true'}
            onChange={e => setField('normalize', e.target.value === 'true')}
          >
            <option value="true">Yes</option>
            <option value="false">No</option>
          </select>
        </div>
        <div className="form-group">
          <label>Default Model</label>
          <select
            value={model.is_default ? 'true' : 'false'}
            onChange={e => setField('is_default', e.target.value === 'true')}
          >
            <option value="false">No</option>
            <option value="true">Yes</option>
          </select>
        </div>
      </div>

      {provider !== 'sentence_transformers' && (
        <div className="form-row">
          <div className="form-group">
            <label>Endpoint (optional)</label>
            <input
              type="text"
              value={model.custom_endpoint || ''}
              onChange={e => setField('custom_endpoint', e.target.value)}
              placeholder={provider === 'ollama' ? 'http://localhost:11434' : 'https://api.openai.com/v1'}
            />
          </div>
          <div className="form-group">
            <label>API Key (optional)</label>
            <input
              type="password"
              value={customApiKeyIsMasked ? '' : (model.custom_api_key || '')}
              onChange={e => setField('custom_api_key', e.target.value)}
              placeholder={provider === 'ollama' ? 'N/A for Ollama' : (customApiKeyIsMasked ? '******** (unchanged)' : 'Enter API key')}
              disabled={provider === 'ollama'}
            />
            {customApiKeyIsMasked && provider !== 'ollama' && (
              <div style={{ color: 'var(--text-muted)', fontSize: '12px', marginTop: '6px' }}>
                API key is masked. Leave blank to keep existing; enter a new value to rotate it.
              </div>
            )}
          </div>
        </div>
      )}
    </>
  );
}

// Connections Table
function ConnectionsTable({ connections, onEdit, onDelete, onTest, testingId, testResults }) {
  const getHostDisplay = (c) => {
    const opts = c.extra_options || {};
    switch ((c.connection_type || '').toLowerCase()) {
      case 'soda_external':
        return opts.python_path || '-';
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
    if (['soda_external', 's3', 'azure_blob', 'local_folder', 'onedrive', 'google_drive', 'powerquery'].includes(type)) {
      return '-';
    }
    return c.port ?? '-';
  };

  const getDatabaseDisplay = (c) => {
    const opts = c.extra_options || {};
    switch ((c.connection_type || '').toLowerCase()) {
      case 'soda_external':
        return (opts.timeout_s ?? '-')
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
        <p>No connection settings (data sources) configured</p>
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
                    <><i className="fas fa-times"></i> {testResults[c.id].error || testResults[c.id].message || 'Failed'}</>
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
          <th>ID</th>
          <th>Name</th>
          <th>Description</th>
          <th>Rollout</th>
          <th>Enabled</th>
          <th>Actions</th>
        </tr>
      </thead>
      <tbody>
        {flags.map(f => (
          <tr key={f.id}>
            <td className="name-cell">{f.id}</td>
            <td className="name-cell">{f.name}</td>
            <td style={{ maxWidth: '300px' }}>{f.description || '-'}</td>
            <td><span className="type-badge">{typeof f.rollout_percentage === 'number' ? `${f.rollout_percentage}%` : '100%'}</span></td>
            <td>
              <label className="toggle-switch">
                <input 
                  type="checkbox" 
                  checked={!!f.enabled} 
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

// System Setting Form
function SystemSettingForm({ setting, onChange }) {
  const isEdit = Boolean(setting?.id);

  const setField = (field, value) => {
    onChange({
      ...(setting || {}),
      [field]: value,
    });
  };

  const isSecret = !!setting?.is_secret;
  const valueDisplay = setting?.value;
  const isMaskedSecretValue = isSecret && typeof valueDisplay === 'string' && valueDisplay.includes('*');

  return (
    <>
      <div className="form-row">
        <div className="form-group">
          <label>Category</label>
          <input
            type="text"
            value={setting.category || ''}
            onChange={e => setField('category', e.target.value)}
            placeholder="e.g., llm"
            disabled={isEdit}
          />
        </div>
        <div className="form-group">
          <label>Key</label>
          <input
            type="text"
            value={setting.key || ''}
            onChange={e => setField('key', e.target.value)}
            placeholder="e.g., default_provider"
            disabled={isEdit}
          />
        </div>
      </div>

      <div className="form-row">
        <div className="form-group">
          <label>Value Type</label>
          <select
            value={setting.value_type || 'string'}
            onChange={e => setField('value_type', e.target.value)}
            disabled={isEdit}
          >
            <option value="string">string</option>
            <option value="number">number</option>
            <option value="boolean">boolean</option>
            <option value="json">json</option>
          </select>
        </div>
        <div className="form-group">
          <label>Enabled</label>
          <select
            value={setting.enabled === false ? 'false' : 'true'}
            onChange={e => setField('enabled', e.target.value === 'true')}
          >
            <option value="true">Yes</option>
            <option value="false">No</option>
          </select>
        </div>
      </div>

      <div className="form-group">
        <label>Description</label>
        <input
          type="text"
          value={setting.description || ''}
          onChange={e => setField('description', e.target.value)}
          placeholder="What is this setting used for?"
        />
      </div>

      <div className="form-group">
        <label>Value</label>
        <input
          type={isSecret ? 'password' : 'text'}
          value={(isMaskedSecretValue ? '' : (setting.value || ''))}
          onChange={e => setField('value', e.target.value)}
          placeholder={isMaskedSecretValue ? '******** (unchanged)' : 'Enter value'}
        />
        {isMaskedSecretValue && (
          <div style={{ color: 'var(--text-muted)', fontSize: '12px', marginTop: '6px' }}>
            Secret value is masked. Leave blank to keep existing; enter a new value to rotate it.
          </div>
        )}
      </div>

      {!isEdit && (
        <div className="form-row">
          <div className="form-group">
            <label>Secret</label>
            <select value={isSecret ? 'true' : 'false'} onChange={e => setField('is_secret', e.target.value === 'true')}>
              <option value="false">No</option>
              <option value="true">Yes</option>
            </select>
          </div>
          <div className="form-group">
            <label>Required</label>
            <select value={setting.is_required ? 'true' : 'false'} onChange={e => setField('is_required', e.target.value === 'true')}>
              <option value="false">No</option>
              <option value="true">Yes</option>
            </select>
          </div>
        </div>
      )}

      <div className="form-row">
        <div className="form-group">
          <label>Default Value (optional)</label>
          <input
            type="text"
            value={setting.default_value || ''}
            onChange={e => setField('default_value', e.target.value)}
            disabled={isEdit}
          />
        </div>
        <div className="form-group">
          <label>Validation Regex (optional)</label>
          <input
            type="text"
            value={setting.validation_regex || ''}
            onChange={e => setField('validation_regex', e.target.value)}
          />
        </div>
      </div>
    </>
  );
}

// Feature Flag Form
function FeatureFlagForm({ flag, onChange }) {
  // Treat as edit only when we opened the modal for an existing item.
  // New items will get an id as the user types; that should not flip the form into "edit" mode.
  const isEdit = flag?._isNew === false;

  const setField = (field, value) => {
    onChange({
      ...(flag || {}),
      [field]: value,
    });
  };

  const targetingText = (() => {
    const v = flag?.targeting_rules;
    if (typeof v === 'string') return v;
    if (v == null) return '';
    try {
      return JSON.stringify(v, null, 2);
    } catch {
      return '';
    }
  })();

  return (
    <>
      <div className="form-row">
        <div className="form-group">
          <label>ID (optional)</label>
          <input
            type="text"
            value={flag.id || ''}
            onChange={e => setField('id', e.target.value)}
            placeholder="e.g., enable_vector_search"
            disabled={isEdit}
          />
        </div>
        <div className="form-group">
          <label>Enabled</label>
          <select value={flag.enabled ? 'true' : 'false'} onChange={e => setField('enabled', e.target.value === 'true')}>
            <option value="false">No</option>
            <option value="true">Yes</option>
          </select>
        </div>
      </div>

      <div className="form-group">
        <label>Name</label>
        <input
          type="text"
          value={flag.name || ''}
          onChange={e => setField('name', e.target.value)}
          placeholder="Human-friendly flag name"
        />
      </div>

      <div className="form-group">
        <label>Description</label>
        <input
          type="text"
          value={flag.description || ''}
          onChange={e => setField('description', e.target.value)}
          placeholder="What does this flag control?"
        />
      </div>

      <div className="form-row">
        <div className="form-group">
          <label>Rollout Percentage</label>
          <input
            type="number"
            min="0"
            max="100"
            value={typeof flag.rollout_percentage === 'number' ? flag.rollout_percentage : 100}
            onChange={e => setField('rollout_percentage', parseInt(e.target.value, 10))}
          />
        </div>
        <div className="form-group">
          <label>Targeting Rules (JSON, optional)</label>
          <textarea
            value={targetingText}
            onChange={e => setField('targeting_rules', e.target.value)}
            placeholder='{"users": ["alice"], "tenants": ["t1"]}'
            rows={6}
          />
        </div>
      </div>
    </>
  );
}

// LLM Provider Form
function LLMProviderForm({ provider, onChange }) {
  // New items will get an id as the user types; that should not flip the form into "edit" mode.
  const isEdit = provider?._isNew === false;
  return (
    <>
      <div className="form-row">
        <div className="form-group">
          <label>ID (optional)</label>
          <input
            type="text"
            value={provider.id || ''}
            onChange={e => onChange({ ...provider, id: e.target.value })}
            placeholder="e.g., openai_primary"
            disabled={isEdit}
          />
        </div>
        <div className="form-group">
          <label>Provider</label>
          <select
            value={provider.provider || ''}
            onChange={e => onChange({ ...provider, provider: e.target.value })}
            disabled={isEdit}
          >
            <option value="">Select Provider</option>
            <option value="openai">OpenAI</option>
            <option value="anthropic">Anthropic</option>
            <option value="azure_openai">Azure OpenAI</option>
            <option value="ollama">Ollama</option>
            <option value="huggingface">Hugging Face</option>
          </select>
        </div>
      </div>
      <div className="form-row">
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
  // New items will get an id as the user types; that should not flip the form into "edit" mode.
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
    // These are *UI requirements* to prevent confusing backend 422s and to avoid saving unusable configs.
    // Tokens/keys are generally optional to save, but required to successfully test.
    const saveRequired = ['Connection Type', 'Name'];
    const testRequired = [];

    if (isApiLike) {
      saveRequired.push(type === 'odata' ? 'Service URL (Base URL)' : 'Base URL / Endpoint');
      const at = authType;
      if (at === 'bearer' || at === 'oauth2') testRequired.push('Access Token');
      if (at === 'api_key') testRequired.push('API Key');
      if (at === 'basic') testRequired.push('Username', 'Password');
    }

    // DB-like connections: allow either a connection string/URI OR discrete host/port fields.
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
      // Backend requires container, and at least one of connection_string or account_name to be meaningful.
      saveRequired.push('Container', 'Connection String/SAS OR Account Name');
      // Testing needs either a connection string/SAS, or (account_name + account_key).
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
          <label>
            Connection Type <span style={{ color: 'var(--danger)', fontWeight: 700 }}>*</span>
          </label>
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
          <label>
            Name <span style={{ color: 'var(--danger)', fontWeight: 700 }}>*</span>
          </label>
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
        <div
          style={{
            background: 'rgba(0,0,0,0.08)',
            border: '1px solid rgba(255,255,255,0.08)',
            borderRadius: '10px',
            padding: '10px 12px',
            marginBottom: '12px',
            fontSize: '12px',
            color: 'var(--text-muted)'
          }}
        >
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
    { id: 'connections', label: 'Connection Settings (Data Sources)', icon: 'fas fa-plug', count: data.connections.length },
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
      setError('Failed to load configuration data');
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
        showMessage(`Connection test failed: ${result.error || result.message || 'Unknown error'}`, true);
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
      setEditItem({ ...sanitized, _isNew: false });
    } else {
      if (item) {
        setEditItem({ ...item, _isNew: false });
      } else {
        setEditItem({ _isNew: true });
      }
    }
    setModalOpen(true);
  };

  // Save item
  const handleSave = async () => {
    try {
      let endpoint, method;
      const isEdit = editItem?._isNew === false;

      const getSaveValidationError = () => {
        if (!editItem) return 'Nothing to save';

        if (modalType === 'connection') {
          const ct = String(editItem.connection_type || '').trim();
          const nm = String(editItem.name || '').trim();
          if (!ct) return 'Connection Type is required.';
          if (!nm) return 'Name is required.';

          const apiLike = ['api', 'rest_api', 'webapi', 'openapi', 'odata'].includes(ct.toLowerCase());
          if (apiLike) {
            const endpointUrl = String(editItem.connection_string || '').trim();
            if (!endpointUrl) return 'Base URL / Endpoint (or Service URL) is required for API/OData/OpenAPI connections.';
          }
        }

        if (modalType === 'llm') {
          const provider = String(editItem.provider || '').trim();
          const name = String(editItem.name || '').trim();
          if (!provider) return 'Provider is required.';
          if (!name) return 'Name is required.';
        }

        if (modalType === 'embedding') {
          const provider = String(editItem.provider || '').trim();
          const name = String(editItem.name || '').trim();
          const modelName = String(editItem.model_name || '').trim();
          const dim = editItem.dimension;
          if (!provider) return 'Provider is required.';
          if (!name) return 'Name is required.';
          if (!modelName) return 'Model name is required.';
          if (dim === undefined || dim === null || String(dim).trim() === '') return 'Dimension is required.';
        }

        return null;
      };

      const formatApiError = (errPayload) => {
        const detail = errPayload?.detail;
        if (!detail) return errPayload?.message || errPayload?.error || null;
        if (typeof detail === 'string') return detail;
        if (Array.isArray(detail)) {
          const parts = detail.map(d => {
            const locArr = Array.isArray(d?.loc) ? d.loc : [];
            // FastAPI loc is usually ["body", "field", ...]
            const loc = locArr.slice(1).join('.') || 'field';
            const msg = d?.msg || 'invalid value';
            return `${loc}: ${msg}`;
          });
          return parts.join('; ');
        }
        return String(detail);
      };

      const validationError = getSaveValidationError();
      if (validationError) {
        showMessage(validationError, true);
        return;
      }

      const stripEmpty = (obj) => {
        const out = {};
        Object.entries(obj || {}).forEach(([k, v]) => {
          if (v === undefined) return;
          if (v === null) return;
          if (typeof v === 'string' && v.trim() === '') return;
          out[k] = v;
        });
        return out;
      };

      const buildPayload = () => {
        switch (modalType) {
          case 'llm': {
            if (!isEdit) {
              // create: id is optional (server will generate one if omitted)
              return stripEmpty({
                id: editItem.id,
                provider: editItem.provider,
                name: editItem.name,
                description: editItem.description,
                api_key: editItem.api_key,
                api_endpoint: editItem.api_endpoint,
                api_version: editItem.api_version,
                azure_deployment: editItem.azure_deployment,
                azure_resource_name: editItem.azure_resource_name,
                default_chat_model: editItem.default_chat_model,
                default_completion_model: editItem.default_completion_model,
                default_embedding_model: editItem.default_embedding_model,
                default_temperature: editItem.default_temperature,
                default_max_tokens: editItem.default_max_tokens,
                default_top_p: editItem.default_top_p,
                rate_limit_rpm: editItem.rate_limit_rpm,
                rate_limit_tpm: editItem.rate_limit_tpm,
                status: editItem.status,
                is_default: editItem.is_default,
                priority: editItem.priority,
                extra_config: editItem.extra_config,
              });
            }

            // update: do not send api_key unless user typed it (avoid clearing existing keys)
            return stripEmpty({
              name: editItem.name,
              description: editItem.description,
              api_endpoint: editItem.api_endpoint,
              api_version: editItem.api_version,
              azure_deployment: editItem.azure_deployment,
              azure_resource_name: editItem.azure_resource_name,
              default_chat_model: editItem.default_chat_model,
              default_temperature: editItem.default_temperature,
              default_max_tokens: editItem.default_max_tokens,
              rate_limit_rpm: editItem.rate_limit_rpm,
              rate_limit_tpm: editItem.rate_limit_tpm,
              status: editItem.status,
              is_default: editItem.is_default,
              priority: editItem.priority,
              extra_config: editItem.extra_config,
              ...(typeof editItem.api_key === 'string' && editItem.api_key.trim() ? { api_key: editItem.api_key } : {}),
            });
          }

          case 'embedding': {
            if (!isEdit) {
              return stripEmpty({
                id: editItem.id,
                provider: editItem.provider,
                name: editItem.name,
                description: editItem.description,
                model_name: editItem.model_name,
                dimension: editItem.dimension,
                max_input_length: editItem.max_input_length,
                llm_provider_id: editItem.llm_provider_id,
                custom_endpoint: editItem.custom_endpoint,
                custom_api_key: editItem.custom_api_key,
                batch_size: editItem.batch_size,
                normalize: editItem.normalize,
                cost_per_1k_tokens: editItem.cost_per_1k_tokens,
                status: editItem.status,
                is_default: editItem.is_default,
              });
            }

            // update model only supports these fields
            const update = stripEmpty({
              name: editItem.name,
              description: editItem.description,
              max_input_length: editItem.max_input_length,
              llm_provider_id: editItem.llm_provider_id,
              batch_size: editItem.batch_size,
              normalize: editItem.normalize,
              status: editItem.status,
              is_default: editItem.is_default,
            });

            // Only send secrets/endpoint if user provided a value (avoid wiping).
            if (typeof editItem.custom_endpoint === 'string' && editItem.custom_endpoint.trim()) {
              update.custom_endpoint = editItem.custom_endpoint;
            }
            if (typeof editItem.custom_api_key === 'string' && editItem.custom_api_key.trim()) {
              if (!editItem.custom_api_key.includes('*')) {
                update.custom_api_key = editItem.custom_api_key;
              }
            }

            return update;
          }

          case 'connection': {
            if (!isEdit) {
              return stripEmpty({
                id: editItem.id,
                connection_type: editItem.connection_type,
                name: editItem.name,
                description: editItem.description,
                connection_string: editItem.connection_string,
                host: editItem.host,
                port: editItem.port,
                database: editItem.database,
                username: editItem.username,
                password: editItem.password,
                use_ssl: editItem.use_ssl,
                ssl_cert_path: editItem.ssl_cert_path,
                pool_size: editItem.pool_size,
                max_overflow: editItem.max_overflow,
                pool_timeout: editItem.pool_timeout,
                extra_options: editItem.extra_options,
                status: editItem.status,
                is_default: editItem.is_default,
              });
            }

            // update: avoid sending empty secrets
            const base = stripEmpty({
              name: editItem.name,
              description: editItem.description,
              host: editItem.host,
              port: editItem.port,
              database: editItem.database,
              username: editItem.username,
              use_ssl: editItem.use_ssl,
              pool_size: editItem.pool_size,
              status: editItem.status,
              is_default: editItem.is_default,
            });

            if (typeof editItem.password === 'string' && editItem.password.trim()) {
              base.password = editItem.password;
            }
            if (typeof editItem.connection_string === 'string' && editItem.connection_string.trim() && !editItem.connection_string.includes('*')) {
              base.connection_string = editItem.connection_string;
            }
            return base;
          }

          case 'setting': {
            if (!isEdit) {
              return stripEmpty({
                category: editItem.category,
                key: editItem.key,
                value: editItem.value,
                value_type: editItem.value_type,
                description: editItem.description,
                is_secret: editItem.is_secret,
                is_required: editItem.is_required,
                default_value: editItem.default_value,
                validation_regex: editItem.validation_regex,
                enabled: editItem.enabled,
              });
            }

            // Update supports: value, description, enabled, validation_regex
            const update = stripEmpty({
              description: editItem.description,
              enabled: editItem.enabled,
              validation_regex: editItem.validation_regex,
            });

            // Only send value if user actually provided a new one.
            if (typeof editItem.value === 'string' && editItem.value.trim() && !editItem.value.includes('*')) {
              update.value = editItem.value;
            }
            return update;
          }

          case 'flag': {
            const normalizeTargeting = () => {
              const v = editItem.targeting_rules;
              if (v === undefined || v === null) return undefined;
              if (typeof v === 'string') {
                if (!v.trim()) return undefined;
                try {
                  return JSON.parse(v);
                } catch (_e) {
                  throw new Error('Targeting Rules must be valid JSON');
                }
              }
              return v;
            };

            if (!isEdit) {
              return stripEmpty({
                id: editItem.id,
                name: editItem.name,
                description: editItem.description,
                enabled: editItem.enabled,
                rollout_percentage: editItem.rollout_percentage,
                targeting_rules: normalizeTargeting(),
              });
            }

            return stripEmpty({
              name: editItem.name,
              description: editItem.description,
              enabled: editItem.enabled,
              rollout_percentage: editItem.rollout_percentage,
              targeting_rules: normalizeTargeting(),
            });
          }

          default:
            return editItem;
        }
      };
      
      switch (modalType) {
        case 'llm':
          endpoint = isEdit ? `${API_BASE}/llm-providers/${editItem.id}` : `${API_BASE}/llm-providers`;
          break;
        case 'embedding':
          endpoint = isEdit ? `${API_BASE}/embedding-models/${editItem.id}` : `${API_BASE}/embedding-models`;
          break;
        case 'connection':
          endpoint = isEdit ? `${API_BASE}/connections/${editItem.id}` : `${API_BASE}/connections`;
          break;
        case 'setting':
          endpoint = isEdit ? `${API_BASE}/system/${editItem.id}` : `${API_BASE}/system`;
          break;
        case 'flag':
          endpoint = isEdit ? `${API_BASE}/feature-flags/${editItem.id}` : `${API_BASE}/feature-flags`;
          break;
        default:
          return;
      }
      
      method = isEdit ? 'PUT' : 'POST';

      const payload = buildPayload();
      
      const res = await fetch(endpoint, {
        method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      
      if (!res.ok) {
        let errPayload = null;
        try {
          errPayload = await res.json();
        } catch (_e) {
          // ignore
        }
        const msg = formatApiError(errPayload) || `Save failed (HTTP ${res.status})`;
        throw new Error(msg);
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
        body: JSON.stringify({ enabled: !flag.enabled })
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
      case 'embedding':
        return <EmbeddingModelForm model={editItem} onChange={setEditItem} />;
      case 'connection':
        return <ConnectionForm connection={editItem} onChange={setEditItem} />;
      case 'setting':
        return <SystemSettingForm setting={editItem} onChange={setEditItem} />;
      case 'flag':
        return <FeatureFlagForm flag={editItem} onChange={setEditItem} />;
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

  // Disable Save when required fields are missing (prevents confusing 422 errors).
  const getSaveDisabledReason = () => {
    if (!modalOpen) return null;
    if (!editItem) return 'Nothing to save';

    if (modalType === 'connection') {
      const ct = String(editItem.connection_type || '').trim();
      const nm = String(editItem.name || '').trim();
      if (!ct) return 'Connection Type is required';
      if (!nm) return 'Name is required';

      const ctLower = ct.toLowerCase();
      const apiLike = ['api', 'rest_api', 'webapi', 'openapi', 'odata'].includes(ctLower);
      if (apiLike) {
        const endpointUrl = String(editItem.connection_string || '').trim();
        if (!endpointUrl) return 'Base URL / Endpoint is required for API-like connections';
      }

      if (ctLower === 'postgres') {
        const connStr = String(editItem.connection_string || '').trim();
        if (!connStr) {
          if (!String(editItem.host || '').trim()) return 'Host is required for Postgres (or provide connection_string)';
          if (editItem.port === undefined || editItem.port === null || String(editItem.port).trim() === '') return 'Port is required for Postgres (or provide connection_string)';
          if (!String(editItem.database || '').trim()) return 'Database is required for Postgres (or provide connection_string)';
          if (!String(editItem.username || '').trim()) return 'Username is required for Postgres (or provide connection_string)';
        }
      }

      if (ctLower === 'neo4j' || ctLower === 'opensearch' || ctLower === 'redis') {
        const connStr = String(editItem.connection_string || '').trim();
        if (!connStr) {
          if (!String(editItem.host || '').trim()) return `Host is required for ${ct} (or provide connection_string)`;
          if (editItem.port === undefined || editItem.port === null || String(editItem.port).trim() === '') return `Port is required for ${ct} (or provide connection_string)`;
        }
      }

      if (ctLower === 'local_folder') {
        const folder = String(editItem.extra_options?.folder_path || '').trim();
        if (!folder) return 'Folder Path is required for Local Folder';
      }

      if (ctLower === 's3') {
        const bucket = String(editItem.extra_options?.bucket || '').trim();
        const region = String(editItem.extra_options?.region || '').trim();
        if (!bucket) return 'Bucket is required for S3';
        if (!region) return 'Region is required for S3';
      }

      if (ctLower === 'azure_blob') {
        const container = String(editItem.extra_options?.container || '').trim();
        if (!container) return 'Container is required for Azure Blob';
        const connStr = String(editItem.connection_string || '').trim();
        const accountName = String(editItem.extra_options?.account_name || '').trim();
        if (!connStr && !accountName) return 'Provide Connection String/SAS OR Account Name for Azure Blob';
      }

      if (ctLower === 'soda_external') {
        const pythonPath = String(editItem.extra_options?.python_path || '').trim();
        if (!pythonPath) return 'Python Interpreter Path is required for Soda External Runner';
      }
    }

    if (modalType === 'llm') {
      const provider = String(editItem.provider || '').trim();
      const name = String(editItem.name || '').trim();
      if (!provider) return 'Provider is required';
      if (!name) return 'Name is required';
    }

    if (modalType === 'embedding') {
      const provider = String(editItem.provider || '').trim();
      const name = String(editItem.name || '').trim();
      const modelName = String(editItem.model_name || '').trim();
      const dim = editItem.dimension;
      if (!provider) return 'Provider is required';
      if (!name) return 'Name is required';
      if (!modelName) return 'Model name is required';
      if (dim === undefined || dim === null || String(dim).trim() === '') return 'Dimension is required';
    }

    return null;
  };

  const saveDisabledReason = getSaveDisabledReason();
  const saveDisabled = Boolean(saveDisabledReason);

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
        title={editItem?._isNew === false ? `Edit ${modalType}` : `Add ${modalType}`}
        footer={
          <>
            <button className="btn-secondary" onClick={() => setModalOpen(false)}>Cancel</button>
            <button
              className="btn-primary"
              onClick={handleSave}
              disabled={saveDisabled}
              title={saveDisabledReason || ''}
            >
              Save
            </button>
          </>
        }
      >
        {renderModalContent()}
      </Modal>
    </div>
  );
}
