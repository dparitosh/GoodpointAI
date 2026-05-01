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

const PHASE_TABS = [
  { key: 'pre',     icon: 'fa-filter',         label: 'Pre-Transform',  desc: 'Filter & normalise before mapping' },
  { key: 'quality', icon: 'fa-shield-alt',     label: 'Quality Check',  desc: 'Gate records on data quality' },
  { key: 'post',    icon: 'fa-flag-checkered', label: 'Post-Transform', desc: 'Assert & route after mapping' },
];

/**
 * WizardRuleEngine — self-contained Rule Engine panel used within the Map step.
 *
 * Props:
 *   rules           – array of rule objects from wizardData.rules
 *   activePhase     – 'pre' | 'quality' | 'post'
 *   sourceFields    – string[] of source field names (from extractSchemaFields)
 *   onPhaseChange   – (phase: string) => void
 *   onAddRule       – (phase: string) => void
 *   onRemoveRule    – (id: string) => void
 *   onUpdateRule    – (id: string, patch: object) => void
 */
const WizardRuleEngine = ({
  rules,
  activePhase,
  sourceFields,
  onPhaseChange,
  onAddRule,
  onRemoveRule,
  onUpdateRule,
}) => {
  const phaseRules = rules.filter(r => r.phase === activePhase);

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

      {/* Phase tabs */}
      <div className="re-tabs">
        {PHASE_TABS.map(tab => {
          const count = rules.filter(r => r.phase === tab.key).length;
          return (
            <button
              key={tab.key}
              className={`re-tab ${activePhase === tab.key ? 'active' : ''}`}
              onClick={() => onPhaseChange(tab.key)}
            >
              <i className={`fas ${tab.icon}`} />
              <span className="re-tab-label">{tab.label}</span>
              {count > 0 && <span className="re-tab-count">{count}</span>}
              <span className="re-tab-desc">{tab.desc}</span>
            </button>
          );
        })}
      </div>

      {/* Rule rows for active phase */}
      <div className="re-rules-area">
        {phaseRules.length === 0 ? (
          <div className="re-empty">
            <i className="fas fa-plus-circle" />
            <span>No {activePhase} rules yet. Add one below.</span>
          </div>
        ) : (
          <div className="re-rules-list">
            <div className="re-rules-header">
              <span>Rule Name</span>
              <span>Field</span>
              <span>Condition</span>
              <span>Value</span>
              <span>Action</span>
              <span>Action Value</span>
              <span>On</span>
              <span></span>
            </div>
            {phaseRules.map(rule => (
              <div key={rule.id} className={`re-rule-row ${rule.enabled ? '' : 're-rule-disabled'}`}>
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
                  {CONDITIONS[activePhase].map(c => <option key={c} value={c}>{c}</option>)}
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
                  {ACTIONS[activePhase].map(a => <option key={a} value={a}>{a}</option>)}
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
            ))}
          </div>
        )}

        <button className="re-btn-add" onClick={() => onAddRule(activePhase)}>
          <i className="fas fa-plus" /> Add{' '}
          {activePhase === 'pre' ? 'Pre-Transform' : activePhase === 'quality' ? 'Quality' : 'Post-Transform'} Rule
        </button>
      </div>
    </div>
  );
};

export default WizardRuleEngine;
