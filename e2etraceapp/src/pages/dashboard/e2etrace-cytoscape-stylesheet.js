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
            'transition-property': 'background-color, line-color, target-arrow-color, width, height, border-color, shadow-blur, shadow-opacity',
            'transition-duration': '0.3s',
            'transition-timing-function': 'ease-in-out',
            'font-family': '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
            'text-wrap': 'wrap',
            'text-max-width': '100px',
            'text-overflow-wrap': 'ellipsis',
            'cursor': 'pointer',
            'shadow-blur': 6,
            'shadow-color': 'rgba(0,0,0,0.2)',
            'shadow-opacity': 0.4,
            'shadow-offset-x': 2,
            'shadow-offset-y': 2,
        }
    },
    
    // === NODE HOVER EFFECTS ===
    {
        selector: 'node:hover',
        style: {
            'shadow-blur': 20,
            'shadow-color': '#007bff',
            'shadow-opacity': 0.8,
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
            'shadow-blur': 25,
            'shadow-color': '#ff6b35',
            'shadow-opacity': 1,
        }
    },
    
    // === NODE GROUPING BY TYPE ===
    
    // Database Systems
    {
        selector: 'node[group="Database"], node[group="Teamcenter"], node[group="CustomDB"]',
        style: {
            'shape': 'barrel',
            'background-color': '#4a90e2',
            'color': 'white',
            'text-outline-color': '#2c5aa0',
            'border-color': '#2c5aa0',
            'width': 65,
            'height': 45,
        }
    },
    
    // File Systems
    {
        selector: 'node[group="CSV"]',
        style: {
            'shape': 'round-rectangle',
            'background-color': '#f39c12',
            'color': 'white',
            'text-outline-color': '#d68910',
            'border-color': '#d68910',
            'width': 55,
            'height': 35,
            'corner-radius': 8,
        }
    },
    
    {
        selector: 'node[group="JSON"]',
        style: {
            'shape': 'hexagon',
            'background-color': '#9b59b6',
            'color': 'white',
            'text-outline-color': '#7d3c98',
            'border-color': '#7d3c98',
            'width': 55,
            'height': 55,
        }
    },
    
    {
        selector: 'node[group="XML"], node[group="PLMXML"]',
        style: {
            'shape': 'pentagon',
            'background-color': '#e67e22',
            'color': 'white',
            'text-outline-color': '#d35400',
            'border-color': '#d35400',
            'width': 55,
            'height': 55,
        }
    },
    
    // Processing Systems
    {
        selector: 'node[group="Processor"], node[group="Transform"], node[group="ETL"]',
        style: {
            'shape': 'diamond',
            'background-color': '#27ae60',
            'color': 'white',
            'text-outline-color': '#1e8449',
            'border-color': '#1e8449',
            'width': 55,
            'height': 55,
        }
    },
    
    // API and Service Nodes
    {
        selector: 'node[group="API"], node[group="Service"], node[group="Endpoint"]',
        style: {
            'shape': 'octagon',
            'background-color': '#8e44ad',
            'color': 'white',
            'text-outline-color': '#7d3c98',
            'border-color': '#7d3c98',
            'width': 50,
            'height': 50,
        }
    },
    
    // Data Quality Issues - Critical nodes
    {
        selector: 'node[group="DataQualityIssue"], node.error',
        style: {
            'background-color': '#e74c3c',
            'shape': 'star',
            'border-width': 3,
            'border-color': '#c0392b',
            'width': 55,
            'height': 55,
            'font-size': '10px',
            'color': 'white',
            'text-outline-color': '#c0392b',
            'shadow-color': '#e74c3c',
            'shadow-blur': 12,
            'shadow-opacity': 0.7,
        }
    },
    
    // === NIFI SPECIFIC STYLING ===
    {
        selector: 'node.nifi-processor',
        style: {
            'shape': 'round-rectangle',
            'background-color': '#66bb6a',
            'color': 'white',
            'text-outline-color': '#388e3c',
            'border-color': '#388e3c',
            'cursor': 'pointer',
            'corner-radius': 12,
        }
    },
    
    {
        selector: 'node.nifi-processor[state="STOPPED"]',
        style: {
            'background-color': '#ef5350',
            'text-outline-color': '#c62828',
            'border-color': '#c62828',
            'opacity': 0.85,
        }
    },
    
    {
        selector: 'node.nifi-processor[state="DISABLED"]',
        style: {
            'background-color': '#bdbdbd',
            'text-outline-color': '#757575',
            'border-color': '#757575',
            'cursor': 'not-allowed',
            'opacity': 0.6,
        }
    },
    
    {
        selector: 'node.nifi-inputport',
        style: {
            'shape': 'triangle',
            'background-color': '#29b6f6',
            'color': 'white',
            'text-outline-color': '#0288d1',
            'border-color': '#0288d1',
            'width': 45,
            'height': 45,
        }
    },
    
    {
        selector: 'node.nifi-outputport',
        style: {
            'shape': 'vee',
            'background-color': '#ff7043',
            'color': 'white',
            'text-outline-color': '#e64a19',
            'border-color': '#e64a19',
            'width': 45,
            'height': 45,
        }
    },
    
    {
        selector: 'node.nifi-processgroup',
        style: {
            'shape': 'round-rectangle',
            'background-color': '#9ccc65',
            'color': 'white',
            'text-outline-color': '#689f38',
            'border-color': '#689f38',
            'corner-radius': 15,
            'padding': 10,
            'text-valign': 'top',
            'text-halign': 'center',
        }
    },
    
    // === RELATIONSHIP AND EDGE STYLING ===
    {
        selector: 'edge',
        style: {
            'width': 'mapData(weight, 0, 10, 2, 6)',
            'line-color': '#666',
            'target-arrow-color': '#666',
            'target-arrow-shape': 'triangle',
            'target-arrow-size': 'mapData(weight, 0, 10, 10, 15)',
            'curve-style': 'bezier',
            'control-point-step-size': 40,
            'label': 'data(label)',
            'font-size': '10px',
            'color': '#444',
            'text-outline-width': 1,
            'text-outline-color': 'white',
            'opacity': 0.7,
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
    
    {
        selector: 'edge:hover',
        style: {
            'opacity': 1,
            'line-color': '#007bff',
            'target-arrow-color': '#007bff',
            'width': 'mapData(weight, 0, 10, 4, 8)',
            'z-index': 999,
            'shadow-blur': 8,
            'shadow-color': '#007bff',
            'shadow-opacity': 0.5,
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
            'shadow-blur': 12,
            'shadow-color': '#ff6b35',
            'shadow-opacity': 0.7,
        }
    },
    
    // === RELATIONSHIP TYPE STYLING ===
    {
        selector: 'edge[type="dataflow"], edge.dataflow',
        style: {
            'line-color': '#2ecc71',
            'target-arrow-color': '#2ecc71',
            'line-style': 'solid',
        }
    },
    
    {
        selector: 'edge[type="dependency"], edge.dependency',
        style: {
            'line-color': '#e74c3c',
            'target-arrow-color': '#e74c3c',
            'line-style': 'dashed',
            'line-dash-pattern': [8, 4],
        }
    },
    
    {
        selector: 'edge[type="inheritance"], edge.inheritance',
        style: {
            'line-color': '#9b59b6',
            'target-arrow-color': '#9b59b6',
            'target-arrow-shape': 'triangle-backcurve',
        }
    },
    
    {
        selector: 'edge[type="composition"], edge.composition',
        style: {
            'line-color': '#f39c12',
            'target-arrow-color': '#f39c12',
            'target-arrow-shape': 'diamond',
        }
    },
    
    {
        selector: 'edge.critical, edge[priority="high"]',
        style: {
            'line-color': '#dc3545',
            'target-arrow-color': '#dc3545',
            'width': 6,
            'z-index': 100,
            'line-style': 'solid',
            'shadow-blur': 8,
            'shadow-color': '#dc3545',
            'shadow-opacity': 0.5,
        }
    },
    
    // === SEARCH AND FILTER HIGHLIGHTS ===
    {
        selector: '.search-highlight',
        style: {
            'border-width': 5,
            'border-color': '#17a2b8',
            'shadow-blur': 25,
            'shadow-color': '#17a2b8',
            'shadow-opacity': 0.9,
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
            'shadow-blur': 15,
            'shadow-color': '#ffc107',
            'shadow-opacity': 0.7,
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
            'parent-opacity': 0.9,
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
            'cursor': 'pointer',
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
            'shadow-color': '#27ae60',
        }
    },
    
    {
        selector: 'node[status="warning"], node.warning',
        style: {
            'border-color': '#f39c12',
            'shadow-color': '#f39c12',
        }
    },
    
    {
        selector: 'node[status="error"], node.error',
        style: {
            'border-color': '#e74c3c',
            'shadow-color': '#e74c3c',
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