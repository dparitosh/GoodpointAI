import { createMachine, assign } from 'xstate';
import { API_CONFIG } from '../config/api-config.js';
import { addErrorMessage } from './xstateHelpers.js';

/**
 * AWS Integration State Machine
 * Manages S3, DynamoDB, SQS, Lambda interactions
 */

export const awsIntegrationMachine = createMachine({
  id: 'awsIntegration',
  initial: 'idle',
  
  context: {
    connectionStatus: {
      s3: false,
      dynamodb: false,
      sqs: false,
      lambda: false
    },
    s3Objects: [],
    dynamoItems: [],
    sqsMessages: [],
    lambdaResults: [],
    uploadProgress: 0,
    errors: [],
    config: {
      region: 'us-east-1',
      bucket: '',
      tableName: '',
      queueUrl: '',
      functionName: ''
    }
  },
  
  states: {
    idle: {
      on: {
        CONNECT: 'connecting',
        CHECK_HEALTH: 'checkingHealth',
        S3_UPLOAD: 'uploadingToS3',
        S3_LIST: 'listingS3Objects',
        S3_DOWNLOAD: 'downloadingFromS3',
        DYNAMO_PUT: 'puttingToDynamo',
        DYNAMO_QUERY: 'queryingDynamo',
        SQS_SEND: 'sendingToSQS',
        SQS_RECEIVE: 'receivingFromSQS',
        LAMBDA_INVOKE: 'invokingLambda'
      }
    },
    
    checkingHealth: {
      invoke: {
        id: 'checkAWSHealth',
        src: async () => {
          const response = await fetch('/api/aws/health');
          if (!response.ok) throw new Error('AWS health check failed');
          return await response.json();
        },
        onDone: {
          target: 'idle',
          actions: assign({
            connectionStatus: (_, event) => event.data.services || {}
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
    
    connecting: {
      invoke: {
        id: 'connectToAWS',
        src: async (context) => {
          const response = await fetch(`${API_CONFIG.API_BASE_URL}/api/aws/connect`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              region: context.config.region
            })
          });
          if (!response.ok) throw new Error('AWS connection failed');
          return await response.json();
        },
        onDone: {
          target: 'connected',
          actions: assign({
            connectionStatus: (_, event) => event.data.services
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
    
    connected: {
      on: {
        DISCONNECT: 'idle',
        S3_UPLOAD: 'uploadingToS3',
        S3_LIST: 'listingS3Objects',
        S3_DOWNLOAD: 'downloadingFromS3',
        DYNAMO_PUT: 'puttingToDynamo',
        DYNAMO_QUERY: 'queryingDynamo',
        SQS_SEND: 'sendingToSQS',
        SQS_RECEIVE: 'receivingFromSQS',
        LAMBDA_INVOKE: 'invokingLambda'
      }
    },
    
    uploadingToS3: {
      invoke: {
        id: 'uploadToS3',
        src: async (context, event) => {
          const formData = new FormData();
          formData.append('file', event.file);
          formData.append('bucket_name', event.bucket || context.config.bucket);
          if (event.key) {
            formData.append('key', event.key);
          }
          
          const response = await fetch(`${API_CONFIG.API_BASE_URL}/api/aws/s3/upload`, {
            method: 'POST',
            body: formData
          });
          
          if (!response.ok) throw new Error('S3 upload failed');
          return await response.json();
        },
        onDone: {
          target: 'idle',
          actions: assign({
            s3Objects: (context, event) => [...context.s3Objects, event.data],
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
    
    listingS3Objects: {
      invoke: {
        id: 'listS3Objects',
        src: async (context, event) => {
          const bucket = event.bucket || context.config.bucket;
          const prefix = event.prefix || '';
          const response = await fetch(
            `${API_CONFIG.API_BASE_URL}/api/aws/s3/list/${bucket}?prefix=${prefix}`
          );
          if (!response.ok) throw new Error('Failed to list S3 objects');
          return await response.json();
        },
        onDone: {
          target: 'idle',
          actions: assign({
            s3Objects: (_, event) => event.data.objects || []
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
    
    downloadingFromS3: {
      invoke: {
        id: 'downloadFromS3',
        src: async (context, event) => {
          const response = await fetch(`${API_CONFIG.API_BASE_URL}/api/aws/s3/download`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              bucket_name: event.bucket || context.config.bucket,
              key: event.key
            })
          });
          if (!response.ok) throw new Error('S3 download failed');
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
    
    puttingToDynamo: {
      invoke: {
        id: 'putToDynamo',
        src: async (context, event) => {
          const response = await fetch(`${API_CONFIG.API_BASE_URL}/api/aws/dynamodb/put`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              table_name: event.tableName || context.config.tableName,
              item: event.item
            })
          });
          if (!response.ok) throw new Error('DynamoDB put failed');
          return await response.json();
        },
        onDone: {
          target: 'idle',
          actions: assign({
            dynamoItems: (context, event) => [...context.dynamoItems, event.data]
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
    
    queryingDynamo: {
      invoke: {
        id: 'queryDynamo',
        src: async (context, event) => {
          const response = await fetch(`${API_CONFIG.API_BASE_URL}/api/aws/dynamodb/query`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              table_name: event.tableName || context.config.tableName,
              key_condition_expression: event.keyCondition,
              expression_attribute_values: event.attributeValues
            })
          });
          if (!response.ok) throw new Error('DynamoDB query failed');
          return await response.json();
        },
        onDone: {
          target: 'idle',
          actions: assign({
            dynamoItems: (_, event) => event.data.items || []
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
    
    sendingToSQS: {
      invoke: {
        id: 'sendToSQS',
        src: async (context, event) => {
          const response = await fetch(`${API_CONFIG.API_BASE_URL}/api/aws/sqs/send`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              queue_url: event.queueUrl || context.config.queueUrl,
              message_body: event.message,
              message_attributes: event.attributes || {}
            })
          });
          if (!response.ok) throw new Error('SQS send failed');
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
    
    receivingFromSQS: {
      invoke: {
        id: 'receiveFromSQS',
        src: async (context, event) => {
          const queueUrl = event.queueUrl || context.config.queueUrl;
          const maxMessages = event.maxMessages || 10;
          const response = await fetch(
            `${API_CONFIG.API_BASE_URL}/api/aws/sqs/receive/${encodeURIComponent(queueUrl)}?max_messages=${maxMessages}`
          );
          if (!response.ok) throw new Error('SQS receive failed');
          return await response.json();
        },
        onDone: {
          target: 'idle',
          actions: assign({
            sqsMessages: (_, event) => event.data.messages || []
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
    
    invokingLambda: {
      invoke: {
        id: 'invokeLambda',
        src: async (context, event) => {
          const response = await fetch(`${API_CONFIG.API_BASE_URL}/api/aws/lambda/invoke`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              function_name: event.functionName || context.config.functionName,
              payload: event.payload || {},
              invocation_type: event.invocationType || 'RequestResponse'
            })
          });
          if (!response.ok) throw new Error('Lambda invocation failed');
          return await response.json();
        },
        onDone: {
          target: 'idle',
          actions: assign({
            lambdaResults: (context, event) => [...context.lambdaResults, event.data]
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
            uploadProgress: () => 0,
            connectionStatus: () => ({
              s3: false,
              dynamodb: false,
              sqs: false,
              lambda: false
            })
          })
        }
      }
    }
  }
});

export default awsIntegrationMachine;
