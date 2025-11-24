import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import './WorkflowManagerPage.css';

/**
 * Workflow Manager Page
 * 
 * Manages multiple workflow instances - each representing a unique
 * source→target migration pipeline with its own configuration and state.
 * 
 * Features:
 * - List all workflow instances
 * - Create new workflows from templates or custom config
 * - View workflow details and progress
 * - Execute workflow actions (start, pause, stop)
 * - Monitor statistics and health
 */
const WorkflowManagerPage = () => {
  const navigate = useNavigate();
  const [workflows, setWorkflows] = useState([]);
  const [statistics, setStatistics] = useState(null);
  const [templates, setTemplates] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState({
    status: 'all',
    sourceType: 'all',
    targetType: 'all',
    search: ''
  });
  const [showCreateModal, setShowCreateModal] = useState(false);

  useEffect(() => {
    loadWorkflowData();
  }, [filter]);

  const loadWorkflowData = async () => {
    try {
      setLoading(true);
      
      // Load workflows
      const workflowsRes = await fetch('/api/workflows/');
      const workflowsData = await workflowsRes.ok ? await workflowsRes.json() : [];
      
      // Load statistics
      const statsRes = await fetch('/api/workflows/statistics/summary');
      const statsData = await statsRes.ok ? await statsRes.json() : null;
      
      // Load templates
      const templatesRes = await fetch('/api/workflows/templates/list');
      const templatesData = await templatesRes.ok ? await templatesRes.json() : [];
      
      setWorkflows(workflowsData);
      setStatistics(statsData);
      setTemplates(templatesData);
    } catch (error) {
      console.error('Error loading workflow data:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleWorkflowAction = async (workflowId, action) => {
    try {
      const response = await fetch(`/api/workflows/${workflowId}/execute`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action, execution_params: {} })
      });
      
      if (response.ok) {
        const result = await response.json();
        alert(result.message);
        loadWorkflowData();
      } else {
        const error = await response.json();
        alert(`Error: ${error.detail}`);
      }
    } catch (error) {
      console.error('Error executing workflow action:', error);
      alert('Failed to execute workflow action');
    }
  };

  const handleViewWorkflow = (workflowId) => {
    navigate(`/workflow/${workflowId}`);
  };

  const handleDeleteWorkflow = async (workflowId) => {
    if (!confirm('Are you sure you want to delete this workflow?')) return;
    
    try {
      const response = await fetch(`/api/workflows/${workflowId}`, {
        method: 'DELETE'
      });
      
      if (response.ok) {
        alert('Workflow deleted successfully');
        loadWorkflowData();
      }
    } catch (error) {
      console.error('Error deleting workflow:', error);
      alert('Failed to delete workflow');
    }
  };

  const getStatusBadgeClass = (status) => {
    const statusMap = {
      draft: 'status-draft',
      configured: 'status-configured',
      running: 'status-running',
      paused: 'status-paused',
      completed: 'status-completed',
      failed: 'status-failed',
      cancelled: 'status-cancelled'
    };
    return statusMap[status] || 'status-default';
  };

  const getSourceIcon = (sourceType) => {
    const iconMap = {
      teamcenter: '🏢',
      windchill: '🔄',
      catia: '🎨',
      nx: '⚙️',
      creo: '🔧'
    };
    return iconMap[sourceType] || '📦';
  };

  const getTargetIcon = (targetType) => {
    const iconMap = {
      neo4j: '🕸️',
      cloud_plm: '☁️',
      opensearch: '🔍',
      warehouse: '🏭',
      datalake: '💾'
    };
    return iconMap[targetType] || '🎯';
  };

  if (loading) {
    return (
      <div className="workflow-manager-loading">
        <div className="loading-spinner"></div>
        <p>Loading workflows...</p>
      </div>
    );
  }

  return (
    <div className="workflow-manager-page">
      {/* Header */}
      <div className="workflow-header">
        <div className="header-title">
          <h1>🏭 Workflow Instance Manager</h1>
          <p className="header-subtitle">PLM Data Migration AI Factory - Manage Multiple Pipelines</p>
        </div>
        <button 
          className="btn-create-workflow"
          onClick={() => setShowCreateModal(true)}
        >
          ➕ Create Workflow
        </button>
      </div>

      {/* Statistics Dashboard */}
      {statistics && (
        <div className="workflow-statistics">
          <div className="stat-card">
            <div className="stat-icon">📊</div>
            <div className="stat-content">
              <div className="stat-value">{statistics.total_workflows}</div>
              <div className="stat-label">Total Workflows</div>
            </div>
          </div>
          <div className="stat-card">
            <div className="stat-icon">▶️</div>
            <div className="stat-content">
              <div className="stat-value">{statistics.active_executions}</div>
              <div className="stat-label">Active</div>
            </div>
          </div>
          <div className="stat-card">
            <div className="stat-icon">📈</div>
            <div className="stat-content">
              <div className="stat-value">{statistics.total_records_processed.toLocaleString()}</div>
              <div className="stat-label">Records Processed</div>
            </div>
          </div>
          <div className="stat-card">
            <div className="stat-icon">✅</div>
            <div className="stat-content">
              <div className="stat-value">{statistics.average_quality_score?.toFixed(1)}%</div>
              <div className="stat-label">Avg Quality</div>
            </div>
          </div>
        </div>
      )}

      {/* Filters */}
      <div className="workflow-filters">
        <div className="filter-group">
          <label>Status:</label>
          <select 
            value={filter.status} 
            onChange={(e) => setFilter({...filter, status: e.target.value})}
          >
            <option value="all">All</option>
            <option value="draft">Draft</option>
            <option value="configured">Configured</option>
            <option value="running">Running</option>
            <option value="paused">Paused</option>
            <option value="completed">Completed</option>
            <option value="failed">Failed</option>
          </select>
        </div>
        
        <div className="filter-group">
          <label>Source:</label>
          <select 
            value={filter.sourceType} 
            onChange={(e) => setFilter({...filter, sourceType: e.target.value})}
          >
            <option value="all">All</option>
            <option value="teamcenter">Teamcenter</option>
            <option value="windchill">Windchill</option>
            <option value="catia">CATIA</option>
            <option value="nx">Siemens NX</option>
            <option value="creo">PTC Creo</option>
          </select>
        </div>

        <div className="filter-group">
          <label>Target:</label>
          <select 
            value={filter.targetType} 
            onChange={(e) => setFilter({...filter, targetType: e.target.value})}
          >
            <option value="all">All</option>
            <option value="neo4j">Neo4j</option>
            <option value="cloud_plm">Cloud PLM</option>
            <option value="opensearch">OpenSearch</option>
            <option value="warehouse">Warehouse</option>
            <option value="datalake">Data Lake</option>
          </select>
        </div>

        <div className="filter-group filter-search">
          <input 
            type="text"
            placeholder="🔍 Search workflows..."
            value={filter.search}
            onChange={(e) => setFilter({...filter, search: e.target.value})}
          />
        </div>
      </div>

      {/* Workflows Grid */}
      <div className="workflows-grid">
        {workflows.map((workflow) => (
          <div key={workflow.id} className="workflow-card">
            <div className="workflow-card-header">
              <div className="workflow-title-row">
                <h3 className="workflow-name">{workflow.name}</h3>
                <span className={`status-badge ${getStatusBadgeClass(workflow.status)}`}>
                  {workflow.status}
                </span>
              </div>
              <p className="workflow-description">{workflow.description}</p>
            </div>

            <div className="workflow-card-body">
              {/* Source → Target */}
              <div className="workflow-pipeline">
                <div className="pipeline-node">
                  <span className="node-icon">{getSourceIcon(workflow.source_type)}</span>
                  <span className="node-label">{workflow.source_name}</span>
                  <span className="node-type">{workflow.source_type}</span>
                </div>
                <div className="pipeline-arrow">→</div>
                <div className="pipeline-node">
                  <span className="node-icon">{getTargetIcon(workflow.target_type)}</span>
                  <span className="node-label">{workflow.target_name}</span>
                  <span className="node-type">{workflow.target_type}</span>
                </div>
              </div>

              {/* Progress Bar */}
              {workflow.status === 'running' && (
                <div className="workflow-progress">
                  <div className="progress-bar">
                    <div 
                      className="progress-fill" 
                      style={{ width: `${workflow.progress_percentage}%` }}
                    />
                  </div>
                  <span className="progress-text">{workflow.progress_percentage.toFixed(1)}%</span>
                </div>
              )}

              {/* Statistics */}
              <div className="workflow-stats">
                <div className="stat-item">
                  <span className="stat-label">Records:</span>
                  <span className="stat-value">{workflow.total_records.toLocaleString()}</span>
                </div>
                <div className="stat-item">
                  <span className="stat-label">Processed:</span>
                  <span className="stat-value">{workflow.processed_records.toLocaleString()}</span>
                </div>
                <div className="stat-item">
                  <span className="stat-label">Failed:</span>
                  <span className="stat-value failed">{workflow.failed_records}</span>
                </div>
                {workflow.quality_score && (
                  <div className="stat-item">
                    <span className="stat-label">Quality:</span>
                    <span className="stat-value quality">{workflow.quality_score.toFixed(1)}%</span>
                  </div>
                )}
              </div>

              {/* Timestamps */}
              <div className="workflow-timestamps">
                <small>Created: {new Date(workflow.created_at).toLocaleDateString()}</small>
                {workflow.started_at && (
                  <small>Started: {new Date(workflow.started_at).toLocaleTimeString()}</small>
                )}
              </div>
            </div>

            <div className="workflow-card-actions">
              <button 
                className="btn-action btn-view"
                onClick={() => handleViewWorkflow(workflow.id)}
                title="View Workflow Graph"
              >
                👁️ View
              </button>
              
              {workflow.status === 'draft' || workflow.status === 'configured' || workflow.status === 'paused' ? (
                <button 
                  className="btn-action btn-start"
                  onClick={() => handleWorkflowAction(workflow.id, 'start')}
                  title="Start Workflow"
                >
                  ▶️ Start
                </button>
              ) : null}
              
              {workflow.status === 'running' ? (
                <>
                  <button 
                    className="btn-action btn-pause"
                    onClick={() => handleWorkflowAction(workflow.id, 'pause')}
                    title="Pause Workflow"
                  >
                    ⏸️ Pause
                  </button>
                  <button 
                    className="btn-action btn-stop"
                    onClick={() => handleWorkflowAction(workflow.id, 'stop')}
                    title="Stop Workflow"
                  >
                    ⏹️ Stop
                  </button>
                </>
              ) : null}
              
              {(workflow.status === 'draft' || workflow.status === 'completed' || workflow.status === 'failed') && (
                <button 
                  className="btn-action btn-delete"
                  onClick={() => handleDeleteWorkflow(workflow.id)}
                  title="Delete Workflow"
                >
                  🗑️ Delete
                </button>
              )}
            </div>
          </div>
        ))}
      </div>

      {workflows.length === 0 && (
        <div className="empty-state">
          <div className="empty-icon">📭</div>
          <h3>No Workflows Found</h3>
          <p>Create your first workflow to start migrating PLM data</p>
          <button 
            className="btn-create-workflow"
            onClick={() => setShowCreateModal(true)}
          >
            ➕ Create Workflow
          </button>
        </div>
      )}

      {/* Create Workflow Modal (placeholder) */}
      {showCreateModal && (
        <div className="modal-overlay" onClick={() => setShowCreateModal(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2>Create New Workflow</h2>
              <button className="btn-close" onClick={() => setShowCreateModal(false)}>✕</button>
            </div>
            <div className="modal-body">
              <p>Use templates or configure custom source→target pipeline:</p>
              
              <div className="templates-list">
                {templates.map((template) => (
                  <div key={template.id} className="template-card">
                    <h4>{template.name}</h4>
                    <p>{template.description}</p>
                    <div className="template-meta">
                      <span>⏱️ {template.estimated_duration_hours}h</span>
                      <span>📊 {template.complexity}</span>
                    </div>
                    <button className="btn-use-template">Use Template</button>
                  </div>
                ))}
              </div>
              
              <button className="btn-custom-config">➕ Custom Configuration</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default WorkflowManagerPage;
