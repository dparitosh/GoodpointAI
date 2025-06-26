import React, { useEffect, useState, useRef, useCallback } from 'react';
import { E2ETraceUIPanel } from '../../../components/e2etrace-ui-panel';
import { e2etraceFetchWithRetry } from '../../../api/e2etrace-api';
import { E2ETraceCytoscapeGraph } from '../e2etrace-cytoscape-graph';
import { cytoscapeStylesheet } from '../e2etrace-cytoscape-stylesheet';
import { e2etraceUseLayout } from '../../../contexts/e2etrace-layout-context';
import './e2etrace-nifi-flow-diagram.css';

// Helper to transform NiFi flow data to Cytoscape.js elements
const transformNiFiFlowToCytoscape = (flowData) => {
    const elements = [];
    const seenIds = new Set();

    const addNode = (component, type, parentId = null) => {
        if (!component || seenIds.has(component.id)) return;
        seenIds.add(component.id);

        elements.push({
            group: 'nodes',
            data: {
                id: component.id,
                label: component.name,
                state: component.state,
                type: type, // processor, input-port, output-port, process-group
                group: type, // For styling
                properties: component, // Store all NiFi properties
                parent: parentId,
                tooltip: `ID: ${component.id}\nName: ${component.name}\nType: ${type}\nState: ${component.state || 'N/A'}`
            },
            classes: `nifi-${type.toLowerCase().replace(/_/g, '-')}`
        });
    };

    const addConnection = (connection) => {
        if (!connection || seenIds.has(connection.id)) return;
        seenIds.add(connection.id);

        elements.push({
            group: 'edges',
            data: {
                id: connection.id,
                source: connection.source.id,
                target: connection.destination.id,
                label: connection.name || connection.selectedRelationships?.join(', ') || 'Flow',
                type: 'connection',
                properties: connection,
                tooltip: `ID: ${connection.id}\nSource: ${connection.source.name}\nDestination: ${connection.destination.name}\nQueued: ${connection.status?.queued || 'N/A'}`
            },
            classes: 'nifi-connection'
        });
    };

    if (flowData.processors) {
        flowData.processors.forEach(p => addNode(p.component, 'Processor'));
    }
    if (flowData.inputPorts) {
        flowData.inputPorts.forEach(p => addNode(p.component, 'InputPort'));
    }
    if (flowData.outputPorts) {
        flowData.outputPorts.forEach(p => addNode(p.component, 'OutputPort'));
    }
    if (flowData.processGroups) {
        flowData.processGroups.forEach(pg => {
            addNode(pg.component, 'ProcessGroup');
            // Recursively add components within nested process groups (if fetched)
            // Note: The /flow/{id} endpoint might not return full nested contents by default.
            // You might need to fetch nested process groups individually if deep nesting is required.
            if (pg.component.contents) {
                pg.component.contents.processors?.forEach(p => addNode(p.component, 'Processor', pg.component.id));
                pg.component.contents.inputPorts?.forEach(p => addNode(p.component, 'InputPort', pg.component.id));
                pg.component.contents.outputPorts?.forEach(p => addNode(p.component, 'OutputPort', pg.component.id));
                pg.component.contents.connections?.forEach(c => addConnection(c.component)); // Connections within nested groups
            }
        });
    }
    if (flowData.connections) {
        flowData.connections.forEach(c => addConnection(c.component));
    }

    return elements;
};

export function E2ETraceNiFiFlowDiagram({ processGroupId }) {
    const [flowData, setFlowData] = useState(null);
    const [isUpdatingProcessor, setIsUpdatingProcessor] = useState(false);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [showConfirmDialog, setShowConfirmDialog] = useState(false);
    const [processorToConfirm, setProcessorToConfirm] = useState(null); // { id, label, action }
    const cyRef = useRef(null); // Cytoscape instance ref
    const { layoutConfig } = e2etraceUseLayout();

    const fetchFlowData = useCallback(async () => {
        try {
            const response = await e2etraceFetchWithRetry(`/api/nifi/flow/${processGroupId}`);
            const data = await response.json();
            setFlowData(data.processGroupFlow);
            setError(null); // Clear previous errors on successful fetch
        } catch (e) {
            setError(e.message);
        }
    }, [processGroupId]);

    useEffect(() => {
        const initialFetch = async () => {
            setLoading(true);
            await fetchFlowData();
            setLoading(false);
        };
        initialFetch();
    }, [processGroupId, fetchFlowData]);

    // Effect to handle processor start/stop clicks
    useEffect(() => {
        const cy = cyRef.current;
        if (!cy) return;

        const handleProcessorTap = async (evt) => {
            const node = evt.target;
            const processorId = node.id();
            const processorState = node.data('state');

            if (processorState !== 'RUNNING' && processorState !== 'STOPPED' && processorState !== 'DISABLED') {
                console.log(`Processor ${processorId} is in state ${processorState}, no action taken.`);
                return;
            }

            const action = processorState === 'RUNNING' ? 'stop' : 'start';
            setProcessorToConfirm({ id: processorId, label: node.data('label'), action: action });
            setShowConfirmDialog(true);

            setIsUpdatingProcessor(true);
            setError(null);

            try {
                await e2etraceFetchWithRetry(`/api/nifi/processor/${processorId}/${action}`, { method: 'PUT' });
                await fetchFlowData(); // Refresh data after state change
            } catch (e) {
                setError(`Failed to ${action} processor: ${e.message}`);
            } finally {
                setIsUpdatingProcessor(false);
            }
        };

        cy.on('tap', 'node.nifi-processor', handleProcessorTap);

        // Cleanup function for the event listener
        return () => {
            if (cy && !cy.isDestroyed()) {
                cy.off('tap', 'node.nifi-processor', handleProcessorTap);
            }
        };
    }, [cyRef, fetchFlowData]);

    const handleConfirmAction = async () => {
        if (!processorToConfirm) return;

        setShowConfirmDialog(false);
        setIsUpdatingProcessor(true);
        setError(null);

        try {
            await e2etraceFetchWithRetry(`/api/nifi/processor/${processorToConfirm.id}/${processorToConfirm.action}`, { method: 'PUT' });
            await fetchFlowData(); // Refresh data after state change
        } catch (e) {
            setError(`Failed to ${processorToConfirm.action} processor: ${e.message}`);
        } finally {
            setIsUpdatingProcessor(false);
            setProcessorToConfirm(null);
        }
    };

    const handleCancelAction = () => {
        setShowConfirmDialog(false);
        setProcessorToConfirm(null);
        setIsUpdatingProcessor(false); // Reset updating state if action was cancelled
    };

    const cyElements = flowData ? transformNiFiFlowToCytoscape(flowData) : [];
    const showLoadingIndicator = loading || isUpdatingProcessor;

    return (
        <E2ETraceUIPanel className="e2etrace-nifi-flow-diagram-panel">
            <div className="e2etrace-nifi-flow-header">
                <h3>Flow Diagram</h3>
                <p>Click a processor to start/stop it.</p>
            </div>
            {showLoadingIndicator && (
                <div className="e2etrace-loading-overlay">
                    <div className="e2etrace-spinner"></div>
                    <p>{loading ? 'Loading flow diagram...' : 'Updating processor...'}</p>
                </div>
            )}
            {error && <p className="error">Error: {error}</p>}
            {!loading && !error && cyElements.length === 0 && <p>No flow data to display.</p>}
            {!loading && !error && cyElements.length > 0 && (
                <E2ETraceCytoscapeGraph
                    elements={cyElements}
                    stylesheet={cytoscapeStylesheet} // Re-use existing stylesheet, may need NiFi-specific styles
                    layout={layoutConfig}
                    cyRef={cyRef}
                />
            )}

            {showConfirmDialog && processorToConfirm && (
                <div className="e2etrace-confirm-dialog-overlay">
                    <div className="e2etrace-confirm-dialog-content">
                        <h4>Confirm Action</h4>
                        <p>Are you sure you want to <strong>{processorToConfirm.action}</strong> processor "<strong>{processorToConfirm.label}</strong>"?</p>
                        <div className="e2etrace-confirm-dialog-actions">
                            <button onClick={handleCancelAction} className="e2etrace-button-cancel">Cancel</button>
                            <button onClick={handleConfirmAction} className="e2etrace-button-confirm">Confirm</button>
                        </div>
                    </div>
                </div>
            )}
        </E2ETraceUIPanel>
    );
}