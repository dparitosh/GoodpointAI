/**
 * Agentic Configuration Hook - Corporate Standard Implementation
 * Provides React hooks for Agentic AI orchestration configuration
 * per corporate standards.
 */

import { useState, useCallback, useEffect, useRef } from 'react';
import { e2etraceFetchWithRetry } from '../api/e2etrace-api.js';
import { API_CONFIG } from '../config/api-config.js';

const AGENTIC_API_BASE = API_CONFIG.ENDPOINTS.AGENTIC_ORCHESTRATION_CONFIG;
const AGENTIC_SYSTEM_API = API_CONFIG.ENDPOINTS.AGENTIC_SYSTEM;

/**
 * Hook for Agentic Configuration management
 * @returns {Object} Configuration state and methods
 */
export const useAgenticConfig = () => {
  const [config, setConfig] = useState(null);
  const [schema, setSchema] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [validationResult, setValidationResult] = useState(null);

  const loadConfig = useCallback(async () => {
    setIsLoading(true);
    setError(null);

    try {
      const response = await e2etraceFetchWithRetry(AGENTIC_API_BASE);
      const data = await response.json();
      
      if (data.status === 'success') {
        setConfig(data.data);
      } else {
        setConfig(data);
      }
      
      return data;
    } catch (err) {
      const errorMsg = err.message || 'Failed to load configuration';
      setError(errorMsg);
      throw err;
    } finally {
      setIsLoading(false);
    }
  }, []);

  const loadSchema = useCallback(async () => {
    setIsLoading(true);
    setError(null);

    try {
      const response = await e2etraceFetchWithRetry(`${AGENTIC_API_BASE}/schema`);
      const data = await response.json();
      
      if (data.status === 'success') {
        setSchema(data.schema);
      } else {
        setSchema(data);
      }
      
      return data;
    } catch (err) {
      const errorMsg = err.message || 'Failed to load schema';
      setError(errorMsg);
      throw err;
    } finally {
      setIsLoading(false);
    }
  }, []);

  const updateConfig = useCallback(async (configUpdate, triggerDeployment = true) => {
    setIsLoading(true);
    setError(null);

    try {
      const response = await e2etraceFetchWithRetry(
        `${AGENTIC_API_BASE}?trigger_deployment=${triggerDeployment}`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(configUpdate)
        }
      );
      const data = await response.json();
      
      // Reload config after update
      await loadConfig();
      
      return data;
    } catch (err) {
      const errorMsg = err.message || 'Failed to update configuration';
      setError(errorMsg);
      throw err;
    } finally {
      setIsLoading(false);
    }
  }, [loadConfig]);

  const validateConfig = useCallback(async (configData) => {
    setIsLoading(true);
    setError(null);

    try {
      const response = await e2etraceFetchWithRetry(`${AGENTIC_API_BASE}/validate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(configData)
      });
      const data = await response.json();
      
      setValidationResult(data);
      return data;
    } catch (err) {
      const errorMsg = err.message || 'Validation failed';
      setError(errorMsg);
      throw err;
    } finally {
      setIsLoading(false);
    }
  }, []);

  return {
    config,
    schema,
    validationResult,
    isLoading,
    error,
    loadConfig,
    loadSchema,
    updateConfig,
    validateConfig
  };
};

/**
 * Hook for Agentic System Status monitoring
 * @returns {Object} System status state and methods
 */
export const useAgenticSystemStatus = () => {
  const [status, setStatus] = useState(null);
  const [activeAgents, setActiveAgents] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const intervalRef = useRef(null);

  const checkStatus = useCallback(async () => {
    setIsLoading(true);
    setError(null);

    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 5000);
      let response;
      try {
        // Use plain fetch (no retries) — this is a best-effort health probe.
        // Retries here cause console spam when the backend is starting up.
        response = await fetch(`${AGENTIC_SYSTEM_API}/status`, { signal: controller.signal });
      } finally {
        clearTimeout(timeoutId);
      }
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();
      
      // Normalize response: ensure status field is set (use system_health as fallback)
      const normalizedStatus = {
        ...data,
        status: data.status || data.system_health || 'unknown'
      };
      
      setStatus(normalizedStatus);
      setActiveAgents(data.active_agents || []);
      
      return normalizedStatus;
    } catch (err) {
      const errorMsg = err.name === 'AbortError' ? 'unavailable' : (err.message || 'Status check failed');
      setError(errorMsg);
      setStatus({ status: 'unavailable', system_health: 'unavailable' });
      // Don't throw - this is a health check
      return { status: 'unavailable', error: errorMsg };
    } finally {
      setIsLoading(false);
    }
  }, []);

  const stopPolling = useCallback(() => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
  }, []);

  const startPolling = useCallback((intervalMs = 15000) => {
    stopPolling();
    checkStatus();
    intervalRef.current = setInterval(checkStatus, intervalMs);
  }, [checkStatus, stopPolling]);

  useEffect(() => {
    return () => stopPolling();
  }, [stopPolling]);

  return {
    status,
    activeAgents,
    isLoading,
    error,
    checkStatus,
    startPolling,
    stopPolling
  };
};

/**
 * Hook for Deployment management
 * @returns {Object} Deployment state and methods
 */
export const useAgenticDeployment = () => {
  const [deploymentStatus, setDeploymentStatus] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const intervalRef = useRef(null);

  const checkDeploymentStatus = useCallback(async () => {
    setIsLoading(true);
    setError(null);

    try {
      const response = await e2etraceFetchWithRetry(`${AGENTIC_API_BASE}/deployment/status`);
      const data = await response.json();
      
      setDeploymentStatus(data);
      return data;
    } catch (err) {
      const errorMsg = err.message || 'Deployment status check failed';
      setError(errorMsg);
      return { status: 'error', error: errorMsg };
    } finally {
      setIsLoading(false);
    }
  }, []);

  const triggerDeployment = useCallback(async () => {
    setIsLoading(true);
    setError(null);

    try {
      const response = await e2etraceFetchWithRetry(`${AGENTIC_API_BASE}/deployment/trigger`, {
        method: 'POST'
      });
      const data = await response.json();
      
      setDeploymentStatus(data);
      return data;
    } catch (err) {
      const errorMsg = err.message || 'Deployment trigger failed';
      setError(errorMsg);
      throw err;
    } finally {
      setIsLoading(false);
    }
  }, []);

  const stopPolling = useCallback(() => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
  }, []);

  const startPolling = useCallback((intervalMs = 5000) => {
    stopPolling();
    checkDeploymentStatus();
    intervalRef.current = setInterval(checkDeploymentStatus, intervalMs);
  }, [checkDeploymentStatus, stopPolling]);

  useEffect(() => {
    return () => stopPolling();
  }, [stopPolling]);

  return {
    deploymentStatus,
    isLoading,
    error,
    checkDeploymentStatus,
    triggerDeployment,
    startPolling,
    stopPolling
  };
};

/**
 * Combined hook for full Agentic AI integration
 * @returns {Object} Combined Agentic AI state and methods
 */
export const useAgenticAI = () => {
  const config = useAgenticConfig();
  const system = useAgenticSystemStatus();
  const deployment = useAgenticDeployment();

  const initialize = useCallback(async () => {
    const results = await Promise.allSettled([
      config.loadConfig(),
      config.loadSchema(),
      system.checkStatus()
    ]);
    const failures = results.filter(r => r.status === 'rejected');
    return { ok: failures.length === 0, failures: failures.length };
  }, [config, system]);

  return {
    // Configuration
    config: config.config,
    schema: config.schema,
    loadConfig: config.loadConfig,
    updateConfig: config.updateConfig,
    validateConfig: config.validateConfig,
    
    // System Status
    systemStatus: system.status,
    activeAgents: system.activeAgents,
    checkSystemStatus: system.checkStatus,
    startSystemPolling: system.startPolling,
    stopSystemPolling: system.stopPolling,
    
    // Deployment
    deploymentStatus: deployment.deploymentStatus,
    checkDeploymentStatus: deployment.checkDeploymentStatus,
    triggerDeployment: deployment.triggerDeployment,
    
    // Combined
    isLoading: config.isLoading || system.isLoading || deployment.isLoading,
    error: config.error || system.error || deployment.error,
    initialize
  };
};

export default {
  useAgenticConfig,
  useAgenticSystemStatus,
  useAgenticDeployment,
  useAgenticAI
};
