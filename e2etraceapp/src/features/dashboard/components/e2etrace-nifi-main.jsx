import React, { useState, useEffect } from 'react';
import { E2ETraceUIPanel } from '../../../components/e2etrace-ui-panel';
import { e2etraceFetchWithRetry } from '../../../utils/e2etrace-api';
import { E2ETraceNiFiFlowDiagram } from './e2etrace-nifi-flow-diagram';
import { E2ETraceNiFiStatusPanel } from './e2etrace-nifi-status-panel';
import './e2etrace-nifi-main.css';

export function E2ETraceNiFiMain() {
    const [processGroups, setProcessGroups] = useState([]);
    const [selectedProcessGroupId, setSelectedProcessGroupId] = useState(null);
    const [loadingGroups, setLoadingGroups] = useState(true);
    const [errorGroups, setErrorGroups] = useState(null);

    useEffect(() => {
        const fetchProcessGroups = async () => {
            try {
                setLoadingGroups(true);
                const response = await e2etraceFetchWithRetry('/api/nifi/process_groups');
                const data = await response.json();
                if (data && data.processGroups) {
                    setProcessGroups(data.processGroups);
                    if (data.processGroups.length > 0) {
                        setSelectedProcessGroupId(data.processGroups[0].id);
                    }
                }
            } catch (e) {
                setErrorGroups(e.message);
            } finally {
                setLoadingGroups(false);
            }
        };
        fetchProcessGroups();
    }, []);

    if (loadingGroups) {
        return <E2ETraceUIPanel><p>Loading NiFi process groups...</p></E2ETraceUIPanel>;
    }
    if (errorGroups) {
        return <E2ETraceUIPanel><p className="error">Error loading NiFi process groups: {errorGroups}</p></E2ETraceUIPanel>;
    }
    if (processGroups.length === 0) {
        return <E2ETraceUIPanel><p>No NiFi process groups found.</p></E2ETraceUIPanel>;
    }

    return (
        <div className="e2etrace-nifi-main-container two-column-layout">
            <E2ETraceUIPanel className="e2etrace-nifi-list-panel">
                <h2>Process Groups</h2>
                <ul className="e2etrace-nifi-group-list">
                    {processGroups.map(group => (
                        <li
                            key={group.id}
                            className={group.id === selectedProcessGroupId ? 'active' : ''}
                            onClick={() => setSelectedProcessGroupId(group.id)}
                        >
                            {group.name}
                        </li>
                    ))}
                </ul>
            </E2ETraceUIPanel>
            <div className="e2etrace-nifi-main-content">
                {!selectedProcessGroupId ? (
                    <E2ETraceUIPanel>
                        <p>Select a process group from the left to view its details.</p>
                    </E2ETraceUIPanel>
                ) : (
                <div className="e2etrace-nifi-content-area">
                    {/* Render the flow diagram and status panel for the selected process group */}
                    <E2ETraceNiFiFlowDiagram processGroupId={selectedProcessGroupId} />
                    <E2ETraceNiFiStatusPanel processGroupId={selectedProcessGroupId} />
                </div>
            )}
        </div>
        </div>
    );
}