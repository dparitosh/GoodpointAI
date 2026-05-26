/**
 * Embedding Model Form Component
 */
import React from 'react';

export function EmbeddingModelForm({ model, onChange }) {
  const isEdit = model?._isNew === false;
  const provider = model?.provider || '';
  const customApiKeyIsMasked = typeof model?.custom_api_key === 'string' && model.custom_api_key.includes('*');

  const setField = (field, value) => {
    onChange({
      ...(model || {}),
      [field]: value,
    });
  };

  const handleProviderChange = (nextProvider) => {
    const next = { ...(model || {}), provider: nextProvider };

    // Friendly defaults for common providers
    if (!isEdit) {
      if (nextProvider === 'sentence_transformers') {
        if (!next.model_name) next.model_name = 'all-MiniLM-L6-v2';
        if (next.dimension == null || next.dimension === '') next.dimension = 384;
        if (!next.name) next.name = 'Local SentenceTransformers';
      }
      if (nextProvider === 'ollama') {
        if (!next.model_name) next.model_name = 'nomic-embed-text';
        if (next.dimension == null || next.dimension === '') next.dimension = 768;
        if (!next.custom_endpoint) next.custom_endpoint = 'http://localhost:11434';
        if (!next.name) next.name = 'Ollama Nomic Embeddings';
      }
      if (nextProvider === 'openai') {
        if (!next.model_name) next.model_name = 'text-embedding-3-small';
        if (next.dimension == null || next.dimension === '') next.dimension = 1536;
        if (!next.custom_endpoint) next.custom_endpoint = 'https://api.openai.com/v1';
        if (!next.name) next.name = 'OpenAI Embeddings';
      }
    }

    onChange(next);
  };

  return (
    <>
      <div className="form-row">
        <div className="form-group">
          <label>ID (optional)</label>
          <input
            type="text"
            value={model.id || ''}
            onChange={e => setField('id', e.target.value)}
            placeholder="e.g., ollama_nomic"
            disabled={isEdit}
          />
        </div>
        <div className="form-group">
          <label>Provider</label>
          <select
            value={provider}
            onChange={e => handleProviderChange(e.target.value)}
            disabled={isEdit}
          >
            <option value="">Select Provider</option>
            <option value="ollama">Ollama</option>
            <option value="sentence_transformers">SentenceTransformers (Local)</option>
            <option value="openai">OpenAI</option>
            <option value="azure_openai">Azure OpenAI</option>
            <option value="huggingface">Hugging Face</option>
            <option value="cohere">Cohere</option>
            <option value="custom">Custom</option>
          </select>
        </div>
      </div>

      <div className="form-row">
        <div className="form-group">
          <label>Display Name</label>
          <input
            type="text"
            value={model.name || ''}
            onChange={e => setField('name', e.target.value)}
            placeholder="e.g., Ollama Nomic Embeddings"
          />
        </div>
        <div className="form-group">
          <label>Status</label>
          <select value={model.status || 'active'} onChange={e => setField('status', e.target.value)}>
            <option value="active">Active</option>
            <option value="inactive">Inactive</option>
            <option value="testing">Testing</option>
            <option value="deprecated">Deprecated</option>
          </select>
        </div>
      </div>

      <div className="form-group">
        <label>Description</label>
        <input
          type="text"
          value={model.description || ''}
          onChange={e => setField('description', e.target.value)}
          placeholder="Optional notes"
        />
      </div>

      <div className="form-row">
        <div className="form-group">
          <label>Model Name</label>
          <input
            type="text"
            value={model.model_name || ''}
            onChange={e => setField('model_name', e.target.value)}
            placeholder={provider === 'ollama' ? 'nomic-embed-text' : 'all-MiniLM-L6-v2'}
            disabled={isEdit}
          />
        </div>
        <div className="form-group">
          <label>Dimension</label>
          <input
            type="number"
            value={model.dimension ?? ''}
            onChange={e => setField('dimension', parseInt(e.target.value, 10) || '')}
            placeholder="e.g., 768"
            disabled={isEdit}
          />
        </div>
      </div>

      <div className="form-row">
        <div className="form-group">
          <label>Max Input Length</label>
          <input
            type="number"
            value={model.max_input_length ?? 512}
            onChange={e => setField('max_input_length', parseInt(e.target.value, 10) || 0)}
          />
        </div>
        <div className="form-group">
          <label>Batch Size</label>
          <input
            type="number"
            value={model.batch_size ?? 32}
            onChange={e => setField('batch_size', parseInt(e.target.value, 10) || 0)}
          />
        </div>
      </div>

      <div className="form-row">
        <div className="form-group">
          <label>Normalize Embeddings</label>
          <select
            value={model.normalize === false ? 'false' : 'true'}
            onChange={e => setField('normalize', e.target.value === 'true')}
          >
            <option value="true">Yes</option>
            <option value="false">No</option>
          </select>
        </div>
        <div className="form-group">
          <label>Default Model</label>
          <select
            value={model.is_default ? 'true' : 'false'}
            onChange={e => setField('is_default', e.target.value === 'true')}
          >
            <option value="false">No</option>
            <option value="true">Yes</option>
          </select>
        </div>
      </div>

      {provider !== 'sentence_transformers' && (
        <div className="form-row">
          <div className="form-group">
            <label>Endpoint (optional)</label>
            <input
              type="text"
              value={model.custom_endpoint || ''}
              onChange={e => setField('custom_endpoint', e.target.value)}
              placeholder={provider === 'ollama' ? 'http://localhost:11434' : 'https://api.openai.com/v1'}
            />
          </div>
          <div className="form-group">
            <label>API Key (optional)</label>
            <input
              type="password"
              value={customApiKeyIsMasked ? '' : (model.custom_api_key || '')}
              onChange={e => setField('custom_api_key', e.target.value)}
              placeholder={provider === 'ollama' ? 'N/A for Ollama' : (customApiKeyIsMasked ? '******** (unchanged)' : 'Enter API key')}
              disabled={provider === 'ollama'}
            />
            {customApiKeyIsMasked && provider !== 'ollama' && (
              <div style={{ color: 'var(--text-muted)', fontSize: '12px', marginTop: '6px' }}>
                API key is masked. Leave blank to keep existing; enter a new value to rotate it.
              </div>
            )}
          </div>
        </div>
      )}
    </>
  );
}

export default EmbeddingModelForm;
