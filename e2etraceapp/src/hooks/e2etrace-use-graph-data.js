import { useState, useEffect } from 'react';
import { e2etraceFetchWithRetry } from '../api/e2etrace-api';
import { e2etraceCreateTableElementsFromGraph } from '../utils/e2etrace-graph';
import { API_CONFIG } from '../config/api-config.js';

export function useE2ETraceGraphData(setTableElements) {
  const [graphData, setGraphData] = useState({ nodes: [], edges: [] });
  const [loading, setLoading] = useState(true);
  const [loadingError, setLoadingError] = useState(null);

  useEffect(() => {
    let isMounted = true;

    async function fetchInitialData() {
      setLoading(true);
      setLoadingError(null);
      try {
        const response = await e2etraceFetchWithRetry(API_CONFIG.ENDPOINTS.GRAPH);
        const data = await response.json();
        if (isMounted) {
            setGraphData(data);
            if (setTableElements) {
                const tableData = e2etraceCreateTableElementsFromGraph(data);
                setTableElements(tableData);
            }
        }
      } catch (error) {
        console.error('[useGraphData] fetchInitialData: Error caught:', error);
        if (isMounted) {
            setLoadingError(`Error loading graph: ${error.message}. Check console for details.`);
        }
      } finally {
        if (isMounted) {
            setLoading(false);
        }
      }
    }
    fetchInitialData();

    return () => {
        isMounted = false;
    };
  }, [setTableElements]);

  return { graphData, loading, loadingError, setGraphData };
}

export const e2etraceUseGraphData = useE2ETraceGraphData;