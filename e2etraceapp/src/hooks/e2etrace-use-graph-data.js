import { useState, useEffect } from 'react';
import { e2etraceFetchWithRetry } from '../api/e2etrace-api';
import { e2etraceCreateTableElementsFromGraph } from '../utils/e2etrace-graph';
import { API_CONFIG } from '../config/api-config.js';

export function e2etraceUseGraphData(setTableElements) {
  const [graphData, setGraphData] = useState({ nodes: [], edges: [] });
  const [loading, setLoading] = useState(true);
  const [loadingError, setLoadingError] = useState(null);

  useEffect(() => {
    let isMounted = true;

    async function fetchInitialData() {
      console.log('[useGraphData] fetchInitialData: Setting loading to true.');
      setLoading(true);
      setLoadingError(null);
      try {
        console.log('[useGraphData] fetchInitialData: Attempting to fetch', API_CONFIG.ENDPOINTS.GRAPH);
        const response = await e2etraceFetchWithRetry(API_CONFIG.ENDPOINTS.GRAPH);
        console.log('[useGraphData] fetchInitialData: Received response status:', response.status);
        const data = await response.json();
        console.log('[useGraphData] fetchInitialData: Successfully parsed JSON data.');
        if (isMounted) {
            setGraphData(data);
            console.log('[useGraphData] fetchInitialData: Graph data set.');
            if (setTableElements) {
                const tableData = e2etraceCreateTableElementsFromGraph(data);
                setTableElements(tableData);
                console.log('[useGraphData] fetchInitialData: Table elements set.');
            }
        }
      } catch (error) {
        console.error('[useGraphData] fetchInitialData: Error caught:', error);
        if (isMounted) {
            setLoadingError(`Error loading graph: ${error.message}. Check console for details.`);
        }
      } finally {
        console.log('[useGraphData] fetchInitialData: In finally block, setting loading to false.');
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