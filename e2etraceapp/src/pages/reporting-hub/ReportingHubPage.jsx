/**
 * Reporting Hub
 * =============
 * Centralised view of every report/output produced by any dashboard page:
 *   Migration Wizard · Data Lineage · Analytics · DQ Dashboard
 *   Data Discovery · Observability · Self-Healing Monitor
 *
 * API calls:
 *   GET  /api/report-hub          → list all unified reports
 *   GET  /api/report-hub/summary  → aggregate KPIs
 *   GET  /api/report-hub/{id}     → single report detail (modal)
 *   DELETE /api/report-hub/{id}   → delete a report
 *   POST /api/report-hub          → save (called from other pages)
 */

import React, { useState, useCallback, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { API_CONFIG } from '../../config/api-config.js';
import { e2etraceFetchWithRetry } from '../../api/e2etrace-api.js';
import './ReportingHubPage.css';

// ─── Type meta ───────────────────────────────────────────────────────────────

const TYPE_META = {
  migration:    { label: 'Migration',         icon: 'fas fa-exchange-alt',    color: '#3b82f6', page: '/migration' },
  lineage:      { label: 'Lineage',           icon: 'fas fa-project-diagram', color: '#8b5cf6', page: '/lineage' },
  analytics:    { label: 'Analytics',         icon: 'fas fa-chart-line',      color: '#0ea5e9', page: '/analytics' },
  dq_scan:      { label: 'DQ Scan',           icon: 'fas fa-shield-alt',      color: '#22c55e', page: '/dq-dashboard' },
  discovery:    { label: 'Discovery',         icon: 'fas fa-search-location', color: '#f59e0b', page: '/data-discovery' },
  observability:{ label: 'Observability',     icon: 'fas fa-heartbeat',       color: '#ef4444', page: '/observability' },
  self_healing: { label: 'Self-Healing',      icon: 'fas fa-wrench',          color: '#6366f1', page: '/self-healing' },
};

const STATUS_META = {
  pass:    { label: 'Pass',    color: '#22c55e', bg: '#dcfce7' },
  fail:    { label: 'Fail',    color: '#ef4444', bg: '#fee2e2' },
  warning: { label: 'Warning', color: '#f59e0b', bg: '#fef3c7' },
  info:    { label: 'Info',    color: '#3b82f6', bg: '#eff6ff' },
  running: { label: 'Running', color: '#8b5cf6', bg: '#f3f4f6' },
};

// ─── Demo / seed data ─────────────────────────────────────────────────────────

const _now = Date.now();
const _ago = (h) => new Date(_now - h * 3600 * 1000).toISOString();

const DEMO_REPORTS = [
  {
    report_id: 'demo-mig-001',
    report_type: 'migration',
    title: 'PLM Parts Master → Target DB (Run #42)',
    source_page: 'migration',
    workflow_id: 'wf-plm-001',
    run_id: 'run-42',
    status: 'pass',
    summary: { records_processed: 3412, errors: 0, quality_score: 96.2, duration_s: 47 },
    tags: ['migration', 'plm', 'parts-master'],
    created_at: _ago(1.5),
  },
  {
    report_id: 'demo-disc-001',
    report_type: 'discovery',
    title: 'Discovery: /data/plm',
    source_page: 'data-discovery',
    workflow_id: null,
    run_id: null,
    status: 'info',
    summary: { total_files: 6, total_size_bytes: 1932544, file_types: ['csv', 'json', 'xlsx', 'parquet'] },
    tags: ['discovery', 'plm'],
    created_at: _ago(2),
  },
  {
    report_id: 'demo-dq-001',
    report_type: 'dq_scan',
    title: 'DQ Scan: workflow_instances',
    source_page: 'dq-dashboard',
    workflow_id: null,
    run_id: null,
    status: 'warning',
    summary: { overall_score: 78.4, issues_count: 12, rows_scanned: 3412, table: 'workflow_instances' },
    tags: ['dq', 'workflow_instances'],
    created_at: _ago(3),
  },
  {
    report_id: 'demo-lin-001',
    report_type: 'lineage',
    title: 'Lineage Snapshot: PLM Workflow wf-plm-001',
    source_page: 'lineage',
    workflow_id: 'wf-plm-001',
    run_id: null,
    status: 'info',
    summary: { nodes: 14, edges: 18, node_types: ['source_system', 'transformation', 'target_system'] },
    tags: ['lineage', 'plm'],
    created_at: _ago(4),
  },
  {
    report_id: 'demo-analytics-001',
    report_type: 'analytics',
    title: 'Analytics: Quality Reports Query (PostgreSQL)',
    source_page: 'analytics',
    workflow_id: null,
    run_id: null,
    status: 'info',
    summary: { rows_returned: 25, data_source: 'postgres', query_type: 'SQL' },
    tags: ['analytics', 'quality'],
    created_at: _ago(5),
  },
  {
    report_id: 'demo-obs-001',
    report_type: 'observability',
    title: 'Observability Snapshot — 07 Mar 2026 10:00',
    source_page: 'observability',
    workflow_id: null,
    run_id: null,
    status: 'pass',
    summary: { quality_score: 91.5, active_alerts: 1, agentic_agents_ready: 7 },
    tags: ['observability', 'health'],
    created_at: _ago(6),
  },
  {
    report_id: 'demo-sh-001',
    report_type: 'self_healing',
    title: 'Self-Healing: Task Execution (retry scenario)',
    source_page: 'self-healing',
    workflow_id: null,
    run_id: 'task-sh-99',
    status: 'pass',
    summary: { total_tasks: 120, successful: 115, failed: 2, retried: 5, dlq_messages: 1 },
    tags: ['self-healing', 'retry'],
    created_at: _ago(8),
  },
  {
    report_id: 'demo-mig-002',
    report_type: 'migration',
    title: 'PLM BOM Structure → Neo4j (Run #41)',
    source_page: 'migration',
    workflow_id: 'wf-plm-002',
    run_id: 'run-41',
    status: 'fail',
    summary: { records_processed: 952, errors: 18, quality_score: 62.1, duration_s: 31 },
    tags: ['migration', 'plm', 'bom'],
    created_at: _ago(26),
  },
  {
    report_id: 'demo-dq-002',
    report_type: 'dq_scan',
    title: 'DQ Scan: data_sources',
    source_page: 'dq-dashboard',
    workflow_id: null,
    run_id: null,
    status: 'pass',
    summary: { overall_score: 95.1, issues_count: 2, rows_scanned: 44, table: 'data_sources' },
    tags: ['dq', 'data_sources'],
    created_at: _ago(27),
  },
];

const DEMO_SUMMARY = {
  total: DEMO_REPORTS.length,
  by_type: { migration: 2, discovery: 1, dq_scan: 2, lineage: 1, analytics: 1, observability: 1, self_healing: 1 },
  by_status: { pass: 4, fail: 1, warning: 1, info: 3 },
};

// ─── Helpers ──────────────────────────────────────────────────────────────────

function fmtDate(iso) {
  if (!iso) return '—';
  return new Date(iso).toLocaleString();
}
function fmtRelative(iso) {
  if (!iso) return '';
  const diff = Date.now() - new Date(iso).getTime();
  const m = Math.floor(diff / 60000);
  if (m < 1) return 'just now';
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}
function typeMeta(t) { return TYPE_META[t] || { label: t, icon: 'fas fa-file-alt', color: '#94a3b8', page: null }; }
function statusBadge(s) {
  const m = STATUS_META[s] || { label: s, color: '#94a3b8', bg: '#f1f5f9' };
  return (
    <span className="rh-status-badge" style={{ color: m.color, background: m.bg }}>
      {m.label}
    </span>
  );
}

// ─── Export helpers ──────────────────────────────────────────────────────────

function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  setTimeout(() => URL.revokeObjectURL(url), 150);
}

function exportReportAsJSON(report) {
  const payload = {
    report_id: report.report_id,
    report_type: report.report_type,
    title: report.title,
    status: report.status,
    workflow_id: report.workflow_id,
    run_id: report.run_id,
    source_page: report.source_page,
    tags: report.tags,
    created_at: report.created_at,
    summary: report.summary,
    result: report.result ?? null,
  };
  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' });
  const safe = (report.title || report.report_id).replace(/[^a-z0-9_-]/gi, '_').slice(0, 60);
  downloadBlob(blob, `report-${safe}-${Date.now()}.json`);
}

function exportReportAsCSV(report) {
  // Flatten summary fields into CSV rows
  const rows = [['Field', 'Value']];
  rows.push(['report_id', report.report_id ?? '']);
  rows.push(['report_type', report.report_type ?? '']);
  rows.push(['title', report.title ?? '']);
  rows.push(['status', report.status ?? '']);
  rows.push(['workflow_id', report.workflow_id ?? '']);
  rows.push(['run_id', report.run_id ?? '']);
  rows.push(['created_at', report.created_at ?? '']);
  if (report.summary && typeof report.summary === 'object') {
    Object.entries(report.summary).forEach(([k, v]) => {
      rows.push([k, Array.isArray(v) ? v.join('; ') : String(v ?? '')]);
    });
  }
  const csv = rows.map((r) => r.map((c) => {
    const s = String(c);
    return /[
\r,"]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  }).join(',')).join('\n');
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' });
  const safe = (report.title || report.report_id).replace(/[^a-z0-9_-]/gi, '_').slice(0, 60);
  downloadBlob(blob, `report-${safe}-${Date.now()}.csv`);
}

function exportReportsListAsJSON(reportsList) {
  const blob = new Blob(
    [JSON.stringify({ exported_at: new Date().toISOString(), count: reportsList.length, reports: reportsList }, null, 2)],
    { type: 'application/json' }
  );
  downloadBlob(blob, `reports-export-${Date.now()}.json`);
}

function exportReportsListAsCSV(reportsList) {
  const headers = ['report_id', 'report_type', 'title', 'status', 'workflow_id', 'run_id', 'source_page', 'tags', 'created_at'];
  const rows = [headers, ...reportsList.map((r) => [
    r.report_id ?? '', r.report_type ?? '', r.title ?? '', r.status ?? '',
    r.workflow_id ?? '', r.run_id ?? '', r.source_page ?? '',
    (r.tags || []).join('; '), r.created_at ?? '',
  ])];
  const csv = rows.map((r) => r.map((c) => {
    const s = String(c);
    return /[\n\r,"]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  }).join(',')).join('\n');
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' });
  downloadBlob(blob, `reports-export-${Date.now()}.csv`);
}

// ─── Sub-components ───────────────────────────────────────────────────────────

function KpiCard({ label, value, color, icon }) {
  return (
    <div className="rh-kpi-card">
      <div className="rh-kpi-icon" style={{ color }}><i className={icon} /></div>
      <div className="rh-kpi-body">
        <div className="rh-kpi-value" style={{ color }}>{value}</div>
        <div className="rh-kpi-label">{label}</div>
      </div>
    </div>
  );
}

function TypePill({ type, count, active, onClick }) {
  const m = type ? typeMeta(type) : { label: 'All', icon: 'fas fa-th-list', color: '#6b7280', page: null };
  return (
    <button
      className={`rh-type-pill${active ? ' rh-type-pill-active' : ''}`}
      style={active ? { background: m.color, color: '#fff', borderColor: m.color } : { borderColor: m.color, color: m.color }}
      onClick={onClick}
    >
      <i className={m.icon} /> {m.label} {count != null && <span className="rh-pill-count">{count}</span>}
    </button>
  );
}

function ReportDetailModal({ report, onClose }) {
  if (!report) return null;
  const m = typeMeta(report.report_type);
  return (
    <div className="rh-modal-overlay" onClick={onClose}>
      <div className="rh-modal" onClick={(e) => e.stopPropagation()}>
        <div className="rh-modal-header" style={{ borderLeft: `4px solid ${m.color}` }}>
          <div className="rh-modal-title"><i className={m.icon} style={{ color: m.color }} /> {report.title}</div>
          <button className="rh-modal-close" onClick={onClose}><i className="fas fa-times" /></button>
        </div>
        <div className="rh-modal-body">
          <div className="rh-modal-meta">
            <span><b>Type:</b> {m.label}</span>
            {report.workflow_id && <span><b>Workflow:</b> {report.workflow_id}</span>}
            {report.run_id && <span><b>Run:</b> {report.run_id}</span>}
            <span><b>Created:</b> {fmtDate(report.created_at)}</span>
            <span>{statusBadge(report.status)}</span>
          </div>
          {report.tags?.length > 0 && (
            <div className="rh-modal-tags">
              {report.tags.map((t) => <span key={t} className="rh-tag">{t}</span>)}
            </div>
          )}
          {report.summary && (
            <div className="rh-modal-section">
              <div className="rh-modal-section-title">Summary</div>
              <div className="rh-modal-kv">
                {Object.entries(report.summary).map(([k, v]) => (
                  <div key={k} className="rh-modal-kv-row">
                    <span className="rh-modal-kv-key">{k.replace(/_/g, ' ')}</span>
                    <span className="rh-modal-kv-val">{Array.isArray(v) ? v.join(', ') : String(v)}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
          {report.result && (
            <div className="rh-modal-section">
              <div className="rh-modal-section-title">Full Result Payload</div>
              <pre className="rh-modal-json">{JSON.stringify(report.result, null, 2)}</pre>
            </div>
          )}
          <div className="rh-modal-footer">
            <button className="rh-btn rh-btn-secondary" onClick={() => exportReportAsJSON(report)}>
              <i className="fas fa-file-code" /> Export JSON
            </button>
            <button className="rh-btn rh-btn-secondary" onClick={() => exportReportAsCSV(report)}>
              <i className="fas fa-file-csv" /> Export CSV
            </button>
            {m.page && (
              <Link to={m.page} className="rh-link-btn" onClick={onClose}>
                <i className={m.icon} /> Open {m.label} page
              </Link>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

// ─── Main Component ───────────────────────────────────────────────────────────

export default function ReportingHubPage() {
  const [liveMode, setLiveMode]         = useState(false);
  const [reports, setReports]           = useState(DEMO_REPORTS);
  const [summary, setSummary]           = useState(DEMO_SUMMARY);
  const [loading, setLoading]           = useState(false);
  const [error, setError]               = useState(null);

  // filters
  const [filterType, setFilterType]     = useState('');
  const [filterStatus, setFilterStatus] = useState('');
  const [filterSearch, setFilterSearch] = useState('');

  // detail modal
  const [detailReport, setDetailReport] = useState(null);

  const loadReports = useCallback(() => {
    setLoading(true);
    setError(null);
    Promise.all([
      fetch(`${API_CONFIG.API_BASE_URL}${API_CONFIG.ENDPOINTS.REPORT_HUB}`).then((r) => r.ok ? r.json() : null),
      fetch(`${API_CONFIG.API_BASE_URL}${API_CONFIG.ENDPOINTS.REPORT_HUB_SUMMARY}`).then((r) => r.ok ? r.json() : null),
    ])
      .then(([data, sum]) => {
        if (Array.isArray(data) && data.length > 0) {
          setReports(data);
          setLiveMode(true);
        }
        if (sum && typeof sum.total === 'number' && sum.total > 0) {
          setSummary(sum);
        }
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => { loadReports(); }, [loadReports]);

  const deleteReport = useCallback((id) => {
    fetch(`${API_CONFIG.API_BASE_URL}${API_CONFIG.ENDPOINTS.REPORT_HUB}/${id}`, { method: 'DELETE' })
      .then((r) => r.ok ? setReports((prev) => prev.filter((r) => r.report_id !== id)) : null)
      .catch(() => {});
  }, []);

  // derived
  const filtered = reports.filter((r) => {
    if (filterType && r.report_type !== filterType) return false;
    if (filterStatus && r.status !== filterStatus) return false;
    if (filterSearch) {
      const q = filterSearch.toLowerCase();
      const hay = `${r.title} ${(r.tags||[]).join(' ')} ${r.workflow_id||''} ${r.run_id||''}`.toLowerCase();
      if (!hay.includes(q)) return false;
    }
    return true;
  });

  const byTypeCounts = Object.entries(summary.by_type || {}).sort((a, b) => b[1] - a[1]);

  return (
    <div className="rh-page">

      {/* ── HEADER ─────────────────────────────────────────────── */}
      <div className="rh-header">
        <div className="rh-header-left">
          <span className="rh-header-icon"><i className="fas fa-clipboard-list" /></span>
          <div>
            <h1>Reporting Hub</h1>
            <p>Unified view of all reports from Migration, Lineage, Analytics, DQ, Discovery, Observability and Self-Healing</p>
          </div>
        </div>
        <div className="rh-header-right">
          {liveMode
            ? <span className="rh-live-badge"><span className="rh-live-dot" />LIVE</span>
            : <span className="rh-demo-badge"><i className="fas fa-flask" /> DEMO</span>}
          <button className="rh-btn rh-btn-secondary" onClick={loadReports} disabled={loading}>
            {loading ? <><i className="fas fa-spinner fa-spin" /> Loading…</> : <><i className="fas fa-sync-alt" /> Refresh</>}
          </button>
        </div>
      </div>

      {/* ── KPI STRIP ──────────────────────────────────────────── */}
      <div className="rh-kpi-strip">
        <KpiCard label="Total Reports" value={summary.total || 0} color="#3b82f6" icon="fas fa-clipboard-list" />
        <KpiCard label="Passing" value={summary.by_status?.pass || 0} color="#22c55e" icon="fas fa-check-circle" />
        <KpiCard label="Failing" value={summary.by_status?.fail || 0} color="#ef4444" icon="fas fa-times-circle" />
        <KpiCard label="Warnings" value={summary.by_status?.warning || 0} color="#f59e0b" icon="fas fa-exclamation-triangle" />
      </div>

      {/* ── TYPE QUICK-FILTER PILLS ─────────────────────────────── */}
      <div className="rh-type-pills-row">
        <TypePill type="" count={reports.length} active={filterType === ''} onClick={() => setFilterType('')} />
        {byTypeCounts.map(([t, n]) => (
          <TypePill key={t} type={t} count={n} active={filterType === t} onClick={() => setFilterType(filterType === t ? '' : t)} />
        ))}
      </div>

      {/* ── SEARCH + STATUS FILTER ─────────────────────────────── */}
      <div className="rh-filter-row">
        <input
          className="rh-input"
          type="text"
          placeholder="Search title, tags, workflow, run ID…"
          value={filterSearch}
          onChange={(e) => setFilterSearch(e.target.value)}
        />
        <select className="rh-select" value={filterStatus} onChange={(e) => setFilterStatus(e.target.value)}>
          <option value="">All statuses</option>
          {Object.entries(STATUS_META).map(([k, m]) => (
            <option key={k} value={k}>{m.label}</option>
          ))}
        </select>
        {(filterType || filterStatus || filterSearch) && (
          <button className="rh-btn rh-btn-ghost" onClick={() => { setFilterType(''); setFilterStatus(''); setFilterSearch(''); }}>
            <i className="fas fa-times" /> Clear
          </button>
        )}
        <span className="rh-result-count">{filtered.length} report{filtered.length !== 1 ? 's' : ''}</span>
        <div className="rh-export-actions">
          <button
            className="rh-btn rh-btn-secondary"
            onClick={() => exportReportsListAsJSON(filtered)}
            disabled={filtered.length === 0}
            title="Export all filtered reports as JSON"
          >
            <i className="fas fa-file-code" /> Export JSON
          </button>
          <button
            className="rh-btn rh-btn-secondary"
            onClick={() => exportReportsListAsCSV(filtered)}
            disabled={filtered.length === 0}
            title="Export all filtered reports as CSV"
          >
            <i className="fas fa-file-csv" /> Export CSV
          </button>
        </div>
      </div>

      {/* ── ERROR ──────────────────────────────────────────────── */}
      {error && (
        <div className="rh-alert">
          <i className="fas fa-exclamation-circle" /> {error}
          <button onClick={() => setError(null)}><i className="fas fa-times" /></button>
        </div>
      )}

      {/* ── REPORTS LIST ───────────────────────────────────────── */}
      <div className="rh-report-list">
        {filtered.length === 0 ? (
          <div className="rh-empty-state">
            <i className="fas fa-inbox rh-empty-icon" />
            <div className="rh-empty-title">No reports match the current filter</div>
          </div>
        ) : (
          filtered.map((r) => {
            const m = typeMeta(r.report_type);
            return (
              <div key={r.report_id} className="rh-report-row" onClick={() => setDetailReport(r)}>
                <div className="rh-row-type-bar" style={{ background: m.color }} />
                <div className="rh-row-icon" style={{ color: m.color }}><i className={m.icon} /></div>
                <div className="rh-row-body">
                  <div className="rh-row-title">{r.title}</div>
                  <div className="rh-row-meta">
                    <span className="rh-row-type-label" style={{ color: m.color }}>{m.label}</span>
                    {r.workflow_id && <span className="rh-row-meta-item"><i className="fas fa-project-diagram" /> {r.workflow_id}</span>}
                    {r.run_id && <span className="rh-row-meta-item"><i className="fas fa-terminal" /> {r.run_id}</span>}
                    {r.tags?.map((t) => <span key={t} className="rh-tag">{t}</span>)}
                  </div>
                  {r.summary && (
                    <div className="rh-row-summary">
                      {Object.entries(r.summary).slice(0, 4).map(([k, v]) => (
                        <span key={k} className="rh-summary-kv">
                          <span className="rh-summary-key">{k.replace(/_/g, ' ')}</span>
                          <span className="rh-summary-val">{Array.isArray(v) ? v.join(', ') : String(v)}</span>
                        </span>
                      ))}
                    </div>
                  )}
                </div>
                <div className="rh-row-right">
                  {statusBadge(r.status)}
                  <span className="rh-row-time" title={fmtDate(r.created_at)}>{fmtRelative(r.created_at)}</span>
                  <button
                    className="rh-row-export"
                    title="Export this report as JSON"
                    onClick={(e) => { e.stopPropagation(); exportReportAsJSON(r); }}
                  >
                    <i className="fas fa-download" />
                  </button>
                  {m.page && (
                    <Link to={m.page} className="rh-row-goto" title={`Open ${m.label}`} onClick={(e) => e.stopPropagation()}>
                      <i className="fas fa-external-link-alt" />
                    </Link>
                  )}
                  <button
                    className="rh-row-delete"
                    title="Delete report"
                    onClick={(e) => { e.stopPropagation(); deleteReport(r.report_id); }}
                  >
                    <i className="fas fa-trash-alt" />
                  </button>
                </div>
              </div>
            );
          })
        )}
      </div>

      {/* ── WORKFLOW CROSS-REFERENCES ────────────────────────────── */}
      {(() => {
        const workflowGroups = {};
        reports.forEach((r) => {
          if (r.workflow_id) {
            if (!workflowGroups[r.workflow_id]) workflowGroups[r.workflow_id] = [];
            workflowGroups[r.workflow_id].push(r);
          }
        });
        const entries = Object.entries(workflowGroups).filter(([, rs]) => rs.length > 1);
        if (!entries.length) return null;
        return (
          <div className="rh-card rh-xref-card">
            <div className="rh-section-header">
              <span><i className="fas fa-link" /> Workflow Cross-References</span>
              <span className="rh-section-sub">Reports grouped by workflow — trace end-to-end</span>
            </div>
            {entries.map(([wfId, rs]) => (
              <div key={wfId} className="rh-xref-group">
                <div className="rh-xref-wf-id"><i className="fas fa-project-diagram" /> {wfId}</div>
                <div className="rh-xref-items">
                  {rs.map((r) => {
                    const m = typeMeta(r.report_type);
                    return (
                      <button key={r.report_id} className="rh-xref-item" style={{ borderColor: m.color, color: m.color }} onClick={() => setDetailReport(r)}>
                        <i className={m.icon} /> {m.label}
                        <span className="rh-xref-status">{statusBadge(r.status)}</span>
                      </button>
                    );
                  })}
                </div>
              </div>
            ))}
          </div>
        );
      })()}

      {/* ── DETAIL MODAL ─────────────────────────────────────────── */}
      {detailReport && <ReportDetailModal report={detailReport} onClose={() => setDetailReport(null)} />}
    </div>
  );
}
