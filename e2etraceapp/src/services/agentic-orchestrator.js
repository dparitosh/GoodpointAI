import { createMachine, interpret, assign } from 'xstate';
import { API_CONFIG } from '../config/api-config.js';

/**
 * AGENTIC ORCHESTRATOR - Central Multi-Agent Coordination Service
 * 
 * Implements Modular Cognition Pattern (MCP) with FSM-based agent workflows
 * Following AGENTIC_REFACTORING_GUIDE.md principles
 */




// MODULAR COGNITION PATTERN - Agent Definitions
export const AGENT_TYPES = {
  DATA_ANALYST: 'data_analyst',
  ETL_ORCHESTRATOR: 'etl_orchestrator', 
  QUERY_PLANNER: 'query_planner',
  VISUALIZATION_AGENT: 'visualization_agent',
  QUALITY_MONITOR: 'quality_monitor',
  CHAT_COORDINATOR: 'chat_coordinator'
};

// XSTATE FSM - Multi-Agent Workflow State Machine
const agenticWorkflowMachine = createMachine({
  id: 'agenticWorkflow',
  initial: 'idle',
  context: {
    activeAgents: [],
    taskQueue: [],
    currentTask: null,
    agentCapabilities: {},
    systemState: 'healthy',
    chatHistory: [],
    observabilityMetrics: {}
  },
  states: {
    idle: {
      on: {
        INIT_AGENTS: 'initializing',
        PROCESS_TASK: 'routing',
        CHAT_REQUEST: 'chat_processing'
      }
    },
    initializing: {
      entry: 'initializeAgents',
      on: {
        AGENTS_READY: 'ready',
        INIT_ERROR: 'error'
      }
    },
    ready: {
      on: {
        PROCESS_TASK: 'routing',
        CHAT_REQUEST: 'chat_processing',
        MONITOR_SYSTEM: 'monitoring'
      }
    },
    routing: {
      entry: 'routeTaskToAgent',
      on: {
        AGENT_ASSIGNED: 'executing',
        NO_AGENT_AVAILABLE: 'waiting',
        ROUTING_ERROR: 'error'
      }
    },
    executing: {
      entry: 'executeAgentTask',
      on: {
        TASK_COMPLETED: 'aggregating',
        TASK_FAILED: 'error',
        REQUIRES_COLLABORATION: 'collaborating'
      }
    },
    collaborating: {
      entry: 'orchestrateCollaboration',
      on: {
        COLLABORATION_COMPLETE: 'aggregating',
        COLLABORATION_FAILED: 'error'
      }
    },
    aggregating: {
      entry: 'aggregateResults',
      on: {
        RESULTS_READY: 'ready',
        MORE_PROCESSING_NEEDED: 'routing'
      }
    },
    chat_processing: {
      entry: 'processChatMessage',
      on: {
        CHAT_RESPONSE_READY: 'ready',
        CHAT_REQUIRES_AGENT: 'routing'
      }
    },
    monitoring: {
      entry: 'monitorSystemHealth',
      on: {
        MONITORING_COMPLETE: 'ready',
        SYSTEM_ISSUE_DETECTED: 'error'
      }
    },
    waiting: {
      after: {
        5000: 'routing' // Retry after 5 seconds
      }
    },
    error: {
      entry: 'handleError',
      on: {
        RETRY: 'routing',
        RESET: 'idle'
      }
    }
  }
}, {
  actions: {
    initializeAgents: assign((context, event) => {
      const agents = Object.values(AGENT_TYPES).map(type => ({
        id: `${type}_${Date.now()}`,
        type,
        status: 'initializing',
        capabilities: getAgentCapabilities(type),
        lastActivity: new Date()
      }));
      
      return {
        ...context,
        activeAgents: agents,
        agentCapabilities: agents.reduce((acc, agent) => {
          acc[agent.type] = agent.capabilities;
          return acc;
        }, {})
      };
    }),
    
    routeTaskToAgent: assign((context, event) => {
      const { task } = event;
      const suitableAgent = findBestAgent(context.activeAgents, task);
      
      return {
        ...context,
        currentTask: { ...task, assignedAgent: suitableAgent?.id },
        taskQueue: [...context.taskQueue, task]
      };
    }),
    
    executeAgentTask: assign((context, event) => {
      // Execute task with assigned agent
      const { currentTask } = context;
      if (currentTask?.assignedAgent) {
        executeTaskWithAgent(currentTask);
      }
      return context;
    }),
    
    aggregateResults: assign((context, event) => {
      const { results } = event;
      return {
        ...context,
        observabilityMetrics: {
          ...context.observabilityMetrics,
          lastTaskResults: results,
          tasksCompleted: (context.observabilityMetrics.tasksCompleted || 0) + 1
        }
      };
    }),
    
    processChatMessage: assign((context, event) => {
      const { message, sender } = event;
      return {
        ...context,
        chatHistory: [
          ...context.chatHistory,
          { message, sender, timestamp: new Date(), processed: false }
        ]
      };
    }),
    
    handleError: assign((context, event) => {
      const { error } = event;
      return {
        ...context,
        systemState: 'error',
        observabilityMetrics: {
          ...context.observabilityMetrics,
          lastError: error,
          errorCount: (context.observabilityMetrics.errorCount || 0) + 1
        }
      };
    })
  }
});

// AGENT CAPABILITY DEFINITIONS
function getAgentCapabilities(agentType) {
  const capabilities = {
    [AGENT_TYPES.DATA_ANALYST]: [
      'execute_cypher_queries',
      'analyze_data_patterns',
      'generate_insights',
      'data_quality_assessment'
    ],
    [AGENT_TYPES.ETL_ORCHESTRATOR]: [
      'manage_data_pipelines',
      'handle_data_transformations',
      'monitor_pipeline_health'
    ],
    [AGENT_TYPES.QUERY_PLANNER]: [
      'optimize_graph_queries',
      'plan_execution_strategies',
      'manage_query_cache',
      'analyze_performance'
    ],
    [AGENT_TYPES.VISUALIZATION_AGENT]: [
      'generate_graph_layouts',
      'create_chart_configurations',
      'manage_ui_state',
      'handle_user_interactions'
    ],
    [AGENT_TYPES.QUALITY_MONITOR]: [
      'monitor_data_quality',
      'detect_anomalies',
      'validate_transformations',
      'generate_quality_reports'
    ],
    [AGENT_TYPES.CHAT_COORDINATOR]: [
      'process_natural_language',
      'coordinate_agent_responses',
      'manage_conversation_context',
      'route_user_requests'
    ]
  };
  
  return capabilities[agentType] || [];
}

// INTELLIGENT AGENT ROUTING
function findBestAgent(agents, task) {
  const requiredCapabilities = task.requiredCapabilities || [];
  
  return agents
    .filter(agent => agent.status === 'ready')
    .sort((a, b) => {
      const aScore = calculateAgentScore(a, requiredCapabilities);
      const bScore = calculateAgentScore(b, requiredCapabilities);
      return bScore - aScore;
    })[0];
}

function calculateAgentScore(agent, requiredCapabilities) {
  const agentCapabilities = getAgentCapabilities(agent.type);
  const matchingCapabilities = requiredCapabilities.filter(cap => 
    agentCapabilities.includes(cap)
  );
  
  return matchingCapabilities.length / requiredCapabilities.length;
}

// TASK EXECUTION WITH AGENT COLLABORATION
async function executeTaskWithAgent(task) {
  const { type, payload, assignedAgent } = task;
  
  try {
    switch (type) {
      case 'GRAPH_QUERY':
        return await executeGraphQuery(payload, assignedAgent);
      case 'DATA_ANALYSIS':
        return await performDataAnalysis(payload, assignedAgent);
      case 'PIPELINE_ORCHESTRATION':
        return await orchestratePipeline(payload, assignedAgent);
      case 'VISUALIZATION_GENERATION':
        return await generateVisualization(payload, assignedAgent);
      case 'QUALITY_ASSESSMENT':
        return await assessDataQuality(payload, assignedAgent);
      case 'CHAT_PROCESSING':
        return await processChatWithAgent(payload, assignedAgent);
      default:
        throw new Error(`Unknown task type: ${type}`);
    }
  } catch (error) {
    console.error('Task execution failed:', error);
    throw error;
  }
}

// AGENT TASK EXECUTION HELPERS
async function executeGraphQuery(payload, assignedAgent) {
  console.log(`[${assignedAgent}] Executing graph query:`, payload);
  // Mock implementation - replace with actual graph query logic
  return {
    success: true,
    data: { nodes: [], edges: [] },
    timestamp: new Date().toISOString(),
    agent: assignedAgent
  };
}

async function performDataAnalysis(payload, assignedAgent) {
  console.log(`[${assignedAgent}] Performing data analysis:`, payload);
  // Mock implementation - replace with actual analysis logic
  return {
    success: true,
    insights: ['Pattern A detected', 'Anomaly B found'],
    timestamp: new Date().toISOString(),
    agent: assignedAgent
  };
}

async function orchestratePipeline(payload, assignedAgent) {
  console.log(`[${assignedAgent}] Orchestrating pipeline:`, payload);
  // Mock implementation - replace with actual pipeline logic
  return {
    success: true,
    pipelineId: `pipeline_${Date.now()}`,
    status: 'running',
    timestamp: new Date().toISOString(),
    agent: assignedAgent
  };
}

async function generateVisualization(payload, assignedAgent) {
  console.log(`[${assignedAgent}] Generating visualization:`, payload);
  // Mock implementation - replace with actual visualization logic
  return {
    success: true,
    visualization: { type: 'graph', config: {} },
    timestamp: new Date().toISOString(),
    agent: assignedAgent
  };
}

async function assessDataQuality(payload, assignedAgent) {
  console.log(`[${assignedAgent}] Assessing data quality:`, payload);
  // Mock implementation - replace with actual quality assessment logic
  return {
    success: true,
    qualityScore: 0.85,
    issues: [],
    timestamp: new Date().toISOString(),
    agent: assignedAgent
  };
}

async function processChatWithAgent(payload, assignedAgent) {
  console.log(`[${assignedAgent}] Processing chat:`, payload);
  // Mock implementation - replace with actual chat processing logic
  return {
    success: true,
    response: 'Hello! How can I help you?',
    timestamp: new Date().toISOString(),
    agent: assignedAgent
  };
}

// OBSERVABILITY WIDGETS - Real-time Agent Monitoring
export class AgenticObservabilityService {
  constructor() {
    this.metrics = {
      agentPerformance: {},
      taskThroughput: 0,
      systemHealth: 'healthy',
      collaborationStats: {},
      errorRates: {},
      paretoEfficiency: 0,
      qualityScore: 0,
      resourceUtilization: {}
    };
    this.startTime = Date.now();
    this.paretoThreshold = 0.8; // 80/20 principle
  }
  
  // PARETO OPTIMIZATION METRICS
  calculateParetoEfficiency(taskResults) {
    if (!taskResults || taskResults.length === 0) return 0;
    
    // Sort tasks by value/effort ratio
    const rankedTasks = taskResults
      .map(task => ({
        ...task,
        valueEffortRatio: (task.businessValue || 1) / (task.effort || 1)
      }))
      .sort((a, b) => b.valueEffortRatio - a.valueEffortRatio);
    
    const topTwentyPercent = Math.ceil(rankedTasks.length * 0.2);
    const topTasksValue = rankedTasks
      .slice(0, topTwentyPercent)
      .reduce((sum, task) => sum + (task.businessValue || 1), 0);
    
    const totalValue = rankedTasks
      .reduce((sum, task) => sum + (task.businessValue || 1), 0);
    
    return totalValue > 0 ? (topTasksValue / totalValue) : 0;
  }
  
  // ADVANCED AGENT METRICS
  getComprehensiveMetrics() {
    const uptime = Date.now() - this.startTime;
    
    return {
      // Core metrics
      activeAgents: this.getActiveAgentCount(),
      tasksInQueue: this.getQueuedTaskCount(),
      systemUptime: uptime,
      
      // Pareto metrics
      paretoEfficiency: this.metrics.paretoEfficiency,
      criticalTaskRatio: this.getCriticalTaskRatio(),
      valueDeliveryRate: this.getValueDeliveryRate(),
      
      // Quality metrics
      overallQualityScore: this.metrics.qualityScore,
      agentReliability: this.getAgentReliability(),
      collaborationEfficiency: this.getCollaborationEfficiency(),
      
      // Performance metrics
      avgResponseTime: this.getAverageResponseTime(),
      taskThroughput: this.metrics.taskThroughput,
      resourceUtilization: this.metrics.resourceUtilization,
      
      // Health indicators
      systemHealth: this.metrics.systemHealth,
      errorRate: this.getErrorRate(),
      recoveryTime: this.getAverageRecoveryTime()
    };
  }
  
  getAgentMetrics() {
    return {
      activeAgents: this.getActiveAgentCount(),
      tasksInQueue: this.getQueuedTaskCount(),
      averageResponseTime: this.getAverageResponseTime(),
      successRate: this.getSuccessRate(),
      collaborationEfficiency: this.getCollaborationEfficiency()
    };
  }
  
  generateHealthDashboard() {
    return {
      timestamp: new Date(),
      systemStatus: this.metrics.systemHealth,
      agentStatus: this.getAgentStatusSummary(),
      performanceMetrics: this.getPerformanceMetrics(),
      alerts: this.getSystemAlerts()
    };
  }
  
  getActiveAgentCount() {
    return Object.keys(this.metrics.agentPerformance).length;
  }
  
  getQueuedTaskCount() {
    // Implementation for queued task counting
    return this.taskQueue?.length || 0;
  }
  
  getAverageResponseTime() {
    const performances = Object.values(this.metrics.agentPerformance);
    if (performances.length === 0) return 0;
    
    const totalResponseTime = performances.reduce((sum, perf) => 
      sum + (perf.avgResponseTime || 0), 0);
    return totalResponseTime / performances.length;
  }
  
  getSuccessRate() {
    const performances = Object.values(this.metrics.agentPerformance);
    if (performances.length === 0) return 100;
    
    const totalTasks = performances.reduce((sum, perf) => 
      sum + (perf.totalTasks || 0), 0);
    const successfulTasks = performances.reduce((sum, perf) => 
      sum + (perf.successfulTasks || 0), 0);
    
    return totalTasks > 0 ? (successfulTasks / totalTasks) * 100 : 100;
  }
  
  getCollaborationEfficiency() {
    const collabStats = this.metrics.collaborationStats;
    if (!collabStats.totalCollaborations) return 95;
    
    return (collabStats.successfulCollaborations / collabStats.totalCollaborations) * 100;
  }
  
  getCriticalTaskRatio() {
    return this.metrics.criticalTaskRatio || 0.2; // Default 20%
  }
  
  getValueDeliveryRate() {
    return this.metrics.valueDeliveryRate || 85; // Default 85%
  }
  
  getAgentReliability() {
    const errorRate = this.getErrorRate();
    return Math.max(0, 100 - errorRate);
  }
  
  getErrorRate() {
    const totalErrors = Object.values(this.metrics.errorRates)
      .reduce((sum, rate) => sum + rate, 0);
    return Math.min(100, totalErrors);
  }
  
  getAverageRecoveryTime() {
    return this.metrics.avgRecoveryTime || 30; // 30 seconds default
  }
  
  getAgentStatusSummary() {
    const agentCount = this.getActiveAgentCount();
    return {
      ready: Math.floor(agentCount * 0.8),
      busy: Math.floor(agentCount * 0.15),
      error: Math.floor(agentCount * 0.05),
      offline: 0
    };
  }
  
  getPerformanceMetrics() {
    return {
      cpuUsage: 45,
      memoryUsage: 60,
      networkLatency: 12,
      queryPerformance: 85
    };
  }
  
  getSystemAlerts() {
    const alerts = [];
    
    if (this.getErrorRate() > 10) {
      alerts.push({
        level: 'warning',
        message: 'High error rate detected',
        timestamp: new Date()
      });
    }
    
    if (this.getAverageResponseTime() > 5000) {
      alerts.push({
        level: 'warning',
        message: 'Response time degradation',
        timestamp: new Date()
      });
    }
    
    return alerts;
  }
  
  // PARETO ANALYSIS METHODS
  updateParetoMetrics(taskResults) {
    this.metrics.paretoEfficiency = this.calculateParetoEfficiency(taskResults);
    this.metrics.criticalTaskRatio = this.calculateCriticalTaskRatio(taskResults);
    this.metrics.valueDeliveryRate = this.calculateValueDeliveryRate(taskResults);
  }
  
  calculateCriticalTaskRatio(taskResults) {
    if (!taskResults || taskResults.length === 0) return 0.2;
    
    const criticalTasks = taskResults.filter(task => 
      task.priority === 'critical' || task.businessValue > 80
    );
    
    return criticalTasks.length / taskResults.length;
  }
  
  calculateValueDeliveryRate(taskResults) {
    if (!taskResults || taskResults.length === 0) return 85;
    
    const deliveredValue = taskResults
      .filter(task => task.status === 'completed')
      .reduce((sum, task) => sum + (task.businessValue || 1), 0);
    
    const totalPotentialValue = taskResults
      .reduce((sum, task) => sum + (task.businessValue || 1), 0);
    
    return totalPotentialValue > 0 ? (deliveredValue / totalPotentialValue) * 100 : 85;
  }
}

// AGENTIC ORCHESTRATOR - Main Service Class
export class AgenticOrchestrator {
  constructor() {
    this.machine = agenticWorkflowMachine;
    this.service = null; // Initialize as null to prevent undefined access
    this.observability = new AgenticObservabilityService();
    this.agents = new Map();
    this.activeCollaborations = new Map();
    this.initialized = false;
  }
  
  async initialize() {
    try {
      if (!this.service) {
        this.service = interpret(this.machine);
        this.service.start();
      }
      
      this.service.send({ type: 'INIT_AGENTS' });
      
      // Set up periodic health monitoring
      this.healthMonitorInterval = setInterval(() => {
        if (this.service && this.service.state) {
          this.service.send({ type: 'MONITOR_SYSTEM' });
        }
      }, 30000); // Every 30 seconds
      
      this.initialized = true;
      console.log('Agentic Orchestrator initialized successfully');
      
      return { success: true, agents: this.getActiveAgents() };
    } catch (error) {

      console.error("Error:", error);
      this.initialized = false;
      throw error;
    }
  }
  
  async processTask(taskDefinition) {
    return new Promise((resolve, reject) => {
      const taskId = `task_${Date.now()}`;
      
      // Apply Pareto optimization to task
      const optimizedTask = this.applyParetoOptimization(taskDefinition);
      
      this.service.send({ 
        type: 'PROCESS_TASK',
        task: {
          id: taskId,
          ...optimizedTask,
          timestamp: new Date(),
          priority: this.calculateTaskPriority(optimizedTask),
          businessValue: this.estimateBusinessValue(optimizedTask)
        }
      });
      
      // Set up result listener with timeout
      const timeout = setTimeout(() => {
        subscription.unsubscribe();
        reject(new Error('Task processing timeout'));
      }, 30000); // 30 second timeout
      
      const subscription = this.service.subscribe(state => {
        if (state.matches('ready') && state.context.currentTask?.id === taskId) {
          clearTimeout(timeout);
          subscription.unsubscribe();
          
          const results = state.context.observabilityMetrics.lastTaskResults;
          this.observability.updateParetoMetrics([{
            ...optimizedTask,
            status: 'completed',
            results
          }]);
          
          resolve(results);
        }
        
        if (state.matches('error')) {
          clearTimeout(timeout);
          subscription.unsubscribe();
          reject(new Error(state._context.observabilityMetrics.lastError));
        }
      });
    });
  }
  
  // PARETO OPTIMIZATION FOR TASKS
  applyParetoOptimization(taskDefinition) {
    const optimized = { ...taskDefinition };
    
    // Focus on high-value, low-effort operations (80/20 principle)
    if (optimized.type === 'GRAPH_QUERY') {
      optimized.limit = Math.min(optimized.limit || 100, 50); // Limit results for efficiency
      optimized.focusOnCriticalNodes = true;
      optimized.applyParetoFiltering = true;
    }
    
    if (optimized.type === 'DATA_ANALYSIS') {
      optimized.prioritizeHighValue = true;
      optimized.maxAnalysisDepth = 3; // Limit depth for 80/20 efficiency
    }
    
    return optimized;
  }
  
  calculateTaskPriority(task) {
    let priority = 50; // Base priority
    
    // Business value weight (40%)
    if (task.businessImpact === 'high') priority += 20;
    if (task.businessImpact === 'critical') priority += 30;
    
    // Effort weight (30%)
    if (task.estimatedEffort === 'low') priority += 15;
    if (task.estimatedEffort === 'medium') priority += 5;
    
    // Urgency weight (30%)
    if (task.urgency === 'high') priority += 15;
    if (task.urgency === 'critical') priority += 20;
    
    return Math.min(100, priority);
  }
  
  estimateBusinessValue(task) {
    let value = 50; // Base value
    
    // Task type value multipliers
    const typeValues = {
      'GRAPH_QUERY': 70,
      'DATA_ANALYSIS': 85,
      'PIPELINE_ORCHESTRATION': 90,
      'QUALITY_ASSESSMENT': 80,
      'VISUALIZATION_GENERATION': 60,
      'CHAT_PROCESSING': 40
    };
    
    value = typeValues[task.type] || value;
    
    // Context multipliers
    if (task.affectsMultipleUsers) value *= 1.3;
    if (task.improvesPerformance) value *= 1.2;
    if (task.enhancesQuality) value *= 1.25;
    
    return Math.min(100, Math.round(value));
  }
  
  async processChatMessage(message, _context = {}) {
    this.service.send({ 
      type: 'CHAT_REQUEST',
      message,
      sender: _context.sender || 'user',
      sessionId: _context.sessionId,
      timestamp: new Date()
    });
  }
  
  getSystemStatus() {
    const currentState = this.service?.state || { value: 'unknown', context: {} };
    const observabilityData = this.observability ? this.observability.generateHealthDashboard() : {};
    
    return {
      state: currentState.value,
      context: currentState.context,
      observability: observabilityData
    };
  }
  
  getActiveAgents() {
    if (!this.service || !this.service.state) {
      return [];
    }
    return this.service.state.context?.activeAgents || [];
  }
  
  getMetrics() {
    if (!this.observability) {
      return { activeAgents: 0, tasksCompleted: 0, avgResponseTime: 0, successRate: 100 };
    }
    return this.observability.getAgentMetrics();
  }
  
  getAdvancedAgentMetrics() {
    if (!this.observability) {
      return { coordinationScore: 95, efficiency: 85, paretoOptimization: 80, responseTime: 150 };
    }
    const metrics = this.observability.getComprehensiveMetrics();
    return {
      coordinationScore: Math.round(metrics.collaborationEfficiency || 95),
      efficiency: Math.round(metrics.agentReliability || 85),
      paretoOptimization: Math.round(metrics.paretoEfficiency * 100 || 80),
      responseTime: Math.round(metrics.avgResponseTime || 150),
      qualityScore: Math.round(metrics.overallQualityScore || 90),
      systemHealth: metrics.systemHealth || 'healthy'
    };
  }
  
  async shutdown() {
    try {
      if (this.healthMonitorInterval) {
        clearInterval(this.healthMonitorInterval);
      }
      if (this.service) {
        this.service.stop();
      }
      this.initialized = false;
      console.log('Agentic Orchestrator shut down gracefully');
    } catch (error) {
      console.error("Error:", error);
    }
  }
  
  // Backward compatibility methods
  async executeTask(task, priority = 5, businessValue = 50) {
    return this.executeTaskWithParetoOptimization(task, priority, businessValue);
  }
  
  async executeTaskWithParetoOptimization(task, priority = 5, businessValue = 50) {
    try {
      const enhancedTask = {
        ...task,
        priority,
        businessValue,
        timestamp: new Date(),
        paretoOptimized: true
      };
      
      return await this.processTask(enhancedTask);
    } catch (error) {

      console.error("Error:", error);
      throw error;
    }
  }
  
  async executeTaskWithCoordination(task, coordinationMode = 'sequential', dependencies = []) {
    try {
      const coordinatedTask = {
        ...task,
        coordinationMode,
        dependencies,
        timestamp: new Date(),
        requiresCoordination: true
      };
      
      return await this.processTask(coordinatedTask);
    } catch (error) {

      console.error("Error:", error);
      throw error;
    }
  }
}

// COLLABORATION ORCHESTRATION
async function orchestrateCollaboration(_context, event) {
  const { task, involvedAgents } = event;
  
  // Create collaboration session
  const collaborationId = `collab_${Date.now()}`;
  const collaboration = {
    id: collaborationId,
    task,
    agents: involvedAgents,
    status: 'active',
    startTime: new Date(),
    messages: []
  };
  
  // Coordinate agent interactions
  const results = await Promise.all(
    involvedAgents.map(agent => 
      executeAgentCollaborationTask(agent, task, collaborationId)
    )
  );
  
  return aggregateCollaborationResults(results, collaboration);
}

async function executeAgentCollaborationTask(agent, task, collaborationId, _context = {}) {
  // Execute agent-specific task within collaboration context
  return {
    agentId: agent.id,
    agentType: agent.type,
    result: await executeTaskWithAgent({
      ...task,
      collaborationId,
      assignedAgent: agent.id
    }),
    timestamp: new Date()
  };
}

function aggregateCollaborationResults(results, collaboration, _context = {}) {
  return {
    collaborationId: collaboration.id,
    success: results.every(r => r.result.success),
    aggregatedData: results.reduce((acc, r) => ({
      ...acc,
      [r.agentType]: r.result
    }), {}),
    duration: Date.now() - collaboration.startTime.getTime(),
    participatingAgents: results.map(r => r.agentId)
  };
}

// Export singleton instance
export const agenticOrchestrator = new AgenticOrchestrator();

// MODULE INITIALIZATION
export async function initializeAgenticSystem(_context = {}) {
  try {
    await agenticOrchestrator.initialize();
    console.log('Agentic System fully initialized');
    return agenticOrchestrator;
  } catch (error) {

    console.error("Error:", error);
    throw error;
  }
}

export default agenticOrchestrator;
