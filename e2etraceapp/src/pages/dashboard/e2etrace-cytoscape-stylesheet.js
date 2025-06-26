export const cytoscapeStylesheet = [
    {
        selector: 'node',
        style: {
            'background-color': 'data(properties.color)', // Dynamic color from node properties
            'label': 'data(label)',
            'text-valign': 'center',
            'text-halign': 'center',
            'font-size': '11px', // Increased for readability
            'color': 'var(--cy-node-text-color, var(--text-color))', // Use a specific variable or fallback
            'text-outline-width': 2, // Thicker for better contrast
            'text-outline-color': 'var(--background-color)',
            'width': 'mapData(properties.size, 0, 100, 20, 80)',
            'height': 'mapData(properties.size, 0, 100, 20, 80)',
            'border-width': 2, // Slightly thicker border
            'border-color': 'var(--border-color)',
            'shape': 'ellipse',
            'z-index': 10,
            'opacity': 1,
            'transition-property': 'background-color, line-color, target-arrow-color, width, height, border-color, shadow-blur, shadow-opacity',
            'transition-duration': '0.2s',
            'transition-timing-function': 'ease-in-out',
            'text-wrap': 'wrap',
            'text-max-width': '90px',
        }
    },
    {
        selector: 'node:hover',
        style: {
            'shadow-blur': 15,
            'shadow-color': 'var(--cy-selected-color)',
            'shadow-opacity': 0.6,
            'border-color': 'var(--cy-selected-color)',
        }
    },
    {
        selector: 'node[group="DataQualityIssue"]',
        style: {
            'background-color': 'var(--cy-critical-color)',
            'shape': 'diamond',
            'border-width': 2,
            'border-color': 'darkred',
            'width': 40,
            'height': 40,
            'font-size': '12px',
            'color': 'white',
            'text-outline-color': 'darkred',
        }
    },
    {
        selector: 'node[group="Teamcenter"]',
        style: {
            'shape': 'round-rectangle',
            'background-color': '#4D8DDA', // Blue
            'color': 'var(--cy-node-text-on-dark-bg, white)',
            'text-outline-color': '#265282',
        }
    },
    {
        selector: 'node[group="CustomDB"]',
        style: {
            'shape': 'barrel',
            'background-color': '#579380', // Teal
            'color': 'var(--cy-node-text-on-dark-bg, white)',
            'text-outline-color': '#2E5A4B',
        }
    },
    {
        selector: 'node[group="CSV"]',
        style: {
            'shape': 'triangle',
            'background-color': '#FFC354', // Gold
            'color': 'var(--cy-node-text-on-light-bg, black)',
            'text-outline-color': '#E0A83B',
        }
    },
    {
        selector: 'node[group="PLMXML"]',
        style: {
            'shape': 'pentagon',
            'background-color': '#F79767', // Orange
            'color': 'var(--cy-node-text-on-dark-bg, white)',
            'text-outline-color': '#B86741',
        }
    },
    {
        selector: 'node[group="JSON"]',
        style: {
            'shape': 'hexagon',
            'background-color': '#C990C0', // Purple
            'color': 'var(--cy-node-text-on-dark-bg, white)',
            'text-outline-color': '#8A5C84',
        }
    },
    // NiFi specific node styles
    {
        selector: 'node.nifi-processor',
        style: {
            'shape': 'round-rectangle',
            'background-color': 'var(--cy-nifi-processor-color, #66BB6A)', // Green
            'color': 'var(--cy-node-text-on-dark-bg, white)',
            'text-outline-color': 'var(--cy-nifi-processor-outline, #388E3C)',
            'cursor': 'pointer'
        }
    },
    {
        selector: 'node.nifi-processor[state="STOPPED"]',
        style: {
            'background-color': 'var(--cy-nifi-processor-stopped-color, #EF5350)', // Red
            'text-outline-color': 'var(--cy-nifi-processor-stopped-outline, #C62828)',
        }
    },
    {
        selector: 'node.nifi-processor[state="DISABLED"]',
        style: {
            'background-color': 'var(--cy-nifi-processor-disabled-color, #BDBDBD)', // Grey
            'text-outline-color': 'var(--cy-nifi-processor-disabled-outline, #757575)',
            'cursor': 'not-allowed'
        }
    },
    {
        selector: 'node.nifi-processor:active',
        style: {
            'overlay-color': 'var(--accent-color)',
            'overlay-opacity': 0.2
        }
    },
    {
        selector: 'node.nifi-inputport',
        style: {
            'shape': 'octagon',
            'background-color': 'var(--cy-nifi-input-port-color, #29B6F6)', // Light Blue
            'color': 'var(--cy-node-text-on-dark-bg, white)',
            'text-outline-color': 'var(--cy-nifi-input-port-outline, #0288D1)',
        }
    },
    {
        selector: 'node.nifi-outputport',
        style: {
            'shape': 'octagon',
            'background-color': 'var(--cy-nifi-output-port-color, #FF7043)', // Orange
            'color': 'var(--cy-node-text-on-dark-bg, white)',
            'text-outline-color': 'var(--cy-nifi-output-port-outline, #E64A19)',
        }
    },
    {
        selector: 'node.nifi-processgroup',
        style: {
            'shape': 'round-rectangle',
            'background-color': 'var(--cy-nifi-process-group-color, #9CCC65)', // Light Green
            'color': 'var(--cy-node-text-on-dark-bg, white)',
            'text-outline-color': 'var(--cy-nifi-process-group-outline, #689F38)',
        }
    },
    {
        selector: 'edge',
        style: {
            'width': 2,
            'line-color': 'var(--border-color)',
            'target-arrow-color': 'var(--border-color)',
            'target-arrow-shape': 'triangle',
            'curve-style': 'bezier',
            'label': 'data(label)',
            'font-size': '9px',
            'color': 'var(--text-muted-color)',
            'text-outline-width': 1,
            'text-outline-color': 'var(--background-color)',
            'opacity': 0.6,
            'transition-property': 'line-color, target-arrow-color, opacity',
            'transition-duration': '0.2s',
        }
    },
    {
        selector: 'edge:hover',
        style: {
            'opacity': 1,
            'line-color': 'var(--cy-selected-color)',
            'target-arrow-color': 'var(--cy-selected-color)',
        }
    },
    // NiFi specific edge styles
    {
        selector: 'edge.nifi-connection',
        style: {
            'line-color': 'var(--cy-nifi-connection-color, #757575)', // Grey
            'target-arrow-color': 'var(--cy-nifi-connection-color, #757575)',
        }
    },
    {
        selector: 'edge.critical',
        style: {
            'line-color': 'var(--cy-critical-color)',
            'target-arrow-color': 'var(--cy-critical-color)',
            'width': 3,
            'z-index': 10,
        }
    },
    {
        selector: ':selected',
        style: {
            'border-width': 3,
            'border-color': 'var(--cy-selected-color)',
            'overlay-padding': 3,
            'overlay-color': 'var(--cy-selected-bg)',
            'overlay-opacity': 0.2,
            'z-index': 9999,
            // For selected edges
            'line-color': 'var(--cy-selected-color)',
            'target-arrow-color': 'var(--cy-selected-color)',
            'opacity': 1,
        }
    },
    {
        selector: 'node.cy-expand-collapse-collapsed-node',
        style: {
            'background-color': '#888',
            'shape': 'round-rectangle',
            'label': 'data(label)',
            'text-valign': 'center',
            'text-halign': 'center',
            'font-size': '10px',
            'color': 'var(--cy-node-text-on-dark-bg, white)',
            'text-outline-width': 1,
            'text-outline-color': '#555',
            'width': '40px',
            'height': '20px',
            'border-width': 1,
            'border-color': '#666',
        }
    },
    {
        selector: '.cy-expand-collapse-meta-edge',
        style: {
            'line-color': '#888',
            'target-arrow-color': '#888',
            'width': 2,
            'curve-style': 'bezier',
        }
    },
    {
        selector: 'node.cy-expand-collapse-parent',
        style: {
            'background-opacity': 0.1,
            'background-color': 'var(--cy-parent-bg)',
            'border-color': 'var(--cy-parent-border)',
            'border-width': 2,
            'shape': 'round-rectangle',
            'padding': '10px',
            'text-valign': 'top',
            'text-halign': 'right',
            'font-size': '12px',
            'color': 'var(--text-color)',
            'text-outline-color': 'var(--background-color)',
        }
    }
];