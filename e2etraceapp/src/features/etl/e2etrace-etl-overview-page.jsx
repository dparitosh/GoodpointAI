import React, { useState, useEffect, useCallback } from 'react';
import { E2ETraceUIPanel } from '../../components/e2etrace-ui-panel';
import './e2etrace-etl-overview-page.css'; // Assuming a new CSS file for this panel

export function E2ETraceETLOverviewPage() {
  const [etlMetrics, setEtlMetrics] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Function to simulate fetching ETL data
  const fetchEtlData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      // Simulate API call delay
      await new Promise(resolve => setTimeout(resolve, 800));

      // Mock data - in a real application, this would come from an API
      const mockData = {
        latestStatus: Math.random() > 0.1 ? 'Success' : 'Failed',
        ingestionVolume: `${(Math.random() * 2 + 0.5).toFixed(1)} TB (Last 24h)`,
        pendingDQIssues: Math.floor(Math.random() * 20) + 5,
        criticalDQIssues: Math.floor(Math.random() * 5),
        scheduledJobs: Math.floor(Math.random() * 10) + 3,
        lastRemediation: new Date().toLocaleString(),
      };
      setEtlMetrics(mockData);
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
    <div className="e2etrace-etl-overview-panel">
      <E2ETraceUIPanel>
        <div className="e2etrace-etl-header">
          <h2>ETL & Data Quality Operations</h2>
          <button onClick={fetchEtlData} disabled={loading} className="e2etrace-refresh-button">
            {loading ? 'Refreshing...' : 'Refresh Data'}
          </button>
        </div>
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
      </E2ETraceUIPanel>
    </div>
  );
}

export default E2ETraceETLOverviewPage;