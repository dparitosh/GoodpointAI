import React, { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { XStateVisualizer } from '../../components/xstate-visualizer/XStateVisualizer';
import './WorkflowDetailPage.css';

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

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
  const loadAbortRef = useRef(null);
  const loadSeqRef = useRef(0);

  // Load workflow details on mount and when workflowId changes
  useEffect(() => {
    loadWorkflowDetails();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [workflowId]);

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
    };
  }, [workflowId]);

  // Auto-refresh when workflow is running (separate effect)
  useEffect(() => {
    let interval;
    if (workflow?.status === 'running') {
      interval = setInterval(() => {
        // Wrap in try-catch to prevent interval from continuing on error
        try {
          loadWorkflowDetails();
        } catch (error) {
          console.error('Error in auto-refresh:', error);
          clearInterval(interval);
        }
      }, 5000);
    }
    
    return () => {
      if (interval) {
        clearInterval(interval);
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [workflow?.status]);

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
        workflowRes = await fetch(`/api/workflows/${workflowId}`, { signal: controller.signal });
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
          const graphRes = await fetch(`/api/workflows/${workflowId}/graph`, { signal: controller.signal });
          if (graphRes.ok) {
            const graphData = await graphRes.json();
            if (seq !== loadSeqRef.current) return;
            setGraphData(graphData);
          }
        } catch {
          // Fallback to default PLM workflow if custom graph not available
          const fallbackRes = await fetch('/api/plm/workflow', { signal: controller.signal });
          if (fallbackRes.ok) {
            const fallbackData = await fallbackRes.json();
            if (seq !== loadSeqRef.current) return;
            setGraphData(fallbackData);
          }
        }
      } else {
        console.error('Workflow not found:', workflowId);
        navigate('/workflow-manager', { 
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
      
      const response = await fetch(`/api/workflows/${workflowId}/execute`, {
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
      } else {
        const error = await response.json();
        console.error(`Workflow action ${action} failed:`, error.detail);
      }
    } catch (error) {
      if (error.name === 'AbortError') {
        console.error('Workflow action request timed out');
      } else {
        console.error('Error executing workflow action:', error);
      }
    }
  };

  if (loading) {
    return (
      <div className="workflow-detail-loading">
        <div className="loading-spinner"></div>
        <p>Loading workflow details...</p>
      </div>
    );
  }

  if (!workflow) {
    return (
      <div className="workflow-detail-error">
        <h2>Workflow Not Found</h2>
        <button onClick={() => navigate('/workflow-manager')}>← Back to Workflows</button>
      </div>
    );
  }

  return (
    <div className="workflow-detail-page">
      {/* Header */}
      <div className="workflow-detail-header">
        <button className="btn-back" onClick={() => navigate('/workflow-manager')}>
          ← Back to Workflows
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
          {workflow.status === 'draft' || workflow.status === 'configured' || workflow.status === 'paused' ? (
            <button 
              className="btn-action btn-start"
              onClick={() => handleWorkflowAction('start')}
            >
              ▶ Start Workflow
            </button>
          ) : null}
          
          {workflow.status === 'running' ? (
            <>
              <button 
                className="btn-action btn-pause"
                onClick={() => handleWorkflowAction('pause')}
              >
                ‖ Pause
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
          <h2>◳ Workflow Pipeline Visualization</h2>
          <div className="visualizer-container">
            <XStateVisualizer
              graphData={graphData}
              defaultView="stateflow"
              theme="dark"
            />
          </div>
        </div>
      )}

      {/* Execution Metadata */}
      {workflow.execution_metadata && (
        <div className="execution-metadata-section">
          <h3>Execution Details</h3>
          <pre className="metadata-json">
            {JSON.stringify(workflow.execution_metadata, null, 2)}
          </pre>
        </div>
      )}

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
