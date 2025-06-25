import React, { useRef, useEffect } from 'react';

export function E2ETraceChatPanel({
  chatMessages,
  chatInputValue,
  onChatInputChange,
  onSendMessage,
  isChatSending,
}) {
  const chatInputRef = useRef(null);
  const messagesEndRef = useRef(null);

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !isChatSending) {
      e.preventDefault(); // Prevent form submission if wrapped in form
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
  }, [chatMessages]);

  return (
    <div className="e2etrace-chat-panel">
      <h3>Chat</h3>
      <div className="e2etrace-chat-messages">
        {chatMessages.map((msg, index) => (
          <div key={index} className={`e2etrace-chat-message e2etrace-chat-message-${msg.sender.toLowerCase()}`}>
            <strong>{msg.sender}:</strong> {msg.text}
          </div>
        ))}
        <div ref={messagesEndRef} />
      </div>
      <div className="e2etrace-chat-input-area">
        <input
          type="text"
          ref={chatInputRef}
          value={chatInputValue}
          onChange={onChatInputChange}
          onKeyPress={handleKeyPress}
          disabled={isChatSending}
          placeholder="Ask about the graph..."
          id="e2etrace-chat-input"
          aria-label="Chat input"
        />
        <button id="send-chat-button" onClick={() => !isChatSending && onSendMessage()} disabled={isChatSending}>
          {isChatSending ? 'Sending...' : 'Send'}
        </button>
      </div>
    </div>
  );
}