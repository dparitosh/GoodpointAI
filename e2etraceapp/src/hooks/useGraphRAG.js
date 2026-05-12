/**
 * GraphRAG Integration Hook - Corporate Standard Implementation
 * Provides React hooks for Neo4j GraphRAG AI-powered operations
 * per corporate standards.
 */

import { useState, useCallback, useEffect, useRef } from 'react';
import graphIntegrationService from '../services/GraphIntegrationService.js';

/**
 * Hook for GraphRAG AI-powered queries
 * Combines graph context with semantic search for intelligent responses
 * @returns {Object} GraphRAG state and methods
 */
export const useGraphRAGQuery = () => {
  const [answers, setAnswers] = useState([]);
  const [sources, setSources] = useState([]);
  const [toolsInvoked, setToolsInvoked] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [latencyMs, setLatencyMs] = useState(0);

  const executeQuery = useCallback(async (question, options = {}) => {
    const { context = null, tools = null, topK = 5 } = options;
    
    setIsLoading(true);
    setError(null);

    try {
      const result = await graphIntegrationService.executeGraphRAGQuery(
        question,
        context,
        tools,
        topK
      );
      
      setAnswers(result.answers || []);
      setSources(result.sources || []);
      setToolsInvoked(result.tools_invoked || []);
      setLatencyMs(result.latency_ms || 0);
      
      if (result.error) {
        setError(result.error);
      }
      
      return result;
    } catch (err) {
      const errorMsg = err.message || 'GraphRAG query failed';
      setError(errorMsg);
      throw err;
    } finally {
      setIsLoading(false);
    }
  }, []);

  const reset = useCallback(() => {
    setAnswers([]);
    setSources([]);
    setToolsInvoked([]);
    setError(null);
    setLatencyMs(0);
    setIsLoading(false);
  }, []);

  return {
    answers,
    sources,
    toolsInvoked,
    isLoading,
    error,
    latencyMs,
    executeQuery,
    reset
  };
};

/**
 * Hook for GraphRAG health monitoring
 * @returns {Object} Health state and methods
 */
export const useGraphRAGHealth = () => {
  const [health, setHealth] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const intervalRef = useRef(null);

  const checkHealth = useCallback(async () => {
    setIsLoading(true);
    setError(null);

    try {
      const result = await graphIntegrationService.checkGraphRAGHealth();
      setHealth(result);
      return result;
    } catch (err) {
      const errorMsg = err.message || 'Health check failed';
      setError(errorMsg);
      setHealth({ status: 'unavailable', neo4j_connected: false });
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

  const startPolling = useCallback((intervalMs = 30000) => {
    stopPolling();
    checkHealth();
    intervalRef.current = setInterval(checkHealth, intervalMs);
  }, [checkHealth, stopPolling]);

  useEffect(() => {
    return () => stopPolling();
  }, [stopPolling]);

  return {
    health,
    isLoading,
    error,
    checkHealth,
    startPolling,
    stopPolling
  };
};

/**
 * Hook for GraphRAG tools listing
 * @returns {Object} Tools state and methods
 */
export const useGraphRAGTools = () => {
  const [tools, setTools] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);

  const loadTools = useCallback(async () => {
    setIsLoading(true);
    setError(null);

    try {
      const result = await graphIntegrationService.listGraphRAGTools();
      setTools(Array.isArray(result.tools) ? result.tools : result);
      return result;
    } catch (err) {
      const errorMsg = err.message || 'Failed to list tools';
      setError(errorMsg);
      throw err;
    } finally {
      setIsLoading(false);
    }
  }, []);

  return {
    tools,
    isLoading,
    error,
    loadTools
  };
};

/**
 * Combined hook for AI-powered suggestions using GraphRAG
 * Useful for mapping suggestions, validation hints, and data analysis
 * @returns {Object} AI suggestion state and methods
 */
export const useAISuggestions = () => {
  const [suggestions, setSuggestions] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);

  const getMappingSuggestions = useCallback(async (sourceSchema, targetSchema) => {
    setIsLoading(true);
    setError(null);

    try {
      const question = `Given a source schema with fields: ${JSON.stringify(sourceSchema)} 
        and a target schema with fields: ${JSON.stringify(targetSchema)}, 
        suggest optimal field mappings and transformations.`;
      
      const result = await graphIntegrationService.executeGraphRAGQuery(
        question,
        'data mapping optimization',
        ['mapping_analyzer'],
        10
      );
      
      const mappingSuggestions = result.answers.map((answer, idx) => ({
        id: idx,
        suggestion: answer,
        confidence: result.sources[idx]?.score || 0.8,
        source: result.sources[idx]?.source || 'GraphRAG'
      }));
      
      setSuggestions(mappingSuggestions);
      return mappingSuggestions;
    } catch (err) {
      const errorMsg = err.message || 'Failed to get mapping suggestions';
      setError(errorMsg);
      return [];
    } finally {
      setIsLoading(false);
    }
  }, []);

  const getValidationInsights = useCallback(async (dataSchema, validationRules) => {
    setIsLoading(true);
    setError(null);

    try {
      const question = `Analyze the data schema: ${JSON.stringify(dataSchema)} 
        with validation rules: ${JSON.stringify(validationRules)}. 
        Identify potential data quality issues and suggest improvements.`;
      
      const result = await graphIntegrationService.executeGraphRAGQuery(
        question,
        'data quality analysis',
        ['quality_analyzer'],
        5
      );
      
      const insights = result.answers.map((answer, idx) => ({
        id: idx,
        insight: answer,
        severity: result.sources[idx]?.severity || 'info',
        recommendation: result.sources[idx]?.recommendation || ''
      }));
      
      setSuggestions(insights);
      return insights;
    } catch (err) {
      const errorMsg = err.message || 'Failed to get validation insights';
      setError(errorMsg);
      return [];
    } finally {
      setIsLoading(false);
    }
  }, []);

  const getDataAnalysis = useCallback(async (data, analysisType = 'general') => {
    setIsLoading(true);
    setError(null);

    try {
      const sampleData = Array.isArray(data) ? data.slice(0, 10) : data;
      const question = `Perform ${analysisType} analysis on the following data sample: 
        ${JSON.stringify(sampleData)}. 
        Provide insights about data patterns, anomalies, and quality.`;
      
      const result = await graphIntegrationService.executeGraphRAGQuery(
        question,
        `${analysisType} data analysis`,
        ['data_analyzer'],
        5
      );
      
      setSuggestions(result.answers || []);
      return result;
    } catch (err) {
      const errorMsg = err.message || 'Failed to analyze data';
      setError(errorMsg);
      return { answers: [], sources: [] };
    } finally {
      setIsLoading(false);
    }
  }, []);

  const reset = useCallback(() => {
    setSuggestions([]);
    setError(null);
    setIsLoading(false);
  }, []);

  return {
    suggestions,
    isLoading,
    error,
    getMappingSuggestions,
    getValidationInsights,
    getDataAnalysis,
    reset
  };
};

export default {
  useGraphRAGQuery,
  useGraphRAGHealth,
  useGraphRAGTools,
  useAISuggestions
};
