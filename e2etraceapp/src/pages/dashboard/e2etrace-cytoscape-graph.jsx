import React, { useEffect, memo, useRef } from 'react';
import cytoscape from 'cytoscape';

import tippy from 'tippy.js';
import 'tippy.js/dist/tippy.css';

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
  const tippyRef = useRef(null);
  const popperRef = useRef(null);
  const expandCollapseApiRef = useRef(null);

  useEffect(() => {
    if (!containerRef.current) return;

    const escapeHtml = (value) => String(value)
      .replaceAll('&', '&amp;')
      .replaceAll('<', '&lt;')
      .replaceAll('>', '&gt;')
      .replaceAll('"', '&quot;')
      .replaceAll("'", '&#39;');

    const buildTooltipHtml = (ele) => {
      const kind = ele.isNode && ele.isNode() ? 'Node' : 'Edge';
      const label = ele.data('label') || ele.data('type') || ele.id();
      const group = ele.data('group') || ele.data('type') || '';
      const props = ele.data('properties') || {};

      let propsBlock = '';
      try {
        propsBlock = escapeHtml(JSON.stringify(props, null, 2));
      } catch {
        propsBlock = escapeHtml(String(props));
      }

      return [
        `<div class="cy-tooltip-title">${escapeHtml(kind)}: ${escapeHtml(label)}</div>`,
        group ? `<div class="cy-tooltip-subtitle">${escapeHtml(group)}</div>` : '',
        `<pre class="cy-tooltip-pre">${propsBlock}</pre>`,
      ].join('');
    };

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

    // Expand/collapse for compound nodes (if any)
    try {
      expandCollapseApiRef.current = cy.expandCollapse({
        layoutBy: layout,
        fisheye: true,
        animate: true,
        undoable: false,
      });
    } catch (e) {
      // If plugin isn't available, skip silently.
      expandCollapseApiRef.current = null;
    }

    // Tooltip: tippy.js anchored via cytoscape-popper
    const tip = tippy(document.createElement('div'), {
      content: '',
      trigger: 'manual',
      interactive: true,
      allowHTML: true,
      appendTo: document.body,
      placement: 'bottom',
    });
    tippyRef.current = tip;

    const hideTooltip = () => {
      try {
        tip.hide();
      } catch {
        // ignore
      }
      popperRef.current = null;
    };

    const showTooltipFor = (ele) => {
      if (!ele || ele.destroyed()) return;
      const ref = ele.popperRef && ele.popperRef();
      if (!ref) return;

      popperRef.current = ref;
      tip.setContent(buildTooltipHtml(ele));
      tip.setProps({
        getReferenceClientRect: ref.getBoundingClientRect,
      });
      tip.show();
    };

    const handleOver = (evt) => showTooltipFor(evt.target);
    const handleOut = () => hideTooltip();

    cy.on('mouseover', 'node, edge', handleOver);
    cy.on('mouseout', 'node, edge', handleOut);

    const handleViewportChange = () => {
      const ref = popperRef.current;
      if (!ref) return;
      try {
        tip.setProps({ getReferenceClientRect: ref.getBoundingClientRect });
      } catch {
        // ignore
      }
    };
    cy.on('pan zoom resize', handleViewportChange);

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
      cy.off('mouseover', 'node, edge', handleOver);
      cy.off('mouseout', 'node, edge', handleOut);
      cy.off('pan zoom resize', handleViewportChange);
      hideTooltip();

      if (tippyRef.current) {
        try {
          tippyRef.current.destroy();
        } catch {
          // ignore
        }
        tippyRef.current = null;
      }
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