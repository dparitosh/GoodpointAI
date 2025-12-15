# XState-Style Visualizer for ETL & Data Migration

An interactive XState-inspired graph visualization system for ETL (Extract, Transform, Load) and data migration operations with advanced features and smooth animations.

## Features

### Visual Design
- **XState-Inspired UI**: Clean, modern interface mimicking XState Visualizer's aesthetic
- **Dark/Light Themes**: Smooth theme switching with persistent preferences
- **Color-Coded Nodes**: Distinct colors for each ETL entity type
  - Database/Teamcenter: `#48a4ff` (Blue)
  - CSV Files: `#ffba5a` (Orange)
  - JSON Files: `#9b6cff` (Violet)
  - XML/PLMXML: `#ff7077` (Red)
  - ETL/Transform: `#21d5c1` (Teal)
  - API/Services: `#6e6fff` (Purple)
  - Data Quality Issues: `#e74c3c` (Red Alert)
- **Rounded Rectangles**: Soft, professional node shapes with shadows
- **Animated Edges**: Smooth, curved connections with directional arrows

### Layout
- **3-Panel Design**: Tree Navigator | Graph Canvas | Inspector Panel
- **Resizable Panels**: Drag dividers to adjust panel widths
- **Bottom Event Drawer**: Collapsible event log with timeline
- **Responsive**: Adapts to different screen sizes

### Interactions
- **Click**: Select nodes and edges
- **Double-Click**: Open detailed node drawer
- **Ctrl+Click**: Multi-select nodes
- **Shift+Drag**: Pan the canvas
- **Hover**: Glow effects on nodes and edges
- **Smart Snapping**: Nodes snap to alignment when dragging

### Panels

#### Left Panel - Tree Navigator
- Hierarchical view of all nodes grouped by type
- Expandable/collapsible tree structure
- Search functionality
- Click to select and focus on graph
- Node count badges

#### Center Panel - Graph Canvas
- Interactive Cytoscape.js visualization
- Zoom and pan controls
- Fit-to-screen button
- Reset layout button
- Animated transitions on layout changes
- Support for compound nodes (grouping)

#### Right Panel - Inspector
- **Properties Tab**: View and edit node attributes
- **Relationships Tab**: Connected nodes and edge types
- **Metadata Tab**: System information (ID, type, timestamps)
- **AI Insights Tab**: Placeholder for ML-powered suggestions
- **History Tab**: Migration and change history

#### Bottom Panel - Event Log
- Real-time event stream
- Color-coded event types (info, success, warning, error)
- Click events to highlight affected nodes
- Export functionality
- Timestamp tracking

### Advanced Features

#### Detail Drawer
- Slides in from right on double-click
- Comprehensive node information
- Quick actions (Edit, View History, Export, Delete)
- Relationship visualization
- Escape key to close

#### Animation System
- Smooth node selection with pulse effect
- Edge animations from source to target
- Layout transitions with easing
- Fade-in/out for expanding/collapsing groups
- Hover elevation effects

#### Smart Interactions
- **Multi-Select**: Hold Ctrl/Cmd and click multiple nodes
- **Canvas Pan**: Hold Shift and drag to pan the entire view
- **Smart Snapping**: Nodes align automatically when close to others
- **Keyboard Shortcuts**:
  - `Escape`: Close drawers/modals
  - `Ctrl+A`: Select all (future enhancement)
  - `Del`: Delete selected (future enhancement)

## Usage

### Basic Usage

```jsx
import { XStateVisualizer } from './components/xstate-visualizer';

function App() {
  const graphData = {
    nodes: [
      {
        id: 'part-001',
        label: 'Engine Assembly',
        type: 'Part',
        properties: { partNumber: 'ENG-001', status: 'Active' }
      }
    ],
    edges: [
      {
        source: 'part-001',
        target: 'part-002',
        label: 'HAS_PART',
        type: 'HAS_PART'
      }
    ]
  };

  const handleNodeUpdate = (nodeId, updates) => {
    // Handle property updates
    console.log('Node updated:', nodeId, updates);
  };

  return (
    <XStateVisualizer 
      graphData={graphData} 
      onNodeUpdate={handleNodeUpdate}
    />
  );
}
```

### Data Format

#### Node Structure
```javascript
{
  id: 'unique-id',           // Required: Unique identifier
  label: 'Display Name',     // Required: Node label
  type: 'Part',              // Node type for coloring
  group: 'Part',             // Optional: Group name
  backgroundColor: '#48a4ff', // Optional: Custom color
  properties: {              // Optional: Custom properties
    key: 'value'
  },
  status: 'healthy',         // Optional: 'healthy', 'warning', 'error'
  size: 50                   // Optional: Node size
}
```

#### Edge Structure
```javascript
{
  id: 'edge-id',             // Optional: Unique identifier
  source: 'node-id-1',       // Required: Source node ID
  target: 'node-id-2',       // Required: Target node ID
  label: 'HAS_PART',         // Optional: Edge label
  type: 'HAS_PART',          // Optional: Edge type
  weight: 3                  // Optional: Edge thickness (1-10)
}
```

## Components

### XStateVisualizer
Main orchestrator component that brings everything together.

**Props:**
- `graphData` (object): Graph data with nodes and edges
- `onNodeUpdate` (function): Callback for node property updates

### XStateLayout
3-panel resizable layout component.

**Props:**
- `treePanel` (ReactNode): Left panel content
- `graphPanel` (ReactNode): Center panel content
- `inspectorPanel` (ReactNode): Right panel content
- `eventPanel` (ReactNode): Bottom panel content
- `theme` (string): 'light' or 'dark'

### TreeNavigator
Hierarchical tree view for navigation.

**Props:**
- `nodes` (array): Tree structure of nodes
- `onNodeClick` (function): Click handler
- `selectedNodeId` (string): Currently selected node
- `theme` (string): Theme setting

### InspectorPanel
Detailed node information panel.

**Props:**
- `selectedNode` (object): Node to inspect
- `onPropertyChange` (function): Property edit handler
- `aiInsights` (array): AI-generated insights
- `migrationHistory` (array): Change history
- `theme` (string): Theme setting

### EventPanel
Event log and timeline.

**Props:**
- `events` (array): Event list
- `onEventClick` (function): Event click handler
- `theme` (string): Theme setting

### DetailDrawer
Slide-in drawer for detailed node view.

**Props:**
- `node` (object): Node to display
- `isOpen` (boolean): Drawer state
- `onClose` (function): Close handler
- `theme` (string): Theme setting

## Customization

### Theming
Modify theme colors in CSS files:
- `XStateLayout.css`: Panel backgrounds and borders
- `xstate-cytoscape-stylesheet.js`: Node and edge colors

### Node Colors
Update the color map in `XStateVisualizer.jsx`:
```javascript
const getColorForType = (type) => {
  const colorMap = {
    'Part': '#48a4ff',
    'Document': '#6e6fff',
    // Add more types...
  };
  return colorMap[type] || colorMap['default'];
};
```

### Layout Algorithm
Change the layout in `XStateVisualizer.jsx`:
```javascript
const layoutConfig = {
  name: 'fcose',  // or 'cose', 'grid', 'circle', 'concentric'
  // ... layout options
};
```

## Browser Support
- Chrome/Edge: Full support
- Firefox: Full support
- Safari: Full support
- IE11: Not supported

## Performance
- Optimized for graphs with up to 500 nodes
- Uses React memo for component optimization
- Cytoscape.js for efficient graph rendering
- Smooth 60fps animations

## Future Enhancements
- [ ] Keyboard shortcuts for all actions
- [ ] Node grouping and clustering
- [ ] Export graph as image
- [ ] Undo/redo functionality
- [ ] Real-time collaboration
- [ ] GraphQL integration
- [ ] WebSocket live updates
- [ ] Advanced filtering and search
- [ ] Custom node shapes
- [ ] Animation recording

## License
MIT

## Contributors
- Built with React, Cytoscape.js, and XState design principles
