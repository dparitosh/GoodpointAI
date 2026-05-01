import React, { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import API_CONFIG, { buildEndpoint } from '../../config/api-config';
import { XStateVisualizer } from '../../components/xstate-visualizer/XStateVisualizer';
import { LoadingSpinner, PageLoader, SPINNER_VARIANTS } from '../../components/LoadingSpinner.jsx';
import './WorkflowDetailPage.css';

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

const buildWebSocketUrl = (path) => {
  const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
  return `${protocol}://${window.location.host}${path}`;
};

const mapMigrationStateToWorkflowStage = (state) => {
  const s = String(state || '').toLowerCase();
  if (!s) return null;

  if (['initializing', 'discovering'].includes(s)) return 'extracting';
  if (['profiling', 'schema_mapping'].includes(s)) return 'transforming';
  if (['data_migration'].includes(s)) return 'loading';
  if (['validation'].includes(s)) return 'validating';
  if (['completed'].includes(s)) return 'finalizing';
  return null;
};

const mapMigrationStateToActiveGraphStage = (state) => {
  const s = String(state || '').toLowerCase();
  if (!s) return null;

  if (['initializing', 'discovering'].includes(s)) return 'extract';
  if (['profiling', 'schema_mapping'].includes(s)) return 'transform';
  if (['data_migration'].includes(s)) return 'load';
  if (['validation'].includes(s)) return 'quality';
  return null;
};

const applyMigrationUpdateToGraphData = (data, update) => {
  if (!data || !Array.isArray(data.nodes)) return data;

  const state = String(update?.state || '').toLowerCase();
  const isCompleted = state === 'completed';
  const isFailed = state === 'failed';

  if (isCompleted) {
    return {
      ...data,
      nodes: data.nodes.map((n) => ({ ...n, status: 'healthy' }))
    };
  }

  if (isFailed) {
    return {
      ...data,
      nodes: data.nodes.map((n) => ({ ...n, status: 'error' }))
    };
  }

  const activeStage = mapMigrationStateToActiveGraphStage(update?.state);
  if (!activeStage) return data;

  return {
    ...data,
    nodes: data.nodes.map((n) => {
      const nodeStage = String(n?.stage || '').toLowerCase();
      const isActive = nodeStage === activeStage;
      return {
        ...n,
        status: isActive ? 'warning' : 'healthy'
      };
    })
  };
};

const isEmptyGraphData = (data) => {
  if (!data) return true;
  if (!Array.isArray(data.nodes)) return true;
  return data.nodes.length === 0;
};

const buildFallbackGraphFromWorkflow = (workflow) => {
  const sourceLabel = workflow?.source_name || 'Source';
  const targetLabel = workflow?.target_name || 'Target';

  const nodes = [
    { id: 'source', label: sourceLabel, type: 'source', stage: 'source', status: 'healthy' },
    { id: 'extract', label: 'Extract', type: 'pipeline', stage: 'extract', status: 'healthy' },
    { id: 'transform', label: 'Transform', type: 'pipeline', stage: 'transform', status: 'healthy' },
    { id: 'quality', label: 'Quality', type: 'pipeline', stage: 'quality', status: 'healthy' },
    { id: 'load', label: 'Load', type: 'pipeline', stage: 'load', status: 'healthy' },
    { id: 'target', label: targetLabel, type: 'target', stage: 'target', status: 'healthy' }
  ];

  const edges = [
    { id: 'edge-source-extract', source: 'source', target: 'extract', type: 'transition', label: '' },
    { id: 'edge-extract-transform', source: 'extract', target: 'transform', type: 'transition', label: '' },
    { id: 'edge-transform-quality', source: 'transform', target: 'quality', type: 'transition', label: '' },
    { id: 'edge-quality-load', source: 'quality', target: 'load', type: 'transition', label: '' },
    { id: 'edge-load-target', source: 'load', target: 'target', type: 'transition', label: '' }
  ];

  return { nodes, edges };
};

/**
 * Workflow Detail Page
 * 
 * Displays detailed view of a specific workflow instance with:
 * - Full XState visualizer showing the configured pipeline
 * - Real-time execution status and progress
 * - Configuration details (source, target, AI agents)
 * - Execution controls (start, pause, stop)
 * - History and logs
 */
const WorkflowDetailPage = () => {
  const { workflowId } = useParams();
  const navigate = useNavigate();
  const [workflow, setWorkflow] = useState(null);
  const [graphData, setGraphData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [archive, setArchive] = useState(null);
  const [archiveLoading, setArchiveLoading] = useState(false);
  const [archiveError, setArchiveError] = useState(null);
  const [wsConnected, setWsConnected] = useState(false);
  const loadAbortRef = useRef(null);
  const loadSeqRef = useRef(0);
  const archiveAbortRef = useRef(null);
  const archiveSeqRef = useRef(0);

  const wsRef = useRef(null);
  const wsSessionIdRef = useRef(null);
  const wsReconnectTimeoutRef = useRef(null);
  const lastWsUpdateRef = useRef(null);
  const latestWorkflowRef = useRef({ status: null, sessionId: null });

  // Load workflow details on mount and when workflowId changes
  useEffect(() => {
    loadWorkflowDetails();
    loadWorkflowArchive();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [workflowId]);

  // Refresh archive after a run completes (so ETL + snapshots are up-to-date)
  useEffect(() => {
    const currentRunId = workflow?.execution_metadata?.plm_run_id;
    const archiveRunId = archive?.workflow?.execution_metadata?.plm_run_id;

    if (workflow?.status === 'completed' && currentRunId && currentRunId !== archiveRunId) {
      loadWorkflowArchive();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [workflow?.status, workflow?.execution_metadata?.plm_run_id]);

  useEffect(() => {
    latestWorkflowRef.current = {
      status: workflow?.status,
      sessionId: workflow?.execution_metadata?.migration_session_id
    };
  }, [workflow?.status, workflow?.execution_metadata?.migration_session_id]);

  // Cancel any in-flight requests on unmount/workflowId changes
  useEffect(() => {
    return () => {
      if (loadAbortRef.current) {
        try {
          loadAbortRef.current.abort();
        } catch {
          // ignore
        }
      }

      if (archiveAbortRef.current) {
        try {
          archiveAbortRef.current.abort();
        } catch {
          // ignore
        }
      }

      // WebSocket cleanup
      if (wsReconnectTimeoutRef.current) {
        clearTimeout(wsReconnectTimeoutRef.current);
        wsReconnectTimeoutRef.current = null;
      }
    };
  }, [workflowId]);

  const loadWorkflowArchive = async () => {
    const seq = ++archiveSeqRef.current;
    if (archiveAbortRef.current) {
      try {
        archiveAbortRef.current.abort();
      } catch {
        // ignore
      }
    }
    const controller = new AbortController();
    archiveAbortRef.current = controller;

    try {
      setArchiveLoading(true);
      setArchiveError(null);

      const res = await fetch(`${buildEndpoint(API_CONFIG.ENDPOINTS.WORKFLOW_ARCHIVE, workflowId)}?limit_reports=50`, { signal: controller.signal });
      if (seq !== archiveSeqRef.current) return;

      if (!res.ok) {
        let msg = `Failed to load archive (${res.status})`;
        try {
          const err = await res.json();
          if (err?.detail) msg = String(err.detail);
        } catch {
          // ignore
        }
        setArchive(null);
        setArchiveError(msg);
        return;
      }

      const data = await res.json();
      if (seq !== archiveSeqRef.current) return;
      setArchive(data);
    } catch (error) {
      if (error?.name === 'AbortError') return;
      if (seq !== archiveSeqRef.current) return;
      setArchive(null);
      setArchiveError('Could not load archive');
    } finally {
      if (seq === archiveSeqRef.current) {
        setArchiveLoading(false);
      }
    }
  };

  // Auto-refresh when workflow is running (separate effect)
  useEffect(() => {
    let interval;
    if (workflow?.status === 'running') {
      const refreshMs = wsConnected ? 30000 : 5000;
      interval = setInterval(() => {
        // Wrap in try-catch to prevent interval from continuing on error
        try {
          loadWorkflowDetails();
        } catch (error) {
          console.error('Error in auto-refresh:', error);
          clearInterval(interval);
        }
      }, refreshMs);
    }
    
    return () => {
      if (interval) {
        clearInterval(interval);
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [workflow?.status, wsConnected]);

  // Subscribe to migration session updates for real-time visualizer updates
  useEffect(() => {
    const sessionId = workflow?.execution_metadata?.migration_session_id;

    const cleanup = () => {
      if (wsReconnectTimeoutRef.current) {
        clearTimeout(wsReconnectTimeoutRef.current);
        wsReconnectTimeoutRef.current = null;
      }
      if (wsRef.current) {
        try {
          wsRef.current.close();
        } catch {
          // ignore
        }
      }
      wsRef.current = null;
      wsSessionIdRef.current = null;
      setWsConnected(false);
    };

    const scheduleReconnect = () => {
      if (wsReconnectTimeoutRef.current) return;
      wsReconnectTimeoutRef.current = setTimeout(() => {
        wsReconnectTimeoutRef.current = null;
        const latest = latestWorkflowRef.current;
        if (latest?.status === 'running' && latest?.sessionId) {
          // re-run effect by forcing a noop state update isn't needed; just connect
          connect(latest.sessionId);
        }
      }, 2000);
    };

    const connect = (sid) => {
      const url = buildWebSocketUrl(buildEndpoint(API_CONFIG.ENDPOINTS.MIGRATION_WS, sid));
      let ws;
      try {
        ws = new WebSocket(url);
      } catch (err) {
        console.warn('Failed to create WebSocket connection:', err);
        return;
      }

      wsRef.current = ws;
      wsSessionIdRef.current = sid;

      ws.onopen = () => {
        setWsConnected(true);
      };

      ws.onmessage = (evt) => {
        let msg;
        try {
          msg = JSON.parse(evt.data);
        } catch {
          return;
        }

        if (!msg || msg.type === 'heartbeat') return;
        if (msg.session_id && String(msg.session_id) !== String(wsSessionIdRef.current || '')) return;

        lastWsUpdateRef.current = msg;

        // Reflect WS progress/state into the header + progress UI
        setWorkflow((prev) => {
          if (!prev) return prev;

          const next = { ...prev };
          const stage = mapMigrationStateToWorkflowStage(msg.state);

          next.execution_metadata = {
            ...(next.execution_metadata || {}),
            migration_session_state: msg.state,
            migration_session_updated_at: msg.timestamp
          };

          if (typeof msg.progress === 'number' && Number.isFinite(msg.progress)) {
            next.progress_percentage = msg.progress;
          }
          if (typeof msg.quality === 'number' && Number.isFinite(msg.quality)) {
            next.quality_score = msg.quality;
          }
          if (Array.isArray(msg.errors) && msg.errors.length > 0) {
            next.execution_metadata.migration_errors = msg.errors;
          }
          if (stage) {
            next.current_stage = stage;
          }
          return next;
        });

        // Reflect WS state into node statuses
        setGraphData((prev) => applyMigrationUpdateToGraphData(prev, msg));
      };

      ws.onclose = () => {
        setWsConnected(false);
        const latest = latestWorkflowRef.current;
        if (latest?.status === 'running' && latest?.sessionId === sid) {
          scheduleReconnect();
        }
      };

      ws.onerror = () => {
        // Close triggers reconnect path
        try {
          ws.close();
        } catch {
          // ignore
        }
      };
    };

    if (workflow?.status !== 'running' || !sessionId) {
      cleanup();
      return cleanup;
    }

    // Already connected (or connecting) to the right session
    if (
      wsRef.current &&
      wsSessionIdRef.current === sessionId &&
      (wsRef.current.readyState === WebSocket.OPEN || wsRef.current.readyState === WebSocket.CONNECTING)
    ) {
      return cleanup;
    }

    cleanup();
    connect(sessionId);
    return cleanup;
  }, [workflow?.status, workflow?.execution_metadata?.migration_session_id]);

  const loadWorkflowDetails = async () => {
    const seq = ++loadSeqRef.current;
    if (loadAbortRef.current) {
      try {
        loadAbortRef.current.abort();
      } catch {
        // ignore
      }
    }
    const controller = new AbortController();
    loadAbortRef.current = controller;

    try {
      setLoading(true);
      
      // Load workflow details
      // Transient 404s can happen right after creation due to async-ish persistence/races.
      // Retry briefly before declaring the workflow missing.
      let workflowRes;
      for (let attempt = 0; attempt < 3; attempt += 1) {
        workflowRes = await fetch(buildEndpoint(API_CONFIG.ENDPOINTS.WORKFLOW_DETAILS, workflowId), { signal: controller.signal });
        if (workflowRes.ok) break;
        if (workflowRes.status === 404 && attempt < 2) {
          await sleep(250 * (attempt + 1));
          continue;
        }
        break;
      }
      if (workflowRes.ok) {
        const workflowData = await workflowRes.json();
        if (seq !== loadSeqRef.current) return;
        setWorkflow(workflowData);
        
        // Load workflow-specific graph
        try {
          const graphRes = await fetch(buildEndpoint(API_CONFIG.ENDPOINTS.WORKFLOW_GRAPH, workflowId), { signal: controller.signal });
          if (!graphRes.ok) {
            throw new Error(`Workflow graph not available (${graphRes.status})`);
          }

          const graphJson = await graphRes.json();
          if (seq !== loadSeqRef.current) return;

          if (isEmptyGraphData(graphJson)) {
            throw new Error('Workflow graph is empty');
          }

          const withLiveState = lastWsUpdateRef.current
            ? applyMigrationUpdateToGraphData(graphJson, lastWsUpdateRef.current)
            : graphJson;
          setGraphData(withLiveState);
        } catch (error) {
          if (error?.name === 'AbortError') throw error;

          // Fallback to default PLM workflow if custom graph not available
          let fallbackGraph = null;
          try {
            const availabilityRes = await fetch(API_CONFIG.ENDPOINTS.PLM_AVAILABILITY, { signal: controller.signal });
            if (availabilityRes.ok) {
              const availability = await availabilityRes.json();
              if (availability?.available) {
                const fallbackRes = await fetch(API_CONFIG.ENDPOINTS.PLM_WORKFLOW, { signal: controller.signal });
                if (fallbackRes.ok) {
                  fallbackGraph = await fallbackRes.json();
                }
              }
            }
          } catch (fallbackError) {
            if (fallbackError?.name === 'AbortError') throw fallbackError;
          }

          const chosen = !isEmptyGraphData(fallbackGraph) ? fallbackGraph : buildFallbackGraphFromWorkflow(workflowData);
          const withLiveState = lastWsUpdateRef.current
            ? applyMigrationUpdateToGraphData(chosen, lastWsUpdateRef.current)
            : chosen;
          if (seq !== loadSeqRef.current) return;
          setGraphData(withLiveState);
        }
      } else {
        console.error('Workflow not found:', workflowId);
        navigate('/workflows', {
          state: { error: 'Workflow not found' }
        });
      }
    } catch (error) {
      if (error?.name === 'AbortError') return;
      console.error('Error loading workflow details:', error);
      // Don't navigate on network errors, just show error state
      if (seq === loadSeqRef.current) {
        setWorkflow(null);
      }
    } finally {
      if (seq === loadSeqRef.current) {
        setLoading(false);
      }
    }
  };

  const handleWorkflowAction = async (action) => {
    try {
      // Add timeout to prevent hanging requests
      const controller = new AbortController();
      // Starting a workflow may legitimately take longer than 30s; avoid false timeouts.
      const timeoutMs = action === 'start' ? 5 * 60 * 1000 : 30000;
      const timeoutId = setTimeout(() => controller.abort(), timeoutMs);
      
      const response = await fetch(buildEndpoint(API_CONFIG.ENDPOINTS.WORKFLOW_EXECUTE, workflowId), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action, execution_params: {} }),
        signal: controller.signal
      });
      
      clearTimeout(timeoutId);
      
      if (response.ok) {
        const result = await response.json();
        console.log(`Workflow action ${action} succeeded:`, result.message);
        await loadWorkflowDetails();
        if (action === 'start') {
          // Prime archive (snapshots/ETL) early; it will refresh again on completion.
          loadWorkflowArchive();
        }
      } else {
        const error = await response.json();
        console.error(`Workflow action ${action} failed:`, error.detail);
      }
    } catch (error) {
      if (error?.name === 'AbortError') {
        // Request timed out — silently ignore
      } else {
        console.error('Error executing workflow action:', error);
      }
    }
  };

  if (loading) {
    return (
      <PageLoader message="Loading workflow details..." />
    );
  }

  if (!workflow) {
    return (
      <div className="workflow-detail-error">
        <h2>Workflow Not Found</h2>
        <button onClick={() => navigate('/workflows')}>← Back to My Workflows</button>
      </div>
    );
  }

  return (
    <div className="workflow-detail-page">
      {/* Header */}
      <div className="workflow-detail-header">
        <button className="btn-back" onClick={() => navigate('/workflows')}>
          ← Back to My Workflows
        </button>
        
        <div className="header-info">
          <h1>{workflow.name}</h1>
          <p>{workflow.description}</p>
          <div className="header-meta">
            <span className={`status-badge status-${workflow.status}`}>
              {workflow.status}
            </span>
            {workflow.current_stage && (
              <span className="stage-badge">Stage: {workflow.current_stage}</span>
            )}
          </div>
        </div>

        <div className="header-actions">
          {(workflow.status === 'configured' || workflow.status === 'paused') && (
            <button
              className="btn-action btn-resume"
              onClick={() => navigate(`/migration?resumeWorkflowId=${encodeURIComponent(workflow.id)}`)}
            >
              <i className="fas fa-edit" aria-hidden="true" /> Resume in Wizard
            </button>
          )}

          {workflow.status === 'draft' || workflow.status === 'configured' || workflow.status === 'paused' ? (
            <button 
              className="btn-action btn-start"
              onClick={() => handleWorkflowAction('start')}
            >
              <i className="fas fa-play" aria-hidden="true" /> Start Workflow
            </button>
          ) : null}
          
          {workflow.status === 'running' ? (
            <>
              <button 
                className="btn-action btn-pause"
                onClick={() => handleWorkflowAction('pause')}
              >
                <i className="fas fa-pause" aria-hidden="true" /> Pause
              </button>
              <button 
                className="btn-action btn-stop"
                onClick={() => handleWorkflowAction('stop')}
              >
                ■ Stop
              </button>
            </>
          ) : null}
        </div>
      </div>

      {/* Progress Section */}
      {workflow.status === 'running' && (
        <div className="workflow-progress-section">
          <div className="progress-info">
            <span className="progress-label">Overall Progress:</span>
            <span className="progress-percentage">{workflow.progress_percentage.toFixed(1)}%</span>
          </div>
          <div className="progress-bar-large">
            <div 
              className="progress-fill-large" 
              style={{ width: `${workflow.progress_percentage}%` }}
            />
          </div>
          <div className="progress-stats">
            <div className="progress-stat">
              <span className="stat-label">Total:</span>
              <span className="stat-value">{workflow.total_records.toLocaleString()}</span>
            </div>
            <div className="progress-stat">
              <span className="stat-label">Processed:</span>
              <span className="stat-value success">{workflow.processed_records.toLocaleString()}</span>
            </div>
            <div className="progress-stat">
              <span className="stat-label">Failed:</span>
              <span className="stat-value error">{workflow.failed_records}</span>
            </div>
            {workflow.quality_score && (
              <div className="progress-stat">
                <span className="stat-label">Quality:</span>
                <span className="stat-value quality">{workflow.quality_score.toFixed(1)}%</span>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Configuration Cards */}
      <div className="config-section">
        <div className="config-card">
          <h3>Source Configuration</h3>
          <div className="config-details">
            <div className="config-row">
              <span className="config-label">System:</span>
              <span className="config-value">{workflow.source_name}</span>
            </div>
            <div className="config-row">
              <span className="config-label">Type:</span>
              <span className="config-value">{workflow.source_type}</span>
            </div>
            {workflow.source_config && Object.entries(workflow.source_config).map(([key, value]) => (
              <div key={key} className="config-row">
                <span className="config-label">{key}:</span>
                <span className="config-value">{typeof value === 'object' ? JSON.stringify(value) : value}</span>
              </div>
            ))}
          </div>
        </div>

        <div className="config-card">
          <h3>Target Configuration</h3>
          <div className="config-details">
            <div className="config-row">
              <span className="config-label">System:</span>
              <span className="config-value">{workflow.target_name}</span>
            </div>
            <div className="config-row">
              <span className="config-label">Type:</span>
              <span className="config-value">{workflow.target_type}</span>
            </div>
            {workflow.target_config && Object.entries(workflow.target_config).map(([key, value]) => (
              <div key={key} className="config-row">
                <span className="config-label">{key}:</span>
                <span className="config-value">{typeof value === 'object' ? JSON.stringify(value) : value}</span>
              </div>
            ))}
          </div>
        </div>

        {workflow.ai_agents_enabled && workflow.ai_agents_enabled.length > 0 && (
          <div className="config-card">
            <h3>AI Agents</h3>
            <div className="ai-agents-list">
              {workflow.ai_agents_enabled.map((agent) => (
                <div key={agent} className="ai-agent-badge">
                  {agent.replace('_', ' ').toUpperCase()}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Workflow Visualizer */}
      {graphData && (
        <div className="workflow-visualizer-section">
          <h2><i className="fas fa-project-diagram" aria-hidden="true" /> Workflow Pipeline Visualization</h2>
          <div className="visualizer-container">
            <XStateVisualizer
              graphData={graphData}
              defaultView="stateflow"
              theme="dark"
            />
          </div>
        </div>
      )}

      {/* Execution Metadata — omit raw JSON dump; visible details are surfaced in config cards and archive above */}

      {/* Archive / History */}
      <div className="execution-metadata-section">
        <h3>Archive / History</h3>

        {archiveLoading ? (
          <div className="archive-status">
            <LoadingSpinner variant={SPINNER_VARIANTS?.SMALL || undefined} message="Loading archive..." />
          </div>
        ) : null}

        {!archiveLoading && archiveError ? (
          <div className="archive-error">
            {archiveError}
          </div>
        ) : null}

        {!archiveLoading && !archiveError && archive ? (
          <>
            <div className="config-section">
              <div className="config-card">
                <h3>Datasets</h3>
                <div className="config-details">
                  <div className="config-row">
                    <span className="config-label">Source:</span>
                    <span className="config-value">
                      {archive?.datasets?.source?.name || workflow.source_name}
                    </span>
                  </div>
                  <div className="config-row">
                    <span className="config-label">Source Type:</span>
                    <span className="config-value">
                      {archive?.datasets?.source?.type || workflow.source_type}
                    </span>
                  </div>
                  {archive?.datasets?.source?.connection?.file_path ? (
                    <div className="config-row">
                      <span className="config-label">File:</span>
                      <span className="config-value">{archive.datasets.source.connection.file_path}</span>
                    </div>
                  ) : null}
                  {archive?.datasets?.source_warning ? (
                    <div className="config-row">
                      <span className="config-label">Note:</span>
                      <span className="config-value">{archive.datasets.source_warning}</span>
                    </div>
                  ) : null}
                  <div className="config-row">
                    <span className="config-label">Target:</span>
                    <span className="config-value">{archive?.datasets?.target?.name || workflow.target_name}</span>
                  </div>
                  <div className="config-row">
                    <span className="config-label">Target Type:</span>
                    <span className="config-value">{archive?.datasets?.target?.type || workflow.target_type}</span>
                  </div>
                </div>
              </div>

              <div className="config-card">
                <h3>ETL Output</h3>
                <div className="config-details">
                  {(archive?.etl?.runs || []).length === 0 ? (
                    <div className="config-row">
                      <span className="config-label">Runs:</span>
                      <span className="config-value">None</span>
                    </div>
                  ) : (
                    (archive.etl.runs || []).map((r) => (
                      <div key={r.run_id} className="archive-run">
                        <div className="archive-run-header">
                          <div className="archive-run-id">Run: {r.run_id}</div>
                          {r.status ? <div className="archive-run-status">{r.status}</div> : null}
                        </div>
                        <div className="archive-run-counts">
                          <div>Staged: {r?.counts?.staged_records ?? 0}</div>
                          <div>Parts: {r?.counts?.parts ?? 0}</div>
                          <div>BOM: {r?.counts?.bom_items ?? 0}</div>
                          <div>DQ Gates: {(r?.data_quality?.gates || []).length}</div>
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </div>

              <div className="config-card">
                <h3>Factory Reports</h3>
                <div className="config-details">
                  <div className="config-row">
                    <span className="config-label">Snapshots:</span>
                    <span className="config-value">{archive?.reports?.factory_snapshots_total ?? 0}</span>
                  </div>
                  <div className="archive-snapshots">
                    {(archive?.reports?.factory_snapshots || []).map((s) => (
                      <div key={s.report_id} className="archive-snapshot">
                        <div className="archive-snapshot-top">
                          <div className="archive-snapshot-id">{s.report_id}</div>
                          <div className="archive-snapshot-date">{s.created_at ? new Date(s.created_at).toLocaleString() : ''}</div>
                        </div>
                        <div className="archive-snapshot-meta">
                          <div>Status: {s?.summary?.status || 'unknown'}</div>
                          {s.execution_id ? <div>Exec: {s.execution_id}</div> : null}
                          {s.plm_run_id ? <div>Run: {s.plm_run_id}</div> : null}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              <div className="config-card">
                <h3>Rulesets</h3>
                <div className="config-details">
                  {Object.entries(archive?.rulesets || {}).length === 0 ? (
                    <div className="config-row">
                      <span className="config-label">Rules:</span>
                      <span className="config-value">None</span>
                    </div>
                  ) : (
                    Object.entries(archive.rulesets).map(([entityType, rules]) => (
                      <div key={entityType} className="config-row">
                        <span className="config-label">{entityType}:</span>
                        <span className="config-value">{Array.isArray(rules) ? rules.length : 0}</span>
                      </div>
                    ))
                  )}
                </div>
              </div>
            </div>

            <details className="archive-raw" style={{ display: 'none' }}>
              <summary>Raw archive JSON</summary>
              <pre className="metadata-json">{JSON.stringify(archive, null, 2)}</pre>
            </details>
          </>
        ) : null}
      </div>

      {/* Timestamps */}
      <div className="timestamps-section">
        <div className="timestamp-item">
          <span className="timestamp-label">Created:</span>
          <span className="timestamp-value">{new Date(workflow.created_at).toLocaleString()}</span>
          {workflow.created_by && <span className="timestamp-user">by {workflow.created_by}</span>}
        </div>
        {workflow.started_at && (
          <div className="timestamp-item">
            <span className="timestamp-label">Started:</span>
            <span className="timestamp-value">{new Date(workflow.started_at).toLocaleString()}</span>
          </div>
        )}
        {workflow.completed_at && (
          <div className="timestamp-item">
            <span className="timestamp-label">Completed:</span>
            <span className="timestamp-value">{new Date(workflow.completed_at).toLocaleString()}</span>
          </div>
        )}
      </div>
    </div>
  );
};

export default WorkflowDetailPage;
