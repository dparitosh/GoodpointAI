import { createMachine, assign } from 'xstate';
import { API_CONFIG } from '../config/api-config.js';

/**
 * OData Integration State Machine
 * Manages OData service queries and operations
 */

export const odataIntegrationMachine = createMachine({
  id: 'odataIntegration',
  initial: 'idle',
  
  context: {
    connectionStatus: false,
    metadata: null,
    entities: [],
    queryResults: [],
    errors: [],
    config: {
      serviceUrl: '',
      entitySet: '',
      authType: 'none',
      credentials: {}
    }
  },
  
  states: {
    idle: {
      on: {
        CONNECT: 'connecting',
        CHECK_HEALTH: 'checkingHealth',
        GET_METADATA: 'fetchingMetadata',
        QUERY_ENTITIES: 'queryingEntities',
        GET_ENTITY: 'fetchingEntity',
        CREATE_ENTITY: 'creatingEntity',
        UPDATE_ENTITY: 'updatingEntity',
        DELETE_ENTITY: 'deletingEntity',
        BATCH_OPERATION: 'executingBatch'
      }
    },
    
    checkingHealth: {
      invoke: {
        id: 'checkODataHealth',
        src: async () => {
          const response = await fetch('/api/odata/health');
          if (!response.ok) throw new Error('OData health check failed');
          return await response.json();
        },
        onDone: {
          target: 'idle',
          actions: assign({
            connectionStatus: (_, event) => event.data.status === 'healthy'
          })
        },
        onError: {
          target: 'error',
          actions: assign({
            errors: (context, event) => [...context.errors, event.data.message]
          })
        }
      }
    },
    
    connecting: {
      invoke: {
        id: 'connectToOData',
        src: async (context, event) => {
          const response = await fetch(`${API_CONFIG.API_BASE_URL}/api/odata/connect`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              service_url: event.serviceUrl || context.config.serviceUrl,
              auth_type: event.authType || context.config.authType,
              credentials: event.credentials || context.config.credentials
            })
          });
          if (!response.ok) throw new Error('OData connection failed');
          return await response.json();
        },
        onDone: {
          target: 'connected',
          actions: assign({
            connectionStatus: () => true,
            config: (context, event) => ({
              ...context.config,
              serviceUrl: event.data.service_url
            })
          })
        },
        onError: {
          target: 'error',
          actions: assign({
            errors: (context, event) => [...context.errors, event.data.message]
          })
        }
      }
    },
    
    connected: {
      on: {
        DISCONNECT: 'idle',
        GET_METADATA: 'fetchingMetadata',
        QUERY_ENTITIES: 'queryingEntities',
        GET_ENTITY: 'fetchingEntity',
        CREATE_ENTITY: 'creatingEntity',
        UPDATE_ENTITY: 'updatingEntity',
        DELETE_ENTITY: 'deletingEntity',
        BATCH_OPERATION: 'executingBatch'
      }
    },
    
    fetchingMetadata: {
      invoke: {
        id: 'fetchMetadata',
        src: async (context) => {
          const response = await fetch(
            `${API_CONFIG.API_BASE_URL}/api/odata/metadata?service_url=${encodeURIComponent(context.config.serviceUrl)}`
          );
          if (!response.ok) throw new Error('Failed to fetch OData metadata');
          return await response.json();
        },
        onDone: {
          target: 'idle',
          actions: assign({
            metadata: (_, event) => event.data.metadata,
            entities: (_, event) => event.data.entity_sets || []
          })
        },
        onError: {
          target: 'error',
          actions: assign({
            errors: (context, event) => [...context.errors, event.data.message]
          })
        }
      }
    },
    
    queryingEntities: {
      invoke: {
        id: 'queryEntities',
        src: async (context, event) => {
          const response = await fetch(`${API_CONFIG.API_BASE_URL}/api/odata/query`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              service_url: context.config.serviceUrl,
              entity_set: event.entitySet || context.config.entitySet,
              filter: event.filter,
              select: event.select,
              expand: event.expand,
              orderby: event.orderby,
              top: event.top,
              skip: event.skip
            })
          });
          if (!response.ok) throw new Error('OData query failed');
          return await response.json();
        },
        onDone: {
          target: 'idle',
          actions: assign({
            queryResults: (_, event) => event.data.results || []
          })
        },
        onError: {
          target: 'error',
          actions: assign({
            errors: (context, event) => [...context.errors, event.data.message]
          })
        }
      }
    },
    
    fetchingEntity: {
      invoke: {
        id: 'fetchEntity',
        src: async (context, event) => {
          const entitySet = event.entitySet || context.config.entitySet;
          const entityKey = event.entityKey;
          const response = await fetch(
            `${API_CONFIG.API_BASE_URL}/api/odata/entity/${entitySet}/${entityKey}?service_url=${encodeURIComponent(context.config.serviceUrl)}`
          );
          if (!response.ok) throw new Error('Failed to fetch entity');
          return await response.json();
        },
        onDone: {
          target: 'idle',
          actions: assign({
            queryResults: (context, event) => [event.data]
          })
        },
        onError: {
          target: 'error',
          actions: assign({
            errors: (context, event) => [...context.errors, event.data.message]
          })
        }
      }
    },
    
    creatingEntity: {
      invoke: {
        id: 'createEntity',
        src: async (context, event) => {
          const response = await fetch(`${API_CONFIG.API_BASE_URL}/api/odata/create`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              service_url: context.config.serviceUrl,
              entity_set: event.entitySet || context.config.entitySet,
              data: event.data
            })
          });
          if (!response.ok) throw new Error('Failed to create entity');
          return await response.json();
        },
        onDone: {
          target: 'idle',
          actions: assign({
            queryResults: (context, event) => [...context.queryResults, event.data]
          })
        },
        onError: {
          target: 'error',
          actions: assign({
            errors: (context, event) => [...context.errors, event.data.message]
          })
        }
      }
    },
    
    updatingEntity: {
      invoke: {
        id: 'updateEntity',
        src: async (context, event) => {
          const response = await fetch(`${API_CONFIG.API_BASE_URL}/api/odata/update`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              service_url: context.config.serviceUrl,
              entity_set: event.entitySet || context.config.entitySet,
              entity_key: event.entityKey,
              data: event.data
            })
          });
          if (!response.ok) throw new Error('Failed to update entity');
          return await response.json();
        },
        onDone: 'idle',
        onError: {
          target: 'error',
          actions: assign({
            errors: (context, event) => [...context.errors, event.data.message]
          })
        }
      }
    },
    
    deletingEntity: {
      invoke: {
        id: 'deleteEntity',
        src: async (context, event) => {
          const response = await fetch(`${API_CONFIG.API_BASE_URL}/api/odata/delete`, {
            method: 'DELETE',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              service_url: context.config.serviceUrl,
              entity_set: event.entitySet || context.config.entitySet,
              entity_key: event.entityKey
            })
          });
          if (!response.ok) throw new Error('Failed to delete entity');
          return await response.json();
        },
        onDone: 'idle',
        onError: {
          target: 'error',
          actions: assign({
            errors: (context, event) => [...context.errors, event.data.message]
          })
        }
      }
    },
    
    executingBatch: {
      invoke: {
        id: 'executeBatch',
        src: async (context, event) => {
          const response = await fetch(`${API_CONFIG.API_BASE_URL}/api/odata/batch`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              service_url: context.config.serviceUrl,
              operations: event.operations
            })
          });
          if (!response.ok) throw new Error('Batch operation failed');
          return await response.json();
        },
        onDone: {
          target: 'idle',
          actions: assign({
            queryResults: (_, event) => event.data.results || []
          })
        },
        onError: {
          target: 'error',
          actions: assign({
            errors: (context, event) => [...context.errors, event.data.message]
          })
        }
      }
    },
    
    error: {
      on: {
        RETRY: 'idle',
        RESET: {
          target: 'idle',
          actions: assign({
            errors: () => [],
            connectionStatus: () => false,
            queryResults: () => []
          })
        }
      }
    }
  }
});

export default odataIntegrationMachine;
