import React from 'react';
import './e2etrace-widget.css';

const Widget = ({ 
  title, 
  children, 
  className = '', 
  headerActions,
  loading = false,
  error = null,
  fullHeight = false,
  collapsible = false,
  initialCollapsed = false
}) => {
  const [collapsed, setCollapsed] = React.useState(initialCollapsed);

  return (
    <div className={`widget ${className} ${fullHeight ? 'full-height' : ''} ${collapsed ? 'collapsed' : ''}`}>
      {title && (
        <div className="widget-header">
          <div className="widget-title">
            {title}
            {loading && <span className="widget-loading">Loading...</span>}
          </div>
          <div className="widget-header-actions">
            {headerActions}
            {collapsible && (
              <button 
                className="widget-collapse-btn"
                onClick={() => setCollapsed(!collapsed)}
                title={collapsed ? 'Expand' : 'Collapse'}
              >
                {collapsed ? '▼' : '▲'}
              </button>
            )}
          </div>
        </div>
      )}
      
      {!collapsed && (
        <div className="widget-content">
          {error ? (
            <div className="widget-error">
              <div className="error-icon">!</div>
              <div className="error-message">{error}</div>
            </div>
          ) : (
            children
          )}
        </div>
      )}
    </div>
  );
};

export default Widget;
