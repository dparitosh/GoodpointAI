import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { XStateLayout } from './XStateLayout';
import { TreeNavigator } from './TreeNavigator';
import { InspectorPanel } from './InspectorPanel';
import { EventPanel } from './EventPanel';
import { DetailDrawer } from './DetailDrawer';
import { StateFlowDiagram } from './StateFlowDiagram';
import { E2ETraceCytoscapeGraph } from '../../pages/dashboard/e2etrace-cytoscape-graph';
import { xstateStylesheet, xstateStylesheetDark } from './xstate-cytoscape-stylesheet';
import { useAdvancedCytoscapeInteractions } from '../../hooks/useAdvancedCytoscapeInteractions';
import { useE2ETraceTheme } from '../../contexts/e2etrace-theme-context.jsx';
import { getNodeColor } from '../../constants/node-colors';
import './XStateVisualizer.css';

/**
 * XState Visualizer Main Component
 * Complete XState-style graph visualization with 3-panel layout
 * Modes: Graph View, State Flow Diagram
 */
export const XStateVisualizer = ({
  graphData,
  onNodeUpdate,
  theme: themeOverride,
  embedded = false,
  enabledViewModes = ['stateflow', 'graph'],
  uiVariant = 'full', // 'full' | 'graph-only'
  navigatorVariant = 'tree', // 'tree' | 'workflow'
  workflowOptions = [],
  selectedWorkflowId = '',
  onWorkflowSelect,
  workflowNavigatorHint = '',
}) => {
  const themeContext = useE2ETraceTheme?.();
  const normalizedThemeOverride = String(themeOverride || '').toLowerCase();
  const theme = normalizedThemeOverride === 'dark' || normalizedThemeOverride === 'light'
    ? normalizedThemeOverride
    : (themeContext?.theme === 'dark' ? 'dark' : 'light');
  const [selectedNode, setSelectedNode] = useState(null);
  const [events, setEvents] = useState([]);
  const [isDetailDrawerOpen, setIsDetailDrawerOpen] = useState(false);
  const [detailDrawerNode, setDetailDrawerNode] = useState(null);
  const [viewMode, setViewMode] = useState('stateflow'); // 'graph' | 'stateflow'
  const [_layoutMode, _setLayoutMode] = useState('hierarchical');
  const cyRef = useRef(null);

  const normalizedEnabledViewModes = useMemo(() => {
    const allowed = ['stateflow', 'graph'];
    const incoming = Array.isArray(enabledViewModes) ? enabledViewModes : [];
    const filtered = incoming.filter((mode) => allowed.includes(mode));
    return filtered.length > 0 ? filtered : ['stateflow'];
  }, [enabledViewModes]);

  useEffect(() => {
    if (normalizedEnabledViewModes.includes(viewMode)) return;
    setViewMode(normalizedEnabledViewModes.includes('stateflow') ? 'stateflow' : normalizedEnabledViewModes[0] || 'stateflow');
  }, [normalizedEnabledViewModes, viewMode]);

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
    // Prevent invalid-edge-endpoint warnings by avoiding node overlap.
    // When randomize is false, Cytoscape may start many nodes at (0,0) and
    // fcose can end up with overlapping nodes in small graphs.
    randomize: true,
    avoidOverlap: true,
    avoidOverlapPadding: 24,
    nodeOverlap: 24,
    spacingFactor: 1.2,
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
    if (!node?.id) return;

    // Always update selected node state (works for all view modes)
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

    // If Cytoscape is mounted, also visually select + focus
    if (!cyRef.current) return;

    const cy = cyRef.current;
    const cyNode = cy.getElementById(node.id);

    if (cyNode.length > 0) {
      cy.elements().unselect();
      cyNode.select();
      cy.animate({
        fit: { eles: cyNode, padding: 100 },
        duration: 500,
        easing: 'ease-out-quad'
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

  // Get stylesheet based on theme
  const stylesheet = theme === 'dark' ? xstateStylesheetDark : xstateStylesheet;

  const treePanel = useMemo(() => {
    if (navigatorVariant === 'workflow') {
      const safeSelected = selectedWorkflowId || '';
      const hasOptions = Array.isArray(workflowOptions) && workflowOptions.length > 0;

      return (
        <div className={`xstate-visualizer__workflow-navigator xstate-visualizer__workflow-navigator--${theme}`}>
          <label className="xstate-visualizer__workflow-label" htmlFor="xstate-workflow-selector">
            Workflow Instance
          </label>
          <select
            id="xstate-workflow-selector"
            className="xstate-visualizer__workflow-select"
            value={safeSelected}
            onChange={(e) => onWorkflowSelect?.(e.target.value)}
            disabled={!hasOptions}
            aria-label="Workflow instance selector"
          >
            {hasOptions ? null : <option value="">No workflows</option>}
            {workflowOptions.map((wf) => {
              const id = wf?.id;
              if (!id) return null;
              const label = wf?.name || wf?.workflow_name || wf?.title || id;
              return (
                <option key={id} value={id}>
                  {label}
                </option>
              );
            })}
          </select>
          {workflowNavigatorHint ? (
            <div className="xstate-visualizer__workflow-hint">{String(workflowNavigatorHint)}</div>
          ) : null}
        </div>
      );
    }

    return (
      <TreeNavigator
        nodes={treeNodes}
        onNodeClick={handleNodeClick}
        selectedNodeId={selectedNode?.id}
        theme={theme}
      />
    );
  }, [navigatorVariant, selectedWorkflowId, workflowOptions, onWorkflowSelect, workflowNavigatorHint, theme, treeNodes, handleNodeClick, selectedNode?.id]);

  if (uiVariant === 'graph-only') {
    return (
      <div className={`xstate-visualizer xstate-visualizer--${theme}${embedded ? ' xstate-visualizer--embedded' : ''} xstate-visualizer--graph-only`}>
        <div className="xstate-visualizer__graph-only">
          <div style={{ width: '100%', height: '100%', position: 'relative' }}>
            <E2ETraceCytoscapeGraph
              elements={cytoscapeElements}
              stylesheet={stylesheet}
              layout={layoutConfig}
              cyRef={cyRef}
            />

            <div className="xstate-visualizer__controls">
              <button
                className="xstate-visualizer__control-btn"
                onClick={() => cyRef.current?.fit()}
                title="Fit to screen"
              >
                <i className="fas fa-expand" aria-hidden="true" />
              </button>
              <button
                className="xstate-visualizer__control-btn"
                onClick={() => cyRef.current?.layout(layoutConfig).run()}
                title="Reset layout"
              >
                <i className="fas fa-sync" aria-hidden="true" />
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className={`xstate-visualizer xstate-visualizer--${theme}${embedded ? ' xstate-visualizer--embedded' : ''}`}>
      {/* Theme and View Mode Toggle Buttons */}
      <div className="xstate-visualizer__toolbar">
        <div className="xstate-visualizer__view-toggle">
          {normalizedEnabledViewModes.includes('stateflow') ? (
            <button
              className={`view-toggle-btn ${viewMode === 'stateflow' ? 'active' : ''}`}
              onClick={() => setViewMode('stateflow')}
              title="State Flow Diagram - XState Style"
            >
              <i className="fas fa-exchange-alt" aria-hidden="true" /> State Flow
            </button>
          ) : null}
          {normalizedEnabledViewModes.includes('graph') ? (
            <button
              className={`view-toggle-btn ${viewMode === 'graph' ? 'active' : ''}`}
              onClick={() => setViewMode('graph')}
              title="Graph View"
            >
              <i className="fas fa-project-diagram" aria-hidden="true" /> Graph
            </button>
          ) : null}
        </div>
      </div>

      {/* Detail Drawer */}
      <DetailDrawer
        node={detailDrawerNode}
        isOpen={isDetailDrawerOpen}
        onClose={() => setIsDetailDrawerOpen(false)}
        theme={theme}
      />

      {viewMode === 'stateflow' ? (
        <XStateLayout
          theme={theme}
          treePanel={treePanel}
          graphPanel={
            <StateFlowDiagram
              nodes={graphData?.nodes || []}
              edges={graphData?.edges || []}
              selectedNode={selectedNode}
              onNodeClick={handleNodeClick}
              onNodeDoubleClick={(node) => {
                setDetailDrawerNode(node);
                setIsDetailDrawerOpen(true);
              }}
              theme={theme}
              layout="fcose"
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
      ) : (
        <XStateLayout
          theme={theme}
          treePanel={treePanel}
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
                  <i className="fas fa-expand" aria-hidden="true" />
                </button>
                <button 
                  className="xstate-visualizer__control-btn"
                  onClick={() => cyRef.current?.layout(layoutConfig).run()}
                  title="Reset layout"
                >
                  <i className="fas fa-sync" aria-hidden="true" />
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
      )}
    </div>
  );
};

/**
 * Get color for node type - delegates to centralized constants
 * IMPORTANT: DO NOT define colors here - update constants/node-colors.js instead
 * @param {string} type - Node type/group name
 * @returns {string} Hex color code
 */
const getColorForType = (type) => {
  return getNodeColor(type);
};

export default XStateVisualizer;
