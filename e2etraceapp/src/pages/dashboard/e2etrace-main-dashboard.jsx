import React, { useState, useEffect, useRef, useMemo, useCallback } from 'react';
import E2ETraceGraphContainer from './components/e2etrace-graph-container.jsx';
import E2ETraceGraphChat from './components/e2etrace-graph-chat.jsx';
import GraphToolbar from '../../components/e2etrace-graph-toolbar.jsx';
import ETLOverview from '../../components/e2etrace-etl-overview.jsx';
import EnhancedETLOverview from '../../components/e2etrace-enhanced-etl-overview.jsx';
import Widget from '../../components/e2etrace-widget.jsx';
import { E2ETraceDataTable } from '../../components/e2etrace-data-table';
import { E2ETraceAdvancedSearch } from '../../components/e2etrace-advanced-search';
import { E2ETraceGraphLegendDropdown } from '../../components/e2etrace-graph-legend-dropdown';
import { e2etraceUseGraphData } from '../../hooks/e2etrace-use-graph-data';
import { e2etraceUseDashboardState } from '../../hooks/e2etrace-use-dashboard-state';
import { e2etraceUseLayout } from '../../contexts/e2etrace-layout-context';
import { e2etraceUseGraphSelection } from '../../hooks/e2etrace-use-graph-selection';
import { e2etraceTransformDataForCytoscape } from '../../utils/e2etrace-graph';
import { applyGraphFilter, calculateGraphStats } from '../../utils/e2etrace-graph-enhancement';
import './e2etrace-main-dashboard.css';
import '../../components/e2etrace-advanced-search.css';
import '../../components/e2etrace-graph-legend-dropdown.css';
import { ErrorBoundary, Skeleton } from '../../components/ErrorBoundaryAndSkeleton.jsx';

export default function E2ETraceMainDashboard() {
  // Use graphData from the hook, not local state
  const [selectedNodeCount, setSelectedNodeCount] = useState(0);
  const [filteredNodeCount, setFilteredNodeCount] = useState(0);
  const [colorScheme, setColorScheme] = useState('default');
  
  // State managed by custom hooks
  const [tableElements, setTableElements] = useState([]);
  const { graphData, loading, loadingError } = e2etraceUseGraphData(setTableElements);
  const { chatMessages, chatInputValue, isChatSending, handleSendChatMessage, onChatInputChange } = e2etraceUseDashboardState(/* setGraphData */ null, null, setTableElements);
  const cyRef = useRef(null);

  // Get Cytoscape layout configuration from context
  const { layoutConfig: _layoutConfig } = e2etraceUseLayout();

  // Integrate graph selection logic into a custom hook
  e2etraceUseGraphSelection(cyRef, graphData, setTableElements);

  // Cytoscape elements derived from graphData with enhancements
  const cyElements = useMemo(() => {
    return e2etraceTransformDataForCytoscape(graphData, { 
      colorScheme,
      autoGrouping: true,
      sizingProperty: 'importance',
      defaultSize: 50
    });
  }, [graphData, colorScheme]);

  // Calculate graph statistics as a derived value — avoids the extra render
  // that a useEffect+setState pair would cause.
  const graphStats = useMemo(() => calculateGraphStats(cyElements), [cyElements]);

  // Enhanced search handler with highlighting
  const handleAdvancedSearch = useCallback((query) => {
    const cy = cyRef.current;
    if (!cy) return;
    
    if (cy.highlightSearchResults) {
      cy.highlightSearchResults(query);
    } else {
      // Fallback to basic highlighting
      cy.elements().removeClass('search-highlight search-dimmed');
      if (!query) return;
      
      const matches = cy.elements().filter(ele => {
        const data = ele.data();
        const searchableText = [
          data.label,
          data.id,
          data.group,
          data.type,
          JSON.stringify(data.properties || {})
        ].join(' ').toLowerCase();
        
        return searchableText.includes(query.toLowerCase());
      });
      
      if (matches.length > 0) {
        cy.elements().addClass('search-dimmed');
        matches.removeClass('search-dimmed').addClass('search-highlight');
      }
    }
  }, []);

  // Enhanced filter handler
  const handleFilter = useCallback((filterOptions) => {
    const cy = cyRef.current;
    if (!cy) return;
    
    cy.elements().removeClass('filtered-out');
    
    const { nodeTypes = [], edgeTypes = [], statusFilter = [] } = filterOptions;
    
    let filteredCount = 0;
    
    // Filter by node types
    if (nodeTypes.length > 0) {
      const unmatchedNodes = cy.nodes().filter(node => {
        const nodeData = node.data();
        return !nodeTypes.includes(nodeData.type || nodeData.group);
      });
      unmatchedNodes.addClass('filtered-out');
      filteredCount += unmatchedNodes.length;
    }
    
    // Filter by edge types
    if (edgeTypes.length > 0) {
      const unmatchedEdges = cy.edges().filter(edge => {
        const edgeData = edge.data();
        return !edgeTypes.includes(edgeData.type);
      });
      unmatchedEdges.addClass('filtered-out');
    }
    
    // Filter by status
    if (statusFilter.length > 0) {
      const unmatchedByStatus = cy.nodes().filter(node => {
        const nodeData = node.data();
        return nodeData.status && !statusFilter.includes(nodeData.status);
      });
      unmatchedByStatus.addClass('filtered-out');
      filteredCount += unmatchedByStatus.length;
    }
    
    setFilteredNodeCount(filteredCount);
  }, []);

  // Handle layout changes
  const handleLayoutChange = useCallback((layoutName) => {
    const cy = cyRef.current;
    if (!cy) return;
    
    const layoutOptions = getLayoutOptions(layoutName);
    cy.layout(layoutOptions).run();
  }, []);

  // Handle color scheme changes
  const handleColorSchemeChange = useCallback((scheme) => {
    setColorScheme(scheme);
    // The graph will re-render with new colors via the useMemo dependency
  }, []);

  // Get layout options for different layouts
  const getLayoutOptions = (layoutName) => {
    const baseOptions = {
      name: layoutName,
      animate: true,
      animationDuration: 500,
      fit: true,
      padding: 30
    };

    switch (layoutName) {
      case 'cose':
        return {
          ...baseOptions,
          nodeRepulsion: function(node) { return node.degree() * 2000; },
          nodeOverlap: 20,
          idealEdgeLength: 100,
          edgeElasticity: 100,
          nestingFactor: 5,
          gravity: 80,
          numIter: 1000,
          initialTemp: 200,
          coolingFactor: 0.95,
          minTemp: 1.0
        };
      case 'grid':
        return { ...baseOptions, rows: undefined, cols: undefined };
      case 'circle':
        return { ...baseOptions, radius: undefined, startAngle: 3 / 2 * Math.PI };
      case 'concentric':
        return {
          ...baseOptions,
          concentric: function(node) { return node.degree(); },
          levelWidth: function(_nodes) { return 2; },
          spacing: 30
        };
      case 'breadthfirst':
        return {
          ...baseOptions,
          directed: true,
          spacingFactor: 1.75,
          avoidOverlap: true
        };
      default:
        return baseOptions;
    }
  };

  // Update selected count when selection changes
  useEffect(() => {
    const cy = cyRef.current;
    if (!cy) return;
    
    const updateSelectedCount = () => {
      setSelectedNodeCount(cy.$(':selected').length);
    };
    
    cy.on('select unselect', updateSelectedCount);
    return () => {
      if (cy) cy.off('select unselect', updateSelectedCount);
    };
  }, []);

  // Callback for table row clicks to select and focus on graph elements
  const handleGraphElementClick = useCallback((elementId) => {
    const cy = cyRef.current;
    if (!cy || !elementId) return;

    const elementToSelect = cy.getElementById(String(elementId));
    if (elementToSelect.length > 0) {
      cy.elements().unselect();
      elementToSelect.select();
      cy.animate({ 
        fit: { eles: elementToSelect, padding: 100 }, 
        duration: 500, 
        easing: 'ease-out-quad' 
      });
    }
  }, []);

  // Handler for ETL overview filter applications
  const handleETLFilterApply = useCallback((filterOptions) => {
    if (filterOptions.type && cyRef.current) {
      // Apply type-based filter to highlight nodes of specific types
      applyGraphFilter(cyRef.current, { nodeType: filterOptions.type });
    }
  }, []);

  return (
    <div className="dashboard-container" style={{ 
      background: '#f8f9fa', 
      padding: '0.5rem',
      minHeight: '100vh'
    }}>
      {/* Enhanced ETL Pipeline Overview with Charts and Excel Export */}
      <EnhancedETLOverview
        graphStats={graphStats}
        selectedNodeCount={selectedNodeCount}
        filteredNodeCount={filteredNodeCount}
        loadingError={loadingError}
        graphData={graphData}
        onElementClick={handleGraphElementClick}
        onFilterApply={handleETLFilterApply}
        cytoscapeRef={cyRef}
      />
      
      {/* Advanced Graph Toolbar */}
      <GraphToolbar
        cytoscapeRef={cyRef}
        onSearchChange={handleAdvancedSearch}
        onFilterChange={handleFilter}
        onLayoutChange={handleLayoutChange}
        onColorSchemeChange={handleColorSchemeChange}
        graphStats={graphStats}
      />
      
      {/* Graph and Chat - Side by Side */}
      <div style={{ 
        display: 'grid', 
        gridTemplateColumns: '1fr 400px', 
        gap: '1rem',
        marginBottom: '1rem',
        height: '600px'
      }}>
        {/* Graph Visualization */}
        <Widget
          title="Graph Visualization"
          loading={loading}
          className="graph-widget"
          fullHeight={true}
        >
          <div style={{ 
            position: 'relative', 
            height: '500px',
            overflow: 'hidden',
            borderRadius: '8px',
            border: '1px solid #e9ecef'
          }}>
            <ErrorBoundary fallback={<div>Error loading graph visualization</div>}>
              <E2ETraceGraphContainer elements={cyElements} isLoading={loading} cyRef={cyRef} />
            </ErrorBoundary>
          </div>
        </Widget>
        
        {/* Chat Panel */}
        <Widget
          title="Graph Chat Assistant"
          className="chat-widget"
          fullHeight={true}
        >
          <div style={{ 
            overflow: 'hidden',
            height: '500px'
          }}>
            <ErrorBoundary fallback={<div>Error loading chat assistant</div>}>
              <E2ETraceGraphChat 
                chatMessages={chatMessages} 
                chatInputValue={chatInputValue} 
                isChatSending={isChatSending} 
                onSendMessage={handleSendChatMessage} 
                onInputChange={onChatInputChange} 
              />
            </ErrorBoundary>
          </div>
        </Widget>
      </div>
      
      {/* Data Table - Bottom, Full Width */}
      <Widget
        title={`Data Table (${tableElements?.length || 0} items)`}
        headerActions={
          tableElements?.length > 0 && (
            <span style={{ 
              fontSize: '0.8rem', 
              color: '#6c757d',
              fontWeight: 'normal'
            }}>
              Click any row to highlight in graph
            </span>
          )
        }
        fullHeight={false}
        collapsible={true}
        className="data-table-widget"
      >
        <div style={{ 
          maxHeight: '500px',
          overflow: 'auto'
        }}>
          <ErrorBoundary fallback={<div>Error loading data table</div>}>
            <E2ETraceDataTable tableElements={tableElements} onRowClick={handleGraphElementClick} />
          </ErrorBoundary>
        </div>
      </Widget>
    </div>
  );
}
