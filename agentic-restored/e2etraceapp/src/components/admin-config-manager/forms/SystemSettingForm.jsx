/**
 * System Setting Form Component
 */
import React from 'react';

export function SystemSettingForm({ setting, onChange }) {
  const isEdit = Boolean(setting?.id);

  const setField = (field, value) => {
    onChange({
      ...(setting || {}),
      [field]: value,
    });
  };

  const isSecret = !!setting?.is_secret;
  const valueDisplay = setting?.value;
  const isMaskedSecretValue = isSecret && typeof valueDisplay === 'string' && valueDisplay.includes('*');

  return (
    <>
      <div className="form-row">
        <div className="form-group">
          <label>Category</label>
          <input
            type="text"
            value={setting.category || ''}
            onChange={e => setField('category', e.target.value)}
            placeholder="e.g., llm"
            disabled={isEdit}
          />
        </div>
        <div className="form-group">
          <label>Key</label>
          <input
            type="text"
            value={setting.key || ''}
            onChange={e => setField('key', e.target.value)}
            placeholder="e.g., default_provider"
            disabled={isEdit}
          />
        </div>
      </div>

      <div className="form-row">
        <div className="form-group">
          <label>Value Type</label>
          <select
            value={setting.value_type || 'string'}
            onChange={e => setField('value_type', e.target.value)}
            disabled={isEdit}
          >
            <option value="string">string</option>
            <option value="number">number</option>
            <option value="boolean">boolean</option>
            <option value="json">json</option>
          </select>
        </div>
        <div className="form-group">
          <label>Enabled</label>
          <select
            value={setting.enabled === false ? 'false' : 'true'}
            onChange={e => setField('enabled', e.target.value === 'true')}
          >
            <option value="true">Yes</option>
            <option value="false">No</option>
          </select>
        </div>
      </div>

      <div className="form-group">
        <label>Description</label>
        <input
          type="text"
          value={setting.description || ''}
          onChange={e => setField('description', e.target.value)}
          placeholder="What is this setting used for?"
        />
      </div>

      <div className="form-group">
        <label>Value</label>
        <input
          type={isSecret ? 'password' : 'text'}
          value={(isMaskedSecretValue ? '' : (setting.value || ''))}
          onChange={e => setField('value', e.target.value)}
          placeholder={isMaskedSecretValue ? '******** (unchanged)' : 'Enter value'}
        />
        {isMaskedSecretValue && (
          <div style={{ color: 'var(--text-muted)', fontSize: '12px', marginTop: '6px' }}>
            Secret value is masked. Leave blank to keep existing; enter a new value to rotate it.
          </div>
        )}
      </div>

      {!isEdit && (
        <div className="form-row">
          <div className="form-group">
            <label>Secret</label>
            <select value={isSecret ? 'true' : 'false'} onChange={e => setField('is_secret', e.target.value === 'true')}>
              <option value="false">No</option>
              <option value="true">Yes</option>
            </select>
          </div>
          <div className="form-group">
            <label>Required</label>
            <select value={setting.is_required ? 'true' : 'false'} onChange={e => setField('is_required', e.target.value === 'true')}>
              <option value="false">No</option>
              <option value="true">Yes</option>
            </select>
          </div>
        </div>
      )}

      <div className="form-row">
        <div className="form-group">
          <label>Default Value (optional)</label>
          <input
            type="text"
            value={setting.default_value || ''}
            onChange={e => setField('default_value', e.target.value)}
            disabled={isEdit}
          />
        </div>
        <div className="form-group">
          <label>Validation Regex (optional)</label>
          <input
            type="text"
            value={setting.validation_regex || ''}
            onChange={e => setField('validation_regex', e.target.value)}
          />
        </div>
      </div>
    </>
  );
}

export default SystemSettingForm;
