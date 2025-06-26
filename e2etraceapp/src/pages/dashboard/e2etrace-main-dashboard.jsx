import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import cytoscape from 'cytoscape';
import { E2ETraceCytoscapeGraph } from './e2etrace-cytoscape-graph';
import { cytoscapeStylesheet } from './e2etrace-cytoscape-stylesheet';
import { E2ETraceGraphFilter } from './components/e2etrace-graph-filter';
import { E2ETraceDataTable } from '../../components/e2etrace-data-table';
import { E2ETraceChatPanel } from '../../components/e2etrace-chat-panel';
import { e2etraceUseGraphData } from '../../hooks/e2etrace-use-graph-data';
import { e2etraceUseDashboardState } from '../../hooks/e2etrace-use-dashboard-state';
import { e2etraceUseLayout } from '../../contexts/e2etrace-layout-context';
import { e2etraceUseGraphSelection } from '../../hooks/e2etrace-use-graph-selection';
import { e2etraceCreateTableElementsFromGraph, e2etraceTransformDataForCytoscape } from '../../utils/e2etrace-graph';
import { useGraphFilter } from '../../contexts/e2etrace-graph-filter-context';
import { E2ETraceGraphLegend } from './components/e2etrace-graph-legend';
import './e2etrace-main-dashboard.css';

const Widget = ({ title, children, className }) => (
  <div className={`dashboard-widget ${className || ''}`}>
    <div className="dashboard-widget-header">{title}</div>
    <div className="dashboard-widget-content">{children}</div>
  </div>
);

// --- Main React Component: E2ETraceMainDashboard ---
const E2ETraceMainDashboard = () => {
    // State managed by custom hooks
    const [tableElements, setTableElements] = useState([]);
    const { graphData, loading, loadingError, setGraphData } = e2etraceUseGraphData(setTableElements);
    const { chatMessages, chatInputValue, isChatSending, handleSendChatMessage, onChatInputChange } = e2etraceUseDashboardState(setGraphData, null, setTableElements);
    const cyRef = useRef(null);

    const { filterText, setFilterText } = useGraphFilter(); // Use filterText and setFilterText from context

    // Get Cytoscape layout configuration from context
    const { layoutConfig } = e2etraceUseLayout();

    // Integrate graph selection logic into a custom hook
    e2etraceUseGraphSelection(cyRef, graphData, setTableElements);

    // Cytoscape elements derived from graphData
    const cyElements = useMemo(() => e2etraceTransformDataForCytoscape(graphData), [graphData]);

    // Callback for table row clicks to select and focus on graph elements
    const handleGraphElementClick = useCallback((elementId) => { // This needs to be inside the graph tab
        const cy = cyRef.current;
        if (!cy || !elementId) return;

        const elementToSelect = cy.getElementById(String(elementId));
        if (elementToSelect.length > 0) {
            cy.elements().unselect(); // Unselect all first
            elementToSelect.select(); // Select the clicked element
            cy.animate({ fit: { eles: elementToSelect, padding: 100 }, duration: 500, easing: 'ease-out-quad' });
        }
    }, [cyRef]);

    // Graph filtering logic
    useEffect(() => {
        const cy = cyRef.current;
        if (!cy) return;

        if (!filterText) {
            cy.elements().show(); // Show all if no filter
            return;
        }

        const filtered = cy.elements().filter((ele) => {
            const data = ele.data();
            return (
                (data.label && data.label.toLowerCase().includes(filterText.toLowerCase())) ||
                (data.id && String(data.id).toLowerCase().includes(filterText.toLowerCase())) ||
                (data.group && data.group.toLowerCase().includes(filterText.toLowerCase())) ||
                (data.properties && JSON.stringify(data.properties).toLowerCase().includes(filterText.toLowerCase()))
            );
        });
        cy.elements().hide();
        filtered.show();
    }, [filterText, cyRef, cyElements]); // Re-apply filter if graph data changes

    return (
        <div className="dashboard-container dashboard-widgets-layout">
          <div className="dashboard-widgets-row">
            <Widget title="Graph Visualization" className="graph-widget">
              {loading && <div id="loading" className="loading-spinner">Loading graph data...</div>}
              {loadingError && <div id="loading-error" className="error-message">{loadingError}</div>}
              {!loading && !loadingError && cyElements.length === 0 && (
                  <div id="no-graph-data">No graph data to display.</div>
              )}
              {!loading && !loadingError && (
                  <E2ETraceCytoscapeGraph
                      elements={cyElements}
                      stylesheet={cytoscapeStylesheet}
                      layout={layoutConfig}
                      cyRef={cyRef}
                  />
              )}
            </Widget>
            <Widget title="Chat" className="chat-widget">
              <E2ETraceChatPanel
                chatMessages={chatMessages}
                onSendMessage={handleSendChatMessage}
                isChatSending={isChatSending}
                chatInputValue={chatInputValue}
                onChatInputChange={onChatInputChange}
              />
            </Widget>
          </div>
          <div className="dashboard-widgets-row">
            <Widget title="Data Table" className="table-widget">
              <E2ETraceDataTable tableElements={tableElements} onRowClick={handleGraphElementClick} />
            </Widget>
            <Widget title="Filter" className="filter-widget">
              <E2ETraceGraphFilter filterText={filterText} onFilterTextChange={setFilterText} />
            </Widget>
            <Widget title="Legend" className="legend-widget">
              <E2ETraceGraphLegend stylesheet={cytoscapeStylesheet} />
            </Widget>
          </div>
        </div>
    );
};

export default E2ETraceMainDashboard;