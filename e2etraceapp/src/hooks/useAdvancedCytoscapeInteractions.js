import { useEffect, useRef } from 'react';

/**
 * Custom hook for advanced cytoscape interactions
 * Implements XState-like interaction patterns
 */
export const useAdvancedCytoscapeInteractions = (cyRef, options = {}) => {
  const {
    onNodeDoubleClick,
    onMultiSelect,
    onCanvasPan,
    enableSmartSnapping = true
  } = options;

  const selectedNodesRef = useRef(new Set());
  const lastClickTimeRef = useRef(0);
  const isCtrlPressedRef = useRef(false);
  const isShiftPressedRef = useRef(false);

  useEffect(() => {
    if (!cyRef.current) return;
    const cy = cyRef.current;

    // Track keyboard modifiers
    const handleKeyDown = (e) => {
      if (e.key === 'Control' || e.key === 'Meta') {
        isCtrlPressedRef.current = true;
      }
      if (e.key === 'Shift') {
        isShiftPressedRef.current = true;
      }
    };

    const handleKeyUp = (e) => {
      if (e.key === 'Control' || e.key === 'Meta') {
        isCtrlPressedRef.current = false;
      }
      if (e.key === 'Shift') {
        isShiftPressedRef.current = false;
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    window.addEventListener('keyup', handleKeyUp);

    // Double-click detection
    const handleNodeTap = (evt) => {
      const node = evt.target;
      const now = Date.now();
      const timeSinceLastClick = now - lastClickTimeRef.current;

      if (timeSinceLastClick < 300) {
        // Double click detected
        if (onNodeDoubleClick) {
          onNodeDoubleClick(node.data());
        }
        // Animate expansion effect
        node.animate({
          style: {
            width: node.style('width') * 1.2,
            height: node.style('height') * 1.2
          },
          duration: 200,
          complete: () => {
            node.animate({
              style: {
                width: node.style('width') / 1.2,
                height: node.style('height') / 1.2
              },
              duration: 200
            });
          }
        });
      }

      lastClickTimeRef.current = now;

      // Ctrl+Click for multi-select
      if (isCtrlPressedRef.current) {
        if (node.selected()) {
          selectedNodesRef.current.delete(node.id());
        } else {
          selectedNodesRef.current.add(node.id());
        }
        
        if (onMultiSelect) {
          onMultiSelect(Array.from(selectedNodesRef.current));
        }
      } else if (!isShiftPressedRef.current) {
        selectedNodesRef.current.clear();
        selectedNodesRef.current.add(node.id());
      }
    };

    // Shift+Drag for canvas panning
    let isPanning = false;
    let panStartPosition = null;

    const handleMouseDown = (evt) => {
      if (isShiftPressedRef.current && evt.target === cy) {
        isPanning = true;
        panStartPosition = evt.position;
        cy.userPanningEnabled(false);
      }
    };

    const handleMouseMove = (evt) => {
      if (isPanning && panStartPosition) {
        const delta = {
          x: evt.position.x - panStartPosition.x,
          y: evt.position.y - panStartPosition.y
        };
        
        cy.panBy(delta);
        panStartPosition = evt.position;

        if (onCanvasPan) {
          onCanvasPan(cy.pan());
        }
      }
    };

    const handleMouseUp = () => {
      if (isPanning) {
        isPanning = false;
        panStartPosition = null;
        cy.userPanningEnabled(true);
      }
    };

    // Smart snapping for node positioning
    if (enableSmartSnapping) {
      let draggedNode = null;
      const snapThreshold = 20; // pixels

      const handleNodeDragStart = (evt) => {
        draggedNode = evt.target;
      };

      const handleNodeDrag = (evt) => {
        if (!draggedNode) return;

        const draggedPos = draggedNode.position();
        const allNodes = cy.nodes().not(draggedNode);

        // Find nearby nodes for snapping
        allNodes.forEach(node => {
          const nodePos = node.position();
          const dx = Math.abs(draggedPos.x - nodePos.x);
          const dy = Math.abs(draggedPos.y - nodePos.y);

          // Snap to X alignment
          if (dx < snapThreshold && dy > snapThreshold) {
            draggedNode.position('x', nodePos.x);
            // Visual feedback
            flashSnapGuide(cy, nodePos.x, 'vertical');
          }

          // Snap to Y alignment
          if (dy < snapThreshold && dx > snapThreshold) {
            draggedNode.position('y', nodePos.y);
            // Visual feedback
            flashSnapGuide(cy, nodePos.y, 'horizontal');
          }
        });
      };

      const handleNodeDragEnd = () => {
        draggedNode = null;
      };

      cy.on('grab', 'node', handleNodeDragStart);
      cy.on('drag', 'node', handleNodeDrag);
      cy.on('free', 'node', handleNodeDragEnd);
    }

    // Register event listeners
    cy.on('tap', 'node', handleNodeTap);
    cy.on('mousedown', handleMouseDown);
    cy.on('mousemove', handleMouseMove);
    cy.on('mouseup', handleMouseUp);

    // Cleanup
    return () => {
      window.removeEventListener('keydown', handleKeyDown);
      window.removeEventListener('keyup', handleKeyUp);
      
      if (cy) {
        cy.off('tap', 'node', handleNodeTap);
        cy.off('mousedown', handleMouseDown);
        cy.off('mousemove', handleMouseMove);
        cy.off('mouseup', handleMouseUp);
        
        if (enableSmartSnapping) {
          cy.off('grab', 'node');
          cy.off('drag', 'node');
          cy.off('free', 'node');
        }
      }
    };
  }, [cyRef, onNodeDoubleClick, onMultiSelect, onCanvasPan, enableSmartSnapping]);

  return {
    selectedNodes: Array.from(selectedNodesRef.current)
  };
};

// Helper function to show snap guides
function flashSnapGuide(cy, position, orientation) {
  // This would create a temporary visual guide line
  // Implementation depends on how you want to render the guide
  // For now, we'll just use a simple console log
  console.log(`Snap guide: ${orientation} at ${position}`);
}

export default useAdvancedCytoscapeInteractions;
