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
    // Load mock ETL workflow data
    loadETLWorkflowData();
  }, []);

  const loadETLWorkflowData = () => {
    // Create comprehensive ETL workflow graph
    const mockGraphData = {
      nodes: [
        // Source Stage
        { id: 'oracle_src', label: 'Oracle DB', type: 'source', stage: 'sources', status: 'healthy', properties: { connection: 'prod-db-01', tables: 45 } },
        { id: 'postgres_src', label: 'PostgreSQL', type: 'source', stage: 'sources', status: 'healthy', properties: { connection: 'postgres-main', tables: 32 } },
        { id: 'excel_src', label: 'Excel Files', type: 'source', stage: 'sources', status: 'healthy', properties: { location: '/data/imports', files: 12 } },
        
        // Extract Stage
        { id: 'extract_oracle', label: 'Extract Oracle', type: 'extract', stage: 'extract', status: 'healthy', properties: { method: 'JDBC', threads: 4 } },
        { id: 'extract_postgres', label: 'Extract PostgreSQL', type: 'extract', stage: 'extract', status: 'healthy', properties: { method: 'JDBC', threads: 4 } },
        { id: 'extract_excel', label: 'Extract Excel', type: 'extract', stage: 'extract', status: 'healthy', properties: { parser: 'Apache POI', batch: 1000 } },
        
        // Transform Stage
        { id: 'transform_cleanse', label: 'Data Cleansing', type: 'transform', stage: 'transform', status: 'healthy', properties: { rules: 15, regex: 8 } },
        { id: 'transform_normalize', label: 'Normalization', type: 'transform', stage: 'transform', status: 'healthy', properties: { standards: 'ISO', format: 'UTF-8' } },
        { id: 'transform_enrich', label: 'Data Enrichment', type: 'transform', stage: 'transform', status: 'warning', properties: { apis: 3, cache: true } },
        { id: 'transform_aggregate', label: 'Aggregation', type: 'transform', stage: 'transform', status: 'healthy', properties: { groupBy: 'product_id', functions: ['sum', 'avg'] } },
        
        // Quality Stage
        { id: 'quality_validate', label: 'Data Validation', type: 'quality', stage: 'quality', status: 'healthy', properties: { rules: 25, threshold: 95 } },
        { id: 'quality_profile', label: 'Data Profiling', type: 'quality', stage: 'quality', status: 'healthy', properties: { metrics: 12, sampling: 0.1 } },
        { id: 'quality_audit', label: 'Audit Trail', type: 'quality', stage: 'quality', status: 'healthy', properties: { retention: '90 days', encrypted: true } },
        
        // Load Stage
        { id: 'load_staging', label: 'Load to Staging', type: 'load', stage: 'load', status: 'healthy', properties: { method: 'Bulk Insert', batchSize: 5000 } },
        { id: 'load_production', label: 'Load to Production', type: 'load', stage: 'load', status: 'healthy', properties: { method: 'Merge', validation: true } },
        
        // Target Stage
        { id: 'neo4j_target', label: 'Neo4j Graph', type: 'target', stage: 'target', status: 'healthy', properties: { nodes: 125000, relationships: 340000 } },
        { id: 'warehouse_target', label: 'Data Warehouse', type: 'target', stage: 'target', status: 'healthy', properties: { tables: 78, indexes: 156 } },
        { id: 'datalake_target', label: 'Data Lake', type: 'target', stage: 'target', status: 'healthy', properties: { format: 'Parquet', compression: 'Snappy' } },
      ],
      edges: [
        // Source to Extract
        { id: 'e1', source: 'oracle_src', target: 'extract_oracle', label: 'JDBC Connection', type: 'dataflow' },
        { id: 'e2', source: 'postgres_src', target: 'extract_postgres', label: 'JDBC Connection', type: 'dataflow' },
        { id: 'e3', source: 'excel_src', target: 'extract_excel', label: 'File Read', type: 'dataflow' },
        
        // Extract to Transform
        { id: 'e4', source: 'extract_oracle', target: 'transform_cleanse', label: 'Raw Data', type: 'dataflow' },
        { id: 'e5', source: 'extract_postgres', target: 'transform_cleanse', label: 'Raw Data', type: 'dataflow' },
        { id: 'e6', source: 'extract_excel', target: 'transform_cleanse', label: 'Raw Data', type: 'dataflow' },
        
        // Transform chain
        { id: 'e7', source: 'transform_cleanse', target: 'transform_normalize', label: 'Cleansed Data', type: 'dataflow' },
        { id: 'e8', source: 'transform_normalize', target: 'transform_enrich', label: 'Normalized Data', type: 'dataflow' },
        { id: 'e9', source: 'transform_enrich', target: 'transform_aggregate', label: 'Enriched Data', type: 'dataflow' },
        
        // Transform to Quality
        { id: 'e10', source: 'transform_aggregate', target: 'quality_validate', label: 'Transformed Data', type: 'dataflow' },
        { id: 'e11', source: 'quality_validate', target: 'quality_profile', label: 'Validated Data', type: 'dataflow' },
        { id: 'e12', source: 'quality_profile', target: 'quality_audit', label: 'Profiled Data', type: 'dataflow' },
        
        // Quality to Load
        { id: 'e13', source: 'quality_audit', target: 'load_staging', label: 'Quality Checked', type: 'dataflow' },
        { id: 'e14', source: 'load_staging', target: 'load_production', label: 'Staged Data', type: 'dataflow' },
        
        // Load to Target
        { id: 'e15', source: 'load_production', target: 'neo4j_target', label: 'Graph Data', type: 'dataflow' },
        { id: 'e16', source: 'load_production', target: 'warehouse_target', label: 'Relational Data', type: 'dataflow' },
        { id: 'e17', source: 'load_production', target: 'datalake_target', label: 'Archive Data', type: 'dataflow' },
      ]
    };

    setGraphData(mockGraphData);
    setLoading(false);
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
            <span className="stat-value">6</span>
            <span className="stat-label">ETL Stages</span>
          </div>
        </div>
      </div>

      <div className="landing-info-banner">
        <div className="info-item">
          <span className="info-icon">🔀</span>
          <span className="info-text">Interactive State Flow with proper connections and animations</span>
        </div>
        <div className="info-item">
          <span className="info-icon">🎯</span>
          <span className="info-text">Drag nodes, zoom, pan - full XState-style UX</span>
        </div>
        <div className="info-item">
          <span className="info-icon">📊</span>
          <span className="info-text">3-panel layout: Tree | Diagram | Inspector</span>
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
