/**
 * Data Lineage Visualizer - Enterprise Edition
 * =============================================
 * 
 * Full integration with Postgres workflows and Neo4j lineage graph.
 * Features: Workflow dropdown, lineage tracing, impact analysis, audit trail.
 */

import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { Link } from 'react-router-dom';
import ReactFlow, {
  MiniMap,
  Controls,
  Background,
  useNodesState,
  useEdgesState,
  Panel,
  MarkerType
} from 'reactflow';
import 'reactflow/dist/style.css';
import { e2etraceFetchWithRetry } from '../../api/e2etrace-api';
import './LineageVisualizerPage.css';
import { useReportHub } from '../../hooks/useReportHub.js';

const NODE_TYPE_CONFIG = {
  source_system: { color: 'var(--info-color, #0078D4)', icon: 'SRC', label: 'Source System' },
  target_system: { color: 'var(--success-color, #24A148)', icon: 'TGT', label: 'Target System' },
  transformation: { color: 'var(--warning-color, #FF832B)', icon: 'TRF', label: 'Transformation' },
  validation: { color: 'var(--accent-color, #0066CC)', icon: 'VAL', label: 'Validation' },
  agent: { color: 'var(--error-color, #DA1E28)', icon: 'AGT', label: 'Agent' },
  data_record: { color: 'var(--primary-light, #4D94E0)', icon: 'REC', label: 'Data Record' },
  default: { color: 'var(--text-muted, #6b7280)', icon: 'NOD', label: 'Node' }
};

const RELATIONSHIP_STYLES = {
  EXTRACTED_FROM: { color: 'var(--info-color, #0078D4)', dash: '' },
  TRANSFORMED_BY: { color: 'var(--warning-color, #FF832B)', dash: '5,5' },
  VALIDATED_BY: { color: 'var(--success-color, #24A148)', dash: '2,2' },
  LOADED_TO: { color: 'var(--accent-color, #0066CC)', dash: '' },
  DEPENDS_ON: { color: 'var(--error-color, #DA1E28)', dash: '5,5' },
  PROCESSED_BY: { color: 'var(--accent-hover-color, #0052A3)', dash: '' }
};

// Static ReactFlow configuration objects to prevent recreation on each render
const FIT_VIEW_OPTIONS = { padding: 0.2 };
const MINIMAP_NODE_COLOR = (node) => node.style?.background || 'var(--text-muted, #777)';
const MINIMAP_MASK_COLOR = 'rgba(0,0,0,0.1)';
// Empty nodeTypes/edgeTypes - must be defined outside component to prevent React Flow warning
const NODE_TYPES = {};
const EDGE_TYPES = {};

const LineageVisualizerPage = () => {
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  
  const [workflows, setWorkflows] = useState([]);
  const [selectedWorkflowId, setSelectedWorkflowId] = useState('');
  const [workflowNameSearch, setWorkflowNameSearch] = useState('');
  const [workflowDetails, setWorkflowDetails] = useState(null);
    const filteredWorkflows = useMemo(() => {
      const q = String(workflowNameSearch || '').trim().toLowerCase();
      if (!q) return workflows;
      return (workflows || []).filter((wf) => {
        const name = String(wf?.name || '').toLowerCase();
        return name.includes(q);
      });
    }, [workflows, workflowNameSearch]);

  
  const [recordId, setRecordId] = useState('');
  const [direction, setDirection] = useState('both');
  const [maxDepth, setMaxDepth] = useState(5);
  const [filterType, setFilterType] = useState('all');
  
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [selectedNode, setSelectedNode] = useState(null);
  const [impactAnalysis, setImpactAnalysis] = useState(null);
  const [auditTrail, setAuditTrail] = useState(null);
  const [activeTab, setActiveTab] = useState('lineage');
  
  const [dbStatus, setDbStatus] = useState({ postgres: false, neo4j: false });
  const { saveReport, saving: rhSaving, saved: rhSaved } = useReportHub();

  useEffect(() => {
    const checkConnectivity = async () => {
      try {
        const response = await fetch('/health');
        // Check if response is JSON before parsing
        const contentType = response.headers.get('content-type');
        if (!contentType || !contentType.includes('application/json')) {
          // Backend not running - got HTML fallback from Vite
          setDbStatus({ postgres: false, neo4j: false });
          return;
        }
        const health = await response.json();
        setDbStatus({
          postgres: health.dependencies?.postgres?.ok || false,
          neo4j: health.dependencies?.neo4j?.ok || false
        });
      } catch {
        setDbStatus({ postgres: false, neo4j: false });
      }
    };
    checkConnectivity();
  }, []);

  useEffect(() => {
    const fetchWorkflows = async () => {
      try {
        setLoading(true);
        const response = await e2etraceFetchWithRetry('/api/workflows/');
        if (!response.ok) throw new Error('Failed to fetch workflows');
        const data = await response.json();
        setWorkflows(Array.isArray(data) ? data : []);
        if (Array.isArray(data) && data.length > 0 && !selectedWorkflowId) {
          setSelectedWorkflowId(data[0].id);
        }
      } catch {
        setError('Could not load workflows from database');
        setWorkflows([]);
      } finally {
        setLoading(false);
      }
    };
    fetchWorkflows();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!selectedWorkflowId) {
      setWorkflowDetails(null);
      return;
    }
    const fetchWorkflowDetails = async () => {
      try {
        const response = await e2etraceFetchWithRetry(`/api/workflows/${selectedWorkflowId}`);
        if (response.ok) {
          const data = await response.json();
          setWorkflowDetails(data);
        }
      } catch (err) {
        console.error('Error fetching workflow details:', err);
      }
    };
    fetchWorkflowDetails();
  }, [selectedWorkflowId]);

  const loadLineageGraph = useCallback(async () => {
    if (!selectedWorkflowId) {
      setError('Please select a workflow');
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams();
      if (filterType && filterType !== 'all') {
        params.append('node_types', filterType);
      }
      const qs = params.toString();
      const response = await e2etraceFetchWithRetry(
        `/api/lineage/workflows/${selectedWorkflowId}/lineage-graph${qs ? `?${qs}` : ''}`
      );
      if (!response.ok) throw new Error(`Failed to load lineage: ${response.statusText}`);
      const data = await response.json();
      if (data.nodes && data.nodes.length > 0) {
        convertToReactFlow(data);
      } else {
        setNodes([]);
        setEdges([]);
        setError('No lineage data found for this workflow');
      }
    } catch (err) {
      setError(err.message || 'Failed to load lineage graph');
      setNodes([]);
      setEdges([]);
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedWorkflowId, filterType]);

  const traceRecordLineage = useCallback(async () => {
    if (!recordId.trim()) {
      setError('Please enter a record ID');
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const response = await e2etraceFetchWithRetry('/api/lineage/trace', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          record_id: recordId,
          direction: direction,
          max_depth: maxDepth,
          ...(filterType && filterType !== 'all' ? { node_types: [filterType] } : {})
        })
      });
      if (!response.ok) throw new Error(`Failed to trace lineage: ${response.statusText}`);
      const data = await response.json();
      if (data.nodes && Object.keys(data.nodes).length > 0) {
        convertLineageTraceToReactFlow(data);
      } else {
        setNodes([]);
        setEdges([]);
        setError('No lineage found for this record');
      }
    } catch (err) {
      setError(err.message || 'Failed to trace record lineage');
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [recordId, direction, maxDepth, filterType]);

  const convertToReactFlow = useCallback((data) => {
    const flowNodes = data.nodes.map((node, index) => {
      let properties = {};
      try {
        properties = typeof node.properties === 'string' ? JSON.parse(node.properties) : (node.properties || {});
      } catch { /* ignore */ }
      const nodeType = (node.type || 'default').toLowerCase();
      const config = NODE_TYPE_CONFIG[nodeType] || NODE_TYPE_CONFIG.default;
      return {
        id: node.id,
        type: 'default',
        data: {
          label: (
            <div className="node-content">
              <div className="node-icon">{config.icon}</div>
              <div className="node-name">{node.name || node.id}</div>
              <div className="node-type-label">{config.label}</div>
            </div>
          ),
          nodeData: { ...node, properties }
        },
        position: { x: (index % 6) * 220 + 50, y: Math.floor(index / 6) * 180 + 50 },
        style: {
          background: config.color,
          color: 'var(--text-on-primary, #fff)',
          border: '2px solid rgba(255,255,255,0.2)',
          borderRadius: '8px',
          padding: '0',
          width: 160,
          boxShadow: '0 4px 12px rgba(0,0,0,0.15)'
        }
      };
    });

    const flowEdges = (data.relationships || [])
      .filter(rel => rel && rel.start && rel.end)
      .map((rel, index) => {
        const relType = rel.type || 'DEPENDS_ON';
        const relStyle = RELATIONSHIP_STYLES[relType] || { color: 'var(--text-muted, #888)', dash: '' };
        return {
          id: `edge-${rel.start}-${rel.end}-${index}`,
          source: rel.start,
          target: rel.end,
          label: relType.replace(/_/g, ' '),
          type: 'smoothstep',
          animated: true,
          markerEnd: { type: MarkerType.ArrowClosed, color: relStyle.color },
          style: { stroke: relStyle.color, strokeWidth: 2, strokeDasharray: relStyle.dash },
          labelStyle: { fill: relStyle.color, fontWeight: 600, fontSize: 10 }
        };
      });

    setNodes(flowNodes);
    setEdges(flowEdges);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const convertLineageTraceToReactFlow = useCallback((data) => {
    const flowNodes = Object.entries(data.nodes).map(([id, node], index) => {
      let properties = {};
      try {
        properties = typeof node.properties === 'string' ? JSON.parse(node.properties) : (node.properties || {});
      } catch { /* ignore */ }
      const nodeType = (node.type || 'default').toLowerCase();
      const config = NODE_TYPE_CONFIG[nodeType] || NODE_TYPE_CONFIG.default;
      const isUpstream = data.upstream?.includes(id);
      const isDownstream = data.downstream?.includes(id);
      const isSource = id === data.record_id;

      return {
        id: id,
        type: 'default',
        data: {
          label: (
            <div className="node-content">
              <div className="node-icon">{config.icon}</div>
              <div className="node-name">{node.name || id}</div>
              <div className="node-type-label">{config.label}</div>
              {isUpstream && <div className="node-direction">UPSTREAM</div>}
              {isDownstream && <div className="node-direction">DOWNSTREAM</div>}
            </div>
          ),
          nodeData: { ...node, properties }
        },
        position: { x: isUpstream ? 100 : isDownstream ? 600 : 350, y: index * 140 + 50 },
        style: {
          background: config.color,
          color: 'var(--text-on-primary, #fff)',
          border: isSource ? '4px solid var(--warning-color, #fbbf24)' : '2px solid rgba(255,255,255,0.2)',
          borderRadius: '8px',
          padding: '0',
          width: 160,
          boxShadow: isSource ? '0 0 20px rgba(255,131,43,0.45)' : '0 4px 12px rgba(0,0,0,0.15)'
        }
      };
    });

    const flowEdges = (data.relationships || []).map((rel, index) => ({
      id: `edge-${rel.start}-${rel.end}-${index}`,
      source: rel.start,
      target: rel.end,
      label: rel.type?.replace(/_/g, ' ') || '',
      type: 'smoothstep',
      animated: true,
      markerEnd: { type: MarkerType.ArrowClosed },
      style: { stroke: 'var(--text-muted, #64748b)', strokeWidth: 2 }
    }));

    setNodes(flowNodes);
    setEdges(flowEdges);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const runImpactAnalysis = useCallback(async (nodeId, changeType) => {
    setLoading(true);
    setError(null);
    try {
      const response = await e2etraceFetchWithRetry('/api/lineage/impact-analysis', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ source_node_id: nodeId, change_type: changeType, simulation_mode: true })
      });
      if (!response.ok) throw new Error('Impact analysis failed');
      const data = await response.json();
      setImpactAnalysis(data);
      setActiveTab('impact');
    } catch (err) {
      setError(err.message || 'Failed to run impact analysis');
    } finally {
      setLoading(false);
    }
  }, []);

  const getAuditTrail = useCallback(async () => {
    if (!selectedWorkflowId) {
      setError('Please select a workflow');
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const response = await e2etraceFetchWithRetry('/api/lineage/audit-trail', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ workflow_id: selectedWorkflowId, include_transformations: true })
      });
      if (!response.ok) throw new Error('Failed to get audit trail');
      const data = await response.json();
      setAuditTrail(data);
      setActiveTab('audit');
    } catch (err) {
      setError(err.message || 'Failed to get audit trail');
    } finally {
      setLoading(false);
    }
  }, [selectedWorkflowId]);

  const onNodeClick = useCallback((event, node) => {
    setSelectedNode(node);
  }, []);

  const legend = useMemo(() => (
    <div className="lineage-legend">
      <h4>Node Types</h4>
      {Object.entries(NODE_TYPE_CONFIG).filter(([k]) => k !== 'default').map(([type, config]) => (
        <div key={type} className="legend-item">
          <span className="legend-color" style={{ background: config.color }}>{config.icon}</span>
          <span className="legend-label">{config.label}</span>
        </div>
      ))}
    </div>
  ), []);

  // Quick start guide for new users
  const renderGettingStarted = () => (
    <div className="getting-started-panel">
      <div className="gs-header">
        <h2>Data Lineage Explorer</h2>
        <p>Track data flow across systems with complete traceability and compliance</p>
      </div>
      
      <div className="gs-steps">
        <div className="gs-step">
          <div className="step-number">1</div>
          <div className="step-content">
            <h4>Select a Workflow</h4>
            <p>Choose a data workflow from the dropdown to explore its lineage</p>
            <input
              type="text"
              value={workflowNameSearch}
              onChange={(e) => setWorkflowNameSearch(e.target.value)}
              placeholder="Search workflow name..."
              className="form-input gs-select"
            />
            <select 
              value={selectedWorkflowId} 
              onChange={(e) => setSelectedWorkflowId(e.target.value)}
              disabled={loading || workflows.length === 0}
              className="form-select gs-select"
            >
              <option value="">-- Select Workflow --</option>
              {filteredWorkflows.map(wf => (
                <option key={wf.id} value={wf.id}>{wf.name} ({wf.status})</option>
              ))}
            </select>
          </div>
        </div>

        <div className="gs-step">
          <div className="step-number">2</div>
          <div className="step-content">
            <h4>Load Lineage Graph</h4>
            <p>Visualize how data flows through sources, transformations, and destinations</p>
            <div className="step-actions">
              <button 
                onClick={loadLineageGraph} 
                disabled={loading || !selectedWorkflowId}
                className="btn btn-primary"
              >
                {loading ? 'Loading...' : 'Load Lineage Graph'}
              </button>
              <Link
                to={`/workflow/${encodeURIComponent(selectedWorkflowId || '')}`}
                className="btn btn-secondary btn-sm"
                aria-disabled={!selectedWorkflowId}
                onClick={(e) => { if (!selectedWorkflowId) e.preventDefault(); }}
              >
                View Workflow
              </Link>
            </div>
          </div>
        </div>

        <div className="gs-step">
          <div className="step-number">3</div>
          <div className="step-content">
            <h4>Analyze and Export</h4>
            <p>Click nodes for impact analysis, generate audit trails for compliance</p>
            <div className="step-actions">
              <button onClick={getAuditTrail} disabled={!selectedWorkflowId} className="btn btn-secondary btn-sm">
                Generate Audit Trail
              </button>
            </div>
          </div>
        </div>
      </div>

      <div className="gs-quick-actions">
        <h3>Common Actions</h3>
        <div className="quick-actions-grid">
          <button className="quick-action-card" onClick={() => { if (workflows[0]) { setSelectedWorkflowId(workflows[0].id); loadLineageGraph(); } }} disabled={workflows.length === 0}>
            <div className="qa-icon">LOAD</div>
            <div className="qa-text">
              <strong>Quick Load</strong>
              <span>Load first available workflow</span>
            </div>
          </button>
          
          <button className="quick-action-card" onClick={getAuditTrail} disabled={!selectedWorkflowId}>
            <div className="qa-icon">AUDIT</div>
            <div className="qa-text">
              <strong>Compliance Audit</strong>
              <span>Generate compliance report</span>
            </div>
          </button>
          
          <button className="quick-action-card" onClick={() => setActiveTab('impact')} disabled={!impactAnalysis}>
            <div className="qa-icon">IMPACT</div>
            <div className="qa-text">
              <strong>Impact Analysis</strong>
              <span>See downstream effects</span>
            </div>
          </button>

          <button className="quick-action-card" onClick={() => {
            if (nodes.length > 0) {
              const blob = new Blob([JSON.stringify({ nodes, edges }, null, 2)], { type: 'application/json' });
              const url = URL.createObjectURL(blob);
              const a = document.createElement('a');
              a.href = url;
              a.download = `lineage-${selectedWorkflowId}-${Date.now()}.json`;
              a.click();
              URL.revokeObjectURL(url);
            }
          }} disabled={nodes.length === 0}>
            <div className="qa-icon">EXPORT</div>
            <div className="qa-text">
              <strong>Export Graph</strong>
              <span>Download as JSON</span>
            </div>
          </button>
        </div>
      </div>

      {workflowDetails && (
        <div className="gs-workflow-preview">
          <h3>Selected Workflow Details</h3>
          <div className="workflow-preview-card">
            <div className="preview-row">
              <label>Name:</label>
              <span>{workflowDetails.name}</span>
            </div>
            <div className="preview-row">
              <label>Status:</label>
              <span className={`status-${workflowDetails.status?.toLowerCase()}`}>{workflowDetails.status}</span>
            </div>
            <div className="preview-row">
              <label>Type:</label>
              <span>{workflowDetails.workflow_type || 'ETL'}</span>
            </div>
            <div className="preview-row">
              <label>Last Run:</label>
              <span>{workflowDetails.updated_at ? new Date(workflowDetails.updated_at).toLocaleString() : 'Never'}</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );

  return (
    <div className="lineage-visualizer-page">
      <header className="page-header">
        <div className="header-content">
          <h1>Data Lineage Explorer</h1>
          <p>Track data flow across systems with full traceability</p>
        </div>
        <div className="connection-status">
          <span className={`status-badge ${dbStatus.postgres ? 'connected' : 'disconnected'}`}>
            PostgreSQL: {dbStatus.postgres ? 'Connected' : 'Offline'}
          </span>
          <span className={`status-badge ${dbStatus.neo4j ? 'connected' : 'disconnected'}`}>
            Neo4j: {dbStatus.neo4j ? 'Connected' : 'Offline'}
          </span>
          {nodes.length > 0 && (
            <button
              className="btn btn-secondary btn-sm"
              onClick={() => saveReport({
                report_type: 'lineage',
                title: `Lineage Snapshot: ${workflowDetails?.name || selectedWorkflowId || 'Graph'}`,
                source_page: 'lineage',
                workflow_id: selectedWorkflowId || undefined,
                status: 'info',
                summary: { nodes: nodes.length, edges: edges.length },
                result: { nodes: nodes.map(n => n.id), edges: edges.map(e => e.id), workflow_id: selectedWorkflowId },
                tags: ['lineage'],
              })}
              disabled={rhSaving}
              title="Save snapshot to Reporting Hub"
            >
              {rhSaved ? <><i className="fas fa-check" /> Saved</> : rhSaving ? <><i className="fas fa-spinner fa-spin" /> Saving…</> : <><i className="fas fa-clipboard-list" /> Save Report</>}
            </button>
          )}
          <Link to="/reporting-hub" className="btn btn-secondary btn-sm" title="Reporting Hub">
            <i className="fas fa-clipboard-list" /> Reports
          </Link>
        </div>
      </header>

      {error && (
        <div className="error-banner">
          <span className="error-icon">!</span>
          <span>{error}</span>
          <button onClick={() => setError(null)} className="dismiss-btn">Dismiss</button>
        </div>
      )}

      {/* Show Getting Started if no lineage loaded yet */}
      {nodes.length === 0 && !loading && activeTab === 'lineage' ? (
        renderGettingStarted()
      ) : (
        <>
          <div className="controls-section">
            <div className="control-panel">
              <h3>Workflow Selection</h3>
              <div className="control-row">
                <input
                  type="text"
                  value={workflowNameSearch}
                  onChange={(e) => setWorkflowNameSearch(e.target.value)}
                  placeholder="Search workflow name..."
                  className="form-input"
                />
                <select 
                  value={selectedWorkflowId} 
                  onChange={(e) => setSelectedWorkflowId(e.target.value)}
                  disabled={loading || workflows.length === 0}
                  className="form-select"
                >
                  <option value="">-- Select Workflow --</option>
                  {filteredWorkflows.map(wf => (
                    <option key={wf.id} value={wf.id}>
                      {wf.name || wf.id} ({wf.status || 'unknown'})
                    </option>
                  ))}
                </select>
                <button onClick={loadLineageGraph} disabled={loading || !selectedWorkflowId} className="btn btn-primary">
                  {loading ? 'Loading...' : 'Load Graph'}
                </button>
                <Link
                  to={`/workflow/${encodeURIComponent(selectedWorkflowId || '')}`}
                  className="btn btn-secondary"
                  aria-disabled={!selectedWorkflowId}
                  onClick={(e) => { if (!selectedWorkflowId) e.preventDefault(); }}
                >
                  View Workflow
                </Link>
                <button onClick={getAuditTrail} disabled={loading || !selectedWorkflowId} className="btn btn-secondary">
                  Audit Trail
                </button>
              </div>
              {workflowDetails && (
                <div className="workflow-info">
                  <span><strong>Source:</strong> {workflowDetails.source_name} ({workflowDetails.source_type})</span>
                  <span><strong>Target:</strong> {workflowDetails.target_name} ({workflowDetails.target_type})</span>
                  <span><strong>Status:</strong> <span className={`status-${workflowDetails.status}`}>{workflowDetails.status}</span></span>
                </div>
              )}
            </div>

            <div className="control-panel">
              <h3>Record Lineage Trace</h3>
              <div className="control-row">
                <input
                  type="text"
                  placeholder="Enter Record ID..."
                  value={recordId}
                  onChange={(e) => setRecordId(e.target.value)}
                  className="form-input"
                />
                <select value={direction} onChange={(e) => setDirection(e.target.value)} className="form-select compact">
                  <option value="both">Both Directions</option>
                  <option value="upstream">Upstream Only</option>
                  <option value="downstream">Downstream Only</option>
                </select>
                <label className="depth-label">Depth:</label>
                <input
                  type="number"
                  min="1"
                  max="10"
                  value={maxDepth}
                  onChange={(e) => setMaxDepth(parseInt(e.target.value) || 5)}
                  className="form-input compact"
                />
                <button onClick={traceRecordLineage} disabled={loading || !recordId.trim()} className="btn btn-primary">
                  Trace
                </button>
              </div>
            </div>

            <div className="control-panel">
              <h3>Filter by Type</h3>
              <div className="filter-buttons">
                <button className={`filter-btn ${filterType === 'all' ? 'active' : ''}`} onClick={() => setFilterType('all')}>All</button>
                {Object.entries(NODE_TYPE_CONFIG).filter(([k]) => k !== 'default').map(([type, config]) => (
                  <button 
                    key={type}
                    className={`filter-btn ${filterType === type ? 'active' : ''}`}
                    onClick={() => setFilterType(type)}
                    style={{ '--btn-color': config.color }}
                  >
                    {config.label}
                  </button>
                ))}
              </div>
            </div>
          </div>

          <div className="tab-bar">
            <button className={`tab ${activeTab === 'lineage' ? 'active' : ''}`} onClick={() => setActiveTab('lineage')}>
              Lineage Graph
            </button>
            <button className={`tab ${activeTab === 'audit' ? 'active' : ''}`} onClick={() => setActiveTab('audit')} disabled={!auditTrail}>
              Audit Trail
            </button>
            <button className={`tab ${activeTab === 'impact' ? 'active' : ''}`} onClick={() => setActiveTab('impact')} disabled={!impactAnalysis}>
              Impact Analysis
            </button>
          </div>

          <div className="main-content">
            {activeTab === 'lineage' && (
              <div className="graph-container">
                {nodes.length === 0 && !loading ? (
                  <div className="empty-state">
                    <div className="empty-icon">LINEAGE</div>
                    <h3>No Lineage Data</h3>
                    <p>Select a workflow and click Load Graph to visualize data lineage from Neo4j</p>
                  </div>
                ) : (
                  <ReactFlow
                    nodes={nodes}
                    edges={edges}
                    onNodesChange={onNodesChange}
                    onEdgesChange={onEdgesChange}
                    onNodeClick={onNodeClick}
                    nodeTypes={NODE_TYPES}
                    edgeTypes={EDGE_TYPES}
                    fitView
                    fitViewOptions={FIT_VIEW_OPTIONS}
                  >
                    <Controls />
                    <MiniMap nodeColor={MINIMAP_NODE_COLOR} maskColor={MINIMAP_MASK_COLOR} />
                    <Background variant="dots" gap={16} size={1} color="var(--border-color, #e2e8f0)" />
                    <Panel position="top-right">{legend}</Panel>
                  </ReactFlow>
                )}
              </div>
            )}

            {activeTab === 'audit' && auditTrail && (
              <div className="audit-container">
                <div className="audit-header">
                  <h3>Audit Trail - {auditTrail.workflow_id}</h3>
                  <div className="audit-summary">
                    <span>Total Records: <strong>{auditTrail.total_records}</strong></span>
                    <span className={`compliance-status ${auditTrail.compliance_status?.toLowerCase()}`}>
                      Compliance: {auditTrail.compliance_status}
                    </span>
                    <span>Generated: {new Date(auditTrail.generated_at).toLocaleString()}</span>
                  </div>
                </div>
                <div className="audit-records">
                  {auditTrail.audit_trail?.map((record, i) => (
                    <div key={i} className="audit-record">
                      <div className="record-header">
                        <span className="record-name">{record.node?.name || record.node?.id}</span>
                        <span className="record-type">{record.node?.type}</span>
                      </div>
                      <div className="record-details">
                        <span>Created: {new Date(record.node?.created_at).toLocaleString()}</span>
                        <span>Relationships: {record.relationships?.length || 0}</span>
                      </div>
                    </div>
                  ))}
                </div>
                <button className="btn btn-primary export-btn">Export Audit Report</button>
              </div>
            )}

            {activeTab === 'impact' && impactAnalysis && (
              <div className="impact-container">
                <div className="impact-header">
                  <h3>Impact Analysis Results</h3>
                </div>
                <div className="impact-metrics">
                  <div className="metric-card">
                    <label>Source Node</label>
                    <span className="metric-value">{impactAnalysis.source_node_id}</span>
                  </div>
                  <div className="metric-card">
                    <label>Change Type</label>
                    <span className="metric-value">{impactAnalysis.change_type}</span>
                  </div>
                  <div className="metric-card highlight">
                    <label>Affected Systems</label>
                    <span className="metric-value">{impactAnalysis.affected_count}</span>
                  </div>
                  <div className={`metric-card risk-${impactAnalysis.risk_assessment?.toLowerCase()}`}>
                    <label>Risk Level</label>
                    <span className="metric-value">{impactAnalysis.risk_assessment?.toUpperCase()}</span>
                  </div>
                </div>
                <div className="recommendations-section">
                  <h4>Recommendations</h4>
                  <ul>{impactAnalysis.recommendations?.map((rec, i) => <li key={i}>{rec}</li>)}</ul>
                </div>
                <div className="affected-nodes-section">
                  <h4>Affected Nodes ({impactAnalysis.affected_count})</h4>
                  <div className="affected-list">
                    {impactAnalysis.affected_nodes?.slice(0, 20).map((item, i) => (
                      <div key={i} className="affected-item">
                        <span className="affected-name">{item.node?.name || item.node?.id}</span>
                        <span className={`impact-level level-${item.impact_level?.toLowerCase()}`}>{item.impact_level}</span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}

            {selectedNode && (
              <div className="details-panel">
                <div className="panel-header">
                  <h3>Node Details</h3>
                  <button className="close-btn" onClick={() => setSelectedNode(null)}>X</button>
                </div>
                <div className="panel-body">
                  <div className="detail-row"><label>ID:</label><span>{selectedNode.id}</span></div>
                  <div className="detail-row"><label>Type:</label><span>{selectedNode.data?.nodeData?.type || 'Unknown'}</span></div>
                  <div className="detail-row"><label>Name:</label><span>{selectedNode.data?.nodeData?.name || selectedNode.id}</span></div>
                  {selectedNode.data?.nodeData?.workflow_id && (
                    <div className="detail-row"><label>Workflow:</label><span>{selectedNode.data.nodeData.workflow_id}</span></div>
                  )}
                  {selectedNode.data?.nodeData?.properties && Object.keys(selectedNode.data.nodeData.properties).length > 0 && (
                    <div className="properties-section">
                      <h4>Properties</h4>
                      <pre>{JSON.stringify(selectedNode.data.nodeData.properties, null, 2)}</pre>
                    </div>
                  )}
                  <div className="impact-actions">
                    <h4>Run Impact Analysis</h4>
                    <div className="action-buttons">
                      <button className="btn btn-sm" onClick={() => runImpactAnalysis(selectedNode.id, 'schema_change')}>Schema Change</button>
                      <button className="btn btn-sm" onClick={() => runImpactAnalysis(selectedNode.id, 'data_quality')}>Data Quality</button>
                      <button className="btn btn-sm" onClick={() => runImpactAnalysis(selectedNode.id, 'system_failure')}>System Failure</button>
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>
        </>
      )}

      {loading && (
        <div className="loading-overlay">
          <div className="spinner"></div>
          <span>Loading...</span>
        </div>
      )}
    </div>
  );
};

export default LineageVisualizerPage;
