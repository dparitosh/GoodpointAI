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

  useEffect(() => {
    loadETLWorkflowData();
  }, []);

  const loadETLWorkflowData = async () => {
    try {
      const response = await fetch('/api/plm/workflow');
      if (response.ok) {
        const data = await response.json();
        setGraphData(data);
      } else {
        console.error('Failed to load workflow data:', response.statusText);
      }
    } catch (error) {
      console.error('Error loading workflow data:', error);
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
            <span className="stat-value">{graphData.nodes.length}</span>
            <span className="stat-label">Nodes</span>
          </div>
          <div className="stat-badge">
            <span className="stat-value">{graphData.edges.length}</span>
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

      <div className="landing-info-banner">
        <div className="info-item">
          <span className="info-icon">🏭</span>
          <span className="info-text">PLM Data Migration AI Factory - 5 PLM Sources, 4 AI Agents, 5 Target Systems</span>
        </div>
        <div className="info-item">
          <span className="info-icon">🤖</span>
          <span className="info-text">AI-Orchestrated ETL: Data Analyst, ETL Orchestrator, Quality Monitor, Visualization</span>
        </div>
        <div className="info-item">
          <span className="info-icon">🎯</span>
          <span className="info-text">Teamcenter, Windchill, CATIA, NX, Creo → Neo4j, Cloud PLM, OpenSearch</span>
        </div>
      </div>

      <XStateVisualizer
        graphData={graphData}
        onNodeUpdate={handleNodeUpdate}
      />
    </div>
  );
};

export default XStateLandingPage;
