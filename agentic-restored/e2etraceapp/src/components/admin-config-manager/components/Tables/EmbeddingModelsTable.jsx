/**
 * Embedding Models Table Component
 */
import React from 'react';
import { StatusBadge } from '../StatusBadge';

export function EmbeddingModelsTable({ models, onEdit, onDelete, onTest, testingId }) {
  if (!models.length) {
    return (
      <div className="empty-state">
        <i className="fas fa-vector-square"></i>
        <p>No embedding models configured</p>
      </div>
    );
  }

  return (
    <table className="config-table">
      <thead>
        <tr>
          <th>Provider</th>
          <th>Name</th>
          <th>Model</th>
          <th>Dimensions</th>
          <th>API Key</th>
          <th>Status</th>
          <th>Actions</th>
        </tr>
      </thead>
      <tbody>
        {models.map(m => (
          <tr key={m.id}>
            <td className="provider-cell">
              {m.provider.toUpperCase()}
              {m.is_default && <span className="default-badge">Default</span>}
            </td>
            <td className="name-cell">{m.name}</td>
            <td className="model-cell">{m.model_name}</td>
            <td>{m.dimension ?? '-'}</td>
            <td>
              {m.provider === 'sentence_transformers' ? (
                <span className="api-key-display" style={{ color: 'var(--text-muted)' }}>
                  N/A (Local)
                </span>
              ) : m.custom_api_key ? (
                <span className="api-key-display masked">
                  <i className="fas fa-check-circle"></i> Configured
                </span>
              ) : (
                <span className="api-key-display missing">
                  <i className="fas fa-exclamation-circle"></i> Not set
                </span>
              )}
            </td>
            <td><StatusBadge status={m.status} /></td>
            <td className="actions-cell">
              <button
                className="btn-action btn-test"
                onClick={() => onTest(m.id)}
                disabled={testingId === m.id}
                title="Test Model"
              >
                {testingId === m.id ? <i className="fas fa-spinner fa-spin"></i> : <i className="fas fa-plug"></i>}
              </button>
              <button className="btn-action btn-edit" onClick={() => onEdit(m)} title="Edit">
                <i className="fas fa-edit"></i>
              </button>
              <button className="btn-action btn-delete" onClick={() => onDelete(m.id)} title="Delete">
                <i className="fas fa-trash"></i>
              </button>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export default EmbeddingModelsTable;
