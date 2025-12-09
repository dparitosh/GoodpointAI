import React, { useState } from 'react';
import './InspectorPanel.css';

/**
 * Inspector Panel Component for XState Visualizer
 * Displays and allows editing of node properties, metadata, and relationships
 */
export const InspectorPanel = ({ 
  selectedNode, 
  onPropertyChange,
  aiInsights = [],
  migrationHistory = [],
  theme = 'light' 
}) => {
  const [activeTab, setActiveTab] = useState('properties');
  const [editingField, setEditingField] = useState(null);

  if (!selectedNode) {
    return (
      <div className={`inspector-panel inspector-panel--${theme}`}>
        <div className="inspector-panel__empty">
          <div className="inspector-panel__empty-icon">◻</div>
          <p>Select a node to view details</p>
        </div>
      </div>
    );
  }

  const tabs = [
    { id: 'properties', label: 'Properties', icon: '⚙' },
    { id: 'relationships', label: 'Relationships', icon: '⛭' },
    { id: 'metadata', label: 'Metadata', icon: '✎' },
    { id: 'ai', label: 'AI Insights', icon: '✧' },
    { id: 'history', label: 'History', icon: '◰' }
  ];

  const handleFieldEdit = (field, value) => {
    if (onPropertyChange) {
      onPropertyChange(selectedNode.id, field, value);
    }
    setEditingField(null);
  };

  return (
    <div className={`inspector-panel inspector-panel--${theme}`}>
      {/* Node Header */}
      <div className="inspector-panel__header">
        <div 
          className="inspector-panel__node-icon"
          style={{ backgroundColor: selectedNode.color || '#48a4ff' }}
        />
        <div className="inspector-panel__header-info">
          <h3 className="inspector-panel__node-title">{selectedNode.label || selectedNode.id}</h3>
          <span className="inspector-panel__node-type">{selectedNode.type || 'Unknown'}</span>
        </div>
      </div>

      {/* Tabs */}
      <div className="inspector-panel__tabs">
        {tabs.map(tab => (
          <button
            key={tab.id}
            className={`inspector-panel__tab ${
              activeTab === tab.id ? 'inspector-panel__tab--active' : ''
            }`}
            onClick={() => setActiveTab(tab.id)}
          >
            <span className="inspector-panel__tab-icon">{tab.icon}</span>
            <span className="inspector-panel__tab-label">{tab.label}</span>
          </button>
        ))}
      </div>

      {/* Tab Content */}
      <div className="inspector-panel__content">
        {activeTab === 'properties' && (
          <div className="inspector-panel__section">
            <h4 className="inspector-panel__section-title">Properties</h4>
            <div className="inspector-panel__properties">
              {Object.entries(selectedNode.properties || {}).map(([key, value]) => (
                <div key={key} className="inspector-panel__property">
                  <label className="inspector-panel__property-label">{key}</label>
                  {editingField === key ? (
                    <input
                      type="text"
                      className="inspector-panel__property-input"
                      defaultValue={value}
                      onBlur={(e) => handleFieldEdit(key, e.target.value)}
                      onKeyPress={(e) => {
                        if (e.key === 'Enter') {
                          handleFieldEdit(key, e.target.value);
                        }
                      }}
                      autoFocus
                    />
                  ) : (
                    <div 
                      className="inspector-panel__property-value"
                      onClick={() => setEditingField(key)}
                    >
                      {String(value)}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {activeTab === 'relationships' && (
          <div className="inspector-panel__section">
            <h4 className="inspector-panel__section-title">Relationships</h4>
            <div className="inspector-panel__relationships">
              {selectedNode.relationships && selectedNode.relationships.length > 0 ? (
                selectedNode.relationships.map((rel, index) => (
                  <div key={index} className="inspector-panel__relationship">
                    <div className="inspector-panel__relationship-type">{rel.type}</div>
                    <div className="inspector-panel__relationship-target">→ {rel.target}</div>
                  </div>
                ))
              ) : (
                <div className="inspector-panel__empty-state">No relationships found</div>
              )}
            </div>
          </div>
        )}

        {activeTab === 'metadata' && (
          <div className="inspector-panel__section">
            <h4 className="inspector-panel__section-title">Metadata</h4>
            <div className="inspector-panel__metadata">
              <div className="inspector-panel__meta-item">
                <span className="inspector-panel__meta-label">ID:</span>
                <span className="inspector-panel__meta-value">{selectedNode.id}</span>
              </div>
              <div className="inspector-panel__meta-item">
                <span className="inspector-panel__meta-label">Type:</span>
                <span className="inspector-panel__meta-value">{selectedNode.type}</span>
              </div>
              <div className="inspector-panel__meta-item">
                <span className="inspector-panel__meta-label">Group:</span>
                <span className="inspector-panel__meta-value">{selectedNode.group || 'N/A'}</span>
              </div>
              {selectedNode.created && (
                <div className="inspector-panel__meta-item">
                  <span className="inspector-panel__meta-label">Created:</span>
                  <span className="inspector-panel__meta-value">{selectedNode.created}</span>
                </div>
              )}
              {selectedNode.modified && (
                <div className="inspector-panel__meta-item">
                  <span className="inspector-panel__meta-label">Modified:</span>
                  <span className="inspector-panel__meta-value">{selectedNode.modified}</span>
                </div>
              )}
            </div>
          </div>
        )}

        {activeTab === 'ai' && (
          <div className="inspector-panel__section">
            <h4 className="inspector-panel__section-title">AI Insights</h4>
            <div className="inspector-panel__ai-insights">
              {aiInsights.length > 0 ? (
                aiInsights.map((insight, index) => (
                  <div key={index} className="inspector-panel__ai-insight">
                    <div className="inspector-panel__ai-insight-header">
                      <span className="inspector-panel__ai-insight-type">{insight.type}</span>
                      <span className="inspector-panel__ai-insight-confidence">
                        {Math.round(insight.confidence * 100)}%
                      </span>
                    </div>
                    <p className="inspector-panel__ai-insight-text">{insight.text}</p>
                  </div>
                ))
              ) : (
                <div className="inspector-panel__empty-state">
                  <span>◈ No AI insights available</span>
                  <button className="inspector-panel__generate-btn">Generate Insights</button>
                </div>
              )}
            </div>
          </div>
        )}

        {activeTab === 'history' && (
          <div className="inspector-panel__section">
            <h4 className="inspector-panel__section-title">Migration History</h4>
            <div className="inspector-panel__history">
              {migrationHistory.length > 0 ? (
                migrationHistory.map((event, index) => (
                  <div key={index} className="inspector-panel__history-item">
                    <div className="inspector-panel__history-timestamp">{event.timestamp}</div>
                    <div className="inspector-panel__history-event">{event.event}</div>
                    <div className="inspector-panel__history-details">{event.details}</div>
                  </div>
                ))
              ) : (
                <div className="inspector-panel__empty-state">No history available</div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default InspectorPanel;
