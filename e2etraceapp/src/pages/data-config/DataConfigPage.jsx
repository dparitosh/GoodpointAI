import React, { useState, useEffect } from 'react';
import { e2etraceFetchWithRetry } from '../../api/e2etrace-api.js';
import { API_CONFIG } from '../../config/api-config.js';
import workflowService from '../../services/workflow-service.js';
import './DataConfigPage.css';

const DataConfigPage = () => {
  const [dataSources, setDataSources] = useState([]);
  const [schemaInfo, setSchemaInfo] = useState({});
  const [activeTab, setActiveTab] = useState('sources');
  const [isLoading, setIsLoading] = useState(false);
  const [connectionStatus, setConnectionStatus] = useState({});
  const [workflowStatus, setWorkflowStatus] = useState({ status: 'not_started' });
  const [configurationProgress, setConfigurationProgress] = useState(0);
  
  // Data Source Management State
  const [showCreateSourceModal, setShowCreateSourceModal] = useState(false);
  const [editingSource, setEditingSource] = useState(null);
  const [newSourceConfig, setNewSourceConfig] = useState({
    name: '',
    type: 'database',
    connection: {
      host: '',
      port: '',
      database: '',
      username: '',
      password: ''
    },
    description: ''
  });
  
  // Available source types and their configurations
  const sourceTypes = {
    database: {
      name: 'Database (SQL)',
      fields: ['host', 'port', 'database', 'username', 'password'],
      defaultPort: '5432'
    },
    neo4j: {
      name: 'Neo4j Graph Database',
      fields: ['uri', 'username', 'password', 'database'],
      defaultPort: '7687'
    },
    mongodb: {
      name: 'MongoDB',
      fields: ['host', 'port', 'database', 'username', 'password'],
      defaultPort: '27017'
    },
    api: {
      name: 'REST API',
      fields: ['baseUrl', 'apiKey', 'authType'],
      defaultPort: '443'
    },
    file: {
      name: 'File Source',
      fields: ['path', 'format', 'delimiter'],
      defaultPort: null
    },
    kafka: {
      name: 'Apache Kafka',
      fields: ['brokers', 'topic', 'groupId'],
      defaultPort: '9092'
    }
  };
  
  // Neo4j Configuration State
  const [neo4jConfig, setNeo4jConfig] = useState({
    uri: 'bolt://localhost:7687',
    username: 'neo4j',
    password: '',
    database: 'neo4j'
  });
  const [showNeo4jConfig, setShowNeo4jConfig] = useState(false);
  const [configTestResult, setConfigTestResult] = useState(null);

  useEffect(() => {
    loadDataSources();
    loadSchemaInfo();
    loadNeo4jConfig();
    updateWorkflowStatus();
  }, []);

  const loadNeo4jConfig = async () => {
    try {
      const response = await e2etraceFetchWithRetry(API_CONFIG.ENDPOINTS.NEO4J_CONFIG);
      const config = await response.json();
      setNeo4jConfig({
        uri: config.uri || 'bolt://localhost:7687',
        username: config.username || 'neo4j',
        password: '', // Don't load password for security
        database: config.database || 'neo4j'
      });
      setConnectionStatus(prev => ({ ...prev, neo4j: config.connection_status === 'connected' }));
    } catch (error) {
      console.error('Error loading Neo4j config:', error);
    }
  };

  const updateWorkflowStatus = () => {
    setWorkflowStatus(workflowService.getWorkflowStatus());
  };

  const handleCompleteConfiguration = async () => {
    setIsLoading(true);
    try {
      await workflowService.executeDataConfiguration({
        schemaConfig: schemaInfo,
        dataSources: dataSources.filter(ds => ds.status === 'connected')
      });
      updateWorkflowStatus();
      alert('Data Configuration completed successfully! You can now proceed to Data Pipelines.');
    } catch (error) {
      console.error('Failed to complete data configuration:', error);
      alert('Failed to complete data configuration. Please check your connections and try again.');
    } finally {
      setIsLoading(false);
    }
  };

  const loadDataSources = async () => {
    setIsLoading(true);
    try {
      const response = await e2etraceFetchWithRetry(API_CONFIG.ENDPOINTS.DATA_SOURCES);
      const sources = await response.json();
      setDataSources(Array.isArray(sources) ? sources : []);
    } catch (error) {
      console.error('Error loading data sources:', error);
      setDataSources([]);
    } finally {
      setIsLoading(false);
    }
  };

  const loadSchemaInfo = async () => {
    try {
      const [labelsResponse, relsResponse] = await Promise.all([
        e2etraceFetchWithRetry(API_CONFIG.ENDPOINTS.SCHEMA_LABELS),
        e2etraceFetchWithRetry(API_CONFIG.ENDPOINTS.SCHEMA_RELATIONSHIPS)
      ]);

      const labels = await labelsResponse.json();
      const relationships = await relsResponse.json();

      setSchemaInfo({
        nodeLabels: labels.labels || [],
        relationshipTypes: relationships.types || [],
        totalNodes: labels.count || 0,
        totalRelationships: relationships.count || 0
      });

    } catch (error) {
      console.error('Error loading schema info:', error);
      setSchemaInfo({
        nodeLabels: [],
        relationshipTypes: [],
        totalNodes: 0,
        totalRelationships: 0
      });
    }
  };

  // ============= DATA SOURCE MANAGEMENT =============

  const createDataSource = async () => {
    try {
      setIsLoading(true);
      console.log('Creating data source with config:', newSourceConfig);
      
      const sourceData = {
        name: newSourceConfig.name,
        type: newSourceConfig.type,
        connection: newSourceConfig.connection,
        description: newSourceConfig.description,
        status: 'disconnected',
        created: new Date().toISOString()
      };

      console.log('Sending data to backend:', sourceData);

      // Save to backend using centralized API config
      const response = await e2etraceFetchWithRetry(API_CONFIG.ENDPOINTS.DATA_SOURCES, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(sourceData)
      });

      console.log('Backend response status:', response.status);

      if (response.ok) {
        const savedSource = await response.json();
        console.log('Saved source from backend:', savedSource);
        const sourceData = savedSource.data || savedSource;
        setDataSources(prev => [...prev, sourceData]);
        setShowCreateSourceModal(false);
        resetNewSourceConfig();
        
        // Test connection after creation (non-blocking)
        if (sourceData.id) {
          console.log('Testing connection for newly created source:', sourceData.id);
          testConnection(sourceData.id).catch(err => {
            console.warn('Connection test failed for new source, but source was created successfully:', err);
          });
        }
        
        alert('Data source created successfully!');
      } else {
        const errorData = await response.json();
        console.error('Backend error response:', errorData);
        throw new Error(errorData.message || 'Failed to create data source');
      }
    } catch (error) {
      console.error('Error creating data source:', error);
      alert('Failed to create data source: ' + error.message);
    } finally {
      setIsLoading(false);
    }
  };

  const updateDataSource = async (sourceId) => {
    try {
      setIsLoading(true);
      
      const response = await e2etraceFetchWithRetry(`${API_CONFIG.ENDPOINTS.DATA_SOURCES}/${sourceId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(editingSource)
      });

      if (response.ok) {
        const updatedSource = await response.json();
        setDataSources(prev => prev.map(s => s.id === sourceId ? (updatedSource.data || updatedSource) : s));
        setEditingSource(null);
        
        // Test updated connection
        await testConnection(sourceId);
      } else {
        const errorData = await response.json();
        throw new Error(errorData.message || 'Failed to update data source');
      }
    } catch (error) {
      console.error('Error updating data source:', error);
      alert('Failed to update data source: ' + error.message);
    } finally {
      setIsLoading(false);
    }
  };

  const deleteDataSource = async (sourceId) => {
    if (!confirm('Are you sure you want to delete this data source? This cannot be undone.')) {
      return;
    }

    try {
      setIsLoading(true);
      
      const response = await e2etraceFetchWithRetry(`${API_CONFIG.ENDPOINTS.DATA_SOURCES}/${sourceId}`, {
        method: 'DELETE'
      });

      if (response.ok) {
        setDataSources(prev => prev.filter(s => s.id !== sourceId));
      } else {
        const errorData = await response.json();
        throw new Error(errorData.message || 'Failed to delete data source');
      }
    } catch (error) {
      console.error('Error deleting data source:', error);
      alert('Failed to delete data source: ' + error.message);
    } finally {
      setIsLoading(false);
    }
  };

  const resetNewSourceConfig = () => {
    setNewSourceConfig({
      name: '',
      type: 'database',
      connection: {
        host: '',
        port: '',
        database: '',
        username: '',
        password: ''
      },
      description: ''
    });
  };

  const testConnection = async (sourceId) => {
    setIsLoading(true);
    try {
      console.log('Testing connection for source ID:', sourceId);
      const response = await e2etraceFetchWithRetry(API_CONFIG.ENDPOINTS.DATA_SOURCE_TEST(sourceId), {
        method: 'POST'
      });
      const result = await response.json();
      
      console.log('Connection test result:', result);
      
      // Update connection status based on test result
      setConnectionStatus(prev => ({ ...prev, [sourceId]: result.success }));
      
      if (result.success) {
        console.log('Connection test successful for', sourceId);
      } else {
        console.warn(`Connection test failed for ${sourceId}:`, result.message);
      }
      
      // Reload data sources to update status
      await loadDataSources();
    } catch (error) {
      console.error(`Connection test failed for ${sourceId}:`, error);
      setConnectionStatus(prev => ({ ...prev, [sourceId]: false }));
      // Don't show alert for connection test failures during creation
      // The user will see the status in the UI
    } finally {
      setIsLoading(false);
    }
  };

  const testNeo4jConfig = async () => {
    setIsLoading(true);
    setConfigTestResult(null);
    try {
      const response = await e2etraceFetchWithRetry(API_CONFIG.ENDPOINTS.NEO4J_CONFIG_TEST, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(neo4jConfig)
      });
      const result = await response.json();
      setConfigTestResult(result);
    } catch (error) {
      setConfigTestResult({
        status: 'failed',
        message: `Connection test failed: ${error.message}`
      });
    } finally {
      setIsLoading(false);
    }
  };

  const saveNeo4jConfig = async () => {
    setIsLoading(true);
    try {
      const response = await e2etraceFetchWithRetry(API_CONFIG.ENDPOINTS.NEO4J_CONFIG, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(neo4jConfig)
      });
      const result = await response.json();
      
      if (result.status === 'success') {
        setConfigTestResult(result);
        setConnectionStatus(prev => ({ ...prev, neo4j: true }));
        await loadDataSources(); // Refresh data sources
        alert('Neo4j configuration saved successfully!');
        setShowNeo4jConfig(false);
      } else {
        throw new Error(result.message);
      }
    } catch (error) {
      alert(`Failed to save configuration: ${error.message}`);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="data-config-page">
      <div className="page-header">
        <h1>📊 Data Configuration</h1>
        <p className="page-description">
          Configure and manage your data sources, schemas, and connections
        </p>
      </div>

      <div className="tab-navigation">
        <button 
          className={`tab ${activeTab === 'sources' ? 'active' : ''}`}
          onClick={() => setActiveTab('sources')}
        >
          🔗 Connected Sources
        </button>
        <button 
          className={`tab ${activeTab === 'manage' ? 'active' : ''}`}
          onClick={() => setActiveTab('manage')}
        >
          ⚙️ Manage Sources
        </button>
        <button 
          className={`tab ${activeTab === 'schema' ? 'active' : ''}`}
          onClick={() => setActiveTab('schema')}
        >
          📊 Schema & Structure
        </button>
        <button 
          className={`tab ${activeTab === 'validation' ? 'active' : ''}`}
          onClick={() => setActiveTab('validation')}
        >
          ✅ Data Validation
        </button>
      </div>

      <div className="content-area">
        {/* Connected Sources Tab */}
        {activeTab === 'sources' && (
          <div className="sources-section">
            <div className="section-header">
              <h2>Connected Data Sources</h2>
              <button 
                onClick={loadDataSources}
                className="btn btn-primary"
                disabled={isLoading}
              >
                🔄 Refresh Connections
              </button>
            </div>

            <div className="data-sources-grid">
              {dataSources.map(source => (
                <div key={source.id} className="data-source-card">
                  <div className="source-header">
                    <h3>{source.name}</h3>
                    <span className={`status-badge ${source.status}`}>
                      {source.status === 'connected' ? '🟢 Connected' : '🔴 Disconnected'}
                    </span>
                  </div>
                  
                  <div className="source-details">
                    <div className="detail-row">
                      <span className="label">Type:</span>
                      <span className="value">{source.type.toUpperCase()}</span>
                    </div>
                    <div className="detail-row">
                      <span className="label">Endpoint:</span>
                      <span className="value">{source.endpoint}</span>
                    </div>
                    <div className="detail-row">
                      <span className="label">Description:</span>
                      <span className="value">{source.description}</span>
                    </div>
                  </div>

                  <div className="source-actions">
                    <button 
                      onClick={() => testConnection(source.id)}
                      className="btn btn-secondary"
                      disabled={isLoading}
                    >
                      🔍 Test Connection
                    </button>
                    <button 
                      className="btn btn-outline"
                      onClick={() => {
                        if (source.id === 'neo4j') {
                          setShowNeo4jConfig(true);
                        }
                      }}
                    >
                      ⚙️ Configure
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Manage Sources Tab */}
        {activeTab === 'manage' && (
          <div className="manage-section">
            <div className="section-header">
              <h2>Data Source Management</h2>
              <button 
                onClick={() => setShowCreateSourceModal(true)}
                className="btn btn-primary"
              >
                ➕ Add New Data Source
              </button>
            </div>

            <div className="source-types-overview">
              <h3>Supported Data Source Types</h3>
              <div className="source-types-grid">
                {Object.entries(sourceTypes).map(([key, type]) => (
                  <div key={key} className="source-type-card">
                    <h4>{type.name}</h4>
                    <div className="type-details">
                      <p><strong>Required Fields:</strong></p>
                      <ul>
                        {type.fields.map(field => (
                          <li key={field}>{field}</li>
                        ))}
                      </ul>
                      {type.defaultPort && (
                        <p><strong>Default Port:</strong> {type.defaultPort}</p>
                      )}
                    </div>
                    <button 
                      className="btn btn-outline btn-sm"
                      onClick={() => {
                        setNewSourceConfig(prev => ({ ...prev, type: key }));
                        setShowCreateSourceModal(true);
                      }}
                    >
                      Create {type.name} Source
                    </button>
                  </div>
                ))}
              </div>
            </div>

            <div className="existing-sources">
              <h3>Existing Sources</h3>
              <div className="sources-table">
                <div className="table-header">
                  <span>Name</span>
                  <span>Type</span>
                  <span>Status</span>
                  <span>Actions</span>
                </div>
                {dataSources.map(source => (
                  <div key={source.id} className="table-row">
                    <span className="source-name">{source.name}</span>
                    <span className="source-type">{source.type}</span>
                    <span className={`source-status ${source.status}`}>
                      {source.status === 'connected' ? '✅ Connected' : '❌ Disconnected'}
                    </span>
                    <div className="source-actions">
                      <button 
                        className="btn btn-sm btn-outline"
                        onClick={() => testConnection(source.id)}
                        disabled={isLoading}
                      >
                        🔌 Test
                      </button>
                      <button 
                        className="btn btn-sm btn-secondary"
                        onClick={() => setEditingSource(source)}
                      >
                        ✏️ Edit
                      </button>
                      <button 
                        className="btn btn-sm btn-danger"
                        onClick={() => deleteDataSource(source.id)}
                      >
                        🗑️ Delete
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* Schema Tab */}
        {activeTab === 'schema' && (
          <div className="schema-section">
            <div className="section-header">
              <h2>Database Schema & Structure</h2>
              <button 
                onClick={loadSchemaInfo}
                className="btn btn-primary"
                disabled={isLoading}
              >
                🔄 Refresh Schema
              </button>
            </div>

            <div className="schema-stats">
              <div className="stat-card">
                <div className="stat-value">{schemaInfo.totalNodes || 0}</div>
                <div className="stat-label">Total Nodes</div>
              </div>
              <div className="stat-card">
                <div className="stat-value">{schemaInfo.totalRelationships || 0}</div>
                <div className="stat-label">Total Relationships</div>
              </div>
              <div className="stat-card">
                <div className="stat-value">{schemaInfo.nodeLabels?.length || 0}</div>
                <div className="stat-label">Node Types</div>
              </div>
              <div className="stat-card">
                <div className="stat-value">{schemaInfo.relationshipTypes?.length || 0}</div>
                <div className="stat-label">Relationship Types</div>
              </div>
            </div>

            <div className="schema-details">
              <div className="schema-column">
                <h3>Node Labels</h3>
                <div className="label-list">
                  {schemaInfo.nodeLabels?.map((label, index) => (
                    <div key={index} className="label-item">
                      <span className="label-name">{label}</span>
                    </div>
                  )) || <p>No node labels found</p>}
                </div>
              </div>

              <div className="schema-column">
                <h3>Relationship Types</h3>
                <div className="label-list">
                  {schemaInfo.relationshipTypes?.map((type, index) => (
                    <div key={index} className="label-item">
                      <span className="label-name">{type}</span>
                    </div>
                  )) || <p>No relationship types found</p>}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Validation Tab */}
        {activeTab === 'validation' && (
          <div className="validation-section">
            <div className="section-header">
              <h2>Data Quality Validation</h2>
              <button className="btn btn-primary">
                🔍 Run Validation
              </button>
            </div>

            <div className="validation-rules">
              <h3>Validation Rules</h3>
              <div className="rules-list">
                <div className="rule-item">
                  <span className="rule-name">Node Completeness</span>
                  <span className="rule-status">✅ Passed</span>
                </div>
                <div className="rule-item">
                  <span className="rule-name">Relationship Integrity</span>
                  <span className="rule-status">✅ Passed</span>
                </div>
                <div className="rule-item">
                  <span className="rule-name">Data Type Consistency</span>
                  <span className="rule-status">⚠️ Warning</span>
                </div>
                <div className="rule-item">
                  <span className="rule-name">Duplicate Detection</span>
                  <span className="rule-status">❌ Failed</span>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Create Source Modal */}
      {showCreateSourceModal && (
        <div className="modal-overlay" onClick={() => setShowCreateSourceModal(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2>➕ Create New Data Source</h2>
              <button 
                className="modal-close"
                onClick={() => setShowCreateSourceModal(false)}
              >
                ✕
              </button>
            </div>

            <div className="modal-body">
              <div className="form-group">
                <label>Source Name</label>
                <input
                  type="text"
                  value={newSourceConfig.name}
                  onChange={(e) => setNewSourceConfig(prev => ({ ...prev, name: e.target.value }))}
                  placeholder="Enter source name"
                />
              </div>

              <div className="form-group">
                <label>Source Type</label>
                <select
                  value={newSourceConfig.type}
                  onChange={(e) => setNewSourceConfig(prev => ({ ...prev, type: e.target.value }))}
                >
                  {Object.entries(sourceTypes).map(([key, type]) => (
                    <option key={key} value={key}>{type.name}</option>
                  ))}
                </select>
              </div>

              <div className="form-group">
                <label>Description</label>
                <textarea
                  value={newSourceConfig.description}
                  onChange={(e) => setNewSourceConfig(prev => ({ ...prev, description: e.target.value }))}
                  placeholder="Describe this data source"
                />
              </div>

              <h3>Connection Details</h3>
              {sourceTypes[newSourceConfig.type]?.fields.map(field => (
                <div key={field} className="form-group">
                  <label>{field.charAt(0).toUpperCase() + field.slice(1)}</label>
                  <input
                    type={field.includes('password') ? 'password' : 'text'}
                    value={newSourceConfig.connection[field] || ''}
                    onChange={(e) => setNewSourceConfig(prev => ({
                      ...prev,
                      connection: { ...prev.connection, [field]: e.target.value }
                    }))}
                    placeholder={field === 'port' ? sourceTypes[newSourceConfig.type].defaultPort : `Enter ${field}`}
                  />
                </div>
              ))}
            </div>

            <div className="modal-footer">
              <button
                className="btn btn-secondary"
                onClick={() => setShowCreateSourceModal(false)}
              >
                Cancel
              </button>
              <button
                className="btn btn-primary"
                onClick={() => {
                  console.log('Create Source button clicked');
                  console.log('newSourceConfig.name:', newSourceConfig.name);
                  console.log('isLoading:', isLoading);
                  console.log('Button disabled?', !newSourceConfig.name || isLoading);
                  createDataSource();
                }}
                disabled={!newSourceConfig.name || isLoading}
              >
                Create Source
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Neo4j Configuration Modal */}
      {showNeo4jConfig && (
        <div className="modal-overlay" onClick={() => setShowNeo4jConfig(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2>🗄️ Neo4j Database Configuration</h2>
              <button 
                className="modal-close"
                onClick={() => setShowNeo4jConfig(false)}
              >
                ✕
              </button>
            </div>

            <div className="modal-body">
              <p className="config-description">
                Configure your Neo4j database connection. These settings will be used by the Python backend to connect to your Neo4j instance.
              </p>

              <div className="config-form">
                <div className="form-group">
                  <label>Database URI</label>
                  <input
                    type="text"
                    value={neo4jConfig.uri}
                    onChange={(e) => setNeo4jConfig(prev => ({ ...prev, uri: e.target.value }))}
                    placeholder="bolt://localhost:7687"
                    className="form-input"
                  />
                  <small className="form-help">Format: bolt://hostname:port or neo4j://hostname:port</small>
                </div>

                <div className="form-group">
                  <label>Username</label>
                  <input
                    type="text"
                    value={neo4jConfig.username}
                    onChange={(e) => setNeo4jConfig(prev => ({ ...prev, username: e.target.value }))}
                    placeholder="neo4j"
                    className="form-input"
                  />
                </div>

                <div className="form-group">
                  <label>Password</label>
                  <input
                    type="password"
                    value={neo4jConfig.password}
                    onChange={(e) => setNeo4jConfig(prev => ({ ...prev, password: e.target.value }))}
                    placeholder="Enter password"
                    className="form-input"
                  />
                </div>

                <div className="form-group">
                  <label>Database Name</label>
                  <input
                    type="text"
                    value={neo4jConfig.database}
                    onChange={(e) => setNeo4jConfig(prev => ({ ...prev, database: e.target.value }))}
                    placeholder="neo4j"
                    className="form-input"
                  />
                  <small className="form-help">Default database name is usually 'neo4j'</small>
                </div>

                {configTestResult && (
                  <div className={`test-result ${configTestResult.status}`}>
                    <div className="result-icon">
                      {configTestResult.status === 'success' ? '✅' : '❌'}
                    </div>
                    <div className="result-message">
                      {configTestResult.message}
                    </div>
                  </div>
                )}
              </div>
            </div>

            <div className="modal-footer">
              <button
                className="btn btn-secondary"
                onClick={testNeo4jConfig}
                disabled={isLoading || !neo4jConfig.uri || !neo4jConfig.username || !neo4jConfig.password}
              >
                🔍 Test Connection
              </button>
              <button
                className="btn btn-primary"
                onClick={saveNeo4jConfig}
                disabled={isLoading || !neo4jConfig.uri || !neo4jConfig.username || !neo4jConfig.password}
              >
                💾 Save Configuration
              </button>
              <button
                className="btn btn-outline"
                onClick={() => setShowNeo4jConfig(false)}
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      {isLoading && (
        <div className="loading-overlay">
          <div className="loading-spinner">Loading...</div>
        </div>
      )}
    </div>
  );
};

export default DataConfigPage;
