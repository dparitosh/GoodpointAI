/**
 * GraphQL Integration Hook - Corporate Standard Implementation
 * Provides React hooks for GraphQL operations with proper state management
 * and error handling per corporate standards.
 */

import { useState, useCallback, useRef, useEffect } from 'react';
import graphIntegrationService from '../services/GraphIntegrationService.js';

/**
 * Hook for GraphQL schema introspection
 * @returns {Object} Introspection state and methods
 */
export const useSchemaIntrospection = () => {
  const [schema, setSchema] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const abortControllerRef = useRef(null);

  const introspect = useCallback(async (content, format, name) => {
    // Cancel any pending request
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    abortControllerRef.current = new AbortController();

    setIsLoading(true);
    setError(null);

    try {
      const result = await graphIntegrationService.introspectSchema(content, format, name);
      setSchema(result);
      return result;
    } catch (err) {
      if (err.name !== 'AbortError') {
        const errorMsg = err.message || 'Schema introspection failed';
        setError(errorMsg);
        throw err;
      }
    } finally {
      setIsLoading(false);
    }
  }, []);

  const reset = useCallback(() => {
    setSchema(null);
    setError(null);
    setIsLoading(false);
  }, []);

  useEffect(() => {
    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
    };
  }, []);

  return {
    schema,
    isLoading,
    error,
    introspect,
    reset
  };
};

/**
 * Hook for GraphQL query execution
 * @returns {Object} Query state and methods
 */
export const useGraphQLQuery = () => {
  const [data, setData] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);

  const executeQuery = useCallback(async (query, sourceData, variables = null) => {
    setIsLoading(true);
    setError(null);

    try {
      const result = await graphIntegrationService.executeGraphQLQuery(query, sourceData, variables);
      
      if (result.errors && result.errors.length > 0) {
        setError(result.errors.map(e => e.message).join(', '));
      } else {
        setData(result.data);
      }
      
      return result;
    } catch (err) {
      const errorMsg = err.message || 'Query execution failed';
      setError(errorMsg);
      throw err;
    } finally {
      setIsLoading(false);
    }
  }, []);

  const reset = useCallback(() => {
    setData(null);
    setError(null);
    setIsLoading(false);
  }, []);

  return {
    data,
    isLoading,
    error,
    executeQuery,
    reset
  };
};

/**
 * Hook for GraphQL data transformation
 * @returns {Object} Transform state and methods
 */
export const useGraphQLTransform = () => {
  const [transformedData, setTransformedData] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [stats, setStats] = useState({ applied: 0, failed: 0 });

  const transform = useCallback(async (sourceData, targetData, mappings) => {
    setIsLoading(true);
    setError(null);

    try {
      // Convert mapping format to GraphQL transform format
      const transformMappings = mappings.map(m => ({
        source_field: m.sourceField || m.source_field,
        target_field: m.targetField || m.target_field,
        transformation: m.transformation || null
      }));

      const result = await graphIntegrationService.transformData(
        sourceData, 
        targetData, 
        transformMappings
      );
      
      setTransformedData(result.transformed_data);
      setStats({
        applied: result.mappings_applied,
        failed: result.mappings_failed
      });
      
      if (result.errors && result.errors.length > 0) {
        setError(result.errors.map(e => e.message || e.error).join(', '));
      }
      
      return result;
    } catch (err) {
      const errorMsg = err.message || 'Data transformation failed';
      setError(errorMsg);
      throw err;
    } finally {
      setIsLoading(false);
    }
  }, []);

  const reset = useCallback(() => {
    setTransformedData(null);
    setError(null);
    setStats({ applied: 0, failed: 0 });
    setIsLoading(false);
  }, []);

  return {
    transformedData,
    isLoading,
    error,
    stats,
    transform,
    reset
  };
};

/**
 * Hook for GraphQL Catalogue (persisted queries)
 * @returns {Object} Catalogue state and methods
 */
export const useGraphQLCatalogue = () => {
  const [queries, setQueries] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [pagination, setPagination] = useState({ total: 0, limit: 100, offset: 0 });

  const loadQueries = useCallback(async (limit = 100, offset = 0) => {
    setIsLoading(true);
    setError(null);

    try {
      const result = await graphIntegrationService.listPersistedQueries(limit, offset);
      setQueries(Array.isArray(result.queries) ? result.queries : result);
      setPagination({
        total: result.total || (Array.isArray(result) ? result.length : 0),
        limit,
        offset
      });
      return result;
    } catch (err) {
      const errorMsg = err.message || 'Failed to load queries';
      setError(errorMsg);
      throw err;
    } finally {
      setIsLoading(false);
    }
  }, []);

  const saveQuery = useCallback(async (name, query, description, format = 'json') => {
    setIsLoading(true);
    setError(null);

    try {
      const result = await graphIntegrationService.saveQuery(name, query, description, format);
      // Refresh the list after saving
      await loadQueries(pagination.limit, pagination.offset);
      return result;
    } catch (err) {
      const errorMsg = err.message || 'Failed to save query';
      setError(errorMsg);
      throw err;
    } finally {
      setIsLoading(false);
    }
  }, [loadQueries, pagination.limit, pagination.offset]);

  return {
    queries,
    isLoading,
    error,
    pagination,
    loadQueries,
    saveQuery
  };
};

export default {
  useSchemaIntrospection,
  useGraphQLQuery,
  useGraphQLTransform,
  useGraphQLCatalogue
};
