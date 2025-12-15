/**
 * Data Lineage Visualizer
 * ===========================
 * 
 * Interactive data lineage visualization with:
 * - Real-time lineage graph rendering
 * - Upstream/downstream tracing
 * - Impact analysis simulation
 * - Audit trail explorer
 * - Compliance reporting
 * 
 * Features:
 * - Pan/zoom graph navigation
 * - Node filtering by type
 * - Relationship highlighting
 * - Export to PDF/PNG
 */

import React, { useState, useEffect, useCallback } from 'react';
import ReactFlow, {
  MiniMap,
  Controls,
  Background,
  useNodesState,
  useEdgesState,
  addEdge,
  Panel
} from 'reactflow';
import 'reactflow/dist/style.css';
import './LineageVisualizerPage.css';

const nodeTypes = {
  SOURCE_SYSTEM: { color: '#3b82f6', icon: '▦' },
  TARGET_SYSTEM: { color: '#10b981', icon: '◎' },
  TRANSFORMATION: { color: '#f59e0b', icon: '⚙' },
  VALIDATION: { color: '#8b5cf6', icon: '✓' },
  AGENT: { color: '#ef4444', icon: '✧' },
  DATA_RECORD: { color: '#6366f1', icon: '◳' }
};

const LineageVisualizerPage = () => {
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [workflowId, setWorkflowId] = useState('');
  const [recordId, setRecordId] = useState('');
  const [direction, setDirection] = useState('both');
  const [maxDepth, setMaxDepth] = useState(5);
  const [loading, setLoading] = useState(false);
  const [selectedNode, setSelectedNode] = useState(null);
  const [impactAnalysis, setImpactAnalysis] = useState(null);
  const [auditTrail, setAuditTrail] = useState(null);
  const [filterType, setFilterType] = useState('all');

  // Load lineage graph for workflow
  const loadWorkflowLineage = async () => {
    if (!workflowId.trim()) {
      alert('Please enter a workflow ID');
      return;
    }

    setLoading(true);
    try {
      const response = await fetch(`/api/lineage/workflows/${workflowId}/lineage-graph`);
      const data = await response.json();

      if (data.nodes && data.nodes.length > 0) {
        convertToReactFlow(data);
      } else {
        alert('No lineage data found for this workflow');
        setNodes([]);
        setEdges([]);
      }
    } catch (error) {
      console.error('Error loading workflow lineage:', error);
      alert('Failed to load lineage graph');
    } finally {
      setLoading(false);
    }
  };

  // Trace lineage for specific record
  const traceRecordLineage = async () => {
    if (!recordId.trim()) {
      alert('Please enter a record ID');
      return;
    }

    setLoading(true);
    try {
      const response = await fetch('/api/lineage/trace', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          record_id: recordId,
          direction: direction,
          max_depth: maxDepth
        })
      });
      const data = await response.json();

      if (data.nodes && Object.keys(data.nodes).length > 0) {
        convertLineageTraceToReactFlow(data);
      } else {
        alert('No lineage found for this record');
        setNodes([]);
        setEdges([]);
      }
    } catch (error) {
      console.error('Error tracing lineage:', error);
      alert('Failed to trace record lineage');
    } finally {
      setLoading(false);
    }
  };

  // Convert Neo4j data to ReactFlow format
  const convertToReactFlow = (data) => {
    const flowNodes = data.nodes.map((node, index) => {
      const properties = JSON.parse(node.properties || '{}');
      const nodeType = node.type.toUpperCase();
      const config = nodeTypes[nodeType] || nodeTypes.DATA_RECORD;

      return {
        id: node.id,
        type: 'default',
        data: {
          label: (
            <div style={{ textAlign: 'center' }}>
              <div style={{ fontSize: '24px' }}>{config.icon}</div>
              <div style={{ fontWeight: 'bold' }}>{node.name}</div>
              <div style={{ fontSize: '12px', color: '#666' }}>{nodeType}</div>
            </div>
          )
        },
        position: { x: (index % 5) * 250, y: Math.floor(index / 5) * 200 },
        style: {
          background: config.color,
          color: 'white',
          border: '2px solid #222',
          borderRadius: '8px',
          padding: '10px',
          width: 180
        }
      };
    });

    const flowEdges = data.relationships
      .filter(rel => rel)
      .map(rel => ({
        id: `${rel.start}-${rel.end}`,
        source: rel.start,
        target: rel.end,
        label: rel.type,
        type: 'smoothstep',
        animated: true,
        style: { stroke: '#888', strokeWidth: 2 }
      }));

    setNodes(flowNodes);
    setEdges(flowEdges);
  };

  // Convert lineage trace to ReactFlow format
  const convertLineageTraceToReactFlow = (data) => {
    const flowNodes = Object.entries(data.nodes).map(([id, node], index) => {
      const properties = JSON.parse(node.properties || '{}');
      const nodeType = node.type.toUpperCase();
      const config = nodeTypes[nodeType] || nodeTypes.DATA_RECORD;
      const isUpstream = data.upstream.includes(id);
      const isDownstream = data.downstream.includes(id);

      return {
        id: id,
        type: 'default',
        data: {
          label: (
            <div style={{ textAlign: 'center' }}>
              <div style={{ fontSize: '24px' }}>{config.icon}</div>
              <div style={{ fontWeight: 'bold' }}>{node.name}</div>
              <div style={{ fontSize: '12px', color: '#666' }}>{nodeType}</div>
              {isUpstream && <div style={{ fontSize: '10px' }}>↑ Upstream</div>}
              {isDownstream && <div style={{ fontSize: '10px' }}>↓ Downstream</div>}
            </div>
          )
        },
        position: {
          x: isUpstream ? 100 : isDownstream ? 500 : 300,
          y: index * 150
        },
        style: {
          background: config.color,
          color: 'white',
          border: id === data.record_id ? '3px solid #ff0' : '2px solid #222',
          borderRadius: '8px',
          padding: '10px',
          width: 180
        }
      };
    });

    const flowEdges = data.relationships.map(rel => ({
      id: `${rel.start}-${rel.end}`,
      source: rel.start,
      target: rel.end,
      label: rel.type,
      type: 'smoothstep',
      animated: true,
      style: { stroke: '#888', strokeWidth: 2 }
    }));

    setNodes(flowNodes);
    setEdges(flowEdges);
  };

  // Run impact analysis
  const runImpactAnalysis = async (nodeId, changeType) => {
    setLoading(true);
    try {
      const response = await fetch('/api/lineage/impact-analysis', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          source_node_id: nodeId,
          change_type: changeType,
          simulation_mode: true
        })
      });
      const data = await response.json();
      setImpactAnalysis(data);
    } catch (error) {
      console.error('Error running impact analysis:', error);
      alert('Failed to run impact analysis');
    } finally {
      setLoading(false);
    }
  };

  // Get audit trail
  const getAuditTrail = async () => {
    if (!workflowId.trim()) {
      alert('Please enter a workflow ID');
      return;
    }

    setLoading(true);
    try {
      const response = await fetch('/api/lineage/audit-trail', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          workflow_id: workflowId,
          include_transformations: true
        })
      });
      const data = await response.json();
      setAuditTrail(data);
    } catch (error) {
      console.error('Error getting audit trail:', error);
      alert('Failed to get audit trail');
    } finally {
      setLoading(false);
    }
  };

  // Handle node click
  const onNodeClick = useCallback((event, node) => {
    setSelectedNode(node);
  }, []);

  // Filter nodes by type
  const filterNodesByType = (type) => {
    setFilterType(type);
    if (type === 'all') {
      // Show all nodes
      setNodes(prev => prev.map(n => ({ ...n, hidden: false })));
    } else {
      // Show only specific type
      setNodes(prev =>
        prev.map(n => ({
          ...n,
          hidden: !n.style.background.includes(nodeTypes[type]?.color || '')
        }))
      );
    }
  };

  return (
    <div className="lineage-visualizer-page">
      <div className="lineage-header">
        <h1>Data Lineage Visualizer</h1>
        <p>Track data flow, analyze impact, and maintain compliance</p>
      </div>

      <div className="lineage-controls">
        <div className="control-section">
          <h3>Load Workflow Lineage</h3>
          <div className="input-group">
            <input
              type="text"
              placeholder="Workflow ID"
              value={workflowId}
              onChange={(e) => setWorkflowId(e.target.value)}
            />
            <button onClick={loadWorkflowLineage} disabled={loading}>
              {loading ? 'Loading...' : 'Load Graph'}
            </button>
            <button onClick={getAuditTrail} disabled={loading}>
              Audit Trail
            </button>
          </div>
        </div>

        <div className="control-section">
          <h3>Trace Record Lineage</h3>
          <div className="input-group">
            <input
              type="text"
              placeholder="Record ID"
              value={recordId}
              onChange={(e) => setRecordId(e.target.value)}
            />
            <select value={direction} onChange={(e) => setDirection(e.target.value)}>
              <option value="both">Both</option>
              <option value="upstream">Upstream</option>
              <option value="downstream">Downstream</option>
            </select>
            <input
              type="number"
              min="1"
              max="10"
              value={maxDepth}
              onChange={(e) => setMaxDepth(parseInt(e.target.value))}
              style={{ width: '80px' }}
            />
            <button onClick={traceRecordLineage} disabled={loading}>
              Trace
            </button>
          </div>
        </div>

        <div className="control-section">
          <h3>Filter by Type</h3>
          <div className="filter-buttons">
            <button onClick={() => filterNodesByType('all')}>All</button>
            {Object.keys(nodeTypes).map(type => (
              <button key={type} onClick={() => filterNodesByType(type)}>
                {nodeTypes[type].icon} {type}
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="lineage-graph-container">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onNodeClick={onNodeClick}
          fitView
        >
          <Controls />
          <MiniMap />
          <Background variant="dots" gap={12} size={1} />
          <Panel position="top-right">
            <div className="graph-legend">
              <h4>Legend</h4>
              {Object.entries(nodeTypes).map(([type, config]) => (
                <div key={type} className="legend-item">
                  <span style={{ color: config.color }}>{config.icon}</span>
                  <span>{type}</span>
                </div>
              ))}
            </div>
          </Panel>
        </ReactFlow>
      </div>

      {selectedNode && (
        <div className="node-details-panel">
          <h3>Node Details</h3>
          <button className="close-btn" onClick={() => setSelectedNode(null)}>×</button>
          <div className="node-info">
            <p><strong>ID:</strong> {selectedNode.id}</p>
            <p><strong>Type:</strong> {selectedNode.data.label}</p>
          </div>
          <div className="impact-actions">
            <h4>Impact Analysis</h4>
            <button onClick={() => runImpactAnalysis(selectedNode.id, 'schema_change')}>
              Schema Change
            </button>
            <button onClick={() => runImpactAnalysis(selectedNode.id, 'data_quality')}>
              Data Quality
            </button>
            <button onClick={() => runImpactAnalysis(selectedNode.id, 'system_failure')}>
              System Failure
            </button>
          </div>
        </div>
      )}

      {impactAnalysis && (
        <div className="impact-analysis-panel">
          <h3>Impact Analysis Results</h3>
          <button className="close-btn" onClick={() => setImpactAnalysis(null)}>×</button>
          <div className="impact-summary">
            <p><strong>Source Node:</strong> {impactAnalysis.source_node_id}</p>
            <p><strong>Change Type:</strong> {impactAnalysis.change_type}</p>
            <p><strong>Affected Systems:</strong> {impactAnalysis.affected_count}</p>
            <p><strong>Risk Level:</strong> 
              <span className={`risk-badge risk-${impactAnalysis.risk_assessment}`}>
                {impactAnalysis.risk_assessment.toUpperCase()}
              </span>
            </p>
          </div>
          <div className="recommendations">
            <h4>Recommendations</h4>
            <ul>
              {impactAnalysis.recommendations.map((rec, i) => (
                <li key={i}>{rec}</li>
              ))}
            </ul>
          </div>
          <div className="affected-nodes">
            <h4>Affected Nodes ({impactAnalysis.affected_count})</h4>
            <div className="affected-list">
              {impactAnalysis.affected_nodes.slice(0, 10).map((node, i) => (
                <div key={i} className="affected-item">
                  <span>{node.node.name}</span>
                  <span className={`impact-badge impact-${node.impact_level}`}>
                    {node.impact_level}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {auditTrail && (
        <div className="audit-trail-panel">
          <h3>Audit Trail - {auditTrail.workflow_id}</h3>
          <button className="close-btn" onClick={() => setAuditTrail(null)}>×</button>
          <div className="audit-summary">
            <p><strong>Total Records:</strong> {auditTrail.total_records}</p>
            <p><strong>Compliance Status:</strong> 
              <span className="compliance-badge">✓ {auditTrail.compliance_status}</span>
            </p>
            <p><strong>Generated:</strong> {new Date(auditTrail.generated_at).toLocaleString()}</p>
          </div>
          <div className="audit-records">
            <h4>Audit Records</h4>
            <div className="records-list">
              {auditTrail.audit_trail.slice(0, 20).map((record, i) => (
                <div key={i} className="audit-record">
                  <div><strong>{record.node.name}</strong></div>
                  <div className="audit-meta">
                    Type: {record.node.type} | 
                    Created: {new Date(record.node.created_at).toLocaleString()}
                  </div>
                  <div className="audit-relationships">
                    {record.relationships.length} relationship(s)
                  </div>
                </div>
              ))}
            </div>
          </div>
          <button className="export-btn">Export to PDF</button>
        </div>
      )}
    </div>
  );
};

export default LineageVisualizerPage;
