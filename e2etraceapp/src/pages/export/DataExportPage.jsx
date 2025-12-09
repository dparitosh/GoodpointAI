import React, { useState, useEffect } from 'react';
import { e2etraceFetchWithRetry } from '../../api/e2etrace-api';
import { API_CONFIG } from '@config/api-config.js';
import { saveAs } from 'file-saver';
import * as XLSX from 'xlsx';
import './DataExportPage.css';

const DataExportPage = () => {
  const [exportConfig, setExportConfig] = useState({
    format: 'excel',
    includeSchema: true,
    includeMetadata: false,
    compressionType: 'none',
    dateRange: 'all',
    filterQuery: '',
  });
  
  const [availableDatasets, setAvailableDatasets] = useState([]);
  const [selectedDatasets, setSelectedDatasets] = useState([]);
  const [exportHistory, setExportHistory] = useState([]);
  const [isExporting, setIsExporting] = useState(false);
  const [exportProgress, setExportProgress] = useState(0);
  const [activeTab, setActiveTab] = useState('configure');

  useEffect(() => {
    loadAvailableDatasets();
    loadExportHistory();
  }, []);

  const loadAvailableDatasets = async () => {
    try {
      // Load from Neo4j
      const response = await e2etraceFetchWithRetry(API_CONFIG.ENDPOINTS.SCHEMA_LABELS);
      const data = await response.json();
      
      const datasets = data.labels?.map(label => ({
        id: label,
        name: label,
        type: 'neo4j_node',
        count: data.counts?.[label] || 0,
        description: `Neo4j nodes with label: ${label}`
      })) || [];

      // Add relationship datasets
      const relResponse = await e2etraceFetchWithRetry(API_CONFIG.ENDPOINTS.SCHEMA_RELATIONSHIPS);
      const relData = await relResponse.json();
      
      const relationships = relData.relationships?.map(rel => ({
        id: `rel_${rel}`,
        name: rel,
        type: 'neo4j_relationship',
        count: relData.counts?.[rel] || 0,
        description: `Neo4j relationships of type: ${rel}`
      })) || [];

      setAvailableDatasets([...datasets, ...relationships]);
    } catch (error) {
      console.error('Failed to load datasets:', error);
      setAvailableDatasets([]);
    }
  };

  const loadExportHistory = async () => {
    try {
      const response = await fetch('/api/export/history');
      if (response.ok) {
        const history = await response.json();
        setExportHistory(history);
      } else {
        setExportHistory([]);
      }
    } catch (error) {
      console.error('Failed to load export history:', error);
      setExportHistory([]);
    }
  };

  const handleDatasetSelection = (datasetId) => {
    setSelectedDatasets(prev => 
      prev.includes(datasetId) 
        ? prev.filter(id => id !== datasetId)
        : [...prev, datasetId]
    );
  };

  const handleExport = async () => {
    if (selectedDatasets.length === 0) {
      alert('Please select at least one dataset to export');
      return;
    }

    setIsExporting(true);
    setExportProgress(0);

    try {
      // Simulate progress
      const progressInterval = setInterval(() => {
        setExportProgress(prev => Math.min(prev + 10, 90));
      }, 500);

      // Fetch data for selected datasets
      const exportData = {};
      
      for (const datasetId of selectedDatasets) {
        const dataset = availableDatasets.find(d => d.id === datasetId);
        
        if (dataset.type === 'neo4j_node') {
          // Fetch nodes with this label
          const response = await e2etraceFetchWithRetry(`${API_CONFIG.ENDPOINTS.ENTITIES}?label=${dataset.name}`);
          const data = await response.json();
          exportData[dataset.name] = data.nodes || [];
        } else if (dataset.type === 'neo4j_relationship') {
          // Fetch relationships of this type
          const response = await e2etraceFetchWithRetry(`${API_CONFIG.ENDPOINTS.GRAPH}?relationshipType=${dataset.name}`);
          const data = await response.json();
          exportData[dataset.name] = data.relationships || [];
        }
      }

      clearInterval(progressInterval);
      setExportProgress(100);

      // Export based on format
      if (exportConfig.format === 'excel') {
        await exportToExcel(exportData);
      } else if (exportConfig.format === 'csv') {
        await exportToCSV(exportData);
      } else if (exportConfig.format === 'json') {
        await exportToJSON(exportData);
      }

      // Add to history
      const newExport = {
        id: Date.now(),
        timestamp: new Date(),
        format: exportConfig.format,
        datasets: selectedDatasets.map(id => availableDatasets.find(d => d.id === id)?.name).filter(Boolean),
        fileSize: 'Calculating...',
        status: 'completed'
      };
      
      setExportHistory(prev => [newExport, ...prev]);

    } catch (error) {
      console.error('Export failed:', error);
      alert('Export failed. Please try again.');
    } finally {
      setIsExporting(false);
      setExportProgress(0);
    }
  };

  const exportToExcel = async (data) => {
    const wb = XLSX.utils.book_new();
    
    Object.entries(data).forEach(([sheetName, sheetData]) => {
      if (Array.isArray(sheetData) && sheetData.length > 0) {
        const ws = XLSX.utils.json_to_sheet(sheetData);
        XLSX.utils.book_append_sheet(wb, ws, sheetName);
      }
    });

    if (exportConfig.includeSchema) {
      // Add schema information
      const schemaData = selectedDatasets.map(id => {
        const dataset = availableDatasets.find(d => d.id === id);
        return {
          Dataset: dataset?.name,
          Type: dataset?.type,
          Count: dataset?.count,
          Description: dataset?.description
        };
      });
      const schemaWs = XLSX.utils.json_to_sheet(schemaData);
      XLSX.utils.book_append_sheet(wb, schemaWs, 'Schema_Info');
    }

    const wbout = XLSX.write(wb, { bookType: 'xlsx', type: 'array' });
    const blob = new Blob([wbout], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' });
    saveAs(blob, `e2etrace_export_${new Date().toISOString().split('T')[0]}.xlsx`);
  };

  const exportToCSV = async (data) => {
    Object.entries(data).forEach(([fileName, fileData]) => {
      if (Array.isArray(fileData) && fileData.length > 0) {
        const csv = XLSX.utils.json_to_sheet(fileData);
        const csvOutput = XLSX.utils.sheet_to_csv(csv);
        const blob = new Blob([csvOutput], { type: 'text/csv;charset=utf-8;' });
        saveAs(blob, `${fileName}_${new Date().toISOString().split('T')[0]}.csv`);
      }
    });
  };

  const exportToJSON = async (data) => {
    const jsonData = {
      exportDate: new Date().toISOString(),
      config: exportConfig,
      data: data
    };
    
    const blob = new Blob([JSON.stringify(jsonData, null, 2)], { type: 'application/json' });
    saveAs(blob, `e2etrace_export_${new Date().toISOString().split('T')[0]}.json`);
  };

  return (
    <div className="data-export-page">
      <div className="page-header">
        <h1>↗ Data Export</h1>
        <p>Export your data in various formats for analysis, backup, or migration</p>
      </div>

      <div className="export-tabs">
        <button 
          className={`tab-button ${activeTab === 'configure' ? 'active' : ''}`}
          onClick={() => setActiveTab('configure')}
        >
          Configure Export
        </button>
        <button 
          className={`tab-button ${activeTab === 'history' ? 'active' : ''}`}
          onClick={() => setActiveTab('history')}
        >
          Export History
        </button>
      </div>

      {activeTab === 'configure' && (
        <div className="export-configuration">
          <div className="export-layout">
            <div className="export-left-panel">
              <div className="config-section">
                <h3>Export Format</h3>
                <div className="format-options">
                  <label>
                    <input 
                      type="radio" 
                      name="format" 
                      value="excel"
                      checked={exportConfig.format === 'excel'}
                      onChange={(e) => setExportConfig({...exportConfig, format: e.target.value})}
                    />
                    <span className="format-option">
                      <i className="fas fa-file-excel"></i>
                      Excel (.xlsx)
                    </span>
                  </label>
                  <label>
                    <input 
                      type="radio" 
                      name="format" 
                      value="csv"
                      checked={exportConfig.format === 'csv'}
                      onChange={(e) => setExportConfig({...exportConfig, format: e.target.value})}
                    />
                    <span className="format-option">
                      <i className="fas fa-file-csv"></i>
                      CSV Files
                    </span>
                  </label>
                  <label>
                    <input 
                      type="radio" 
                      name="format" 
                      value="json"
                      checked={exportConfig.format === 'json'}
                      onChange={(e) => setExportConfig({...exportConfig, format: e.target.value})}
                    />
                    <span className="format-option">
                      <i className="fas fa-file-code"></i>
                      JSON
                    </span>
                  </label>
                </div>
              </div>

              <div className="config-section">
                <h3>Export Options</h3>
                <div className="option-checkboxes">
                  <label>
                    <input 
                      type="checkbox"
                      checked={exportConfig.includeSchema}
                      onChange={(e) => setExportConfig({...exportConfig, includeSchema: e.target.checked})}
                    />
                    Include Schema Information
                  </label>
                  <label>
                    <input 
                      type="checkbox"
                      checked={exportConfig.includeMetadata}
                      onChange={(e) => setExportConfig({...exportConfig, includeMetadata: e.target.checked})}
                    />
                    Include Metadata
                  </label>
                </div>
              </div>

              <div className="config-section">
                <h3>Data Filter</h3>
                <textarea 
                  placeholder="Optional: Enter Cypher query to filter data..."
                  value={exportConfig.filterQuery}
                  onChange={(e) => setExportConfig({...exportConfig, filterQuery: e.target.value})}
                  rows={4}
                />
              </div>
            </div>

            <div className="export-right-panel">
              <h3>Available Datasets</h3>
              <div className="dataset-list">
                {availableDatasets.map(dataset => (
                  <div key={dataset.id} className="dataset-item">
                    <label>
                      <input 
                        type="checkbox"
                        checked={selectedDatasets.includes(dataset.id)}
                        onChange={() => handleDatasetSelection(dataset.id)}
                      />
                      <div className="dataset-info">
                        <div className="dataset-name">
                          <i className={`fas ${dataset.type === 'neo4j_node' ? 'fa-circle' : dataset.type === 'neo4j_relationship' ? 'fa-arrow-right' : 'fa-chart-bar'}`}></i>
                          {dataset.name}
                        </div>
                        <div className="dataset-meta">
                          <span className="dataset-count">{dataset.count.toLocaleString()} records</span>
                          <span className="dataset-type">{dataset.type}</span>
                        </div>
                        <div className="dataset-description">{dataset.description}</div>
                      </div>
                    </label>
                  </div>
                ))}
              </div>

              <div className="export-summary">
                <div className="summary-row">
                  <span>Selected Datasets:</span>
                  <strong>{selectedDatasets.length}</strong>
                </div>
                <div className="summary-row">
                  <span>Estimated Records:</span>
                  <strong>
                    {selectedDatasets.reduce((total, id) => {
                      const dataset = availableDatasets.find(d => d.id === id);
                      return total + (dataset?.count || 0);
                    }, 0).toLocaleString()}
                  </strong>
                </div>
              </div>

              <button 
                className="export-button"
                onClick={handleExport}
                disabled={isExporting || selectedDatasets.length === 0}
              >
                {isExporting ? (
                  <>
                    <i className="fas fa-spinner fa-spin"></i>
                    Exporting... {exportProgress}%
                  </>
                ) : (
                  <>
                    <i className="fas fa-download"></i>
                    Export Data
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}

      {activeTab === 'history' && (
        <div className="export-history">
          <h3>Recent Exports</h3>
          <div className="history-list">
            {exportHistory.map(exportItem => (
              <div key={exportItem.id} className="history-item">
                <div className="history-info">
                  <div className="history-header">
                    <span className="history-date">
                      {exportItem.timestamp.toLocaleDateString()} {exportItem.timestamp.toLocaleTimeString()}
                    </span>
                    <span className={`history-status ${exportItem.status}`}>
                      {exportItem.status}
                    </span>
                  </div>
                  <div className="history-details">
                    <span>Format: {exportItem.format.toUpperCase()}</span>
                    <span>Size: {exportItem.fileSize}</span>
                    <span>Datasets: {exportItem.datasets.join(', ')}</span>
                  </div>
                </div>
                <div className="history-actions">
                  <button className="action-button" title="Download Again">
                    <i className="fas fa-download"></i>
                  </button>
                  <button className="action-button" title="View Details">
                    <i className="fas fa-info-circle"></i>
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default DataExportPage;
