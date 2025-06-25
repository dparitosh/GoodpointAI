import { useEffect } from "react";

export function e2etraceUseResizablePanels(
  leftPanelRef,
  rightPanelRef,
  resizerRef,
  mainAreaRef,
  cyRef
) {
  useEffect(() => {
    const resizer = resizerRef.current;
    const leftPanel = leftPanelRef.current;
    const rightPanel = rightPanelRef.current;
    const mainArea = mainAreaRef.current;

    if (!resizer || !leftPanel || !rightPanel || !mainArea || !cyRef) {
      console.warn(
        "[useResizablePanels] Resizable panel elements not found. Ensure refs are correctly assigned."
      );
      return;
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

        // Use requestAnimationFrame to avoid layout thrashing
        requestAnimationFrame(() => {
          leftPanel.style.width = `${newLeftWidth}px`;
          if (cyRef.current) {
            cyRef.current.resize();
          }
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

    resizer.addEventListener("mousedown", onMouseDown);

    return () => {
      resizer.removeEventListener("mousedown", onMouseDown);
    };
  }, [leftPanelRef, rightPanelRef, resizerRef, mainAreaRef, cyRef]);
}