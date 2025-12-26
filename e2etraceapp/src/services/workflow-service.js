import { API_CONFIG, WORKFLOW_STAGES, getWorkflowProgress, executeBatchOperations } from '@config/api-config.js';
import { e2etraceFetchWithRetry } from '../api/e2etrace-api.js';

/**
 * Workflow Management Service
 * Orchestrates the data flow: Configuration → Pipelines → Flow → Reporting
 */
class WorkflowService {
  constructor() {
    this.currentWorkflow = null;
    this.workflowHistory = [];
    this.eventListeners = new Map();
  }

  // Event Management
  addEventListener(event, callback) {
    if (!this.eventListeners.has(event)) {
      this.eventListeners.set(event, []);
    }
    this.eventListeners.get(event).push(callback);
  }

  removeEventListener(event, callback) {
    if (this.eventListeners.has(event)) {
      const callbacks = this.eventListeners.get(event);
      const index = callbacks.indexOf(callback);
      if (index > -1) {
        callbacks.splice(index, 1);
      }
    }
  }

  emit(event, data) {
    if (this.eventListeners.has(event)) {
      this.eventListeners.get(event).forEach(callback => callback(data));
    }
  }

  // Workflow Initialization
  async initializeWorkflow(workflowConfig = {}) {
    const workflow = {
      id: `workflow_${Date.now()}`,
      name: workflowConfig.name || 'Data Analytics Workflow',
      description: workflowConfig.description || 'End-to-end data analytics and reporting workflow',
      stages: Object.values(WORKFLOW_STAGES),
      currentStage: WORKFLOW_STAGES.DATA_CONFIGURATION,
      completedStages: [],
      createdAt: new Date().toISOString(),
      configuration: {
        autoAdvance: workflowConfig.autoAdvance || false,
        validateStages: workflowConfig.validateStages !== false,
        enableRollback: workflowConfig.enableRollback !== false,
        ...workflowConfig.configuration
      }
    };

    this.currentWorkflow = workflow;
    this.emit('workflow:initialized', workflow);
    
    return workflow;
  }

  // Stage 1: Data Configuration
  async executeDataConfiguration(config = {}) {
    this.emit('stage:started', { stage: WORKFLOW_STAGES.DATA_CONFIGURATION });

    try {
      const operations = [
        {
          name: 'Check Data Sources',
          endpoint: API_CONFIG.ENDPOINTS.DATA_SOURCES,
          options: { method: 'GET' }
        },
        {
          name: 'Discover Schema',
          endpoint: API_CONFIG.ENDPOINTS.SCHEMA_DISCOVERY,
          options: { method: 'POST', data: config.schemaConfig }
        },
        {
          name: 'Validate Data Quality',
          endpoint: API_CONFIG.ENDPOINTS.DATA_QUALITY,
          options: { method: 'GET' }
        }
      ];

      const results = await executeBatchOperations(operations);
      
      if (results.success) {
        await this.completeStage(WORKFLOW_STAGES.DATA_CONFIGURATION, {
          dataSources: results.results.find(r => r.operation.includes('Data Sources'))?.data,
          schema: results.results.find(r => r.operation.includes('Schema'))?.data,
          qualityReport: results.results.find(r => r.operation.includes('Quality'))?.data
        });
      } else {
        throw new Error(`Data configuration failed: ${results.errors.map(e => e.error).join(', ')}`);
      }

      return results;
    } catch (error) {
      this.emit('stage:error', { stage: WORKFLOW_STAGES.DATA_CONFIGURATION, error });
      throw error;
    }
  }

  // Stage 2: Data Pipelines
  async executeDataPipelines(config = {}) {
    if (!this.isStageCompleted(WORKFLOW_STAGES.DATA_CONFIGURATION)) {
      throw new Error('Data Configuration must be completed before executing Data Pipelines');
    }

    this.emit('stage:started', { stage: WORKFLOW_STAGES.DATA_PIPELINES });

    try {
      const operations = [
        {
          name: 'Create Data Mappings',
          endpoint: API_CONFIG.ENDPOINTS.MAPPINGS,
          options: { method: 'POST', data: config.mappingRules }
        },
        {
          name: 'Initialize Migration Plans',
          endpoint: API_CONFIG.ENDPOINTS.MIGRATION_PLANS,
          options: { method: 'GET' }
        }
      ];

      const results = await executeBatchOperations(operations);
      
      if (results.success) {
        await this.completeStage(WORKFLOW_STAGES.DATA_PIPELINES, {
          mappings: results.results.find(r => r.operation.includes('Mappings'))?.data,
          migrationPlans: results.results.find(r => r.operation.includes('Migration'))?.data
        });
      } else {
        throw new Error(`Data pipelines setup failed: ${results.errors.map(e => e.error).join(', ')}`);
      }

      return results;
    } catch (error) {
      this.emit('stage:error', { stage: WORKFLOW_STAGES.DATA_PIPELINES, error });
      throw error;
    }
  }

  // Stage 3: Data Flow
  async executeDataFlow(config = {}) {
    if (!this.isStageCompleted(WORKFLOW_STAGES.DATA_PIPELINES)) {
      throw new Error('Data Pipelines must be completed before executing Data Flow');
    }

    this.emit('stage:started', { stage: WORKFLOW_STAGES.DATA_FLOW });

    try {
      const operations = [
        {
          name: 'Load Graph Data',
          endpoint: API_CONFIG.ENDPOINTS.GRAPH,
          options: { method: 'GET' }
        },
        {
          name: 'Initialize Flow Monitoring',
          endpoint: API_CONFIG.ENDPOINTS.FLOW_HEALTH,
          options: { method: 'GET' }
        },
        {
          name: 'Load Performance Metrics',
          endpoint: API_CONFIG.ENDPOINTS.PERFORMANCE_METRICS,
          options: { method: 'GET' }
        }
      ];

      const results = await executeBatchOperations(operations);
      
      if (results.success) {
        await this.completeStage(WORKFLOW_STAGES.DATA_FLOW, {
          graphData: results.results.find(r => r.operation.includes('Graph'))?.data,
          flowHealth: results.results.find(r => r.operation.includes('Monitoring'))?.data,
          metrics: results.results.find(r => r.operation.includes('Metrics'))?.data
        });
      } else {
        throw new Error(`Data flow initialization failed: ${results.errors.map(e => e.error).join(', ')}`);
      }

      return results;
    } catch (error) {
      this.emit('stage:error', { stage: WORKFLOW_STAGES.DATA_FLOW, error });
      throw error;
    }
  }

  // Stage 4: Reporting
  async executeReporting(config = {}) {
    if (!this.isStageCompleted(WORKFLOW_STAGES.DATA_FLOW)) {
      throw new Error('Data Flow must be completed before executing Reporting');
    }

    this.emit('stage:started', { stage: WORKFLOW_STAGES.REPORTING });

    try {
      const operations = [
        {
          name: 'Load Analytics',
          endpoint: API_CONFIG.ENDPOINTS.ANALYTICS,
          options: { method: 'GET' }
        },
        {
          name: 'Initialize Dashboards',
          endpoint: API_CONFIG.ENDPOINTS.DASHBOARDS,
          options: { method: 'GET' }
        },
        {
          name: 'Prepare Export Capabilities',
          endpoint: API_CONFIG.ENDPOINTS.EXPORT_FORMATS,
          options: { method: 'GET' }
        }
      ];

      const results = await executeBatchOperations(operations);
      
      if (results.success) {
        await this.completeStage(WORKFLOW_STAGES.REPORTING, {
          analytics: results.results.find(r => r.operation.includes('Analytics'))?.data,
          dashboards: results.results.find(r => r.operation.includes('Dashboards'))?.data,
          exportFormats: results.results.find(r => r.operation.includes('Export'))?.data
        });
      } else {
        throw new Error(`Reporting setup failed: ${results.errors.map(e => e.error).join(', ')}`);
      }

      return results;
    } catch (error) {
      this.emit('stage:error', { stage: WORKFLOW_STAGES.REPORTING, error });
      throw error;
    }
  }

  // Workflow Management Methods
  async completeStage(stage, data = {}) {
    if (!this.currentWorkflow) {
      throw new Error('No active workflow');
    }

    this.currentWorkflow.completedStages.push(stage);
    this.currentWorkflow.stageData = {
      ...this.currentWorkflow.stageData,
      [stage]: {
        completedAt: new Date().toISOString(),
        data
      }
    };

    const progress = getWorkflowProgress(this.currentWorkflow.completedStages);
    this.currentWorkflow.currentStage = progress.nextStage;
    this.currentWorkflow.progress = progress.progress;

    this.emit('stage:completed', { stage, data, progress });

    // Auto-advance if enabled
    if (this.currentWorkflow.configuration.autoAdvance && progress.nextStage) {
      setTimeout(() => this.advanceToNextStage(), 1000);
    }

    return this.currentWorkflow;
  }

  async advanceToNextStage() {
    const progress = getWorkflowProgress(this.currentWorkflow.completedStages);
    
    if (progress.nextStage) {
      this.emit('workflow:advancing', { 
        from: progress.currentStage, 
        to: progress.nextStage 
      });
    } else {
      this.emit('workflow:completed', { workflow: this.currentWorkflow });
    }
  }

  isStageCompleted(stage) {
    return this.currentWorkflow?.completedStages.includes(stage) || false;
  }

  getWorkflowStatus() {
    if (!this.currentWorkflow) {
      return { status: 'not_started' };
    }

    const progress = getWorkflowProgress(this.currentWorkflow.completedStages);
    
    return {
      status: progress.progress === 100 ? 'completed' : 'in_progress',
      workflow: this.currentWorkflow,
      progress
    };
  }

  // Data Integration Methods
  async validateStagePrerequisites(stage) {
    const prerequisites = {
      [WORKFLOW_STAGES.DATA_CONFIGURATION]: [],
      [WORKFLOW_STAGES.DATA_PIPELINES]: [WORKFLOW_STAGES.DATA_CONFIGURATION],
      [WORKFLOW_STAGES.DATA_FLOW]: [WORKFLOW_STAGES.DATA_CONFIGURATION, WORKFLOW_STAGES.DATA_PIPELINES],
      [WORKFLOW_STAGES.REPORTING]: [WORKFLOW_STAGES.DATA_CONFIGURATION, WORKFLOW_STAGES.DATA_PIPELINES, WORKFLOW_STAGES.DATA_FLOW]
    };

    const required = prerequisites[stage] || [];
    const missing = required.filter(prereq => !this.isStageCompleted(prereq));

    return {
      canProceed: missing.length === 0,
      missingPrerequisites: missing
    };
  }

  async rollbackToStage(targetStage) {
    if (!this.currentWorkflow.configuration.enableRollback) {
      throw new Error('Rollback is disabled for this workflow');
    }

    const stages = Object.values(WORKFLOW_STAGES);
    const targetIndex = stages.indexOf(targetStage);
    
    if (targetIndex === -1) {
      throw new Error(`Invalid stage: ${targetStage}`);
    }

    // Remove completed stages after target
    this.currentWorkflow.completedStages = this.currentWorkflow.completedStages
      .filter(stage => stages.indexOf(stage) <= targetIndex);
    
    this.currentWorkflow.currentStage = targetStage;
    
    this.emit('workflow:rollback', { targetStage, currentWorkflow: this.currentWorkflow });
    
    return this.currentWorkflow;
  }

  // Cleanup
  dispose() {
    this.eventListeners.clear();
    this.currentWorkflow = null;
    this.workflowHistory = [];
  }
}

// Singleton instance
const workflowService = new WorkflowService();

export default workflowService;
