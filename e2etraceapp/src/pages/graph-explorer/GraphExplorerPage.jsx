/**
 * Graph Explorer Page - Main page for Neo4j graph visualization
 * Integrates with GraphQL, Neo4j GraphRAG, and migration history
 */

import React, { useState, useEffect } from 'react';
import { useRecoilState, useRecoilValue } from 'recoil';
import {
  graphDataAtom,
  graphFiltersAtom,
  neo4jConnectionAtom,
  graphQueryPanelAtom
} from '../../state/atoms/graphAtoms';
import connectionService from '../../services/connectionService';
import graphIntegrationService from '../../services/GraphIntegrationService';
import './GraphExplorerPage.css';

const GraphExplorerPage = () => {
  const [graphData, setGraphData] = useRecoilState(graphDataAtom);
  const [filters, setFilters] = useRecoilState(graphFiltersAtom);
  const [connection, setConnection] = useRecoilState(neo4jConnectionAtom);
  const [queryPanel, setQueryPanel] = useRecoilState(graphQueryPanelAtom);
  
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

    // Auto-connect if configured
    if (connection.auto_connect && !connection.connected) {
      handleConnect();
    }

    return () => {
      connectionService.removeEventListener('connected', handleConnected);
      connectionService.removeEventListener('disconnected', handleDisconnected);
      connectionService.removeEventListener('graph-data-loaded', handleGraphDataLoaded);
      connectionService.removeEventListener('connection-error', handleError);
    };
  }, []);

  const handleConnect = async () => {
    setLoading(true);
    setError(null);
    
    try {
      await connectionService.connect(
        connection.uri,
        connection.user,
        connection.password
      );
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
    setLoading(true);
    setError(null);
    
    try {
      await connectionService.loadGraphData(filters);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleExecuteQuery = async () => {
    setQueryPanel(prev => ({ ...prev, executing: true, error: null }));
    
    try {
      const results = await connectionService.executeQuery(queryPanel.query);
      setQueryPanel(prev => ({ ...prev, results, executing: false }));
    } catch (err) {
      setQueryPanel(prev => ({ ...prev, error: err.message, executing: false }));
    }
  };

  return (
    <div className="graph-explorer-page">
      <header className="graph-explorer-header">
        <h1>Graph Explorer</h1>
        <div className="connection-controls">
          {!connection.connected ? (
            <button onClick={handleConnect} disabled={loading}>
              Connect to Neo4j
            </button>
          ) : (
            <>
              <span className="connection-status">Connected</span>
              <button onClick={handleDisconnect}>Disconnect</button>
            </>
          )}
        </div>
      </header>

      {error && (
        <div className="error-message">
          {error}
        </div>
      )}

      <main className="graph-explorer-content">
        <div className="graph-controls">
          <h2>Filters</h2>
          <div className="filter-group">
            <label>
              Limit:
              <input
                type="number"
                value={filters.limit}
                onChange={(e) => setFilters(prev => ({ ...prev, limit: parseInt(e.target.value) }))}
                min="1"
                max="1000"
              />
            </label>
          </div>
          
          <button onClick={handleLoadData} disabled={!connection.connected || loading}>
            Load Graph Data
          </button>
        </div>

        <div className="graph-visualization">
          {loading && <div className="loading">Loading graph data...</div>}
          
          {graphData.nodes.length > 0 && (
            <div className="graph-stats">
              <p>Nodes: {graphData.nodes.length}</p>
              <p>Edges: {graphData.edges.length}</p>
              {graphData.lastUpdated && (
                <p>Last Updated: {new Date(graphData.lastUpdated).toLocaleString()}</p>
              )}
            </div>
          )}

          <div className="graph-canvas">
            {/* Graph visualization would go here - using Cytoscape, D3, or similar */}
            <p className="placeholder-text">
              Graph visualization will render here when data is loaded
            </p>
          </div>
        </div>

        {queryPanel.isOpen && (
          <div className="query-panel">
            <h2>Cypher Query</h2>
            <textarea
              value={queryPanel.query}
              onChange={(e) => setQueryPanel(prev => ({ ...prev, query: e.target.value }))}
              placeholder="MATCH (n) RETURN n LIMIT 25"
              rows={5}
            />
            <button onClick={handleExecuteQuery} disabled={queryPanel.executing}>
              Execute Query
            </button>
            
            {queryPanel.results && (
              <div className="query-results">
                <h3>Results</h3>
                <pre>{JSON.stringify(queryPanel.results, null, 2)}</pre>
              </div>
            )}
            
            {queryPanel.error && (
              <div className="query-error">{queryPanel.error}</div>
            )}
          </div>
        )}
      </main>
    </div>
  );
};

export default GraphExplorerPage;
