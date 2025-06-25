import React, { useEffect, useState } from 'react';
import { E2ETraceUIPanel } from '../../../components/e2etrace-ui-panel';
import { e2etraceFetchWithRetry } from '../../../utils/e2etrace-api';
import './e2etrace-nifi-status-panel.css';

export function E2ETraceNiFiStatusPanel({ processGroupId }) {
    const [statusData, setStatusData] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    useEffect(() => {
        const fetchStatusData = async () => {
            try {
                setLoading(true);
                const response = await e2etraceFetchWithRetry(`/api/nifi/status/${processGroupId}`);
                const data = await response.json();
                setStatusData(data.processGroupStatus);
            } catch (e) {
                setError(e.message);
            } finally {
                setLoading(false);
            }
        };
        fetchStatusData();
        // Refresh status every 10 seconds
        const interval = setInterval(fetchStatusData, 10000);
        return () => clearInterval(interval);
    }, [processGroupId]);

    if (loading) {
        return <E2ETraceUIPanel className="e2etrace-nifi-status-panel"><p>Loading status...</p></E2ETraceUIPanel>;
    }
    if (error) {
        return <E2ETraceUIPanel className="e2etrace-nifi-status-panel"><p className="error">Error loading status: {error}</p></E2ETraceUIPanel>;
    }
    if (!statusData) {
        return <E2ETraceUIPanel className="e2etrace-nifi-status-panel"><p>No status data available.</p></E2ETraceUIPanel>;
    }

    return (
        <E2ETraceUIPanel className="e2etrace-nifi-status-panel">
            <h3>Current Status</h3>
            <p><strong>Active Threads:</strong> {statusData.activeThreadCount}</p>
            <p><strong>Queued:</strong> {statusData.queued}</p>
            <p><strong>Bytes In:</strong> {statusData.bytesIn ? `${(statusData.bytesIn / (1024 * 1024)).toFixed(2)} MB` : 'N/A'}</p>
            <p><strong>Bytes Out:</strong> {statusData.bytesOut ? `${(statusData.bytesOut / (1024 * 1024)).toFixed(2)} MB` : 'N/A'}</p>
            <p><strong>FlowFiles In:</strong> {statusData.flowFilesIn}</p>
            <p><strong>FlowFiles Out:</strong> {statusData.flowFilesOut}</p>
        </E2ETraceUIPanel>
    );
}