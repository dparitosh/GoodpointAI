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

import React, { useState, useCallback, useEffect } from 'react';
import { API_CONFIG } from '../../config/api-config.js';
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
          { name: 'supplier_data.xlsx', path: '/data/suppliers/supplier_data.xlsx', file_type: 'xlsx', size_bytes: 512000, row_count: 876, column_count: 12, null_rate: 8.3, profile: {} },
          { name: 'contacts.csv',       path: '/data/suppliers/contacts.csv',       file_type: 'csv',  size_bytes: 65536,  row_count: 244, column_count: 7,  null_rate: 5.1, profile: {} },
          { name: 'agreements.json',    path: '/data/suppliers/agreements.json',    file_type: 'json', size_bytes: 43008,  row_count: 38,  column_count: 9,  null_rate: 0,   profile: {} },
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

function ProfileRow({ file }) {
  const [expanded, setExpanded] = useState(false);
  const hasProfile = file.profile && Object.keys(file.profile).length > 0;
  return (
    <>
      <tr className={expanded ? 'dd-row-expanded' : ''}>
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
              <button className="dd-expand-btn" onClick={() => setExpanded(!expanded)}>
                {expanded ? 'Hide' : 'Profile'}
              </button>
            )
            : <span className="dd-no-profile">—</span>}
        </td>
      </tr>
      {expanded && hasProfile && (
        <tr className="dd-profile-row">
          <td colSpan={7}>
            <div className="dd-profile-panel">
              <div className="dd-profile-cols">
                {Object.entries(file.profile).map(([col, stats]) => (
                  <div key={col} className="dd-col-stat">
                    <div className="dd-col-name">{col}</div>
                    <div className="dd-col-meta">
                      {stats.type && <span className="dd-col-type">{stats.type}</span>}
                      {stats.null_rate != null && (
                        <span className="dd-col-null">
                          {stats.null_rate.toFixed(0)}% null
                        </span>
                      )}
                    </div>
                    {stats.sample && (
                      <div className="dd-col-samples">
                        {stats.sample.slice(0, 3).map((v, i) => (
                          <span key={i} className="dd-sample-val">{String(v)}</span>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          </td>
        </tr>
      )}
    </>
  );
}

// ─── Main Component ──────────────────────────────────────────────────────────

export default function DataDiscoveryPage() {
  // ── Source selection
  const [sources, setSources]             = useState([]);
  const [selectedSourceId, setSelected]   = useState('');
  const [folderPath, setFolderPath]       = useState('');
  const [recursive, setRecursive]         = useState(true);

  // ── Live vs demo mode (false = showing demo seed data)
  const [liveMode, setLiveMode]           = useState(false);

  // ── Discovery state
  const [status, setStatus]               = useState('done'); // idle | running | done | error
  const [result, setResult]               = useState(DEMO_RESULT);
  const [error, setError]                 = useState(null);

  // ── Saved reports (past runs)
  const [savedReports, setSavedReports]   = useState(DEMO_PAST_RUNS);
  const [activeReportId, setActiveReportId] = useState(null);

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
    fetch(`${API_BASE}${API_CONFIG.ENDPOINTS.AGENTIC_DISCOVERY}/reports`)
      .then((r) => r.ok ? r.json() : [])
      .then((data) => { if (Array.isArray(data) && data.length > 0) setSavedReports(data); })
      .catch(() => {}); // retain demo data on fetch error
  }, []);

  // Load registered folder datasources + saved reports on mount
  useEffect(() => {
    fetch(`${API_BASE}/api/data-sources`)
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
      })
      .catch(() => setSources([]));
    loadSavedReports();
  }, [loadSavedReports]);

  // Restore a past saved report into the active view
  const restoreReport = useCallback((saved) => {
    setResult(saved.result);
    setStatus('done');
    setActiveReportId(saved.report_id);
    setScanResult(null);
    setScanError(null);
    setError(null);
  }, []);

  const runDiscovery = useCallback(async () => {
    if (!selectedSourceId && !folderPath.trim()) return;
    setStatus('running');
    setResult(null);
    setError(null);
    setScanResult(null);
    setScanError(null);
    setActiveReportId(null);

    const selectedSource = sources.find((s) => s.id === selectedSourceId);
    const resolvedPath = selectedSource
      ? (selectedSource.connection?.folder_path || selectedSource.connection?.file_path || selectedSource.connection?.connection_string || '')
      : folderPath.trim();
    const body = {
      source_id: selectedSourceId || undefined,
      folder_path: resolvedPath || undefined,
      recursive,
      include_profiling: true,
      save_report: true,
    };

    try {
      const res = await fetch(`${API_BASE}${API_CONFIG.ENDPOINTS.AGENTIC_DISCOVERY}`, {
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
  }, [selectedSourceId, folderPath, recursive, loadSavedReports]);

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
      const res = await fetch(`${API_BASE}${API_CONFIG.ENDPOINTS.AGENTIC_QUALITY_SCAN}`, {
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
          ? 'Cannot reach the backend (port 8011). Start the backend server and try again.'
          : msg
      );
    } finally {
      setScanning(false);
    }
  }, [selectedSourceId, folderPath]);

  // ── Derive display data from result
  const taskResult = result?.result || result || {};
  const files = Array.isArray(taskResult.files) ? taskResult.files
    : Array.isArray(taskResult.discovered_files) ? taskResult.discovered_files
    : [];
  const byType = taskResult.by_type || taskResult.file_types || {};
  const catalog = taskResult.catalog || {};

  const fileTypes = [...new Set(files.map((f) => f.file_type).filter(Boolean))];
  const filtered = files.filter((f) => {
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

  const totalSize = files.reduce((s, f) => s + (f.size_bytes || 0), 0);
  const nullRateFiles = files.filter((f) => f.null_rate != null);
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
            disabled={status === 'running' || (!selectedSourceId && !folderPath.trim())}
          >
            {status === 'running'
              ? <><i className="fas fa-spinner fa-spin" /> Discovering…</>
              : <><i className="fas fa-play" /> Discover</>}
          </button>
        </div>
      </div>

      {/* ── SOURCE SELECTOR ─────────────────────────────────────── */}
      <div className="dd-card dd-source-card">
        <div className="dd-source-row">
          <div className="dd-source-group">
            <label className="dd-label">Registered Folder Source</label>
            <select
              className="dd-select"
              value={selectedSourceId}
              onChange={(e) => { setSelected(e.target.value); setFolderPath(''); }}
            >
              <option value="">— select a registered source —</option>
              {sources.map((s) => (
                <option key={s.id} value={s.id}>{s.name} ({s.connection?.folder_path || s.connection?.file_path || s.connection?.connection_string || s.folder_path || s.id})</option>
              ))}
            </select>
          </div>
          <div className="dd-source-divider">or</div>
          <div className="dd-source-group dd-source-group-flex">
            <label className="dd-label">Folder Path</label>
            <input
              className="dd-input"
              type="text"
              placeholder="e.g. /data/uploads or C:\data\csv"
              value={selectedSourceId
                ? (sources.find((s) => s.id === selectedSourceId)?.connection?.folder_path
                  || sources.find((s) => s.id === selectedSourceId)?.connection?.file_path
                  || sources.find((s) => s.id === selectedSourceId)?.connection?.connection_string
                  || '')
                : folderPath}
              onChange={(e) => { setFolderPath(e.target.value); setSelected(''); }}
              disabled={!!selectedSourceId}
            />
          </div>
          <label className="dd-checkbox-label">
            <input type="checkbox" checked={recursive} onChange={(e) => setRecursive(e.target.checked)} />
            Recursive
          </label>
        </div>
      </div>

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
              value={fmtNum(files.length)}
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
              <span><i className="fas fa-list" /> Files ({filtered.length}{filtered.length !== files.length ? ` / ${files.length}` : ''})</span>
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
                    : sorted.map((f, i) => <ProfileRow key={f.path || i} file={f} />)}
                </tbody>
              </table>
            </div>
          </div>
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
