import React, { useMemo, useState, useEffect } from 'react';
import ReactECharts from 'echarts-for-react';
import * as echarts from 'echarts'; // Add this import for gradients
import { e2etraceFetchWithRetry } from '../../api/e2etrace-api';
import { API_CONFIG } from '../../config/api-config.js';
import { saveAs } from 'file-saver';
import { useNavigate, useSearchParams } from 'react-router-dom';

const chartTypes = [
  { value: 'bar', label: 'Bar Chart' },
  { value: 'line', label: 'Line Chart' },
  { value: 'pie', label: 'Pie Chart' },
  { value: 'scatter', label: 'Scatter Plot' },
  { value: 'area', label: 'Area Chart' },
];

const aggregationTypes = [
  { value: 'count', label: 'Count' },
  { value: 'sum', label: 'Sum' },
  { value: 'avg', label: 'Average' },
  { value: 'min', label: 'Minimum' },
  { value: 'max', label: 'Maximum' },
];

export default function ReportingPage() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();

  const [entities, setEntities] = useState([]);
  const [entity, setEntity] = useState(null);
  const [xProp, setXProp] = useState('');
  const [yProp, setYProp] = useState('');
  const [aggregation, setAggregation] = useState('count');
  const [filter, setFilter] = useState('');
  const [chartType, setChartType] = useState('bar');
  const [loadingEntities, setLoadingEntities] = useState(false);
  const [loadingResult, setLoadingResult] = useState(false);
  const [result, setResult] = useState([]);
  const [chartOption, setChartOption] = useState(null);
  const [limit, setLimit] = useState(50);

  const [qualityReports, setQualityReports] = useState([]);
  const [qualityReportsLoading, setQualityReportsLoading] = useState(false);
  const [qualityReportsError, setQualityReportsError] = useState(null);
  const [selectedQualityReport, setSelectedQualityReport] = useState(null);

  const [plmRunReports, setPlmRunReports] = useState([]);
  const [plmRunReportsLoading, setPlmRunReportsLoading] = useState(false);
  const [plmRunReportsError, setPlmRunReportsError] = useState(null);
  const [selectedPersistedReport, setSelectedPersistedReport] = useState(null);

  const requestedReportId = useMemo(() => {
    const raw = searchParams.get('reportId');
    return raw ? String(raw) : '';
  }, [searchParams]);

  const requestedQualityTable = useMemo(() => {
    const raw = searchParams.get('qualityTable');
    return raw ? String(raw) : '';
  }, [searchParams]);

  const getScoreColor = (score) => {
    const normalized = Number(score);
    if (!Number.isFinite(normalized)) return '#6c757d';
    if (normalized >= 0.9) return '#28a745';
    if (normalized >= 0.7) return '#ffc107';
    return '#dc3545';
  };

  const downloadJson = (filename, payload) => {
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json;charset=utf-8' });
    saveAs(blob, filename);
  };

  const csvEscape = (value) => {
    const s = value == null ? '' : String(value);
    if (/[\n\r",]/.test(s)) return `"${s.replace(/"/g, '""')}"`;
    return s;
  };

  const downloadCsv = (filename, rows) => {
    const csv = rows.map((row) => row.map(csvEscape).join(',')).join('\n');
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' });
    saveAs(blob, filename);
  };

  const exportQualityReportCsv = (report) => {
    const header = [
      'table_name',
      'scan_id',
      'scan_date',
      'overall_score',
      'completeness_score',
      'accuracy_score',
      'consistency_score',
      'validity_score',
      'row_count',
      'column_count',
      'issue_severity',
      'issue_description',
      'issue_affected_rows',
      'issue_affected_columns',
      'issue_suggestion',
    ];

    const issues = Array.isArray(report?.issues) ? report.issues : [];
    const rows = issues.length
      ? issues.map((issue) => [
          report.table_name,
          report.scan_id,
          report.scan_date,
          report.overall_score,
          report.completeness_score,
          report.accuracy_score,
          report.consistency_score,
          report.validity_score,
          report.row_count,
          report.column_count,
          issue?.severity,
          issue?.description,
          issue?.affected_rows,
          Array.isArray(issue?.affected_columns) ? issue.affected_columns.join('|') : '',
          issue?.suggestion,
        ])
      : [
          [
            report.table_name,
            report.scan_id,
            report.scan_date,
            report.overall_score,
            report.completeness_score,
            report.accuracy_score,
            report.consistency_score,
            report.validity_score,
            report.row_count,
            report.column_count,
            '',
            '',
            '',
            '',
            '',
          ],
        ];

    downloadCsv(
      `quality_report_${String(report.table_name || 'unknown')}_${new Date().toISOString().split('T')[0]}.csv`,
      [header, ...rows],
    );
  };

  // Fetch available entities and properties
  useEffect(() => {
    setLoadingEntities(true);
    e2etraceFetchWithRetry(API_CONFIG.ENDPOINTS.ENTITIES)
      .then(res => res.json())
      .then(data => {
        const validEntities = data.filter(en => Array.isArray(en.properties) && en.properties.length > 0);
        setEntities(validEntities);
        // Auto-select first entity
        if (validEntities.length > 0) {
          setEntity(validEntities[0]);
          setXProp(validEntities[0].properties[0] || '');
        }
      })
      .catch(error => {
        console.error('Error fetching entities:', error);
        setEntities([]);
      })
      .finally(() => setLoadingEntities(false));
  }, []);

  // Fetch Quality Reports (centralized here; Data Quality page no longer owns reporting UI)
  useEffect(() => {
    let cancelled = false;
    const run = async () => {
      try {
        setQualityReportsLoading(true);
        setQualityReportsError(null);
        const res = await fetch('/api/analytics/quality/reports');
        if (!res.ok) throw new Error('Failed to fetch quality reports');
        const data = await res.json();
        if (cancelled) return;
        setQualityReports(Array.isArray(data) ? data : []);
      } catch (error) {
        if (cancelled) return;
        setQualityReports([]);
        setQualityReportsError(error?.message || 'Failed to fetch quality reports');
      } finally {
        if (!cancelled) setQualityReportsLoading(false);
      }
    };

    run();
    return () => {
      cancelled = true;
    };
  }, []);

  // Fetch persisted PLM run reports
  useEffect(() => {
    let cancelled = false;
    const run = async () => {
      try {
        setPlmRunReportsLoading(true);
        setPlmRunReportsError(null);
        const res = await fetch('/api/reports?report_type=plm_etl_run&limit=50');
        if (!res.ok) throw new Error('Failed to fetch persisted run reports');
        const data = await res.json();
        if (cancelled) return;
        setPlmRunReports(Array.isArray(data) ? data : []);
      } catch (error) {
        if (cancelled) return;
        setPlmRunReports([]);
        setPlmRunReportsError(error?.message || 'Failed to fetch persisted run reports');
      } finally {
        if (!cancelled) setPlmRunReportsLoading(false);
      }
    };

    run();
    return () => {
      cancelled = true;
    };
  }, []);

  // Deep-link: load persisted report details (?reportId=...)
  useEffect(() => {
    if (!requestedReportId) return;
    let cancelled = false;
    const run = async () => {
      try {
        const res = await fetch(`/api/reports/${encodeURIComponent(requestedReportId)}`);
        if (!res.ok) throw new Error('Report not found');
        const data = await res.json();
        if (!cancelled) setSelectedPersistedReport(data);
      } catch {
        if (!cancelled) setSelectedPersistedReport(null);
      }
    };
    run();
    return () => {
      cancelled = true;
    };
  }, [requestedReportId]);

  // Apply deep link selection (?qualityTable=...)
  useEffect(() => {
    if (!requestedQualityTable) return;
    if (!Array.isArray(qualityReports) || qualityReports.length === 0) return;
    const found = qualityReports.find((r) => r?.table_name === requestedQualityTable);
    if (found) setSelectedQualityReport(found);
  }, [qualityReports, requestedQualityTable]);

  // Generate chart options
  const generateChartOption = (records, chartType) => {
    if (!records || records.length === 0) return null;

    const baseOption = {
      tooltip: { trigger: 'item' },
      toolbox: {
        show: true,
        feature: {
          saveAsImage: { show: true, title: 'Save as Image' },
          dataView: { show: true, title: 'Data View' },
          restore: { show: true, title: 'Restore' },
        }
      },
      grid: { 
        left: '3%', 
        right: '4%', 
        bottom: '3%', 
        containLabel: true 
      },
    };

    switch (chartType) {
      case 'bar':
        return {
          ...baseOption,
          xAxis: { 
            type: 'category', 
            data: records.map(row => String(row.x)),
            axisLabel: { rotate: 45, interval: 0 }
          },
          yAxis: { type: 'value' },
          series: [{
            type: 'bar',
            data: records.map(row => Number(row.y) || 0),
            itemStyle: {
              color: '#188df0'
            }
          }],
        };

      case 'line':
        return {
          ...baseOption,
          xAxis: { 
            type: 'category', 
            data: records.map(row => String(row.x)),
            boundaryGap: false
          },
          yAxis: { type: 'value' },
          series: [{
            type: 'line',
            data: records.map(row => Number(row.y) || 0),
            smooth: true,
            symbol: 'circle',
            symbolSize: 6,
            lineStyle: { width: 2 }
          }],
        };

      case 'pie':
        return {
          ...baseOption,
          tooltip: { trigger: 'item', formatter: '{a} <br/>{b}: {c} ({d}%)' },
          legend: { orient: 'horizontal', bottom: 10 },
          series: [{
            type: 'pie',
            radius: ['30%', '70%'],
            data: records.map(row => ({ 
              value: Number(row.y) || 0, 
              name: String(row.x) 
            })),
            label: {
              show: true,
              formatter: '{b}: {d}%'
            }
          }],
        };

      case 'scatter':
        return {
          ...baseOption,
          xAxis: { type: 'value', name: xProp },
          yAxis: { type: 'value', name: yProp || 'Count' },
          series: [{
            type: 'scatter',
            data: records.map(row => [Number(row.x) || 0, Number(row.y) || 0]),
            symbolSize: 8
          }],
        };

      case 'area':
        return {
          ...baseOption,
          xAxis: { 
            type: 'category', 
            data: records.map(row => String(row.x)),
            boundaryGap: false
          },
          yAxis: { type: 'value' },
          series: [{
            type: 'line',
            data: records.map(row => Number(row.y) || 0),
            smooth: true,
            areaStyle: { opacity: 0.3 }
          }],
        };

      default:
        return baseOption;
    }
  };

  // Generate and run search
  const handleSearch = async () => {
    if (!entity || !xProp) {
      alert('Please select an entity and X property');
      return;
    }
    setLoadingResult(true);
    
    let cypher = '';
    if (aggregation === 'count') {
      cypher = `
        MATCH (n:\`${entity.label}\`)
        ${filter ? `WHERE n.${xProp} ${filter}` : ''}
        RETURN n.${xProp} AS x, count(*) AS y
        ORDER BY y DESC
        LIMIT ${limit}
      `;
    } else if (yProp) {
      cypher = `
        MATCH (n:\`${entity.label}\`)
        WHERE n.${yProp} IS NOT NULL ${filter ? `AND n.${xProp} ${filter}` : ''}
        RETURN n.${xProp} AS x, ${aggregation}(n.${yProp}) AS y
        ORDER BY y DESC
        LIMIT ${limit}
      `;
    } else {
      cypher = `
        MATCH (n:\`${entity.label}\`)
        ${filter ? `WHERE n.${xProp} ${filter}` : ''}
        RETURN n.${xProp} AS x, count(*) AS y
        ORDER BY y DESC
        LIMIT ${limit}
      `;
    }

    try {
      const res = await e2etraceFetchWithRetry(API_CONFIG.ENDPOINTS.GRAPH_QUERY, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ cypher }),
      });
      const data = await res.json();
      const records = data.records || [];
      setResult(records);
      
      if (records.length > 0) {
        const chartOption = generateChartOption(records, chartType);
        chartOption.title = { 
          text: `${entity.label} - ${xProp} Analysis`,
          left: 'center',
          textStyle: { fontSize: 18, fontWeight: 'bold' }
        };
        setChartOption(chartOption);
      } else {
        setChartOption(null);
      }
    } catch (error) {
      console.error('Error:', error);
      setResult([]);
      setChartOption(null);
    } finally {
      setLoadingResult(false);
    }
  };

  return (
    <div style={{ padding: '2rem', maxWidth: 1200, margin: '0 auto' }}>
      <h2 style={{ textAlign: 'center', marginBottom: '2rem', color: '#2c3e50' }}>
        Advanced Reporting & Visualization
      </h2>

      {/* Quality Reports (centralized) */}
      <div style={{
        background: 'var(--card-bg)',
        borderRadius: 12,
        padding: '1.25rem',
        marginBottom: '1.5rem',
        border: '1px solid var(--border-color)'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '1rem', marginBottom: '1rem' }}>
          <h3 style={{ margin: 0 }}>Quality Reports</h3>
          {selectedQualityReport ? (
            <button
              type="button"
              onClick={() => setSelectedQualityReport(null)}
              style={{
                padding: '0.5rem 0.75rem',
                borderRadius: 8,
                border: '1px solid var(--border-color)',
                background: 'var(--card-bg)',
                cursor: 'pointer'
              }}
            >
              Back to list
            </button>
          ) : null}
        </div>

        {qualityReportsError ? (
          <div style={{ color: 'var(--error-color)' }}>{qualityReportsError}</div>
        ) : null}

        {qualityReportsLoading ? (
          <div>Loading quality reports…</div>
        ) : null}

        {!qualityReportsLoading && !qualityReportsError && !selectedQualityReport ? (
          <>
            {qualityReports.length === 0 ? (
              <div>No quality reports yet. Run a scan to generate reports.</div>
            ) : (
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '1rem' }}>
                {qualityReports.map((report, idx) => (
                  <button
                    key={`${report?.scan_id || report?.table_name || idx}`}
                    type="button"
                    onClick={() => setSelectedQualityReport(report)}
                    style={{
                      textAlign: 'left',
                      padding: '1rem',
                      borderRadius: 12,
                      border: '1px solid var(--border-color)',
                      background: 'var(--card-bg)',
                      cursor: 'pointer'
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '0.75rem' }}>
                      <div style={{ fontWeight: 700 }}>{report.table_name}</div>
                      <div style={{
                        padding: '0.25rem 0.5rem',
                        borderRadius: 999,
                        background: getScoreColor(report.overall_score),
                        color: '#fff',
                        fontWeight: 700
                      }}>
                        {Number.isFinite(Number(report.overall_score)) ? `${Math.round(Number(report.overall_score) * 100)}%` : 'N/A'}
                      </div>
                    </div>
                    <div style={{ marginTop: '0.75rem', display: 'grid', gap: '0.25rem', opacity: 0.9 }}>
                      <div>Issues: {Array.isArray(report.issues) ? report.issues.length : 0}</div>
                      <div>Scanned: {report.scan_date ? new Date(report.scan_date).toLocaleDateString() : '—'}</div>
                    </div>
                  </button>
                ))}
              </div>
            )}
          </>
        ) : null}

        {!qualityReportsLoading && !qualityReportsError && selectedQualityReport ? (
          <div style={{ display: 'grid', gap: '1rem' }}>
            <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: '1rem', flexWrap: 'wrap' }}>
              <div>
                <div style={{ fontSize: '1.1rem', fontWeight: 800 }}>{selectedQualityReport.table_name}</div>
                <div style={{ opacity: 0.85, marginTop: '0.25rem' }}>
                  Scan ID: {selectedQualityReport.scan_id || '—'} · Date:{' '}
                  {selectedQualityReport.scan_date ? new Date(selectedQualityReport.scan_date).toLocaleString() : '—'}
                </div>
              </div>

              <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                <button
                  type="button"
                  onClick={() => downloadJson(
                    `quality_report_${String(selectedQualityReport.table_name || 'unknown')}_${new Date().toISOString().split('T')[0]}.json`,
                    selectedQualityReport,
                  )}
                  style={{
                    padding: '0.5rem 0.75rem',
                    borderRadius: 8,
                    border: '1px solid var(--border-color)',
                    background: 'var(--card-bg)',
                    cursor: 'pointer'
                  }}
                >
                  Download JSON
                </button>

                <button
                  type="button"
                  onClick={() => exportQualityReportCsv(selectedQualityReport)}
                  style={{
                    padding: '0.5rem 0.75rem',
                    borderRadius: 8,
                    border: '1px solid var(--border-color)',
                    background: 'var(--card-bg)',
                    cursor: 'pointer'
                  }}
                >
                  Download CSV
                </button>

                <button
                  type="button"
                  onClick={() => navigate('/spreadsheet')}
                  style={{
                    padding: '0.5rem 0.75rem',
                    borderRadius: 8,
                    border: '1px solid var(--border-color)',
                    background: 'var(--card-bg)',
                    cursor: 'pointer'
                  }}
                >
                  Open Spreadsheet
                </button>
              </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: '0.75rem' }}>
              <div style={{ padding: '0.75rem', border: '1px solid var(--border-color)', borderRadius: 12, background: 'var(--card-bg)' }}>
                <div style={{ opacity: 0.8 }}>Overall</div>
                <div style={{ fontWeight: 800, color: getScoreColor(selectedQualityReport.overall_score) }}>
                  {Number.isFinite(Number(selectedQualityReport.overall_score)) ? `${(Number(selectedQualityReport.overall_score) * 100).toFixed(1)}%` : 'N/A'}
                </div>
              </div>
              <div style={{ padding: '0.75rem', border: '1px solid var(--border-color)', borderRadius: 12, background: 'var(--card-bg)' }}>
                <div style={{ opacity: 0.8 }}>Issues</div>
                <div style={{ fontWeight: 800 }}>{Array.isArray(selectedQualityReport.issues) ? selectedQualityReport.issues.length : 0}</div>
              </div>
              <div style={{ padding: '0.75rem', border: '1px solid var(--border-color)', borderRadius: 12, background: 'var(--card-bg)' }}>
                <div style={{ opacity: 0.8 }}>Rows</div>
                <div style={{ fontWeight: 800 }}>{selectedQualityReport.row_count != null ? Number(selectedQualityReport.row_count).toLocaleString() : '—'}</div>
              </div>
              <div style={{ padding: '0.75rem', border: '1px solid var(--border-color)', borderRadius: 12, background: 'var(--card-bg)' }}>
                <div style={{ opacity: 0.8 }}>Columns</div>
                <div style={{ fontWeight: 800 }}>{selectedQualityReport.column_count != null ? selectedQualityReport.column_count : '—'}</div>
              </div>
            </div>

            {Array.isArray(selectedQualityReport.issues) && selectedQualityReport.issues.length > 0 ? (
              <div style={{ display: 'grid', gap: '0.5rem' }}>
                <div style={{ fontWeight: 700 }}>Issues</div>
                {selectedQualityReport.issues.map((issue, idx) => (
                  <div
                    key={idx}
                    style={{
                      padding: '0.75rem',
                      borderRadius: 12,
                      border: '1px solid var(--border-color)',
                      background: 'var(--card-bg)'
                    }}
                  >
                    <div style={{ fontWeight: 700 }}>
                      {issue?.severity ? String(issue.severity).toUpperCase() : 'ISSUE'}: {issue?.description || ''}
                    </div>
                    <div style={{ opacity: 0.85, marginTop: '0.25rem' }}>
                      Affected rows: {issue?.affected_rows ?? '—'} · Columns:{' '}
                      {Array.isArray(issue?.affected_columns) ? issue.affected_columns.join(', ') : '—'}
                    </div>
                    {issue?.suggestion ? (
                      <div style={{ opacity: 0.9, marginTop: '0.25rem' }}>Suggestion: {issue.suggestion}</div>
                    ) : null}
                  </div>
                ))}
              </div>
            ) : null}
          </div>
        ) : null}
      </div>

      {/* Persisted PLM ETL Run Reports */}
      <div style={{
        background: 'var(--card-bg)',
        borderRadius: 12,
        padding: '1.25rem',
        marginBottom: '1.5rem',
        border: '1px solid var(--border-color)'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '1rem', marginBottom: '1rem', flexWrap: 'wrap' }}>
          <h3 style={{ margin: 0 }}>PLM ETL Run Reports</h3>
          {selectedPersistedReport ? (
            <button
              type="button"
              onClick={() => {
                setSelectedPersistedReport(null);
                navigate('/reporting');
              }}
              style={{
                padding: '0.5rem 0.75rem',
                borderRadius: 8,
                border: '1px solid var(--border-color)',
                background: 'var(--card-bg)',
                cursor: 'pointer'
              }}
            >
              Back to list
            </button>
          ) : null}
        </div>

        {plmRunReportsError ? (
          <div style={{ color: 'var(--error-color)' }}>{plmRunReportsError}</div>
        ) : null}

        {plmRunReportsLoading ? <div>Loading run reports…</div> : null}

        {!plmRunReportsLoading && !selectedPersistedReport ? (
          <>
            {plmRunReports.length === 0 ? (
              <div>No persisted run reports yet. Run PLM ETL to generate one.</div>
            ) : (
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: '1rem' }}>
                {plmRunReports.map((r) => (
                  <button
                    key={r.id}
                    type="button"
                    onClick={() => navigate(`/reporting?reportId=${encodeURIComponent(r.id)}`)}
                    style={{
                      textAlign: 'left',
                      padding: '1rem',
                      borderRadius: 12,
                      border: '1px solid var(--border-color)',
                      background: 'var(--card-bg)',
                      cursor: 'pointer'
                    }}
                  >
                    <div style={{ fontWeight: 800 }}>{r.title || 'PLM ETL Run Report'}</div>
                    <div style={{ opacity: 0.85, marginTop: '0.25rem' }}>
                      Run ID: {r.run_id || '—'}
                    </div>
                    <div style={{ opacity: 0.8, marginTop: '0.25rem' }}>
                      Created: {r.created_at ? new Date(r.created_at).toLocaleString() : '—'}
                    </div>
                  </button>
                ))}
              </div>
            )}
          </>
        ) : null}

        {selectedPersistedReport ? (
          <div style={{ display: 'grid', gap: '0.75rem' }}>
            <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: '1rem', flexWrap: 'wrap' }}>
              <div>
                <div style={{ fontWeight: 900 }}>{selectedPersistedReport.title || selectedPersistedReport.id}</div>
                <div style={{ opacity: 0.85, marginTop: '0.25rem' }}>
                  Type: {selectedPersistedReport.report_type} · Run ID: {selectedPersistedReport.run_id || '—'}
                </div>
              </div>
              <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                <button
                  type="button"
                  onClick={() => downloadJson(
                    `report_${String(selectedPersistedReport.report_type || 'report')}_${new Date().toISOString().split('T')[0]}.json`,
                    selectedPersistedReport.payload,
                  )}
                  style={{
                    padding: '0.5rem 0.75rem',
                    borderRadius: 8,
                    border: '1px solid var(--border-color)',
                    background: 'var(--card-bg)',
                    cursor: 'pointer'
                  }}
                >
                  Download JSON
                </button>
                <button
                  type="button"
                  onClick={() => navigate(`/spreadsheet?reportId=${encodeURIComponent(selectedPersistedReport.id)}`)}
                  style={{
                    padding: '0.5rem 0.75rem',
                    borderRadius: 8,
                    border: '1px solid var(--border-color)',
                    background: 'var(--card-bg)',
                    cursor: 'pointer'
                  }}
                >
                  Open Spreadsheet
                </button>
              </div>
            </div>

            <pre style={{
              whiteSpace: 'pre-wrap',
              background: 'var(--accent-color)',
              color: 'white',
              borderRadius: 12,
              padding: '1rem',
              overflowX: 'auto'
            }}>
              {JSON.stringify(selectedPersistedReport.payload, null, 2)}
            </pre>
          </div>
        ) : null}
      </div>
      
      {/* Enhanced Search Panel */}
      <div style={{
        display: 'grid', 
        gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', 
        gap: '1rem',
        background: 'var(--accent-color)',
        borderRadius: 12, 
        padding: '2rem', 
        marginBottom: '2rem', 
        boxShadow: '0 10px 30px rgba(0,0,0,0.2)',
        color: 'white'
      }}>
        <div>
          <label style={{ display: 'block', marginBottom: '0.5rem', fontWeight: 'bold' }}>
            Entity
          </label>
          <select
            value={entity ? entity.label : ''}
            onChange={e => {
              const ent = entities.find(en => en.label === e.target.value);
              setEntity(ent); setXProp(''); setYProp('');
            }}
            disabled={loadingEntities || !entities.length}
            style={{ width: '100%', padding: '0.5rem', borderRadius: 6, border: 'none' }}
          >
            <option value="">Select Entity</option>
            {entities.map(en => (
              <option key={en.label} value={en.label}>
                {en.label} ({en.type})
              </option>
            ))}
          </select>
        </div>

        <div>
          <label style={{ display: 'block', marginBottom: '0.5rem', fontWeight: 'bold' }}>
            X-Axis Property
          </label>
          <select 
            value={xProp} 
            onChange={e => setXProp(e.target.value)} 
            disabled={!entity}
            style={{ width: '100%', padding: '0.5rem', borderRadius: 6, border: 'none' }}
          >
            <option value="">Select Property</option>
            {entity && entity.properties && entity.properties.map(p => 
              <option key={p} value={p}>{p}</option>
            )}
          </select>
        </div>

        <div>
          <label style={{ display: 'block', marginBottom: '0.5rem', fontWeight: 'bold' }}>
            Y-Axis Property
          </label>
          <select 
            value={yProp} 
            onChange={e => setYProp(e.target.value)} 
            disabled={!entity}
            style={{ width: '100%', padding: '0.5rem', borderRadius: 6, border: 'none' }}
          >
            <option value="">Count</option>
            {entity && entity.properties && entity.properties.map(p => 
              <option key={p} value={p}>{p}</option>
            )}
          </select>
        </div>

        <div>
          <label style={{ display: 'block', marginBottom: '0.5rem', fontWeight: 'bold' }}>
            Aggregation
          </label>
          <select 
            value={aggregation} 
            onChange={e => setAggregation(e.target.value)}
            style={{ width: '100%', padding: '0.5rem', borderRadius: 6, border: 'none' }}
          >
            {aggregationTypes.map(agg => 
              <option key={agg.value} value={agg.value}>{agg.label}</option>
            )}
          </select>
        </div>

        <div>
          <label style={{ display: 'block', marginBottom: '0.5rem', fontWeight: 'bold' }}>
            Chart Type
          </label>
          <select 
            value={chartType} 
            onChange={e => setChartType(e.target.value)}
            style={{ width: '100%', padding: '0.5rem', borderRadius: 6, border: 'none' }}
          >
            {chartTypes.map(ct => 
              <option key={ct.value} value={ct.value}>{ct.label}</option>
            )}
          </select>
        </div>

        <div>
          <label style={{ display: 'block', marginBottom: '0.5rem', fontWeight: 'bold' }}>
            Filter (Optional)
          </label>
          <input
            type="text"
            value={filter}
            onChange={e => setFilter(e.target.value)}
            placeholder="e.g. > 30 or = 'ACTIVE'"
            disabled={!entity || !xProp}
            style={{ width: '100%', padding: '0.5rem', borderRadius: 6, border: 'none' }}
          />
        </div>

        <div>
          <label style={{ display: 'block', marginBottom: '0.5rem', fontWeight: 'bold' }}>
            Limit
          </label>
          <input
            type="number"
            value={limit}
            onChange={e => setLimit(parseInt(e.target.value) || 50)}
            min="1"
            max="1000"
            style={{ width: '100%', padding: '0.5rem', borderRadius: 6, border: 'none' }}
          />
        </div>

        <div style={{ display: 'flex', alignItems: 'flex-end' }}>
          <button
            onClick={handleSearch}
            style={{ 
              width: '100%',
              padding: '0.75rem 1.5rem', 
              fontWeight: 'bold',
              background: 'linear-gradient(45deg, #FE6B8B 30%, #FF8E53 90%)',
              color: 'white',
              border: 'none',
              borderRadius: 6,
              cursor: 'pointer',
              fontSize: '1rem',
              transition: 'transform 0.2s',
            }}
            disabled={!entity || !xProp || loadingResult}
            onMouseOver={e => e.target.style.transform = 'scale(1.05)'}
            onMouseOut={e => e.target.style.transform = 'scale(1)'
            }
          >
            {loadingResult ? 'Analyzing...' : 'Generate Visualization'}
          </button>
        </div>
      </div>

      {/* Enhanced Chart Display */}
      <div style={{ 
        background: '#fff', 
        borderRadius: 12, 
        boxShadow: '0 8px 32px rgba(0,0,0,0.1)', 
        padding: '2rem', 
        marginBottom: '2rem',
        minHeight: 400
      }}>
        {chartOption ? (
          <ReactECharts 
            option={chartOption} 
            theme={theme}
            style={{ height: 500, width: '100%' }} 
            opts={{ renderer: 'canvas' }}
          />
        ) : (
          <div style={{ 
            textAlign: 'center', 
            color: '#888', 
            fontSize: '1.2rem',
            paddingTop: '3rem'
          }}>
            ◳ Configure your search parameters and generate a visualization
          </div>
        )}
      </div>

      {/* Enhanced Result Table */}
      {result.length > 0 && (
        <div style={{ 
          background: '#fff', 
          borderRadius: 12, 
          boxShadow: '0 8px 32px rgba(0,0,0,0.1)', 
          overflow: 'hidden',
          marginBottom: '2rem'
        }}>
          <div style={{ 
            background: 'var(--accent-color)',
            color: 'white',
            padding: '1rem 2rem',
            fontSize: '1.1rem',
            fontWeight: 'bold'
          }}>
            ↗ Data Results ({result.length} records)
          </div>
          <div style={{ maxHeight: 400, overflow: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead style={{ position: 'sticky', top: 0, background: '#f8f9fa' }}>
                <tr>
                  <th style={{ padding: '1rem', borderBottom: '2px solid #dee2e6', textAlign: 'left' }}>
                    {xProp || 'X'}
                  </th>
                  <th style={{ padding: '1rem', borderBottom: '2px solid #dee2e6', textAlign: 'left' }}>
                    {yProp || 'Count'}
                  </th>
                </tr>
              </thead>
              <tbody>
                {result.map((row, idx) => (
                  <tr key={idx} style={{ 
                    background: idx % 2 === 0 ? '#f8f9fa' : '#fff',
                    transition: 'background-color 0.2s'
                  }}>
                    <td style={{ padding: '0.75rem 1rem', borderBottom: '1px solid #dee2e6' }}>
                      {row.x}
                    </td>
                    <td style={{ padding: '0.75rem 1rem', borderBottom: '1px solid #dee2e6' }}>
                      {typeof row.y === 'number' ? row.y.toLocaleString() : row.y}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Link to dedicated spreadsheet page */}
      <div style={{ 
        marginTop: '3rem', 
        textAlign: 'center',
        padding: '2rem',
        background: 'var(--accent-color)',
        borderRadius: '12px',
        color: 'white'
      }}>
        <h3 style={{ margin: '0 0 1rem 0' }}>◳ Need Advanced Data Analysis?</h3>
        <p style={{ margin: '0 0 1.5rem 0', opacity: 0.9 }}>
          Use our dedicated ECharts Spreadsheet for Excel import/export, advanced charting, and data manipulation.
        </p>
        <a 
          href="#/spreadsheet" 
          style={{
            display: 'inline-block',
            padding: '0.75rem 1.5rem',
            background: 'rgba(255, 255, 255, 0.2)',
            border: '2px solid rgba(255, 255, 255, 0.3)',
            borderRadius: '8px',
            color: 'white',
            textDecoration: 'none',
            fontWeight: 'bold',
            transition: 'all 0.3s ease'
          }}
          onMouseOver={(e) => {
            e.target.style.background = 'rgba(255, 255, 255, 0.3)';
            e.target.style.transform = 'translateY(-2px)';
          }}
          onMouseOut={(e) => {
            e.target.style.background = 'rgba(255, 255, 255, 0.2)';
            e.target.style.transform = 'translateY(0)';
          }}
        >
          ➔ Open ECharts Spreadsheet
        </a>
      </div>
    </div>
  );
}
