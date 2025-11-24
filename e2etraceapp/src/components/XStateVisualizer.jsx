/**
 * XState Visualizer Component
 * Visualizes state machine transitions with nodes and relationships using Cytoscape
 */

import React, { useEffect, useRef, useState } from 'react';
import cytoscape from 'cytoscape';
import './XStateVisualizer.css';

const XStateVisualizer = ({ stateData, onNodeClick }) => {
  const containerRef = useRef(null);
  const cyRef = useRef(null);
  const [selectedNode, setSelectedNode] = useState(null);

  useEffect(() => {
    if (!containerRef.current || !stateData) return;

    // Initialize Cytoscape
    const cy = cytoscape({
      container: containerRef.current,
      
      elements: [
        // Nodes (States)
        ...stateData.states.map(state => ({
          data: {
            id: state.id,
            label: state.name,
            type: state.type || 'normal',
            metadata: state.metadata || {}
          }
        })),
        
        // Edges (Transitions)
        ...stateData.transitions.map((transition, idx) => ({
          data: {
            id: `edge-${idx}`,
            source: transition.from,
            target: transition.to,
            label: transition.event || '',
            metadata: transition.metadata || {}
          }
        }))
      ],

      style: [
        // Node styles with Neon Glow
        {
          selector: 'node',
          style: {
            'background-color': '#0066CC',
            'label': 'data(label)',
            'color': '#FFFFFF',
            'text-valign': 'center',
            'text-halign': 'center',
            'font-size': '14px',
            'font-weight': 'bold',
            'width': '80px',
            'height': '80px',
            'border-width': 3,
            'border-color': '#00ccff',
            'text-wrap': 'wrap',
            'text-max-width': '75px',
            'shadow-blur': 20,
            'shadow-color': '#00ccff',
            'shadow-opacity': 0.7,
            'text-outline-width': 2,
            'text-outline-color': '#0a0e27'
          }
        },
        
        // Initial state (Gold with glow)
        {
          selector: 'node[type="initial"]',
          style: {
            'background-color': '#FFD700',
            'border-color': '#FFA500',
            'shape': 'round-rectangle',
            'shadow-color': '#FFD700',
            'color': '#0a0e27'
          }
        },
        
        // Final state (Purple/Magenta with glow)
        {
          selector: 'node[type="final"]',
          style: {
            'background-color': '#9370DB',
            'border-color': '#8A2BE2',
            'shape': 'round-rectangle',
            'shadow-color': '#9370DB'
          }
        },
        
        // Active/Current state (Neon Green with pulse)
        {
          selector: 'node[type="active"]',
          style: {
            'background-color': '#00FF00',
            'border-color': '#00FF00',
            'border-width': 5,
            'shadow-color': '#00FF00',
            'shadow-blur': 30,
            'shadow-opacity': 1,
            'color': '#0a0e27'
          }
        },
        
        // Error state (Red with warning glow)
        {
          selector: 'node[type="error"]',
          style: {
            'background-color': '#FF0040',
            'border-color': '#FF1744',
            'shape': 'octagon',
            'shadow-color': '#FF0040',
            'shadow-blur': 25
          }
        },
        
        // Compound nodes (parent states) with glassmorphic effect
        {
          selector: 'node[type="compound"]',
          style: {
            'background-color': '#FF8C00',
            'background-opacity': 0.4,
            'border-color': '#00ccff',
            'border-style': 'dashed',
            'border-width': 2,
            'color': '#00ffff',
            'shadow-color': '#FF8C00'
          }
        },
        
        // Selected node with intense glow
        {
          selector: 'node:selected',
          style: {
            'border-width': 6,
            'border-color': '#00ffff',
            'background-color': '#4D94E6',
            'shadow-color': '#00ffff',
            'shadow-blur': 40,
            'shadow-opacity': 1
          }
        },

        // Edge styles with Neon Cyan
        {
          selector: 'edge',
          style: {
            'width': 3,
            'line-color': '#00ccff',
            'target-arrow-color': '#00ccff',
            'target-arrow-shape': 'triangle',
            'curve-style': 'bezier',
            'label': 'data(label)',
            'font-size': '11px',
            'color': '#00ffff',
            'text-background-color': 'rgba(10, 14, 39, 0.95)',
            'text-background-opacity': 1,
            'text-background-padding': '4px',
            'text-rotation': 'autorotate',
            'text-outline-width': 1,
            'text-outline-color': '#00ccff',
            'arrow-scale': 1.5
          }
        },
        
        // Edge hover effect (interactive)
        {
          selector: 'edge:hover',
          style: {
            'width': 5,
            'line-color': '#00ffff',
            'target-arrow-color': '#00ffff'
          }
        },
        
        // Self-loop edges with dramatic arc
        {
          selector: 'edge[source=target]',
          style: {
            'curve-style': 'unbundled-bezier',
            'control-point-distances': [50],
            'control-point-weights': [0.5],
            'line-color': '#FF8C00',
            'target-arrow-color': '#FF8C00'
          }
        },
        
        // Selected edge with max intensity
        {
          selector: 'edge:selected',
          style: {
            'line-color': '#00ffff',
            'target-arrow-color': '#00ffff',
            'width': 6,
            'opacity': 1
          }
        }
      ],

      layout: {
        name: 'breadthfirst',
        directed: true,
        spacingFactor: 1.5,
        animate: true,
        animationDuration: 500
      },

      minZoom: 0.5,
      maxZoom: 3,
      wheelSensitivity: 0.2
    });

    // Event handlers
    cy.on('tap', 'node', (event) => {
      const node = event.target;
      setSelectedNode({
        id: node.id(),
        label: node.data('label'),
        type: node.data('type'),
        metadata: node.data('metadata')
      });
      
      if (onNodeClick) {
        onNodeClick(node.data());
      }
    });

    cy.on('tap', 'edge', (event) => {
      const edge = event.target;
      setSelectedNode({
        id: edge.id(),
        from: edge.data('source'),
        to: edge.data('target'),
        label: edge.data('label'),
        metadata: edge.data('metadata'),
        isEdge: true
      });
    });

    // Store reference
    cyRef.current = cy;

    // Cleanup
    return () => {
      if (cyRef.current) {
        cyRef.current.destroy();
      }
    };
  }, [stateData, onNodeClick]);

  const handleLayoutChange = (layoutName) => {
    if (cyRef.current) {
      cyRef.current.layout({
        name: layoutName,
        animate: true,
        animationDuration: 500
      }).run();
    }
  };

  const handleFitView = () => {
    if (cyRef.current) {
      cyRef.current.fit(null, 50);
    }
  };

  const handleExportImage = () => {
    if (cyRef.current) {
      const png = cyRef.current.png({
        output: 'blob',
        bg: '#FFFFFF',
        full: true,
        scale: 2
      });
      
      const url = URL.createObjectURL(png);
      const link = document.createElement('a');
      link.href = url;
      link.download = 'xstate-diagram.png';
      link.click();
      URL.revokeObjectURL(url);
    }
  };

  return (
    <div className="xstate-visualizer">
      <div className="controls visualizer-toolbar">
        <div className="control-group">
          <button onClick={handleFitView} className="toolbar-btn">
            <i className="fas fa-search-plus"></i> Fit View
          </button>
        </div>
        <div className="control-group">
          <label>Layout:</label>
          <button onClick={() => handleLayoutChange('breadthfirst')} className="toolbar-btn">
            <i className="fas fa-sitemap"></i> Hierarchical
          </button>
          <button onClick={() => handleLayoutChange('circle')} className="toolbar-btn">
            <i className="fas fa-circle-notch"></i> Circle
          </button>
          <button onClick={() => handleLayoutChange('cose')} className="toolbar-btn">
            <i className="fas fa-project-diagram"></i> Force
          </button>
        </div>
        <div className="control-group">
          <button onClick={handleExportImage} className="toolbar-btn">
            <i className="fas fa-download"></i> Export PNG
          </button>
        </div>
      </div>

      <div ref={containerRef} className="visualizer-canvas cytoscape-container" />

      {selectedNode && (
        <div className="context-hud node-details-panel">
          <h4>{selectedNode.isEdge ? '⚡ TRANSITION DATA' : '🔮 STATE DATA'}</h4>
          <div className="context-variable detail-item">
            <span className="context-key">ID:</span>
            <span className="context-value">{selectedNode.id}</span>
          </div>
          <div className="context-variable detail-item">
            <span className="context-key">Label:</span>
            <span className="context-value">{selectedNode.label || 'N/A'}</span>
          </div>
          {selectedNode.isEdge ? (
            <>
              <div className="context-variable detail-item">
                <span className="context-key">From:</span>
                <span className="context-value">{selectedNode.from}</span>
              </div>
              <div className="context-variable detail-item">
                <span className="context-key">To:</span>
                <span className="context-value">{selectedNode.to}</span>
              </div>
            </>
          ) : (
            <div className="context-variable detail-item">
              <span className="context-key">Type:</span>
              <span className="context-value">{selectedNode.type || 'normal'}</span>
            </div>
          )}
          {selectedNode.metadata && Object.keys(selectedNode.metadata).length > 0 && (
            <div className="context-variable detail-item">
              <span className="context-key">Metadata:</span>
              <pre className="context-value">{JSON.stringify(selectedNode.metadata, null, 2)}</pre>
            </div>
          )}
          <button onClick={() => setSelectedNode(null)} className="close-btn">
            <i className="fas fa-times"></i> Close
          </button>
        </div>
      )}
    </div>
  );
};

export default XStateVisualizer;
