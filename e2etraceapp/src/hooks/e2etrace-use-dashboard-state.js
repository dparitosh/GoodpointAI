import { useState } from 'react';
import { e2etraceFetchWithRetry } from '../utils/e2etrace-api';

export function e2etraceUseDashboardState() {
    const [chatMessages, setChatMessages] = useState([]);
    const [chatInputValue, setChatInputValue] = useState('');
    const [isChatSending, setIsChatSending] = useState(false);
    const [tableElements, setTableElements] = useState([]);
  
    const handleSendChatMessage = async () => {
      if (!chatInputValue.trim()) return;
      const userMessage = chatInputValue.trim();
      setChatMessages(prev => [...prev, { sender: 'You', text: userMessage }]);
      setChatInputValue('');
      setIsChatSending(true);

      try { // Corrected function name
        const response = await e2etraceFetchWithRetry('/api/chat', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ query: userMessage })
        });
        if (!response.ok) {
          const errorData = await response.json().catch(() => ({ message: `Chat API error: ${response.status}` }));
          throw new Error(errorData.message || `Chat API error: ${response.status}`);
        }
        const llmResponse = await response.json();
        console.log('[useDashboardState] Full response from chat API:', llmResponse);

        setChatMessages(prev => [...prev, { sender: 'AI', text: llmResponse.textResponse || "Received a response." }]);

        if (llmResponse.graphData && llmResponse.graphData.nodes && llmResponse.graphData.edges) {
          console.log("[useDashboardState] Received new graph data from chat:", llmResponse.graphData);
          return llmResponse.graphData;
        } else if (llmResponse.tableData) {
          console.log("[useDashboardState] Received new table data from chat:", llmResponse.tableData);
          return llmResponse.tableData;
        }
      } catch (error) {
        console.error('Error sending message or processing LLM response:', error);
        setChatMessages(prev => [...prev, { sender: 'System', text: `Error: ${error.message}` }]);
      } finally {
        setIsChatSending(false);
      }
    };
  
    return { chatMessages, setChatMessages, chatInputValue, setChatInputValue, isChatSending, handleSendChatMessage, tableElements, setTableElements };
}