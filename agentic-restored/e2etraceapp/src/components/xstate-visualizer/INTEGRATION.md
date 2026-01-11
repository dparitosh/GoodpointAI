# XState Visualizer Integration Guide

This guide shows how to integrate the XState Visualizer into your existing GraphTrace application.

## Quick Start

### 1. Import the Component

```jsx
import { XStateVisualizer } from '../components/xstate-visualizer';
```

### 2. Prepare Your Graph Data

The visualizer expects data in this format:

```jsx
const graphData = {
  nodes: [
    {
      id: 'unique-id',
      label: 'Display Name',
      type: 'Database',  // or CSV, JSON, XML, ETL, Transform, API, Service, DataQualityIssue
      properties: {
        // Custom properties
      },
      status: 'healthy'  // optional: healthy, warning, error
    }
  ],
  edges: [
    {
      source: 'node-id-1',
      target: 'node-id-2',
      label: 'EXTRACT',
      type: 'EXTRACT'  // or LOAD, TRANSFORM, INDEX, etc.
    }
  ]
};
```

### 3. Use the Component

```jsx
function YourPage() {
  const [graphData, setGraphData] = useState(null);
  
  const handleNodeUpdate = (nodeId, updates) => {
    // Handle property updates
    setGraphData(prevData => ({
      ...prevData,
      nodes: prevData.nodes.map(node =>
        node.id === nodeId
          ? { ...node, properties: { ...node.properties, ...updates } }
          : node
      )
    }));
  };

  return (
    <XStateVisualizer 
      graphData={graphData}
      onNodeUpdate={handleNodeUpdate}
    />
  );
}
```

## Integration with Existing Dashboard

### Option 1: Replace Main Dashboard Graph

In `e2etrace-main-dashboard.jsx`:

```jsx
import { XStateVisualizer } from '../../components/xstate-visualizer';

// Replace E2ETraceGraphContainer with:
<XStateVisualizer 
  graphData={{
    nodes: graphData.nodes || [],
    edges: graphData.edges || []
  }}
  onNodeUpdate={handleNodeUpdate}
/>
```

### Option 2: Add as New Route

In your routing configuration:

```jsx
import XStateVisualizerPage from './pages/xstate-visualizer/XStateVisualizerPage';

// Add route
<Route path="/xstate-visualizer" element={<XStateVisualizerPage />} />
```

### Option 3: Modal/Overlay

```jsx
import { useState } from 'react';
import { XStateVisualizer } from '../components/xstate-visualizer';

function YourComponent() {
  const [showVisualizer, setShowVisualizer] = useState(false);
  
  return (
    <>
      <button onClick={() => setShowVisualizer(true)}>
        Open XState Visualizer
      </button>
      
      {showVisualizer && (
        <div style={{ 
          position: 'fixed', 
          inset: 0, 
          zIndex: 9999,
          background: 'white' 
        }}>
          <button onClick={() => setShowVisualizer(false)}>Close</button>
          <XStateVisualizer graphData={yourData} />
        </div>
      )}
    </>
  );
}
```

## Converting Existing Data

If you have data from Neo4j or other sources, convert it:

```jsx
function convertNeo4jToXState(neo4jData) {
  const nodes = neo4jData.records.map(record => {
    const node = record.get('n');
    return {
      id: node.identity.toString(),
      label: node.properties.name || node.properties.id,
      type: node.labels[0],
      properties: node.properties,
      status: determineStatus(node)
    };
  });
  
  const edges = neo4jData.records.map(record => {
    const relationship = record.get('r');
    return {
      source: relationship.start.toString(),
      target: relationship.end.toString(),
      label: relationship.type,
      type: relationship.type
    };
  });
  
  return { nodes, edges };
}
```

## Customization

### Custom Node Colors

```jsx
// In XStateVisualizer.jsx or your wrapper
const customColorMap = {
  'CustomType1': '#ff6b6b',
  'CustomType2': '#4ecdc4',
  'CustomType3': '#ffe66d'
};

// Apply when creating nodes
nodes.map(node => ({
  ...node,
  backgroundColor: customColorMap[node.type] || '#95a5a6'
}));
```

### Custom Event Handlers

```jsx
<XStateVisualizer 
  graphData={graphData}
  onNodeUpdate={(id, updates) => {
    console.log('Node updated:', id, updates);
    // Your custom logic
  }}
  onNodeSelect={(node) => {
    console.log('Node selected:', node);
  }}
/>
```

## Advanced Features

### Programmatic Control

```jsx
import { useRef } from 'react';

function YourComponent() {
  const visualizerRef = useRef(null);
  
  const focusNode = (nodeId) => {
    if (visualizerRef.current) {
      visualizerRef.current.focusNode(nodeId);
    }
  };
  
  return (
    <XStateVisualizer 
      ref={visualizerRef}
      graphData={graphData}
    />
  );
}
```

### Real-time Updates

```jsx
import { useEffect } from 'react';

function LiveGraphVisualizer() {
  const [graphData, setGraphData] = useState(initialData);
  
  useEffect(() => {
    // Subscribe to WebSocket or polling
    const ws = new WebSocket('ws://your-server/graph-updates');
    
    ws.onmessage = (event) => {
      const update = JSON.parse(event.data);
      setGraphData(prevData => applyUpdate(prevData, update));
    };
    
    return () => ws.close();
  }, []);
  
  return <XStateVisualizer graphData={graphData} />;
}
```

## Performance Tips

1. **Lazy Loading**: Load the visualizer only when needed
```jsx
const XStateVisualizer = lazy(() => 
  import('../components/xstate-visualizer/XStateVisualizer')
);
```

2. **Memoization**: Memoize graph data transformations
```jsx
const transformedData = useMemo(() => 
  transformToXStateFormat(rawData),
  [rawData]
);
```

3. **Pagination**: For large graphs, implement data pagination
```jsx
const visibleNodes = nodes.slice(page * pageSize, (page + 1) * pageSize);
```

## Troubleshooting

### Issue: Nodes not showing
**Solution**: Ensure all nodes have valid `id`, `label`, and `type` properties

### Issue: Layout looks compressed
**Solution**: Adjust layout config in XStateVisualizer.jsx
```jsx
const layoutConfig = {
  name: 'fcose',
  nodeRepulsion: 4500,  // Increase this
  idealEdgeLength: 150  // Increase this
};
```

### Issue: Theme not applying
**Solution**: Ensure CSS files are imported in order

### Issue: Performance degradation
**Solution**: 
- Reduce node count per view
- Disable animations for large graphs
- Use virtualization for tree navigator

## Examples

See `src/pages/xstate-visualizer/XStateVisualizerPage.jsx` for a complete working example.

## Support

For issues and questions:
- Check the main README.md
- Review component prop types
- Examine the demo page implementation
