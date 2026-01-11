/**
 * useLoading Hook
 * Manages loading states for async operations
 */
import { useState, useCallback, useRef } from 'react';

/**
 * Hook for managing loading states
 * @param {boolean} [initialLoading=false] - Initial loading state
 * @returns {Object} Loading state management utilities
 */
export function useLoading(initialLoading = false) {
  const [loading, setLoading] = useState(initialLoading);
  const [error, setError] = useState(null);
  const abortControllerRef = useRef(null);

  /**
   * Start loading state
   */
  const startLoading = useCallback(() => {
    setLoading(true);
    setError(null);
    // Create new abort controller for this operation
    abortControllerRef.current = new AbortController();
    return abortControllerRef.current.signal;
  }, []);

  /**
   * Stop loading state
   */
  const stopLoading = useCallback(() => {
    setLoading(false);
  }, []);

  /**
   * Set error state
   * @param {Error|string} err - Error object or message
   */
  const setLoadingError = useCallback((err) => {
    setError(err instanceof Error ? err.message : err);
    setLoading(false);
  }, []);

  /**
   * Clear error state
   */
  const clearError = useCallback(() => {
    setError(null);
  }, []);

  /**
   * Cancel ongoing operation
   */
  const cancel = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    setLoading(false);
  }, []);

  /**
   * Wrap an async function with loading state management
   * @param {Function} asyncFn - Async function to wrap
   * @returns {Function} Wrapped function
   */
  const withLoading = useCallback((asyncFn) => {
    return async (...args) => {
      const signal = startLoading();
      try {
        const result = await asyncFn(...args, { signal });
        stopLoading();
        return result;
      } catch (err) {
        if (err.name === 'AbortError') {
          // Operation was cancelled
          return null;
        }
        setLoadingError(err);
        throw err;
      }
    };
  }, [startLoading, stopLoading, setLoadingError]);

  return {
    loading,
    error,
    startLoading,
    stopLoading,
    setLoadingError,
    clearError,
    cancel,
    withLoading,
    isLoading: loading, // Alias for convenience
  };
}

/**
 * Hook for managing multiple named loading states
 * @returns {Object} Multi-loading state management utilities
 */
export function useMultiLoading() {
  const [loadingStates, setLoadingStates] = useState({});
  const [errors, setErrors] = useState({});

  /**
   * Start loading for a specific key
   * @param {string} key - Loading state key
   */
  const startLoading = useCallback((key) => {
    setLoadingStates(prev => ({ ...prev, [key]: true }));
    setErrors(prev => {
      const { [key]: _removed, ...rest } = prev;
      return rest;
    });
  }, []);

  /**
   * Stop loading for a specific key
   * @param {string} key - Loading state key
   */
  const stopLoading = useCallback((key) => {
    setLoadingStates(prev => {
      const { [key]: _removed, ...rest } = prev;
      return rest;
    });
  }, []);

  /**
   * Set error for a specific key
   * @param {string} key - Loading state key
   * @param {Error|string} error - Error object or message
   */
  const setError = useCallback((key, error) => {
    setErrors(prev => ({
      ...prev,
      [key]: error instanceof Error ? error.message : error
    }));
    stopLoading(key);
  }, [stopLoading]);

  /**
   * Clear error for a specific key
   * @param {string} key - Loading state key
   */
  const clearError = useCallback((key) => {
    setErrors(prev => {
      const { [key]: _removed, ...rest } = prev;
      return rest;
    });
  }, []);

  /**
   * Check if a specific key is loading
   * @param {string} key - Loading state key
   * @returns {boolean} Whether the key is loading
   */
  const isLoading = useCallback((key) => {
    return !!loadingStates[key];
  }, [loadingStates]);

  /**
   * Get error for a specific key
   * @param {string} key - Loading state key
   * @returns {string|null} Error message or null
   */
  const getError = useCallback((key) => {
    return errors[key] || null;
  }, [errors]);

  /**
   * Check if any loading is in progress
   */
  const anyLoading = Object.keys(loadingStates).length > 0;

  /**
   * Clear all loading states
   */
  const clearAll = useCallback(() => {
    setLoadingStates({});
    setErrors({});
  }, []);

  return {
    loadingStates,
    errors,
    startLoading,
    stopLoading,
    setError,
    clearError,
    isLoading,
    getError,
    anyLoading,
    clearAll,
  };
}

export default useLoading;
