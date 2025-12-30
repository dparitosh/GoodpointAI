/**
 * ETL Workflow Service
 * Coordinates Extract, Transform, Load operations across the application
 */

import { etlEngine } from './etl-engine.js';
import { e2etraceFetchWithRetry } from '../api/e2etrace-api';
import { API_CONFIG } from '../config/api-config.js';

class ETLWorkflowService {
  constructor() {
    this.workflows = new Map();
    this.templates = new Map();
    this.metrics = {
      totalWorkflows: 0,
      successfulRuns: 0,
      failedRuns: 0,
      avgDuration: 0,
      throughput: 0
    /**
     * ETL Workflow Service
     * Thin wrapper around the backend Workflow Instance Manager APIs.
     * No local demo templates, no fabricated metrics.
     */

    import { e2etraceFetchWithRetry } from '../api/e2etrace-api';
    import { API_CONFIG } from '../config/api-config.js';

    class ETLWorkflowService {
      async listWorkflows() {
        const response = await e2etraceFetchWithRetry(API_CONFIG.ENDPOINTS.WORKFLOWS, { method: 'GET' });
        const data = await response.json();
        return Array.isArray(data) ? data : [];
      }

      async listWorkflowTemplates() {
        const response = await e2etraceFetchWithRetry(API_CONFIG.ENDPOINTS.WORKFLOW_TEMPLATES, { method: 'GET' });
        const data = await response.json();
        return Array.isArray(data) ? data : [];
      }

      async instantiateWorkflowFromTemplate(templateId, { sourceId, targetId, name } = {}) {
        if (!templateId) throw new Error('templateId is required');
        if (!sourceId) throw new Error('sourceId is required');
        if (!targetId) throw new Error('targetId is required');

        const url = `${API_CONFIG.ENDPOINTS.WORKFLOW_INSTANTIATE(templateId)}?source_id=${encodeURIComponent(
          sourceId
        )}&target_id=${encodeURIComponent(targetId)}${name ? `&name=${encodeURIComponent(name)}` : ''}`;

        const response = await e2etraceFetchWithRetry(url, { method: 'POST' });
        return await response.json();
      }

      async executeWorkflow(workflowId, { action = 'start', executionParams = {} } = {}) {
        if (!workflowId) throw new Error('workflowId is required');
        const response = await e2etraceFetchWithRetry(API_CONFIG.ENDPOINTS.WORKFLOW_EXECUTE(workflowId), {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ action, execution_params: executionParams }),
        });
        return await response.json();
      }

      async deleteWorkflow(workflowId) {
        if (!workflowId) throw new Error('workflowId is required');
        await e2etraceFetchWithRetry(API_CONFIG.ENDPOINTS.WORKFLOW_DELETE(workflowId), { method: 'DELETE' });
      }
    } else if (options.source) {

    export const etlWorkflowService = new ETLWorkflowService();
      extractorType = 'neo4j'; // Default fallback
    }
    
    switch (extractorType) {
      case 'neo4j':
        return await etlEngine.extract('neo4j', {
          query: config.query || 'MATCH (n) RETURN n LIMIT 100',
          params: config.params || {}
        });
      
      case 'file':
        const fileType = this.detectFileType(options.file?.name || config.filename);
        return await etlEngine.extract(fileType, {
          file: options.file,
          url: config.url,
          delimiter: config.delimiter
        });
      
      default:
        throw new Error(`Unsupported extraction source: ${extractorType}`);
    }
  }

  async executeTransformationStep(step, data, config, options) {
    const transformationType = step.transformer || 'mapping';
    
    switch (transformationType) {
      case 'mapping':
        return await etlEngine.transform('mapping', data, {
          mappings: config.mappings || options.mappings || []
        });
      
      case 'cleanse':
        return await etlEngine.transform('cleanse', data, {
          rules: config.cleansingRules || [],
          aggressive: config.aggressive || false
        });
      
      case 'normalize':
        return await etlEngine.transform('normalize', data, {
          schema: config.schema || {},
          autoDetectTypes: config.autoDetectTypes || true
        });
      
      default:
        return await etlEngine.transform(transformationType, data, config);
    }
  }

  async executeLoadingStep(step, data, config, options) {
    const loaderType = step.loader || config.target || 'neo4j';
    
    switch (loaderType) {
      case 'neo4j':
        return await etlEngine.load('neo4j', data, {
          nodeLabel: config.nodeLabel || 'ImportedData',
          properties: config.properties || {}
        });
      
      case 'file':
        const exportFormat = config.format || options.exportFormat || 'csv';
        return await etlEngine.load(exportFormat, data, {
          filename: config.filename || `export_${Date.now()}.${exportFormat}`
        });
      
      default:
        throw new Error(`Unsupported loading target: ${loaderType}`);
    }
  }

  async executeValidationStep(step, data, config, options) {
    const validationType = step.validator || 'schema';
    
    switch (validationType) {
      case 'schema':
        return await etlEngine.validate('schema', data, {
          schema: config.schema || this.inferSchema(data)
        });
      
      case 'quality':
        return await etlEngine.validate('quality', data, {
          threshold: config.threshold || 0.9,
          rules: config.qualityRules || []
        });
      
      case 'business':
        return await etlEngine.validate('business', data, {
          rules: config.businessRules || []
        });
      
      default:
        return await etlEngine.validate(validationType, data, config);
    }
  }

  // ============= SPECIALIZED WORKFLOWS =============

  async processSpreadsheetData(file, options = {}) {
    const workflow = await this.createWorkflow('spreadsheet_processing', {
      name: `Spreadsheet Processing: ${file.name}`,
      source: 'file',
      exportFormat: options.exportFormat || 'excel'
    });

    return await this.executeWorkflow(workflow.id, null, {
      file,
      exportFormat: options.exportFormat,
      mappings: options.mappings,
      validationRules: options.validationRules
    });
  }

  async migrateData(sourceConfig, targetConfig, mappings) {
    const workflow = await this.createWorkflow('data_migration', {
      name: 'Data Migration',
      source: sourceConfig.type,
      target: targetConfig.type,
      mappings
    });

    return await this.executeWorkflow(workflow.id, null, {
      source: sourceConfig,
      target: targetConfig,
      mappings
    });
  }

  async validateDataQuality(data, qualityRules = []) {
    const workflow = await this.createWorkflow('data_quality', {
      name: 'Data Quality Assessment',
      qualityRules
    });

    return await this.executeWorkflow(workflow.id, data, { qualityRules });
  }

  // ============= MONITORING & METRICS =============

  getWorkflowStatus(workflowId) {
    const workflow = this.workflows.get(workflowId);
    if (!workflow) return null;

    return {
      id: workflow.id,
      name: workflow.name,
      status: workflow.status,
      progress: this.calculateProgress(workflow),
      metrics: workflow.metrics,
      currentStep: workflow.steps.find(step => step.status === 'running')?.stage,
      error: workflow.error
    };
  }

  calculateProgress(workflow) {
    const totalSteps = workflow.steps.length;
    const completedSteps = workflow.steps.filter(step => step.status === 'completed').length;
    return (completedSteps / totalSteps) * 100;
  }

  getWorkflowMetrics() {
    return {
      ...this.metrics,
      activeWorkflows: Array.from(this.workflows.values()).filter(w => w.status === 'running').length,
      totalWorkflows: this.workflows.size
    };
  }

  updateAverageMetrics() {
    const completedWorkflows = Array.from(this.workflows.values()).filter(w => 
      w.status === 'completed' || w.status === 'failed'
    );
    
    if (completedWorkflows.length > 0) {
      const totalDuration = completedWorkflows.reduce((sum, w) => sum + (w.metrics.duration || 0), 0);
      const totalThroughput = completedWorkflows.reduce((sum, w) => sum + (w.metrics.throughput || 0), 0);
      
      this.metrics.avgDuration = totalDuration / completedWorkflows.length;
      this.metrics.throughput = totalThroughput / completedWorkflows.length;
    }
  }

  // ============= UTILITY METHODS =============

  detectFileType(filename) {
    if (!filename) return 'json';
    
    const extension = filename.split('.').pop().toLowerCase();
    switch (extension) {
      case 'csv': return 'csv';
      case 'json': return 'json';
      case 'xml': return 'xml';
      case 'xlsx':
      case 'xls': return 'csv'; // Excel files will be processed as CSV using xlsx-based reader
      default: return 'json';
    }
  }

  inferSchema(data) {
    if (!Array.isArray(data) || data.length === 0) return {};
    
    const sample = data[0];
    const schema = {
      required: Object.keys(sample),
      types: {}
    };
    
    for (const [key, value] of Object.entries(sample)) {
      schema.types[key] = typeof value;
    }
    
    return schema;
  }

  // Cleanup old workflows
  cleanup(maxAge = 24 * 60 * 60 * 1000) { // 24 hours
    const cutoff = Date.now() - maxAge;
    
    for (const [id, workflow] of this.workflows.entries()) {
      const workflowTime = new Date(workflow.created).getTime();
      if (workflowTime < cutoff && workflow.status !== 'running') {
        this.workflows.delete(id);
      }
    }
  }
}

// Export singleton instance
export const etlWorkflowService = new ETLWorkflowService();
export default etlWorkflowService;
