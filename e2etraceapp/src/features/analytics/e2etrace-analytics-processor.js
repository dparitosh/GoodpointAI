export function e2etraceProcessGraphDataForAnalytics(graphData) {
    if (!graphData || !graphData.nodes || !graphData.edges) {
        console.warn("E2ETrace: Cannot process analytics, invalid graph data provided.");
        return null;
    }

    // 1. Count of nodes per label type
    const labelCounts = graphData.nodes.reduce((acc, node) => {
        const label = node.group || 'Unknown';
        acc[label] = (acc[label] || 0) + 1;
        return acc;
    }, {});

    // Count of edges per label type
    const relationshipCounts = graphData.edges.reduce((acc, edge) => {
        const label = edge.label || 'Unknown';
        acc[label] = (acc[label] || 0) + 1;
        return acc;
    }, {});

    // --- Data Migration & Quality Metrics ---
    const legacyNodes = graphData.nodes.filter(n => n.properties?.system === 'legacy');
    const targetNodes = graphData.nodes.filter(n => n.properties?.system === 'target');

    const mappedLegacyNodes = new Set(graphData.edges.map(e => e.from));
    const mappedTargetNodes = new Set(graphData.edges.map(e => e.to));

    const mappingCoverage = {
        mapped: mappedLegacyNodes.size,
        unmapped: legacyNodes.length - mappedLegacyNodes.size,
    };

    const orphanTargetNodes = targetNodes.filter(n => !mappedTargetNodes.has(n.id));

    const dataQualityIssues = graphData.nodes.filter(n => n.group === 'DataQualityIssue').length;

    // 2. Count of nodes per property value
    const propertyValueCounts = graphData.nodes.reduce((acc, node) => {
        if (node.properties) {
            Object.entries(node.properties).forEach(([key, value]) => {
                if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') {
                    if (!acc[key]) {
                        acc[key] = {};
                    }
                    acc[key][String(value)] = (acc[key][String(value)] || 0) + 1;
                }
            });
        }
        return acc;
    }, {});

    return {
        labelCounts,
        relationshipCounts,
        propertyValueCounts,
        mappingCoverage,
        orphanTargetNodes,
        dataQualityIssues
    };
}