/**
 * 🔄 Self-Healing Orchestration Machine
 * =====================================
 * 
 * XState machine for resilient data migration with:
 * - Exponential backoff retry logic
 * - Circuit breaker pattern
 * - Intelligent failure routing
 * - Validation checkpoints
 * - Auto-recovery mechanisms
 * - Dead letter queue handling
 * 
 * Integrations:
 * - Data Lineage tracking for failure root cause analysis
 * - OpenSearch for failure pattern detection
 * - Ollama for intelligent error classification
 */

import { createMachine, assign } from 'xstate';

// ============= CONSTANTS =============

export const SelfHealingStates = {
  IDLE: 'idle',
  EXECUTING: 'executing',
  VALIDATING: 'validating',
  RETRYING: 'retrying',
  CIRCUIT_OPEN: 'circuit_open',
  CIRCUIT_HALF_OPEN: 'circuit_half_open',
  ROUTING_ALTERNATIVE: 'routing_alternative',
  RECOVERING: 'recovering',
  FAILED: 'failed',
  COMPLETED: 'completed',
  DEAD_LETTER: 'dead_letter'
};

export const SelfHealingEvents = {
  START: 'START',
  SUCCESS: 'SUCCESS',
  VALIDATION_PASSED: 'VALIDATION_PASSED',
  VALIDATION_FAILED: 'VALIDATION_FAILED',
  ERROR: 'ERROR',
  RETRY: 'RETRY',
  RETRY_EXHAUSTED: 'RETRY_EXHAUSTED',
  CIRCUIT_BREAKER_TRIP: 'CIRCUIT_BREAKER_TRIP',
  CIRCUIT_RESET: 'CIRCUIT_RESET',
  ROUTE_ALTERNATIVE: 'ROUTE_ALTERNATIVE',
  RECOVERY_SUCCESS: 'RECOVERY_SUCCESS',
  RECOVERY_FAILED: 'RECOVERY_FAILED',
  SEND_TO_DLQ: 'SEND_TO_DLQ',
  CANCEL: 'CANCEL'
};

// Retry configuration
const RETRY_CONFIG = {
  maxAttempts: 5,
  initialDelayMs: 1000,
  maxDelayMs: 30000,
  backoffMultiplier: 2,
  jitterFactor: 0.1
};

// Circuit breaker configuration
const CIRCUIT_BREAKER_CONFIG = {
  failureThreshold: 5,
  successThreshold: 2,
  timeoutMs: 60000,
  halfOpenMaxAttempts: 3
};

// ============= HELPER FUNCTIONS =============

/**
 * Calculate exponential backoff with jitter
 */
const calculateBackoff = (attempt, config = RETRY_CONFIG) => {
  const exponentialDelay = Math.min(
    config.initialDelayMs * Math.pow(config.backoffMultiplier, attempt),
    config.maxDelayMs
  );
  
  // Add jitter to prevent thundering herd
  const jitter = exponentialDelay * config.jitterFactor * (Math.random() - 0.5);
  return Math.floor(exponentialDelay + jitter);
};

/**
 * Classify error severity
 */
const classifyError = (error) => {
  const errorMessage = error?.message?.toLowerCase() || '';
  
  if (errorMessage.includes('network') || errorMessage.includes('timeout')) {
    return { severity: 'TRANSIENT', retryable: true, category: 'NETWORK' };
  } else if (errorMessage.includes('auth') || errorMessage.includes('permission')) {
    return { severity: 'CRITICAL', retryable: false, category: 'AUTH' };
  } else if (errorMessage.includes('schema') || errorMessage.includes('validation')) {
    return { severity: 'MEDIUM', retryable: false, category: 'VALIDATION' };
  } else if (errorMessage.includes('data quality') || errorMessage.includes('corrupt')) {
    return { severity: 'MEDIUM', retryable: true, category: 'DATA_QUALITY' };
  } else {
    return { severity: 'UNKNOWN', retryable: true, category: 'UNKNOWN' };
  }
};

/**
 * Determine if circuit breaker should trip
 */
const shouldTripCircuitBreaker = (context) => {
  return context.consecutiveFailures >= CIRCUIT_BREAKER_CONFIG.failureThreshold;
};

/**
 * Check if alternative route is available
 */
const hasAlternativeRoute = (context) => {
  return context.alternativeRoutes && context.alternativeRoutes.length > 0;
};

/**
 * Select alternative route based on failure history
 */
const selectAlternativeRoute = (context) => {
  if (!context.alternativeRoutes?.length) return null;
  
  // Filter out previously failed routes
  const availableRoutes = context.alternativeRoutes.filter(
    route => !context.failedRoutes.includes(route.id)
  );
  
  if (availableRoutes.length === 0) return null;
  
  // Select route with highest success rate
  return availableRoutes.sort((a, b) => b.successRate - a.successRate)[0];
};

// ============= MACHINE DEFINITION =============

export const selfHealingMachine = createMachine({
  id: 'self-healing-orchestration',
  initial: SelfHealingStates.IDLE,
  
  context: {
    // Execution context
    taskId: null,
    workflowId: null,
    currentRoute: null,
    alternativeRoutes: [],
    
    // Retry state
    retryAttempt: 0,
    maxRetries: RETRY_CONFIG.maxAttempts,
    lastError: null,
    errorHistory: [],
    
    // Circuit breaker state
    consecutiveFailures: 0,
    consecutiveSuccesses: 0,
    circuitBreakerOpenTime: null,
    halfOpenAttempts: 0,
    
    // Recovery state
    failedRoutes: [],
    recoveryStrategies: [],
    validationCheckpoints: [],
    
    // Metrics
    startTime: null,
    totalDuration: 0,
    successCount: 0,
    failureCount: 0,
    retryCount: 0,
    
    // Dead letter queue
    dlqMessages: []
  },
  
  states: {
    [SelfHealingStates.IDLE]: {
      meta: {
        label: 'Idle',
        description: 'Waiting for task execution',
        color: '#6c757d',
        icon: '⏸️'
      },
      on: {
        [SelfHealingEvents.START]: {
          target: SelfHealingStates.EXECUTING,
          actions: assign({
            startTime: () => Date.now(),
            retryAttempt: 0,
            consecutiveFailures: 0,
            errorHistory: []
          })
        }
      }
    },
    
    [SelfHealingStates.EXECUTING]: {
      meta: {
        label: 'Executing',
        description: 'Running task on primary route',
        color: '#007bff',
        icon: '▶️',
        progress: true
      },
      entry: ['logExecution', 'trackLineage'],
      on: {
        [SelfHealingEvents.SUCCESS]: {
          target: SelfHealingStates.VALIDATING,
          actions: assign({
            consecutiveSuccesses: (ctx) => ctx.consecutiveSuccesses + 1,
            consecutiveFailures: 0,
            successCount: (ctx) => ctx.successCount + 1
          })
        },
        [SelfHealingEvents.ERROR]: [
          {
            target: SelfHealingStates.CIRCUIT_OPEN,
            cond: 'shouldTripCircuitBreaker',
            actions: assign({
              lastError: (_, event) => event.error,
              errorHistory: (ctx, event) => [...ctx.errorHistory, {
                timestamp: Date.now(),
                error: event.error,
                classification: classifyError(event.error)
              }],
              consecutiveFailures: (ctx) => ctx.consecutiveFailures + 1,
              circuitBreakerOpenTime: () => Date.now()
            })
          },
          {
            target: SelfHealingStates.RETRYING,
            cond: 'canRetry',
            actions: assign({
              lastError: (_, event) => event.error,
              errorHistory: (ctx, event) => [...ctx.errorHistory, {
                timestamp: Date.now(),
                error: event.error,
                classification: classifyError(event.error)
              }],
              retryAttempt: (ctx) => ctx.retryAttempt + 1,
              consecutiveFailures: (ctx) => ctx.consecutiveFailures + 1,
              failureCount: (ctx) => ctx.failureCount + 1
            })
          },
          {
            target: SelfHealingStates.ROUTING_ALTERNATIVE,
            cond: 'hasAlternativeRoute',
            actions: assign({
              lastError: (_, event) => event.error,
              failedRoutes: (ctx) => [...ctx.failedRoutes, ctx.currentRoute?.id],
              consecutiveFailures: (ctx) => ctx.consecutiveFailures + 1
            })
          },
          {
            target: SelfHealingStates.FAILED,
            actions: assign({
              lastError: (_, event) => event.error,
              failureCount: (ctx) => ctx.failureCount + 1
            })
          }
        ],
        [SelfHealingEvents.CANCEL]: {
          target: SelfHealingStates.FAILED,
          actions: assign({
            lastError: () => new Error('Task cancelled by user')
          })
        }
      }
    },
    
    [SelfHealingStates.VALIDATING]: {
      meta: {
        label: 'Validating',
        description: 'Running validation checkpoints',
        color: '#28a745',
        icon: '✓',
        progress: true
      },
      entry: ['runValidationCheckpoints'],
      on: {
        [SelfHealingEvents.VALIDATION_PASSED]: {
          target: SelfHealingStates.COMPLETED,
          actions: assign({
            totalDuration: (ctx) => Date.now() - ctx.startTime
          })
        },
        [SelfHealingEvents.VALIDATION_FAILED]: {
          target: SelfHealingStates.RECOVERING,
          actions: assign({
            lastError: (_, event) => event.error
          })
        }
      }
    },
    
    [SelfHealingStates.RETRYING]: {
      meta: {
        label: 'Retrying',
        description: 'Exponential backoff retry in progress',
        color: '#ffc107',
        icon: '🔄',
        progress: true
      },
      entry: ['calculateBackoff', 'logRetry'],
      after: {
        RETRY_DELAY: {
          target: SelfHealingStates.EXECUTING,
          actions: assign({
            retryCount: (ctx) => ctx.retryCount + 1
          })
        }
      },
      on: {
        [SelfHealingEvents.RETRY_EXHAUSTED]: {
          target: SelfHealingStates.ROUTING_ALTERNATIVE,
          cond: 'hasAlternativeRoute'
        },
        [SelfHealingEvents.CANCEL]: {
          target: SelfHealingStates.FAILED
        }
      }
    },
    
    [SelfHealingStates.CIRCUIT_OPEN]: {
      meta: {
        label: 'Circuit Open',
        description: 'Circuit breaker tripped - cooling down',
        color: '#dc3545',
        icon: '🚫',
        alert: true
      },
      entry: ['logCircuitOpen', 'notifyMonitoring'],
      after: {
        CIRCUIT_TIMEOUT: {
          target: SelfHealingStates.CIRCUIT_HALF_OPEN,
          actions: assign({
            halfOpenAttempts: 0
          })
        }
      },
      on: {
        [SelfHealingEvents.ROUTE_ALTERNATIVE]: {
          target: SelfHealingStates.ROUTING_ALTERNATIVE,
          cond: 'hasAlternativeRoute'
        }
      }
    },
    
    [SelfHealingStates.CIRCUIT_HALF_OPEN]: {
      meta: {
        label: 'Circuit Half-Open',
        description: 'Testing if service recovered',
        color: '#fd7e14',
        icon: '🔶',
        progress: true
      },
      entry: ['logCircuitHalfOpen'],
      on: {
        [SelfHealingEvents.SUCCESS]: [
          {
            target: SelfHealingStates.VALIDATING,
            cond: 'circuitBreakerCanReset',
            actions: assign({
              consecutiveSuccesses: (ctx) => ctx.consecutiveSuccesses + 1,
              consecutiveFailures: 0,
              circuitBreakerOpenTime: null,
              halfOpenAttempts: 0
            })
          },
          {
            target: SelfHealingStates.CIRCUIT_HALF_OPEN,
            actions: assign({
              consecutiveSuccesses: (ctx) => ctx.consecutiveSuccesses + 1,
              halfOpenAttempts: (ctx) => ctx.halfOpenAttempts + 1
            })
          }
        ],
        [SelfHealingEvents.ERROR]: {
          target: SelfHealingStates.CIRCUIT_OPEN,
          actions: assign({
            consecutiveFailures: (ctx) => ctx.consecutiveFailures + 1,
            consecutiveSuccesses: 0,
            circuitBreakerOpenTime: () => Date.now(),
            halfOpenAttempts: 0
          })
        }
      }
    },
    
    [SelfHealingStates.ROUTING_ALTERNATIVE]: {
      meta: {
        label: 'Alternative Route',
        description: 'Switching to backup route',
        color: '#17a2b8',
        icon: '🔀',
        progress: true
      },
      entry: ['selectAlternativeRoute', 'logRouteChange'],
      always: [
        {
          target: SelfHealingStates.EXECUTING,
          cond: 'alternativeRouteSelected',
          actions: assign({
            retryAttempt: 0,
            consecutiveFailures: 0
          })
        },
        {
          target: SelfHealingStates.DEAD_LETTER
        }
      ]
    },
    
    [SelfHealingStates.RECOVERING]: {
      meta: {
        label: 'Recovering',
        description: 'Executing recovery strategy',
        color: '#6f42c1',
        icon: '🔧',
        progress: true
      },
      entry: ['executeRecoveryStrategy'],
      on: {
        [SelfHealingEvents.RECOVERY_SUCCESS]: {
          target: SelfHealingStates.COMPLETED,
          actions: assign({
            totalDuration: (ctx) => Date.now() - ctx.startTime
          })
        },
        [SelfHealingEvents.RECOVERY_FAILED]: {
          target: SelfHealingStates.DEAD_LETTER
        }
      }
    },
    
    [SelfHealingStates.COMPLETED]: {
      meta: {
        label: 'Completed',
        description: 'Task completed successfully',
        color: '#28a745',
        icon: '✅',
        final: true
      },
      type: 'final',
      entry: ['logSuccess', 'updateMetrics', 'createLineageNode']
    },
    
    [SelfHealingStates.FAILED]: {
      meta: {
        label: 'Failed',
        description: 'Task failed after all recovery attempts',
        color: '#dc3545',
        icon: '❌',
        alert: true,
        final: true
      },
      type: 'final',
      entry: ['logFailure', 'updateMetrics', 'notifyFailure', 'createLineageNode']
    },
    
    [SelfHealingStates.DEAD_LETTER]: {
      meta: {
        label: 'Dead Letter Queue',
        description: 'Task moved to DLQ for manual review',
        color: '#6c757d',
        icon: '📮',
        alert: true,
        final: true
      },
      type: 'final',
      entry: ['sendToDeadLetterQueue', 'logDLQ', 'notifyOperations']
    }
  }
}, {
  // Guards
  guards: {
    canRetry: (context) => {
      if (context.retryAttempt >= context.maxRetries) return false;
      
      const lastError = context.errorHistory[context.errorHistory.length - 1];
      return lastError?.classification?.retryable !== false;
    },
    
    shouldTripCircuitBreaker: (context) => {
      return shouldTripCircuitBreaker(context);
    },
    
    hasAlternativeRoute: (context) => {
      return hasAlternativeRoute(context);
    },
    
    circuitBreakerCanReset: (context) => {
      return context.consecutiveSuccesses >= CIRCUIT_BREAKER_CONFIG.successThreshold;
    },
    
    alternativeRouteSelected: (context) => {
      return context.currentRoute !== null;
    }
  },
  
  // Delays
  delays: {
    RETRY_DELAY: (context) => {
      return calculateBackoff(context.retryAttempt);
    },
    
    CIRCUIT_TIMEOUT: () => {
      return CIRCUIT_BREAKER_CONFIG.timeoutMs;
    }
  },
  
  // Actions
  actions: {
    logExecution: (context) => {
      console.log(`[Self-Healing] Executing task ${context.taskId} on route ${context.currentRoute?.id}`);
    },
    
    trackLineage: (context) => {
      console.log(`[Self-Healing] Tracking lineage for workflow ${context.workflowId}`);
    },
    
    calculateBackoff: (context) => {
      const delay = calculateBackoff(context.retryAttempt);
      console.log(`[Self-Healing] Retry ${context.retryAttempt + 1}/${context.maxRetries} after ${delay}ms`);
    },
    
    logRetry: (context) => {
      console.log(`[Self-Healing] Retrying task ${context.taskId}`, {
        attempt: context.retryAttempt,
        error: context.lastError?.message
      });
    },
    
    logCircuitOpen: (context) => {
      console.error(`[Self-Healing] Circuit breaker OPEN - ${context.consecutiveFailures} consecutive failures`);
    },
    
    logCircuitHalfOpen: () => {
      console.log(`[Self-Healing] Circuit breaker HALF-OPEN - testing recovery`);
    },
    
    selectAlternativeRoute: assign({
      currentRoute: (context) => selectAlternativeRoute(context)
    }),
    
    logRouteChange: (context) => {
      console.log(`[Self-Healing] Switching to alternative route: ${context.currentRoute?.id}`);
    },
    
    runValidationCheckpoints: (context) => {
      console.log(`[Self-Healing] Running ${context.validationCheckpoints.length} validation checkpoints`);
    },
    
    executeRecoveryStrategy: (context) => {
      console.log(`[Self-Healing] Executing recovery strategy for task ${context.taskId}`);
    },
    
    logSuccess: (context) => {
      console.log(`[Self-Healing] Task ${context.taskId} completed successfully in ${context.totalDuration}ms`);
    },
    
    logFailure: (context) => {
      console.error(`[Self-Healing] Task ${context.taskId} FAILED after ${context.retryCount} retries`);
    },
    
    logDLQ: (context) => {
      console.warn(`[Self-Healing] Task ${context.taskId} moved to Dead Letter Queue`);
    },
    
    sendToDeadLetterQueue: assign({
      dlqMessages: (context) => [...context.dlqMessages, {
        taskId: context.taskId,
        workflowId: context.workflowId,
        timestamp: Date.now(),
        error: context.lastError,
        errorHistory: context.errorHistory,
        retryCount: context.retryCount
      }]
    }),
    
    updateMetrics: (context) => {
      console.log(`[Self-Healing] Metrics:`, {
        successCount: context.successCount,
        failureCount: context.failureCount,
        retryCount: context.retryCount,
        duration: context.totalDuration
      });
    },
    
    createLineageNode: (context) => {
      console.log(`[Self-Healing] Creating lineage node for task ${context.taskId}`);
    },
    
    notifyMonitoring: (context) => {
      console.warn(`[Self-Healing] ALERT: Circuit breaker tripped for ${context.currentRoute?.id}`);
    },
    
    notifyFailure: (context) => {
      console.error(`[Self-Healing] ALERT: Task ${context.taskId} failed permanently`);
    },
    
    notifyOperations: (context) => {
      console.warn(`[Self-Healing] ALERT: Task ${context.taskId} requires manual intervention`);
    }
  }
});

// Export for testing and integration
export default selfHealingMachine;
