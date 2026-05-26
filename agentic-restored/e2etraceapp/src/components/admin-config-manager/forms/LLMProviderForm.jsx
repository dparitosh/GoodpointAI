/**
 * LLM Provider Form Component
 */
import React from 'react';

export function LLMProviderForm({ provider, onChange }) {
  const isEdit = provider?._isNew === false;

  return (
    <>
      <div className="form-row">
        <div className="form-group">
          <label>ID (optional)</label>
          <input
            type="text"
            value={provider.id || ''}
            onChange={e => onChange({ ...provider, id: e.target.value })}
            placeholder="e.g., openai_primary"
            disabled={isEdit}
          />
        </div>
        <div className="form-group">
          <label>Provider</label>
          <select
            value={provider.provider || ''}
            onChange={e => onChange({ ...provider, provider: e.target.value })}
            disabled={isEdit}
          >
            <option value="">Select Provider</option>
            <option value="openai">OpenAI</option>
            <option value="anthropic">Anthropic</option>
            <option value="azure_openai">Azure OpenAI</option>
            <option value="ollama">Ollama</option>
            <option value="huggingface">Hugging Face</option>
          </select>
        </div>
      </div>

      <div className="form-row">
        <div className="form-group">
          <label>Display Name</label>
          <input
            type="text"
            value={provider.name || ''}
            onChange={e => onChange({ ...provider, name: e.target.value })}
            placeholder="e.g., OpenAI GPT-4"
          />
        </div>
      </div>

      <div className="form-group">
        <label>API Key</label>
        <input
          type="password"
          value={provider.api_key || ''}
          onChange={e => onChange({ ...provider, api_key: e.target.value })}
          placeholder="Enter API key"
        />
      </div>

      <div className="form-row">
        <div className="form-group">
          <label>API Endpoint</label>
          <input
            type="text"
            value={provider.api_endpoint || ''}
            onChange={e => onChange({ ...provider, api_endpoint: e.target.value })}
            placeholder="https://api.openai.com/v1"
          />
        </div>
        <div className="form-group">
          <label>Default Chat Model</label>
          <input
            type="text"
            value={provider.default_chat_model || ''}
            onChange={e => onChange({ ...provider, default_chat_model: e.target.value })}
            placeholder="gpt-4-turbo-preview"
          />
        </div>
      </div>

      {provider.provider === 'azure_openai' && (
        <div className="form-row">
          <div className="form-group">
            <label>Azure Deployment</label>
            <input
              type="text"
              value={provider.azure_deployment || ''}
              onChange={e => onChange({ ...provider, azure_deployment: e.target.value })}
            />
          </div>
          <div className="form-group">
            <label>Azure Resource Name</label>
            <input
              type="text"
              value={provider.azure_resource_name || ''}
              onChange={e => onChange({ ...provider, azure_resource_name: e.target.value })}
            />
          </div>
        </div>
      )}

      <div className="form-row">
        <div className="form-group">
          <label>Status</label>
          <select value={provider.status || 'inactive'} onChange={e => onChange({ ...provider, status: e.target.value })}>
            <option value="active">Active</option>
            <option value="inactive">Inactive</option>
            <option value="testing">Testing</option>
            <option value="deprecated">Deprecated</option>
          </select>
        </div>
        <div className="form-group">
          <label>Default Provider</label>
          <select value={provider.is_default ? 'true' : 'false'} onChange={e => onChange({ ...provider, is_default: e.target.value === 'true' })}>
            <option value="false">No</option>
            <option value="true">Yes</option>
          </select>
        </div>
      </div>
    </>
  );
}

export default LLMProviderForm;
