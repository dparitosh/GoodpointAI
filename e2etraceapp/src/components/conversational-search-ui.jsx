/**
 * Conversational Search UI Component
 * 
 * Google-like search interface with chat-style conversations.
 * Supports semantic, vector, and hybrid search modes.
 * Displays results in a professional table format.
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import DOMPurify from 'dompurify';
import './conversational-search-ui.css';
import API_CONFIG, { getFullUrl } from '../config/api-config';

// Search mode configurations
const SEARCH_MODES = {
  semantic: {
    id: 'semantic',
    name: 'Semantic',
    description: 'Full-text search using BM25 with query expansion',
    icon: 'fa-font',
    color: '#4CAF50'
  },
  vector: {
    id: 'vector',
    name: 'Vector',
    description: 'k-NN similarity search using embeddings',
    icon: 'fa-vector-square',
    color: '#2196F3'
  },
  hybrid: {
    id: 'hybrid',
    name: 'Hybrid',
    description: 'Combined semantic + vector + GraphRAG',
    icon: 'fa-layer-group',
    color: '#FF9800'
  }
};

// Source type icons and colors
const SOURCE_STYLES = {
  opensearch_semantic: { icon: 'fa-search', color: '#4CAF50', label: 'Semantic' },
  opensearch_vector: { icon: 'fa-vector-square', color: '#2196F3', label: 'Vector' },
  graphrag: { icon: 'fa-project-diagram', color: '#9C27B0', label: 'GraphRAG' },
  unknown: { icon: 'fa-question', color: '#9E9E9E', label: 'Unknown' }
};

/**
 * Message component for chat history
 */
function ChatMessage({ message, isUser }) {
  return (
    <div className={`chat-message ${isUser ? 'user' : 'assistant'}`}>
      <div className="message-avatar">
        <i className={`fas ${isUser ? 'fa-user' : 'fa-robot'}`} />
      </div>
      <div className="message-content">
        <div className="message-text">{message.content}</div>
        {message.search_mode && (
          <div className="message-meta">
            <span className={`mode-badge mode-${message.search_mode}`}>
              <i className={`fas ${SEARCH_MODES[message.search_mode]?.icon || 'fa-search'}`} />
              {message.search_mode}
            </span>
            {message.results_count !== undefined && (
              <span className="results-count">{message.results_count} results</span>
            )}
            {message.took_ms && (
              <span className="took-time">{message.took_ms}ms</span>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

/**
 * Search mode selector component
 */
function SearchModeSelector({ mode, onChange, disabled }) {
  return (
    <div className="search-mode-selector">
      <span className="mode-label">Search Mode:</span>
      <div className="mode-buttons">
        {Object.values(SEARCH_MODES).map(m => (
          <button
            key={m.id}
            className={`mode-btn ${mode === m.id ? 'active' : ''}`}
            onClick={() => onChange(m.id)}
            disabled={disabled}
            title={m.description}
            style={{ '--mode-color': m.color }}
          >
            <i className={`fas ${m.icon}`} />
            <span>{m.name}</span>
          </button>
        ))}
      </div>
    </div>
  );
}

/**
 * Search result card - Google-like display
 */
function SearchResultCard({ result, index }) {
  const sourceStyle = SOURCE_STYLES[result.source_type] || SOURCE_STYLES.unknown;
  
  // Parse highlights if available - sanitize HTML to prevent XSS
  const renderSnippet = () => {
    if (result.highlights && result.highlights.length > 0) {
      // Sanitize HTML to prevent XSS attacks
      const cleanHtml = DOMPurify.sanitize(result.highlights[0]);
      return (
        <p 
          className="result-snippet" 
          dangerouslySetInnerHTML={{ __html: cleanHtml }} 
        />
      );
    }
    return <p className="result-snippet">{result.snippet}</p>;
  };
  
  return (
    <div className="search-result-card">
      <div className="result-header">
        <span className="result-rank">#{index + 1}</span>
        <span 
          className="result-source-type" 
          style={{ '--source-color': sourceStyle.color }}
        >
          <i className={`fas ${sourceStyle.icon}`} />
          {sourceStyle.label}
        </span>
        <span className="result-score">
          {(result.score * 100).toFixed(1)}% match
        </span>
      </div>
      
      <h3 className="result-title">
        <a href={result.url || '#'} target="_blank" rel="noopener noreferrer">
          {result.title}
        </a>
      </h3>
      
      <div className="result-source">
        <i className="fas fa-file" />
        <span>{result.source}</span>
      </div>
      
      {renderSnippet()}
      
      {result.graph_context && (
        <div className="result-graph-context">
          <span className="graph-badge">
            <i className="fas fa-project-diagram" />
            {result.graph_context.node_type}
          </span>
          {result.graph_context.relationships?.length > 0 && (
            <span className="relationships-count">
              {result.graph_context.relationships.length} relationships
            </span>
          )}
        </div>
      )}
      
      {result.metadata && Object.keys(result.metadata).length > 0 && (
        <div className="result-metadata">
          {Object.entries(result.metadata).slice(0, 3).map(([key, value]) => (
            <span key={key} className="metadata-tag">
              {key}: {String(value).substring(0, 30)}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

/**
 * Search results table view
 */
function SearchResultsTable({ results }) {
  return (
    <div className="search-results-table-container">
      <table className="search-results-table">
        <thead>
          <tr>
            <th>#</th>
            <th>Title</th>
            <th>Source</th>
            <th>Type</th>
            <th>Score</th>
          </tr>
        </thead>
        <tbody>
          {results.map((result, index) => {
            const sourceStyle = SOURCE_STYLES[result.source_type] || SOURCE_STYLES.unknown;
            return (
              <tr key={result.id}>
                <td className="col-rank">{index + 1}</td>
                <td className="col-title">
                  <a href={result.url || '#'} target="_blank" rel="noopener noreferrer">
                    {result.title}
                  </a>
                </td>
                <td className="col-source">{result.source}</td>
                <td className="col-type">
                  <span className="source-badge" style={{ '--source-color': sourceStyle.color }}>
                    <i className={`fas ${sourceStyle.icon}`} />
                    {sourceStyle.label}
                  </span>
                </td>
                <td className="col-score">{(result.score * 100).toFixed(1)}%</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

/**
 * File Results Table - Separate panel showing files with download links
 */
function FileResultsTable({ results }) {
  if (!results || results.length === 0) return null;
  
  // Extract filename from source field
  const extractFileName = (source) => {
    if (!source) return 'Unknown';
    // Handle paths like "000678_A;1-SKF_6306-2Z7097_Prt2.stp"
    const parts = source.split(/[/\\]/);
    return parts[parts.length - 1] || source;
  };
  
  // Get file extension
  const getFileExtension = (filename) => {
    const ext = filename.split('.').pop()?.toLowerCase() || '';
    return ext;
  };
  
  // Get icon for file type
  const getFileIcon = (filename) => {
    const ext = getFileExtension(filename);
    const iconMap = {
      'stp': 'fa-cube',
      'step': 'fa-cube',
      'stl': 'fa-cubes',
      'pdf': 'fa-file-pdf',
      'doc': 'fa-file-word',
      'docx': 'fa-file-word',
      'xls': 'fa-file-excel',
      'xlsx': 'fa-file-excel',
      'csv': 'fa-file-csv',
      'json': 'fa-file-code',
      'xml': 'fa-file-code',
      'txt': 'fa-file-alt',
      'jpg': 'fa-file-image',
      'jpeg': 'fa-file-image',
      'png': 'fa-file-image',
      'gif': 'fa-file-image',
    };
    return iconMap[ext] || 'fa-file';
  };
  
  // Get category badge color
  const getCategoryColor = (category) => {
    const colors = {
      'PLM Part': '#4CAF50',
      'PLM Assembly': '#2196F3',
      'Graph Document': '#9C27B0',
      'Document': '#FF9800'
    };
    return colors[category] || '#9E9E9E';
  };

  // Generate download URL
  const getDownloadUrl = (result) => {
    // If there's a direct URL, use it
    if (result.url && result.url !== '#') return result.url;
    // Otherwise construct from source
    const filename = extractFileName(result.source);
    return getFullUrl(API_CONFIG.ENDPOINTS.FILES_DOWNLOAD(filename));
  };
  
  return (
    <div className="file-results-panel">
      <div className="file-results-header">
        <h3>
          <i className="fas fa-folder-open" />
          Files Found ({results.length})
        </h3>
        <span className="download-hint">
          <i className="fas fa-info-circle" />
          Click filename to download
        </span>
      </div>
      <div className="file-results-table-wrapper">
        <table className="file-results-table">
          <thead>
            <tr>
              <th className="col-icon"></th>
              <th className="col-filename">File Name</th>
              <th className="col-category">Category</th>
              <th className="col-source-idx">Source Index</th>
              <th className="col-relevance">Relevance</th>
              <th className="col-actions">Actions</th>
            </tr>
          </thead>
          <tbody>
            {results.map((result, index) => {
              const filename = extractFileName(result.source);
              const categoryColor = getCategoryColor(result.category);
              const downloadUrl = getDownloadUrl(result);
              
              return (
                <tr key={result.id || index}>
                  <td className="col-icon">
                    <i className={`fas ${getFileIcon(filename)}`} />
                  </td>
                  <td className="col-filename">
                    <a 
                      href={downloadUrl} 
                      target="_blank" 
                      rel="noopener noreferrer"
                      title={`Download ${filename}`}
                    >
                      {filename}
                    </a>
                    {result.title && result.title !== filename && (
                      <span className="file-title">{result.title}</span>
                    )}
                  </td>
                  <td className="col-category">
                    <span 
                      className="category-badge" 
                      style={{ '--category-color': categoryColor }}
                    >
                      {result.category || 'Document'}
                    </span>
                  </td>
                  <td className="col-source-idx">
                    <span className="source-index">
                      {result.metadata?.index || result.source_type || 'unknown'}
                    </span>
                  </td>
                  <td className="col-relevance">
                    <div className="relevance-bar">
                      <div 
                        className="relevance-fill"
                        style={{ width: `${Math.min(result.score * 100, 100)}%` }}
                      />
                      <span className="relevance-text">
                        {(result.score * 100).toFixed(0)}%
                      </span>
                    </div>
                  </td>
                  <td className="col-actions">
                    <a 
                      href={downloadUrl}
                      className="download-btn"
                      target="_blank"
                      rel="noopener noreferrer"
                      title="Download file"
                    >
                      <i className="fas fa-download" />
                    </a>
                    {result.url && result.url !== '#' && (
                      <a 
                        href={result.url}
                        className="view-btn"
                        target="_blank"
                        rel="noopener noreferrer"
                        title="View in new tab"
                      >
                        <i className="fas fa-external-link-alt" />
                      </a>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

/**
 * Sources summary component
 */
function SourcesSummary({ summary }) {
  if (!summary || Object.keys(summary).length === 0) return null;
  
  return (
    <div className="sources-summary">
      <span className="summary-label">Sources:</span>
      {Object.entries(summary).map(([source, count]) => {
        const style = SOURCE_STYLES[source] || SOURCE_STYLES.unknown;
        return (
          <span 
            key={source} 
            className="source-count"
            style={{ '--source-color': style.color }}
          >
            <i className={`fas ${style.icon}`} />
            {count} {style.label}
          </span>
        );
      })}
    </div>
  );
}

/**
 * Main Conversational Search UI Component
 */
export default function ConversationalSearchUI({ onResultSelect: _onResultSelect }) {
  const [query, setQuery] = useState('');
  const [searchMode, setSearchMode] = useState('hybrid');
  const [isSearching, setIsSearching] = useState(false);
  const [error, setError] = useState(null);
  const [viewMode, setViewMode] = useState('cards'); // 'cards' or 'table'
  
  // Conversation state
  const [conversationId, setConversationId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [results, setResults] = useState([]);
  const [sourcesSummary, setSourcesSummary] = useState({});
  const [searchStats, setSearchStats] = useState(null);
  
  // Service health
  const [serviceHealth, setServiceHealth] = useState(null);
  
  const inputRef = useRef(null);
  const resultsRef = useRef(null);
  
  // Check service health on mount
  useEffect(() => {
    fetch(getFullUrl(API_CONFIG.ENDPOINTS.SEARCH_HEALTH))
      .then(res => res.json())
      .then(data => setServiceHealth(data))
      .catch(() => setServiceHealth({ status: 'unknown' }));
  }, []);
  
  // Execute search
  const executeSearch = useCallback(async () => {
    if (!query.trim()) return;
    
    setIsSearching(true);
    setError(null);
    
    // Add user message to conversation
    const userMessage = {
      role: 'user',
      content: query,
      search_mode: searchMode,
      timestamp: new Date().toISOString()
    };
    setMessages(prev => [...prev, userMessage]);
    
    try {
      const response = await fetch(getFullUrl(API_CONFIG.ENDPOINTS.SEARCH_QUERY), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query: query.trim(),
          mode: searchMode,
          conversation_id: conversationId,
          top_k: 20,
          include_snippets: true
        })
      });
      
      if (!response.ok) {
        throw new Error(`Search failed: ${response.statusText}`);
      }
      
      const data = await response.json();
      
      // Update state with results
      setResults(data.results || []);
      setSourcesSummary(data.sources_summary || {});
      setConversationId(data.conversation_id);
      setSearchStats({
        total: data.total_count,
        took_ms: data.took_ms,
        mode: data.mode
      });
      
      // Add assistant message
      const assistantMessage = {
        role: 'assistant',
        content: data.assistant_message,
        search_mode: data.mode,
        results_count: data.total_count,
        took_ms: data.took_ms,
        timestamp: data.timestamp
      };
      setMessages(prev => [...prev, assistantMessage]);
      
      // Clear input
      setQuery('');
      
      // Scroll to results
      if (resultsRef.current) {
        resultsRef.current.scrollIntoView({ behavior: 'smooth' });
      }
      
    } catch (err) {
      setError(err.message);
      
      // Add error message to conversation
      const errorMessage = {
        role: 'assistant',
        content: `Search failed: ${err.message}. Please try again.`,
        timestamp: new Date().toISOString()
      };
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setIsSearching(false);
    }
  }, [query, searchMode, conversationId]);
  
  // Handle key press
  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      executeSearch();
    }
  };
  
  // Clear conversation
  const clearConversation = () => {
    setMessages([]);
    setResults([]);
    setSourcesSummary({});
    setConversationId(null);
    setSearchStats(null);
    setQuery('');
    inputRef.current?.focus();
  };
  
  return (
    <div className="conversational-search-ui">
      {/* Header with service status */}
      <div className="search-header">
        <div className="header-title">
          <i className="fas fa-search" />
          <h2>Conversational Search</h2>
        </div>
        <div className="header-status">
          {serviceHealth && (
            <span className={`health-badge ${serviceHealth.status === 'healthy' && (!serviceHealth.opensearch?.available || !serviceHealth.graphrag?.available) ? 'degraded' : serviceHealth.status}`}>
              <i className={`fas ${serviceHealth.status === 'healthy' && serviceHealth.opensearch?.available && serviceHealth.graphrag?.available ? 'fa-check-circle' : 'fa-exclamation-circle'}`} />
              {serviceHealth.status === 'healthy' && (!serviceHealth.opensearch?.available || !serviceHealth.graphrag?.available) ? 'Degraded' : serviceHealth.status}
            </span>
          )}
          {serviceHealth?.opensearch?.available === false && (
            <span className="service-badge error" title="OpenSearch Unavailable">
              <i className="fas fa-exclamation-triangle" /> No Vector Search
            </span>
          )}
          {serviceHealth?.graphrag?.available && (
            <span className="service-badge graphrag">
              <i className="fas fa-project-diagram" /> GraphRAG
            </span>
          )}
        </div>
      </div>
      
      {/* Search input area */}
      <div className="search-input-area">
        <SearchModeSelector 
          mode={searchMode} 
          onChange={setSearchMode}
          disabled={isSearching}
        />
        
        <div className="search-box">
          <div className="search-input-wrapper">
            <i className="fas fa-search search-icon" />
            <input
              ref={inputRef}
              type="text"
              placeholder="Ask a question or search for documents..."
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyPress={handleKeyPress}
              disabled={isSearching}
            />
            {query && (
              <button 
                className="clear-btn" 
                onClick={() => setQuery('')}
                disabled={isSearching}
              >
                <i className="fas fa-times" />
              </button>
            )}
          </div>
          <button 
            className="search-btn"
            onClick={executeSearch}
            disabled={isSearching || !query.trim()}
          >
            {isSearching ? (
              <><i className="fas fa-spinner fa-spin" /> Searching...</>
            ) : (
              <><i className="fas fa-paper-plane" /> Search</>
            )}
          </button>
        </div>
        
        {/* Quick suggestions */}
        <div className="quick-suggestions">
          <span className="suggestions-label">Try:</span>
          <button onClick={() => setQuery('Find all CAD documents')}>CAD documents</button>
          <button onClick={() => setQuery('Show parts with quality issues')}>Quality issues</button>
          <button onClick={() => setQuery('Recent workflow failures')}>Workflow failures</button>
          <button onClick={() => setQuery('Assembly relationships')}>Assemblies</button>
        </div>
      </div>
      
      {/* Error display */}
      {error && (
        <div className="search-error">
          <i className="fas fa-exclamation-triangle" />
          <span>{error}</span>
          <button onClick={() => setError(null)}><i className="fas fa-times" /></button>
        </div>
      )}
      
      {/* Conversation history */}
      {messages.length > 0 && (
        <div className="conversation-history">
          <div className="conversation-header">
            <h3><i className="fas fa-comments" /> Conversation</h3>
            <button className="clear-btn" onClick={clearConversation}>
              <i className="fas fa-trash" /> Clear
            </button>
          </div>
          <div className="messages-list">
            {messages.map((msg, idx) => (
              <ChatMessage 
                key={idx} 
                message={msg} 
                isUser={msg.role === 'user'} 
              />
            ))}
          </div>
        </div>
      )}
      
      {/* File Results Table - Separate panel showing file names with download links */}
      <FileResultsTable results={results} />
      
      {/* Search results */}
      {results.length > 0 && (
        <div className="search-results" ref={resultsRef}>
          <div className="results-header">
            <div className="results-info">
              <h3>
                <i className="fas fa-list" /> 
                {searchStats?.total || results.length} Results
              </h3>
              <span className="results-time">
                in {searchStats?.took_ms || 0}ms
              </span>
              <span className={`results-mode mode-${searchStats?.mode || searchMode}`}>
                <i className={`fas ${SEARCH_MODES[searchStats?.mode || searchMode]?.icon}`} />
                {searchStats?.mode || searchMode}
              </span>
            </div>
            
            <div className="results-controls">
              <SourcesSummary summary={sourcesSummary} />
              
              <div className="view-toggle">
                <button 
                  className={viewMode === 'cards' ? 'active' : ''}
                  onClick={() => setViewMode('cards')}
                  title="Card view"
                >
                  <i className="fas fa-th-large" />
                </button>
                <button 
                  className={viewMode === 'table' ? 'active' : ''}
                  onClick={() => setViewMode('table')}
                  title="Table view"
                >
                  <i className="fas fa-table" />
                </button>
              </div>
            </div>
          </div>
          
          {viewMode === 'cards' ? (
            <div className="results-cards">
              {results.map((result, index) => (
                <SearchResultCard 
                  key={result.id} 
                  result={result} 
                  index={index}
                />
              ))}
            </div>
          ) : (
            <SearchResultsTable results={results} />
          )}
        </div>
      )}
      
      {/* Empty state */}
      {messages.length === 0 && results.length === 0 && (
        <div className="empty-state">
          <i className="fas fa-search-plus" />
          <h3>Start Your Search</h3>
          <p>
            Use natural language to search across documents, CAD files, and knowledge graphs.
            Choose your search mode above for different search strategies.
          </p>
          <div className="mode-descriptions">
            {Object.values(SEARCH_MODES).map(m => (
              <div key={m.id} className="mode-description">
                <i className={`fas ${m.icon}`} style={{ color: m.color }} />
                <strong>{m.name}:</strong> {m.description}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
