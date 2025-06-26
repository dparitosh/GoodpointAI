import React, { useEffect, memo, useRef } from 'react';
import cytoscape from 'cytoscape';

// Import and register extensions
import fcose from 'cytoscape-fcose';
import coseBilkent from 'cytoscape-cose-bilkent';
import expandCollapse from 'cytoscape-expand-collapse';
import popper from 'cytoscape-popper';

// Register extensions on the cytoscape object.
// This should only be done once in the application.
try {
  cytoscape.use(fcose);
  cytoscape.use(coseBilkent);
  cytoscape.use(expandCollapse);
  cytoscape.use(popper);
} catch (e) {
  console.error("Could not register Cytoscape extension, likely already registered.", e);
}

// Memoize the component to prevent re-renders when props haven't changed.
export const E2ETraceCytoscapeGraph = memo(({ elements, stylesheet, layout, cyRef }) => {
  const containerRef = useRef(null);

  useEffect(() => {
    if (!containerRef.current) return;
    // Initialize Cytoscape instance
    const cy = cytoscape({
      container: containerRef.current,
      elements,
      style: stylesheet,
      layout,
      wheelSensitivity: 0.2,
      minZoom: 0.2,
      maxZoom: 2.5,
      pixelRatio: 'auto',
    });
    if (cyRef) cyRef.current = cy;
    // Add corporate-style background and border
    cy.on('render', () => {
      if (containerRef.current) {
        containerRef.current.style.background = 'linear-gradient(135deg, #f4f6fa 0%, #e9eef6 100%)';
        containerRef.current.style.border = '1.5px solid #d1d7e6';
        containerRef.current.style.borderRadius = '12px';
        containerRef.current.style.boxShadow = '0 2px 16px 0 rgba(40,60,90,0.08)';
      }
    });
    // Clean up on unmount
    return () => {
      cy.destroy();
      if (cyRef) cyRef.current = null;
    };
  }, [elements, stylesheet, layout, cyRef]);

  return (
    <div
      ref={containerRef}
      style={{
        width: '100%',
        height: '100%',
        background: 'linear-gradient(135deg, #f4f6fa 0%, #e9eef6 100%)',
        border: '1.5px solid #d1d7e6',
        borderRadius: '12px',
        boxShadow: '0 2px 16px 0 rgba(40,60,90,0.08)',
        transition: 'box-shadow 0.2s',
      }}
    />
  );
});

E2ETraceCytoscapeGraph.displayName = 'E2ETraceCytoscapeGraph';