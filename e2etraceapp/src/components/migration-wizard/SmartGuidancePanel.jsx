import React, { useState, useEffect, useCallback, useRef, useLayoutEffect } from 'react';
import { API_CONFIG } from '../../config/api-config.js';
import './SmartGuidancePanel.css';

const RECOMMENDATION_META = {
  discovery: {
    icon: 'fa-compass',
    color: 'blue',
    label: 'Discovery',
    actionLabel: 'Start Discovery',
    actionIcon: 'fa-search',
    description: 'Scan your files safely',
  },
  profiling: {
    icon: 'fa-microscope',
    color: 'purple',
    label: 'Profiling',
    actionLabel: 'Start Semantic Analysis',
    actionIcon: 'fa-dna',
    description: 'Deep column-level insights',
  },
  quality: {
    icon: 'fa-shield-alt',
    color: 'green',
    label: 'Quality Check',
    actionLabel: 'Start Quality Scan',
    actionIcon: 'fa-check-circle',
    description: 'Detect and fix data issues',
  },
};

// Quick-ask suggestion chips shown before the user types
const SUGGESTION_CHIPS = [
  { label: 'What should I do first?', icon: 'fa-play-circle' },
  { label: 'How long will this take?', icon: 'fa-clock' },
  { label: 'Will this change my data?', icon: 'fa-shield-alt' },
  { label: 'What files are supported?', icon: 'fa-file-alt' },
];

const STATIC_FALLBACK = (previousRuns) =>
  previousRuns
    ? {
        recommendation: 'profiling',
        headline: 'Run Data Profiling',
        reason: 'Discovery is done. Profiling goes deeper — it reads each column and checks for patterns, blanks, and unexpected values.',
        expected_outcome: 'A column-by-column quality report and automatic classification of your data.',
        next_steps: ["Click 'Run Semantic Analysis'", 'Review the column quality report', 'Proceed to Field Mapping'],
        complexity: 'low',
        estimated_time: '3-8 minutes',
        tips: ['Profiling uses your existing discovery results — no extra setup needed'],
        llm_powered: false,
      }
    : {
        recommendation: 'discovery',
        headline: 'Start with Discovery',
        reason: "Your data hasn't been scanned yet. Discovery gives you a quick, safe look at what files you have and flags any obvious issues.",
        expected_outcome: 'A clear summary of your files, record counts, and initial data issues.',
        next_steps: ["Click 'Run Discovery' to scan your data", 'Review the insights that appear', 'Accept discovery and move to Profiling'],
        complexity: 'low',
        estimated_time: '2-5 minutes',
        tips: ["Discovery is read-only — it won't change your data", 'You can re-run it any time to refresh the results'],
        llm_powered: false,
      };

// Animated ellipsis for "thinking" state
function ThinkingDots() {
  return (
    <span className="sgp-thinking-dots" aria-label="Thinking">
      <span /><span /><span />
    </span>
  );
}

const SmartGuidancePanel = ({
  sourceSystem = null,
  fileCount = null,
  fileTypes = null,
  previousRuns = false,
  userRole = 'business',
  onAction,
  // eslint-disable-next-line no-unused-vars
  onDismiss,
}) => {
  const [loading, setLoading] = useState(true);
  const [guidance, setGuidance] = useState(null);
  const [nlpQuery, setNlpQuery] = useState('');
  const [nlpLoading, setNlpLoading] = useState(false);
  // Chat history: [{role:'assistant'|'user', text, guidance?}]
  const [chatHistory, setChatHistory] = useState([]);
  // Progressive disclosure: which card indices have steps expanded
  const [expandedCards, setExpandedCards] = useState({});
  const inputRef = useRef(null);
  const chatEndRef = useRef(null);

  const toggleSteps = useCallback((idx) => {
    setExpandedCards(prev => ({ ...prev, [idx]: !prev[idx] }));
  }, []);

  const scrollToBottom = () => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useLayoutEffect(() => {
    scrollToBottom();
  }, [chatHistory, loading]);

  const fetchGuidance = useCallback(async (nlpText = null) => {
    if (nlpText) setNlpLoading(true);
    else setLoading(true);

    try {
      const baseUrl = API_CONFIG?.API_BASE_URL || '';
      const endpoint = `${baseUrl}${API_CONFIG.ENDPOINTS.AGENTIC_SMART_GUIDANCE}`;

      const body = {
        source_name:   sourceSystem?.name || null,
        source_id:     sourceSystem?.id   || null,
        file_count:    typeof fileCount === 'number' ? fileCount : null,
        file_types:    Array.isArray(fileTypes) ? fileTypes : null,
        previous_runs: Boolean(previousRuns),
        user_role:     userRole,
        ...(nlpText ? { nlp_query: nlpText } : {}),
      };

      const resp = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });

      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const data = await resp.json();

      if (nlpText) {
        setChatHistory(prev => {
          // If the last message is the user's question, always append the response after it
          // (never move the answer above the user's message)
          if (prev.length > 0 && prev[prev.length - 1].role === 'user') {
            return [...prev, { role: 'assistant', text: data.headline, guidance: data }];
          }
          // Last message is already an assistant card — replace it only if same recommendation
          // to avoid stacking two identical cards
          const lastAssistantIdx = prev.map((m, i) => m.role === 'assistant' && m.guidance ? i : -1).filter(i => i !== -1).pop();
          if (lastAssistantIdx != null && prev[lastAssistantIdx]?.guidance?.recommendation === data.recommendation) {
            const updated = [...prev];
            updated[lastAssistantIdx] = { role: 'assistant', text: data.headline, guidance: data };
            return updated;
          }
          return [...prev, { role: 'assistant', text: data.headline, guidance: data }];
        });
        setGuidance(data);
      } else {
        setGuidance(data);
        setChatHistory([{ role: 'assistant', text: data.headline, guidance: data }]);
      }
    } catch {
      const fallback = STATIC_FALLBACK(previousRuns);
      if (nlpText) {
        // Show a plain text response — do NOT duplicate the existing guidance card
        setChatHistory(prev => [
          ...prev,
          { role: 'assistant', text: "I'm having trouble reaching the AI service right now. Please check the backend is running or try again shortly.", guidance: null },
        ]);
      } else {
        setGuidance(fallback);
        setChatHistory([{ role: 'assistant', text: fallback.headline, guidance: fallback }]);
      }
    } finally {
      setLoading(false);
      setNlpLoading(false);
    }
  }, [sourceSystem, fileCount, fileTypes, previousRuns, userRole]);

  useEffect(() => { fetchGuidance(); }, [fetchGuidance]);

  const handleNlpSubmit = useCallback((text) => {
    const trimmed = (text || nlpQuery).trim();
    if (!trimmed || nlpLoading) return;
    setChatHistory(prev => [...prev, { role: 'user', text: trimmed }]);
    setNlpQuery('');
    fetchGuidance(trimmed);
  }, [nlpQuery, nlpLoading, fetchGuidance]);

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleNlpSubmit();
    }
  };

  const handleAction = () => {
    if (guidance?.recommendation && onAction) {
      onAction(guidance.recommendation);
    }
  };

  // The most recent assistant guidance entry
  const latestGuidance = [...chatHistory].reverse().find(m => m.role === 'assistant' && m.guidance)?.guidance || guidance;

  return (
    <div className="smart-guidance-panel" role="region" aria-label="Smart Guidance">

      {/* ── Header ── */}
      <div className="sgp-header">
        <div className="sgp-header-left">
          <div className="sgp-avatar">
            <i className="fas fa-robot" aria-hidden="true" />
          </div>
          <div>
            <div className="sgp-title">AI Migration Assistant</div>
            <div className="sgp-subtitle">Ask me anything about your data</div>
          </div>
        </div>
        <div className="sgp-header-right">
          {latestGuidance?.llm_powered && (
            <span className="sgp-ai-badge">
              <i className="fas fa-sparkles" />
              AI
            </span>
          )}
          {onDismiss && (
            <button className="sgp-dismiss" onClick={onDismiss} title="Dismiss" aria-label="Dismiss guidance">
              <i className="fas fa-times" />
            </button>
          )}
        </div>
      </div>

      {/* ── Chat window ── */}
      <div className="sgp-chat-window">

        {/* Initial loading skeleton */}
        {loading && (
          <div className="sgp-bubble assistant sgp-bubble-loading" aria-busy="true">
            <ThinkingDots />
          </div>
        )}

        {/* Chat messages */}
        {!loading && chatHistory.map((msg, idx) => {
          const isUser = msg.role === 'user';
          const msgGuidance = msg.guidance;
          const msgMeta = msgGuidance ? (RECOMMENDATION_META[msgGuidance.recommendation] || RECOMMENDATION_META.discovery) : null;

          return (
            <div key={idx} className={`sgp-message-row ${isUser ? 'user' : 'assistant'}`}>
              {!isUser && (
                <div className="sgp-msg-avatar">
                  <i className="fas fa-robot" />
                </div>
              )}

              <div className={`sgp-bubble ${isUser ? 'user' : 'assistant'}`}>
                {isUser ? (
                  <span>{msg.text}</span>
                ) : msgGuidance ? (
                  <div className={`sgp-answer-card sgp-type-${msgGuidance.recommendation}`}>

                    {/* ── Type pill + meta ── */}
                    <div className="sgp-answer-top">
                      <span className={`sgp-type-pill ${msgGuidance.recommendation}`}>
                        <i className={`fas ${msgMeta.icon}`} />
                        {msgMeta.label}
                      </span>
                      <div className="sgp-answer-meta">
                        {msgGuidance.estimated_time && (
                          <span className="sgp-meta-tag">
                            <i className="fas fa-clock" />
                            {msgGuidance.estimated_time}
                          </span>
                        )}
                        {msgGuidance.complexity && (
                          <span className="sgp-meta-tag">
                            <span className={`sgp-dot ${msgGuidance.complexity}`} />
                            {msgGuidance.complexity.charAt(0).toUpperCase() + msgGuidance.complexity.slice(1)} effort
                          </span>
                        )}
                      </div>
                    </div>

                    {/* ── Headline ── */}
                    <h4 className="sgp-answer-headline">{msgGuidance.headline}</h4>

                    {/* ── Reason — conversational prose, no label ── */}
                    {msgGuidance.reason && (
                      <p className="sgp-answer-prose">{msgGuidance.reason}</p>
                    )}

                    {/* ── Progressive disclosure: steps + outcome + tip ── */}
                    {(msgGuidance.next_steps?.length > 0 || msgGuidance.expected_outcome || msgGuidance.tips?.length > 0) && (
                      <div className="sgp-details-section">
                        <button
                          className="sgp-details-toggle"
                          onClick={() => toggleSteps(idx)}
                          aria-expanded={!!expandedCards[idx]}
                        >
                          <i className="fas fa-list-ol" />
                          How it works
                          <i className={`fas fa-chevron-${expandedCards[idx] ? 'up' : 'down'} sgp-toggle-chevron`} />
                        </button>

                        {expandedCards[idx] && (
                          <div className="sgp-details-body">
                            {/* Connected timeline steps */}
                            {msgGuidance.next_steps?.length > 0 && (
                              <div className="sgp-timeline">
                                {msgGuidance.next_steps.map((step, si) => (
                                  <div key={si} className="sgp-tl-item">
                                    <div className="sgp-tl-marker">{si + 1}</div>
                                    <div className="sgp-tl-text">{step}</div>
                                  </div>
                                ))}
                              </div>
                            )}

                            {/* Expected outcome callout */}
                            {msgGuidance.expected_outcome && (
                              <div className="sgp-outcome-row">
                                <i className="fas fa-check-circle" />
                                <span>{msgGuidance.expected_outcome}</span>
                              </div>
                            )}

                            {/* Tip — single inline note */}
                            {msgGuidance.tips?.length > 0 && (
                              <p className="sgp-tip-note">
                                <i className="fas fa-lightbulb" />
                                {msgGuidance.tips[0]}
                              </p>
                            )}
                          </div>
                        )}
                      </div>
                    )}

                    {/* ── Actions — only on last assistant message ── */}
                    {idx === chatHistory.length - 1 && (
                      <div className="sgp-answer-actions">
                        <button
                          className={`sgp-cta-btn sgp-cta-${msgGuidance.recommendation}`}
                          onClick={handleAction}
                        >
                          <i className={`fas ${msgMeta.actionIcon}`} />
                          {msgMeta.actionLabel}
                        </button>
                        {onDismiss && (
                          <button className="sgp-link-btn" onClick={onDismiss}>
                            I'll choose manually
                          </button>
                        )}
                      </div>
                    )}

                  </div>
                ) : (
                  <span>{msg.text}</span>
                )}
              </div>
            </div>
          );
        })}

        {/* NLP thinking indicator */}
        {nlpLoading && (
          <div className="sgp-message-row assistant">
            <div className="sgp-msg-avatar"><i className="fas fa-robot" /></div>
            <div className="sgp-bubble assistant sgp-bubble-loading">
              <ThinkingDots />
            </div>
          </div>
        )}

        <div ref={chatEndRef} />
      </div>

      {/* ── Suggestion chips (only before first user message) ── */}
      {chatHistory.filter(m => m.role === 'user').length === 0 && !loading && (
        <div className="sgp-chips" role="list" aria-label="Quick suggestions">
          {SUGGESTION_CHIPS.map((chip) => (
            <button
              key={chip.label}
              className="sgp-chip"
              role="listitem"
              onClick={() => handleNlpSubmit(chip.label)}
              disabled={nlpLoading}
            >
              <i className={`fas ${chip.icon}`} />
              {chip.label}
            </button>
          ))}
        </div>
      )}

      {/* ── NLP input bar ── */}
      <div className="sgp-input-bar">
        <div className="sgp-input-wrap">
          <i className="fas fa-comment-dots sgp-input-icon" aria-hidden="true" />
          <input
            ref={inputRef}
            className="sgp-input"
            type="text"
            placeholder="Ask a question about your migration…"
            value={nlpQuery}
            onChange={(e) => setNlpQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={nlpLoading || loading}
            aria-label="Ask AI assistant"
            maxLength={300}
          />
          <button
            className="sgp-send-btn"
            onClick={() => handleNlpSubmit()}
            disabled={!nlpQuery.trim() || nlpLoading || loading}
            aria-label="Send"
          >
            {nlpLoading ? <i className="fas fa-spinner fa-spin" /> : <i className="fas fa-paper-plane" />}
          </button>
        </div>
      </div>

    </div>
  );
};

export default SmartGuidancePanel;
