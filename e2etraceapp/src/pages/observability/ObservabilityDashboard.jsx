import React, { useState, useEffect } from 'react';
import { e2etraceFetchWithRetry } from '../../api/e2etrace-api';
import './ObservabilityDashboard.css';

/**
 * Observability & Monitoring Dashboard
 * Real-time system monitoring, alerts, and performance metrics
 */
export const ObservabilityDashboard = () => {
  const [alerts, setAlerts] = useState([]);
  const [qualityMetrics, setQualityMetrics] = useState(null);
  const [agenticStatus, setAgenticStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshInterval, setRefreshInterval] = useState(30000); // 30 seconds

  useEffect(() => {
    fetchAllMetrics();
    
    const interval = setInterval(() => {
      fetchAllMetrics();
    }, refreshInterval);

    return () => clearInterval(interval);
  }, [refreshInterval]);

  const fetchAllMetrics = async () => {
    setLoading(true);
    try {
      // Fetch monitoring alerts
      const alertsResponse = await e2etraceFetchWithRetry('/api/monitoring/alerts');
      setAlerts(alertsResponse || []);

      // Fetch data quality metrics
      const qualityResponse = await e2etraceFetchWithRetry('/api/monitoring/data-quality');
      setQualityMetrics(qualityResponse);

      // Fetch agentic system status
      try {
        const agenticResponse = await e2etraceFetchWithRetry('/api/agentic/system/status');
        setAgenticStatus(agenticResponse);
      } catch (err) {
        console.warn('Agentic system not available:', err);
      }

    } catch (error) {
      console.error('Error fetching metrics:', error);
    } finally {
      setLoading(false);
    }
  };

  const getAlertIcon = (level) => {
    switch (level) {
      case 'error': return '●';
      case 'warning': return '●';
      case 'info': return '●';
      default: return '○';
    }
  };

  const getQualityScoreColor = (score) => {
    if (score >= 95) return '#24A148';
    if (score >= 85) return '#0078D4';
    if (score >= 70) return '#FF832B';
    return '#DA1E28';
  };

  return (
    <div className="observability-dashboard">
      <div className="observability-header">
        <h1>Observability & Monitoring</h1>
        <div className="observability-controls">
          <select
            value={refreshInterval}
            onChange={(e) => setRefreshInterval(Number(e.target.value))}
            className="refresh-select"
          >
            <option value={10000}>Refresh: 10s</option>
            <option value={30000}>Refresh: 30s</option>
            <option value={60000}>Refresh: 1min</option>
            <option value={300000}>Refresh: 5min</option>
          </select>
          <button onClick={fetchAllMetrics} className="refresh-btn">
            ↻ Refresh Now
          </button>
        </div>
      </div>

      {loading && !qualityMetrics ? (
        <div className="loading-state">
          <div className="loading-spinner"></div>
          <p>Loading metrics...</p>
        </div>
      ) : (
        <>
          {/* System Overview Cards */}
          <div className="metrics-grid">
            {/* Data Quality Score */}
            <div className="metric-card">
              <div className="metric-header">
                <h3>Data Quality Score</h3>
                <span className="metric-icon">✓</span>
              </div>
              <div className="metric-value" style={{ color: getQualityScoreColor(qualityMetrics?.qualityScore || 0) }}>
                {qualityMetrics?.qualityScore?.toFixed(1) || 0}%
              </div>
              <div className="metric-details">
                <div className="metric-detail-item">
                  <span>Valid Records:</span>
                  <span>{qualityMetrics?.validRecords?.toLocaleString() || 0}</span>
                </div>
                <div className="metric-detail-item">
                  <span>Total Records:</span>
                  <span>{qualityMetrics?.totalRecords?.toLocaleString() || 0}</span>
                </div>
              </div>
            </div>

            {/* Data Issues */}
            <div className="metric-card">
              <div className="metric-header">
                <h3>Data Issues</h3>
                <span className="metric-icon">!</span>
              </div>
              <div className="metric-value" style={{ color: '#FF832B' }}>
                {((qualityMetrics?.duplicates || 0) + (qualityMetrics?.nullValues || 0))}
              </div>
              <div className="metric-details">
                <div className="metric-detail-item">
                  <span>Duplicates:</span>
                  <span>{qualityMetrics?.duplicates || 0}</span>
                </div>
                <div className="metric-detail-item">
                  <span>Null Values:</span>
                  <span>{qualityMetrics?.nullValues || 0}</span>
                </div>
              </div>
            </div>

            {/* System Alerts */}
            <div className="metric-card">
              <div className="metric-header">
                <h3>Active Alerts</h3>
                <span className="metric-icon">◉</span>
              </div>
              <div className="metric-value">
                {alerts.length}
              </div>
              <div className="metric-details">
                <div className="metric-detail-item">
                  <span>Critical:</span>
                  <span>{alerts.filter(a => a.level === 'error').length}</span>
                </div>
                <div className="metric-detail-item">
                  <span>Warnings:</span>
                  <span>{alerts.filter(a => a.level === 'warning').length}</span>
                </div>
              </div>
            </div>

            {/* Agentic System Status */}
            {agenticStatus && (
              <div className="metric-card">
                <div className="metric-header">
                  <h3>Agentic System</h3>
                  <span className="metric-icon">◈</span>
                </div>
                <div className="metric-value" style={{ color: '#24A148' }}>
                  {agenticStatus.active_agents?.length || 0}
                </div>
                <div className="metric-details">
                  <div className="metric-detail-item">
                    <span>Active Agents:</span>
                    <span>{agenticStatus.active_agents?.length || 0}</span>
                  </div>
                  <div className="metric-detail-item">
                    <span>Queue Size:</span>
                    <span>{agenticStatus.task_queue_size || 0}</span>
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Alerts Panel */}
          <div className="alerts-panel">
            <h2>Recent Alerts</h2>
            {alerts.length === 0 ? (
              <div className="no-alerts">
                <span>✓</span>
                <p>No active alerts - System healthy</p>
              </div>
            ) : (
              <div className="alerts-list">
                {alerts.map((alert) => (
                  <div key={alert.id} className={`alert-item alert-${alert.level}`}>
                    <div className="alert-icon">{getAlertIcon(alert.level)}</div>
                    <div className="alert-content">
                      <div className="alert-message">{alert.message}</div>
                      <div className="alert-meta">
                        <span className="alert-component">{alert.component}</span>
                        <span className="alert-timestamp">
                          {new Date(alert.timestamp).toLocaleString()}
                        </span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Quality Issues Detail */}
          {qualityMetrics?.issues && qualityMetrics.issues.length > 0 && (
            <div className="quality-issues-panel">
              <h2>Data Quality Issues</h2>
              <div className="issues-list">
                {qualityMetrics.issues.map((issue, idx) => (
                  <div key={idx} className="issue-item">
                    <div className="issue-type">{issue.issue || 'Unknown'}</div>
                    <div className="issue-node">Node: {issue.nodeId}</div>
                    <div className="issue-types">Types: {issue.nodeType?.join(', ') || 'N/A'}</div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Agentic Agents List */}
          {agenticStatus?.active_agents && agenticStatus.active_agents.length > 0 && (
            <div className="agents-panel">
              <h2>Active Agents</h2>
              <div className="agents-grid">
                {agenticStatus.active_agents.map((agent) => (
                  <div key={agent.id} className="agent-card">
                    <div className="agent-header">
                      <h3>{agent.name}</h3>
                      <span className={`agent-status agent-status-${agent.status}`}>
                        {agent.status}
                      </span>
                    </div>
                    <div className="agent-type">{agent.type}</div>
                    <div className="agent-capabilities">
                      {agent.capabilities?.slice(0, 3).map((cap, idx) => (
                        <span key={idx} className="capability-badge">
                          {cap.name}
                        </span>
                      ))}
                      {agent.capabilities?.length > 3 && (
                        <span className="capability-badge">
                          +{agent.capabilities.length - 3} more
                        </span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
};

export default ObservabilityDashboard;
