import React, { useEffect, memo } from 'react';
import CytoscapeComponent from 'react-cytoscapejs';
import cytoscape from 'cytoscape';

// Import and register extensions
import fcose from 'cytoscape-fcose';
import coseBilkent from 'cytoscape-cose-bilkent';
import expandCollapse from 'cytoscape-expand-collapse';
import popper from 'cytoscape-popper';
import tippy from 'tippy.js';
import 'tippy.js/dist/tippy.css';

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

  // Effect for Tooltip Management
  useEffect(() => {
    const cy = cyRef.current;
    if (!cy) return;

    // Use a single tippy instance for performance
    let tippyInstance;

    const makeTippy = (ele) => {
      const ref = ele.popperRef();
      const content = ele.data('tooltip');

      if (!ref || !content) return;

      // Destroy any existing tippy instance
      if (tippyInstance) {
        tippyInstance.destroy();
      }

      const dummyDomEle = document.createElement('div');
      dummyDomEle.innerHTML = content;

      tippyInstance = tippy(dummyDomEle, {
        getReferenceClientRect: ref.getBoundingClientRect,
        trigger: 'manual',
        content: () => dummyDomEle,
        arrow: true,
        placement: 'bottom',
        hideOnClick: false,
        interactive: true,
        appendTo: document.body,
      });

      tippyInstance.show();
    };

    const destroyTippy = () => {
      if (tippyInstance) {
        tippyInstance.destroy();
        tippyInstance = null;
      }
    };

    cy.on('mouseover', 'node, edge', (e) => makeTippy(e.target));
    cy.on('mouseout', 'node, edge', destroyTippy);
    cy.on('drag', 'node', destroyTippy); // Hide tooltip while dragging

    // Cleanup on component unmount or when cyRef changes
    return () => {
      if (cy) {
        cy.removeListener('mouseover');
        cy.removeListener('mouseout');
        cy.removeListener('drag');
      }
      destroyTippy();
    };
  }, [cyRef, elements]); // Rerun if cyRef or elements change to re-bind events

  // This effect handles running the layout and fitting the graph into view
  useEffect(() => {
    const cy = cyRef.current;
    if (cy && elements && elements.length > 0) {
      const layoutInstance = cy.layout(layout);
      layoutInstance.run();
    }
  }, [elements, layout, cyRef]); // Rerun when elements or layout config changes

  return (
    <CytoscapeComponent
      elements={CytoscapeComponent.normalizeElements(elements)}
      stylesheet={stylesheet}
      style={{ width: '100%', height: '100%' }}
      cy={(cy) => {
        cyRef.current = cy;
      }}
      // We run the layout manually in a useEffect for more control
      layout={{ name: 'preset' }} 
    />
  );
});

E2ETraceCytoscapeGraph.displayName = 'E2ETraceCytoscapeGraph';