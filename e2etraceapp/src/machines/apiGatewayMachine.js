import { createMachine, assign } from 'xstate';
import { API_CONFIG } from '../config/api-config.js';

/**
 * API Gateway State Machine
 * Manages REST API routing, rate limiting, and request/response transformations
 */

export const apiGatewayMachine = createMachine({
  id: 'apiGateway',
  initial: 'idle',
  
  context: {
    routes: [],
    rateLimits: {},
    requests: [],
    responses: [],
    transformations: [],
    errors: [],
    config: {
      baseUrl: API_CONFIG.API_BASE_URL,
      timeout: 30,
      retries: 3,
      rateLimitEnabled: true
    }
  },
  
  states: {
    idle: {
      on: {
        CHECK_HEALTH: 'checkingHealth',
        LIST_ROUTES: 'listingRoutes',
        REGISTER_ROUTE: 'registeringRoute',
        PROXY_REQUEST: 'proxying',
        GET_RATE_LIMITS: 'fetchingRateLimits',
        SET_RATE_LIMIT: 'settingRateLimit',
        ADD_TRANSFORMATION: 'addingTransformation',
        GET_METRICS: 'fetchingMetrics'
      }
    },
    
    checkingHealth: {
      invoke: {
        id: 'checkGatewayHealth',
        src: async () => {
          const response = await fetch('/api/gateway/health');
          if (!response.ok) throw new Error('API Gateway health check failed');
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
    
    listingRoutes: {
      invoke: {
        id: 'listRoutes',
        src: async () => {
          const response = await fetch(`${API_CONFIG.API_BASE_URL}/api/gateway/routes`);
          if (!response.ok) throw new Error('Failed to list routes');
          return await response.json();
        },
        onDone: {
          target: 'idle',
          actions: assign({
            routes: (_, event) => event.data.routes || []
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
    
    registeringRoute: {
      invoke: {
        id: 'registerRoute',
        src: async (context, event) => {
          const response = await fetch(`${API_CONFIG.API_BASE_URL}/api/gateway/routes`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              path: event.path,
              method: event.method,
              target_url: event.targetUrl,
              rate_limit: event.rateLimit,
              auth_required: event.authRequired || false,
              transformation: event.transformation
            })
          });
          if (!response.ok) throw new Error('Failed to register route');
          return await response.json();
        },
        onDone: {
          target: 'idle',
          actions: assign({
            routes: (context, event) => [...context.routes, event.data]
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
    
    proxying: {
      invoke: {
        id: 'proxyRequest',
        src: async (context, event) => {
          const response = await fetch(`${API_CONFIG.API_BASE_URL}/api/gateway/proxy`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              method: event.method || 'GET',
              path: event.path,
              headers: event.headers || {},
              body: event.body,
              query_params: event.queryParams || {}
            })
          });
          if (!response.ok) throw new Error('Proxy request failed');
          return await response.json();
        },
        onDone: {
          target: 'idle',
          actions: assign({
            requests: (context, event) => [...context.requests, event.data.request],
            responses: (context, event) => [...context.responses, event.data.response]
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
    
    fetchingRateLimits: {
      invoke: {
        id: 'getRateLimits',
        src: async () => {
          const response = await fetch(`${API_CONFIG.API_BASE_URL}/api/gateway/rate-limits`);
          if (!response.ok) throw new Error('Failed to fetch rate limits');
          return await response.json();
        },
        onDone: {
          target: 'idle',
          actions: assign({
            rateLimits: (_, event) => event.data.rate_limits || {}
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
    
    settingRateLimit: {
      invoke: {
        id: 'setRateLimit',
        src: async (context, event) => {
          const response = await fetch(`${API_CONFIG.API_BASE_URL}/api/gateway/rate-limit`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              endpoint: event.endpoint,
              requests_per_minute: event.requestsPerMinute,
              burst_size: event.burstSize
            })
          });
          if (!response.ok) throw new Error('Failed to set rate limit');
          return await response.json();
        },
        onDone: {
          target: 'idle',
          actions: assign({
            rateLimits: (context, event) => ({
              ...context.rateLimits,
              [event.data.endpoint]: event.data.limit
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
    
    addingTransformation: {
      invoke: {
        id: 'addTransformation',
        src: async (context, event) => {
          const response = await fetch(`${API_CONFIG.API_BASE_URL}/api/gateway/transformation`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              route_pattern: event.routePattern,
              type: event.type, // request, response
              transformation: event.transformation
            })
          });
          if (!response.ok) throw new Error('Failed to add transformation');
          return await response.json();
        },
        onDone: {
          target: 'idle',
          actions: assign({
            transformations: (context, event) => [...context.transformations, event.data]
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
    
    fetchingMetrics: {
      invoke: {
        id: 'getMetrics',
        src: async (context, event) => {
          const timeRange = event.timeRange || '1h';
          const response = await fetch(`${API_CONFIG.API_BASE_URL}/api/gateway/metrics?time_range=${timeRange}`);
          if (!response.ok) throw new Error('Failed to fetch metrics');
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
    
    error: {
      on: {
        RETRY: 'idle',
        RESET: {
          target: 'idle',
          actions: assign({
            errors: () => [],
            requests: () => [],
            responses: () => []
          })
        }
      }
    }
  }
});

export default apiGatewayMachine;
