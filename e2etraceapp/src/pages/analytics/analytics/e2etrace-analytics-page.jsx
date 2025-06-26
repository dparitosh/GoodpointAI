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

const Widget = ({ title, children, className }) => (
  <div className={`dashboard-widget ${className || ''}`}>
    <div className="dashboard-widget-header">{title}</div>
    <div className="dashboard-widget-content">{children}</div>
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
        <div className="e2etrace-analytics-page dashboard-widgets-layout">
            <h1>Graph Analytics Dashboard</h1>
            {error && <E2ETraceUIPanel><div className="e2etrace-analytics-page-error">Error loading analytics: {error}</div></E2ETraceUIPanel>}
            {!error && !loading && !metrics && <E2ETraceUIPanel><div className="e2etrace-analytics-page-no-data">No metrics to display.</div></E2ETraceUIPanel>}
            {!error && (
            <div className="dashboard-widgets-row">
                <Widget title="Migration Mapping Coverage" className="chart-widget">
                    <EChartsReact option={mappingCoverageGaugeOption || {}} style={{ height: '300px' }} theme={theme} showLoading={loading} />
                </Widget>
                <Widget title="Node Status Distribution" className="chart-widget">
                    <EChartsReact option={statusDistributionChartOption || {}} style={{ height: '300px' }} theme={theme} showLoading={loading} />
                </Widget>
                <Widget title="Node Distribution by System" className="chart-widget">
                    <EChartsReact option={labelChartOption || {}} style={{ height: '300px' }} theme={theme} showLoading={loading} />
                </Widget>
                <Widget title="Relationship Distribution" className="chart-widget">
                    <EChartsReact option={relationshipChartOption || {}} style={{ height: '300px' }} theme={theme} showLoading={loading} />
                </Widget>
            </div>
            )}
            {!error && metrics && (
            <div className="dashboard-widgets-row">
                <Widget title="Key Metrics" className="metrics-widget">
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
                <Widget title="Property-wise Counts" className="property-widget">
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