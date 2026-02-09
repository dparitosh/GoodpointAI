/**
 * Connection Service - Manages Neo4j connections and graph data fetches
 * Coordinates active session, listeners, and backend API calls
 */
import API_CONFIG, { getFullUrl } from '../config/api-config';

class ConnectionService {
  constructor() {
    this.listeners = new Map();
    this.connectionInfo = {
      config: {
        uri: '',
        user: '',
        auto_connect: false
      },
      status: 'disconnected'
    };
    this.graphData = null;
  }

  // Event handling
  addEventListener(event, callback) {
    if (!this.listeners.has(event)) {
      this.listeners.set(event, []);
    }
    this.listeners.get(event).push(callback);
  }

  removeEventListener(event, callback) {
    if (this.listeners.has(event)) {
      const callbacks = this.listeners.get(event);
      const index = callbacks.indexOf(callback);
      if (index > -1) {
        callbacks.splice(index, 1);
      }
    }
  }

  emit(event, data) {
    if (this.listeners.has(event)) {
      this.listeners.get(event).forEach(callback => callback(data));
    }
  }

  // Connection management
  async connect(uri, user, password) {
    try {
      this.emit('connecting', { uri, user });
      
      // Validate connection via backend API
      const response = await fetch(getFullUrl(API_CONFIG.ENDPOINTS.GRAPH_VALIDATE), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ uri, user, password })
      });
      
      if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: 'Connection failed' }));
        throw new Error(error.detail || 'Connection validation failed');
      }
      
      const result = await response.json();
      
      this.connectionInfo = {
        config: { uri, user, auto_connect: false },
        status: 'connected',
        database: result.database || 'neo4j',
        version: result.version || 'unknown'
      };
      
      this.emit('connected', { uri, user, ...result });
      return true;
    } catch (error) {
      this.connectionInfo.status = 'disconnected';
      this.emit('connection-error', { error: error.message });
      return false;
    }
  }

  disconnect() {
    this.connectionInfo.status = 'disconnected';
    this.emit('disconnected', {});
  }

  /**
   * Connect using backend's stored Neo4j credentials
   * Uses the configuration saved in Data Sources settings
   */
  async connectViaBackend() {
    try {
      this.emit('connecting', {});
      
      // Get Neo4j config which also tests the connection
      const response = await fetch(getFullUrl(API_CONFIG.ENDPOINTS.NEO4J_CONFIG));
      
      if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: 'Failed to get Neo4j config' }));
        throw new Error(error.detail || 'Failed to retrieve Neo4j configuration');
      }
      
      const result = await response.json();
      
      if (result.connection_status !== 'connected') {
        // Use detailed error message from backend if available
        const errorMessage = result.error_message || this._getConnectionErrorMessage(result.error_type);
        throw new Error(errorMessage);
      }
      
      this.connectionInfo = {
        config: { uri: result.uri || '', user: result.username || '', auto_connect: true },
        status: 'connected',
        database: result.database || 'neo4j'
      };
      
      this.emit('connected', result);
      return true;
    } catch (error) {
      this.connectionInfo.status = 'disconnected';
      this.emit('connection-error', { error: error.message });
      throw error;
    }
  }

  getConnectionInfo() {
    return this.connectionInfo;
  }

  /**
   * Get user-friendly error message based on error type
   */
  _getConnectionErrorMessage(errorType) {
    const errorMessages = {
      'no_config': 'Neo4j connection not configured. Please set up Neo4j in Data Configuration.',
      'service_unavailable': 'Neo4j service is not running. Please start Neo4j in Neo4j Desktop or ensure the service is running.',
      'auth_failed': 'Neo4j authentication failed. Please check your username and password in Data Configuration.',
      'unknown': 'Neo4j connection failed. Please check your configuration.'
    };
    return errorMessages[errorType] || 'Neo4j connection failed. Please check your configuration in Data Sources.';
  }

  // Graph data operations
  async loadGraphData(_filters) {
    try {
      // Backend exposes GET /api/graph for default graph payload.
      // Filters are currently ignored (kept for API compatibility).
      const response = await fetch(getFullUrl(API_CONFIG.ENDPOINTS.GRAPH));
      
      if (!response.ok) {
        throw new Error('Failed to load graph data');
      }
      
      const data = await response.json();
      this.graphData = {
        ...data,
        lastUpdated: new Date().toISOString()
      };
      
      this.emit('graph-data-loaded', this.graphData);
      return this.graphData;
    } catch (error) {
      this.emit('graph-data-error', { error: error.message });
      throw error;
    }
  }

  async executeQuery(query) {
    // Execute Cypher query via backend
    const response = await fetch(getFullUrl(API_CONFIG.ENDPOINTS.GRAPH_QUERY), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query })
    });

    if (!response.ok) {
      throw new Error('Query execution failed');
    }

    return await response.json();
  }
}

// Singleton instance
const connectionService = new ConnectionService();
export default connectionService;
