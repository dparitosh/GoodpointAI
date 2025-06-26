import React from 'react';
import { E2ETraceUIPanel } from '../../../components/e2etrace-ui-panel';

export const E2ETraceQuickActions = () => {
    return (
        <E2ETraceUIPanel className="e2etrace-quick-actions">
            <h3>Quick Actions</h3>
            <div className="e2etrace-quick-actions-grid">
                <button onClick={() => console.log('Run Data Quality Check')}>Run DQ Check</button>
                <button onClick={() => console.log('Initiate Remediation')}>Remediate</button>
                <button onClick={() => console.log('Trace Lineage')}>Trace Lineage</button>
                <button onClick={() => console.log('View in Teamcenter')}>View in TC</button>
                <button onClick={() => console.log('Open Zeppelin Notebook')}>Zeppelin</button>
                <button onClick={() => console.log('Manage Ingestion')}>Ingestion</button>
            </div>
        </E2ETraceUIPanel>
    );
};