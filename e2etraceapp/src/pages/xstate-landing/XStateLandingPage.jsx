import React, { useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { XStateVisualizer } from '../../components/xstate-visualizer/XStateVisualizer';
import goodPointLogo from '../../assets/goodpoint-logo.svg';
import { getSampleInteractiveStateFlow, SAMPLE_WORKFLOW_ID } from '../../data/sampleInteractiveStateFlow';
import './XStateLandingPage.css';

/**
 * XState Landing Page
 * Main entry point showcasing the interactive State Flow Diagram
 * with full XState-style visualization
 */
const XStateLandingPage = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const [workflows, setWorkflows] = useState([]);
  const [workflowsLoading, setWorkflowsLoading] = useState(true);
  const [workflowsError, setWorkflowsError] = useState(null);

  const [graphData, setGraphData] = useState({ nodes: [], edges: [] });
  const [graphLoading, setGraphLoading] = useState(true);
  const [graphError, setGraphError] = useState(null);

  const selectedWorkflowId = (searchParams.get('workflowId') || SAMPLE_WORKFLOW_ID).trim();

  const safeGraphData = useMemo(() => {
    const data = graphData && typeof graphData === 'object' ? graphData : { nodes: [], edges: [] };
    return {
      ...data,
      nodes: Array.isArray(data.nodes) ? data.nodes : [],
      edges: Array.isArray(data.edges) ? data.edges : [],
    };
  }, [graphData]);

  useEffect(() => {
    let cancelled = false;

    const loadWorkflows = async () => {
      setWorkflowsLoading(true);
      setWorkflowsError(null);

      try {
        const res = await fetch('/api/workflows/');
        const json = res.ok ? await res.json() : [];
        const normalized = Array.isArray(json)
          ? json
          : Array.isArray(json?.workflows)
            ? json.workflows
            : Array.isArray(json?.items)
              ? json.items
              : [];

        if (cancelled) return;
        setWorkflows(normalized);

        const hasQuery = Boolean(searchParams.get('workflowId'));
        if (!hasQuery) {
          const firstWorkflowId = normalized?.[0]?.id || null;
          const nextId = firstWorkflowId || SAMPLE_WORKFLOW_ID;
          setSearchParams({ workflowId: nextId }, { replace: true });
        }
      } catch (e) {
        if (cancelled) return;
        setWorkflows([]);
        setWorkflowsError(e?.message || 'Failed to load workflows');
      } finally {
        if (!cancelled) setWorkflowsLoading(false);
      }
    };

    loadWorkflows();

    return () => {
      cancelled = true;
    };
  }, [searchParams, setSearchParams]);

  useEffect(() => {
    let cancelled = false;

    const loadGraph = async () => {
      setGraphLoading(true);
      setGraphError(null);

      if (selectedWorkflowId === SAMPLE_WORKFLOW_ID) {
        setGraphData(getSampleInteractiveStateFlow());
        setGraphLoading(false);
        return;
      }

      try {
        const res = await fetch(`/api/workflows/${encodeURIComponent(selectedWorkflowId)}`);
        if (!res.ok) {
          if (cancelled) return;
          setGraphData({ nodes: [], edges: [] });
          setGraphError(`Workflow unavailable (HTTP ${res.status})`);
          return;
        }

        const json = await res.json();
        const cfg = (json && typeof json === 'object' ? json.workflow_config : null) || {};
        const normalized = {
          ...(typeof cfg === 'object' && cfg !== null ? cfg : {}),
          nodes: Array.isArray(cfg?.nodes) ? cfg.nodes : [],
          edges: Array.isArray(cfg?.edges) ? cfg.edges : [],
        };

        if (cancelled) return;
        setGraphData(normalized);
      } catch (e) {
        if (cancelled) return;
        setGraphData({ nodes: [], edges: [] });
        setGraphError(e?.message || 'Failed to load workflow');
      } finally {
        if (!cancelled) setGraphLoading(false);
      }
    };

    loadGraph();

    return () => {
      cancelled = true;
    };
  }, [selectedWorkflowId]);

  const handleNodeUpdate = (nodeId, updates) => {
    console.log('Node updated:', nodeId, updates);
    // Handle node updates if needed
  };

  if (workflowsLoading || graphLoading) {
    return (
      <div className="xstate-landing-loading">
        <div className="loading-spinner"></div>
        <p>Loading Interactive State Flow Diagram...</p>
      </div>
    );
  }

  return (
    <div className="xstate-landing-page">
      <div className="landing-header">
        <div className="landing-header-content">
          <img src={goodPointLogo} alt="GoodPoint" className="landing-logo" />
          <div className="landing-title-group">
            <h1>GoodPoint AgenticAI</h1>
            <p className="landing-subtitle">PLM Data Migration Platform - Interactive Workflow Visualization</p>
          </div>
        </div>

        <div className="landing-workflow-selector">
          <label className="landing-workflow-selector__label" htmlFor="workflow-selector">
            Workflow
          </label>
          <select
            id="workflow-selector"
            className="landing-workflow-selector__select"
            value={selectedWorkflowId}
            onChange={(e) => setSearchParams({ workflowId: e.target.value })}
            aria-label="Workflow selector"
          >
            <option value={SAMPLE_WORKFLOW_ID}>Sample Demo Flow</option>
            {workflows.map((wf) => {
              const id = wf?.id;
              if (!id) return null;
              const label = wf?.name || wf?.workflow_name || wf?.title || id;
              return (
                <option key={id} value={id}>
                  {label}
                </option>
              );
            })}
          </select>
          {workflowsError ? (
            <div className="landing-workflow-selector__hint">{String(workflowsError)}</div>
          ) : null}
        </div>

        <div className="landing-stats">
          <div className="stat-badge">
            <span className="stat-value">{safeGraphData.nodes.length}</span>
            <span className="stat-label">Nodes</span>
          </div>
          <div className="stat-badge">
            <span className="stat-value">{safeGraphData.edges.length}</span>
            <span className="stat-label">Connections</span>
          </div>
          <div className="stat-badge">
            <span className="stat-value">7</span>
            <span className="stat-label">Factory Stages</span>
          </div>
          <div className="stat-badge">
            <span className="stat-value">4</span>
            <span className="stat-label">AI Agents</span>
          </div>
        </div>
      </div>

      <XStateVisualizer
        graphData={safeGraphData}
        onNodeUpdate={handleNodeUpdate}
        enabledViewModes={['stateflow']}
      />
    </div>
  );
};

export default XStateLandingPage;
