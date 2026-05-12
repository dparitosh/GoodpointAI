/**
 * DataHealthPanel — AI-generated Data Health Report viewer (Step 2 / Discovery)
 *
 * Displays the output of the DataDiscoveryAgent `data_health_report` task:
 *  • Readiness Score + Trust Score gauges
 *  • Semantic Header Map  (original column → AI business name)
 *  • Distribution Anomalies  (mixed formats, outliers)
 *  • Autonomously Inferred Rules  (with "Apply" to wizard rule engine)
 *  • Per-column Trust Breakdown  (sortable table)
 */
import React, { useState, useMemo, useCallback } from 'react';
import './DataHealthPanel.css';

// ── Helpers ─────────────────────────────────────────────────────────────────

/** Return 'green' | 'yellow' | 'red' based on 0-100 score */
function scoreColor(score) {
  if (score == null) return 'gray';
  if (score >= 80) return 'green';
  if (score >= 60) return 'yellow';
  return 'red';
}

/** Confidence → badge style */
function confidenceClass(confidence) {
  if (confidence == null) return 'low';
  const v = typeof confidence === 'string' ? parseFloat(confidence) : confidence;
  if (v >= 0.8) return 'high';
  if (v >= 0.5) return 'medium';
  return 'low';
}

/** Format 0-1 float or 0-100 int as a percentage string */
function fmtPct(v) {
  if (v == null) return '—';
  const n = typeof v === 'string' ? parseFloat(v) : v;
  const pct = n <= 1 ? Math.round(n * 100) : Math.round(n);
  return `${pct}%`;
}

// ── Sub-components ───────────────────────────────────────────────────────────

/** Circular-ish score gauge using a conic-gradient ring */
function ScoreGauge({ label, score, subtitle }) {
  const color  = scoreColor(score);
  const pct    = score != null ? Math.min(100, Math.max(0, score)) : 0;

  return (
    <div className={`dh-gauge dh-gauge-${color}`}>
      <div
        className="dh-gauge-ring"
        style={{ background: `conic-gradient(var(--dh-gauge-fill) ${pct * 3.6}deg, var(--dh-gauge-track) 0deg)` }}
      >
        <div className="dh-gauge-inner">
          <span className="dh-gauge-score">{score != null ? score : '—'}</span>
        </div>
      </div>
      <div className="dh-gauge-label">{label}</div>
      {subtitle && <div className="dh-gauge-subtitle">{subtitle}</div>}
    </div>
  );
}

/** Collapsible panel section */
function Section({ title, icon, badge, defaultOpen = true, children }) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="dh-section">
      <button
        className="dh-section-header"
        onClick={() => setOpen(o => !o)}
        aria-expanded={open}
      >
        <span className="dh-section-title">
          {icon && <i className={`fas fa-${icon}`} />}
          {title}
          {badge != null && <span className="dh-section-badge">{badge}</span>}
        </span>
        <i className={`fas fa-chevron-${open ? 'up' : 'down'} dh-chevron`} />
      </button>
      {open && <div className="dh-section-body">{children}</div>}
    </div>
  );
}

// ── Main component ───────────────────────────────────────────────────────────

/**
 * @param {object}   healthReport     Full response from `_generate_data_health_report()`
 * @param {function} onApplyRule      Callback: (ruleObj) => void — called when user clicks "Apply" on an inferred rule
 * @param {boolean}  loading          Show skeleton/spinner while report is being fetched
 */
export default function DataHealthPanel({ healthReport, onApplyRule, loading = false }) {
  const [trustSort, setTrustSort] = useState('score_asc');   // 'score_asc' | 'score_desc' | 'name'
  const [headerSearch, setHeaderSearch] = useState('');

  // ── Destructure report fields ────────────────────────────────────────────
  const {
    readiness_score       = null,
    trust_analysis        = {},
    semantic_header_map   = {},
    distribution_anomalies = [],
    inferred_rules        = [],

    signals               = [],
    files_scanned         = 0,
    timestamp,
  } = healthReport || {};

  const trustScore          = trust_analysis?.overall_trust_score ?? null;
  const trustLevel          = trust_analysis?.trust_level ?? null;
  const columnTrustScores   = trust_analysis?.column_trust_scores ?? {};
  const trustIssueColumns   = trust_analysis?.columns_with_issues ?? [];

  // ── Semantic header map ──────────────────────────────────────────────────
  const headerEntries = useMemo(() => {
    const entries = Object.entries(semantic_header_map);
    if (!headerSearch.trim()) return entries;
    const q = headerSearch.toLowerCase();
    return entries.filter(([orig, mapped]) =>
      orig.toLowerCase().includes(q) || String(mapped).toLowerCase().includes(q)
    );
  }, [semantic_header_map, headerSearch]);

  // ── Trust breakdown (sorted) ─────────────────────────────────────────────
  const sortedTrustCols = useMemo(() => {
    const entries = Object.entries(columnTrustScores);
    if (trustSort === 'name') {
      return entries.sort(([a], [b]) => a.localeCompare(b));
    }
    return entries.sort(([, a], [, b]) =>
      trustSort === 'score_asc'
        ? (a.trust_score ?? 100) - (b.trust_score ?? 100)
        : (b.trust_score ?? 100) - (a.trust_score ?? 100)
    );
  }, [columnTrustScores, trustSort]);

  // ── Apply inferred rule to wizard ────────────────────────────────────────
  const handleApplyRule = useCallback((rule) => {
    if (!onApplyRule) return;
    onApplyRule({
      id:          `ai-inferred-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
      name:        rule.rule_name,
      description: rule.rule_description,
      column:      rule.column,
      type:        rule.rule_type,
      pattern:     rule.inferred_pattern,
      confidence:  rule.confidence,
      source:      'ai_inferred',
      phase:       'pre',
    });
  }, [onApplyRule]);

  // ── Loading state ────────────────────────────────────────────────────────
  if (loading) {
    return (
      <div className="dh-panel dh-loading" aria-busy="true">
        <i className="fas fa-spinner fa-spin" />
        <span>Generating AI Data Health Report…</span>
      </div>
    );
  }

  if (!healthReport) return null;

  // ── RENDER ───────────────────────────────────────────────────────────────
  return (
    <div className="dh-panel">

      {/* ── Header bar ────────────────────────────────────────────────── */}
      <div className="dh-header-bar">
        <span className="dh-header-icon"><i className="fas fa-heartbeat" /></span>
        <div>
          <h3 className="dh-header-title">AI Data Health Report</h3>
          {timestamp && (
            <span className="dh-header-meta">
              {files_scanned > 0 && `${files_scanned} files · `}
              Generated {new Date(timestamp).toLocaleString()}
            </span>
          )}
        </div>
        <span className="dh-ai-badge"><i className="fas fa-robot" /> AI-powered</span>
      </div>

      {/* ── Score row ─────────────────────────────────────────────────── */}
      <div className="dh-score-row">
        <ScoreGauge
          label="Data Readiness"
          score={readiness_score}
          subtitle={
            readiness_score >= 80 ? 'Ready for migration'
            : readiness_score >= 60 ? 'Minor remediation needed'
            : 'Significant issues found'
          }
        />
        <ScoreGauge
          label="Data Trust"
          score={trustScore}
          subtitle={trustLevel ? `Trust level: ${trustLevel}` : null}
        />
        {signals?.length > 0 && (
          <div className="dh-signals-summary">
            <div className="dh-signals-count">{signals.length}</div>
            <div className="dh-signals-label">Quality Signals</div>
            <ul className="dh-signals-list">
              {signals.slice(0, 4).map((s, i) => (
                <li key={i} className={`dh-signal dh-signal-${s.severity || 'warning'}`}>
                  <i className="fas fa-circle" />
                  <span>{s.column}: {s.type?.replace(/_/g, ' ')}</span>
                </li>
              ))}
              {signals.length > 4 && (
                <li className="dh-signal dh-signal-more">+{signals.length - 4} more</li>
              )}
            </ul>
          </div>
        )}
      </div>

      {/* ── Semantic header map ────────────────────────────────────────── */}
      {Object.keys(semantic_header_map).length > 0 && (
        <Section title="Semantic Header Map" icon="language" badge={Object.keys(semantic_header_map).length}>
          <div className="dh-search-row">
            <i className="fas fa-search dh-search-icon" />
            <input
              className="dh-search-input"
              type="text"
              placeholder="Filter columns…"
              value={headerSearch}
              onChange={e => setHeaderSearch(e.target.value)}
              aria-label="Filter semantic header map"
            />
          </div>
          <table className="dh-table" aria-label="Semantic header map">
            <thead>
              <tr>
                <th>Original Column</th>
                <th>AI Business Name</th>
              </tr>
            </thead>
            <tbody>
              {headerEntries.map(([orig, mapped]) => (
                <tr key={orig}>
                  <td className="dh-col-original"><code>{orig}</code></td>
                  <td className="dh-col-mapped">
                    {orig !== mapped
                      ? <><i className="fas fa-magic dh-magic-icon" />{mapped}</>
                      : <span className="dh-unchanged">{mapped}</span>
                    }
                  </td>
                </tr>
              ))}
              {headerEntries.length === 0 && (
                <tr><td colSpan={2} className="dh-empty">No columns match filter.</td></tr>
              )}
            </tbody>
          </table>
        </Section>
      )}

      {/* ── Distribution anomalies ─────────────────────────────────────── */}
      {distribution_anomalies?.length > 0 && (
        <Section title="Distribution Anomalies" icon="exclamation-triangle" badge={distribution_anomalies.length} defaultOpen>
          <div className="dh-anomaly-list">
            {distribution_anomalies.map((anom, i) => (
              <div
                key={i}
                className={`dh-anomaly-card dh-anomaly-${anom.severity || 'warning'}`}
              >
                <div className="dh-anomaly-header">
                  <i className={`fas fa-${anom.severity === 'high' ? 'exclamation-circle' : 'exclamation-triangle'}`} />
                  <strong>{anom.column}</strong>
                  <span className={`dh-severity-badge dh-severity-${anom.severity || 'warning'}`}>
                    {anom.severity || 'warning'}
                  </span>
                </div>
                <p className="dh-anomaly-desc">{anom.description}</p>
                {anom.recommendation && (
                  <div className="dh-anomaly-rec">
                    <i className="fas fa-lightbulb" /> {anom.recommendation}
                  </div>
                )}
                {anom.dominant_format && (
                  <div className="dh-anomaly-formats">
                    Dominant: <code>{anom.dominant_format}</code>
                    {anom.dominant_pct != null && ` (${fmtPct(anom.dominant_pct)})`}
                    {anom.minority_formats?.length > 0 && (
                      <> · Minority: {anom.minority_formats.map(f => <code key={f}>{f}</code>)}</>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        </Section>
      )}

      {/* ── Inferred rules ─────────────────────────────────────────────── */}
      {inferred_rules?.length > 0 && (
        <Section title="Autonomously Inferred Rules" icon="robot" badge={inferred_rules.length}>
          <p className="dh-section-desc">
            Rules discovered by AI analysis of data patterns. Review and apply to the Rule Engine.
          </p>
          <div className="dh-rule-list">
            {inferred_rules.map((rule, i) => (
              <div key={i} className="dh-rule-card">
                <div className="dh-rule-header">
                  <span className="dh-rule-name">{rule.rule_name}</span>
                  <span className={`dh-conf-badge dh-conf-${confidenceClass(rule.confidence)}`}>
                    {fmtPct(rule.confidence)} confidence
                  </span>
                  {onApplyRule && (
                    <button
                      className="dh-btn-apply"
                      onClick={() => handleApplyRule(rule)}
                      title="Add this rule to the Rule Engine"
                    >
                      <i className="fas fa-plus" /> Apply
                    </button>
                  )}
                </div>
                <p className="dh-rule-desc">{rule.rule_description}</p>
                <div className="dh-rule-meta">
                  {rule.column && <span><i className="fas fa-columns" /> {rule.column}</span>}
                  {rule.rule_type && <span><i className="fas fa-tag" /> {rule.rule_type?.replace(/_/g, ' ')}</span>}
                  {rule.inferred_pattern && <span><i className="fas fa-code" /> <code>{rule.inferred_pattern}</code></span>}
                </div>
                {rule.evidence && (
                  <div className="dh-rule-evidence">
                    <i className="fas fa-clipboard-list" /> {rule.evidence}
                  </div>
                )}
              </div>
            ))}
          </div>
        </Section>
      )}

      {/* ── Column trust breakdown ─────────────────────────────────────── */}
      {sortedTrustCols.length > 0 && (
        <Section title="Column Trust Breakdown" icon="shield-alt" badge={sortedTrustCols.length} defaultOpen={false}>
          {trustIssueColumns.length > 0 && (
            <div className="dh-trust-alert">
              <i className="fas fa-info-circle" />
              {trustIssueColumns.length} column{trustIssueColumns.length > 1 ? 's' : ''} with trust concerns:
              {' '}{trustIssueColumns.slice(0, 5).join(', ')}{trustIssueColumns.length > 5 ? '…' : ''}
            </div>
          )}
          <div className="dh-trust-controls">
            <label className="dh-sort-label">Sort by:</label>
            {[
              ['score_asc',  'Score ↑'],
              ['score_desc', 'Score ↓'],
              ['name',       'Name'],
            ].map(([val, lbl]) => (
              <button
                key={val}
                className={`dh-sort-btn ${trustSort === val ? 'active' : ''}`}
                onClick={() => setTrustSort(val)}
              >
                {lbl}
              </button>
            ))}
          </div>
          <table className="dh-table dh-trust-table" aria-label="Column trust scores">
            <thead>
              <tr>
                <th>Column</th>
                <th>Trust Score</th>
                <th>Issues</th>
              </tr>
            </thead>
            <tbody>
              {sortedTrustCols.map(([col, info]) => {
                const ts = info?.trust_score ?? 100;
                const color = scoreColor(ts);
                return (
                  <tr key={col} className={ts < 60 ? 'dh-trust-row-warn' : ''}>
                    <td><code>{col}</code></td>
                    <td>
                      <div className="dh-trust-bar-wrap">
                        <div
                          className={`dh-trust-bar dh-trust-bar-${color}`}
                          style={{ width: `${ts}%` }}
                          role="progressbar"
                          aria-valuenow={ts}
                          aria-valuemin={0}
                          aria-valuemax={100}
                          aria-label={`Trust score ${ts}%`}
                        />
                        <span className="dh-trust-pct">{ts}</span>
                      </div>
                    </td>
                    <td className="dh-trust-flags">
                      {info?.flags?.length > 0
                        ? info.flags.map(f => (
                          <span key={f} className="dh-flag">{f.replace(/_/g, ' ')}</span>
                        ))
                        : <span className="dh-flag-ok">OK</span>
                      }
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </Section>
      )}

    </div>
  );
}
