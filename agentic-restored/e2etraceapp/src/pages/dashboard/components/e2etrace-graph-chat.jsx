import React, { useState } from 'react';

export default function E2ETraceGraphChat({ 
  chatMessages = [], 
  chatInputValue = '', 
  isChatSending = false, 
  onSendMessage, 
  onInputChange 
}) {
  const [localMessages, setLocalMessages] = useState([]);
  const [localInputValue, setLocalInputValue] = useState('');
  const [localIsLoading, setLocalIsLoading] = useState(false);

  // Use props if provided, otherwise use local state
  const messages = chatMessages.length > 0 ? chatMessages : localMessages;
  const inputMessage = chatInputValue !== '' ? chatInputValue : localInputValue;
  const isLoading = isChatSending || localIsLoading;

  const handleSendMessage = () => {
    if (!inputMessage.trim()) return;
    
    if (onSendMessage) {
      // Use parent's handler if provided
      onSendMessage();
    } else {
      // Local fallback implementation
      setLocalMessages(prev => [...prev, { text: inputMessage, isUser: true, id: Date.now() }]);
      setLocalInputValue('');
      setLocalIsLoading(true);
      
      // Simulate bot response with a note about connecting to real API
      setTimeout(() => {
        setLocalMessages(prev => [...prev, { 
          text: "Connected to Neo4j backend. Chat functionality requires implementation of natural language processing for graph queries.", 
          isUser: false, 
          id: Date.now() + 1 
        }]);
        setLocalIsLoading(false);
      }, 1000);
    }
  };

  const handleInputChange = (e) => {
    if (onInputChange) {
      onInputChange(e);
    } else {
      setLocalInputValue(e.target.value);
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  return (
    <div style={{ 
      height: '100%', 
      display: 'flex', 
      flexDirection: 'column',
      overflow: 'hidden'
    }}>
      {/* Chat Messages */}
      <div style={{ 
        flex: 1, 
        overflowY: 'auto',
        padding: '0.75rem',
        display: 'flex',
        flexDirection: 'column',
        gap: '0.75rem',
        minHeight: 0
      }}>
        {messages.length === 0 ? (
          <div style={{
            textAlign: 'center',
            color: '#6c757d',
            fontSize: '0.85rem',
            marginTop: '2rem'
          }}>
            Start a conversation about the graph...
          </div>
        ) : (
          messages.map((message, index) => (
            <div
              key={message.id || index}
              style={{
                display: 'flex',
                justifyContent: message.isUser ? 'flex-end' : 'flex-start',
                marginBottom: '0.5rem'
              }}
            >
              <div
                style={{
                  maxWidth: '80%',
                  padding: '0.5rem 0.75rem',
                  borderRadius: '12px',
                  fontSize: '0.85rem',
                  lineHeight: '1.4',
                  backgroundColor: message.isUser ? '#007bff' : '#f8f9fa',
                  color: message.isUser ? '#fff' : '#333',
                  border: message.isUser ? 'none' : '1px solid #e9ecef'
                }}
              >
                {message.sender && (
                  <div style={{ 
                    fontSize: '0.7rem', 
                    opacity: 0.8, 
                    marginBottom: '0.25rem',
                    fontWeight: '600'
                  }}>
                    {message.sender}
                  </div>
                )}
                {message.text}
              </div>
            </div>
          ))
        )}
        {isLoading && (
          <div style={{ display: 'flex', justifyContent: 'flex-start' }}>
            <div style={{
              padding: '0.5rem 0.75rem',
              backgroundColor: '#f8f9fa',
              border: '1px solid #e9ecef',
              borderRadius: '12px',
              fontSize: '0.85rem',
              color: '#6c757d'
            }}>
              AI is thinking...
            </div>
          </div>
        )}
      </div>

      {/* Chat Input */}
      <div style={{
        borderTop: '1px solid #e9ecef',
        padding: '0.75rem',
        backgroundColor: '#f8f9fa'
      }}>
        <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'flex-end' }}>
          <textarea
            value={inputMessage}
            onChange={handleInputChange}
            onKeyPress={handleKeyPress}
            placeholder="Ask about the graph or enter a Cypher query..."
            disabled={isLoading}
            style={{
              flex: 1,
              padding: '0.5rem',
              border: '1px solid #ced4da',
              borderRadius: '6px',
              fontSize: '0.85rem',
              resize: 'none',
              minHeight: '38px',
              maxHeight: '100px',
              backgroundColor: isLoading ? '#f8f9fa' : '#fff'
            }}
            rows={1}
          />
          <button
            onClick={handleSendMessage}
            disabled={!inputMessage.trim() || isLoading}
            style={{
              padding: '0.5rem 1rem',
              border: 'none',
              borderRadius: '6px',
              backgroundColor: '#007bff',
              color: '#fff',
              fontSize: '0.85rem',
              cursor: 'pointer',
              opacity: (!inputMessage.trim() || isLoading) ? 0.6 : 1,
              height: '38px'
            }}
          >
            {isLoading ? '...' : 'Send'}
          </button>
        </div>
        <div style={{
          fontSize: '0.7rem',
          color: '#6c757d',
          marginTop: '0.25rem'
        }}>
          Press Enter to send, Shift+Enter for new line
        </div>
      </div>
    </div>
  );
}