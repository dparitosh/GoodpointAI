import { enhanceNodes, enhanceEdges } from './e2etrace-graph-enhancement';

const formatTooltipText = (props) => Object.entries(props || {}).map(([k, v], i) => `${i + 1}. <strong>${k}:</strong> ${JSON.stringify(v, null, 2)}<br>`).join("");

export function e2etraceCreateTableElementsFromGraph(graphData) {
    const elements = [];
    const seenKeys = new Set(); // To track generated keys and ensure uniqueness

    if (graphData && graphData.nodes) {
        graphData.nodes.forEach(node => {
            let baseId = String(node.id);
            let uniqueKey = `node-${baseId}`;
            let counter = 0;
            while (seenKeys.has(uniqueKey)) {
                counter++;
                uniqueKey = `node-${baseId}-${counter}`;
            }
            seenKeys.add(uniqueKey);
            elements.push({
                element_type: 'Node',
                id: node.id,
                _uniqueKey: uniqueKey, // Add a truly unique key for React
                label: node.label,
                group: node.group,
                ...(node.properties || {})
            });
        });
    }
    if (graphData && graphData.edges) {
        graphData.edges.forEach(edge => {
            let baseId = String(edge.id);
            let uniqueKey = `edge-${baseId}`;
            let counter = 0;
            while (seenKeys.has(uniqueKey)) {
                counter++;
                uniqueKey = `edge-${baseId}-${counter}`;
            }
            seenKeys.add(uniqueKey);
            elements.push({
                element_type: 'Edge',
                id: edge.id,
                _uniqueKey: uniqueKey, // Add a truly unique key for React
                label: edge.label,
                source: edge.from,
                target: edge.to,
                ...(edge.properties || {})
            });
        });
    }
    return elements;
}

export function e2etraceTransformDataForCytoscape(graphData, options = {}) {
    const elements = [];
    const originalIdToCyIdMap = new Map(); // Map original node IDs to their unique Cytoscape IDs
    const seenCyIds = new Set(); // To ensure unique IDs for Cytoscape elements

    // First pass: Create all nodes with enhanced properties
    if (graphData && graphData.nodes) {
        // Enhance nodes with visual properties and metadata
        const enhancedNodes = enhanceNodes(graphData.nodes.map(node => ({
            group: 'nodes',
            data: {
                id: node.id,
                label: node.label,
                type: node.group,
                group: node.group,
                properties: node.properties || {},
                ...node
            }
        })), options);

        enhancedNodes.forEach((nodeElement, index) => {
            const node = graphData.nodes[index];
            const nodeData = nodeElement.data;
            
            let baseId = String(node.id);
            let cyId = baseId;
            let counter = 0;
            while (seenCyIds.has(cyId)) {
                counter++;
                cyId = `${baseId}-${counter}`;
            }
            seenCyIds.add(cyId);
            originalIdToCyIdMap.set(node.id, cyId); // Store the mapping

            // Build CSS classes
            const cssClasses = [];
            const group = nodeData.group || nodeData.type || 'DefaultGroup';
            cssClasses.push(group.toLowerCase().replace(/\s+/g, '-'));
            
            if (nodeData.status) {
                cssClasses.push(nodeData.status.toLowerCase());
            }
            
            if (nodeData.importance) {
                cssClasses.push(`importance-${nodeData.importance}`);
            }

            elements.push({
                group: 'nodes',
                data: {
                    id: cyId, // Use the unique ID for Cytoscape
                    label: nodeData.label,
                    type: nodeData.type || nodeData.group,
                    group: nodeData.group,
                    backgroundColor: nodeData.backgroundColor,
                    size: nodeData.size,
                    status: nodeData.status,
                    importance: nodeData.importance,
                    description: nodeData.description,
                    metrics: nodeData.metrics || {},
                    neo4j_labels: node.group ? [node.group] : (node.properties?.labels || ['DefaultLabel']),
                    properties: nodeData.properties || {},
                    parent: node.properties && node.properties.parentId ? String(node.properties.parentId) : undefined,
                    tooltip: formatTooltipText(nodeData.properties),
                },
                classes: cssClasses.join(' ')
            });
        });
    }

    // Second pass: Create all edges with enhanced properties
    if (graphData && graphData.edges) {
        // Enhance edges with visual properties and metadata
        const enhancedEdges = enhanceEdges(graphData.edges.map(edge => ({
            group: 'edges',
            data: {
                id: edge.id,
                source: edge.from,
                target: edge.to,
                label: edge.label,
                properties: edge.properties || {},
                ...edge
            }
        })), options);

        enhancedEdges.forEach((edgeElement, index) => {
            const edge = graphData.edges[index];
            const edgeData = edgeElement.data;
            
            if (!edge || edge.from == null || edge.from == undefined || edge.to == null || edge.to == undefined) {
                console.warn(`Skipping edge with missing 'from' or 'to' fields.`, edge);
                return;
            }

            const sourceId = String(edge.from);
            const targetId = String(edge.to);
            const uniqueSourceId = originalIdToCyIdMap.get(sourceId);
            const uniqueTargetId = originalIdToCyIdMap.get(targetId);

            if (!uniqueSourceId || !uniqueTargetId) {
                console.warn(`Skipping edge due to missing or unmapped source/target node. Edge:`, edge, 
                    `Source original ID: ${sourceId} (mapped to: ${uniqueSourceId}), Target original ID: ${targetId} (mapped to: ${uniqueTargetId})`);
                return;
            }
            
            let baseId = String(edge.id);
            let cyId = baseId;
            let counter = 0;
            while (seenCyIds.has(cyId)) {
                counter++;
                cyId = `${baseId}-${counter}`;
            }
            seenCyIds.add(cyId);

            // Build CSS classes for edges
            const edgeClasses = [];
            
            if (edgeData.type) {
                edgeClasses.push(edgeData.type.toLowerCase().replace(/\s+/g, '-'));
            }
            
            if (edge.properties && edge.properties.status === 'CRITICAL') {
                edgeClasses.push('critical');
            }
            
            if (edge.label) {
                const sanitizedLabel = edge.label.toLowerCase().replace(/\s+/g, '-').replace(/[^a-z0-9-]/g, '');
                if (sanitizedLabel) {
                    edgeClasses.push(`edge-${sanitizedLabel}`);
                }
            }

            elements.push({
                group: 'edges',
                data: {
                    id: cyId, // Use the unique ID for Cytoscape
                    originalId: edge.id, // Keep original ID if needed elsewhere
                    source: uniqueSourceId, // Use the unique Cytoscape ID for source
                    target: uniqueTargetId, // Use the unique Cytoscape ID for target
                    label: edge.label,
                    type: edgeData.type,
                    weight: edgeData.weight || 1,
                    description: edgeData.description,
                    properties: edgeData.properties || {},
                    tooltip: formatTooltipText(edgeData.properties),
                },
                classes: edgeClasses.join(' ')
            });
        });
    }

    console.log('Enhanced graph elements created:', {
        nodes: elements.filter(el => el.group === 'nodes').length,
        edges: elements.filter(el => el.group === 'edges').length,
        totalElements: elements.length
    });

    return elements;
}