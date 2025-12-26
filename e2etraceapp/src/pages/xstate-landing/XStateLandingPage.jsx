import React, { useState, useEffect } from 'react';
import { XStateVisualizer } from '../../components/xstate-visualizer/XStateVisualizer';
import goodPointLogo from '../../assets/goodpoint-logo.svg';
import './XStateLandingPage.css';

/**
 * XState Landing Page
 * Main entry point showcasing the interactive State Flow Diagram
 * with full XState-style visualization
 */
const XStateLandingPage = () => {
  const [graphData, setGraphData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(null);

  useEffect(() => {
    loadETLWorkflowData();
  }, []);

  const loadETLWorkflowData = async () => {
    try {
      const response = await fetch('/api/plm/workflow');
      if (response.ok) {
        const data = await response.json();
        const normalized = {
          ...(typeof data === 'object' && data !== null ? data : {}),
          nodes: Array.isArray(data?.nodes) ? data.nodes : [],
          edges: Array.isArray(data?.edges) ? data.edges : [],
        };
        setGraphData(normalized);
        setLoadError(null);
      } else {
        console.error('Failed to load workflow data:', response.statusText);
        setGraphData({ nodes: [], edges: [] });
        setLoadError(response.statusText || 'Failed to load workflow data');
      }
    } catch (error) {
      console.error('Error loading workflow data:', error);
      setGraphData({ nodes: [], edges: [] });
      setLoadError(error?.message || 'Error loading workflow data');
    } finally {
      setLoading(false);
    }
  };

  const handleNodeUpdate = (nodeId, updates) => {
    console.log('Node updated:', nodeId, updates);
    // Handle node updates if needed
  };

  if (loading) {
    return (
      <div className="xstate-landing-loading">
        <div className="loading-spinner"></div>
        <p>Loading Interactive State Flow Diagram...</p>
      </div>
    );
  }

  const safeGraphData = graphData && typeof graphData === 'object'
    ? {
        ...graphData,
        nodes: Array.isArray(graphData.nodes) ? graphData.nodes : [],
        edges: Array.isArray(graphData.edges) ? graphData.edges : [],
      }
    : { nodes: [], edges: [] };

  return (
    <div className="xstate-landing-page">
      <div className="landing-header">
        <div className="landing-header-content">
          <img src={goodPointLogo} alt="GoodPoint" className="landing-logo" />
          <div className="landing-title-group">
            <h1>GoodPoint AgenticAI</h1>
            <p className="landing-subtitle">PLM Data Migration Platform - Interactive Workflow Visualization</p>
          </div>
        </div>
        <div className="landing-stats">
          <div className="stat-badge">
            <span className="stat-value">{safeGraphData.nodes.length}</span>
            <span className="stat-label">Nodes</span>
          </div>
          <div className="stat-badge">
            <span className="stat-value">{safeGraphData.edges.length}</span>
            <span className="stat-label">Connections</span>
          </div>
          <div className="stat-badge">
            <span className="stat-value">7</span>
            <span className="stat-label">Factory Stages</span>
          </div>
          <div className="stat-badge">
            <span className="stat-value">4</span>
            <span className="stat-label">AI Agents</span>
          </div>
        </div>
      </div>

      {loadError ? (
        <div className="xstate-landing-loading">
          <p>Unable to load workflow data. Showing empty diagram.</p>
          <p style={{ opacity: 0.8, fontSize: 12 }}>{String(loadError)}</p>
        </div>
      ) : null}



      <XStateVisualizer
        graphData={safeGraphData}
        onNodeUpdate={handleNodeUpdate}
      />
    </div>
  );
};

export default XStateLandingPage;
