/**
 * Advanced Graph Data Processing Utilities
 * Provides functions for enhancing graph data with colors, grouping, relationships, and metadata
 */

import cytoscape from 'cytoscape';
import { colorSchemes } from '../pages/dashboard/e2etrace-cytoscape-stylesheet';
import { getNodeColor as getCentralizedNodeColor, getNodeShape, getEdgeColor, getEdgeStyle } from '../constants/node-colors';

/**
 * Enhance nodes with visual properties based on their type and data
 */
export const enhanceNodes = (nodes, options = {}) => {
    const { 
        colorScheme = 'default',
        autoGrouping = true,
        sizingProperty = 'importance',
        defaultSize = 50
    } = options;

    // Note: scheme is kept for backward compatibility but colors now come from centralized constants
    const scheme = colorSchemes[colorScheme] || colorSchemes.default;

    return nodes.map(node => {
        const enhanced = { ...node };
        const data = enhanced.data || {};

        // Auto-detect node group/type if not specified
        if (autoGrouping && !data.group) {
            data.group = detectNodeGroup(data);
        }

        // Set background color based on group/type - uses centralized color constants
        if (!data.backgroundColor) {
            data.backgroundColor = getNodeColor(data.group || data.type, scheme);
        }

        // Set node shape based on group/type - uses centralized shape mapping
        if (!data.shape) {
            data.shape = getNodeShape(data.group || data.type);
        }

        // Set node size based on importance or custom property
        if (!data.size) {
            data.size = getNodeSize(data, sizingProperty, defaultSize);
        }

        // Add status if determinable from data
        if (!data.status && data.properties) {
            data.status = determineNodeStatus(data.properties);
        }

        // Enhance metadata
        data.description = data.description || generateNodeDescription(data);
        
        // Add metrics if available
        if (data.properties && !data.metrics) {
            data.metrics = extractMetrics(data.properties);
        }

        enhanced.data = data;
        return enhanced;
    });
};

/**
 * Enhance edges with visual properties and relationship metadata
 */
export const enhanceEdges = (edges, options = {}) => {
    const { 
        colorScheme: _colorScheme = 'default',
        autoTyping = true,
        weightProperty = 'weight'
    } = options;

    return edges.map(edge => {
        const enhanced = { ...edge };
        const data = enhanced.data || {};

        // Auto-detect edge type if not specified
        if (autoTyping && !data.type) {
            data.type = detectEdgeType(data);
        }

        // Set edge color based on type - uses centralized dynamic colors
        if (!data.lineColor) {
            data.lineColor = getEdgeColor(data.type || data.label);
        }

        // Set edge line style based on type
        if (!data.lineStyle) {
            data.lineStyle = getEdgeStyle(data.type || data.label);
        }

        // Set weight if not specified
        if (!data.weight && data.properties) {
            data.weight = extractWeight(data.properties, weightProperty);
        }

        // Add relationship metadata
        data.description = data.description || generateEdgeDescription(data);

        enhanced.data = data;
        return enhanced;
    });
};

/**
 * Auto-detect node group based on properties and naming patterns
 */
const detectNodeGroup = (nodeData) => {
    const { id = '', label = '', type = '', properties: _properties = {} } = nodeData;
    const text = `${id} ${label} ${type}`.toLowerCase();

    // Database patterns
    if (text.includes('database') || text.includes('db') || text.includes('sql') || 
        text.includes('teamcenter') || text.includes('oracle') || text.includes('mysql')) {
        return 'Database';
    }

    // File patterns
    if (text.includes('csv') || text.includes('.csv')) return 'CSV';
    if (text.includes('json') || text.includes('.json')) return 'JSON';
    if (text.includes('xml') || text.includes('.xml') || text.includes('plmxml')) return 'XML';

    // Processing patterns
    if (text.includes('processor') || text.includes('transform') || text.includes('etl') ||
        text.includes('process') || text.includes('convert')) {
        return 'Processor';
    }

    // API patterns
    if (text.includes('api') || text.includes('service') || text.includes('endpoint') ||
        text.includes('rest') || text.includes('http')) {
        return 'API';
    }

    return 'Unknown';
};

/**
 * Auto-detect edge type based on properties and naming patterns
 */
const detectEdgeType = (edgeData) => {
    const { label = '', source = '', target = '', properties = {} } = edgeData;
    const text = `${label} ${source} ${target}`.toLowerCase();

    if (text.includes('dataflow') || text.includes('data') || text.includes('flow')) {
        return 'dataflow';
    }

    if (text.includes('depend') || text.includes('require') || text.includes('need')) {
        return 'dependency';
    }

    if (text.includes('inherit') || text.includes('extend') || text.includes('parent')) {
        return 'inheritance';
    }

    if (text.includes('compose') || text.includes('contain') || text.includes('part')) {
        return 'composition';
    }

    if (properties.critical || text.includes('critical') || text.includes('important')) {
        return 'critical';
    }

    return 'connection';
};

/**
 * Get node color based on group
 * IMPORTANT: Uses centralized color constants from constants/node-colors.js
 * DO NOT define colors here - update the constants file instead
 * 
 * @param {string} group - Node group/type name
 * @param {Object} scheme - Color scheme (kept for backward compatibility, not used)
 * @returns {string} Hex color code
 */
const getNodeColor = (group, _scheme) => {
    // Delegate to centralized color function
    return getCentralizedNodeColor(group);
};

/**
 * Calculate node size based on importance or other properties
 */
const getNodeSize = (nodeData, sizingProperty, defaultSize) => {
    const { properties = {}, importance } = nodeData;

    if (importance) {
        const sizeMap = {
            'high': defaultSize * 1.5,
            'medium': defaultSize,
            'low': defaultSize * 0.7
        };
        return sizeMap[importance] || defaultSize;
    }

    if (properties[sizingProperty]) {
        const value = properties[sizingProperty];
        if (typeof value === 'number') {
            return Math.max(30, Math.min(100, value));
        }
    }

    // Size based on degree (connections)
    if (properties.degree) {
        return Math.max(40, Math.min(80, 40 + properties.degree * 5));
    }

    return defaultSize;
};

/**
 * Determine node status from properties
 */
const determineNodeStatus = (properties) => {
    const { state, status, health, running, enabled, error } = properties;

    if (error || state === 'ERROR' || status === 'ERROR') return 'error';
    if (state === 'STOPPED' || status === 'STOPPED' || !enabled) return 'stopped';
    if (state === 'DISABLED' || status === 'DISABLED') return 'disabled';
    if (running || state === 'RUNNING' || status === 'RUNNING') return 'running';
    if (health === 'HEALTHY' || status === 'HEALTHY') return 'healthy';
    if (health === 'WARNING' || status === 'WARNING') return 'warning';

    return 'unknown';
};

/**
 * Generate descriptive text for nodes
 */
const generateNodeDescription = (nodeData) => {
    const { type, group, properties = {} } = nodeData;
    
    let description = '';
    
    if (type || group) {
        description += `${type || group} component`;
    }
    
    if (properties.description) {
        description += description ? ` - ${properties.description}` : properties.description;
    }
    
    if (properties.version) {
        description += ` (v${properties.version})`;
    }

    return description || 'Graph node';
};

/**
 * Generate descriptive text for edges
 */
const generateEdgeDescription = (edgeData) => {
    const { type, properties = {} } = edgeData;
    
    let description = '';
    
    if (type) {
        description += `${type} relationship`;
    }
    
    if (properties.description) {
        description += description ? ` - ${properties.description}` : properties.description;
    }

    return description || 'Graph connection';
};

/**
 * Extract metrics from node properties
 */
const extractMetrics = (properties) => {
    const metrics = {};
    
    // Common metric patterns
    const metricKeys = ['throughput', 'latency', 'errorRate', 'cpuUsage', 'memoryUsage', 
                       'connections', 'requests', 'responses', 'bytes', 'count'];
    
    metricKeys.forEach(key => {
        if (properties[key] !== undefined) {
            metrics[key] = properties[key];
        }
    });

    return metrics;
};

/**
 * Extract weight from edge properties
 */
const extractWeight = (properties, weightProperty) => {
    if (properties[weightProperty] !== undefined) {
        return Number(properties[weightProperty]);
    }
    
    // Look for common weight indicators
    const weightKeys = ['weight', 'strength', 'count', 'frequency', 'throughput'];
    
    for (const key of weightKeys) {
        if (properties[key] !== undefined) {
            return Number(properties[key]) || 1;
        }
    }

    return 1;
};

/**
 * Apply search highlighting to graph elements
 */
export const applySearchHighlight = (elements, searchTerm) => {
    if (!searchTerm) {
        return elements.map(el => ({
            ...el,
            classes: el.classes?.replace(/\s*(search-highlight|search-dimmed)\s*/g, ' ').trim() || ''
        }));
    }

    const searchLower = searchTerm.toLowerCase();
    
    return elements.map(el => {
        const data = el.data || {};
        const label = (data.label || '').toLowerCase();
        const id = (data.id || '').toLowerCase();
        const type = (data.type || '').toLowerCase();
        
        const isMatch = label.includes(searchLower) || 
                       id.includes(searchLower) || 
                       type.includes(searchLower);
        
        let classes = el.classes || '';
        
        // Remove existing search classes
        classes = classes.replace(/\s*(search-highlight|search-dimmed)\s*/g, ' ').trim();
        
        // Add appropriate class
        if (isMatch) {
            classes += ' search-highlight';
        } else {
            classes += ' search-dimmed';
        }
        
        return {
            ...el,
            classes: classes.trim()
        };
    });
};

/**
 * Apply filtering to graph elements
 */
export const applyGraphFilter = (elements, filterOptions) => {
    const { 
        nodeTypes = [], 
        edgeTypes = [], 
        statusFilter = [], 
        hideFiltered = false 
    } = filterOptions;

    return elements.map(el => {
        const data = el.data || {};
        let shouldShow = true;
        
        if (el.group === 'nodes' && nodeTypes.length > 0) {
            shouldShow = nodeTypes.includes(data.type || data.group);
        }
        
        if (el.group === 'edges' && edgeTypes.length > 0) {
            shouldShow = shouldShow && edgeTypes.includes(data.type);
        }
        
        if (statusFilter.length > 0 && data.status) {
            shouldShow = shouldShow && statusFilter.includes(data.status);
        }
        
        let classes = el.classes || '';
        classes = classes.replace(/\s*filtered-out\s*/g, ' ').trim();
        
        if (!shouldShow) {
            if (hideFiltered) {
                return null; // Will be filtered out
            } else {
                classes += ' filtered-out';
            }
        }
        
        return {
            ...el,
            classes: classes.trim()
        };
    }).filter(Boolean);
};

/**
 * Calculate graph statistics
 */
export const calculateGraphStats = (elements) => {
    const nodes = elements.filter(el => el.group === 'nodes');
    const edges = elements.filter(el => el.group === 'edges');
    
    // Node type distribution
    const nodeTypes = {};
    nodes.forEach(node => {
        const type = node.data?.type || node.data?.group || 'Unknown';
        nodeTypes[type] = (nodeTypes[type] || 0) + 1;
    });
    
    // Edge type distribution
    const edgeTypes = {};
    edges.forEach(edge => {
        const type = edge.data?.type || 'Unknown';
        edgeTypes[type] = (edgeTypes[type] || 0) + 1;
    });
    
    // Status distribution
    const statusDistribution = {};
    nodes.forEach(node => {
        const status = node.data?.status || 'Unknown';
        statusDistribution[status] = (statusDistribution[status] || 0) + 1;
    });
    
    return {
        totalNodes: nodes.length,
        totalEdges: edges.length,
        nodeTypes,
        edgeTypes,
        statusDistribution,
        averageConnections: edges.length > 0 ? (edges.length * 2) / nodes.length : 0
    };
};

/**
 * Apply ETL-specific filters to the graph
 */
export const applyETLFilter = (cy, filterType, options = {}) => {
    if (!cy) return;

    // Reset previous filters
    cy.elements().removeClass('filtered-out highlighted etl-filtered');
    
    let targetElements = cy.collection();

    switch (filterType) {
        case 'source':
            targetElements = cy.nodes().filter(node => {
                const data = node.data();
                return data.type === 'source' || 
                       data.category === 'input' ||
                       data.group === 'Source' ||
                       data.label?.toLowerCase().includes('source');
            });
            break;

        case 'processor':
        case 'transformation':
            targetElements = cy.nodes().filter(node => {
                const data = node.data();
                return data.type === 'processor' || 
                       data.category === 'transformation' ||
                       data.group === 'Processor' ||
                       data.label?.toLowerCase().includes('transform') ||
                       data.label?.toLowerCase().includes('process');
            });
            break;

        case 'destination':
            targetElements = cy.nodes().filter(node => {
                const data = node.data();
                return data.type === 'destination' || 
                       data.category === 'output' ||
                       data.group === 'Destination' ||
                       data.label?.toLowerCase().includes('destination') ||
                       data.label?.toLowerCase().includes('output');
            });
            break;

        case 'pipeline': {
            // Highlight entire connected components
            const connectedComponents = getConnectedComponents(cy);
            if (options.pipelineIndex !== undefined && connectedComponents[options.pipelineIndex]) {
                targetElements = connectedComponents[options.pipelineIndex];
            }
            break;
        }

        case 'error':
            targetElements = cy.nodes().filter(node => {
                const data = node.data();
                return data.status === 'error' || 
                       data.status === 'failed' ||
                       data.hasError === true;
            });
            break;

        case 'performance':
            // Highlight high-throughput or slow nodes
            targetElements = cy.nodes().filter(node => {
                const data = node.data();
                const metrics = data.metrics || {};
                return metrics.throughput > 1000 || metrics.latency > 500;
            });
            break;

        default:
            return;
    }

    // Hide non-target elements and highlight targets
    const allElements = cy.elements();
    const nonTargetElements = allElements.difference(targetElements);
    
    if (options.hideOthers) {
        nonTargetElements.addClass('filtered-out');
    }
    
    targetElements.addClass('etl-filtered highlighted');
    
    // Include connected edges for better visualization
    const connectedEdges = targetElements.connectedEdges();
    connectedEdges.addClass('etl-filtered');

    // Auto-fit to filtered elements if requested
    if (options.autoFit && targetElements.length > 0) {
        cy.animate({
            fit: { eles: targetElements, padding: 50 },
            duration: 500,
            easing: 'ease-out-quad'
        });
    }

    return {
        filtered: targetElements.length,
        hidden: nonTargetElements.length
    };
};

/**
 * Get connected components (pipelines) in the graph
 */
const getConnectedComponents = (cy) => {
    const visited = new Set();
    const components = [];
    
    cy.nodes().forEach(node => {
        if (!visited.has(node.id())) {
            const component = cy.collection();
            const stack = [node];
            
            while (stack.length > 0) {
                const current = stack.pop();
                if (!visited.has(current.id())) {
                    visited.add(current.id());
                    component.merge(current);
                    
                    // Add connected nodes
                    current.connectedEdges().forEach(edge => {
                        const otherNode = edge.source().id() === current.id() ? edge.target() : edge.source();
                        if (!visited.has(otherNode.id())) {
                            stack.push(otherNode);
                        }
                        component.merge(edge);
                    });
                }
            }
            
            components.push(component);
        }
    });
    
    return components;
};

/**
 * Highlight ETL performance bottlenecks
 */
export const highlightPerformanceIssues = (cy, thresholds = {}) => {
    if (!cy) return;

    const {
        maxLatency = 1000,
        minThroughput = 100,
        maxErrorRate = 5
    } = thresholds;

    cy.nodes().removeClass('performance-issue high-latency low-throughput high-error');

    cy.nodes().forEach(node => {
        const data = node.data();
        const metrics = data.metrics || {};

        if (metrics.latency > maxLatency) {
            node.addClass('performance-issue high-latency');
        }

        if (metrics.throughput < minThroughput) {
            node.addClass('performance-issue low-throughput');
        }

        if (metrics.errorRate > maxErrorRate) {
            node.addClass('performance-issue high-error');
        }
    });
};

/**
 * Calculate ETL-specific pipeline metrics
 */
export const calculatePipelineMetrics = (graphData) => {
    if (!graphData || !graphData.nodes) {
        return {
            totalPipelines: 0,
            avgPipelineLength: 0,
            longestPipeline: 0,
            shortestPipeline: 0,
            pipelineEfficiency: 0
        };
    }

    // Transform data to proper Cytoscape format if needed
    const nodes = graphData.nodes.map(node => ({
        group: 'nodes',
        data: {
            id: node.data?.id || node.id,
            ...node.data
        }
    }));

    const edges = (graphData.edges || []).map(edge => ({
        group: 'edges',
        data: {
            id: edge.data?.id || edge.id,
            source: edge.data?.source || edge.source,
            target: edge.data?.target || edge.target,
            ...edge.data
        }
    }));

    // Skip pipeline analysis if we don't have valid elements
    if (nodes.length === 0) {
        return {
            totalPipelines: 0,
            avgPipelineLength: 0,
            longestPipeline: 0,
            shortestPipeline: 0,
            pipelineEfficiency: 0
        };
    }

    let cy;
    try {
        // Create temporary cytoscape instance for analysis
        cy = cytoscape({
            elements: [...nodes, ...edges],
            headless: true
        });

        const components = getConnectedComponents(cy);
        const pipelineLengths = components.map(comp => comp.nodes().length);
        
        const totalPipelines = components.length;
        const avgPipelineLength = pipelineLengths.length > 0 ? 
            pipelineLengths.reduce((sum, len) => sum + len, 0) / pipelineLengths.length : 0;
        const longestPipeline = Math.max(...pipelineLengths, 0);
        const shortestPipeline = Math.min(...pipelineLengths, 0);
        
        // Calculate efficiency based on node connectivity
        const totalNodes = nodes.length;
        const totalEdges = edges.length;
        const pipelineEfficiency = totalNodes > 0 ? (totalEdges / totalNodes) * 100 : 0;

        cy.destroy();

        return {
            totalPipelines,
            avgPipelineLength: parseFloat(avgPipelineLength.toFixed(1)),
            longestPipeline,
            shortestPipeline,
            pipelineEfficiency: parseFloat(pipelineEfficiency.toFixed(1))
        };
    } catch (error) {
        console.warn('Error calculating pipeline metrics:', error);
        if (cy) cy.destroy();
        
        // Return basic metrics without Cytoscape analysis
        return {
            totalPipelines: 1,
            avgPipelineLength: nodes.length,
            longestPipeline: nodes.length,
            shortestPipeline: nodes.length,
            pipelineEfficiency: edges.length > 0 ? (edges.length / nodes.length) * 100 : 0
        };
    }
};

export default {
    enhanceNodes,
    enhanceEdges,
    applySearchHighlight,
    applyGraphFilter,
    calculateGraphStats,
    applyETLFilter,
    highlightPerformanceIssues,
    calculatePipelineMetrics
};
