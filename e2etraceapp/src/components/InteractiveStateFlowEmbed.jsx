import React, { useEffect, useMemo, useState } from 'react';
import { XStateVisualizer } from './xstate-visualizer/XStateVisualizer';
import { usePlmWorkflowGraph } from '../hooks/usePlmWorkflowGraph';
import { getSampleInteractiveStateFlow } from '../data/sampleInteractiveStateFlow';

export const InteractiveStateFlowEmbed = ({ mode = 'live' }) => {
  const isSample = mode === 'sample';
  const { graphData, loading, loadError } = usePlmWorkflowGraph();

  const [workflows, setWorkflows] = useState([]);
  const [workflowsLoading, setWorkflowsLoading] = useState(true);
  const [workflowsError, setWorkflowsError] = useState(null);
  const [selectedWorkflowId, setSelectedWorkflowId] = useState('');

  const [workflowGraphData, setWorkflowGraphData] = useState(null);
  const [workflowGraphLoading, setWorkflowGraphLoading] = useState(false);
  const [workflowGraphError, setWorkflowGraphError] = useState(null);

  useEffect(() => {
    if (isSample) return;

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

        if (!selectedWorkflowId) {
          const firstWorkflowId = normalized?.[0]?.id || '';
          setSelectedWorkflowId(firstWorkflowId);
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
  }, [isSample, selectedWorkflowId]);

  useEffect(() => {
    if (isSample) return;
    if (!selectedWorkflowId) {
      setWorkflowGraphData(null);
      setWorkflowGraphError(null);
      return;
    }

    let cancelled = false;

    const loadWorkflowGraph = async () => {
      setWorkflowGraphLoading(true);
      setWorkflowGraphError(null);

      try {
        const res = await fetch(`/api/workflows/${encodeURIComponent(selectedWorkflowId)}`);
        if (!res.ok) {
          if (cancelled) return;
          setWorkflowGraphData({ nodes: [], edges: [] });
          setWorkflowGraphError(`Workflow unavailable (HTTP ${res.status})`);
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
        setWorkflowGraphData(normalized);
      } catch (e) {
        if (cancelled) return;
        setWorkflowGraphData({ nodes: [], edges: [] });
        setWorkflowGraphError(e?.message || 'Failed to load workflow');
      } finally {
        if (!cancelled) setWorkflowGraphLoading(false);
      }
    };

    loadWorkflowGraph();

    return () => {
      cancelled = true;
    };
  }, [isSample, selectedWorkflowId]);

  const workflowNavigatorHint = useMemo(() => {
    if (isSample) return '';
    if (workflowsLoading) return 'Loading workflows…';
    if (workflowsError) return String(workflowsError);
    if (!workflows || workflows.length === 0) return 'No workflow instances available.';
    if (workflowGraphLoading) return 'Loading selected workflow…';
    if (workflowGraphError) return String(workflowGraphError);
    return '';
  }, [isSample, workflowsLoading, workflowsError, workflows, workflowGraphLoading, workflowGraphError]);

  const effectiveGraphData = isSample
    ? getSampleInteractiveStateFlow()
    : selectedWorkflowId
      ? (workflowGraphData || { nodes: [], edges: [] })
      : graphData;

  const effectiveLoading = isSample ? false : (loading || (Boolean(selectedWorkflowId) && workflowGraphLoading));
  const _effectiveLoadError = isSample ? null : loadError;

  if (effectiveLoading) {
    return (
      <div className="xstate-visualizer__loading" style={{ padding: '1rem' }}>
        <div className="xstate-visualizer__loading-spinner" />
        <div className="xstate-visualizer__loading-text">Loading Interactive State Flow…</div>
      </div>
    );
  }

  return (
    <div>
      <XStateVisualizer
        graphData={effectiveGraphData}
        embedded
        enabledViewModes={['stateflow']}
        navigatorVariant="workflow"
        workflowOptions={workflows}
        selectedWorkflowId={selectedWorkflowId}
        onWorkflowSelect={setSelectedWorkflowId}
        workflowNavigatorHint={workflowNavigatorHint}
      />
    </div>
  );
};
