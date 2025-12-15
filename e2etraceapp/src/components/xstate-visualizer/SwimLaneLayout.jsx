import React, { useMemo } from 'react';
import './SwimLaneLayout.css';

/**
 * Swim Lane Layout Component
 * Displays workflow stages as horizontal lanes with nodes positioned within stages
 */
export const SwimLaneLayout = ({ nodes, edges, selectedNode, onNodeClick }) => {
  // Define workflow stages (swim lanes)
  const stages = useMemo(() => [
    { id: 'source', label: 'Data Sources', color: '#0078D4', order: 1 },
    { id: 'extract', label: 'Extract', color: '#48a4ff', order: 2 },
    { id: 'transform', label: 'Transform', color: '#21d5c1', order: 3 },
    { id: 'quality', label: 'Quality Check', color: '#ffba5a', order: 4 },
    { id: 'load', label: 'Load', color: '#24A148', order: 5 },
    { id: 'target', label: 'Target Systems', color: '#6e6fff', order: 6 }
  ], []);

  // Assign nodes to swim lanes based on their type/stage
  const nodesByStage = useMemo(() => {
    const grouped = {};
    stages.forEach(stage => {
      grouped[stage.id] = [];
    });

    nodes.forEach(node => {
      const type = (node.type || node.group || '').toLowerCase();
      const label = (node.label || '').toLowerCase();
      
      // Determine stage based on node type/properties
      let stageId = 'source'; // default
      
      if (type.includes('database') || type.includes('csv') || type.includes('json') || type.includes('xml')) {
        stageId = 'source';
      } else if (type.includes('extract') || label.includes('extract')) {
        stageId = 'extract';
      } else if (type.includes('transform') || type.includes('etl') || label.includes('transform') || label.includes('mapper')) {
        stageId = 'transform';
      } else if (type.includes('quality') || type.includes('validation') || label.includes('quality') || label.includes('validate')) {
        stageId = 'quality';
      } else if (type.includes('load') || label.includes('load')) {
        stageId = 'load';
      } else if (type.includes('neo4j') || type.includes('api') || type.includes('service') || label.includes('target')) {
        stageId = 'target';
      }

      grouped[stageId].push(node);
    });

    return grouped;
  }, [nodes, stages]);

  // Calculate detailed connections for visualization
  const flowConnections = useMemo(() => {
    const connections = [];
    
    edges.forEach(edge => {
      const sourceNode = nodes.find(n => n.id === edge.source);
      const targetNode = nodes.find(n => n.id === edge.target);
      
      if (sourceNode && targetNode) {
        const sourceStage = Object.keys(nodesByStage).find(stage => 
          nodesByStage[stage].some(n => n.id === sourceNode.id)
        );
        const targetStage = Object.keys(nodesByStage).find(stage => 
          nodesByStage[stage].some(n => n.id === targetNode.id)
        );
        
        if (sourceStage && targetStage) {
          connections.push({
            id: edge.id || `${edge.source}-${edge.target}`,
            source: edge.source,
            target: edge.target,
            sourceNode,
            targetNode,
            sourceStage,
            targetStage,
            label: edge.label || edge.type,
            type: edge.type,
            weight: edge.weight || 1
          });
        }
      }
    });

    return connections;
  }, [edges, nodes, nodesByStage]);

  // Calculate stage-to-stage flow lines
  const stageFlowLines = useMemo(() => {
    const lines = new Map();
    
    flowConnections.forEach(conn => {
      const key = `${conn.sourceStage}-${conn.targetStage}`;
      if (!lines.has(key)) {
        lines.set(key, {
          from: conn.sourceStage,
          to: conn.targetStage,
          count: 0,
          connections: []
        });
      }
      const line = lines.get(key);
      line.count++;
      line.connections.push(conn);
    });

    return Array.from(lines.values());
  }, [flowConnections]);

  const getNodeIcon = (node) => {
    const type = (node.type || '').toLowerCase();
    if (type.includes('database')) return '▦';
    if (type.includes('csv')) return '◳';
    if (type.includes('json')) return '◻';
    if (type.includes('xml')) return '◰';
    if (type.includes('etl')) return '⚙';
    if (type.includes('transform')) return '↻';
    if (type.includes('api')) return '⚭';
    if (type.includes('quality')) return '✓';
    if (type.includes('neo4j')) return '◆';
    return '◻';
  };

  const getStatusClass = (node) => {
    const status = node.status || 'default';
    return `swimlane-node-status-${status}`;
  };

  return (
    <div className="swimlane-container">
      <div className="swimlane-header">
        <h3>ETL Workflow Pipeline - Interactive State Flow</h3>
        <div className="swimlane-stats">
          <span className="stat">
            <span className="stat-label">Total Nodes:</span>
            <span className="stat-value">{nodes.length}</span>
          </span>
          <span className="stat">
            <span className="stat-label">Connections:</span>
            <span className="stat-value">{edges.length}</span>
          </span>
          <span className="stat">
            <span className="stat-label">Stages:</span>
            <span className="stat-value">{stages.length}</span>
          </span>
          <span className="stat">
            <span className="stat-label">Flow Lines:</span>
            <span className="stat-value">{stageFlowLines.length}</span>
          </span>
        </div>
      </div>

      <div className="swimlane-wrapper">
        {/* Stage Flow Indicators */}
        <div className="stage-flow-indicators">
          {stages.map((stage, idx) => (
            <React.Fragment key={stage.id}>
              <div className="stage-indicator" style={{ backgroundColor: stage.color }}>
                <span className="stage-indicator-label">{stage.label}</span>
              </div>
              {idx < stages.length - 1 && (
                <div className="stage-flow-arrow">
                  <div className="flow-line"></div>
                  <div className="flow-arrow">➜</div>
                  <div className="flow-count">
                    {stageFlowLines.find(l => 
                      stages[idx].id === l.from && stages[idx + 1].id === l.to
                    )?.count || 0}
                  </div>
                </div>
              )}
            </React.Fragment>
          ))}
        </div>

        <div className="swimlane-stages">
        {stages.map(stage => (
          <div key={stage.id} className="swimlane-stage" data-stage={stage.id}>
            <div className="swimlane-stage-header" style={{ backgroundColor: stage.color }}>
              <span className="stage-label">{stage.label}</span>
              <span className="stage-count">{nodesByStage[stage.id]?.length || 0}</span>
            </div>
            
            <div className="swimlane-stage-content">
              {nodesByStage[stage.id]?.map((node, idx) => (
                <div
                  key={node.id}
                  className={`swimlane-node ${selectedNode?.id === node.id ? 'selected' : ''} ${getStatusClass(node)}`}
                  onClick={() => onNodeClick?.(node)}
                  style={{
                    backgroundColor: node.backgroundColor || stage.color,
                    animationDelay: `${idx * 0.1}s`
                  }}
                >
                  <div className="swimlane-node-icon">{getNodeIcon(node)}</div>
                  <div className="swimlane-node-content">
                    <div className="swimlane-node-label">{node.label || node.id}</div>
                    {node.properties && (
                      <div className="swimlane-node-meta">
                        {Object.entries(node.properties).slice(0, 2).map(([key, value]) => (
                          <span key={key} className="meta-item">
                            {key}: {value}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                  {node.status && (
                    <div className={`swimlane-node-status-indicator status-${node.status}`}>
                      {node.status === 'healthy' && '✓'}
                      {node.status === 'warning' && '!'}
                      {node.status === 'error' && '✗'}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
      </div>

      {/* Interactive Flow Connections */}
      <div className="swimlane-flow-details">
        <h4>Active Data Flows ({flowConnections.length})</h4>
        <div className="flow-connections-list">
          {flowConnections.slice(0, 10).map((conn) => (
            <div 
              key={conn.id} 
              className={`flow-connection-item ${
                selectedNode?.id === conn.source || selectedNode?.id === conn.target ? 'highlighted' : ''
              }`}
              onClick={() => {
                if (onNodeClick) {
                  onNodeClick(selectedNode?.id === conn.source ? conn.targetNode : conn.sourceNode);
                }
              }}
            >
              <div className="flow-source">
                {getNodeIcon(conn.sourceNode)} {conn.sourceNode.label}
              </div>
              <div className="flow-arrow-label">
                <div className="flow-type">{conn.label || conn.type}</div>
                <div className="flow-arrow-icon">→</div>
              </div>
              <div className="flow-target">
                {getNodeIcon(conn.targetNode)} {conn.targetNode.label}
              </div>
            </div>
          ))}
          {flowConnections.length > 10 && (
            <div className="flow-more">
              +{flowConnections.length - 10} more connections
            </div>
          )}
        </div>
      </div>

      {/* SVG Connection Lines Overlay */}
      <svg className="swimlane-connections-svg" aria-hidden="true">
        <defs>
          <marker
            id="arrowhead-swimlane"
            markerWidth="10"
            markerHeight="10"
            refX="9"
            refY="3"
            orient="auto"
          >
            <polygon points="0 0, 10 3, 0 6" fill="#0078D4" opacity="0.6" />
          </marker>
          <filter id="glow">
            <feGaussianBlur stdDeviation="2" result="coloredBlur"/>
            <feMerge>
              <feMergeNode in="coloredBlur"/>
              <feMergeNode in="SourceGraphic"/>
            </feMerge>
          </filter>
        </defs>
        {/* Draw connections between selected node and related nodes */}
        {selectedNode && flowConnections
          .filter(conn => conn.source === selectedNode.id || conn.target === selectedNode.id)
          .map((conn, idx) => (
            <g key={conn.id}>
              <line
                x1="20%"
                y1={`${(idx + 1) * 10}%`}
                x2="80%"
                y2={`${(idx + 1) * 10}%`}
                stroke="#0078D4"
                strokeWidth="2"
                strokeDasharray="5,5"
                opacity="0.6"
                markerEnd="url(#arrowhead-swimlane)"
                filter="url(#glow)"
                className="connection-line-animated"
              />
            </g>
          ))
        }
      </svg>
    </div>
  );
};
