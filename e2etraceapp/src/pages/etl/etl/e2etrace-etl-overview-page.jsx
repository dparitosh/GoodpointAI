// e2etrace-etl-overview-page.jsx
import React, { useState, useEffect, useCallback } from 'react';
import { E2ETraceUIPanel } from '../../../components/e2etrace-ui-panel';
import { e2etraceFetchWithRetry } from '../../../api/e2etrace-api';
import './e2etrace-etl-overview-page.css';

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
