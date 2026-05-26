/**
 * Feature Flags Table Component
 */
import React from 'react';

export function FeatureFlagsTable({ flags, onToggle, onEdit, onDelete }) {
  if (!flags.length) {
    return (
      <div className="empty-state">
        <i className="fas fa-flag"></i>
        <p>No feature flags configured</p>
      </div>
    );
  }

  return (
    <table className="config-table">
      <thead>
        <tr>
          <th>ID</th>
          <th>Name</th>
          <th>Description</th>
          <th>Rollout</th>
          <th>Enabled</th>
          <th>Actions</th>
        </tr>
      </thead>
      <tbody>
        {flags.map(f => (
          <tr key={f.id}>
            <td className="name-cell">{f.id}</td>
            <td className="name-cell">{f.name}</td>
            <td style={{ maxWidth: '300px' }}>{f.description || '-'}</td>
            <td><span className="type-badge">{typeof f.rollout_percentage === 'number' ? `${f.rollout_percentage}%` : '100%'}</span></td>
            <td>
              <label className="toggle-switch">
                <input
                  type="checkbox"
                  checked={!!f.enabled}
                  onChange={() => onToggle(f)}
                />
                <span className="toggle-slider"></span>
              </label>
            </td>
            <td className="actions-cell">
              <button className="btn-action btn-edit" onClick={() => onEdit(f)} title="Edit">
                <i className="fas fa-edit"></i>
              </button>
              <button className="btn-action btn-delete" onClick={() => onDelete(f.id)} title="Delete">
                <i className="fas fa-trash"></i>
              </button>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export default FeatureFlagsTable;
