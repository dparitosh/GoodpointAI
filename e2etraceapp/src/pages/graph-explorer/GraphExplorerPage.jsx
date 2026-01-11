/**
 * Graph Explorer Page - Main page for Neo4j graph visualization
 * Integrates with GraphQL, Neo4j GraphRAG, and migration history
 * Powered by GoodPoint AI - TCS UI/UX Compliant
 */

import React, { useMemo, useRef, useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import connectionService from '../../services/connectionService';
import goodPointLogo from '../../assets/goodpoint-logo.svg';
import { E2ETraceCytoscapeGraph } from '../dashboard/e2etrace-cytoscape-graph';
import { cytoscapeStylesheet } from '../dashboard/e2etrace-cytoscape-stylesheet';
import { e2etraceTransformDataForCytoscape } from '../../utils/e2etrace-graph';
import { getRuntimeConfig } from '../../config/runtime-config';
import { API_CONFIG } from '../../config/api-config';
import { e2etraceFetchWithRetry } from '../../api/e2etrace-api';
import { 
  getNodeColor, 
  getNodeShape,
  getEdgeColor,
  getEdgeStyle,
} from '../../constants/node-colors';
import './GraphExplorerPage.css';

// Cypher-compatible operators for Neo4j queries
// These map UI options to actual Cypher comparison syntax
const CYPHER_OPERATORS = {
  '=': { label: '= (Equals)', cypher: '=', description: 'Exact match' },
  '<>': { label: '<> (Not Equals)', cypher: '<>', description: 'Not equal to' },
  'CONTAINS': { label: 'CONTAINS', cypher: 'CONTAINS', description: 'String contains substring' },
  'STARTS WITH': { label: 'STARTS WITH', cypher: 'STARTS WITH', description: 'String starts with' },
  'ENDS WITH': { label: 'ENDS WITH', cypher: 'ENDS WITH', description: 'String ends with' },
  '=~': { label: '=~ (Regex)', cypher: '=~', description: 'Regular expression match' },
  '>': { label: '> (Greater)', cypher: '>', description: 'Greater than' },
  '>=': { label: '>= (Greater or Equal)', cypher: '>=', description: 'Greater than or equal' },
  '<': { label: '< (Less)', cypher: '<', description: 'Less than' },
  '<=': { label: '<= (Less or Equal)', cypher: '<=', description: 'Less than or equal' },
  'IN': { label: 'IN (List)', cypher: 'IN', description: 'Value in list' },
  'IS NULL': { label: 'IS NULL', cypher: 'IS NULL', description: 'Property is null' },
  'IS NOT NULL': { label: 'IS NOT NULL', cypher: 'IS NOT NULL', description: 'Property exists' }
};

// Build a Cypher WHERE clause from search conditions
const buildCypherWhereClause = (conditions, nodeAlias = 'n') => {
  const validConditions = conditions.filter(c => c.property && (c.value || c.operator === 'IS NULL' || c.operator === 'IS NOT NULL'));
  if (validConditions.length === 0) return { clause: '', params: {} };
  
  const clauses = [];
  const params = {};
  
  validConditions.forEach((cond, idx) => {
    const paramName = `param${idx}`;
    const propPath = `${nodeAlias}.${cond.property}`;
    let clause = '';
    
    switch (cond.operator) {
      case '=':
        clause = `${propPath} = $${paramName}`;
        params[paramName] = cond.value;
        break;
      case '<>':
        clause = `${propPath} <> $${paramName}`;
        params[paramName] = cond.value;
        break;
      case 'CONTAINS':
        clause = `${propPath} CONTAINS $${paramName}`;
        params[paramName] = cond.value;
        break;
      case 'STARTS WITH':
        clause = `${propPath} STARTS WITH $${paramName}`;
        params[paramName] = cond.value;
        break;
      case 'ENDS WITH':
        clause = `${propPath} ENDS WITH $${paramName}`;
        params[paramName] = cond.value;
        break;
      case '=~':
        clause = `${propPath} =~ $${paramName}`;
        params[paramName] = cond.value;
        break;
      case '>':
        clause = `toFloat(${propPath}) > toFloat($${paramName})`;
        params[paramName] = cond.value;
        break;
      case '>=':
        clause = `toFloat(${propPath}) >= toFloat($${paramName})`;
        params[paramName] = cond.value;
        break;
      case '<':
        clause = `toFloat(${propPath}) < toFloat($${paramName})`;
        params[paramName] = cond.value;
        break;
      case '<=':
        clause = `toFloat(${propPath}) <= toFloat($${paramName})`;
        params[paramName] = cond.value;
        break;
      case 'IN':
        {
          // Parse comma-separated values into array
          const listValues = cond.value.split(',').map(v => v.trim());
          clause = `${propPath} IN $${paramName}`;
          params[paramName] = listValues;
          break;
        }
      case 'IS NULL':
        clause = `${propPath} IS NULL`;
        break;
      case 'IS NOT NULL':
        clause = `${propPath} IS NOT NULL`;
        break;
      default:
        clause = `${propPath} CONTAINS $${paramName}`;
        params[paramName] = cond.value;
    }
    
    if (idx > 0) {
      clause = `${cond.logic} ${clause}`;
    }
    clauses.push(clause);
  });
  
  return {
    clause: clauses.length > 0 ? `WHERE ${clauses.join(' ')}` : '',
    params
  };
};

const GraphExplorerPage = () => {
  const navigate = useNavigate();
  // Local state management (replaced Recoil)
  const [graphData, setGraphData] = useState({
    nodes: [],
    edges: [],
    loading: false,
    lastUpdated: null
  });
  
  const [filters, setFilters] = useState({
    limit: 100,
    entityTypes: [],
    relationshipTypes: [],
    searchQuery: ''
  });
  
  const [connection, setConnection] = useState({
    connected: false,
    status: 'checking',
    message: ''
  });
  
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const [selectedElement, setSelectedElement] = useState(null);
  const selectedElementRef = useRef(null);

  const cyRef = useRef(null);
  const [_cyReady, setCyReady] = useState(false);

  // Advanced Search State
  const [showAdvancedSearch, setShowAdvancedSearch] = useState(false);
  const [searchConditions, setSearchConditions] = useState([
    { id: 1, nodeType: '', property: '', operator: 'CONTAINS', value: '', logic: 'AND' }
  ]);
  const [workflowFilter, setWorkflowFilter] = useState({ id: '', name: '' });
  const [searchLoading, setSearchLoading] = useState(false);
  const [generatedCypher, setGeneratedCypher] = useState(''); // Show generated query
  
  // Workflows fetched from /api/workflows endpoint (PostgreSQL)
  const [availableWorkflows, setAvailableWorkflows] = useState([]);

  // Schema entities fetched from /api/entities endpoint (node types with properties)
  const [schemaEntities, setSchemaEntities] = useState([]);

  // Legend visibility
  const [showLegend, setShowLegend] = useState(true);

  // Get unique node types from both graph data and schema entities from backend
  const nodeTypes = useMemo(() => {
    const types = new Set();
    // Add types from loaded graph data
    graphData.nodes.forEach(n => {
      const type = n.type || n.group || 'Default';
      types.add(type);
    });
    // Add types from schema entities (from backend /api/entities)
    schemaEntities
      .filter(e => e.type === 'node')
      .forEach(e => types.add(e.label));
    return Array.from(types).sort();
  }, [graphData.nodes, schemaEntities]);

  // Get properties for a specific node type or all properties if no type selected
  const getPropertiesForNodeType = useMemo(() => {
    return (nodeType) => {
      const props = new Set();
      
      // Add properties from schema entities (backend source of truth)
      if (nodeType) {
        const entity = schemaEntities.find(e => e.type === 'node' && e.label === nodeType);
        if (entity && entity.properties) {
          entity.properties.forEach(p => props.add(p));
        }
      } else {
        // No type selected - show all properties from all node types
        schemaEntities
          .filter(e => e.type === 'node')
          .forEach(e => {
            if (e.properties) {
              e.properties.forEach(p => props.add(p));
            }
          });
      }
      
      // Also add properties from currently loaded graph data
      graphData.nodes.forEach(node => {
        const nodeTypeMatch = !nodeType || (node.type || node.group) === nodeType;
        if (nodeTypeMatch) {
          Object.keys(node).forEach(key => {
            if (!['id', 'x', 'y', 'size'].includes(key)) {
              props.add(key);
            }
          });
          // Also check nested properties
          if (node.properties) {
            Object.keys(node.properties).forEach(key => props.add(key));
          }
        }
      });
      
      return Array.from(props).sort();
    };
  }, [graphData.nodes, schemaEntities]);

  // Legacy nodeProperties for backward compatibility (all properties)
  const _nodeProperties = useMemo(() => {
    return getPropertiesForNodeType(null);
  }, [getPropertiesForNodeType]);

  // Get workflow options from fetched workflows (from /api/workflows endpoint)
  // Fallback to extracting from graph data if workflows API is unavailable
  const workflowOptions = useMemo(() => {
    // Primary source: workflows fetched from /api/workflows
    if (availableWorkflows.length > 0) {
      const ids = availableWorkflows
        .map(wf => String(wf.id || wf.workflow_id || ''))
        .filter(id => id);
      const names = availableWorkflows
        .map(wf => String(wf.name || wf.workflow_name || ''))
        .filter(name => name);
      return {
        ids: [...new Set(ids)].sort(),
        names: [...new Set(names)].sort(),
        workflows: availableWorkflows // Include full workflow objects for filtering
      };
    }
    
    // Fallback: try to extract from graph node properties
    const ids = new Set();
    const names = new Set();
    graphData.nodes.forEach(node => {
      const wfId = node.workflowId || node.workflow_id || (node.properties && (node.properties.workflowId || node.properties.workflow_id)) || '';
      const wfName = node.workflowName || node.workflow_name || (node.properties && (node.properties.workflowName || node.properties.workflow_name)) || '';
      if (wfId) ids.add(String(wfId));
      if (wfName) names.add(String(wfName));
    });
    return {
      ids: Array.from(ids).sort(),
      names: Array.from(names).sort(),
      workflows: []
    };
  }, [availableWorkflows, graphData.nodes]);

  const workflowPairs = useMemo(() => {
    // Only available when we have backend workflow objects (id <-> name mapping).
    const source = Array.isArray(workflowOptions.workflows) ? workflowOptions.workflows : [];
    if (source.length === 0) return [];

    const byId = new Map();
    source.forEach((wf) => {
      const id = String(wf?.id || wf?.workflow_id || '').trim();
      const name = String(wf?.name || wf?.workflow_name || '').trim();
      if (!id || !name) return;
      if (!byId.has(id)) {
        byId.set(id, { id, name });
      }
    });

    return Array.from(byId.values()).sort((a, b) =>
      a.name.localeCompare(b.name) || a.id.localeCompare(b.id)
    );
  }, [workflowOptions.workflows]);

  const workflowNameOptions = useMemo(() => {
    if (workflowPairs.length > 0) {
      return [...new Set(workflowPairs.map((p) => p.name))].sort((a, b) => a.localeCompare(b));
    }
    return (workflowOptions.names || []).slice().sort((a, b) => String(a).localeCompare(String(b)));
  }, [workflowPairs, workflowOptions.names]);

  const workflowIdOptions = useMemo(() => {
    if (workflowPairs.length === 0) {
      return (workflowOptions.ids || []).slice().sort((a, b) => String(a).localeCompare(String(b)));
    }

    const selectedName = String(workflowFilter?.name || '').trim();
    const ids = selectedName
      ? workflowPairs.filter((p) => p.name === selectedName).map((p) => p.id)
      : workflowPairs.map((p) => p.id);
    return [...new Set(ids)].sort((a, b) => a.localeCompare(b));
  }, [workflowPairs, workflowOptions.ids, workflowFilter?.name]);

  const handleWorkflowNameChange = (nextName) => {
    const name = String(nextName || '').trim();
    if (!name) {
      setWorkflowFilter({ id: '', name: '' });
      return;
    }

    if (workflowPairs.length === 0) {
      setWorkflowFilter((prev) => ({ ...prev, name }));
      return;
    }

    const idsForName = workflowPairs
      .filter((p) => p.name === name)
      .map((p) => p.id)
      .sort((a, b) => a.localeCompare(b));

    setWorkflowFilter({ name, id: idsForName[0] || '' });
  };

  const handleWorkflowIdChange = (nextId) => {
    const id = String(nextId || '').trim();
    if (!id) {
      setWorkflowFilter((prev) => ({ ...prev, id: '' }));
      return;
    }

    if (workflowPairs.length === 0) {
      setWorkflowFilter((prev) => ({ ...prev, id }));
      return;
    }

    const match = workflowPairs.find((p) => p.id === id);
    setWorkflowFilter({ id, name: match?.name || '' });
  };

  const resolvedWorkflowId = useMemo(() => {
    const id = String(workflowFilter?.id || '').trim();
    if (id) return id;

    const name = String(workflowFilter?.name || '').trim();
    if (!name) return '';

    if (workflowPairs.length > 0) {
      const idsForName = workflowPairs
        .filter((p) => p.name === name)
        .map((p) => p.id)
        .sort((a, b) => a.localeCompare(b));
      return String(idsForName[0] || '').trim();
    }

    const match = (availableWorkflows || []).find((wf) => {
      const wfName = String(wf?.name || wf?.workflow_name || '').trim();
      return wfName && wfName === name;
    });

    return String(match?.id || match?.workflow_id || '').trim();
  }, [workflowFilter?.id, workflowFilter?.name, workflowPairs, availableWorkflows]);

  // Build dynamic legend from actual node types in the data
  // Colors are auto-generated based on type names (deterministic hash)
  const dynamicNodeTypeLegend = useMemo(() => {
    const typeMap = new Map();
    graphData.nodes.forEach(node => {
      const typeName = node.type || node.group || 'Default';
      if (!typeMap.has(typeName)) {
        // All colors are dynamically generated from type name
        typeMap.set(typeName, {
          color: getNodeColor(typeName),
          shape: getNodeShape(typeName),
          label: typeName
        });
      }
    });
    return Array.from(typeMap.entries()).sort((a, b) => a[0].localeCompare(b[0]));
  }, [graphData.nodes]);

  // Build dynamic legend from actual edge types in the data
  const dynamicEdgeTypeLegend = useMemo(() => {
    const typeMap = new Map();
    graphData.edges.forEach(edge => {
      const typeName = edge.type || edge.label || 'default';
      if (!typeMap.has(typeName)) {
        // All colors are dynamically generated from type name
        typeMap.set(typeName, {
          color: getEdgeColor(typeName),
          style: getEdgeStyle(typeName),
          label: typeName
        });
      }
    });
    return Array.from(typeMap.entries()).sort((a, b) => a[0].localeCompare(b[0]));
  }, [graphData.edges]);

  useEffect(() => {
    selectedElementRef.current = selectedElement;
  }, [selectedElement]);

  const cyElements = useMemo(() => {
    if (graphData.nodes.length === 0) return [];
    try {
      return e2etraceTransformDataForCytoscape(
        { nodes: graphData.nodes, edges: graphData.edges },
        { colorScheme: 'default', autoGrouping: true }
      );
    } catch (e) {
      console.error('Failed to transform graph data for Cytoscape:', e);
      return [];
    }
  }, [graphData.nodes, graphData.edges]);

  const cyLayout = useMemo(
    () => ({
      name: 'cose-bilkent',
      animate: true,
      randomize: true,
      fit: true,
      padding: 30,
      nodeDimensionsIncludeLabels: true,

      // COSE-Bilkent tuning (kept close to the referenced example)
      packComponents: true,
      nestingFactor: 0.9,
      nodeRepulsion: 4500,
      idealEdgeLength: 100,
      edgeElasticity: 0.45,
      gravity: 0.25,
      initialEnergyOnIncremental: 0.5,
    }),
    []
  );

  const cyStylesheet = useMemo(
    () => ([
      ...cytoscapeStylesheet,
      {
        selector: '.dimmed',
        style: {
          'opacity': 0.15,
          'text-opacity': 0.05,
        }
      },
      {
        selector: 'edge.dimmed',
        style: {
          'opacity': 0.12,
          'text-opacity': 0,
        }
      },
      {
        selector: 'node.focus',
        style: {
          'border-width': 5,
          'border-color': '#0066CC',
        }
      },
      {
        selector: 'node.hover',
        style: {
          'border-width': 4,
          'border-color': '#48a4ff',
          'z-index': 999,
        }
      },
      {
        selector: 'edge.focus',
        style: {
          'width': 8,
          'line-color': '#0066CC',
          'target-arrow-color': '#0066CC',
        }
      },
      {
        selector: 'edge.hover',
        style: {
          'width': 6,
          'line-color': '#48a4ff',
          'target-arrow-color': '#48a4ff',
          'z-index': 999,
        }
      },
      {
        selector: 'node.neighbor',
        style: {
          'border-width': 3,
        }
      },
      {
        selector: 'edge.neighbor',
        style: {
          'width': 5,
          'text-opacity': 0.6,
        }
      },
    ]),
    []
  );

  // Callback function when Cytoscape is ready
  const handleCyReady = React.useCallback((cy) => {
    setCyReady(true);

    const clearFocusClasses = () => {
      cy.batch(() => {
        cy.elements().removeClass('dimmed neighbor focus hover');
      });
    };

    const applyNodeFocus = (node) => {
      cy.batch(() => {
        cy.elements().addClass('dimmed').removeClass('neighbor focus hover');
        node.removeClass('dimmed').addClass('focus hover');
        node.neighborhood().removeClass('dimmed').addClass('neighbor');
      });
    };

    const applyEdgeFocus = (edge) => {
      cy.batch(() => {
        cy.elements().addClass('dimmed').removeClass('neighbor focus hover');
        edge.removeClass('dimmed').addClass('focus hover');
        edge.connectedNodes().removeClass('dimmed').addClass('neighbor');
        edge.connectedEdges().removeClass('dimmed').addClass('neighbor');
      });
    };

    const handleBackgroundTap = (evt) => {
      if (evt.target === cy) {
        cy.elements().unselect();
        clearFocusClasses();
        setSelectedElement(null);
      }
    };

    const handleNodeTap = (evt) => {
      const node = evt.target;
      cy.elements().unselect();
      node.select();
      applyNodeFocus(node);
      cy.animate({
        fit: { eles: node, padding: 80 },
        duration: 300
      });
      const elementData = {
        kind: 'node',
        id: node.id(),
        data: node.data(),
      };
      setSelectedElement(elementData);
    };

    const handleEdgeTap = (evt) => {
      const edge = evt.target;
      cy.elements().unselect();
      edge.select();
      applyEdgeFocus(edge);
      cy.animate({
        fit: { eles: edge, padding: 120 },
        duration: 300
      });
      setSelectedElement({
        kind: 'edge',
        id: edge.id(),
        data: edge.data(),
      });
    };

    const handleNodeHover = (evt) => {
      if (selectedElementRef.current) return;
      evt.target.addClass('hover');
      applyNodeFocus(evt.target);
    };

    const handleEdgeHover = (evt) => {
      if (selectedElementRef.current) return;
      evt.target.addClass('hover');
      applyEdgeFocus(evt.target);
    };

    const handleUnhover = (evt) => {
      evt.target.removeClass('hover');
      if (selectedElementRef.current) return;
      clearFocusClasses();
    };

    // Remove any existing handlers first
    cy.off('tap');
    cy.off('mouseover', 'node');
    cy.off('mouseover', 'edge');
    cy.off('mouseout', 'node');
    cy.off('mouseout', 'edge');

    // Add handlers
    cy.on('tap', handleBackgroundTap);
    cy.on('tap', 'node', handleNodeTap);
    cy.on('tap', 'edge', handleEdgeTap);
    cy.on('mouseover', 'node', handleNodeHover);
    cy.on('mouseover', 'edge', handleEdgeHover);
    cy.on('mouseout', 'node', handleUnhover);
    cy.on('mouseout', 'edge', handleUnhover);
  }, []);

  // Zoom control functions
  const handleZoomIn = () => {
    const cy = cyRef.current;
    if (cy) {
      cy.animate({ zoom: cy.zoom() * 1.3, duration: 200 });
    }
  };

  const handleZoomOut = () => {
    const cy = cyRef.current;
    if (cy) {
      cy.animate({ zoom: cy.zoom() * 0.7, duration: 200 });
    }
  };

  const handleFitGraph = () => {
    const cy = cyRef.current;
    if (cy) {
      cy.animate({ fit: { padding: 50 }, duration: 300 });
    }
  };

  const handleResetView = () => {
    const cy = cyRef.current;
    if (cy) {
      cy.animate({ zoom: 1, pan: { x: 0, y: 0 }, duration: 300 });
      cy.fit(50);
    }
  };

  // Advanced search handlers
  const addSearchCondition = () => {
    setSearchConditions(prev => [
      ...prev,
      { id: Date.now(), nodeType: '', property: '', operator: 'CONTAINS', value: '', logic: 'AND' }
    ]);
  };

  const removeSearchCondition = (id) => {
    setSearchConditions(prev => prev.filter(c => c.id !== id));
  };

  const updateSearchCondition = (id, field, value) => {
    setSearchConditions(prev => prev.map(c => 
      c.id === id ? { ...c, [field]: value } : c
    ));
  };

  // Execute search via Neo4j Cypher query
  const executeAdvancedSearch = async () => {
    const cy = cyRef.current;
    
    // Clear previous highlights
    if (cy) {
      cy.elements().removeClass('search-highlight search-dimmed');
    }
    
    // Build the Cypher query
    const validConditions = searchConditions.filter(c => 
      c.property && (c.value || c.operator === 'IS NULL' || c.operator === 'IS NOT NULL')
    );
    
    // Build label filter
    const labelFilters = searchConditions
      .filter(c => c.nodeType)
      .map(c => c.nodeType);
    const uniqueLabels = [...new Set(labelFilters)];
    const labelClause = uniqueLabels.length > 0 ? `:${uniqueLabels.join('|')}` : '';
    
    // Build WHERE clause
    const { clause: whereClause, params } = buildCypherWhereClause(validConditions);
    
    // Construct the full Cypher query
    const cypherQuery = `MATCH (n${labelClause}) ${whereClause} OPTIONAL MATCH (n)-[r]-(m) RETURN n, r, m LIMIT 500`;
    
    setGeneratedCypher(cypherQuery);
    
    // If no conditions, just highlight locally
    if (validConditions.length === 0 && uniqueLabels.length === 0) {
      // Local filtering on current graph
      if (cy) {
        const matchingNodes = cy.nodes().filter(node => {
          const nodeData = node.data();
          // Check workflow filter
          if (workflowFilter.id || workflowFilter.name) {
            const workflowId = nodeData.workflowId || nodeData.workflow_id || '';
            const workflowName = nodeData.workflowName || nodeData.workflow_name || '';
            if (workflowFilter.id && !String(workflowId).toLowerCase().includes(workflowFilter.id.toLowerCase())) {
              return false;
            }
            if (workflowFilter.name && !String(workflowName).toLowerCase().includes(workflowFilter.name.toLowerCase())) {
              return false;
            }
          }
          return true;
        });
        
        if (matchingNodes.length > 0) {
          cy.elements().addClass('search-dimmed');
          matchingNodes.removeClass('search-dimmed').addClass('search-highlight');
          matchingNodes.connectedEdges().removeClass('search-dimmed');
          cy.animate({ fit: { eles: matchingNodes, padding: 50 }, duration: 300 });
        }
      }
      return;
    }
    
    // Execute query via backend
    try {
      setSearchLoading(true);
      setError(null);
      
      const response = await e2etraceFetchWithRetry(
        `${API_CONFIG.ENDPOINTS.GRAPH_QUERY}`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ query: cypherQuery, params })
        }
      );
      
      if (!response.ok) {
        throw new Error(`Search failed: ${response.statusText}`);
      }
      
      const result = await response.json();
      console.log('Search API result:', result);
      
      // Update graph data with search results
      if (result && (result.nodes || result.edges)) {
        // Normalize edge fields (backend may send 'from_node'/'to_node' instead of 'from'/'to')
        const normalizedEdges = (result.edges || []).map(edge => ({
          ...edge,
          from: edge.from ?? edge.from_node,
          to: edge.to ?? edge.to_node
        }));
        
        console.log('Setting graph data:', { nodes: result.nodes?.length, edges: normalizedEdges.length });
        
        setGraphData(prev => ({
          ...prev,
          nodes: result.nodes || [],
          edges: normalizedEdges,
          lastUpdated: new Date().toISOString()
        }));
      } else {
        console.warn('Search returned no nodes or edges:', result);
      }
      
    } catch (err) {
      console.error('Search query failed:', err);
      setError(`Search failed: ${err.message}`);
      
      // Fall back to local filtering
      if (cy) {
        localFilterSearch(cy, searchConditions, workflowFilter);
      }
    } finally {
      setSearchLoading(false);
    }
  };

  // Local filtering fallback (when backend query fails)
  const localFilterSearch = (cy, conditions, wfFilter) => {
    const matchingNodes = cy.nodes().filter(node => {
      const nodeData = node.data();
      
      // Check workflow filter
      if (wfFilter.id || wfFilter.name) {
        const workflowId = nodeData.workflowId || nodeData.workflow_id || '';
        const workflowName = nodeData.workflowName || nodeData.workflow_name || '';
        if (wfFilter.id && !String(workflowId).toLowerCase().includes(wfFilter.id.toLowerCase())) {
          return false;
        }
        if (wfFilter.name && !String(workflowName).toLowerCase().includes(wfFilter.name.toLowerCase())) {
          return false;
        }
      }

      // Filter by conditions
      const validConditions = conditions.filter(c => c.property && c.value);
      if (validConditions.length === 0) return true;

      let result = null;
      for (const cond of validConditions) {
        const nodeValue = String(nodeData[cond.property] || nodeData.properties?.[cond.property] || '').toLowerCase();
        const searchValue = cond.value.toLowerCase();
        
        let conditionMet = false;
        switch (cond.operator) {
          case '=':
            conditionMet = nodeValue === searchValue;
            break;
          case '<>':
            conditionMet = nodeValue !== searchValue;
            break;
          case 'CONTAINS':
            conditionMet = nodeValue.includes(searchValue);
            break;
          case 'STARTS WITH':
            conditionMet = nodeValue.startsWith(searchValue);
            break;
          case 'ENDS WITH':
            conditionMet = nodeValue.endsWith(searchValue);
            break;
          case '=~':
            try {
              conditionMet = new RegExp(cond.value, 'i').test(nodeData[cond.property] || '');
            } catch { conditionMet = false; }
            break;
          case '>':
            conditionMet = parseFloat(nodeValue) > parseFloat(searchValue);
            break;
          case '>=':
            conditionMet = parseFloat(nodeValue) >= parseFloat(searchValue);
            break;
          case '<':
            conditionMet = parseFloat(nodeValue) < parseFloat(searchValue);
            break;
          case '<=':
            conditionMet = parseFloat(nodeValue) <= parseFloat(searchValue);
            break;
          case 'IN':
            {
              const listValues = searchValue.split(',').map(v => v.trim());
              conditionMet = listValues.includes(nodeValue);
              break;
            }
          case 'IS NULL':
            conditionMet = !nodeData[cond.property] && !nodeData.properties?.[cond.property];
            break;
          case 'IS NOT NULL':
            conditionMet = !!(nodeData[cond.property] || nodeData.properties?.[cond.property]);
            break;
          default:
            conditionMet = nodeValue.includes(searchValue);
        }

        if (result === null) {
          result = conditionMet;
        } else if (cond.logic === 'AND') {
          result = result && conditionMet;
        } else {
          result = result || conditionMet;
        }
      }

      return result !== false;
    });

    // Apply highlighting
    if (matchingNodes.length > 0) {
      cy.elements().addClass('search-dimmed');
      matchingNodes.removeClass('search-dimmed').addClass('search-highlight');
      matchingNodes.connectedEdges().removeClass('search-dimmed');
      cy.animate({ fit: { eles: matchingNodes, padding: 50 }, duration: 300 });
    }
  };

  const clearSearch = () => {
    const cy = cyRef.current;
    if (cy) {
      cy.elements().removeClass('search-highlight search-dimmed');
    }
    setSearchConditions([{ id: 1, nodeType: '', property: '', operator: 'CONTAINS', value: '', logic: 'AND' }]);
    setWorkflowFilter({ id: '', name: '' });
    setGeneratedCypher('');
  };

  useEffect(() => {
    // Setup event listeners
    const handleConnected = () => {
      setConnection(prev => ({ ...prev, connected: true, status: 'connected' }));
    };

    const handleDisconnected = () => {
      setConnection(prev => ({ ...prev, connected: false, status: 'disconnected' }));
    };

    const handleGraphDataLoaded = (data) => {
      if (!data || typeof data !== 'object') {
        setGraphData(prev => ({ ...prev, loading: false }));
        return;
      }
      setGraphData(prev => ({ ...prev, ...data, loading: false }));
    };

    const handleError = (data) => {
      const message = data && typeof data === 'object' ? data.error : null;
      setError(message || 'An unexpected error occurred.');
      setLoading(false);
    };

    connectionService.addEventListener('connected', handleConnected);
    connectionService.addEventListener('disconnected', handleDisconnected);
    connectionService.addEventListener('graph-data-loaded', handleGraphDataLoaded);
    connectionService.addEventListener('connection-error', handleError);

    return () => {
      connectionService.removeEventListener('connected', handleConnected);
      connectionService.removeEventListener('disconnected', handleDisconnected);
      connectionService.removeEventListener('graph-data-loaded', handleGraphDataLoaded);
      connectionService.removeEventListener('connection-error', handleError);
    };
  }, []);

  // Fetch available workflows from backend API (PostgreSQL)
  useEffect(() => {
    const fetchWorkflows = async () => {
      try {
        const response = await e2etraceFetchWithRetry(
          `${API_CONFIG.ENDPOINTS.WORKFLOWS}?skip=0&limit=100`,
          { method: 'GET' }
        );
        if (response.ok) {
          const data = await response.json();
          // API returns an array of workflow objects with id, name, etc.
          if (Array.isArray(data)) {
            setAvailableWorkflows(data);
          } else if (data && Array.isArray(data.items)) {
            // Handle paginated response if applicable
            setAvailableWorkflows(data.items);
          } else if (data && Array.isArray(data.workflows)) {
            setAvailableWorkflows(data.workflows);
          }
        }
      } catch (err) {
        console.warn('Failed to fetch workflows:', err.message);
        // Non-critical - workflows dropdown will just be empty
      }
    };
    
    fetchWorkflows();
  }, []);

  // Fetch schema entities (node types with properties) from backend API
  useEffect(() => {
    const fetchSchemaEntities = async () => {
      try {
        const response = await e2etraceFetchWithRetry(
          `${API_CONFIG.ENDPOINTS.ENTITIES}?skip=0&limit=500`,
          { method: 'GET' }
        );
        if (response.ok) {
          const data = await response.json();
          // API returns array of {type: "node"|"relationship", label: string, properties: string[]}
          if (Array.isArray(data)) {
            setSchemaEntities(data);
          }
        }
      } catch (err) {
        console.warn('Failed to fetch schema entities:', err.message);
        // Non-critical - property dropdown will fall back to graph data properties
      }
    };
    
    fetchSchemaEntities();
  }, []);

  useEffect(() => {
    // Auto-connect using backend's Neo4j configuration
    let cancelled = false;

    const checkAndConnect = async () => {
      try {
        setConnection(prev => ({ ...prev, status: 'checking', message: 'Checking Neo4j connection...' }));
        
        // First check if backend has Neo4j configured
        const runtime = await getRuntimeConfig();
        if (cancelled) return;
        
        const neo4j = runtime && runtime.neo4j ? runtime.neo4j : null;
        if (!neo4j || !neo4j.uri) {
          setConnection({
            connected: false,
            status: 'not-configured',
            message: 'Neo4j not configured. Please configure it in Data Sources settings.'
          });
          return;
        }

        // Try to connect using backend's stored credentials
        setConnection(prev => ({ ...prev, status: 'connecting', message: 'Connecting to Neo4j...' }));
        await connectionService.connectViaBackend();
        
      } catch (err) {
        if (cancelled) return;
        setConnection({
          connected: false,
          status: 'error',
          message: err.message || 'Failed to connect to Neo4j'
        });
      }
    };

    checkAndConnect();

    return () => {
      cancelled = true;
    };
  }, []);

  const handleReconnect = async () => {
    try {
      setLoading(true);
      setError(null);
      setConnection(prev => ({ ...prev, status: 'connecting', message: 'Reconnecting...' }));
      await connectionService.connectViaBackend();
    } catch (err) {
      setError(err.message);
      setConnection({
        connected: false,
        status: 'error',
        message: err.message || 'Failed to reconnect'
      });
    } finally {
      setLoading(false);
    }
  };

  const handleLoadData = async () => {
    try {
      setLoading(true);
      setError(null);
      await connectionService.loadGraphData(filters);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleFilterChange = (key, value) => {
    setFilters(prev => ({ ...prev, [key]: value }));
  };

  return (
    <div className="graph-explorer-page">
      {/* Header with branding */}
      <div className="page-header">
        <div className="header-content">
          <img src={goodPointLogo} alt="GoodPoint" className="page-logo" />
          <div className="header-title">
            <h1>Graph Explorer</h1>
            <p className="header-subtitle">AI powered PLM Data migration</p>
          </div>
        </div>
      </div>

      {/* Connection Status Panel */}
      <div className="connection-panel card">
        <h2>Neo4j Connection</h2>
        <div className="connection-status">
          <span className={`status-indicator ${connection.status}`}></span>
          <span className="status-text">
            {connection.connected ? 'Connected' : connection.message || 'Checking...'}
          </span>
        </div>
        
        {connection.status === 'not-configured' && (
          <div className="connection-info">
            <p>Neo4j connection is not configured.</p>
            <a href="/#/admin" className="btn-primary">
              <i className="fas fa-cog" aria-hidden="true"></i> Configure in Admin Settings
            </a>
          </div>
        )}
        
        {connection.status === 'error' && (
          <div className="connection-info">
            <button 
              onClick={handleReconnect} 
              disabled={loading}
              className="btn-primary"
            >
              {loading ? 'Reconnecting...' : 'Retry Connection'}
            </button>
            <a href="/#/admin" className="btn-secondary">
              Check Settings
            </a>
          </div>
        )}
      </div>

      {/* Filters Panel */}
      {connection.connected && (
        <div className="filters-panel card">
          <div className="filters-header">
            <h2>Filters</h2>
            <button 
              type="button"
              className="btn-toggle"
              onClick={() => setShowAdvancedSearch(!showAdvancedSearch)}
            >
              <i className={`fas ${showAdvancedSearch ? 'fa-minus' : 'fa-search-plus'}`} aria-hidden="true"></i>
              {showAdvancedSearch ? 'Simple Search' : 'Advanced Search'}
            </button>
          </div>
          
          {!showAdvancedSearch ? (
            /* Simple Search */
            <div className="simple-search">
              <div className="filter-group">
                <label>Limit:</label>
                <input
                  type="number"
                  value={filters.limit}
                  onChange={(e) => {
                    const next = Number(e.target.value);
                    if (Number.isFinite(next)) handleFilterChange('limit', next);
                  }}
                  min="10"
                  max="1000"
                />
              </div>
              <div className="filter-group">
                <label>Search:</label>
                <input
                  type="text"
                  value={filters.searchQuery}
                  onChange={(e) => handleFilterChange('searchQuery', e.target.value)}
                  placeholder="Search nodes..."
                />
              </div>
              <button 
                onClick={handleLoadData} 
                disabled={loading}
                className="btn-primary"
              >
                {loading ? 'Loading...' : 'Load Graph Data'}
              </button>
            </div>
          ) : (
            /* Advanced Search - Agile PLM Style */
            <div className="advanced-search">
              {/* Workflow Filter Section */}
              <div className="workflow-filter-section">
                <h3><i className="fas fa-project-diagram" aria-hidden="true"></i> Workflow Association</h3>
                <div className="workflow-filter-row">
                  <div className="filter-group">
                    <label>Workflow Name:</label>
                    <select
                      value={workflowFilter.name}
                      onChange={(e) => handleWorkflowNameChange(e.target.value)}
                      className="workflow-select"
                    >
                      <option value="">All Workflow Names</option>
                      {workflowNameOptions.map(name => (
                        <option key={name} value={name}>{name}</option>
                      ))}
                    </select>
                  </div>
                  <div className="filter-group">
                    <label>Workflow ID:</label>
                    <select
                      value={workflowFilter.id}
                      onChange={(e) => handleWorkflowIdChange(e.target.value)}
                      className="workflow-select"
                    >
                      <option value="">All Workflow IDs</option>
                      {workflowIdOptions.map(id => (
                        <option key={id} value={id}>{id}</option>
                      ))}
                    </select>
                  </div>
                </div>

                <div className="workflow-filter-actions">
                  <button
                    type="button"
                    className="btn-primary btn-small"
                    disabled={!resolvedWorkflowId}
                    onClick={() => navigate(`/graph-explorer/workflow/${encodeURIComponent(resolvedWorkflowId)}`)}
                    title={resolvedWorkflowId ? 'Open workflow details' : 'Select a workflow id to view details'}
                  >
                    View Workflow Details
                  </button>
                </div>
              </div>

              {/* Search Conditions */}
              <h3><i className="fas fa-filter" aria-hidden="true"></i> Search Conditions (Cypher)</h3>
              <div className="search-conditions">
                {searchConditions.map((condition, index) => (
                  <div key={condition.id} className="search-condition-row">
                    {index > 0 && (
                      <select
                        value={condition.logic}
                        onChange={(e) => updateSearchCondition(condition.id, 'logic', e.target.value)}
                        className="logic-select"
                      >
                        <option value="AND">AND</option>
                        <option value="OR">OR</option>
                      </select>
                    )}
                    <select
                      value={condition.nodeType}
                      onChange={(e) => {
                        updateSearchCondition(condition.id, 'nodeType', e.target.value);
                        // Reset property when node type changes to avoid invalid selections
                        updateSearchCondition(condition.id, 'property', '');
                      }}
                      className="node-type-select"
                    >
                      <option value="">All Node Types</option>
                      {nodeTypes.map(type => (
                        <option key={type} value={type}>{type}</option>
                      ))}
                    </select>
                    <select
                      value={condition.property}
                      onChange={(e) => updateSearchCondition(condition.id, 'property', e.target.value)}
                      className="property-select"
                    >
                      <option value="">Select Property</option>
                      {getPropertiesForNodeType(condition.nodeType).map(prop => (
                        <option key={prop} value={prop}>{prop}</option>
                      ))}
                    </select>
                    <select
                      value={condition.operator}
                      onChange={(e) => updateSearchCondition(condition.id, 'operator', e.target.value)}
                      className="operator-select"
                      title={CYPHER_OPERATORS[condition.operator]?.description || 'Select operator'}
                    >
                      {Object.entries(CYPHER_OPERATORS).map(([key, op]) => (
                        <option key={key} value={key}>{op.label}</option>
                      ))}
                    </select>
                    <input
                      type="text"
                      value={condition.value}
                      onChange={(e) => updateSearchCondition(condition.id, 'value', e.target.value)}
                      placeholder={condition.operator === 'IN' ? 'val1, val2, val3' : 
                                   condition.operator === '=~' ? '.*regex.*' : 
                                   condition.operator === 'IS NULL' || condition.operator === 'IS NOT NULL' ? '(not needed)' : 'Value...'}
                      className="value-input"
                      disabled={condition.operator === 'IS NULL' || condition.operator === 'IS NOT NULL'}
                    />
                    {searchConditions.length > 1 && (
                      <button
                        type="button"
                        className="btn-icon btn-danger"
                        onClick={() => removeSearchCondition(condition.id)}
                        title="Remove condition"
                      >
                        <i className="fas fa-times" aria-hidden="true"></i>
                      </button>
                    )}
                  </div>
                ))}
              </div>
              
              {/* Generated Cypher Query Preview */}
              {generatedCypher && (
                <div className="cypher-preview">
                  <h4><i className="fas fa-code" aria-hidden="true"></i> Generated Cypher Query</h4>
                  <pre className="cypher-code">{generatedCypher}</pre>
                </div>
              )}
              
              <div className="search-actions">
                <button type="button" className="btn-secondary" onClick={addSearchCondition}>
                  <i className="fas fa-plus" aria-hidden="true"></i> Add Condition
                </button>
                <button type="button" className="btn-primary" onClick={executeAdvancedSearch} disabled={searchLoading}>
                  <i className={`fas ${searchLoading ? 'fa-spinner fa-spin' : 'fa-search'}`} aria-hidden="true"></i> 
                  {searchLoading ? ' Searching...' : ' Search'}
                </button>
                <button type="button" className="btn-secondary" onClick={clearSearch}>
                  <i className="fas fa-eraser" aria-hidden="true"></i> Clear
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Graph Visualization Area */}
      {connection.connected && graphData.nodes.length > 0 && (
        <div className="graph-container card">
          <div className="graph-header">
            <h2>Graph Visualization</h2>
            <div className="graph-toolbar">
              {/* Zoom Controls */}
              <div className="zoom-controls" role="group" aria-label="Zoom controls">
                <button type="button" className="btn-toolbar" onClick={handleZoomIn} title="Zoom In">
                  <i className="fas fa-search-plus" aria-hidden="true"></i>
                </button>
                <button type="button" className="btn-toolbar" onClick={handleZoomOut} title="Zoom Out">
                  <i className="fas fa-search-minus" aria-hidden="true"></i>
                </button>
                <button type="button" className="btn-toolbar" onClick={handleFitGraph} title="Fit to Screen">
                  <i className="fas fa-compress-arrows-alt" aria-hidden="true"></i>
                </button>
                <button type="button" className="btn-toolbar" onClick={handleResetView} title="Reset View">
                  <i className="fas fa-undo" aria-hidden="true"></i>
                </button>
              </div>
              <div className="toolbar-divider"></div>
              {/* Legend Toggle */}
              <button 
                type="button" 
                className={`btn-toolbar ${showLegend ? 'active' : ''}`}
                onClick={() => setShowLegend(!showLegend)}
                title="Toggle Legend"
              >
                <i className="fas fa-palette" aria-hidden="true"></i> Legend
              </button>
            </div>
          </div>
          
          <div className="graph-stats">
            <span><i className="fas fa-circle" aria-hidden="true"></i> Nodes: {graphData.nodes.length}</span>
            <span><i className="fas fa-arrow-right" aria-hidden="true"></i> Edges: {graphData.edges.length}</span>
            {graphData.lastUpdated && (
              <span><i className="fas fa-clock" aria-hidden="true"></i> Last Updated: {new Date(graphData.lastUpdated).toLocaleTimeString()}</span>
            )}
          </div>

          <div className="graph-main-area">
            {/* Legend Panel - shows actual types from loaded data */}
            {showLegend && (
              <div className="legend-panel">
                <div className="legend-section">
                  <h4><i className="fas fa-circle" aria-hidden="true"></i> Node Types ({dynamicNodeTypeLegend.length})</h4>
                  <ul className="legend-list">
                    {dynamicNodeTypeLegend.length > 0 ? (
                      dynamicNodeTypeLegend.map(([type, config]) => (
                        <li key={type} className="legend-item">
                          <span 
                            className={`legend-shape shape-${config.shape}`} 
                            style={{ backgroundColor: config.color }}
                          ></span>
                          <span className="legend-label">{config.label}</span>
                        </li>
                      ))
                    ) : (
                      // Show message when no data loaded - types come from Neo4j dynamically
                      <li className="legend-item legend-placeholder">
                        <span className="legend-label text-muted">Load graph data to see node types</span>
                      </li>
                    )}
                  </ul>
                </div>
                <div className="legend-section">
                  <h4><i className="fas fa-arrow-right" aria-hidden="true"></i> Relationship Types ({dynamicEdgeTypeLegend.length})</h4>
                  <ul className="legend-list">
                    {dynamicEdgeTypeLegend.length > 0 ? (
                      dynamicEdgeTypeLegend.map(([type, config]) => (
                        <li key={type} className="legend-item">
                          <span 
                            className={`legend-line line-${config.style}`}
                            style={{ backgroundColor: config.color }}
                          ></span>
                          <span className="legend-label">{config.label}</span>
                        </li>
                      ))
                    ) : (
                      // Show message when no data loaded - types come from Neo4j dynamically
                      <li className="legend-item legend-placeholder">
                        <span className="legend-label text-muted">Load graph data to see relationship types</span>
                      </li>
                    )}
                  </ul>
                </div>
              </div>
            )}

            <div className="graph-visualization">
              <E2ETraceCytoscapeGraph
                elements={cyElements}
                stylesheet={cyStylesheet}
                layout={cyLayout}
                cyRef={cyRef}
                onReady={handleCyReady}
              />
            </div>

            {/* Node Details Side Panel - integrated into graph-main-area layout */}
            {selectedElement && (
              <div className="node-details-panel" role="region" aria-label="Selected element details">
                <div className="node-details-header">
                  <div className="node-details-title">
                    <span className="node-type-badge" style={{ backgroundColor: selectedElement.data?.backgroundColor || '#48a4ff' }}>
                      {selectedElement.kind === 'node' ? 'Node' : 'Edge'}
                    </span>
                    <h3>{selectedElement.data?.label || selectedElement.id}</h3>
                  </div>
                  <button
                    type="button"
                    className="node-details-close"
                    onClick={() => {
                      const cy = cyRef.current;
                      if (cy) {
                        cy.elements().unselect();
                        cy.elements().removeClass('dimmed neighbor focus hover');
                      }
                      setSelectedElement(null);
                    }}
                    aria-label="Close details panel"
                  >
                    <i className="fas fa-times" aria-hidden="true"></i>
                  </button>
                </div>

                <div className="node-details-content">
                  {/* Basic Info Section */}
                  <div className="details-section">
                    <h4 className="details-section-title">
                      <i className="fas fa-info-circle" aria-hidden="true"></i> Basic Information
                    </h4>
                    <table className="details-table">
                      <tbody>
                        <tr>
                          <td className="details-key">ID</td>
                          <td className="details-value">{String(selectedElement.id)}</td>
                        </tr>
                        {selectedElement.data?.label != null && (
                          <tr>
                            <td className="details-key">Label</td>
                            <td className="details-value">{String(selectedElement.data.label)}</td>
                          </tr>
                        )}
                        {selectedElement.data?.type != null && (
                          <tr>
                            <td className="details-key">Type</td>
                            <td className="details-value">{String(selectedElement.data.type)}</td>
                          </tr>
                        )}
                        {selectedElement.data?.group != null && (
                          <tr>
                            <td className="details-key">Group</td>
                            <td className="details-value">{String(selectedElement.data.group)}</td>
                          </tr>
                        )}
                        {selectedElement.data?.status != null && (
                          <tr>
                            <td className="details-key">Status</td>
                            <td className="details-value">
                              <span className={`status-badge status-${selectedElement.data.status}`}>
                                {String(selectedElement.data.status)}
                              </span>
                            </td>
                          </tr>
                        )}
                      </tbody>
                    </table>
                  </div>

                  {/* Properties Section */}
                  {selectedElement.data && Object.keys(selectedElement.data).filter(k => 
                    !['id', 'label', 'type', 'group', 'status', 'backgroundColor', 'source', 'target'].includes(k)
                  ).length > 0 && (
                    <div className="details-section">
                      <h4 className="details-section-title">
                        <i className="fas fa-cog" aria-hidden="true"></i> Properties
                      </h4>
                      <table className="details-table">
                        <tbody>
                          {Object.entries(selectedElement.data)
                            .filter(([key]) => !['id', 'label', 'type', 'group', 'status', 'backgroundColor', 'source', 'target'].includes(key))
                            .map(([key, value]) => (
                              <tr key={key}>
                                <td className="details-key">{key}</td>
                                <td className="details-value">
                                  {typeof value === 'object' ? JSON.stringify(value) : String(value)}
                                </td>
                              </tr>
                            ))
                          }
                        </tbody>
                      </table>
                    </div>
                  )}

                  {/* Edge Connection Info */}
                  {selectedElement.kind === 'edge' && (
                    <div className="details-section">
                      <h4 className="details-section-title">
                        <i className="fas fa-link" aria-hidden="true"></i> Connection
                      </h4>
                      <table className="details-table">
                        <tbody>
                          <tr>
                            <td className="details-key">Source</td>
                            <td className="details-value">{String(selectedElement.data?.source || '')}</td>
                          </tr>
                          <tr>
                            <td className="details-key">Target</td>
                            <td className="details-value">{String(selectedElement.data?.target || '')}</td>
                          </tr>
                        </tbody>
                      </table>
                    </div>
                  )}

                  {/* Raw Data Collapsible */}
                  <details className="details-section details-raw">
                    <summary>
                      <i className="fas fa-code" aria-hidden="true"></i> Raw Data
                    </summary>
                    <pre className="raw-data-pre">{JSON.stringify(selectedElement.data, null, 2)}</pre>
                  </details>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Error Display */}
      {error && (
        <div className="error-banner">
          <strong>Error:</strong> {error}
          <button onClick={() => setError(null)} className="btn-close">×</button>
        </div>
      )}
    </div>
  );
};

export default GraphExplorerPage;
