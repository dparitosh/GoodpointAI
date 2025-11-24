// XState-inspired Cytoscape Stylesheet for PLM Graph Visualization

export const xstateStylesheet = [
  // === BASE NODE STYLES (XSTATE-INSPIRED) ===
  {
    selector: 'node',
    style: {
      'background-color': 'data(backgroundColor)',
      'label': 'data(label)',
      'text-valign': 'center',
      'text-halign': 'center',
      'font-size': '13px',
      'font-weight': '600',
      'color': '#2c3e50',
      'text-outline-width': 0,
      'width': 'mapData(size, 0, 100, 80, 120)',
      'height': 'mapData(size, 0, 100, 60, 80)',
      'border-width': 2,
      'border-color': '#e1e4e8',
      'shape': 'round-rectangle',
      'z-index': 10,
      'opacity': 1,
      'transition-property': 'background-color, line-color, target-arrow-color, width, height, border-color, shadow-blur, shadow-opacity',
      'transition-duration': '0.4s',
      'transition-timing-function': 'cubic-bezier(0.4, 0.0, 0.2, 1)',
      'font-family': '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
      'text-wrap': 'wrap',
      'text-max-width': '110px',
      'cursor': 'pointer',
      'shadow-blur': 8,
      'shadow-color': 'rgba(0,0,0,0.12)',
      'shadow-opacity': 0.5,
      'shadow-offset-x': 0,
      'shadow-offset-y': 2,
      'corner-radius': 12,
      'padding': 8,
      'background-opacity': 0.95,
    }
  },

  // === NODE HOVER EFFECTS (XSTATE GLOW) ===
  {
    selector: 'node:hover',
    style: {
      'shadow-blur': 20,
      'shadow-color': '#007acc',
      'shadow-opacity': 0.6,
      'border-color': '#007acc',
      'border-width': 3,
      'z-index': 999,
      'transform': 'scale(1.05)',
      'background-opacity': 1,
    }
  },

  // === NODE SELECTION EFFECTS (PULSE ANIMATION) ===
  {
    selector: 'node:selected',
    style: {
      'border-width': 3,
      'border-color': '#0098ff',
      'overlay-padding': 8,
      'overlay-color': '#0098ff',
      'overlay-opacity': 0.15,
      'z-index': 9999,
      'shadow-blur': 30,
      'shadow-color': '#0098ff',
      'shadow-opacity': 0.8,
      'background-opacity': 1,
    }
  },

  // === PLM NODE TYPES (XSTATE COLOR SCHEME) ===
  
  // Part Nodes
  {
    selector: 'node[type="Part"], node[group="Part"]',
    style: {
      'background-color': '#48a4ff',
      'color': 'white',
      'border-color': '#3b87d6',
    }
  },

  // Document Nodes
  {
    selector: 'node[type="Document"], node[group="Document"]',
    style: {
      'background-color': '#6e6fff',
      'color': 'white',
      'border-color': '#5555e6',
    }
  },

  // Recipe Nodes
  {
    selector: 'node[type="Recipe"], node[group="Recipe"]',
    style: {
      'background-color': '#21d5c1',
      'color': 'white',
      'border-color': '#1ab39f',
    }
  },

  // Material Nodes
  {
    selector: 'node[type="Material"], node[group="Material"]',
    style: {
      'background-color': '#ffba5a',
      'color': 'white',
      'border-color': '#e6a240',
    }
  },

  // Supplier Nodes
  {
    selector: 'node[type="Supplier"], node[group="Supplier"]',
    style: {
      'background-color': '#ff7077',
      'color': 'white',
      'border-color': '#e65660',
    }
  },

  // Batch Nodes
  {
    selector: 'node[type="Batch"], node[group="Batch"]',
    style: {
      'background-color': '#9b6cff',
      'color': 'white',
      'border-color': '#8252e6',
    }
  },

  // BOM Nodes
  {
    selector: 'node[type="BOM"], node[group="BOM"]',
    style: {
      'background-color': '#4caf50',
      'color': 'white',
      'border-color': '#388e3c',
    }
  },

  // === COMPOUND NODES (XSTATE STATE CLUSTERS) ===
  {
    selector: 'node.compound',
    style: {
      'background-opacity': 0.15,
      'background-color': '#e3f2fd',
      'border-color': '#90caf9',
      'border-width': 2,
      'border-style': 'dashed',
      'shape': 'round-rectangle',
      'padding': 20,
      'text-valign': 'top',
      'text-halign': 'center',
      'font-size': 15,
      'font-weight': 'bold',
      'color': '#1976d2',
      'corner-radius': 16,
    }
  },

  {
    selector: 'node.compound:hover',
    style: {
      'background-opacity': 0.25,
      'border-color': '#42a5f5',
    }
  },

  // === EDGE STYLES (ANIMATED TRANSITIONS) ===
  {
    selector: 'edge',
    style: {
      'width': 'mapData(weight, 0, 10, 2, 5)',
      'line-color': '#cbd2d9',
      'target-arrow-color': '#cbd2d9',
      'target-arrow-shape': 'triangle',
      'target-arrow-size': 12,
      'curve-style': 'bezier',
      'control-point-step-size': 60,
      'label': 'data(label)',
      'font-size': '11px',
      'color': '#586069',
      'text-outline-width': 2,
      'text-outline-color': 'white',
      'opacity': 0.8,
      'transition-property': 'line-color, target-arrow-color, opacity, width',
      'transition-duration': '0.3s',
      'font-family': '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
      'text-wrap': 'wrap',
      'text-max-width': '100px',
      'text-rotation': 'autorotate',
      'text-margin-y': -12,
      'z-index': 5,
      'line-style': 'solid',
    }
  },

  {
    selector: 'edge:hover',
    style: {
      'opacity': 1,
      'line-color': '#007acc',
      'target-arrow-color': '#007acc',
      'width': 'mapData(weight, 0, 10, 3, 6)',
      'z-index': 999,
      'shadow-blur': 10,
      'shadow-color': '#007acc',
      'shadow-opacity': 0.4,
    }
  },

  {
    selector: 'edge:selected',
    style: {
      'line-color': '#0098ff',
      'target-arrow-color': '#0098ff',
      'width': 'mapData(weight, 0, 10, 4, 8)',
      'opacity': 1,
      'z-index': 9999,
      'shadow-blur': 15,
      'shadow-color': '#0098ff',
      'shadow-opacity': 0.6,
    }
  },

  // === ANIMATED EDGE STYLES ===
  {
    selector: 'edge.animated',
    style: {
      'line-style': 'dashed',
      'line-dash-pattern': [10, 5],
      'line-dash-offset': 24,
    }
  },

  // === RELATIONSHIP TYPE STYLING ===
  {
    selector: 'edge[type="HAS_PART"]',
    style: {
      'line-color': '#48a4ff',
      'target-arrow-color': '#48a4ff',
    }
  },

  {
    selector: 'edge[type="DEPENDS_ON"]',
    style: {
      'line-color': '#ff7077',
      'target-arrow-color': '#ff7077',
      'line-style': 'dashed',
      'line-dash-pattern': [8, 4],
    }
  },

  {
    selector: 'edge[type="USES"]',
    style: {
      'line-color': '#21d5c1',
      'target-arrow-color': '#21d5c1',
    }
  },

  {
    selector: 'edge[type="SUPPLIES"]',
    style: {
      'line-color': '#ffba5a',
      'target-arrow-color': '#ffba5a',
    }
  },

  // === SEARCH AND FILTER HIGHLIGHTS ===
  {
    selector: '.search-highlight',
    style: {
      'border-width': 4,
      'border-color': '#ffc107',
      'shadow-blur': 25,
      'shadow-color': '#ffc107',
      'shadow-opacity': 0.9,
      'z-index': 9998,
      'overlay-padding': 10,
      'overlay-color': '#ffc107',
      'overlay-opacity': 0.2,
    }
  },

  {
    selector: '.search-dimmed',
    style: {
      'opacity': 0.15,
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

  // === EXPAND/COLLAPSE STYLES ===
  {
    selector: 'node.cy-expand-collapse-collapsed-node',
    style: {
      'background-color': '#95a5a6',
      'shape': 'round-rectangle',
      'label': 'data(label)',
      'text-valign': 'center',
      'text-halign': 'center',
      'font-size': '11px',
      'color': 'white',
      'width': 70,
      'height': 40,
      'border-width': 2,
      'border-color': '#7f8c8d',
      'corner-radius': 10,
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
      'opacity': 0.5,
    }
  },

  // === STATUS INDICATORS ===
  {
    selector: 'node[status="healthy"], node.healthy',
    style: {
      'border-color': '#4caf50',
      'shadow-color': '#4caf50',
    }
  },

  {
    selector: 'node[status="warning"], node.warning',
    style: {
      'border-color': '#ffc107',
      'shadow-color': '#ffc107',
    }
  },

  {
    selector: 'node[status="error"], node.error',
    style: {
      'border-color': '#f44336',
      'shadow-color': '#f44336',
    }
  },

  // === ACTIVE/INTERACTION STATES ===
  {
    selector: 'node:active',
    style: {
      'overlay-color': '#007acc',
      'overlay-opacity': 0.25,
      'overlay-padding': 6,
    }
  },

  {
    selector: 'edge:active',
    style: {
      'overlay-color': '#007acc',
      'overlay-opacity': 0.15,
    }
  },
];

// Dark theme variant
export const xstateStylesheetDark = [
  ...xstateStylesheet.map(rule => {
    if (rule.selector === 'node') {
      return {
        ...rule,
        style: {
          ...rule.style,
          'color': '#e4e6eb',
          'border-color': '#3e3e42',
          'shadow-color': 'rgba(0,0,0,0.4)',
          'background-opacity': 0.9,
        }
      };
    }
    if (rule.selector === 'edge') {
      return {
        ...rule,
        style: {
          ...rule.style,
          'color': '#a8b1bd',
          'line-color': '#4e4e52',
          'target-arrow-color': '#4e4e52',
          'text-outline-color': '#1e1e1e',
        }
      };
    }
    if (rule.selector === 'node.compound') {
      return {
        ...rule,
        style: {
          ...rule.style,
          'background-color': '#094771',
          'border-color': '#1976d2',
          'color': '#64b5f6',
        }
      };
    }
    return rule;
  })
];

export default xstateStylesheet;
