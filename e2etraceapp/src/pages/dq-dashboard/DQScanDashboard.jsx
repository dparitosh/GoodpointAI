/**
 * Data Quality Scan Dashboard
 * ===========================
 * Real-time DQ scan statistics with ECharts visualizations.
 * Uses live /api/analytics/quality/* endpoints with built-in dummy fallback.
 */

import React, { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import ReactECharts from 'echarts-for-react';
import { useReportHub } from '../../hooks/useReportHub.js';
import { apiClient } from '../../utils/apiClient.js';
import { API_CONFIG } from '../../config/api-config.js';
import { AgentPipelineStrip } from '../../components/agent-pipeline-strip/AgentPipelineStrip.jsx';
import './DQScanDashboard.css';

// ─────────────────────────────────────────────────────────────────────────────
// HELPERS
// ─────────────────────────────────────────────────────────────────────────────
function scoreColor(score) {
  if (score >= 90) return '#22c55e';
  if (score >= 75) return '#f59e0b';
  return '#ef4444';
}

function scoreLabel(score) {
  if (score >= 90) return 'Excellent';
  if (score >= 75) return 'Good';
  if (score >= 60) return 'Fair';
  return 'Poor';
}

function severityBadge(sev) {
  const map = { critical: '#ef4444', warning: '#f59e0b', info: '#3b82f6' };
  return map[sev] || '#6b7280';
}

function fmtDate(iso) {
  if (!iso) return '–';
  const d = new Date(iso);
  return d.toLocaleString('en-GB', { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' });
}

// ─────────────────────────────────────────────────────────────────────────────
// CHART OPTIONS
// ─────────────────────────────────────────────────────────────────────────────
function buildScoreGauge(label, score) {
  const color = scoreColor(score);
  return {
    backgroundColor: 'transparent',
    series: [{
      type: 'gauge',
      startAngle: 200, endAngle: -20,
      min: 0, max: 100,
      radius: '90%',
      axisLine: {
        lineStyle: {
          width: 14,
          color: [[score / 100, color], [1, '#e5e7eb']],
        },
      },
      axisTick: { show: false },
      splitLine: { show: false },
      axisLabel: { show: false },
      pointer: { show: false },
      detail: {
        offsetCenter: [0, '10%'],
        valueAnimation: true,
        formatter: (v) => `{val|${v.toFixed(1)}}\n{lab|${scoreLabel(v)}}`,
        rich: {
          val: { fontSize: 22, fontWeight: 700, color, lineHeight: 28 },
          lab: { fontSize: 11, color: '#6b7280', lineHeight: 18 },
        },
      },
      title: {
        offsetCenter: [0, '-35%'],
        fontSize: 12,
        color: '#374151',
        fontWeight: 600,
      },
      data: [{ value: score, name: label }],
    }],
  };
}

function buildDimensionsRadar(profile) {
  const dims = ['Completeness', 'Uniqueness', 'Validity', 'Freshness'];
  const vals = [profile.completeness, profile.uniqueness, profile.validity, profile.freshness];
  return {
    backgroundColor: 'transparent',
    tooltip: { trigger: 'item' },
    radar: {
      indicator: dims.map((d) => ({ name: d, max: 100 })),
      shape: 'polygon',
      splitNumber: 4,
      axisName: { color: '#374151', fontSize: 11 },
      splitLine: { lineStyle: { color: '#e5e7eb' } },
      splitArea: { areaStyle: { color: ['rgba(59,130,246,0.03)', 'rgba(59,130,246,0.06)'] } },
      axisLine: { lineStyle: { color: '#d1d5db' } },
    },
    series: [{
      type: 'radar',
      data: [{
        value: vals,
        name: 'Quality Dimensions',
        areaStyle: { color: 'rgba(59,130,246,0.15)' },
        lineStyle: { color: '#3b82f6', width: 2 },
        itemStyle: { color: '#3b82f6' },
      }],
    }],
  };
}

function buildScoreTrend(history) {
  return {
    backgroundColor: 'transparent',
    tooltip: { trigger: 'axis', formatter: (p) => `${p[0].name}<br/>Avg Score: <b>${p[0].value}</b>` },
    grid: { left: 40, right: 20, top: 20, bottom: 30 },
    xAxis: {
      type: 'category',
      data: history.map((h) => h.date.slice(5)),
      axisLabel: { fontSize: 10, color: '#6b7280' },
      axisLine: { lineStyle: { color: '#e5e7eb' } },
    },
    yAxis: {
      type: 'value', min: 60, max: 100,
      axisLabel: { fontSize: 10, color: '#6b7280' },
      splitLine: { lineStyle: { color: '#f3f4f6', type: 'dashed' } },
    },
    series: [{
      type: 'line', smooth: true,
      data: history.map((h) => h.avgScore),
      areaStyle: { color: { type: 'linear', x: 0, y: 0, x2: 0, y2: 1, colorStops: [{ offset: 0, color: 'rgba(34,197,94,0.25)' }, { offset: 1, color: 'rgba(34,197,94,0.02)' }] } },
      lineStyle: { color: '#22c55e', width: 2.5 },
      itemStyle: { color: '#22c55e' },
      symbol: 'circle', symbolSize: 6,
    }],
  };
}

function buildIssuesBySeverity(reports) {
  const counts = { critical: 0, warning: 0, info: 0 };
  reports.forEach((r) => r.issues.forEach((i) => { counts[i.severity] = (counts[i.severity] || 0) + i.count; }));
  return {
    backgroundColor: 'transparent',
    tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
    legend: { bottom: 0, textStyle: { fontSize: 11 } },
    series: [{
      type: 'pie', radius: ['45%', '72%'],
      avoidLabelOverlap: true,
      label: { show: false },
      emphasis: { label: { show: true, fontSize: 13, fontWeight: 'bold' } },
      data: [
        { value: counts.critical, name: 'Critical', itemStyle: { color: '#ef4444' } },
        { value: counts.warning, name: 'Warning', itemStyle: { color: '#f59e0b' } },
        { value: counts.info, name: 'Info', itemStyle: { color: '#3b82f6' } },
      ],
    }],
  };
}

function buildTableScoreBar(reports) {
  const sorted = [...reports].sort((a, b) => a.overall_score - b.overall_score);
  return {
    backgroundColor: 'transparent',
    tooltip: { trigger: 'axis', formatter: (p) => `${p[0].name}<br/>Score: <b>${p[0].value}</b>` },
    grid: { left: 140, right: 30, top: 10, bottom: 20 },
    xAxis: { type: 'value', min: 0, max: 100, axisLabel: { fontSize: 10, color: '#6b7280' }, splitLine: { lineStyle: { color: '#f3f4f6' } } },
    yAxis: { type: 'category', data: sorted.map((r) => r.table_name), axisLabel: { fontSize: 10, color: '#374151' }, axisTick: { show: false } },
    series: [{
      type: 'bar', barWidth: 16,
      data: sorted.map((r) => ({
        value: r.overall_score,
        itemStyle: { color: scoreColor(r.overall_score), borderRadius: [0, 4, 4, 0] },
      })),
      label: { show: true, position: 'right', formatter: (p) => `${p.value}%`, fontSize: 10, color: '#374151' },
    }],
  };
}

function buildDimensionsHeatmap(reports) {
  const dims = ['Completeness', 'Uniqueness', 'Validity', 'Freshness'];
  const dimKeys = ['completeness', 'uniqueness', 'validity', 'freshness'];
  const tables = reports.map((r) => r.table_name);
  const data = [];
  reports.forEach((r, ti) => {
    dimKeys.forEach((dk, di) => {
      data.push([di, ti, r.profile[dk]]);
    });
  });
  return {
    backgroundColor: 'transparent',
    tooltip: { formatter: (p) => `${tables[p.value[1]]} / ${dims[p.value[0]]}<br/><b>${p.value[2].toFixed(1)}%</b>` },
    grid: { left: 130, right: 60, top: 10, bottom: 60 },
    xAxis: { type: 'category', data: dims, axisLabel: { fontSize: 10, color: '#6b7280', rotate: 30 }, axisTick: { show: false } },
    yAxis: { type: 'category', data: tables, axisLabel: { fontSize: 10, color: '#374151' }, axisTick: { show: false } },
    visualMap: { min: 50, max: 100, calculable: true, orient: 'horizontal', left: 'center', bottom: 0, itemWidth: 12, itemHeight: 60, textStyle: { fontSize: 10 }, inRange: { color: ['#fecaca', '#fef3c7', '#bbf7d0', '#22c55e'] } },
    series: [{ type: 'heatmap', data, label: { show: true, formatter: (p) => p.value[2].toFixed(0), fontSize: 9 } }],
  };
}

// ─────────────────────────────────────────────────────────────────────────────
// COMPONENTS
// ─────────────────────────────────────────────────────────────────────────────
function KpiCard({ label, value, sub, color, icon }) {
  return (
    <div className="dq-kpi-card">
      <div className="dq-kpi-icon" style={{ background: `${color}18`, color }}>{icon}</div>
      <div className="dq-kpi-body">
        <div className="dq-kpi-value" style={{ color }}>{value}</div>
        <div className="dq-kpi-label">{label}</div>
        {sub && <div className="dq-kpi-sub">{sub}</div>}
      </div>
    </div>
  );
}

function SectionHeader({ title, badge }) {
  return (
    <div className="dq-section-header">
      <h3>{title}</h3>
      {badge && <span className="dq-badge">{badge}</span>}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// MAIN COMPONENT
// ─────────────────────────────────────────────────────────────────────────────
export default function DQScanDashboard() {
  const [reports, setReports] = useState([]);
  const [history] = useState([]);
  const [selected, setSelected] = useState(null);
  const [liveMode, setLiveMode] = useState(false);
  const [scanningTable, setScanningTable] = useState(null);
  const [availableTables, setAvailableTables] = useState([]);
  const [tablePickerOpen, setTablePickerOpen] = useState(false);
  const [pickerTable, setPickerTable] = useState('');

  // ── Folder datasource scan state
  const [scanMode, setScanMode] = useState('table'); // 'table' | 'folder'
  const [folderSources, setFolderSources] = useState([]);
  const [pickerFolderSourceId, setPickerFolderSourceId] = useState('');

  const [scanError, setScanError] = useState(null);
  const { saveReport, saving: rhSaving, saved: rhSaved } = useReportHub();

  // Attempt live data load on mount
  useEffect(() => {
    apiClient.get(API_CONFIG.ENDPOINTS.DATA_QUALITY_REPORTS)
      .then((data) => {
        if (Array.isArray(data) && data.length > 0) {
          const merged = data.map((r) => ({
            ...r,
            profile: r.profile || { completeness: r.overall_score || 80, uniqueness: 100, validity: r.overall_score || 80, freshness: 70 },
            issues: r.issues || [],
          }));
          setReports(merged);
          setLiveMode(true);
        }
      })
      .catch(() => { /* backend unavailable — use dummy data */ });
  }, []);

  const loadTables = useCallback(() => {
    // Load DB tables
    apiClient.get(API_CONFIG.ENDPOINTS.DATA_QUALITY_TABLES)
      .then((d) => setAvailableTables(d.tables || []))
      .catch(() => setAvailableTables([]));
    // Load registered folder datasources (backend uses 'local_folder', 'file', not 'folder')
    apiClient.get(API_CONFIG.ENDPOINTS.DATA_SOURCES)
      .then((data) => {
        const FILE_TYPES = new Set(['folder', 'local_folder', 'file', 's3', 'aws_s3', 'azure_blob', 'azure', 'onedrive', 'google_drive']);
        const folders = Array.isArray(data)
          ? data.filter((s) => {
              const t = (s.type || s.source_type || '').toLowerCase();
              return FILE_TYPES.has(t) || !!(s.connection?.folder_path || s.connection?.file_path);
            })
          : [];
        setFolderSources(folders);
      })
      .catch(() => setFolderSources([]));
  }, []);

  const openPicker = () => {
    setScanError(null);
    setScanMode('table');
    setPickerTable('');
    setPickerFolderSourceId('');
    loadTables();
    setTablePickerOpen(true);
  };

  const runScan = useCallback(async () => {
    if (!pickerTable) return;
    setTablePickerOpen(false);
    setScanningTable(pickerTable);
    setScanError(null);
    try {
      await apiClient.post(API_CONFIG.ENDPOINTS.DATA_QUALITY_SCAN(pickerTable), {});
      const refreshed = await apiClient.get(API_CONFIG.ENDPOINTS.DATA_QUALITY_REPORTS);
      if (Array.isArray(refreshed) && refreshed.length > 0) {
        setReports(refreshed.map((r) => ({ ...r, profile: r.profile || { completeness: 80, uniqueness: 100, validity: 80, freshness: 70 }, issues: r.issues || [] })));
        setLiveMode(true);
      }
    } catch (e) {
      const msg = e.message || 'network error';
      setScanError(
        msg === 'Failed to fetch'
          ? 'Cannot reach the backend server. Ensure the server is running and try again.'
          : `Scan request failed: ${msg}`
      );
    }
    setScanningTable(null);
    setPickerTable('');
  }, [pickerTable]);

  const runFolderScan = useCallback(async () => {
    if (!pickerFolderSourceId) return;
    const src = folderSources.find((s) => String(s.id) === String(pickerFolderSourceId));
    const label = src ? (src.name || src.connection?.folder_path || src.connection?.file_path || pickerFolderSourceId) : pickerFolderSourceId;
    setTablePickerOpen(false);
    setScanningTable(label);
    setScanError(null);
    try {
      const data = await apiClient.post(API_CONFIG.ENDPOINTS.AGENTIC_QUALITY_SCAN, { source_id: pickerFolderSourceId, scan_type: 'full', save_report: true });
      // Normalise agentic response into report format
      const r = data?.result || data || {};
      const newReport = {
        scan_id: `folder-${pickerFolderSourceId}-${Date.now()}`,
        table_name: label,
        data_source: 'folder',
        overall_score: r.overall_score != null ? (r.overall_score <= 1 ? r.overall_score * 100 : r.overall_score) : 75,
        rows_scanned: r.rows_scanned || r.total_rows || 0,
        issues_count: r.issues_count || (Array.isArray(r.issues) ? r.issues.length : 0),
        issues: Array.isArray(r.issues) ? r.issues : [],
        scan_date: new Date().toISOString(),
        status: r.status || 'completed',
        profile: {
          completeness: r.completeness != null ? (r.completeness <= 1 ? r.completeness * 100 : r.completeness) : 80,
          uniqueness:   r.uniqueness   != null ? (r.uniqueness   <= 1 ? r.uniqueness   * 100 : r.uniqueness)   : 90,
          validity:     r.validity     != null ? (r.validity     <= 1 ? r.validity     * 100 : r.validity)     : 80,
          freshness:    r.freshness    != null ? (r.freshness    <= 1 ? r.freshness    * 100 : r.freshness)    : 70,
        },
      };
      setReports((prev) => [newReport, ...prev]);
      setLiveMode(true);
    } catch (e) {
      const msg = e.message || 'network error';
      setScanError(
        msg === 'Failed to fetch'
          ? 'Cannot reach the backend server. Ensure the server is running and try again.'
          : `Folder scan request failed: ${msg}`
      );
    }
    setScanningTable(null);
    setPickerFolderSourceId('');
  }, [pickerFolderSourceId, folderSources]);

  // ── Aggregate KPIs ──────────────────────────────────────────────────────────
  const totalRows = reports.reduce((s, r) => s + (r.rows_scanned || 0), 0);
  const totalIssues = reports.reduce((s, r) => s + (r.issues_count || 0), 0);
  const avgScore = reports.length ? (reports.reduce((s, r) => s + (r.overall_score || 0), 0) / reports.length).toFixed(1) : '–';
  const criticalCount = reports.reduce((s, r) => s + r.issues.filter((i) => i.severity === 'critical').reduce((a, i) => a + i.count, 0), 0);
  const todayPrefix = new Date().toISOString().slice(0, 10);
  const scansToday = reports.filter((r) => r.scan_date?.startsWith(todayPrefix));
  const lastRunSub = scansToday.length > 0
    ? 'last run ' + new Date(Math.max(...scansToday.map((r) => new Date(r.scan_date).getTime()))).toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit', hour12: false }) + ' local'
    : 'no scans today';

  const echartsOpts = { renderer: 'canvas' };

  return (
    <div className="dq-dashboard">
      {/* ── AGENT PIPELINE CONTEXT ──────────────────────────────── */}
      <AgentPipelineStrip activeStageName="quality" />

      {/* ── HEADER ──────────────────────────────────────────────── */}
      <div className="dq-header">
        <div className="dq-header-left">
          <div className="dq-header-title">
            <span className="dq-header-icon"><i className="fas fa-shield-alt" /></span>
            <div>
              <h1>Data Quality Scan Dashboard</h1>
              <p>Automated profiling · Rule validation · Anomaly detection</p>
            </div>
          </div>
        </div>
        <div className="dq-header-right">
          {liveMode && <span className="dq-live-badge"><span className="dq-live-dot" />LIVE</span>}
          {scanningTable && <span className="dq-scanning-badge"><i className="fas fa-spinner fa-spin" /> Scanning {scanningTable}…</span>}
          <button
            className="dq-btn dq-btn-secondary"
            onClick={() => {
              const latest = reports[0];
              saveReport({
                report_type: 'dq_scan',
                title: `DQ Scan Summary — ${reports.length} table${reports.length !== 1 ? 's' : ''}`,
                source_page: 'dq-dashboard',
                status: (latest?.overall_score ?? 0) >= 90 ? 'pass' : (latest?.overall_score ?? 0) >= 70 ? 'warning' : 'fail',
                summary: {
                  tables_scanned: reports.length,
                  avg_score: reports.length ? (reports.reduce((s, r) => s + (r.overall_score || 0), 0) / reports.length).toFixed(1) : 0,
                  total_issues: reports.reduce((s, r) => s + (r.issues_count || 0), 0),
                },
                result: { reports: reports.slice(0, 10) },
                tags: ['dq'],
              });
            }}
            disabled={rhSaving || reports.length === 0}
            title="Save to Reporting Hub"
          >
            {rhSaved ? <><i className="fas fa-check" /> Saved</> : <><i className="fas fa-clipboard-list" /> Save Report</>}
          </button>
          <Link to="/reporting-hub" className="dq-btn dq-btn-secondary" title="Reporting Hub">
            <i className="fas fa-clipboard-list" /> Reports
          </Link>
          {reports.length > 0 && (
            <Link to="/lineage" className="dq-btn dq-btn-secondary" title="View data lineage" style={{ textDecoration: 'none' }}>
              <i className="fas fa-stream" /> View Lineage →
            </Link>
          )}
          <button className="dq-btn dq-btn-primary" onClick={openPicker}>
            <i className="fas fa-play" /> Run Scan
          </button>
        </div>
      </div>

      {/* ── SCAN ERROR ──────────────────────────────────────────── */}
      {scanError && (
        <div className="dq-card" style={{ background: '#fef2f2', border: '1px solid #fecaca', color: '#dc2626', padding: '0.75rem 1rem', fontSize: '0.82rem' }}>
          <i className="fas fa-exclamation-circle" /> {scanError}
          <button style={{ float: 'right', background: 'none', border: 'none', cursor: 'pointer', color: '#dc2626' }} onClick={() => setScanError(null)}><i className="fas fa-times" /></button>
        </div>
      )}

      {/* ── KPI STRIP ───────────────────────────────────────────── */}
      <div className="dq-kpi-strip">
        <KpiCard label="Average DQ Score" value={`${avgScore}%`} sub={`${reports.length} tables scanned`} color="#3b82f6" icon={<i className="fas fa-chart-pie" />} />
        <KpiCard label="Total Rows Scanned" value={totalRows.toLocaleString()} sub="across all tables" color="#8b5cf6" icon={<i className="fas fa-table" />} />
        <KpiCard label="Total Issues" value={totalIssues} sub={`${criticalCount} critical`} color={criticalCount > 0 ? '#ef4444' : '#22c55e'} icon={<i className="fas fa-exclamation-triangle" />} />
        <KpiCard label="Scans Today" value={scansToday.length} sub={lastRunSub} color="#22c55e" icon={<i className="fas fa-check-circle" />} />
        <KpiCard label="Critical Issues" value={criticalCount} sub={criticalCount === 0 ? 'All clear' : 'Action required'} color={criticalCount > 0 ? '#ef4444' : '#22c55e'} icon={<i className="fas fa-bug" />} />
      </div>

      {/* ── ROW 1: Trend + Issues donut + Table scores ───────────── */}
      <div className="dq-row">
        <div className="dq-card dq-card-wide">
          <SectionHeader title="DQ Score Trend (7 days)" badge="weekly" />
          <ReactECharts option={buildScoreTrend(history)} style={{ height: 190 }} opts={echartsOpts} />
        </div>
        <div className="dq-card dq-card-narrow">
          <SectionHeader title="Issues by Severity" />
          <ReactECharts option={buildIssuesBySeverity(reports)} style={{ height: 200 }} opts={echartsOpts} />
        </div>
        <div className="dq-card dq-card-narrow">
          <SectionHeader title="Table DQ Scores" />
          <ReactECharts option={buildTableScoreBar(reports)} style={{ height: 200 }} opts={echartsOpts} />
        </div>
      </div>

      {/* ── ROW 2: Dimension heatmap ─────────────────────────────── */}
      <div className="dq-row">
        <div className="dq-card" style={{ flex: 1 }}>
          <SectionHeader title="Quality Dimensions Heatmap" badge="per table" />
          <ReactECharts option={buildDimensionsHeatmap(reports)} style={{ height: 240 }} opts={echartsOpts} />
        </div>
      </div>

      {/* ── ROW 3: Report table ──────────────────────────────────── */}
      <div className="dq-row">
        <div className="dq-card" style={{ flex: 1 }}>
          <SectionHeader title="Scan Reports" badge={`${reports.length} reports`} />
          <div className="dq-table-wrapper">
            <table className="dq-table">
              <thead>
                <tr>
                  <th>Table</th>
                  <th>Source</th>
                  <th>Score</th>
                  <th>Rows</th>
                  <th>Issues</th>
                  <th>Scanned</th>
                  <th>Status</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {reports.map((r) => (
                  <tr key={r.scan_id} className={selected?.scan_id === r.scan_id ? 'dq-row-selected' : ''}>
                    <td><span className="dq-table-name">{r.table_name}</span></td>
                    <td><span className="dq-source-badge">{r.data_source}</span></td>
                    <td>
                      <div className="dq-score-cell">
                        <span className="dq-score-val" style={{ color: scoreColor(r.overall_score) }}>{r.overall_score?.toFixed(1)}%</span>
                        <div className="dq-score-bar">
                          <div className="dq-score-fill" style={{ width: `${r.overall_score}%`, background: scoreColor(r.overall_score) }} />
                        </div>
                      </div>
                    </td>
                    <td>{r.rows_scanned?.toLocaleString()}</td>
                    <td>
                      {r.issues_count > 0
                        ? <span className="dq-issue-count" style={{ background: r.issues.some((i) => i.severity === 'critical') ? '#fef2f2' : '#fffbeb', color: r.issues.some((i) => i.severity === 'critical') ? '#dc2626' : '#d97706' }}>{r.issues_count}</span>
                        : <span className="dq-no-issues">None</span>}
                    </td>
                    <td className="dq-date-cell">{fmtDate(r.scan_date)}</td>
                    <td><span className="dq-status-badge dq-status-completed">{r.status}</span></td>
                    <td>
                      <div style={{ display: 'flex', gap: 6, alignItems: 'center', flexWrap: 'wrap' }}>
                        <button className="dq-detail-btn" onClick={() => setSelected(selected?.scan_id === r.scan_id ? null : r)}>
                          {selected?.scan_id === r.scan_id ? 'Close' : 'Details'}
                        </button>
                        <Link
                          to={`/lineage?table=${encodeURIComponent(r.table_name)}`}
                          className="dq-detail-btn"
                          style={{ textDecoration: 'none', fontSize: 11, display: 'flex', alignItems: 'center', gap: 4 }}
                          title="View data lineage for this table"
                        >
                          <i className="fas fa-stream" style={{ fontSize: 10 }} /> Lineage
                        </Link>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {/* ── DETAIL PANEL ────────────────────────────────────────── */}
      {selected && (
        <div className="dq-detail-panel">
          <div className="dq-detail-header">
            <h3>
              <i className="fas fa-search" /> Scan Detail — <span className="dq-detail-table">{selected.table_name}</span>
            </h3>
            <button className="dq-close-btn" onClick={() => setSelected(null)}><i className="fas fa-times" /></button>
          </div>
          <div className="dq-detail-body">
            {/* Gauge + Radar */}
            <div className="dq-detail-charts">
              <div className="dq-detail-chart-wrap">
                <div className="dq-chart-label">Overall Score</div>
                <ReactECharts option={buildScoreGauge(selected.table_name, selected.overall_score)} style={{ height: 180 }} opts={echartsOpts} />
              </div>
              <div className="dq-detail-chart-wrap">
                <div className="dq-chart-label">Quality Dimensions</div>
                <ReactECharts option={buildDimensionsRadar(selected.profile)} style={{ height: 180 }} opts={echartsOpts} />
              </div>
              {/* Dimension bars */}
              <div className="dq-dimension-bars">
                {[['Completeness', selected.profile.completeness], ['Uniqueness', selected.profile.uniqueness], ['Validity', selected.profile.validity], ['Freshness', selected.profile.freshness]].map(([dim, val]) => (
                  <div key={dim} className="dq-dim-row">
                    <span className="dq-dim-label">{dim}</span>
                    <div className="dq-dim-track">
                      <div className="dq-dim-fill" style={{ width: `${val}%`, background: scoreColor(val) }} />
                    </div>
                    <span className="dq-dim-val" style={{ color: scoreColor(val) }}>{val.toFixed(1)}%</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Issues list */}
            <div className="dq-detail-issues">
              <div className="dq-detail-issues-title">Issues Detected ({selected.issues.length})</div>
              {selected.issues.length === 0
                ? <div className="dq-no-issues-block"><i className="fas fa-check-circle" /> No issues found — this table passed all checks.</div>
                : (
                  <table className="dq-issues-table">
                    <thead><tr><th>Rule</th><th>Column</th><th>Severity</th><th>Count</th></tr></thead>
                    <tbody>
                      {selected.issues.map((iss, idx) => (
                        <tr key={idx}>
                          <td>{iss.rule}</td>
                          <td><code>{iss.column}</code></td>
                          <td><span className="dq-sev-badge" style={{ background: `${severityBadge(iss.severity)}18`, color: severityBadge(iss.severity) }}>{iss.severity}</span></td>
                          <td><b>{iss.count}</b></td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
            </div>
          </div>
        </div>
      )}

      {/* ── TABLE / FOLDER PICKER MODAL ─────────────────────────── */}
      {tablePickerOpen && (
        <div className="dq-modal-overlay" onClick={() => setTablePickerOpen(false)}>
          <div className="dq-modal" onClick={(e) => e.stopPropagation()}>
            <div className="dq-modal-header">
              <h3><i className="fas fa-play-circle" /> Run Quality Scan</h3>
              <button className="dq-close-btn" onClick={() => setTablePickerOpen(false)}><i className="fas fa-times" /></button>
            </div>

            {/* Tab switcher */}
            <div className="dq-modal-tabs">
              <button
                className={`dq-modal-tab${scanMode === 'table' ? ' dq-modal-tab-active' : ''}`}
                onClick={() => setScanMode('table')}
              >
                <i className="fas fa-database" /> Database Table
              </button>
              <button
                className={`dq-modal-tab${scanMode === 'folder' ? ' dq-modal-tab-active' : ''}`}
                onClick={() => setScanMode('folder')}
              >
                <i className="fas fa-folder-open" /> Folder Source
              </button>
            </div>

            <div className="dq-modal-body">
              {scanMode === 'table' ? (
                availableTables.length > 0
                  ? (
                    <select className="dq-select" value={pickerTable} onChange={(e) => setPickerTable(e.target.value)}>
                      <option value="">— choose a table —</option>
                      {availableTables.map((t) => <option key={t} value={t}>{t}</option>)}
                    </select>
                  )
                  : (
                    <input
                      className="dq-input"
                      placeholder="Enter table name e.g. plm_parts"
                      value={pickerTable}
                      onChange={(e) => setPickerTable(e.target.value)}
                    />
                  )
              ) : (
                folderSources.length > 0
                  ? (
                    <select className="dq-select" value={pickerFolderSourceId} onChange={(e) => setPickerFolderSourceId(e.target.value)}>
                      <option value="">— choose a folder source —</option>
                      {folderSources.map((s) => (
                        <option key={s.id} value={s.id}>{s.name || s.connection?.folder_path || s.connection?.file_path || s.id}</option>
                      ))}
                    </select>
                  )
                  : (
                    <div className="dq-modal-empty">
                      <i className="fas fa-folder-open" />
                      <span>No folder datasources registered. Add one via <b>Admin &gt; Datasources</b>.</span>
                    </div>
                  )
              )}
            </div>

            <div className="dq-modal-footer">
              <button className="dq-btn dq-btn-ghost" onClick={() => setTablePickerOpen(false)}>Cancel</button>
              {scanMode === 'table' ? (
                <button className="dq-btn dq-btn-primary" disabled={!pickerTable} onClick={runScan}>
                  <i className="fas fa-play" /> Scan Table
                </button>
              ) : (
                <button className="dq-btn dq-btn-primary" disabled={!pickerFolderSourceId} onClick={runFolderScan}>
                  <i className="fas fa-play" /> Scan Folder
                </button>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
