/**
 * Neo4j Data Service for FastAPI Integration
 * Handles data analysis, migration, and mapping operations
 */

import { API_CONFIG, getFullUrl, buildEndpoint } from '../config/api-config.js';

class Neo4jDataService {
  constructor() {
    this.config = API_CONFIG;
  }

  // Generic API call wrapper with centralized configuration
  async apiCall(endpoint, options = {}) {
    const url = getFullUrl(endpoint);
    const defaultOptions = {
      headers: {
        'Content-Type': 'application/json',
      },
      timeout: this.config.API_TIMEOUT,
    };

    try {
      const response = await fetch(url, { ...defaultOptions, ...options });
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      return await response.json();
    } catch (error) {
      console.error(`API call failed for ${endpoint}:`, error);
      throw error;
    }
  }

  // Data Analysis Operations
  async getDataAnalytics(filters = {}) {
    const query = new URLSearchParams(filters).toString();
    return this.apiCall(`${this.config.ENDPOINTS.ANALYTICS}${query ? `?${query}` : ''}`);
  }

  async getNodeStatistics(nodeType = null) {
    const endpoint = nodeType ? `${this.config.ENDPOINTS.ANALYTICS_NODES}/${nodeType}` : this.config.ENDPOINTS.ANALYTICS_NODES;
    return this.apiCall(endpoint);
  }

  async getRelationshipAnalytics() {
    return this.apiCall(this.config.ENDPOINTS.ANALYTICS_RELATIONSHIPS);
  }

  async getDataQualityMetrics() {
    return this.apiCall(this.config.ENDPOINTS.DATA_QUALITY);
  }

  // Migration Operations
  async getMigrationPlans() {
    return this.apiCall(this.config.ENDPOINTS.MIGRATION_PLANS);
  }

  async createMigrationPlan(planData) {
    return this.apiCall(this.config.ENDPOINTS.MIGRATION_PLANS, {
      method: 'POST',
      body: JSON.stringify(planData),
    });
  }

  async executeMigrationPlan(planId) {
    return this.apiCall(buildEndpoint(this.config.ENDPOINTS.MIGRATION_EXECUTE, planId), {
      method: 'POST',
    });
  }

  async getMigrationStatus(planId) {
    return this.apiCall(buildEndpoint(this.config.ENDPOINTS.MIGRATION_STATUS, planId));
  }

  // NiFi Integration
  async getNiFiProcessGroups() {
    return this.apiCall(this.config.ENDPOINTS.NIFI_PROCESS_GROUPS);
  }

  async getNiFiProcessors() {
    return this.apiCall(this.config.ENDPOINTS.NIFI_PROCESSORS);
  }

  async createNiFiMapping(mappingData) {
    return this.apiCall(this.config.ENDPOINTS.NIFI_MAPPINGS, {
      method: 'POST',
      body: JSON.stringify(mappingData),
    });
  }

  async syncWithNiFi(syncConfig) {
    return this.apiCall(this.config.ENDPOINTS.NIFI_SYNC, {
      method: 'POST',
      body: JSON.stringify(syncConfig),
    });
  }

  // Data Mapping Operations
  async getDataMappings(sourceSystem = null, targetSystem = null) {
    const params = new URLSearchParams();
    if (sourceSystem) params.append('source', sourceSystem);
    if (targetSystem) params.append('target', targetSystem);
    
    return this.apiCall(`${this.config.ENDPOINTS.MAPPINGS}${params.toString() ? `?${params.toString()}` : ''}`);
  }

  async createDataMapping(mappingData) {
    return this.apiCall(this.config.ENDPOINTS.MAPPINGS, {
      method: 'POST',
      body: JSON.stringify(mappingData),
    });
  }

  async validateMapping(mappingId) {
    return this.apiCall(buildEndpoint(this.config.ENDPOINTS.MAPPING_VALIDATE, mappingId), {
      method: 'POST',
    });
  }

  // Data Scrubbing and Cleansing
  async getDataQualityRules() {
    return this.apiCall(this.config.ENDPOINTS.DATA_QUALITY_RULES);
  }

  async applyDataScrubbing(scrubConfig) {
    return this.apiCall(this.config.ENDPOINTS.DATA_QUALITY_SCRUB, {
      method: 'POST',
      body: JSON.stringify(scrubConfig),
    });
  }

  async getDuplicateAnalysis() {
    return this.apiCall(this.config.ENDPOINTS.DATA_QUALITY_DUPLICATES);
  }

  // Target Application Integration
  async getTargetApplications() {
    return this.apiCall(this.config.ENDPOINTS.TARGET_APPS);
  }

  async syncToTargetApp(appId, syncData) {
    return this.apiCall(buildEndpoint(this.config.ENDPOINTS.TARGET_APP_SYNC, appId), {
      method: 'POST',
      body: JSON.stringify(syncData),
    });
  }

  // Custom Cypher Queries for Spreadsheet Integration
  async executeCypherQuery(query, parameters = {}) {
    return this.apiCall(this.config.ENDPOINTS.GRAPH_QUERY, {
      method: 'POST',
      body: JSON.stringify({
        query,
        parameters,
      }),
    });
  }

  // Bulk Data Operations for Spreadsheet
  async bulkImportData(data, config = {}) {
    return this.apiCall(this.config.ENDPOINTS.BULK_IMPORT, {
      method: 'POST',
      body: JSON.stringify({
        data,
        config,
      }),
    });
  }

  async bulkExportData(exportConfig) {
    return this.apiCall(this.config.ENDPOINTS.BULK_EXPORT, {
      method: 'POST',
      body: JSON.stringify(exportConfig),
    });
  }

  // Schema and Metadata Operations
  async getDatabaseSchema() {
    return this.apiCall(this.config.ENDPOINTS.GRAPH_SCHEMA);
  }

  async getNodeLabels() {
    return this.apiCall(this.config.ENDPOINTS.SCHEMA_LABELS);
  }

  async getRelationshipTypes() {
    return this.apiCall(this.config.ENDPOINTS.SCHEMA_RELATIONSHIPS);
  }

  async getPropertyKeys() {
    return this.apiCall(this.config.ENDPOINTS.SCHEMA_PROPERTIES);
  }
}

export default new Neo4jDataService();
