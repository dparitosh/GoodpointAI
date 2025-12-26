import { createMachine, assign } from 'xstate';
import { API_CONFIG } from '../config/api-config.js';

/**
 * LLM Integration State Machine
 * Manages interactions with OpenAI, Claude, Azure OpenAI, and Ollama
 */

export const llmIntegrationMachine = createMachine({
  id: 'llmIntegration',
  initial: 'idle',
  
  context: {
    provider: 'openai', // openai, anthropic, azure-openai, ollama
    model: null,
    conversation: [],
    currentResponse: null,
    streaming: false,
    embeddings: [],
    availableModels: [],
    errors: [],
    config: {
      temperature: 0.7,
      maxTokens: 1000
    }
  },
  
  states: {
    idle: {
      on: {
        SET_PROVIDER: {
          actions: assign({
            provider: (_, event) => event.provider,
            model: (_, event) => event.model || null
          })
        },
        CHECK_HEALTH: 'checkingHealth',
        SEND_MESSAGE: 'sending',
        GET_EMBEDDING: 'embedding',
        LIST_MODELS: 'listingModels'
      }
    },
    
    checkingHealth: {
      invoke: {
        id: 'checkLLMHealth',
        src: async () => {
          const response = await fetch('/api/llm/health');
          if (!response.ok) throw new Error('LLM health check failed');
          return await response.json();
        },
        onDone: {
          target: 'idle',
          actions: assign({
            availableModels: (_, event) => event.data.models || {}
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
    
    sending: {
      invoke: {
        id: 'sendChatMessage',
        src: async (context, event) => {
          const endpoint = context.provider === 'openai' 
            ? `${API_CONFIG.API_BASE_URL}/api/llm/openai/chat`
            : context.provider === 'anthropic'
            ? `${API_CONFIG.API_BASE_URL}/api/llm/anthropic/chat`
            : context.provider === 'ollama'
            ? `${API_CONFIG.API_BASE_URL}/api/llm/ollama/chat`
            : `${API_CONFIG.API_BASE_URL}/api/llm/chat?provider=${encodeURIComponent(context.provider)}`;
          
          const messages = [
            ...context.conversation,
            { role: 'user', content: event.message }
          ];
          
          const response = await fetch(endpoint, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              messages,
              model: context.model,
              temperature: context.config.temperature,
              max_tokens: context.config.maxTokens
            })
          });
          
          if (!response.ok) throw new Error('LLM request failed');
          return await response.json();
        },
        onDone: {
          target: 'idle',
          actions: assign({
            conversation: (context, event) => [
              ...context.conversation,
              { role: 'user', content: event.data.message },
              { role: 'assistant', content: event.data.response }
            ],
            currentResponse: (_, event) => event.data
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
    
    embedding: {
      invoke: {
        id: 'getEmbedding',
        src: async (context, event) => {
          const endpoint = context.provider === 'openai'
            ? `${API_CONFIG.API_BASE_URL}/api/llm/openai/embedding`
            : `${API_CONFIG.API_BASE_URL}/api/llm/ollama/embedding`;
          
          const response = await fetch(endpoint, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              text: event.text,
              model: context.model
            })
          });
          
          if (!response.ok) throw new Error('Embedding request failed');
          return await response.json();
        },
        onDone: {
          target: 'idle',
          actions: assign({
            embeddings: (context, event) => [
              ...context.embeddings,
              { text: event.data.text, embedding: event.data.embedding }
            ]
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
    
    listingModels: {
      invoke: {
        id: 'listOllamaModels',
        src: async () => {
          const response = await fetch(`${API_CONFIG.API_BASE_URL}/api/llm/ollama/models`);
          if (!response.ok) throw new Error('Failed to list models');
          return await response.json();
        },
        onDone: {
          target: 'idle',
          actions: assign({
            availableModels: (_, event) => event.data.models
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
            conversation: () => [],
            errors: () => [],
            currentResponse: () => null
          })
        }
      }
    }
  }
});

export default llmIntegrationMachine;
