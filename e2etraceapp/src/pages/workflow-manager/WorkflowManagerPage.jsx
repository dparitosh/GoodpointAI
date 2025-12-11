import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import './WorkflowManagerPage.css';
import './WorkflowManagerPageWizard.css';

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
  const [showConfigModal, setShowConfigModal] = useState(false);
  const [configStep, setConfigStep] = useState(1);
  const [selectedTemplate, setSelectedTemplate] = useState(null);
  const [validationErrors, setValidationErrors] = useState({});
  const [showHelp, setShowHelp] = useState({});
  const [isLoading, setIsLoading] = useState(false);
  const [workflowConfig, setWorkflowConfig] = useState({
    name: '',
    source: {
      system: '',
      type: '',
      version: '',
      endpoint: '',
      authentication: ''
    },
    target: {
      system: '',
      type: '',
      uri: '',
      database: ''
    }
  });

  useEffect(() => {
    loadWorkflowData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filter]);

  const loadWorkflowData = async () => {
    try {
      setLoading(true);
      
      // Build query parameters from filter
      const params = new URLSearchParams();
      if (filter.status && filter.status !== 'all') {
        params.append('status', filter.status);
      }
      if (filter.sourceType && filter.sourceType !== 'all') {
        params.append('source_type', filter.sourceType);
      }
      if (filter.targetType && filter.targetType !== 'all') {
        params.append('target_type', filter.targetType);
      }
      if (filter.search && filter.search.trim()) {
        params.append('search', filter.search.trim());
      }
      
      // Load workflows with filters
      const queryString = params.toString();
      const workflowsUrl = queryString ? `/api/workflows/?${queryString}` : '/api/workflows/';
      const workflowsRes = await fetch(workflowsUrl);
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
      // Add timeout to prevent hanging requests
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 30000); // 30 second timeout
      
      const response = await fetch(`/api/workflows/${workflowId}/execute`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action, execution_params: {} }),
        signal: controller.signal
      });
      
      clearTimeout(timeoutId);
      
      if (response.ok) {
        const result = await response.json();
        console.log(`Workflow ${action} action succeeded:`, result.message);
        await loadWorkflowData();
      } else {
        const error = await response.json();
        console.error(`Workflow ${action} action failed:`, error.detail);
      }
    } catch (error) {
      if (error.name === 'AbortError') {
        console.error('Workflow action request timed out');
      } else {
        console.error('Error executing workflow action:', error);
      }
    }
  };

  const handleViewWorkflow = (workflowId) => {
    navigate(`/workflow/${workflowId}`);
  };

  const handleDeleteWorkflow = async (workflowId) => {
    // TODO: Replace with proper confirmation modal
    if (!window.confirm('Are you sure you want to delete this workflow?')) return;
    
    try {
      // Add timeout to prevent hanging requests
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 30000); // 30 second timeout
      
      const response = await fetch(`/api/workflows/${workflowId}`, {
        method: 'DELETE',
        signal: controller.signal
      });
      
      clearTimeout(timeoutId);
      
      if (response.ok) {
        console.log('Workflow deleted successfully:', workflowId);
        await loadWorkflowData();
      } else {
        console.error('Failed to delete workflow:', workflowId);
      }
    } catch (error) {
      if (error.name === 'AbortError') {
        console.error('Delete workflow request timed out');
      } else {
        console.error('Error deleting workflow:', error);
      }
    }
  };

  const handleUseTemplate = (template) => {
    // Set selected template and pre-fill configuration
    setSelectedTemplate(template);
    setConfigStep(1);
    setValidationErrors({});
    setShowHelp({});
    setWorkflowConfig({
      name: `${template.name} - ${new Date().toLocaleDateString()}`,
      source: {
        system: `${template.source_type.charAt(0).toUpperCase() + template.source_type.slice(1)} Production`,
        type: template.source_type,
        version: '13.2',
        endpoint: `https://${template.source_type}.company.com/api`,
        authentication: 'SOA'
      },
      target: {
        system: `${template.target_type.charAt(0).toUpperCase() + template.target_type.slice(1)} Instance`,
        type: template.target_type,
        uri: template.target_type === 'neo4j' ? 'neo4j+s://prod.databases.neo4j.io' : 'https://target.company.com',
        database: 'plm_migration'
      }
    });
    setShowCreateModal(false);
    setShowConfigModal(true);
  };

  const validateStep = (step) => {
    const errors = {};
    
    if (step === 1) {
      if (!workflowConfig.name || workflowConfig.name.trim().length < 3) {
        errors.name = 'Workflow name must be at least 3 characters';
      }
    } else if (step === 2) {
      if (!workflowConfig.source.system) errors.sourceSystem = 'Source system name is required';
      if (!workflowConfig.source.endpoint) errors.sourceEndpoint = 'Source endpoint is required';
      if (workflowConfig.source.endpoint && !workflowConfig.source.endpoint.startsWith('http')) {
        errors.sourceEndpoint = 'Endpoint must start with http:// or https://';
      }
    } else if (step === 3) {
      if (!workflowConfig.target.system) errors.targetSystem = 'Target system name is required';
      if (!workflowConfig.target.uri) errors.targetUri = 'Target URI is required';
      if (workflowConfig.target.uri && !workflowConfig.target.uri.match(/^(https?|neo4j)/)) {
        errors.targetUri = 'URI must start with http://, https://, or neo4j';
      }
    }
    
    setValidationErrors(errors);
    return Object.keys(errors).length === 0;
  };

  const handleNextStep = () => {
    if (validateStep(configStep)) {
      setConfigStep(configStep + 1);
    }
  };

  const handlePrevStep = () => {
    setConfigStep(configStep - 1);
    setValidationErrors({});
  };

  const toggleHelp = (field) => {
    setShowHelp({...showHelp, [field]: !showHelp[field]});
  };

  const handleCreateWorkflow = async () => {
    // Final validation
    if (!validateStep(1) || !validateStep(2) || !validateStep(3)) {
      console.warn('Validation failed before creating workflow');
      return;
    }

    setIsLoading(true);
    try {
      // Add timeout to prevent hanging requests
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 30000); // 30 second timeout
      
      const response = await fetch(
        `/api/workflows/templates/${selectedTemplate.id}/instantiate?source_id=${encodeURIComponent(workflowConfig.source.system)}&target_id=${encodeURIComponent(workflowConfig.target.system)}&name=${encodeURIComponent(workflowConfig.name)}`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          signal: controller.signal
        }
      );
      
      clearTimeout(timeoutId);
      
      if (response.ok) {
        const newWorkflow = await response.json();
        // Close modal and reset state first
        setShowConfigModal(false);
        setConfigStep(1);
        setValidationErrors({});
        // Wait for workflow list to refresh before navigating
        await loadWorkflowData();
        // Navigate immediately - no arbitrary timeout needed
        navigate(`/workflow/${newWorkflow.id}`);
      } else {
        const error = await response.json();
        console.error('Error creating workflow:', error.detail || 'Unknown error');
      }
    } catch (error) {
      if (error.name === 'AbortError') {
        console.error('Workflow creation request timed out');
      } else {
        console.error('Error creating workflow:', error);
      }
    } finally {
      setIsLoading(false);
    }
  };

  const handleCustomConfig = () => {
    console.info('Custom workflow configuration coming soon');
    // TODO: Implement custom configuration modal
    setShowCreateModal(false);
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
      teamcenter: '■',
      windchill: '◆',
      catia: '□',
      nx: '⚙',
      creo: '◇'
    };
    return iconMap[sourceType] || '▦';
  };

  const getTargetIcon = (targetType) => {
    const iconMap = {
      neo4j: '◈',
      cloud_plm: '☁',
      opensearch: '◎',
      warehouse: '▦',
      datalake: '◉'
    };
    return iconMap[targetType] || '◆';
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
          <h1>▦ Workflow Instance Manager</h1>
          <p className="header-subtitle">PLM Data Migration AI Factory - Manage Multiple Pipelines</p>
        </div>
        <button 
          className="btn-create-workflow"
          onClick={() => setShowCreateModal(true)}
        >
          ✚ Create Workflow
        </button>
      </div>

      {/* Statistics Dashboard */}
      {statistics && (
        <div className="workflow-statistics">
          <div className="stat-card">
            <div className="stat-icon">▦</div>
            <div className="stat-content">
              <div className="stat-value">{statistics.total_workflows}</div>
              <div className="stat-label">Total Workflows</div>
            </div>
          </div>
          <div className="stat-card">
            <div className="stat-icon">▶</div>
            <div className="stat-content">
              <div className="stat-value">{statistics.active_executions}</div>
              <div className="stat-label">Active</div>
            </div>
          </div>
          <div className="stat-card">
            <div className="stat-icon">▲</div>
            <div className="stat-content">
              <div className="stat-value">{statistics.total_records_processed.toLocaleString()}</div>
              <div className="stat-label">Records Processed</div>
            </div>
          </div>
          <div className="stat-card">
            <div className="stat-icon">✓</div>
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

      {/* Create Workflow Modal */}
      {showCreateModal && (
        <div className="modal-overlay" onClick={() => setShowCreateModal(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2>Create New Workflow</h2>
              <button className="btn-close" onClick={() => setShowCreateModal(false)}>×</button>
            </div>
            <div className="modal-body">
              <p>Use templates or configure custom source→target pipeline:</p>
              
              <div className="templates-list">
                {templates.length > 0 ? (
                  templates.map((template) => (
                    <div key={template.id} className="template-card">
                      <h4>{template.name}</h4>
                      <p>{template.description}</p>
                      <div className="template-meta">
                        <span>⌚ {template.estimated_duration_hours}h</span>
                        <span>▦ {template.complexity}</span>
                      </div>
                      <button 
                        className="btn-use-template"
                        onClick={() => handleUseTemplate(template)}
                      >
                        Use Template
                      </button>
                    </div>
                  ))
                ) : (
                  <div className="no-templates">
                    <p>Loading templates...</p>
                  </div>
                )}
              </div>
              
              <button 
                className="btn-custom-config"
                onClick={handleCustomConfig}
              >
                ✚ Custom Configuration
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Configuration Modal */}
      {showConfigModal && selectedTemplate && (
        <div className="modal-overlay" onClick={() => { setShowConfigModal(false); setConfigStep(1); }}>
          <div className="modal-wizard" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <div className="header-content">
                <h2>Configure Workflow</h2>
                <p className="template-name">Based on: {selectedTemplate.name}</p>
              </div>
              <button className="close-button" onClick={() => { setShowConfigModal(false); setConfigStep(1); }}>×</button>
            </div>

            {/* Progress Stepper */}
            <div className="wizard-stepper">
              <div className={`step ${configStep === 1 ? 'active' : configStep > 1 ? 'completed' : ''}`}>
                <div className="step-number">1</div>
                <div className="step-label">Workflow Info</div>
              </div>
              <div className="step-connector"></div>
              <div className={`step ${configStep === 2 ? 'active' : configStep > 2 ? 'completed' : ''}`}>
                <div className="step-number">2</div>
                <div className="step-label">Source System</div>
              </div>
              <div className="step-connector"></div>
              <div className={`step ${configStep === 3 ? 'active' : configStep > 3 ? 'completed' : ''}`}>
                <div className="step-number">3</div>
                <div className="step-label">Target System</div>
              </div>
              <div className="step-connector"></div>
              <div className={`step ${configStep === 4 ? 'active' : ''}`}>
                <div className="step-number">4</div>
                <div className="step-label">Review</div>
              </div>
            </div>

            <div className="modal-body">
              {/* Step 1: Workflow Information */}
              {configStep === 1 && (
                <div className="wizard-step">
                  <div className="step-header">
                    <h3>Workflow Information</h3>
                    <p className="step-description">Provide a descriptive name for this migration workflow</p>
                  </div>
                  <div className="form-container">
                    <div className="form-group">
                      <label htmlFor="workflow-name">
                        Workflow Name <span className="required">*</span>
                      </label>
                      <input
                        id="workflow-name"
                        type="text"
                        className={`form-control ${validationErrors.name ? 'error' : ''}`}
                        value={workflowConfig.name}
                        onChange={(e) => {
                          setWorkflowConfig({ ...workflowConfig, name: e.target.value });
                          if (validationErrors.name) setValidationErrors({ ...validationErrors, name: null });
                        }}
                        placeholder="e.g., Teamcenter to Neo4j Migration - December 2025"
                        autoFocus
                      />
                      {validationErrors.name && (
                        <div className="error-message">{validationErrors.name}</div>
                      )}
                      <button className="help-toggle" onClick={() => toggleHelp('name')}>
                        {showHelp.name ? '▼' : '▶'} Help
                      </button>
                      {showHelp.name && (
                        <div className="help-text">
                          Choose a descriptive name that includes the source, target, and purpose. 
                          This helps identify the workflow later when reviewing migration history.
                        </div>
                      )}
                    </div>
                    <div className="form-group readonly">
                      <label>Template</label>
                      <div className="readonly-field">
                        <span className="field-icon">◈</span>
                        {selectedTemplate.name}
                      </div>
                      <div className="field-description">{selectedTemplate.description}</div>
                    </div>
                  </div>
                </div>
              )}

              {/* Step 2: Source Configuration */}
              {configStep === 2 && (
                <div className="wizard-step">
                  <div className="step-header">
                    <h3>Source System Configuration</h3>
                    <p className="step-description">Configure the system you're migrating data from</p>
                  </div>
                  <div className="form-container">
                    <div className="form-row">
                      <div className="form-group">
                        <label htmlFor="source-system">
                          System Name <span className="required">*</span>
                        </label>
                        <input
                          id="source-system"
                          type="text"
                          className={`form-control ${validationErrors.sourceSystem ? 'error' : ''}`}
                          value={workflowConfig.source.system}
                          onChange={(e) => {
                            setWorkflowConfig({
                              ...workflowConfig,
                              source: { ...workflowConfig.source, system: e.target.value }
                            });
                            if (validationErrors.sourceSystem) setValidationErrors({ ...validationErrors, sourceSystem: null });
                          }}
                          placeholder="e.g., Teamcenter Production Environment"
                        />
                        {validationErrors.sourceSystem && (
                          <div className="error-message">{validationErrors.sourceSystem}</div>
                        )}
                      </div>
                      <div className="form-group">
                        <label htmlFor="source-type">System Type</label>
                        <input
                          id="source-type"
                          type="text"
                          className="form-control"
                          value={workflowConfig.source.type}
                          onChange={(e) => setWorkflowConfig({
                            ...workflowConfig,
                            source: { ...workflowConfig.source, type: e.target.value }
                          })}
                          placeholder="e.g., teamcenter, windchill"
                        />
                      </div>
                    </div>
                    <div className="form-row">
                      <div className="form-group">
                        <label htmlFor="source-version">Version</label>
                        <input
                          id="source-version"
                          type="text"
                          className="form-control"
                          value={workflowConfig.source.version}
                          onChange={(e) => setWorkflowConfig({
                            ...workflowConfig,
                            source: { ...workflowConfig.source, version: e.target.value }
                          })}
                          placeholder="e.g., 13.2, 12.3"
                        />
                      </div>
                      <div className="form-group">
                        <label htmlFor="source-endpoint">
                          Endpoint URL <span className="required">*</span>
                        </label>
                        <input
                          id="source-endpoint"
                          type="text"
                          className={`form-control ${validationErrors.sourceEndpoint ? 'error' : ''}`}
                          value={workflowConfig.source.endpoint}
                          onChange={(e) => {
                            setWorkflowConfig({
                              ...workflowConfig,
                              source: { ...workflowConfig.source, endpoint: e.target.value }
                            });
                            if (validationErrors.sourceEndpoint) setValidationErrors({ ...validationErrors, sourceEndpoint: null });
                          }}
                          placeholder="https://teamcenter.company.com/api"
                        />
                        {validationErrors.sourceEndpoint && (
                          <div className="error-message">{validationErrors.sourceEndpoint}</div>
                        )}
                      </div>
                    </div>
                    <div className="form-group">
                      <label htmlFor="source-auth">Authentication Method</label>
                      <select
                        id="source-auth"
                        className="form-control"
                        value={workflowConfig.source.authentication}
                        onChange={(e) => setWorkflowConfig({
                          ...workflowConfig,
                          source: { ...workflowConfig.source, authentication: e.target.value }
                        })}
                      >
                        <option value="SOA">SOA Authentication</option>
                        <option value="API_KEY">API Key</option>
                        <option value="OAUTH">OAuth 2.0</option>
                        <option value="BASIC">Basic Authentication</option>
                        <option value="SAML">SAML</option>
                      </select>
                      <button className="help-toggle" onClick={() => toggleHelp('sourceAuth')}>
                        {showHelp.sourceAuth ? '▼' : '▶'} Authentication Guide
                      </button>
                      {showHelp.sourceAuth && (
                        <div className="help-text">
                          <strong>SOA:</strong> Teamcenter Service-Oriented Architecture<br/>
                          <strong>API Key:</strong> Token-based authentication<br/>
                          <strong>OAuth 2.0:</strong> Industry-standard authorization<br/>
                          Credentials will be configured in the next step.
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              )}

              {/* Step 3: Target Configuration */}
              {configStep === 3 && (
                <div className="wizard-step">
                  <div className="step-header">
                    <h3>Target System Configuration</h3>
                    <p className="step-description">Configure the destination system for your migrated data</p>
                  </div>
                  <div className="form-container">
                    <div className="form-row">
                      <div className="form-group">
                        <label htmlFor="target-system">
                          System Name <span className="required">*</span>
                        </label>
                        <input
                          id="target-system"
                          type="text"
                          className={`form-control ${validationErrors.targetSystem ? 'error' : ''}`}
                          value={workflowConfig.target.system}
                          onChange={(e) => {
                            setWorkflowConfig({
                              ...workflowConfig,
                              target: { ...workflowConfig.target, system: e.target.value }
                            });
                            if (validationErrors.targetSystem) setValidationErrors({ ...validationErrors, targetSystem: null });
                          }}
                          placeholder="e.g., Neo4j Knowledge Graph Production"
                        />
                        {validationErrors.targetSystem && (
                          <div className="error-message">{validationErrors.targetSystem}</div>
                        )}
                      </div>
                      <div className="form-group">
                        <label htmlFor="target-type">System Type</label>
                        <input
                          id="target-type"
                          type="text"
                          className="form-control"
                          value={workflowConfig.target.type}
                          onChange={(e) => setWorkflowConfig({
                            ...workflowConfig,
                            target: { ...workflowConfig.target, type: e.target.value }
                          })}
                          placeholder="e.g., neo4j, postgresql"
                        />
                      </div>
                    </div>
                    <div className="form-row">
                      <div className="form-group">
                        <label htmlFor="target-uri">
                          Connection URI <span className="required">*</span>
                        </label>
                        <input
                          id="target-uri"
                          type="text"
                          className={`form-control ${validationErrors.targetUri ? 'error' : ''}`}
                          value={workflowConfig.target.uri}
                          onChange={(e) => {
                            setWorkflowConfig({
                              ...workflowConfig,
                              target: { ...workflowConfig.target, uri: e.target.value }
                            });
                            if (validationErrors.targetUri) setValidationErrors({ ...validationErrors, targetUri: null });
                          }}
                          placeholder="neo4j+s://xxxxx.databases.neo4j.io"
                        />
                        {validationErrors.targetUri && (
                          <div className="error-message">{validationErrors.targetUri}</div>
                        )}
                      </div>
                      <div className="form-group">
                        <label htmlFor="target-database">Database Name</label>
                        <input
                          id="target-database"
                          type="text"
                          className="form-control"
                          value={workflowConfig.target.database}
                          onChange={(e) => setWorkflowConfig({
                            ...workflowConfig,
                            target: { ...workflowConfig.target, database: e.target.value }
                          })}
                          placeholder="e.g., plm_migration, neo4j"
                        />
                      </div>
                    </div>
                    <button className="help-toggle" onClick={() => toggleHelp('targetConnection')}>
                      {showHelp.targetConnection ? '▼' : '▶'} Connection Help
                    </button>
                    {showHelp.targetConnection && (
                      <div className="help-text">
                        <strong>Neo4j URI format:</strong> neo4j+s://[instance-id].databases.neo4j.io<br/>
                        <strong>PostgreSQL format:</strong> postgresql://[host]:[port]/[database]<br/>
                        Connection credentials will be securely managed in the workflow settings.
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* Step 4: Review and Confirm */}
              {configStep === 4 && (
                <div className="wizard-step">
                  <div className="step-header">
                    <h3>Review Configuration</h3>
                    <p className="step-description">Verify all settings before creating your workflow</p>
                  </div>
                  <div className="review-container">
                    <div className="review-section">
                      <h4>Workflow Details</h4>
                      <div className="review-grid">
                        <div className="review-item">
                          <span className="label">Name:</span>
                          <span className="value">{workflowConfig.name}</span>
                        </div>
                        <div className="review-item">
                          <span className="label">Template:</span>
                          <span className="value">{selectedTemplate.name}</span>
                        </div>
                        <div className="review-item">
                          <span className="label">Initial Status:</span>
                          <span className="value status-badge draft">DRAFT</span>
                        </div>
                        <div className="review-item">
                          <span className="label">Initial Stage:</span>
                          <span className="value">IDLE (Ready for setup)</span>
                        </div>
                      </div>
                    </div>
                    <div className="review-section">
                      <h4>Source System</h4>
                      <div className="review-grid">
                        <div className="review-item">
                          <span className="label">System:</span>
                          <span className="value">{workflowConfig.source.system}</span>
                        </div>
                        <div className="review-item">
                          <span className="label">Type:</span>
                          <span className="value">{workflowConfig.source.type}</span>
                        </div>
                        <div className="review-item">
                          <span className="label">Version:</span>
                          <span className="value">{workflowConfig.source.version || 'Not specified'}</span>
                        </div>
                        <div className="review-item">
                          <span className="label">Endpoint:</span>
                          <span className="value endpoint">{workflowConfig.source.endpoint}</span>
                        </div>
                        <div className="review-item">
                          <span className="label">Authentication:</span>
                          <span className="value">{workflowConfig.source.authentication}</span>
                        </div>
                      </div>
                    </div>
                    <div className="review-section">
                      <h4>Target System</h4>
                      <div className="review-grid">
                        <div className="review-item">
                          <span className="label">System:</span>
                          <span className="value">{workflowConfig.target.system}</span>
                        </div>
                        <div className="review-item">
                          <span className="label">Type:</span>
                          <span className="value">{workflowConfig.target.type}</span>
                        </div>
                        <div className="review-item">
                          <span className="label">URI:</span>
                          <span className="value endpoint">{workflowConfig.target.uri}</span>
                        </div>
                        <div className="review-item">
                          <span className="label">Database:</span>
                          <span className="value">{workflowConfig.target.database}</span>
                        </div>
                      </div>
                    </div>
                    <div className="info-banner">
                      <div className="banner-icon">ⓘ</div>
                      <div className="banner-content">
                        <strong>Next Steps:</strong> After creating this workflow in DRAFT status, you'll be able to:
                        <ul>
                          <li>Configure detailed data mappings</li>
                          <li>Set up transformation rules</li>
                          <li>Test the connection to both systems</li>
                          <li>Review and validate before starting the migration</li>
                        </ul>
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </div>

            {/* Wizard Navigation */}
            <div className="wizard-footer">
              <div className="footer-actions">
                <button 
                  className="button-secondary" 
                  onClick={() => { setShowConfigModal(false); setConfigStep(1); }}
                >
                  Cancel
                </button>
                <div className="navigation-buttons">
                  {configStep > 1 && (
                    <button 
                      className="button-secondary" 
                      onClick={handlePrevStep}
                    >
                      ← Previous
                    </button>
                  )}
                  {configStep < 4 ? (
                    <button 
                      className="button-primary" 
                      onClick={handleNextStep}
                    >
                      Next →
                    </button>
                  ) : (
                    <button 
                      className="button-primary create" 
                      onClick={handleCreateWorkflow}
                      disabled={isLoading}
                    >
                      {isLoading ? 'Creating...' : '✓ Create Workflow'}
                    </button>
                  )}
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default WorkflowManagerPage;
