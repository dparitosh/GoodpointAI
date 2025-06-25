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

export function e2etraceTransformDataForCytoscape(graphData) {
    const elements = [];
    const originalIdToCyIdMap = new Map(); // Map original node IDs to their unique Cytoscape IDs
    const seenCyIds = new Set(); // To ensure unique IDs for Cytoscape elements

    if (graphData && graphData.nodes) {
        graphData.nodes.forEach(node => {
            let baseId = String(node.id);
            let cyId = baseId;
            let counter = 0;
            while (seenCyIds.has(cyId)) {
                counter++;
                cyId = `${baseId}-${counter}`;
            }
            seenCyIds.add(cyId);
            originalIdToCyIdMap.set(node.id, cyId); // Store the mapping

            elements.push({
                group: 'nodes',
                data: {
                    id: cyId, // Use the unique ID for Cytoscape
                    label: node.label,
                    neo4j_labels: node.group ? [node.group] : (node.properties?.labels || ['DefaultLabel']),
                    group: node.group || (node.properties?.labels?.[0] || 'DefaultGroup'),
                    properties: node.properties || {},
                    parent: node.properties && node.properties.parentId ? String(node.properties.parentId) : undefined,
                    tooltip: formatTooltipText(node.properties),
                },
                classes: `${(node.group || (node.properties?.labels?.[0] || 'DefaultGroup')).toLowerCase().replace(/\s+/g, '-')}`
            });
        });
    }
    if (graphData && graphData.edges) {
        graphData.edges.forEach((edge) => {
            if (!edge || edge.from == null || edge.from == undefined || edge.to == null || edge.to == undefined) {
                console.warn(`Skipping edge with missing 'from' or 'to' fields.`, edge);
                return;
            }

            const sourceId = String(edge.from);
            const targetId = String(edge.to);
            const uniqueSourceId = originalIdToCyIdMap.get(sourceId);
            const uniqueTargetId = originalIdToCyIdMap.get(targetId);

            if (!uniqueSourceId || !uniqueTargetId) {
                // This means an edge refers to a node ID that either doesn't exist or wasn't uniquely mapped.
                // This could happen if the original graph data has an edge pointing to a non-existent node.
                // Or if the node's original ID was duplicated and the edge refers to one of the duplicates that wasn't picked as the primary.
                // For now, we'll skip this edge. A more robust solution might involve creating placeholder nodes or logging a critical error.
                console.warn(`Skipping edge due to missing or unmapped source/target node. Edge:`, edge, `Source original ID: ${sourceId} (mapped to: ${uniqueSourceId}), Target original ID: ${targetId} (mapped to: ${uniqueTargetId})`);

                console.warn(`Skipping edge with missing source/target node.`, edge);
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

            const edgeClasses = []; // Reset edgeClasses for each edge
            if (edge.properties && edge.properties.status === 'CRITICAL') { // Check for critical status
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
                    properties: edge.properties || {},
                    tooltip: formatTooltipText(edge.properties),
                },
                classes: edgeClasses.join(' ')
            });
        });
    }
    return elements;
}