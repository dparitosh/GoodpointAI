const formatTooltipText = (props) => Object.entries(props || {}).map(([k, v], i) => `${i + 1}. <strong>${k}:</strong> ${JSON.stringify(v, null, 2)}<br>`).join("");

export function e2etraceCreateTableElementsFromGraph(graphData) {
    const elements = [];
    if (graphData && graphData.nodes) {
        graphData.nodes.forEach(node => {
            elements.push({
                element_type: 'Node',
                id: node.id,
                label: node.label,
                group: node.group,
                ...(node.properties || {})
            });
        });
    }
    if (graphData && graphData.edges) {
        graphData.edges.forEach(edge => {
            elements.push({
                element_type: 'Edge',
                id: edge.id,
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
    const processedNodeIds = new Set();

    if (graphData && graphData.nodes) {
        graphData.nodes.forEach(node => {
            elements.push({
                group: 'nodes',
                data: {
                    id: String(node.id),
                    label: node.label,
                    neo4j_labels: node.group ? [node.group] : (node.properties?.labels || ['DefaultLabel']),
                    group: node.group || (node.properties?.labels?.[0] || 'DefaultGroup'),
                    properties: node.properties || {},
                    parent: node.properties && node.properties.parentId ? String(node.properties.parentId) : undefined,
                    tooltip: formatTooltipText(node.properties),
                },
                classes: `${(node.group || (node.properties?.labels?.[0] || 'DefaultGroup')).toLowerCase().replace(/\s+/g, '-')}`
            });
            processedNodeIds.add(String(node.id));
        });
    }
    if (graphData && graphData.edges) {
        graphData.edges.forEach((edge) => {
            if (!edge || edge.from == null || edge.to == null) {
                console.warn(`Skipping edge with missing 'from' or 'to' fields.`, edge);
                return;
            }

            const sourceId = String(edge.from);
            const targetId = String(edge.to);

            if (!processedNodeIds.has(sourceId) || !processedNodeIds.has(targetId)) {
                console.warn(`Skipping edge with missing source/target node.`, edge);
                return;
            }

            const edgeClasses = [];
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
                    id: String(edge.id),
                    source: sourceId,
                    target: targetId,
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