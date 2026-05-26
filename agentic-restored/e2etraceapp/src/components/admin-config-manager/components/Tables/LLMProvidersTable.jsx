/**
 * LLM Providers Table Component
 */
import React from 'react';
import { StatusBadge } from '../StatusBadge';

export function LLMProvidersTable({ providers, onEdit, onDelete, onTest, testingId }) {
  if (!providers.length) {
    return (
      <div className="empty-state">
        <i className="fas fa-brain"></i>
        <p>No LLM providers configured</p>
      </div>
    );
  }

  return (
    <table className="config-table">
      <thead>
        <tr>
          <th>Provider</th>
          <th>Name</th>
          <th>Endpoint</th>
          <th>Model</th>
          <th>API Key</th>
          <th>Status</th>
          <th>Actions</th>
        </tr>
      </thead>
      <tbody>
        {providers.map(p => (
          <tr key={p.id}>
            <td className="provider-cell">
              {p.provider.toUpperCase()}
              {p.is_default && <span className="default-badge">Default</span>}
            </td>
            <td className="name-cell">{p.name}</td>
            <td className="endpoint-cell" title={p.api_endpoint}>{p.api_endpoint || '-'}</td>
            <td className="model-cell">{p.default_chat_model || '-'}</td>
            <td>
              {p.api_key_masked ? (
                <span className="api-key-display masked">
                  <i className="fas fa-check-circle"></i> {p.api_key_masked}
                </span>
              ) : (
                <span className="api-key-display missing">
                  <i className="fas fa-exclamation-circle"></i> Not set
                </span>
              )}
            </td>
            <td><StatusBadge status={p.status} /></td>
            <td className="actions-cell">
              <button
                className="btn-action btn-test"
                onClick={() => onTest(p.id)}
                disabled={testingId === p.id}
                title="Test Connection"
              >
                {testingId === p.id ? <i className="fas fa-spinner fa-spin"></i> : <i className="fas fa-plug"></i>}
              </button>
              <button className="btn-action btn-edit" onClick={() => onEdit(p)} title="Edit">
                <i className="fas fa-edit"></i>
              </button>
              <button className="btn-action btn-delete" onClick={() => onDelete(p.id)} title="Delete">
                <i className="fas fa-trash"></i>
              </button>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export default LLMProvidersTable;
