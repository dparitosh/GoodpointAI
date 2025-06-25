import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import cytoscape from 'cytoscape';

// Import custom components and hooks
import { E2ETraceCytoscapeGraph } from './e2etrace-cytoscape-graph';
import { cytoscapeStylesheet } from './e2etrace-cytoscape-stylesheet';
import { E2ETraceChatPanel } from '../../components/e2etrace-chat-panel';
import { E2ETraceGraphFilter } from './components/e2etrace-graph-filter';
import { E2ETraceDataTable } from '../../components/e2etrace-data-table';
import { e2etraceUseGraphData } from '../../hooks/e2etrace-use-graph-data';
import { e2etraceUseDashboardState } from '../../hooks/e2etrace-use-dashboard-state';
import { e2etraceUseLayout } from '../../contexts/e2etrace-layout-context'; // Import the layout context hook
import { e2etraceUseResizablePanels } from '../../hooks/e2etrace-use-resizable-panels'; // Import the resizable panels hook
import { e2etraceUseGraphSelection } from '../../hooks/e2etrace-use-graph-selection'; // Import the new graph selection hook
import { e2etraceCreateTableElementsFromGraph, e2etraceTransformDataForCytoscape } from '../../utils/e2etrace-graph';
import { useGraphFilter } from '../../contexts/e2etrace-graph-filter-context'; // Import the new context hook
import { E2ETraceGraphLegend } from './components/e2etrace-graph-legend'; // Re-import from dedicated file
import { E2ETraceQuickActions } from './components/e2etrace-quick-actions'; // Import Quick Actions
// --- Main React Component: E2ETraceMainDashboard ---
const E2ETraceMainDashboard = () => {
    // State managed by custom hooks
    const [tableElements, setTableElements] = useState([]);
    const { graphData, loading, loadingError, setGraphData } = e2etraceUseGraphData(setTableElements);
    const { chatMessages, chatInputValue, isChatSending, handleSendChatMessage, onChatInputChange } = e2etraceUseDashboardState(setGraphData, null, setTableElements);
    
    // Refs for resizable panels
    const graphContainerRef = useRef(null);
    const rightPanelContainerRef = useRef(null);
    const mainResizerRef = useRef(null);
    const mainContentAreaRef = useRef(null);
    const cyRef = useRef(null);

    const { filterText, setFilterText } = useGraphFilter(); // Use filterText and setFilterText from context

    // Integrate resizable panels hook
    e2etraceUseResizablePanels(graphContainerRef, rightPanelContainerRef, mainResizerRef, mainContentAreaRef, cyRef, true); // Resizing is always active

    // Cytoscape elements derived from graphData
    const cyElements = useMemo(() => e2etraceTransformDataForCytoscape(graphData), [graphData]);

    // Get Cytoscape layout configuration from context
    const { layoutConfig } = e2etraceUseLayout();

    // Integrate graph selection logic into a custom hook
    e2etraceUseGraphSelection(cyRef, graphData, setTableElements);

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

    const suggestedPrompts = useMemo(() => [
        "Show me the complete BOM for VALVE-ASSEMBLY-001",
        "What are the key attributes of the asset with ID Pump-SK-007?",
        "Find all 'Safety Critical' components in Teamcenter.",
        "Trace the origin of 'material_specification' for HOUSING-010.",
        "Identify all duplicate 'Material Specification' records.",
        "Show me all 'Drawing' documents not linked to 'Released' Parts.",
        "What is the status of 'Daily Teamcenter Sync' pipeline?",
        "Show me all data that failed to load from last 'PLMXML Ingestion'.",
        "Identify highly central 'Parts' or 'Documents' in our PLM graph.",
        "Generate a Cypher query for 'Released' components in 'Offshore Rig' assets with 'Safety Critical' classification."
    ], []);

    return (
        <div className="dashboard-container"> {/* This remains the top-level container */}
            <div className="main-content-area" ref={mainContentAreaRef}>
                <div id="graph-container" ref={graphContainerRef}>
                    {loading && <div id="loading">Loading graph data...</div>}
                    {loadingError && <div id="loading-error" style={{ color: 'red' }}>{loadingError}</div>}
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
                </div>
                <div 
                    className="resizer" 
                    id="main-resizer-v" 
                    ref={mainResizerRef}>
                </div>
                <div 
                    className="right-panel-container" 
                    ref={rightPanelContainerRef}>
                    {/* Chat Panel remains at the top of the right panel */}
                    <E2ETraceChatPanel
                        chatMessages={chatMessages}
                        onSendMessage={handleSendChatMessage}
                        isChatSending={isChatSending}
                        chatInputValue={chatInputValue}
                        onChatInputChange={onChatInputChange}
                        suggestedPrompts={suggestedPrompts}
                    />
                    {/* Graph Filter is now a standalone component below chat */}
                    <E2ETraceGraphFilter filterText={filterText} onFilterTextChange={setFilterText} />
                    {/* Data-related components stacked vertically below the filter */}
                    <E2ETraceDataTable tableElements={tableElements} onRowClick={handleGraphElementClick} />
                    <E2ETraceGraphLegend stylesheet={cytoscapeStylesheet} />
                    <E2ETraceQuickActions />
                </div>
            </div>
        </div>
    );
};

export default E2ETraceMainDashboard;