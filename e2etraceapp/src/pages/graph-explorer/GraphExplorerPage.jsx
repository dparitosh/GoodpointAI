/**
 * Graph Explorer Page - Main page for Neo4j graph visualization
 * Integrates with GraphQL, Neo4j GraphRAG, and migration history
 * Powered by GoodPoint AI - TCS UI/UX Compliant
 */

import React, { useMemo, useRef, useState, useEffect } from 'react';
import connectionService from '../../services/connectionService';
import graphIntegrationService from '../../services/GraphIntegrationService';
import goodPointLogo from '../../assets/goodpoint-logo.svg';
import { E2ETraceCytoscapeGraph } from '../dashboard/e2etrace-cytoscape-graph';
import { cytoscapeStylesheet } from '../dashboard/e2etrace-cytoscape-stylesheet';
import { e2etraceTransformDataForCytoscape } from '../../utils/e2etrace-graph';
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

  const [selectedElement, setSelectedElement] = useState(null);

  const cyRef = useRef(null);

  const cyElements = useMemo(() => {
    if (!connection.connected || graphData.nodes.length === 0) return [];
    try {
      return e2etraceTransformDataForCytoscape(
        { nodes: graphData.nodes, edges: graphData.edges },
        { colorScheme: 'default', autoGrouping: true }
      );
    } catch (e) {
      console.error('Failed to transform graph data for Cytoscape:', e);
      return [];
    }
  }, [connection.connected, graphData.nodes, graphData.edges]);

  const cyLayout = useMemo(
    () => ({
      name: 'fcose',
      animate: true,
      randomize: true,
      fit: true,
      padding: 30,
      nodeDimensionsIncludeLabels: true,
    }),
    []
  );

  const cyStylesheet = useMemo(
    () => ([
      ...cytoscapeStylesheet,
      {
        selector: '.dimmed',
        style: {
          'opacity': 0.15,
          'text-opacity': 0.05,
        }
      },
      {
        selector: 'edge.dimmed',
        style: {
          'opacity': 0.12,
          'text-opacity': 0,
        }
      },
      {
        selector: 'node.focus',
        style: {
          'border-width': 5,
        }
      },
      {
        selector: 'edge.focus',
        style: {
          'width': 8,
        }
      },
      {
        selector: 'node.neighbor',
        style: {
          'border-width': 3,
        }
      },
      {
        selector: 'edge.neighbor',
        style: {
          'width': 5,
          'text-opacity': 0.6,
        }
      },
    ]),
    []
  );

  useEffect(() => {
    const cy = cyRef.current;
    if (!cy) return;

    const clearFocusClasses = () => {
      cy.batch(() => {
        cy.elements().removeClass('dimmed neighbor focus');
      });
    };

    const applyNodeFocus = (node) => {
      cy.batch(() => {
        cy.elements().addClass('dimmed').removeClass('neighbor focus');
        node.removeClass('dimmed').addClass('focus');
        node.neighborhood().removeClass('dimmed').addClass('neighbor');
      });
    };

    const applyEdgeFocus = (edge) => {
      cy.batch(() => {
        cy.elements().addClass('dimmed').removeClass('neighbor focus');
        edge.removeClass('dimmed').addClass('focus');
        edge.connectedNodes().removeClass('dimmed').addClass('neighbor');
        edge.connectedEdges().removeClass('dimmed').addClass('neighbor');
      });
    };

    const handleBackgroundTap = (evt) => {
      if (evt.target === cy) {
        cy.elements().unselect();
        clearFocusClasses();
        setSelectedElement(null);
      }
    };

    const handleNodeTap = (evt) => {
      const node = evt.target;
      cy.elements().unselect();
      node.select();
      applyNodeFocus(node);
      cy.fit(node, 80);
      setSelectedElement({
        kind: 'node',
        id: node.id(),
        data: node.data(),
      });
    };

    const handleEdgeTap = (evt) => {
      const edge = evt.target;
      cy.elements().unselect();
      edge.select();
      applyEdgeFocus(edge);
      cy.fit(edge, 120);
      setSelectedElement({
        kind: 'edge',
        id: edge.id(),
        data: edge.data(),
      });
    };

    cy.on('tap', handleBackgroundTap);
    cy.on('tap', 'node', handleNodeTap);
    cy.on('tap', 'edge', handleEdgeTap);

    return () => {
      cy.off('tap', handleBackgroundTap);
      cy.off('tap', 'node', handleNodeTap);
      cy.off('tap', 'edge', handleEdgeTap);
    };
  }, [cyElements]);

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
            <E2ETraceCytoscapeGraph
              elements={cyElements}
              stylesheet={cyStylesheet}
              layout={cyLayout}
              cyRef={cyRef}
            />
          </div>

          {selectedElement && (
            <div className="selection-panel" role="region" aria-label="Selected element details">
              <div className="selection-header">
                <h3>
                  Selected {selectedElement.kind === 'node' ? 'Node' : 'Edge'}
                </h3>
                <button
                  type="button"
                  className="btn-secondary btn-small"
                  onClick={() => {
                    const cy = cyRef.current;
                    if (cy) {
                      cy.elements().unselect();
                      cy.elements().removeClass('dimmed neighbor focus');
                    }
                    setSelectedElement(null);
                  }}
                >
                  Clear
                </button>
              </div>

              <div className="selection-meta">
                <div><strong>ID:</strong> {String(selectedElement.id)}</div>
                {selectedElement.data?.label != null && (
                  <div><strong>Label:</strong> {String(selectedElement.data.label)}</div>
                )}
                {selectedElement.data?.group != null && (
                  <div><strong>Group:</strong> {String(selectedElement.data.group)}</div>
                )}
                {selectedElement.data?.type != null && (
                  <div><strong>Type:</strong> {String(selectedElement.data.type)}</div>
                )}
              </div>

              <details className="selection-details" open>
                <summary>Raw Data</summary>
                <pre>{JSON.stringify(selectedElement.data, null, 2)}</pre>
              </details>
            </div>
          )}
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
