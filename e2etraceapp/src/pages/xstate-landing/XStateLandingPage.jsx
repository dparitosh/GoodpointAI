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
    // Try to load from backend API, fallback to mock data
    loadETLWorkflowData();
  }, []);

  const loadETLWorkflowData = async () => {
    try {
      // Try to fetch from backend PLM workflow API
      const response = await fetch('/api/plm/workflow');
      if (response.ok) {
        const data = await response.json();
        setGraphData(data);
        setLoading(false);
        return;
      }
    } catch (error) {
      console.log('Backend API not available, using mock data:', error.message);
    }
    
    // Fallback to comprehensive mock data
    loadMockPLMWorkflowData();
  };

  const loadMockPLMWorkflowData = () => {
    // PLM Data Migration AI Factory Model - Comprehensive Workflow
    const mockGraphData = {
      nodes: [
        // PLM Source Systems Stage
        { id: 'teamcenter_src', label: 'Teamcenter PLM', type: 'plm_source', stage: 'plm_sources', status: 'healthy', properties: { version: '13.2', parts: 125000, boms: 45000, documents: 89000 } },
        { id: 'windchill_src', label: 'Windchill PLM', type: 'plm_source', stage: 'plm_sources', status: 'healthy', properties: { version: '12.1', parts: 98000, changes: 23000, workflows: 450 } },
        { id: 'catia_src', label: 'CATIA V6', type: 'cad_source', stage: 'plm_sources', status: 'healthy', properties: { version: 'V6R2021', models: 34000, assemblies: 12000 } },
        { id: 'nx_src', label: 'Siemens NX', type: 'cad_source', stage: 'plm_sources', status: 'healthy', properties: { version: 'NX 2206', models: 28000, drawings: 15000 } },
        { id: 'creo_src', label: 'PTC Creo', type: 'cad_source', stage: 'plm_sources', status: 'warning', properties: { version: '9.0', models: 19000, features: 45000 } },
        
        
        // AI Agent Orchestration Layer
        { id: 'ai_data_analyst', label: 'Data Analyst Agent', type: 'ai_agent', stage: 'ai_orchestration', status: 'active', properties: { role: 'analysis', tasks: 145, accuracy: '97.2%' } },
        { id: 'ai_etl_orchestrator', label: 'ETL Orchestrator Agent', type: 'ai_agent', stage: 'ai_orchestration', status: 'active', properties: { role: 'orchestration', pipelines: 23, uptime: '99.8%' } },
        { id: 'ai_quality_monitor', label: 'Quality Monitor Agent', type: 'ai_agent', stage: 'ai_orchestration', status: 'active', properties: { role: 'quality', checks: 340, issues: 12 } },
        { id: 'ai_viz_agent', label: 'Visualization Agent', type: 'ai_agent', stage: 'ai_orchestration', status: 'active', properties: { role: 'visualization', dashboards: 15, alerts: 8 } },
        
        // Extract Stage
        { id: 'extract_teamcenter', label: 'Extract Teamcenter', type: 'extract', stage: 'extract', status: 'healthy', properties: { method: 'SOA/REST', format: 'PLMXML', batch: 5000 } },
        { id: 'extract_windchill', label: 'Extract Windchill', type: 'extract', stage: 'extract', status: 'healthy', properties: { method: 'REST API', format: 'JSON', batch: 3000 } },
        { id: 'extract_cad', label: 'Extract CAD Data', type: 'extract', stage: 'extract', status: 'healthy', properties: { parser: 'Multi-CAD', formats: ['STEP', 'IGES', 'JT'], batch: 1000 } },
        
        // Transform Stage - PLM Specific
        { id: 'transform_plm_schema', label: 'PLM Schema Mapping', type: 'transform', stage: 'transform', status: 'healthy', properties: { mappings: 450, standards: 'ISO 10303', conflicts: 3 } },
        { id: 'transform_bom_flatten', label: 'BOM Flattening', type: 'transform', stage: 'transform', status: 'healthy', properties: { levels: 12, parts: 125000, relationships: 340000 } },
        { id: 'transform_cad_metadata', label: 'CAD Metadata Extract', type: 'transform', stage: 'transform', status: 'healthy', properties: { attributes: 230, geometries: 'preserved', pmis: 'extracted' } },
        { id: 'transform_normalize', label: 'Data Normalization', type: 'transform', stage: 'transform', status: 'healthy', properties: { standards: 'ISO 10303/STEP', encoding: 'UTF-8', uom: 'SI' } },
        { id: 'transform_enrich', label: 'AI Enrichment', type: 'transform', stage: 'transform', status: 'warning', properties: { ml_models: 5, classifications: 12000, confidence: '94.5%' } },
        { id: 'transform_relationship', label: 'Relationship Mapping', type: 'transform', stage: 'transform', status: 'healthy', properties: { types: ['parent_of', 'replaces', 'references'], edges: 340000 } },
        
        // Quality Stage - SODA Framework
        { id: 'quality_plm_validate', label: 'PLM Data Validation', type: 'quality', stage: 'quality', status: 'healthy', properties: { rules: 85, threshold: 98, failures: 234 } },
        { id: 'quality_bom_integrity', label: 'BOM Integrity Check', type: 'quality', stage: 'quality', status: 'healthy', properties: { orphans: 0, cycles: 0, depth: 'validated' } },
        { id: 'quality_cad_verify', label: 'CAD File Verification', type: 'quality', stage: 'quality', status: 'warning', properties: { missing: 45, corrupted: 3, repaired: 38 } },
        { id: 'quality_profile', label: 'Data Profiling', type: 'quality', stage: 'quality', status: 'healthy', properties: { metrics: 45, anomalies: 12, confidence: 0.96 } },
        { id: 'quality_audit', label: 'Compliance Audit', type: 'quality', stage: 'quality', status: 'healthy', properties: { standards: ['ISO 9001', 'AS9100'], retention: '7 years', encrypted: true } },
        
        // Load Stage
        { id: 'load_staging', label: 'Staging Environment', type: 'load', stage: 'load', status: 'healthy', properties: { method: 'Incremental', batchSize: 5000, parallelism: 8 } },
        { id: 'load_validation', label: 'Pre-Production Validation', type: 'load', stage: 'load', status: 'healthy', properties: { tests: 245, passed: 243, automated: true } },
        { id: 'load_production', label: 'Production Deployment', type: 'load', stage: 'load', status: 'healthy', properties: { method: 'Blue-Green', rollback: 'enabled', downtime: '0ms' } },
        
        // Target Systems Stage
        { id: 'neo4j_target', label: 'Neo4j Knowledge Graph', type: 'target', stage: 'target', status: 'healthy', properties: { nodes: 380000, relationships: 890000, depth: 12 } },
        { id: 'target_plm', label: 'Target PLM System', type: 'target', stage: 'target', status: 'healthy', properties: { system: 'Cloud PLM', parts: 380000, integrations: 15 } },
        { id: 'opensearch_target', label: 'OpenSearch Index', type: 'target', stage: 'target', status: 'healthy', properties: { documents: 380000, shards: 5, replicas: 2 } },
        { id: 'warehouse_target', label: 'Analytics Warehouse', type: 'target', stage: 'target', status: 'healthy', properties: { tables: 145, views: 78, reports: 234 } },
        { id: 'datalake_target', label: 'Enterprise Data Lake', type: 'target', stage: 'target', status: 'healthy', properties: { format: 'Delta Lake', compression: 'Zstd', retention: '10 years' } },
      ],
      edges: [
        // PLM Sources to Extraction
        { id: 'e1', source: 'teamcenter_src', target: 'extract_teamcenter', label: 'SOA/PLMXML', type: 'dataflow' },
        { id: 'e2', source: 'windchill_src', target: 'extract_windchill', label: 'REST API', type: 'dataflow' },
        { id: 'e3', source: 'catia_src', target: 'extract_cad', label: 'STEP/IGES', type: 'dataflow' },
        { id: 'e4', source: 'nx_src', target: 'extract_cad', label: 'JT Format', type: 'dataflow' },
        { id: 'e5', source: 'creo_src', target: 'extract_cad', label: 'Native Files', type: 'dataflow' },
        
        // AI Agent Orchestration
        { id: 'e6', source: 'ai_data_analyst', target: 'extract_teamcenter', label: 'Schema Analysis', type: 'control' },
        { id: 'e7', source: 'ai_data_analyst', target: 'extract_windchill', label: 'Data Profiling', type: 'control' },
        { id: 'e8', source: 'ai_etl_orchestrator', target: 'extract_teamcenter', label: 'Pipeline Control', type: 'control' },
        { id: 'e9', source: 'ai_etl_orchestrator', target: 'extract_windchill', label: 'Flow Management', type: 'control' },
        { id: 'e10', source: 'ai_etl_orchestrator', target: 'extract_cad', label: 'Batch Scheduling', type: 'control' },
        
        // Extract to Transform
        { id: 'e11', source: 'extract_teamcenter', target: 'transform_plm_schema', label: 'Parts & BOMs', type: 'dataflow' },
        { id: 'e12', source: 'extract_windchill', target: 'transform_plm_schema', label: 'Change Objects', type: 'dataflow' },
        { id: 'e13', source: 'extract_cad', target: 'transform_cad_metadata', label: 'CAD Models', type: 'dataflow' },
        
        // Transform Chain - PLM Processing
        { id: 'e14', source: 'transform_plm_schema', target: 'transform_bom_flatten', label: 'Mapped Schema', type: 'dataflow' },
        { id: 'e15', source: 'transform_bom_flatten', target: 'transform_normalize', label: 'Flattened BOM', type: 'dataflow' },
        { id: 'e16', source: 'transform_cad_metadata', target: 'transform_normalize', label: 'CAD Attributes', type: 'dataflow' },
        { id: 'e17', source: 'transform_normalize', target: 'transform_enrich', label: 'Normalized Data', type: 'dataflow' },
        { id: 'e18', source: 'transform_enrich', target: 'transform_relationship', label: 'Enriched Data', type: 'dataflow' },
        
        // AI Agent to Transform
        { id: 'e19', source: 'ai_data_analyst', target: 'transform_enrich', label: 'ML Classification', type: 'control' },
        { id: 'e20', source: 'ai_viz_agent', target: 'transform_relationship', label: 'Graph Generation', type: 'control' },
        
        // Transform to Quality
        { id: 'e21', source: 'transform_relationship', target: 'quality_plm_validate', label: 'Transformed Data', type: 'dataflow' },
        { id: 'e22', source: 'quality_plm_validate', target: 'quality_bom_integrity', label: 'Validated Parts', type: 'dataflow' },
        { id: 'e23', source: 'quality_bom_integrity', target: 'quality_cad_verify', label: 'Verified BOMs', type: 'dataflow' },
        { id: 'e24', source: 'quality_cad_verify', target: 'quality_profile', label: 'Verified CAD', type: 'dataflow' },
        { id: 'e25', source: 'quality_profile', target: 'quality_audit', label: 'Profiled Data', type: 'dataflow' },
        
        // AI Quality Monitoring
        { id: 'e26', source: 'ai_quality_monitor', target: 'quality_plm_validate', label: 'Rule Engine', type: 'control' },
        { id: 'e27', source: 'ai_quality_monitor', target: 'quality_bom_integrity', label: 'Integrity Checks', type: 'control' },
        { id: 'e28', source: 'ai_quality_monitor', target: 'quality_cad_verify', label: 'Anomaly Detection', type: 'control' },
        
        // Quality to Load
        { id: 'e29', source: 'quality_audit', target: 'load_staging', label: 'Quality Approved', type: 'dataflow' },
        { id: 'e30', source: 'load_staging', target: 'load_validation', label: 'Staged Data', type: 'dataflow' },
        { id: 'e31', source: 'load_validation', target: 'load_production', label: 'Validated Load', type: 'dataflow' },
        
        // AI Orchestration to Load
        { id: 'e32', source: 'ai_etl_orchestrator', target: 'load_production', label: 'Deployment Control', type: 'control' },
        
        // Load to Target Systems
        { id: 'e33', source: 'load_production', target: 'neo4j_target', label: 'Knowledge Graph', type: 'dataflow' },
        { id: 'e34', source: 'load_production', target: 'target_plm', label: 'PLM Objects', type: 'dataflow' },
        { id: 'e35', source: 'load_production', target: 'opensearch_target', label: 'Search Index', type: 'dataflow' },
        { id: 'e36', source: 'load_production', target: 'warehouse_target', label: 'Analytics Data', type: 'dataflow' },
        { id: 'e37', source: 'load_production', target: 'datalake_target', label: 'Archive Storage', type: 'dataflow' },
        
        // AI Visualization
        { id: 'e38', source: 'ai_viz_agent', target: 'neo4j_target', label: 'Graph Viz', type: 'control' },
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
