/**
 * PLM Migration State Machine Definition
 * Defines states, transitions, and metadata for migration visualization
 */

export const MigrationStates = {
  IDLE: 'idle',
  INITIALIZING: 'initializing',
  DISCOVERING: 'discovering',
  PROFILING: 'profiling',
  SCHEMA_MAPPING: 'schema_mapping',
  DATA_MIGRATION: 'data_migration',
  VALIDATION: 'validation',
  PAUSED: 'paused',
  COMPLETED: 'completed',
  FAILED: 'failed',
  CANCELLED: 'cancelled'
};

export const MigrationEvents = {
  START: 'START',
  PAUSE: 'PAUSE',
  RESUME: 'RESUME',
  RETRY: 'RETRY',
  CANCEL: 'CANCEL',
  AUTO: 'AUTO',
  ERROR: 'ERROR'
};

/**
 * State machine configuration
 */
export const plmMigrationMachine = {
  id: 'plm-migration',
  initial: MigrationStates.IDLE,
  
  states: {
    [MigrationStates.IDLE]: {
      label: 'Idle',
      description: 'Migration not started',
      color: '#6c757d',
      on: {
        [MigrationEvents.START]: MigrationStates.INITIALIZING
      },
      actions: ['START'],
      metadata: {
        icon: 'pause-circle',
        configPage: null
      }
    },
    
    [MigrationStates.INITIALIZING]: {
      label: 'Initializing',
      description: 'Setting up migration environment',
      color: '#17a2b8',
      on: {
        [MigrationEvents.AUTO]: MigrationStates.DISCOVERING,
        [MigrationEvents.CANCEL]: MigrationStates.CANCELLED
      },
      actions: ['CANCEL'],
      metadata: {
        icon: 'settings',
        configPage: null,
        progress: true
      }
    },
    
    [MigrationStates.DISCOVERING]: {
      label: 'Discovering',
      description: 'Analyzing source databases',
      color: '#007bff',
      on: {
        [MigrationEvents.AUTO]: MigrationStates.PROFILING,
        [MigrationEvents.PAUSE]: MigrationStates.PAUSED,
        [MigrationEvents.CANCEL]: MigrationStates.CANCELLED
      },
      actions: ['PAUSE', 'CANCEL'],
      metadata: {
        icon: 'search',
        configPage: '/config/sources',
        progress: true
      }
    },
    
    [MigrationStates.PROFILING]: {
      label: 'Profiling',
      description: 'Profiling data structures',
      color: '#6610f2',
      on: {
        [MigrationEvents.AUTO]: MigrationStates.SCHEMA_MAPPING,
        [MigrationEvents.PAUSE]: MigrationStates.PAUSED,
        [MigrationEvents.CANCEL]: MigrationStates.CANCELLED
      },
      actions: ['PAUSE', 'CANCEL'],
      metadata: {
        icon: 'bar-chart',
        configPage: '/config/profiling',
        progress: true
      }
    },
    
    [MigrationStates.SCHEMA_MAPPING]: {
      label: 'Schema Mapping',
      description: 'Mapping source to target schema',
      color: '#e83e8c',
      on: {
        [MigrationEvents.AUTO]: MigrationStates.DATA_MIGRATION,
        [MigrationEvents.PAUSE]: MigrationStates.PAUSED,
        [MigrationEvents.CANCEL]: MigrationStates.CANCELLED
      },
      actions: ['PAUSE', 'CANCEL'],
      metadata: {
        icon: 'git-merge',
        configPage: '/config/schema-mapping',
        progress: true
      }
    },
    
    [MigrationStates.DATA_MIGRATION]: {
      label: 'Data Migration',
      description: 'Migrating data to target',
      color: '#fd7e14',
      on: {
        [MigrationEvents.AUTO]: MigrationStates.VALIDATION,
        [MigrationEvents.PAUSE]: MigrationStates.PAUSED,
        [MigrationEvents.CANCEL]: MigrationStates.CANCELLED
      },
      actions: ['PAUSE', 'CANCEL'],
      metadata: {
        icon: 'database',
        configPage: null,
        progress: true
      }
    },
    
    [MigrationStates.VALIDATION]: {
      label: 'Validation',
      description: 'Validating migrated data',
      color: '#20c997',
      on: {
        [MigrationEvents.AUTO]: MigrationStates.COMPLETED,
        [MigrationEvents.ERROR]: MigrationStates.FAILED,
        [MigrationEvents.CANCEL]: MigrationStates.CANCELLED
      },
      actions: ['CANCEL'],
      metadata: {
        icon: 'check-circle',
        configPage: null,
        progress: true
      }
    },
    
    [MigrationStates.PAUSED]: {
      label: 'Paused',
      description: 'Migration paused by user',
      color: '#ffc107',
      on: {
        [MigrationEvents.RESUME]: MigrationStates.DISCOVERING,
        [MigrationEvents.CANCEL]: MigrationStates.CANCELLED
      },
      actions: ['RESUME', 'CANCEL'],
      metadata: {
        icon: 'pause',
        configPage: null
      }
    },
    
    [MigrationStates.COMPLETED]: {
      label: 'Completed',
      description: 'Migration completed successfully',
      color: '#28a745',
      on: {},
      actions: [],
      metadata: {
        icon: 'check-circle-fill',
        configPage: null,
        final: true
      }
    },
    
    [MigrationStates.FAILED]: {
      label: 'Failed',
      description: 'Migration failed with errors',
      color: '#dc3545',
      on: {
        [MigrationEvents.RETRY]: MigrationStates.INITIALIZING
      },
      actions: ['RETRY'],
      metadata: {
        icon: 'x-circle',
        configPage: null,
        error: true
      }
    },
    
    [MigrationStates.CANCELLED]: {
      label: 'Cancelled',
      description: 'Migration cancelled by user',
      color: '#6c757d',
      on: {
        [MigrationEvents.RETRY]: MigrationStates.INITIALIZING
      },
      actions: ['RETRY'],
      metadata: {
        icon: 'slash-circle',
        configPage: null
      }
    }
  }
};

/**
 * Get state configuration
 */
export function getStateConfig(stateName) {
  return plmMigrationMachine.states[stateName] || null;
}

/**
 * Check if transition is valid
 */
export function canTransition(currentState, event) {
  const stateConfig = getStateConfig(currentState);
  if (!stateConfig) return false;
  return Object.keys(stateConfig.on).includes(event);
}

/**
 * Get available actions for current state
 */
export function getAvailableActions(currentState) {
  const stateConfig = getStateConfig(currentState);
  return stateConfig ? stateConfig.actions || [] : [];
}
