import { createMachine, assign, interpret } from 'xstate';
import { ETLEngine } from './etl-engine.js';

/**
 * AGENTIC ETL ORCHESTRATOR - Modular Cognition Pattern Implementation
 * Applies Pareto principle to focus on 20% of ETL operations that provide 80% value
 * Integrates with existing ETL Engine using agentic orchestration patterns
 */




// AGENTIC STATES - FSM for ETL Orchestration
const etlOrchestrationMachine = createMachine({
  id: 'etlOrchestration',
  initial: 'idle',
  context: {
    agents: new Map(),
    activeJobs: [],
    metrics: {},
    errors: [],
    currentPipeline: null
  },
  states: {
    idle: {
      on: {
        START_PIPELINE: {
          target: 'analyzing',
          actions: 'initializePipeline'
        }
      }
    },
    analyzing: {
      entry: 'deployAnalysisAgent',
      on: {
        ANALYSIS_COMPLETE: {
          target: 'orchestrating',
          actions: 'storeAnalysis'
        },
        ANALYSIS_FAILED: {
          target: 'error',
          actions: 'captureError'
        }
      }
    },
    orchestrating: {
      entry: 'deployOrchestrationAgents',
      on: {
        EXTRACTION_COMPLETE: {
          target: 'transforming',
          actions: 'processExtractionResults'
        },
        ORCHESTRATION_FAILED: {
          target: 'error',
          actions: 'captureError'
        }
      }
    },
    transforming: {
      entry: 'deployTransformationAgents',
      on: {
        TRANSFORMATION_COMPLETE: {
          target: 'loading',
          actions: 'processTransformationResults'
        },
        TRANSFORMATION_FAILED: {
          target: 'error',
          actions: 'captureError'
        }
      }
    },
    loading: {
      entry: 'deployLoadingAgents',
      on: {
        LOADING_COMPLETE: {
          target: 'monitoring',
          actions: 'processLoadingResults'
        },
        LOADING_FAILED: {
          target: 'error',
          actions: 'captureError'
        }
      }
    },
    monitoring: {
      entry: 'deployMonitoringAgents',
      on: {
        MONITORING_COMPLETE: {
          target: 'completed',
          actions: 'finalizeResults'
        },
        QUALITY_ISSUE: {
          target: 'transforming',
          actions: 'handleQualityIssue'
        }
      }
    },
    completed: {
      entry: 'notifyCompletion',
      on: {
        RESET: {
          target: 'idle',
          actions: 'cleanup'
        }
      }
    },
    error: {
      entry: 'handleError',
      on: {
        RETRY: {
          target: 'analyzing',
          actions: 'resetPipeline'
        },
        RESET: {
          target: 'idle',
          actions: 'cleanup'
        }
      }
    }
  }
}, {
  actions: {
    initializePipeline: assign({
      currentPipeline: (context, event) => event.pipeline,
      activeJobs: [],
      errors: []
    }),
    deployAnalysisAgent: (context, event) => {
      console.log('Deploying Analysis Agent for pipeline:', context.currentPipeline?.name);
    },
    storeAnalysis: assign({
      metrics: (context, event) => ({ ...context.metrics, analysis: event.results })
    }),
    captureError: assign({
      errors: (context, event) => [...context.errors, event.error]
    }),
    cleanup: assign({
      currentPipeline: null,
      activeJobs: [],
      errors: []
    })
  }
});

// AGENTIC ETL AGENTS - Specialized AI Agents for ETL Operations
class AgenticETLAgent {
  constructor(type, _config = {}) {
    this.type = type;
    this.config = _config;
    this.status = 'idle';
    this.metrics = {};
    this.etlEngine = new ETLEngine();
  }

  async execute(task) {
    this.status = 'running';
    const startTime = Date.now();
    
    try {
      let result;
      switch (this.type) {
        case 'analyzer':
          result = await this.analyzeDataSources(task);
          break;
        case 'extractor':
          result = await this.extractData(task);
          break;
        case 'transformer':
          result = await this.transformData(task);
          break;
        case 'loader':
          result = await this.loadData(task);
          break;
        case 'monitor':
          result = await this.monitorQuality(task);
          break;
        default:
          throw new Error(`Unknown agent type: ${this.type}`);
      }
      
      this.status = 'completed';
      this.metrics = {
        executionTime: Date.now() - startTime,
        recordsProcessed: result.recordCount || 0,
        successRate: result.successRate || 100
      };
      
      return result;
    } catch (error) {
      this.status = 'error';
      this.metrics = {
        executionTime: Date.now() - startTime,
        error: error.message
      };
      throw error;
    }
  }

  // ANALYSIS AGENT - Applies Pareto analysis to identify critical data sources
  async analyzeDataSources(task) {
    const { dataSources } = task;
    
    // Apply Pareto principle: identify 20% of sources providing 80% of value
    const sourceAnalysis = await Promise.all(
      dataSources.map(async (source) => {
        const sampleData = await this.etlEngine.extract(source.type, { 
          ...source._config, 
          limit: 100 // Sample for analysis
        });
        
        return {
          sourceId: source.id,
          type: source.type,
          recordCount: sampleData.recordCount,
          quality: this.assessDataQuality(sampleData._data),
          businessValue: this.calculateBusinessValue(sampleData._data, source.metadata),
          complexity: this.assessComplexity(source._config)
        };
      })
    );
    
    // Pareto ranking: value/effort ratio
    const rankedSources = sourceAnalysis
      .map(analysis => ({
        ...analysis,
        paretoScore: (analysis.businessValue * analysis.quality) / analysis.complexity
      }))
      .sort((a, b) => b.paretoScore - a.paretoScore);
    
    return {
      analysis: sourceAnalysis,
      paretoRanking: rankedSources,
      criticalSources: rankedSources.slice(0, Math.ceil(rankedSources.length * 0.2)),
      recommendations: this.generateRecommendations(rankedSources)
    };
  }

  // EXTRACTION AGENT - Focus on high-value sources first
  async extractData(task) {
    const { sources, prioritization } = task;
    const results = [];
    
    // Process critical sources first (Pareto optimization)
    const orderedSources = prioritization === 'pareto' 
      ? this.orderByParetoValue(sources)
      : sources;
    
    for (const source of orderedSources) {
      try {
        const extracted = await this.etlEngine.extract(source.type, source._config);
        results.push({
          sourceId: source.id,
          success: true,
          _data: extracted.data,
          metadata: extracted.metadata,
          recordCount: extracted.recordCount
        });
      } catch (error) {
        results.push({
          sourceId: source.id,
          success: false,
          error: error.message
        });
      }
    }
    
    return {
      results,
      successRate: (results.filter(r => r.success).length / results.length) * 100,
      totalRecords: results.reduce((sum, r) => sum + (r.recordCount || 0), 0)
    };
  }

  // TRANSFORMATION AGENT - Smart transformation based on data analysis
  async transformData(task) {
    const { data, transformations } = task;
    
    // Apply intelligent transformation ordering
    const optimizedTransformations = this.optimizeTransformations(transformations, _data);
    
    let transformedData = data;
    const transformationResults = [];
    
    for (const transformation of optimizedTransformations) {
      try {
        const result = await this.etlEngine.transform(
          transformation.type,
          transformedData,
          transformation._config
        );
        
        transformedData = result.data;
        transformationResults.push({
          type: transformation.type,
          success: true,
          recordsAffected: result.recordsAffected || 0
        });
      } catch (error) {
        transformationResults.push({
          type: transformation.type,
          success: false,
          error: error.message
        });
      }
    }
    
    return {
      data: transformedData,
      transformations: transformationResults,
      qualityScore: this.calculateQualityScore(transformedData)
    };
  }

  // LOADING AGENT - Optimized loading strategies
  async loadData(task) {
    const { data, targets } = task;
    const results = [];
    
    // Parallel loading for independent targets
    const loadPromises = targets.map(async (target) => {
      try {
        const result = await this.etlEngine.load(target.type, _data, target.config);
        return {
          targetId: target.id,
          success: true,
          recordsLoaded: result.recordsLoaded || 0
        };
      } catch (error) {
        return {
          targetId: target.id,
          success: false,
          error: error.message
        };
      }
    });
    
    const loadResults = await Promise.all(loadPromises);
    
    return {
      results: loadResults,
      successRate: (loadResults.filter(r => r.success).length / loadResults.length) * 100,
      totalRecordsLoaded: loadResults.reduce((sum, r) => sum + (r.recordsLoaded || 0), 0)
    };
  }

  // MONITORING AGENT - Real-time quality monitoring
  async monitorQuality(task) {
    const { data, thresholds } = task;
    
    const qualityMetrics = {
      completeness: this.calculateCompleteness(_data),
      accuracy: this.calculateAccuracy(_data),
      consistency: this.calculateConsistency(_data),
      validity: this.calculateValidity(_data),
      uniqueness: this.calculateUniqueness(_data)
    };
    
    const qualityIssues = [];
    Object.entries(qualityMetrics).forEach(([metric, value]) => {
      const threshold = thresholds[metric] || 90;
      if (value < threshold) {
        qualityIssues.push({
          metric,
          value,
          threshold,
          severity: value < threshold * 0.8 ? 'high' : 'medium'
        });
      }
    });
    
    return {
      metrics: qualityMetrics,
      issues: qualityIssues,
      overallScore: Object.values(qualityMetrics).reduce((sum, val) => sum + val, 0) / Object.keys(qualityMetrics).length,
      passed: qualityIssues.length === 0
    };
  }

  // HELPER METHODS for Pareto Analysis
  assessDataQuality(_data) {
    if (!_data || data.length === 0) return 0;
    
    const completeness = data.filter(row => 
      Object.values(row).every(val => val !== null && val !== undefined && val !== '')
    ).length / data.length;
    
    return completeness * 100;
  }

  calculateBusinessValue(_data, metadata) {
    // Simple business value calculation based on metadata
    const baseValue = data.length; // Volume
    const typeValue = metadata?.type === 'critical' ? 2 : 1;
    const freshnessValue = metadata?.lastUpdated ? 
      Math.max(1, 2 - (Date.now() - new Date(metadata.lastUpdated).getTime()) / (1000 * 60 * 60 * 24)) : 1;
    
    return baseValue * typeValue * freshnessValue;
  }

  assessComplexity(_config) {
    // Complexity based on configuration parameters
    const paramCount = Object.keys(_config).length;
    const hasAdvanced = Object.values(_config).some(val => 
      typeof val === 'object' || typeof val === 'function'
    );
    
    return paramCount + (hasAdvanced ? 5 : 0);
  }

  generateRecommendations(rankedSources) {
    return rankedSources.map((source, index) => ({
      sourceId: source.sourceId,
      priority: _index < rankedSources.length * 0.2 ? 'high' : 
                index < rankedSources.length * 0.5 ? 'medium' : 'low',
      recommendation: index < rankedSources.length * 0.2 
        ? 'Process immediately - high value, low complexity'
        : 'Schedule for batch processing'
    }));
  }

  orderByParetoValue(sources) {
    return sources.sort((a, b) => (b.paretoScore || 0) - (a.paretoScore || 0));
  }

  optimizeTransformations(transformations, _data) {
    // Optimize transformation order based on data characteristics
    return transformations.sort((a, b) => {
      const priorityOrder = ['cleanse', 'normalize', 'validate', 'mapping'];
      return priorityOrder.indexOf(a.type) - priorityOrder.indexOf(b.type);
    });
  }

  calculateQualityScore(_data) {
    if (!_data || data.length === 0) return 0;
    
    const completeness = this.calculateCompleteness(_data);
    const consistency = this.calculateConsistency(_data);
    
    return (completeness + consistency) / 2;
  }

  calculateCompleteness(_data) {
    if (!_data || data.length === 0) return 100;
    
    const totalFields = data.length * Object.keys(_data[0] || {}).length;
    const completedFields = data.reduce((sum, row) => 
      sum + Object.values(row).filter(val => val !== null && val !== undefined && val !== '').length, 0
    );
    
    return totalFields > 0 ? (completedFields / totalFields) * 100 : 100;
  }

  calculateAccuracy(_data) {
    // Simple accuracy check - could be enhanced with _validation rules
    return 95; // Placeholder
  }

  calculateConsistency(_data) {
    if (!_data || data.length === 0) return 100;
    
    // Check type consistency for each field
    const fields = Object.keys(_data[0] || {});
    const consistencyScores = fields.map(field => {
      const types = new Set(_data.map(row => typeof row[field]));
      return types.size === 1 ? 100 : 60; // Penalty for mixed types
    });
    
    return consistencyScores.length > 0 
      ? consistencyScores.reduce((sum, score) => sum + score, 0) / consistencyScores.length
      : 100;
  }

  calculateValidity(_data) {
    // Placeholder for _validation logic
    return 90;
  }

  calculateUniqueness(_data) {
    if (!_data || data.length === 0) return 100;
    
    const uniqueRecords = new Set(_data.map(row => JSON.stringify(row))).size;
    return (uniqueRecords / _data.length) * 100;
  }
}

// AGENTIC ETL ORCHESTRATOR - Main orchestration class
export class AgenticETLOrchestrator {
  constructor() {
    this.machine = etlOrchestrationMachine;
    this.service = interpret(this.machine);
    this.agents = new Map();
    this.activeJobs = new Map();
    
    this.service.start();
  }

  // Start an agentic ETL pipeline
  async executePipeline(pipelineConfig) {
    const jobId = `job_${Date.now()}`;
    
    try {
      // Deploy specialized agents based on pipeline requirements
      const agents = this.deployAgents(pipelineConfig);
      this.activeJobs.set(jobId, { agents, _config: pipelineConfig, status: 'running' });
      
      // FSM-driven execution
      this.service.send({ type: 'START_PIPELINE', pipeline: pipelineConfig });
      
      // Sequential agent execution with FSM coordination
      const analysisResult = await agents.analyzer.execute({
        dataSources: pipelineConfig.sources
      });
      
      this.service.send({ type: 'ANALYSIS_COMPLETE', results: analysisResult });
      
      const extractionResult = await agents.extractor.execute({
        sources: analysisResult.criticalSources,
        prioritization: 'pareto'
      });
      
      this.service.send({ type: 'EXTRACTION_COMPLETE', results: extractionResult });
      
      const transformationResult = await agents.transformer.execute({
        _data: extractionResult.results.filter(r => r.success).map(r => r._data).flat(),
        transformations: pipelineConfig.transformations
      });
      
      this.service.send({ type: 'TRANSFORMATION_COMPLETE', results: transformationResult });
      
      const loadingResult = await agents.loader.execute({
        _data: transformationResult.data,
        targets: pipelineConfig.targets
      });
      
      this.service.send({ type: 'LOADING_COMPLETE', results: loadingResult });
      
      const monitoringResult = await agents.monitor.execute({
        _data: transformationResult.data,
        thresholds: pipelineConfig.qualityThresholds || {}
      });
      
      if (monitoringResult.passed) {
        this.service.send({ type: 'MONITORING_COMPLETE', results: monitoringResult });
      } else {
        this.service.send({ type: 'QUALITY_ISSUE', issues: monitoringResult.issues });
        // Could trigger retry or alternative processing
      }
      
      const finalResult = {
        jobId,
        status: 'completed',
        analysis: analysisResult,
        extraction: extractionResult,
        transformation: transformationResult,
        loading: loadingResult,
        monitoring: monitoringResult,
        metrics: this.calculateOverallMetrics([
          analysisResult, extractionResult, transformationResult, loadingResult, monitoringResult
        ])
      };
      
      this.activeJobs.set(jobId, { ...this.activeJobs.get(jobId), status: 'completed', result: finalResult });
      
      return finalResult;
      
    } catch (error) {
      this.service.send({ type: 'ORCHESTRATION_FAILED', error });
      
      const errorResult = {
        jobId,
        status: 'error',
        error: error.message,
        timestamp: new Date().toISOString()
      };
      
      this.activeJobs.set(jobId, { ...this.activeJobs.get(jobId), status: 'error', result: errorResult });
      
      throw error;
    }
  }

  // Deploy specialized agents for the pipeline
  deployAgents(pipelineConfig) {
    return {
      analyzer: new AgenticETLAgent('analyzer', pipelineConfig.analysisConfig),
      extractor: new AgenticETLAgent('extractor', pipelineConfig.extractionConfig),
      transformer: new AgenticETLAgent('transformer', pipelineConfig.transformationConfig),
      loader: new AgenticETLAgent('loader', pipelineConfig.loadingConfig),
      monitor: new AgenticETLAgent('monitor', pipelineConfig.monitoringConfig)
    };
  }

  // Calculate overall pipeline metrics
  calculateOverallMetrics(results) {
    const totalRecords = results.reduce((sum, result) => {
      return sum + (result.totalRecords || result.recordsProcessed || 0);
    }, 0);
    
    const averageQuality = results
      .filter(result => result.qualityScore || result.overallScore)
      .reduce((sum, result, _, arr) => sum + (result.qualityScore || result.overallScore) / arr.length, 0);
    
    return {
      totalRecordsProcessed: totalRecords,
      averageQualityScore: averageQuality,
      executionTime: Date.now() - this.service.state.context.startTime,
      agentCount: 5,
      paretoEfficiency: this.calculateParetoEfficiency(results)
    };
  }

  calculateParetoEfficiency(results) {
    // Measure if we achieved 80% value with 20% effort
    // This is a simplified calculation
    return 0.8; // Placeholder
  }

  // Get current orchestration status
  getStatus() {
    return {
      currentState: this.service.state.value,
      activeJobs: Array.from(this.activeJobs.entries()).map(([id, job]) => ({
        id,
        status: job.status,
        _config: job.config.name || 'Unnamed Pipeline'
      })),
      metrics: this.service.state.context.metrics
    };
  }

  // Cleanup completed jobs
  cleanup() {
    const completedJobs = Array.from(this.activeJobs.entries())
      .filter(([_, job]) => job.status === 'completed' || job.status === 'error');
    
    completedJobs.forEach(([jobId]) => this.activeJobs.delete(jobId));
    
    this.service.send({ type: 'RESET' });
  }
}

// Export for integration with existing ETL Engine
export default AgenticETLOrchestrator;
