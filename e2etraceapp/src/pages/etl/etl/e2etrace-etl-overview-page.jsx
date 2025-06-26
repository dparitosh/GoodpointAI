// e2etrace-etl-overview-page.jsx
import React, { useState, useEffect, useCallback } from 'react';
import { e2etraceFetchWithRetry } from '../../../api/e2etrace-api';
import './e2etrace-etl-overview-page.css';

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

export function E2ETraceETLOverviewPage() {
  const [etlMetrics, setEtlMetrics] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Function to fetch actual ETL data from the backend
  const fetchEtlData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      // --- CHANGE START ---
      // Replace the setTimeout and mockData with an actual API call
      const response = await e2etraceFetchWithRetry('/api/etl/metrics'); // Assuming this endpoint exists
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ message: `HTTP error! status: ${response.status}` }));
        throw new Error(errorData.message || `Failed to fetch ETL data: ${response.status}`);
      }
      const realData = await response.json();

      // Assuming realData structure matches what you want to display
      // You might need to transform realData if its structure differs from etlMetrics
      setEtlMetrics({
        latestStatus: realData.latestStatus || 'Unknown',
        ingestionVolume: realData.ingestionVolume || 'N/A',
        pendingDQIssues: realData.pendingDQIssues || 0,
        criticalDQIssues: realData.criticalDQIssues || 0,
        scheduledJobs: realData.scheduledJobs || 0,
        lastRemediation: realData.lastRemediation || 'N/A',
      });
      // --- CHANGE END ---

    } catch (e) {
      setError('Failed to fetch ETL data. Please try again.');
      console.error('ETL data fetch error:', e);
    } finally {
      setLoading(false);
    }
  }, []);

  // Fetch data on component mount
  useEffect(() => {
    fetchEtlData();
  }, [fetchEtlData]);

  return (
    <div className="e2etrace-etl-overview-panel dashboard-widgets-layout" style={{ padding: '2rem', background: '#f0f2f8', minHeight: '100vh' }}>
      <Widget
        title="ETL & Data Quality Operations"
        className="etl-widget"
        subheader={[
          <button onClick={fetchEtlData} disabled={loading} className="e2etrace-refresh-button" key="refresh">
            {loading ? 'Refreshing...' : 'Refresh Data'}
          </button>
        ]}
        style={{ maxWidth: 600, margin: '0 auto' }}
      >
        {error && <p className="e2etrace-error-message">{error}</p>}
        {loading && <p>Loading ETL metrics...</p>}
        {!loading && !error && etlMetrics && (
          <>
            <p>This panel provides an overview of ETL job statuses, data quality reports, and other operational metrics.</p>
            <ul>
              <li>Latest ETL Run Status: <span className={`status-indicator ${etlMetrics.latestStatus === 'Success' ? 'success' : 'failed'}`}>{etlMetrics.latestStatus}</span></li>
              <li>Data Ingestion Volume: {etlMetrics.ingestionVolume}</li>
              <li>Pending Data Quality Issues: {etlMetrics.pendingDQIssues} (Critical: {etlMetrics.criticalDQIssues})</li>
              <li>Scheduled Jobs: {etlMetrics.scheduledJobs}</li>
              <li>Last Remediation Action: {etlMetrics.lastRemediation}</li>
            </ul>
          </>
        )}
      </Widget>
    </div>
  );
}

export default E2ETraceETLOverviewPage;
