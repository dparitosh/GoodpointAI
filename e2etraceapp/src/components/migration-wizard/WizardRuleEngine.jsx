import React from 'react';

const CONDITIONS = {
  pre:     ['IS_NULL', 'IS_EMPTY', 'MATCHES_REGEX', 'NOT_IN_LIST', 'CUSTOM'],
  quality: ['IS_NULL', 'IS_NOT_UNIQUE', 'OUT_OF_RANGE', 'FAILS_REGEX', 'BELOW_MIN_LENGTH', 'ABOVE_MAX_LENGTH', 'CUSTOM'],
  post:    ['IS_NULL', 'OUT_OF_RANGE', 'MATCHES_REGEX', 'CUSTOM'],
};

const ACTIONS = {
  pre:     ['SET_DEFAULT', 'SKIP_RECORD', 'COERCE_TYPE', 'TRIM', 'TO_UPPER', 'TO_LOWER', 'REGEX_REPLACE'],
  quality: ['REJECT_RECORD', 'FLAG_WARNING', 'SET_DEFAULT', 'QUARANTINE'],
  post:    ['REJECT_RECORD', 'FLAG_WARNING', 'ROUTE_TO_DLQ', 'AUDIT_LOG', 'ASSERT'],
};

const PHASES = [
  { key: 'pre',     icon: 'fa-filter',         label: 'Pre-Transform',  color: '#6366f1', desc: 'Filter & normalise before mapping' },
  { key: 'quality', icon: 'fa-shield-alt',     label: 'Quality Check',  color: '#f59e0b', desc: 'Gate records on data quality' },
  { key: 'post',    icon: 'fa-flag-checkered', label: 'Post-Transform', color: '#10b981', desc: 'Assert & route after mapping' },
];

const PHASE_META = Object.fromEntries(PHASES.map(p => [p.key, p]));

/**
 * WizardRuleEngine — unified Rule Engine table showing pre-transform, quality,
 * and post-transform rules as categories in one place.
 *
 * Props:
 *   rules        – array of rule objects from wizardData.rules
 *   activePhase  – kept for API compat (not used for display filtering)
 *   sourceFields – string[] of source field names
 *   onPhaseChange, onAddRule, onRemoveRule, onUpdateRule – callbacks
 */
const WizardRuleEngine = ({
  rules,
  sourceFields,
  onAddRule,
  onRemoveRule,
  onUpdateRule,
}) => {
  return (
    <div className="re-panel">
      <div className="re-panel-header">
        <span className="re-panel-title">
          <i className="fas fa-sliders-h" /> Rule Engine
        </span>
        <span className="re-panel-subtitle">
          Configure pre-transform filters, data quality gates, and post-transform assertions
        </span>
        <span className="re-badge">{rules.length} rule{rules.length !== 1 ? 's' : ''}</span>
      </div>

      {/* Category legend */}
      <div className="re-legend">
        {PHASES.map(p => (
          <span key={p.key} className="re-legend-item">
            <span className="re-category-badge" style={{ background: p.color }}>
              <i className={`fas ${p.icon}`} /> {p.label}
            </span>
            <span className="re-legend-desc">{p.desc}</span>
          </span>
        ))}
      </div>

      {/* Unified table */}
      <div className="re-rules-area">
        {rules.length === 0 ? (
          <div className="re-empty">
            <i className="fas fa-plus-circle" />
            <span>No rules yet. Use the buttons below to add a rule in any category.</span>
          </div>
        ) : (
          <div className="re-rules-list">
            <div className="re-rules-header re-rules-header--unified">
              <span>Category</span>
              <span>Rule Name</span>
              <span>Field</span>
              <span>Condition</span>
              <span>Value</span>
              <span>Action</span>
              <span>Action Value</span>
              <span>On</span>
              <span></span>
            </div>
            {rules.map(rule => {
              const meta = PHASE_META[rule.phase] || PHASE_META.pre;
              return (
                <div key={rule.id} className={`re-rule-row re-rule-row--unified ${rule.enabled ? '' : 're-rule-disabled'}`}>
                  {/* Category badge */}
                  <span className="re-category-badge" style={{ background: meta.color }}>
                    <i className={`fas ${meta.icon}`} /> {meta.label}
                  </span>
                  <input
                    className="re-input re-name"
                    placeholder="Rule name…"
                    value={rule.name}
                    onChange={e => onUpdateRule(rule.id, { name: e.target.value })}
                  />
                  <select
                    className="re-select re-field"
                    value={rule.field}
                    onChange={e => onUpdateRule(rule.id, { field: e.target.value })}
                  >
                    <option value="*">All fields</option>
                    {sourceFields.map(f => <option key={f} value={f}>{f}</option>)}
                  </select>
                  <select
                    className="re-select re-condition"
                    value={rule.condition}
                    onChange={e => onUpdateRule(rule.id, { condition: e.target.value })}
                  >
                    <option value="">-- condition --</option>
                    {(CONDITIONS[rule.phase] || CONDITIONS.pre).map(c => (
                      <option key={c} value={c}>{c}</option>
                    ))}
                  </select>
                  <input
                    className="re-input re-cond-val"
                    placeholder="e.g. pattern, range…"
                    value={rule.condition_value}
                    onChange={e => onUpdateRule(rule.id, { condition_value: e.target.value })}
                  />
                  <select
                    className="re-select re-action"
                    value={rule.action}
                    onChange={e => onUpdateRule(rule.id, { action: e.target.value })}
                  >
                    <option value="">-- action --</option>
                    {(ACTIONS[rule.phase] || ACTIONS.pre).map(a => (
                      <option key={a} value={a}>{a}</option>
                    ))}
                  </select>
                  <input
                    className="re-input re-action-val"
                    placeholder="e.g. default val…"
                    value={rule.action_value}
                    onChange={e => onUpdateRule(rule.id, { action_value: e.target.value })}
                  />
                  <label className="re-toggle" title={rule.enabled ? 'Enabled' : 'Disabled'}>
                    <input
                      type="checkbox"
                      checked={rule.enabled}
                      onChange={e => onUpdateRule(rule.id, { enabled: e.target.checked })}
                    />
                    <span className="re-toggle-track" />
                  </label>
                  <button className="re-btn-delete" title="Remove rule" onClick={() => onRemoveRule(rule.id)}>
                    <i className="fas fa-trash-alt" />
                  </button>
                </div>
              );
            })}
          </div>
        )}

        {/* Add buttons — one per category */}
        <div className="re-add-row">
          {PHASES.map(p => (
            <button
              key={p.key}
              className="re-btn-add"
              style={{ borderColor: p.color, color: p.color }}
              onClick={() => onAddRule(p.key)}
            >
              <i className={`fas ${p.icon}`} /> Add {p.label} Rule
            </button>
          ))}
        </div>
      </div>
    </div>
  );
};

export default WizardRuleEngine;
