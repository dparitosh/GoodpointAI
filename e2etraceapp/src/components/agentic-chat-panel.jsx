import React, { useState, useEffect, useRef, useCallback } from 'react';
import { agenticOrchestrator, AGENT_TYPES } from '../services/agentic-orchestrator.js';

/**
 * AGENTIC CHAT PANEL - Multi-Agent Conversation Interface
 * 
 * Implements threaded conversations with intelligent agent coordination
 * Following AGENTIC_REFACTORING_GUIDE.md principles
 */



import './agentic-chat-panel.css';

const AgenticChatPanel = ({
  onSendMessage,
  onChatInputChange,
  suggestedPrompts = [],
  selectedNodeLabel,
  onAskSelectedNode,
  className = '',
  isVisible = true
}) => {
  const [messages, setMessages] = useState([]);
  const [inputValue, setInputValue] = useState('');
  const [isProcessing, setIsProcessing] = useState(false);
  const [activeAgents, setActiveAgents] = useState([]);
  const [_conversationThreads, _setConversationThreads] = useState(new Map());
  const [currentThread, _setCurrentThread] = useState('main');
  const [agentTypingIndicator, setAgentTypingIndicator] = useState(null);
  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);

  // INITIALIZE AGENTIC CHAT SYSTEM
  useEffect(() => {
    initializeAgenticChat();
    return () => {
      // Cleanup
    };
  }, []);

  const initializeAgenticChat = async () => {
    try {
      // Get system status from orchestrator
      const systemStatus = agenticOrchestrator.getSystemStatus();
      
      // Initialize with welcome message from Chat Coordinator
      const welcomeMessage = {
        id: `msg_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
        type: 'agent',
        content: 'Hello! I\'m your AI assistant with specialized agents ready to help. I can analyze data, orchestrate ETL processes, optimize queries, and more. What would you like to explore?',
        agent: AGENT_TYPES.CHAT_COORDINATOR,
        timestamp: new Date(),
        thread: 'main'
      };

      setMessages([welcomeMessage]);
      setActiveAgents(systemStatus._context?.activeAgents || []);

      // Add suggested prompts based on agent capabilities
      if (suggestedPrompts.length === 0) {
        addIntelligentSuggestions();
      }

    } catch (error) {
      console.error("Error:", error);
      addErrorMessage('Failed to initialize chat system. Please try again.');
    }
  };

  // PROCESS USER MESSAGE with Agent Coordination
  const handleSendMessage = useCallback(async (message = inputValue) => {
    if (!message.trim() || isProcessing) return;

    const userMessage = {
      id: `msg_${Date.now()}_user_${Math.random().toString(36).substr(2, 9)}`,
      type: 'user',
      content: message,
      timestamp: new Date(),
      thread: currentThread
    };

    setMessages(prev => [...prev, userMessage]);
    setInputValue('');
    setIsProcessing(true);
    setAgentTypingIndicator(AGENT_TYPES.CHAT_COORDINATOR);

    try {
      // Analyze message intent and route to appropriate agents
      const chatTask = {
        type: 'CHAT_PROCESSING',
        requiredCapabilities: [
          'process_natural_language',
          'coordinate_agent_responses',
          'route_user_requests'
        ],
        payload: {
          message,
          context: {
            selectedNode: selectedNodeLabel,
            conversationHistory: messages.slice(-5), // Last 5 messages for context
            currentThread,
            timestamp: new Date()
          }
        }
      };

      const response = await agenticOrchestrator.processTask(chatTask);
      
      // Process multi-agent response
      await processAgentResponse(response, userMessage);

      if (onSendMessage) {
        onSendMessage(userMessage);
      }

    } catch (error) {
      console.error("Error:", error);
      addErrorMessage('Sorry, I encountered an error processing your message. Please try again.');
    } finally {
      setIsProcessing(false);
      setAgentTypingIndicator(null);
    }
  }, [inputValue, isProcessing, currentThread, messages, selectedNodeLabel, onSendMessage]);

  // Process agent response and coordination
  const processAgentResponse = async (response, userMessage) => {
    const { intent, suggestedAgents, primaryResponse, collaborationNeeded } = response;

    // Add primary response from Chat Coordinator
    const primaryMessage = {
      id: `msg_${Date.now()}`,
      type: 'agent',
      content: primaryResponse || 'I understand your request. Let me coordinate with the appropriate agents.',
      agent: AGENT_TYPES.CHAT_COORDINATOR,
      timestamp: new Date(),
      thread: currentThread,
      intent
    };

    setMessages(prev => [...prev, primaryMessage]);

    // If collaboration is needed, orchestrate multi-agent response
    if (collaborationNeeded && suggestedAgents?.length > 0) {
      await orchestrateMultiAgentResponse(userMessage, suggestedAgents, intent);
    }
  };

  // Orchestrate multi-agent responses
  const orchestrateMultiAgentResponse = async (userMessage, agents, intent) => {
    for (const agentType of agents) {
      setAgentTypingIndicator(agentType);

      try {
        const agentTask = createAgentSpecificTask(userMessage.content, agentType, intent);
        const agentResponse = await agenticOrchestrator.processTask(agentTask);

        if (agentResponse?.message) {
          const agentMessage = {
            id: `msg_${Date.now()}_${agentType}`,
            type: 'agent',
            content: agentResponse.message,
            agent: agentType,
            timestamp: new Date(),
            thread: currentThread,
            data: agentResponse.data,
            visualizations: agentResponse.visualizations
          };

          setMessages(prev => [...prev, agentMessage]);

          // Add delay for natural conversation flow
          await new Promise(resolve => setTimeout(resolve, 1000));
        }

      } catch (error) {
        console.error("Error:", error);
      }
    }

    setAgentTypingIndicator(null);
  };

  // Create agent-specific tasks
  const createAgentSpecificTask = (message, agentType, intent) => {
    const baseTasks = {
      [AGENT_TYPES.DATA_ANALYST]: {
        type: 'DATA_ANALYSIS',
        requiredCapabilities: ['analyze_data_patterns', 'generate_insights'],
        payload: { query: message, intent, analysisType: 'conversational' }
      },
      [AGENT_TYPES.ETL_ORCHESTRATOR]: {
        type: 'PIPELINE_ORCHESTRATION',
        requiredCapabilities: ['manage_data_pipelines', 'coordinate_nifi_flows'],
        payload: { request: message, intent, mode: 'advisory' }
      },
      [AGENT_TYPES.QUERY_PLANNER]: {
        type: 'GRAPH_QUERY',
        requiredCapabilities: ['optimize_graph_queries', 'plan_execution_strategies'],
        payload: { naturalLanguageQuery: message, intent, optimize: true }
      },
      [AGENT_TYPES.VISUALIZATION_AGENT]: {
        type: 'VISUALIZATION_GENERATION',
        requiredCapabilities: ['create_chart_configurations', 'generate_graph_layouts'],
        payload: { request: message, intent, format: 'chat_friendly' }
      },
      [AGENT_TYPES.QUALITY_MONITOR]: {
        type: 'QUALITY_ASSESSMENT',
        requiredCapabilities: ['monitor_data_quality', 'validate_transformations'],
        payload: { context: message, intent, reportLevel: 'summary' }
      }
    };

    return baseTasks[agentType] || baseTasks[AGENT_TYPES.CHAT_COORDINATOR];
  };

  // Handle input changes
  const handleInputChange = (e) => {
    const value = e.target.value;
    setInputValue(value);
    
    if (onChatInputChange) {
      onChatInputChange(value);
    }
  };

  // Handle key press
  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  // Handle suggested prompts
  const handleSuggestedPrompt = (prompt) => {
    setInputValue(prompt);
    inputRef.current?.focus();
  };

  // Ask about selected node
  const handleAskSelectedNode = () => {
    if (selectedNodeLabel && onAskSelectedNode) {
      const nodeQuery = `Tell me about the selected node: ${selectedNodeLabel}`;
      handleSendMessage(nodeQuery);
      onAskSelectedNode();
    }
  };

  // Add error message
  const addErrorMessage = (errorText) => {
    const errorMessage = {
      id: `msg_${Date.now()}error`,
      type: 'system',
      content: errorText,
      timestamp: new Date(),
      thread: currentThread,
      isError: true
    };

    setMessages(prev => [...prev, errorMessage]);
  };

  // Add intelligent suggestions
  const addIntelligentSuggestions = () => {
    const _suggestions = [
      'Analyze the graph structure and patterns',
      'Show me data quality metrics',
      'Optimize the current query performance',
      'Generate a visualization for this data',
      'Plan an ETL pipeline for data transformation',
      'What are the most connected nodes?'
    ];

    // Add suggestions based on context
    // This could be expanded with dynamic suggestions from agents
  };

  // SCROLL TO BOTTOM
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // RENDER MESSAGE with Agent-Specific Styling
  const renderMessage = (message) => {
    const isUser = message.type === 'user';
    const _isSystem = message.type === 'system';
    const agentInfo = getAgentInfo(message.agent);

    return (
      <div 
        key={message.id}
        className={`message ${message.type} ${message.isError ? 'error' : ''}`}
      >
        <div className="message-header">
          {!isUser && (
            <div className="agent-avatar">
              <span className="agent-icon">{agentInfo.icon}</span>
              <span className="agent-name">{agentInfo.name}</span>
            </div>
          )}
          <span className="message-time">
            {message.timestamp instanceof Date 
              ? message.timestamp.toLocaleTimeString() 
              : new Date(message.timestamp || Date.now()).toLocaleTimeString()}
          </span>
        </div>
        
        <div className="message-content">
          {message.content}
          
          {message.data && (
            <div className="message-_data">
              <details>
                <summary>View Data</summary>
                <pre>{JSON.stringify(message.data, null, 2)}</pre>
              </details>
            </div>
          )}
          
          {message.visualizations && (
            <div className="message-visualizations">
              {message.visualizations.map((viz, index) => (
                <div key={index} className="visualization-suggestion">
                  ◳ {viz.title}: {viz.description}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    );
  };

  // GET AGENT INFORMATION
  const getAgentInfo = (agentType) => {
    const agentConfig = {
      [AGENT_TYPES.CHAT_COORDINATOR]: { icon: '◉', name: 'Chat Coordinator' },
      [AGENT_TYPES.DATA_ANALYST]: { icon: '◳', name: 'Data Analyst' },
      [AGENT_TYPES.ETL_ORCHESTRATOR]: { icon: '↻', name: 'ETL Orchestrator' },
      [AGENT_TYPES.QUERY_PLANNER]: { icon: '◆', name: 'Query Planner' },
      [AGENT_TYPES.VISUALIZATION_AGENT]: { icon: '◻', name: 'Visualization Agent' },
      [AGENT_TYPES.QUALITY_MONITOR]: { icon: '✓', name: 'Quality Monitor' }
    };

    return agentConfig[agentType] || { icon: '✧', name: 'AI Agent' };
  };

  // RENDER TYPING INDICATOR
  const renderTypingIndicator = () => {
    if (!agentTypingIndicator) return null;

    const agentInfo = getAgentInfo(agentTypingIndicator);

    return (
      <div className="typing-indicator">
        <div className="agent-avatar">
          <span className="agent-icon">{agentInfo.icon}</span>
          <span className="agent-name">{agentInfo.name}</span>
        </div>
        <div className="typing-animation">
          <span>is thinking</span>
          <div className="dots">
            <span>.</span>
            <span>.</span>
            <span>.</span>
          </div>
        </div>
      </div>
    );
  };

  if (!isVisible) return null;

  return (
    <div className={`agentic-chat-panel ${className}`}>
      <div className="chat-header">
        <h3>◉ Multi-Agent Assistant</h3>
        <div className="active-agents">
          {activeAgents.slice(0, 3).map(agent => {
            const agentInfo = getAgentInfo(agent.type);
            return (
              <span key={agent.id} className="active-agent" title={agentInfo.name}>
                {agentInfo.icon}
              </span>
            );
          })}
          {activeAgents.length > 3 && (
            <span className="more-agents">+{activeAgents.length - 3}</span>
          )}
        </div>
      </div>

      <div className="messages-container">
        {messages.map(renderMessage)}
        {renderTypingIndicator()}
        <div ref={messagesEndRef} />
      </div>

      {suggestedPrompts.length > 0 && (
        <div className="suggested-prompts">
          {suggestedPrompts.slice(0, 3).map((prompt, index) => (
            <button
              key={index}
              className="suggested-prompt"
              onClick={() => handleSuggestedPrompt(prompt)}
              disabled={isProcessing}
            >
              {prompt}
            </button>
          ))}
        </div>
      )}

      <div className="chat-input-container">
        {selectedNodeLabel && (
          <button
            className="ask-node-button"
            onClick={handleAskSelectedNode}
            disabled={isProcessing}
            title={`Ask about ${selectedNodeLabel}`}
          >
            ? Ask about "{selectedNodeLabel}"
          </button>
        )}

        <div className="input-wrapper">
          <textarea
            ref={inputRef}
            value={inputValue}
            onChange={handleInputChange}
            onKeyPress={handleKeyPress}
            placeholder="Ask the agents anything about your data..."
            disabled={isProcessing}
            rows="2"
          />
          <button
            onClick={() => handleSendMessage()}
            disabled={isProcessing || !inputValue.trim()}
            className="send-button"
          >
            {isProcessing ? '…' : '➔'}
          </button>
        </div>
      </div>
    </div>
  );
};

export default AgenticChatPanel;
