import React, { useState } from 'react';
import './TreeNavigator.css';

/**
 * Tree Navigator Component for XState Visualizer
 * Displays hierarchical PLM node structure with expand/collapse
 */
export const TreeNavigator = ({ nodes = [], onNodeClick, selectedNodeId, theme = 'light' }) => {
  const [expandedNodes, setExpandedNodes] = useState(new Set());

  const toggleExpand = (nodeId) => {
    setExpandedNodes(prev => {
      const newSet = new Set(prev);
      if (newSet.has(nodeId)) {
        newSet.delete(nodeId);
      } else {
        newSet.add(nodeId);
      }
      return newSet;
    });
  };

  const renderTreeNode = (node, level = 0) => {
    const hasChildren = node.children && node.children.length > 0;
    const isExpanded = expandedNodes.has(node.id);
    const isSelected = selectedNodeId === node.id;

    return (
      <div key={node.id} className="tree-navigator__node-wrapper">
        <div
          className={`tree-navigator__node tree-navigator__node--level-${level} ${
            isSelected ? 'tree-navigator__node--selected' : ''
          }`}
          style={{ paddingLeft: `${level * 16 + 8}px` }}
          onClick={() => onNodeClick && onNodeClick(node)}
        >
          {hasChildren && (
            <button
              className={`tree-navigator__expand-btn ${
                isExpanded ? 'tree-navigator__expand-btn--expanded' : ''
              }`}
              onClick={(e) => {
                e.stopPropagation();
                toggleExpand(node.id);
              }}
              aria-label={isExpanded ? 'Collapse' : 'Expand'}
            >
              ▶
            </button>
          )}
          {!hasChildren && <span className="tree-navigator__spacer" />}
          
          <span 
            className={`tree-navigator__icon tree-navigator__icon--${node.type || 'default'}`}
            style={{ backgroundColor: node.color || getColorForType(node.type) }}
          />
          
          <span className="tree-navigator__label">{node.label || node.id}</span>
          
          {node.count !== undefined && (
            <span className="tree-navigator__badge">{node.count}</span>
          )}
        </div>

        {hasChildren && isExpanded && (
          <div className="tree-navigator__children">
            {node.children.map(child => renderTreeNode(child, level + 1))}
          </div>
        )}
      </div>
    );
  };

  return (
    <div className={`tree-navigator tree-navigator--${theme}`}>
      <div className="tree-navigator__search">
        <input
          type="text"
          className="tree-navigator__search-input"
          placeholder="Search nodes..."
        />
      </div>
      
      <div className="tree-navigator__content">
        {nodes.length > 0 ? (
          nodes.map(node => renderTreeNode(node))
        ) : (
          <div className="tree-navigator__empty">
            <span>No nodes available</span>
          </div>
        )}
      </div>
    </div>
  );
};

// Helper function to get color based on node type
const getColorForType = (type) => {
  const colorMap = {
    'Part': '#48a4ff',
    'Document': '#6e6fff',
    'Recipe': '#21d5c1',
    'Material': '#ffba5a',
    'Supplier': '#ff7077',
    'Batch': '#9b6cff',
    'BOM': '#4caf50',
    'Process': '#ff9800',
    'Database': '#4a90e2',
    'API': '#8e44ad',
    'default': '#95a5a6'
  };
  return colorMap[type] || colorMap['default'];
};

export default TreeNavigator;
