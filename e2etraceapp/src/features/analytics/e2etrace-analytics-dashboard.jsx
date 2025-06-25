import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { e2etraceProcessGraphDataForAnalytics } from './e2etrace-analytics-processor';
import { E2ETraceUIPanel } from '../../components/e2etrace-ui-panel';
import { EChartsReact } from '../../components/e2etrace-echarts-react';
import { e2etraceFetchWithRetry } from '../../utils/e2etrace-api';
import { e2etraceUseTheme } from '../../contexts/e2etrace-theme-context';
import './e2etrace-analytics-dashboard.css';

const E2ETraceAnalyticsDashboard = () => {
    const [metrics, setMetrics] = useState(null);
    const { theme } = e2etraceUseTheme(); // Get the current theme
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    useEffect(() => {
        const fetchAndProcessData = async () => {
            try {
                // Use the new e2etraceFetchWithRetry function
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

    if (loading) return <div className="analytics-dashboard-loading">Loading analytics...</div>;
    if (error) return <div className="analytics-dashboard-error">Error loading analytics: {error}</div>;
    if (!metrics) return <div className="analytics-dashboard-loading">No metrics to display.</div>;

    // ECharts options objects
    const labelChartOption = {
        tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
        grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
        xAxis: [{
            type: 'category',
            data: Object.keys(metrics.labelCounts),
            axisTick: { alignWithLabel: true },
            axisLabel: { color: 'var(--text-color)' }
        }],
        yAxis: [{ type: 'value', axisLabel: { color: 'var(--text-color)' } }],
        series: [{
            name: 'Node Count',
            type: 'bar',
            barWidth: '60%',
            data: Object.values(metrics.labelCounts),
            itemStyle: { color: 'var(--accent-color)' }
        }],
        backgroundColor: 'transparent'
    };

    const coveragePercentage = (metrics.mappingCoverage.mapped + metrics.mappingCoverage.unmapped) > 0
        ? (metrics.mappingCoverage.mapped / (metrics.mappingCoverage.mapped + metrics.mappingCoverage.unmapped)) * 100
        : 0;

    const mappingCoverageGaugeOption = {
        series: [{
            type: 'gauge',
            startAngle: 180,
            endAngle: 0,
            center: ['50%', '75%'],
            radius: '90%',
            min: 0,
            max: 100,
            splitNumber: 5,
            axisLine: {
                lineStyle: {
                    width: 8,
                    color: [
                        [0.7, '#d32f2f'],
                        [0.9, '#fbc02d'],
                        [1, '#388e3c']
                    ]
                }
            },
            pointer: {
                icon: 'path://M12.8,0.7l12,40.1H0.7L12.8,0.7z',
                length: '12%',
                width: 20,
                offsetCenter: [0, '-60%'],
                itemStyle: { color: 'auto' }
            },
            axisTick: {
                length: 12,
                lineStyle: { color: 'auto', width: 2 }
            },
            splitLine: {
                length: 20,
                lineStyle: { color: 'auto', width: 5 }
            },
            axisLabel: {
                color: 'var(--text-muted-color)',
                fontSize: 14,
                distance: -55,
            },
            title: {
                offsetCenter: [0, '-10%'],
                fontSize: 20,
                color: 'var(--text-color)'
            },
            detail: {
                fontSize: 30,
                offsetCenter: [0, '-35%'],
                valueAnimation: true,
                formatter: (value) => `${Math.round(value)}%`,
                color: 'inherit'
            },
            data: [{
                value: coveragePercentage,
                name: 'Mapping Coverage',
            }]
        }],
        backgroundColor: 'transparent'
    };

    const relationshipChartOption = {
        tooltip: { trigger: 'item' },
        legend: {
            orient: 'vertical',
            left: 'left',
            textStyle: { color: 'var(--text-color)' }
        },
        series: [{
            name: 'Relationship Types',
            type: 'pie',
            radius: '70%',
            data: Object.entries(metrics.relationshipCounts).map(([name, value]) => ({ name, value })),
            emphasis: { itemStyle: { shadowBlur: 10, shadowOffsetX: 0, shadowColor: 'rgba(0, 0, 0, 0.5)' } }
        }],
        backgroundColor: 'transparent'
    };

    return (
        <div className="e2etrace-analytics-dashboard">
            <header>
                <h1>Data Quality & Migration Dashboard</h1>
                <Link to="/">Back to Graph</Link>
            </header>
            <main className="e2etrace-analytics-content">
                <div className="e2etrace-analytics-grid"> {/* Corrected class name */}
                    <E2ETraceUIPanel className="e2etrace-chart-section"> {/* Corrected class name */}
                        <h2>Migration Mapping Coverage</h2>
                        <EChartsReact option={mappingCoverageGaugeOption} style={{ height: '300px' }} theme={theme} />
                    </E2ETraceUIPanel>

                    <E2ETraceUIPanel className="e2etrace-metrics-section"> {/* Corrected class name */}
                        <h2>Key Metrics</h2>
                        <div className="e2etrace-metric-card">Total Data Quality Issues: <strong>{metrics.dataQualityIssues}</strong></div> {/* Corrected class name */}
                        <div className="e2etrace-metric-card">Orphan Target Nodes: <strong>{metrics.orphanTargetNodes.length}</strong></div> {/* Corrected class name */}
                         {metrics.orphanTargetNodes.length > 0 && (
                            <ul className="e2etrace-metric-list"> {/* Corrected class name */}
                                {metrics.orphanTargetNodes.slice(0, 5).map(node => <li key={node.id}>{node.label}</li>)}
                                {metrics.orphanTargetNodes.length > 5 && <li>...and {metrics.orphanTargetNodes.length - 5} more</li>}
                            </ul>
                        )}
                    </E2ETraceUIPanel>

                    <E2ETraceUIPanel className="e2etrace-chart-section e2etrace-full-width-panel"> {/* Corrected class name */}
                        <h2>Node Distribution by Label</h2>
                        <EChartsReact option={labelChartOption} style={{ height: '400px' }} theme={theme} />
                    </E2ETraceUIPanel>

                    <E2ETraceUIPanel className="e2etrace-chart-section"> {/* Corrected class name */}
                        <h2>Relationship Distribution</h2>
                        <EChartsReact option={relationshipChartOption} style={{ height: '300px' }} theme={theme} />
                    </E2ETraceUIPanel>

                    <E2ETraceUIPanel className="e2etrace-metrics-section"> {/* Corrected class name */}
                        <h2>Property-wise Counts</h2>
                        <div className="e2etrace-property-metrics"> {/* Corrected class name */}
                            {Object.entries(metrics.propertyValueCounts).map(([prop, values]) => (
                                <div key={prop} className="e2etrace-property-card"> {/* Corrected class name */}
                                    <h3>{prop}</h3>
                                    <ul>
                                        {Object.entries(values).map(([value, count]) => (
                                            <li key={value}>
                                                <span>{value}:</span> <strong>{count}</strong>
                                            </li>
                                        ))}
                                    </ul>
                                </div>
                            ))}
                        </div>
                    </E2ETraceUIPanel>
                </div>
            </main>
        </div>
    );
};

export default E2ETraceAnalyticsDashboard;