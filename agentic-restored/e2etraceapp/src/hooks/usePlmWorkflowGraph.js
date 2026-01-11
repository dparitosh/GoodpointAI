import { useEffect, useMemo, useState } from 'react';

export const usePlmWorkflowGraph = () => {
  const [graphData, setGraphData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(null);
  const [availability, setAvailability] = useState({ available: false, reason: null });

  useEffect(() => {
    const load = async () => {
      try {
        const availabilityRes = await fetch('/api/plm/workflow/availability');
        if (!availabilityRes.ok) {
          setAvailability({ available: false, reason: `HTTP ${availabilityRes.status}` });
          setGraphData({ nodes: [], edges: [] });
          setLoadError('PLM workflow availability check failed');
          return;
        }

        const availabilityJson = await availabilityRes.json();
        const available = Boolean(availabilityJson?.available);
        const reason = typeof availabilityJson?.reason === 'string' ? availabilityJson.reason : null;
        setAvailability({ available, reason });

        if (!available) {
          setGraphData({ nodes: [], edges: [] });
          setLoadError(reason || 'PLM workflow data is not configured');
          return;
        }

        const workflowRes = await fetch('/api/plm/workflow');
        if (!workflowRes.ok) {
          setGraphData({ nodes: [], edges: [] });
          setLoadError(workflowRes.statusText || `HTTP ${workflowRes.status}`);
          return;
        }

        const data = await workflowRes.json();
        const normalized = {
          ...(typeof data === 'object' && data !== null ? data : {}),
          nodes: Array.isArray(data?.nodes) ? data.nodes : [],
          edges: Array.isArray(data?.edges) ? data.edges : [],
        };
        setGraphData(normalized);
        setLoadError(null);
      } catch (error) {
        setAvailability({ available: false, reason: 'Network error' });
        setGraphData({ nodes: [], edges: [] });
        setLoadError(error?.message || 'Network error');
      } finally {
        setLoading(false);
      }
    };

    load();
  }, []);

  const safeGraphData = useMemo(() => {
    return graphData && typeof graphData === 'object'
      ? {
          ...graphData,
          nodes: Array.isArray(graphData.nodes) ? graphData.nodes : [],
          edges: Array.isArray(graphData.edges) ? graphData.edges : [],
        }
      : { nodes: [], edges: [] };
  }, [graphData]);

  return { graphData: safeGraphData, loading, loadError, availability };
};
