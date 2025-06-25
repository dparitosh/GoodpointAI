import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import CytoscapeComponent from 'react-cytoscapejs';
import cytoscape from 'cytoscape';
import fcose from 'cytoscape-fcose';
import popper from 'cytoscape-popper'; // For Cytoscape to use Popper.js positioning
import { Tooltip as ReactTippyTooltip } from 'react-tippy';
import 'react-tippy/dist/tippy.css'; // Default react-tippy CSS
import ReactDOM from 'react-dom/client'; // Needed for createRoot for tooltips

// Register Cytoscape extensions
cytoscape.use(fcose);
// popper.js is often used implicitly by extensions like react-tippy integration
// cytoscape.use(popper); // No explicit use needed, it extends prototype

// --- Helper function to transform raw graph data to Cytoscape.js element format ---
// This function can remain largely the same.
function transformDataForCytoscape(graphData) {
    const elements = [];
    if (graphData && graphData.nodes) {
        graphData.nodes.forEach(node => {
            elements.push({
                group: 'nodes',
                data: {
                    id: String(node.id),
                    label: node.label,
                    neo4j_labels: node.labels || (node.group ? [node.group] : ['Unknown']),
                    group: node.group || 'Unknown',
                    properties: node.properties,
                    parent: node.properties && node.properties.parentId ? String(node.properties.parentId) : undefined,
                },
                classes: node.group ? node.group.toLowerCase().replace(/\s+/g, '-') : 'unknown'
            });
        });
    }
    if (graphData && graphData.edges) {
        graphData.edges.forEach(edge => {
            elements.push({
                group: 'edges',
                data: {
                    id: String(edge.id),
                    source: String(edge.from),
                    target: String(edge.to),
                    label: edge.label,
                    properties: edge.properties,
                },
                classes: (edge.properties && edge.properties.status === 'CRITICAL') ? 'critical' : ''
            });
        });
    }
    return elements;
}

// --- Cytoscape Stylesheet (can be a constant) ---
const cytoscapeStylesheet = [
    {
        selector: 'node',
        style: {
            'background-color': 'var(--ndl-color-palette-neutral-bg-strong, #E0E5E9)', // NDL neutral
            'border-color': 'var(--ndl-color-palette-neutral-border-default, #A6B1BB)',
            'border-width': 1.5,
            'label': 'data(label)',        // Display the 'label' data property
            'width': 40,
            'height': 40,
            'font-size': 'var(--ndl-font-size-70, 12px)',
            'font-family': 'var(--ndl-font-family-sans, Arial, sans-serif)',
            'text-valign': 'center',
            'text-halign': 'center',
            'color': 'var(--ndl-color-text-on-neutral, #212529)',
            'text-wrap': 'wrap',
            'text-max-width': '90px',
            'text-outline-width': 1,
            'text-outline-color': 'var(--ndl-color-palette-neutral-bg-strong, #E0E5E9)',
        }
    },
    {
        selector: 'node.supplier', // Style for nodes with class 'supplier'
        style: {
            'background-color': '#FFF9C4',
            'border-color': '#FFC107'
        }
    },
    {
        selector: 'node.manufacturer', // Style for nodes with class 'manufacturer'
        style: {
            'background-color': '#C8E6C9',
            'border-color': '#4CAF50'
        }
    },
    {
        selector: 'edge',
        style: {
            'width': 1.5,
            'line-color': 'var(--ndl-color-palette-neutral-border-default, #A6B1BB)',
            'target-arrow-shape': 'triangle', // Arrowhead shape
            'target-arrow-color': 'var(--ndl-color-palette-neutral-border-default, #A6B1BB)',
            'curve-style': 'unbundled-bezier', // Often good with fcose
            'label': 'data(label)',         // Display edge label (relationship type)
            'font-size': 'var(--ndl-font-size-60, 10px)',
            'font-family': 'var(--ndl-font-family-sans, Arial, sans-serif)',
            'color': 'var(--ndl-color-text-default, #333333)',
            'text-background-color': 'var(--ndl-color-bg-canvas, #fff)',
            'text-background-opacity': 1,
            'text-background-padding': '2px',
            'text-background-shape': 'roundrectangle',
            'text-rotation': 'autorotate'   // Rotate edge labels with the edge
        }
    },
    {
        selector: 'edge.critical',
        style: {
            'line-color': 'red',
            'target-arrow-color': 'red'
        }
    },
    {
        selector: ':selected', // Style for selected elements
        style: {
            'border-width': 3,
            'border-color': 'var(--ndl-color-palette-primary-border-strong, #005EA8)',
            'line-color': 'var(--ndl-color-palette-primary-border-strong, #005EA8)',
            'target-arrow-color': 'var(--ndl-color-palette-primary-border-strong, #005EA8)',
            'background-color': 'var(--ndl-color-palette-primary-bg-hover, #CCE5FF)',
            'z-index': 9999
        }
    }
];

// --- ECharts Placeholder Component (for Data Quality Dashboard) ---
// In a real app, this would be a separate file: e2etrace-data-quality-dashboard.jsx
const DataQualityDashboard = ({ data }) => {
    // This component would use ECharts to render various charts based on 'data'
    // For now, it's a placeholder.
    if (!data || data.length === 0) {
        return <div className="data-quality-placeholder">No data quality metrics to display.</div>;
    }
    return (
        <div className="data-quality-dashboard">
            <h3>Data Quality Metrics (ECharts Placeholder)</h3>
            {/* Render ECharts components here, e.g., <EChartsReact option={chartOption} /> */}
            <pre>{JSON.stringify(data, null, 2)}</pre>
        </div>
    );
};

// --- Chat Panel Component (for Interactive Chat) ---
// In a real app, this would be a separate file: e2etrace-chat-panel.jsx
const ChatPanel = ({ messages, onSendMessage, isSending, chatInputValue, setChatInputValue }) => {
    const chatMessagesEndRef = useRef(null);

    useEffect(() => {
        chatMessagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [messages]);

    const handleKeyPress = (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            onSendMessage();
        }
    };

    return (
        <div id="interactive-chat-panel" className="chat-panel">
            <h2>Interactive Chat</h2>
            <div id="chat-messages">
                {messages.map((msg, index) => (
                    <div key={index} className={`chat-message ${msg.sender === 'You' ? 'user-message' : 'ai-message'}`}>
                        <strong>{msg.sender}:</strong> {msg.text}
                    </div>
                ))}
                <div ref={chatMessagesEndRef} />
            </div>
            <div className="chat-input-container">
                <input
                    type="text"
                    id="chat-input"
                    placeholder="Ask about the graph or enter a Cypher query..."
                    value={chatInputValue}
                    onChange={(e) => setChatInputValue(e.target.value)}
                    onKeyPress={handleKeyPress}
                    disabled={isSending}
                />
                <button id="send-chat-button" onClick={onSendMessage} disabled={isSending}>
                    {isSending ? 'Sending...' : 'Send'}
                </button>
            </div>
        </div>
    );
};


// --- Main React Component: E2ETraceMainDashboard ---
const E2ETraceMainDashboard = () => {
    const [graphData, setGraphData] = useState({ nodes: [], edges: [] });
    const [loading, setLoading] = useState(true);
    const [loadingError, setLoadingError] = useState(null);
    const [chatMessages, setChatMessages] = useState([]);
    const [chatInputValue, setChatInputValue] = useState('');
    const [isChatSending, setIsChatSending] = useState(false);
    const [tableElements, setTableElements] = useState([]); // For the data-panel tables
    const [dashboardMetrics, setDashboardMetrics] = useState([]); // For ECharts data

    // Refs for resizable panels
    const graphContainerRef = useRef(null);
    const chatPanelsContainerRef = useRef(null);
    const mainResizerRef = useRef(null);
    const mainContentAreaRef = useRef(null);

    // Cytoscape.js instance ref
    const cyRef = useRef(null);

    // --- Fetch Initial Graph Data ---
    useEffect(() => {
        async function fetchInitialData() {
            setLoading(true);
            setLoadingError(null);
            try {
                const response = await fetch('/api/graph');
                if (!response.ok) {
                    const errorData = await response.json();
                    throw new Error(errorData.message || `HTTP error! status: ${response.status}`);
                }
                const data = await response.json();
                console.log('[E2ETraceMainDashboard] Initial graph data fetched:', data);
                setGraphData(data);
                // Populate initial table data (e.g., all nodes and edges)
                const combined = [];
                if (data.nodes) data.nodes.forEach(node => combined.push({ ...node, elementType: 'Node' }));
                if (data.edges) data.edges.forEach(edge => combined.push({ ...edge, elementType: 'Relationship' }));
                setTableElements(combined);
                // Placeholder for initial dashboard metrics
                setDashboardMetrics([{ name: 'Total Nodes', value: data.nodes.length }, { name: 'Total Edges', value: data.edges.length }]);

            } catch (error) {
                console.error('Failed to fetch initial graph data:', error);
                setLoadingError(`Error loading graph: ${error.message}. Check console for details.`);
            } finally {
                setLoading(false);
            }
        }
        fetchInitialData();
    }, []);

    // --- Cytoscape Instance Setup and Event Listeners ---
    const cyElements = useMemo(() => transformDataForCytoscape(graphData), [graphData]);

    const cyLayout = useMemo(() => ({
        name: 'fcose',
        animate: true,
        animationDuration: 500,
        fit: true,
        padding: 30,
        quality: 'default',
        nodeRepulsion: () => 4500,
        edgeElasticity: () => 0.45,
        gravity: 0.25,
        numIter: 2500,
        tile: true,
        nestingFactor: 0.9,
        nodeDimensionsIncludeLabels: true
    }), []);

    useEffect(() => {
        const cy = cyRef.current;
        if (!cy) return;

        console.log('[E2ETraceMainDashboard] Cytoscape instance available, setting up extensions and listeners.');

        // Cleanup previous tooltips
        if (cy.scratch('_reactTippyRoots')) {
            cy.scratch('_reactTippyRoots').forEach(root => root.unmount());
        }
        const reactTippyRoots = [];

        cy.elements().forEach(ele => {
            // Ensure popperRef is available and clean up previous popper elements
            const popperRefElement = ele.popperRef();
            if (popperRefElement) {
                while (popperRefElement.firstChild) {
                    popperRefElement.removeChild(popperRefElement.firstChild);
                }
                const tooltipRoot = ReactDOM.createRoot(popperRefElement);
                reactTippyRoots.push(tooltipRoot);

                let tooltipContentStr = '';
                if (ele.isNode()) {
                    tooltipContentStr = `<b>ID:</b> ${ele.id()}<br/><b>Label:</b> ${ele.data('label') || 'N/A'}<br/><b>Group:</b> ${ele.data('group') || 'N/A'}`;
                    const neo4jLabels = ele.data('neo4j_labels');
                    if (neo4jLabels && neo4jLabels.length > 0) {
                        tooltipContentStr += `<br/><b>Neo4j Labels:</b> ${neo4jLabels.join(', ')}`;
                    }
                } else if (ele.isEdge()) {
                    tooltipContentStr = `<b>ID:</b> ${ele.id()}<br/><b>Type:</b> ${ele.data('label') || 'N/A'}<br/><b>Source:</b> ${ele.source().id()}<br/><b>Target:</b> ${ele.target().id()}`;
                }
                const props = ele.data('properties');
                if (props && Object.keys(props).length > 0) {
                    tooltipContentStr += '<br/><b>Properties:</b><ul style="margin:0;padding-left:15px;list-style-type:disc;">';
                    for (const key_prop in props) {
                        tooltipContentStr += `<li><small><strong>${key_prop}:</strong> ${JSON.stringify(props[key_prop])}</small></li>`;
                    }
                    tooltipContentStr += '</ul>';
                }

                const renderTooltip = (isVisible) => {
                    tooltipRoot.render(
                        <ReactTippyTooltip
                            html={<div dangerouslySetInnerHTML={{ __html: tooltipContentStr }} />}
                            open={isVisible}
                            position="bottom" trigger="manual" interactive={true} arrow={true} theme="light"
                        >
                            <span style={{ display: 'inline-block' }} />
                        </ReactTippyTooltip>
                    );
                };

                ele.on('mouseover', () => renderTooltip(true));
                ele.on('mouseout', () => renderTooltip(false));
            }
        });
        cy.scratch('_reactTippyRoots', reactTippyRoots);

        // Expand/Collapse logic (if using cytoscape-expand-collapse)
        // Note: The original app.js had a check for typeof cy.expandCollapse === 'function'
        // You would need to ensure this extension is properly loaded and initialized.
        // For simplicity, I'm omitting the expandCollapse API initialization here,
        // but you would re-add it if you have the extension.

        // Event listener for element selection
        cy.on('select', 'node, edge', (evt) => {
            const element = evt.target;
            console.log('Element selected:', element.id(), element.data());
            // You might want to update a state here to show properties in a dedicated panel
            // setSelectedGraphElement(element.data());
        });

        cy.on('unselect', 'node, edge', () => {
            // setSelectedGraphElement(null);
        });

        // Fit graph to view after initial load or data change
        cy.fit();

        return () => { // Cleanup function
            console.log('[E2ETraceMainDashboard] Cleaning up Cytoscape extensions and listeners.');
            if (cy.scratch('_reactTippyRoots')) {
                cy.scratch('_reactTippyRoots').forEach(root => root.unmount());
                cy.scratch('_reactTippyRoots', null);
            }
            cy.elements().forEach(ele => {
                ele.off('mouseover');
                ele.off('mouseout');
            });
            cy.off('select', 'node, edge');
            cy.off('unselect', 'node, edge');
            // If expandCollapseApi had a destroy method, it would be called here.
        };
    }, [cyRef, cyElements]); // Rerun when cy instance is (re)created or cyElements changes

    // --- Resizable Panels Logic (React-idiomatic) ---
    useEffect(() => {
        const resizer = mainResizerRef.current;
        const leftPanel = graphContainerRef.current;
        const rightPanel = chatPanelsContainerRef.current;
        const mainContentArea = mainContentAreaRef.current;
        const cy = cyRef.current;

        if (!resizer || !leftPanel || !rightPanel || !mainContentArea) {
            console.warn('Resizable panel elements not found. Ensure refs are correctly attached.');
            return;
        }

        let isResizing = false;

        const onMouseMove = (e) => {
            if (!isResizing) return;

            const dx = e.clientX - resizer.startX;
            let newLeftWidth = resizer.initialLeftWidth + dx;
            let newRightWidth = resizer.initialRightWidth - dx;

            const minPanelWidth = 150; // Minimum width in pixels for each panel
            const resizerWidth = resizer.offsetWidth;
            const containerWidth = mainContentArea.offsetWidth - resizerWidth;

            // Enforce minimum widths
            if (newLeftWidth < minPanelWidth) {
                newLeftWidth = minPanelWidth;
                newRightWidth = containerWidth - newLeftWidth;
            } else if (newRightWidth < minPanelWidth) {
                newRightWidth = minPanelWidth;
                newLeftWidth = containerWidth - newRightWidth;
            }

            leftPanel.style.flex = `0 0 ${newLeftWidth}px`;
            rightPanel.style.flex = `0 0 ${newRightWidth}px`;

            if (cy && typeof cy.resize === 'function') {
                cy.resize(); // Notify Cytoscape to adjust its layout
            }
        };

        const onMouseUp = () => {
            isResizing = false;
            document.removeEventListener('mousemove', onMouseMove);
            document.removeEventListener('mouseup', onMouseUp);

            document.body.style.userSelect = '';
            document.body.style.pointerEvents = '';

            if (cy && typeof cy.resize === 'function') {
                cy.resize(); // Final resize call
            }
        };

        const onMouseDown = (e) => {
            isResizing = true;
            resizer.startX = e.clientX;
            resizer.initialLeftWidth = leftPanel.offsetWidth;
            resizer.initialRightWidth = rightPanel.offsetWidth;

            document.body.style.userSelect = 'none';
            document.body.style.pointerEvents = 'none';

            document.addEventListener('mousemove', onMouseMove);
            document.addEventListener('mouseup', onMouseUp);
        };

        resizer.addEventListener('mousedown', onMouseDown);

        return () => { // Cleanup
            resizer.removeEventListener('mousedown', onMouseDown);
            document.removeEventListener('mousemove', onMouseMove);
            document.removeEventListener('mouseup', onMouseUp);
        };
    }, [cyRef]); // Dependency on cyRef to ensure resize is called correctly

    // --- Chat Logic ---
    const handleSendChatMessage = useCallback(async () => {
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
                const errorData = await response.json();
                throw new Error(errorData.message || `Chat API error: ${response.status}`);
            }
            const llmResponse = await response.json();

            setChatMessages(prev => [...prev, { sender: 'AI', text: llmResponse.textResponse || "Received a response." }]);

            if (llmResponse.graphData && llmResponse.graphData.nodes && llmResponse.graphData.edges) {
                console.log("[E2ETraceMainDashboard] Received new graph data from chat:", llmResponse.graphData);
                setGraphData(llmResponse.graphData); // Update React state with new graph data
            }
            if (llmResponse.tableData) {
                console.log("[E2ETraceMainDashboard] Received new table data from chat:", llmResponse.tableData);
                setTableElements(llmResponse.tableData); // Update React state with new table data
            }
            if (llmResponse.dashboardMetrics) {
                console.log("[E2ETraceMainDashboard] Received new dashboard metrics from chat:", llmResponse.dashboardMetrics);
                setDashboardMetrics(llmResponse.dashboardMetrics); // Update React state with new dashboard metrics
            }

        } catch (error) {
            console.error('Error sending message or processing LLM response:', error);
            setChatMessages(prev => [...prev, { sender: 'System', text: `Error: ${error.message}` }]);
        } finally {
            setIsChatSending(false);
        }
    }, [chatInputValue]);

    // --- Render Data Tables (simplified for this example) ---
    const renderDataTables = () => {
        if (tableElements.length === 0) {
            return <p>No data to display in tables.</p>;
        }
        // In a real app, this would be a more sophisticated table component
        return (
            <div className="data-table-container">
                <h3>Elements Data</h3>
                <table>
                    <thead>
                        <tr>
                            <th>ID</th>
                            <th>Type</th>
                            <th>Label</th>
                            <th>Properties</th>
                        </tr>
                    </thead>
                    <tbody>
                        {tableElements.map((item, index) => (
                            <tr key={item.id || index}>
                                <td>{item.id}</td>
                                <td>{item.elementType}</td>
                                <td>{item.label || item.type}</td>
                                <td>{JSON.stringify(item.properties)}</td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        );
    };

    return (
        <div className="dashboard-container">
            <div className="main-content-area" ref={mainContentAreaRef}>
                <div id="graph-container" ref={graphContainerRef}>
                    {loading && <div id="loading">Loading graph data...</div>}
                    {loadingError && <div id="loading-error" style={{ color: 'red' }}>{loadingError}</div>}
                    {!loading && !loadingError && cyElements.length === 0 && (
                        <div id="no-graph-data">No graph data to display.</div>
                    )}
                    {!loading && !loadingError && cyElements.length > 0 && (
                        <CytoscapeComponent
                            cy={(cy) => { cyRef.current = cy; }}
                            elements={cyElements}
                            stylesheet={cytoscapeStylesheet}
                            layout={cyLayout}
                            style={{ width: '100%', height: '100%' }}
                        />
                    )}
                </div>
                <div className="resizer" id="main-resizer-v" ref={mainResizerRef}></div>
                <div className="chat-panels-container" ref={chatPanelsContainerRef}>
                    <ChatPanel
                        messages={chatMessages}
                        onSendMessage={handleSendChatMessage}
                        isSending={isChatSending}
                        chatInputValue={chatInputValue}
                        setChatInputValue={setChatInputValue}
                    />
                </div>
            </div>
            <div id="data-panel">
                <h2>Data Tables</h2>
                <div id="data-tables-container">
                    {renderDataTables()}
                    <DataQualityDashboard data={dashboardMetrics} />
                </div>
            </div>
        </div>
    );
};

export default E2ETraceMainDashboard;