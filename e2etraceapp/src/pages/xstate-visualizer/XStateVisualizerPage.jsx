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

// Generate sample graph data for demonstration
function generateSampleGraphData() {
  const nodes = [
    // Parts
    {
      id: 'part-001',
      label: 'Engine Assembly',
      type: 'Part',
      group: 'Part',
      backgroundColor: '#48a4ff',
      properties: {
        partNumber: 'ENG-001',
        revision: 'A',
        status: 'Active',
        weight: '150 kg',
        material: 'Aluminum Alloy'
      },
      status: 'healthy',
      size: 80
    },
    {
      id: 'part-002',
      label: 'Gearbox',
      type: 'Part',
      group: 'Part',
      backgroundColor: '#48a4ff',
      properties: {
        partNumber: 'GBX-002',
        revision: 'B',
        status: 'Active',
        weight: '75 kg'
      },
      status: 'healthy',
      size: 60
    },
    {
      id: 'part-003',
      label: 'Control Unit',
      type: 'Part',
      group: 'Part',
      backgroundColor: '#48a4ff',
      properties: {
        partNumber: 'CTL-003',
        revision: 'C',
        status: 'Review',
      },
      status: 'warning',
      size: 50
    },

    // Documents
    {
      id: 'doc-001',
      label: 'Technical Spec',
      type: 'Document',
      group: 'Document',
      backgroundColor: '#6e6fff',
      properties: {
        docNumber: 'TS-001',
        version: '2.1',
        author: 'Engineering Team',
        lastModified: '2024-01-15'
      },
      size: 50
    },
    {
      id: 'doc-002',
      label: 'Assembly Guide',
      type: 'Document',
      group: 'Document',
      backgroundColor: '#6e6fff',
      properties: {
        docNumber: 'AG-002',
        version: '1.5',
        pages: 45
      },
      size: 50
    },

    // Materials
    {
      id: 'mat-001',
      label: 'Aluminum 6061',
      type: 'Material',
      group: 'Material',
      backgroundColor: '#ffba5a',
      properties: {
        materialCode: 'AL-6061',
        grade: 'T6',
        density: '2.7 g/cm³'
      },
      size: 45
    },
    {
      id: 'mat-002',
      label: 'Steel Grade 8',
      type: 'Material',
      group: 'Material',
      backgroundColor: '#ffba5a',
      properties: {
        materialCode: 'ST-G8',
        tensileStrength: '150 ksi'
      },
      size: 45
    },

    // Suppliers
    {
      id: 'sup-001',
      label: 'ACME Manufacturing',
      type: 'Supplier',
      group: 'Supplier',
      backgroundColor: '#ff7077',
      properties: {
        supplierCode: 'ACME-001',
        location: 'Detroit, MI',
        rating: '4.5/5'
      },
      size: 55
    },

    // Recipes/Processes
    {
      id: 'rec-001',
      label: 'Machining Process',
      type: 'Recipe',
      group: 'Recipe',
      backgroundColor: '#21d5c1',
      properties: {
        processID: 'MACH-001',
        cycleTime: '120 min',
        tolerance: '±0.01mm'
      },
      size: 50
    },

    // BOM
    {
      id: 'bom-001',
      label: 'Engine BOM',
      type: 'BOM',
      group: 'BOM',
      backgroundColor: '#4caf50',
      properties: {
        bomID: 'BOM-ENG-001',
        items: 42,
        cost: '$12,500'
      },
      size: 60
    },

    // Batches
    {
      id: 'batch-001',
      label: 'Batch Q1-2024',
      type: 'Batch',
      group: 'Batch',
      backgroundColor: '#9b6cff',
      properties: {
        batchNumber: 'Q1-2024-001',
        quantity: 100,
        status: 'In Production'
      },
      size: 50
    }
  ];

  const edges = [
    // Part relationships
    { id: 'e1', source: 'part-001', target: 'part-002', label: 'HAS_PART', type: 'HAS_PART', weight: 3 },
    { id: 'e2', source: 'part-001', target: 'part-003', label: 'HAS_PART', type: 'HAS_PART', weight: 2 },
    
    // Document relationships
    { id: 'e3', source: 'doc-001', target: 'part-001', label: 'DOCUMENTS', type: 'DOCUMENTS', weight: 2 },
    { id: 'e4', source: 'doc-002', target: 'part-001', label: 'DOCUMENTS', type: 'DOCUMENTS', weight: 2 },
    
    // Material relationships
    { id: 'e5', source: 'part-001', target: 'mat-001', label: 'USES', type: 'USES', weight: 3 },
    { id: 'e6', source: 'part-002', target: 'mat-002', label: 'USES', type: 'USES', weight: 2 },
    
    // Supplier relationships
    { id: 'e7', source: 'sup-001', target: 'mat-001', label: 'SUPPLIES', type: 'SUPPLIES', weight: 2 },
    { id: 'e8', source: 'sup-001', target: 'mat-002', label: 'SUPPLIES', type: 'SUPPLIES', weight: 2 },
    
    // Process relationships
    { id: 'e9', source: 'rec-001', target: 'part-002', label: 'PROCESSES', type: 'PROCESSES', weight: 2 },
    
    // BOM relationships
    { id: 'e10', source: 'bom-001', target: 'part-001', label: 'INCLUDES', type: 'INCLUDES', weight: 3 },
    { id: 'e11', source: 'bom-001', target: 'part-002', label: 'INCLUDES', type: 'INCLUDES', weight: 2 },
    { id: 'e12', source: 'bom-001', target: 'part-003', label: 'INCLUDES', type: 'INCLUDES', weight: 2 },
    
    // Batch relationships
    { id: 'e13', source: 'batch-001', target: 'part-001', label: 'PRODUCES', type: 'PRODUCES', weight: 2 },
    { id: 'e14', source: 'batch-001', target: 'sup-001', label: 'SOURCED_FROM', type: 'SOURCED_FROM', weight: 1 },
    
    // Dependencies
    { id: 'e15', source: 'part-002', target: 'part-003', label: 'DEPENDS_ON', type: 'DEPENDS_ON', weight: 2 },
  ];

  return { nodes, edges };
}
