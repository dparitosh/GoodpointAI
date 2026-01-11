import { createMachine, assign } from 'xstate';
import { API_CONFIG } from '../config/api-config.js';
import { addErrorMessage } from './xstateHelpers.js';

/**
 * File System Integration State Machine
 * Manages file uploads, XML/JSON/CSV processing, batch operations
 */

export const fileSystemIntegrationMachine = createMachine({
  id: 'fileSystemIntegration',
  initial: 'idle',
  
  context: {
    files: [],
    directories: [],
    parsedData: null,
    validationResults: null,
    batchResults: null,
    uploadProgress: 0,
    monitoringActive: false,
    errors: [],
    config: {
      uploadDir: './data/uploads',
      maxFileSize: 100, // MB
      allowedExtensions: ['.xml', '.json', '.csv', '.xlsx']
    }
  },
  
  states: {
    idle: {
      on: {
        LIST_DIRECTORY: 'listing',
        UPLOAD_FILE: 'uploading',
        PARSE_XML: 'parsingXML',
        PARSE_JSON: 'parsingJSON',
        PARSE_CSV: 'parsingCSV',
        BATCH_OPERATION: 'batchProcessing',
        START_MONITORING: 'monitoring',
        CHECK_HEALTH: 'checkingHealth'
      }
    },
    
    checkingHealth: {
      invoke: {
        id: 'checkFileSystemHealth',
        src: async () => {
          const response = await fetch('/api/filesystem/health');
          if (!response.ok) throw new Error('File system health check failed');
          return await response.json();
        },
        onDone: 'idle',
        onError: {
          target: 'error',
          actions: assign({
            errors: (context, event) => addErrorMessage(context.errors, event.data.message)
          })
        }
      }
    },
    
    listing: {
      invoke: {
        id: 'listDirectory',
        src: async (context, event) => {
          const response = await fetch(`${API_CONFIG.API_BASE_URL}/api/filesystem/list`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              path: event.path || context.config.uploadDir,
              recursive: event.recursive || false,
              filter_extension: event.filterExtension
            })
          });
          if (!response.ok) throw new Error('Failed to list directory');
          return await response.json();
        },
        onDone: {
          target: 'idle',
          actions: assign({
            files: (_, event) => event.data.files,
            directories: (_, event) => event.data.files.filter(f => f.is_directory)
          })
        },
        onError: {
          target: 'error',
          actions: assign({
            errors: (context, event) => addErrorMessage(context.errors, event.data.message)
          })
        }
      }
    },
    
    uploading: {
      invoke: {
        id: 'uploadFile',
        src: async (context, event) => {
          const formData = new FormData();
          formData.append('file', event.file);
          if (event.destinationPath) {
            formData.append('destination_path', event.destinationPath);
          }
          
          const response = await fetch(`${API_CONFIG.API_BASE_URL}/api/filesystem/upload`, {
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
          target: 'error',
          actions: assign({
            errors: (context, event) => addErrorMessage(context.errors, event.data.message),
            uploadProgress: () => 0
          })
        }
      }
    },
    
    parsingXML: {
      initial: 'parsing',
      
      states: {
        parsing: {
          invoke: {
            id: 'parseXML',
            src: async (context, event) => {
              const response = await fetch(`${API_CONFIG.API_BASE_URL}/api/filesystem/xml/parse`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                  file_path: event.filePath,
                  namespace_map: event.namespaceMap || {}
                })
              });
              if (!response.ok) throw new Error('XML parsing failed');
              return await response.json();
            },
            onDone: {
              target: 'parsed',
              actions: assign({
                parsedData: (_, event) => event.data
              })
            },
            onError: '#fileSystemIntegration.error'
          }
        },
        
        parsed: {
          on: {
            VALIDATE: 'validating',
            DONE: '#fileSystemIntegration.idle'
          }
        },
        
        validating: {
          invoke: {
            id: 'validateXML',
            src: async (context, event) => {
              const response = await fetch(
                `${API_CONFIG.API_BASE_URL}/api/filesystem/xml/validate?file_path=${event.filePath}&schema_path=${event.schemaPath}`
              );
              if (!response.ok) throw new Error('XML validation failed');
              return await response.json();
            },
            onDone: {
              target: 'parsed',
              actions: assign({
                validationResults: (_, event) => event.data
              })
            },
            onError: '#fileSystemIntegration.error'
          }
        }
      }
    },
    
    parsingJSON: {
      invoke: {
        id: 'parseJSON',
        src: async (context, event) => {
          const response = await fetch(`${API_CONFIG.API_BASE_URL}/api/filesystem/json/parse`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              file_path: event.filePath,
              schema_validate: event.schemaValidate || false,
              json_schema: event.jsonSchema
            })
          });
          if (!response.ok) throw new Error('JSON parsing failed');
          return await response.json();
        },
        onDone: {
          target: 'idle',
          actions: assign({
            parsedData: (_, event) => event.data,
            validationResults: (_, event) => event.data.validation
          })
        },
        onError: {
          target: 'error',
          actions: assign({
            errors: (context, event) => addErrorMessage(context.errors, event.data.message)
          })
        }
      }
    },
    
    parsingCSV: {
      invoke: {
        id: 'parseCSV',
        src: async (context, event) => {
          const response = await fetch(`${API_CONFIG.API_BASE_URL}/api/filesystem/csv/parse`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              file_path: event.filePath,
              delimiter: event.delimiter || ',',
              encoding: event.encoding || 'utf-8',
              header_row: event.headerRow || 0
            })
          });
          if (!response.ok) throw new Error('CSV parsing failed');
          return await response.json();
        },
        onDone: {
          target: 'idle',
          actions: assign({
            parsedData: (_, event) => event.data
          })
        },
        onError: {
          target: 'error',
          actions: assign({
            errors: (context, event) => addErrorMessage(context.errors, event.data.message)
          })
        }
      }
    },
    
    batchProcessing: {
      invoke: {
        id: 'batchOperation',
        src: async (context, event) => {
          const response = await fetch(`${API_CONFIG.API_BASE_URL}/api/filesystem/batch/operation`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              operation: event.operation, // copy, move, delete
              source_pattern: event.sourcePattern,
              destination: event.destination
            })
          });
          if (!response.ok) throw new Error('Batch operation failed');
          return await response.json();
        },
        onDone: {
          target: 'idle',
          actions: assign({
            batchResults: (_, event) => event.data.results
          })
        },
        onError: {
          target: 'error',
          actions: assign({
            errors: (context, event) => addErrorMessage(context.errors, event.data.message)
          })
        }
      }
    },
    
    monitoring: {
      invoke: {
        id: 'startFolderMonitoring',
        src: async (context, event) => {
          const response = await fetch(`${API_CONFIG.API_BASE_URL}/api/filesystem/watch/start`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              watch_path: event.watchPath,
              file_patterns: event.filePatterns || ['*.*'],
              action: event.action || 'process',
              destination_path: event.destinationPath
            })
          });
          if (!response.ok) throw new Error('Failed to start monitoring');
          return await response.json();
        },
        onDone: {
          target: 'idle',
          actions: assign({
            monitoringActive: () => true
          })
        },
        onError: {
          target: 'error',
          actions: assign({
            errors: (context, event) => addErrorMessage(context.errors, event.data.message)
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
            parsedData: () => null,
            validationResults: () => null,
            uploadProgress: () => 0
          })
        }
      }
    }
  }
});

export default fileSystemIntegrationMachine;
