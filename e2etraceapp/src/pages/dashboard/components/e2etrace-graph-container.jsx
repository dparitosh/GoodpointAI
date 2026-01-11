import React, { useCallback, useEffect, useRef, useState } from 'react';
import cytoscape from 'cytoscape';
import { cytoscapeStylesheet } from '../e2etrace-cytoscape-stylesheet';
import CytoscapeTooltip from '../../../components/e2etrace-cytoscape-tooltip';

const Graph = ({ elements = [], isLoading, cyRef }) => {
  const localCyRef = useRef(null);
  const [cyInstance, setCyInstance] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!localCyRef.current) {
      console.error('Graph container ref is null');
      return;
    }

    let createdCy = null;

    try {
      console.log('Creating Cytoscape instance with elements:', elements);
      
      const cy = cytoscape({
        container: localCyRef.current,
        elements: elements || [],
        style: cytoscapeStylesheet,
        layout: {
          name: 'cose',
          directed: true,
          padding: 30,
          nodeRepulsion: function(node) {
            return node.degree() * 2000;
          },
          nodeOverlap: 20,
          idealEdgeLength: function(_edge) {
            return 100;
          },
          edgeElasticity: function(_edge) {
            return 100;
          },
          nestingFactor: 5,
          gravity: 80,
          numIter: 1000,
          initialTemp: 200,
          coolingFactor: 0.95,
          minTemp: 1.0,
          animate: true,
          animationDuration: 500,
          animationEasing: 'ease-out',
          randomize: false,
          componentSpacing: 100,
          boundingBox: undefined,
          avoidOverlap: true,
          avoidOverlapPadding: 10,
          nodeDimensionsIncludeLabels: true,
          spacingFactor: undefined,
          radius: undefined,
          startAngle: 3 / 2 * Math.PI,
          sweep: undefined,
          clockwise: true,
          sort: undefined,
          animateFilter: function(_node, _i) {
            return true;
          },
          ready: undefined,
          stop: undefined,
          transform: function(_node, position) {
            return position;
          }
        },
        // Note: wheelSensitivity default (1) is recommended for cross-platform compatibility
        motionBlur: false,
        pixelRatio: 'auto',
        textureOnViewport: false,
        hideEdgesOnViewport: false,
        hideLabelsOnViewport: false,
        renderToHighQuality: true,
        panningEnabled: true,
        userPanningEnabled: true,
        zoomingEnabled: true,
        userZoomingEnabled: true,
        boxSelectionEnabled: true,
        selectionType: 'single',
        touchTapThreshold: 8,
        desktopTapThreshold: 4,
        autolock: false,
        autoungrabify: false,
        autounselectify: false,
        headless: false,
        styleEnabled: true,
        motionBlurOpacity: 0.2,
        // pixelRatio/motionBlur/textureOnViewport/hideEdgesOnViewport are already set above
      });

      createdCy = cy;

      // Enhanced interaction handling
      cy.on('tap', 'node', function(evt) {
        const node = evt.target;
        console.log('Node tapped:', node.data());
        
        // Highlight connected nodes and edges
        const connectedEdges = node.connectedEdges();
        const connectedNodes = connectedEdges.connectedNodes();
        
        // Remove previous highlights
        cy.elements().removeClass('search-highlight path-highlight');
        
        // Add highlights
        node.addClass('search-highlight');
        connectedNodes.addClass('path-highlight');
        connectedEdges.addClass('path-highlight');
      });

      cy.on('tap', 'edge', function(evt) {
        const edge = evt.target;
        console.log('Edge tapped:', edge.data());
        
        // Highlight the edge and its connected nodes
        cy.elements().removeClass('search-highlight path-highlight');
        edge.addClass('search-highlight');
        edge.connectedNodes().addClass('path-highlight');
      });

      // Clear highlights when clicking on background
      cy.on('tap', function(evt) {
        if (evt.target === cy) {
          cy.elements().removeClass('search-highlight path-highlight search-dimmed filtered-out');
        }
      });

      // Double-click to fit
      cy.on('dblclick', function(evt) {
        if (evt.target === cy) {
          cy.fit();
        }
      });

      setCyInstance(cy);
      if (cyRef) cyRef.current = cy;
      setError(null);

      // Fit the graph after layout is complete
      cy.ready(() => {
        if (elements && elements.length > 0) {
          cy.fit();
          cy.center();
        }
      });

      console.log('Cytoscape instance created successfully with advanced styling');

    } catch (err) {
      console.error('Error creating Cytoscape instance:', err);
      setError(err.message);
    }

    return () => {
      if (createdCy) {
        createdCy.removeAllListeners?.();
        createdCy.destroy();
      }
      if (cyRef) cyRef.current = null;
    };
  }, [elements, cyRef]);

  // Enhanced search functionality
  const highlightSearchResults = useCallback((searchTerm) => {
    if (!cyInstance || !searchTerm) {
      cyInstance?.elements().removeClass('search-highlight search-dimmed');
      return;
    }

    const searchLower = searchTerm.toLowerCase();
    const matchingElements = cyInstance.elements().filter(el => {
      const label = el.data('label') || '';
      const id = el.data('id') || '';
      return label.toLowerCase().includes(searchLower) || id.toLowerCase().includes(searchLower);
    });

    // Remove previous highlights
    cyInstance.elements().removeClass('search-highlight search-dimmed');

    if (matchingElements.length > 0) {
      // Highlight matches
      matchingElements.addClass('search-highlight');
      
      // Dim non-matches
      cyInstance.elements().not(matchingElements).addClass('search-dimmed');
      
      // Fit to highlighted elements
      cyInstance.fit(matchingElements, 50);
    }
  }, [cyInstance]);

  // Expose search functionality
  useEffect(() => {
    if (cyInstance && cyRef) {
      cyRef.current.highlightSearchResults = highlightSearchResults;
    }
  }, [cyInstance, cyRef, highlightSearchResults]);

  if (error) {
    return (
      <div style={{ 
        width: '100%', 
        height: '100%', 
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        flexDirection: 'column',
        background: '#f8f9fa',
        color: '#dc3545',
        fontSize: '0.9rem',
        textAlign: 'center',
        padding: '2rem'
      }}>
        <div style={{ marginBottom: '1rem', fontSize: '1.1rem', fontWeight: 'bold' }}>
          Graph Visualization Error
        </div>
        <div style={{ marginBottom: '1rem' }}>
          {error}
        </div>
        <div style={{ fontSize: '0.8rem', color: '#6c757d' }}>
          Please check the console for more details
        </div>
      </div>
    );
  }

  return (
    <div style={{ 
      width: '100%', 
      height: '100%', 
      position: 'relative',
      overflow: 'hidden',
      background: '#ffffff',
      border: '1px solid #e9ecef',
      borderRadius: '8px'
    }}>
      <div
        ref={localCyRef}
        style={{
          width: '100%',
          height: '100%',
          background: '#ffffff'
        }}
      />
      
      {/* Enhanced Tooltip */}
      <CytoscapeTooltip cytoscapeRef={cyRef || { current: cyInstance }} />
      
      {isLoading && (
        <div style={{
          position: 'absolute',
          top: '50%',
          left: '50%',
          transform: 'translate(-50%, -50%)',
          background: 'rgba(255, 255, 255, 0.95)',
          padding: '1.5rem',
          borderRadius: '8px',
          border: '1px solid #e9ecef',
          fontSize: '0.9rem',
          color: '#495057',
          zIndex: 10,
          boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)',
          textAlign: 'center'
        }}>
          <div style={{ marginBottom: '0.5rem' }}>Loading graph visualization...</div>
          <div style={{ 
            width: '100px', 
            height: '2px', 
            background: '#e9ecef', 
            borderRadius: '1px',
            overflow: 'hidden',
            margin: '0 auto'
          }}>
            <div style={{
              width: '30px',
              height: '100%',
              background: '#007bff',
              borderRadius: '1px',
              animation: 'loading 1.5s ease-in-out infinite'
            }}></div>
          </div>
        </div>
      )}
      
      {!isLoading && (!elements || elements.length === 0) && (
        <div style={{
          position: 'absolute',
          top: '50%',
          left: '50%',
          transform: 'translate(-50%, -50%)',
          color: '#6c757d',
          fontSize: '0.9rem',
          textAlign: 'center',
          padding: '2rem'
        }}>
          <div style={{ marginBottom: '1rem', fontSize: '1.1rem' }}>
            No graph data available
          </div>
          <div style={{ fontSize: '0.8rem', lineHeight: '1.4' }}>
            Try loading data from the dashboard controls<br />
            or check your data connection
          </div>
        </div>
      )}
      
      {cyInstance && (
        <div style={{
          position: 'absolute',
          bottom: '10px',
          right: '10px',
          background: 'rgba(255, 255, 255, 0.9)',
          padding: '0.5rem',
          borderRadius: '4px',
          fontSize: '0.75rem',
          color: '#6c757d',
          zIndex: 5
        }}>
          {elements?.length || 0} nodes
        </div>
      )}
      
      <style>{`
        @keyframes loading {
          0% { transform: translateX(-70px); }
          100% { transform: translateX(140px); }
        }
      `}</style>
    </div>
  );
};

export default Graph;