import React, { useEffect, useRef, useState, useCallback } from 'react';
import cytoscape from 'cytoscape';
import fcose from 'cytoscape-fcose';
import './StateFlowDiagram.css';

// Register layout
cytoscape.use(fcose);

/**
 * State Flow Diagram - XState-style interactive workflow visualization
 * Shows state transitions with animated edges and interactive nodes
 */
export const StateFlowDiagram = ({ 
  nodes = [], 
  edges = [], 
  selectedNode, 
  onNodeClick, 
  onNodeDoubleClick,
  theme = 'light',
  layout = 'fcose' 
}) => {
  const containerRef = useRef(null);
  const cyRef = useRef(null);
  const [hoveredNode, setHoveredNode] = useState(null);

  useEffect(() => {
    if (!containerRef.current || nodes.length === 0) return;

    // Destroy existing instance
    if (cyRef.current) {
      cyRef.current.destroy();
    }

    // Convert nodes and edges to Cytoscape format
    const elements = [
      ...nodes.map(node => ({
        data: {
          id: node.id,
          label: node.label || node.id,
          type: node.type || node.group,
          group: node.group,
          backgroundColor: node.backgroundColor || getColorForType(node.type),
          properties: node.properties,
          status: node.status,
          parent: node.parent // For compound nodes
        },
        classes: [
          node.type?.toLowerCase().replace(/\s+/g, '-') || 'default',
          node.status || 'default',
          node.parent ? 'child-node' : 'root-node'
        ].join(' ')
      })),
      ...edges.map(edge => ({
        data: {
          id: edge.id || `${edge.source}-${edge.target}`,
          source: edge.source,
          target: edge.target,
          label: edge.label || edge.type,
          type: edge.type || 'CONNECTED_TO',
          weight: edge.weight || 1,
          animated: true
        },
        classes: [
          edge.type?.toLowerCase().replace(/\s+/g, '-') || 'default',
          'animated-edge'
        ].join(' ')
      }))
    ];

    // Initialize Cytoscape
    const cy = cytoscape({
      container: containerRef.current,
      elements,
      style: getStylesheet(theme),
      layout: getLayoutConfig(layout),
      minZoom: 0.3,
      maxZoom: 3,
      wheelSensitivity: 0.2,
      boxSelectionEnabled: true,
      selectionType: 'single'
    });

    cyRef.current = cy;

    // Event handlers
    cy.on('tap', 'node', (evt) => {
      const node = evt.target;
      const nodeData = nodes.find(n => n.id === node.id());
      
      if (nodeData && onNodeClick) {
        onNodeClick(nodeData);
      }

      // Animate focus
      cy.animate({
        fit: {
          eles: node,
          padding: 100
        },
        duration: 500,
        easing: 'ease-out-quad'
      });
    });

    cy.on('dbltap', 'node', (evt) => {
      const node = evt.target;
      const nodeData = nodes.find(n => n.id === node.id());
      
      if (nodeData && onNodeDoubleClick) {
        onNodeDoubleClick(nodeData);
      }
    });

    cy.on('mouseover', 'node', (evt) => {
      const node = evt.target;
      setHoveredNode(node.id());
      
      // Highlight connected edges
      const connectedEdges = node.connectedEdges();
      connectedEdges.addClass('highlighted-edge');
      
      // Highlight connected nodes
      const connectedNodes = node.neighborhood('node');
      connectedNodes.addClass('connected-neighbor');
    });

    cy.on('mouseout', 'node', (evt) => {
      setHoveredNode(null);
      cy.elements().removeClass('highlighted-edge connected-neighbor');
    });

    // Handle edge animations
    cy.on('mouseover', 'edge', (evt) => {
      evt.target.addClass('edge-hover');
    });

    cy.on('mouseout', 'edge', (evt) => {
      evt.target.removeClass('edge-hover');
    });

    // Free drag with snap
    cy.on('free', 'node', (evt) => {
      const node = evt.target;
      snapToGrid(node, 20); // 20px grid
    });

    // Cleanup
    return () => {
      if (cyRef.current) {
        cyRef.current.destroy();
      }
    };
  }, [nodes, edges, theme, layout]);

  // Sync selected node
  useEffect(() => {
    if (!cyRef.current) return;

    cyRef.current.nodes().removeClass('selected');
    
    if (selectedNode) {
      const node = cyRef.current.getElementById(selectedNode.id);
      if (node.length > 0) {
        node.addClass('selected');
      }
    }
  }, [selectedNode]);

  // Toolbar actions
  const handleFitToScreen = useCallback(() => {
    if (cyRef.current) {
      cyRef.current.fit(null, 50);
    }
  }, []);

  const handleResetLayout = useCallback(() => {
    if (cyRef.current) {
      cyRef.current.layout(getLayoutConfig(layout)).run();
    }
  }, [layout]);

  const handleZoomIn = useCallback(() => {
    if (cyRef.current) {
      cyRef.current.zoom({
        level: cyRef.current.zoom() * 1.2,
        renderedPosition: { x: cyRef.current.width() / 2, y: cyRef.current.height() / 2 }
      });
    }
  }, []);

  const handleZoomOut = useCallback(() => {
    if (cyRef.current) {
      cyRef.current.zoom({
        level: cyRef.current.zoom() * 0.8,
        renderedPosition: { x: cyRef.current.width() / 2, y: cyRef.current.height() / 2 }
      });
    }
  }, []);

  const handleExportPNG = useCallback(() => {
    if (cyRef.current) {
      const png = cyRef.current.png({ scale: 2, full: true });
      const link = document.createElement('a');
      link.download = 'workflow-diagram.png';
      link.href = png;
      link.click();
    }
  }, []);

  return (
    <div className={`state-flow-diagram state-flow-diagram--${theme}`}>
      <div ref={containerRef} className="state-flow-canvas" />
      
      {/* Floating Toolbar */}
      <div className="state-flow-toolbar">
        <button 
          onClick={handleZoomIn}
          className="toolbar-btn"
          title="Zoom In"
        >
          ➕
        </button>
        <button 
          onClick={handleZoomOut}
          className="toolbar-btn"
          title="Zoom Out"
        >
          ➖
        </button>
        <button 
          onClick={handleFitToScreen}
          className="toolbar-btn"
          title="Fit to Screen"
        >
          ⊡
        </button>
        <button 
          onClick={handleResetLayout}
          className="toolbar-btn"
          title="Reset Layout"
        >
          ⟲
        </button>
        <button 
          onClick={handleExportPNG}
          className="toolbar-btn"
          title="Export PNG"
        >
          ▣
        </button>
      </div>

      {/* Hover Tooltip */}
      {hoveredNode && (
        <div className="state-flow-tooltip">
          {nodes.find(n => n.id === hoveredNode)?.label || hoveredNode}
        </div>
      )}
    </div>
  );
};

// Snap node to grid
const snapToGrid = (node, gridSize) => {
  const pos = node.position();
  const snappedX = Math.round(pos.x / gridSize) * gridSize;
  const snappedY = Math.round(pos.y / gridSize) * gridSize;
  node.position({ x: snappedX, y: snappedY });
};

// Layout configurations
const getLayoutConfig = (layoutType) => {
  const configs = {
    fcose: {
      name: 'fcose',
      quality: 'proof',
      animate: true,
      animationDuration: 800,
      animationEasing: 'ease-out-cubic',
      fit: true,
      padding: 80,
      nodeDimensionsIncludeLabels: true,
      uniformNodeDimensions: false,
      packComponents: true,
      nodeRepulsion: 8000,
      idealEdgeLength: 200,
      edgeElasticity: 0.45,
      nestingFactor: 0.1,
      gravity: 0.25,
      numIter: 2500,
      tile: true,
      tilingPaddingVertical: 40,
      tilingPaddingHorizontal: 40,
      gravityRangeCompound: 1.5,
      gravityCompound: 1.0,
      gravityRange: 3.8,
      initialEnergyOnIncremental: 0.3
    },
    breadthfirst: {
      name: 'breadthfirst',
      directed: true,
      spacingFactor: 1.5,
      animate: true,
      animationDuration: 800,
      padding: 80,
      avoidOverlap: true
    },
    cose: {
      name: 'cose',
      animate: true,
      animationDuration: 800,
      nodeRepulsion: 8000,
      idealEdgeLength: 200,
      padding: 80
    }
  };

  return configs[layoutType] || configs.fcose;
};

// XState-inspired stylesheet
const getStylesheet = (theme) => {
  const isDark = theme === 'dark';
  
  return [
    // Node styles
    {
      selector: 'node',
      style: {
        'background-color': 'data(backgroundColor)',
        'label': 'data(label)',
        'color': isDark ? '#e0e0e0' : '#24292e',
        'text-valign': 'center',
        'text-halign': 'center',
        'font-size': '14px',
        'font-weight': '600',
        'font-family': 'Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
        'text-wrap': 'wrap',
        'text-max-width': '120px',
        'width': '180px',
        'height': '60px',
        'shape': 'roundrectangle',
        'border-width': '3px',
        'border-color': isDark ? '#3e3e42' : '#e1e4e8',
        'border-opacity': 1,
        'padding': '12px',
        'text-margin-y': '2px',
        'overlay-opacity': 0,
        'transition-property': 'border-color, border-width, box-shadow',
        'transition-duration': '0.3s',
        'box-shadow': '0 4px 12px rgba(0, 0, 0, 0.15)',
        'z-index': 10
      }
    },
    // Node hover
    {
      selector: 'node:active',
      style: {
        'overlay-opacity': 0
      }
    },
    {
      selector: 'node.selected',
      style: {
        'border-color': '#0078D4',
        'border-width': '4px',
        'box-shadow': '0 0 0 4px rgba(0, 120, 212, 0.2), 0 8px 24px rgba(0, 0, 0, 0.2)',
        'z-index': 999
      }
    },
    {
      selector: 'node.connected-neighbor',
      style: {
        'border-color': '#FF832B',
        'border-width': '3px',
        'opacity': 1
      }
    },
    // Status-based node styles
    {
      selector: 'node.healthy',
      style: {
        'border-color': '#24A148',
        'background-opacity': 0.95
      }
    },
    {
      selector: 'node.warning',
      style: {
        'border-color': '#FF832B',
        'background-opacity': 0.95
      }
    },
    {
      selector: 'node.error',
      style: {
        'border-color': '#DA1E28',
        'background-opacity': 0.95
      }
    },
    // Compound/parent nodes
    {
      selector: 'node:parent',
      style: {
        'background-opacity': 0.1,
        'border-width': '2px',
        'border-style': 'dashed',
        'border-color': isDark ? '#555' : '#ccc',
        'text-valign': 'top',
        'text-halign': 'center',
        'font-size': '12px',
        'font-weight': '500',
        'padding': '20px'
      }
    },
    // Edge styles
    {
      selector: 'edge',
      style: {
        'width': 3,
        'line-color': isDark ? '#555' : '#0078D4',
        'target-arrow-color': isDark ? '#555' : '#0078D4',
        'target-arrow-shape': 'triangle',
        'target-arrow-fill': 'filled',
        'arrow-scale': 1.5,
        'curve-style': 'bezier',
        'control-point-step-size': 80,
        'label': 'data(label)',
        'font-size': '11px',
        'font-weight': '600',
        'text-rotation': 'autorotate',
        'text-margin-y': -12,
        'text-background-color': isDark ? '#1e1e1e' : '#ffffff',
        'text-background-opacity': 0.9,
        'text-background-padding': '4px',
        'text-background-shape': 'roundrectangle',
        'text-border-width': 1,
        'text-border-color': isDark ? '#3e3e42' : '#e1e4e8',
        'text-border-opacity': 1,
        'color': isDark ? '#e0e0e0' : '#24292e',
        'opacity': 0.8,
        'z-index': 1
      }
    },
    {
      selector: 'edge.highlighted-edge',
      style: {
        'width': 5,
        'line-color': '#0078D4',
        'target-arrow-color': '#0078D4',
        'opacity': 1,
        'z-index': 999
      }
    },
    {
      selector: 'edge.edge-hover',
      style: {
        'width': 5,
        'line-color': '#FF832B',
        'target-arrow-color': '#FF832B',
        'opacity': 1
      }
    },
    // Animated edges
    {
      selector: 'edge.animated-edge',
      style: {
        'line-style': 'solid',
        'line-dash-pattern': [10, 5],
        'line-dash-offset': 24
      }
    }
  ];
};

// Helper: Get color for node type (PLM Data Migration AI Factory)
const getColorForType = (type) => {
  const colorMap = {
    // PLM Sources - TCS Blue shades
    'plm_source': '#0033A0',      // TCS Blue - Teamcenter, Windchill
    'cad_source': '#00539B',      // TCS Dark Blue - CATIA, NX, Creo
    
    // AI Agents - TCS Purple
    'ai_agent': '#6A1B9A',        // Purple - AI Orchestration Layer
    
    // Extract - Light blue
    'extract': '#42A5F5',         // Light Blue - Extraction processes
    
    // Transform - TCS Orange
    'transform': '#FB8C00',       // Orange - Transformations
    
    // Quality (SODA) - TCS Green
    'quality': '#43A047',         // Green - Quality checks
    
    // Load - TCS Indigo
    'load': '#5E35B1',            // Indigo - Loading stages
    
    // Target Systems - TCS Dark
    'target': '#263238',          // Dark - Target systems
    
    // Legacy support
    'Database': '#1976D2',
    'CSV': '#FB8C00',
    'JSON': '#7B1FA2',
    'XML': '#E53935',
    'Processor': '#42A5F5',
    'ETL': '#42A5F5',
    'API': '#5E35B1',
    'Service': '#5E35B1',
    'Quality': '#43A047',
    'DataQualityIssue': '#D32F2F',
    'default': '#78909C'
  };
  return colorMap[type] || colorMap['default'];
};
