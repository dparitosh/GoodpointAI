import React, { useEffect, useState, useMemo } from 'react';
import { e2etraceProcessGraphDataForAnalytics } from './e2etrace-analytics-processor';
import { E2ETraceUIPanel } from '../../components/e2etrace-ui-panel';
import { EChartsReact } from '../../components/e2etrace-echarts-react';
import { e2etraceFetchWithRetry } from '../../utils/e2etrace-api';
import { E2ETraceTabs } from '../../components/e2etrace-tabs';
import { e2etraceUseTheme } from '../../contexts/e2etrace-theme-context';
import {
    getLabelChartOption,
    getMappingCoverageGaugeOption,
    getStatusDistributionChartOption,
    getRelationshipChartOption
} from './e2etrace-analytics-charts';
import './e2etrace-analytics-page.css'; // New CSS file for the page

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
        <div className="e2etrace-analytics-page">
            <h1>Graph Analytics</h1>
            {error && <E2ETraceUIPanel><div className="e2etrace-analytics-page-error">Error loading analytics: {error}</div></E2ETraceUIPanel>}
            {!error && !loading && !metrics && <E2ETraceUIPanel><div className="e2etrace-analytics-page-no-data">No metrics to display.</div></E2ETraceUIPanel>}
            {/* Render the main layout but pass loading state to children */}
            { !error && (
            <E2ETraceTabs
                tabs={[
                    {
                        label: 'Migration & Data Quality',
                        content: (
                            <div className="e2etrace-analytics-grid">
                                <E2ETraceUIPanel className="e2etrace-chart-section">
                                    <h2>Migration Mapping Coverage</h2>
                                    <EChartsReact option={mappingCoverageGaugeOption || {}} style={{ height: '300px' }} theme={theme} showLoading={loading} />
                                </E2ETraceUIPanel>
                                {statusDistributionChartOption && (
                                    <E2ETraceUIPanel className="e2etrace-chart-section">
                                        <h2>Node Status Distribution</h2>
                                        <EChartsReact option={statusDistributionChartOption} style={{ height: '300px' }} theme={theme} showLoading={loading} />
                                    </E2ETraceUIPanel>
                                )}
                                <E2ETraceUIPanel className="e2etrace-metrics-section">
                                    <h2>Key Metrics</h2>
                                    {loading ? <p>Loading metrics...</p> : metrics && (
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
                                </E2ETraceUIPanel>
                            </div>
                        ),
                    },
                    {
                        label: 'Graph Overview',
                        content: (
                            <div className="e2etrace-analytics-grid">
                                <E2ETraceUIPanel className="e2etrace-chart-section e2etrace-full-width-panel">
                                    <h2>Node Distribution by System</h2>
                                    <EChartsReact option={labelChartOption || {}} style={{ height: '400px' }} theme={theme} showLoading={loading} />
                                </E2ETraceUIPanel>
                                <E2ETraceUIPanel className="e2etrace-chart-section">
                                    <h2>Relationship Distribution</h2>
                                    <EChartsReact option={relationshipChartOption || {}} style={{ height: '300px' }} theme={theme} showLoading={loading} />
                                </E2ETraceUIPanel>
                                <E2ETraceUIPanel className="e2etrace-metrics-section">
                                    <h2>Property-wise Counts</h2>
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
                                </E2ETraceUIPanel>
                            </div>
                        ),
                    },
                ]}
            />
            )}
        </div>
    );
}