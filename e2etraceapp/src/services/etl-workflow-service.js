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
    };
    
    this.initializeDefaultWorkflows();
  }

  initializeDefaultWorkflows() {
    // Data Import Workflow
    this.createWorkflowTemplate('data_import', {
      name: 'Data Import Workflow',
      description: 'Import data from various sources into the system',
      steps: [
        { type: 'extract', stage: 'extraction' },
        { type: 'validate', stage: 'validation', validator: 'schema' },
        { type: 'transform', stage: 'transformation', transformer: 'cleanse' },
        { type: 'load', stage: 'loading', loader: 'neo4j' }
      ],
      defaultConfig: {
        extraction: { source: 'auto' }, // Will be determined based on input
        validation: { strict: true },
        transformation: { skipErrors: false },
        loading: { batchSize: 1000 }
      }
    });

    // Data Migration Workflow
    this.createWorkflowTemplate('data_migration', {
      name: 'Data Migration Workflow',
      description: 'Migrate data between systems with mapping',
      steps: [
        { type: 'extract', stage: 'extraction' },
        { type: 'validate', stage: 'source_validation', validator: 'quality' },
        { type: 'transform', stage: 'mapping', transformer: 'mapping' },
        { type: 'validate', stage: 'target_validation', validator: 'business' },
        { type: 'load', stage: 'loading' }
      ],
      defaultConfig: {
        mapping: { required: true },
        validation: { businessRules: true }
      }
    });

    // Data Quality Workflow
    this.createWorkflowTemplate('data_quality', {
      name: 'Data Quality Assessment',
      description: 'Assess and improve data quality',
      steps: [
        { type: 'extract', stage: 'extraction' },
        { type: 'validate', stage: 'quality_check', validator: 'quality' },
        { type: 'transform', stage: 'cleansing', transformer: 'cleanse' },
        { type: 'validate', stage: 'final_validation', validator: 'integrity' },
        { type: 'load', stage: 'loading' }
      ],
      defaultConfig: {
        quality: { threshold: 0.95 },
        cleansing: { aggressive: false }
      }
    });

    // Spreadsheet Processing Workflow
    this.createWorkflowTemplate('spreadsheet_processing', {
      name: 'Spreadsheet Data Processing',
      description: 'Process spreadsheet data with validation and conversion',
      steps: [
        { type: 'extract', stage: 'file_import', config: { source: 'file' } },
        { type: 'validate', stage: 'format_validation', validator: 'schema' },
        { type: 'transform', stage: 'data_conversion', transformer: 'normalize' },
        { type: 'validate', stage: 'data_validation', validator: 'business' },
        { type: 'load', stage: 'data_export' }
      ],
      defaultConfig: {
        file_import: { source: 'file' },
        conversion: { autoDetectTypes: true },
        export: { format: 'multiple' }
      }
    });
  }

  // ============= WORKFLOW MANAGEMENT =============

  createWorkflowTemplate(id, template) {
    this.templates.set(id, {
      ...template,
      id,
      created: new Date().toISOString(),
      version: '1.0'
    });
  }

  getWorkflowTemplate(id) {
    return this.templates.get(id);
  }

  listWorkflowTemplates() {
    return Array.from(this.templates.values());
  }

  async createWorkflow(templateId, config = {}) {
    const template = this.getWorkflowTemplate(templateId);
    if (!template) {
      throw new Error(`Workflow template not found: ${templateId}`);
    }

    const workflow = {
      id: `workflow_${Date.now()}`,
      templateId,
      name: config.name || template.name,
      description: config.description || template.description,
      status: 'created',
      config: { ...template.defaultConfig, ...config },
      steps: template.steps.map(step => ({
        ...step,
        id: `step_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
        status: 'pending'
      })),
      created: new Date().toISOString(),
      metrics: {
        recordsProcessed: 0,
        errors: [],
        warnings: [],
        duration: 0,
        stages: {}
      }
    };

    this.workflows.set(workflow.id, workflow);
    return workflow;
  }

  async executeWorkflow(workflowId, inputData, options = {}) {
    const workflow = this.workflows.get(workflowId);
    if (!workflow) {
      throw new Error(`Workflow not found: ${workflowId}`);
    }

    workflow.status = 'running';
    workflow.startTime = Date.now();
    
    try {
      let currentData = inputData;
      const stageResults = [];

      // Execute each workflow step
      for (const step of workflow.steps) {
        step.status = 'running';
        const stepStartTime = Date.now();

        try {
          const stepResult = await this.executeWorkflowStep(step, currentData, workflow.config, options);
          
          step.status = 'completed';
          step.duration = Date.now() - stepStartTime;
          step.recordsProcessed = stepResult.recordsProcessed || 0;
          
          // Update workflow metrics
          workflow.metrics.recordsProcessed += stepResult.recordsProcessed || 0;
          workflow.metrics.stages[step.stage] = {
            duration: step.duration,
            recordsProcessed: step.recordsProcessed,
            status: 'success'
          };

          if (stepResult.errors?.length > 0) {
            workflow.metrics.errors.push(...stepResult.errors);
          }
          if (stepResult.warnings?.length > 0) {
            workflow.metrics.warnings.push(...stepResult.warnings);
          }

          // Update data for next step
          if (stepResult.data !== undefined) {
            currentData = stepResult.data;
          }

          stageResults.push(stepResult);

        } catch (stepError) {
          step.status = 'failed';
          step.error = stepError.message;
          workflow.metrics.stages[step.stage] = {
            duration: Date.now() - stepStartTime,
            status: 'failed',
            error: stepError.message
          };
          throw stepError;
        }
      }

      workflow.status = 'completed';
      workflow.endTime = Date.now();
      workflow.metrics.duration = workflow.endTime - workflow.startTime;
      workflow.metrics.throughput = workflow.metrics.recordsProcessed / (workflow.metrics.duration / 1000);

      // Update global metrics
      this.metrics.totalWorkflows++;
      this.metrics.successfulRuns++;
      this.updateAverageMetrics();

      return {
        workflowId,
        status: 'success',
        data: currentData,
        stages: stageResults,
        metrics: workflow.metrics
      };

    } catch (error) {
      workflow.status = 'failed';
      workflow.endTime = Date.now();
      workflow.metrics.duration = workflow.endTime - workflow.startTime;
      workflow.error = error.message;

      // Update global metrics
      this.metrics.totalWorkflows++;
      this.metrics.failedRuns++;
      this.updateAverageMetrics();

      throw new Error(`Workflow execution failed: ${error.message}`);
    }
  }

  async executeWorkflowStep(step, data, workflowConfig, options) {
    const stepConfig = { ...workflowConfig[step.stage], ...step.config };

    switch (step.type) {
      case 'extract':
        return await this.executeExtractionStep(step, stepConfig, options);
      
      case 'transform':
        return await this.executeTransformationStep(step, data, stepConfig, options);
      
      case 'load':
        return await this.executeLoadingStep(step, data, stepConfig, options);
      
      case 'validate':
        return await this.executeValidationStep(step, data, stepConfig, options);
      
      default:
        throw new Error(`Unknown workflow step type: ${step.type}`);
    }
  }

  // ============= STAGE-SPECIFIC IMPLEMENTATIONS =============

  async executeExtractionStep(step, config, options) {
    // Determine extractor type - prioritize file if file is provided
    let extractorType;
    if (options.file) {
      extractorType = 'file';
    } else if (config.source === 'auto') {
      // Auto-detect based on available options
      if (options.file) {
        extractorType = 'file';
      } else if (config.query || options.query) {
        extractorType = 'neo4j';
      } else {
        extractorType = 'neo4j'; // Default
      }
    } else if (config.source) {
      extractorType = config.source;
    } else if (options.source) {
      extractorType = options.source;
    } else {
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
      
      case 'nifi':
        return await etlEngine.extract('nifi', {
          processGroupId: config.processGroupId || options.processGroupId
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
      
      case 'nifi':
        return await etlEngine.load('nifi', data, {
          processGroupId: config.processGroupId,
          endpoint: config.endpoint
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
      case 'xls': return 'csv'; // Excel files will be processed as CSV using XLSX
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
