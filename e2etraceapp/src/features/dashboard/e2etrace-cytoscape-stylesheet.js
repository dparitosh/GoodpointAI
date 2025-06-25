export const cytoscapeStylesheet = [
    {
        selector: 'node',
        style: {
            'background-color': 'data(properties.color)', // Dynamic color from node properties
            'label': 'data(label)',
            'text-valign': 'center',
            'text-halign': 'center',
            'font-size': '11px', // Increased for readability
            'color': 'var(--text-color)',
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
            'color': 'white',
            'text-outline-color': '#265282',
        }
    },
    {
        selector: 'node[group="CustomDB"]',
        style: {
            'shape': 'barrel',
            'background-color': '#579380', // Teal
            'color': 'white',
            'text-outline-color': '#2E5A4B',
        }
    },
    {
        selector: 'node[group="CSV"]',
        style: {
            'shape': 'triangle',
            'background-color': '#FFC354', // Gold
            'color': 'black',
            'text-outline-color': '#E0A83B',
        }
    },
    {
        selector: 'node[group="PLMXML"]',
        style: {
            'shape': 'pentagon',
            'background-color': '#F79767', // Orange
            'color': 'white',
            'text-outline-color': '#B86741',
        }
    },
    {
        selector: 'node[group="JSON"]',
        style: {
            'shape': 'hexagon',
            'background-color': '#C990C0', // Purple
            'color': 'white',
            'text-outline-color': '#8A5C84',
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
            'color': 'white',
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