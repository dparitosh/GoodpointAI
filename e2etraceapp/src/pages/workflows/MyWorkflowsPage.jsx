import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import API_CONFIG from '../../config/api-config';
import { apiClient } from '../../utils/apiClient';
import './MyWorkflowsPage.css';

// ─── helpers ────────────────────────────────────────────────────────────────

const STATUS_META = {
  configured:  { label: 'Configured',  cls: 'status-configured'  },
  running:     { label: 'Running',      cls: 'status-running'     },
  completed:   { label: 'Completed',   cls: 'status-completed'   },
  failed:      { label: 'Failed',      cls: 'status-failed'      },
  paused:      { label: 'Paused',      cls: 'status-paused'      },
  cancelled:   { label: 'Cancelled',  cls: 'status-cancelled'   },
};

const SOURCE_ICONS = {
  teamcenter:  'fas fa-sitemap',
  windchill:   'fas fa-wind',
  filesystem:  'fas fa-folder-open',
  database:    'fas fa-database',
  plm:         'fas fa-cube',
  csv:         'fas fa-file-csv',
  default:     'fas fa-plug',
};

const TARGET_ICONS = {
  neo4j:       'fas fa-project-diagram',
  opensearch:  'fas fa-search',
  database:    'fas fa-database',
  default:     'fas fa-bullseye',
};

function statusMeta(status) {
  return STATUS_META[(status || '').toLowerCase()] || { label: status || 'Unknown', cls: 'status-unknown' };
}

function iconFor(map, type) {
  return map[(type || '').toLowerCase()] || map.default;
}

function fmtDate(iso) {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' });
  } catch {
    return iso;
  }
}

// ─── empty state ─────────────────────────────────────────────────────────────

function EmptyState({ onNew }) {
  return (
    <div className="mwp-empty">
      <i className="fas fa-exchange-alt mwp-empty-icon" />
      <h3>No workflows yet</h3>
      <p>Create your first migration workflow to get started.</p>
      <button className="btn-primary" onClick={onNew}>
        <i className="fas fa-plus" /> New Migration
      </button>
    </div>
  );
}

// ─── workflow row ────────────────────────────────────────────────────────────

function WorkflowRow({ wf, onOpen, onExecute, executing }) {
  const { label, cls } = statusMeta(wf.status);
  const pct = Math.round(wf.progress_percentage || 0);
  const srcIcon = iconFor(SOURCE_ICONS, wf.source_type);
  const tgtIcon = iconFor(TARGET_ICONS, wf.target_type);
  const canRun = ['configured', 'completed', 'failed', 'cancelled'].includes((wf.status || '').toLowerCase());

  return (
    <tr className="mwp-row" onClick={() => onOpen(wf)}>
      <td className="mwp-col-name">
        <span className="mwp-row-name" title={wf.name}>{wf.name}</span>
        {wf.description && <span className="mwp-row-desc">{wf.description}</span>}
      </td>
      <td className="mwp-col-pipeline">
        <span className="mwp-pipeline-node"><i className={srcIcon} /> {wf.source_name || wf.source_type || '—'}</span>
        <span className="mwp-pipeline-arrow"><i className="fas fa-arrow-right" /></span>
        <span className="mwp-pipeline-node"><i className={tgtIcon} /> {wf.target_name || wf.target_type || '—'}</span>
      </td>
      <td className="mwp-col-status">
        <span className={`mwp-status-badge ${cls}`}>{label}</span>
        {wf.status === 'running' && (
          <div className="mwp-progress-bar">
            <div className="mwp-progress-fill" style={{ width: `${pct}%` }} />
            <span className="mwp-progress-label">{pct}%</span>
          </div>
        )}
      </td>
      <td className="mwp-col-date">{fmtDate(wf.created_at)}</td>
      <td className="mwp-col-by">{wf.created_by || '—'}</td>
      <td className="mwp-col-actions" onClick={e => e.stopPropagation()}>
        {canRun && (
          <button className="btn-run" title="Execute" onClick={() => onExecute(wf.id)} disabled={executing === wf.id}>
            <i className={executing === wf.id ? 'fas fa-spinner fa-spin' : 'fas fa-play'} />
          </button>
        )}
        <button className="btn-open" onClick={() => onOpen(wf)}>
          <i className="fas fa-arrow-right" /> Open
        </button>
      </td>
    </tr>
  );
}

// ─── page ────────────────────────────────────────────────────────────────────

export default function MyWorkflowsPage() {
  const navigate = useNavigate();
  const [workflows, setWorkflows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [search, setSearch] = useState('');
  const [filterStatus, setFilterStatus] = useState('all');
  const [executing, setExecuting] = useState(null);
  const [validating, setValidating] = useState(false);
  const [validateResult, setValidateResult] = useState(null); // null | { summary, orphaned, partial, deleted_ids, dry_run }

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await apiClient.get(API_CONFIG.ENDPOINTS.WORKFLOWS + '/');
      setWorkflows(Array.isArray(data) ? data : []);
    } catch (err) {
      setError(err.message || 'Failed to load workflows');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleExecute = useCallback(async (workflowId) => {
    setExecuting(workflowId);
    try {
      await apiClient.post(`/api/workflows/${workflowId}/execute`);
      navigate(`/workflow/${workflowId}`);
    } catch (err) {
      alert(`Could not execute workflow: ${err.message}`);
    } finally {
      setExecuting(null);
    }
  }, [navigate]);

  const handleValidate = useCallback(async (dryRun = true) => {
    setValidating(true);
    if (!dryRun) setValidateResult(null);
    try {
      const data = await apiClient.post(
        `${API_CONFIG.ENDPOINTS.WORKFLOW_VALIDATE_SOURCES}?dry_run=${dryRun}`
      );
      setValidateResult(data);
      if (!dryRun && data.summary?.deleted > 0) {
        // Reload list — orphaned entries have been deleted
        await load();
      }
    } catch (err) {
      setValidateResult({ _error: err.message || 'Validation failed' });
    } finally {
      setValidating(false);
    }
  }, [load]);

  const handleDismissValidate = useCallback(() => setValidateResult(null), []);

  const handleOpen = useCallback((wf) => {
    const resumable = ['configured', 'paused'].includes((wf.status || '').toLowerCase());
    if (resumable) {
      navigate(`/migration?resumeWorkflowId=${encodeURIComponent(wf.id)}`);
    } else {
      navigate(`/workflow/${wf.id}`);
    }
  }, [navigate]);

  const statusOptions = ['all', ...Object.keys(STATUS_META)];

  const visible = useMemo(() => {
    const q = search.toLowerCase();
    return workflows.filter(wf => {
      const matchSearch = !q
        || (wf.name || '').toLowerCase().includes(q)
        || (wf.description || '').toLowerCase().includes(q)
        || (wf.source_name || '').toLowerCase().includes(q)
        || (wf.target_name || '').toLowerCase().includes(q);
      const matchStatus = filterStatus === 'all' || (wf.status || '').toLowerCase() === filterStatus;
      return matchSearch && matchStatus;
    });
  }, [workflows, search, filterStatus]);

  return (
    <div className="mwp-page">
      {/* ── Page header ── */}
      <div className="mwp-header">
        <div className="mwp-header-left">
          <h1 className="mwp-title">
            <i className="fas fa-exchange-alt" /> My Workflows
          </h1>
          <p className="mwp-subtitle">All migration and data pipeline workflows</p>
        </div>
        <div className="mwp-header-right">
          <button className="btn-icon" title="Refresh" onClick={load} disabled={loading}>
            <i className={`fas fa-sync-alt ${loading ? 'fa-spin' : ''}`} />
          </button>
          <button
            className="btn-icon"
            title="Validate data sources — check which workflows have unregistered source/target and remove orphaned ones"
            onClick={() => handleValidate(true)}
            disabled={validating || loading}
          >
            <i className={`fas fa-check-double ${validating ? 'fa-spin' : ''}`} />
          </button>
          <button className="btn-primary" onClick={() => navigate('/migration')}>
            <i className="fas fa-plus" /> New Migration
          </button>
        </div>
      </div>

      {/* ── Validation result panel ── */}
      {validateResult && (
        <div className={`mwp-validate-panel ${
          validateResult._error ? 'mwp-validate-error'
          : validateResult.summary?.orphaned > 0 ? 'mwp-validate-warn'
          : 'mwp-validate-ok'
        }`}>
          <div className="mwp-validate-header">
            <span className="mwp-validate-title">
              <i className={`fas ${
                validateResult._error ? 'fa-times-circle'
                : validateResult.summary?.orphaned > 0 ? 'fa-exclamation-triangle'
                : 'fa-check-circle'
              }`} />
              {validateResult._error
                ? ` Validation error: ${validateResult._error}`
                : validateResult.dry_run
                  ? ' Validation preview'
                  : ` Validation complete — ${validateResult.summary?.deleted ?? 0} workflow(s) deleted`
              }
            </span>
            <button className="mwp-validate-dismiss" onClick={handleDismissValidate}>
              <i className="fas fa-times" />
            </button>
          </div>

          {!validateResult._error && (
            <>
              <div className="mwp-validate-summary">
                <span className="mwp-vs-chip mwp-vs-ok"><i className="fas fa-check" /> {validateResult.summary?.valid ?? 0} valid</span>
                <span className="mwp-vs-chip mwp-vs-warn"><i className="fas fa-exclamation" /> {validateResult.summary?.partial ?? 0} partial</span>
                <span className="mwp-vs-chip mwp-vs-bad"><i className="fas fa-unlink" /> {validateResult.summary?.orphaned ?? 0} orphaned</span>
                {validateResult.summary?.skipped_running > 0 && (
                  <span className="mwp-vs-chip mwp-vs-skip"><i className="fas fa-running" /> {validateResult.summary.skipped_running} skipped (running)</span>
                )}
              </div>

              {validateResult.summary?.orphaned > 0 && validateResult.dry_run && (
                <>
                  <div className="mwp-validate-orphan-list">
                    <strong>Orphaned workflows (both source and target unregistered):</strong>
                    <ul>
                      {(validateResult.orphaned_workflows || []).map(wf => (
                        <li key={wf.id}>
                          <span className="mwp-vo-name">{wf.name || wf.id}</span>
                          <span className="mwp-vo-ids">
                            source: <code>{wf.source_id}</code> · target: <code>{wf.target_id}</code>
                          </span>
                        </li>
                      ))}
                    </ul>
                  </div>
                  <div className="mwp-validate-actions">
                    <button
                      className="btn-danger"
                      onClick={() => handleValidate(false)}
                      disabled={validating}
                    >
                      <i className={`fas ${validating ? 'fa-spinner fa-spin' : 'fa-trash'}`} />
                      Delete {validateResult.summary.orphaned} orphaned workflow(s)
                    </button>
                    <button className="btn-link" onClick={handleDismissValidate}>Cancel</button>
                  </div>
                </>
              )}

              {validateResult.summary?.partial > 0 && (
                <div className="mwp-validate-partial-list">
                  <strong>Partially registered (one side missing — not deleted):</strong>
                  <ul>
                    {(validateResult.partial_workflows || []).map(wf => (
                      <li key={wf.id}>
                        <span className="mwp-vo-name">{wf.name || wf.id}</span>
                        <span className="mwp-vo-ids">
                          source: <code className={wf.source_registered ? '' : 'mwp-vo-missing'}>{wf.source_id}</code>
                          {' · '}
                          target: <code className={wf.target_registered ? '' : 'mwp-vo-missing'}>{wf.target_id}</code>
                        </span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </>
          )}
        </div>
      )}

      {/* ── Toolbar ── */}
      <div className="mwp-toolbar">
        <div className="mwp-search-wrap">
          <i className="fas fa-search mwp-search-icon" />
          <input
            className="mwp-search"
            type="text"
            placeholder="Search by name, source, or target…"
            value={search}
            onChange={e => setSearch(e.target.value)}
          />
          {search && (
            <button className="mwp-search-clear" onClick={() => setSearch('')}>
              <i className="fas fa-times" />
            </button>
          )}
        </div>

        <div className="mwp-filter-row">
          {statusOptions.map(s => (
            <button
              key={s}
              className={`mwp-filter-chip ${filterStatus === s ? 'active' : ''}`}
              onClick={() => setFilterStatus(s)}
            >
              {s === 'all' ? 'All' : (STATUS_META[s]?.label || s)}
            </button>
          ))}
        </div>

        <span className="mwp-count">
          {visible.length} of {workflows.length} workflow{workflows.length !== 1 ? 's' : ''}
        </span>
      </div>

      {/* ── Body ── */}
      {loading ? (
        <div className="mwp-loading">
          <i className="fas fa-spinner fa-spin" />
          <span>Loading workflows…</span>
        </div>
      ) : error ? (
        <div className="mwp-error">
          <i className="fas fa-exclamation-circle" />
          <span>{error}</span>
          <button className="btn-primary" onClick={load}>Retry</button>
        </div>
      ) : visible.length === 0 && workflows.length === 0 ? (
        <EmptyState onNew={() => navigate('/migration')} />
      ) : visible.length === 0 ? (
        <div className="mwp-no-match">
          <i className="fas fa-filter" />
          <span>No workflows match your filters.</span>
          <button className="btn-link" onClick={() => { setSearch(''); setFilterStatus('all'); }}>
            Clear filters
          </button>
        </div>
      ) : (
        <div className="mwp-table-wrap">
          <table className="mwp-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Pipeline</th>
                <th>Status</th>
                <th>Created</th>
                <th>By</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {visible.map(wf => (
                <WorkflowRow
                  key={wf.id}
                  wf={wf}
                  onOpen={handleOpen}
                  onExecute={handleExecute}
                  executing={executing}
                />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
