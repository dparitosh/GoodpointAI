/**
 * Data Discovery Page
 * ====================
 * Discover, profile and catalog folder-type data sources via the MCP
 * DataDiscoveryAgent.
 *
 * API calls (all via MCP orchestration):
 *   POST /api/agentic/discovery   → discover + profile a folder source
 *   GET  /api/data-sources        → list registered datasources
 *   POST /api/agentic/quality-scan → run DQ scan on a discovered source
 */

import React, { useState, useCallback, useEffect, useMemo, useRef } from 'react';
import { useSearchParams, Link } from 'react-router-dom';
import { API_CONFIG } from '../../config/api-config.js';
import { e2etraceFetchWithRetry } from '../../api/e2etrace-api';
import writeXlsxFile from 'write-excel-file';
import { AgentPipelineStrip } from '../../components/agent-pipeline-strip/AgentPipelineStrip.jsx';
import './DataDiscoveryPage.css';

const API_BASE = import.meta.env.VITE_API_BASE_URL || '';

// ─── Helpers ────────────────────────────────────────────────────────────────

const FILE_TYPE_COLORS = {
  csv:   '#22c55e',
  json:  '#3b82f6',
  xml:   '#f59e0b',
  xlsx:  '#10b981',
  parquet: '#8b5cf6',
  text:  '#6b7280',
  other: '#94a3b8',
};

// ─── Demo / seed data (shown before first live run) ─────────────────────────

const _DEMO_FILES = [
  {
    name: 'parts_master.csv',
    path: '/data/plm/parts_master.csv',
    file_type: 'csv',
    size_bytes: 245760,
    row_count: 3412,
    column_count: 8,
    null_rate: 2.1,
    profile: {
      part_number: { type: 'string', null_rate: 0,   sample: ['PN-001', 'PN-002', 'PN-003'] },
      name:        { type: 'string', null_rate: 1.2, sample: ['Bolt M8', 'Nut M8', 'Washer'] },
      category:    { type: 'string', null_rate: 4.5, sample: ['Fastener', 'Fastener', 'Hardware'] },
      material:    { type: 'string', null_rate: 8.0, sample: ['Steel', 'Steel', 'Aluminium'] },
      weight_kg:   { type: 'float',  null_rate: 2.1, sample: [0.012, 0.008, 0.003] },
      unit_cost:   { type: 'float',  null_rate: 0,   sample: [0.45, 0.30, 0.12] },
      supplier_id: { type: 'string', null_rate: 3.4, sample: ['SUP-001', 'SUP-001', 'SUP-003'] },
      status:      { type: 'string', null_rate: 0,   sample: ['active', 'active', 'obsolete'] },
    },
  },
  {
    name: 'bom_structure.json',
    path: '/data/plm/bom_structure.json',
    file_type: 'json',
    size_bytes: 89344,
    row_count: 1205,
    column_count: 6,
    null_rate: 0.8,
    profile: {},
  },
  {
    name: 'supplier_data.xlsx',
    path: '/data/suppliers/supplier_data.xlsx',
    file_type: 'xlsx',
    size_bytes: 512000,
    row_count: 876,
    column_count: 12,
    null_rate: 8.3,
    profile: {},
  },
  {
    name: 'transactions.parquet',
    path: '/data/warehouse/transactions.parquet',
    file_type: 'parquet',
    size_bytes: 1048576,
    row_count: 45231,
    column_count: 15,
    null_rate: 0.2,
    profile: {},
  },
  {
    name: 'revisions.csv',
    path: '/data/plm/revisions.csv',
    file_type: 'csv',
    size_bytes: 32768,
    row_count: 412,
    column_count: 5,
    null_rate: 12.4,
    profile: {},
  },
  {
    name: 'product_config.json',
    path: '/data/plm/product_config.json',
    file_type: 'json',
    size_bytes: 4096,
    row_count: null,
    column_count: null,
    null_rate: null,
    profile: {},
  },
];

const DEMO_RESULT = {
  report_id: 'demo-001',
  result: {
    files: _DEMO_FILES,
    by_type: { csv: 2, json: 2, xlsx: 1, parquet: 1 },
    catalog: { avg_row_count: 8427 },
    summary: { total_files: 6, total_size_bytes: 1932544 },
  },
};

const DEMO_PAST_RUNS = [
  {
    report_id: 'demo-pr-001',
    label: 'PLM data folder — demo',
    source_id: null,
    folder_path: '/data/plm',
    total_files: 6,
    total_size_bytes: 1932544,
    created_at: new Date(Date.now() - 3600 * 2 * 1000).toISOString(),
    result: DEMO_RESULT,
  },
  {
    report_id: 'demo-pr-002',
    label: 'Supplier exports — demo',
    source_id: null,
    folder_path: '/data/suppliers',
    total_files: 3,
    total_size_bytes: 620544,
    created_at: new Date(Date.now() - 3600 * 26 * 1000).toISOString(),
    result: {
      report_id: 'demo-pr-002',
      result: {
        files: [
          {
            name: 'supplier_data.xlsx', path: '/data/suppliers/supplier_data.xlsx', file_type: 'xlsx',
            size_bytes: 512000, row_count: 876, column_count: 12, null_rate: 8.3,
            profile: {
              supplier_id:    { type: 'string',  null_rate: 0,    sample: ['SUP-001', 'SUP-002', 'SUP-003'] },
              supplier_name:  { type: 'string',  null_rate: 1.2,  sample: ['Acme Corp', 'Globex Ltd', 'Initech'] },
              country:        { type: 'string',  null_rate: 3.4,  sample: ['USA', 'Germany', 'India'] },
              category:       { type: 'string',  null_rate: 5.7,  sample: ['Electronics', 'Fasteners', 'Plastics'] },
              rating:         { type: 'float',   null_rate: 12.1, sample: [4.2, 3.8, 4.7] },
              lead_time_days: { type: 'integer', null_rate: 8.0,  sample: [14, 21, 7] },
              unit_cost_usd:  { type: 'float',   null_rate: 6.3,  sample: [12.50, 0.45, 3.20] },
              currency:       { type: 'string',  null_rate: 2.1,  sample: ['USD', 'EUR', 'INR'] },
              contact_email:  { type: 'string',  null_rate: 15.2, sample: ['ops@acme.com', null, 'supply@initech.com'] },
              phone:          { type: 'string',  null_rate: 22.4, sample: ['+1-555-0100', null, '+49-30-12345'] },
              status:         { type: 'string',  null_rate: 0,    sample: ['active', 'active', 'inactive'] },
              onboarded_date: { type: 'date',    null_rate: 4.5,  sample: ['2021-03-15', '2019-07-01', '2023-01-10'] },
            },
          },
          {
            name: 'contacts.csv', path: '/data/suppliers/contacts.csv', file_type: 'csv',
            size_bytes: 65536, row_count: 244, column_count: 7, null_rate: 5.1,
            profile: {
              contact_id:   { type: 'string',  null_rate: 0,    sample: ['C-001', 'C-002', 'C-003'] },
              first_name:   { type: 'string',  null_rate: 0,    sample: ['Alice', 'Bob', 'Carol'] },
              last_name:    { type: 'string',  null_rate: 0.4,  sample: ['Smith', 'Jones', 'Williams'] },
              email:        { type: 'string',  null_rate: 3.3,  sample: ['alice@acme.com', 'bob@globex.com', null] },
              phone:        { type: 'string',  null_rate: 18.4, sample: ['+1-555-0101', null, '+44-20-7946'] },
              company:      { type: 'string',  null_rate: 1.6,  sample: ['Acme Corp', 'Globex Ltd', 'Initech'] },
              country:      { type: 'string',  null_rate: 2.5,  sample: ['USA', 'Germany', 'UK'] },
            },
          },
          {
            name: 'agreements.json', path: '/data/suppliers/agreements.json', file_type: 'json',
            size_bytes: 43008, row_count: 38, column_count: 9, null_rate: 0,
            profile: {
              agreement_id:   { type: 'string',  null_rate: 0,   sample: ['AGR-2021-001', 'AGR-2022-014', 'AGR-2023-007'] },
              supplier_id:    { type: 'string',  null_rate: 0,   sample: ['SUP-001', 'SUP-002', 'SUP-001'] },
              type:           { type: 'string',  null_rate: 0,   sample: ['NDA', 'MSA', 'SLA'] },
              start_date:     { type: 'date',    null_rate: 0,   sample: ['2021-01-01', '2022-06-15', '2023-03-01'] },
              end_date:       { type: 'date',    null_rate: 2.6, sample: ['2024-12-31', null, '2025-02-28'] },
              value_usd:      { type: 'float',   null_rate: 0,   sample: [250000, 85000, 1200000] },
              status:         { type: 'string',  null_rate: 0,   sample: ['active', 'expired', 'active'] },
              signed_by:      { type: 'string',  null_rate: 5.3, sample: ['J. Doe', 'M. Lee', null] },
              renewal_notice: { type: 'integer', null_rate: 7.9, sample: [30, 60, null] },
            },
          },
        ],
        by_type: { xlsx: 1, csv: 1, json: 1 },
        catalog: { avg_row_count: 386 },
        summary: { total_files: 3, total_size_bytes: 620544 },
      },
    },
  },
];

function typeColor(ft) {
  return FILE_TYPE_COLORS[String(ft).toLowerCase()] || FILE_TYPE_COLORS.other;
}

function fmtAge(iso) {
  if (!iso) return '';
  const diff = (Date.now() - new Date(iso).getTime()) / 1000;
  if (diff < 60)    return 'Just now';
  if (diff < 3600)  return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}

function fmtSize(bytes) {
  if (bytes == null) return '—';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function fmtNum(n) {
  if (n == null) return '—';
  return Number(n).toLocaleString();
}

function scoreColor(s) {
  if (s >= 90) return '#22c55e';
  if (s >= 70) return '#f59e0b';
  return '#ef4444';
}

// ─── Sub-components ─────────────────────────────────────────────────────────

function KpiCard({ label, value, sub, color, icon }) {
  return (
    <div className="dd-kpi-card">
      <div className="dd-kpi-icon" style={{ color }}>{icon}</div>
      <div className="dd-kpi-body">
        <div className="dd-kpi-value" style={{ color }}>{value}</div>
        <div className="dd-kpi-label">{label}</div>
        {sub && <div className="dd-kpi-sub">{sub}</div>}
      </div>
    </div>
  );
}

function FileTypeBar({ byType }) {
  const entries = Object.entries(byType || {}).sort((a, b) => b[1] - a[1]);
  const total = entries.reduce((s, [, n]) => s + n, 0);
  if (!total) return <div className="dd-empty">No files</div>;
  return (
    <div className="dd-type-bar-container">
      <div className="dd-type-bar-track">
        {entries.map(([ft, n]) => (
          <div
            key={ft}
            className="dd-type-bar-segment"
            style={{ width: `${(n / total) * 100}%`, background: typeColor(ft) }}
            title={`${ft}: ${n}`}
          />
        ))}
      </div>
      <div className="dd-type-bar-legend">
        {entries.map(([ft, n]) => (
          <span key={ft} className="dd-legend-item">
            <span className="dd-legend-dot" style={{ background: typeColor(ft) }} />
            {ft} ({n})
          </span>
        ))}
      </div>
    </div>
  );
}

// Derive DQ rule results from profile column stats
function deriveDqRules(profile, rowCount) {
  const rules = [];
  Object.entries(profile || {}).forEach(([col, stats]) => {
    const nr = stats.null_rate ?? 0;
    const completeness = 100 - nr;
    // Non-null check
    const nnStatus = nr === 0 ? 'pass' : nr < 5 ? 'warn' : 'fail';
    rules.push({
      rule: 'not_null',
      column: col,
      status: nnStatus,
      detail: nr === 0 ? 'No nulls detected' : `${nr.toFixed(1)}% null values`,
      affected: rowCount != null ? Math.round((nr / 100) * rowCount) : null,
    });
    // Completeness check
    const compStatus = completeness >= 95 ? 'pass' : completeness >= 80 ? 'warn' : 'fail';
    rules.push({
      rule: 'completeness',
      column: col,
      status: compStatus,
      detail: `${completeness.toFixed(1)}% complete`,
      affected: rowCount != null ? Math.round((nr / 100) * rowCount) : null,
    });
    // Valid type check (pass if type is known)
    if (stats.type) {
      rules.push({
        rule: 'valid_type',
        column: col,
        status: 'pass',
        detail: `Detected as ${stats.type}`,
        affected: 0,
      });
    }
  });
  return rules;
}

const DQ_STATUS_COLORS = { pass: '#22c55e', warn: '#f59e0b', fail: '#ef4444' };
const DQ_STATUS_ICONS  = { pass: 'fas fa-check-circle', warn: 'fas fa-exclamation-circle', fail: 'fas fa-times-circle' };

// Simplified table row — Review button selects the file for the profile panel below
function ProfileRow({ file, isSelected, onSelect }) {
  const hasProfile = file.profile && Object.keys(file.profile).length > 0;
  const dqRules = hasProfile ? deriveDqRules(file.profile, file.row_count) : [];
  const failCount = dqRules.filter((r) => r.status === 'fail').length;

  return (
    <tr className={isSelected ? 'dd-row-selected' : ''}>
      <td>
        <span className="dd-file-icon">
          <i className={`fas fa-file${file.file_type === 'csv' ? '-csv' : file.file_type === 'pdf' ? '-pdf' : file.file_type === 'excel' || file.file_type === 'xlsx' ? '-excel' : '-alt'}`} />
        </span>
        <span className="dd-file-name" title={file.path}>{file.name || file.path}</span>
      </td>
      <td>
        <span className="dd-type-badge" style={{ background: `${typeColor(file.file_type)}22`, color: typeColor(file.file_type) }}>
          {file.file_type || '—'}
        </span>
      </td>
      <td className="dd-num">{fmtSize(file.size_bytes)}</td>
      <td className="dd-num">{fmtNum(file.row_count)}</td>
      <td className="dd-num">{fmtNum(file.column_count)}</td>
      <td className="dd-num">
        {file.null_rate != null
          ? <span style={{ color: file.null_rate > 20 ? '#ef4444' : '#6b7280' }}>{file.null_rate.toFixed(1)}%</span>
          : '—'}
      </td>
      <td>
        {hasProfile
          ? (
            <button
              className={`dd-expand-btn${isSelected ? ' dd-expand-btn--active' : ''}`}
              onClick={() => onSelect(isSelected ? null : file)}
              title={isSelected ? 'Deselect file' : 'View profile, DQ rules and null report'}
            >
              {isSelected ? <><i className="fas fa-check" /> Selected</> : 'Review'}
              {!isSelected && failCount > 0 && (
                <span className="dd-profile-fail-badge">{failCount} fail</span>
              )}
            </button>
          )
          : <span className="dd-no-profile">no profile</span>}
      </td>
    </tr>
  );
}

// Full profile review panel — rendered below the file table
function FileProfilePanel({ file, allFiles, onSelectFile, onRunQualityScan }) {
  const [activeTab, setActiveTab] = useState('profile');

  // Reset to profile tab when file changes
  useEffect(() => { setActiveTab('profile'); }, [file?.path]);

  const hasProfile = file && file.profile && Object.keys(file.profile).length > 0;
  const dqRules    = hasProfile ? deriveDqRules(file.profile, file.row_count) : [];
  const nullColumns = Object.entries((file?.profile) || {})
    .filter(([, s]) => s.null_rate != null && s.null_rate > 0)
    .sort(([, a], [, b]) => b.null_rate - a.null_rate);
  const dqSummary = {
    pass: dqRules.filter((r) => r.status === 'pass').length,
    warn: dqRules.filter((r) => r.status === 'warn').length,
    fail: dqRules.filter((r) => r.status === 'fail').length,
  };

  return (
    <div className="dd-card dd-profile-review-card">
      {/* File selector header */}
      <div className="dd-profile-review-header">
        <span className="dd-profile-review-title"><i className="fas fa-chart-line" /> File Profile Review</span>
        <div className="dd-profile-file-selector">
          <label className="dd-label" style={{ marginBottom: 0, whiteSpace: 'nowrap' }}>Select file:</label>
          <select
            className="dd-select"
            value={file?.path || ''}
            onChange={(e) => {
              const selected = allFiles.find((f) => f.path === e.target.value);
              onSelectFile(selected || null);
            }}
          >
            <option value="">— choose a file to review —</option>
            {allFiles.map((f) => {
              const fp = f.profile && Object.keys(f.profile).length > 0;
              const rules = fp ? deriveDqRules(f.profile, f.row_count) : [];
              const fails = rules.filter((r) => r.status === 'fail').length;
              return (
                <option key={f.path} value={f.path}>
                  {f.name || f.path}
                  {f.null_rate != null ? `  •  ${f.null_rate.toFixed(1)}% null` : ''}
                  {fails > 0 ? `  •  ⚠ ${fails} DQ fail` : ''}
                  {!fp ? '  (no profile)' : ''}
                </option>
              );
            })}
          </select>
        </div>
      </div>

      {!file && (
        <div className="dd-empty-state" style={{ padding: '2rem 1rem' }}>
          <i className="fas fa-mouse-pointer dd-empty-icon" style={{ fontSize: '2rem' }} />
          <div className="dd-empty-title">Click <strong>Review</strong> on any file above, or select from the dropdown</div>
          <div className="dd-empty-sub">Column stats, DQ rules and null values will appear here</div>
        </div>
      )}

      {file && !hasProfile && (
        <div className="dd-empty-state" style={{ padding: '2rem 1rem' }}>
          <i className="fas fa-info-circle dd-empty-icon" style={{ fontSize: '2rem', color: '#94a3b8' }} />
          <div className="dd-empty-title">No profile data for <em>{file.name || file.path}</em></div>
          <div className="dd-empty-sub">Run Discovery with profiling enabled to generate column stats.</div>
        </div>
      )}

      {file && hasProfile && (
        <div className="dd-profile-panel">
          {/* File meta bar */}
          <div className="dd-profile-meta-bar">
            <span className="dd-type-badge" style={{ background: `${typeColor(file.file_type)}22`, color: typeColor(file.file_type) }}>{file.file_type}</span>
            {file.size_bytes != null && <span className="dd-meta-pill"><i className="fas fa-hdd" /> {fmtSize(file.size_bytes)}</span>}
            {file.row_count != null && <span className="dd-meta-pill"><i className="fas fa-table" /> {fmtNum(file.row_count)} rows</span>}
            {file.column_count != null && <span className="dd-meta-pill"><i className="fas fa-columns" /> {file.column_count} cols</span>}
            {file.null_rate != null && (
              <span className="dd-meta-pill" style={{ color: file.null_rate > 10 ? '#dc2626' : '#475569' }}>
                <i className="fas fa-exclamation-triangle" /> {file.null_rate.toFixed(1)}% null overall
              </span>
            )}
          </div>

          {/* Tab bar */}
          <div className="dd-profile-tabs">
            <button
              className={`dd-profile-tab${activeTab === 'profile' ? ' dd-profile-tab--active' : ''}`}
              onClick={() => setActiveTab('profile')}
            >
              <i className="fas fa-columns" /> Column Profile
            </button>
            <button
              className={`dd-profile-tab${activeTab === 'dq' ? ' dd-profile-tab--active' : ''}`}
              onClick={() => setActiveTab('dq')}
            >
              <i className="fas fa-shield-alt" /> DQ Rules
              {dqSummary.fail > 0 && <span className="dd-tab-fail-badge">{dqSummary.fail}</span>}
              {dqSummary.fail === 0 && dqSummary.warn > 0 && <span className="dd-tab-warn-badge">{dqSummary.warn}</span>}
            </button>
            <button
              className={`dd-profile-tab${activeTab === 'nulls' ? ' dd-profile-tab--active' : ''}`}
              onClick={() => setActiveTab('nulls')}
            >
              <i className="fas fa-exclamation-triangle" /> Null Report
              {nullColumns.length > 0 && <span className="dd-tab-warn-badge">{nullColumns.length}</span>}
            </button>
          </div>

          {/* Column Profile tab */}
          {activeTab === 'profile' && (
            <div className="dd-profile-cols">
              {Object.entries(file.profile).map(([col, stats]) => (
                <div key={col} className="dd-col-stat">
                  <div className="dd-col-name">{col}</div>
                  <div className="dd-col-meta">
                    {stats.type && <span className="dd-col-type">{stats.type}</span>}
                    {stats.null_rate != null && (
                      <span className="dd-col-null" style={{ color: stats.null_rate > 15 ? '#ef4444' : stats.null_rate > 5 ? '#f59e0b' : '#6b7280' }}>
                        {stats.null_rate.toFixed(0)}% null
                      </span>
                    )}
                  </div>
                  {stats.sample && (
                    <div className="dd-col-samples">
                      {stats.sample.filter((v) => v != null).slice(0, 3).map((v, i) => (
                        <span key={i} className="dd-sample-val">{String(v)}</span>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}

          {/* DQ Rules tab */}
          {activeTab === 'dq' && (
            <div className="dd-dq-report">
              <div className="dd-dq-summary">
                <span className="dd-dq-badge dd-dq-pass"><i className="fas fa-check-circle" /> {dqSummary.pass} pass</span>
                <span className="dd-dq-badge dd-dq-warn"><i className="fas fa-exclamation-circle" /> {dqSummary.warn} warn</span>
                <span className="dd-dq-badge dd-dq-fail"><i className="fas fa-times-circle" /> {dqSummary.fail} fail</span>
              </div>
              <table className="dd-dq-table">
                <thead>
                  <tr>
                    <th>Status</th>
                    <th>Rule</th>
                    <th>Column</th>
                    <th>Detail</th>
                    <th>Rows Affected</th>
                  </tr>
                </thead>
                <tbody>
                  {dqRules.map((r, i) => (
                    <tr key={i} className={`dd-dq-row dd-dq-row--${r.status}`}>
                      <td>
                        <span className="dd-dq-status" style={{ color: DQ_STATUS_COLORS[r.status] }}>
                          <i className={DQ_STATUS_ICONS[r.status]} /> {r.status}
                        </span>
                      </td>
                      <td><code className="dd-dq-rule-name">{r.rule}</code></td>
                      <td><span className="dd-col-name" style={{ display: 'inline' }}>{r.column}</span></td>
                      <td className="dd-dq-detail">{r.detail}</td>
                      <td className="dd-num">{r.affected != null ? fmtNum(r.affected) : '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <div className="dd-dq-footer">
                <button className="dd-btn dd-btn-secondary dd-btn-sm" onClick={() => onRunQualityScan && onRunQualityScan(file)}>
                  <i className="fas fa-play" /> Run Full Quality Scan
                </button>
                <span className="dd-dq-note">Rules derived from column profiling. Run a full scan for definitive results.</span>
              </div>
            </div>
          )}

          {/* Null Values Report tab */}
          {activeTab === 'nulls' && (
            <div className="dd-null-report">
              {nullColumns.length === 0 ? (
                <div className="dd-null-clean">
                  <i className="fas fa-check-circle" style={{ color: '#22c55e' }} /> No null values detected in any column.
                </div>
              ) : (
                <>
                  <p className="dd-null-intro">
                    <strong>{nullColumns.length}</strong> column{nullColumns.length !== 1 ? 's' : ''} contain null values.
                    {file.row_count != null && <> File has {fmtNum(file.row_count)} rows.</>}
                  </p>
                  <table className="dd-null-table">
                    <thead>
                      <tr>
                        <th>Column</th>
                        <th>Type</th>
                        <th>Null Rate</th>
                        <th>Null Rows</th>
                        <th>Completeness</th>
                        <th>Severity</th>
                      </tr>
                    </thead>
                    <tbody>
                      {nullColumns.map(([col, stats]) => {
                        const nr = stats.null_rate;
                        const severity = nr >= 20 ? 'high' : nr >= 5 ? 'medium' : 'low';
                        const severityColor = severity === 'high' ? '#ef4444' : severity === 'medium' ? '#f59e0b' : '#22c55e';
                        const nullRows = file.row_count != null ? Math.round((nr / 100) * file.row_count) : null;
                        return (
                          <tr key={col} className="dd-null-row">
                            <td><span className="dd-col-name" style={{ display: 'inline' }}>{col}</span></td>
                            <td><span className="dd-col-type">{stats.type || '—'}</span></td>
                            <td>
                              <div className="dd-null-bar-wrap">
                                <div className="dd-null-bar-track">
                                  <div className="dd-null-bar-fill" style={{ width: `${Math.min(nr, 100)}%`, background: severityColor }} />
                                </div>
                                <span style={{ color: severityColor, fontWeight: 600, fontSize: '0.8rem', minWidth: 42 }}>{nr.toFixed(1)}%</span>
                              </div>
                            </td>
                            <td className="dd-num">{nullRows != null ? fmtNum(nullRows) : '—'}</td>
                            <td className="dd-num" style={{ color: DQ_STATUS_COLORS[nr >= 5 ? (nr >= 20 ? 'fail' : 'warn') : 'pass'] }}>
                              {(100 - nr).toFixed(1)}%
                            </td>
                            <td>
                              <span className="dd-severity-badge" style={{ background: `${severityColor}22`, color: severityColor }}>{severity}</span>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                  <div className="dd-dq-footer">
                    <button className="dd-btn dd-btn-secondary dd-btn-sm" onClick={() => onRunQualityScan && onRunQualityScan(file)}>
                      <i className="fas fa-play" /> Run Full Quality Scan
                    </button>
                  </div>
                </>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ─── Main Component ──────────────────────────────────────────────────────────

export default function DataDiscoveryPage() {
  const [searchParams] = useSearchParams();

  // ── Source selection
  const [sources, setSources]             = useState([]);
  const [selectedSourceId, setSelected]   = useState('');
  const [folderPath, setFolderPath]       = useState('');
  const [recursive, setRecursive]         = useState(true);

  // ── Source input mode: 'source' | 'path' | 'upload'
  const [sourceMode, setSourceMode]       = useState('source');

  // ── File upload mode state
  const [uploadFiles, setUploadFiles]     = useState([]);   // File[] from <input type=file>
  const [uploading, setUploading]         = useState(false);
  const [uploadProgress, setUploadProgress] = useState(null); // {done, total}

  // ── Live vs demo mode (false = showing demo seed data)
  const [liveMode, setLiveMode]           = useState(false);

  // ── Discovery state
  const [status, setStatus]               = useState('done'); // idle | running | done | error
  const [result, setResult]               = useState(DEMO_RESULT);
  const [error, setError]                 = useState(null);

  // ── Export state
  const [exporting, setExporting]         = useState(false);

  // ── Saved reports (past runs)
  const [savedReports, setSavedReports]   = useState(DEMO_PAST_RUNS);
  const [activeReportId, setActiveReportId] = useState(null);

  // ── Workflow guidance banner (shown when navigating from migration wizard)
  const [fromWizard, setFromWizard]       = useState(false);

  // ── Selected file for profile review panel
  const [selectedProfileFile, setSelectedProfileFile] = useState(null);

  // ── DB connection test status
  const [dbConnStatus, setDbConnStatus]   = useState(null); // null | 'testing' | 'ok' | 'error'

  // ── Quality scan state
  const [scanning, setScanning]           = useState(false);
  const [scanResult, setScanResult]       = useState(null);
  const [scanError, setScanError]         = useState(null);

  // ── Filter / sort
  const [filterType, setFilterType]       = useState('');
  const [filterName, setFilterName]       = useState('');
  const [sortKey, setSortKey]             = useState('name');
  const [sortDir, setSortDir]             = useState('asc');

  const loadSavedReports = useCallback(() => {
    e2etraceFetchWithRetry(`${API_BASE}${API_CONFIG.ENDPOINTS.AGENTIC_DISCOVERY}/reports`)
      .then((r) => r.ok ? r.json() : [])
      .then((data) => { if (Array.isArray(data) && data.length > 0) setSavedReports(data); })
      .catch(() => {}); // retain demo data on fetch error
  }, []);

  // Load registered folder datasources + saved reports on mount
  useEffect(() => {
    const paramSource = searchParams.get('source');
    if (paramSource) setFromWizard(true);

    e2etraceFetchWithRetry(`${API_BASE}/api/data-sources`)
      .then((r) => r.ok ? r.json() : [])
      .then((data) => {
        // Include all file/folder-backed source types (backend uses 'local_folder', 'file', not 'folder')
        const FILE_TYPES = new Set(['folder', 'local_folder', 'file', 's3', 'aws_s3', 'azure_blob', 'azure', 'onedrive', 'google_drive']);
        const folderSources = Array.isArray(data)
          ? data.filter((s) => {
              const t = (s.type || s.source_type || '').toLowerCase();
              return FILE_TYPES.has(t) || !!(s.connection?.folder_path || s.connection?.file_path);
            })
          : [];
        setSources(folderSources);
        // Auto-select source coming from wizard URL param
        if (paramSource && folderSources.find((s) => s.id === paramSource)) {
          setSelected(paramSource);
        }
      })
      .catch(() => setSources([]));
    loadSavedReports();
  }, [loadSavedReports, searchParams]);

  // Restore a past saved report into the active view
  const restoreReport = useCallback((saved) => {
    setResult(saved.result);
    setStatus('done');
    setActiveReportId(saved.report_id);
    setScanResult(null);
    setScanError(null);
    setError(null);
  }, []);

  // Re-use: pre-fill source inputs from a past run then restore its result
  const reuseRun = useCallback((saved) => {
    if (saved.source_id && sources.find((s) => s.id === saved.source_id)) {
      setSelected(saved.source_id);
      setFolderPath('');
    } else if (saved.folder_path) {
      setFolderPath(saved.folder_path);
      setSelected('');
    }
    restoreReport(saved);
    setLiveMode(true);
  }, [sources, restoreReport]);

  const runDiscovery = useCallback(async () => {
    // Validate based on mode
    if (sourceMode === 'upload' && uploadFiles.length === 0) return;
    if (sourceMode !== 'upload' && !selectedSourceId && !folderPath.trim()) return;

    setStatus('running');
    setResult(null);
    setError(null);
    setScanResult(null);
    setScanError(null);
    setActiveReportId(null);
    setSelectedProfileFile(null);

    // ── Upload mode: push files to server first, then discover upload dir
    let resolvedDiscoveryPath;
    if (sourceMode === 'upload') {
      setUploading(true);
      setUploadProgress({ done: 0, total: uploadFiles.length });
      try {
        for (let i = 0; i < uploadFiles.length; i++) {
          const fd = new FormData();
          fd.append('file', uploadFiles[i]);
          const res = await e2etraceFetchWithRetry(`${API_BASE}/api/filesystem/upload`, { method: 'POST', body: fd });
          if (!res.ok) {
            const d = await res.json().catch(() => ({}));
            throw new Error(d.detail || `Upload failed for ${uploadFiles[i].name}`);
          }
          const data = await res.json();
          // Use the server-reported path for the first file's parent dir
          if (i === 0 && data.file_path) {
            resolvedDiscoveryPath = data.file_path.replace(/[\\/][^\\/]+$/, ''); // strip filename
          }
          setUploadProgress({ done: i + 1, total: uploadFiles.length });
        }
      } catch (e) {
        setError(e.message || 'File upload failed');
        setStatus('error');
        setUploading(false);
        setUploadProgress(null);
        return;
      } finally {
        setUploading(false);
        setUploadProgress(null);
      }
    }

    const selectedSource = sources.find((s) => s.id === selectedSourceId);
    const resolvedPath = resolvedDiscoveryPath ||
      (selectedSource
        ? (selectedSource.connection?.folder_path || selectedSource.connection?.file_path || selectedSource.connection?.connection_string || '')
        : folderPath.trim());
    const body = {
      source_id: sourceMode === 'source' ? (selectedSourceId || undefined) : undefined,
      folder_path: resolvedPath || undefined,
      recursive: sourceMode === 'upload' ? false : recursive,
      include_profiling: true,
      save_report: true,
    };

    try {
      const res = await e2etraceFetchWithRetry(`${API_BASE}${API_CONFIG.ENDPOINTS.AGENTIC_DISCOVERY}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);
      setResult(data);
      setStatus('done');
      setLiveMode(true);
      if (data.report_id) setActiveReportId(data.report_id);
      loadSavedReports(); // refresh history panel
    } catch (e) {
      setError(e.message || 'Discovery failed');
      setStatus('error');
    }
  }, [selectedSourceId, folderPath, recursive, sourceMode, uploadFiles, loadSavedReports, sources]);

  // Auto-restore most recent past run for the pre-selected source from wizard
  useEffect(() => {
    const paramSource = searchParams.get('source');
    if (!paramSource || savedReports === DEMO_PAST_RUNS) return; // only run once real reports loaded
    const matchingRuns = savedReports.filter(
      (r) => r.source_id === paramSource || String(r.source_id) === String(paramSource)
    );
    if (matchingRuns.length > 0) {
      // Sort by created_at desc, pick newest
      const newest = matchingRuns.sort((a, b) =>
        new Date(b.created_at) - new Date(a.created_at)
      )[0];
      restoreReport(newest);
      setLiveMode(true);
    } else {
      // No past run for this source — set to idle so user knows to click Discover
      setStatus('idle');
      setResult(null);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [savedReports]);

  const runQualityScan = useCallback(async () => {
    if (!selectedSourceId && !folderPath.trim()) return;
    setScanning(true);
    setScanResult(null);
    setScanError(null);

    const selectedSrc = sources.find((s) => s.id === selectedSourceId);
    const resolvedScanPath = selectedSrc
      ? (selectedSrc.connection?.folder_path || selectedSrc.connection?.file_path || selectedSrc.connection?.connection_string || '')
      : folderPath.trim();
    const body = {
      source_id: selectedSourceId || undefined,
      folder_path: resolvedScanPath || undefined,
      scan_type: 'full',
      save_report: true,
    };

    try {
      const res = await e2etraceFetchWithRetry(`${API_BASE}${API_CONFIG.ENDPOINTS.AGENTIC_QUALITY_SCAN}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);
      setScanResult(data);
    } catch (e) {
      const msg = e.message || 'Quality scan failed';
      setScanError(
        msg === 'Failed to fetch'
          ? 'Cannot reach the backend server. Ensure the server is running and try again.'
          : msg
      );
    } finally {
      setScanning(false);
    }
  }, [selectedSourceId, folderPath, sources]);

  // Run quality scan triggered from ProfileRow "Run Full Quality Scan" button
  const runQualityScanForFile = useCallback((_file) => {
    // Scroll to top so user sees the scan running
    window.scrollTo({ top: 0, behavior: 'smooth' });
    runQualityScan();
  }, [runQualityScan]);

  // ── Derive display data from result (shared by export callbacks and render)
  const taskResult = useMemo(() => result?.result || result || {}, [result]);
  const discoveredFiles = useMemo(() => (
    Array.isArray(taskResult.files) ? taskResult.files
    : Array.isArray(taskResult.discovered_files) ? taskResult.discovered_files
    : []
  ), [taskResult]);

  // ── Export functions
  const exportToJSON = useCallback(() => {
    if (!result) return;
    setExporting(true);
    try {
      const totalSize = discoveredFiles.reduce((s, f) => s + (f.size_bytes || 0), 0);
      
      const exportData = {
        exported_at: new Date().toISOString(),
        discovery_result: result,
        report_id: activeReportId,
        source: folderPath || selectedSourceId,
        file_count: discoveredFiles.length,
        total_size_bytes: totalSize,
      };
      const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `data-discovery-${Date.now()}.json`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } finally {
      setExporting(false);
    }
  }, [result, activeReportId, folderPath, selectedSourceId, discoveredFiles]);

  const exportToCSV = useCallback(() => {
    if (!result) return;
    if (!discoveredFiles.length) return;
    
    setExporting(true);
    try {
      // CSV header
      const headers = [
        'File Name',
        'File Type',
        'Size (KB)',
        'Rows',
        'Columns',
        'Null Rate (%)',
        'Completeness (%)',
        'Cardinality (%)',
        'Data Type',
        'Semantic Type',
        'Top Values',
        'Distinct Count',
      ];
      
      // Build CSV rows — emit one row per column per file
      const rows = [];
      rows.push(headers.join(','));

      discoveredFiles.forEach((f) => {
        const sizeKB = ((f.size_bytes || 0) / 1024).toFixed(2);
        const nullRate = f.null_rate != null ? f.null_rate.toFixed(2) : '';
        const completeness = f.completeness != null ? f.completeness.toFixed(2) : '';
        const profile = f.profile || {};
        const colKeys = Object.keys(profile);
        if (colKeys.length === 0) {
          // No profile data: emit one file-level row
          rows.push([
            csvEscape(f.name || ''),
            csvEscape(f.file_type || ''),
            sizeKB, f.row_count || '', f.column_count || '',
            nullRate, completeness, '', '', '', '', '',
          ].join(','));
          return;
        }
        colKeys.forEach((colKey) => {
          const col = profile[colKey] || {};
          const cardinalityPct = col.cardinality_ratio
            ? (col.cardinality_ratio * 100).toFixed(2)
            : '';
          const topValues = col.top_values
            ? col.top_values.map(tv => `${tv.value}(${tv.percentage}%)`).join('; ')
            : '';
          rows.push([
            csvEscape(f.name || ''),
            csvEscape(f.file_type || ''),
            sizeKB, f.row_count || '', f.column_count || '',
            nullRate, completeness,
            cardinalityPct,
            csvEscape(col.type || ''),
            csvEscape(col.semantic_type || ''),
            csvEscape(topValues),
            col.distinct_count || '',
          ].join(','));
        });
      });
      
      const csv = rows.join('\n');
      const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `data-discovery-${Date.now()}.csv`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      // Delay revoke so Firefox can complete the download fetch
      setTimeout(() => URL.revokeObjectURL(url), 150);
    } finally {
      setExporting(false);
    }
  }, [result, discoveredFiles]);

  const csvEscape = (value) => {
    if (value === null || value === undefined) return '';
    const s = String(value);
    if (/[\n\r,"]/g.test(s)) {
      return `"${s.replace(/"/g, '""')}"`;
    }
    return s;
  };

  const exportToXlsx = useCallback(async () => {
    if (!discoveredFiles.length) return;
    setExporting(true);
    try {
      const HEADER_STYLE = { fontWeight: 'bold', backgroundColor: '#1F3864', color: '#FFFFFF', align: 'center' };
      const headerRow = [
        { value: 'File Name',        ...HEADER_STYLE },
        { value: 'File Type',        ...HEADER_STYLE },
        { value: 'Column',           ...HEADER_STYLE },
        { value: 'Size (KB)',        ...HEADER_STYLE },
        { value: 'Rows',             ...HEADER_STYLE },
        { value: 'Null Rate (%)',    ...HEADER_STYLE },
        { value: 'Completeness (%)', ...HEADER_STYLE },
        { value: 'Data Type',        ...HEADER_STYLE },
        { value: 'Semantic Type',    ...HEADER_STYLE },
        { value: 'Distinct Count',   ...HEADER_STYLE },
        { value: 'Top Values',       ...HEADER_STYLE },
        { value: 'Issue Flag',       ...HEADER_STYLE },
      ];

      const dataRows = [];
      discoveredFiles.forEach((f) => {
        const sizeKB = parseFloat(((f.size_bytes || 0) / 1024).toFixed(2));
        const profile = f.profile || {};
        const colKeys = Object.keys(profile);
        if (colKeys.length === 0) {
          dataRows.push([
            { value: f.name || '' }, { value: f.file_type || '' }, { value: '—' },
            { value: sizeKB, type: Number }, { value: f.row_count || 0, type: Number },
            { value: f.null_rate || 0, type: Number }, { value: f.completeness || 0, type: Number },
            { value: '' }, { value: '' }, { value: 0, type: Number }, { value: '' }, { value: 'No profile' },
          ]);
          return;
        }
        colKeys.forEach((colKey) => {
          const col = profile[colKey] || {};
          const nullRate = col.null_rate != null ? col.null_rate : f.null_rate || 0;
          const issues = [];
          if (nullRate > 10) issues.push(`High nulls (${nullRate}%)`);
          const topValues = (col.top_values || []).map(tv => `${tv.value}(${tv.percentage}%)`).join('; ');
          dataRows.push([
            { value: f.name || '', fontWeight: 'bold' },
            { value: f.file_type || '' },
            { value: colKey },
            { value: sizeKB, type: Number },
            { value: f.row_count || 0, type: Number },
            { value: parseFloat(nullRate.toFixed ? nullRate.toFixed(2) : nullRate) || 0, type: Number, backgroundColor: nullRate > 10 ? '#FFC7CE' : undefined },
            { value: f.completeness != null ? parseFloat(f.completeness.toFixed(2)) : null, type: f.completeness != null ? Number : String },
            { value: col.type || '' },
            { value: col.semantic_type || '' },
            { value: col.distinct_count || 0, type: Number },
            { value: topValues },
            { value: issues.join('; ') || 'OK', color: issues.length ? '#C00000' : '#375623' },
          ]);
        });
      });

      await writeXlsxFile(
        [[headerRow, ...dataRows]],
        {
          sheets: ['Discovery Report'],
          fileName: `data-discovery-${Date.now()}.xlsx`,
          columns: [
            [{ width: 28 }, { width: 10 }, { width: 20 }, { width: 10 }, { width: 8 },
             { width: 12 }, { width: 14 }, { width: 14 }, { width: 16 }, { width: 14 }, { width: 30 }, { width: 20 }],
          ],
        }
      );
    } finally {
      setExporting(false);
    }
  }, [discoveredFiles]);
  const byType = taskResult.by_type || taskResult.file_types || {};
  const catalog = taskResult.catalog || {};

  const fileTypes = [...new Set(discoveredFiles.map((f) => f.file_type).filter(Boolean))];
  const filtered = discoveredFiles.filter((f) => {
    if (filterType && f.file_type !== filterType) return false;
    if (filterName && !String(f.name || f.path || '').toLowerCase().includes(filterName.toLowerCase())) return false;
    return true;
  });
  const sorted = [...filtered].sort((a, b) => {
    let av = a[sortKey], bv = b[sortKey];
    if (typeof av === 'string') av = av.toLowerCase();
    if (typeof bv === 'string') bv = bv.toLowerCase();
    if (av == null) return 1;
    if (bv == null) return -1;
    return sortDir === 'asc' ? (av < bv ? -1 : av > bv ? 1 : 0) : (av > bv ? -1 : av < bv ? 1 : 0);
  });

  const totalSize = discoveredFiles.reduce((s, f) => s + (f.size_bytes || 0), 0);
  const nullRateFiles = discoveredFiles.filter((f) => f.null_rate != null);
  const avgNullRate = nullRateFiles.length
    ? nullRateFiles.reduce((s, f) => s + f.null_rate, 0) / nullRateFiles.length
    : 0;

  const toggleSort = (key) => {
    if (sortKey === key) setSortDir(d => d === 'asc' ? 'desc' : 'asc');
    else { setSortKey(key); setSortDir('asc'); }
  };
  const sortIcon = (key) => sortKey === key ? (sortDir === 'asc' ? ' ↑' : ' ↓') : '';

  return (
    <div className="dd-page">

      {/* ── AGENT PIPELINE CONTEXT ──────────────────────────────── */}
      <AgentPipelineStrip activeStageName="discovery" />

      {/* ── HEADER ─────────────────────────────────────────────── */}
      <div className="dd-header">
        <div className="dd-header-left">
          <span className="dd-header-icon"><i className="fas fa-search-location" /></span>
          <div>
            <h1>Data Discovery</h1>
            <p>Profile and catalog folder data sources via MCP DataDiscoveryAgent</p>
          </div>
        </div>
        <div className="dd-header-right">
          {liveMode
            ? <span className="dd-live-badge"><span className="dd-live-dot" />LIVE</span>
            : <span className="dd-demo-badge"><i className="fas fa-flask" /> DEMO</span>}
          {status === 'done' && discoveredFiles.length > 0 && (
            <>
              <button
                className="dd-btn dd-btn-secondary"
                onClick={exportToJSON}
                disabled={exporting}
                title="Export discovery results as JSON"
              >
                {exporting
                  ? <><i className="fas fa-spinner fa-spin" /> Exporting…</>
                  : <><i className="fas fa-file-code" /> Export JSON</>}
              </button>
              <button
                className="dd-btn dd-btn-secondary"
                onClick={exportToCSV}
                disabled={exporting}
                title="Export file summary as CSV (one row per column)"
              >
                <i className="fas fa-file-csv" /> Export CSV
              </button>
              <button
                className="dd-btn dd-btn-secondary"
                onClick={exportToXlsx}
                disabled={exporting}
                title="Export full discovery report as XLSX (one row per column, all files)"
              >
                <i className="fas fa-file-excel" /> Export XLSX
              </button>
              <Link
                to="/dq-dashboard"
                className="dd-btn dd-btn-primary"
                style={{ textDecoration: 'none' }}
                title="Check data quality for discovered files"
              >
                <i className="fas fa-shield-alt" /> Check Data Quality →
              </Link>
            </>
          )}
          {status === 'done' && (
            <button
              className="dd-btn dd-btn-secondary"
              onClick={runQualityScan}
              disabled={scanning}
            >
              {scanning
                ? <><i className="fas fa-spinner fa-spin" /> Scanning…</>
                : <><i className="fas fa-shield-alt" /> Quality Scan</>}
            </button>
          )}
          <button
            className="dd-btn dd-btn-primary"
            onClick={runDiscovery}
            disabled={
              status === 'running' || uploading ||
              (sourceMode === 'upload' ? uploadFiles.length === 0 : (!selectedSourceId && !folderPath.trim()))
            }
          >
            {uploading
              ? <><i className="fas fa-spinner fa-spin" /> Uploading {uploadProgress?.done}/{uploadProgress?.total}…</>
              : status === 'running'
              ? <><i className="fas fa-spinner fa-spin" /> Discovering…</>
              : <><i className="fas fa-play" /> Discover</>}
          </button>
        </div>
      </div>

      {/* ── SOURCE SELECTOR ─────────────────────────────────────── */}
      <div className="dd-card dd-source-card">

        {/* ── WORKFLOW GUIDANCE BANNER ─────────────────────────────── */}
        {fromWizard && (
          <div className="dd-guidance-banner">
            <div className="dd-guidance-icon"><i className="fas fa-info-circle" /></div>
            <div className="dd-guidance-body">
              <strong>Next steps in your migration workflow:</strong>
              <ol className="dd-guidance-steps">
                <li>Your source is pre-selected below. Click <strong>Discover</strong> to profile its files.</li>
                <li>Review the file list and click <strong>Profile</strong> on any file to inspect column stats, DQ rules, and null values.</li>
                <li>Click <strong>Quality Scan</strong> to run a full DQ scan across all files.</li>
                <li>Return to the Migration Wizard to proceed to <strong>Map Fields</strong> (Step 3).</li>
              </ol>
            </div>
            <button className="dd-guidance-close" onClick={() => setFromWizard(false)}><i className="fas fa-times" /></button>
          </div>
        )}

        {/* ── Mode tabs ────────────────────────────────────────────── */}
        <div className="dd-mode-tabs">
          <button
            className={`dd-mode-tab${sourceMode === 'source' ? ' dd-mode-tab--active' : ''}`}
            onClick={() => setSourceMode('source')}
          >
            <i className="fas fa-database" /> Registered Source
          </button>
          <button
            className={`dd-mode-tab${sourceMode === 'path' ? ' dd-mode-tab--active' : ''}`}
            onClick={() => setSourceMode('path')}
          >
            <i className="fas fa-folder-open" /> Folder Path
          </button>
          <button
            className={`dd-mode-tab${sourceMode === 'upload' ? ' dd-mode-tab--active' : ''}`}
            onClick={() => setSourceMode('upload')}
          >
            <i className="fas fa-upload" /> Upload Files
          </button>
        </div>

        {/* ── Registered Source ────────────────────────────────────── */}
        {sourceMode === 'source' && (
          <div className="dd-source-row">
            <div className="dd-source-group dd-source-group-flex">
              <label className="dd-label">Registered Folder Source</label>
              <select
                className="dd-select"
                value={selectedSourceId}
                onChange={(e) => {
                  const id = e.target.value;
                  setSelected(id);
                  setFolderPath('');
                  if (id) {
                    const src = sources.find((s) => s.id === id);
                    const type = (src?.type || src?.source_type || '').toLowerCase();
                    const DB_TYPES = new Set(['postgresql', 'postgres', 'mysql', 'mssql', 'sqlserver', 'oracle', 'mongodb', 'redis', 'elasticsearch', 'database']);
                    if (DB_TYPES.has(type)) {
                      setDbConnStatus('testing');
                      e2etraceFetchWithRetry(`${API_BASE}/api/data-sources/${encodeURIComponent(id)}/test`, { method: 'POST' })
                        .then(async (r) => {
                          if (!r.ok) { setDbConnStatus('error'); return; }
                          const body = await r.json().catch(() => null);
                          setDbConnStatus(body && body.success === false ? 'error' : 'ok');
                        })
                        .catch(() => setDbConnStatus('error'));
                    } else {
                      setDbConnStatus(null);
                    }
                  } else {
                    setDbConnStatus(null);
                  }
                }}
              >
                <option value="">— select a registered source —</option>
                {sources.map((s) => (
                  <option key={s.id} value={s.id}>{s.name} ({s.connection?.folder_path || s.connection?.file_path || s.connection?.connection_string || s.folder_path || s.id})</option>
                ))}
              </select>
              {sources.length === 0 && (
                <span className="dd-source-hint">No registered sources — add one in <a href="#/admin" className="dd-link">Admin</a> or use Folder Path / Upload Files mode.</span>
              )}
              {dbConnStatus === 'testing' && <span className="dd-conn-status testing"><i className="fas fa-circle-notch fa-spin" /> Testing connection…</span>}
              {dbConnStatus === 'ok'      && <span className="dd-conn-status ok"><i className="fas fa-check-circle" /> Connected</span>}
              {dbConnStatus === 'error'   && <span className="dd-conn-status error"><i className="fas fa-exclamation-circle" /> Connection failed</span>}
            </div>
            <label className="dd-checkbox-label">
              <input type="checkbox" checked={recursive} onChange={(e) => setRecursive(e.target.checked)} />
              Recursive
            </label>
          </div>
        )}

        {/* ── Folder Path ──────────────────────────────────────────── */}
        {sourceMode === 'path' && (
          <div className="dd-source-row">
            <div className="dd-source-group dd-source-group-flex">
              <label className="dd-label">Folder Path (server-accessible)</label>
              <input
                className="dd-input"
                type="text"
                placeholder="e.g. /data/uploads or C:\data\csv"
                value={folderPath}
                onChange={(e) => { setFolderPath(e.target.value); setSelected(''); }}
              />
            </div>
            <label className="dd-checkbox-label">
              <input type="checkbox" checked={recursive} onChange={(e) => setRecursive(e.target.checked)} />
              Recursive
            </label>
          </div>
        )}

        {/* ── Upload Files ─────────────────────────────────────────── */}
        {sourceMode === 'upload' && (
          <div className="dd-upload-area">
            <label className="dd-upload-label">
              <input
                type="file"
                multiple
                accept=".csv,.json,.xml,.xlsx,.parquet,.txt,.tsv"
                className="dd-upload-input"
                onChange={(e) => setUploadFiles(Array.from(e.target.files || []))}
              />
              <div className="dd-upload-drop">
                <i className="fas fa-cloud-upload-alt dd-upload-icon" />
                <div className="dd-upload-prompt">
                  {uploadFiles.length === 0
                    ? <><strong>Click to select files</strong> or drag &amp; drop<br /><span className="dd-upload-hint">CSV, JSON, XML, XLSX, Parquet, TSV</span></>
                    : <><strong>{uploadFiles.length} file{uploadFiles.length !== 1 ? 's' : ''} selected</strong> — click to change</>}
                </div>
              </div>
            </label>

            {uploadFiles.length > 0 && (
              <div className="dd-upload-file-list">
                {uploadFiles.map((f, i) => {
                  const ext = f.name.split('.').pop().toLowerCase();
                  return (
                    <div key={`${f.name}-${f.size}-${i}`} className="dd-upload-file-row">
                      <span className="dd-type-badge" style={{ background: `${typeColor(ext)}22`, color: typeColor(ext) }}>{ext}</span>
                      <span className="dd-upload-file-name" title={f.name}>{f.name}</span>
                      <span className="dd-upload-file-size">{fmtSize(f.size)}</span>
                      <button
                        className="dd-upload-file-remove"
                        title="Remove"
                        onClick={() => setUploadFiles((prev) => prev.filter((_, j) => j !== i))}
                      >
                        <i className="fas fa-times" />
                      </button>
                    </div>
                  );
                })}
              </div>
            )}

            {uploading && uploadProgress && (
              <div className="dd-upload-progress">
                <div className="dd-upload-progress-bar" style={{ width: `${(uploadProgress.done / uploadProgress.total) * 100}%` }} />
                <span>Uploading {uploadProgress.done} / {uploadProgress.total}…</span>
              </div>
            )}
          </div>
        )}
      </div>

      {/* ── RECENT SCANS (quick-resume) ──────────────────────────── */}
      {savedReports.length > 0 && status !== 'running' && (
        <div className="dd-recent-scans">
          <span className="dd-recent-scans-label"><i className="fas fa-history" /> Recent:</span>
          {savedReports.slice(0, 3).map((r) => (
            <div key={r.report_id} className={`dd-recent-tile${activeReportId === r.report_id ? ' dd-recent-tile--active' : ''}`}>
              <i className="fas fa-folder" aria-hidden="true" />
              <div className="dd-recent-tile-info">
                <span className="dd-recent-tile-name" title={r.folder_path || r.label}>
                  {r.folder_path ? r.folder_path.split(/[/\\]/).filter(Boolean).pop() : (r.label || 'Unknown')}
                </span>
                <span className="dd-recent-tile-meta">
                  {r.total_files ?? '?'} files
                  {r.created_at && <> &bull; {fmtAge(r.created_at)}</>}
                </span>
              </div>
              <button
                className="dd-recent-reuse-btn"
                onClick={() => reuseRun(r)}
                title={`Re-use: ${r.folder_path || r.label}`}
              >
                Re-use
              </button>
            </div>
          ))}
        </div>
      )}

      {/* ── ERROR ───────────────────────────────────────────────── */}
      {status === 'error' && error && (
        <div className="dd-alert dd-alert-error">
          <i className="fas fa-exclamation-circle" /> {error}
          <button className="dd-alert-close" onClick={() => { setStatus('idle'); setError(null); }}>
            <i className="fas fa-times" />
          </button>
        </div>
      )}
      {scanError && (
        <div className="dd-alert dd-alert-error">
          <i className="fas fa-exclamation-circle" /> Quality scan: {scanError}
          <button className="dd-alert-close" onClick={() => setScanError(null)}>
            <i className="fas fa-times" />
          </button>
        </div>
      )}

      {/* ── RUNNING STATE ───────────────────────────────────────── */}
      {status === 'running' && (
        <div className="dd-card dd-running-card">
          <i className="fas fa-circle-notch fa-spin dd-spin-icon" />
          <div>
            <div className="dd-running-title">Discovering files…</div>
            <div className="dd-running-sub">DataDiscoveryAgent is scanning the folder and profiling files</div>
          </div>
        </div>
      )}

      {/* ── RESULTS ─────────────────────────────────────────────── */}
      {status === 'done' && (
        <>
          {/* KPI strip */}
          <div className="dd-kpi-strip">
            <KpiCard
              label="Total Files"
              value={fmtNum(discoveredFiles.length)}
              sub={`${Object.keys(byType).length} file types`}
              color="#3b82f6"
              icon={<i className="fas fa-folder-open" />}
            />
            <KpiCard
              label="Total Size"
              value={fmtSize(totalSize)}
              sub="across all files"
              color="#8b5cf6"
              icon={<i className="fas fa-hdd" />}
            />
            <KpiCard
              label="Avg Null Rate"
              value={`${avgNullRate.toFixed(1)}%`}
              sub="across profiled files"
              color={avgNullRate > 20 ? '#ef4444' : '#22c55e'}
              icon={<i className="fas fa-exclamation-triangle" />}
            />
            {catalog.avg_row_count != null && (
              <KpiCard
                label="Avg Row Count"
                value={fmtNum(Math.round(catalog.avg_row_count))}
                sub="per structured file"
                color="#f59e0b"
                icon={<i className="fas fa-table" />}
              />
            )}
          </div>

          {/* File type breakdown */}
          <div className="dd-card">
            <div className="dd-section-header">
              <span><i className="fas fa-chart-bar" /> File Type Breakdown</span>
            </div>
            <FileTypeBar byType={byType} />
          </div>

          {/* Quality scan result banner */}
          {scanResult && (
            <div className="dd-card dd-scan-result-card">
              <div className="dd-section-header">
                <span><i className="fas fa-shield-alt" /> Quality Scan Result</span>
                <span
                  className="dd-status-badge"
                  style={{
                    background: `${scoreColor(
                      (scanResult?.result?.overall_score || scanResult?.overall_score || 0) * 100
                    )}22`,
                    color: scoreColor(
                      (scanResult?.result?.overall_score || scanResult?.overall_score || 0) * 100
                    ),
                  }}
                >
                  {scanResult?.result?.status || scanResult?.status || 'unknown'}
                </span>
              </div>
              <div className="dd-scan-scores">
                {['completeness', 'accuracy', 'consistency', 'validity'].map((dim) => {
                  const val = (scanResult?.result?.[dim] || scanResult?.[dim]);
                  if (val == null) return null;
                  const pct = val <= 1 ? val * 100 : val;
                  return (
                    <div key={dim} className="dd-scan-dim">
                      <div className="dd-scan-dim-label">{dim}</div>
                      <div className="dd-scan-bar-track">
                        <div className="dd-scan-bar-fill" style={{ width: `${pct}%`, background: scoreColor(pct) }} />
                      </div>
                      <span className="dd-scan-dim-val" style={{ color: scoreColor(pct) }}>{pct.toFixed(0)}%</span>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* File table */}
          <div className="dd-card">
            <div className="dd-section-header">
              <span><i className="fas fa-list" /> Files ({filtered.length}{filtered.length !== discoveredFiles.length ? ` / ${discoveredFiles.length}` : ''})</span>
              <div className="dd-filters">
                {fileTypes.length > 1 && (
                  <select className="dd-select-sm" value={filterType} onChange={(e) => setFilterType(e.target.value)}>
                    <option value="">All types</option>
                    {fileTypes.map((ft) => <option key={ft} value={ft}>{ft}</option>)}
                  </select>
                )}
                <input
                  className="dd-input-sm"
                  type="text"
                  placeholder="Search name…"
                  value={filterName}
                  onChange={(e) => setFilterName(e.target.value)}
                />
              </div>
            </div>
            <div className="dd-table-wrapper">
              <table className="dd-table">
                <thead>
                  <tr>
                    <th onClick={() => toggleSort('name')} className="dd-sortable">Name{sortIcon('name')}</th>
                    <th onClick={() => toggleSort('file_type')} className="dd-sortable">Type{sortIcon('file_type')}</th>
                    <th onClick={() => toggleSort('size_bytes')} className="dd-sortable">Size{sortIcon('size_bytes')}</th>
                    <th onClick={() => toggleSort('row_count')} className="dd-sortable">Rows{sortIcon('row_count')}</th>
                    <th onClick={() => toggleSort('column_count')} className="dd-sortable">Cols{sortIcon('column_count')}</th>
                    <th onClick={() => toggleSort('null_rate')} className="dd-sortable">Null%{sortIcon('null_rate')}</th>
                    <th>Profile</th>
                  </tr>
                </thead>
                <tbody>
                  {sorted.length === 0
                    ? (
                      <tr>
                        <td colSpan={7} className="dd-empty-row">No files match the current filter</td>
                      </tr>
                    )
                    : sorted.map((f, i) => (
                      <ProfileRow
                        key={f.path || i}
                        file={f}
                        isSelected={selectedProfileFile?.path === f.path}
                        onSelect={setSelectedProfileFile}
                      />
                    ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* File Profile Review Panel */}
          <FileProfilePanel
            file={selectedProfileFile}
            allFiles={discoveredFiles}
            onSelectFile={setSelectedProfileFile}
            onRunQualityScan={runQualityScanForFile}
          />
        </>
      )}

      {/* ── EMPTY STATE ─────────────────────────────────────────── */}
      {status === 'idle' && (
        <div className="dd-empty-state">
          <i className="fas fa-search-location dd-empty-icon" />
          <div className="dd-empty-title">Select a data source and click Discover</div>
          <div className="dd-empty-sub">
            The DataDiscoveryAgent will enumerate files, infer schemas and profile row counts, column stats and null rates.
          </div>
        </div>
      )}

      {/* ── PAST RUNS ────────────────────────────────────────────── */}
      {savedReports.length > 0 && (
        <div className="dd-card dd-past-runs-card">
          <div className="dd-section-header">
            <span><i className="fas fa-history" /> Past Runs</span>
            <button className="dd-btn-refresh" onClick={loadSavedReports} title="Refresh">
              <i className="fas fa-sync-alt" />
            </button>
          </div>
          <div className="dd-past-runs-list">
            {savedReports.map((r) => (
              <div
                key={r.report_id}
                className={`dd-past-run-row${activeReportId === r.report_id ? ' dd-past-run-active' : ''}`}
                onClick={() => restoreReport(r)}
                title="Click to restore this discovery result"
              >
                <span className="dd-pr-icon"><i className="fas fa-folder-open" /></span>
                <div className="dd-pr-info">
                  <span className="dd-pr-label">{r.label}</span>
                  <span className="dd-pr-meta">
                    {r.total_files} file{r.total_files !== 1 ? 's' : ''}
                    {r.total_size_bytes > 0 && <> &bull; {fmtSize(r.total_size_bytes)}</>}
                    {r.created_at && (
                      <> &bull; {new Date(r.created_at).toLocaleString()}</>
                    )}
                  </span>
                </div>
                {activeReportId === r.report_id && (
                  <span className="dd-pr-active-badge">viewing</span>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
