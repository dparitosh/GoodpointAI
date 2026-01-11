import React, { useState, useEffect, useMemo } from 'react';
import { applyETLFilter, highlightPerformanceIssues, calculatePipelineMetrics } from '../utils/e2etrace-graph-enhancement.js';
import { e2etraceFetchWithRetry } from '../api/e2etrace-api';
import './e2etrace-etl-overview.css';

const ETLOverview = ({ 
  graphStats, 
  selectedNodeCount, 
  filteredNodeCount, 
  loadingError,
  graphData,
  onElementClick: _onElementClick,
  onFilterApply,
  cytoscapeRef
}) => {
  const [activeTab, setActiveTab] = useState('metrics');
  const [expanded, setExpanded] = useState(false);
  const [activeFilter, setActiveFilter] = useState(null);
  const [qualityData, setQualityData] = useState({
    totalRecords: '0',
    validRecords: '0',
    duplicates: '0',
    nullValues: '0',
    qualityScore: '0.0'
  });

  // Load data quality metrics from API
  useEffect(() => {
    const fetchDataQuality = async () => {
      try {
        const response = await e2etraceFetchWithRetry('/api/monitoring/data-quality');
        const data = await response.json();
        setQualityData({
          totalRecords: data.totalRecords?.toLocaleString() || '0',
          validRecords: data.validRecords?.toLocaleString() || '0',
          duplicates: data.duplicates?.toLocaleString() || '0',
          nullValues: data.nullValues?.toLocaleString() || '0',
          qualityScore: data.qualityScore?.toFixed(1) || '0.0'
        });
      } catch (error) {
        console.error('Error fetching data quality metrics:', error);
        // Fallback to calculated values from graph data
        if (graphData && graphData.nodes) {
          const totalNodes = graphData.nodes.length;
          const validNodes = graphData.nodes.filter(n => n.data && n.data.id).length;
          const duplicateNodes = graphData.nodes.filter(n => n.data && n.data.status === 'duplicate').length;
          const nullNodes = graphData.nodes.filter(n => n.data && Object.values(n.data).some(v => v === null || v === undefined)).length;
          
          setQualityData({
            totalRecords: totalNodes.toLocaleString(),
            validRecords: validNodes.toLocaleString(),
            duplicates: duplicateNodes.toLocaleString(),
            nullValues: nullNodes.toLocaleString(),
            qualityScore: ((validNodes / Math.max(totalNodes, 1)) * 100).toFixed(1)
          });
        }
      }
    };

    fetchDataQuality();
  }, [graphData]);

  // Enhanced ETL metrics calculated from graph data
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
        pipelineMetrics: {}
      };
    }

    let pipelineMetrics = {};
    try {
      // Use enhanced pipeline metrics calculation
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

    // Mock performance metrics (in real app, these would come from monitoring data)
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
      pipelineMetrics
    };
  }, [graphData]);

  const handleMetricClick = (metricType, value) => {
    if (!cytoscapeRef?.current || value <= 0) return;

    // Clear previous filter if clicking the same metric
    if (activeFilter === metricType) {
      cytoscapeRef.current.elements().removeClass('filtered-out highlighted etl-filtered');
      setActiveFilter(null);
      return;
    }

    // Apply ETL-specific filter
    const result = applyETLFilter(cytoscapeRef.current, metricType, {
      hideOthers: false,
      autoFit: true
    });

    setActiveFilter(metricType);

    // Notify parent component if callback provided
    if (onFilterApply) {
      onFilterApply({ 
        type: metricType, 
        result: result,
        active: true 
      });
    }
  };

  const handlePerformanceHighlight = () => {
    if (!cytoscapeRef?.current) return;

    highlightPerformanceIssues(cytoscapeRef.current, {
      maxLatency: etlMetrics.latency * 1.5,
      minThroughput: etlMetrics.throughput * 0.5,
      maxErrorRate: parseFloat(etlMetrics.errorRate) + 2
    });
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
            {trend > 0 ? <i className="fas fa-arrow-up" aria-hidden="true" /> : <i className="fas fa-arrow-down" aria-hidden="true" />} {Math.abs(trend)}%
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

  const StatusIndicator = ({ status, label }) => {
    const getStatusColor = (status) => {
      switch (status) {
        case 'healthy': return '#28a745';
        case 'warning': return '#ffc107';
        case 'error': return '#dc3545';
        default: return '#6c757d';
      }
    };

    return (
      <div className="status-indicator">
        <div 
          className="status-dot" 
          style={{ backgroundColor: getStatusColor(status) }}
        />
        <span>{label}</span>
      </div>
    );
  };

  return (
    <div className={`etl-overview ${expanded ? 'expanded' : ''}`}>
      <div className="etl-header">
        <div className="etl-title">
          <h3>ETL Pipeline Overview</h3>
          <div className="etl-status-bar">
            <StatusIndicator status="healthy" label="Sources" />
            <StatusIndicator status="healthy" label="Transforms" />
            <StatusIndicator status="warning" label="Quality" />
            <StatusIndicator status="healthy" label="Destinations" />
          </div>
        </div>
        <div className="etl-controls">
          <button 
            className={`tab-button ${activeTab === 'metrics' ? 'active' : ''}`}
            onClick={() => setActiveTab('metrics')}
          >
            Metrics
          </button>
          <button 
            className={`tab-button ${activeTab === 'performance' ? 'active' : ''}`}
            onClick={() => setActiveTab('performance')}
          >
            Performance
          </button>
          <button 
            className={`tab-button ${activeTab === 'quality' ? 'active' : ''}`}
            onClick={() => setActiveTab('quality')}
          >
            Data Quality
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
              <i className="fas fa-times" aria-hidden="true" />
            </button>
          )}
        </div>
      </div>

      <div className="etl-content">
        {activeTab === 'metrics' && (
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
              title="Total Nodes"
              value={graphStats.totalNodes || 0}
              color="#fd7e14"
              subtitle="Graph Elements"
            />
            <MetricCard
              title="Total Connections"
              value={graphStats.totalEdges || 0}
              color="#20c997"
              subtitle="Data Flows"
            />
          </div>
        )}

        {activeTab === 'performance' && (
          <div className="metrics-grid">
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
            <MetricCard
              title="Avg Latency"
              value={`${etlMetrics.latency}ms`}
              color={etlMetrics.latency < 100 ? '#28a745' : '#ffc107'}
              subtitle="Processing Time"
              trend={-1.2}
            />
            <MetricCard
              title="Error Rate"
              value={`${etlMetrics.errorRate}%`}
              color={parseFloat(etlMetrics.errorRate) < 5 ? '#28a745' : '#dc3545'}
              subtitle="Failed Records"
              trend={-0.8}
            />
            <MetricCard
              title="Selected"
              value={selectedNodeCount || 0}
              color="#ffc107"
              subtitle="Graph Selection"
            />
            <MetricCard
              title="Filtered"
              value={filteredNodeCount || 0}
              color="#dc3545"
              subtitle="Hidden Nodes"
            />
          </div>
        )}

        {activeTab === 'quality' && (
          <div className="metrics-grid">
            <MetricCard
              title="Quality Score"
              value={`${qualityData.qualityScore}%`}
              color={parseFloat(qualityData.qualityScore) > 90 ? '#28a745' : '#ffc107'}
              subtitle="Overall Data Health"
              trend={1.5}
            />
            <MetricCard
              title="Total Records"
              value={qualityData.totalRecords}
              color="#007bff"
              subtitle="Processed Today"
            />
            <MetricCard
              title="Valid Records"
              value={qualityData.validRecords}
              color="#28a745"
              subtitle="Passed Validation"
            />
            <MetricCard
              title="Duplicates"
              value={qualityData.duplicates}
              color="#ffc107"
              subtitle="Duplicate Entries"
            />
            <MetricCard
              title="Null Values"
              value={qualityData.nullValues}
              color="#dc3545"
              subtitle="Missing Data"
            />
            <MetricCard
              title="Avg Connections"
              value={graphStats.averageConnections ? graphStats.averageConnections.toFixed(1) : '0'}
              color="#6f42c1"
              subtitle="Node Connectivity"
            />
          </div>
        )}

        {expanded && (
          <div className="etl-detailed-view">
            <div className="detailed-section">
              <h4>Pipeline Health Summary</h4>
              <div className="health-bars">
                <div className="health-bar">
                  <label>Data Ingestion</label>
                  <div className="progress-bar">
                    <div className="progress-fill" style={{ width: '95%', backgroundColor: '#28a745' }}></div>
                  </div>
                  <span>95%</span>
                </div>
                <div className="health-bar">
                  <label>Transformation</label>
                  <div className="progress-bar">
                    <div className="progress-fill" style={{ width: '88%', backgroundColor: '#ffc107' }}></div>
                  </div>
                  <span>88%</span>
                </div>
                <div className="health-bar">
                  <label>Data Output</label>
                  <div className="progress-bar">
                    <div className="progress-fill" style={{ width: '92%', backgroundColor: '#28a745' }}></div>
                  </div>
                  <span>92%</span>
                </div>
              </div>
            </div>

            <div className="detailed-section">
              <h4>Pipeline Structure</h4>
              <div className="pipeline-stats">
                <div className="stat-item">
                  <span className="stat-label">Average Pipeline Length:</span>
                  <span className="stat-value">{etlMetrics.pipelineMetrics?.avgPipelineLength || 0} nodes</span>
                </div>
                <div className="stat-item">
                  <span className="stat-label">Longest Pipeline:</span>
                  <span className="stat-value">{etlMetrics.pipelineMetrics?.longestPipeline || 0} nodes</span>
                </div>
                <div className="stat-item">
                  <span className="stat-label">Pipeline Efficiency:</span>
                  <span className="stat-value">{etlMetrics.pipelineMetrics?.pipelineEfficiency || 0}%</span>
                </div>
              </div>
            </div>

            <div className="detailed-section">
              <h4>Analysis Tools</h4>
              <div className="analysis-buttons">
                <button 
                  className="analysis-btn primary"
                  onClick={handlePerformanceHighlight}
                  title="Highlight performance bottlenecks"
                >
                  <i className="fas fa-search" aria-hidden="true" /> Find Bottlenecks
                </button>
                <button 
                  className="analysis-btn secondary"
                  onClick={clearAllFilters}
                  title="Clear all filters and highlights"
                >
                  <i className="fas fa-sync" aria-hidden="true" /> Reset View
                </button>
                <button 
                  className="analysis-btn secondary"
                  onClick={() => handleMetricClick('error', 1)}
                  title="Highlight nodes with errors"
                >
                  ! Find Errors
                </button>
              </div>
            </div>

            <div className="detailed-section">
              <h4>Quick Actions</h4>
              <div className="action-buttons">
                <button className="action-btn primary" onClick={handlePerformanceHighlight}>
                  Highlight Performance Issues
                </button>
                <button className="action-btn secondary" onClick={clearAllFilters}>
                  Clear All Filters
                </button>
                <button className="action-btn secondary" onClick={() => handleMetricClick('error', 1)}>
                  Show Error Nodes
                </button>
              </div>
            </div>
          </div>
        )}

        {loadingError && (
          <div className="etl-error">
            <div className="error-icon">!</div>
            <div className="error-content">
              <strong>Pipeline Error:</strong> {loadingError}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default ETLOverview;
