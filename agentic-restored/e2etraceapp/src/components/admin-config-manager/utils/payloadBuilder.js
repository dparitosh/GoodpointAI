/**
 * Build API request payloads with proper validation and field filtering
 */

const stripEmpty = (obj) => {
  const out = {};
  Object.entries(obj || {}).forEach(([k, v]) => {
    if (v === undefined) return;
    if (v === null) return;
    if (typeof v === 'string' && v.trim() === '') return;
    out[k] = v;
  });
  return out;
};

export const buildPayload = (editItem, modalType) => {
  const isEdit = editItem?._isNew === false;

  switch (modalType) {
    case 'llm': {
      if (!isEdit) {
        // create: id is optional (server will generate one if omitted)
        return stripEmpty({
          id: editItem.id,
          provider: editItem.provider,
          name: editItem.name,
          description: editItem.description,
          api_key: editItem.api_key,
          api_endpoint: editItem.api_endpoint,
          api_version: editItem.api_version,
          azure_deployment: editItem.azure_deployment,
          azure_resource_name: editItem.azure_resource_name,
          default_chat_model: editItem.default_chat_model,
          default_completion_model: editItem.default_completion_model,
          default_embedding_model: editItem.default_embedding_model,
          default_temperature: editItem.default_temperature,
          default_max_tokens: editItem.default_max_tokens,
          default_top_p: editItem.default_top_p,
          rate_limit_rpm: editItem.rate_limit_rpm,
          rate_limit_tpm: editItem.rate_limit_tpm,
          status: editItem.status,
          is_default: editItem.is_default,
          priority: editItem.priority,
          extra_config: editItem.extra_config,
        });
      }

      // update: do not send api_key unless user typed it (avoid clearing existing keys)
      return stripEmpty({
        name: editItem.name,
        description: editItem.description,
        api_endpoint: editItem.api_endpoint,
        api_version: editItem.api_version,
        azure_deployment: editItem.azure_deployment,
        azure_resource_name: editItem.azure_resource_name,
        default_chat_model: editItem.default_chat_model,
        default_temperature: editItem.default_temperature,
        default_max_tokens: editItem.default_max_tokens,
        rate_limit_rpm: editItem.rate_limit_rpm,
        rate_limit_tpm: editItem.rate_limit_tpm,
        status: editItem.status,
        is_default: editItem.is_default,
        priority: editItem.priority,
        extra_config: editItem.extra_config,
        ...(typeof editItem.api_key === 'string' && editItem.api_key.trim() ? { api_key: editItem.api_key } : {}),
      });
    }

    case 'embedding': {
      if (!isEdit) {
        return stripEmpty({
          id: editItem.id,
          provider: editItem.provider,
          name: editItem.name,
          description: editItem.description,
          model_name: editItem.model_name,
          dimension: editItem.dimension,
          max_input_length: editItem.max_input_length,
          llm_provider_id: editItem.llm_provider_id,
          custom_endpoint: editItem.custom_endpoint,
          custom_api_key: editItem.custom_api_key,
          batch_size: editItem.batch_size,
          normalize: editItem.normalize,
          cost_per_1k_tokens: editItem.cost_per_1k_tokens,
          status: editItem.status,
          is_default: editItem.is_default,
        });
      }

      // update model only supports these fields
      const update = stripEmpty({
        name: editItem.name,
        description: editItem.description,
        max_input_length: editItem.max_input_length,
        llm_provider_id: editItem.llm_provider_id,
        batch_size: editItem.batch_size,
        normalize: editItem.normalize,
        status: editItem.status,
        is_default: editItem.is_default,
      });

      // Only send secrets/endpoint if user provided a value (avoid wiping).
      if (typeof editItem.custom_endpoint === 'string' && editItem.custom_endpoint.trim()) {
        update.custom_endpoint = editItem.custom_endpoint;
      }
      if (typeof editItem.custom_api_key === 'string' && editItem.custom_api_key.trim()) {
        if (!editItem.custom_api_key.includes('*')) {
          update.custom_api_key = editItem.custom_api_key;
        }
      }

      return update;
    }

    case 'connection': {
      if (!isEdit) {
        return stripEmpty({
          id: editItem.id,
          connection_type: editItem.connection_type,
          name: editItem.name,
          description: editItem.description,
          connection_string: editItem.connection_string,
          host: editItem.host,
          port: editItem.port,
          database: editItem.database,
          username: editItem.username,
          password: editItem.password,
          use_ssl: editItem.use_ssl,
          ssl_cert_path: editItem.ssl_cert_path,
          pool_size: editItem.pool_size,
          max_overflow: editItem.max_overflow,
          pool_timeout: editItem.pool_timeout,
          extra_options: editItem.extra_options,
          status: editItem.status,
          is_default: editItem.is_default,
        });
      }

      // update: avoid sending empty secrets
      const base = stripEmpty({
        name: editItem.name,
        description: editItem.description,
        host: editItem.host,
        port: editItem.port,
        database: editItem.database,
        username: editItem.username,
        use_ssl: editItem.use_ssl,
        pool_size: editItem.pool_size,
        status: editItem.status,
        is_default: editItem.is_default,
      });

      if (typeof editItem.password === 'string' && editItem.password.trim()) {
        base.password = editItem.password;
      }
      if (typeof editItem.connection_string === 'string' && editItem.connection_string.trim() && !editItem.connection_string.includes('*')) {
        base.connection_string = editItem.connection_string;
      }
      return base;
    }

    case 'setting': {
      if (!isEdit) {
        return stripEmpty({
          category: editItem.category,
          key: editItem.key,
          value: editItem.value,
          value_type: editItem.value_type,
          description: editItem.description,
          is_secret: editItem.is_secret,
          is_required: editItem.is_required,
          default_value: editItem.default_value,
          validation_regex: editItem.validation_regex,
          enabled: editItem.enabled,
        });
      }

      // Update supports: value, description, enabled, validation_regex
      const update = stripEmpty({
        description: editItem.description,
        enabled: editItem.enabled,
        validation_regex: editItem.validation_regex,
      });

      // Only send value if user actually provided a new one.
      if (typeof editItem.value === 'string' && editItem.value.trim() && !editItem.value.includes('*')) {
        update.value = editItem.value;
      }
      return update;
    }

    case 'flag': {
      const normalizeTargeting = () => {
        const v = editItem.targeting_rules;
        if (v === undefined || v === null) return undefined;
        if (typeof v === 'string') {
          if (!v.trim()) return undefined;
          try {
            return JSON.parse(v);
          } catch (_e) {
            throw new Error('Targeting Rules must be valid JSON');
          }
        }
        return v;
      };

      if (!isEdit) {
        return stripEmpty({
          id: editItem.id,
          name: editItem.name,
          description: editItem.description,
          enabled: editItem.enabled,
          rollout_percentage: editItem.rollout_percentage,
          targeting_rules: normalizeTargeting(),
        });
      }

      return stripEmpty({
        name: editItem.name,
        description: editItem.description,
        enabled: editItem.enabled,
        rollout_percentage: editItem.rollout_percentage,
        targeting_rules: normalizeTargeting(),
      });
    }

    default:
      return editItem;
  }
};
