import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import CytoscapeComponent from 'react-cytoscapejs';
import { Link as RouterLink } from 'react-router-dom'; // Renamed to avoid conflict

// Cytoscape and extensions
import cytoscape from 'cytoscape';
import fcose from 'cytoscape-fcose';
import coseBilkent from 'cytoscape-cose-bilkent'; // Import cose-bilkent
import expandCollapse from 'cytoscape-expand-collapse';
import popper from 'cytoscape-popper'; // For Cytoscape to use Popper.js positioning

// Tooltip library from reference
import tippy from 'tippy.js';
import 'tippy.js/dist/tippy.css'; // Default tippy.js CSS
import { useResizablePanels } from './useResizablePanels'; // Import custom hook
import { DataTable } from './DataTable'; // Import DataTable component
import { ChatPanel } from './ChatPanel'; // Import ChatPanel component
import { useLayout } from './LayoutContext'; // Corrected import path
import './App.css';

// Explicitly register Cytoscape extensions after imports
cytoscape.use(fcose);
cytoscape.use(coseBilkent); // Register cose-bilkent
cytoscape.use(expandCollapse);
cytoscape.use(popper); // Register cytoscape-popper
console.log('[App React] Registered fcose, coseBilkent, expandCollapse, and popper extensions on the imported cytoscape library.');

// --- Helper functions adapted from reference ---
const nodeColorMap = {}; // To store assigned color class per category
let colorClassIndex = 0; // To cycle through predefined color classes
const PREDEFINED_COLOR_GROUPS = 4; // Number of --cy-color-group-N variables in App.css

function getNodeColorClass(nodeData) {
  const category = nodeData.group || (nodeData.properties?.labels?.[0] || 'DefaultGroup');
  if (!nodeColorMap[category]) {
    // Assign a class from a predefined set, cycling through them
    nodeColorMap[category] = `color-group-${(colorClassIndex % PREDEFINED_COLOR_GROUPS) + 1}`;
    colorClassIndex++;
  }
  return nodeColorMap[category];
}

const formatTooltipText = (props) => Object.entries(props || {}).map(([k, v], i) => `${i + 1}. <strong>${k}:</strong> ${JSON.stringify(v)}<br>`).join("");
// Helper function to transform raw graph data to Cytoscape.js element format
function transformDataForCytoscape(graphData) {
    const elements = [];
    const processedNodeIds = new Set(); // Keep track of node IDs that have been processed

    if (graphData && graphData.nodes) {
        console.log('[App React] transformDataForCytoscape: Processing nodes. Count:', graphData.nodes.length);
        let nodeCounter = 0;
        graphData.nodes.forEach(node => {
            elements.push({
                group: 'nodes',
                data: {
                    id: String(node.id), // Ensure this matches your backend NodeModel's ID field
                    label: node.label,
                    neo4j_labels: node.group ? [node.group] : (node.properties?.labels || ['DefaultLabel']),
                    group: node.group || (node.properties?.labels?.[0] || 'DefaultGroup'),
                    properties: node.properties || {}, // Ensure properties is an object
                    parent: node.properties && node.properties.parentId ? String(node.properties.parentId) : undefined,
                    tooltip: formatTooltipText(node.properties), // Add formatted tooltip data
                },
                // Add base class and dynamic color class
                classes: `${(node.group || (node.properties?.labels?.[0] || 'DefaultGroup')).toLowerCase().replace(/\s+/g, '-')} ${getNodeColorClass(node)}`
            });
            // console.log(`[App React] transformDataForCytoscape: Added node ${String(node.id)} to elements.`);
            processedNodeIds.add(String(node.id)); // Add processed node ID to our set
            nodeCounter++;
        });
        console.log(`[App React] transformDataForCytoscape: Finished processing ${nodeCounter} nodes. Total processedNodeIds: ${processedNodeIds.size}`);
    }
    if (graphData && graphData.edges) {
        console.log('[App React] transformDataForCytoscape: Processing edges. Count:', graphData.edges.length);
        graphData.edges.forEach((edge, index) => {
            // First, check if the edge object itself is valid
            if (!edge) {
                console.warn(`[App React] transformDataForCytoscape: Edge at index ${index} is null or undefined. Skipping.`);
                return; // Skip this iteration if edge is null/undefined
            }

            // Ensure source and target nodes are defined and not null/undefined
            if (edge.from == null || edge.to == null) { // Check for 'from' and 'to' as per logged data
                // Log more detailed information about the problematic edge
                console.warn(`[App React] transformDataForCytoscape: Skipping edge with ID '${edge.id || "Unknown ID"}' due to missing 'from' or 'to' fields. Edge data:`, edge);
                return; // Skip this edge if source or target ID is null or undefined
            }

            const sourceId = String(edge.from); // Use 'from'
            const targetId = String(edge.to);   // Use 'to'

            // Explicitly check if source and target nodes were processed and added to 'elements'
            if (!processedNodeIds.has(sourceId)) {
                console.warn(`[App React] transformDataForCytoscape: Skipping edge ID '${edge.id || "Unknown"}' (index ${index}). Reason: Source node ID '${sourceId}' NOT FOUND in processedNodeIds. Edge data:`, edge, 'Current processedNodeIds:', Array.from(processedNodeIds));
                return;
            }
            if (!processedNodeIds.has(targetId)) {
                console.warn(`[App React] transformDataForCytoscape: Skipping edge ID '${edge.id || "Unknown"}' (index ${index}). Reason: Target node ID '${targetId}' NOT FOUND in processedNodeIds. Edge data:`, edge, 'Current processedNodeIds:', Array.from(processedNodeIds));
                return;
            }

            elements.push({
                group: 'edges',
                data: {
                    id: String(edge.id),        // Ensure this matches your backend EdgeModel's ID field
                    source: sourceId,
                    target: targetId,
                    label: edge.label,
                    properties: edge.properties || {}, // Ensure properties is an object
                    tooltip: formatTooltipText(edge.properties), // Add formatted tooltip data
                },
                classes: (edge.properties && edge.properties.status === 'CRITICAL') ? 'critical' : ''
            });
        });
    } else {
        console.log('[App React] transformDataForCytoscape: No edges array found in graphData or it is empty.');
    }
    return elements;
}

// Helper function to create table elements from graph data
function createTableElementsFromGraph(graphData) {
  const combined = [];
  if (graphData && graphData.nodes) {
    graphData.nodes.forEach(node => combined.push({ ...node, id: String(node.id), elementType: 'Node' }));
  }
  if (graphData && graphData.edges) {
    graphData.edges.forEach(edge => combined.push({ ...edge, id: String(edge.id), elementType: 'Relationship' }));
  }
  return combined;
}

// --- Cytoscape Stylesheet ---
const cytoscapeStylesheet = [
    {
        selector: 'node',
        style: {
            // Background color will be primarily set by dynamic classes like .color-group-1
            // 'background-color': 'var(--cy-node-bg)', // Fallback if no group class matches
            'border-color': 'var(--cy-node-border)',
            'border-width': 1, // Reference uses 0.5px, 1px is a good compromise
            'shape': 'ellipse', // Default shape, can be overridden by specific classes
            'label': 'data(label)', // Ensure this is the correct data property for labels
            'width': 'label', // Auto-size based on label content.
            'height': 'label', // For this to work best with fcose,
                               // ensure fcose layout option 'nodeDimensionsIncludeLabels' is true
                               // in your LayoutContext.js.
            'padding': '10px', // Add padding around the label within the node
            'font-size': '12px',
            'font-family': 'Segoe UI, Arial, sans-serif', // Fluent UI typical font
            'text-valign': 'center',
            'text-halign': 'center',
            'color': 'var(--cy-node-text)', // Text color from theme
            'text-wrap': 'wrap', // Allow text to wrap within the auto-sized node
            'text-max-width': '80px', // From reference
            'text-outline-width': 0, // Reference doesn't use outline by default
            'text-outline-color': 'var(--cy-node-text-outline)', // Keep for theme consistency if outline is added
            // Shadow can be added if desired, but reference doesn't have it by default
            // 'shadow-blur': 5,
            // 'shadow-color': 'var(--cy-edge-color)',
            // 'shadow-offset-x': 2,
            // 'shadow-offset-y': 2,
            // 'shadow-opacity': 0.5
        }
    },    
    // Dynamic color group styling (add more if PREDEFINED_COLOR_GROUPS increases)
    { selector: 'node.color-group-1', style: { 'background-color': 'var(--cy-color-group-1-bg)', 'border-color': 'var(--cy-color-group-1-border)' } },
    { selector: 'node.color-group-2', style: { 'background-color': 'var(--cy-color-group-2-bg)', 'border-color': 'var(--cy-color-group-2-border)' } },
    { selector: 'node.color-group-3', style: { 'background-color': 'var(--cy-color-group-3-bg)', 'border-color': 'var(--cy-color-group-3-border)' } },
    { selector: 'node.color-group-4', style: { 'background-color': 'var(--cy-color-group-4-bg)', 'border-color': 'var(--cy-color-group-4-border)' } },
    // Specific types (can override or complement color groups if their styles are uncommented)
    {
        selector: 'node.supplier',
        style: {
            // 'shape': 'rectangle', // Example: give suppliers a different shape
            'background-color': 'var(--cy-supplier-bg)',
            'border-color': 'var(--cy-supplier-border)'
        }
    },
    {
        selector: 'node.manufacturer',
        style: {
            // 'shape': 'diamond', // Example: give manufacturers a different shape
            'background-color': 'var(--cy-manufacturer-bg)',
            'border-color': 'var(--cy-manufacturer-border)'
        }
    },
    {
        selector: 'edge',
        style: {
            'width': 1, // From reference
            'line-color': 'var(--cy-edge-color)', // Use theme variable
            'target-arrow-shape': 'triangle',
            'target-arrow-color': 'var(--cy-edge-color)', // Use theme variable
            'curve-style': 'unbundled-bezier', // From reference
            'label': 'data(label)',
            'font-size': '10px', // From reference
            'font-family': 'Segoe UI, Arial, sans-serif',
            'color': 'var(--cy-edge-text)', // Use theme variable
            'text-background-color': 'var(--cy-edge-text-bg)', 
            'text-background-opacity': 0.7, // Adjusted for better readability than reference's 0.1
            'text-background-padding': '2px',
            'text-rotation': 'autorotate',
            'arrow-scale': 1, // Default arrow size
            'z-index': 5, // Ensure edges are rendered below nodes by default
        }
    },
    {
        selector: 'edge.critical',
        style: {
            'line-color': 'var(--cy-critical-color)',
            'target-arrow-color': 'var(--cy-critical-color)',
            'width': 1.5, // Make critical edges slightly more prominent
        }
    },
    {
        selector: ':selected',
        style: {
            'border-width': 2, // Adjusted from current
            'border-color': 'var(--cy-selected-color)', // Use theme variable
            'background-color': 'var(--cy-selected-bg)', // Use theme variable
            'line-color': 'var(--cy-selected-color)', // Use theme variable
            'target-arrow-color': 'var(--cy-selected-color)', // Use theme variable
            'z-index': 10000, // Higher z-index for selected elements
            'shadow-opacity': 0.8, // Stronger shadow for selected elements
        }
    },
    {
        selector: ':parent', // Style for compound parent nodes
        style: {
            'background-color': 'var(--cy-parent-bg)',
            'border-color': 'var(--cy-parent-border)', // Use theme variable
            'border-width': 1, // Adjusted from current, reference uses 0.5
            'text-valign': 'top',
            'text-halign': 'center',
            'padding': '15px', // Ensure parent has enough padding for its children
            'font-weight': 'bold',
            'label': 'data(label)', // Ensure parent nodes also show labels
            'color': 'var(--cy-node-text)',
            'text-outline-color': 'var(--cy-node-text-outline)', // Use theme variable
            'text-outline-width': 0, // No outline for parent labels by default
            'shape': 'roundrectangle', // Common shape for parent nodes
        }
    }
];

// layoutOptions will now come from LayoutContext via layoutConfig

function App() {
  const [graphData, setGraphData] = useState({ nodes: [], edges: [] });
  const [loading, setLoading] = useState(true);
  const [loadingError, setLoadingError] = useState(null);
  const [chatMessages, setChatMessages] = useState([]);
  const [chatInputValue, setChatInputValue] = useState('');
  const [isChatSending, setIsChatSending] = useState(false);
  const [tableElements, setTableElements] = useState([]);
  const { layoutConfig } = useLayout(); // Consume layout config from context

  const cyRef = useRef(null);
  const tippyInstancesRef = useRef({}); // To store tippy instances
  // Refs for resizable panels
  const graphContainerRef = useRef(null);
  const mainContentAreaRef = useRef(null);
  const mainResizerRef = useRef(null);
  const rightPanelRef = useRef(null);

  useResizablePanels(graphContainerRef, rightPanelRef, mainResizerRef, mainContentAreaRef, cyRef);

  // Note on layout: The active layout (e.g., fcose, cose-bilkent) and its specific options
  // are determined by the `layoutConfig` provided by `LayoutContext` (via `useLayout()`).
  // To change to 'fcose' or adjust its parameters (like idealEdgeLength, nodeSeparation,
  // nodeDimensionsIncludeLabels), modify the configuration in your `LayoutContext.js` file.
  useEffect(() => {

    async function fetchInitialData() {
      console.log('[App React] fetchInitialData: Setting loading to true.');
      setLoading(true);
      setLoadingError(null);
      try {
        console.log('[App React] fetchInitialData: Attempting to fetch /api/graph');
        const response = await fetch('/api/graph');
        console.log('[App React] fetchInitialData: Received response status:', response.status);

        if (!response.ok) {
          console.log('[App React] fetchInitialData: Response not OK. Status:', response.status);
          const errorData = await response.json().catch(() => ({ message: `HTTP error! status: ${response.status}` }));
          console.log('[App React] fetchInitialData: Parsed error data:', errorData);
          throw new Error(errorData.message || `HTTP error! status: ${response.status}`);
        }
        const data = await response.json();
        console.log('[App React] fetchInitialData: Successfully parsed JSON data. Proceeding to set state.'); // Log before processing potentially large data
        setGraphData(data);
        setTableElements(createTableElementsFromGraph(data));
        console.log('[App React] fetchInitialData: Graph and table elements set.');
      } catch (error) {
        console.error('[App React] fetchInitialData: Error caught:', error);
        setLoadingError(`Error loading graph: ${error.message}. Check console for details.`);
      } finally {
        console.log('[App React] fetchInitialData: In finally block, setting loading to false.');
        setLoading(false);
      }
    }
    fetchInitialData();
  }, []);

  const transformedElements = useMemo(() => transformDataForCytoscape(graphData), [graphData]);

  // --- Cytoscape Effect Setup Functions ---
  // (These functions can be defined here or moved to a separate utility file if they grow)
  const setupTippyTooltips = useCallback((cyInstance, currentTransformedElements) => {
    if (!cyInstance || currentTransformedElements.length === 0) return () => {};

    // Destroy old tippy instances before creating new ones
    Object.values(tippyInstancesRef.current).forEach((t) => t.destroy());
    tippyInstancesRef.current = {};

    currentTransformedElements.forEach((elData) => { // Iterate over transformed data to get tooltip content
      const cyEl = cyInstance.getElementById(elData.data.id);
      // Ensure element exists, has popperRef, and has tooltip data
      if (cyEl.length === 0 || typeof cyEl.popperRef !== 'function' || !elData.data.tooltip) return;

      const ref = cyEl.popperRef(); // Get popperRef from Cytoscape element
      if (!ref) return; // Popper ref might not be available immediately or for all elements

      const dummyDomEle = document.createElement('div'); // Tippy needs a DOM element to attach to

      const tip = tippy(dummyDomEle, { // Initialize tippy
        getReferenceClientRect: ref.getBoundingClientRect, // Use popperRef's BoundingClientRect for positioning
        content: () => { // Content can be a function returning an HTML string or element
          const contentDiv = document.createElement('div');
          contentDiv.innerHTML = elData.data.tooltip; // Use pre-formatted tooltip from element data
          return contentDiv;
        },
        trigger: 'manual', // We'll show/hide manually based on Cytoscape events
        arrow: true,
        placement: 'bottom',
        hideOnClick: false, // Keep tooltip open on click if needed
        allowHTML: true,
        interactive: true, // Allows interaction with tooltip content
        appendTo: document.body, // Append to body to avoid z-index issues with other UI elements
      });

      tippyInstancesRef.current[elData.data.id] = tip;

      cyEl.on('mouseover', () => tip.show());
      cyEl.on('mouseout', () => tip.hide());
    });

    return () => {
      // Cleanup: destroy all tippy instances when effect re-runs or component unmounts
      Object.values(tippyInstancesRef.current).forEach((t) => t.destroy());
      tippyInstancesRef.current = {};
      if (cyInstance && cyInstance.elements) { // Check if cyInstance and elements method exist
        cyInstance.elements().off('mouseover mouseout'); // Remove listeners to prevent memory leaks
      }
    };
  }, []); // No dependencies that change frequently, so this runs once on mount and cleans up on unmount

  // Cytoscape Instance Effects (Tooltips, Expand/Collapse)
  useEffect(() => {
    const cy = cyRef.current;

    // Check if the Cytoscape instance is available and has elements
    // Tooltip and expand/collapse logic should only run if cy is initialized and has elements
    if (!cy || transformedElements.length === 0) {
      // console.log('[App React] Cytoscape instance not ready or no elements to process for effects.'); // Suppress this log as it's expected on initial render
      return;
    }
    console.log('[App React] Setting up Cytoscape effects...');

    const cleanupTooltips = setupTippyTooltips(cy, transformedElements); // Use the new tippy.js setup
    // expandCollapse and neighborHighlighting setup removed

    return () => {
      console.log('[App React] Cleaning up all Cytoscape effects.');
      cleanupTooltips();
    };
  // Ensure all dependencies for useCallback hooks are stable or included if they change    
  }, [transformedElements, layoutConfig, setupTippyTooltips]);

  // Chat Logic
  const handleSendChatMessage = async () => {
    if (!chatInputValue.trim()) return;
    const userMessage = chatInputValue.trim();
    setChatMessages(prev => [...prev, { sender: 'You', text: userMessage }]);
    setChatInputValue('');
    setIsChatSending(true);

    try {
      const response = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: userMessage })
      });
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ message: `Chat API error: ${response.status}` }));
        throw new Error(errorData.message || `Chat API error: ${response.status}`);
      }
      const llmResponse = await response.json();
      console.log('[App React] Full response from chat API:', llmResponse); // Log the full response

      setChatMessages(prev => [...prev, { sender: 'AI', text: llmResponse.textResponse || "Received a response." }]);

      if (llmResponse.graphData && llmResponse.graphData.nodes && llmResponse.graphData.edges) {
        console.log("[App React] Received new graph data from chat:", llmResponse.graphData);
        setGraphData(llmResponse.graphData); // This will trigger transformedElements re-computation
        setTableElements(createTableElementsFromGraph(llmResponse.graphData));
      } else if (llmResponse.tableData) {
        console.log("[App React] Received new table data from chat:", llmResponse.tableData);
        // Assuming llmResponse.tableData is an array of objects for the table
        // This might need adjustment based on the actual structure of tableData
        // Check if tableData is an array, otherwise try to extract nodes/edges
        if (Array.isArray(llmResponse.tableData) && llmResponse.tableData.length > 0) {
          setTableElements(llmResponse.tableData);
        } else {
          // If tableData is expected to be graph-like, transform it
          setTableElements(createTableElementsFromGraph(llmResponse.tableData));
        }
      }
    } catch (error) {
      console.error('Error sending message or processing LLM response:', error);
      setChatMessages(prev => [...prev, { sender: 'System', text: `Error: ${error.message}` }]);
    } finally {
      setIsChatSending(false);
    }
  };

  // Effect to fit the graph whenever elements change or layout runs
  const initialFitDone = useRef(false); // Ref to track if the first fit has occurred

  useEffect(() => {
    const cy = cyRef.current;
    if (cy && transformedElements.length > 0) {
      // Use a slightly longer delay for the very first fit, 0ms for subsequent fits
      const delay = initialFitDone.current ? 0 : 100; // e.g., 100ms for the first fit

      const timeoutId = setTimeout(() => {
        if (cyRef.current) { // Re-check in case component unmounted during timeout
          cyRef.current.resize();
          cyRef.current.fit(cyRef.current.elements(), layoutConfig.padding); // Use padding from context
          console.log(`[App React] Graph fit executed (delay: ${delay}ms).`);
          if (!initialFitDone.current) {
            initialFitDone.current = true; // Mark that the initial fit has been done
          }
        }
      }, delay);
      return () => clearTimeout(timeoutId); // Cleanup timeout on unmount or re-run
    }
  }, [transformedElements, cyRef, layoutConfig]); // Depend on layoutConfig from context
  // Effect to handle window resize
  useEffect(() => {
    const cy = cyRef.current;
    if (!cy) return;

    const handleResize = () => {
      cy.resize();
      // Optionally, re-fit after resize, or let user pan/zoom.
      // If you always want it to fit and there are elements:
      if (transformedElements.length > 0) {
        cy.fit(cy.elements(), layoutConfig.padding); // Use padding from context
      }
    };

    window.addEventListener('resize', handleResize);
    return () => {
      window.removeEventListener('resize', handleResize);
    };
  }, [cyRef, transformedElements, layoutConfig]); // Depend on layoutConfig from context

  const handleRefreshLayout = useCallback(() => {
    const cy = cyRef.current;
    if (!cy || transformedElements.length === 0) {
      console.log('[App React] Cannot refresh layout: Cytoscape instance not ready or no elements.');
      return;
    }

    console.log('[App React] Refreshing layout with config from context:', layoutConfig);
    const layout = cy.layout(layoutConfig); // Use layout config from context

    // Listen for the layoutstop event to fit the graph after the layout is done
    layout.one('layoutstop', () => {
      console.log('[App React] Layout stopped, fitting graph.');
      if (cyRef.current) { // Re-check cy instance as this is an async callback
        cyRef.current.fit(cyRef.current.elements(), layoutConfig.padding);
      }
    });
    layout.run(); // Run the layout
  }, [cyRef, transformedElements, layoutConfig]); // Depend on layoutConfig from context
  return (
    <div className="dashboard-container">
      <header>
        <h1>E2E Trace App (Neoboi)</h1>
        <nav className="app-nav">
          <RouterLink to="/layout-settings">Configure Layout</RouterLink>
          <RouterLink to="/analytics">Analytics</RouterLink> {/* Add link to analytics */}
        </nav>
      </header>
      <div className="main-content-area" ref={mainContentAreaRef}>
        <div id="graph-container" ref={graphContainerRef} className="graph-panel">
          <div className="panel-header">
            <h3>Graph Visualization</h3>
            {transformedElements.length > 0 && ( // Only show button if there are elements
              <button onClick={handleRefreshLayout} className="panel-header-button">
                Refresh Layout
              </button>
            )}
          </div>
          <div className="cytoscape-wrapper"> {/* Wrapper for Cytoscape and messages */}
            {loading && <div className="loading-message">Loading graph data...</div>}
            {loadingError && <div className="error-message">{loadingError}</div>}
            {!loading && !loadingError && transformedElements.length > 0 && (
              <CytoscapeComponent
                elements={transformedElements}
                style={{ width: '100%', height: '100%' }} // Fills the cytoscape-wrapper
                stylesheet={cytoscapeStylesheet}
                cy={instance => { cyRef.current = instance; }} // Changed 'cy' to 'instance' for clarity
                layout={layoutConfig} // Use layout config from context
                cytoscape={cytoscape}
              />
            )}
            {!loading && transformedElements.length === 0 && !loadingError && (
              <div className="info-message">No graph data to display.</div>
            )}
          </div>
        </div>
        <div id="main-resizer-v" ref={mainResizerRef} className="resizer-v"></div>
        <div ref={rightPanelRef} className="chat-panel-container"> {/* Container for ChatPanel, assign ref here */}
            <ChatPanel
              chatMessages={chatMessages}
              chatInputValue={chatInputValue}
              onChatInputChange={(e) => setChatInputValue(e.target.value)}
              onSendMessage={handleSendChatMessage}
              isChatSending={isChatSending}
            />
        </div>
      </div>
      {/* Data table is now a separate component */}
      <DataTable tableElements={tableElements} />
    </div>
  )
}

export default App
