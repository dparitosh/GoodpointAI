import React, { useState, useEffect } from 'react';
import { e2etraceFetchWithRetry } from '../../api/e2etrace-api';
import { API_CONFIG } from '../../config/api-config.js';
import './DataMappingPage.css';

const DataMappingPage = () => {
  const [mappings, setMappings] = useState([]);
  const [templates, setTemplates] = useState([]);
  const [activeTab, setActiveTab] = useState('mappings');
  const [isLoading, setIsLoading] = useState(false);
  const [selectedMapping, setSelectedMapping] = useState(null);

  // Load real data from Neo4j via API
  useEffect(() => {
    loadMappings();
    loadTemplates();
  }, []);

  const loadMappings = async () => {
    setIsLoading(true);
    try {
      const response = await e2etraceFetchWithRetry(API_CONFIG.ENDPOINTS.DATA_MAPPING_RULES);
      const data = await response.json();
      const mappingsFromAPI = Array.isArray(data) ? data.map(mapping => ({
        id: mapping.id,
        name: mapping.name,
        description: mapping.description,
        sourceSystem: mapping.source_system_id,
        targetSystem: mapping.target_system_id,
        status: mapping.status,
        fields: mapping.field_mappings?.length || 0,
        lastModified: mapping.updated_at || mapping.created_at
      })) : [];
      
      setMappings(mappingsFromAPI);
    } catch (error) {
      console.error('Error loading mappings:', error);
      setMappings([]);
    } finally {
      setIsLoading(false);
    }
  };

  const loadTemplates = async () => {
    try {
      const response = await e2etraceFetchWithRetry(API_CONFIG.ENDPOINTS.DATA_MAPPING_TEMPLATES);
      const templatesFromAPI = await response.json();
      
      const processedTemplates = Array.isArray(templatesFromAPI) ? templatesFromAPI.map(template => ({
        id: template.id,
        name: template.name,
        description: template.description,
        category: template.category,
        sourceType: template.source_type,
        targetType: template.target_type,
        fieldMappings: template.field_mappings || [],
        tags: template.tags || []
      })) : [];
      
      setTemplates(processedTemplates);
    } catch (error) {
      console.error('Error loading templates:', error);
      setTemplates([]);
    }
  };

  const createNewMapping = async () => {
    try {
      const newMapping = {
        name: 'New Mapping',
        description: 'Enter mapping description',
        source_system_id: 'neo4j',
        target_system_id: 'nifi', 
        field_mappings: [],
        status: 'draft'
      };

      const response = await e2etraceFetchWithRetry(API_CONFIG.ENDPOINTS.DATA_MAPPING_RULES, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newMapping)
      });

      if (response.ok) {
        const createdMapping = await response.json();
        setMappings(prev => [...prev, {
          id: createdMapping.id,
          name: createdMapping.name,
          description: createdMapping.description,
          sourceSystem: createdMapping.source_system_id,
          targetSystem: createdMapping.target_system_id,
          status: createdMapping.status,
          fields: createdMapping.field_mappings?.length || 0,
          lastModified: createdMapping.updated_at || createdMapping.created_at
        }]);
        setSelectedMapping(createdMapping);
        setActiveTab('editor');
      }
    } catch (error) {
      console.error('Error creating mapping:', error);
      alert('Failed to create mapping: ' + error.message);
    }
  };

  const updateMapping = async (mappingData) => {
    try {
      const response = await e2etraceFetchWithRetry(`${API_CONFIG.ENDPOINTS.DATA_MAPPING_RULES}/${mappingData.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(mappingData)
      });

      if (response.ok) {
        const updatedMapping = await response.json();
        setMappings(prev => prev.map(m => m.id === mappingData.id ? {
          id: updatedMapping.id,
          name: updatedMapping.name,
          description: updatedMapping.description,
          sourceSystem: updatedMapping.source_system_id,
          targetSystem: updatedMapping.target_system_id,
          status: updatedMapping.status,
          fields: updatedMapping.field_mappings?.length || 0,
          lastModified: updatedMapping.updated_at
        } : m));
        setSelectedMapping(updatedMapping);
      }
    } catch (error) {
      console.error('Error updating mapping:', error);
      alert('Failed to update mapping: ' + error.message);
    }
  };

  const deleteMapping = async (mappingId) => {
    if (!confirm('Are you sure you want to delete this mapping?')) return;
    
    try {
      const response = await e2etraceFetchWithRetry(`${API_CONFIG.ENDPOINTS.DATA_MAPPING_RULES}/${mappingId}`, {
        method: 'DELETE'
      });

      if (response.ok) {
        setMappings(prev => prev.filter(m => m.id !== mappingId));
        if (selectedMapping?.id === mappingId) {
          setSelectedMapping(null);
        }
      }
    } catch (error) {
      console.error('Error deleting mapping:', error);
      alert('Failed to delete mapping: ' + error.message);
    }
  };

  // Add utility functions for mapping management

  const applyTemplate = async (template) => {
    try {
      const sourceId = prompt('Enter source system ID:');
      const targetId = prompt('Enter target system ID:');
      const mappingName = prompt('Enter mapping name:');
      
      if (!sourceId || !targetId || !mappingName) return;

      const response = await e2etraceFetchWithRetry(
        `${API_CONFIG.ENDPOINTS.DATA_MAPPING_APPLY_TEMPLATE(template.id)}?source_system_id=${sourceId}&target_system_id=${targetId}&rule_name=${mappingName}`,
        { method: 'POST' }
      );

      if (response.ok) {
        const newMapping = await response.json();
        await loadMappings(); // Reload mappings
        setSelectedMapping(newMapping);
        setActiveTab('editor');
        alert('Template applied successfully!');
      }
    } catch (error) {
      console.error('Error applying template:', error);
      alert('Failed to apply template: ' + error.message);
    }
  };

  const editMapping = (mapping) => {
    setSelectedMapping(mapping);
    setActiveTab('editor');
  };

  const executeMapping = async (mappingId) => {
    try {
      setIsLoading(true);
      const response = await e2etraceFetchWithRetry(API_CONFIG.ENDPOINTS.DATA_MAPPING_EXECUTE(mappingId), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          mapping_id: mappingId,
          execution_mode: 'execute',
          batch_size: 1000
        })
      });

      if (response.ok) {
        const result = await response.json();
        if (result.success) {
          alert(`Mapping executed successfully! Processed ${result.records_processed} records.`);
        } else {
          alert(`Mapping execution failed: ${result.message}`);
        }
      }
    } catch (error) {
      console.error('Error executing mapping:', error);
      alert('Failed to execute mapping: ' + error.message);
    } finally {
      setIsLoading(false);
    }
  };

  const validateMapping = async (mappingId) => {
    try {
      setIsLoading(true);
      const response = await e2etraceFetchWithRetry(API_CONFIG.ENDPOINTS.DATA_MAPPING_VALIDATE(mappingId), {
        method: 'POST'
      });

      if (response.ok) {
        const result = await response.json();
        if (result.success) {
          alert('Mapping validation passed!');
        } else {
          alert(`Mapping validation failed: ${result.message}\nErrors: ${result.errors?.join(', ')}`);
        }
      }
    } catch (error) {
      console.error('Error validating mapping:', error);
      alert('Failed to validate mapping: ' + error.message);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="data-mapping-page">
      <div className="page-header">
        <h1>◳ Data Mapping</h1>
        <p className="page-description">
          Configure data transformation and mapping rules between systems
        </p>
      </div>

      <div className="tab-navigation">
        <button 
          className={`tab ${activeTab === 'mappings' ? 'active' : ''}`}
          onClick={() => setActiveTab('mappings')}
        >
          ◻ Active Mappings
        </button>
        <button 
          className={`tab ${activeTab === 'templates' ? 'active' : ''}`}
          onClick={() => setActiveTab('templates')}
        >
          ✎ Templates
        </button>
        <button 
          className={`tab ${activeTab === 'editor' ? 'active' : ''}`}
          onClick={() => setActiveTab('editor')}
        >
          ✎ Mapping Editor
        </button>
      </div>

      <div className="content-area">
        {/* Active Mappings Tab */}
        {activeTab === 'mappings' && (
          <div className="mappings-section">
            <div className="section-header">
              <h2>Data Mapping Configurations</h2>
              <button 
                onClick={createNewMapping}
                className="btn btn-primary"
              >
                ✚ New Mapping
              </button>
            </div>

            <div className="mappings-grid">
              {mappings.map(mapping => (
                <div key={mapping.id} className="mapping-card">
                  <div className="mapping-header">
                    <h3>{mapping.name}</h3>
                    <span className={`status-badge ${mapping.status}`}>
                      {mapping.status.toUpperCase()}
                    </span>
                  </div>

                  <div className="mapping-flow">
                    <div className="system-box source">
                      <span className="system-label">Source</span>
                      <span className="system-name">{mapping.sourceSystem}</span>
                    </div>
                    <div className="flow-arrow">→</div>
                    <div className="system-box target">
                      <span className="system-label">Target</span>
                      <span className="system-name">{mapping.targetSystem}</span>
                    </div>
                  </div>

                  <div className="mapping-details">
                    <p className="mapping-description">{mapping.description}</p>
                    <div className="mapping-stats">
                      <span className="stat">▦ {mapping.fields} fields</span>
                      <span className="stat">◷ {new Date(mapping.lastModified).toLocaleDateString()}</span>
                    </div>
                  </div>

                  <div className="mapping-actions">
                    <button 
                      onClick={() => editMapping(mapping)}
                      className="btn btn-secondary btn-sm"
                    >
                      ✎ Edit
                    </button>
                    <button 
                      onClick={() => validateMapping(mapping.id)}
                      className="btn btn-outline btn-sm"
                      disabled={isLoading}
                    >
                      ✓ Validate
                    </button>
                    <button 
                      onClick={() => executeMapping(mapping.id)}
                      className="btn btn-success btn-sm"
                      disabled={isLoading}
                    >
                      ➔ Execute
                    </button>
                    <button 
                      onClick={() => deleteMapping(mapping.id)}
                      className="btn btn-danger btn-sm"
                    >
                      ✗ Delete
                    </button>
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
              <h2>Mapping Templates</h2>
              <button className="btn btn-primary">
                ✚ Create Template
              </button>
            </div>

            <div className="templates-grid">
              {templates.map(template => (
                <div key={template.id} className="template-card">
                  <div className="template-header">
                    <h3>{template.name}</h3>
                    <span className="template-category">{template.category}</span>
                  </div>

                  <p className="template-description">{template.description}</p>

                  <div className="template-fields">
                    <h4>Template Fields:</h4>
                    <div className="fields-list">
                      {template.fields.map((field, index) => (
                        <span key={index} className="field-tag">
                          {field}
                        </span>
                      ))}
                    </div>
                  </div>

                  <div className="template-actions">
                    <button 
                      onClick={() => applyTemplate(template)}
                      className="btn btn-primary btn-sm"
                    >
                      ➔ Use Template
                    </button>
                    <button className="btn btn-outline btn-sm">
                      ✎ Edit Template
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Mapping Editor Tab */}
        {activeTab === 'editor' && (
          <div className="editor-section">
            <div className="section-header">
              <h2>Mapping Editor</h2>
              <div className="editor-actions">
                <button className="btn btn-outline">
                  ● Save Draft
                </button>
                <button className="btn btn-success">
                  ➔ Deploy Mapping
                </button>
              </div>
            </div>

            {selectedMapping ? (
              <div className="mapping-editor">
                <div className="editor-form">
                  <div className="form-section">
                    <h3>Basic Information</h3>
                    <div className="form-grid">
                      <div className="form-group">
                        <label>Mapping Name</label>
                        <input 
                          type="text" 
                          value={selectedMapping.name}
                          onChange={(e) => setSelectedMapping({
                            ...selectedMapping,
                            name: e.target.value
                          })}
                        />
                      </div>
                      <div className="form-group">
                        <label>Description</label>
                        <textarea 
                          value={selectedMapping.description}
                          onChange={(e) => setSelectedMapping({
                            ...selectedMapping,
                            description: e.target.value
                          })}
                        />
                      </div>
                    </div>
                  </div>

                  <div className="form-section">
                    <h3>Source Configuration</h3>
                    <div className="form-grid">
                      <div className="form-group">
                        <label>Source System</label>
                        <select 
                          value={selectedMapping.sourceSystem}
                          onChange={(e) => setSelectedMapping({
                            ...selectedMapping,
                            sourceSystem: e.target.value
                          })}
                        >
                          <option value="Select Source">Select Source</option>
                          <option value="Neo4j Graph Database">Neo4j Graph Database</option>
                          <option value="CSV File">CSV File</option>
                          <option value="JSON API">JSON API</option>
                          <option value="SQL Database">SQL Database</option>
                        </select>
                      </div>
                      <div className="form-group">
                        <label>Target System</label>
                        <select 
                          value={selectedMapping.targetSystem}
                          onChange={(e) => setSelectedMapping({
                            ...selectedMapping,
                            targetSystem: e.target.value
                          })}
                        >
                          <option value="Select Target">Select Target</option>
                          <option value="Apache NiFi">Apache NiFi</option>
                          <option value="Neo4j Graph Database">Neo4j Graph Database</option>
                          <option value="Relational Database">Relational Database</option>
                          <option value="File Export">File Export</option>
                        </select>
                      </div>
                    </div>
                  </div>

                  <div className="form-section">
                    <h3>Field Mappings</h3>
                    <div className="field-mappings">
                      <div className="mapping-row header">
                        <span>Source Field</span>
                        <span>Transformation</span>
                        <span>Target Field</span>
                        <span>Actions</span>
                      </div>
                      {/* Field mapping rows would be dynamically generated here */}
                      <div className="mapping-row">
                        <input type="text" placeholder="Enter source field" />
                        <select>
                          <option>No transformation</option>
                          <option>Uppercase</option>
                          <option>Lowercase</option>
                          <option>Date format</option>
                          <option>Custom function</option>
                        </select>
                        <input type="text" placeholder="Enter target field" />
                        <button className="btn btn-sm btn-danger">✗</button>
                      </div>
                    </div>
                    <button className="btn btn-outline">
                      ✚ Add Field Mapping
                    </button>
                  </div>
                </div>
              </div>
            ) : (
              <div className="no-mapping-selected">
                <p>Select a mapping to edit or create a new one.</p>
              </div>
            )}
          </div>
        )}
      </div>

      {isLoading && (
        <div className="loading-overlay">
          <div className="loading-spinner">Loading...</div>
        </div>
      )}
    </div>
  );
};

export default DataMappingPage;
