// Enhanced Cytoscape Stylesheet with comprehensive styling, tooltips, highlighting, and color schemes
export const cytoscapeStylesheet = [
    // === BASE NODE STYLES ===
    {
        selector: 'node',
        style: {
            'background-color': 'data(backgroundColor)',
            'label': 'data(label)',
            'text-valign': 'center',
            'text-halign': 'center',
            'font-size': '12px',
            'color': '#333',
            'text-outline-width': 2,
            'text-outline-color': 'white',
            'width': 'mapData(size, 0, 100, 40, 80)',
            'height': 'mapData(size, 0, 100, 40, 80)',
            'border-width': 2,
            'border-color': '#666',
            'shape': 'ellipse',
            'z-index': 10,
            'opacity': 1,
            'transition-property': 'background-color, line-color, target-arrow-color, width, height, border-color',
            'transition-duration': '0.3s',
            'transition-timing-function': 'ease-in-out',
            'font-family': '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
            'text-wrap': 'wrap',
            'text-max-width': '100px',
        }
    },
    
    // === NODE HOVER EFFECTS (via .hover class - apply programmatically) ===
    {
        selector: 'node.hover',
        style: {
            'border-color': '#007bff',
            'border-width': 3,
            'z-index': 999,
        }
    },
    
    // === NODE SELECTION EFFECTS ===
    {
        selector: 'node:selected',
        style: {
            'border-width': 4,
            'border-color': '#ff6b35',
            'overlay-padding': 6,
            'overlay-color': '#ff6b35',
            'overlay-opacity': 0.2,
            'z-index': 9999,
        }
    },
    
    // NOTE: Node type colors and shapes are now FULLY DYNAMIC
    // Colors come from data(backgroundColor) set by e2etrace-graph-enhancement.js
    // Shapes are set via data(shape) using the centralized color system in constants/node-colors.js
    // No more hardcoded node type styles needed!
    
    // Dynamic shape support - shapes determined by node type hash
    {
        selector: 'node[shape="ellipse"]',
        style: { 'shape': 'ellipse' }
    },
    {
        selector: 'node[shape="rectangle"]',
        style: { 'shape': 'rectangle' }
    },
    {
        selector: 'node[shape="round-rectangle"]',
        style: { 'shape': 'round-rectangle', 'corner-radius': 8 }
    },
    {
        selector: 'node[shape="diamond"]',
        style: { 'shape': 'diamond' }
    },
    {
        selector: 'node[shape="hexagon"]',
        style: { 'shape': 'hexagon' }
    },
    {
        selector: 'node[shape="octagon"]',
        style: { 'shape': 'octagon' }
    },
    {
        selector: 'node[shape="triangle"]',
        style: { 'shape': 'triangle' }
    },
    {
        selector: 'node[shape="star"]',
        style: { 'shape': 'star' }
    },
    {
        selector: 'node[shape="barrel"]',
        style: { 'shape': 'barrel' }
    },
    {
        selector: 'node[shape="pentagon"]',
        style: { 'shape': 'pentagon' }
    },
    {
        selector: 'node[shape="vee"]',
        style: { 'shape': 'vee' }
    },
    {
        selector: 'node[shape="rhomboid"]',
        style: { 'shape': 'rhomboid' }
    },
    
    // Error/Critical nodes still get special treatment
    {
        selector: 'node.error, node[status="error"]',
        style: {
            'border-width': 3,
            'border-color': '#FF0000',
        }
    },
    
    // === RELATIONSHIP AND EDGE STYLING ===
    // Edge colors are now DYNAMIC - set via data(lineColor) from enhancement
    {
        selector: 'edge',
        style: {
            'width': 'mapData(weight, 0, 10, 2, 6)',
            'line-color': 'data(lineColor)',
            'target-arrow-color': 'data(lineColor)',
            'target-arrow-shape': 'triangle',
            'arrow-scale': 1.2,
            'curve-style': 'bezier',
            'control-point-step-size': 40,
            'label': 'data(label)',
            'font-size': '10px',
            'color': '#444',
            'text-outline-width': 1,
            'text-outline-color': 'white',
            'opacity': 0.8,
            'transition-property': 'line-color, target-arrow-color, opacity, width',
            'transition-duration': '0.2s',
            'font-family': '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
            'text-wrap': 'wrap',
            'text-max-width': '80px',
            'text-rotation': 'autorotate',
            'text-margin-y': -10,
            'z-index': 5,
        }
    },
    
    // Fallback for edges without lineColor data
    {
        selector: 'edge[!lineColor]',
        style: {
            'line-color': '#7f8c8d',
            'target-arrow-color': '#7f8c8d',
        }
    },
    
    // Dynamic line styles based on data
    {
        selector: 'edge[lineStyle="dashed"]',
        style: {
            'line-style': 'dashed',
            'line-dash-pattern': [8, 4],
        }
    },
    {
        selector: 'edge[lineStyle="dotted"]',
        style: {
            'line-style': 'dotted',
            'line-dash-pattern': [2, 4],
        }
    },
    
    // Edge hover (via .hover class - apply programmatically)
    {
        selector: 'edge.hover',
        style: {
            'opacity': 1,
            'line-color': '#007bff',
            'target-arrow-color': '#007bff',
            'width': 'mapData(weight, 0, 10, 4, 8)',
            'z-index': 999,
        }
    },
    
    {
        selector: 'edge:selected',
        style: {
            'line-color': '#ff6b35',
            'target-arrow-color': '#ff6b35',
            'width': 'mapData(weight, 0, 10, 5, 10)',
            'opacity': 1,
            'z-index': 9999,
        }
    },
    
    // NOTE: Relationship type colors are now DYNAMIC
    // Colors come from data(lineColor) set by e2etrace-graph-enhancement.js
    // using the centralized color system in constants/node-colors.js
    
    // Critical edges still get special treatment (override)
    {
        selector: 'edge.critical, edge[priority="high"]',
        style: {
            'line-color': '#FF0000',
            'target-arrow-color': '#FF0000',
            'width': 6,
            'z-index': 100,
            'line-style': 'solid',
        }
    },
    
    // === SEARCH AND FILTER HIGHLIGHTS ===
    {
        selector: '.search-highlight',
        style: {
            'border-width': 5,
            'border-color': '#17a2b8',
            'z-index': 9998,
            'overlay-padding': 8,
            'overlay-color': '#17a2b8',
            'overlay-opacity': 0.25,
        }
    },
    
    {
        selector: '.search-dimmed',
        style: {
            'opacity': 0.2,
            'events': 'no',
        }
    },
    
    {
        selector: '.filtered-out',
        style: {
            'opacity': 0.05,
            'events': 'no',
        }
    },
    
    {
        selector: '.path-highlight',
        style: {
            'border-width': 4,
            'border-color': '#ffc107',
            'z-index': 9997,
        }
    },
    
    // === CLUSTERING AND GROUPING ===
    {
        selector: 'node.cluster-parent',
        style: {
            'background-opacity': 0.1,
            'background-color': '#ecf0f1',
            'border-color': '#bdc3c7',
            'border-width': 2,
            'shape': 'round-rectangle',
            'padding': 20,
            'text-valign': 'top',
            'text-halign': 'center',
            'font-size': 14,
            'font-weight': 'bold',
            'color': '#2c3e50',
            'text-outline-color': 'white',
            'corner-radius': 15,
        }
    },
    
    {
        selector: 'node.cluster-child',
        style: {
            'opacity': 0.9,
        }
    },
    
    // === EXPAND/COLLAPSE STYLES ===
    {
        selector: 'node.cy-expand-collapse-collapsed-node',
        style: {
            'background-color': '#95a5a6',
            'shape': 'round-rectangle',
            'label': 'data(label)',
            'text-valign': 'center',
            'text-halign': 'center',
            'font-size': '10px',
            'color': 'white',
            'text-outline-width': 1,
            'text-outline-color': '#7f8c8d',
            'width': 55,
            'height': 30,
            'border-width': 2,
            'border-color': '#7f8c8d',
            'corner-radius': 8,
        }
    },
    
    {
        selector: '.cy-expand-collapse-meta-edge',
        style: {
            'line-color': '#95a5a6',
            'target-arrow-color': '#95a5a6',
            'width': 2,
            'curve-style': 'bezier',
            'line-style': 'dotted',
            'opacity': 0.6,
        }
    },
    
    // === STATUS AND PERFORMANCE INDICATORS ===
    {
        selector: 'node[status="healthy"], node.healthy',
        style: {
            'border-color': '#27ae60',
        }
    },
    
    {
        selector: 'node[status="warning"], node.warning',
        style: {
            'border-color': '#f39c12',
        }
    },
    
    {
        selector: 'node[status="error"], node.error',
        style: {
            'border-color': '#e74c3c',
        }
    },
    
    // === NODE SIZE VARIATIONS BY IMPORTANCE ===
    {
        selector: 'node[importance="high"]',
        style: {
            'width': 90,
            'height': 90,
            'font-size': '14px',
            'border-width': 3,
        }
    },
    
    {
        selector: 'node[importance="medium"]',
        style: {
            'width': 65,
            'height': 65,
            'font-size': '12px',
            'border-width': 2,
        }
    },
    
    {
        selector: 'node[importance="low"]',
        style: {
            'width': 45,
            'height': 45,
            'font-size': '10px',
            'border-width': 1,
        }
    },
    
    // === INTERACTION ENHANCEMENTS ===
    {
        selector: 'node:active',
        style: {
            'overlay-color': '#3498db',
            'overlay-opacity': 0.3,
            'overlay-padding': 4,
        }
    },
    
    {
        selector: 'edge:active',
        style: {
            'overlay-color': '#3498db',
            'overlay-opacity': 0.2,
        }
    },
    
    // ETL Filter States
    {
        selector: '.etl-filtered',
        style: {
            'overlay-opacity': 0.3,
            'overlay-color': '#007bff',
            'border-width': 3,
            'border-color': '#007bff',
            'z-index': 999
        }
    },
    {
        selector: 'edge.etl-filtered',
        style: {
            'line-color': '#007bff',
            'target-arrow-color': '#007bff',
            'width': 4,
            'opacity': 1,
            'z-index': 999
        }
    },

    // Performance Issue Indicators
    {
        selector: '.performance-issue',
        style: {
            'border-width': 3,
            'border-style': 'dashed'
        }
    },
    {
        selector: '.high-latency',
        style: {
            'border-color': '#ffc107',
            'overlay-color': '#ffc107',
            'overlay-opacity': 0.2
        }
    },
    {
        selector: '.low-throughput',
        style: {
            'border-color': '#fd7e14',
            'overlay-color': '#fd7e14',
            'overlay-opacity': 0.2
        }
    },
    {
        selector: '.high-error',
        style: {
            'border-color': '#dc3545',
            'overlay-color': '#dc3545',
            'overlay-opacity': 0.3
        }
    },

    // Pipeline Highlighting
    {
        selector: '.pipeline-highlighted',
        style: {
            'background-color': data => data('backgroundColor') || '#17a2b8',
            'border-width': 4,
            'border-color': '#17a2b8',
            'overlay-color': '#17a2b8',
            'overlay-opacity': 0.2
        }
    },

    // ...existing styles...
];

// Enhanced Color Schemes for different themes
export const colorSchemes = {
    default: {
        primary: '#007bff',
        secondary: '#6c757d',
        success: '#28a745',
        warning: '#ffc107',
        danger: '#dc3545',
        info: '#17a2b8',
        light: '#f8f9fa',
        dark: '#343a40'
    },
    dark: {
        primary: '#0d6efd',
        secondary: '#6c757d',
        success: '#198754',
        warning: '#ffc107',
        danger: '#dc3545',
        info: '#0dcaf0',
        light: '#212529',
        dark: '#f8f9fa'
    },
    corporate: {
        primary: '#1f4e79',
        secondary: '#5a6c7d',
        success: '#2d5016',
        warning: '#8b4513',
        danger: '#8b0000',
        info: '#2f4f4f',
        light: '#f5f5f5',
        dark: '#2c3e50'
    },
    vibrant: {
        primary: '#ff6b35',
        secondary: '#004e89',
        success: '#1a936f',
        warning: '#f18f01',
        danger: '#c73e1d',
        info: '#84bcda',
        light: '#f7f9fb',
        dark: '#1b2021'
    }
};