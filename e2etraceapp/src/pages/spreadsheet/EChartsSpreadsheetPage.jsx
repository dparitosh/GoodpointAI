import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import ReactECharts from 'echarts-for-react';
import { saveAs } from 'file-saver';
import { readExcelArrayBufferToAoa, sheetsToXlsxBlob } from '../../utils/spreadsheet-utils.js';
import { useSearchParams } from 'react-router-dom';

import { e2etraceFetchWithRetry } from '../../api/e2etrace-api';
import { API_CONFIG } from '../../config/api-config.js';
import { etlEngine } from '../../services/etl-engine';

import './EChartsSpreadsheetPage.css';

const EChartsSpreadsheetPage = () => {
  const [searchParams] = useSearchParams();
  // Spreadsheet state
  const [spreadsheetData, setSpreadsheetData] = useState([]);
  const [selectedData, setSelectedData] = useState([]);
  const [dragStart, setDragStart] = useState(null);
  const [dragEnd, setDragEnd] = useState(null);

  // UI state
  const [activeTab, setActiveTab] = useState('data');
  const [isLoading, setIsLoading] = useState(false);

  // Conversion state
  const [rawData, setRawData] = useState('');
  const [sourceFormat, setSourceFormat] = useState('json');
  const [targetFormat, setTargetFormat] = useState('csv');
  const [mappingRules, setMappingRules] = useState([]);
  const [conversionHistory, setConversionHistory] = useState([]);
  const [dataValidationResults, setDataValidationResults] = useState([]);
  const [savedMappingTemplates, setSavedMappingTemplates] = useState([]);

  // Chart state
  const [chartConfig, setChartConfig] = useState({
    type: 'bar',
    title: 'Data Visualization',
    xAxisColumn: 0,
    yAxisColumns: [1],
    legendColumn: null,
  });

  const fileInputRef = useRef(null);

  const flattenToKeyValueRows = useCallback((obj, prefix = '') => {
    const rows = [];
    const walk = (value, path) => {
      if (value == null) {
        rows.push([path, '']);
        return;
      }
      if (Array.isArray(value)) {
        if (value.length === 0) {
          rows.push([path, '[]']);
          return;
        }
        value.forEach((v, idx) => walk(v, `${path}[${idx}]`));
        return;
      }
      if (typeof value === 'object') {
        const keys = Object.keys(value);
        if (keys.length === 0) {
          rows.push([path, '{}']);
          return;
        }
        keys.forEach((k) => walk(value[k], path ? `${path}.${k}` : k));
        return;
      }
      rows.push([path, String(value)]);
    };

    walk(obj, prefix);
    return rows;
  }, []);

  useEffect(() => {
    const reportId = String(searchParams.get('reportId') || '').trim();
    if (!reportId) return;

    let cancelled = false;
    const run = async () => {
      setIsLoading(true);
      try {
        const res = await fetch(`/api/reports/${encodeURIComponent(reportId)}`);
        if (!res.ok) throw new Error('Failed to load report');
        const data = await res.json();
        if (cancelled) return;

        const payload = data?.payload ?? {};
        const rows = flattenToKeyValueRows(payload);
        setSpreadsheetData([['field', 'value'], ...rows]);
        setSelectedData([]);
        setActiveTab('data');
      } catch (error) {
        if (!cancelled) {
          alert(error?.message || 'Failed to load report');
        }
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    };

    run();
    return () => {
      cancelled = true;
    };
  }, [flattenToKeyValueRows, searchParams]);

  const convertCsvToJson = useCallback((csvData) => {
    if (!Array.isArray(csvData) || csvData.length < 2) return [];
    const [headers, ...rows] = csvData;
    return rows.map((row) => {
      const obj = {};
      headers.forEach((header, index) => {
        obj[header] = row[index] ?? '';
      });
      return obj;
    });
  }, []);

  const convertXmlToCsv = useCallback((xmlData) => {
    const parser = new DOMParser();
    const xmlDoc = parser.parseFromString(xmlData, 'text/xml');
    if (xmlDoc.getElementsByTagName('parsererror').length > 0) {
      throw new Error('Invalid XML format');
    }

    const root = xmlDoc.documentElement;
    const records = Array.from(root.children);
    if (!records.length) throw new Error('No data elements found in XML');

    const first = records[0];
    const headers = Array.from(first.children).map((c) => c.tagName);
    const rows = records.map((el) =>
      headers.map((h) => el.getElementsByTagName(h)[0]?.textContent?.trim() || '')
    );
    return [headers, ...rows];
  }, []);

  const validateData = useCallback((data) => {
    const results = [];
    if (!data?.length) return results;
    const headers = data[0] || [];
    const rows = data.slice(1);
    if (!rows.length) return results;

    headers.forEach((header, colIndex) => {
      const columnData = rows.map((row) => row[colIndex]);
      const nonEmptyCount = columnData.filter((cell) => cell != null && String(cell).trim()).length;
      const completeness = (nonEmptyCount / rows.length) * 100;
      results.push({
        column: header,
        index: colIndex,
        completeness: completeness.toFixed(1),
      });
    });

    return results;
  }, []);

  const handleFileImport = async (event) => {
    const file = event.target.files?.[0];
    if (!file) return;

    setIsLoading(true);
    try {
      const ext = (file.name.split('.').pop() || '').toLowerCase();

      if (ext === 'xlsx' || ext === 'xls') {
        const buffer = await file.arrayBuffer();
        const aoa = await readExcelArrayBufferToAoa(buffer);
        setSpreadsheetData(aoa);
        setSelectedData([]);
        setActiveTab('data');
        return;
      }

      const text = await file.text();
      if (ext === 'csv') {
        const rows = text
          .split(/\r?\n/)
          .filter((l) => l.trim().length > 0)
          .map((line) => line.split(',').map((v) => v.trim()));
        setSpreadsheetData(rows);
        setSelectedData([]);
        setActiveTab('data');
        return;
      }

      if (ext === 'json') {
        const parsed = JSON.parse(text);
        const arr = Array.isArray(parsed) ? parsed : [parsed];
        const headers = Array.from(
          arr.reduce((s, obj) => {
            Object.keys(obj || {}).forEach((k) => s.add(k));
            return s;
          }, new Set())
        );
        const rows = arr.map((obj) => headers.map((h) => (obj && obj[h] != null ? String(obj[h]) : '')));
        setSpreadsheetData([headers, ...rows]);
        setSelectedData([]);
        setActiveTab('data');
        return;
      }

      if (ext === 'xml') {
        const aoa = convertXmlToCsv(text);
        setSpreadsheetData(aoa);
        setSelectedData([]);
        setActiveTab('data');
        return;
      }

      throw new Error(`Unsupported file type: .${ext}`);
    } catch (error) {
      console.error('File import failed:', error);
      alert(`Import failed: ${error.message}`);
    } finally {
      setIsLoading(false);
      event.target.value = '';
    }
  };

  const handleAdvancedExport = useCallback(
    async (format) => {
      const dataToExport = selectedData.length ? selectedData : spreadsheetData;
      if (!dataToExport.length) return;

      switch (format) {
        case 'excel': {
          const excelBlob = await sheetsToXlsxBlob([{ name: 'Data', aoa: dataToExport }]);
          saveAs(excelBlob, 'echarts-spreadsheet-data.xlsx');
          break;
        }
        case 'csv': {
          const csvContent = dataToExport
            .map((row) => row.map((cell) => `"${String(cell ?? '').replace(/"/g, '""')}"`).join(','))
            .join('\n');
          const csvBlob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
          saveAs(csvBlob, 'echarts-spreadsheet-data.csv');
          break;
        }
        case 'json': {
          if (dataToExport.length < 2) return;
          const jsonData = convertCsvToJson(dataToExport);
          const jsonBlob = new Blob([JSON.stringify(jsonData, null, 2)], { type: 'application/json' });
          saveAs(jsonBlob, 'echarts-spreadsheet-data.json');
          break;
        }
        case 'xml': {
          if (dataToExport.length < 2) return;
          const [headers, ...rows] = dataToExport;
          let xmlContent = '<?xml version="1.0" encoding="UTF-8"?>\n<data>\n';
          rows.forEach((row) => {
            xmlContent += '  <record>\n';
            headers.forEach((header, index) => {
              const tag = String(header || 'field').replace(/[^a-zA-Z0-9_\-]/g, '_');
              xmlContent += `    <${tag}>${row[index] ?? ''}</${tag}>\n`;
            });
            xmlContent += '  </record>\n';
          });
          xmlContent += '</data>';
          const xmlBlob = new Blob([xmlContent], { type: 'application/xml' });
          saveAs(xmlBlob, 'echarts-spreadsheet-data.xml');
          break;
        }
      }
    },
    [convertCsvToJson, selectedData, spreadsheetData]
  );

  const loadNeo4jData = async () => {
    setIsLoading(true);
    try {
      const response = await e2etraceFetchWithRetry(API_CONFIG.ENDPOINTS.GRAPH);
      const data = await response.json();

      const headers = ['Node ID', 'Label', 'Properties', 'Connections'];
      const rows = (data.nodes || []).map((node) => {
        const nodeId = node?.data?.id;
        const connections = (data.edges || []).filter(
          (edge) => edge?.data?.source === nodeId || edge?.data?.target === nodeId
        ).length;
        return [
          nodeId ?? '',
          node?.data?.label || 'Unknown',
          JSON.stringify(node?.data?.properties || {}),
          connections,
        ];
      });

      setSpreadsheetData([headers, ...rows]);
      setSelectedData([]);
      setActiveTab('data');
    } catch (error) {
      console.error('Error loading graph data:', error);
      alert('Error loading graph data. Please check the backend connection.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleCellMouseDown = (rowIndex, colIndex) => {
    setDragStart({ row: rowIndex, col: colIndex });
    setDragEnd(null);
  };

  const handleCellMouseEnter = (rowIndex, colIndex) => {
    if (dragStart) setDragEnd({ row: rowIndex, col: colIndex });
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
          row.push(spreadsheetData[r]?.[c] ?? '');
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

  const handleDataConversion = async () => {
    if (!rawData.trim()) return;
    setIsLoading(true);
    try {
      let converted;

      if (sourceFormat === 'json') {
        const parsed = JSON.parse(rawData);
        const arr = Array.isArray(parsed) ? parsed : [parsed];
        const headers = Object.keys(arr[0] || {});
        converted = [headers, ...arr.map((o) => headers.map((h) => (o && o[h] != null ? String(o[h]) : '')))];
      } else if (sourceFormat === 'xml') {
        converted = convertXmlToCsv(rawData);
      } else {
        converted = rawData
          .split(/\r?\n/)
          .filter((l) => l.trim().length > 0)
          .map((line) => line.split(',').map((v) => v.trim()));
      }

      setSpreadsheetData(converted);
      setSelectedData([]);
      setActiveTab('data');

      const validationResults = validateData(converted);
      setDataValidationResults(validationResults);

      setConversionHistory((prev) =>
        [
          {
            id: Date.now(),
            timestamp: new Date().toISOString(),
            sourceFormat,
            targetFormat,
            rowCount: Math.max(0, converted.length - 1),
            mappingRulesUsed: mappingRules.length,
          },
          ...prev,
        ].slice(0, 10)
      );
    } catch (error) {
      console.error('Conversion failed:', error);
      alert(`Conversion failed: ${error.message}`);
    } finally {
      setIsLoading(false);
    }
  };

  const saveMappingTemplate = (name) => {
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
      targetFormat,
    };

    setSavedMappingTemplates((prev) => [...prev, template]);
  };

  const loadMappingTemplate = (template) => {
    setMappingRules(template.rules || []);
    setSourceFormat(template.sourceFormat || 'json');
    setTargetFormat(template.targetFormat || 'csv');
  };

  const deleteMappingTemplate = (templateId) => {
    setSavedMappingTemplates((prev) => prev.filter((t) => t.id !== templateId));
  };

  const chartOption = useMemo(() => {
    const data = selectedData.length ? selectedData : spreadsheetData;
    if (!data?.length || data.length < 2) return {};

    const headers = data[0] || [];
    const rows = data.slice(1);
    const { type, title, xAxisColumn, yAxisColumns } = chartConfig;

    const categories = rows.map((row) => row[xAxisColumn] ?? '');
    const series = (yAxisColumns || []).map((colIndex) => ({
      name: headers[colIndex] || `Series ${colIndex}`,
      type,
      data: rows.map((row) => {
        const v = row[colIndex];
        const n = Number(v);
        return Number.isFinite(n) ? n : 0;
      }),
    }));

    return {
      title: { text: title, left: 'center' },
      tooltip: { trigger: type === 'pie' ? 'item' : 'axis' },
      xAxis: { type: 'category', data: categories },
      yAxis: { type: 'value' },
      series,
    };
  }, [chartConfig, selectedData, spreadsheetData]);

  return (
    <div className="echarts-spreadsheet-page">
      <div className="spreadsheet-header">
        <h1>◳ ECharts Data Spreadsheet</h1>
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
            ◻ Import File
          </button>

          <div className="export-dropdown">
            <button className="btn btn-secondary dropdown-toggle" disabled={!spreadsheetData.length}>
              ◻ Export
            </button>
            <div className="dropdown-menu">
              <button onClick={() => handleAdvancedExport('excel')} className="dropdown-item">
                ◳ Excel (.xlsx)
              </button>
              <button onClick={() => handleAdvancedExport('csv')} className="dropdown-item">
                ◳ CSV (.csv)
              </button>
              <button onClick={() => handleAdvancedExport('json')} className="dropdown-item">
                ◰ JSON (.json)
              </button>
              <button onClick={() => handleAdvancedExport('xml')} className="dropdown-item">
                ◻ XML (.xml)
              </button>
            </div>
          </div>

          <button onClick={loadNeo4jData} className="btn btn-info" disabled={isLoading}>
            ↦ Import from Neo4j
          </button>
        </div>
      </div>

      <div className="tab-navigation">
        <button type="button" className={`tab ${activeTab === 'data' ? 'active' : ''}`} onClick={() => setActiveTab('data')}>
          Data
        </button>
        <button type="button" className={`tab ${activeTab === 'convert' ? 'active' : ''}`} onClick={() => setActiveTab('convert')}>
          Convert
        </button>
        <button type="button" className={`tab ${activeTab === 'mapping' ? 'active' : ''}`} onClick={() => setActiveTab('mapping')}>
          Mapping
        </button>
        <button type="button" className={`tab ${activeTab === 'validation' ? 'active' : ''}`} onClick={() => setActiveTab('validation')}>
          Validation
        </button>
        <button type="button" className={`tab ${activeTab === 'templates' ? 'active' : ''}`} onClick={() => setActiveTab('templates')}>
          Templates
        </button>
        <button type="button" className={`tab ${activeTab === 'chart' ? 'active' : ''}`} onClick={() => setActiveTab('chart')}>
          Chart
        </button>
        <button type="button" className={`tab ${activeTab === 'config' ? 'active' : ''}`} onClick={() => setActiveTab('config')}>
          Config
        </button>
      </div>

      {activeTab === 'data' && (
        <div className="data-section">
          <div className="data-info">
            <span>Rows: {spreadsheetData.length}</span>
            <span>Columns: {spreadsheetData[0]?.length || 0}</span>
            {selectedData.length > 0 && (
              <span>
                Selected: {selectedData.length}×{selectedData[0]?.length || 0}
              </span>
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

      {activeTab === 'convert' && (
        <div className="convert-section">
          <div className="convert-container">
            <div className="convert-controls">
              <div className="format-selectors">
                <div className="format-group">
                  <label>Source Format:</label>
                  <select value={sourceFormat} onChange={(e) => setSourceFormat(e.target.value)}>
                    <option value="json">JSON</option>
                    <option value="xml">XML</option>
                    <option value="csv">CSV</option>
                  </select>
                </div>
                <div className="conversion-arrow">→</div>
                <div className="format-group">
                  <label>Target Format:</label>
                  <select value={targetFormat} onChange={(e) => setTargetFormat(e.target.value)}>
                    <option value="csv">CSV/Spreadsheet</option>
                    <option value="json">JSON</option>
                    <option value="xml">XML</option>
                  </select>
                </div>
              </div>

              <button
                onClick={handleDataConversion}
                className="btn btn-primary conversion-btn"
                disabled={isLoading || !rawData.trim()}
              >
                ↻ Convert Data
              </button>
            </div>

            <div className="convert-input">
              <label>Input:</label>
              <textarea value={rawData} onChange={(e) => setRawData(e.target.value)} placeholder="Paste data here" />
            </div>

            {conversionHistory.length > 0 && (
              <div className="conversion-history">
                <h4>Recent Conversions</h4>
                <div className="history-list">
                  {conversionHistory.map((entry) => (
                    <div key={entry.id} className="history-item">
                      <span>{new Date(entry.timestamp).toLocaleString()}</span>
                      <span>
                        {entry.sourceFormat.toUpperCase()} → {entry.targetFormat.toUpperCase()}
                      </span>
                      <span>{entry.rowCount} rows</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {activeTab === 'mapping' && (
        <div className="mapping-section">
          <div className="mapping-container">
            <div className="mapping-header">
              <h3>Mapping Rules</h3>
              <button
                className="btn btn-secondary"
                onClick={() =>
                  setMappingRules((prev) => [
                    ...prev,
                    { id: Date.now(), sourceColumn: 0, targetColumn: 0, transformation: 'none', customFunction: 'return value;' },
                  ])
                }
              >
                + Add Rule
              </button>
            </div>

            {mappingRules.length === 0 ? (
              <p>No rules configured.</p>
            ) : (
              <div className="mapping-rules">
                {mappingRules.map((rule) => (
                  <div key={rule.id} className="mapping-rule">
                    <div>
                      <label>Source Column</label>
                      <input
                        type="number"
                        value={rule.sourceColumn}
                        onChange={(e) =>
                          setMappingRules((prev) =>
                            prev.map((r) => (r.id === rule.id ? { ...r, sourceColumn: Number(e.target.value) } : r))
                          )
                        }
                      />
                    </div>
                    <div>
                      <label>Target Column</label>
                      <input
                        type="number"
                        value={rule.targetColumn}
                        onChange={(e) =>
                          setMappingRules((prev) =>
                            prev.map((r) => (r.id === rule.id ? { ...r, targetColumn: Number(e.target.value) } : r))
                          )
                        }
                      />
                    </div>
                    <div>
                      <label>Transform</label>
                      <select
                        value={rule.transformation}
                        onChange={(e) =>
                          setMappingRules((prev) =>
                            prev.map((r) => (r.id === rule.id ? { ...r, transformation: e.target.value } : r))
                          )
                        }
                      >
                        <option value="none">None</option>
                        <option value="uppercase">Uppercase</option>
                        <option value="lowercase">Lowercase</option>
                        <option value="trim">Trim</option>
                        <option value="number">Number</option>
                      </select>
                    </div>
                    <button className="btn btn-danger" onClick={() => setMappingRules((prev) => prev.filter((r) => r.id !== rule.id))}>
                      Remove
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {activeTab === 'validation' && (
        <div className="validation-section">
          <div className="validation-container">
            <div className="validation-header">
              <h3>Validation Results</h3>
              <button
                className="btn btn-secondary"
                disabled={!spreadsheetData.length || isLoading}
                onClick={async () => {
                  setIsLoading(true);
                  try {
                    const enhanced = await etlEngine.validate('schema', spreadsheetData, { strict: false });
                    setDataValidationResults(Array.isArray(enhanced?.results) ? enhanced.results : validateData(spreadsheetData));
                  } catch (e) {
                    setDataValidationResults(validateData(spreadsheetData));
                  } finally {
                    setIsLoading(false);
                  }
                }}
              >
                Run Validation
              </button>
            </div>

            {dataValidationResults.length === 0 ? (
              <p>No validation results.</p>
            ) : (
              <div className="validation-results">
                {dataValidationResults.map((result, idx) => (
                  <div key={idx} className="validation-result">
                    <strong>{result.column ?? `Column ${result.index ?? idx}`}</strong>
                    <span>Completeness: {result.completeness ?? '—'}%</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {activeTab === 'templates' && (
        <div className="templates-section">
          <div className="templates-container">
            <div className="templates-header">
              <h3>Templates</h3>
              <button className="btn btn-secondary" onClick={() => saveMappingTemplate(prompt('Template name') || '')}>
                Save Current
              </button>
            </div>

            {savedMappingTemplates.length === 0 ? (
              <p>No templates saved.</p>
            ) : (
              <div className="templates-list">
                {savedMappingTemplates.map((t) => (
                  <div key={t.id} className="template-item">
                    <div>
                      <strong>{t.name}</strong>
                      <div>{new Date(t.createdAt).toLocaleString()}</div>
                    </div>
                    <div className="template-actions">
                      <button className="btn btn-primary" onClick={() => loadMappingTemplate(t)}>
                        Load
                      </button>
                      <button className="btn btn-danger" onClick={() => deleteMappingTemplate(t.id)}>
                        Delete
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {activeTab === 'chart' && (
        <div className="chart-section">
          <div className="chart-container">
            <div className="chart-controls">
              <div className="chart-control-group">
                <label>Type:</label>
                <select value={chartConfig.type} onChange={(e) => setChartConfig((c) => ({ ...c, type: e.target.value }))}>
                  <option value="bar">Bar</option>
                  <option value="line">Line</option>
                  <option value="scatter">Scatter</option>
                </select>
              </div>
              <div className="chart-control-group">
                <label>Title:</label>
                <input value={chartConfig.title} onChange={(e) => setChartConfig((c) => ({ ...c, title: e.target.value }))} />
              </div>
            </div>
            <div className="echarts-container">
              <ReactECharts option={chartOption} style={{ height: 420 }} />
            </div>
          </div>
        </div>
      )}

      {activeTab === 'config' && (
        <div className="config-section">
          <div className="config-container">
            <p>Chart and data settings are available in other tabs.</p>
          </div>
        </div>
      )}
    </div>
  );
};

export default EChartsSpreadsheetPage;
