import React, { useMemo, useState, useCallback } from 'react';
import { API_CONFIG } from '../../config/api-config.js';

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

// ── NLP_EXAMPLES ─────────────────────────────────────────────────────────────
const NLP_EXAMPLES = [
  'part_number must not be empty',
  'status must be one of: Active, Inactive, Pending',
  'quantity must be between 0 and 99999',
  'customer_id must be unique',
  'description must have at least 3 characters',
  'sku must match pattern ^[A-Z]{3}-\\d{4}$',
];

/**
 * NlpRuleInput — chat-style panel for describing rules in plain English.
 * Calls POST /api/rules/v1/nlp-to-rule and appends the returned rule(s) to
 * the wizard rule list via onAddRules.
 */
const NlpRuleInput = ({ sourceFields, fieldMappings, onAddRules }) => {
  const [text, setText] = useState('');
  const [loading, setLoading] = useState(false);
  const [lastResult, setLastResult] = useState(null); // { rules, interpretation, ai_powered }
  const [error, setError] = useState(null);

  const handleGenerate = useCallback(async () => {
    const desc = text.trim();
    if (!desc) return;
    setLoading(true);
    setError(null);
    setLastResult(null);
    try {
      const _apiBase = (typeof import.meta !== 'undefined' && import.meta.env?.VITE_API_BASE_URL) || '';
      const res = await fetch(`${_apiBase}${API_CONFIG.ENDPOINTS.RULES_NLP_TO_RULE}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          description: desc,
          available_fields: sourceFields || [],
          context_hint: 'PLM/ETL migration wizard rule configuration',
        }),
      });
      if (!res.ok) throw new Error(`Server error ${res.status}`);
      const data = await res.json();
      setLastResult(data);
      if (data.rules && data.rules.length > 0) {
        onAddRules(data.rules);
        setText('');
      }
    } catch (err) {
      setError(err?.message || 'Failed to generate rule');
    } finally {
      setLoading(false);
    }
  }, [text, sourceFields, onAddRules]);

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
      handleGenerate();
    }
  };

  return (
    <div className="re-nlp-panel">
      <div className="re-nlp-header">
        <span className="re-nlp-title">
          <i className="fas fa-robot" /> Describe a rule in plain English
        </span>
        <span className="re-nlp-badge re-nlp-badge--ai">AI</span>
      </div>

      <div className="re-nlp-examples">
        {NLP_EXAMPLES.map(ex => (
          <button
            key={ex}
            className="re-nlp-example-chip"
            onClick={() => setText(ex)}
            tabIndex={-1}
          >
            {ex}
          </button>
        ))}
      </div>

      <div className="re-nlp-input-row">
        <textarea
          className="re-nlp-textarea"
          rows={2}
          placeholder={'e.g. "part_number must not be empty and must be unique"\nPress Ctrl+Enter or click Generate'}
          value={text}
          onChange={e => setText(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={loading}
        />
        <button
          className={`re-nlp-generate-btn${loading ? ' re-nlp-generate-btn--loading' : ''}`}
          onClick={handleGenerate}
          disabled={loading || !text.trim()}
          title="Generate rule(s) from description (Ctrl+Enter)"
        >
          {loading
            ? <><i className="fas fa-spinner fa-spin" /> Generating…</>
            : <><i className="fas fa-wand-magic-sparkles" /> Generate</>}
        </button>
      </div>

      {error && (
        <div className="re-nlp-error">
          <i className="fas fa-exclamation-triangle" /> {error}
        </div>
      )}

      {lastResult && (
        <div className={`re-nlp-result ${lastResult.ai_powered ? 're-nlp-result--ai' : 're-nlp-result--fallback'}`}>
          <i className={`fas ${lastResult.ai_powered ? 'fa-robot' : 'fa-puzzle-piece'}`} />
          {' '}{lastResult.interpretation}
          {lastResult.rules?.length > 0 && (
            <span className="re-nlp-rule-count">
              {lastResult.rules.length} rule{lastResult.rules.length !== 1 ? 's' : ''} added ✓
            </span>
          )}
        </div>
      )}
    </div>
  );
};

/**
 * WizardRuleEngine — unified Rule Engine table showing pre-transform, quality,
 * and post-transform rules as categories in one place.
 *
 * Props:
 *   rules        – array of rule objects from wizardData.rules
 *   activePhase  – kept for API compat (not used for display filtering)
 *   sourceFields – string[] of source field names
 *   fieldMappings – array of field mapping objects
 *   onPhaseChange, onAddRule, onRemoveRule, onUpdateRule – callbacks
 *   onAddRules   – callback(rules[]) to bulk-append rules (from NLP generation)
 */
const WizardRuleEngine = ({
  rules,
  sourceFields,
  fieldMappings = [],
  onAddRule,
  onRemoveRule,
  onUpdateRule,
  onAddRules,
}) => {
  // Build source-field → target-field lookup for inline mapping context
  const mappedTargetBySource = useMemo(() => {
    const map = {};
    for (const m of fieldMappings) {
      const src = m.source_field || m.sourceField;
      const tgt = m.target_field || m.targetField;
      if (src && tgt) map[src] = tgt;
    }
    return map;
  }, [fieldMappings]);

  // Bulk-add callback for NLP panel (falls back to onAddRule if not provided)
  const handleAddRules = useCallback((newRules) => {
    if (typeof onAddRules === 'function') {
      onAddRules(newRules);
    } else if (typeof onAddRule === 'function') {
      // Fallback: add each rule individually using the single-add callback
      newRules.forEach(r => onAddRule(r.phase || 'quality', r));
    }
  }, [onAddRules, onAddRule]);
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

      {/* ── NLP Rule Input ─────────────────────────────────────────────── */}
      <NlpRuleInput
        sourceFields={sourceFields}
        fieldMappings={fieldMappings}
        onAddRules={handleAddRules}
      />

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
              <span>Field <span className="re-mapped-hint">(→ Target)</span></span>
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
                  <div className="re-field-col">
                    <select
                      className="re-select re-field"
                      value={rule.field}
                      onChange={e => onUpdateRule(rule.id, { field: e.target.value })}
                    >
                      <option value="*">All fields</option>
                      {sourceFields.map(f => <option key={f} value={f}>{f}</option>)}
                    </select>
                    {rule.field && rule.field !== '*' && mappedTargetBySource[rule.field] && (
                      <span className="re-mapped-to" title={`Maps to: ${mappedTargetBySource[rule.field]}`}>
                        → {mappedTargetBySource[rule.field]}
                      </span>
                    )}
                  </div>
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
