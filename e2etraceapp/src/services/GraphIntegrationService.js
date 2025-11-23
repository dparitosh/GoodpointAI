/**
 * Graph Integration Service - Coordinates backend API calls from settings panes
 * Manages GraphQL introspection, Neo4j queries, and GraphRAG operations
 */

const API_BASE = process.env.REACT_APP_API_URL || 'http://localhost:8000';

class GraphIntegrationService {
  // GraphQL Operations
  async introspectSchema(content, format, name) {
    const response = await fetch(`${API_BASE}/api/graphql/introspect`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content, format, name })
    });
    
    if (!response.ok) {
      throw new Error(`Schema introspection failed: ${response.statusText}`);
    }
    
    return await response.json();
  }

  async executeGraphQLQuery(query, data, variables = null) {
    const response = await fetch(`${API_BASE}/api/graphql/query`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query, data, variables })
    });
    
    if (!response.ok) {
      throw new Error(`Query execution failed: ${response.statusText}`);
    }
    
    return await response.json();
  }

  async transformData(sourceData, targetData, mappings) {
    const response = await fetch(`${API_BASE}/api/graphql/transform`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ source_data: sourceData, target_data: targetData, mappings })
    });
    
    if (!response.ok) {
      throw new Error(`Transform failed: ${response.statusText}`);
    }
    
    return await response.json();
  }

  // GraphQL Catalogue Operations
  async listPersistedQueries(limit = 100, offset = 0) {
    const response = await fetch(
      `${API_BASE}/api/graphql/catalogue/queries?limit=${limit}&offset=${offset}`
    );
    
    if (!response.ok) {
      throw new Error(`Failed to list queries: ${response.statusText}`);
    }
    
    return await response.json();
  }

  async saveQuery(name, query, description, format = 'json') {
    const response = await fetch(`${API_BASE}/api/graphql/catalogue/queries`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, query, description, format })
    });
    
    if (!response.ok) {
      throw new Error(`Failed to save query: ${response.statusText}`);
    }
    
    return await response.json();
  }

  // Neo4j GraphRAG Operations
  async executeGraphRAGQuery(question, context = null, tools = null, topK = 5) {
    const response = await fetch(`${API_BASE}/api/neo4j-graphrag/query`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        question,
        context,
        tools,
        top_k: topK,
        include_paths: false
      })
    });
    
    if (!response.ok) {
      throw new Error(`GraphRAG query failed: ${response.statusText}`);
    }
    
    return await response.json();
  }

  async checkGraphRAGHealth() {
    const response = await fetch(`${API_BASE}/api/neo4j-graphrag/health`);
    
    if (!response.ok) {
      throw new Error(`Health check failed: ${response.statusText}`);
    }
    
    return await response.json();
  }

  async listGraphRAGTools() {
    const response = await fetch(`${API_BASE}/api/neo4j-graphrag/tools`);
    
    if (!response.ok) {
      throw new Error(`Failed to list tools: ${response.statusText}`);
    }
    
    return await response.json();
  }

  // Migration Integration
  async getMigrationHistory(sessionId) {
    const response = await fetch(
      `${API_BASE}/api/migration/advanced/${sessionId}/history`
    );
    
    if (!response.ok) {
      throw new Error(`Failed to get migration history: ${response.statusText}`);
    }
    
    return await response.json();
  }

  // Analytics Integration
  async getAnalyticsMetrics(metricType, startDate = null, endDate = null) {
    let url = `${API_BASE}/api/analytics/${metricType}`;
    const params = new URLSearchParams();
    
    if (startDate) params.append('start_date', startDate);
    if (endDate) params.append('end_date', endDate);
    
    if (params.toString()) {
      url += `?${params.toString()}`;
    }
    
    const response = await fetch(url);
    
    if (!response.ok) {
      throw new Error(`Failed to get analytics: ${response.statusText}`);
    }
    
    return await response.json();
  }
}

// Singleton instance
const graphIntegrationService = new GraphIntegrationService();
export default graphIntegrationService;
