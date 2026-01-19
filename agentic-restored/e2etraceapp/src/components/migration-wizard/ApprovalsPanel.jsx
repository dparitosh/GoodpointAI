import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { e2etraceFetchWithRetry } from '../../api/e2etrace-api';
import { API_CONFIG } from '../../config/api-config.js';

const statusBadgeClass = (status) => {
  const s = String(status || '').toLowerCase();
  if (s === 'approved') return 'badge badge-success';
  if (s === 'rejected') return 'badge badge-danger';
  return 'badge badge-warning';
};

const safeJson = async (resp) => {
  try {
    return await resp.json();
  } catch {
    return null;
  }
};

export const ApprovalsPanel = ({
  runId,
  defaultAction = 'materialize',
  onTokenSelected,
  title = 'Human-in-the-loop approvals',
  defaultRequestedBy = '',
  impact = null,
  sample = null,
}) => {
  const baseUrl = useMemo(() => `${API_CONFIG?.API_BASE_URL || ''}/api/migrations`, []);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [items, setItems] = useState([]);

  const safeImpact = useMemo(() => {
    return impact && typeof impact === 'object' && !Array.isArray(impact) ? impact : {};
  }, [impact]);

  const safeSample = useMemo(() => {
    if (!Array.isArray(sample)) return [];
    return sample.filter((r) => r && typeof r === 'object' && !Array.isArray(r)).slice(0, 10);
  }, [sample]);

  const [newRequest, setNewRequest] = useState({
    action: defaultAction,
    requested_by: defaultRequestedBy,
    summary: `Approve ${defaultAction} for this run`,
    note: '',
  });

  const refresh = useCallback(async () => {
    const rid = String(runId || '').trim();
    if (!rid) return;

    setIsLoading(true);
    setError(null);
    try {
      const resp = await e2etraceFetchWithRetry(`${baseUrl}/runs/${encodeURIComponent(rid)}/approvals`);
      const data = await safeJson(resp);
      setItems(Array.isArray(data) ? data : []);
    } catch (e) {
      setError(e?.message || 'Failed to load approvals');
    } finally {
      setIsLoading(false);
    }
  }, [baseUrl, runId]);

  useEffect(() => {
    refresh().catch(() => {});
  }, [refresh]);

  const createRequest = useCallback(async () => {
    const rid = String(runId || '').trim();
    if (!rid) return;

    setIsLoading(true);
    setError(null);
    try {
      const resp = await e2etraceFetchWithRetry(`${baseUrl}/runs/${encodeURIComponent(rid)}/approvals`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          action: newRequest.action,
          summary: newRequest.summary,
          requested_by: newRequest.requested_by,
          note: newRequest.note,
          impact: safeImpact,
          sample: safeSample,
        }),
      });
      const created = await safeJson(resp);
      if (created?.token && typeof onTokenSelected === 'function') {
        onTokenSelected({ token: created.token, action: created?.action || newRequest.action });
      }
      await refresh();
    } catch (e) {
      setError(e?.message || 'Failed to create approval request');
    } finally {
      setIsLoading(false);
    }
  }, [baseUrl, newRequest, onTokenSelected, refresh, runId, safeImpact, safeSample]);

  const decide = useCallback(
    async (approvalId, decision) => {
      const rid = String(runId || '').trim();
      if (!rid) return;
      const aid = String(approvalId || '').trim();
      if (!aid) return;

      const decisionNorm = String(decision || '').toLowerCase();
      const verb = decisionNorm === 'approve' ? 'approve' : 'reject';
      if (!confirm(`Are you sure you want to ${verb} this approval request?`)) return;

      setIsLoading(true);
      setError(null);
      try {
        await e2etraceFetchWithRetry(`${baseUrl}/runs/${encodeURIComponent(rid)}/approvals/${encodeURIComponent(aid)}/${verb}`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ decided_by: newRequest.requested_by || 'ui', note: '' }),
        });
        await refresh();
      } catch (e) {
        setError(e?.message || `Failed to ${verb} request`);
      } finally {
        setIsLoading(false);
      }
    },
    [baseUrl, newRequest.requested_by, refresh, runId]
  );

  const copy = useCallback(async (text) => {
    const t = String(text || '');
    if (!t) return;
    try {
      await navigator.clipboard.writeText(t);
    } catch {
      // best-effort
    }
  }, []);

  const hasRun = String(runId || '').trim().length > 0;

  return (
    <div className="mcp-approvals-panel" aria-busy={isLoading ? 'true' : 'false'}>
      <div className="mcp-approvals-header">
        <h4>{title}</h4>
        <button className="btn btn-sm btn-ghost" onClick={refresh} disabled={!hasRun || isLoading}>
          <i className="fas fa-sync" /> Refresh
        </button>
      </div>

      {!hasRun && (
        <div className="inline-alert info">
          No MCP run id yet. Run Discovery first to create the MCP run.
        </div>
      )}

      {error && <div className="inline-alert error">{error}</div>}

      <div className="mcp-approvals-create">
        <div className="form-row">
          <label>Action</label>
          <input
            type="text"
            value={newRequest.action}
            onChange={(e) => setNewRequest((p) => ({ ...p, action: e.target.value }))}
            disabled={!hasRun || isLoading}
            aria-label="Approval action"
          />
        </div>
        <div className="form-row">
          <label>Requested by</label>
          <input
            type="text"
            value={newRequest.requested_by}
            onChange={(e) => setNewRequest((p) => ({ ...p, requested_by: e.target.value }))}
            placeholder="Your name (optional)"
            disabled={!hasRun || isLoading}
            aria-label="Requested by"
          />
        </div>
        <div className="form-row">
          <label>Summary</label>
          <input
            type="text"
            value={newRequest.summary}
            onChange={(e) => setNewRequest((p) => ({ ...p, summary: e.target.value }))}
            disabled={!hasRun || isLoading}
            aria-label="Approval request summary"
          />
        </div>
        <div className="form-row">
          <label>Note</label>
          <input
            type="text"
            value={newRequest.note}
            onChange={(e) => setNewRequest((p) => ({ ...p, note: e.target.value }))}
            placeholder="Optional context / risk / impact"
            disabled={!hasRun || isLoading}
            aria-label="Approval request note"
          />
        </div>

        <div className="actions-row">
          <button className="btn btn-primary" onClick={createRequest} disabled={!hasRun || isLoading}>
            <i className="fas fa-hand-paper" /> Request approval
          </button>
        </div>
      </div>

      <div className="mcp-approvals-list" role="list">
        {items.length === 0 ? (
          <div className="placeholder">No approval requests yet.</div>
        ) : (
          items.map((a) => {
            const status = a?.status;
            const token = a?.token;
            return (
              <div key={a?.approval_id || Math.random()} className="approval-item" role="listitem">
                <div className="approval-top">
                  <div className="approval-title">
                    <span className={statusBadgeClass(status)}>{String(status || 'pending')}</span>
                    <strong>{String(a?.action || '')}</strong>
                  </div>
                  <div className="approval-meta">
                    {a?.requested_by ? <span>Requested by {a.requested_by}</span> : <span>Requested</span>}
                    {a?.requested_at ? <span>• {new Date(a.requested_at).toLocaleString()}</span> : null}
                  </div>
                </div>

                {a?.summary && <div className="approval-summary">{a.summary}</div>}

                {token && (
                  <div className="approval-token">
                    <code title="Approval token">{token}</code>
                    <div className="token-actions">
                      <button className="btn btn-sm btn-secondary" onClick={() => copy(token)}>
                        Copy
                      </button>
                      <button
                        className="btn btn-sm btn-primary"
                        onClick={() =>
                          typeof onTokenSelected === 'function' && onTokenSelected({ token, action: a?.action })
                        }
                      >
                        Use token
                      </button>
                    </div>
                  </div>
                )}

                <div className="approval-actions">
                  <button
                    className="btn btn-sm btn-success"
                    onClick={() => decide(a?.approval_id, 'approve')}
                    disabled={isLoading || String(status || '').toLowerCase() !== 'pending'}
                    title="Approve (admin action)"
                  >
                    <i className="fas fa-check" /> Approve
                  </button>
                  <button
                    className="btn btn-sm btn-warning"
                    onClick={() => decide(a?.approval_id, 'reject')}
                    disabled={isLoading || String(status || '').toLowerCase() !== 'pending'}
                    title="Reject (admin action)"
                  >
                    <i className="fas fa-times" /> Reject
                  </button>
                </div>

                <div className="approval-footnote">
                  Tip: approvals are enforced only when the backend has <code>GRAPH_TRACE_APPROVALS_REQUIRED=true</code>.
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};

export default ApprovalsPanel;
