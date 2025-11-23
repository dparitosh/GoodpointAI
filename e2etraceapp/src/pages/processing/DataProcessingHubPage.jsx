import React, { useState, useEffect, useCallback } from 'react';
import { etlWorkflowService } from '../../services/etl-workflow-service';
import { etlEngine } from '../../services/etl-engine';
import goodPointLogo from '../../assets/goodpoint-logo.svg';
import './DataProcessingHubPage.css';

const DataProcessingHubPage = () => {
  // State management
  const [activeTab, setActiveTab] = useState('workflows');
  const [workflows, setWorkflows] = useState([]);
  const [templates, setTemplates] = useState([]);
  const [metrics, setMetrics] = useState({});
  const [selectedWorkflow, setSelectedWorkflow] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  
  // Workflow creation state
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [selectedTemplate, setSelectedTemplate] = useState('');
  const [workflowConfig, setWorkflowConfig] = useState({});
  
  // Data processing state
  const [processingData, setProcessingData] = useState(null);
  const [processingResults, setProcessingResults] = useState([]);

  // Load initial data
  useEffect(() => {
    loadTemplates();
    loadMetrics();
    loadWorkflows();
  }, []);

  const loadTemplates = useCallback(() => {
    const workflowTemplates = etlWorkflowService.listWorkflowTemplates();
    setTemplates(workflowTemplates);
  }, []);

  const loadMetrics = useCallback(() => {
    const workflowMetrics = etlWorkflowService.getWorkflowMetrics();
    setMetrics(workflowMetrics);
  }, []);

  const loadWorkflows = useCallback(() => {
    // Get recent workflows from the service
    const recentWorkflows = Array.from(etlWorkflowService.workflows.values())
      .sort((a, b) => new Date(b.created) - new Date(a.created))
      .slice(0, 20);
    setWorkflows(recentWorkflows);
  }, []);

  // Workflow management
  const createWorkflow = async (templateId, config) => {
    try {
      setIsLoading(true);
      const workflow = await etlWorkflowService.createWorkflow(templateId, config);
      setWorkflows(prev => [workflow, ...prev]);
      setShowCreateModal(false);
      setSelectedTemplate('');
      setWorkflowConfig({});
      return workflow;
    } catch (error) {
      console.error('Failed to create workflow:', error);
      alert(`Failed to create workflow: ${error.message}`);
    } finally {
      setIsLoading(false);
    }
  };

  const executeWorkflow = async (workflowId, inputData = null) => {
    try {
      setIsLoading(true);
      const result = await etlWorkflowService.executeWorkflow(workflowId, inputData);
      
      // Update workflow status
      setWorkflows(prev => prev.map(w => 
        w.id === workflowId 
          ? { ...w, status: result.status, metrics: result.metrics }
          : w
      ));
      
      setProcessingResults(prev => [result, ...prev.slice(0, 9)]);
      loadMetrics(); // Refresh metrics
      
      return result;
    } catch (error) {
      console.error('Workflow execution failed:', error);
      alert(`Workflow execution failed: ${error.message}`);
    } finally {
      setIsLoading(false);
    }
  };

  const deleteWorkflow = (workflowId) => {
    if (confirm('Are you sure you want to delete this workflow?')) {
      etlWorkflowService.workflows.delete(workflowId);
      setWorkflows(prev => prev.filter(w => w.id !== workflowId));
      if (selectedWorkflow?.id === workflowId) {
        setSelectedWorkflow(null);
      }
    }
  };

  // Quick processing functions
  const processFile = async (file, processingType = 'import') => {
    try {
      setIsLoading(true);
      let result;
      
      switch (processingType) {
        case 'import':
          result = await etlWorkflowService.processSpreadsheetData(file, {
            exportFormat: 'excel',
            validationRules: []
          });
          break;
        
        case 'validate':
          // Extract data first, then validate
          const extractResult = await etlEngine.extract('csv', { file });
          result = await etlWorkflowService.validateDataQuality(extractResult.data);
          break;
        
        case 'convert':
          const workflow = await etlWorkflowService.createWorkflow('spreadsheet_processing', {
            name: `Convert ${file.name}`,
            conversion: true
          });
          result = await etlWorkflowService.executeWorkflow(workflow.id, null, { file });
          break;
      }
      
      setProcessingResults(prev => [result, ...prev.slice(0, 9)]);
      loadMetrics();
      
    } catch (error) {
      console.error('File processing failed:', error);
      alert(`File processing failed: ${error.message}`);
    } finally {
      setIsLoading(false);
    }
  };

  const getStatusColor = (status) => {
    switch (status) {
      case 'completed': return '#28a745';
      case 'running': return '#007bff';
      case 'failed': return '#dc3545';
      case 'pending': return '#6c757d';
      default: return '#6c757d';
    }
  };

  const formatDuration = (ms) => {
    if (!ms) return '0ms';
    if (ms < 1000) return `${ms}ms`;
    if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
    return `${(ms / 60000).toFixed(1)}m`;
  };

  return (
    <div className="data-processing-hub">
      <div className="page-header">
        <div className="page-header-branding">
          <img src={goodPointLogo} alt="GoodPoint" className="page-logo" />
          <div className="page-title-section">
            <h1>Data Processing Hub</h1>
            <p className="page-subtitle">AI powered PLM Data migration</p>
          </div>
        </div>
        <p className="page-description">
          Centralized Extract, Transform, Load (ETL) operations and data processing workflows
        </p>
        
        <div className="metrics-summary">
          <div className="metric-card">
            <span className="metric-value">{metrics.totalWorkflows || 0}</span>
            <span className="metric-label">Total Workflows</span>
          </div>
          <div className="metric-card">
            <span className="metric-value">{metrics.successfulRuns || 0}</span>
            <span className="metric-label">Successful Runs</span>
          </div>
          <div className="metric-card">
            <span className="metric-value">{metrics.activeWorkflows || 0}</span>
            <span className="metric-label">Active</span>
          </div>
          <div className="metric-card">
            <span className="metric-value">{formatDuration(metrics.avgDuration)}</span>
            <span className="metric-label">Avg Duration</span>
          </div>
        </div>
      </div>

      <div className="tab-navigation">
        <button 
          className={`tab ${activeTab === 'workflows' ? 'active' : ''}`}
          onClick={() => setActiveTab('workflows')}
        >
          🔄 Workflows
        </button>
        <button 
          className={`tab ${activeTab === 'templates' ? 'active' : ''}`}
          onClick={() => setActiveTab('templates')}
        >
          📋 Templates
        </button>
        <button 
          className={`tab ${activeTab === 'processing' ? 'active' : ''}`}
          onClick={() => setActiveTab('processing')}
        >
          ⚡ Quick Processing
        </button>
        <button 
          className={`tab ${activeTab === 'monitor' ? 'active' : ''}`}
          onClick={() => setActiveTab('monitor')}
        >
          📊 Monitor
        </button>
      </div>

      <div className="content-area">
        {/* Workflows Tab */}
        {activeTab === 'workflows' && (
          <div className="workflows-section">
            <div className="section-header">
              <h2>Active Workflows</h2>
              <button 
                onClick={() => setShowCreateModal(true)}
                className="btn btn-primary"
                disabled={isLoading}
              >
                ➕ Create Workflow
              </button>
            </div>

            <div className="workflows-grid">
              {workflows.map(workflow => (
                <div key={workflow.id} className="workflow-card">
                  <div className="workflow-header">
                    <h3>{workflow.name}</h3>
                    <span 
                      className="status-badge" 
                      style={{ backgroundColor: getStatusColor(workflow.status) }}
                    >
                      {workflow.status.toUpperCase()}
                    </span>
                  </div>

                  <div className="workflow-details">
                    <p className="workflow-description">{workflow.description}</p>
                    
                    <div className="workflow-progress">
                      <div className="progress-bar">
                        <div 
                          className="progress-fill" 
                          style={{ 
                            width: `${etlWorkflowService.calculateProgress(workflow)}%`,
                            backgroundColor: getStatusColor(workflow.status)
                          }}
                        />
                      </div>
                      <span className="progress-text">
                        {etlWorkflowService.calculateProgress(workflow).toFixed(0)}%
                      </span>
                    </div>

                    <div className="workflow-stats">
                      <span className="stat">📊 {workflow.metrics?.recordsProcessed || 0} records</span>
                      <span className="stat">⏱️ {formatDuration(workflow.metrics?.duration)}</span>
                      <span className="stat">📅 {new Date(workflow.created).toLocaleDateString()}</span>
                    </div>

                    {workflow.error && (
                      <div className="error-message">
                        <strong>Error:</strong> {workflow.error}
                      </div>
                    )}
                  </div>

                  <div className="workflow-actions">
                    {workflow.status === 'created' && (
                      <button 
                        onClick={() => executeWorkflow(workflow.id)}
                        className="btn btn-success btn-sm"
                        disabled={isLoading}
                      >
                        ▶️ Execute
                      </button>
                    )}
                    <button 
                      onClick={() => setSelectedWorkflow(workflow)}
                      className="btn btn-secondary btn-sm"
                    >
                      👁️ View Details
                    </button>
                    {workflow.status !== 'running' && (
                      <button 
                        onClick={() => deleteWorkflow(workflow.id)}
                        className="btn btn-danger btn-sm"
                      >
                        🗑️ Delete
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Templates Tab */}
        {activeTab === 'templates' && (
          <div className="templates-section">
            <div className="section-header">
              <h2>Workflow Templates</h2>
            </div>

            <div className="templates-grid">
              {templates.map(template => (
                <div key={template.id} className="template-card">
                  <div className="template-header">
                    <h3>{template.name}</h3>
                    <span className="template-version">v{template.version}</span>
                  </div>

                  <p className="template-description">{template.description}</p>

                  <div className="template-steps">
                    <h4>Processing Steps:</h4>
                    <div className="steps-list">
                      {template.steps.map((step, index) => (
                        <div key={index} className="step-item">
                          <span className="step-number">{index + 1}</span>
                          <span className="step-name">{step.stage}</span>
                          <span className="step-type">{step.type}</span>
                        </div>
                      ))}
                    </div>
                  </div>

                  <div className="template-actions">
                    <button 
                      onClick={() => {
                        setSelectedTemplate(template.id);
                        setShowCreateModal(true);
                      }}
                      className="btn btn-primary btn-sm"
                    >
                      📥 Use Template
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Quick Processing Tab */}
        {activeTab === 'processing' && (
          <div className="processing-section">
            <div className="section-header">
              <h2>Quick Data Processing</h2>
              <p>Upload files for immediate processing without creating workflows</p>
            </div>

            <div className="processing-options">
              <div className="processing-card">
                <h3>📊 Data Import & Validation</h3>
                <p>Import CSV, Excel, or JSON files with automatic validation</p>
                <input 
                  type="file" 
                  accept=".csv,.xlsx,.xls,.json"
                  onChange={(e) => e.target.files[0] && processFile(e.target.files[0], 'import')}
                  disabled={isLoading}
                />
                <button className="btn btn-primary" disabled={isLoading}>
                  Import & Validate
                </button>
              </div>

              <div className="processing-card">
                <h3>🔄 Data Conversion</h3>
                <p>Convert between different data formats (CSV, Excel, JSON, XML)</p>
                <input 
                  type="file" 
                  accept=".csv,.xlsx,.xls,.json,.xml"
                  onChange={(e) => e.target.files[0] && processFile(e.target.files[0], 'convert')}
                  disabled={isLoading}
                />
                <button className="btn btn-primary" disabled={isLoading}>
                  Convert Data
                </button>
              </div>

              <div className="processing-card">
                <h3>✅ Quality Assessment</h3>
                <p>Analyze data quality and identify issues</p>
                <input 
                  type="file" 
                  accept=".csv,.xlsx,.xls,.json"
                  onChange={(e) => e.target.files[0] && processFile(e.target.files[0], 'validate')}
                  disabled={isLoading}
                />
                <button className="btn btn-primary" disabled={isLoading}>
                  Assess Quality
                </button>
              </div>
            </div>

            {/* Recent Processing Results */}
            {processingResults.length > 0 && (
              <div className="results-section">
                <h3>Recent Processing Results</h3>
                <div className="results-list">
                  {processingResults.map((result, index) => (
                    <div key={index} className="result-item">
                      <div className="result-header">
                        <span className="result-name">{result.workflowId}</span>
                        <span 
                          className="result-status"
                          style={{ color: getStatusColor(result.status) }}
                        >
                          {result.status}
                        </span>
                      </div>
                      <div className="result-details">
                        <span>📊 {result.metrics?.recordsProcessed || 0} records</span>
                        <span>⏱️ {formatDuration(result.metrics?.duration)}</span>
                        <span>⚠️ {result.metrics?.errors?.length || 0} errors</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* Monitor Tab */}
        {activeTab === 'monitor' && (
          <div className="monitor-section">
            <div className="section-header">
              <h2>Processing Monitor</h2>
            </div>

            <div className="monitor-grid">
              <div className="monitor-card">
                <h3>System Performance</h3>
                <div className="performance-metrics">
                  <div className="metric">
                    <label>Average Throughput:</label>
                    <span>{metrics.throughput?.toFixed(2) || '0'} records/sec</span>
                  </div>
                  <div className="metric">
                    <label>Success Rate:</label>
                    <span>{((metrics.successfulRuns / Math.max(metrics.totalWorkflows, 1)) * 100).toFixed(1)}%</span>
                  </div>
                  <div className="metric">
                    <label>Average Duration:</label>
                    <span>{formatDuration(metrics.avgDuration)}</span>
                  </div>
                </div>
              </div>

              <div className="monitor-card">
                <h3>Active Processing</h3>
                <div className="active-workflows">
                  {workflows.filter(w => w.status === 'running').map(workflow => (
                    <div key={workflow.id} className="active-workflow">
                      <span className="workflow-name">{workflow.name}</span>
                      <div className="progress-indicator">
                        <div className="progress-bar">
                          <div 
                            className="progress-fill running"
                            style={{ width: `${etlWorkflowService.calculateProgress(workflow)}%` }}
                          />
                        </div>
                      </div>
                    </div>
                  ))}
                  {workflows.filter(w => w.status === 'running').length === 0 && (
                    <p className="no-active">No active processing workflows</p>
                  )}
                </div>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Create Workflow Modal */}
      {showCreateModal && (
        <div className="modal-overlay">
          <div className="modal">
            <div className="modal-header">
              <h3>Create New Workflow</h3>
              <button 
                onClick={() => setShowCreateModal(false)}
                className="modal-close"
              >
                ✕
              </button>
            </div>

            <div className="modal-body">
              <div className="form-group">
                <label>Workflow Template:</label>
                <select 
                  value={selectedTemplate}
                  onChange={(e) => setSelectedTemplate(e.target.value)}
                >
                  <option value="">Select a template</option>
                  {templates.map(template => (
                    <option key={template.id} value={template.id}>
                      {template.name}
                    </option>
                  ))}
                </select>
              </div>

              {selectedTemplate && (
                <>
                  <div className="form-group">
                    <label>Workflow Name:</label>
                    <input 
                      type="text"
                      value={workflowConfig.name || ''}
                      onChange={(e) => setWorkflowConfig(prev => ({ ...prev, name: e.target.value }))}
                      placeholder="Enter workflow name"
                    />
                  </div>

                  <div className="form-group">
                    <label>Description:</label>
                    <textarea 
                      value={workflowConfig.description || ''}
                      onChange={(e) => setWorkflowConfig(prev => ({ ...prev, description: e.target.value }))}
                      placeholder="Enter workflow description"
                    />
                  </div>
                </>
              )}
            </div>

            <div className="modal-footer">
              <button 
                onClick={() => setShowCreateModal(false)}
                className="btn btn-secondary"
              >
                Cancel
              </button>
              <button 
                onClick={() => createWorkflow(selectedTemplate, workflowConfig)}
                className="btn btn-primary"
                disabled={!selectedTemplate || isLoading}
              >
                Create Workflow
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Workflow Details Modal */}
      {selectedWorkflow && (
        <div className="modal-overlay">
          <div className="modal large">
            <div className="modal-header">
              <h3>{selectedWorkflow.name} - Details</h3>
              <button 
                onClick={() => setSelectedWorkflow(null)}
                className="modal-close"
              >
                ✕
              </button>
            </div>

            <div className="modal-body">
              <div className="workflow-details-grid">
                <div className="detail-section">
                  <h4>Workflow Information</h4>
                  <div className="detail-item">
                    <label>Status:</label>
                    <span style={{ color: getStatusColor(selectedWorkflow.status) }}>
                      {selectedWorkflow.status.toUpperCase()}
                    </span>
                  </div>
                  <div className="detail-item">
                    <label>Created:</label>
                    <span>{new Date(selectedWorkflow.created).toLocaleString()}</span>
                  </div>
                  <div className="detail-item">
                    <label>Description:</label>
                    <span>{selectedWorkflow.description}</span>
                  </div>
                </div>

                <div className="detail-section">
                  <h4>Processing Steps</h4>
                  <div className="steps-timeline">
                    {selectedWorkflow.steps.map((step, index) => (
                      <div key={step.id} className={`step-timeline-item ${step.status}`}>
                        <div className="step-number">{index + 1}</div>
                        <div className="step-info">
                          <div className="step-name">{step.stage}</div>
                          <div className="step-type">{step.type}</div>
                          <div className="step-status">{step.status}</div>
                          {step.duration && (
                            <div className="step-duration">{formatDuration(step.duration)}</div>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                {selectedWorkflow.metrics && (
                  <div className="detail-section">
                    <h4>Metrics</h4>
                    <div className="metrics-grid">
                      <div className="metric">
                        <label>Records Processed:</label>
                        <span>{selectedWorkflow.metrics.recordsProcessed}</span>
                      </div>
                      <div className="metric">
                        <label>Duration:</label>
                        <span>{formatDuration(selectedWorkflow.metrics.duration)}</span>
                      </div>
                      <div className="metric">
                        <label>Errors:</label>
                        <span>{selectedWorkflow.metrics.errors?.length || 0}</span>
                      </div>
                      <div className="metric">
                        <label>Warnings:</label>
                        <span>{selectedWorkflow.metrics.warnings?.length || 0}</span>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            </div>

            <div className="modal-footer">
              <button 
                onClick={() => setSelectedWorkflow(null)}
                className="btn btn-secondary"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {isLoading && (
        <div className="loading-overlay">
          <div className="loading-spinner">Processing...</div>
        </div>
      )}
    </div>
  );
};

export default DataProcessingHubPage;
