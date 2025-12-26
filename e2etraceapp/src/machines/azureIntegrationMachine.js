import { createMachine, assign } from 'xstate';
import { API_CONFIG } from '../config/api-config.js';

/**
 * Azure Cloud Integration State Machine
 * Manages Azure Blob Storage, Cosmos DB, Service Bus, Event Hub operations
 */

export const azureIntegrationMachine = createMachine({
  id: 'azureIntegration',
  initial: 'idle',
  
  context: {
    connectionStatus: 'disconnected',
    selectedService: null,
    uploadProgress: 0,
    files: [],
    documents: [],
    messages: [],
    errors: [],
    config: {
      containerName: 'plm-data',
      databaseName: 'graphtrace',
      queueName: 'workflow-queue'
    }
  },
  
  states: {
    idle: {
      on: {
        CONNECT: 'connecting',
        SELECT_SERVICE: {
          actions: assign({
            selectedService: (_, event) => event.service
          })
        }
      }
    },
    
    connecting: {
      invoke: {
        id: 'checkAzureHealth',
        src: async () => {
          const response = await fetch('/api/azure/health');
          if (!response.ok) throw new Error('Azure connection failed');
          return await response.json();
        },
        onDone: {
          target: 'connected',
          actions: assign({
            connectionStatus: () => 'connected'
          })
        },
        onError: {
          target: 'error',
          actions: assign({
            connectionStatus: () => 'error',
            errors: (context, event) => [...context.errors, event.data.message]
          })
        }
      }
    },
    
    connected: {
      initial: 'idle',
      
      on: {
        DISCONNECT: 'idle'
      },
      
      states: {
        idle: {
          on: {
            UPLOAD_BLOB: 'uploadingBlob',
            LIST_BLOBS: 'listingBlobs',
            QUERY_COSMOS: 'queryingCosmos',
            SEND_MESSAGE: 'sendingMessage',
            SEND_EVENT: 'sendingEvent'
          }
        },
        
        uploadingBlob: {
          invoke: {
            id: 'uploadBlob',
            src: async (context, event) => {
              const formData = new FormData();
              formData.append('file', event.file);
              formData.append('container_name', context.config.containerName);
              
              const response = await fetch(`${API_CONFIG.API_BASE_URL}/api/azure/blob/upload`, {
                method: 'POST',
                body: formData
              });
              
              if (!response.ok) throw new Error('Upload failed');
              return await response.json();
            },
            onDone: {
              target: 'idle',
              actions: assign({
                files: (context, event) => [...context.files, event.data],
                uploadProgress: () => 100
              })
            },
            onError: {
              target: 'idle',
              actions: assign({
                errors: (context, event) => [...context.errors, event.data.message],
                uploadProgress: () => 0
              })
            }
          }
        },
        
        listingBlobs: {
          invoke: {
            id: 'listBlobs',
            src: async (context) => {
              const response = await fetch(
                `${API_CONFIG.API_BASE_URL}/api/azure/blob/list/${context.config.containerName}`
              );
              if (!response.ok) throw new Error('Failed to list blobs');
              return await response.json();
            },
            onDone: {
              target: 'idle',
              actions: assign({
                files: (_, event) => event.data.blobs
              })
            },
            onError: {
              target: 'idle',
              actions: assign({
                errors: (context, event) => [...context.errors, event.data.message]
              })
            }
          }
        },
        
        queryingCosmos: {
          invoke: {
            id: 'queryCosmos',
            src: async (context, event) => {
              const response = await fetch(
                `${API_CONFIG.API_BASE_URL}/api/azure/cosmos/documents/${event.containerId}`,
                {
                  method: 'GET',
                  headers: { 'Content-Type': 'application/json' }
                }
              );
              if (!response.ok) throw new Error('Cosmos query failed');
              return await response.json();
            },
            onDone: {
              target: 'idle',
              actions: assign({
                documents: (_, event) => event.data.documents
              })
            },
            onError: {
              target: 'idle',
              actions: assign({
                errors: (context, event) => [...context.errors, event.data.message]
              })
            }
          }
        },
        
        sendingMessage: {
          invoke: {
            id: 'sendServiceBusMessage',
            src: async (context, event) => {
              const response = await fetch(`${API_CONFIG.API_BASE_URL}/api/azure/servicebus/send`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                  queue_name: context.config.queueName,
                  message_body: event.message,
                  properties: event.properties || {}
                })
              });
              if (!response.ok) throw new Error('Failed to send message');
              return await response.json();
            },
            onDone: {
              target: 'idle',
              actions: assign({
                messages: (context, event) => [...context.messages, event.data]
              })
            },
            onError: {
              target: 'idle',
              actions: assign({
                errors: (context, event) => [...context.errors, event.data.message]
              })
            }
          }
        },
        
        sendingEvent: {
          invoke: {
            id: 'sendEventHubEvent',
            src: async (context, event) => {
              const response = await fetch(`${API_CONFIG.API_BASE_URL}/api/azure/eventhub/send`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                  event_hub_name: event.eventHubName || 'plm-events',
                  events: event.events,
                  partition_key: event.partitionKey
                })
              });
              if (!response.ok) throw new Error('Failed to send events');
              return await response.json();
            },
            onDone: 'idle',
            onError: {
              target: 'idle',
              actions: assign({
                errors: (context, event) => [...context.errors, event.data.message]
              })
            }
          }
        }
      }
    },
    
    error: {
      on: {
        RETRY: 'connecting',
        RESET: {
          target: 'idle',
          actions: assign({
            connectionStatus: () => 'disconnected',
            errors: () => []
          })
        }
      }
    }
  }
});

export default azureIntegrationMachine;
