/**
 * File Batch Processor Page
 * Handles large-scale (thousands/lakhs of files) parallel ingestion via:
 *   1. Directory discovery  → POST /api/multimodal/discover
 *   2. Batch submission     → POST /api/multimodal/analyze-batch  (returns job_id)
 *   3. Status polling       → GET  /api/multimodal/batch-status/{job_id}
 *   4. Results + lineage    → GET  /api/multimodal/batch-results/{job_id}
 */

import React, { useState, useRef, useCallback, useEffect } from 'react';
import './FileBatchProcessorPage.css';

const API_BASE = import.meta.env.VITE_API_BASE_URL || '';

// ─── Helpers ────────────────────────────────────────────────────────────────

const FILE_TYPE_ICONS = {
  pdf: 'fas fa-file-pdf',
  image: 'fas fa-file-image',
  excel: 'fas fa-file-excel',
  word: 'fas fa-file-word',
  cad: 'fas fa-drafting-compass',
  video: 'fas fa-file-video',
  text: 'fas fa-file-alt',
  unknown: 'fas fa-file',
};

function typeIcon(ft) {
  return FILE_TYPE_ICONS[ft] || FILE_TYPE_ICONS.unknown;
}

function fmtMs(ms) {
  if (ms == null) return '—';
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

function fmtPct(n, total) {
  if (!total) return '0%';
  return `${Math.round((n / total) * 100)}%`;
}

// ─── Component ───────────────────────────────────────────────────────────────

export default function FileBatchProcessorPage() {
  // ── Step 1: Discovery inputs
  const [directory, setDirectory] = useState('');
  const [recursive, setRecursive] = useState(true);
  const [concurrency, setConcurrency] = useState(8);
  const [flushSize, setFlushSize] = useState(50);

  // ── Discovery state
  const [discovering, setDiscovering] = useState(false);
  const [manifest, setManifest] = useState(null);  // {total_files, by_type, file_paths}
  const [discoverError, setDiscoverError] = useState(null);

  // ── Batch job state
  const [submitting, setSubmitting] = useState(false);
  const [jobId, setJobId] = useState(null);
  const [jobStatus, setJobStatus] = useState(null); // {status, processed, succeeded, failed, total_files, progress_pct}
  const [jobError, setJobError] = useState(null);

  // ── Results state
  const [results, setResults] = useState([]);
  const [resultsPage, setResultsPage] = useState(0);
  const [resultsTotal, setResultsTotal] = useState(null);
  const [resultsFilter, setResultsFilter] = useState({ file_type: '', success_only: false });
  const [loadingResults, setLoadingResults] = useState(false);

  const pollRef = useRef(null);
  const PAGE_SIZE = 25;

  // ── Stop polling on unmount
  useEffect(() => () => clearInterval(pollRef.current), []);

  // ────────────────────────────────────────────────────────────────────────────
  // Step 1: Discover files in a directory
  // ────────────────────────────────────────────────────────────────────────────
  const handleDiscover = useCallback(async () => {
    if (!directory.trim()) return;
    setDiscovering(true);
    setDiscoverError(null);
    setManifest(null);
    setJobId(null);
    setJobStatus(null);
    setResults([]);
    try {
      const res = await fetch(`${API_BASE}/api/multimodal/discover`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ directory: directory.trim(), recursive }),
      });
      if (!res.ok) throw new Error(`Discovery failed: ${res.status} ${res.statusText}`);
      const data = await res.json();
      setManifest(data);
    } catch (err) {
      setDiscoverError(err.message);
    } finally {
      setDiscovering(false);
    }
  }, [directory, recursive]);

  // ────────────────────────────────────────────────────────────────────────────
  // Step 2: Submit batch job
  // ────────────────────────────────────────────────────────────────────────────
  // Step 4: Fetch paged results  (defined first — used by startPolling below)
  // ────────────────────────────────────────────────────────────────────────────
  const fetchResults = useCallback(async (jid, page, filter) => {
    setLoadingResults(true);
    try {
      const params = new URLSearchParams({
        skip: page * PAGE_SIZE,
        limit: PAGE_SIZE,
        ...(filter.file_type ? { file_type: filter.file_type } : {}),
        ...(filter.success_only ? { success_only: 'true' } : {}),
      });
      const res = await fetch(`${API_BASE}/api/multimodal/batch-results/${jid}?${params}`);
      if (!res.ok) throw new Error(`Failed to load results: ${res.status}`);
      const data = await res.json();
      setResults(data.results || []);
      setResultsTotal(data.total);
      setResultsPage(page);
    } catch (err) {
      console.error(err);
    } finally {
      setLoadingResults(false);
    }
  }, []);

  // ────────────────────────────────────────────────────────────────────────────
  // Step 3: Poll job status
  // ────────────────────────────────────────────────────────────────────────────
  const startPolling = useCallback((jid) => {
    clearInterval(pollRef.current);
    pollRef.current = setInterval(async () => {
      try {
        const res = await fetch(`${API_BASE}/api/multimodal/batch-status/${jid}`);
        if (!res.ok) return;
        const data = await res.json();
        setJobStatus(data);
        if (data.status === 'completed' || data.status === 'failed') {
          clearInterval(pollRef.current);
          if (data.status === 'completed') {
            fetchResults(jid, 0, { file_type: '', success_only: false });
          }
        }
      } catch (_) {/* keep polling */}
    }, 2000);
  }, [fetchResults]);

  // ────────────────────────────────────────────────────────────────────────────
  const handleSubmitBatch = useCallback(async () => {
    if (!manifest) return;
    setSubmitting(true);
    setJobError(null);
    setJobId(null);
    setJobStatus(null);
    setResults([]);
    try {
      const res = await fetch(`${API_BASE}/api/multimodal/analyze-batch`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          file_paths: manifest.file_paths,
          concurrency,
          db_flush_size: flushSize,
        }),
      });
      if (!res.ok) throw new Error(`Batch submission failed: ${res.status} ${res.statusText}`);
      const data = await res.json();
      setJobId(data.job_id);
      // For small inline jobs (≤20 files) the backend returns results directly
      if (data.status === 'completed' && Array.isArray(data.results)) {
        setResults(data.results);
        setResultsTotal(data.results.length);
        setJobStatus({ status: 'completed', processed: data.results.length, succeeded: data.succeeded, failed: data.failed, total_files: data.results.length, progress_pct: 100 });
      } else {
        startPolling(data.job_id);
      }
    } catch (err) {
      setJobError(err.message);
    } finally {
      setSubmitting(false);
    }
  }, [manifest, concurrency, flushSize, startPolling]);

  const handleFilterChange = (newFilter) => {
    const f = { ...resultsFilter, ...newFilter };
    setResultsFilter(f);
    if (jobId) fetchResults(jobId, 0, f);
  };

  const handlePageChange = (page) => {
    if (jobId) fetchResults(jobId, page, resultsFilter);
  };

  // ── Derived
  const totalPages = resultsTotal != null ? Math.ceil(resultsTotal / PAGE_SIZE) : 0;
  const isRunning = jobStatus && (jobStatus.status === 'running' || jobStatus.status === 'pending');
  const isComplete = jobStatus && jobStatus.status === 'completed';
  const isFailed = jobStatus && jobStatus.status === 'failed';

  // ────────────────────────────────────────────────────────────────────────────
  // Render
  // ────────────────────────────────────────────────────────────────────────────
  return (
    <div className="fbp-page">

      {/* ── Header ── */}
      <div className="fbp-header">
        <h1><i className="fas fa-layer-group" /> Batch File Processor</h1>
        <p>
          Discover, classify and process thousands of files in parallel — with Neo4j genealogy
          tracking and per-file result reporting.
        </p>
        <div className="fbp-header-pills">
          <span className="fbp-pill"><i className="fas fa-bolt" /> Async parallel ingestion</span>
          <span className="fbp-pill"><i className="fas fa-project-diagram" /> Neo4j lineage graph</span>
          <span className="fbp-pill"><i className="fas fa-database" /> Postgres result store</span>
          <span className="fbp-pill"><i className="fas fa-search-plus" /> Directory discovery</span>
        </div>
      </div>

      <div className="fbp-main">

        {/* ═══════════════════════════════════════════════════════════════════ */}
        {/* Panel 1 — Discovery                                                 */}
        {/* ═══════════════════════════════════════════════════════════════════ */}
        <section className="fbp-panel">
          <div className="fbp-panel-title">
            <i className="fas fa-search" />
            <span>Step 1 — Discover Files</span>
          </div>

          <div className="fbp-form-row">
            <label className="fbp-label">Directory path</label>
            <input
              className="fbp-input"
              type="text"
              placeholder="/mnt/data/uploads  or  C:\data\files"
              value={directory}
              onChange={e => setDirectory(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleDiscover()}
            />
          </div>

          <div className="fbp-form-row fbp-form-row--inline">
            <label className="fbp-checkbox-label">
              <input type="checkbox" checked={recursive} onChange={e => setRecursive(e.target.checked)} />
              Recursive (include subdirectories)
            </label>
          </div>

          <div className="fbp-form-row fbp-form-row--inline">
            <div className="fbp-field-group">
              <label className="fbp-label">Concurrency</label>
              <input className="fbp-input fbp-input--sm" type="number" min={1} max={32} value={concurrency} onChange={e => setConcurrency(Number(e.target.value))} />
              <span className="fbp-help">parallel workers</span>
            </div>
            <div className="fbp-field-group">
              <label className="fbp-label">Flush size</label>
              <input className="fbp-input fbp-input--sm" type="number" min={10} max={500} value={flushSize} onChange={e => setFlushSize(Number(e.target.value))} />
              <span className="fbp-help">files per DB flush</span>
            </div>
          </div>

          <button
            className="fbp-btn fbp-btn--primary"
            onClick={handleDiscover}
            disabled={discovering || !directory.trim()}
          >
            {discovering
              ? <><i className="fas fa-spinner fa-spin" /> Scanning…</>
              : <><i className="fas fa-folder-open" /> Discover Files</>}
          </button>

          {discoverError && (
            <div className="fbp-alert fbp-alert--error">
              <i className="fas fa-exclamation-circle" /> {discoverError}
            </div>
          )}
        </section>

        {/* ═══════════════════════════════════════════════════════════════════ */}
        {/* Panel 2 — Manifest                                                  */}
        {/* ═══════════════════════════════════════════════════════════════════ */}
        {manifest && (
          <section className="fbp-panel">
            <div className="fbp-panel-title">
              <i className="fas fa-list-alt" />
              <span>Step 2 — Review Manifest &amp; Submit</span>
            </div>

            <div className="fbp-manifest-summary">
              <div className="fbp-stat-card">
                <div className="fbp-stat-value">{manifest.total_files.toLocaleString()}</div>
                <div className="fbp-stat-label">Total files</div>
              </div>
              {Object.entries(manifest.by_type || {}).map(([ft, count]) => (
                <div key={ft} className="fbp-stat-card">
                  <div className="fbp-stat-value">
                    <i className={typeIcon(ft)} style={{ marginRight: 6 }} />
                    {count.toLocaleString()}
                  </div>
                  <div className="fbp-stat-label">{ft.toUpperCase()}</div>
                </div>
              ))}
            </div>

            {manifest.total_files === 0 ? (
              <div className="fbp-alert fbp-alert--warn">
                <i className="fas fa-exclamation-triangle" /> No files found in that directory.
              </div>
            ) : (
              <button
                className="fbp-btn fbp-btn--success"
                onClick={handleSubmitBatch}
                disabled={submitting || isRunning}
              >
                {submitting
                  ? <><i className="fas fa-spinner fa-spin" /> Submitting…</>
                  : <><i className="fas fa-play-circle" /> Process {manifest.total_files.toLocaleString()} Files</>}
              </button>
            )}

            {jobError && (
              <div className="fbp-alert fbp-alert--error">
                <i className="fas fa-exclamation-circle" /> {jobError}
              </div>
            )}
          </section>
        )}

        {/* ═══════════════════════════════════════════════════════════════════ */}
        {/* Panel 3 — Progress                                                  */}
        {/* ═══════════════════════════════════════════════════════════════════ */}
        {jobId && jobStatus && (
          <section className="fbp-panel">
            <div className="fbp-panel-title">
              <i className={isRunning ? 'fas fa-spinner fa-spin' : isComplete ? 'fas fa-check-circle' : 'fas fa-times-circle'} />
              <span>Step 3 — Job Progress</span>
              <span className={`fbp-status-badge fbp-status-badge--${jobStatus.status}`}>{jobStatus.status}</span>
            </div>

            <div className="fbp-progress-bar-wrap">
              <div className="fbp-progress-bar" style={{ width: `${jobStatus.progress_pct ?? 0}%` }} />
            </div>
            <div className="fbp-progress-legend">
              <span>{jobStatus.progress_pct ?? 0}% complete</span>
              <span>{(jobStatus.processed ?? 0).toLocaleString()} / {(jobStatus.total_files ?? manifest?.total_files ?? '?').toLocaleString()} files</span>
            </div>

            <div className="fbp-manifest-summary" style={{ marginTop: 16 }}>
              <div className="fbp-stat-card fbp-stat-card--ok">
                <div className="fbp-stat-value"><i className="fas fa-check" /> {(jobStatus.succeeded ?? 0).toLocaleString()}</div>
                <div className="fbp-stat-label">Succeeded</div>
              </div>
              <div className="fbp-stat-card fbp-stat-card--err">
                <div className="fbp-stat-value"><i className="fas fa-times" /> {(jobStatus.failed ?? 0).toLocaleString()}</div>
                <div className="fbp-stat-label">Failed</div>
              </div>
              <div className="fbp-stat-card">
                <div className="fbp-stat-value fbp-mono">{jobId.slice(0, 8)}…</div>
                <div className="fbp-stat-label">Job ID</div>
              </div>
            </div>

            {isFailed && (
              <div className="fbp-alert fbp-alert--error">
                <i className="fas fa-exclamation-circle" /> Job failed on the server.
              </div>
            )}
          </section>
        )}

        {/* ═══════════════════════════════════════════════════════════════════ */}
        {/* Panel 4 — Results                                                   */}
        {/* ═══════════════════════════════════════════════════════════════════ */}
        {(isComplete || results.length > 0) && (
          <section className="fbp-panel fbp-panel--results">
            <div className="fbp-panel-title">
              <i className="fas fa-table" />
              <span>Step 4 — Results</span>
              {resultsTotal != null && (
                <span className="fbp-count-badge">{resultsTotal.toLocaleString()} records</span>
              )}
            </div>

            {/* Filters */}
            <div className="fbp-filter-bar">
              <select
                className="fbp-select"
                value={resultsFilter.file_type}
                onChange={e => handleFilterChange({ file_type: e.target.value })}
              >
                <option value="">All file types</option>
                {Object.keys(manifest?.by_type || {}).map(ft => (
                  <option key={ft} value={ft}>{ft.toUpperCase()}</option>
                ))}
              </select>
              <label className="fbp-checkbox-label">
                <input
                  type="checkbox"
                  checked={resultsFilter.success_only}
                  onChange={e => handleFilterChange({ success_only: e.target.checked })}
                />
                Successes only
              </label>
            </div>

            {/* Table */}
            <div className="fbp-table-wrap">
              {loadingResults ? (
                <div className="fbp-loading"><i className="fas fa-spinner fa-spin" /> Loading…</div>
              ) : results.length === 0 ? (
                <div className="fbp-empty">No results match the current filter.</div>
              ) : (
                <table className="fbp-table">
                  <thead>
                    <tr>
                      <th>File</th>
                      <th>Type</th>
                      <th>Status</th>
                      <th>Time</th>
                      <th>Preview</th>
                    </tr>
                  </thead>
                  <tbody>
                    {results.map((r, idx) => (
                      <ResultRow key={r.path || idx} row={r} />
                    ))}
                  </tbody>
                </table>
              )}
            </div>

            {/* Pagination */}
            {totalPages > 1 && (
              <div className="fbp-pagination">
                <button
                  className="fbp-btn fbp-btn--sm"
                  disabled={resultsPage === 0}
                  onClick={() => handlePageChange(resultsPage - 1)}
                >
                  <i className="fas fa-chevron-left" /> Prev
                </button>
                <span className="fbp-page-info">
                  Page {resultsPage + 1} of {totalPages}
                  {' '}({fmtPct((resultsPage + 1) * PAGE_SIZE, resultsTotal)} of file results)
                </span>
                <button
                  className="fbp-btn fbp-btn--sm"
                  disabled={resultsPage >= totalPages - 1}
                  onClick={() => handlePageChange(resultsPage + 1)}
                >
                  Next <i className="fas fa-chevron-right" />
                </button>
              </div>
            )}
          </section>
        )}

      </div>
    </div>
  );
}

// ─── Result row sub-component ────────────────────────────────────────────────

function ResultRow({ row }) {
  const [expanded, setExpanded] = useState(false);
  const filename = row.path ? row.path.split(/[\\/]/).pop() : '—';
  return (
    <>
      <tr
        className={`fbp-tr ${row.success ? 'fbp-tr--ok' : 'fbp-tr--err'}`}
        onClick={() => setExpanded(e => !e)}
        style={{ cursor: 'pointer' }}
      >
        <td className="fbp-td fbp-td--file">
          <i className={typeIcon(row.file_type)} style={{ marginRight: 6, color: '#0066cc' }} />
          <span className="fbp-filename" title={row.path}>{filename}</span>
        </td>
        <td className="fbp-td fbp-td--type">{row.file_type || '—'}</td>
        <td className="fbp-td fbp-td--status">
          {row.success
            ? <span className="fbp-badge fbp-badge--ok"><i className="fas fa-check" /> OK</span>
            : <span className="fbp-badge fbp-badge--err"><i className="fas fa-times" /> Error</span>}
        </td>
        <td className="fbp-td fbp-td--time">{fmtMs(row.processing_time_ms)}</td>
        <td className="fbp-td fbp-td--preview">
          {row.text_content
            ? <span className="fbp-preview-text">{row.text_content.slice(0, 80)}…</span>
            : row.error
              ? <span className="fbp-error-text">{row.error.slice(0, 80)}</span>
              : '—'}
        </td>
      </tr>
      {expanded && (
        <tr className="fbp-tr-detail">
          <td colSpan={5}>
            <div className="fbp-detail-panel">
              <div className="fbp-detail-path"><strong>Path:</strong> {row.path}</div>
              {row.error && (
                <div className="fbp-detail-error"><strong>Error:</strong> {row.error}</div>
              )}
              {row.text_content && (
                <div className="fbp-detail-section">
                  <strong>Extracted text</strong>
                  <pre className="fbp-pre">{row.text_content.slice(0, 2000)}{row.text_content.length > 2000 ? '\n…' : ''}</pre>
                </div>
              )}
              {row.metadata && Object.keys(row.metadata).length > 0 && (
                <div className="fbp-detail-section">
                  <strong>Metadata</strong>
                  <pre className="fbp-pre">{JSON.stringify(row.metadata, null, 2)}</pre>
                </div>
              )}
              {row.extracted_data && Object.keys(row.extracted_data).length > 0 && (
                <div className="fbp-detail-section">
                  <strong>Extracted data</strong>
                  <pre className="fbp-pre">{JSON.stringify(row.extracted_data, null, 2)}</pre>
                </div>
              )}
            </div>
          </td>
        </tr>
      )}
    </>
  );
}
