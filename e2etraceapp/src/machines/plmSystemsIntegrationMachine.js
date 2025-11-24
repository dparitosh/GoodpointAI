import { createMachine, assign } from 'xstate';

/**
 * PLM Systems Integration State Machine
 * Manages Teamcenter, Windchill, ENOVIA, Aras Innovator integration
 */

export const plmSystemsIntegrationMachine = createMachine({
  id: 'plmSystemsIntegration',
  initial: 'idle',
  
  context: {
    systemType: null, // teamcenter, windchill, enovia, aras
    connectionStatus: {},
    queryResults: [],
    bomStructure: null,
    parts: [],
    documents: [],
    exportData: null,
    errors: [],
    config: {
      objectType: 'Part',
      limit: 100,
      includeRelations: false
    }
  },
  
  states: {
    idle: {
      on: {
        SELECT_SYSTEM: {
          actions: assign({
            systemType: (_, event) => event.systemType
          })
        },
        CHECK_HEALTH: 'checkingHealth',
        QUERY_OBJECTS: 'querying',
        GET_BOM: 'fetchingBOM',
        EXPORT_DATA: 'exporting'
      }
    },
    
    checkingHealth: {
      invoke: {
        id: 'checkPLMHealth',
        src: async () => {
          const response = await fetch('http://localhost:8000/api/plm/systems/health');
          if (!response.ok) throw new Error('PLM health check failed');
          return await response.json();
        },
        onDone: {
          target: 'idle',
          actions: assign({
            connectionStatus: (_, event) => event.data.systems
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
    
    querying: {
      initial: 'determining',
      
      states: {
        determining: {
          always: [
            { target: 'teamcenter', cond: (context) => context.systemType === 'teamcenter' },
            { target: 'windchill', cond: (context) => context.systemType === 'windchill' },
            { target: 'enovia', cond: (context) => context.systemType === 'enovia' },
            { target: 'aras', cond: (context) => context.systemType === 'aras' }
          ]
        },
        
        teamcenter: {
          invoke: {
            id: 'queryTeamcenter',
            src: async (context, event) => {
              const response = await fetch('http://localhost:8000/api/plm/teamcenter/query', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                  system_type: 'teamcenter',
                  object_type: context.config.objectType,
                  query_criteria: event.criteria || {},
                  properties: event.properties || ['item_id', 'object_name'],
                  limit: context.config.limit
                })
              });
              if (!response.ok) throw new Error('Teamcenter query failed');
              return await response.json();
            },
            onDone: {
              target: '#plmSystemsIntegration.idle',
              actions: assign({
                queryResults: (_, event) => event.data.objects,
                parts: (_, event) => event.data.objects
              })
            },
            onError: '#plmSystemsIntegration.error'
          }
        },
        
        windchill: {
          invoke: {
            id: 'queryWindchill',
            src: async (context, event) => {
              const response = await fetch('http://localhost:8000/api/plm/windchill/query', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                  system_type: 'windchill',
                  object_type: context.config.objectType,
                  query_criteria: event.criteria || {},
                  properties: event.properties || ['Number', 'Name', 'Version'],
                  limit: context.config.limit
                })
              });
              if (!response.ok) throw new Error('Windchill query failed');
              return await response.json();
            },
            onDone: {
              target: '#plmSystemsIntegration.idle',
              actions: assign({
                queryResults: (_, event) => event.data.objects,
                parts: (_, event) => event.data.objects
              })
            },
            onError: '#plmSystemsIntegration.error'
          }
        },
        
        enovia: {
          invoke: {
            id: 'queryEnovia',
            src: async (context, event) => {
              const response = await fetch('http://localhost:8000/api/plm/enovia/query', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                  system_type: 'enovia',
                  object_type: context.config.objectType,
                  query_criteria: event.criteria || {},
                  properties: event.properties || ['name', 'title', 'current'],
                  limit: context.config.limit
                })
              });
              if (!response.ok) throw new Error('ENOVIA query failed');
              return await response.json();
            },
            onDone: {
              target: '#plmSystemsIntegration.idle',
              actions: assign({
                queryResults: (_, event) => event.data.objects,
                parts: (_, event) => event.data.objects
              })
            },
            onError: '#plmSystemsIntegration.error'
          }
        },
        
        aras: {
          invoke: {
            id: 'queryAras',
            src: async (context, event) => {
              const response = await fetch('http://localhost:8000/api/plm/aras/query', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                  system_type: 'aras',
                  object_type: context.config.objectType,
                  query_criteria: event.criteria || {},
                  limit: context.config.limit
                })
              });
              if (!response.ok) throw new Error('Aras query failed');
              return await response.json();
            },
            onDone: {
              target: '#plmSystemsIntegration.idle',
              actions: assign({
                queryResults: (_, event) => event.data.response
              })
            },
            onError: '#plmSystemsIntegration.error'
          }
        }
      }
    },
    
    fetchingBOM: {
      invoke: {
        id: 'getBOM',
        src: async (context, event) => {
          const response = await fetch(
            `http://localhost:8000/api/plm/teamcenter/bom/${event.partId}?levels=${event.levels || -1}`
          );
          if (!response.ok) throw new Error('BOM fetch failed');
          return await response.json();
        },
        onDone: {
          target: 'idle',
          actions: assign({
            bomStructure: (_, event) => event.data.bom
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
    
    exporting: {
      invoke: {
        id: 'exportPLMData',
        src: async (context, event) => {
          const response = await fetch('http://localhost:8000/api/plm/export', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              system_type: context.systemType,
              object_type: context.config.objectType,
              object_ids: event.objectIds,
              format: event.format || 'json'
            })
          });
          if (!response.ok) throw new Error('Export failed');
          return await response.json();
        },
        onDone: {
          target: 'idle',
          actions: assign({
            exportData: (_, event) => event.data
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
            queryResults: () => [],
            bomStructure: () => null,
            errors: () => []
          })
        }
      }
    }
  }
});

export default plmSystemsIntegrationMachine;
