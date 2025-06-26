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

    // Store tippy instances in a Map to manage them per element
    const tippyInstances = new Map();

    const makeTippy = (ele) => {
      const ref = ele.popperRef();
      const content = ele.data('tooltip');

      if (!ref || !content) return;
      
      let instance = tippyInstances.get(ele.id());
      if (!instance) {
        const dummyDomEle = document.createElement('div');
        dummyDomEle.innerHTML = content;

        instance = tippy(dummyDomEle, {
          getReferenceClientRect: ref.getBoundingClientRect,
          trigger: 'manual',
          content: () => dummyDomEle,
          arrow: true,
          placement: 'bottom',
          hideOnClick: false,
          interactive: true,
          appendTo: document.body,
        });
        tippyInstances.set(ele.id(), instance);
      }
      instance.show();
    };

    const destroyTippy = (ele) => {
      const instance = tippyInstances.get(ele.id());
      if (instance) {
        instance.destroy();
        tippyInstances.delete(ele.id());
      }
    };

    const onMouseOver = (e) => makeTippy(e.target);
    const onMouseOut = (e) => destroyTippy(e.target);
    const onDrag = (e) => destroyTippy(e.target); // Hide tooltip while dragging

    cy.on('mouseover', 'node, edge', onMouseOver);
    cy.on('mouseout', 'node, edge', onMouseOut);
    cy.on('drag', 'node', onDrag);

    // Cleanup on component unmount or when cyRef changes
    return () => {
      if (cy) {
        cy.removeListener('mouseover', 'node, edge', onMouseOver);
        cy.removeListener('mouseout', 'node, edge', onMouseOut);
        cy.removeListener('drag', 'node', onDrag);
      }
      // Destroy all remaining tippy instances
      tippyInstances.forEach(instance => instance.destroy());
      tippyInstances.clear();
    };
  }, [cyRef, elements]); // Rerun if cyRef or elements change to re-bind events

  return (
    <CytoscapeComponent
      elements={CytoscapeComponent.normalizeElements(elements)}
      stylesheet={stylesheet}
      style={{ width: '100%', height: '100%' }}
      cy={(cy) => {
        cyRef.current = cy;
      }}
      // Pass the layout object directly to the component for initialization.
      // The component will handle running the layout.
      layout={layout}
    />
  );
});

E2ETraceCytoscapeGraph.displayName = 'E2ETraceCytoscapeGraph';