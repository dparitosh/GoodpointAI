/**
 * System Settings Table Component
 */
import React from 'react';
import { StatusBadge } from '../StatusBadge';

export function SystemSettingsTable({ settings, onEdit, onDelete }) {
  if (!settings.length) {
    return (
      <div className="empty-state">
        <i className="fas fa-cog"></i>
        <p>No system settings configured</p>
      </div>
    );
  }

  // Group by category
  const grouped = settings.reduce((acc, s) => {
    const cat = s.category || 'general';
    if (!acc[cat]) acc[cat] = [];
    acc[cat].push(s);
    return acc;
  }, {});

  return (
    <div>
      {Object.entries(grouped).map(([category, items]) => (
        <div key={category} style={{ marginBottom: '24px' }}>
          <h4 style={{
            margin: '0 0 12px 0',
            textTransform: 'uppercase',
            fontSize: '12px',
            color: 'var(--text-muted)',
            letterSpacing: '0.5px'
          }}>
            {category}
          </h4>
          <table className="config-table">
            <thead>
              <tr>
                <th>Key</th>
                <th>Value</th>
                <th>Type</th>
                <th>Status</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {items.map(s => (
                <tr key={s.id}>
                  <td className="name-cell">{s.key}</td>
                  <td className="endpoint-cell">
                    {s.is_secret ? '********' : (s.value || s.default_value || '-')}
                  </td>
                  <td><span className="type-badge">{s.value_type}</span></td>
                  <td><StatusBadge status={s.enabled ? 'active' : 'inactive'} /></td>
                  <td className="actions-cell">
                    <button className="btn-action btn-edit" onClick={() => onEdit(s)} title="Edit">
                      <i className="fas fa-edit"></i>
                    </button>
                    <button className="btn-action btn-delete" onClick={() => onDelete(s.id)} title="Delete">
                      <i className="fas fa-trash"></i>
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ))}
    </div>
  );
}

export default SystemSettingsTable;
