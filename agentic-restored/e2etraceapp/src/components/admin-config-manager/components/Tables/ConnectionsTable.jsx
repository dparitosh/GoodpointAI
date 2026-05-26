/**
 * Connections Table Component
 */
import React from 'react';
import { StatusBadge } from '../StatusBadge';

export function ConnectionsTable({ connections, onEdit, onDelete, onTest, testingId, testResults }) {
  const getHostDisplay = (c) => {
    const opts = c.extra_options || {};
    switch ((c.connection_type || '').toLowerCase()) {
      case 'soda_external':
        return opts.python_path || '-';
      case 's3':
        return opts.bucket || '-';
      case 'azure_blob':
        return opts.account_name || '-';
      case 'local_folder':
        return opts.folder_path || '-';
      case 'onedrive':
        return opts.root_path || '-';
      case 'google_drive':
        return opts.folder_id || opts.root_path || '-';
      case 'powerquery':
        return 'PowerQuery';
      default:
        return c.host || '-';
    }
  };

  const getPortDisplay = (c) => {
    const type = (c.connection_type || '').toLowerCase();
    if (['soda_external', 's3', 'azure_blob', 'local_folder', 'onedrive', 'google_drive', 'powerquery'].includes(type)) {
      return '-';
    }
    return c.port ?? '-';
  };

  const getDatabaseDisplay = (c) => {
    const opts = c.extra_options || {};
    switch ((c.connection_type || '').toLowerCase()) {
      case 'soda_external':
        return (opts.timeout_s ?? '-')
      case 's3':
        return opts.prefix || '-';
      case 'azure_blob':
        return opts.container || '-';
      case 'local_folder':
        return '-';
      case 'onedrive':
        return opts.drive_id || '-';
      case 'google_drive':
        return opts.shared_drive_id || '-';
      case 'powerquery':
        return (opts.query_name || opts.data_source_name || '-')
      default:
        return c.database || c.index_name || '-';
    }
  };

  if (!connections.length) {
    return (
      <div className="empty-state">
        <i className="fas fa-plug"></i>
        <p>No connection settings (data sources) configured</p>
      </div>
    );
  }

  return (
    <table className="config-table">
      <thead>
        <tr>
          <th>Type</th>
          <th>Name</th>
          <th>Host</th>
          <th>Port</th>
          <th>Database</th>
          <th>Status</th>
          <th>Test Result</th>
          <th>Actions</th>
        </tr>
      </thead>
      <tbody>
        {connections.map(c => (
          <tr key={c.id}>
            <td className="provider-cell">
              {c.connection_type.toUpperCase()}
              {c.is_default && <span className="default-badge">Default</span>}
            </td>
            <td className="name-cell">{c.name}</td>
            <td className="endpoint-cell">{getHostDisplay(c)}</td>
            <td>{getPortDisplay(c)}</td>
            <td>{getDatabaseDisplay(c)}</td>
            <td><StatusBadge status={c.status} /></td>
            <td>
              {testResults[c.id] && (
                <span className={`test-result ${testResults[c.id].success ? 'success' : 'failure'}`}>
                  {testResults[c.id].success ? (
                    <><i className="fas fa-check"></i> Connected</>
                  ) : (
                    <><i className="fas fa-times"></i> {testResults[c.id].error || testResults[c.id].message || 'Failed'}</>
                  )}
                </span>
              )}
            </td>
            <td className="actions-cell">
              <button
                className="btn-action btn-test"
                onClick={() => onTest(c.id)}
                disabled={testingId === c.id}
                title="Test Connection"
              >
                {testingId === c.id ? <i className="fas fa-spinner fa-spin"></i> : <i className="fas fa-plug"></i>}
              </button>
              <button className="btn-action btn-edit" onClick={() => onEdit(c)} title="Edit">
                <i className="fas fa-edit"></i>
              </button>
              <button className="btn-action btn-delete" onClick={() => onDelete(c.id)} title="Delete">
                <i className="fas fa-trash"></i>
              </button>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export default ConnectionsTable;
