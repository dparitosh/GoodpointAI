/**
 * Graph State Atoms - Recoil state management for Graph Explorer
 * Stores graph data, filters, query panel state, and Neo4j configuration
 */

import { atom } from 'recoil';

export const graphDataAtom = atom({
  key: 'graphData',
  default: {
    nodes: [],
    edges: [],
    lastUpdated: null,
    loading: false,
    error: null
  }
});

export const graphFiltersAtom = atom({
  key: 'graphFilters',
  default: {
    limit: 100,
    entityTypes: [],
    relationshipTypes: [],
    searchTerm: ''
  }
});

export const graphQueryPanelAtom = atom({
  key: 'graphQueryPanel',
  default: {
    isOpen: false,
    query: '',
    results: null,
    executing: false,
    error: null
  }
});

export const neo4jConnectionAtom = atom({
  key: 'neo4jConnection',
  default: {
    uri: process.env.REACT_APP_NEO4J_URI || 'bolt://localhost:7687',
    user: process.env.REACT_APP_NEO4J_USER || 'neo4j',
    password: '',
    connected: false,
    auto_connect: false,
    status: 'disconnected'
  }
});

export const graphViewModeAtom = atom({
  key: 'graphViewMode',
  default: 'explorer' // 'explorer' | 'mock'
});
