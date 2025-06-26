import React, { useRef, useEffect } from 'react';
import './e2etrace-chat-panel.css';

export function E2ETraceChatPanel({
  chatMessages,
  chatInputValue,
  onChatInputChange,
  onSendMessage,
  suggestedPrompts,
  isChatSending,
  typingIndicator,
  onAskSelectedNode,
  selectedNodeLabel,
  agentAvatarUrl, // New: agent avatar
  userAvatarUrl,  // New: user avatar
}) {
  const chatInputRef = useRef(null);
  const messagesEndRef = useRef(null);

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey && !isChatSending) {
      e.preventDefault();
      onSendMessage();
    }
  };

  useEffect(() => {
    if (!isChatSending && chatInputRef.current) {
      chatInputRef.current.focus();
    }
  }, [isChatSending]);

  useEffect(() => {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [chatMessages, typingIndicator]);

  return (
    <div className="e2etrace-chat-panel">
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.5rem' }}>
        <h3 style={{ flex: 1 }}>Chat</h3>
        {onAskSelectedNode && selectedNodeLabel && (
          <button
            className="e2etrace-suggested-prompt-button"
            onClick={onAskSelectedNode}
            style={{ fontWeight: 600 }}
          >
            Ask about selected node: "{selectedNodeLabel}"
          </button>
        )}
      </div>
      <div className="e2etrace-chat-messages" role="log" aria-live="polite" tabIndex={0}>
        {chatMessages.map((msg, index) => {
          const isAgent = msg.sender === 'Agent';
          return (
            <div key={index} className={`e2etrace-chat-message e2etrace-chat-message-${isAgent ? 'agent' : 'user'}`.trim()} style={{ display: 'flex', alignItems: isAgent ? 'flex-start' : 'flex-end', gap: '0.5rem' }} tabIndex={0} aria-label={`${isAgent ? 'Agent' : 'You'} message`}> 
              {isAgent && agentAvatarUrl && (
                <img src={agentAvatarUrl} alt="Agent avatar" className="e2etrace-chat-avatar" style={{ width: 32, height: 32, borderRadius: '50%' }} />
              )}
              <div style={{ flex: 1 }}>
                <div style={{ fontWeight: 600, fontSize: '0.95em', marginBottom: 2 }}>{isAgent ? 'Agent' : 'You'}</div>
                <div>{msg.text}</div>
                {msg.timestamp && <div style={{ fontSize: '0.8em', color: '#888', marginTop: 2 }}>{msg.timestamp}</div>}
              </div>
              {!isAgent && userAvatarUrl && (
                <img src={userAvatarUrl} alt="User avatar" className="e2etrace-chat-avatar" style={{ width: 32, height: 32, borderRadius: '50%' }} />
              )}
            </div>
          );
        })}
        {typingIndicator && (
          <div className="e2etrace-chat-typing-indicator">Agent is typing…</div>
        )}
        <div ref={messagesEndRef} />
      </div>
      <div className="e2etrace-chat-input-area">
        <textarea
          ref={chatInputRef}
          value={chatInputValue}
          onChange={onChatInputChange}
          onKeyDown={handleKeyDown}
          disabled={isChatSending}
          placeholder="Ask about the graph..."
          id="e2etrace-chat-input"
          aria-label="Chat input"
          rows={1}
          style={{ resize: 'vertical', minHeight: 36, maxHeight: 120 }}
        />
        <button id="send-chat-button" onClick={() => !isChatSending && onSendMessage()} disabled={isChatSending}>
          {isChatSending ? 'Sending...' : 'Send'}
        </button>
      </div>
      {suggestedPrompts && suggestedPrompts.length > 0 && (
        <div className="e2etrace-suggested-prompts">
          {suggestedPrompts.map((prompt, idx) => (
            <button key={idx} onClick={() => onChatInputChange({ target: { value: prompt } })} className="e2etrace-suggested-prompt-button">
              {prompt}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}