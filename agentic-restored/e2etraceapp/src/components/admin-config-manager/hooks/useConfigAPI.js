/**
 * Custom hook for API operations on admin configuration
 */
import { useCallback } from 'react';
import { formatApiError } from '../utils/apiErrorFormatter';
import { buildPayload } from '../utils/payloadBuilder';
import { getSaveValidationError } from '../utils/validators';

const API_BASE = `${process.env.VITE_API_BASE_URL || ''}/api/admin/config`;

export const useConfigAPI = (state, showMessage) => {
  const {
    setLoading,
    setData,
    setHealth,
    setTestingId,
    setTestResults,
    setModalOpen,
    data
  } = state;

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const [llmRes, embRes, connRes, sysRes, flagRes, healthRes] = await Promise.all([
        fetch(`${API_BASE}/llm-providers`),
        fetch(`${API_BASE}/embedding-models`),
        fetch(`${API_BASE}/connections`),
        fetch(`${API_BASE}/system`),
        fetch(`${API_BASE}/feature-flags`),
        fetch(`${API_BASE}/health`)
      ]);

      const [llm, emb, conn, sys, flags, health] = await Promise.all([
        llmRes.json(),
        embRes.json(),
        connRes.json(),
        sysRes.json(),
        flagRes.json(),
        healthRes.json()
      ]);

      setData({
        llmProviders: llm,
        embeddingModels: emb,
        connections: conn,
        systemConfigs: sys,
        featureFlags: flags
      });
      setHealth(health);
    } catch (err) {
      showMessage('Failed to load configuration data', true);
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, [setLoading, setData, setHealth, showMessage]);

  const handleTestConnection = useCallback(async (id) => {
    setTestingId(id);
    try {
      const res = await fetch(`${API_BASE}/connections/${id}/test`, { method: 'POST' });
      const result = await res.json();
      setTestResults(prev => ({ ...prev, [id]: result }));
      if (result.success) {
        showMessage('Connection test successful');
      } else {
        showMessage(`Connection test failed: ${result.error || result.message || 'Unknown error'}`, true);
      }
    } catch (err) {
      setTestResults(prev => ({ ...prev, [id]: { success: false, error: err.message } }));
      showMessage(`Connection test failed: ${err.message}`, true);
    } finally {
      setTestingId(null);
    }
  }, [setTestingId, setTestResults, showMessage]);

  const handleTestLLM = useCallback(async (id) => {
    setTestingId(id);
    try {
      const res = await fetch(`${API_BASE}/llm-providers/${id}/test`, { method: 'POST' });
      const result = await res.json();
      if (result.success) {
        showMessage('LLM provider test successful');
      } else {
        showMessage(`LLM test failed: ${result.error || 'Check API key and endpoint'}`, true);
      }
    } catch (err) {
      showMessage(`LLM test failed: ${err.message}`, true);
    } finally {
      setTestingId(null);
    }
  }, [setTestingId, showMessage]);

  const handleTestEmbedding = useCallback(async (id) => {
    setTestingId(id);
    try {
      const res = await fetch(`${API_BASE}/embedding-models/${id}/test`, { method: 'POST' });
      const result = await res.json();
      if (result.success) {
        showMessage('Embedding model test successful');
      } else {
        showMessage(`Embedding test failed: ${result.error || 'Check configuration'}`, true);
      }
    } catch (err) {
      showMessage(`Embedding test failed: ${err.message}`, true);
    } finally {
      setTestingId(null);
    }
  }, [setTestingId, showMessage]);

  const handleSave = useCallback(async (editItem, modalType, isNewItem) => {
    try {
      let endpoint, method;
      const isEdit = !isNewItem;

      const validationError = getSaveValidationError(editItem, modalType);
      if (validationError) {
        showMessage(validationError, true);
        return;
      }

      const payload = buildPayload(editItem, modalType);

      switch (modalType) {
        case 'llm':
          endpoint = isEdit ? `${API_BASE}/llm-providers/${editItem.id}` : `${API_BASE}/llm-providers`;
          break;
        case 'embedding':
          endpoint = isEdit ? `${API_BASE}/embedding-models/${editItem.id}` : `${API_BASE}/embedding-models`;
          break;
        case 'connection':
          endpoint = isEdit ? `${API_BASE}/connections/${editItem.id}` : `${API_BASE}/connections`;
          break;
        case 'setting':
          endpoint = isEdit ? `${API_BASE}/system/${editItem.id}` : `${API_BASE}/system`;
          break;
        case 'flag':
          endpoint = isEdit ? `${API_BASE}/feature-flags/${editItem.id}` : `${API_BASE}/feature-flags`;
          break;
        default:
          return;
      }

      method = isEdit ? 'PUT' : 'POST';

      const res = await fetch(endpoint, {
        method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      if (!res.ok) {
        let errPayload = null;
        try {
          errPayload = await res.json();
        } catch (_e) {
          // ignore
        }
        const msg = formatApiError(errPayload) || `Save failed (HTTP ${res.status})`;
        throw new Error(msg);
      }

      setModalOpen(false);
      showMessage('Configuration saved successfully');
      await fetchData();
    } catch (err) {
      showMessage(`Save failed: ${err.message}`, true);
    }
  }, [showMessage, fetchData, setModalOpen]);

  const handleDelete = useCallback(async (type, id) => {
    if (!window.confirm('Are you sure you want to delete this configuration?')) return;

    try {
      let endpoint;
      switch (type) {
        case 'llm': endpoint = `${API_BASE}/llm-providers/${id}`; break;
        case 'embedding': endpoint = `${API_BASE}/embedding-models/${id}`; break;
        case 'connection': endpoint = `${API_BASE}/connections/${id}`; break;
        case 'setting': endpoint = `${API_BASE}/system/${id}`; break;
        case 'flag': endpoint = `${API_BASE}/feature-flags/${id}`; break;
        default: return;
      }

      await fetch(endpoint, { method: 'DELETE' });
      showMessage('Configuration deleted');
      await fetchData();
    } catch (err) {
      showMessage(`Delete failed: ${err.message}`, true);
    }
  }, [showMessage, fetchData]);

  const handleToggleFlag = useCallback(async (flag) => {
    try {
      await fetch(`${API_BASE}/feature-flags/${flag.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ enabled: !flag.enabled })
      });
      await fetchData();
    } catch (err) {
      showMessage(`Toggle failed: ${err.message}`, true);
    }
  }, [showMessage, fetchData]);

  const handleClearCache = useCallback(async () => {
    try {
      await fetch(`${API_BASE}/cache/invalidate`, { method: 'POST' });
      showMessage('Configuration cache cleared');
    } catch (err) {
      showMessage(`Cache clear failed: ${err.message}`, true);
    }
  }, [showMessage]);

  return {
    fetchData,
    handleTestConnection,
    handleTestLLM,
    handleTestEmbedding,
    handleSave,
    handleDelete,
    handleToggleFlag,
    handleClearCache
  };
};
