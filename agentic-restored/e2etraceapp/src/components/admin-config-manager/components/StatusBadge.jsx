/**
 * Status Badge Component
 */
import React from 'react';

export function StatusBadge({ status }) {
  const statusClass = {
    'active': 'status-active',
    'inactive': 'status-inactive',
    'testing': 'status-testing',
    'deprecated': 'status-deprecated',
    'healthy': 'status-healthy',
    'degraded': 'status-degraded',
    'configured': 'status-configured',
    'unconfigured': 'status-unconfigured',
    'missing_api_key': 'status-inactive'
  }[status] || 'status-inactive';

  const displayStatus = status === 'missing_api_key' ? 'No API Key' : status;

  return <span className={`status-badge ${statusClass}`}>{displayStatus}</span>;
}

export default StatusBadge;
