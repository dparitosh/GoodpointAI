/**
 * Feature Flag Form Component
 */
import React from 'react';

export function FeatureFlagForm({ flag, onChange }) {
  const isEdit = flag?._isNew === false;

  const setField = (field, value) => {
    onChange({
      ...(flag || {}),
      [field]: value,
    });
  };

  const targetingText = (() => {
    const v = flag?.targeting_rules;
    if (typeof v === 'string') return v;
    if (v == null) return '';
    try {
      return JSON.stringify(v, null, 2);
    } catch {
      return '';
    }
  })();

  return (
    <>
      <div className="form-row">
        <div className="form-group">
          <label>ID (optional)</label>
          <input
            type="text"
            value={flag.id || ''}
            onChange={e => setField('id', e.target.value)}
            placeholder="e.g., enable_vector_search"
            disabled={isEdit}
          />
        </div>
        <div className="form-group">
          <label>Enabled</label>
          <select value={flag.enabled ? 'true' : 'false'} onChange={e => setField('enabled', e.target.value === 'true')}>
            <option value="false">No</option>
            <option value="true">Yes</option>
          </select>
        </div>
      </div>

      <div className="form-group">
        <label>Name</label>
        <input
          type="text"
          value={flag.name || ''}
          onChange={e => setField('name', e.target.value)}
          placeholder="Human-friendly flag name"
        />
      </div>

      <div className="form-group">
        <label>Description</label>
        <input
          type="text"
          value={flag.description || ''}
          onChange={e => setField('description', e.target.value)}
          placeholder="What does this flag control?"
        />
      </div>

      <div className="form-row">
        <div className="form-group">
          <label>Rollout Percentage</label>
          <input
            type="number"
            min="0"
            max="100"
            value={typeof flag.rollout_percentage === 'number' ? flag.rollout_percentage : 100}
            onChange={e => setField('rollout_percentage', parseInt(e.target.value, 10))}
          />
        </div>
        <div className="form-group">
          <label>Targeting Rules (JSON, optional)</label>
          <textarea
            value={targetingText}
            onChange={e => setField('targeting_rules', e.target.value)}
            placeholder='{"users": ["alice"], "tenants": ["t1"]}'
            rows={6}
          />
        </div>
      </div>
    </>
  );
}

export default FeatureFlagForm;
