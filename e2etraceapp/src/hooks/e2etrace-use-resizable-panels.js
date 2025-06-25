import { useEffect } from "react";

export function e2etraceUseResizablePanels(
  leftPanelRef,
  rightPanelRef,
  resizerRef,
  mainContentAreaRef,
  cyRef,
  isActive // New prop to indicate if the panel is active
) {
  useEffect(() => {
    const resizer = resizerRef.current;
    const leftPanel = leftPanelRef.current;
    const rightPanel = rightPanelRef.current;
    const mainArea = mainContentAreaRef.current;
    const cy = cyRef.current;

    const cleanup = () => {
      if (resizer) {
        resizer.removeEventListener("mousedown", onMouseDown); // Ensure listener is removed
        delete resizer._has_listeners; // Clean up custom flag
      }
      // Also remove global mousemove/mouseup listeners if they are active
      document.removeEventListener("mousemove", onMouseMove);
      document.removeEventListener("mouseup", onMouseUp);
      console.log("[useResizablePanels] Cleaned up resizable panel listeners.");
    };

    // Only proceed if the panel is active and all necessary DOM elements and Cytoscape instance are available
    // Crucially, check for `rightPanel` here as well.
    if (!isActive || !resizer || !leftPanel || !rightPanel || !mainArea || !cy) {
      // If conditions are not met, ensure any existing listeners are removed.
      // This handles cases where isActive becomes false, or refs become null (e.g., component unmounts).
      if (resizer && resizer._has_listeners) { // Check if listeners were previously attached
        cleanup(); // Perform cleanup if listeners were active
      }
      console.warn(
        "[useResizablePanels] Resizable panel elements not found or panel is not active. Skipping resize setup."
      );
      return; // No cleanup function needed if listeners weren't attached or already cleaned.
    }

    // Attach listeners only if they haven't been attached for this resizer instance
    if (!resizer._has_listeners) { // Use a custom property on the DOM element to track
      console.log("[useResizablePanels] Attaching resizable panel listeners.");
      resizer.addEventListener("mousedown", onMouseDown);
      resizer._has_listeners = true; // Mark as having listeners
    }

    let isResizing = false;

    const onMouseDown = (e) => {
      e.preventDefault();
      isResizing = true;
      document.body.style.cursor = "col-resize";
      document.body.style.userSelect = "none";

      const startX = e.clientX;
      const initialLeftWidth = leftPanel.offsetWidth;

      const onMouseMove = (moveEvent) => {
        if (!isResizing) return;

        const newLeftWidth = initialLeftWidth + (moveEvent.clientX - startX);

        // Prevent panels from becoming too small
        const minWidth = Math.max(100, mainArea.offsetWidth * 0.1); // At least 100px or 10%
        const maxLeftWidth = mainArea.offsetWidth - minWidth; // Max left width is total - min right

        if (newLeftWidth < minWidth || newLeftWidth > maxLeftWidth) {
          return; // Stop if trying to go too small
        }

        // Use requestAnimationFrame to avoid layout thrashing
        requestAnimationFrame(() => {
          leftPanel.style.width = `${newLeftWidth}px`; // Update width
          cy.resize(); // Ensure Cytoscape resizes to the new width
        });
      };

      const onMouseUp = () => {
        isResizing = false;
        document.body.style.cursor = "";
        document.body.style.userSelect = "";
        document.removeEventListener("mousemove", onMouseMove);
        document.removeEventListener("mouseup", onMouseUp);
      };

      document.addEventListener("mousemove", onMouseMove);
      document.addEventListener("mouseup", onMouseUp);
    };

    // Cleanup function for useEffect
    return cleanup;
  }, [leftPanelRef, rightPanelRef, resizerRef, mainContentAreaRef, cyRef, isActive]); // Dependencies
}