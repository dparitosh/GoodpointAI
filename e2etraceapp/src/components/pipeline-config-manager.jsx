/**
 * Pipeline Configuration Manager Component
 * 
 * Provides UI for managing file patterns, pipeline templates, 
 * search configurations, and index settings stored in PostgreSQL.
 * 
 * Uses compact row-based table layout to reduce scrolling.
 */

import { useState, useEffect, useCallback } from 'react';
import API_CONFIG from '../config/api-config';
import './pipeline-config-manager.css';

const API_BASE = `${API_CONFIG.API_BASE_URL || ''}/config`;

// Category icons mapping (FontAwesome classes)
const CATEGORY_ICONS = {
  document: 'fas fa-file-alt',
  cad: 'fas fa-drafting-compass',
  simulation: 'fas fa-flask',
  data: 'fas fa-database',
  text: 'fas fa-file-lines',
  image: 'fas fa-image',
  video: 'fas fa-video',
  archive: 'fas fa-file-archive',
  binary: 'fas fa-microchip',
  other: 'fas fa-paperclip',
};

// Pipeline type colors
const PIPELINE_COLORS = {
  search_index: '#24A148',
  knowledge_graph: '#0066CC',
  database_migration: '#FF832B',
  plm_graph_sync: '#8A3FFC',
};

/**
 * File Pattern Editor Dialog
 */
function FilePatternDialog({ pattern, onSave, onClose, categories }) {
  const [formData, setFormData] = useState({
    category: pattern?.category || 'document',
    pattern: pattern?.pattern || '*.txt',
    description: pattern?.description || '',
    mime_type: pattern?.mime_type || '',
    parser_hint: pattern?.parser_hint || '',
    enabled: pattern?.enabled ?? true,
  });

  const handleSubmit = (e) => {
    e.preventDefault();
    onSave(formData);
  };

  return (
    <div className="config-dialog-overlay" onClick={onClose}>
      <div className="config-dialog" onClick={(e) => e.stopPropagation()}>
        <h3>{pattern?.id ? 'Edit File Pattern' : 'Add File Pattern'}</h3>
        <form onSubmit={handleSubmit}>
          <div className="form-row">
            <div className="form-group">
              <label>Category</label>
              <select 
                value={formData.category} 
                onChange={(e) => setFormData({ ...formData, category: e.target.value })}
              >
                {categories.map((cat) => (
                  <option key={cat} value={cat}>
                    {cat.charAt(0).toUpperCase() + cat.slice(1)}
                  </option>
                ))}
              </select>
            </div>
            <div className="form-group">
              <label>Pattern</label>
              <input
                type="text"
                value={formData.pattern}
                onChange={(e) => setFormData({ ...formData, pattern: e.target.value })}
                placeholder="*.pdf"
                required
              />
            </div>
          </div>
          
          <div className="form-row">
            <div className="form-group">
              <label>MIME Type</label>
              <input
                type="text"
                value={formData.mime_type}
                onChange={(e) => setFormData({ ...formData, mime_type: e.target.value })}
                placeholder="application/pdf"
              />
            </div>
            <div className="form-group">
              <label>Parser Hint</label>
              <input
                type="text"
                value={formData.parser_hint}
                onChange={(e) => setFormData({ ...formData, parser_hint: e.target.value })}
                placeholder="pdf_parser"
              />
            </div>
          </div>
          
          <div className="form-group">
            <label>Description</label>
            <input
              type="text"
              value={formData.description}
              onChange={(e) => setFormData({ ...formData, description: e.target.value })}
              placeholder="PDF documents"
            />
          </div>
          
          <div className="form-group checkbox-group">
            <label>
              <input
                type="checkbox"
                checked={formData.enabled}
                onChange={(e) => setFormData({ ...formData, enabled: e.target.checked })}
              />
              Enabled
            </label>
          </div>
          
          <div className="dialog-actions">
            <button type="button" className="btn-secondary" onClick={onClose}>Cancel</button>
            <button type="submit" className="btn-primary">Save</button>
          </div>
        </form>
      </div>
    </div>
  );
}

/**
 * File Patterns Section - Table Layout
 */
function FilePatternSection({ patterns, categories, onRefresh }) {
  const [showDialog, setShowDialog] = useState(false);
  const [editingPattern, setEditingPattern] = useState(null);
  const [filterCategory, setFilterCategory] = useState('');
  const [_saving, setSaving] = useState(false);

  const filteredPatterns = filterCategory
    ? patterns.filter((p) => p.category === filterCategory)
    : patterns;

  // Sort by category then pattern
  const sortedPatterns = [...filteredPatterns].sort((a, b) => {
    if (a.category !== b.category) return a.category.localeCompare(b.category);
    return a.pattern.localeCompare(b.pattern);
  });

  const handleSave = async (formData) => {
    setSaving(true);
    try {
      const url = editingPattern?.id
        ? `${API_BASE}/file-patterns/${editingPattern.id}`
        : `${API_BASE}/file-patterns`;
      const method = editingPattern?.id ? 'PUT' : 'POST';

      const response = await fetch(url, {
        method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(formData),
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to save pattern');
      }

      setShowDialog(false);
      setEditingPattern(null);
      onRefresh();
    } catch (error) {
      alert(`Error: ${error.message}`);
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (patternId) => {
    if (!confirm('Are you sure you want to delete this pattern?')) return;
    
    try {
      const response = await fetch(`${API_BASE}/file-patterns/${patternId}`, {
        method: 'DELETE',
      });
      if (!response.ok) throw new Error('Failed to delete');
      onRefresh();
    } catch (error) {
      alert(`Error: ${error.message}`);
    }
  };

  const handleToggleEnabled = async (pattern) => {
    try {
      await fetch(`${API_BASE}/file-patterns/${pattern.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ enabled: !pattern.enabled }),
      });
      onRefresh();
    } catch (error) {
      alert(`Error: ${error.message}`);
    }
  };

  return (
    <div className="config-section">
      <div className="section-header">
        <h3><i className="fas fa-folder"></i> File Patterns</h3>
        <div className="section-actions">
          <select 
            value={filterCategory} 
            onChange={(e) => setFilterCategory(e.target.value)}
            className="filter-select"
          >
            <option value="">All Categories ({patterns.length})</option>
            {categories.map((cat) => (
              <option key={cat} value={cat}>
                {cat} ({patterns.filter(p => p.category === cat).length})
              </option>
            ))}
          </select>
          <button 
            className="btn-primary btn-sm"
            onClick={() => {
              setEditingPattern(null);
              setShowDialog(true);
            }}
          >
            <i className="fas fa-plus"></i> Add Pattern
          </button>
        </div>
      </div>

      <div className="config-table-compact">
        <table className="compact-table">
          <thead>
            <tr>
              <th>Category</th>
              <th>Pattern</th>
              <th>Description</th>
              <th>MIME Type</th>
              <th>Parser</th>
              <th>Status</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {sortedPatterns.map((pattern) => (
              <tr key={pattern.id} className={!pattern.enabled ? 'row-disabled' : ''}>
                <td>
                  <span className="category-badge-sm">
                    <i className={CATEGORY_ICONS[pattern.category] || 'fas fa-paperclip'}></i>
                    {pattern.category}
                  </span>
                </td>
                <td><code className="pattern-code-sm">{pattern.pattern}</code></td>
                <td className="text-muted">{pattern.description || '-'}</td>
                <td className="text-muted">{pattern.mime_type || '-'}</td>
                <td className="text-muted">{pattern.parser_hint || '-'}</td>
                <td>
                  <span className={`status-badge-sm ${pattern.enabled ? 'status-active' : 'status-inactive'}`}>
                    {pattern.enabled ? 'Active' : 'Inactive'}
                  </span>
                </td>
                <td>
                  <div className="action-buttons-sm">
                    <button
                      className={`btn-icon-sm ${pattern.enabled ? 'btn-success' : ''}`}
                      onClick={() => handleToggleEnabled(pattern)}
                      title={pattern.enabled ? 'Disable' : 'Enable'}
                    >
                      <i className={`fas ${pattern.enabled ? 'fa-toggle-on' : 'fa-toggle-off'}`}></i>
                    </button>
                    <button
                      className="btn-icon-sm"
                      onClick={() => {
                        setEditingPattern(pattern);
                        setShowDialog(true);
                      }}
                      title="Edit"
                    >
                      <i className="fas fa-edit"></i>
                    </button>
                    <button
                      className="btn-icon-sm btn-danger"
                      onClick={() => handleDelete(pattern.id)}
                      title="Delete"
                    >
                      <i className="fas fa-trash"></i>
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {sortedPatterns.length === 0 && (
          <div className="empty-state">No file patterns found</div>
        )}
      </div>

      {showDialog && (
        <FilePatternDialog
          pattern={editingPattern}
          categories={categories}
          onSave={handleSave}
          onClose={() => {
            setShowDialog(false);
            setEditingPattern(null);
          }}
        />
      )}
    </div>
  );
}

/**
 * Pipeline Templates Section - Compact Table Layout
 */
function PipelineTemplateSection({ templates }) {
  return (
    <div className="config-section">
      <div className="section-header">
        <h3><i className="fas fa-sync-alt"></i> Pipeline Templates</h3>
      </div>

      <div className="config-table-compact">
        <table className="compact-table">
          <thead>
            <tr>
              <th>Name</th>
              <th>Type</th>
              <th>Data</th>
              <th>Source → Target</th>
              <th>Categories</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {templates.map((template) => (
              <tr key={template.id} className={!template.enabled ? 'row-disabled' : ''}>
                <td>
                  <div className="template-name-cell">
                    <span 
                      className="pipeline-dot" 
                      style={{backgroundColor: PIPELINE_COLORS[template.pipeline_type] || '#666'}}
                    ></span>
                    <strong>{template.name}</strong>
                    {template.is_system && <i className="fas fa-lock system-icon"></i>}
                  </div>
                </td>
                <td><span className="type-badge-sm">{template.pipeline_type.replace(/_/g, ' ')}</span></td>
                <td><span className={`data-badge-sm ${template.data_type}`}>{template.data_type}</span></td>
                <td className="text-muted">{template.source_type} → {template.target_type}</td>
                <td>
                  {template.file_patterns && template.file_patterns.length > 0 ? (
                    <span className="category-count">{template.file_patterns.length} types</span>
                  ) : '-'}
                </td>
                <td>
                  <span className={`status-badge-sm ${template.enabled ? 'status-active' : 'status-inactive'}`}>
                    {template.enabled ? 'Active' : 'Inactive'}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {templates.length === 0 && (
          <div className="empty-state">No pipeline templates found</div>
        )}
      </div>
    </div>
  );
}

/**
 * Search Configuration Section - Table Layout
 */
function SearchConfigSection({ configs, onRefresh }) {
  const handleToggleDefault = async (config) => {
    try {
      await fetch(`${API_BASE}/search-configs/${config.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ is_default: true }),
      });
      onRefresh();
    } catch (error) {
      alert(`Error: ${error.message}`);
    }
  };

  const handleToggleEnabled = async (config) => {
    try {
      await fetch(`${API_BASE}/search-configs/${config.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ enabled: !config.enabled }),
      });
      onRefresh();
    } catch (error) {
      alert(`Error: ${error.message}`);
    }
  };

  const searchModeIcons = {
    semantic: 'fas fa-spell-check',
    vector: 'fas fa-vector-square',
    hybrid: 'fas fa-random',
  };

  return (
    <div className="config-section">
      <div className="section-header">
        <h3><i className="fas fa-search"></i> Search Configurations</h3>
      </div>

      <div className="config-table-container">
        <table className="config-table">
          <thead>
            <tr>
              <th style={{width: '180px'}}>Name</th>
              <th style={{width: '100px'}}>Mode</th>
              <th style={{width: '200px'}}>Model</th>
              <th style={{width: '100px'}}>Dimensions</th>
              <th style={{width: '100px'}}>Threshold</th>
              <th style={{width: '80px'}}>Default</th>
              <th style={{width: '80px'}}>Status</th>
              <th style={{width: '120px'}}>Actions</th>
            </tr>
          </thead>
          <tbody>
            {configs.map((config) => (
              <tr key={config.id} className={!config.enabled ? 'row-disabled' : ''}>
                <td>
                  <strong>{config.name}</strong>
                  {config.description && (
                    <div className="text-muted text-small">{config.description}</div>
                  )}
                </td>
                <td>
                  <span className="mode-badge">
                    <i className={searchModeIcons[config.search_mode] || 'fas fa-search'}></i>
                    {config.search_mode}
                  </span>
                </td>
                <td className="text-muted text-small">{config.model_name || '-'}</td>
                <td className="text-muted">{config.vector_dimension || '-'}</td>
                <td className="text-muted">{config.similarity_threshold || '-'}</td>
                <td>
                  {config.is_default && (
                    <span className="default-badge">
                      <i className="fas fa-star"></i>
                    </span>
                  )}
                </td>
                <td>
                  <span className={`status-badge ${config.enabled ? 'status-active' : 'status-inactive'}`}>
                    {config.enabled ? 'Active' : 'Inactive'}
                  </span>
                </td>
                <td>
                  <div className="action-buttons">
                    <button
                      className={`btn-icon ${config.enabled ? 'btn-success' : ''}`}
                      onClick={() => handleToggleEnabled(config)}
                      title={config.enabled ? 'Disable' : 'Enable'}
                    >
                      <i className={`fas ${config.enabled ? 'fa-toggle-on' : 'fa-toggle-off'}`}></i>
                    </button>
                    {!config.is_default && config.enabled && (
                      <button
                        className="btn-icon"
                        onClick={() => handleToggleDefault(config)}
                        title="Set as Default"
                      >
                        <i className="fas fa-star"></i>
                      </button>
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {configs.length === 0 && (
          <div className="empty-state">No search configurations found</div>
        )}
      </div>
    </div>
  );
}

/**
 * Index Configuration Section - Table Layout
 */
function IndexConfigSection({ configs }) {
  return (
    <div className="config-section">
      <div className="section-header">
        <h3><i className="fas fa-book"></i> Index Configurations</h3>
      </div>

      <div className="config-table-container">
        <table className="config-table">
          <thead>
            <tr>
              <th style={{width: '200px'}}>Name</th>
              <th style={{width: '80px'}}>Shards</th>
              <th style={{width: '80px'}}>Replicas</th>
              <th style={{width: '80px'}}>KNN</th>
              <th style={{width: '150px'}}>Vector Field</th>
              <th style={{width: '100px'}}>Dimensions</th>
              <th style={{width: '80px'}}>Status</th>
              <th style={{width: '80px'}}>System</th>
            </tr>
          </thead>
          <tbody>
            {configs.map((config) => (
              <tr key={config.id} className={!config.enabled ? 'row-disabled' : ''}>
                <td>
                  <strong>{config.name}</strong>
                  {config.description && (
                    <div className="text-muted text-small">{config.description}</div>
                  )}
                </td>
                <td className="text-center">{config.settings?.number_of_shards || 1}</td>
                <td className="text-center">{config.settings?.number_of_replicas || 0}</td>
                <td className="text-center">
                  {config.knn_enabled ? (
                    <span className="knn-badge">
                      <i className="fas fa-check"></i>
                    </span>
                  ) : (
                    <span className="text-muted">-</span>
                  )}
                </td>
                <td className="text-muted text-small">{config.vector_field || '-'}</td>
                <td className="text-muted">{config.vector_dimension || '-'}</td>
                <td>
                  <span className={`status-badge ${config.enabled ? 'status-active' : 'status-inactive'}`}>
                    {config.enabled ? 'Active' : 'Inactive'}
                  </span>
                </td>
                <td>
                  {config.is_system && (
                    <span className="system-badge">
                      <i className="fas fa-lock"></i>
                    </span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {configs.length === 0 && (
          <div className="empty-state">No index configurations found</div>
        )}
      </div>
    </div>
  );
}

/**
 * Main Pipeline Configuration Manager Component
 */
export default function PipelineConfigManager() {
  const [activeTab, setActiveTab] = useState('patterns');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [data, setData] = useState({
    file_patterns: [],
    pipeline_templates: [],
    search_configs: [],
    index_configs: [],
  });
  const [categories, setCategories] = useState([]);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [allConfigsRes, categoriesRes] = await Promise.all([
        fetch(`${API_BASE}/all?enabled_only=false`),
        fetch(`${API_BASE}/categories`),
      ]);

      if (!allConfigsRes.ok) throw new Error('Failed to fetch configurations');
      if (!categoriesRes.ok) throw new Error('Failed to fetch categories');

      const allConfigs = await allConfigsRes.json();
      const categoriesData = await categoriesRes.json();

      setData(allConfigs);
      setCategories(categoriesData.file_categories || []);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  if (loading) {
    return (
      <div className="config-manager loading">
        <div className="loading-spinner">
          <i className="fas fa-spinner fa-spin"></i> Loading configurations...
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="config-manager error">
        <div className="error-message">
          <h3><i className="fas fa-exclamation-triangle"></i> Error Loading Configurations</h3>
          <p>{error}</p>
          <button onClick={fetchData} className="btn-primary">
            <i className="fas fa-redo"></i> Retry
          </button>
        </div>
      </div>
    );
  }

  const tabs = [
    { id: 'patterns', icon: 'fas fa-folder', label: 'File Patterns', count: data.file_patterns.length },
    { id: 'templates', icon: 'fas fa-sync-alt', label: 'Pipelines', count: data.pipeline_templates.length },
    { id: 'search', icon: 'fas fa-search', label: 'Search', count: data.search_configs.length },
    { id: 'indexes', icon: 'fas fa-book', label: 'Indexes', count: data.index_configs.length },
  ];

  return (
    <div className="config-manager">
      <div className="config-header">
        <h2><i className="fas fa-search-plus"></i> Hybrid Search Configuration</h2>
        <p>Manage hybrid search patterns, vector embeddings, and semantic search configurations</p>
      </div>

      <div className="config-tabs">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            className={`tab-btn ${activeTab === tab.id ? 'active' : ''}`}
            onClick={() => setActiveTab(tab.id)}
          >
            <i className={tab.icon}></i>
            <span className="tab-label">{tab.label}</span>
            <span className="tab-count">{tab.count}</span>
          </button>
        ))}
      </div>

      <div className="config-content">
        {activeTab === 'patterns' && (
          <FilePatternSection
            patterns={data.file_patterns}
            categories={categories}
            onRefresh={fetchData}
          />
        )}
        {activeTab === 'templates' && (
          <PipelineTemplateSection templates={data.pipeline_templates} />
        )}
        {activeTab === 'search' && (
          <SearchConfigSection
            configs={data.search_configs}
            onRefresh={fetchData}
          />
        )}
        {activeTab === 'indexes' && (
          <IndexConfigSection configs={data.index_configs} />
        )}
      </div>
    </div>
  );
}
