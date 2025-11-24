import React, { useState, useCallback, useMemo, useRef, useEffect } from 'react';
import { XStateLayout } from './XStateLayout';
import { TreeNavigator } from './TreeNavigator';
import { InspectorPanel } from './InspectorPanel';
import { EventPanel } from './EventPanel';
import { DetailDrawer } from './DetailDrawer';
import { SwimLaneLayout } from './SwimLaneLayout';
import { E2ETraceCytoscapeGraph } from '../../pages/dashboard/e2etrace-cytoscape-graph';
import { xstateStylesheet, xstateStylesheetDark } from './xstate-cytoscape-stylesheet';
import { useAdvancedCytoscapeInteractions } from '../../hooks/useAdvancedCytoscapeInteractions';
import './XStateVisualizer.css';

/**
 * XState Visualizer Main Component
 * Complete XState-style graph visualization with 3-panel layout + swimlane workflow view
 */
export const XStateVisualizer = ({ graphData, onNodeUpdate }) => {
  const [theme, setTheme] = useState('light');
  const [selectedNode, setSelectedNode] = useState(null);
  const [events, setEvents] = useState([]);
  const [isDetailDrawerOpen, setIsDetailDrawerOpen] = useState(false);
  const [detailDrawerNode, setDetailDrawerNode] = useState(null);
  const [viewMode, setViewMode] = useState('graph'); // 'graph' or 'swimlane'
  const cyRef = useRef(null);

  // Convert graph data to tree structure for navigator
  const treeNodes = useMemo(() => {
    if (!graphData || !graphData.nodes) return [];

    // Group nodes by type for hierarchical display
    const nodesByType = {};
    graphData.nodes.forEach(node => {
      const type = node.type || node.group || 'Other';
      if (!nodesByType[type]) {
        nodesByType[type] = [];
      }
      nodesByType[type].push(node);
    });

    // Create tree structure
    return Object.entries(nodesByType).map(([type, nodes]) => ({
      id: `type-${type}`,
      label: type,
      type: type,
      count: nodes.length,
      color: getColorForType(type),
      children: nodes.map(node => ({
        id: node.id,
        label: node.label || node.id,
        type: node.type || node.group,
        color: node.backgroundColor || getColorForType(node.type),
        properties: node.properties,
        relationships: node.relationships
      }))
    }));
  }, [graphData]);

  // Convert graph data to cytoscape elements
  const cytoscapeElements = useMemo(() => {
    if (!graphData) return [];

    const nodes = (graphData.nodes || []).map(node => ({
      data: {
        id: node.id,
        label: node.label || node.id,
        type: node.type || node.group,
        group: node.group,
        backgroundColor: node.backgroundColor || getColorForType(node.type),
        properties: node.properties,
        status: node.status,
        size: node.size || 50
      }
    }));

    const edges = (graphData.edges || []).map(edge => ({
      data: {
        id: edge.id || `${edge.source}-${edge.target}`,
        source: edge.source,
        target: edge.target,
        label: edge.label,
        type: edge.type,
        weight: edge.weight || 1
      }
    }));

    return [...nodes, ...edges];
  }, [graphData]);

  // Layout configuration
  const layoutConfig = {
    name: 'fcose',
    animate: true,
    animationDuration: 600,
    animationEasing: 'cubic-bezier(0.4, 0.0, 0.2, 1)',
    fit: true,
    padding: 50,
    nodeDimensionsIncludeLabels: true,
    randomize: false,
    nodeRepulsion: 4500,
    idealEdgeLength: 150,
    edgeElasticity: 0.45,
    nestingFactor: 0.1,
    gravity: 0.25,
    numIter: 2500,
    tile: true,
    tilingPaddingVertical: 30,
    tilingPaddingHorizontal: 30,
  };

  // Handle node selection
  const handleNodeClick = useCallback((node) => {
    if (!cyRef.current) return;

    const cy = cyRef.current;
    const cyNode = cy.getElementById(node.id);
    
    if (cyNode.length > 0) {
      // Unselect all and select the clicked node
      cy.elements().unselect();
      cyNode.select();
      
      // Animate to focus on the node
      cy.animate({
        fit: { eles: cyNode, padding: 100 },
        duration: 500,
        easing: 'ease-out-quad'
      });

      // Update selected node state
      setSelectedNode({
        ...node,
        relationships: getNodeRelationships(node.id, graphData)
      });

      // Add event
      addEvent({
        type: 'info',
        title: 'Node Selected',
        details: `Selected ${node.type || 'node'}: ${node.label || node.id}`,
        timestamp: new Date().toISOString(),
        affectedNodes: [node.id]
      });
    }
  }, [graphData]);

  // Handle property changes
  const handlePropertyChange = useCallback((nodeId, field, value) => {
    if (onNodeUpdate) {
      onNodeUpdate(nodeId, { [field]: value });
    }

    addEvent({
      type: 'info',
      title: 'Property Updated',
      details: `Updated ${field} to "${value}"`,
      timestamp: new Date().toISOString(),
      affectedNodes: [nodeId]
    });
  }, [onNodeUpdate]);

  // Handle event clicks
  const handleEventClick = useCallback((event) => {
    if (event.affectedNodes && event.affectedNodes.length > 0 && cyRef.current) {
      const cy = cyRef.current;
      const nodes = cy.collection();
      
      event.affectedNodes.forEach(nodeId => {
        const node = cy.getElementById(nodeId);
        if (node.length > 0) {
          nodes.merge(node);
        }
      });

      if (nodes.length > 0) {
        cy.elements().unselect();
        nodes.select();
        cy.animate({
          fit: { eles: nodes, padding: 100 },
          duration: 500,
          easing: 'ease-out-quad'
        });
      }
    }
  }, []);

  // Add event to log
  const addEvent = (event) => {
    setEvents(prev => [...prev, { ...event, id: Date.now() }]);
  };

  // Get node relationships
  const getNodeRelationships = (nodeId, data) => {
    if (!data || !data.edges) return [];
    
    return data.edges
      .filter(edge => edge.source === nodeId || edge.target === nodeId)
      .map(edge => ({
        type: edge.type || edge.label || 'CONNECTED_TO',
        target: edge.source === nodeId ? edge.target : edge.source,
        direction: edge.source === nodeId ? 'outgoing' : 'incoming'
      }));
  };

  // Handle double-click on nodes
  const handleNodeDoubleClick = useCallback((nodeData) => {
    const fullNode = {
      ...nodeData,
      relationships: getNodeRelationships(nodeData.id, graphData)
    };
    
    setDetailDrawerNode(fullNode);
    setIsDetailDrawerOpen(true);

    addEvent({
      type: 'info',
      title: 'Node Detail View',
      details: `Opened detailed view for ${nodeData.label || nodeData.id}`,
      timestamp: new Date().toISOString(),
      affectedNodes: [nodeData.id]
    });
  }, [graphData]);

  // Handle multi-select
  const handleMultiSelect = useCallback((nodeIds) => {
    addEvent({
      type: 'info',
      title: 'Multi-Select',
      details: `Selected ${nodeIds.length} nodes`,
      timestamp: new Date().toISOString(),
      affectedNodes: nodeIds
    });
  }, []);

  // Handle canvas pan
  const handleCanvasPan = useCallback(() => {
    // Optional: Add logic for pan tracking
  }, []);

  // Setup advanced interactions
  useAdvancedCytoscapeInteractions(cyRef, {
    onNodeDoubleClick: handleNodeDoubleClick,
    onMultiSelect: handleMultiSelect,
    onCanvasPan: handleCanvasPan,
    enableSmartSnapping: true
  });

  // Setup cytoscape event listeners
  useEffect(() => {
    if (!cyRef.current) return;

    const cy = cyRef.current;

    // Node selection handler
    const onNodeSelect = (evt) => {
      const node = evt.target;
      const nodeData = node.data();
      
      setSelectedNode({
        id: nodeData.id,
        label: nodeData.label,
        type: nodeData.type,
        group: nodeData.group,
        color: nodeData.backgroundColor,
        properties: nodeData.properties || {},
        relationships: getNodeRelationships(nodeData.id, graphData)
      });
    };

    // Node unselect handler
    const onNodeUnselect = () => {
      if (cy.$(':selected').length === 0) {
        setSelectedNode(null);
      }
    };

    cy.on('select', 'node', onNodeSelect);
    cy.on('unselect', 'node', onNodeUnselect);

    return () => {
      if (cy) {
        cy.off('select', 'node', onNodeSelect);
        cy.off('unselect', 'node', onNodeUnselect);
      }
    };
  }, [graphData]);

  // Toggle theme
  const toggleTheme = () => {
    setTheme(prev => prev === 'light' ? 'dark' : 'light');
  };

  // Get stylesheet based on theme
  const stylesheet = theme === 'dark' ? xstateStylesheetDark : xstateStylesheet;

  return (
    <div className={`xstate-visualizer xstate-visualizer--${theme}`}>
      {/* Theme and View Mode Toggle Buttons */}
      <div className="xstate-visualizer__toolbar">
        <button 
          className="xstate-visualizer__theme-toggle"
          onClick={toggleTheme}
          aria-label="Toggle theme"
        >
          {theme === 'light' ? '🌙' : '☀️'}
        </button>
        <div className="xstate-visualizer__view-toggle">
          <button
            className={`view-toggle-btn ${viewMode === 'graph' ? 'active' : ''}`}
            onClick={() => setViewMode('graph')}
            title="Graph View"
          >
            🔷 Graph
          </button>
          <button
            className={`view-toggle-btn ${viewMode === 'swimlane' ? 'active' : ''}`}
            onClick={() => setViewMode('swimlane')}
            title="Swimlane Workflow View"
          >
            📊 Workflow
          </button>
        </div>
      </div>

      {/* Detail Drawer */}
      <DetailDrawer
        node={detailDrawerNode}
        isOpen={isDetailDrawerOpen}
        onClose={() => setIsDetailDrawerOpen(false)}
        theme={theme}
      />

      {viewMode === 'graph' ? (
        <XStateLayout
          theme={theme}
          treePanel={
            <TreeNavigator
              nodes={treeNodes}
              onNodeClick={handleNodeClick}
              selectedNodeId={selectedNode?.id}
              theme={theme}
            />
          }
          graphPanel={
            <div style={{ width: '100%', height: '100%', position: 'relative' }}>
              <E2ETraceCytoscapeGraph
                elements={cytoscapeElements}
                stylesheet={stylesheet}
                layout={layoutConfig}
                cyRef={cyRef}
              />
              
              {/* Graph Controls Overlay */}
              <div className="xstate-visualizer__controls">
                <button 
                  className="xstate-visualizer__control-btn"
                  onClick={() => cyRef.current?.fit()}
                  title="Fit to screen"
                >
                  ⊡
                </button>
                <button 
                  className="xstate-visualizer__control-btn"
                  onClick={() => cyRef.current?.layout(layoutConfig).run()}
                  title="Reset layout"
                >
                  ⟲
                </button>
              </div>
            </div>
          }
          inspectorPanel={
            <InspectorPanel
              selectedNode={selectedNode}
              onPropertyChange={handlePropertyChange}
              theme={theme}
            />
          }
          eventPanel={
            <EventPanel
              events={events}
              onEventClick={handleEventClick}
              theme={theme}
            />
          }
        />
      ) : (
        <XStateLayout
          theme={theme}
          treePanel={
            <TreeNavigator
              nodes={treeNodes}
              onNodeClick={handleNodeClick}
              selectedNodeId={selectedNode?.id}
              theme={theme}
            />
          }
          graphPanel={
            <SwimLaneLayout
              nodes={graphData?.nodes || []}
              edges={graphData?.edges || []}
              selectedNode={selectedNode}
              onNodeClick={handleNodeClick}
            />
          }
          inspectorPanel={
            <InspectorPanel
              selectedNode={selectedNode}
              onPropertyChange={handlePropertyChange}
              theme={theme}
            />
          }
          eventPanel={
            <EventPanel
              events={events}
              onEventClick={handleEventClick}
              theme={theme}
            />
          }
        />
      )}
    </div>
  );
};

// Helper function to get color based on node type (ETL/Data Migration)
const getColorForType = (type) => {
  const colorMap = {
    // Data Sources
    'Database': '#48a4ff',
    'Teamcenter': '#48a4ff',
    'CustomDB': '#48a4ff',
    'CSV': '#ffba5a',
    'JSON': '#9b6cff',
    'XML': '#ff7077',
    'PLMXML': '#ff7077',
    // Processing/Transform
    'Processor': '#21d5c1',
    'Transform': '#21d5c1',
    'ETL': '#21d5c1',
    // Services
    'API': '#6e6fff',
    'Service': '#6e6fff',
    'Endpoint': '#6e6fff',
    // Issues
    'DataQualityIssue': '#e74c3c',
    // Default
    'default': '#95a5a6'
  };
  return colorMap[type] || colorMap['default'];
};

export default XStateVisualizer;
