/**
 * PLM Rule Engine Management Component
 * 
 * Provides UI for:
 * - Creating and managing rule sets
 * - Defining hierarchical rules with DAG dependencies
 * - Rule templates and expression builder
 * - Execution and result visualization
 * - Quarantine management
 */

import React, { useState, useEffect, useCallback } from 'react';
import { API_CONFIG } from '../config/api-config';
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
      />
    );
  }

  return (
    <table className="rule-table">
      <thead>
        <tr>
          <th>Name</th>
          <th>Category</th>
          <th>Context</th>
          <th>Version</th>
          <th>Execution Mode</th>
          <th>Rules</th>
          <th>Status</th>
          <th>Actions</th>
        </tr>
      </thead>
      <tbody>
        {ruleSets.map(rs => (
          <tr key={rs.id}>
            <td className="name-cell">
              <strong>{rs.name}</strong>
              {rs.description && <small>{rs.description}</small>}
            </td>
            <td>{rs.category || 'general'}</td>
            <td>{rs.context || '-'}</td>
            <td>{rs.version}</td>
            <td>
              <span className={`execution-mode ${rs.execution_mode}`}>
                {rs.execution_mode}
              </span>
            </td>
            <td className="count-cell">{rs.rule_count || 0}</td>
            <td>
              <StatusBadge status={rs.is_active ? 'active' : 'inactive'} />
            </td>
            <td className="actions-cell">
              <button 
                className="btn-action btn-view" 
                onClick={() => onViewRules(rs)}
                title="View Rules"
              >
                <i className="fas fa-list"></i>
              </button>
              <button 
                className="btn-action btn-run" 
                onClick={() => onExecute(rs)}
                title="Execute Rules"
              >
                <i className="fas fa-play"></i>
              </button>
              <button 
                className="btn-action btn-edit" 
                onClick={() => onEdit(rs)}
                title="Edit"
              >
                <i className="fas fa-edit"></i>
              </button>
              <button 
                className="btn-action btn-delete" 
                onClick={() => onDelete(rs.id)}
                title="Delete"
              >
                <i className="fas fa-trash"></i>
              </button>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

// Rules Table (for viewing rules within a rule set)
function RulesTable({ rules, onEdit, onDelete, onAddChild }) {
  if (!rules.length) {
    return (
      <EmptyState 
        icon="fas fa-gavel" 
        message="No rules in this rule set"
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
          <div className="rule-header">
            <div className="rule-title">
              <LevelBadge level={rule.level} />
              <strong>{rule.name}</strong>
              <SeverityBadge severity={rule.severity} />
            </div>
            <div className="rule-actions">
              <button 
                className="btn-action btn-add-child" 
                onClick={() => onAddChild(rule)}
                title="Add Child Rule"
              >
                <i className="fas fa-plus"></i>
              </button>
              <button 
                className="btn-action btn-edit" 
                onClick={() => onEdit(rule)}
                title="Edit"
              >
                <i className="fas fa-edit"></i>
              </button>
              <button 
                className="btn-action btn-delete" 
                onClick={() => onDelete(rule.id)}
                title="Delete"
              >
                <i className="fas fa-trash"></i>
              </button>
            </div>
          </div>
          <div className="rule-body">
            <div className="rule-expression">
              <code>{rule.expression}</code>
            </div>
            <div className="rule-meta">
              <span className="action-badge" title="Action on Fail">
                <i className="fas fa-exclamation-triangle"></i> {rule.action_on_fail}
              </span>
              <span className="type-badge" title="Expression Type">
                <i className="fas fa-code"></i> {rule.expression_type}
              </span>
            </div>
          </div>
          
          {/* Child Rules */}
          {childRulesMap[rule.id] && childRulesMap[rule.id].length > 0 && (
            <div className="child-rules">
              <div className="child-rules-header">
                <i className="fas fa-sitemap"></i> Child Rules ({childRulesMap[rule.id].length})
              </div>
              {childRulesMap[rule.id].map(child => (
                <div key={child.id} className="rule-card child-rule">
                  <div className="rule-header">
                    <div className="rule-title">
                      <LevelBadge level={child.level} />
                      <strong>{child.name}</strong>
                      <SeverityBadge severity={child.severity} />
                    </div>
                    <div className="rule-actions">
                      <button 
                        className="btn-action btn-edit" 
                        onClick={() => onEdit(child)}
                        title="Edit"
                      >
                        <i className="fas fa-edit"></i>
                      </button>
                      <button 
                        className="btn-action btn-delete" 
                        onClick={() => onDelete(child.id)}
                        title="Delete"
                      >
                        <i className="fas fa-trash"></i>
                      </button>
                    </div>
                  </div>
                  <div className="rule-body">
                    <div className="rule-expression">
                      <code>{child.expression}</code>
                    </div>
                    <div className="rule-meta">
                      <span className="dependency-badge" title="Dependency Condition">
                        <i className="fas fa-link"></i> {child.dependency_condition || 'parent_pass'}
                      </span>
                      <span className="action-badge" title="Action on Fail">
                        <i className="fas fa-exclamation-triangle"></i> {child.action_on_fail}
                      </span>
                    </div>
                  </div>
                </div>
              ))}
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

// Rule Set Form
function RuleSetForm({ ruleSet, onSave, onCancel }) {
  const [form, setForm] = useState({
    name: ruleSet?.name || '',
    description: ruleSet?.description || '',
    version: ruleSet?.version || '1.0.0',
    category: ruleSet?.category || 'general',
    context: ruleSet?.context || '',
    target_entity_type: ruleSet?.target_entity_type || '',
    execution_mode: ruleSet?.execution_mode || 'sequential',
    stop_on_critical: ruleSet?.stop_on_critical ?? true,
    timeout_seconds: ruleSet?.timeout_seconds || 3600,
  });

  const handleChange = (field, value) => {
    setForm(prev => ({ ...prev, [field]: value }));
  };

  return (
    <div className="form-grid">
      <div className="form-group">
        <label>Name *</label>
        <input
          type="text"
          value={form.name}
          onChange={e => handleChange('name', e.target.value)}
          placeholder="e.g., BOM Validation V1"
          required
        />
      </div>
      
      <div className="form-group">
        <label>Description</label>
        <textarea
          value={form.description}
          onChange={e => handleChange('description', e.target.value)}
          placeholder="Describe the purpose of this rule set"
          rows={3}
        />
      </div>
      
      <div className="form-row">
        <div className="form-group">
          <label>Version</label>
          <input
            type="text"
            value={form.version}
            onChange={e => handleChange('version', e.target.value)}
            placeholder="1.0.0"
          />
        </div>
        
        <div className="form-group">
          <label>Category</label>
          <select
            value={form.category}
            onChange={e => handleChange('category', e.target.value)}
          >
            <option value="general">General</option>
            <option value="plm_validation">PLM Validation</option>
            <option value="data_quality">Data Quality</option>
            <option value="compliance">Compliance</option>
            <option value="etl">ETL</option>
          </select>
        </div>
      </div>
      
      <div className="form-row">
        <div className="form-group">
          <label>Context</label>
          <input
            type="text"
            value={form.context}
            onChange={e => handleChange('context', e.target.value)}
            placeholder="e.g., Engineering_BOM"
          />
        </div>
        
        <div className="form-group">
          <label>Target Entity Type</label>
          <input
            type="text"
            value={form.target_entity_type}
            onChange={e => handleChange('target_entity_type', e.target.value)}
            placeholder="e.g., BOM, Item, CADModel"
          />
        </div>
      </div>
      
      <div className="form-row">
        <div className="form-group">
          <label>Execution Mode</label>
          <select
            value={form.execution_mode}
            onChange={e => handleChange('execution_mode', e.target.value)}
          >
            <option value="sequential">Sequential</option>
            <option value="parallel">Parallel</option>
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
          />
        </div>
      </div>
      
      <div className="form-group checkbox-group">
        <label>
          <input
            type="checkbox"
            checked={form.stop_on_critical}
            onChange={e => handleChange('stop_on_critical', e.target.checked)}
          />
          Stop execution on critical failure
        </label>
      </div>
      
      <div className="form-actions">
        <button className="btn-secondary" onClick={onCancel}>Cancel</button>
        <button 
          className="btn-primary" 
          onClick={() => onSave(form)}
          disabled={!form.name}
        >
          {ruleSet?.id ? 'Update Rule Set' : 'Create Rule Set'}
        </button>
      </div>
    </div>
  );
}

// Rule Form
function RuleForm({ rule, ruleSetId, parentRuleId, templates, onSave, onCancel }) {
  const [form, setForm] = useState({
    rule_set_id: ruleSetId,
    name: rule?.name || '',
    description: rule?.description || '',
    level: rule?.level || 'entity',
    severity: rule?.severity || 'warning',
    expression: rule?.expression || '',
    expression_type: rule?.expression_type || 'python',
    action_on_fail: rule?.action_on_fail || 'log',
    transformation_expression: rule?.transformation_expression || '',
    parent_rule_id: parentRuleId || rule?.parent_rule_id || null,
    dependency_condition: rule?.dependency_condition || 'parent_pass',
    sequence_order: rule?.sequence_order || 0,
  });
  
  const [testResult, setTestResult] = useState(null);
  const [testing, setTesting] = useState(false);

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
  };

  const testExpression = async () => {
    setTesting(true);
    setTestResult(null);
    try {
      const response = await fetch(`${API_BASE}/validate-expression`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          expression: form.expression,
          expression_type: form.expression_type,
          test_data: { test: true },
        }),
      });
      const data = await response.json();
      setTestResult(data);
    } catch (error) {
      setTestResult({ valid: false, error: error.message });
    }
    setTesting(false);
  };

  return (
    <div className="form-grid">
      {templates && templates.length > 0 && (
        <div className="form-group template-selector">
          <label>Start from Template</label>
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
      
      <div className="form-group">
        <label>Name *</label>
        <input
          type="text"
          value={form.name}
          onChange={e => handleChange('name', e.target.value)}
          placeholder="e.g., R101 - Lifecycle Check"
          required
        />
      </div>
      
      <div className="form-group">
        <label>Description</label>
        <textarea
          value={form.description}
          onChange={e => handleChange('description', e.target.value)}
          placeholder="Describe what this rule validates"
          rows={2}
        />
      </div>
      
      <div className="form-row">
        <div className="form-group">
          <label>Level</label>
          <select
            value={form.level}
            onChange={e => handleChange('level', e.target.value)}
          >
            <option value="attribute">Attribute (Field-level)</option>
            <option value="entity">Entity (Row-level)</option>
            <option value="relationship">Relationship (Graph/BOM)</option>
          </select>
        </div>
        
        <div className="form-group">
          <label>Severity</label>
          <select
            value={form.severity}
            onChange={e => handleChange('severity', e.target.value)}
          >
            <option value="info">Info</option>
            <option value="warning">Warning</option>
            <option value="critical">Critical</option>
            <option value="blocker">Blocker</option>
          </select>
        </div>
      </div>
      
      <div className="form-group">
        <label>Expression *</label>
        <div className="expression-editor">
          <textarea
            value={form.expression}
            onChange={e => handleChange('expression', e.target.value)}
            placeholder="e.g., lifecycle_state == 'RELEASED'"
            rows={3}
            className="code-input"
          />
          <div className="expression-actions">
            <select
              value={form.expression_type}
              onChange={e => handleChange('expression_type', e.target.value)}
              className="expression-type-select"
            >
              <option value="python">Python</option>
              <option value="sql">SQL</option>
              <option value="sparksql">SparkSQL</option>
              <option value="cypher">Cypher</option>
            </select>
            <button 
              className="btn-secondary btn-small"
              onClick={testExpression}
              disabled={testing || !form.expression}
            >
              {testing ? <i className="fas fa-spinner fa-spin"></i> : <i className="fas fa-flask"></i>}
              Test
            </button>
          </div>
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
      
      <div className="form-row">
        <div className="form-group">
          <label>Action on Fail</label>
          <select
            value={form.action_on_fail}
            onChange={e => handleChange('action_on_fail', e.target.value)}
          >
            <option value="log">Log</option>
            <option value="warn">Warn</option>
            <option value="quarantine">Quarantine</option>
            <option value="reject">Reject</option>
            <option value="transform">Transform</option>
            <option value="escalate">Escalate</option>
          </select>
        </div>
        
        <div className="form-group">
          <label>Sequence Order</label>
          <input
            type="number"
            value={form.sequence_order}
            onChange={e => handleChange('sequence_order', parseInt(e.target.value))}
            min={0}
          />
        </div>
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
      
      {parentRuleId && (
        <div className="form-group">
          <label>Dependency Condition</label>
          <select
            value={form.dependency_condition}
            onChange={e => handleChange('dependency_condition', e.target.value)}
          >
            <option value="parent_pass">Run if parent passes</option>
            <option value="parent_fail">Run if parent fails</option>
            <option value="always">Always run</option>
          </select>
        </div>
      )}
      
      <div className="form-actions">
        <button className="btn-secondary" onClick={onCancel}>Cancel</button>
        <button 
          className="btn-primary" 
          onClick={() => onSave(form)}
          disabled={!form.name || !form.expression}
        >
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
          data: { records: Array.isArray(data) ? data : [data] },
        }),
      });
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
  
  // Selected items
  const [selectedRuleSet, setSelectedRuleSet] = useState(null);
  const [selectedRule, setSelectedRule] = useState(null);
  const [parentRuleId, setParentRuleId] = useState(null);
  const [currentRules, setCurrentRules] = useState([]);

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
      const data = await response.json();
      setTemplates(data.items || []);
    } catch (err) {
      console.error('Failed to load templates:', err);
    }
  }, []);

  const loadExecutions = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE}/executions`);
      const data = await response.json();
      setExecutions(data.items || []);
    } catch (err) {
      console.error('Failed to load executions:', err);
    }
  }, []);

  const loadQuarantine = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE}/quarantine`);
      const data = await response.json();
      setQuarantine(data.items || []);
    } catch (err) {
      console.error('Failed to load quarantine:', err);
    }
  }, []);

  const loadRulesForSet = useCallback(async (ruleSetId) => {
    try {
      const response = await fetch(`${API_BASE}/sets/${ruleSetId}`);
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
            onViewDetails={(ex) => console.log('View execution:', ex)}
            loading={loading}
          />
        )}

        {activeTab === 'quarantine' && (
          <QuarantineTable
            records={quarantine}
            onReview={(rec) => console.log('Review:', rec)}
            onRelease={(id) => console.log('Release:', id)}
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
    </div>
  );
}

export default RuleEngineManagement;
