/**
 * Connection Service - Manages Neo4j connections and graph data fetches
 * Coordinates active session, listeners, and backend API calls
 */

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
      
      // TODO: Establish actual Neo4j connection via backend API
      // For now, connection is handled by backend
      this.connectionInfo = {
        config: { uri, user, auto_connect: false },
        status: 'connected'
      };
      
      this.emit('connected', { uri, user });
      return true;
    } catch (error) {
      this.emit('connection-error', { error: error.message });
      return false;
    }
  }

  disconnect() {
    this.connectionInfo.status = 'disconnected';
    this.emit('disconnected', {});
  }

  getConnectionInfo() {
    return this.connectionInfo;
  }

  // Graph data operations
  async loadGraphData(filters) {
    try {
      // Backend exposes GET /api/graph for default graph payload.
      // Filters are currently ignored (kept for API compatibility).
      const response = await fetch('/api/graph');
      
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
    try {
      // Execute Cypher query via backend
      const response = await fetch('/api/query', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query })
      });
      
      if (!response.ok) {
        throw new Error('Query execution failed');
      }
      
      return await response.json();
    } catch (error) {
      throw error;
    }
  }
}

// Singleton instance
const connectionService = new ConnectionService();
export default connectionService;
