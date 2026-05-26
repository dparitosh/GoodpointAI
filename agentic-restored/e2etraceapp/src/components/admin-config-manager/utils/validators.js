/**
 * Validation logic for configuration forms
 */

export const getSaveValidationError = (editItem, modalType) => {
  if (!editItem) return 'Nothing to save';

  if (modalType === 'connection') {
    const ct = String(editItem.connection_type || '').trim();
    const nm = String(editItem.name || '').trim();
    if (!ct) return 'Connection Type is required.';
    if (!nm) return 'Name is required.';

    const apiLike = ['api', 'rest_api', 'webapi', 'openapi', 'odata'].includes(ct.toLowerCase());
    if (apiLike) {
      const endpointUrl = String(editItem.connection_string || '').trim();
      if (!endpointUrl) return 'Base URL / Endpoint (or Service URL) is required for API/OData/OpenAPI connections.';
    }
  }

  if (modalType === 'llm') {
    const provider = String(editItem.provider || '').trim();
    const name = String(editItem.name || '').trim();
    if (!provider) return 'Provider is required.';
    if (!name) return 'Name is required.';
  }

  if (modalType === 'embedding') {
    const provider = String(editItem.provider || '').trim();
    const name = String(editItem.name || '').trim();
    const modelName = String(editItem.model_name || '').trim();
    const dim = editItem.dimension;
    if (!provider) return 'Provider is required.';
    if (!name) return 'Name is required.';
    if (!modelName) return 'Model name is required.';
    if (dim === undefined || dim === null || String(dim).trim() === '') return 'Dimension is required.';
  }

  return null;
};

export const getSaveDisabledReason = (modalOpen, modalType, editItem) => {
  if (!modalOpen) return null;
  if (!editItem) return 'Nothing to save';

  if (modalType === 'connection') {
    const ct = String(editItem.connection_type || '').trim();
    const nm = String(editItem.name || '').trim();
    if (!ct) return 'Connection Type is required';
    if (!nm) return 'Name is required';

    const ctLower = ct.toLowerCase();
    const apiLike = ['api', 'rest_api', 'webapi', 'openapi', 'odata'].includes(ctLower);
    if (apiLike) {
      const endpointUrl = String(editItem.connection_string || '').trim();
      if (!endpointUrl) return 'Base URL / Endpoint is required for API-like connections';
    }

    if (ctLower === 'postgres') {
      // Add postgres-specific validation if needed
    }
  }

  return null;
};
