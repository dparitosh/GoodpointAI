import { e2etraceFetchWithRetry } from '../api/e2etrace-api';
import { API_CONFIG } from './api-config.js';

let runtimeConfigPromise = null;

export async function getRuntimeConfig({ forceRefresh = false } = {}) {
  if (forceRefresh) {
    runtimeConfigPromise = null;
  }

  if (!runtimeConfigPromise) {
    runtimeConfigPromise = (async () => {
      try {
        const response = await e2etraceFetchWithRetry(API_CONFIG.ENDPOINTS.RUNTIME_CONFIG, { method: 'GET' });
        const json = await response.json();
        return json && typeof json === 'object' ? json : null;
      } catch {
        return null;
      }
    })();
  }

  return await runtimeConfigPromise;
}

export function clearRuntimeConfigCache() {
  runtimeConfigPromise = null;
}
