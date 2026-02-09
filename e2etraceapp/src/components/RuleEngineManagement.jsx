/**
 * PLM Rule Engine Management Component
 * 
 * Provides UI for:
 * - Creating and managing rule sets
 * - Defining hierarchical rules with DAG dependencies
 * - Rule templates and expression builder
 * - Decision Table editor (spreadsheet-style)
 * - Execution and result visualization
 * - Quarantine management
 */

import React, { useState, useEffect, useCallback } from 'react';
import { API_CONFIG } from '../config/api-config';
import DecisionTableEditor from './DecisionTableEditor';
import './RuleEngineManagement.css';

const API_BASE = `${API_CONFIG?.API_BASE_URL || ''}/api/rules`;

// Severity color mapping
const SEVERITY_COLORS = {
  info: '#2196f3',
  warning: '#ff9800',
  critical: '#f44336',
  blocker: '#9c27b0',
};

// Level colors
const LEVEL_COLORS = {
  attribute: '#4caf50',
  entity: '#2196f3',
  relationship: '#9c27b0',
};

// Tab Navigation Component
function TabNavigation({ tabs, activeTab, onTabChange }) {
  return (
    <div className="rule-tab-nav">
      {tabs.map(tab => (
        <button
          key={tab.id}
          className={`rule-tab-btn ${activeTab === tab.id ? 'active' : ''}`}
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
    'draft': 'status-draft',
    'deprecated': 'status-deprecated',
    'archived': 'status-archived',
    'passed': 'status-passed',
    'failed': 'status-failed',
    'running': 'status-running',
    'pending': 'status-pending',
    'completed': 'status-completed',
    'error': 'status-error',
  }[status] || 'status-inactive';
  
  return <span className={`status-badge ${statusClass}`}>{status}</span>;
}

// Severity Badge Component
function SeverityBadge({ severity }) {
  return (
    <span 
      className="severity-badge" 
      style={{ backgroundColor: SEVERITY_COLORS[severity] || '#999' }}
    >
      {severity}
    </span>
  );
}

// Level Badge Component
function LevelBadge({ level }) {
  return (
    <span 
      className="level-badge" 
      style={{ backgroundColor: LEVEL_COLORS[level] || '#999' }}
    >
      {level}
    </span>
  );
}

// Modal Component
function Modal({ isOpen, onClose, title, children, size = 'medium' }) {
  if (!isOpen) return null;
  
  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className={`modal-content modal-${size}`} onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <h3>{title}</h3>
          <button className="modal-close" onClick={onClose}>
            <i className="fas fa-times"></i>
          </button>
        </div>
        <div className="modal-body">{children}</div>
      </div>
    </div>
  );
}

// Empty State Component
function EmptyState({ icon, message, action }) {
  return (
    <div className="empty-state">
      <i className={icon}></i>
      <p>{message}</p>
      {action}
    </div>
  );
}

// Rule Sets Table
function RuleSetsTable({ ruleSets, onEdit, onDelete, onViewRules, onExecute, loading }) {
  if (loading) {
    return (
      <div className="loading-state">
        <i className="fas fa-spinner fa-spin"></i>
        <p>Loading rule sets...</p>
      </div>
    );
  }

  if (!ruleSets.length) {
    return (
      <EmptyState 
        icon="fas fa-clipboard-check" 
        message="No rule sets defined yet"
        action={<span className="empty-hint">Create a rule set to define data quality validation rules</span>}
      />
    );
  }

  return (
    <div className="data-grid ruleset-grid">
      <div className="grid-header">
        <div className="grid-row header-row">
          <div className="grid-cell cell-name">Rule Set</div>
          <div className="grid-cell cell-category">Category</div>
          <div className="grid-cell cell-context">Context</div>
          <div className="grid-cell cell-version">Version</div>
          <div className="grid-cell cell-mode">Execution</div>
          <div className="grid-cell cell-count">Rules</div>
          <div className="grid-cell cell-status">Status</div>
          <div className="grid-cell cell-actions">Actions</div>
        </div>
      </div>
      <div className="grid-body">
        {ruleSets.map(rs => (
          <div key={rs.id} className="grid-row data-row">
            <div className="grid-cell cell-name">
              <div className="cell-content-stacked">
                <strong className="primary-text">{rs.name}</strong>
                {rs.description && <span className="secondary-text">{rs.description}</span>}
              </div>
            </div>
            <div className="grid-cell cell-category">
              <span className="category-tag">{rs.category || 'general'}</span>
            </div>
            <div className="grid-cell cell-context">
              <span className="context-text">{rs.context || '—'}</span>
            </div>
            <div className="grid-cell cell-version">
              <span className="version-badge">{rs.version}</span>
            </div>
            <div className="grid-cell cell-mode">
              <span className={`execution-mode-badge ${rs.execution_mode}`}>
                {rs.execution_mode}
              </span>
            </div>
            <div className="grid-cell cell-count">
              <span className="count-badge">{rs.rule_count || 0}</span>
            </div>
            <div className="grid-cell cell-status">
              <StatusBadge status={rs.is_active ? 'active' : 'inactive'} />
            </div>
            <div className="grid-cell cell-actions">
              <div className="action-group">
                <button 
                  className="btn-icon btn-view" 
                  onClick={() => onViewRules(rs)}
                  title="View Rules"
                >
                  <i className="fas fa-list"></i>
                </button>
                <button 
                  className="btn-icon btn-run" 
                  onClick={() => onExecute(rs)}
                  title="Execute Rules"
                >
                  <i className="fas fa-play"></i>
                </button>
                <button 
                  className="btn-icon btn-edit" 
                  onClick={() => onEdit(rs)}
                  title="Edit"
                >
                  <i className="fas fa-edit"></i>
                </button>
                <button 
                  className="btn-icon btn-delete" 
                  onClick={() => onDelete(rs.id)}
                  title="Delete"
                >
                  <i className="fas fa-trash"></i>
                </button>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// Rules Table (for viewing rules within a rule set)
function RulesTable({ rules, onEdit, onDelete, onAddChild }) {
  if (!rules.length) {
    return (
      <EmptyState 
        icon="fas fa-gavel" 
        message="No rules in this rule set"
        action={<span className="empty-hint">Add rules to validate data quality</span>}
      />
    );
  }

  // Build hierarchy
  const parentRules = rules.filter(r => !r.parent_rule_id);
  const childRulesMap = {};
  rules.forEach(r => {
    if (r.parent_rule_id) {
      if (!childRulesMap[r.parent_rule_id]) {
        childRulesMap[r.parent_rule_id] = [];
      }
      childRulesMap[r.parent_rule_id].push(r);
    }
  });

  return (
    <div className="rules-hierarchy">
      {parentRules.map(rule => (
        <div key={rule.id} className="rule-card parent-rule">
          {/* Rule Header Row */}
          <div className="rule-row rule-header-row">
            <div className="rule-row-left">
              <div className="rule-badges">
                <LevelBadge level={rule.level} />
                <SeverityBadge severity={rule.severity} />
              </div>
              <div className="rule-info">
                <strong className="rule-name">{rule.name}</strong>
                {rule.description && <span className="rule-description">{rule.description}</span>}
              </div>
            </div>
            <div className="rule-row-right">
              <div className="action-group">
                <button 
                  className="btn-icon btn-add-child" 
                  onClick={() => onAddChild(rule)}
                  title="Add Child Rule"
                >
                  <i className="fas fa-plus"></i>
                </button>
                <button 
                  className="btn-icon btn-edit" 
                  onClick={() => onEdit(rule)}
                  title="Edit"
                >
                  <i className="fas fa-edit"></i>
                </button>
                <button 
                  className="btn-icon btn-delete" 
                  onClick={() => onDelete(rule.id)}
                  title="Delete"
                >
                  <i className="fas fa-trash"></i>
                </button>
              </div>
            </div>
          </div>
          
          {/* Rule Details Row */}
          <div className="rule-row rule-details-row">
            <div className="rule-expression-block">
              <span className="expression-label">Expression:</span>
              <code className="expression-code">{rule.expression}</code>
            </div>
            <div className="rule-meta-inline">
              <span className="meta-item" title="Action on Fail">
                <i className="fas fa-exclamation-triangle"></i>
                <span>{rule.action_on_fail}</span>
              </span>
              <span className="meta-item" title="Expression Type">
                <i className="fas fa-code"></i>
                <span>{rule.expression_type}</span>
              </span>
              {rule.sequence_order > 0 && (
                <span className="meta-item" title="Sequence Order">
                  <i className="fas fa-sort-numeric-up"></i>
                  <span>#{rule.sequence_order}</span>
                </span>
              )}
            </div>
          </div>
          
          {/* Child Rules */}
          {childRulesMap[rule.id] && childRulesMap[rule.id].length > 0 && (
            <div className="child-rules-section">
              <div className="child-rules-header">
                <i className="fas fa-sitemap"></i>
                <span>Child Rules ({childRulesMap[rule.id].length})</span>
              </div>
              <div className="child-rules-list">
                {childRulesMap[rule.id].map(child => (
                  <div key={child.id} className="rule-card child-rule">
                    <div className="rule-row rule-header-row">
                      <div className="rule-row-left">
                        <div className="rule-badges">
                          <LevelBadge level={child.level} />
                          <SeverityBadge severity={child.severity} />
                        </div>
                        <div className="rule-info">
                          <strong className="rule-name">{child.name}</strong>
                        </div>
                      </div>
                      <div className="rule-row-right">
                        <div className="action-group">
                          <button 
                            className="btn-icon btn-edit" 
                            onClick={() => onEdit(child)}
                            title="Edit"
                          >
                            <i className="fas fa-edit"></i>
                          </button>
                          <button 
                            className="btn-icon btn-delete" 
                            onClick={() => onDelete(child.id)}
                            title="Delete"
                          >
                            <i className="fas fa-trash"></i>
                          </button>
                        </div>
                      </div>
                    </div>
                    <div className="rule-row rule-details-row">
                      <div className="rule-expression-block">
                        <code className="expression-code">{child.expression}</code>
                      </div>
                      <div className="rule-meta-inline">
                        <span className="meta-item dependency-item" title="Dependency">
                          <i className="fas fa-link"></i>
                          <span>{child.dependency_condition || 'parent_pass'}</span>
                        </span>
                        <span className="meta-item" title="Action on Fail">
                          <i className="fas fa-exclamation-triangle"></i>
                          <span>{child.action_on_fail}</span>
                        </span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

// Templates Table
function TemplatesTable({ templates, onUse, loading }) {
  if (loading) {
    return (
      <div className="loading-state">
        <i className="fas fa-spinner fa-spin"></i>
        <p>Loading templates...</p>
      </div>
    );
  }

  if (!templates.length) {
    return (
      <EmptyState 
        icon="fas fa-file-code" 
        message="No rule templates available"
      />
    );
  }

  return (
    <div className="templates-grid">
      {templates.map(t => (
        <div key={t.id} className="template-card">
          <div className="template-header">
            <h4>{t.name}</h4>
            <span className="template-category">{t.category}</span>
          </div>
          <p className="template-description">{t.description}</p>
          <div className="template-expression">
            <code>{t.expression_template}</code>
          </div>
          <div className="template-footer">
            <div className="template-meta">
              <LevelBadge level={t.default_level} />
              <SeverityBadge severity={t.default_severity} />
            </div>
            <button 
              className="btn-primary btn-small" 
              onClick={() => onUse(t)}
            >
              <i className="fas fa-plus"></i> Use Template
            </button>
          </div>
        </div>
      ))}
    </div>
  );
}

// Executions Table
function ExecutionsTable({ executions, onViewDetails, loading }) {
  if (loading) {
    return (
      <div className="loading-state">
        <i className="fas fa-spinner fa-spin"></i>
        <p>Loading executions...</p>
      </div>
    );
  }

  if (!executions.length) {
    return (
      <EmptyState 
        icon="fas fa-history" 
        message="No executions yet"
      />
    );
  }

  return (
    <table className="rule-table">
      <thead>
        <tr>
          <th>Execution ID</th>
          <th>Rule Set</th>
          <th>Status</th>
          <th>Records</th>
          <th>Pass Rate</th>
          <th>Started</th>
          <th>Duration</th>
          <th>Actions</th>
        </tr>
      </thead>
      <tbody>
        {executions.map(ex => (
          <tr key={ex.id}>
            <td className="id-cell">{ex.id.substring(0, 8)}...</td>
            <td>{ex.rule_set_name || ex.rule_set_id}</td>
            <td><StatusBadge status={ex.status} /></td>
            <td>{ex.total_records || 0}</td>
            <td>
              <div className="pass-rate">
                <div 
                  className="pass-rate-bar" 
                  style={{ width: `${Math.max(0, ex.pass_rate || 0)}%` }}
                ></div>
                <span>{(ex.pass_rate || 0).toFixed(1)}%</span>
              </div>
            </td>
            <td>{ex.started_at ? new Date(ex.started_at).toLocaleString() : '-'}</td>
            <td>{ex.duration_seconds ? `${ex.duration_seconds.toFixed(2)}s` : '-'}</td>
            <td className="actions-cell">
              <button 
                className="btn-action btn-view" 
                onClick={() => onViewDetails(ex)}
                title="View Details"
              >
                <i className="fas fa-eye"></i>
              </button>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

// Quarantine Table
function QuarantineTable({ records, onReview, onRelease, loading }) {
  if (loading) {
    return (
      <div className="loading-state">
        <i className="fas fa-spinner fa-spin"></i>
        <p>Loading quarantine records...</p>
      </div>
    );
  }

  if (!records.length) {
    return (
      <EmptyState 
        icon="fas fa-shield-alt" 
        message="No records in quarantine"
      />
    );
  }

  return (
    <table className="rule-table">
      <thead>
        <tr>
          <th>Record ID</th>
          <th>Entity Type</th>
          <th>Rule</th>
          <th>Reason</th>
          <th>Status</th>
          <th>Quarantined At</th>
          <th>Actions</th>
        </tr>
      </thead>
      <tbody>
        {records.map(rec => (
          <tr key={rec.id}>
            <td className="id-cell">{rec.record_id}</td>
            <td>{rec.entity_type}</td>
            <td>{rec.rule_name || rec.rule_id}</td>
            <td className="reason-cell">{rec.quarantine_reason}</td>
            <td><StatusBadge status={rec.status} /></td>
            <td>{new Date(rec.quarantined_at).toLocaleString()}</td>
            <td className="actions-cell">
              <button 
                className="btn-action btn-view" 
                onClick={() => onReview(rec)}
                title="Review"
              >
                <i className="fas fa-search"></i>
              </button>
              <button 
                className="btn-action btn-release" 
                onClick={() => onRelease(rec.id)}
                title="Release"
              >
                <i className="fas fa-unlock"></i>
              </button>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

// Rule Set Form - Enterprise Structure
function RuleSetForm({ ruleSet, onSave, onCancel }) {
  const [form, setForm] = useState({
    name: ruleSet?.name || '',
    description: ruleSet?.description || '',
    version: ruleSet?.version || '1.0.0',
    category: ruleSet?.category || 'general',
    rule_type: ruleSet?.rule_type || 'simple',
    context: ruleSet?.context || '',
    scope: ruleSet?.scope || 'global',
    target_entity_type: ruleSet?.target_entity_type || '',
    execution_mode: ruleSet?.execution_mode || 'sequential',
    priority: ruleSet?.priority || 100,
    stop_on_critical: ruleSet?.stop_on_critical ?? true,
    allow_override: ruleSet?.allow_override ?? true,
    timeout_seconds: ruleSet?.timeout_seconds || 3600,
    parallel_threads: ruleSet?.parallel_threads || 4,
    // Decision Table data (for decision_table type)
    decision_table: ruleSet?.decision_table || null,
  });

  const [activeSection, setActiveSection] = useState('basic');

  const handleChange = (field, value) => {
    setForm(prev => ({ ...prev, [field]: value }));
  };

  // Handle decision table changes
  const handleDecisionTableChange = useCallback((tableData) => {
    setForm(prev => ({ ...prev, decision_table: tableData }));
  }, []);

  return (
    <div className="ruleset-form enterprise-form">
      {/* Form Section Tabs */}
      <div className="form-section-tabs">
        <button 
          className={`section-tab ${activeSection === 'basic' ? 'active' : ''}`}
          onClick={() => setActiveSection('basic')}
        >
          <i className="fas fa-info-circle"></i> Basic Info
        </button>
        <button 
          className={`section-tab ${activeSection === 'scope' ? 'active' : ''}`}
          onClick={() => setActiveSection('scope')}
        >
          <i className="fas fa-crosshairs"></i> Scope & Context
        </button>
        {form.rule_type === 'decision_table' && (
          <button 
            className={`section-tab ${activeSection === 'table' ? 'active' : ''}`}
            onClick={() => setActiveSection('table')}
          >
            <i className="fas fa-table"></i> Decision Table
          </button>
        )}
        <button 
          className={`section-tab ${activeSection === 'execution' ? 'active' : ''}`}
          onClick={() => setActiveSection('execution')}
        >
          <i className="fas fa-cogs"></i> Execution
        </button>
        <button 
          className={`section-tab ${activeSection === 'hierarchy' ? 'active' : ''}`}
          onClick={() => setActiveSection('hierarchy')}
        >
          <i className="fas fa-sitemap"></i> Hierarchy
        </button>
      </div>

      {/* Basic Info Section */}
      {activeSection === 'basic' && (
        <div className="form-section">
          <div className="section-header">
            <h4><i className="fas fa-info-circle"></i> Basic Information</h4>
            <p className="section-hint">Define the ruleset identity and classification</p>
          </div>
          
          <div className="form-row">
            <div className="form-group flex-2">
              <label className="required-label">Ruleset Name</label>
              <input
                type="text"
                value={form.name}
                onChange={e => handleChange('name', e.target.value)}
                placeholder="e.g., BOM Validation Rules V1"
                className="form-input"
                required
              />
            </div>
            <div className="form-group flex-1">
              <label>Version</label>
              <input
                type="text"
                value={form.version}
                onChange={e => handleChange('version', e.target.value)}
                placeholder="1.0.0"
                className="form-input"
              />
            </div>
          </div>
          
          <div className="form-group">
            <label>Description</label>
            <textarea
              value={form.description}
              onChange={e => handleChange('description', e.target.value)}
              placeholder="Describe the business purpose and coverage of this ruleset"
              rows={3}
              className="form-textarea"
            />
          </div>
          
          <div className="form-row">
            <div className="form-group">
              <label>Category</label>
              <select
                value={form.category}
                onChange={e => handleChange('category', e.target.value)}
                className="form-select"
              >
                <option value="general">General</option>
                <option value="plm_validation">PLM Validation</option>
                <option value="data_quality">Data Quality</option>
                <option value="compliance">Compliance</option>
                <option value="etl">ETL Transformation</option>
                <option value="business_rules">Business Rules</option>
              </select>
            </div>
            
            <div className="form-group">
              <label>Rule Type</label>
              <select
                value={form.rule_type}
                onChange={e => handleChange('rule_type', e.target.value)}
                className="form-select"
              >
                <option value="simple">SimpleRule (IF-THEN)</option>
                <option value="decision_table">DecisionTable (Tabular Logic)</option>
                <option value="decision_tree">DecisionTree (Branching Paths)</option>
              </select>
              <span className="field-hint">
                {form.rule_type === 'simple' && 'Single condition → single action'}
                {form.rule_type === 'decision_table' && 'Multiple conditions in table format'}
                {form.rule_type === 'decision_tree' && 'Nested branching decisions'}
              </span>
            </div>
          </div>
        </div>
      )}

      {/* Scope & Context Section */}
      {activeSection === 'scope' && (
        <div className="form-section">
          <div className="section-header">
            <h4><i className="fas fa-crosshairs"></i> Scope & Context</h4>
            <p className="section-hint">Define where and when this ruleset applies</p>
          </div>
          
          <div className="form-row">
            <div className="form-group">
              <label>Scope Level</label>
              <select
                value={form.scope}
                onChange={e => handleChange('scope', e.target.value)}
                className="form-select"
              >
                <option value="global">Global (All Data)</option>
                <option value="organization">Organization</option>
                <option value="site">Site/Location</option>
                <option value="project">Project</option>
                <option value="custom">Custom Filter</option>
              </select>
            </div>
            
            <div className="form-group">
              <label>Context Identifier</label>
              <input
                type="text"
                value={form.context}
                onChange={e => handleChange('context', e.target.value)}
                placeholder="e.g., Engineering_BOM, APAC_Region"
                className="form-input"
              />
              <span className="field-hint">Specific context where rules apply</span>
            </div>
          </div>
          
          <div className="form-group">
            <label>Target Entity Types</label>
            <input
              type="text"
              value={form.target_entity_type}
              onChange={e => handleChange('target_entity_type', e.target.value)}
              placeholder="e.g., BOM, Item, CADModel, Part (comma-separated)"
              className="form-input"
            />
            <span className="field-hint">Entity types this ruleset validates</span>
          </div>
        </div>
      )}

      {/* Decision Table Section - Only for decision_table rule type */}
      {activeSection === 'table' && form.rule_type === 'decision_table' && (
        <div className="form-section decision-table-section">
          <div className="section-header">
            <h4><i className="fas fa-table"></i> Decision Table</h4>
            <p className="section-hint">Define rules in a spreadsheet-like format. Each row represents a rule with conditions (IF) and actions (THEN).</p>
          </div>
          
          <DecisionTableEditor
            tableName={form.name || 'Decision Table'}
            conditionColumns={form.decision_table?.columns?.filter(c => c.type === 'condition') || undefined}
            actionColumns={form.decision_table?.columns?.filter(c => c.type !== 'condition') || undefined}
            rows={form.decision_table?.rows || []}
            onChange={handleDecisionTableChange}
          />
          
          <div className="decision-table-help">
            <h5><i className="fas fa-lightbulb"></i> Tips for Decision Tables</h5>
            <ul>
              <li>Use <strong>*</strong> or leave empty for "any value" in condition columns</li>
              <li>First matching row wins (top-to-bottom evaluation)</li>
              <li>Configure column field mappings via the <i className="fas fa-cog"></i> button</li>
              <li>Import existing rules from Excel using the Import button</li>
            </ul>
          </div>
        </div>
      )}

      {/* Execution Section */}
      {activeSection === 'execution' && (
        <div className="form-section">
          <div className="section-header">
            <h4><i className="fas fa-cogs"></i> Execution Configuration</h4>
            <p className="section-hint">Configure how rules are executed</p>
          </div>
          
          <div className="form-row">
            <div className="form-group">
              <label>Execution Mode</label>
              <select
                value={form.execution_mode}
                onChange={e => handleChange('execution_mode', e.target.value)}
                className="form-select"
              >
                <option value="sequential">Sequential (Ordered)</option>
                <option value="parallel">Parallel (Independent)</option>
                <option value="dag">DAG (Dependency Graph)</option>
              </select>
            </div>
            
            <div className="form-group">
              <label>Timeout (seconds)</label>
              <input
                type="number"
                value={form.timeout_seconds}
                onChange={e => handleChange('timeout_seconds', parseInt(e.target.value))}
                min={60}
                max={86400}
                className="form-input"
              />
            </div>
          </div>

          {/* Execution Mode Info Box */}
          <div className={`info-box info-${form.execution_mode}`}>
            {form.execution_mode === 'sequential' && (
              <>
                <div className="info-icon"><i className="fas fa-list-ol"></i></div>
                <div className="info-content">
                  <strong>Sequential Execution</strong>
                  <p>Rules execute one after another in order. Use when rule outputs feed into subsequent rules (dependencies).</p>
                </div>
              </>
            )}
            {form.execution_mode === 'parallel' && (
              <>
                <div className="info-icon"><i className="fas fa-random"></i></div>
                <div className="info-content">
                  <strong>Parallel Execution</strong>
                  <p>Rules execute simultaneously for better performance. Use only when rules are independent and don't share state.</p>
                </div>
              </>
            )}
            {form.execution_mode === 'dag' && (
              <>
                <div className="info-icon"><i className="fas fa-project-diagram"></i></div>
                <div className="info-content">
                  <strong>DAG Execution</strong>
                  <p>Rules execute based on dependency graph. Automatically resolves execution order from rule dependencies.</p>
                </div>
              </>
            )}
          </div>

          {form.execution_mode === 'parallel' && (
            <div className="form-group">
              <label>Parallel Threads</label>
              <input
                type="number"
                value={form.parallel_threads}
                onChange={e => handleChange('parallel_threads', parseInt(e.target.value))}
                min={1}
                max={16}
                className="form-input"
              />
              <span className="field-hint">Number of concurrent execution threads (1-16)</span>
            </div>
          )}
          
          <div className="form-group checkbox-row">
            <label className="checkbox-label">
              <input
                type="checkbox"
                checked={form.stop_on_critical}
                onChange={e => handleChange('stop_on_critical', e.target.checked)}
              />
              <span className="checkbox-text">Stop execution on critical failure</span>
            </label>
            <span className="field-hint">Halt all rules if a critical/blocker rule fails</span>
          </div>
        </div>
      )}

      {/* Hierarchy Section */}
      {activeSection === 'hierarchy' && (
        <div className="form-section">
          <div className="section-header">
            <h4><i className="fas fa-sitemap"></i> Hierarchy & Precedence</h4>
            <p className="section-hint">Control rule priority and override behavior</p>
          </div>
          
          <div className="form-row">
            <div className="form-group">
              <label>Priority Level</label>
              <input
                type="number"
                value={form.priority}
                onChange={e => handleChange('priority', parseInt(e.target.value))}
                min={1}
                max={1000}
                className="form-input"
              />
              <span className="field-hint">Higher values = higher priority (overrides lower)</span>
            </div>
            
            <div className="form-group">
              <label className="checkbox-label inline-checkbox">
                <input
                  type="checkbox"
                  checked={form.allow_override}
                  onChange={e => handleChange('allow_override', e.target.checked)}
                />
                <span className="checkbox-text">Allow Override by Higher Priority</span>
              </label>
            </div>
          </div>

          {/* Hierarchy Diagram */}
          <div className="hierarchy-diagram">
            <div className="hierarchy-title">Rule Precedence Stack</div>
            <div className="hierarchy-stack">
              <div className={`hierarchy-level ${form.priority > 500 ? 'current-level' : ''}`}>
                <span className="level-label">Site-Specific (500+)</span>
                <span className="level-desc">Highest priority, most specific</span>
              </div>
              <div className={`hierarchy-level ${form.priority > 200 && form.priority <= 500 ? 'current-level' : ''}`}>
                <span className="level-label">Business Unit (200-500)</span>
                <span className="level-desc">Department/team overrides</span>
              </div>
              <div className={`hierarchy-level ${form.priority <= 200 ? 'current-level' : ''}`}>
                <span className="level-label">Global Defaults (1-200)</span>
                <span className="level-desc">Base rules, lowest priority</span>
              </div>
            </div>
            <div className="hierarchy-note">
              <i className="fas fa-info-circle"></i>
              Current priority ({form.priority}) places this ruleset at the <strong>
                {form.priority > 500 ? 'Site-Specific' : form.priority > 200 ? 'Business Unit' : 'Global'}
              </strong> level
            </div>
          </div>
        </div>
      )}
      
      <div className="form-actions">
        <button className="btn-secondary" onClick={onCancel}>Cancel</button>
        <button 
          className="btn-primary" 
          onClick={() => onSave(form)}
          disabled={!form.name}
        >
          <i className="fas fa-save"></i>
          {ruleSet?.id ? 'Update Ruleset' : 'Create Ruleset'}
        </button>
      </div>
    </div>
  );
}

// Rule Form - Enterprise IF/THEN Structure
function RuleForm({ rule, ruleSetId, parentRuleId, templates, onSave, onCancel }) {
  const [form, setForm] = useState({
    rule_set_id: ruleSetId,
    name: rule?.name || '',
    description: rule?.description || '',
    level: rule?.level || 'entity',
    severity: rule?.severity || 'warning',
    priority: rule?.priority || 100,
    // IF Section - Conditions
    expression: rule?.expression || '',
    expression_type: rule?.expression_type || 'python',
    conditions: rule?.conditions || [{ field: '', operator: 'equals', value: '' }],
    condition_logic: rule?.condition_logic || 'AND',
    // THEN Section - Actions
    action_on_fail: rule?.action_on_fail || 'log',
    action_on_pass: rule?.action_on_pass || 'none',
    transformation_expression: rule?.transformation_expression || '',
    action_message: rule?.action_message || '',
    // Hierarchy & Execution
    parent_rule_id: parentRuleId || rule?.parent_rule_id || null,
    inherit_from_parent: rule?.inherit_from_parent ?? true,
    dependency_condition: rule?.dependency_condition || 'parent_pass',
    sequence_order: rule?.sequence_order || 0,
    parallel_safe: rule?.parallel_safe ?? true,
    is_enabled: rule?.is_enabled ?? true,
  });
  
  const [activeSection, setActiveSection] = useState('conditions');
  const [testResult, setTestResult] = useState(null);
  const [testing, setTesting] = useState(false);
  const [conditionMode, setConditionMode] = useState(form.expression ? 'expression' : 'builder');
  const [testDataText, setTestDataText] = useState('{\n  "lifecycle_state": "RELEASED",\n  "weight": 10,\n  "cad_links": ["file1"],\n  "revision": "A"\n}');
  const [testDataError, setTestDataError] = useState(null);

  const handleChange = (field, value) => {
    setForm(prev => ({ ...prev, [field]: value }));
  };

  const applyTemplate = (template) => {
    setForm(prev => ({
      ...prev,
      name: template.name,
      description: template.description,
      expression: template.expression_template,
      level: template.default_level,
      severity: template.default_severity,
      action_on_fail: template.default_action,
    }));
    setConditionMode('expression');
  };

  const testExpression = async () => {
    setTesting(true);
    setTestResult(null);
    setTestDataError(null);
    try {
      let parsedTestData = {};
      if (testDataText && testDataText.trim()) {
        try {
          parsedTestData = JSON.parse(testDataText);
        } catch (e) {
          setTestDataError(`Invalid JSON test data: ${e.message}`);
          setTesting(false);
          return;
        }
      }

      const response = await fetch(`${API_BASE}/validate-expression`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          expression: form.expression,
          expression_type: form.expression_type,
          test_data: parsedTestData,
        }),
      });
      const data = await response.json();
      setTestResult(data);
    } catch (error) {
      setTestResult({ valid: false, error: error.message });
    }
    setTesting(false);
  };

  const addCondition = () => {
    handleChange('conditions', [...form.conditions, { field: '', operator: 'equals', value: '' }]);
  };

  const updateCondition = (index, field, value) => {
    const updated = [...form.conditions];
    updated[index] = { ...updated[index], [field]: value };
    handleChange('conditions', updated);
  };

  const removeCondition = (index) => {
    handleChange('conditions', form.conditions.filter((_, i) => i !== index));
  };

  // Build expression from conditions for backend compatibility
  const buildExpressionFromConditions = () => {
    const escapePyString = (value) => {
      return String(value)
        .replace(/\\/g, '\\\\')
        .replace(/'/g, "\\'")
        .replace(/\r/g, '\\r')
        .replace(/\n/g, '\\n');
    };

    const fieldRef = (field) => `_record.get('${escapePyString(field)}')`;
    const strLit = (value) => `'${escapePyString(value)}'`;

    const conditions = (form.conditions || [])
      .filter(c => c.field && (c.value || c.operator === 'is_empty'))
      .map(c => {
        const f = fieldRef(c.field);
        switch (c.operator) {
          case 'equals':
            return `${f} == ${strLit(c.value)}`;
          case 'not_equals':
            return `${f} != ${strLit(c.value)}`;
          case 'greater_than':
            return `float(${f} or 0) > float(${strLit(c.value)})`;
          case 'less_than':
            return `float(${f} or 0) < float(${strLit(c.value)})`;
          case 'contains':
            return `contains(${f}, ${strLit(c.value)})`;
          case 'is_empty':
            return `is_empty(${f})`;
          case 'matches':
            return `matches_regex(${f}, ${strLit(c.value)})`;
          default:
            return `${f} == ${strLit(c.value)}`;
        }
      })
      .filter(Boolean);

    return conditions.join(form.condition_logic === 'AND' ? ' and ' : ' or ');
  };

  const handleSave = () => {
    let finalForm = { ...form };
    if (conditionMode === 'builder') {
      finalForm.expression = buildExpressionFromConditions();
    }
    onSave(finalForm);
  };

  return (
    <div className="rule-form enterprise-form">
      {/* Template Selector */}
      {templates && templates.length > 0 && (
        <div className="template-selector-bar">
          <i className="fas fa-magic"></i>
          <span>Quick start from template:</span>
          <select onChange={e => {
            const t = templates.find(t => t.id === e.target.value);
            if (t) applyTemplate(t);
          }}>
            <option value="">-- Select Template --</option>
            {templates.map(t => (
              <option key={t.id} value={t.id}>{t.name}</option>
            ))}
          </select>
        </div>
      )}

      {/* Rule Header */}
      <div className="form-section rule-header-section">
        <div className="form-row">
          <div className="form-group flex-2">
            <label className="required-label">Rule Name</label>
            <input
              type="text"
              value={form.name}
              onChange={e => handleChange('name', e.target.value)}
              placeholder="e.g., R101 - Lifecycle State Must Be Released"
              className="form-input"
              required
            />
          </div>
          <div className="form-group">
            <label>Priority</label>
            <input
              type="number"
              value={form.priority}
              onChange={e => handleChange('priority', parseInt(e.target.value))}
              min={1}
              max={1000}
              className="form-input"
            />
          </div>
          <div className="form-group">
            <label className="checkbox-label">
              <input
                type="checkbox"
                checked={form.is_enabled}
                onChange={e => handleChange('is_enabled', e.target.checked)}
              />
              <span>Enabled</span>
            </label>
          </div>
        </div>
        
        <div className="form-group">
          <label>Description</label>
          <textarea
            value={form.description}
            onChange={e => handleChange('description', e.target.value)}
            placeholder="Describe the business logic this rule validates"
            rows={2}
            className="form-textarea"
          />
        </div>
        
        <div className="form-row">
          <div className="form-group">
            <label>Level</label>
            <select value={form.level} onChange={e => handleChange('level', e.target.value)} className="form-select">
              <option value="attribute">Attribute (Field-level)</option>
              <option value="entity">Entity (Row-level)</option>
              <option value="relationship">Relationship (Graph/BOM)</option>
              <option value="cross_entity">Cross-Entity (Multi-record)</option>
            </select>
          </div>
          <div className="form-group">
            <label>Severity</label>
            <select value={form.severity} onChange={e => handleChange('severity', e.target.value)} className="form-select severity-select">
              <option value="info">ℹ️ Info</option>
              <option value="warning">⚠️ Warning</option>
              <option value="critical">🔴 Critical</option>
              <option value="blocker">🚫 Blocker</option>
            </select>
          </div>
        </div>
      </div>

      {/* Section Tabs */}
      <div className="form-section-tabs">
        <button 
          className={`section-tab ${activeSection === 'conditions' ? 'active' : ''}`}
          onClick={() => setActiveSection('conditions')}
        >
          <i className="fas fa-code-branch"></i> IF (Conditions)
        </button>
        <button 
          className={`section-tab ${activeSection === 'actions' ? 'active' : ''}`}
          onClick={() => setActiveSection('actions')}
        >
          <i className="fas fa-bolt"></i> THEN (Actions)
        </button>
        <button 
          className={`section-tab ${activeSection === 'hierarchy' ? 'active' : ''}`}
          onClick={() => setActiveSection('hierarchy')}
        >
          <i className="fas fa-sitemap"></i> Hierarchy
        </button>
        <button 
          className={`section-tab ${activeSection === 'execution' ? 'active' : ''}`}
          onClick={() => setActiveSection('execution')}
        >
          <i className="fas fa-play-circle"></i> Execution
        </button>
      </div>

      {/* IF Section - Conditions */}
      {activeSection === 'conditions' && (
        <div className="form-section condition-section">
          <div className="section-header">
            <h4><i className="fas fa-code-branch"></i> IF — Condition Definition</h4>
            <p className="section-hint">Define when this rule should trigger</p>
          </div>

          {/* Condition Mode Toggle */}
          <div className="condition-mode-toggle">
            <button 
              className={`mode-btn ${conditionMode === 'builder' ? 'active' : ''}`}
              onClick={() => setConditionMode('builder')}
            >
              <i className="fas fa-puzzle-piece"></i> Visual Builder
            </button>
            <button 
              className={`mode-btn ${conditionMode === 'expression' ? 'active' : ''}`}
              onClick={() => setConditionMode('expression')}
            >
              <i className="fas fa-code"></i> Expression Mode
            </button>
          </div>

          {conditionMode === 'builder' ? (
            <div className="condition-builder">
              <div className="condition-logic-selector">
                <label>Match</label>
                <select 
                  value={form.condition_logic} 
                  onChange={e => handleChange('condition_logic', e.target.value)}
                  className="form-select"
                >
                  <option value="AND">ALL conditions (AND)</option>
                  <option value="OR">ANY condition (OR)</option>
                </select>
              </div>

              <div className="conditions-list">
                {form.conditions.map((condition, index) => (
                  <div key={index} className="condition-row">
                    <span className="condition-index">{index + 1}</span>
                    <input
                      type="text"
                      value={condition.field}
                      onChange={e => updateCondition(index, 'field', e.target.value)}
                      placeholder="Field name (e.g., lifecycle_state)"
                      className="form-input condition-field"
                    />
                    <select
                      value={condition.operator}
                      onChange={e => updateCondition(index, 'operator', e.target.value)}
                      className="form-select condition-operator"
                    >
                      <option value="equals">equals</option>
                      <option value="not_equals">not equals</option>
                      <option value="greater_than">greater than</option>
                      <option value="less_than">less than</option>
                      <option value="contains">contains</option>
                      <option value="is_empty">is empty</option>
                      <option value="matches">matches regex</option>
                    </select>
                    <input
                      type="text"
                      value={condition.value}
                      onChange={e => updateCondition(index, 'value', e.target.value)}
                      placeholder="Value"
                      className="form-input condition-value"
                    />
                    <button 
                      className="btn-icon btn-remove"
                      onClick={() => removeCondition(index)}
                      disabled={form.conditions.length === 1}
                    >
                      <i className="fas fa-times"></i>
                    </button>
                  </div>
                ))}
              </div>

              <button className="btn-secondary btn-add-condition" onClick={addCondition}>
                <i className="fas fa-plus"></i> Add Condition
              </button>

              {/* Preview generated expression */}
              <div className="expression-preview">
                <label>Generated Expression:</label>
                <code>{buildExpressionFromConditions() || '(No conditions defined)'}</code>
              </div>
            </div>
          ) : (
            <div className="expression-editor-section">
              <div className="expression-editor">
                <div className="expression-type-bar">
                  <select
                    value={form.expression_type}
                    onChange={e => handleChange('expression_type', e.target.value)}
                    className="form-select"
                  >
                    <option value="python">Python (supported)</option>
                    <option value="sql" disabled>SQL (coming soon)</option>
                    <option value="sparksql" disabled>SparkSQL (coming soon)</option>
                    <option value="cypher" disabled>Cypher (coming soon)</option>
                  </select>
                  <button 
                    className="btn-secondary btn-small"
                    onClick={testExpression}
                    disabled={testing || !form.expression}
                  >
                    {testing ? <i className="fas fa-spinner fa-spin"></i> : <i className="fas fa-flask"></i>}
                    Validate Expression
                  </button>
                </div>
                <div className="expression-testdata">
                  <label>Test Data (JSON)</label>
                  <textarea
                    value={testDataText}
                    onChange={e => setTestDataText(e.target.value)}
                    rows={6}
                    className="code-input"
                    placeholder={'{ "field": "value" }'}
                  />
                  {testDataError ? (
                    <div className="test-result error">
                      <i className="fas fa-times-circle"></i> {testDataError}
                    </div>
                  ) : null}
                  <div className="field-hint">
                    Tip: reference fields via <code>_record.get('field')</code>. Helper functions available: <code>is_empty</code>, <code>is_not_null</code>, <code>contains</code>, <code>matches_regex</code>, <code>in_range</code>, <code>in_list</code>.
                  </div>
                </div>
                <textarea
                  value={form.expression}
                  onChange={e => handleChange('expression', e.target.value)}
                  placeholder={`# ${form.expression_type === 'python' ? 'Python expression returning True/False' : form.expression_type.toUpperCase() + ' condition'}
# Example: lifecycle_state == 'RELEASED' and weight > 0`}
                  rows={5}
                  className="code-input"
                />
              </div>
              {testResult && (
                <div className={`test-result ${testResult.valid ? 'success' : 'error'}`}>
                  {testResult.valid ? (
                    <><i className="fas fa-check-circle"></i> Expression is valid</>
                  ) : (
                    <><i className="fas fa-times-circle"></i> {testResult.error}</>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* THEN Section - Actions */}
      {activeSection === 'actions' && (
        <div className="form-section action-section">
          <div className="section-header">
            <h4><i className="fas fa-bolt"></i> THEN — Action Definition</h4>
            <p className="section-hint">Define what happens when conditions match</p>
          </div>

          <div className="action-panels">
            {/* On Fail Actions */}
            <div className="action-panel fail-panel">
              <div className="panel-header">
                <i className="fas fa-times-circle"></i>
                <span>When Condition FAILS</span>
              </div>
              <div className="form-group">
                <label>Action</label>
                <select
                  value={form.action_on_fail}
                  onChange={e => handleChange('action_on_fail', e.target.value)}
                  className="form-select"
                >
                  <option value="log">📝 Log Only</option>
                  <option value="warn">⚠️ Warn & Continue</option>
                  <option value="quarantine">🔒 Quarantine Record</option>
                  <option value="reject">❌ Reject Record</option>
                  <option value="transform">🔄 Transform Value</option>
                  <option value="escalate">📢 Escalate to Workflow</option>
                </select>
              </div>
              
              {form.action_on_fail === 'transform' && (
                <div className="form-group">
                  <label>Transformation Expression</label>
                  <textarea
                    value={form.transformation_expression}
                    onChange={e => handleChange('transformation_expression', e.target.value)}
                    placeholder="e.g., value.strip().upper()"
                    rows={2}
                    className="code-input"
                  />
                </div>
              )}
              
              <div className="form-group">
                <label>Failure Message</label>
                <input
                  type="text"
                  value={form.action_message}
                  onChange={e => handleChange('action_message', e.target.value)}
                  placeholder="Message shown when rule fails"
                  className="form-input"
                />
              </div>
            </div>

            {/* On Pass Actions */}
            <div className="action-panel pass-panel">
              <div className="panel-header">
                <i className="fas fa-check-circle"></i>
                <span>When Condition PASSES</span>
              </div>
              <div className="form-group">
                <label>Action</label>
                <select
                  value={form.action_on_pass}
                  onChange={e => handleChange('action_on_pass', e.target.value)}
                  className="form-select"
                >
                  <option value="none">No Action (Default)</option>
                  <option value="log">📝 Log Success</option>
                  <option value="enrich">➕ Enrich Record</option>
                  <option value="trigger_next">➡️ Trigger Next Rule</option>
                </select>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Hierarchy Section */}
      {activeSection === 'hierarchy' && (
        <div className="form-section hierarchy-section">
          <div className="section-header">
            <h4><i className="fas fa-sitemap"></i> Rule Hierarchy</h4>
            <p className="section-hint">Configure parent-child relationships and inheritance</p>
          </div>

          {parentRuleId && (
            <div className="parent-info-box">
              <i className="fas fa-link"></i>
              <span>This is a <strong>child rule</strong> of Parent Rule ID: {parentRuleId}</span>
            </div>
          )}

          <div className="form-row">
            <div className="form-group">
              <label>Dependency Condition</label>
              <select
                value={form.dependency_condition}
                onChange={e => handleChange('dependency_condition', e.target.value)}
                className="form-select"
              >
                <option value="parent_pass">🟢 Run if parent PASSES</option>
                <option value="parent_fail">🔴 Run if parent FAILS</option>
                <option value="always">⚪ Always run (independent)</option>
              </select>
            </div>
            
            <div className="form-group">
              <label className="checkbox-label">
                <input
                  type="checkbox"
                  checked={form.inherit_from_parent}
                  onChange={e => handleChange('inherit_from_parent', e.target.checked)}
                />
                <span>Inherit settings from parent</span>
              </label>
            </div>
          </div>

          {/* Hierarchy Visualization */}
          <div className="hierarchy-visual">
            <div className="hierarchy-hint">
              <i className="fas fa-info-circle"></i>
              <p>Child rules can <strong>override</strong> parent rule behaviors or <strong>extend</strong> them with additional checks.</p>
            </div>
          </div>
        </div>
      )}

      {/* Execution Section */}
      {activeSection === 'execution' && (
        <div className="form-section execution-section">
          <div className="section-header">
            <h4><i className="fas fa-play-circle"></i> Execution Settings</h4>
            <p className="section-hint">Control how this rule executes within the ruleset</p>
          </div>

          <div className="form-row">
            <div className="form-group">
              <label>Sequence Order</label>
              <input
                type="number"
                value={form.sequence_order}
                onChange={e => handleChange('sequence_order', parseInt(e.target.value))}
                min={0}
                className="form-input"
              />
              <span className="field-hint">Lower numbers execute first (sequential mode)</span>
            </div>
            
            <div className="form-group">
              <label className="checkbox-label">
                <input
                  type="checkbox"
                  checked={form.parallel_safe}
                  onChange={e => handleChange('parallel_safe', e.target.checked)}
                />
                <span>Safe for Parallel Execution</span>
              </label>
              <span className="field-hint">Rule has no side effects or shared state</span>
            </div>
          </div>

          {/* Execution Mode Info */}
          <div className="execution-info-grid">
            <div className="exec-info-card">
              <div className="exec-icon"><i className="fas fa-list-ol"></i></div>
              <div className="exec-label">Sequential</div>
              <div className="exec-desc">Respects sequence_order. Use when rules depend on prior results.</div>
            </div>
            <div className="exec-info-card">
              <div className="exec-icon"><i className="fas fa-random"></i></div>
              <div className="exec-label">Parallel</div>
              <div className="exec-desc">Ignores order. Only safe for independent rules.</div>
            </div>
            <div className="exec-info-card">
              <div className="exec-icon"><i className="fas fa-project-diagram"></i></div>
              <div className="exec-label">DAG</div>
              <div className="exec-desc">Automatic ordering based on declared dependencies.</div>
            </div>
          </div>
        </div>
      )}
      
      <div className="form-actions">
        <button className="btn-secondary" onClick={onCancel}>Cancel</button>
        <button 
          className="btn-primary" 
          onClick={handleSave}
          disabled={!form.name || (conditionMode === 'expression' && !form.expression)}
        >
          <i className="fas fa-save"></i>
          {rule?.id ? 'Update Rule' : 'Create Rule'}
        </button>
      </div>
    </div>
  );
}

// Execute Dialog
function ExecuteDialog({ ruleSet, onExecute, onClose }) {
  const [testData, setTestData] = useState('[\n  {"id": "ITEM001", "lifecycle_state": "RELEASED", "weight": 1.5}\n]');
  const [executing, setExecuting] = useState(false);
  const [result, setResult] = useState(null);

  const handleExecute = async () => {
    setExecuting(true);
    setResult(null);
    try {
      let data;
      try {
        data = JSON.parse(testData);
      } catch {
        throw new Error('Invalid JSON data');
      }
      
      const response = await fetch(`${API_BASE}/execute`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          rule_set_id: ruleSet.id,
          records: Array.isArray(data) ? data : [data],
        }),
      });
      if (!response.ok) {
        const err = await response.json().catch(() => ({ detail: `HTTP ${response.status}` }));
        throw new Error(err.detail || `Execution failed: HTTP ${response.status}`);
      }
      const result = await response.json();
      setResult(result);
      onExecute(result);
    } catch (error) {
      setResult({ error: error.message });
    }
    setExecuting(false);
  };

  return (
    <Modal
      isOpen={true}
      onClose={onClose}
      title={`Execute: ${ruleSet.name}`}
      size="large"
    >
      <div className="execute-dialog">
        <div className="form-group">
          <label>Test Data (JSON)</label>
          <textarea
            value={testData}
            onChange={e => setTestData(e.target.value)}
            rows={10}
            className="code-input"
            placeholder='[{"field": "value"}]'
          />
        </div>
        
        {result && (
          <div className={`execution-result ${result.error ? 'error' : 'success'}`}>
            {result.error ? (
              <div className="error-message">
                <i className="fas fa-exclamation-circle"></i>
                {result.error}
              </div>
            ) : (
              <div className="result-summary">
                <h4>Execution Complete</h4>
                <div className="result-stats">
                  <div className="stat">
                    <span className="stat-label">Status</span>
                    <StatusBadge status={result.status} />
                  </div>
                  <div className="stat">
                    <span className="stat-label">Records</span>
                    <span className="stat-value">{result.total_records}</span>
                  </div>
                  <div className="stat">
                    <span className="stat-label">Pass Rate</span>
                    <span className="stat-value">{(result.overall_pass_rate || 0).toFixed(1)}%</span>
                  </div>
                  <div className="stat">
                    <span className="stat-label">Duration</span>
                    <span className="stat-value">{(result.duration_seconds || 0).toFixed(2)}s</span>
                  </div>
                </div>
                
                {result.rule_results && result.rule_results.length > 0 && (
                  <div className="rule-results">
                    <h5>Rule Results</h5>
                    {result.rule_results.map((rr, idx) => (
                      <div key={idx} className={`rule-result ${rr.passed ? 'passed' : 'failed'}`}>
                        <span className="rule-name">{rr.rule_name}</span>
                        <StatusBadge status={rr.passed ? 'passed' : 'failed'} />
                        <span className="rule-stats">
                          {rr.passed_count}/{rr.total_checked} passed
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </div>
      
      <div className="modal-footer">
        <button className="btn-secondary" onClick={onClose}>Close</button>
        <button 
          className="btn-primary" 
          onClick={handleExecute}
          disabled={executing}
        >
          {executing ? (
            <><i className="fas fa-spinner fa-spin"></i> Executing...</>
          ) : (
            <><i className="fas fa-play"></i> Execute Rules</>
          )}
        </button>
      </div>
    </Modal>
  );
}

/**
 * Main Rule Engine Management Component
 */
export function RuleEngineManagement() {
  // State
  const [activeTab, setActiveTab] = useState('rule-sets');
  const [ruleSets, setRuleSets] = useState([]);
  const [templates, setTemplates] = useState([]);
  const [executions, setExecutions] = useState([]);
  const [quarantine, setQuarantine] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  
  // Modal states
  const [showRuleSetModal, setShowRuleSetModal] = useState(false);
  const [showRuleModal, setShowRuleModal] = useState(false);
  const [showExecuteModal, setShowExecuteModal] = useState(false);
  const [showRulesPanel, setShowRulesPanel] = useState(false);
  const [showExecutionDetailsModal, setShowExecutionDetailsModal] = useState(false);
  const [showQuarantineReviewModal, setShowQuarantineReviewModal] = useState(false);
  
  // Selected items
  const [selectedRuleSet, setSelectedRuleSet] = useState(null);
  const [selectedRule, setSelectedRule] = useState(null);
  const [parentRuleId, setParentRuleId] = useState(null);
  const [currentRules, setCurrentRules] = useState([]);
  const [selectedExecution, setSelectedExecution] = useState(null);
  const [selectedQuarantineRecord, setSelectedQuarantineRecord] = useState(null);

  const tabs = [
    { id: 'rule-sets', label: 'Rule Sets', icon: 'fas fa-folder-open', count: ruleSets.length },
    { id: 'templates', label: 'Templates', icon: 'fas fa-file-code', count: templates.length },
    { id: 'executions', label: 'Executions', icon: 'fas fa-history', count: executions.length },
    { id: 'quarantine', label: 'Quarantine', icon: 'fas fa-shield-alt', count: quarantine.length },
  ];

  // Load data
  const loadRuleSets = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE}/sets`);
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();
      setRuleSets(data.items || []);
    } catch (err) {
      console.error('Failed to load rule sets:', err);
      setError('Failed to load rule sets');
    }
  }, []);

  const loadTemplates = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE}/templates/`);
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();
      setTemplates(data.items || []);
    } catch (err) {
      console.error('Failed to load templates:', err);
    }
  }, []);

  const loadExecutions = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE}/executions`);
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();
      setExecutions(data.items || []);
    } catch (err) {
      console.error('Failed to load executions:', err);
    }
  }, []);

  const loadQuarantine = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE}/quarantine`);
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();
      setQuarantine(data.items || []);
    } catch (err) {
      console.error('Failed to load quarantine:', err);
    }
  }, []);

  const loadRulesForSet = useCallback(async (ruleSetId) => {
    try {
      const response = await fetch(`${API_BASE}/sets/${ruleSetId}`);
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();
      setCurrentRules(data.rules || []);
    } catch (err) {
      console.error('Failed to load rules:', err);
    }
  }, []);

  useEffect(() => {
    const loadAll = async () => {
      setLoading(true);
      await Promise.all([
        loadRuleSets(),
        loadTemplates(),
        loadExecutions(),
        loadQuarantine(),
      ]);
      setLoading(false);
    };
    loadAll();
  }, [loadRuleSets, loadTemplates, loadExecutions, loadQuarantine]);

  // Handlers
  const handleCreateRuleSet = () => {
    setSelectedRuleSet(null);
    setShowRuleSetModal(true);
  };

  const handleEditRuleSet = (ruleSet) => {
    setSelectedRuleSet(ruleSet);
    setShowRuleSetModal(true);
  };

  const handleSaveRuleSet = async (data) => {
    try {
      const url = selectedRuleSet?.id 
        ? `${API_BASE}/sets/${selectedRuleSet.id}`
        : `${API_BASE}/sets`;
      const method = selectedRuleSet?.id ? 'PUT' : 'POST';
      
      const response = await fetch(url, {
        method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
      });
      
      if (!response.ok) {
        const err = await response.json();
        throw new Error(err.detail || 'Failed to save rule set');
      }
      
      await loadRuleSets();
      setShowRuleSetModal(false);
    } catch (err) {
      setError(err.message);
    }
  };

  const handleDeleteRuleSet = async (id) => {
    if (!confirm('Are you sure you want to delete this rule set?')) return;
    try {
      await fetch(`${API_BASE}/sets/${id}`, { method: 'DELETE' });
      await loadRuleSets();
    } catch {
      setError('Failed to delete rule set');
    }
  };

  const handleViewRules = async (ruleSet) => {
    setSelectedRuleSet(ruleSet);
    await loadRulesForSet(ruleSet.id);
    setShowRulesPanel(true);
  };

  const handleExecuteRuleSet = (ruleSet) => {
    setSelectedRuleSet(ruleSet);
    setShowExecuteModal(true);
  };

  const handleCreateRule = (parentRule = null) => {
    setSelectedRule(null);
    setParentRuleId(parentRule?.id || null);
    setShowRuleModal(true);
  };

  const handleEditRule = (rule) => {
    setSelectedRule(rule);
    setParentRuleId(rule.parent_rule_id);
    setShowRuleModal(true);
  };

  const handleSaveRule = async (data) => {
    try {
      const url = selectedRule?.id 
        ? `${API_BASE}/${selectedRule.id}`
        : `${API_BASE}/`;
      const method = selectedRule?.id ? 'PUT' : 'POST';
      
      const response = await fetch(url, {
        method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
      });
      
      if (!response.ok) {
        const err = await response.json();
        throw new Error(err.detail || 'Failed to save rule');
      }
      
      if (selectedRuleSet) {
        await loadRulesForSet(selectedRuleSet.id);
      }
      await loadRuleSets();
      setShowRuleModal(false);
    } catch (err) {
      setError(err.message);
    }
  };

  const handleDeleteRule = async (id) => {
    if (!confirm('Are you sure you want to delete this rule?')) return;
    try {
      await fetch(`${API_BASE}/${id}`, { method: 'DELETE' });
      if (selectedRuleSet) {
        await loadRulesForSet(selectedRuleSet.id);
      }
      await loadRuleSets();
    } catch {
      setError('Failed to delete rule');
    }
  };

  const handleUseTemplate = () => {
    setSelectedRule(null);
    setParentRuleId(null);
    setShowRuleModal(true);
  };

  // Execution details handler
  const handleViewExecutionDetails = (execution) => {
    setSelectedExecution(execution);
    setShowExecutionDetailsModal(true);
  };

  // Quarantine record review handler
  const handleReviewQuarantine = (record) => {
    setSelectedQuarantineRecord(record);
    setShowQuarantineReviewModal(true);
  };

  // Release record from quarantine
  const handleReleaseQuarantine = async (recordId) => {
    if (!confirm('Are you sure you want to release this record from quarantine?')) return;
    try {
      const response = await fetch(`${API_BASE}/quarantine/${recordId}/resolve`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      });
      if (!response.ok) {
        const err = await response.json();
        throw new Error(err.detail || 'Failed to release record');
      }
      await loadQuarantine();
    } catch (err) {
      setError(err.message || 'Failed to release record from quarantine');
    }
  };

  const handleRefresh = () => {
    loadRuleSets();
    loadTemplates();
    loadExecutions();
    loadQuarantine();
  };

  return (
    <div className="rule-engine-management">
      <div className="rule-engine-header">
        <div className="header-title">
          <h2><i className="fas fa-clipboard-check"></i> PLM Rule Engine</h2>
          <p>Define and execute data quality rules for ETL pipelines</p>
        </div>
        <div className="header-actions">
          <button className="btn-secondary" onClick={handleRefresh}>
            <i className="fas fa-sync-alt"></i> Refresh
          </button>
          {activeTab === 'rule-sets' && (
            <button className="btn-primary" onClick={handleCreateRuleSet}>
              <i className="fas fa-plus"></i> New Rule Set
            </button>
          )}
        </div>
      </div>

      {error && (
        <div className="error-banner">
          <i className="fas fa-exclamation-circle"></i>
          {error}
          <button onClick={() => setError(null)}><i className="fas fa-times"></i></button>
        </div>
      )}

      <TabNavigation tabs={tabs} activeTab={activeTab} onTabChange={setActiveTab} />

      <div className="rule-engine-content">
        {activeTab === 'rule-sets' && (
          <RuleSetsTable
            ruleSets={ruleSets}
            onEdit={handleEditRuleSet}
            onDelete={handleDeleteRuleSet}
            onViewRules={handleViewRules}
            onExecute={handleExecuteRuleSet}
            loading={loading}
          />
        )}

        {activeTab === 'templates' && (
          <TemplatesTable
            templates={templates}
            onUse={handleUseTemplate}
            loading={loading}
          />
        )}

        {activeTab === 'executions' && (
          <ExecutionsTable
            executions={executions}
            onViewDetails={handleViewExecutionDetails}
            loading={loading}
          />
        )}

        {activeTab === 'quarantine' && (
          <QuarantineTable
            records={quarantine}
            onReview={handleReviewQuarantine}
            onRelease={handleReleaseQuarantine}
            loading={loading}
          />
        )}
      </div>

      {/* Rule Set Modal */}
      {showRuleSetModal && (
        <Modal
          isOpen={true}
          onClose={() => setShowRuleSetModal(false)}
          title={selectedRuleSet ? 'Edit Rule Set' : 'Create Rule Set'}
          size="medium"
        >
          <RuleSetForm
            ruleSet={selectedRuleSet}
            onSave={handleSaveRuleSet}
            onCancel={() => setShowRuleSetModal(false)}
          />
        </Modal>
      )}

      {/* Rule Modal */}
      {showRuleModal && (
        <Modal
          isOpen={true}
          onClose={() => setShowRuleModal(false)}
          title={selectedRule ? 'Edit Rule' : (parentRuleId ? 'Add Child Rule' : 'Create Rule')}
          size="large"
        >
          <RuleForm
            rule={selectedRule}
            ruleSetId={selectedRuleSet?.id}
            parentRuleId={parentRuleId}
            templates={templates}
            onSave={handleSaveRule}
            onCancel={() => setShowRuleModal(false)}
          />
        </Modal>
      )}

      {/* Execute Modal */}
      {showExecuteModal && selectedRuleSet && (
        <ExecuteDialog
          ruleSet={selectedRuleSet}
          onExecute={() => {
            loadExecutions();
          }}
          onClose={() => setShowExecuteModal(false)}
        />
      )}

      {/* Rules Panel (Side Panel) */}
      {showRulesPanel && selectedRuleSet && (
        <div className="rules-panel-overlay" onClick={() => setShowRulesPanel(false)}>
          <div className="rules-panel" onClick={e => e.stopPropagation()}>
            <div className="rules-panel-header">
              <h3>
                <i className="fas fa-gavel"></i>
                Rules: {selectedRuleSet.name}
              </h3>
              <div className="panel-actions">
                <button className="btn-primary btn-small" onClick={() => handleCreateRule()}>
                  <i className="fas fa-plus"></i> Add Rule
                </button>
                <button className="btn-close" onClick={() => setShowRulesPanel(false)}>
                  <i className="fas fa-times"></i>
                </button>
              </div>
            </div>
            <div className="rules-panel-content">
              <RulesTable
                rules={currentRules}
                onEdit={handleEditRule}
                onDelete={handleDeleteRule}
                onAddChild={handleCreateRule}
              />
            </div>
          </div>
        </div>
      )}

      {/* Execution Details Modal */}
      {showExecutionDetailsModal && selectedExecution && (
        <Modal
          isOpen={true}
          onClose={() => {
            setShowExecutionDetailsModal(false);
            setSelectedExecution(null);
          }}
          title="Execution Details"
          size="large"
        >
          <div className="execution-details">
            <div className="detail-grid">
              <div className="detail-item">
                <label>Execution ID</label>
                <span className="monospace">{selectedExecution.id}</span>
              </div>
              <div className="detail-item">
                <label>Rule Set</label>
                <span>{selectedExecution.rule_set_name || selectedExecution.rule_set_id}</span>
              </div>
              <div className="detail-item">
                <label>Status</label>
                <StatusBadge status={selectedExecution.status} />
              </div>
              <div className="detail-item">
                <label>Started</label>
                <span>{selectedExecution.started_at ? new Date(selectedExecution.started_at).toLocaleString() : '-'}</span>
              </div>
              <div className="detail-item">
                <label>Completed</label>
                <span>{selectedExecution.completed_at ? new Date(selectedExecution.completed_at).toLocaleString() : '-'}</span>
              </div>
              <div className="detail-item">
                <label>Duration</label>
                <span>{selectedExecution.duration_seconds ? `${selectedExecution.duration_seconds.toFixed(2)}s` : '-'}</span>
              </div>
              <div className="detail-item">
                <label>Total Records</label>
                <span>{selectedExecution.total_records || 0}</span>
              </div>
              <div className="detail-item">
                <label>Pass Rate</label>
                <div className="pass-rate">
                  <div 
                    className="pass-rate-bar" 
                    style={{ width: `${Math.max(0, selectedExecution.pass_rate || 0)}%` }}
                  ></div>
                  <span>{(selectedExecution.pass_rate || 0).toFixed(1)}%</span>
                </div>
              </div>
            </div>
            
            {selectedExecution.rule_results && selectedExecution.rule_results.length > 0 && (
              <div className="rule-results-section">
                <h4><i className="fas fa-list-check"></i> Rule Results</h4>
                <table className="rule-table compact">
                  <thead>
                    <tr>
                      <th>Rule</th>
                      <th>Status</th>
                      <th>Passed</th>
                      <th>Failed</th>
                      <th>Pass Rate</th>
                    </tr>
                  </thead>
                  <tbody>
                    {selectedExecution.rule_results.map((rr, idx) => (
                      <tr key={idx}>
                        <td>{rr.rule_name || rr.rule_id}</td>
                        <td><StatusBadge status={rr.passed ? 'passed' : 'failed'} /></td>
                        <td className="num-cell">{rr.passed_count || 0}</td>
                        <td className="num-cell">{rr.failed_count || 0}</td>
                        <td>
                          {rr.total_checked > 0 
                            ? `${((rr.passed_count / rr.total_checked) * 100).toFixed(1)}%`
                            : '-'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {selectedExecution.errors && selectedExecution.errors.length > 0 && (
              <div className="errors-section">
                <h4><i className="fas fa-exclamation-triangle"></i> Errors</h4>
                <ul className="error-list">
                  {selectedExecution.errors.map((err, idx) => (
                    <li key={idx} className="error-item">{err}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        </Modal>
      )}

      {/* Quarantine Review Modal */}
      {showQuarantineReviewModal && selectedQuarantineRecord && (
        <Modal
          isOpen={true}
          onClose={() => {
            setShowQuarantineReviewModal(false);
            setSelectedQuarantineRecord(null);
          }}
          title="Quarantine Record Review"
          size="large"
        >
          <div className="quarantine-review">
            <div className="review-header">
              <div className="detail-item">
                <label>Record ID</label>
                <span className="monospace">{selectedQuarantineRecord.id}</span>
              </div>
              <div className="detail-item">
                <label>Status</label>
                <StatusBadge status={selectedQuarantineRecord.status || 'quarantined'} />
              </div>
              <div className="detail-item">
                <label>Quarantined At</label>
                <span>
                  {selectedQuarantineRecord.created_at 
                    ? new Date(selectedQuarantineRecord.created_at).toLocaleString() 
                    : '-'}
                </span>
              </div>
            </div>

            <div className="review-section">
              <h4><i className="fas fa-exclamation-circle"></i> Violation Details</h4>
              <div className="violation-info">
                <div className="detail-item">
                  <label>Rule</label>
                  <span>{selectedQuarantineRecord.rule_name || selectedQuarantineRecord.rule_id || '-'}</span>
                </div>
                <div className="detail-item">
                  <label>Reason</label>
                  <span>{selectedQuarantineRecord.reason || 'Rule violation'}</span>
                </div>
                {selectedQuarantineRecord.severity && (
                  <div className="detail-item">
                    <label>Severity</label>
                    <SeverityBadge severity={selectedQuarantineRecord.severity} />
                  </div>
                )}
              </div>
            </div>

            {selectedQuarantineRecord.record_data && (
              <div className="review-section">
                <h4><i className="fas fa-database"></i> Record Data</h4>
                <pre className="record-data-json">
                  {JSON.stringify(selectedQuarantineRecord.record_data, null, 2)}
                </pre>
              </div>
            )}

            <div className="modal-footer">
              <button 
                className="btn-secondary" 
                onClick={() => {
                  setShowQuarantineReviewModal(false);
                  setSelectedQuarantineRecord(null);
                }}
              >
                Close
              </button>
              <button 
                className="btn-primary"
                onClick={() => {
                  handleReleaseQuarantine(selectedQuarantineRecord.id);
                  setShowQuarantineReviewModal(false);
                  setSelectedQuarantineRecord(null);
                }}
              >
                <i className="fas fa-unlock"></i> Release from Quarantine
              </button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
}

export default RuleEngineManagement;
