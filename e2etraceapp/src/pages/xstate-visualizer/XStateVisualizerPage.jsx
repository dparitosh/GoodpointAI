import React, { useState, useEffect } from 'react';
import { XStateVisualizer } from '../../components/xstate-visualizer';

/**
 * XState Visualizer Demo Page
 * Demonstrates the XState-style PLM graph visualization
 */
export default function XStateVisualizerPage() {
  const [graphData, setGraphData] = useState(null);

  useEffect(() => {
    // Generate sample PLM graph data
    const sampleData = generateSampleGraphData();
    setGraphData(sampleData);
  }, []);

  const handleNodeUpdate = (nodeId, updates) => {
    setGraphData(prevData => ({
      ...prevData,
      nodes: prevData.nodes.map(node =>
        node.id === nodeId
          ? { ...node, properties: { ...node.properties, ...updates } }
          : node
      )
    }));
  };

  if (!graphData) {
    return (
      <div style={{ 
        display: 'flex', 
        alignItems: 'center', 
        justifyContent: 'center', 
        height: '100vh',
        fontSize: '18px',
        color: '#586069'
      }}>
        Loading XState Visualizer...
      </div>
    );
  }

  return (
    <XStateVisualizer 
      graphData={graphData} 
      onNodeUpdate={handleNodeUpdate}
    />
  );
}

// Generate sample graph data for demonstration (ETL/Data Migration entities)
function generateSampleGraphData() {
  const nodes = [
    // Data Sources - Databases
    {
      id: 'db-001',
      label: 'Teamcenter DB',
      type: 'Database',
      group: 'Teamcenter',
      backgroundColor: '#48a4ff',
      properties: {
        host: 'tc-prod-01',
        port: '5432',
        status: 'Connected',
        recordCount: '1.2M records'
      },
      status: 'healthy',
      size: 80
    },
    {
      id: 'db-002',
      label: 'Legacy ERP',
      type: 'Database',
      group: 'CustomDB',
      backgroundColor: '#48a4ff',
      properties: {
        host: 'erp-legacy-01',
        type: 'Oracle',
        status: 'Connected',
      },
      status: 'healthy',
      size: 70
    },

    // File Sources - CSV
    {
      id: 'csv-001',
      label: 'Parts Master.csv',
      type: 'CSV',
      group: 'CSV',
      backgroundColor: '#ffba5a',
      properties: {
        fileName: 'parts_master_2024.csv',
        size: '45 MB',
        rows: '125,000',
        encoding: 'UTF-8'
      },
      size: 60
    },
    {
      id: 'csv-002',
      label: 'BOM Extract.csv',
      type: 'CSV',
      group: 'CSV',
      backgroundColor: '#ffba5a',
      properties: {
        fileName: 'bom_extract.csv',
        size: '23 MB',
        rows: '68,000'
      },
      size: 55
    },

    // File Sources - JSON
    {
      id: 'json-001',
      label: 'API Response',
      type: 'JSON',
      group: 'JSON',
      backgroundColor: '#9b6cff',
      properties: {
        source: 'REST API',
        schema: 'Product Catalog',
        version: '2.1'
      },
      size: 50
    },

    // File Sources - XML
    {
      id: 'xml-001',
      label: 'PLM Export',
      type: 'XML',
      group: 'PLMXML',
      backgroundColor: '#ff7077',
      properties: {
        fileName: 'plm_export_q4.xml',
        size: '128 MB',
        schema: 'PLM XML 10.0'
      },
      size: 65
    },

    // Processing Nodes
    {
      id: 'etl-001',
      label: 'Data Cleansing',
      type: 'ETL',
      group: 'ETL',
      backgroundColor: '#21d5c1',
      properties: {
        processor: 'DataCleanser',
        rules: 'Quality Rules v3',
        throughput: '10k/sec'
      },
      size: 60
    },
    {
      id: 'transform-001',
      label: 'Schema Mapper',
      type: 'Transform',
      group: 'Transform',
      backgroundColor: '#21d5c1',
      properties: {
        mapping: 'Legacy → Neo4j',
        fields: 156,
        validationRules: 42
      },
      size: 60
    },

    // API/Services
    {
      id: 'api-001',
      label: 'Migration API',
      type: 'API',
      group: 'API',
      backgroundColor: '#6e6fff',
      properties: {
        endpoint: '/api/migration/v2',
        status: 'Active',
        uptime: '99.9%'
      },
      size: 55
    },
    {
      id: 'service-001',
      label: 'OpenSearch Index',
      type: 'Service',
      group: 'Service',
      backgroundColor: '#6e6fff',
      properties: {
        cluster: 'opensearch-prod',
        indices: 12,
        documents: '5.2M'
      },
      size: 60
    },

    // Target - Neo4j
    {
      id: 'neo4j-001',
      label: 'Neo4j Graph DB',
      type: 'Database',
      group: 'Database',
      backgroundColor: '#48a4ff',
      properties: {
        host: 'neo4j-prod-01',
        database: 'graphtrace',
        nodes: '2.1M',
        relationships: '5.8M'
      },
      status: 'healthy',
      size: 85
    },

    // Data Quality Issue
    {
      id: 'dq-001',
      label: 'Quality Alert',
      type: 'DataQualityIssue',
      group: 'DataQualityIssue',
      backgroundColor: '#e74c3c',
      properties: {
        severity: 'Medium',
        issue: 'Missing required fields',
        affectedRecords: 342
      },
      status: 'warning',
      size: 45
    }
  ];

  const edges = [
    // Source to ETL pipeline
    { id: 'e1', source: 'db-001', target: 'etl-001', label: 'EXTRACT', type: 'EXTRACT', weight: 3 },
    { id: 'e2', source: 'db-002', target: 'etl-001', label: 'EXTRACT', type: 'EXTRACT', weight: 2 },
    { id: 'e3', source: 'csv-001', target: 'etl-001', label: 'LOAD', type: 'LOAD', weight: 2 },
    { id: 'e4', source: 'csv-002', target: 'transform-001', label: 'LOAD', type: 'LOAD', weight: 2 },
    { id: 'e5', source: 'json-001', target: 'transform-001', label: 'LOAD', type: 'LOAD', weight: 2 },
    { id: 'e6', source: 'xml-001', target: 'transform-001', label: 'PARSE', type: 'PARSE', weight: 3 },
    
    // ETL processing
    { id: 'e7', source: 'etl-001', target: 'transform-001', label: 'TRANSFORM', type: 'TRANSFORM', weight: 3 },
    
    // API integration
    { id: 'e8', source: 'api-001', target: 'etl-001', label: 'ORCHESTRATE', type: 'ORCHESTRATE', weight: 2 },
    
    // Transform to targets
    { id: 'e9', source: 'transform-001', target: 'neo4j-001', label: 'LOAD', type: 'LOAD', weight: 3 },
    { id: 'e10', source: 'transform-001', target: 'service-001', label: 'INDEX', type: 'INDEX', weight: 2 },
    
    // Quality issues
    { id: 'e11', source: 'etl-001', target: 'dq-001', label: 'DETECTED', type: 'DETECTED', weight: 1 },
    { id: 'e12', source: 'dq-001', target: 'csv-001', label: 'AFFECTS', type: 'AFFECTS', weight: 1 },
  ];

  return { nodes, edges };
}
