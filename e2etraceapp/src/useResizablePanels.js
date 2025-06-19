import { useEffect } from 'react';

export function useResizablePanels(leftPanelRef, rightPanelRef, resizerRef, mainAreaRef, cyRef) {
  useEffect(() => {
    const resizer = resizerRef.current;
    const leftPanel = leftPanelRef.current;
    const rightPanel = rightPanelRef.current;
    const mainArea = mainAreaRef.current;

    if (!resizer || !leftPanel || !rightPanel || !mainArea) {
      console.warn('[useResizablePanels] Resizable panel elements not found. Ensure refs are correctly assigned.');
      return;
    }

    let isResizing = false;

    const onMouseDown = (e) => {
      isResizing = true;
      e.preventDefault(); // Prevent text selection during resize
      document.body.style.cursor = 'col-resize';
      document.body.style.userSelect = 'none';

      const startX = e.clientX;
      const initialLeftWidth = leftPanel.offsetWidth;

      const onMouseMove = (moveEvent) => {
        if (!isResizing) return;
        const dx = moveEvent.clientX - startX;
        let newLeftWidth = initialLeftWidth + dx;
        const containerWidth = mainArea.offsetWidth - resizer.offsetWidth;
        const minPanelWidth = 150; // Minimum width for panels

        newLeftWidth = Math.max(minPanelWidth, newLeftWidth);
        newLeftWidth = Math.min(newLeftWidth, containerWidth - minPanelWidth);

        leftPanel.style.flex = `0 0 ${newLeftWidth}px`;
        rightPanel.style.flex = `1 1 auto`;

        if (cyRef && cyRef.current) {
          requestAnimationFrame(() => {
            if (cyRef.current) cyRef.current.resize();
          });
        }
      };

      const onMouseUp = () => {
        if (!isResizing) return;
        isResizing = false;
        document.body.style.cursor = '';
        document.body.style.userSelect = '';
        document.removeEventListener('mousemove', onMouseMove);
        document.removeEventListener('mouseup', onMouseUp);

        if (cyRef && cyRef.current) {
          requestAnimationFrame(() => {
            if (cyRef.current) cyRef.current.resize();
          });
        }
      };

      document.addEventListener('mousemove', onMouseMove);
      document.addEventListener('mouseup', onMouseUp);
    };

    resizer.addEventListener('mousedown', onMouseDown);

    return () => {
      resizer.removeEventListener('mousedown', onMouseDown);
      document.body.style.cursor = ''; // Reset cursor on unmount
      document.body.style.userSelect = ''; // Reset userSelect on unmount
    };
  }, [leftPanelRef, rightPanelRef, resizerRef, mainAreaRef, cyRef]);
}