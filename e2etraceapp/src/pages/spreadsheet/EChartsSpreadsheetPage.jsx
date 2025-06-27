import React, { useState, useEffect, useRef, useCallback } from 'react';
import ReactECharts from 'echarts-for-react';
import * as XLSX from 'xlsx';
import { saveAs } from 'file-saver';
import { e2etraceFetchWithRetry } from '../../api/e2etrace-api';
import { API_CONFIG } from '../../config/api-config.js';
import { e2etraceUseGraphData } from '../../hooks/e2etrace-use-graph-data';
import { etlWorkflowService } from '../../services/etl-workflow-service';
import { etlEngine } from '../../services/etl-engine';
import neo4jDataService from '../../services/neo4j-data-service.js';
import './EChartsSpreadsheetPage.css';

const EChartsSpreadsheetPage = () => {
  // Data state
  const [spreadsheetData, setSpreadsheetData] = useState([]);
  const [selectedData, setSelectedData] = useState([]);
  const [chartConfig, setChartConfig] = useState({
    type: 'bar',
    title: 'Data Visualization',
    xAxisColumn: 0,
    yAxisColumns: [1],
    legendColumn: null,
  });

  // Data conversion and mapping state
  const [rawData, setRawData] = useState('');
  const [sourceFormat, setSourceFormat] = useState('json');
  const [targetFormat, setTargetFormat] = useState('csv');
  const [mappingRules, setMappingRules] = useState([]);
  const [nifiProcessors, setNifiProcessors] = useState([]);
  const [conversionHistory, setConversionHistory] = useState([]);
  const [dataValidationResults, setDataValidationResults] = useState([]);
  const [savedMappingTemplates, setSavedMappingTemplates] = useState([]);
  const [exportFormat, setExportFormat] = useState('excel');
  const [bulkOperationMode, setBulkOperationMode] = useState(false);

  // UI state
  const [activeTab, setActiveTab] = useState('data');
  const [isLoading, setIsLoading] = useState(false);
  const [dragStart, setDragStart] = useState(null);
  const [dragEnd, setDragEnd] = useState(null);

  // Refs
  const chartRef = useRef(null);
  const fileInputRef = useRef(null);

  // Use graph data hook for Neo4j integration
  const { graphData, loading: graphLoading } = e2etraceUseGraphData();

  // Load NiFi processors on mount
  useEffect(() => {
    loadNifiProcessors();
  }, []);

  // Enhanced data conversion functions
  const convertJsonToCsv = useCallback((jsonData) => {
    try {
      const parsed = Array.isArray(jsonData) ? jsonData : JSON.parse(jsonData);
      if (!Array.isArray(parsed) || parsed.length === 0) {
        throw new Error('Invalid JSON array');
      }

      // Extract headers from first object
      const headers = Object.keys(parsed[0]);
      const csvData = [headers];

      // Convert each object to row with enhanced type handling
      parsed.forEach(obj => {
        const row = headers.map(header => {
          const value = obj[header];
          if (value === null || value === undefined) return '';
          if (typeof value === 'object') {
            // Handle nested objects and arrays better
            if (Array.isArray(value)) {
              return value.join(';'); // Join arrays with semicolon
            }
            return JSON.stringify(value);
          }
          if (typeof value === 'boolean') return value.toString();
          if (typeof value === 'number') return value.toString();
          return String(value).replace(/"/g, '""'); // Escape quotes for CSV
        });
        csvData.push(row);
      });

      return csvData;
    } catch (error) {
      console.error('JSON to CSV conversion error:', error);
      throw new Error(`Failed to convert JSON to CSV: ${error.message}`);
    }
  }, []);

  const convertXmlToCsv = useCallback((xmlData) => {
    try {
      // Enhanced XML parser with namespace support
      const parser = new DOMParser();
      const xmlDoc = parser.parseFromString(xmlData, 'text/xml');
      
      if (xmlDoc.getElementsByTagName('parsererror').length > 0) {
        throw new Error('Invalid XML format');
      }

      // Find repeating elements (rows) - handle multiple root patterns
      const rootElement = xmlDoc.documentElement;
      let childElements = Array.from(rootElement.children);
      
      // If root has only one child type, look deeper
      if (childElements.length === 1 && childElements[0].children.length > 0) {
        const singleChild = childElements[0];
        if (Array.from(singleChild.children).every(child => child.tagName === singleChild.children[0].tagName)) {
          childElements = Array.from(singleChild.children);
        }
      }
      
      if (childElements.length === 0) {
        throw new Error('No data elements found in XML');
      }

      // Extract headers from first element with attribute handling
      const firstElement = childElements[0];
      const headers = [];
      
      // Add attributes as columns
      if (firstElement.attributes.length > 0) {
        Array.from(firstElement.attributes).forEach(attr => {
          headers.push(`@${attr.name}`);
        });
      }
      
      // Add child elements as columns
      Array.from(firstElement.children).forEach(child => {
        headers.push(child.tagName);
      });

      const csvData = [headers];
      // Convert each XML element to row
      childElements.forEach(element => {
        const row = headers.map(header => {
          const node = element.getElementsByTagName(header)[0];
          return node ? node.textContent.trim() : '';
        });
        csvData.push(row);
      });

      return csvData;
    } catch (error) {
      console.error('XML to CSV conversion error:', error);
      throw new Error(`Failed to convert XML to CSV: ${error.message}`);
    }
  }, []);

  const convertCsvToJson = useCallback((csvData) => {
    try {
      if (!Array.isArray(csvData) || csvData.length < 2) {
        throw new Error('Invalid CSV data format');
      }

      const [headers, ...rows] = csvData;
      return rows.map(row => {
        const obj = {};
        headers.forEach((header, index) => {
          obj[header] = row[index] || '';
        });
        return obj;
      });
    } catch (error) {
      console.error('CSV to JSON conversion error:', error);
      throw new Error(`Failed to convert CSV to JSON: ${error.message}`);
    }
  }, []);

  const applyMappingRules = useCallback((data, rules) => {
    if (!rules.length) return data;

    try {
      return data.map(row => {
        const mappedRow = [...row];
        rules.forEach(rule => {
          if (rule.sourceColumn < row.length) {
            const sourceValue = row[rule.sourceColumn];
            let mappedValue = sourceValue;

            // Apply transformation based on rule type
            switch (rule.transformation) {
              case 'uppercase':
                mappedValue = String(sourceValue).toUpperCase();
                break;
              case 'lowercase':
                mappedValue = String(sourceValue).toLowerCase();
                break;
              case 'trim':
                mappedValue = String(sourceValue).trim();
                break;
              case 'number':
                mappedValue = parseFloat(sourceValue) || 0;
                break;
              case 'date':
                mappedValue = new Date(sourceValue).toISOString().split('T')[0];
                break;
              case 'boolean':
                mappedValue = ['true', '1', 'yes', 'on'].includes(String(sourceValue).toLowerCase());
                break;
              case 'capitalize':
                mappedValue = String(sourceValue).replace(/\w\S*/g, (txt) => 
                  txt.charAt(0).toUpperCase() + txt.substr(1).toLowerCase());
                break;
              case 'extract_numbers':
                mappedValue = String(sourceValue).replace(/[^0-9.]/g, '');
                break;
              case 'remove_special':
                mappedValue = String(sourceValue).replace(/[^a-zA-Z0-9\s]/g, '');
                break;
              case 'custom':
                if (rule.customFunction) {
                  try {
                    // Safely evaluate custom function
                    mappedValue = new Function('value', rule.customFunction)(sourceValue);
                  } catch (e) {
                    console.warn('Custom function error:', e);
                    mappedValue = sourceValue;
                  }
                }
                break;
              default:
                mappedValue = sourceValue;
            }

            if (rule.targetColumn < mappedRow.length) {
              mappedRow[rule.targetColumn] = mappedValue;
            }
          }
        });
        return mappedRow;
      });
    } catch (error) {
      console.error('Mapping rule application error:', error);
      return data;
    }
  }, []);

  // Data validation functions
  const inferDataTypes = useCallback((data) => {
    if (!data || data.length === 0) return {};
    
    const sample = data[0];
    const types = {};
    
    for (const [key, value] of Object.entries(sample)) {
      if (typeof value === 'number') types[key] = 'number';
      else if (typeof value === 'boolean') types[key] = 'boolean';
      else if (value instanceof Date || !isNaN(Date.parse(value))) types[key] = 'date';
      else types[key] = 'string';
    }
    
    return types;
  }, []);

  const validateData = useCallback((data) => {
    const results = [];
    if (!data.length) return results;

    const headers = data[0];
    const rows = data.slice(1);

    headers.forEach((header, colIndex) => {
      const columnData = rows.map(row => row[colIndex]);
      const nonEmptyCount = columnData.filter(cell => cell && cell.toString().trim()).length;
      const completeness = (nonEmptyCount / rows.length) * 100;
      
      // Check data type consistency
      const types = new Set();
      columnData.forEach(cell => {
        if (cell && cell.toString().trim()) {
          if (!isNaN(cell)) types.add('number');
          else if (Date.parse(cell)) types.add('date');
          else types.add('string');
        }
      });

      results.push({
        column: header,
        index: colIndex,
        completeness: completeness.toFixed(1),
        typeConsistency: types.size <= 1 ? 'Good' : 'Mixed',
        uniqueValues: new Set(columnData).size,
        issues: []
      });
    });

    return results;
  }, []);

  // Save and load mapping templates
  const saveMappingTemplate = useCallback((name) => {
    if (!mappingRules.length) {
      alert('No mapping rules to save');
      return;
    }

    const template = {
      id: Date.now(),
      name: name || `Template ${Date.now()}`,
      rules: mappingRules,
      createdAt: new Date().toISOString(),
      sourceFormat,
      targetFormat
    };

    setSavedMappingTemplates(prev => [...prev, template]);
    alert(`Template "${template.name}" saved successfully`);
  }, [mappingRules, sourceFormat, targetFormat]);

  const loadMappingTemplate = useCallback((template) => {
    setMappingRules(template.rules);
    setSourceFormat(template.sourceFormat);
    setTargetFormat(template.targetFormat);
    alert(`Template "${template.name}" loaded successfully`);
  }, []);

  const deleteMappingTemplate = useCallback((templateId) => {
    setSavedMappingTemplates(prev => prev.filter(t => t.id !== templateId));
  }, []);

  // Enhanced export functionality
  const handleAdvancedExport = useCallback((format) => {
    const dataToExport = selectedData.length ? selectedData : spreadsheetData;
    
    switch (format) {
      case 'excel':
        const worksheet = XLSX.utils.aoa_to_sheet(dataToExport);
        const workbook = XLSX.utils.book_new();
        XLSX.utils.book_append_sheet(workbook, worksheet, 'Data');
        const excelBuffer = XLSX.write(workbook, { bookType: 'xlsx', type: 'array' });
        const excelBlob = new Blob([excelBuffer], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' });
        saveAs(excelBlob, 'echarts-spreadsheet-data.xlsx');
        break;
        
      case 'csv':
        const csvContent = dataToExport.map(row => 
          row.map(cell => `"${String(cell).replace(/"/g, '""')}"`).join(',')
        ).join('\n');
        const csvBlob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
        saveAs(csvBlob, 'echarts-spreadsheet-data.csv');
        break;
        
      case 'json':
        if (dataToExport.length > 1) {
          const jsonData = convertCsvToJson(dataToExport);
          const jsonBlob = new Blob([JSON.stringify(jsonData, null, 2)], { type: 'application/json' });
          saveAs(jsonBlob, 'echarts-spreadsheet-data.json');
        }
        break;
        
      case 'xml':
        if (dataToExport.length > 1) {
          const [headers, ...rows] = dataToExport;
          let xmlContent = '<?xml version="1.0" encoding="UTF-8"?>\n<data>\n';
          rows.forEach(row => {
            xmlContent += '  <record>\n';
            headers.forEach((header, index) => {
              xmlContent += `    <${header}>${row[index] || ''}</${header}>\n`;
            });
            xmlContent += '  </record>\n';
          });
          xmlContent += '</data>';
          const xmlBlob = new Blob([xmlContent], { type: 'application/xml' });
          saveAs(xmlBlob, 'echarts-spreadsheet-data.xml');
        }
        break;
    }
  }, [selectedData, spreadsheetData, convertCsvToJson]);

  // Initialize with real Neo4j data
  useEffect(() => {
    if (!spreadsheetData.length) {
      const loadInitialData = async () => {
        try {
          // Load sample data from Neo4j graph for analysis
          const response = await e2etraceFetchWithRetry(API_CONFIG.ENDPOINTS.GRAPH);
          const graphData = await response.json();
          
          if (graphData && graphData.nodes && graphData.nodes.length > 0) {
            // Convert graph nodes to spreadsheet format
            const headers = ['Node ID', 'Label', 'Properties Count', 'Type'];
            const rows = [headers];
            
            graphData.nodes.slice(0, 10).forEach(node => {
              const nodeData = node.data || node;
              rows.push([
                nodeData.id || 'N/A',
                nodeData.label || nodeData.group || 'Unknown',
                Object.keys(nodeData).length,
                nodeData.type || 'Node'
              ]);
            });
            
            setSpreadsheetData(rows);
          } else {
            // If no graph data, start with empty spreadsheet
            setSpreadsheetData([
              ['Column 1', 'Column 2', 'Column 3'],
              ['', '', ''],
              ['', '', '']
            ]);
          }
        } catch (error) {
          console.error('Error loading initial data:', error);
          // Fallback to minimal structure
          setSpreadsheetData([
            ['Column 1', 'Column 2', 'Column 3'],
            ['', '', ''],
            ['', '', '']
          ]);
        }
      };
      
      loadInitialData();
    }
  }, [spreadsheetData.length]);

  // Load NiFi processors
  const loadNifiProcessors = async () => {
    try {
      const response = await e2etraceFetchWithRetry(API_CONFIG.ENDPOINTS.NIFI_PROCESS_GROUPS);
      const data = await response.json();
      setNifiProcessors(data.processGroups || []);
    } catch (error) {
      console.error('Error loading NiFi processors:', error);
    }
  };

  // Handle data conversion with enhanced validation
  const handleDataConversion = useCallback(async () => {
    if (!rawData.trim()) {
      alert('Please enter data to convert');
      return;
    }

    setIsLoading(true);
    try {
      let convertedData = [];
      
      switch (sourceFormat) {
        case 'json':
          convertedData = convertJsonToCsv(rawData);
          break;
        case 'xml':
          convertedData = convertXmlToCsv(rawData);
          break;
        case 'csv':
          // Parse CSV text with better handling
          const rows = rawData.split('\n').map(row => {
            // Handle quoted CSV values
            const result = [];
            let current = '';
            let inQuotes = false;
            
            for (let i = 0; i < row.length; i++) {
              const char = row[i];
              if (char === '"') {
                inQuotes = !inQuotes;
              } else if (char === ',' && !inQuotes) {
                result.push(current.trim());
                current = '';
              } else {
                current += char;
              }
            }
            result.push(current.trim());
            return result;
          });
          convertedData = rows.filter(row => row.some(cell => cell));
          break;
        default:
          throw new Error('Unsupported source format');
      }

      // Apply mapping rules if any
      if (mappingRules.length > 0) {
        convertedData = applyMappingRules(convertedData, mappingRules);
      }

      // Validate converted data
      const validationResults = validateData(convertedData);
      setDataValidationResults(validationResults);

      setSpreadsheetData(convertedData);
      setSelectedData([]);

      // Save to conversion history
      const historyEntry = {
        id: Date.now(),
        timestamp: new Date().toISOString(),
        sourceFormat,
        targetFormat,
        rowCount: convertedData.length - 1, // Exclude header
        mappingRulesUsed: mappingRules.length,
        validationScore: validationResults.reduce((acc, result) => acc + parseFloat(result.completeness), 0) / validationResults.length
      };
      setConversionHistory(prev => [historyEntry, ...prev].slice(0, 10)); // Keep last 10

      setActiveTab('data');
      alert(`Successfully converted ${historyEntry.rowCount} rows from ${sourceFormat.toUpperCase()} to ${targetFormat.toUpperCase()}`);
    } catch (error) {
      console.error('Data conversion error:', error);
      alert(`Conversion failed: ${error.message}`);
    } finally {
      setIsLoading(false);
    }
  }, [rawData, sourceFormat, targetFormat, mappingRules, convertJsonToCsv, convertXmlToCsv, applyMappingRules, validateData]);

  // Handle NiFi data import with enhanced processing
  const handleNifiImport = async () => {
    setIsLoading(true);
    try {
      // Get NiFi process groups
      const response = await e2etraceFetchWithRetry(API_CONFIG.ENDPOINTS.NIFI_PROCESS_GROUPS);
      const data = await response.json();
      const processGroups = data.processGroups || [];
      
      if (processGroups.length === 0) {
        alert('No NiFi process groups found');
        return;
      }

      // Convert NiFi data to spreadsheet format with more details
      const headers = ['Process Group', 'ID', 'Status', 'Processor Count', 'Input Ports', 'Output Ports', 'Last Modified'];
      const rows = processGroups.map(group => [
        group.component?.name || group.name || 'Unknown',
        group.id || '',
        group.status?.runStatus || group.component?.state || 'Unknown',
        group.component?.processorCount || 0,
        group.component?.inputPortCount || 0,
        group.component?.outputPortCount || 0,
        group.component?.lastModified || new Date().toISOString()
      ]);

      setSpreadsheetData([headers, ...rows]);
      setSelectedData([]);
      setActiveTab('data');

      // Get additional NiFi metrics if available
      try {
        const metricsResponse = await e2etraceFetchWithRetry(API_CONFIG.ENDPOINTS.NIFI_METRICS);
        const metrics = await metricsResponse.json();
        console.log('NiFi Metrics:', metrics);
      } catch (metricsError) {
        console.warn('Could not fetch NiFi metrics:', metricsError);
      }

      alert(`Imported ${rows.length} NiFi process groups`);
    } catch (error) {
      console.error('NiFi import error:', error);
      alert(`NiFi import failed: ${error.message}`);
    } finally {
      setIsLoading(false);
    }
  };

  // Add mapping rule
  const addMappingRule = () => {
    const newRule = {
      id: Date.now(),
      sourceColumn: 0,
      targetColumn: 0,
      transformation: 'none',
      customFunction: 'return value;'
    };
    setMappingRules(prev => [...prev, newRule]);
  };

  // Remove mapping rule
  const removeMappingRule = (id) => {
    setMappingRules(prev => prev.filter(rule => rule.id !== id));
  };

  // Update mapping rule
  const updateMappingRule = (id, updates) => {
    setMappingRules(prev => prev.map(rule => 
      rule.id === id ? { ...rule, ...updates } : rule
    ));
  };

  // Chart options based on selected data and configuration
  const getChartOption = useCallback(() => {
    if (!selectedData.length && !spreadsheetData.length) return {};

    const data = selectedData.length ? selectedData : spreadsheetData;
    const headers = data[0] || [];
    const rows = data.slice(1);

    if (!rows.length) return {};

    const { type, title, xAxisColumn, yAxisColumns } = chartConfig;
    
    const categories = rows.map(row => row[xAxisColumn] || '');
    const series = yAxisColumns.map(colIndex => ({
      name: headers[colIndex] || `Series ${colIndex}`,
      type: type,
      data: rows.map(row => {
        const value = row[colIndex];
        return isNaN(value) ? 0 : Number(value);
      }),
    }));

    return {
      title: {
        text: title,
        left: 'center',
        textStyle: { fontSize: 18, fontWeight: 'bold' }
      },
      tooltip: {
        trigger: type === 'pie' ? 'item' : 'axis',
        formatter: type === 'pie' 
          ? '{a} <br/>{b}: {c} ({d}%)'
          : '{b0}<br/>{a0}: {c0}<br/>{a1}: {c1}'
      },
      legend: {
        data: series.map(s => s.name),
        top: '10%',
      },
      grid: type !== 'pie' ? {
        left: '3%',
        right: '4%',
        bottom: '3%',
        containLabel: true
      } : undefined,
      xAxis: type !== 'pie' ? {
        type: 'category',
        data: categories,
        axisLabel: { rotate: 45, interval: 0 }
      } : undefined,
      yAxis: type !== 'pie' ? { type: 'value' } : undefined,
      series: type === 'pie' ? [{
        name: headers[yAxisColumns[0]] || 'Data',
        type: 'pie',
        radius: '50%',
        data: rows.map(row => ({
          name: row[xAxisColumn] || '',
          value: Number(row[yAxisColumns[0]]) || 0
        })),
        emphasis: {
          itemStyle: {
            shadowBlur: 10,
            shadowOffsetX: 0,
            shadowColor: 'rgba(0, 0, 0, 0.5)'
          }
        }
      }] : series,
    };
  }, [selectedData, spreadsheetData, chartConfig]);

  // Handle file import
  const handleFileImport = (event) => {
    const file = event.target.files[0];
    if (!file) return;

    setIsLoading(true);
    const reader = new FileReader();
    
    reader.onload = (e) => {
      try {
        const data = e.target.result;
        const workbook = XLSX.read(data, { type: 'binary' });
        const firstSheet = workbook.SheetNames[0];
        const worksheet = workbook.Sheets[firstSheet];
        const jsonData = XLSX.utils.sheet_to_json(worksheet, { header: 1 });
        
        setSpreadsheetData(jsonData);
        setSelectedData([]);
      } catch (error) {
        console.error('Error reading file:', error);
        alert('Error reading file. Please ensure it\'s a valid Excel file.');
      } finally {
        setIsLoading(false);
      }
    };
    
    reader.readAsBinaryString(file);
  };

  // Handle export
  const handleExport = () => {
    const dataToExport = selectedData.length ? selectedData : spreadsheetData;
    const worksheet = XLSX.utils.aoa_to_sheet(dataToExport);
    const workbook = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(workbook, worksheet, 'Data');
    
    const excelBuffer = XLSX.write(workbook, { bookType: 'xlsx', type: 'array' });
    const blob = new Blob([excelBuffer], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' });
    saveAs(blob, 'echarts-spreadsheet-data.xlsx');
  };

  // Load Neo4j data
  const loadNeo4jData = async () => {
    setIsLoading(true);
    try {
      const response = await e2etraceFetchWithRetry(API_CONFIG.ENDPOINTS.GRAPH);
      const data = await response.json();
      
      // Convert graph data to spreadsheet format
      const headers = ['Node ID', 'Label', 'Properties', 'Connections'];
      const rows = data.nodes.map(node => [
        node.data.id,
        node.data.label || 'Unknown',
        JSON.stringify(node.data.properties || {}),
        data.edges.filter(edge => edge.data.source === node.data.id || edge.data.target === node.data.id).length
      ]);
      
      setSpreadsheetData([headers, ...rows]);
      setSelectedData([]);
    } catch (error) {
      console.error('Error loading Neo4j data:', error);
      alert('Error loading Neo4j data. Please check the connection.');
    } finally {
      setIsLoading(false);
    }
  };

  // Handle cell selection for charts
  const handleCellMouseDown = (rowIndex, colIndex) => {
    setDragStart({ row: rowIndex, col: colIndex });
  };

  const handleCellMouseEnter = (rowIndex, colIndex) => {
    if (dragStart) {
      setDragEnd({ row: rowIndex, col: colIndex });
    }
  };

  const handleCellMouseUp = () => {
    if (dragStart && dragEnd) {
      const startRow = Math.min(dragStart.row, dragEnd.row);
      const endRow = Math.max(dragStart.row, dragEnd.row);
      const startCol = Math.min(dragStart.col, dragEnd.col);
      const endCol = Math.max(dragStart.col, dragEnd.col);

      const selection = [];
      for (let r = startRow; r <= endRow; r++) {
        const row = [];
        for (let c = startCol; c <= endCol; c++) {
          row.push(spreadsheetData[r]?.[c] || '');
        }
        selection.push(row);
      }
      setSelectedData(selection);
    }
    setDragStart(null);
    setDragEnd(null);
  };

  const isCellSelected = (rowIndex, colIndex) => {
    if (!dragStart || !dragEnd) return false;
    const startRow = Math.min(dragStart.row, dragEnd.row);
    const endRow = Math.max(dragStart.row, dragEnd.row);
    const startCol = Math.min(dragStart.col, dragEnd.col);
    const endCol = Math.max(dragStart.col, dragEnd.col);
    
    return rowIndex >= startRow && rowIndex <= endRow && colIndex >= startCol && colIndex <= endCol;
  };

  return (
    <div className="echarts-spreadsheet-page">
      {/* Header */}
      <div className="spreadsheet-header">
        <h1>📊 ECharts Data Spreadsheet</h1>
        <div className="header-actions">
          <input
            type="file"
            ref={fileInputRef}
            accept=".xlsx,.xls,.csv,.json,.xml"
            onChange={handleFileImport}
            style={{ display: 'none' }}
          />
          <button 
            onClick={() => fileInputRef.current?.click()}
            className="btn btn-primary"
            disabled={isLoading}
          >
            📁 Import File
          </button>
          
          <div className="export-dropdown">
            <button 
              className="btn btn-secondary dropdown-toggle"
              disabled={!spreadsheetData.length}
            >
              💾 Export
            </button>
            <div className="dropdown-menu">
              <button onClick={() => handleAdvancedExport('excel')} className="dropdown-item">
                📊 Excel (.xlsx)
              </button>
              <button onClick={() => handleAdvancedExport('csv')} className="dropdown-item">
                📄 CSV (.csv)
              </button>
              <button onClick={() => handleAdvancedExport('json')} className="dropdown-item">
                🗂️ JSON (.json)
              </button>
              <button onClick={() => handleAdvancedExport('xml')} className="dropdown-item">
                📋 XML (.xml)
              </button>
            </div>
          </div>

          <button 
            onClick={handleNifiImport}
            className="btn btn-success"
            disabled={isLoading}
          >
            🔗 Import from NiFi
          </button>
          
          <button 
            onClick={loadNeo4jData}
            className="btn btn-info"
            disabled={isLoading}
          >
            🔗 Import from Neo4j
          </button>
        </div>
      </div>

      {/* Tab Navigation */}
      <div className="tab-navigation">
        <button 
          className={`tab ${activeTab === 'data' ? 'active' : ''}`}
          onClick={() => setActiveTab('data')}
        >
          📋 Data
        </button>
        <button 
          className={`tab ${activeTab === 'convert' ? 'active' : ''}`}
          onClick={() => setActiveTab('convert')}
        >
          🔄 Convert
        </button>
        <button 
          className={`tab ${activeTab === 'mapping' ? 'active' : ''}`}
          onClick={() => setActiveTab('mapping')}
        >
          🗺️ Mapping
        </button>
        <button 
          className={`tab ${activeTab === 'validation' ? 'active' : ''}`}
          onClick={() => setActiveTab('validation')}
        >
          ✅ Validation
        </button>
        <button 
          className={`tab ${activeTab === 'templates' ? 'active' : ''}`}
          onClick={() => setActiveTab('templates')}
        >
          📝 Templates
        </button>
        <button 
          className={`tab ${activeTab === 'chart' ? 'active' : ''}`}
          onClick={() => setActiveTab('chart')}
        >
          📊 Chart
        </button>
        <button 
          className={`tab ${activeTab === 'config' ? 'active' : ''}`}
          onClick={() => setActiveTab('config')}
        >
          ⚙️ Config
        </button>
      </div>

      {/* Content Area */}
      <div className="content-area">
        {/* Data Tab */}
        {activeTab === 'data' && (
          <div className="data-section">
            <div className="data-info">
              <span>Rows: {spreadsheetData.length}</span>
              <span>Columns: {spreadsheetData[0]?.length || 0}</span>
              {selectedData.length > 0 && (
                <span>Selected: {selectedData.length}×{selectedData[0]?.length || 0}</span>
              )}
            </div>
            <div className="spreadsheet-container">
              <table className="spreadsheet-table">
                <tbody>
                  {spreadsheetData.map((row, rowIndex) => (
                    <tr key={rowIndex}>
                      <td className="row-header">{rowIndex + 1}</td>
                      {row.map((cell, colIndex) => (
                        <td
                          key={colIndex}
                          className={`spreadsheet-cell ${isCellSelected(rowIndex, colIndex) ? 'selected' : ''} ${rowIndex === 0 ? 'header-cell' : ''}`}
                          onMouseDown={() => handleCellMouseDown(rowIndex, colIndex)}
                          onMouseEnter={() => handleCellMouseEnter(rowIndex, colIndex)}
                          onMouseUp={handleCellMouseUp}
                        >
                          {cell}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* Convert Tab */}
        {activeTab === 'convert' && (
          <div className="convert-section">
            <div className="convert-container">
              <div className="convert-controls">
                <div className="format-selectors">
                  <div className="format-group">
                    <label>Source Format:</label>
                    <select
                      value={sourceFormat}
                      onChange={(e) => setSourceFormat(e.target.value)}
                    >
                      <option value="json">JSON</option>
                      <option value="xml">XML</option>
                      <option value="csv">CSV</option>
                      <option value="nifi">NiFi Flow</option>
                    </select>
                  </div>
                  <div className="conversion-arrow">➡️</div>
                  <div className="format-group">
                    <label>Target Format:</label>
                    <select
                      value={targetFormat}
                      onChange={(e) => setTargetFormat(e.target.value)}
                    >
                      <option value="csv">CSV/Spreadsheet</option>
                      <option value="json">JSON</option>
                      <option value="xml">XML</option>
                      <option value="excel">Excel</option>
                    </select>
                  </div>
                </div>
                
                <button 
                  onClick={handleDataConversion}
                  className="btn btn-primary conversion-btn"
                  disabled={isLoading || !rawData.trim()}
                >
                  🔄 Convert Data
                </button>
              </div>

              <div className="data-input-section">
                <div className="input-group">
                  <label>Raw Data Input ({sourceFormat.toUpperCase()}):</label>
                  <textarea
                    value={rawData}
                    onChange={(e) => setRawData(e.target.value)}
                    placeholder={`Paste your ${sourceFormat.toUpperCase()} data here...`}
                    rows={15}
                    className="data-textarea"
                  />
                </div>

                <div className="sample-data-section">
                  <h4>Sample Data Examples:</h4>
                  <div className="sample-buttons">
                    <button 
                      onClick={() => setRawData(JSON.stringify([
                        {"id": 1, "name": "John Doe", "age": 30, "city": "New York", "department": "Engineering", "salary": 75000},
                        {"id": 2, "name": "Jane Smith", "age": 25, "city": "London", "department": "Marketing", "salary": 65000},
                        {"id": 3, "name": "Bob Johnson", "age": 35, "city": "Paris", "department": "Sales", "salary": 70000}
                      ], null, 2))}
                      className="btn btn-secondary sample-btn"
                    >
                      Sample JSON (Employee Data)
                    </button>
                    <button 
                      onClick={() => setRawData(`<?xml version="1.0" encoding="UTF-8"?>
<employees>
  <employee id="1">
    <name>John Doe</name>
    <age>30</age>
    <city>New York</city>
    <department>Engineering</department>
    <salary>75000</salary>
  </employee>
  <employee id="2">
    <name>Jane Smith</name>
    <age>25</age>
    <city>London</city>
    <department>Marketing</department>
    <salary>65000</salary>
  </employee>
</employees>`)}
                      className="btn btn-secondary sample-btn"
                    >
                      Sample XML (Employee Data)
                    </button>
                    <button 
                      onClick={() => setRawData(`id,name,age,city,department,salary
1,"John Doe",30,"New York",Engineering,75000
2,"Jane Smith",25,London,Marketing,65000
3,"Bob Johnson",35,Paris,Sales,70000`)}
                      className="btn btn-secondary sample-btn"
                    >
                      Sample CSV (Employee Data)
                    </button>
                    <button 
                      onClick={() => setRawData(JSON.stringify([
                        {"processGroupId": "pg-001", "name": "Data Ingestion", "status": "Running", "processors": 5, "flowFiles": 1250},
                        {"processGroupId": "pg-002", "name": "Data Transformation", "status": "Running", "processors": 8, "flowFiles": 980},
                        {"processGroupId": "pg-003", "name": "Data Export", "status": "Stopped", "processors": 3, "flowFiles": 0}
                      ], null, 2))}
                      className="btn btn-success sample-btn"
                    >
                      Sample NiFi Data
                    </button>
                  </div>
                </div>
              </div>

              {conversionHistory.length > 0 && (
                <div className="conversion-history">
                  <h4>Conversion History:</h4>
                  <div className="history-list">
                    {conversionHistory.map(entry => (
                      <div key={entry.id} className="history-item">
                        <span>{entry.sourceFormat.toUpperCase()} → {entry.targetFormat.toUpperCase()}</span>
                        <span>{entry.rowCount} rows</span>
                        <span>{new Date(entry.timestamp).toLocaleString()}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Mapping Tab */}
        {activeTab === 'mapping' && (
          <div className="mapping-section">
            <div className="mapping-header">
              <h3>Data Mapping Rules</h3>
              <button onClick={addMappingRule} className="btn btn-primary">
                ➕ Add Mapping Rule
              </button>
            </div>

            <div className="mapping-rules">
              {mappingRules.length === 0 ? (
                <div className="no-rules">
                  <p>No mapping rules defined. Click "Add Mapping Rule" to create transformations.</p>
                </div>
              ) : (
                mappingRules.map(rule => (
                  <div key={rule.id} className="mapping-rule">
                    <div className="rule-controls">
                      <div className="rule-field">
                        <label>Source Column:</label>
                        <select
                          value={rule.sourceColumn}
                          onChange={(e) => updateMappingRule(rule.id, { sourceColumn: parseInt(e.target.value) })}
                        >
                          {(spreadsheetData[0] || []).map((header, index) => (
                            <option key={index} value={index}>{header} (Col {index})</option>
                          ))}
                        </select>
                      </div>

                      <div className="rule-field">
                        <label>Target Column:</label>
                        <select
                          value={rule.targetColumn}
                          onChange={(e) => updateMappingRule(rule.id, { targetColumn: parseInt(e.target.value) })}
                        >
                          {(spreadsheetData[0] || []).map((header, index) => (
                            <option key={index} value={index}>{header} (Col {index})</option>
                          ))}
                        </select>
                      </div>

                      <div className="rule-field">
                        <label>Transformation:</label>
                        <select
                          value={rule.transformation}
                          onChange={(e) => updateMappingRule(rule.id, { transformation: e.target.value })}
                        >
                          <option value="none">No Transform</option>
                          <option value="uppercase">UPPERCASE</option>
                          <option value="lowercase">lowercase</option>
                          <option value="capitalize">Capitalize Words</option>
                          <option value="trim">Trim Spaces</option>
                          <option value="number">To Number</option>
                          <option value="boolean">To Boolean</option>
                          <option value="date">To Date</option>
                          <option value="extract_numbers">Extract Numbers</option>
                          <option value="remove_special">Remove Special Chars</option>
                          <option value="custom">Custom Function</option>
                        </select>
                      </div>

                      <button 
                        onClick={() => removeMappingRule(rule.id)}
                        className="btn btn-danger remove-rule-btn"
                      >
                        🗑️
                      </button>
                    </div>

                    {rule.transformation === 'custom' && (
                      <div className="custom-function">
                        <label>Custom Function (JavaScript):</label>
                        <textarea
                          value={rule.customFunction}
                          onChange={(e) => updateMappingRule(rule.id, { customFunction: e.target.value })}
                          placeholder="return value.toUpperCase();"
                          rows={3}
                        />
                        <small>Use 'value' parameter to access the cell value</small>
                      </div>
                    )}
                  </div>
                ))
              )}
            </div>

            <div className="mapping-actions">
              <button 
                onClick={() => {
                  const converted = applyMappingRules(spreadsheetData, mappingRules);
                  setSpreadsheetData(converted);
                  alert('Mapping rules applied successfully!');
                }}
                className="btn btn-success"
                disabled={mappingRules.length === 0}
              >
                ✅ Apply Mapping Rules
              </button>
            </div>
          </div>
        )}

        {/* Validation Tab */}
        {activeTab === 'validation' && (
          <div className="validation-section">
            <div className="validation-header">
              <h3>Data Quality Validation</h3>
              <button 
                onClick={async () => {
                  if (!spreadsheetData || spreadsheetData.length === 0) {
                    alert('No data to validate. Please import data first.');
                    return;
                  }

                  setIsLoading(true);
                  try {
                    // Use ETL engine for comprehensive validation
                    const validationResult = await etlEngine.validate('schema', spreadsheetData, {
                      schema: {
                        required: Object.keys(spreadsheetData[0] || {}),
                        types: inferDataTypes(spreadsheetData)
                      }
                    });

                    // Also run business rules validation
                    const businessValidation = await etlEngine.validate('business', spreadsheetData, {
                      rules: [
                        { field: 'id', rule: 'unique', message: 'ID must be unique' },
                        { field: 'email', rule: 'email', message: 'Invalid email format' },
                        { field: 'date', rule: 'date', message: 'Invalid date format' }
                      ]
                    });

                    // Combine validation results with existing format
                    const existingResults = validateData(spreadsheetData);
                    const enhancedResults = existingResults.map((result, index) => ({
                      ...result,
                      etlValidation: validationResult.isValid,
                      schemaErrors: validationResult.errors?.filter(e => e.field === result.column) || [],
                      businessErrors: businessValidation.errors?.filter(e => e.field === result.column) || []
                    }));

                    setDataValidationResults(enhancedResults);

                    // Show validation summary
                    const summary = `
Validation Complete:
• Total Records: ${validationResult.recordCount || spreadsheetData.length}
• Valid Records: ${validationResult.validRecords || 0}
• Schema Errors: ${validationResult.errors?.length || 0}
• Business Rule Errors: ${businessValidation.errors?.length || 0}
• Pass Rate: ${validationResult.results?.passRate?.toFixed(1) || '0'}%`;
                    
                    alert(summary);

                  } catch (error) {
                    console.error('Enhanced validation failed:', error);
                    // Fallback to basic validation
                    const results = validateData(spreadsheetData);
                    setDataValidationResults(results);
                  } finally {
                    setIsLoading(false);
                  }
                }}
                className="btn btn-primary"
                disabled={!spreadsheetData.length || isLoading}
              >
                🔍 Run Validation
              </button>
            </div>

            {dataValidationResults.length > 0 && (
              <div className="validation-results">
                <h4>Validation Results:</h4>
                <div className="validation-grid">
                  {dataValidationResults.map((result, index) => (
                    <div key={index} className="validation-card">
                      <div className="validation-header-row">
                        <h5>{result.column}</h5>
                        <span className={`quality-score ${parseFloat(result.completeness) >= 90 ? 'excellent' : parseFloat(result.completeness) >= 70 ? 'good' : 'poor'}`}>
                          {result.completeness}%
                        </span>
                      </div>
                      <div className="validation-metrics">
                        <div className="metric">
                          <span className="metric-label">Completeness:</span>
                          <span>{result.completeness}%</span>
                        </div>
                        <div className="metric">
                          <span className="metric-label">Type Consistency:</span>
                          <span className={result.typeConsistency === 'Good' ? 'good' : 'warning'}>{result.typeConsistency}</span>
                        </div>
                        <div className="metric">
                          <span className="metric-label">Unique Values:</span>
                          <span>{result.uniqueValues}</span>
                        </div>
                      </div>
                      {result.issues.length > 0 && (
                        <div className="validation-issues">
                          <h6>Issues:</h6>
                          <ul>
                            {result.issues.map((issue, i) => (
                              <li key={i}>{issue}</li>
                            ))}
                          </ul>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {dataValidationResults.length === 0 && (
              <div className="no-validation">
                <p>No validation results yet. Click "Validate Data" to analyze your data quality.</p>
              </div>
            )}
          </div>
        )}

        {/* Templates Tab */}
        {activeTab === 'templates' && (
          <div className="templates-section">
            <div className="templates-header">
              <h3>Mapping Templates</h3>
              <div className="template-actions">
                <input
                  type="text"
                  placeholder="Template name..."
                  onKeyPress={(e) => {
                    if (e.key === 'Enter') {
                      saveMappingTemplate(e.target.value);
                      e.target.value = '';
                    }
                  }}
                />
                <button 
                  onClick={() => {
                    const name = prompt('Enter template name:');
                    if (name) saveMappingTemplate(name);
                  }}
                  className="btn btn-primary"
                  disabled={!mappingRules.length}
                >
                  💾 Save Current Rules
                </button>
              </div>
            </div>

            <div className="templates-grid">
              {savedMappingTemplates.length === 0 ? (
                <div className="no-templates">
                  <p>No saved templates. Create mapping rules and save them as templates for reuse.</p>
                </div>
              ) : (
                savedMappingTemplates.map(template => (
                  <div key={template.id} className="template-card">
                    <div className="template-header-row">
                      <h5>{template.name}</h5>
                      <span className="template-date">{new Date(template.createdAt).toLocaleDateString()}</span>
                    </div>
                    <div className="template-info">
                      <div className="template-detail">
                        <span>Rules: {template.rules.length}</span>
                      </div>
                      <div className="template-detail">
                        <span>{template.sourceFormat.toUpperCase()} → {template.targetFormat.toUpperCase()}</span>
                      </div>
                    </div>
                    <div className="template-actions">
                      <button 
                        onClick={() => loadMappingTemplate(template)}
                        className="btn btn-secondary btn-sm"
                      >
                        📥 Load
                      </button>
                      <button 
                        onClick={() => deleteMappingTemplate(template.id)}
                        className="btn btn-danger btn-sm"
                      >
                        🗑️ Delete
                      </button>
                    </div>
                  </div>
                ))
              )}
            </div>

            <div className="predefined-templates">
              <h4>Predefined Templates:</h4>
              <div className="predefined-grid">
                <div className="template-card predefined">
                  <h5>NiFi Process Data</h5>
                  <p>Template for processing NiFi flow data with common transformations</p>
                  <button 
                    onClick={() => {
                      const nifiRules = [
                        { id: Date.now(), sourceColumn: 0, targetColumn: 0, transformation: 'trim', customFunction: 'return value;' },
                        { id: Date.now() + 1, sourceColumn: 2, targetColumn: 2, transformation: 'uppercase', customFunction: 'return value;' }
                      ];
                      setMappingRules(nifiRules);
                      alert('NiFi template loaded');
                    }}
                    className="btn btn-success btn-sm"
                  >
                    📥 Load Template
                  </button>
                </div>
                
                <div className="template-card predefined">
                  <h5>Data Cleanup</h5>
                  <p>General data cleaning rules (trim, normalize case, remove special chars)</p>
                  <button 
                    onClick={() => {
                      const cleanupRules = [
                        { id: Date.now(), sourceColumn: 0, targetColumn: 0, transformation: 'trim', customFunction: 'return value;' },
                        { id: Date.now() + 1, sourceColumn: 1, targetColumn: 1, transformation: 'remove_special', customFunction: 'return value;' }
                      ];
                      setMappingRules(cleanupRules);
                      alert('Data cleanup template loaded');
                    }}
                    className="btn btn-success btn-sm"
                  >
                    📥 Load Template
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Chart Tab */}
        {activeTab === 'chart' && (
          <div className="chart-section">
            <ReactECharts
              ref={chartRef}
              option={getChartOption()}
              style={{ height: '600px', width: '100%' }}
              notMerge={true}
              lazyUpdate={true}
            />
          </div>
        )}

        {/* Config Tab */}
        {activeTab === 'config' && (
          <div className="config-section">
            <div className="config-grid">
              <div className="config-group">
                <label>Chart Type:</label>
                <select
                  value={chartConfig.type}
                  onChange={(e) => setChartConfig({...chartConfig, type: e.target.value})}
                >
                  <option value="bar">Bar Chart</option>
                  <option value="line">Line Chart</option>
                  <option value="area">Area Chart</option>
                  <option value="pie">Pie Chart</option>
                  <option value="scatter">Scatter Plot</option>
                </select>
              </div>

              <div className="config-group">
                <label>Title:</label>
                <input
                  type="text"
                  value={chartConfig.title}
                  onChange={(e) => setChartConfig({...chartConfig, title: e.target.value})}
                />
              </div>

              <div className="config-group">
                <label>X-Axis Column:</label>
                <select
                  value={chartConfig.xAxisColumn}
                  onChange={(e) => setChartConfig({...chartConfig, xAxisColumn: parseInt(e.target.value)})}
                >
                  {(spreadsheetData[0] || []).map((header, index) => (
                    <option key={index} value={index}>{header}</option>
                  ))}
                </select>
              </div>

              <div className="config-group">
                <label>Y-Axis Columns:</label>
                <div className="checkbox-group">
                  {(spreadsheetData[0] || []).map((header, index) => (
                    <label key={index} className="checkbox-label">
                      <input
                        type="checkbox"
                        checked={chartConfig.yAxisColumns.includes(index)}
                        onChange={(e) => {
                          const newColumns = e.target.checked
                            ? [...chartConfig.yAxisColumns, index]
                            : chartConfig.yAxisColumns.filter(col => col !== index);
                          setChartConfig({...chartConfig, yAxisColumns: newColumns});
                        }}
                      />
                      {header}
                    </label>
                  ))}
                </div>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Loading Overlay */}
      {isLoading && (
        <div className="loading-overlay">
          <div className="loading-spinner">Loading...</div>
        </div>
      )}
    </div>
  );
};

export default EChartsSpreadsheetPage;
