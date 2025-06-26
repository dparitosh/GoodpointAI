import React, { useState, useEffect, useMemo, useCallback } from 'react';
import ReactECharts from 'echarts-for-react';
import * as XLSX from 'xlsx';
import { saveAs } from 'file-saver';
import { applyETLFilter, highlightPerformanceIssues, calculatePipelineMetrics } from '../utils/e2etrace-graph-enhancement.js';
import './e2etrace-enhanced-etl-overview.css';

// Helper functions defined outside component to avoid hoisting issues
const generateTimeSeriesData = (range) => {
  const hours = range === '24h' ? 24 : range === '7d' ? 168 : 720;
  const interval = hours <= 24 ? 1 : hours <= 168 ? 4 : 24;
  const data = [];
  
  for (let i = 0; i < hours; i += interval) {
    const timestamp = new Date(Date.now() - (hours - i) * 60 * 60 * 1000);
    data.push({
      time: timestamp.toISOString(),
      throughput: 1000 + Math.random() * 3000,
      latency: 50 + Math.random() * 150,
      errorRate: Math.random() * 5,
      successRate: 95 + Math.random() * 5
    });
  }
  return data;
};

const generatePerformanceTrends = () => {
  return [
    { metric: 'Throughput', current: 2850, target: 3000, trend: 'up', unit: 'records/min' },
    { metric: 'Latency', current: 125, target: 100, trend: 'down', unit: 'ms' },
    { metric: 'Success Rate', current: 97.8, target: 98.5, trend: 'up', unit: '%' },
    { metric: 'Data Quality', current: 94.2, target: 95.0, trend: 'up', unit: '%' }
  ];
};

const EnhancedETLOverview = ({ 
  graphStats, 
  selectedNodeCount, 
  filteredNodeCount, 
  loadingError,
  graphData,
  onElementClick,
  onFilterApply,
  cytoscapeRef
}) => {
  const [activeTab, setActiveTab] = useState('dashboard');
  const [expanded, setExpanded] = useState(false);
  const [activeFilter, setActiveFilter] = useState(null);
  const [timeRange, setTimeRange] = useState('24h');

  // Enhanced ETL metrics with time-series data
  const etlMetrics = useMemo(() => {
    if (!graphData || !graphData.nodes) {
      return {
        sources: 0,
        transformations: 0,
        destinations: 0,
        pipelines: 0,
        successRate: 0,
        throughput: 0,
        latency: 0,
        errorRate: 0,
        pipelineMetrics: {},
        timeSeriesData: [],
        nodeTypeDistribution: [],
        performanceTrends: []
      };
    }

    let pipelineMetrics = {};
    try {
      pipelineMetrics = calculatePipelineMetrics(graphData);
    } catch (error) {
      console.warn('Error calculating pipeline metrics:', error);
      pipelineMetrics = {
        totalPipelines: 1,
        avgPipelineLength: 0,
        longestPipeline: 0,
        shortestPipeline: 0,
        pipelineEfficiency: 0
      };
    }

    // Categorize nodes by ETL stage
    const sources = graphData.nodes.filter(node => {
      const data = node.data || node;
      return data.type === 'source' || 
             data.category === 'input' ||
             data.group === 'Source' ||
             (data.label && data.label.toLowerCase().includes('source'));
    });
    
    const transformations = graphData.nodes.filter(node => {
      const data = node.data || node;
      return data.type === 'processor' || 
             data.category === 'transformation' ||
             data.group === 'Processor' ||
             (data.label && data.label.toLowerCase().includes('transform'));
    });
    
    const destinations = graphData.nodes.filter(node => {
      const data = node.data || node;
      return data.type === 'destination' || 
             data.category === 'output' ||
             data.group === 'Destination' ||
             (data.label && data.label.toLowerCase().includes('destination'));
    });

    // Generate mock time-series data
    const timeSeriesData = generateTimeSeriesData(timeRange);
    
    // Generate node type distribution for pie chart
    const nodeTypeDistribution = [
      { name: 'Sources', value: sources.length, color: '#007bff' },
      { name: 'Transformations', value: transformations.length, color: '#28a745' },
      { name: 'Destinations', value: destinations.length, color: '#17a2b8' },
      { name: 'Others', value: Math.max(0, graphData.nodes.length - sources.length - transformations.length - destinations.length), color: '#6c757d' }
    ].filter(item => item.value > 0);

    // Generate performance trends
    const performanceTrends = generatePerformanceTrends();

    // Mock performance metrics
    const successRate = 95.2 + Math.random() * 4.8;
    const throughput = Math.floor(1000 + Math.random() * 5000);
    const latency = Math.floor(50 + Math.random() * 200);
    const errorRate = 100 - successRate;

    return {
      sources: sources.length,
      transformations: transformations.length,
      destinations: destinations.length,
      pipelines: pipelineMetrics.totalPipelines,
      successRate: successRate.toFixed(1),
      throughput,
      latency,
      errorRate: errorRate.toFixed(1),
      pipelineMetrics,
      timeSeriesData,
      nodeTypeDistribution,
      performanceTrends
    };
  }, [graphData, timeRange]);

  // ECharts configurations
  const getTimeSeriesChartOption = () => ({
    title: {
      text: 'Pipeline Performance Over Time',
      left: 'center',
      textStyle: { fontSize: 14, fontWeight: 'bold' }
    },
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross' }
    },
    legend: {
      data: ['Throughput', 'Success Rate', 'Latency'],
      bottom: 10
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '15%',
      containLabel: true
    },
    xAxis: {
      type: 'time',
      boundaryGap: false
    },
    yAxis: [
      {
        type: 'value',
        name: 'Throughput / Success Rate',
        position: 'left'
      },
      {
        type: 'value',
        name: 'Latency (ms)',
        position: 'right'
      }
    ],
    series: [
      {
        name: 'Throughput',
        type: 'line',
        data: etlMetrics.timeSeriesData.map(d => [d.time, d.throughput]),
        smooth: true,
        itemStyle: { color: '#007bff' }
      },
      {
        name: 'Success Rate',
        type: 'line',
        data: etlMetrics.timeSeriesData.map(d => [d.time, d.successRate]),
        smooth: true,
        itemStyle: { color: '#28a745' }
      },
      {
        name: 'Latency',
        type: 'line',
        yAxisIndex: 1,
        data: etlMetrics.timeSeriesData.map(d => [d.time, d.latency]),
        smooth: true,
        itemStyle: { color: '#dc3545' }
      }
    ]
  });

  const getPieChartOption = () => ({
    title: {
      text: 'Node Type Distribution',
      left: 'center',
      textStyle: { fontSize: 14, fontWeight: 'bold' }
    },
    tooltip: {
      trigger: 'item',
      formatter: '{a} <br/>{b}: {c} ({d}%)'
    },
    legend: {
      orient: 'vertical',
      left: 'left'
    },
    series: [
      {
        name: 'Node Types',
        type: 'pie',
        radius: ['40%', '70%'],
        avoidLabelOverlap: false,
        data: etlMetrics.nodeTypeDistribution,
        emphasis: {
          itemStyle: {
            shadowBlur: 10,
            shadowOffsetX: 0,
            shadowColor: 'rgba(0, 0, 0, 0.5)'
          }
        }
      }
    ]
  });

  const getBarChartOption = () => ({
    title: {
      text: 'Performance Metrics vs Targets',
      left: 'center',
      textStyle: { fontSize: 14, fontWeight: 'bold' }
    },
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' }
    },
    legend: {
      data: ['Current', 'Target'],
      bottom: 10
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '15%',
      containLabel: true
    },
    xAxis: {
      type: 'category',
      data: etlMetrics.performanceTrends.map(t => t.metric)
    },
    yAxis: {
      type: 'value'
    },
    series: [
      {
        name: 'Current',
        type: 'bar',
        data: etlMetrics.performanceTrends.map(t => ({
          value: t.current,
          itemStyle: { color: t.trend === 'up' ? '#28a745' : '#dc3545' }
        }))
      },
      {
        name: 'Target',
        type: 'bar',
        data: etlMetrics.performanceTrends.map(t => t.target),
        itemStyle: { color: '#6c757d', opacity: 0.6 }
      }
    ]
  });

  // Excel export functionality
  const exportToExcel = useCallback(() => {
    const workbook = XLSX.utils.book_new();
    
    // ETL Overview Sheet
    const overviewData = [
      ['Metric', 'Value', 'Status'],
      ['Sources', etlMetrics.sources, 'Active'],
      ['Transformations', etlMetrics.transformations, 'Active'],
      ['Destinations', etlMetrics.destinations, 'Active'],
      ['Total Pipelines', etlMetrics.pipelines, 'Running'],
      ['Success Rate (%)', etlMetrics.successRate, parseFloat(etlMetrics.successRate) > 95 ? 'Good' : 'Warning'],
      ['Throughput (records/hour)', etlMetrics.throughput, 'Normal'],
      ['Average Latency (ms)', etlMetrics.latency, etlMetrics.latency < 100 ? 'Good' : 'Warning'],
      ['Error Rate (%)', etlMetrics.errorRate, parseFloat(etlMetrics.errorRate) < 5 ? 'Good' : 'Critical']
    ];
    
    const overviewSheet = XLSX.utils.aoa_to_sheet(overviewData);
    XLSX.utils.book_append_sheet(workbook, overviewSheet, 'ETL Overview');
    
    // Time Series Data Sheet
    const timeSeriesHeaders = ['Timestamp', 'Throughput', 'Latency (ms)', 'Error Rate (%)', 'Success Rate (%)'];
    const timeSeriesData = [
      timeSeriesHeaders,
      ...etlMetrics.timeSeriesData.map(d => [
        new Date(d.time).toLocaleString(),
        d.throughput.toFixed(0),
        d.latency.toFixed(2),
        d.errorRate.toFixed(2),
        d.successRate.toFixed(2)
      ])
    ];
    
    const timeSeriesSheet = XLSX.utils.aoa_to_sheet(timeSeriesData);
    XLSX.utils.book_append_sheet(workbook, timeSeriesSheet, 'Time Series Data');
    
    // Node Distribution Sheet
    const nodeDistHeaders = ['Node Type', 'Count', 'Percentage'];
    const total = etlMetrics.nodeTypeDistribution.reduce((sum, item) => sum + item.value, 0);
    const nodeDistData = [
      nodeDistHeaders,
      ...etlMetrics.nodeTypeDistribution.map(d => [
        d.name,
        d.value,
        ((d.value / total) * 100).toFixed(1) + '%'
      ])
    ];
    
    const nodeDistSheet = XLSX.utils.aoa_to_sheet(nodeDistData);
    XLSX.utils.book_append_sheet(workbook, nodeDistSheet, 'Node Distribution');
    
    // Performance Trends Sheet
    const perfHeaders = ['Metric', 'Current Value', 'Target Value', 'Trend', 'Unit'];
    const perfData = [
      perfHeaders,
      ...etlMetrics.performanceTrends.map(t => [
        t.metric,
        t.current,
        t.target,
        t.trend,
        t.unit
      ])
    ];
    
    const perfSheet = XLSX.utils.aoa_to_sheet(perfData);
    XLSX.utils.book_append_sheet(workbook, perfSheet, 'Performance Trends');
    
    // Generate and save file
    const excelBuffer = XLSX.write(workbook, { bookType: 'xlsx', type: 'array' });
    const data = new Blob([excelBuffer], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' });
    const fileName = `ETL_Overview_${new Date().toISOString().split('T')[0]}.xlsx`;
    saveAs(data, fileName);
  }, [etlMetrics]);

  // Filter handling functions
  const handleMetricClick = (metricType, value) => {
    if (!cytoscapeRef?.current || value <= 0) return;

    if (activeFilter === metricType) {
      cytoscapeRef.current.elements().removeClass('filtered-out highlighted etl-filtered');
      setActiveFilter(null);
      return;
    }

    const result = applyETLFilter(cytoscapeRef.current, metricType, {
      hideOthers: false,
      autoFit: true
    });

    setActiveFilter(metricType);

    if (onFilterApply) {
      onFilterApply({ 
        type: metricType, 
        result: result,
        active: true 
      });
    }
  };

  const clearAllFilters = () => {
    if (!cytoscapeRef?.current) return;
    
    cytoscapeRef.current.elements().removeClass(
      'filtered-out highlighted etl-filtered performance-issue high-latency low-throughput high-error'
    );
    setActiveFilter(null);
  };

  const MetricCard = ({ title, value, color, subtitle, trend, clickable = false, onClick, isActive = false }) => (
    <div 
      className={`etl-metric-card ${clickable ? 'clickable' : ''} ${isActive ? 'active' : ''}`}
      onClick={clickable ? onClick : undefined}
      style={{ borderLeft: `4px solid ${color}` }}
    >
      <div className="metric-header">
        <span className="metric-title">{title}</span>
        {trend && (
          <span className={`metric-trend ${trend > 0 ? 'positive' : 'negative'}`}>
            {trend > 0 ? '↗' : '↘'} {Math.abs(trend)}%
          </span>
        )}
      </div>
      <div className="metric-value" style={{ color }}>{value}</div>
      {subtitle && <div className="metric-subtitle">{subtitle}</div>}
      {isActive && (
        <div className="active-indicator">
          <span>Filtered</span>
        </div>
      )}
    </div>
  );

  return (
    <div className={`enhanced-etl-overview ${expanded ? 'expanded' : ''}`}>
      <div className="etl-header">
        <div className="etl-title">
          <h3>Enhanced ETL Pipeline Overview</h3>
          <div className="time-range-selector">
            <select value={timeRange} onChange={(e) => setTimeRange(e.target.value)}>
              <option value="24h">Last 24 Hours</option>
              <option value="7d">Last 7 Days</option>
              <option value="30d">Last 30 Days</option>
            </select>
          </div>
        </div>
        <div className="etl-controls">
          <button 
            className={`tab-button ${activeTab === 'dashboard' ? 'active' : ''}`}
            onClick={() => setActiveTab('dashboard')}
          >
            Dashboard
          </button>
          <button 
            className={`tab-button ${activeTab === 'charts' ? 'active' : ''}`}
            onClick={() => setActiveTab('charts')}
          >
            Analytics
          </button>
          <button 
            className={`tab-button ${activeTab === 'export' ? 'active' : ''}`}
            onClick={() => setActiveTab('export')}
          >
            Export
          </button>
          <button 
            className="export-button"
            onClick={exportToExcel}
            title="Export to Excel"
          >
            📊 Excel
          </button>
          <button 
            className="expand-button"
            onClick={() => setExpanded(!expanded)}
            title={expanded ? 'Collapse' : 'Expand'}
          >
            {expanded ? '−' : '+'}
          </button>
          {activeFilter && (
            <button 
              className="clear-filter-button"
              onClick={clearAllFilters}
              title="Clear Filters"
            >
              ✕
            </button>
          )}
        </div>
      </div>

      <div className="etl-content">
        {activeTab === 'dashboard' && (
          <div className="dashboard-content">
            <div className="metrics-grid">
              <MetricCard
                title="Sources"
                value={etlMetrics.sources}
                color="#007bff"
                subtitle="Data Inputs"
                clickable={true}
                onClick={() => handleMetricClick('source', etlMetrics.sources)}
                isActive={activeFilter === 'source'}
              />
              <MetricCard
                title="Transformations"
                value={etlMetrics.transformations}
                color="#28a745"
                subtitle="Processing Steps"
                clickable={true}
                onClick={() => handleMetricClick('processor', etlMetrics.transformations)}
                isActive={activeFilter === 'processor'}
              />
              <MetricCard
                title="Destinations"
                value={etlMetrics.destinations}
                color="#17a2b8"
                subtitle="Data Outputs"
                clickable={true}
                onClick={() => handleMetricClick('destination', etlMetrics.destinations)}
                isActive={activeFilter === 'destination'}
              />
              <MetricCard
                title="Active Pipelines"
                value={etlMetrics.pipelines}
                color="#6f42c1"
                subtitle="Running Flows"
              />
              <MetricCard
                title="Success Rate"
                value={`${etlMetrics.successRate}%`}
                color={parseFloat(etlMetrics.successRate) > 95 ? '#28a745' : '#ffc107'}
                subtitle="Last 24 Hours"
                trend={2.1}
              />
              <MetricCard
                title="Throughput"
                value={`${etlMetrics.throughput.toLocaleString()}`}
                color="#007bff"
                subtitle="Records/Hour"
                trend={5.3}
              />
            </div>
            
            {/* Quick Performance Summary */}
            <div className="performance-summary">
              <h4>Performance Summary</h4>
              <div className="summary-grid">
                {etlMetrics.performanceTrends.map((trend, index) => (
                  <div key={index} className="summary-item">
                    <div className="summary-metric">{trend.metric}</div>
                    <div className="summary-values">
                      <span className="current-value">{trend.current} {trend.unit}</span>
                      <span className={`trend-indicator ${trend.trend}`}>
                        {trend.trend === 'up' ? '↗' : '↘'}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {activeTab === 'charts' && (
          <div className="charts-content">
            <div className="charts-grid">
              <div className="chart-container">
                <ReactECharts option={getTimeSeriesChartOption()} style={{ height: '300px' }} />
              </div>
              <div className="chart-container">
                <ReactECharts option={getPieChartOption()} style={{ height: '300px' }} />
              </div>
              <div className="chart-container full-width">
                <ReactECharts option={getBarChartOption()} style={{ height: '300px' }} />
              </div>
            </div>
          </div>
        )}

        {activeTab === 'export' && (
          <div className="export-content">
            <div className="export-options">
              <h4>Export Options</h4>
              <div className="export-buttons">
                <button className="export-btn excel" onClick={exportToExcel}>
                  📊 Export to Excel
                  <span>Complete ETL metrics with charts data</span>
                </button>
                <button className="export-btn pdf" onClick={() => window.print()}>
                  📄 Export to PDF
                  <span>Print current dashboard view</span>
                </button>
                <button className="export-btn json" onClick={() => {
                  const dataStr = JSON.stringify(etlMetrics, null, 2);
                  const dataBlob = new Blob([dataStr], {type: 'application/json'});
                  saveAs(dataBlob, `ETL_Data_${new Date().toISOString().split('T')[0]}.json`);
                }}>
                  🔧 Export Raw Data
                  <span>JSON format for API integration</span>
                </button>
              </div>
            </div>
            
            <div className="export-preview">
              <h4>Export Preview</h4>
              <div className="preview-content">
                <div className="preview-item">
                  <strong>ETL Overview:</strong> {Object.keys(etlMetrics).length} metrics
                </div>
                <div className="preview-item">
                  <strong>Time Series:</strong> {etlMetrics.timeSeriesData.length} data points
                </div>
                <div className="preview-item">
                  <strong>Node Distribution:</strong> {etlMetrics.nodeTypeDistribution.length} categories
                </div>
                <div className="preview-item">
                  <strong>Performance Trends:</strong> {etlMetrics.performanceTrends.length} metrics
                </div>
              </div>
            </div>
          </div>
        )}

        {loadingError && (
          <div className="etl-error">
            <div className="error-icon">⚠</div>
            <div className="error-content">
              <strong>Pipeline Error:</strong> {loadingError}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default EnhancedETLOverview;
