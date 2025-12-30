/**
 * Centralized API Configuration for Neo4j Integration
 * This file manages all API endpoints, ports, and configurations in one place
 */

// Environment-based configuration
const isDevelopment = import.meta.env.DEV;
const isProduction = import.meta.env.PROD;

// Default configuration
const DEFAULT_CONFIG = {
  // Backend API Configuration
  API_BASE_URL: '', // Use Vite proxy in dev; same-origin in prod unless overridden via VITE_API_BASE_URL
  API_TIMEOUT: 30000, // 30 seconds
  API_RETRY_ATTEMPTS: 3,
  API_RETRY_DELAY: 1000, // 1 second
  
  // Neo4j Specific Configuration
  NEO4J_API_VERSION: 'v1',
  NEO4J_DATABASE: 'neo4j',
  
  // Endpoints
  ENDPOINTS: {
    // Health & Status
    HEALTH: '/api/health',
    STATUS: '/api/status',
    
    // Graph Data
    GRAPH: '/api/graph',
    GRAPH_QUERY: '/api/query',
    GRAPH_SCHEMA: '/api/schema',
    ENTITIES: '/api/entities',
    
    // Analytics & Data Quality
    ANALYTICS: '/api/analytics',
    ANALYTICS_NODES: '/api/analytics/nodes',
    ANALYTICS_RELATIONSHIPS: '/api/analytics/relationships',
    DATA_QUALITY: '/api/analytics/quality/dashboard',
    DATA_QUALITY_RULES: '/api/data-quality/rules',
    DATA_QUALITY_SCRUB: '/api/data-quality/scrub',
    DATA_QUALITY_DUPLICATES: '/api/data-quality/duplicates',
    
    // Data Configuration
    DATA_SOURCES: '/api/data-sources',
    DATA_SOURCE_TEST: (sourceId) => `/api/data-sources/${sourceId}/test`,
    DATA_SOURCE_SYNC: (sourceId) => `/api/data-sources/${sourceId}/sync`,
    DATA_SOURCE_TYPES: '/api/data-sources/types/supported',
    SCHEMA_DISCOVERY: '/api/schema/discover',
    
    // Data Mapping
    DATA_MAPPING_RULES: '/api/data-mapping/rules',
    DATA_MAPPING_TEMPLATES: '/api/data-mapping/templates',
    DATA_MAPPING_EXECUTE: (ruleId) => `/api/data-mapping/rules/${ruleId}/execute`,
    DATA_MAPPING_VALIDATE: (ruleId) => `/api/data-mapping/rules/${ruleId}/validate`,
    DATA_MAPPING_APPLY_TEMPLATE: (templateId) => `/api/data-mapping/templates/${templateId}/apply`,
    DATA_MAPPING_FIELD_SUGGESTIONS: (sourceId) => `/api/data-mapping/field-suggestions/${sourceId}`,
    DATA_MAPPING_ANALYTICS: '/api/data-mapping/mapping-analytics',
    
    // Configuration Management
    NEO4J_CONFIG: '/api/config/neo4j',
    NEO4J_CONFIG_TEST: '/api/config/neo4j/test',
    OPENSEARCH_CONFIG: '/api/config/opensearch',
    OPENSEARCH_CONFIG_TEST: '/api/config/opensearch/test',
    CORS_CONFIG: '/api/config/cors',
    SYSTEM_CONFIG: '/api/config/system',
    WORKFLOW_DEFAULTS: '/api/config/workflow-defaults',
    RUNTIME_CONFIG: '/api/config/runtime',
    ENVIRONMENT_STATUS: '/api/config/environment',
    
    // Data Pipelines
    PIPELINES: '/api/pipelines',
    PIPELINE_CREATE: '/api/pipelines',
    PIPELINE_EXECUTE: (pipelineId) => `/api/pipelines/${pipelineId}/execute`,
    PIPELINE_STATUS: (pipelineId) => `/api/pipelines/${pipelineId}/status`,
    PIPELINE_LOGS: (pipelineId) => `/api/pipelines/${pipelineId}/logs`,
    
    // Migration & Mapping
    MIGRATION_PLANS: '/api/migration/plans',
    MIGRATION_EXECUTE: (planId) => `/api/migration/plans/${planId}/execute`,
    MIGRATION_STATUS: (planId) => `/api/migration/plans/${planId}/status`,
    MAPPINGS: '/api/mappings',
    MAPPING_VALIDATE: (mappingId) => `/api/mappings/${mappingId}/validate`,
    MAPPING_TEMPLATES: '/api/mappings/templates',
    
    // Data Flow Monitoring
    FLOW_METRICS: '/api/monitoring/flow-metrics',
    FLOW_ALERTS: '/api/monitoring/alerts',
    FLOW_STATUS: '/api/monitoring/flow-status',
    FLOW_HEALTH: '/api/monitoring/health',
    PERFORMANCE_METRICS: '/api/monitoring/performance-metrics',
    DATA_QUALITY_METRICS: '/api/monitoring/data-quality',
    MONITORING_TEMPLATES: '/api/monitoring/templates',
    
    // Data Conversion & Validation
    DATA_CONVERT: '/api/convert',
    DATA_VALIDATE: '/api/validate',
    CONVERSION_TEMPLATES: '/api/convert/templates',
    
    // Export & Import
    BULK_EXPORT: '/api/bulk/export',
    BULK_IMPORT: '/api/bulk/import',
    EXPORT_FORMATS: '/api/export/formats',
    EXPORT_HISTORY: '/api/export/history',
    
    // Target Applications
    TARGET_APPS: '/api/target-apps',
    TARGET_APP_SYNC: (appId) => `/api/target-apps/${appId}/sync`,
    TARGET_APP_DEPLOY: (appId) => `/api/target-apps/${appId}/deploy`,
    
    // Schema Information
    SCHEMA_LABELS: '/api/schema/labels',
    SCHEMA_RELATIONSHIPS: '/api/schema/relationships',
    SCHEMA_PROPERTIES: '/api/schema/properties',
    SCHEMA_CONSTRAINTS: '/api/schema/constraints',
    
    // Reporting
    REPORTS: '/api/reports',
    REPORT_GENERATE: '/api/reports/generate',
    DASHBOARDS: '/api/dashboards',
    DASHBOARD_DATA: (dashboardId) => `/api/dashboards/${dashboardId}/data`,

    // Workflow Instance Manager
    WORKFLOWS: '/api/workflows',
    WORKFLOW_TEMPLATES: '/api/workflows/templates/list',
    WORKFLOW_INSTANTIATE: (templateId) => `/api/workflows/templates/${templateId}/instantiate`,
    WORKFLOW_EXECUTE: (workflowId) => `/api/workflows/${workflowId}/execute`,
    WORKFLOW_DELETE: (workflowId) => `/api/workflows/${workflowId}`,
    
    // Configuration Management
    CONFIG_BACKUP: '/api/config/backup',
    CONFIG_RESTORE: '/api/config/restore',
    CONFIG_EXPORT: '/api/config/export',
    
    // User & System Settings
    USER_PREFERENCES: '/api/user/preferences',
    SYSTEM_SETTINGS: '/api/system/settings',
  }
};

// Environment-specific overrides
const ENVIRONMENT_CONFIG = {
  development: {
    API_BASE_URL: '', // Use Vite proxy
    API_PORT: 8000, // Neo4j FastAPI backend port
    API_TIMEOUT: 10000,
    DEBUG: true,
  },
  
  testing: {
    API_BASE_URL: import.meta.env.VITE_API_BASE_URL || '',
    API_PORT: 8000,
    API_TIMEOUT: 5000,
    DEBUG: true,
  },
  
  production: {
    API_BASE_URL: import.meta.env.VITE_API_BASE_URL || '',
    API_PORT: 8000,
    API_TIMEOUT: 30000,
    DEBUG: false,
  }
};

// Get current environment
const getCurrentEnvironment = () => {
  if (import.meta.env.MODE === 'test') return 'testing';
  if (isProduction) return 'production';
  return 'development';
};

// Merge configuration
const currentEnv = getCurrentEnvironment();
const envConfig = ENVIRONMENT_CONFIG[currentEnv] || {};

export const API_CONFIG = {
  ...DEFAULT_CONFIG,
  ...envConfig,
  ENVIRONMENT: currentEnv,
  IS_DEVELOPMENT: isDevelopment,
  IS_PRODUCTION: isProduction,
};

// Helper functions for endpoint building
export const buildEndpoint = (endpoint, params = {}) => {
  if (typeof endpoint === 'function') {
    return endpoint(params);
  }
  return endpoint;
};

export const getFullUrl = (endpoint, params = {}) => {
  const path = buildEndpoint(endpoint, params);
  return `${API_CONFIG.API_BASE_URL}${path}`;
};

// Connection health check
export const checkApiHealth = async () => {
  try {
    const healthEndpoint = `${API_CONFIG.API_BASE_URL}${API_CONFIG.ENDPOINTS.HEALTH}`;
    const response = await fetch(healthEndpoint, {
      method: 'GET',
      timeout: 5000,
    });
    return response.ok;
  } catch (error) {
    console.warn('API health check failed:', error);
    return false;
  }
};

// Configuration validation
export const validateConfig = () => {
  const requiredFields = ['API_BASE_URL', 'ENDPOINTS'];
  const missingFields = requiredFields.filter(field => !API_CONFIG[field]);
  
  if (missingFields.length > 0) {
    throw new Error(`Missing required configuration fields: ${missingFields.join(', ')}`);
  }
  
  return true;
};

// Debug logging (only in development)
if (API_CONFIG.DEBUG) {
  console.log('API Configuration Loaded:', {
    environment: API_CONFIG.ENVIRONMENT,
    baseUrl: API_CONFIG.API_BASE_URL,
    timeout: API_CONFIG.API_TIMEOUT,
    retryAttempts: API_CONFIG.API_RETRY_ATTEMPTS,
  });
}

// Workflow Management
export const WORKFLOW_STAGES = {
  DATA_CONFIGURATION: 'data-configuration',
  DATA_PIPELINES: 'data-pipelines', 
  DATA_FLOW: 'data-flow',
  REPORTING: 'reporting'
};

export const WORKFLOW_ENDPOINTS = {
  [WORKFLOW_STAGES.DATA_CONFIGURATION]: [
    API_CONFIG.ENDPOINTS.DATA_SOURCES,
    API_CONFIG.ENDPOINTS.SCHEMA_DISCOVERY,
    API_CONFIG.ENDPOINTS.DATA_QUALITY,
    API_CONFIG.ENDPOINTS.DATA_CONVERT,
    API_CONFIG.ENDPOINTS.DATA_VALIDATE
  ],
  [WORKFLOW_STAGES.DATA_PIPELINES]: [
    API_CONFIG.ENDPOINTS.PIPELINES,
    API_CONFIG.ENDPOINTS.MAPPINGS,
    API_CONFIG.ENDPOINTS.MIGRATION_PLANS
  ],
  [WORKFLOW_STAGES.DATA_FLOW]: [
    API_CONFIG.ENDPOINTS.GRAPH,
    API_CONFIG.ENDPOINTS.FLOW_METRICS,
    API_CONFIG.ENDPOINTS.FLOW_HEALTH,
    API_CONFIG.ENDPOINTS.PERFORMANCE_METRICS
  ],
  [WORKFLOW_STAGES.REPORTING]: [
    API_CONFIG.ENDPOINTS.REPORTS,
    API_CONFIG.ENDPOINTS.DASHBOARDS,
    API_CONFIG.ENDPOINTS.BULK_EXPORT,
    API_CONFIG.ENDPOINTS.ANALYTICS
  ]
};

// Advanced API Helper Functions
export const createApiRequest = (endpoint, options = {}) => {
  const {
    method = 'GET',
    params = {},
    data = null,
    headers = {},
    timeout = API_CONFIG.API_TIMEOUT
  } = options;

  const url = getFullUrl(endpoint, params);
  
  const requestConfig = {
    method,
    headers: {
      'Content-Type': 'application/json',
      ...headers
    },
    timeout
  };

  if (data && (method === 'POST' || method === 'PUT' || method === 'PATCH')) {
    requestConfig.body = JSON.stringify(data);
  }

  return { url, config: requestConfig };
};

export const executeWithRetry = async (apiCall, retries = API_CONFIG.API_RETRY_ATTEMPTS) => {
  for (let attempt = 1; attempt <= retries; attempt++) {
    try {
      const response = await apiCall();
      if (response.ok) {
        return response;
      }
      
      if (attempt === retries) {
        throw new Error(`API call failed after ${retries} attempts: ${response.status} ${response.statusText}`);
      }
    } catch (error) {
      if (attempt === retries) {
        throw error;
      }
      
      // Wait before retrying
      await new Promise(resolve => setTimeout(resolve, API_CONFIG.API_RETRY_DELAY * attempt));
    }
  }
};

// Workflow Progress Tracking
export const getWorkflowProgress = (completedStages = []) => {
  const stages = Object.values(WORKFLOW_STAGES);
  const progress = (completedStages.length / stages.length) * 100;
  
  return {
    currentStage: completedStages[completedStages.length - 1] || stages[0],
    nextStage: stages[stages.indexOf(completedStages[completedStages.length - 1]) + 1],
    progress: Math.round(progress),
    completedStages,
    remainingStages: stages.filter(stage => !completedStages.includes(stage))
  };
};

// Batch API Operations
export const executeBatchOperations = async (operations) => {
  const results = [];
  const errors = [];

  for (const operation of operations) {
    try {
      const { url, config } = createApiRequest(operation.endpoint, operation.options);
      const response = await executeWithRetry(() => fetch(url, config));
      const data = await response.json();
      
      results.push({
        operation: operation.name || operation.endpoint,
        success: true,
        data
      });
    } catch (error) {
      errors.push({
        operation: operation.name || operation.endpoint,
        success: false,
        error: error.message
      });
    }
  }

  return { results, errors, success: errors.length === 0 };
};

// Environment-specific API behavior
export const getEnvironmentFeatures = () => {
  const features = {
    development: {
      enableMockData: false,
      enableDebugLogs: true,
      skipAuthentication: true,
      enableHotReload: true
    },
    testing: {
      enableMockData: false,
      enableDebugLogs: true,
      skipAuthentication: true,
      enableHotReload: false
    },
    production: {
      enableMockData: false,
      enableDebugLogs: false,
      skipAuthentication: false,
      enableHotReload: false
    }
  };

  return features[API_CONFIG.ENVIRONMENT] || features.development;
};

export default API_CONFIG;
