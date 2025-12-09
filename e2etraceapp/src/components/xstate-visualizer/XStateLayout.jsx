import React, { useState } from 'react';
import './XStateLayout.css';

/**
 * XState-inspired 3-panel layout component
 * Left: Tree navigation | Center: Graph canvas | Right: Inspector panel
 * Bottom: Event log drawer
 */
export const XStateLayout = ({
  treePanel,
  graphPanel,
  inspectorPanel,
  eventPanel,
  theme = 'light'
}) => {
  const [leftPanelWidth, setLeftPanelWidth] = useState(220);
  const [rightPanelWidth, setRightPanelWidth] = useState(280);
  const [eventPanelHeight, setEventPanelHeight] = useState(150);
  const [isEventPanelOpen, setIsEventPanelOpen] = useState(false);

  return (
    <div className={`xstate-layout xstate-layout--${theme}`}>
      {/* Left Panel - Tree Navigation */}
      <div 
        className="xstate-layout__left-panel"
        style={{ width: `${leftPanelWidth}px` }}
      >
        <div className="xstate-layout__panel-header">
          <span className="xstate-layout__panel-title">Navigator</span>
        </div>
        <div className="xstate-layout__panel-content">
          {treePanel}
        </div>
      </div>

      {/* Left Resizer */}
      <div 
        className="xstate-layout__resizer xstate-layout__resizer--vertical"
        onMouseDown={(e) => {
          e.preventDefault();
          const startX = e.clientX;
          const startWidth = leftPanelWidth;

          const handleMouseMove = (e) => {
            const newWidth = Math.max(200, Math.min(500, startWidth + (e.clientX - startX)));
            setLeftPanelWidth(newWidth);
          };

          const handleMouseUp = () => {
            document.removeEventListener('mousemove', handleMouseMove);
            document.removeEventListener('mouseup', handleMouseUp);
          };

          document.addEventListener('mousemove', handleMouseMove);
          document.addEventListener('mouseup', handleMouseUp);
        }}
      />

      {/* Center Panel - Graph Canvas */}
      <div className="xstate-layout__center-panel">
        <div className="xstate-layout__panel-header">
          <span className="xstate-layout__panel-title">Graph Visualizer</span>
        </div>
        <div className="xstate-layout__panel-content">
          {graphPanel}
        </div>
      </div>

      {/* Right Resizer */}
      <div 
        className="xstate-layout__resizer xstate-layout__resizer--vertical"
        onMouseDown={(e) => {
          e.preventDefault();
          const startX = e.clientX;
          const startWidth = rightPanelWidth;

          const handleMouseMove = (e) => {
            const newWidth = Math.max(250, Math.min(600, startWidth - (e.clientX - startX)));
            setRightPanelWidth(newWidth);
          };

          const handleMouseUp = () => {
            document.removeEventListener('mousemove', handleMouseMove);
            document.removeEventListener('mouseup', handleMouseUp);
          };

          document.addEventListener('mousemove', handleMouseMove);
          document.addEventListener('mouseup', handleMouseUp);
        }}
      />

      {/* Right Panel - Inspector */}
      <div 
        className="xstate-layout__right-panel"
        style={{ width: `${rightPanelWidth}px` }}
      >
        <div className="xstate-layout__panel-header">
          <span className="xstate-layout__panel-title">Inspector</span>
        </div>
        <div className="xstate-layout__panel-content">
          {inspectorPanel}
        </div>
      </div>

      {/* Bottom Event Panel */}
      {isEventPanelOpen && (
        <>
          <div 
            className="xstate-layout__resizer xstate-layout__resizer--horizontal"
            onMouseDown={(e) => {
              e.preventDefault();
              const startY = e.clientY;
              const startHeight = eventPanelHeight;

              const handleMouseMove = (e) => {
                const newHeight = Math.max(150, Math.min(400, startHeight - (e.clientY - startY)));
                setEventPanelHeight(newHeight);
              };

              const handleMouseUp = () => {
                document.removeEventListener('mousemove', handleMouseMove);
                document.removeEventListener('mouseup', handleMouseUp);
              };

              document.addEventListener('mousemove', handleMouseMove);
              document.addEventListener('mouseup', handleMouseUp);
            }}
          />
          <div 
            className="xstate-layout__bottom-panel"
            style={{ height: `${eventPanelHeight}px` }}
          >
            <div className="xstate-layout__panel-header">
              <span className="xstate-layout__panel-title">Events & Actions</span>
              <button 
                className="xstate-layout__panel-close"
                onClick={() => setIsEventPanelOpen(false)}
                aria-label="Close event panel"
              >
                ×
              </button>
            </div>
            <div className="xstate-layout__panel-content">
              {eventPanel}
            </div>
          </div>
        </>
      )}

      {/* Toggle button when event panel is closed */}
      {!isEventPanelOpen && (
        <button
          className="xstate-layout__event-panel-toggle"
          onClick={() => setIsEventPanelOpen(true)}
          aria-label="Open event panel"
        >
          Events & Actions
        </button>
      )}
    </div>
  );
};

export default XStateLayout;
