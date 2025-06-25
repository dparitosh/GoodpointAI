import { useEffect } from 'react';
import { e2etraceCreateTableElementsFromGraph } from '../utils/e2etrace-graph';

/**
 * Custom hook to manage Cytoscape graph element selection and update associated table data.
 *
 * @param {React.RefObject} cyRef - Ref to the Cytoscape.js instance.
 * @param {object} graphData - The full graph data (nodes and edges).
 * @param {Function} setTableElements - State setter function for the table elements.
 */
export const e2etraceUseGraphSelection = (cyRef, graphData, setTableElements) => {
    useEffect(() => {
        const cy = cyRef.current;
        if (!cy) return;

        // Event listener for element selection
        const onSelect = (evt) => {
            const element = evt.target;
            console.log('Element selected:', element.id(), element.data());
            const selectedTableData = e2etraceCreateTableElementsFromGraph({
                nodes: element.isNode() ? [element.data()] : [],
                edges: element.isEdge() ? [element.data()] : []
            });
            setTableElements(selectedTableData);
        };

        // Event listener for element unselection
        const onUnselect = () => {
            // Reset table elements to all graph data when nothing is selected or multiple are unselected
            if (graphData && graphData.nodes && graphData.edges) {
                setTableElements(e2etraceCreateTableElementsFromGraph(graphData));
            }
        };

        cy.on('select', 'node, edge', onSelect);
        cy.on('unselect', 'node, edge', onUnselect);

        return () => {
            if (cy && !cy.isDestroyed()) {
                cy.off('select', 'node, edge', onSelect);
                cy.off('unselect', 'node, edge', onUnselect);
            }
        };
    }, [cyRef, graphData, setTableElements]);
};