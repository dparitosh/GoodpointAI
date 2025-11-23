/**
 * Graph Explorer Page - Main page for Neo4j graph visualization
 * Integrates with GraphQL, Neo4j GraphRAG, and migration history
 * Powered by GoodPoint AI - TCS UI/UX Compliant
 */

import React, { useState, useEffect } from 'react';
import connectionService from '../../services/connectionService';
import graphIntegrationService from '../../services/GraphIntegrationService';
import goodPointLogo from '../../assets/goodpoint-logo.svg';
import './GraphExplorerPage.css';

const GraphExplorerPage = () => {
  // Local state management (replaced Recoil)
  const [graphData, setGraphData] = useState({
    nodes: [],
    edges: [],
    loading: false,
    lastUpdated: null
  });
  
  const [filters, setFilters] = useState({
    limit: 100,
    entityTypes: [],
    relationshipTypes: [],
    searchQuery: ''
  });
  
  const [connection, setConnection] = useState({
    connected: false,
    status: 'disconnected',
    config: {
      uri: 'bolt://localhost:7687',
      user: 'neo4j',
      password: '',
      database: 'neo4j',
      auto_connect: false
    }
  });
  
  const [queryPanel, setQueryPanel] = useState({
    query: '',
    results: null,
    executing: false,
    error: null
  });
  
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    // Setup event listeners
    const handleConnected = (data) => {
      setConnection(prev => ({ ...prev, connected: true, status: 'connected' }));
    };

    const handleDisconnected = () => {
      setConnection(prev => ({ ...prev, connected: false, status: 'disconnected' }));
    };

    const handleGraphDataLoaded = (data) => {
      setGraphData(prev => ({ ...prev, ...data, loading: false }));
    };

    const handleError = (data) => {
      setError(data.error);
      setLoading(false);
    };

    connectionService.addEventListener('connected', handleConnected);
    connectionService.addEventListener('disconnected', handleDisconnected);
    connectionService.addEventListener('graph-data-loaded', handleGraphDataLoaded);
    connectionService.addEventListener('connection-error', handleError);

    return () => {
      connectionService.removeEventListener('connected', handleConnected);
      connectionService.removeEventListener('disconnected', handleDisconnected);
      connectionService.removeEventListener('graph-data-loaded', handleGraphDataLoaded);
      connectionService.removeEventListener('connection-error', handleError);
    };
  }, []);

  const handleConnect = async () => {
    try {
      setLoading(true);
      setError(null);
      await connectionService.connect(connection.config);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleDisconnect = () => {
    connectionService.disconnect();
  };

  const handleLoadData = async () => {
    try {
      setLoading(true);
      setError(null);
      await connectionService.loadGraphData(filters);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleExecuteQuery = async () => {
    if (!queryPanel.query.trim()) return;

    try {
      setQueryPanel(prev => ({ ...prev, executing: true, error: null }));
      const results = await connectionService.executeQuery(queryPanel.query);
      setQueryPanel(prev => ({ ...prev, results, executing: false }));
    } catch (err) {
      setQueryPanel(prev => ({ ...prev, error: err.message, executing: false }));
    }
  };

  const handleFilterChange = (key, value) => {
    setFilters(prev => ({ ...prev, [key]: value }));
  };

  return (
    <div className="graph-explorer-page">
      {/* Header with branding */}
      <div className="page-header">
        <div className="header-content">
          <img src={goodPointLogo} alt="GoodPoint" className="page-logo" />
          <div className="header-title">
            <h1>Graph Explorer</h1>
            <p className="header-subtitle">AI powered PLM Data migration</p>
          </div>
        </div>
      </div>

      {/* Connection Panel */}
      <div className="connection-panel card">
        <h2>Neo4j Connection</h2>
        <div className="connection-status">
          <span className={`status-indicator ${connection.status}`}></span>
          <span className="status-text">
            {connection.connected ? 'Connected' : 'Disconnected'}
          </span>
        </div>
        
        {!connection.connected && (
          <div className="connection-form">
            <div className="form-group">
              <label>URI:</label>
              <input
                type="text"
                value={connection.config.uri}
                onChange={(e) => setConnection(prev => ({
                  ...prev,
                  config: { ...prev.config, uri: e.target.value }
                }))}
                placeholder="bolt://localhost:7687"
              />
            </div>
            <div className="form-group">
              <label>Username:</label>
              <input
                type="text"
                value={connection.config.user}
                onChange={(e) => setConnection(prev => ({
                  ...prev,
                  config: { ...prev.config, user: e.target.value }
                }))}
                placeholder="neo4j"
              />
            </div>
            <div className="form-group">
              <label>Password:</label>
              <input
                type="password"
                value={connection.config.password}
                onChange={(e) => setConnection(prev => ({
                  ...prev,
                  config: { ...prev.config, password: e.target.value }
                }))}
                placeholder="password"
              />
            </div>
            <button 
              onClick={handleConnect} 
              disabled={loading}
              className="btn-primary"
            >
              {loading ? 'Connecting...' : 'Connect'}
            </button>
          </div>
        )}
        
        {connection.connected && (
          <button 
            onClick={handleDisconnect}
            className="btn-secondary"
          >
            Disconnect
          </button>
        )}
      </div>

      {/* Filters Panel */}
      {connection.connected && (
        <div className="filters-panel card">
          <h2>Filters</h2>
          <div className="filter-group">
            <label>Limit:</label>
            <input
              type="number"
              value={filters.limit}
              onChange={(e) => handleFilterChange('limit', parseInt(e.target.value))}
              min="10"
              max="1000"
            />
          </div>
          <div className="filter-group">
            <label>Search:</label>
            <input
              type="text"
              value={filters.searchQuery}
              onChange={(e) => handleFilterChange('searchQuery', e.target.value)}
              placeholder="Search nodes..."
            />
          </div>
          <button 
            onClick={handleLoadData} 
            disabled={loading}
            className="btn-primary"
          >
            {loading ? 'Loading...' : 'Load Graph Data'}
          </button>
        </div>
      )}

      {/* Query Panel */}
      {connection.connected && (
        <div className="query-panel card">
          <h2>Cypher Query</h2>
          <textarea
            value={queryPanel.query}
            onChange={(e) => setQueryPanel(prev => ({ ...prev, query: e.target.value }))}
            placeholder="MATCH (n) RETURN n LIMIT 25"
            rows="4"
          />
          <button 
            onClick={handleExecuteQuery}
            disabled={queryPanel.executing || !queryPanel.query.trim()}
            className="btn-primary"
          >
            {queryPanel.executing ? 'Executing...' : 'Execute Query'}
          </button>
          
          {queryPanel.results && (
            <div className="query-results">
              <h3>Results:</h3>
              <pre>{JSON.stringify(queryPanel.results, null, 2)}</pre>
            </div>
          )}
          
          {queryPanel.error && (
            <div className="error-message">{queryPanel.error}</div>
          )}
        </div>
      )}

      {/* Graph Visualization Area */}
      {connection.connected && graphData.nodes.length > 0 && (
        <div className="graph-container card">
          <h2>Graph Visualization</h2>
          <div className="graph-stats">
            <span>Nodes: {graphData.nodes.length}</span>
            <span>Edges: {graphData.edges.length}</span>
            {graphData.lastUpdated && (
              <span>Last Updated: {new Date(graphData.lastUpdated).toLocaleTimeString()}</span>
            )}
          </div>
          <div className="graph-visualization">
            <p className="placeholder-text">
              Graph visualization will be rendered here using Cytoscape.js or D3.js
            </p>
          </div>
        </div>
      )}

      {/* Error Display */}
      {error && (
        <div className="error-banner">
          <strong>Error:</strong> {error}
          <button onClick={() => setError(null)} className="btn-close">×</button>
        </div>
      )}
    </div>
  );
};

export default GraphExplorerPage;
