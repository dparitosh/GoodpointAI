/**
 * Enterprise Analytics Hub - Corporate Grade
 * ==========================================
 * 
 * Unified analytics platform integrating:
 * - GraphQL query builder with schema introspection
 * - Multi-datasource support: PostgreSQL, Neo4j, OpenSearch, SODA
 * - Spreadsheet integration: Microsoft 365, Google Sheets
 * - Ollama LLM-powered natural language queries
 * - File content analysis
 * - Quality reports and data profiling
 * 
 * NO EMOJIS - Professional enterprise UI
 */

import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { useSearchParams, Link } from 'react-router-dom';
import ReactECharts from 'echarts-for-react';
import { e2etraceFetchWithRetry } from '../../api/e2etrace-api';
import { getExcelSheetNames, readExcelArrayBufferToAoa } from '../../utils/spreadsheet-utils.js';
import {
  useSchemaIntrospection,
  useGraphQLQuery,
  useGraphQLCatalogue
} from '../../hooks/useGraphQL';
import './EnterpriseAnalyticsHub.css';
import { useReportHub } from '../../hooks/useReportHub.js';
import { useFileFormats } from '../../hooks/useFileFormats.js';

const DATA_SOURCE_CONFIG = {
  postgres: { name: 'PostgreSQL', icon: 'PG', color: '#336791', endpoint: '/api/analytics/sql', queryType: 'SQL' },
  neo4j: { name: 'Neo4j', icon: 'N4J', color: '#008CC1', endpoint: '/api/lineage/cypher', queryType: 'Cypher' },
  opensearch: { name: 'OpenSearch', icon: 'OS', color: '#005EB8', endpoint: '/api/opensearch/search/workflows', queryType: 'OpenSearch DSL' },
  soda: { name: 'SODA Data Quality', icon: 'SDA', color: '#00B4AB', endpoint: '/api/analytics/quality/reports', queryType: 'SODA Check' },
  graphql: { name: 'GraphQL', icon: 'GQL', color: '#E535AB', endpoint: '/api/graphql/db-query', queryType: 'GraphQL' },
  ollama: { name: 'Ollama LLM', icon: 'LLM', color: '#FF6B35', endpoint: '/api/analytics/nlq', queryType: 'Natural Language' }
};

// Visual Query Builder Configuration - matches actual database schema
const QUERY_BUILDER_CONFIG = {
  postgres: {
    entities: ['workflows', 'workflow_instances', 'workflow_definitions', 'data_sources', 'dq_scan_reports', 'reports'],
    fields: {
      workflows: ['id', 'name', 'description', 'status', 'created_at', 'updated_at'],
      workflow_instances: ['id', 'name', 'status', 'source_type', 'target_type', 'progress_percentage', 'quality_score', 'created_at'],
      workflow_definitions: ['id', 'name', 'description', 'state', 'pipeline_id', 'created_at', 'updated_at'],
      data_sources: ['id', 'name', 'type', 'description', 'status', 'environment', 'created_at', 'updated_at'],
      dq_scan_reports: ['scan_id', 'table_name', 'data_source', 'overall_score', 'issues_count', 'scan_date'],
      reports: ['id', 'report_type', 'title', 'source', 'table_name', 'created_at']
    },
    operators: ['=', '!=', '>', '<', '>=', '<=', 'LIKE', 'IN', 'IS NULL', 'IS NOT NULL']
  },
  neo4j: {
    entities: ['SourceSystem', 'TargetSystem', 'DataRecord', 'Transformation', 'Agent'],
    relationships: ['EXTRACTED_FROM', 'TRANSFORMED_BY', 'LOADED_TO', 'PROCESSED_BY', 'DEPENDS_ON'],
    operators: ['=', '<>', '>', '<', 'CONTAINS', 'STARTS WITH', 'ENDS WITH']
  },
  graphql: {
    entities: ['workflows', 'workflow_instances', 'workflow_definitions', 'data_sources', 'reports'],
    fields: {
      workflows: ['id', 'name', 'description', 'status', 'created_at'],
      workflow_instances: ['id', 'name', 'status', 'source_type', 'target_type', 'quality_score'],
      workflow_definitions: ['id', 'name', 'description', 'state', 'pipeline_id'],
      data_sources: ['id', 'name', 'type', 'description', 'status'],
      reports: ['id', 'report_type', 'title', 'source', 'table_name']
    }
  },
  opensearch: {
    indices: ['workflows', 'logs', 'events', 'metrics'],
    queryTypes: ['match', 'term', 'range', 'bool', 'match_all']
  }
};

const CHART_TYPES = [
  { id: 'bar', name: 'Bar Chart' },
  { id: 'line', name: 'Line Chart' },
  { id: 'pie', name: 'Pie Chart' },
  { id: 'scatter', name: 'Scatter Plot' },
  { id: 'area', name: 'Area Chart' },
  { id: 'heatmap', name: 'Heatmap' },
  { id: 'table', name: 'Data Table' }
];

const AGGREGATIONS = [
  { id: 'count', name: 'Count' },
  { id: 'sum', name: 'Sum' },
  { id: 'avg', name: 'Average' },
  { id: 'min', name: 'Minimum' },
  { id: 'max', name: 'Maximum' },
  { id: 'distinct', name: 'Distinct Count' }
];

const VALID_TABS = ['query-builder', 'natural-language', 'quality-reports', 'saved-queries', 'spreadsheets'];

const EnterpriseAnalyticsHub = ({ initialTab = 'query-builder' }) => {
  const [searchParams, setSearchParams] = useSearchParams();
  const tabFromUrl = searchParams.get('tab');
  const resolvedInitial = (tabFromUrl && VALID_TABS.includes(tabFromUrl)) ? tabFromUrl : initialTab;

  // File format helpers \u2014 backend-driven, fallback built-in
  const { acceptTabular, acceptAnalytics } = useFileFormats();

  // Core state
  const [activeTab, setActiveTabState] = useState(resolvedInitial);

  // Keep URL and state in sync
  const setActiveTab = useCallback((tab) => {
    setActiveTabState(tab);
    setSearchParams(tab === 'query-builder' ? {} : { tab }, { replace: true });
  }, [setSearchParams]);
  const [dataSource, setDataSource] = useState('postgres');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const { saveReport: saveToReportHub, saving: rhSaving, saved: rhSaved } = useReportHub();

  // Query Builder state
  const [queryText, setQueryText] = useState('');
  const [queryResults, setQueryResults] = useState(null);
  const [chartType, setChartType] = useState('bar');
  const [aggregation, setAggregation] = useState('count');
  const [groupByField, setGroupByField] = useState('');
  const [valueField, setValueField] = useState('');

  // Visual Query Builder state (like jQuery QueryBuilder)
  const [visualBuilderMode, setVisualBuilderMode] = useState(true);
  const [selectedEntity, setSelectedEntity] = useState('workflows');
  const [selectedFields, setSelectedFields] = useState(['id', 'name', 'status', 'created_at']);
  const [queryRules, setQueryRules] = useState([]);
  const [queryCondition, setQueryCondition] = useState('AND');
  const [queryLimit, setQueryLimit] = useState(100);
  const [queryOrderBy, setQueryOrderBy] = useState('created_at');
  const [queryOrderDir, setQueryOrderDir] = useState('DESC');

  // GraphQL specific
  const { schema } = useSchemaIntrospection();
  useGraphQLQuery();
  const { queries: savedQueries, loadQueries, saveQuery, deleteQuery: deletePersistedQuery } = useGraphQLCatalogue();

  // Natural Language Query state
  const [nlQuery, setNlQuery] = useState('');
  const [nlSuggestions, setNlSuggestions] = useState([]);
  const [nlQueryMetadata, setNlQueryMetadata] = useState(null);

  // Quality Reports state
  const [qualityReports, setQualityReports] = useState([]);
  const [selectedReportIndex, setSelectedReportIndex] = useState(null);
  const [selectedQualityReport, setSelectedQualityReport] = useState(null);
  const [qualityReportDetailLoading, setQualityReportDetailLoading] = useState(false);
  const [qualityInsight, setQualityInsight] = useState(null);
  const [qualityInsightLoading, setQualityInsightLoading] = useState(false);
  const [showScanModal, setShowScanModal] = useState(false);
  const [scanTableInput, setScanTableInput] = useState('');
  const [availableTables, setAvailableTables] = useState([]);
  const [scanModalLoading, setScanModalLoading] = useState(false);
  const [scanModalError, setScanModalError] = useState(null);

  // Save query modal state
  const [saveModalOpen, setSaveModalOpen] = useState(false);
  const [saveModalName, setSaveModalName] = useState('');
  const [saveModalDesc, setSaveModalDesc] = useState('');

  // Saved queries filter + text search
  const [filterSource, setFilterSource] = useState('all');
  const [savedQuerySearch, setSavedQuerySearch] = useState('');

  // Spreadsheet Integration state
  const [spreadsheetConfig, setSpreadsheetConfig] = useState({
    provider: 'none',
    connected: false,
    fileName: null,
    sheets: [],
    selectedSheet: null
  });
  const [spreadsheetData, setSpreadsheetData] = useState([]);
  const [spreadsheetChartType, setSpreadsheetChartType] = useState('bar');
  const [spreadsheetXAxis, setSpreadsheetXAxis] = useState('');
  const [spreadsheetYAxis, setSpreadsheetYAxis] = useState('');
  const [spreadsheetAggregation, setSpreadsheetAggregation] = useState('sum');

  const spreadsheetColumns = useMemo(() => Object.keys(spreadsheetData?.[0] || {}), [spreadsheetData]);

  const filteredSavedQueries = useMemo(() => {
    let qs = filterSource === 'all'
      ? savedQueries
      : savedQueries.filter(q => (q.datasource || 'graphql') === filterSource);
    if (savedQuerySearch.trim()) {
      const lower = savedQuerySearch.toLowerCase();
      qs = qs.filter(q =>
        (q.name || '').toLowerCase().includes(lower) ||
        (q.description || '').toLowerCase().includes(lower)
      );
    }
    return qs;
  }, [savedQueries, filterSource, savedQuerySearch]);

  useEffect(() => {
    if (!Array.isArray(spreadsheetData) || spreadsheetData.length === 0) return;
    if (!Array.isArray(spreadsheetColumns) || spreadsheetColumns.length === 0) return;

    const defaultX = spreadsheetColumns[0];
    const defaultY = spreadsheetColumns[1] || spreadsheetColumns[0];

    if (!spreadsheetXAxis || !spreadsheetColumns.includes(spreadsheetXAxis)) {
      setSpreadsheetXAxis(defaultX);
    }

    if (!spreadsheetYAxis || !spreadsheetColumns.includes(spreadsheetYAxis)) {
      setSpreadsheetYAxis(defaultY);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [spreadsheetData, spreadsheetColumns]);

  // File Analysis state
  const [uploadedFiles, setUploadedFiles] = useState([]);
  const fileInputRef = useRef(null);
  const spreadsheetFileInputRef = useRef(null);
  const spreadsheetXlsxBufferRef = useRef(null);

  // Database status
  const [dbStatus, setDbStatus] = useState({
    postgres: false,
    neo4j: false,
    opensearch: false
  });

  useEffect(() => {
    const checkConnectivity = async () => {
      try {
        const response = await fetch('/health');
        // Check if response is JSON before parsing
        const contentType = response.headers.get('content-type');
        if (!contentType || !contentType.includes('application/json')) {
          // Backend not running - got HTML fallback from Vite
          console.warn('Backend not available (received non-JSON response)');
          setDbStatus({ postgres: false, neo4j: false, opensearch: false });
          return;
        }
        const health = await response.json();
        setDbStatus({
          postgres: health.dependencies?.postgres?.ok || false,
          neo4j: health.dependencies?.neo4j?.ok || false,
          opensearch: health.dependencies?.opensearch?.ok || false
        });
      } catch (err) {
        console.warn('Health check failed - backend may not be running:', err.message);
        setDbStatus({ postgres: false, neo4j: false, opensearch: false });
      }
    };
    checkConnectivity();
  }, []);

  useEffect(() => {
    loadQueries(100, 0).catch(() => {});
    fetchQualityReports();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const fetchQualityReports = async () => {
    try {
      const response = await e2etraceFetchWithRetry('/api/analytics/quality/reports');
      if (response.ok) {
        const data = await response.json();
        setQualityReports(Array.isArray(data) ? data : []);
      } else {
        console.warn('Quality reports returned HTTP', response.status);
        setQualityReports([]);
      }
    } catch (err) {
      console.error('Failed to load quality reports:', err);
      setQualityReports([]);
    }
  };

  const fetchQualityReportDetail = async (scanId) => {
    if (!scanId) {
      setSelectedQualityReport(null);
      return;
    }
    setQualityReportDetailLoading(true);
    try {
      const response = await e2etraceFetchWithRetry(`/api/analytics/quality/reports/${encodeURIComponent(scanId)}`);
      if (response.ok) {
        const data = await response.json();
        setSelectedQualityReport(data || null);
      }
    } catch (err) {
      console.error('Failed to load quality report detail:', err);
      setSelectedQualityReport(null);
    } finally {
      setQualityReportDetailLoading(false);
    }
  };

  const fetchAvailableTables = async () => {
    try {
      const res = await e2etraceFetchWithRetry('/api/analytics/quality/tables');
      if (res.ok) setAvailableTables(await res.json());
    } catch { /* non-fatal */ }
  };

  const runScan = async () => {
    const table = scanTableInput.trim();
    if (!table) { setScanModalError('Please enter or select a table name.'); return; }
    setScanModalLoading(true);
    setScanModalError(null);
    try {
      const res = await e2etraceFetchWithRetry(
        `/api/analytics/quality/scan/${encodeURIComponent(table)}`,
        { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({}) }
      );
      const data = await res.json();
      if (res.ok) {
        setShowScanModal(false);
        setScanTableInput('');
        setTimeout(fetchQualityReports, 800);
      } else {
        setScanModalError(data.detail || 'Scan failed.');
      }
    } catch (err) {
      setScanModalError('Network error: ' + err.message);
    } finally {
      setScanModalLoading(false);
    }
  };

  const fetchQualityInsight = async (scanId) => {
    if (!scanId) { setQualityInsight(null); return; }
    setQualityInsightLoading(true);
    try {
      const response = await e2etraceFetchWithRetry(`/api/analytics/quality/reports/${encodeURIComponent(scanId)}/insights`);
      if (response.ok) {
        setQualityInsight(await response.json());
      } else {
        setQualityInsight(null);
      }
    } catch (err) {
      console.error('Failed to load quality insights:', err);
      setQualityInsight(null);
    } finally {
      setQualityInsightLoading(false);
    }
  };

  // Generate query from visual builder (like jQuery QueryBuilder)
  const generateQueryFromBuilder = useCallback(() => {
    const fields = selectedFields.join(', ') || '*';
    let query = '';

    switch (dataSource) {
      case 'postgres': {
        // Build SQL query
        let whereClause = '';
        if (queryRules.length > 0) {
          const conditions = queryRules.map(rule => {
            const val = typeof rule.value === 'string' ? `'${rule.value}'` : rule.value;
            if (rule.operator === 'IS NULL') return `${rule.field} IS NULL`;
            if (rule.operator === 'IS NOT NULL') return `${rule.field} IS NOT NULL`;
            if (rule.operator === 'IN') return `${rule.field} IN (${rule.value})`;
            if (rule.operator === 'LIKE') return `${rule.field} LIKE '%${rule.value}%'`;
            return `${rule.field} ${rule.operator} ${val}`;
          });
          whereClause = `WHERE ${conditions.join(` ${queryCondition} `)}`;
        }
        query = `SELECT ${fields}\nFROM ${selectedEntity}\n${whereClause}\nORDER BY ${queryOrderBy} ${queryOrderDir}\nLIMIT ${queryLimit}`.trim();
        break;
      }
      case 'neo4j': {
        // Build Cypher query
        const nodeVar = selectedEntity.charAt(0).toLowerCase();
        let whereClause = '';
        if (queryRules.length > 0) {
          const conditions = queryRules.map(rule => {
            const val = typeof rule.value === 'string' ? `'${rule.value}'` : rule.value;
            if (rule.operator === 'CONTAINS') return `${nodeVar}.${rule.field} CONTAINS ${val}`;
            if (rule.operator === 'STARTS WITH') return `${nodeVar}.${rule.field} STARTS WITH ${val}`;
            return `${nodeVar}.${rule.field} ${rule.operator} ${val}`;
          });
          whereClause = `WHERE ${conditions.join(` ${queryCondition} `)}`;
        }
        const returnFields = selectedFields.map(f => `${nodeVar}.${f}`).join(', ');
        query = `MATCH (${nodeVar}:${selectedEntity})\n${whereClause}\nRETURN ${returnFields || nodeVar}\nORDER BY ${nodeVar}.${queryOrderBy} ${queryOrderDir}\nLIMIT ${queryLimit}`.trim();
        break;
      }
      case 'graphql': {
        // Build GraphQL query
        const fieldsStr = selectedFields.join(' ');
        query = `{\n  ${selectedEntity}(limit: ${queryLimit}) {\n    ${fieldsStr}\n  }\n}`;
        break;
      }
      case 'opensearch': {
        // Build OpenSearch DSL
        const mustClauses = queryRules.map(rule => {
          if (rule.operator === '=' || rule.operator === 'term') {
            return { term: { [rule.field]: rule.value } };
          }
          if (rule.operator === 'LIKE' || rule.operator === 'match') {
            return { match: { [rule.field]: rule.value } };
          }
          if (rule.operator === '>' || rule.operator === '>=') {
            return { range: { [rule.field]: { [rule.operator === '>' ? 'gt' : 'gte']: rule.value } } };
          }
          if (rule.operator === '<' || rule.operator === '<=') {
            return { range: { [rule.field]: { [rule.operator === '<' ? 'lt' : 'lte']: rule.value } } };
          }
          return { match: { [rule.field]: rule.value } };
        });
        const queryObj = {
          query: mustClauses.length > 0 
            ? { bool: { [queryCondition === 'AND' ? 'must' : 'should']: mustClauses } }
            : { match_all: {} },
          size: queryLimit,
          sort: [{ [queryOrderBy]: queryOrderDir.toLowerCase() }]
        };
        query = JSON.stringify(queryObj, null, 2);
        break;
      }
      default:
        query = '';
    }
    setQueryText(query);
    return query;
  }, [dataSource, selectedEntity, selectedFields, queryRules, queryCondition, queryLimit, queryOrderBy, queryOrderDir]);

  // Add a new filter rule
  const addQueryRule = useCallback(() => {
    const config = QUERY_BUILDER_CONFIG[dataSource];
    const fields = config?.fields?.[selectedEntity] || config?.entities || ['id'];
    setQueryRules(prev => [...prev, {
      id: Date.now(),
      field: fields[0],
      operator: '=',
      value: ''
    }]);
  }, [dataSource, selectedEntity]);

  // Remove a filter rule
  const removeQueryRule = useCallback((ruleId) => {
    setQueryRules(prev => prev.filter(r => r.id !== ruleId));
  }, []);

  // Update a filter rule
  const updateQueryRule = useCallback((ruleId, updates) => {
    setQueryRules(prev => prev.map(r => r.id === ruleId ? { ...r, ...updates } : r));
  }, []);

  const executeQuery = useCallback(async (overrideText, overrideSource) => {
    const ds = overrideSource || dataSource;
    // In visual builder mode, always generate from the builder to ensure a safe SELECT query
    // In code mode, use the manually entered queryText
    const queryToExecute = overrideText != null
      ? String(overrideText)
      : (visualBuilderMode ? generateQueryFromBuilder() : queryText.trim());

    if (!queryToExecute) {
      setError('Please enter a query or use the visual builder');
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const config = DATA_SOURCE_CONFIG[ds];
      let response;
      let results;

      switch (ds) {
        case 'graphql':
          response = await e2etraceFetchWithRetry(config.endpoint, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ query: queryToExecute, limit: queryLimit })
          });
          results = await response.json();
          if (results.errors && results.errors.length > 0) {
            throw new Error(results.errors[0]?.message || 'GraphQL error');
          }
          // Handle nested data structure
          if (results.data) {
            const dataValues = Object.values(results.data);
            setQueryResults(dataValues.length === 1 ? dataValues[0] : results.data);
          } else {
            setQueryResults(results);
          }
          break;

        case 'neo4j':
          response = await e2etraceFetchWithRetry(config.endpoint, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ cypher: queryToExecute })
          });
          results = await response.json();
          if (results.error) throw new Error(results.error);
          setQueryResults(results.results || results.data || results);
          break;

        case 'postgres':
          response = await e2etraceFetchWithRetry(config.endpoint, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ sql: queryToExecute })
          });
          results = await response.json();
          if (results.error) throw new Error(results.error);
          setQueryResults(results.results || results.data || results);
          break;

        case 'opensearch':
          response = await e2etraceFetchWithRetry(config.endpoint, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ query: JSON.parse(queryToExecute) })
          });
          results = await response.json();
          if (results.error) throw new Error(results.error);
          setQueryResults(results.hits?.hits?.map(h => h._source) || results);
          break;

        default:
          throw new Error(`Unsupported data source: ${ds}`);
      }
    } catch (err) {
      // Provide user-friendly error messages for common SQL validation errors
      let errorMessage = err.message || 'Query execution failed';
      if (errorMessage.includes('must start with SELECT')) {
        errorMessage = '🔒 Security: Only SELECT queries are allowed. This Query Builder is for read-only analytics.';
      } else if (errorMessage.includes('Dangerous keyword')) {
        const keyword = errorMessage.match(/'([A-Z]+)'/)?.[1] || 'keyword';
        errorMessage = `🔒 Security: The keyword "${keyword}" is not allowed. Only SELECT queries are permitted for data safety.`;
      }
      setError(errorMessage);
    } finally {
      setLoading(false);
    }
  }, [queryText, dataSource, visualBuilderMode, generateQueryFromBuilder, queryLimit]);

  const executeNaturalLanguageQuery = useCallback(async () => {
    if (!nlQuery.trim()) return;
    setLoading(true);
    setError(null);
    setNlQueryMetadata(null);
    setNlSuggestions([]);
    try {
      const response = await e2etraceFetchWithRetry('/api/analytics/nlq', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query: nlQuery,
          datasource: dataSource,
          context: { available_tables: schema?.tables || [] }
        })
      });

      const result = await response.json();
      if (!response.ok || !result?.success) {
        throw new Error(result?.error || `Natural language query failed (HTTP ${response.status})`);
      }

      setQueryText(result.generated_query || '');
      setQueryResults(result.results || []);
      setNlQueryMetadata({
        execution_time_ms: result.metadata?.execution_time_ms,
        rows_returned: result.metadata?.rows_returned,
        model: result.metadata?.model,
        llm_powered: result.llm_powered,
        query_type: result.query_type,
        datasource: result.datasource
      });
      setNlSuggestions(result.suggestions || result.related_queries || []);
    } catch (err) {
      setError(err.message || 'Natural language query failed');
    } finally {
      setLoading(false);
    }
  }, [nlQuery, dataSource, schema]);

  const handleSaveQuery = useCallback(() => {
    if (!queryText.trim()) { setError('No query to save'); return; }
    setSaveModalName('');
    setSaveModalDesc('');
    setSaveModalOpen(true);
  }, [queryText]);

  const handleConfirmSave = useCallback(async () => {
    if (!saveModalName.trim()) return;
    try {
      await saveQuery(saveModalName.trim(), queryText, saveModalDesc || `Saved from Analytics Hub - ${dataSource}`, 'graphql');
      setSaveModalOpen(false);
      setSaveModalName('');
      setSaveModalDesc('');
    } catch {
      setError('Failed to save query');
    }
  }, [saveModalName, saveModalDesc, queryText, dataSource, saveQuery]);

  const handleFileUpload = useCallback((event) => {
    const files = Array.from(event?.target?.files || []);
    if (files.length === 0) return;
    files.forEach(file => {
      const reader = new FileReader();
      reader.onload = (e) => {
        let parsedData = null;
        try {
          if (file.name.endsWith('.json')) {
            parsedData = JSON.parse(e.target.result);
          } else if (file.name.endsWith('.csv')) {
            const lines = e.target.result.split('\n');
            const headers = lines[0].split(',').map(h => h.trim());
            parsedData = lines.slice(1).filter(l => l.trim()).map(line => {
              const values = line.split(',');
              return headers.reduce((obj, h, i) => ({ ...obj, [h]: values[i]?.trim() }), {});
            });
          }
        } catch {
          parsedData = e.target.result;
        }
        setUploadedFiles(prev => [...prev, {
          name: file.name,
          size: file.size,
          type: file.type,
          data: parsedData,
          uploadedAt: new Date().toISOString()
        }]);
      };
      if (file.name.endsWith('.json') || file.name.endsWith('.csv') || file.name.endsWith('.txt')) {
        reader.readAsText(file);
      } else {
        reader.readAsArrayBuffer(file);
      }
    });
  }, []);

  const generateChartOption = useMemo(() => {
    if (!queryResults || chartType === 'table') return null;

    let data = queryResults;
    if (typeof data === 'object' && !Array.isArray(data)) {
      data = Object.values(data).flat().filter(d => typeof d === 'object');
    }
    if (!Array.isArray(data) || data.length === 0) return null;

    const keys = Object.keys(data[0] || {});
    const xField = groupByField || keys[0];
    const yField = valueField || keys[1] || keys[0];

    const categories = [...new Set(data.map(d => d[xField]))];
    let values;

    switch (aggregation) {
      case 'sum':
        values = categories.map(cat => 
          data.filter(d => d[xField] === cat)
            .reduce((sum, d) => sum + (parseFloat(d[yField]) || 0), 0)
        );
        break;
      case 'avg':
        values = categories.map(cat => {
          const items = data.filter(d => d[xField] === cat);
          const sum = items.reduce((s, d) => s + (parseFloat(d[yField]) || 0), 0);
          return items.length ? sum / items.length : 0;
        });
        break;
      case 'min':
        values = categories.map(cat =>
          Math.min(...data.filter(d => d[xField] === cat).map(d => parseFloat(d[yField]) || 0))
        );
        break;
      case 'max':
        values = categories.map(cat =>
          Math.max(...data.filter(d => d[xField] === cat).map(d => parseFloat(d[yField]) || 0))
        );
        break;
      case 'distinct':
        values = categories.map(cat =>
          new Set(data.filter(d => d[xField] === cat).map(d => d[yField])).size
        );
        break;
      default:
        values = categories.map(cat => data.filter(d => d[xField] === cat).length);
    }

    const baseOption = {
      backgroundColor: 'transparent',
      textStyle: { color: '#94a3b8' },
      tooltip: { trigger: chartType === 'pie' ? 'item' : 'axis', backgroundColor: 'rgba(30, 41, 59, 0.95)', borderColor: '#475569', textStyle: { color: '#e2e8f0' } },
      legend: { textStyle: { color: '#94a3b8' }, top: 10 },
      grid: { left: '8%', right: '4%', bottom: '15%', top: 40, containLabel: true }
    };

    switch (chartType) {
      case 'pie':
        return {
          ...baseOption,
          series: [{
            type: 'pie',
            radius: ['40%', '70%'],
            data: categories.map((cat, i) => ({ name: cat, value: values[i] })),
            label: { color: '#e2e8f0' }
          }]
        };
      case 'line':
      case 'area':
        return {
          ...baseOption,
          xAxis: { type: 'category', data: categories, name: xField, nameLocation: 'center', nameGap: 35, nameTextStyle: { color: '#94a3b8', fontSize: 12 }, axisLabel: { color: '#94a3b8' }, axisLine: { lineStyle: { color: '#475569' } } },
          yAxis: { type: 'value', name: `${yField} (${aggregation})`, nameLocation: 'middle', nameGap: 50, nameTextStyle: { color: '#94a3b8', fontSize: 12 }, axisLabel: { color: '#94a3b8' }, axisLine: { lineStyle: { color: '#475569' } }, splitLine: { lineStyle: { color: '#334155' } } },
          series: [{
            data: values,
            type: 'line',
            smooth: true,
            areaStyle: chartType === 'area' ? { opacity: 0.3 } : undefined,
            lineStyle: { width: 2 },
            itemStyle: { color: '#3b82f6' }
          }]
        };
      case 'scatter':
        return {
          ...baseOption,
          xAxis: { type: 'value', name: xField, nameLocation: 'center', nameGap: 35, nameTextStyle: { color: '#94a3b8', fontSize: 12 }, axisLabel: { color: '#94a3b8' }, axisLine: { lineStyle: { color: '#475569' } } },
          yAxis: { type: 'value', name: yField, nameLocation: 'middle', nameGap: 50, nameTextStyle: { color: '#94a3b8', fontSize: 12 }, axisLabel: { color: '#94a3b8' }, axisLine: { lineStyle: { color: '#475569' } }, splitLine: { lineStyle: { color: '#334155' } } },
          series: [{
            data: data.slice(0, 100).map(d => [parseFloat(d[xField]) || 0, parseFloat(d[yField]) || 0]),
            type: 'scatter',
            symbolSize: 10,
            itemStyle: { color: '#3b82f6' }
          }]
        };
      default: // bar
        return {
          ...baseOption,
          xAxis: { type: 'category', data: categories, name: xField, nameLocation: 'center', nameGap: 35, nameTextStyle: { color: '#94a3b8', fontSize: 12 }, axisLabel: { color: '#94a3b8', rotate: categories.length > 10 ? 45 : 0 }, axisLine: { lineStyle: { color: '#475569' } } },
          yAxis: { type: 'value', name: `${yField} (${aggregation})`, nameLocation: 'middle', nameGap: 50, nameTextStyle: { color: '#94a3b8', fontSize: 12 }, axisLabel: { color: '#94a3b8' }, axisLine: { lineStyle: { color: '#475569' } }, splitLine: { lineStyle: { color: '#334155' } } },
          series: [{
            data: values,
            type: 'bar',
            barMaxWidth: 50,
            itemStyle: { color: '#3b82f6', borderRadius: [4, 4, 0, 0] }
          }]
        };
    }
  }, [queryResults, chartType, aggregation, groupByField, valueField]);

  // Generate ECharts options for spreadsheet data
  const spreadsheetChartOptions = useMemo(() => {
    if (!spreadsheetData || spreadsheetData.length === 0 || spreadsheetChartType === 'table') return null;
    
    const columns = Object.keys(spreadsheetData[0] || {});
    const xField = spreadsheetXAxis || columns[0];
    const yField = spreadsheetYAxis || columns[1] || columns[0];

    const categories = [...new Set(spreadsheetData.map(d => String(d[xField] || '')))];
    let values;

    switch (spreadsheetAggregation) {
      case 'sum':
        values = categories.map(cat =>
          spreadsheetData.filter(d => String(d[xField]) === cat)
            .reduce((sum, d) => sum + (parseFloat(d[yField]) || 0), 0)
        );
        break;
      case 'avg':
        values = categories.map(cat => {
          const items = spreadsheetData.filter(d => String(d[xField]) === cat);
          const sum = items.reduce((s, d) => s + (parseFloat(d[yField]) || 0), 0);
          return items.length ? Math.round((sum / items.length) * 100) / 100 : 0;
        });
        break;
      case 'min':
        values = categories.map(cat =>
          Math.min(...spreadsheetData.filter(d => String(d[xField]) === cat).map(d => parseFloat(d[yField]) || 0))
        );
        break;
      case 'max':
        values = categories.map(cat =>
          Math.max(...spreadsheetData.filter(d => String(d[xField]) === cat).map(d => parseFloat(d[yField]) || 0))
        );
        break;
      case 'count':
      default:
        values = categories.map(cat => spreadsheetData.filter(d => String(d[xField]) === cat).length);
    }

    const baseOption = {
      backgroundColor: 'transparent',
      textStyle: { color: '#94a3b8' },
      title: { text: `${yField} by ${xField}`, left: 'center', textStyle: { color: '#e2e8f0', fontSize: 16 } },
      tooltip: { trigger: spreadsheetChartType === 'pie' ? 'item' : 'axis', backgroundColor: 'rgba(30, 41, 59, 0.95)', borderColor: '#475569', textStyle: { color: '#e2e8f0' } },
      legend: { textStyle: { color: '#94a3b8' }, top: 35 },
      grid: { left: '3%', right: '4%', bottom: '3%', top: 80, containLabel: true },
      toolbox: {
        feature: {
          saveAsImage: { title: 'Save' },
          dataView: { title: 'Data View', readOnly: true },
          restore: { title: 'Reset' }
        },
        iconStyle: { borderColor: '#94a3b8' }
      }
    };

    switch (spreadsheetChartType) {
      case 'pie':
        return {
          ...baseOption,
          series: [{
            type: 'pie',
            radius: ['40%', '70%'],
            center: ['50%', '55%'],
            data: categories.map((cat, i) => ({ name: cat, value: values[i] })),
            label: { color: '#e2e8f0', formatter: '{b}: {d}%' },
            emphasis: { itemStyle: { shadowBlur: 10, shadowOffsetX: 0, shadowColor: 'rgba(0, 0, 0, 0.5)' } }
          }]
        };
      case 'line':
        return {
          ...baseOption,
          xAxis: { type: 'category', data: categories, name: xField, nameLocation: 'center', nameGap: 35, nameTextStyle: { color: '#94a3b8', fontSize: 12 }, axisLabel: { color: '#94a3b8', rotate: categories.length > 8 ? 45 : 0 }, axisLine: { lineStyle: { color: '#475569' } } },
          yAxis: { type: 'value', name: `${yField} (${spreadsheetAggregation})`, nameLocation: 'middle', nameGap: 50, nameTextStyle: { color: '#94a3b8', fontSize: 12 }, axisLabel: { color: '#94a3b8' }, axisLine: { lineStyle: { color: '#475569' } }, splitLine: { lineStyle: { color: '#334155' } } },
          series: [{
            data: values,
            type: 'line',
            smooth: true,
            lineStyle: { width: 3, color: '#10b981' },
            itemStyle: { color: '#10b981' },
            areaStyle: { opacity: 0.1, color: '#10b981' }
          }]
        };
      case 'area':
        return {
          ...baseOption,
          xAxis: { type: 'category', data: categories, name: xField, nameLocation: 'center', nameGap: 35, nameTextStyle: { color: '#94a3b8', fontSize: 12 }, axisLabel: { color: '#94a3b8', rotate: categories.length > 8 ? 45 : 0 }, axisLine: { lineStyle: { color: '#475569' } } },
          yAxis: { type: 'value', name: `${yField} (${spreadsheetAggregation})`, nameLocation: 'middle', nameGap: 50, nameTextStyle: { color: '#94a3b8', fontSize: 12 }, axisLabel: { color: '#94a3b8' }, axisLine: { lineStyle: { color: '#475569' } }, splitLine: { lineStyle: { color: '#334155' } } },
          series: [{
            data: values,
            type: 'line',
            smooth: true,
            areaStyle: { opacity: 0.4, color: { type: 'linear', x: 0, y: 0, x2: 0, y2: 1, colorStops: [{ offset: 0, color: '#3b82f6' }, { offset: 1, color: 'rgba(59, 130, 246, 0.1)' }] } },
            lineStyle: { width: 2, color: '#3b82f6' },
            itemStyle: { color: '#3b82f6' }
          }]
        };
      case 'scatter':
        return {
          ...baseOption,
          xAxis: { type: 'value', name: xField, nameLocation: 'center', nameGap: 35, nameTextStyle: { color: '#94a3b8', fontSize: 12 }, axisLabel: { color: '#94a3b8' }, axisLine: { lineStyle: { color: '#475569' } } },
          yAxis: { type: 'value', name: yField, nameLocation: 'middle', nameGap: 50, nameTextStyle: { color: '#94a3b8', fontSize: 12 }, axisLabel: { color: '#94a3b8' }, axisLine: { lineStyle: { color: '#475569' } }, splitLine: { lineStyle: { color: '#334155' } } },
          series: [{
            data: spreadsheetData.slice(0, 200).map(d => [parseFloat(d[xField]) || 0, parseFloat(d[yField]) || 0]),
            type: 'scatter',
            symbolSize: 12,
            itemStyle: { color: '#f59e0b' }
          }]
        };
      case 'heatmap':
        return {
          ...baseOption,
          visualMap: { min: Math.min(...values), max: Math.max(...values), calculable: true, orient: 'horizontal', left: 'center', bottom: 10, inRange: { color: ['#1e3a5f', '#3b82f6', '#f59e0b', '#ef4444'] }, textStyle: { color: '#94a3b8' } },
          xAxis: { type: 'category', data: categories.slice(0, 20), name: xField, nameLocation: 'center', nameGap: 35, nameTextStyle: { color: '#94a3b8', fontSize: 12 }, axisLabel: { color: '#94a3b8', rotate: 45 }, axisLine: { lineStyle: { color: '#475569' } } },
          yAxis: { type: 'category', data: [yField], name: 'Value', nameLocation: 'middle', nameGap: 50, nameTextStyle: { color: '#94a3b8', fontSize: 12 }, axisLabel: { color: '#94a3b8' }, axisLine: { lineStyle: { color: '#475569' } } },
          series: [{
            type: 'heatmap',
            data: categories.slice(0, 20).map((cat, i) => [i, 0, values[i]]),
            label: { show: true, color: '#fff' }
          }]
        };
      default: // bar
        return {
          ...baseOption,
          xAxis: { type: 'category', data: categories, name: xField, nameLocation: 'center', nameGap: 35, nameTextStyle: { color: '#94a3b8', fontSize: 12 }, axisLabel: { color: '#94a3b8', rotate: categories.length > 8 ? 45 : 0 }, axisLine: { lineStyle: { color: '#475569' } } },
          yAxis: { type: 'value', name: `${yField} (${spreadsheetAggregation})`, nameLocation: 'middle', nameGap: 50, nameTextStyle: { color: '#94a3b8', fontSize: 12 }, axisLabel: { color: '#94a3b8' }, axisLine: { lineStyle: { color: '#475569' } }, splitLine: { lineStyle: { color: '#334155' } } },
          series: [{
            data: values,
            type: 'bar',
            barMaxWidth: 60,
            itemStyle: {
              color: { type: 'linear', x: 0, y: 0, x2: 0, y2: 1, colorStops: [{ offset: 0, color: '#3b82f6' }, { offset: 1, color: '#1d4ed8' }] },
              borderRadius: [6, 6, 0, 0]
            },
            emphasis: { itemStyle: { color: '#60a5fa' } }
          }]
        };
    }
  }, [spreadsheetData, spreadsheetChartType, spreadsheetXAxis, spreadsheetYAxis, spreadsheetAggregation]);

  const spreadsheetXField = useMemo(() => {
    if (!Array.isArray(spreadsheetColumns) || spreadsheetColumns.length === 0) return '';
    return spreadsheetXAxis && spreadsheetColumns.includes(spreadsheetXAxis)
      ? spreadsheetXAxis
      : spreadsheetColumns[0];
  }, [spreadsheetColumns, spreadsheetXAxis]);

  const spreadsheetYField = useMemo(() => {
    if (!Array.isArray(spreadsheetColumns) || spreadsheetColumns.length === 0) return '';
    const fallback = spreadsheetColumns[1] || spreadsheetColumns[0];
    return spreadsheetYAxis && spreadsheetColumns.includes(spreadsheetYAxis)
      ? spreadsheetYAxis
      : fallback;
  }, [spreadsheetColumns, spreadsheetYAxis]);

  // Load sample spreadsheet data for demo
  const loadSampleSpreadsheetData = useCallback(() => {
    const sampleData = [
      { Department: 'Engineering', Employees: 45, Budget: 2500000, Revenue: 8500000, Quarter: 'Q1' },
      { Department: 'Sales', Employees: 32, Budget: 1800000, Revenue: 12000000, Quarter: 'Q1' },
      { Department: 'Marketing', Employees: 18, Budget: 1200000, Revenue: 4500000, Quarter: 'Q1' },
      { Department: 'HR', Employees: 12, Budget: 800000, Revenue: 0, Quarter: 'Q1' },
      { Department: 'Finance', Employees: 15, Budget: 900000, Revenue: 2000000, Quarter: 'Q1' },
      { Department: 'Engineering', Employees: 48, Budget: 2600000, Revenue: 9200000, Quarter: 'Q2' },
      { Department: 'Sales', Employees: 35, Budget: 1900000, Revenue: 13500000, Quarter: 'Q2' },
      { Department: 'Marketing', Employees: 20, Budget: 1400000, Revenue: 5200000, Quarter: 'Q2' },
      { Department: 'HR', Employees: 12, Budget: 820000, Revenue: 0, Quarter: 'Q2' },
      { Department: 'Finance', Employees: 16, Budget: 950000, Revenue: 2200000, Quarter: 'Q2' },
      { Department: 'Engineering', Employees: 52, Budget: 2800000, Revenue: 10500000, Quarter: 'Q3' },
      { Department: 'Sales', Employees: 38, Budget: 2100000, Revenue: 15000000, Quarter: 'Q3' },
      { Department: 'Marketing', Employees: 22, Budget: 1600000, Revenue: 6000000, Quarter: 'Q3' },
      { Department: 'HR', Employees: 14, Budget: 850000, Revenue: 0, Quarter: 'Q3' },
      { Department: 'Finance', Employees: 17, Budget: 1000000, Revenue: 2500000, Quarter: 'Q3' }
    ];
    setSpreadsheetData(sampleData);
    setSpreadsheetXAxis('Department');
    setSpreadsheetYAxis('Revenue');
    setSpreadsheetConfig((prev) => ({
      ...prev,
      provider: 'demo',
      connected: true
    }));
  }, []);

  const aoaToObjects = useCallback((aoa) => {
    const rows = Array.isArray(aoa) ? aoa : [];
    if (!rows.length) return [];

    const headerRow = Array.isArray(rows[0]) ? rows[0] : [];
    const rawHeaders = headerRow.map((h) => String(h ?? '').trim());
    const headers = rawHeaders.map((h, idx) => (h ? h : `Column${idx + 1}`));

    // Ensure unique header names
    const counts = new Map();
    const uniqueHeaders = headers.map((h) => {
      const n = (counts.get(h) || 0) + 1;
      counts.set(h, n);
      return n === 1 ? h : `${h}_${n}`;
    });

    const dataRows = rows.slice(1);
    const out = [];
    for (const row of dataRows) {
      const cells = Array.isArray(row) ? row : [];
      const obj = {};
      let hasAnyValue = false;
      for (let i = 0; i < uniqueHeaders.length; i++) {
        const v = cells[i];
        const value = v == null ? '' : String(v);
        if (value !== '') hasAnyValue = true;
        obj[uniqueHeaders[i]] = value;
      }
      if (hasAnyValue) out.push(obj);
    }
    return out;
  }, []);

  const importSpreadsheetFile = useCallback(async (file) => {
    if (!file) return;
    const name = String(file.name || '').toLowerCase();

    try {
      setError(null);

      if (name.endsWith('.xlsx')) {
        const arrayBuffer = await file.arrayBuffer();
        spreadsheetXlsxBufferRef.current = arrayBuffer;

        const sheetNames = await getExcelSheetNames(arrayBuffer);
        const selectedSheet = sheetNames?.[0] || null;
        const aoa = await readExcelArrayBufferToAoa(arrayBuffer, selectedSheet ?? undefined);
        const items = aoaToObjects(aoa);
        setSpreadsheetData(items);
        setSpreadsheetConfig((prev) => ({
          ...prev,
          provider: prev.provider === 'microsoft' || prev.provider === 'google' ? prev.provider : 'local',
          connected: true,
          fileName: file.name || null,
          sheets: sheetNames || [],
          selectedSheet
        }));
        return;
      }

      if (name.endsWith('.csv')) {
        spreadsheetXlsxBufferRef.current = null;
        const text = await file.text();
        const lines = text.split(/\r?\n/).filter((l) => l.trim() !== '');
        if (!lines.length) {
          setSpreadsheetData([]);
          return;
        }
        // Simple CSV parse (quoted commas supported in a basic way)
        const parseLine = (line) => {
          const out = [];
          let cur = '';
          let inQuotes = false;
          for (let i = 0; i < line.length; i++) {
            const ch = line[i];
            if (ch === '"') {
              const next = line[i + 1];
              if (inQuotes && next === '"') {
                cur += '"';
                i++;
              } else {
                inQuotes = !inQuotes;
              }
              continue;
            }
            if (ch === ',' && !inQuotes) {
              out.push(cur);
              cur = '';
              continue;
            }
            cur += ch;
          }
          out.push(cur);
          return out;
        };

        const aoa = lines.map(parseLine);
        const items = aoaToObjects(aoa);
        setSpreadsheetData(items);
        setSpreadsheetConfig((prev) => ({
          ...prev,
          provider: prev.provider === 'microsoft' || prev.provider === 'google' ? prev.provider : 'local',
          connected: true,
          fileName: file.name || null,
          sheets: [],
          selectedSheet: null
        }));
        return;
      }

      setError(`Unsupported file type. Supported: ${acceptTabular.replace(/,/g, ', ')}`);
    } catch (err) {
      setError(`Failed to import spreadsheet: ${err?.message || String(err)}`);
    }
  }, [aoaToObjects]);

  const reloadSelectedSpreadsheetSheet = useCallback(async (nextSelectedSheet) => {
    const buffer = spreadsheetXlsxBufferRef.current;
    if (!buffer) return;
    try {
      setError(null);
      const aoa = await readExcelArrayBufferToAoa(buffer, nextSelectedSheet ?? undefined);
      const items = aoaToObjects(aoa);
      setSpreadsheetData(items);
      setSpreadsheetConfig((prev) => ({
        ...prev,
        selectedSheet: nextSelectedSheet
      }));
    } catch (err) {
      setError(`Failed to load sheet: ${err?.message || String(err)}`);
    }
  }, [aoaToObjects]);

  const onSpreadsheetFileSelected = useCallback(async (event) => {
    const file = event?.target?.files?.[0];
    await importSpreadsheetFile(file);
    if (event?.target) event.target.value = '';
  }, [importSpreadsheetFile]);

  const renderDataTable = () => {
    if (!queryResults) return null;
    let data = queryResults;
    if (typeof data === 'object' && !Array.isArray(data)) {
      data = Object.values(data).flat().filter(d => typeof d === 'object');
    }
    if (!Array.isArray(data) || data.length === 0) {
      return <div className="no-data">No tabular data to display</div>;
    }
    const columns = Object.keys(data[0] || {});
    return (
      <div className="data-table-container">
        <table className="data-table">
          <thead>
            <tr>{columns.map(col => <th key={col}>{col}</th>)}</tr>
          </thead>
          <tbody>
            {data.slice(0, 100).map((row, i) => (
              <tr key={i}>{columns.map(col => <td key={col}>{JSON.stringify(row[col])}</td>)}</tr>
            ))}
          </tbody>
        </table>
        {data.length > 100 && <div className="table-footer">Showing first 100 of {data.length} rows</div>}
      </div>
    );
  };

  // Enhanced Data Table for NLQ results - styled like Conversational Search
  const renderEnhancedDataTable = () => {
    if (!queryResults) return <div className="no-data">No queryResults</div>;
    
    let data = queryResults;
    
    // Handle non-array results
    if (typeof data === 'object' && !Array.isArray(data)) {
      data = Object.values(data).flat().filter(d => d && typeof d === 'object');
    }
    
    if (!Array.isArray(data) || data.length === 0) {
      return <div className="no-data">No results to display (data not array or empty)</div>;
    }
    
    const columns = Object.keys(data[0] || {});
    if (columns.length === 0) {
      return <div className="no-data">No columns found in data</div>;
    }
    
    // Determine column type for formatting
    const getColumnType = (col, value) => {
      const colLower = col.toLowerCase();
      if (colLower.includes('count') || colLower.includes('total') || colLower.includes('rows')) return 'number';
      if (colLower.includes('percent') || colLower.includes('avg') || colLower.includes('score')) return 'percent';
      if (colLower.includes('time') || colLower.includes('duration') || colLower.includes('_ms')) return 'time';
      if (colLower.includes('status')) return 'status';
      if (colLower.includes('name') || colLower.includes('id')) return 'identifier';
      if (typeof value === 'number') return 'number';
      return 'text';
    };
    
    // Format cell value based on type
    const formatCellValue = (col, value) => {
      if (value === null || value === undefined) return '-';
      const type = getColumnType(col, value);
      
      switch (type) {
        case 'number':
          return typeof value === 'number' ? value.toLocaleString() : String(value);
        case 'percent':
          return typeof value === 'number' ? `${(value * 100).toFixed(1)}%` : String(value);
        case 'time':
          return typeof value === 'number' ? `${value.toLocaleString()}ms` : String(value);
        case 'status':
          return String(value);
        default:
          return typeof value === 'object' ? JSON.stringify(value) : String(value);
      }
    };
    
    // Get status badge class
    const getStatusClass = (value) => {
      const v = String(value).toLowerCase();
      if (v.includes('complete') || v.includes('success') || v.includes('healthy') || v.includes('online')) return 'status-success';
      if (v.includes('running') || v.includes('pending') || v.includes('progress')) return 'status-warning';
      if (v.includes('fail') || v.includes('error') || v.includes('unhealthy') || v.includes('offline')) return 'status-error';
      return 'status-neutral';
    };
    
    return (
      <table className="nlq-results-table">
        <thead>
          <tr>
            <th>#</th>
            {columns.map(col => (
              <th key={col}>
                {col.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.map((row, i) => (
            <tr key={i} style={{ background: i % 2 === 0 ? '#ffffff' : '#f8fafc' }}>
              <td style={{ color: '#1a2a3a', padding: '0.45rem 0.75rem' }}>{i + 1}</td>
              {columns.map(col => {
                const type = getColumnType(col, row[col]);
                const value = formatCellValue(col, row[col]);
                
                return (
                  <td key={col} style={{ color: '#1a2a3a', padding: '0.45rem 0.75rem' }}>
                    {type === 'status' ? (
                      <span className={`status-badge ${getStatusClass(row[col])}`}>
                        {value}
                      </span>
                    ) : type === 'identifier' ? (
                      <span className="identifier-value">{value}</span>
                    ) : type === 'number' || type === 'percent' || type === 'time' ? (
                      <span className="numeric-value">{value}</span>
                    ) : (
                      value
                    )}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    );
  };

  return (
    <div className="enterprise-analytics-hub">
      {/* Compact Header with Inline Tabs */}
      <header className="hub-header-compact">
        <div className="header-left">
          <h1>Analytics Hub</h1>
          <nav className="hub-tabs-inline">
            <button className={`tab-inline ${activeTab === 'query-builder' ? 'active' : ''}`} onClick={() => setActiveTab('query-builder')}>Query Builder</button>
            <button className={`tab-inline ${activeTab === 'natural-language' ? 'active' : ''}`} onClick={() => setActiveTab('natural-language')}>Natural Language</button>
            <button className={`tab-inline ${activeTab === 'quality-reports' ? 'active' : ''}`} onClick={() => setActiveTab('quality-reports')}>Quality Reports</button>
            <button className={`tab-inline ${activeTab === 'saved-queries' ? 'active' : ''}`} onClick={() => setActiveTab('saved-queries')}>Saved Queries</button>
            <button className={`tab-inline ${activeTab === 'spreadsheets' ? 'active' : ''}`} onClick={() => setActiveTab('spreadsheets')}>Spreadsheets</button>
          </nav>
        </div>
        <div className="header-right">
          <div className="connection-status-mini">
            {Object.entries(dbStatus).map(([db, connected]) => (
              <span key={db} className={`status-dot ${connected ? 'online' : 'offline'}`} title={`${DATA_SOURCE_CONFIG[db]?.name}: ${connected ? 'Connected' : 'Disconnected'}`}>
                {DATA_SOURCE_CONFIG[db]?.icon}
              </span>
            ))}
          </div>
          <button
            className="tab-inline"
            onClick={() => saveToReportHub({
              report_type: 'analytics',
              title: `Analytics: ${dataSource} — ${new Date().toLocaleString()}`,
              source_page: 'analytics',
              status: 'info',
              summary: { rows_returned: queryResults?.length ?? 0, data_source: dataSource, tab: activeTab },
              result: { query: queryText, results: Array.isArray(queryResults) ? queryResults.slice(0, 50) : [] },
              tags: ['analytics', dataSource],
            })}
            disabled={rhSaving || !queryResults?.length}
            title="Save to Reporting Hub"
          >
            {rhSaved ? <><i className="fas fa-check" /> Saved</> : rhSaving ? <i className="fas fa-spinner fa-spin" /> : <><i className="fas fa-clipboard-list" /> Save Report</>}
          </button>
          <Link to="/reporting-hub" className="tab-inline" title="Reporting Hub">
            <i className="fas fa-clipboard-list" /> Reports
          </Link>
        </div>
      </header>

      {error && (
        <div className="error-banner">
          <span className="error-icon">!</span>
          <span>{error}</span>
          <button onClick={() => setError(null)} className="dismiss-btn">X</button>
        </div>
      )}

      {/* REDESIGNED QUERY BUILDER PAGE */}
      {activeTab === 'query-builder' && (
        <div className="query-builder-page">
          {/* Step 1: Data Source Bar */}
          <div className="qb-source-bar">
            <span className="qb-step-label">1. SELECT SOURCE</span>
            <div className="qb-source-buttons">
              {Object.entries(DATA_SOURCE_CONFIG).filter(([k]) => ['postgres', 'neo4j', 'graphql', 'opensearch'].includes(k)).map(([key, config]) => (
                <button
                  key={key}
                  className={`qb-source-btn ${dataSource === key ? 'active' : ''}`}
                  onClick={() => {
                    setDataSource(key);
                    const entities = QUERY_BUILDER_CONFIG[key]?.entities || Object.keys(QUERY_BUILDER_CONFIG[key]?.fields || {});
                    if (entities.length > 0) {
                      setSelectedEntity(entities[0]);
                      const fields = QUERY_BUILDER_CONFIG[key]?.fields?.[entities[0]] || [];
                      setSelectedFields(fields.slice(0, 4));
                    }
                  }}
                  style={{ '--ds-color': config.color }}
                >
                  <span className="source-icon">{config.icon}</span>
                  <span className="source-name">{config.name}</span>
                  {dbStatus[key] !== undefined && (
                    <span className={`source-status ${dbStatus[key] ? 'online' : 'offline'}`} />
                  )}
                </button>
              ))}
            </div>
          </div>

          {/* Main Two-Column Layout */}
          <div className="qb-main-area">
            {/* Left: Query Builder */}
            <div className="qb-config-panel">
              <div className="qb-panel-header">
                <h3>2. BUILD QUERY</h3>
                <div className="qb-mode-switch">
                  <button className={`mode-btn ${visualBuilderMode ? 'active' : ''}`} onClick={() => setVisualBuilderMode(true)}>Visual</button>
                  <button className={`mode-btn ${!visualBuilderMode ? 'active' : ''}`} onClick={() => setVisualBuilderMode(false)}>Code</button>
                </div>
              </div>

              {visualBuilderMode ? (
                <div className="qb-visual-builder">
                  <div className="qb-section">
                    <label className="qb-label">FROM</label>
                    <select value={selectedEntity} onChange={(e) => {
                      setSelectedEntity(e.target.value);
                      const fields = QUERY_BUILDER_CONFIG[dataSource]?.fields?.[e.target.value] || [];
                      setSelectedFields(fields.slice(0, 4));
                    }} className="qb-select">
                      {(QUERY_BUILDER_CONFIG[dataSource]?.entities || Object.keys(QUERY_BUILDER_CONFIG[dataSource]?.fields || {})).map(entity => (
                        <option key={entity} value={entity}>{entity}</option>
                      ))}
                    </select>
                  </div>

                  <div className="qb-section">
                    <label className="qb-label">SELECT</label>
                    <div className="qb-field-grid">
                      {(QUERY_BUILDER_CONFIG[dataSource]?.fields?.[selectedEntity] || []).map(field => (
                        <label key={field} className="qb-field-item">
                          <input type="checkbox" checked={selectedFields.includes(field)} onChange={(e) => {
                            if (e.target.checked) setSelectedFields(prev => [...prev, field]);
                            else setSelectedFields(prev => prev.filter(f => f !== field));
                          }} />
                          <span>{field}</span>
                        </label>
                      ))}
                    </div>
                  </div>

                  <div className="qb-section">
                    <div className="qb-section-header">
                      <label className="qb-label">WHERE</label>
                      <div className="qb-condition-btns">
                        <button className={`cond-btn ${queryCondition === 'AND' ? 'active' : ''}`} onClick={() => setQueryCondition('AND')}>AND</button>
                        <button className={`cond-btn ${queryCondition === 'OR' ? 'active' : ''}`} onClick={() => setQueryCondition('OR')}>OR</button>
                      </div>
                    </div>
                    <div className="qb-filters">
                      {queryRules.map((rule) => (
                        <div key={rule.id} className="qb-filter-row">
                          <select value={rule.field} onChange={(e) => updateQueryRule(rule.id, { field: e.target.value })} className="qb-filter-field">
                            {(QUERY_BUILDER_CONFIG[dataSource]?.fields?.[selectedEntity] || []).map(f => <option key={f} value={f}>{f}</option>)}
                          </select>
                          <select value={rule.operator} onChange={(e) => updateQueryRule(rule.id, { operator: e.target.value })} className="qb-filter-op">
                            {(QUERY_BUILDER_CONFIG[dataSource]?.operators || ['=', '!=', '>', '<', 'LIKE']).map(op => <option key={op} value={op}>{op}</option>)}
                          </select>
                          <input type="text" value={rule.value} onChange={(e) => updateQueryRule(rule.id, { value: e.target.value })} placeholder="value" className="qb-filter-value" />
                          <button className="qb-filter-remove" onClick={() => removeQueryRule(rule.id)}>×</button>
                        </div>
                      ))}
                      <button className="qb-add-filter" onClick={addQueryRule}>+ Add Filter</button>
                    </div>
                  </div>

                  <div className="qb-section qb-options">
                    <div className="qb-option-group">
                      <label>ORDER BY</label>
                      <select value={queryOrderBy} onChange={(e) => setQueryOrderBy(e.target.value)} className="qb-select-sm">
                        {(QUERY_BUILDER_CONFIG[dataSource]?.fields?.[selectedEntity] || ['id']).map(f => <option key={f} value={f}>{f}</option>)}
                      </select>
                      <select value={queryOrderDir} onChange={(e) => setQueryOrderDir(e.target.value)} className="qb-select-sm">
                        <option value="DESC">DESC</option>
                        <option value="ASC">ASC</option>
                      </select>
                    </div>
                    <div className="qb-option-group">
                      <label>LIMIT</label>
                      <input type="number" value={queryLimit} onChange={(e) => setQueryLimit(parseInt(e.target.value) || 100)} min="1" max="1000" className="qb-input-sm" />
                    </div>
                  </div>

                  <button className="qb-generate-btn" onClick={() => generateQueryFromBuilder()}>Generate Query</button>
                </div>
              ) : (
                <div className="qb-code-editor">
                  <div className="qb-editor-hints">
                    <span className="hint-label">{DATA_SOURCE_CONFIG[dataSource]?.name}:</span>
                    <span className="hint-text">
                      {dataSource === 'postgres' && 'SELECT cols FROM table WHERE ...'}
                      {dataSource === 'neo4j' && 'MATCH (n)-[r]->(m) RETURN n, m'}
                      {dataSource === 'graphql' && '{ entity { field1 field2 } }'}
                      {dataSource === 'opensearch' && '{"query": {"match": {...}}}'}
                    </span>
                    {dataSource === 'postgres' && (
                      <span className="hint-security">🔒 Read-only: Only SELECT queries allowed</span>
                    )}
                  </div>
                  <textarea value={queryText} onChange={e => setQueryText(e.target.value)} placeholder={
                    dataSource === 'graphql' ? '{ workflows { id name status } }' :
                    dataSource === 'neo4j' ? 'MATCH (n) RETURN n LIMIT 25' :
                    dataSource === 'postgres' ? 'SELECT * FROM workflows LIMIT 25' :
                    '{"query": {"match_all": {}}}'
                  } className="qb-textarea" spellCheck="false" />
                </div>
              )}

              {visualBuilderMode && queryText && (
                <div className="qb-query-preview">
                  <label className="qb-label">Generated Query</label>
                  <pre className="qb-preview-code">{queryText}</pre>
                </div>
              )}
            </div>

            {/* Right: Results */}
            <div className="qb-results-panel">
              <div className="qb-panel-header">
                <h3>3. RESULTS</h3>
                <div className="qb-action-btns">
                  <button onClick={executeQuery} disabled={loading || (!queryText && !visualBuilderMode)} className="qb-execute-btn">
                    {loading ? 'Running...' : 'Execute'}
                  </button>
                  <button onClick={handleSaveQuery} disabled={!queryText} className="qb-save-btn">Save</button>
                </div>
              </div>

              <div className="qb-results-area">
                {!queryResults && !loading && (
                  <div className="qb-empty-state">
                    <div className="empty-icon">Q</div>
                    <h4>Ready to Query</h4>
                    <p>Build your query and click Execute</p>
                    <div className="qb-quick-examples">
                      <button onClick={() => { setDataSource('postgres'); setQueryText('SELECT status, COUNT(*) as count FROM workflows GROUP BY status'); }}>SQL Example</button>
                      <button onClick={() => { setDataSource('graphql'); setQueryText('{ workflows { id name status } }'); }}>GraphQL Example</button>
                    </div>
                  </div>
                )}

                {loading && (
                  <div className="qb-loading">
                    <div className="loading-spinner"></div>
                    <p>Executing...</p>
                  </div>
                )}

                {queryResults && !loading && (
                  <div className="qb-results-content">
                    <div className="qb-results-toolbar">
                      <span className="result-count">{Array.isArray(queryResults) ? queryResults.length : Object.keys(queryResults).length} records</span>
                      <button
                        className="qb-export-btn"
                        title="Export results as CSV"
                        onClick={() => {
                          const rows = Array.isArray(queryResults) ? queryResults : [queryResults];
                          if (!rows.length) return;
                          const headers = Object.keys(rows[0]);
                          const escape = v => {
                            if (v == null) return '';
                            const s = String(v);
                            return s.includes(',') || s.includes('"') || s.includes('\n')
                              ? `"${s.replace(/"/g, '""')}"`
                              : s;
                          };
                          const csv = [headers.join(','), ...rows.map(r => headers.map(h => escape(r[h])).join(','))].join('\n');
                          const blob = new Blob([csv], { type: 'text/csv' });
                          const url = URL.createObjectURL(blob);
                          const a = document.createElement('a');
                          a.href = url;
                          a.download = `query_results_${new Date().toISOString().slice(0,10)}.csv`;
                          a.click();
                          URL.revokeObjectURL(url);
                        }}
                      >
                        <i className="fas fa-download" />&nbsp;CSV
                      </button>
                      <select value={chartType} onChange={e => setChartType(e.target.value)} className="qb-select-sm">
                        {CHART_TYPES.map(ct => <option key={ct.id} value={ct.id}>{ct.name}</option>)}
                      </select>
                      {chartType !== 'table' && Array.isArray(queryResults) && queryResults.length > 0 && (() => {
                        const cols = Object.keys(queryResults[0] || {});
                        if (cols.length < 2) return null;
                        return (
                          <>
                            <select value={groupByField || cols[0]} onChange={e => setGroupByField(e.target.value)} className="qb-select-sm" title="X-Axis / Group By">
                              {cols.map(c => <option key={c} value={c}>{c}</option>)}
                            </select>
                            <select value={valueField || cols[1] || cols[0]} onChange={e => setValueField(e.target.value)} className="qb-select-sm" title="Y-Axis / Value">
                              {cols.map(c => <option key={c} value={c}>{c}</option>)}
                            </select>
                          </>
                        );
                      })()}
                    </div>
                    <div className="qb-results-display">
                      {chartType === 'table' ? renderDataTable() : generateChartOption ? (
                        <ReactECharts option={generateChartOption} style={{ height: '100%', minHeight: '300px' }} />
                      ) : renderDataTable()}
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Other Tabs - Keep old hub-main structure */}
      {activeTab !== 'query-builder' && activeTab !== 'hybrid-search' && (
        <div className="hub-main">
          <aside className="datasource-sidebar">
            <h3>Data Sources</h3>
            <div className="datasource-list">
              {Object.entries(DATA_SOURCE_CONFIG).map(([key, config]) => (
                <button key={key} className={`datasource-btn ${dataSource === key ? 'active' : ''}`} onClick={() => setDataSource(key)} style={{ '--ds-color': config.color }}>
                  <span className="ds-icon">{config.icon}</span>
                  <span className="ds-name">{config.name}</span>
                  {dbStatus[key] !== undefined && <span className={`ds-status ${dbStatus[key] ? 'online' : 'offline'}`} />}
                </button>
              ))}
            </div>

            {/* Chart Config for visualization tabs */}
            {(activeTab === 'natural-language' || activeTab === 'file-analysis') && (
              <div className="chart-config">
                <h3>Visualization</h3>
                <div className="config-group">
                  <label>Chart Type</label>
                  <select value={chartType} onChange={e => setChartType(e.target.value)} className="config-select">
                    {CHART_TYPES.map(ct => <option key={ct.id} value={ct.id}>{ct.name}</option>)}
                  </select>
                </div>
                <div className="config-group">
                  <label>Aggregation</label>
                  <select value={aggregation} onChange={e => setAggregation(e.target.value)} className="config-select">
                    {AGGREGATIONS.map(a => <option key={a.id} value={a.id}>{a.name}</option>)}
                  </select>
                </div>
              </div>
            )}
          </aside>

          <main className="hub-content">
          {activeTab === 'natural-language' && (
            <div className="nlq-panel">
              <div className="nlq-header">
                <h2>Natural Language Queries</h2>
                <p>Ask questions in plain English - powered by Ollama LLM</p>
                <div className="nlq-datasource-badge" style={{ '--ds-color': DATA_SOURCE_CONFIG[dataSource]?.color }}>
                  <span className="ds-icon">{DATA_SOURCE_CONFIG[dataSource]?.icon}</span>
                  <span>Targeting: {DATA_SOURCE_CONFIG[dataSource]?.name}</span>
                  <span className={`ds-status ${dbStatus[dataSource] ? 'online' : 'offline'}`} />
                </div>
              </div>
              
              {/* Example queries based on selected datasource */}
              <div className="nlq-examples">
                <h4>Try these examples for {DATA_SOURCE_CONFIG[dataSource]?.name}:</h4>
                <div className="example-chips">
                  {dataSource === 'graphql' && (
                    <>
                      <button className="chip" onClick={() => setNlQuery('Show me all workflows with their status')}>Show all workflows</button>
                      <button className="chip" onClick={() => setNlQuery('List the 10 most recent data migrations')}>Recent migrations</button>
                      <button className="chip" onClick={() => setNlQuery('Count workflows by source type')}>Count by source</button>
                    </>
                  )}
                  {dataSource === 'neo4j' && (
                    <>
                      <button className="chip" onClick={() => setNlQuery('Find all data lineage paths between sources and targets')}>Data lineage paths</button>
                      <button className="chip" onClick={() => setNlQuery('Show nodes with the most connections')}>Most connected nodes</button>
                      <button className="chip" onClick={() => setNlQuery('Find orphan nodes without relationships')}>Orphan nodes</button>
                    </>
                  )}
                  {dataSource === 'postgres' && (
                    <>
                      <button className="chip" onClick={() => setNlQuery('Show workflow counts grouped by status')}>Workflow stats</button>
                      <button className="chip" onClick={() => setNlQuery('Find average processing time by source type')}>Processing times</button>
                      <button className="chip" onClick={() => setNlQuery('List tables with row counts')}>Table sizes</button>
                    </>
                  )}
                  {dataSource === 'opensearch' && (
                    <>
                      <button className="chip" onClick={() => setNlQuery('Search for error logs in the last hour')}>Recent errors</button>
                      <button className="chip" onClick={() => setNlQuery('Find documents matching workflow failures')}>Failed workflows</button>
                      <button className="chip" onClick={() => setNlQuery('Aggregate logs by severity level')}>Log severity stats</button>
                    </>
                  )}
                  {dataSource === 'soda' && (
                    <>
                      <button className="chip" onClick={() => setNlQuery('Check data quality for workflows table')}>Workflow quality</button>
                      <button className="chip" onClick={() => setNlQuery('Validate freshness of upload_metrics data')}>Data freshness</button>
                      <button className="chip" onClick={() => setNlQuery('Count missing values in the status column')}>Missing values check</button>
                    </>
                  )}
                  {dataSource === 'ollama' && (
                    <>
                      <button className="chip" onClick={() => setNlQuery('Analyze the workflow processing trends')}>Analyze trends</button>
                      <button className="chip" onClick={() => setNlQuery('What insights can you provide about data migration quality?')}>Migration insights</button>
                      <button className="chip" onClick={() => setNlQuery('Summarize the system health status')}>Health summary</button>
                    </>
                  )}
                </div>
              </div>

              <div className="nlq-input-section">
                <textarea
                  value={nlQuery}
                  onChange={e => setNlQuery(e.target.value)}
                  placeholder={`Ask a question about your ${DATA_SOURCE_CONFIG[dataSource]?.name} data...\n\nExample: ${
                    dataSource === 'graphql' ? 'Show me all failed workflows from the last week' : 
                    dataSource === 'neo4j' ? 'Find the shortest path between two data sources' : 
                    dataSource === 'postgres' ? 'Count records by status grouped by month' : 
                    dataSource === 'soda' ? 'Check data quality for workflows table' :
                    dataSource === 'ollama' ? 'Analyze the workflow processing trends' :
                    'Search for errors containing timeout'}`}
                  className="nlq-textarea"
                />
                <div className="nlq-actions">
                  <button onClick={executeNaturalLanguageQuery} disabled={loading || !nlQuery.trim()} className="btn btn-primary">
                    {loading ? 'Processing...' : `Generate ${DATA_SOURCE_CONFIG[dataSource]?.queryType || 'Query'}`}
                  </button>
                  <button onClick={() => setNlQuery('')} className="btn btn-secondary" disabled={!nlQuery}>Clear</button>
                </div>
              </div>
              
              {queryText && (
                <div className="generated-query">
                  <div className="generated-header">
                    <h4>Generated {DATA_SOURCE_CONFIG[dataSource]?.queryType || 'Query'}{nlQueryMetadata?.query_type ? ` (${nlQueryMetadata.query_type})` : ''}</h4>
                    <button className="btn btn-sm" onClick={() => { setActiveTab('query-builder'); }}>Edit in Query Builder</button>
                  </div>
                  <pre>{queryText}</pre>
                </div>
              )}
              {nlSuggestions.length > 0 && (
                <div className="nl-suggestions">
                  <h4>Related Suggestions</h4>
                  <ul>
                    {nlSuggestions.map((s, i) => (
                      <li key={i} onClick={() => setNlQuery(s)} className="suggestion-item">{s}</li>
                    ))}
                  </ul>
                </div>
              )}
              {queryResults && (
                <div className="nlq-results-panel">
                  <div className="nlq-results-header">
                    <h3>
                      <i className="fas fa-table" style={{ marginRight: '0.5rem' }} />
                      Results from {DATA_SOURCE_CONFIG[dataSource]?.name}
                    </h3>
                    <div className="nlq-results-meta">
                      <span className="result-count">
                        <i className="fas fa-list" style={{ marginRight: '0.25rem' }} />
                        {Array.isArray(queryResults) ? queryResults.length : Object.keys(queryResults).length} records
                      </span>
                      {nlQueryMetadata?.execution_time_ms && (
                        <span className="result-time">
                          <i className="fas fa-clock" style={{ marginRight: '0.25rem' }} />
                          {nlQueryMetadata.execution_time_ms}ms
                        </span>
                      )}
                      {nlQueryMetadata?.llm_powered && (
                        <span className="llm-badge">
                          <i className="fas fa-brain" style={{ marginRight: '0.25rem' }} />
                          LLM Generated
                        </span>
                      )}
                    </div>
                  </div>
                  <div className="nlq-results-table-wrapper">
                    {renderEnhancedDataTable()}
                    {/* Debug: Show raw data structure */}
                    {import.meta.env.DEV && queryResults && (
                      <details style={{ marginTop: '1rem', padding: '0.5rem', background: '#f5f5f5', borderRadius: '4px' }}>
                        <summary style={{ cursor: 'pointer', color: '#666' }}>Debug: Raw Data ({Array.isArray(queryResults) ? queryResults.length : 'not array'} items)</summary>
                        <pre style={{ fontSize: '0.75rem', overflow: 'auto', maxHeight: '200px', color: '#333' }}>
                          {JSON.stringify(queryResults, null, 2)}
                        </pre>
                      </details>
                    )}
                  </div>
                </div>
              )}
            </div>
          )}

          {activeTab === 'quality-reports' && (
            <div className="quality-panel">
              <div className="quality-header">
                <h2>Data Quality Reports</h2>
                <p>Data Quality Metrics + Profiling / Data Discovery for {DATA_SOURCE_CONFIG[dataSource]?.name}</p>
                <div className="quality-actions">
                  <div className="quality-datasource-selector">
                    <span>Source:</span>
                    <select value={dataSource} onChange={e => setDataSource(e.target.value)} className="form-select-sm">
                      {Object.entries(DATA_SOURCE_CONFIG).map(([key, config]) => (
                        <option key={key} value={key}>{config.name}</option>
                      ))}
                    </select>
                  </div>
                  <button onClick={fetchQualityReports} className="btn btn-secondary">Refresh Reports</button>
                  <button
                    onClick={() => { fetchAvailableTables(); setScanModalError(null); setScanTableInput(''); setShowScanModal(true); }}
                    className="btn btn-primary"
                    disabled={!dbStatus[dataSource]}
                  >
                    Run New Scan
                  </button>
                </div>
              </div>
              
              {/* Quality metrics overview */}
              <div className="quality-overview">
                <div className="overview-cards">
                  <div className="overview-card">
                    <span className="overview-icon" style={{ background: '#10b981' }}>✓</span>
                    <div className="overview-content">
                      <span className="overview-value">{qualityReports.filter(r => (r.overall_score || 0) >= 0.9).length}</span>
                      <span className="overview-label">Healthy Tables</span>
                    </div>
                  </div>
                  <div className="overview-card">
                    <span className="overview-icon" style={{ background: '#f59e0b' }}>!</span>
                    <div className="overview-content">
                      <span className="overview-value">{qualityReports.filter(r => (r.overall_score || 0) >= 0.7 && (r.overall_score || 0) < 0.9).length}</span>
                      <span className="overview-label">Warnings</span>
                    </div>
                  </div>
                  <div className="overview-card">
                    <span className="overview-icon" style={{ background: '#ef4444' }}>✗</span>
                    <div className="overview-content">
                      <span className="overview-value">{qualityReports.filter(r => (r.overall_score || 0) < 0.7).length}</span>
                      <span className="overview-label">Critical Issues</span>
                    </div>
                  </div>
                  <div className="overview-card">
                    <span className="overview-icon" style={{ background: '#3b82f6' }}>{DATA_SOURCE_CONFIG[dataSource]?.icon}</span>
                    <div className="overview-content">
                      <span className="overview-value">{qualityReports.length}</span>
                      <span className="overview-label">Total Reports</span>
                    </div>
                  </div>
                </div>
              </div>

              {qualityReports.length === 0 ? (
                <div className="empty-state">
                  <div className="empty-icon" style={{ '--ds-color': DATA_SOURCE_CONFIG[dataSource]?.color }}>{DATA_SOURCE_CONFIG[dataSource]?.icon}</div>
                  <h3>No Quality Reports for {DATA_SOURCE_CONFIG[dataSource]?.name}</h3>
                  <p>Run a scan to capture metrics (row count, missing/invalid/duplicates, freshness) and profiling (null %, cardinality, frequent values, distribution).</p>
                </div>
              ) : (
                <div className="quality-table-container">
                  <table className="quality-table">
                    <thead>
                      <tr>
                        <th>Table</th>
                        <th>Source</th>
                        <th>Score</th>
                        <th>Row Count</th>
                        <th>Missing Values</th>
                        <th>Invalid Values</th>
                        <th>Duplicate Count</th>
                        <th>Freshness (Last Updated)</th>
                        <th>SLA Violations</th>
                        <th>Issues</th>
                        <th>Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {qualityReports.map((report, i) => (
                        <tr
                          key={i}
                          className={`${selectedReportIndex === i ? 'selected' : ''}`}
                          onClick={() => {
                            setSelectedReportIndex(i);
                            fetchQualityReportDetail(report.scan_id);
                            fetchQualityInsight(report.scan_id);
                          }}
                          style={{ cursor: 'pointer' }}
                        >
                          <td className="table-name-cell">
                            <strong>{report.table_name || report.source || 'Unknown'}</strong>
                          </td>
                          <td>
                            <span className="source-badge-compact" style={{ '--ds-color': DATA_SOURCE_CONFIG[report.source || dataSource]?.color }}>
                              {DATA_SOURCE_CONFIG[report.source || dataSource]?.icon}
                            </span>
                          </td>
                          <td className="metric-cell">
                            {typeof report.overall_score === 'number' ? (
                              <span className="score-badge" style={{
                                background: report.overall_score >= 0.9 ? '#10b981' : report.overall_score >= 0.7 ? '#f59e0b' : '#ef4444',
                                color: '#fff',
                                borderRadius: '4px',
                                padding: '2px 6px',
                                fontSize: '0.8rem',
                                fontWeight: 600
                              }}>
                                {(report.overall_score * 100).toFixed(0)}%
                              </span>
                            ) : '—'}
                          </td>
                          <td className="metric-cell">{typeof report.row_count === 'number' ? report.row_count : '—'}</td>
                          <td className="metric-cell">{typeof report.missing_values === 'number' ? report.missing_values : '—'}</td>
                          <td className="metric-cell">{typeof report.invalid_values === 'number' ? report.invalid_values : '—'}</td>
                          <td className="metric-cell">{typeof report.duplicate_count === 'number' ? report.duplicate_count : '—'}</td>
                          <td className="metric-cell">{report.freshness?.last_updated || '—'}</td>
                          <td className="metric-cell">{report.sla_violations ?? '—'}</td>
                          <td className="issues-cell">
                            {report.issues && report.issues.length > 0 ? (
                              <span className="issue-count" title={report.issues.map(i => i.description).join(', ')}>
                                {report.issues.length}
                              </span>
                            ) : (
                              <span className="no-issues">0</span>
                            )}
                          </td>
                          <td className="actions-cell">
                            <button className="btn-action" onClick={(e) => { e.stopPropagation(); setQueryText(`SELECT * FROM ${report.table_name} LIMIT 100`); setDataSource('postgres'); setActiveTab('query-builder'); }} title="Query Table">
                              <i className="fas fa-search"></i>
                            </button>
                            <button className="btn-action" onClick={(e) => {
                              e.stopPropagation();
                              const sid = report.scan_id;
                              if (!sid) return;
                              const link = document.createElement('a');
                              link.href = `/api/analytics/quality/reports/${encodeURIComponent(sid)}/export?format=csv`;
                              link.download = `quality_report_${report.table_name}_${sid.slice(0,8)}.csv`;
                              link.click();
                            }} title="Export CSV">
                              <i className="fas fa-download"></i>
                            </button>                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>

                  <div className="quality-detail">
                    {qualityReportDetailLoading ? (
                      <div className="empty-state" style={{ marginTop: '1rem' }}>
                        <p>Loading report details…</p>
                      </div>
                    ) : !selectedQualityReport ? (
                      <div className="empty-state" style={{ marginTop: '1rem' }}>
                        <p>Select a table above to view Metrics + Profiling.</p>
                      </div>
                    ) : (
                      <div className="quality-detail-grid">
                        <div className="quality-detail-card">
                          <h3>Data Quality Metrics Report</h3>
                          <div className="detail-kv">
                            <div><span>Row count</span><strong>{selectedQualityReport.row_count ?? '—'}</strong></div>
                            <div><span>Missing values</span><strong>{selectedQualityReport.missing_values ?? '—'}</strong></div>
                            <div><span>Invalid values</span><strong>{selectedQualityReport.invalid_values ?? '—'}</strong></div>
                            <div><span>Duplicate count</span><strong>{selectedQualityReport.duplicate_count ?? '—'}</strong></div>
                            <div><span>Freshness (last updated)</span><strong>{selectedQualityReport.freshness?.last_updated || '—'}</strong></div>
                            <div><span>Delayed arrivals</span><strong>{selectedQualityReport.delayed_arrivals ?? '—'}</strong></div>
                            <div><span>SLA violations</span><strong>{selectedQualityReport.sla_violations ?? '—'}</strong></div>
                          </div>

                          {Array.isArray(selectedQualityReport.distribution_metrics) && selectedQualityReport.distribution_metrics.length > 0 ? (
                            <div style={{ marginTop: '1rem' }}>
                              <h4 style={{ margin: '0 0 0.5rem 0' }}>Distribution Metrics (Numeric Columns)</h4>
                              <div className="profiling-table-wrapper">
                                <table className="quality-table profiling-table">
                                  <thead>
                                    <tr>
                                      <th>Column</th>
                                      <th>Min</th>
                                      <th>Max</th>
                                      <th>Avg</th>
                                      <th>Stddev</th>
                                    </tr>
                                  </thead>
                                  <tbody>
                                    {selectedQualityReport.distribution_metrics.map((m, idx) => (
                                      <tr key={idx}>
                                        <td className="table-name-cell"><strong>{m.column}</strong></td>
                                        <td className="metric-cell">{m.min ?? '—'}</td>
                                        <td className="metric-cell">{m.max ?? '—'}</td>
                                        <td className="metric-cell">{typeof m.avg === 'number' ? m.avg.toFixed(4) : (m.avg ?? '—')}</td>
                                        <td className="metric-cell">{typeof m.stddev === 'number' ? m.stddev.toFixed(4) : (m.stddev ?? '—')}</td>
                                      </tr>
                                    ))}
                                  </tbody>
                                </table>
                              </div>
                            </div>
                          ) : null}
                        </div>

                        <div className="quality-detail-card">
                          <h3>Profiling / Data Discovery Report</h3>
                          {Array.isArray(selectedQualityReport.profiling) && selectedQualityReport.profiling.length > 0 ? (
                            <div className="profiling-table-wrapper">
                              <table className="quality-table profiling-table">
                                <thead>
                                  <tr>
                                    <th>Column</th>
                                    <th>Type</th>
                                    <th>Null %</th>
                                    <th>Cardinality</th>
                                    <th>Frequent values</th>
                                    <th>Distribution shape</th>
                                  </tr>
                                </thead>
                                <tbody>
                                  {selectedQualityReport.profiling.map((c, idx) => (
                                    <tr key={idx}>
                                      <td className="table-name-cell"><strong>{c.column}</strong></td>
                                      <td className="metric-cell">{c.data_type || '—'}</td>
                                      <td className="metric-cell">{typeof c.null_percentage === 'number' ? `${c.null_percentage}%` : '—'}</td>
                                      <td className="metric-cell">{typeof c.cardinality === 'number' ? c.cardinality : '—'}</td>
                                      <td className="metric-cell">
                                        {Array.isArray(c.frequent_values) && c.frequent_values.length > 0
                                          ? c.frequent_values.map(v => `${v.value ?? 'NULL'} (${v.count})`).join(', ')
                                          : '—'}
                                      </td>
                                      <td className="metric-cell">{c.distribution_shape || '—'}</td>
                                    </tr>
                                  ))}
                                </tbody>
                              </table>
                            </div>
                          ) : (
                            <p className="text-muted">No profiling data available for this report.</p>
                          )}
                        </div>

                        {/* AI Insights panel */}
                        <div className="quality-detail-card quality-insight-card">
                          <h3>
                            AI Insights&nbsp;
                            {qualityInsight?.llm_powered
                              ? <span className="badge badge-llm">LLM</span>
                              : <span className="badge badge-auto">Auto</span>}
                          </h3>
                          {qualityInsightLoading ? (
                            <p className="text-muted">Generating insights…</p>
                          ) : qualityInsight ? (
                            <>
                              <p className="insight-text">{qualityInsight.insight}</p>
                              <div className="insight-actions">
                                <button className="btn btn-sm" onClick={() => {
                                  const sid = selectedQualityReport?.scan_id;
                                  if (!sid) return;
                                  const link = document.createElement('a');
                                  link.href = `/api/analytics/quality/reports/${encodeURIComponent(sid)}/export?format=json`;
                                  link.download = `quality_report_${selectedQualityReport?.table_name}_${sid.slice(0,8)}.json`;
                                  link.click();
                                }}>
                                  <i className="fas fa-file-code"></i>&nbsp;Export JSON
                                </button>
                                <button className="btn btn-sm" onClick={() => {
                                  const sid = selectedQualityReport?.scan_id;
                                  if (!sid) return;
                                  const link = document.createElement('a');
                                  link.href = `/api/analytics/quality/reports/${encodeURIComponent(sid)}/export?format=csv`;
                                  link.download = `quality_report_${selectedQualityReport?.table_name}_${sid.slice(0,8)}.csv`;
                                  link.click();
                                }}>
                                  <i className="fas fa-file-csv"></i>&nbsp;Export CSV
                                </button>
                              </div>
                            </>
                          ) : (
                            <p className="text-muted">No insights available.</p>
                          )}
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Scan Modal */}
          {showScanModal && (
            <div className="modal-overlay" onClick={() => setShowScanModal(false)}>
              <div className="modal-content" onClick={e => e.stopPropagation()} style={{ maxWidth: '460px' }}>
                <div className="modal-header">
                  <h3>Run Quality Scan</h3>
                  <button className="modal-close" onClick={() => setShowScanModal(false)}>×</button>
                </div>
                <div className="modal-body">
                  <label style={{ display: 'block', marginBottom: '0.5rem', fontWeight: 600 }}>
                    Table name
                  </label>
                  {availableTables.length > 0 ? (
                    <select
                      className="select-input"
                      value={scanTableInput}
                      onChange={e => setScanTableInput(e.target.value)}
                      style={{ width: '100%', marginBottom: '0.75rem' }}
                    >
                      <option value="">— select a table —</option>
                      {availableTables.map(t => (
                        <option key={t} value={t}>{t}</option>
                      ))}
                    </select>
                  ) : (
                    <input
                      className="query-input"
                      type="text"
                      placeholder="e.g. public.my_table or just my_table"
                      value={scanTableInput}
                      onChange={e => setScanTableInput(e.target.value)}
                      onKeyDown={e => e.key === 'Enter' && runScan()}
                      style={{ width: '100%', marginBottom: '0.75rem' }}
                    />
                  )}
                  {scanModalError && (
                    <p style={{ color: '#ef4444', fontSize: '0.85rem', margin: '0 0 0.5rem 0' }}>{scanModalError}</p>
                  )}
                  <p style={{ color: '#6b7280', fontSize: '0.8rem', margin: 0 }}>
                    If no quality rules are configured, a profiling-only scan will run automatically.
                  </p>
                </div>
                <div className="modal-footer">
                  <button className="btn btn-secondary" onClick={() => setShowScanModal(false)}>Cancel</button>
                  <button
                    className="btn btn-primary"
                    onClick={runScan}
                    disabled={scanModalLoading || !scanTableInput.trim()}
                  >
                    {scanModalLoading ? 'Scanning…' : 'Run Scan'}
                  </button>
                </div>
              </div>
            </div>
          )}

          {activeTab === 'spreadsheets' && (
            <div className="spreadsheet-panel">
              <div className="spreadsheet-header">
                <h2>ECharts Spreadsheet Analytics</h2>
                <p>Visualize spreadsheet data with interactive ECharts</p>
                {spreadsheetConfig.fileName && (
                  <p className="connection-info">Loaded: {spreadsheetConfig.fileName}</p>
                )}
              </div>
              
              {/* Data Source Section */}
              <div className="spreadsheet-sources">
                <div className="source-row">
                  <div className="provider-selection">
                    <button
                      className={`provider-btn ${spreadsheetConfig.provider === 'microsoft' ? 'active' : ''}`}
                      onClick={() => setSpreadsheetConfig(prev => ({ ...prev, provider: 'microsoft' }))}
                    >
                      <span className="provider-icon">MS</span>
                      <span>Microsoft 365</span>
                    </button>
                    <button
                      className={`provider-btn ${spreadsheetConfig.provider === 'google' ? 'active' : ''}`}
                      onClick={() => setSpreadsheetConfig(prev => ({ ...prev, provider: 'google' }))}
                    >
                      <span className="provider-icon">G</span>
                      <span>Google Sheets</span>
                    </button>
                    <button
                      className={`provider-btn demo-btn ${spreadsheetData.length > 0 ? 'active' : ''}`}
                      onClick={loadSampleSpreadsheetData}
                    >
                      <span className="provider-icon">DEMO</span>
                      <span>Load Sample Data</span>
                    </button>
                    <button
                      className={`provider-btn ${spreadsheetConfig.provider === 'local' ? 'active' : ''}`}
                      onClick={() => {
                        setSpreadsheetConfig((prev) => ({ ...prev, provider: 'local' }));
                        spreadsheetFileInputRef.current?.click();
                      }}
                      type="button"
                    >
                      <span className="provider-icon">FILE</span>
                      <span>Import File</span>
                    </button>
                  </div>
                </div>

                <input
                  ref={spreadsheetFileInputRef}
                  type="file"
                  accept={acceptTabular}
                  style={{ display: 'none' }}
                  onChange={onSpreadsheetFileSelected}
                />
                
                {(spreadsheetConfig.provider === 'microsoft' || spreadsheetConfig.provider === 'google') && (
                  <div className="connection-section">
                    <h4>Connect to {spreadsheetConfig.provider === 'microsoft' ? 'Microsoft 365' : 'Google Sheets'}</h4>
                    <p className="connection-info">
                      {spreadsheetConfig.provider === 'microsoft'
                        ? 'Use OAuth 2.0 to connect to Excel Online workbooks'
                        : 'Use Google API credentials to access your sheets'}
                    </p>
                    <button
                      className="btn btn-primary"
                      onClick={() => spreadsheetFileInputRef.current?.click()}
                      type="button"
                    >
                      {spreadsheetConfig.connected ? 'Reconnect' : 'Connect Account'}
                    </button>
                  </div>
                )}
              </div>
              
              {/* Chart Configuration */}
              {spreadsheetData.length > 0 && (
                <div className="spreadsheet-chart-config">
                  <div className="config-section">
                    <h4>Chart Configuration</h4>
                    <div className="config-grid">
                      {Array.isArray(spreadsheetConfig.sheets) && spreadsheetConfig.sheets.length > 1 && (
                        <div className="config-item">
                          <label>Sheet</label>
                          <select
                            value={spreadsheetConfig.selectedSheet || spreadsheetConfig.sheets[0]}
                            onChange={(e) => reloadSelectedSpreadsheetSheet(e.target.value)}
                            className="form-select"
                          >
                            {spreadsheetConfig.sheets.map((s) => (
                              <option key={s} value={s}>{s}</option>
                            ))}
                          </select>
                        </div>
                      )}
                      <div className="config-item">
                        <label>Chart Type</label>
                        <select
                          value={spreadsheetChartType}
                          onChange={(e) => setSpreadsheetChartType(e.target.value)}
                          className="form-select"
                        >
                          <option value="bar">Bar Chart</option>
                          <option value="line">Line Chart</option>
                          <option value="pie">Pie Chart</option>
                          <option value="area">Area Chart</option>
                          <option value="scatter">Scatter Plot</option>
                          <option value="heatmap">Heatmap</option>
                          <option value="table">Data Table</option>
                        </select>
                      </div>
                      <div className="config-item">
                        <label>X-Axis / Category</label>
                        <select
                          value={spreadsheetXAxis}
                          onChange={(e) => setSpreadsheetXAxis(e.target.value)}
                          className="form-select"
                        >
                          {Object.keys(spreadsheetData[0] || {}).map(col => (
                            <option key={col} value={col}>{col}</option>
                          ))}
                        </select>
                      </div>
                      <div className="config-item">
                        <label>Y-Axis / Value</label>
                        <select
                          value={spreadsheetYAxis}
                          onChange={(e) => setSpreadsheetYAxis(e.target.value)}
                          className="form-select"
                        >
                          {Object.keys(spreadsheetData[0] || {}).map(col => (
                            <option key={col} value={col}>{col}</option>
                          ))}
                        </select>
                      </div>
                      <div className="config-item">
                        <label>Aggregation</label>
                        <select
                          value={spreadsheetAggregation}
                          onChange={(e) => setSpreadsheetAggregation(e.target.value)}
                          className="form-select"
                        >
                          <option value="sum">Sum</option>
                          <option value="avg">Average</option>
                          <option value="count">Count</option>
                          <option value="min">Minimum</option>
                          <option value="max">Maximum</option>
                        </select>
                      </div>
                    </div>
                  </div>
                  
                  {/* Chart Display */}
                  <div className="spreadsheet-chart-container">
                    {spreadsheetChartType === 'table' ? (
                      <div className="data-table-container">
                        <table className="data-table">
                          <thead>
                            <tr>
                              {Object.keys(spreadsheetData[0] || {}).map(col => (
                                <th key={col}>{col}</th>
                              ))}
                            </tr>
                          </thead>
                          <tbody>
                            {spreadsheetData.slice(0, 50).map((row, i) => (
                              <tr key={i}>
                                {Object.keys(row).map(col => (
                                  <td key={col}>{typeof row[col] === 'number' ? row[col].toLocaleString() : row[col]}</td>
                                ))}
                              </tr>
                            ))}
                          </tbody>
                        </table>
                        {spreadsheetData.length > 50 && (
                          <div className="table-footer">Showing first 50 of {spreadsheetData.length} rows</div>
                        )}
                      </div>
                    ) : spreadsheetChartOptions ? (
                      <ReactECharts 
                        option={spreadsheetChartOptions} 
                        style={{ height: '450px', width: '100%' }} 
                        opts={{ renderer: 'canvas' }}
                      />
                    ) : (
                      <div className="no-chart">Configure chart settings to visualize data</div>
                    )}
                  </div>
                  
                  {/* Data Summary */}
                  <div className="spreadsheet-summary">
                    <div className="summary-stats">
                      <div className="stat-card">
                        <span className="stat-label">Total Rows</span>
                        <span className="stat-value">{spreadsheetData.length}</span>
                      </div>
                      <div className="stat-card">
                        <span className="stat-label">Columns</span>
                        <span className="stat-value">{Object.keys(spreadsheetData[0] || {}).length}</span>
                      </div>
                      <div className="stat-card">
                        <span className="stat-label">X-Axis Categories</span>
                        <span className="stat-value">{new Set(spreadsheetData.map(d => d?.[spreadsheetXField])).size}</span>
                      </div>
                      <div className="stat-card">
                        <span className="stat-label">Y-Axis Range</span>
                        <span className="stat-value">
                          {Math.min(...spreadsheetData.map(d => parseFloat(d?.[spreadsheetYField]) || 0)).toLocaleString()} - {Math.max(...spreadsheetData.map(d => parseFloat(d?.[spreadsheetYField]) || 0)).toLocaleString()}
                        </span>
                      </div>
                    </div>
                    <div className="summary-actions">
                      <button className="btn btn-sm" onClick={() => {
                        setQueryResults(spreadsheetData);
                        setActiveTab('query-builder');
                      }}>
                        Open in Query Builder
                      </button>
                      <button className="btn btn-sm" onClick={() => {
                        const blob = new Blob([JSON.stringify(spreadsheetData, null, 2)], { type: 'application/json' });
                        const url = URL.createObjectURL(blob);
                        const a = document.createElement('a');
                        a.href = url;
                        a.download = 'spreadsheet_data.json';
                        a.click();
                        URL.revokeObjectURL(url);
                      }}>
                        Export JSON
                      </button>
                      <button className="btn btn-sm btn-danger" onClick={() => {
                        setSpreadsheetData([]);
                        setSpreadsheetXAxis('');
                        setSpreadsheetYAxis('');
                        spreadsheetXlsxBufferRef.current = null;
                        setSpreadsheetConfig((prev) => ({
                          ...prev,
                          provider: 'none',
                          connected: false,
                          fileName: null,
                          sheets: [],
                          selectedSheet: null
                        }));
                      }}>
                        Clear Data
                      </button>
                    </div>
                  </div>
                </div>
              )}
              
              {spreadsheetData.length === 0 && (
                <div className="empty-state">
                  <div className="empty-icon">CHART</div>
                  <h3>No Spreadsheet Data</h3>
                  <p>Connect to a spreadsheet provider or load sample data to visualize with ECharts</p>
                  <button className="btn btn-primary" onClick={loadSampleSpreadsheetData}>
                    Load Sample Data
                  </button>
                </div>
              )}
            </div>
          )}

          {activeTab === 'file-analysis' && (
            <div className="file-panel">
              <div className="file-header">
                <h2>File Content Analysis</h2>
                <p>Upload files and analyze or import into {DATA_SOURCE_CONFIG[dataSource]?.name}</p>
                <div className="file-target-ds">
                  <span>Target Datasource:</span>
                  <div className="ds-badge" style={{ '--ds-color': DATA_SOURCE_CONFIG[dataSource]?.color }}>
                    {DATA_SOURCE_CONFIG[dataSource]?.icon} {DATA_SOURCE_CONFIG[dataSource]?.name}
                  </div>
                </div>
              </div>
              
              <div className="upload-section">
                <input
                  type="file"
                  ref={fileInputRef}
                  onChange={handleFileUpload}
                  accept={acceptAnalytics}
                  multiple
                  style={{ display: 'none' }}
                />
                <div className="upload-dropzone" onClick={() => fileInputRef.current?.click()}>
                  <div className="dropzone-content">
                    <span className="dropzone-icon">FILE</span>
                    <span className="dropzone-text">Click to upload or drag files here</span>
                    <span className="dropzone-formats">Supported: {acceptAnalytics.replace(/,/g, ', ')}</span>
                  </div>
                </div>
              </div>
              
              {/* Import options */}
              <div className="import-options">
                <h4>Import Actions</h4>
                <div className="import-actions-grid">
                  <div className="import-action-card">
                    <span className="action-icon" style={{ background: '#3b82f6' }}>SQL</span>
                    <div className="action-content">
                      <strong>Import to PostgreSQL</strong>
                      <span>Create table and insert rows</span>
                    </div>
                    <button className="btn btn-sm" disabled={uploadedFiles.length === 0 || !dbStatus.postgres}>
                      Import
                    </button>
                  </div>
                  <div className="import-action-card">
                    <span className="action-icon" style={{ background: '#008CC1' }}>N4J</span>
                    <div className="action-content">
                      <strong>Import to Neo4j</strong>
                      <span>Create nodes from records</span>
                    </div>
                    <button className="btn btn-sm" disabled={uploadedFiles.length === 0 || !dbStatus.neo4j}>
                      Import
                    </button>
                  </div>
                  <div className="import-action-card">
                    <span className="action-icon" style={{ background: '#E07426' }}>OS</span>
                    <div className="action-content">
                      <strong>Index in OpenSearch</strong>
                      <span>Create searchable index</span>
                    </div>
                    <button className="btn btn-sm" disabled={uploadedFiles.length === 0 || !dbStatus.opensearch}>
                      Index
                    </button>
                  </div>
                  <div className="import-action-card">
                    <span className="action-icon" style={{ background: '#10b981' }}>CHART</span>
                    <div className="action-content">
                      <strong>Visualize with ECharts</strong>
                      <span>Open in Query Builder</span>
                    </div>
                    <button 
                      className="btn btn-sm" 
                      disabled={uploadedFiles.length === 0 || !uploadedFiles.some(f => Array.isArray(f.data))}
                      onClick={() => {
                        const fileWithData = uploadedFiles.find(f => Array.isArray(f.data));
                        if (fileWithData) {
                          setQueryResults(fileWithData.data);
                          setActiveTab('query-builder');
                        }
                      }}
                    >
                      Visualize
                    </button>
                  </div>
                </div>
              </div>

              {uploadedFiles.length > 0 && (
                <div className="uploaded-files">
                  <h4>Uploaded Files ({uploadedFiles.length})</h4>
                  {uploadedFiles.map((file, i) => (
                    <div key={i} className="file-card">
                      <div className="file-icon">
                        {file.name.endsWith('.json') ? 'JSON' : file.name.endsWith('.csv') ? 'CSV' : file.name.endsWith('.xml') ? 'XML' : 'FILE'}
                      </div>
                      <div className="file-info">
                        <span className="file-name">{file.name}</span>
                        <span className="file-meta">
                          {(file.size / 1024).toFixed(2)} KB • 
                          {Array.isArray(file.data) ? `${file.data.length} records` : 'Raw content'} • 
                          {new Date(file.uploadedAt).toLocaleTimeString()}
                        </span>
                      </div>
                      <div className="file-actions">
                        <button
                          className="btn btn-sm btn-primary"
                          onClick={() => {
                            if (Array.isArray(file.data)) {
                              setQueryResults(file.data);
                              setActiveTab('query-builder');
                            } else {
                              alert('File preview:\n\n' + (typeof file.data === 'string' ? file.data.slice(0, 500) : JSON.stringify(file.data, null, 2).slice(0, 500)) + '...');
                            }
                          }}
                        >
                          {Array.isArray(file.data) ? 'Analyze' : 'Preview'}
                        </button>
                        <button
                          className="btn btn-sm"
                          onClick={() => {
                            if (Array.isArray(file.data)) {
                              setSpreadsheetData(file.data);
                              setActiveTab('spreadsheets');
                            }
                          }}
                          disabled={!Array.isArray(file.data)}
                        >
                          Chart
                        </button>
                        <button
                          className="btn btn-sm btn-danger"
                          onClick={() => setUploadedFiles(prev => prev.filter((_, j) => j !== i))}
                        >
                          Remove
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
              
              {uploadedFiles.length === 0 && (
                <div className="empty-state-inline">
                  <p>Upload files to analyze, visualize, or import into your data sources</p>
                </div>
              )}
            </div>
          )}

          {activeTab === 'saved-queries' && (
            <div className="saved-queries-panel">
              <div className="saved-header">
                <h2>Saved Queries</h2>
                <div className="saved-actions">
                  <input
                    type="search"
                    className="form-input-sm"
                    placeholder="Search queries…"
                    value={savedQuerySearch}
                    onChange={e => setSavedQuerySearch(e.target.value)}
                    style={{ minWidth: '180px' }}
                  />
                  <div className="filter-by-ds">
                    <label>Filter by source:</label>
                    <select className="form-select-sm" value={filterSource} onChange={e => setFilterSource(e.target.value)}>
                      <option value="all">All Sources</option>
                      {Object.entries(DATA_SOURCE_CONFIG).map(([key, config]) => (
                        <option key={key} value={key}>{config.name}</option>
                      ))}
                    </select>
                  </div>
                  <button onClick={() => loadQueries(100, 0)} className="btn btn-secondary">Refresh</button>
                </div>
              </div>
              
              {/* Quick query templates */}
              <div className="query-templates">
                <h4>Quick Templates for {DATA_SOURCE_CONFIG[dataSource]?.name}</h4>
                <div className="template-grid">
                  {dataSource === 'graphql' && (
                    <>
                      <div className="template-card" onClick={() => { setQueryText('{\n  workflows(limit: 20) {\n    id\n    name\n    status\n    created_at\n  }\n}'); setActiveTab('query-builder'); }}>
                        <span className="template-icon">LIST</span>
                        <span className="template-name">List Workflows</span>
                      </div>
                      <div className="template-card" onClick={() => { setQueryText('{\n  __schema {\n    types {\n      name\n      fields { name }\n    }\n  }\n}'); setActiveTab('query-builder'); }}>
                        <span className="template-icon">SCHEMA</span>
                        <span className="template-name">Introspect Schema</span>
                      </div>
                    </>
                  )}
                  {dataSource === 'neo4j' && (
                    <>
                      <div className="template-card" onClick={() => { setQueryText('MATCH (n)\nRETURN labels(n) as label, COUNT(*) as count\nORDER BY count DESC'); setActiveTab('query-builder'); }}>
                        <span className="template-icon">STATS</span>
                        <span className="template-name">Node Statistics</span>
                      </div>
                      <div className="template-card" onClick={() => { setQueryText('MATCH (n)-[r]->(m)\nRETURN n, type(r), m\nLIMIT 100'); setActiveTab('query-builder'); }}>
                        <span className="template-icon">GRAPH</span>
                        <span className="template-name">View Relationships</span>
                      </div>
                    </>
                  )}
                  {dataSource === 'postgres' && (
                    <>
                      <div className="template-card" onClick={() => { setQueryText("SELECT table_name, \n       (SELECT COUNT(*) FROM information_schema.columns WHERE table_name = t.table_name) as column_count\nFROM information_schema.tables t\nWHERE table_schema = 'public'\nORDER BY table_name"); setActiveTab('query-builder'); }}>
                        <span className="template-icon">TABLES</span>
                        <span className="template-name">List Tables</span>
                      </div>
                      <div className="template-card" onClick={() => { setQueryText('SELECT status, COUNT(*) as count\nFROM workflows\nGROUP BY status\nORDER BY count DESC'); setActiveTab('query-builder'); }}>
                        <span className="template-icon">AGG</span>
                        <span className="template-name">Status Summary</span>
                      </div>
                    </>
                  )}
                  {dataSource === 'opensearch' && (
                    <>
                      <div className="template-card" onClick={() => { setQueryText('{\n  "query": { "match_all": {} },\n  "size": 20\n}'); setActiveTab('query-builder'); }}>
                        <span className="template-icon">ALL</span>
                        <span className="template-name">Match All</span>
                      </div>
                      <div className="template-card" onClick={() => { setQueryText('{\n  "query": {\n    "bool": {\n      "must": [{ "match": { "status": "error" } }]\n    }\n  },\n  "aggs": {\n    "by_source": { "terms": { "field": "source.keyword" } }\n  }\n}'); setActiveTab('query-builder'); }}>
                        <span className="template-icon">ERR</span>
                        <span className="template-name">Error Analysis</span>
                      </div>
                    </>
                  )}
                </div>
              </div>

              {filteredSavedQueries.length === 0 ? (
                <div className="empty-state">
                  <div className="empty-icon" style={{ '--ds-color': DATA_SOURCE_CONFIG[dataSource]?.color }}>{DATA_SOURCE_CONFIG[dataSource]?.icon}</div>
                  <h3>No Saved Queries</h3>
                  <p>Save queries from the Query Builder to access them here</p>
                  <button className="btn btn-primary" onClick={() => setActiveTab('query-builder')}>Go to Query Builder</button>
                </div>
              ) : (
                <div className="queries-list">
                  {filteredSavedQueries.map((q, i) => (
                    <div key={i} className="query-card">
                      <div className="query-ds-badge" style={{ '--ds-color': DATA_SOURCE_CONFIG[q.datasource || 'graphql']?.color }}>
                        {DATA_SOURCE_CONFIG[q.datasource || 'graphql']?.icon}
                      </div>
                      <div className="query-info">
                        <span className="query-name">{q.name}</span>
                        <span className="query-desc">{q.description}</span>
                        <span className="query-meta">
                          {DATA_SOURCE_CONFIG[q.datasource || 'graphql']?.name} • 
                          {q.created_at ? new Date(q.created_at).toLocaleDateString() : 'Saved'}
                        </span>
                      </div>
                      <div className="query-actions">
                        <button
                          className="btn btn-sm btn-primary"
                          onClick={() => {
                            setQueryText(q.query);
                            setDataSource(q.datasource || 'graphql');
                            setActiveTab('query-builder');
                          }}
                        >
                          Load
                        </button>
                        <button
                          className="btn btn-sm"
                          onClick={async () => {
                            const qText = q.query;
                            const qSource = q.datasource || 'graphql';
                            setQueryText(qText);
                            setDataSource(qSource);
                            await executeQuery(qText, qSource);
                            setActiveTab('query-builder');
                          }}
                          disabled={loading}
                        >
                          Run
                        </button>
                        <button
                          className="btn btn-sm btn-danger"
                          onClick={() => {
                            if (confirm(`Delete query "${q.name}"?`)) {
                              deletePersistedQuery(q.id).catch(err => setError(err.message || 'Failed to delete query'));
                            }
                          }}
                        >
                          Delete
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </main>
      </div>
      )}

      {saveModalOpen && (
        <div className="modal-overlay" onClick={() => setSaveModalOpen(false)}>
          <div className="modal-content" onClick={e => e.stopPropagation()} style={{ maxWidth: '420px' }}>
            <div className="modal-header">
              <h3>Save Query</h3>
              <button className="modal-close" onClick={() => setSaveModalOpen(false)}>×</button>
            </div>
            <div className="modal-body">
              <label style={{ display: 'block', marginBottom: '0.5rem', fontWeight: 600 }}>Name *</label>
              <input
                className="query-input"
                type="text"
                value={saveModalName}
                onChange={e => setSaveModalName(e.target.value)}
                placeholder="My query name"
                onKeyDown={e => e.key === 'Enter' && handleConfirmSave()}
                style={{ width: '100%', marginBottom: '0.75rem' }}
                autoFocus
              />
              <label style={{ display: 'block', marginBottom: '0.5rem', fontWeight: 600 }}>Description (optional)</label>
              <input
                className="query-input"
                type="text"
                value={saveModalDesc}
                onChange={e => setSaveModalDesc(e.target.value)}
                placeholder="Describe what this query does"
                style={{ width: '100%' }}
              />
            </div>
            <div className="modal-footer">
              <button className="btn btn-secondary" onClick={() => setSaveModalOpen(false)}>Cancel</button>
              <button
                className="btn btn-primary"
                onClick={handleConfirmSave}
                disabled={!saveModalName.trim()}
              >
                Save
              </button>
            </div>
          </div>
        </div>
      )}
      {loading && (
        <div className="loading-overlay">
          <div className="spinner"></div>
          <span>Processing...</span>
        </div>
      )}
    </div>
  );
};

export default EnterpriseAnalyticsHub;
