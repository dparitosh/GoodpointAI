import React, { useState, useEffect } from 'react';
import { e2etraceFetchWithRetry } from '../../../api/e2etrace-api';
import { E2ETraceNiFiFlowDiagram } from './e2etrace-nifi-flow-diagram';
import { E2ETraceNiFiStatusPanel } from './e2etrace-nifi-status-panel';
import './e2etrace-nifi-main.css';

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
        return <Widget title="Loading NiFi Process Groups" className="nifi-widget"><p>Loading NiFi process groups...</p></Widget>;
    }
    if (errorGroups) {
        return <Widget title="Error" className="nifi-widget"><p className="error">Error loading NiFi process groups: {errorGroups}</p></Widget>;
    }
    if (processGroups.length === 0) {
        return <Widget title="No NiFi Process Groups" className="nifi-widget"><p>No NiFi process groups found.</p></Widget>;
    }

    return (
        <div className="e2etrace-nifi-main-container dashboard-widgets-layout" style={{ display: 'flex', gap: '2rem', padding: '2rem', background: '#f0f2f8', minHeight: '100vh' }}>
            <Widget title="Process Groups" className="e2trace-nifi-list-panel" style={{ flex: 1, minWidth: 220 }}>
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
            </Widget>
            <Widget title="Process Group Details" className="e2etrace-nifi-main-content" style={{ flex: 3, minWidth: 320 }}>
                {!selectedProcessGroupId ? (
                    <p>Select a process group from the left to view its details.</p>
                ) : (
                <div className="e2etrace-nifi-content-area">
                    <E2ETraceNiFiFlowDiagram processGroupId={selectedProcessGroupId} />
                    <E2ETraceNiFiStatusPanel processGroupId={selectedProcessGroupId} />
                </div>
                )}
            </Widget>
        </div>
    );
}