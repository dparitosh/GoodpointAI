import React, { useEffect } from 'react';
import './DetailDrawer.css';

/**
 * Detail Drawer Component
 * Slides in from the right when a node is double-clicked
 */
export const DetailDrawer = ({ node, isOpen, onClose, theme = 'light' }) => {
  // Close drawer on Escape key
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape' && isOpen) {
        onClose();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen || !node) return null;

  return (
    <>
      {/* Backdrop */}
      <div 
        className={`detail-drawer__backdrop detail-drawer__backdrop--${theme}`}
        onClick={onClose}
      />

      {/* Drawer */}
      <div className={`detail-drawer detail-drawer--${theme} detail-drawer--open`}>
        {/* Header */}
        <div className="detail-drawer__header">
          <div className="detail-drawer__header-content">
            <div 
              className="detail-drawer__node-icon"
              style={{ backgroundColor: node.color || '#48a4ff' }}
            />
            <div className="detail-drawer__header-text">
              <h2 className="detail-drawer__title">{node.label || node.id}</h2>
              <span className="detail-drawer__subtitle">{node.type || 'Node'}</span>
            </div>
          </div>
          <button 
            className="detail-drawer__close-btn"
            onClick={onClose}
            aria-label="Close drawer"
          >
            ×
          </button>
        </div>

        {/* Content */}
        <div className="detail-drawer__content">
          {/* Overview Section */}
          <section className="detail-drawer__section">
            <h3 className="detail-drawer__section-title">Overview</h3>
            <div className="detail-drawer__info-grid">
              <div className="detail-drawer__info-item">
                <span className="detail-drawer__info-label">ID</span>
                <span className="detail-drawer__info-value">{node.id}</span>
              </div>
              <div className="detail-drawer__info-item">
                <span className="detail-drawer__info-label">Type</span>
                <span className="detail-drawer__info-value">{node.type}</span>
              </div>
              {node.group && (
                <div className="detail-drawer__info-item">
                  <span className="detail-drawer__info-label">Group</span>
                  <span className="detail-drawer__info-value">{node.group}</span>
                </div>
              )}
              {node.status && (
                <div className="detail-drawer__info-item">
                  <span className="detail-drawer__info-label">Status</span>
                  <span className={`detail-drawer__status detail-drawer__status--${node.status}`}>
                    {node.status}
                  </span>
                </div>
              )}
            </div>
          </section>

          {/* Properties Section */}
          {node.properties && Object.keys(node.properties).length > 0 && (
            <section className="detail-drawer__section">
              <h3 className="detail-drawer__section-title">Properties</h3>
              <div className="detail-drawer__properties">
                {Object.entries(node.properties).map(([key, value]) => (
                  <div key={key} className="detail-drawer__property">
                    <span className="detail-drawer__property-key">{key}</span>
                    <span className="detail-drawer__property-value">{String(value)}</span>
                  </div>
                ))}
              </div>
            </section>
          )}

          {/* Relationships Section */}
          {node.relationships && node.relationships.length > 0 && (
            <section className="detail-drawer__section">
              <h3 className="detail-drawer__section-title">Relationships</h3>
              <div className="detail-drawer__relationships">
                {node.relationships.map((rel, index) => (
                  <div key={index} className="detail-drawer__relationship">
                    <span className="detail-drawer__relationship-icon">
                      {rel.direction === 'outgoing' ? '→' : '←'}
                    </span>
                    <div className="detail-drawer__relationship-content">
                      <span className="detail-drawer__relationship-type">{rel.type}</span>
                      <span className="detail-drawer__relationship-target">{rel.target}</span>
                    </div>
                  </div>
                ))}
              </div>
            </section>
          )}

          {/* Actions Section */}
          <section className="detail-drawer__section">
            <h3 className="detail-drawer__section-title">Actions</h3>
            <div className="detail-drawer__actions">
              <button className="detail-drawer__action-btn detail-drawer__action-btn--primary">
                Edit Properties
              </button>
              <button className="detail-drawer__action-btn">
                View History
              </button>
              <button className="detail-drawer__action-btn">
                Export Data
              </button>
              <button className="detail-drawer__action-btn detail-drawer__action-btn--danger">
                Delete Node
              </button>
            </div>
          </section>
        </div>
      </div>
    </>
  );
};

export default DetailDrawer;
