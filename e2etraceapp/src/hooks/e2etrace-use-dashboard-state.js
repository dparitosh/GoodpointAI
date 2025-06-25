import { useState } from 'react';
import { e2etraceFetchWithRetry } from '../utils/e2etrace-api';
import { e2etraceCreateTableElementsFromGraph } from '../utils/e2etrace-graph';

export function e2etraceUseDashboardState(setGraphData, _setDashboardMetrics, setTableElements) { // _setDashboardMetrics is ignored as dashboard metrics are now handled by analytics page
    const [chatMessages, setChatMessages] = useState([]);
    const [chatInputValue, setChatInputValue] = useState('');
    const [isChatSending, setIsChatSending] = useState(false);
  
    const onChatInputChange = (e) => {
        setChatInputValue(e.target.value);
    };

    const handleSendChatMessage = async () => {
      if (!chatInputValue.trim()) return;
      // The user input is now treated as a Cypher query to match the backend /api/query endpoint
      const cypherQuery = chatInputValue.trim();
      setChatMessages(prev => [...prev, { sender: 'You', text: cypherQuery, id: Date.now() }]);
      setChatInputValue('');
      setIsChatSending(true);

      try {
        // Point to the correct backend endpoint for executing queries
        const response = await e2etraceFetchWithRetry('/api/query', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          // The body now matches the QueryRequest Pydantic model in the backend
          body: JSON.stringify({ query: cypherQuery, params: {} })
        });
        if (!response.ok) {
          // The backend provides detailed errors, which we can display to the user
          const errorData = await response.json().catch(() => ({ detail: `API error: ${response.status} - ${response.statusText}` }));
          throw new Error(errorData.detail || `API error: ${response.status}`);
        }
        const queryResponse = await response.json();
        console.log('[useDashboardState] Full response from /api/query:', queryResponse);

        // Create a user-friendly text response from the query summary
        let aiTextResponse = "Query executed successfully.";
        if (queryResponse.summaryInfo) {
            const summary = queryResponse.summaryInfo;
            const updates = [];
            if (summary.nodes_created) updates.push(`${summary.nodes_created} nodes created`);
            if (summary.nodes_deleted) updates.push(`${summary.nodes_deleted} nodes deleted`);
            if (summary.relationships_created) updates.push(`${summary.relationships_created} relationships created`);
            if (summary.relationships_deleted) updates.push(`${summary.relationships_deleted} relationships deleted`);
            if (summary.properties_set) updates.push(`${summary.properties_set} properties set`);
            if (updates.length > 0) {
                aiTextResponse = `Query summary: ${updates.join(', ')}.`;
            }
        }
        setChatMessages(prev => [...prev, { sender: 'AI', text: aiTextResponse, id: Date.now() + 1 }]);

        // The response from /api/query is the graph data itself.
        if (queryResponse && queryResponse.nodes && queryResponse.edges) {
          console.log("[useDashboardState] Received new graph data from query:", queryResponse);
          setGraphData?.(queryResponse);
          setTableElements?.(e2etraceCreateTableElementsFromGraph(queryResponse));
        }
      } catch (error) {
        console.error('Error sending query or processing response:', error);
        setChatMessages(prev => [...prev, { sender: 'System', text: `Error: ${error.message}` , id: Date.now() + 2 }]);
      } finally {
        setIsChatSending(false);
      }
    };
  
    return { chatMessages, chatInputValue, isChatSending, handleSendChatMessage, onChatInputChange };
}