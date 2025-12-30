import React, { useState, useEffect } from 'react';
import ReactECharts from 'echarts-for-react';
import { e2etraceFetchWithRetry } from '../../api/e2etrace-api';
import { API_CONFIG } from '../../config/api-config.js';
import './MonitoringPage.css';

const MonitoringPage = () => {
  const [metrics, setMetrics] = useState({});
  const [alerts, setAlerts] = useState([]);
  const [flowStatus, setFlowStatus] = useState([]);
  const [activeTab, setActiveTab] = useState('overview');
  const [isLoading, setIsLoading] = useState(false);
  const [refreshInterval, setRefreshInterval] = useState(30); // seconds

  useEffect(() => {
    loadMonitoringData();
    
    // Set up auto-refresh
    const interval = setInterval(loadMonitoringData, refreshInterval * 1000);
    return () => clearInterval(interval);
  }, [refreshInterval]);

  const loadMonitoringData = async () => {
    setIsLoading(true);
    try {
      // Load real monitoring data from Neo4j backend
      const [flowResponse, alertsResponse] = await Promise.all([
        e2etraceFetchWithRetry(API_CONFIG.ENDPOINTS.FLOW_STATUS),
        e2etraceFetchWithRetry(API_CONFIG.ENDPOINTS.FLOW_ALERTS)
      ]);

      const flowData = await flowResponse.json();
      const alertsData = await alertsResponse.json();

      // Keep basic metric placeholders.
      setMetrics(prev => ({
        totalFlowFiles: prev.totalFlowFiles || 0,
        bytesRead: prev.bytesRead || 0,
        bytesWritten: prev.bytesWritten || 0,
        activeThreads: prev.activeThreads || 0,
        queuedFlowFiles: prev.queuedFlowFiles || 0,
        systemLoad: prev.systemLoad || 0,
        memoryUsed: prev.memoryUsed || '0MB',
        memoryMax: prev.memoryMax || '2GB',
        timestamp: new Date().toISOString()
      import React from 'react';
      import { Navigate } from 'react-router-dom';

      const MonitoringPage = () => <Navigate to="/observability" replace />;

      export default MonitoringPage;
              <div className="no-alerts">
                <p>✓ No active alerts. All systems are running normally.</p>
              </div>
            )}
          </div>
        )}

        {/* Performance Tab */}
        {activeTab === 'performance' && (
          <div className="performance-section">
            <div className="section-header">
              <h2>Performance Metrics</h2>
              <div className="time-range-selector">
                <label>Time Range:</label>
                <select>
                  <option value="1h">Last Hour</option>
                  <option value="6h">Last 6 Hours</option>
                  <option value="24h">Last 24 Hours</option>
                  <option value="7d">Last 7 Days</option>
                </select>
              </div>
            </div>

            <div className="performance-grid">
              <div className="performance-card">
                <h3>Memory Usage</h3>
                <div className="memory-info">
                  <div className="memory-bar">
                    <div 
                      className="memory-used" 
                      style={{ width: '75%' }}
                    ></div>
                  </div>
                  <div className="memory-text">
                    {metrics.memoryUsed} / {metrics.memoryMax} (75%)
                  </div>
                </div>
              </div>

              <div className="performance-card">
                <h3>Thread Pool Status</h3>
                <div className="thread-info">
                  <div className="thread-stat">
                    <span>Active: {metrics.activeThreads}</span>
                  </div>
                  <div className="thread-stat">
                    <span>Available: {50 - (metrics.activeThreads || 0)}</span>
                  </div>
                  <div className="thread-stat">
                    <span>Total Pool: 50</span>
                  </div>
                </div>
              </div>

              <div className="performance-card">
                <h3>System Resources</h3>
                <div className="resource-info">
                  <div className="resource-item">
                    <span>CPU Load: {(metrics.systemLoad * 100)?.toFixed(1) || 0}%</span>
                    <div className="resource-bar">
                      <div 
                        className="resource-used" 
                        style={{ width: `${(metrics.systemLoad * 100) || 0}%` }}
                      ></div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>

      {isLoading && (
        <div className="loading-indicator">
          <div className="loading-spinner">Refreshing...</div>
        </div>
      )}
    </div>
  );
};

export default MonitoringPage;
