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
      'transition-property': 'background-color, line-color, target-arrow-color, width, height, border-color',
      'transition-duration': '0.4s',
      'transition-timing-function': 'cubic-bezier(0.4, 0.0, 0.2, 1)',
      'font-family': '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
      'text-wrap': 'wrap',
      'text-max-width': '110px',
      'corner-radius': 12,
      'padding': 8,
      'background-opacity': 0.95,
    }
  },

  // === NODE HOVER EFFECTS (via .hover class - apply programmatically) ===
  {
    selector: 'node.hover',
    style: {
      'border-color': '#007acc',
      'border-width': 3,
      'z-index': 999,
      'background-opacity': 1,
    }
  },

  // === NODE SELECTION EFFECTS ===
  {
    selector: 'node:selected',
    style: {
      'border-width': 3,
      'border-color': '#0098ff',
      'overlay-padding': 8,
      'overlay-color': '#0098ff',
      'overlay-opacity': 0.15,
      'z-index': 9999,
      'background-opacity': 1,
    }
  },

  // === ETL/DATA SOURCE NODE TYPES (XSTATE COLOR SCHEME) ===
  
  // Database Sources
  {
    selector: 'node[type="Database"], node[group="Database"], node[group="Teamcenter"], node[group="CustomDB"]',
    style: {
      'background-color': '#48a4ff',
      'color': 'white',
      'border-color': '#3b87d6',
      'shape': 'barrel',
    }
  },

  // File Sources - CSV
  {
    selector: 'node[type="CSV"], node[group="CSV"]',
    style: {
      'background-color': '#ffba5a',
      'color': '#1a2a3a',
      'border-color': '#e6a240',
    }
  },

  // File Sources - JSON
  {
    selector: 'node[type="JSON"], node[group="JSON"]',
    style: {
      'background-color': '#9b6cff',
      'color': 'white',
      'border-color': '#8252e6',
    }
  },

  // File Sources - XML/PLMXML
  {
    selector: 'node[type="XML"], node[group="XML"], node[group="PLMXML"]',
    style: {
      'background-color': '#ff7077',
      'color': 'white',
      'border-color': '#e65660',
    }
  },

  // Processing/Transform Nodes
  {
    selector: 'node[type="Processor"], node[group="Processor"], node[type="Transform"], node[group="Transform"], node[type="ETL"], node[group="ETL"]',
    style: {
      'background-color': '#21d5c1',
      'color': 'white',
      'border-color': '#1ab39f',
      'shape': 'diamond',
    }
  },

  // Agentic workflow demo types (used by sample/hero and some workflow configs)
  {
    selector: 'node[type="extract"], node[group="extract"]',
    style: {
      'background-color': '#42A5F5',
      'color': 'white',
      'border-color': '#2f86d1',
      'shape': 'round-rectangle',
    }
  },
  {
    selector: 'node[type="transform"], node[group="transform"]',
    style: {
      'background-color': '#FB8C00',
      'color': 'white',
      'border-color': '#d97706',
      'shape': 'diamond',
    }
  },
  {
    selector: 'node[type="quality"], node[group="quality"]',
    style: {
      'background-color': '#43A047',
      'color': 'white',
      'border-color': '#2e7d32',
      'shape': 'round-rectangle',
    }
  },
  {
    selector: 'node[type="load"], node[group="load"]',
    style: {
      'background-color': '#5E35B1',
      'color': 'white',
      'border-color': '#4527a0',
      'shape': 'round-rectangle',
    }
  },
  {
    selector: 'node[type="target"], node[group="target"]',
    style: {
      'background-color': '#263238',
      'color': 'white',
      'border-color': '#111827',
      'shape': 'round-rectangle',
    }
  },
  {
    selector: 'node[type="ai_agent"], node[group="ai_agent"]',
    style: {
      'background-color': '#6A1B9A',
      'color': 'white',
      'border-color': '#4a148c',
      'shape': 'hexagon',
    }
  },

  // API/Service Nodes
  {
    selector: 'node[type="API"], node[group="API"], node[type="Service"], node[group="Service"], node[type="Endpoint"], node[group="Endpoint"]',
    style: {
      'background-color': '#6e6fff',
      'color': 'white',
      'border-color': '#5555e6',
    }
  },

  // Data Quality Issues
  {
    selector: 'node[type="DataQualityIssue"], node[group="DataQualityIssue"]',
    style: {
      'background-color': '#e74c3c',
      'color': 'white',
      'border-color': '#c0392b',
      'shape': 'star',
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

  // Compound hover (via .hover class - apply programmatically)
  {
    selector: 'node.compound.hover',
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
      'arrow-scale': 1.2,
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

  // Edge hover (via .hover class - apply programmatically)
  {
    selector: 'edge.hover',
    style: {
      'opacity': 1,
      'line-color': '#007acc',
      'target-arrow-color': '#007acc',
      'width': 'mapData(weight, 0, 10, 3, 6)',
      'z-index': 999,
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
    selector: 'edge[type="FLOW"]',
    style: {
      'line-color': '#0033A0',
      'target-arrow-color': '#0033A0',
      'opacity': 0.95,
      'width': 'mapData(weight, 0, 10, 3, 6)',
      'text-outline-color': 'white',
    }
  },
  {
    selector: 'edge[type="ASSISTS"]',
    style: {
      'line-color': '#6A1B9A',
      'target-arrow-color': '#6A1B9A',
      'line-style': 'dashed',
      'line-dash-pattern': [10, 5],
      'opacity': 0.9,
      'width': 'mapData(weight, 0, 10, 2, 5)',
      'text-outline-color': 'white',
    }
  },
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
    }
  },

  {
    selector: 'node[status="warning"], node.warning',
    style: {
      'border-color': '#ffc107',
    }
  },

  {
    selector: 'node[status="error"], node.error',
    style: {
      'border-color': '#f44336',
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
