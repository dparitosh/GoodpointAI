import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { e2etraceFetchWithRetry } from '../../api/e2etrace-api.js';
import { PageLoader } from '../../components/LoadingSpinner.jsx';
import './WorkflowManagerPage.css';

const DEFAULT_LIMIT = 25;

const safeLower = (value) => String(value || '').trim().toLowerCase();

const formatDateTime = (value) => {
  if (!value) return '—';
  try {
    const d = new Date(value);
    if (Number.isNaN(d.getTime())) return String(value);
    return d.toLocaleString();
  } catch {
    return String(value);
  }
};

const normalizeWorkflowStatus = (value) => {
  const v = safeLower(value);
  if (!v) return 'unknown';
  return v;
};

const WorkflowManagerPage = () => {
  const navigate = useNavigate();

  const [filters, setFilters] = useState({
    search: '',
    status: '',
    sourceType: '',
    targetType: ''
  });
  const [query, setQuery] = useState({
    search: '',
    status: '',
    sourceType: '',
    targetType: ''
  });

  const [workflows, setWorkflows] = useState([]);
  const [totalCount, setTotalCount] = useState(null);
  const [skip, setSkip] = useState(0);
  const [limit, setLimit] = useState(DEFAULT_LIMIT);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchSeqRef = useRef(0);

  const pageIndex = useMemo(() => Math.floor(skip / Math.max(1, limit)) + 1, [skip, limit]);
  const totalPages = useMemo(() => {
    if (typeof totalCount !== 'number') return null;
    return Math.max(1, Math.ceil(totalCount / Math.max(1, limit)));
  }, [totalCount, limit]);

  const buildUrl = useCallback(() => {
    const params = new URLSearchParams();
    params.set('skip', String(skip));
    params.set('limit', String(limit));

    if (query.search) params.set('search', query.search);
    if (query.status) params.set('status', query.status);
    if (query.sourceType) params.set('source_type', query.sourceType);
    if (query.targetType) params.set('target_type', query.targetType);

    return `/api/workflows?${params.toString()}`;
  }, [skip, limit, query]);

  const loadWorkflows = useCallback(async () => {
    const seq = ++fetchSeqRef.current;
    setLoading(true);
    setError(null);

    try {
      const response = await e2etraceFetchWithRetry(buildUrl());
      const rawTotal = response.headers.get('X-Total-Count');
      const nextTotal = rawTotal != null ? Number(rawTotal) : null;

      const data = await response.json();
      if (seq !== fetchSeqRef.current) return;

      setWorkflows(Array.isArray(data) ? data : []);
      setTotalCount(Number.isFinite(nextTotal) ? nextTotal : null);
    } catch (err) {
      if (seq !== fetchSeqRef.current) return;
      setWorkflows([]);
      setTotalCount(null);
      setError(err?.message || 'Failed to load workflows');
    } finally {
      if (seq === fetchSeqRef.current) {
        setLoading(false);
      }
    }
  }, [buildUrl]);

  useEffect(() => {
    loadWorkflows();
  }, [loadWorkflows]);

  const applyFilters = () => {
    setSkip(0);
    setQuery({
      search: String(filters.search || '').trim(),
      status: String(filters.status || '').trim(),
      sourceType: String(filters.sourceType || '').trim(),
      targetType: String(filters.targetType || '').trim()
    });
  };

  const clearFilters = () => {
    setSkip(0);
    setFilters({ search: '', status: '', sourceType: '', targetType: '' });
    setQuery({ search: '', status: '', sourceType: '', targetType: '' });
  };

  if (loading && workflows.length === 0) {
    return <PageLoader message="Loading workflows..." />;
  }

  return (
    <div className="workflow-manager-page">
      <div className="workflow-manager-header">
        <div className="workflow-manager-title">
          <h1>Workflow Management</h1>
          <p>Discover, monitor, and open workflow instances.</p>
        </div>

        <div className="workflow-manager-actions">
          <button type="button" className="btn btn-secondary" onClick={loadWorkflows} disabled={loading}>
            Refresh
          </button>
        </div>
      </div>

      <div className="workflow-manager-filters" role="region" aria-label="Workflow filters">
        <div className="filter-row">
          <label className="filter-field">
            <span>Search</span>
            <input
              value={filters.search}
              onChange={(e) => setFilters((prev) => ({ ...prev, search: e.target.value }))}
              placeholder="name, id, description"
              spellCheck={false}
              onKeyDown={(e) => {
                if (e.key === 'Enter') applyFilters();
              }}
            />
          </label>

          <label className="filter-field">
            <span>Status</span>
            <select
              value={filters.status}
              onChange={(e) => setFilters((prev) => ({ ...prev, status: e.target.value }))}
            >
              <option value="">All</option>
              <option value="draft">draft</option>
              <option value="configured">configured</option>
              <option value="running">running</option>
              <option value="paused">paused</option>
              <option value="completed">completed</option>
              <option value="failed">failed</option>
              <option value="archived">archived</option>
            </select>
          </label>

          <label className="filter-field">
            <span>Source type</span>
            <input
              value={filters.sourceType}
              onChange={(e) => setFilters((prev) => ({ ...prev, sourceType: e.target.value }))}
              placeholder="e.g. postgres"
              spellCheck={false}
              onKeyDown={(e) => {
                if (e.key === 'Enter') applyFilters();
              }}
            />
          </label>

          <label className="filter-field">
            <span>Target type</span>
            <input
              value={filters.targetType}
              onChange={(e) => setFilters((prev) => ({ ...prev, targetType: e.target.value }))}
              placeholder="e.g. neo4j"
              spellCheck={false}
              onKeyDown={(e) => {
                if (e.key === 'Enter') applyFilters();
              }}
            />
          </label>

          <div className="filter-buttons">
            <button type="button" className="btn btn-primary" onClick={applyFilters} disabled={loading}>
              Apply
            </button>
            <button type="button" className="btn btn-secondary" onClick={clearFilters} disabled={loading}>
              Clear
            </button>
          </div>
        </div>

        <div className="workflow-manager-summary">
          <div className="summary-item">
            <span className="summary-label">Showing</span>
            <span className="summary-value">{workflows.length}</span>
          </div>
          <div className="summary-item">
            <span className="summary-label">Total</span>
            <span className="summary-value">{typeof totalCount === 'number' ? totalCount : '—'}</span>
          </div>
          <div className="summary-item">
            <span className="summary-label">Page</span>
            <span className="summary-value">
              {pageIndex}
              {typeof totalPages === 'number' ? ` / ${totalPages}` : ''}
            </span>
          </div>
          <div className="summary-item">
            <span className="summary-label">Page size</span>
            <select
              className="page-size"
              value={limit}
              onChange={(e) => {
                const next = Number(e.target.value);
                if (!Number.isFinite(next) || next <= 0) return;
                setSkip(0);
                setLimit(next);
              }}
            >
              <option value={10}>10</option>
              <option value={25}>25</option>
              <option value={50}>50</option>
              <option value={100}>100</option>
            </select>
          </div>

          <div className="summary-item summary-nav">
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => setSkip((prev) => Math.max(0, prev - limit))}
              disabled={loading || skip === 0}
            >
              Prev
            </button>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => setSkip((prev) => prev + limit)}
              disabled={
                loading ||
                (typeof totalCount === 'number' ? skip + limit >= totalCount : workflows.length < limit)
              }
            >
              Next
            </button>
          </div>
        </div>
      </div>

      {error ? (
        <div className="workflow-manager-error" role="alert">
          {error}
        </div>
      ) : null}

      {workflows.length === 0 && !loading ? (
        <div className="workflow-manager-empty">
          <h3>No workflows found</h3>
          <p>
            Try adjusting filters, or run a workflow from the Migration Wizard to generate instances.
          </p>
        </div>
      ) : (
        <div className="workflow-manager-table-container">
          <table className="workflow-manager-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Status</th>
                <th>Source</th>
                <th>Target</th>
                <th>Progress</th>
                <th>Quality</th>
                <th>Updated</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {workflows.map((wf, idx) => {
                const status = normalizeWorkflowStatus(wf?.status);
                return (
                  <tr
                    key={wf?.id || `${wf?.name || 'workflow'}-${idx}`}
                    className="workflow-row"
                    onClick={() => {
                      if (wf?.id) navigate(`/workflow/${encodeURIComponent(wf.id)}`);
                    }}
                    style={{ cursor: wf?.id ? 'pointer' : 'default' }}
                  >
                    <td className="name-cell">
                      <div className="wf-name">{wf?.name || 'Untitled workflow'}</div>
                      <div className="wf-id">{wf?.id || ''}</div>
                    </td>
                    <td>
                      <span className={`wf-status wf-status-${status}`}>{status}</span>
                    </td>
                    <td>
                      <div className="wf-system">{wf?.source_name || '—'}</div>
                      <div className="wf-type">{wf?.source_type || '—'}</div>
                    </td>
                    <td>
                      <div className="wf-system">{wf?.target_name || '—'}</div>
                      <div className="wf-type">{wf?.target_type || '—'}</div>
                    </td>
                    <td>{typeof wf?.progress_percentage === 'number' ? `${wf.progress_percentage.toFixed(1)}%` : '—'}</td>
                    <td>{typeof wf?.quality_score === 'number' ? `${wf.quality_score.toFixed(1)}%` : '—'}</td>
                    <td>{formatDateTime(wf?.updated_at || wf?.created_at)}</td>
                    <td className="actions-cell" onClick={(e) => e.stopPropagation()}>
                      <button
                        type="button"
                        className="btn-action"
                        onClick={() => {
                          if (wf?.id) navigate(`/workflow/${encodeURIComponent(wf.id)}`);
                        }}
                        disabled={!wf?.id}
                        title="Open workflow detail"
                      >
                        <i className="fas fa-external-link-alt" aria-hidden="true" />
                      </button>
                      <button
                        type="button"
                        className="btn-action"
                        onClick={() => {
                          if (wf?.id) navigate(`/graph-explorer/workflow/${encodeURIComponent(wf.id)}`);
                        }}
                        disabled={!wf?.id}
                        title="Open in Graph Explorer"
                      >
                        <i className="fas fa-project-diagram" aria-hidden="true" />
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};

export default WorkflowManagerPage;
