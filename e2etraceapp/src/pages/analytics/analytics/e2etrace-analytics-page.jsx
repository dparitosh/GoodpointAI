import React, { useEffect, useState, useMemo } from 'react';
import { e2etraceProcessGraphDataForAnalytics } from './e2etrace-analytics-processor';
import { E2ETraceUIPanel } from '../../../components/e2etrace-ui-panel';
import { EChartsReact } from '../../../components/e2etrace-echarts-react';
import { e2etraceFetchWithRetry } from '../../../api/e2etrace-api';
import { e2etraceUseTheme } from '../../../contexts/e2etrace-theme-context';
import {
    getLabelChartOption,
    getMappingCoverageGaugeOption,
    getStatusDistributionChartOption,
    getRelationshipChartOption
} from './e2etrace-analytics-charts';
import './e2etrace-analytics-page.css';


// --- Unified Widget Component for All Pages ---
const Widget = ({ title, children, className, style, subheader }) => (
  <div className={`dashboard-widget ${className || ''}`} style={style}>
    <div className="dashboard-widget-header" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '1rem', padding: '0.75rem 1.5rem', borderBottom: '1px solid #e0e4ea', background: '#f4f7fb', fontWeight: 600, fontSize: '1.1rem' }}>
      <span>{title}</span>
    </div>
    {subheader && (
      <div className="dashboard-widget-subheader" style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', padding: '0.5rem 1.5rem', borderBottom: '1px solid #e0e4ea', background: '#f8fafd' }}>
        {Array.isArray(subheader)
          ? subheader.map((child, idx) => (
              <div className="dashboard-widget-subheader-item" key={idx} style={{ display: 'flex', alignItems: 'center' }}>{child}</div>
            ))
          : <div className="dashboard-widget-subheader-item">{subheader}</div>
        }
      </div>
    )}
    <div className="dashboard-widget-content" style={{ padding: '1.5rem', background: '#fff', borderRadius: '0 0 12px 12px', boxShadow: '0 2px 8px rgba(30,40,90,0.06)' }}>{children}</div>
  </div>
);

export function E2ETraceAnalyticsPage() {
    const [metrics, setMetrics] = useState(null);
    const { theme } = e2etraceUseTheme();
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    useEffect(() => {
        const fetchAndProcessData = async () => {
            try {
                const response = await e2etraceFetchWithRetry('/api/graph');
                const graphData = await response.json();
                const processedMetrics = e2etraceProcessGraphDataForAnalytics(graphData);
                setMetrics(processedMetrics);
            } catch (e) {
                setError(e.message);
            } finally {
                setLoading(false);
            }
        };
        fetchAndProcessData();
    }, []);

    // Memoize chart options to prevent recalculation on every render
    const labelChartOption = useMemo(() => getLabelChartOption(metrics, theme), [metrics, theme]);
    const mappingCoverageGaugeOption = useMemo(() => getMappingCoverageGaugeOption(metrics, theme), [metrics, theme]);
    const statusDistributionChartOption = useMemo(() => getStatusDistributionChartOption(metrics, theme), [metrics, theme]);
    const relationshipChartOption = useMemo(() => getRelationshipChartOption(metrics, theme), [metrics, theme]);

    return (
        <div className="e2etrace-analytics-page dashboard-widgets-layout" style={{ padding: '2rem', background: '#f0f2f8', minHeight: '100vh' }}>
            <h1 style={{ marginBottom: '2rem' }}>Graph Analytics Dashboard</h1>
            {error && <Widget title="Error" className="error-widget"><div className="e2etrace-analytics-page-error">Error loading analytics: {error}</div></Widget>}
            {!error && !loading && !metrics && <Widget title="No Data" className="no-data-widget"><div className="e2etrace-analytics-page-no-data">No metrics to display.</div></Widget>}
            {!error && (
            <div className="dashboard-widgets-row" style={{ display: 'flex', flexWrap: 'wrap', gap: '2rem', marginBottom: '2rem' }}>
                <Widget title="Migration Mapping Coverage" className="chart-widget" style={{ flex: 1, minWidth: 320 }}>
                    <EChartsReact option={mappingCoverageGaugeOption || {}} style={{ height: '300px' }} theme={theme} showLoading={loading} />
                </Widget>
                <Widget title="Node Status Distribution" className="chart-widget" style={{ flex: 1, minWidth: 320 }}>
                    <EChartsReact option={statusDistributionChartOption || {}} style={{ height: '300px' }} theme={theme} showLoading={loading} />
                </Widget>
                <Widget title="Node Distribution by System" className="chart-widget" style={{ flex: 1, minWidth: 320 }}>
                    <EChartsReact option={labelChartOption || {}} style={{ height: '300px' }} theme={theme} showLoading={loading} />
                </Widget>
                <Widget title="Relationship Distribution" className="chart-widget" style={{ flex: 1, minWidth: 320 }}>
                    <EChartsReact option={relationshipChartOption || {}} style={{ height: '300px' }} theme={theme} showLoading={loading} />
                </Widget>
            </div>
            )}
            {!error && metrics && (
            <div className="dashboard-widgets-row" style={{ display: 'flex', gap: '2rem' }}>
                <Widget title="Key Metrics" className="metrics-widget" style={{ flex: 1, minWidth: 320 }}>
                    {loading ? <p>Loading metrics...</p> : (
                        <>
                            <div className="e2etrace-metric-card">Total Data Quality Issues: <strong>{metrics.dataQualityIssues}</strong></div>
                            <div className="e2etrace-metric-card">Orphan Target Nodes: <strong>{metrics.orphanTargetNodes.length}</strong></div>
                            {metrics.orphanTargetNodes.length > 0 && (
                                <ul className="e2etrace-metric-list">
                                    {metrics.orphanTargetNodes.slice(0, 5).map(node => <li key={node._uniqueKey || node.id}>{node.label}</li>)}
                                    {metrics.orphanTargetNodes.length > 5 && <li>...and {metrics.orphanTargetNodes.length - 5} more</li>}
                                </ul>
                            )}
                        </>
                    )}
                </Widget>
                <Widget title="Property-wise Counts" className="property-widget" style={{ flex: 2, minWidth: 320 }}>
                    {loading ? <p>Loading counts...</p> : metrics && (
                        <div className="e2etrace-property-metrics">
                            {Object.entries(metrics.propertyValueCounts).map(([prop, values]) => (
                                <div key={prop} className="e2etrace-property-card">
                                    <h3>{prop}</h3>
                                    <ul>
                                        {Object.entries(values).map(([value, count]) => (
                                            <li key={value}><span>{value}:</span> <strong>{count}</strong></li>
                                        ))}
                                    </ul>
                                </div>
                            ))}
                        </div>
                    )}
                </Widget>
            </div>
            )}
        </div>
    );
}