import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import API_CONFIG from '../../config/api-config';
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
    <tr className="mwp-row" onClick={() => onOpen(wf.id)}>
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
        <button className="btn-open" onClick={() => onOpen(wf.id)}>
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

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(API_CONFIG.ENDPOINTS.WORKFLOWS + '/', {
        headers: { 'Content-Type': 'application/json' },
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
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
      const res = await fetch(`/api/workflows/${workflowId}/execute`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      navigate(`/workflow/${workflowId}`);
    } catch (err) {
      alert(`Could not execute workflow: ${err.message}`);
    } finally {
      setExecuting(null);
    }
  }, [navigate]);

  const statusOptions = ['all', ...Object.keys(STATUS_META)];

  const visible = workflows.filter(wf => {
    const matchSearch = !search
      || (wf.name || '').toLowerCase().includes(search.toLowerCase())
      || (wf.description || '').toLowerCase().includes(search.toLowerCase())
      || (wf.source_name || '').toLowerCase().includes(search.toLowerCase())
      || (wf.target_name || '').toLowerCase().includes(search.toLowerCase());
    const matchStatus = filterStatus === 'all' || (wf.status || '').toLowerCase() === filterStatus;
    return matchSearch && matchStatus;
  });

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
          <button className="btn-primary" onClick={() => navigate('/migration')}>
            <i className="fas fa-plus" /> New Migration
          </button>
        </div>
      </div>

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
                  onOpen={id => navigate(`/workflow/${id}`)}
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
