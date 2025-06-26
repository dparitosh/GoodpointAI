import React, { useState, useEffect } from 'react';
import './e2etrace-graph-toolbar.css';

/**
 * Advanced Graph Toolbar Component
 * Provides controls for layout, filtering, search, zoom, and visualization options
 */
const GraphToolbar = ({ 
    cytoscapeRef, 
    onSearchChange,
    onFilterChange,
    onLayoutChange,
    onColorSchemeChange,
    graphStats = {},
    className = ''
}) => {
    const [isExpanded, setIsExpanded] = useState(false);
    const [searchTerm, setSearchTerm] = useState('');
    const [selectedLayout, setSelectedLayout] = useState('cose');
    const [selectedColorScheme, setSelectedColorScheme] = useState('default');
    const [nodeTypeFilters, setNodeTypeFilters] = useState([]);
    const [edgeTypeFilters, setEdgeTypeFilters] = useState([]);
    const [statusFilters, setStatusFilters] = useState([]);
    const [zoomLevel, setZoomLevel] = useState(100);

    // Available layouts
    const layouts = [
        { value: 'cose', label: 'Force-Directed (COSE)', description: 'Physics-based layout' },
        { value: 'grid', label: 'Grid', description: 'Organized grid layout' },
        { value: 'circle', label: 'Circle', description: 'Circular arrangement' },
        { value: 'concentric', label: 'Concentric', description: 'Concentric circles' },
        { value: 'breadthfirst', label: 'Hierarchical', description: 'Tree-like hierarchy' },
        { value: 'random', label: 'Random', description: 'Random positioning' }
    ];

    // Available color schemes
    const colorSchemes = [
        { value: 'default', label: 'Default', description: 'Standard blue theme' },
        { value: 'dark', label: 'Dark', description: 'Dark theme' },
        { value: 'corporate', label: 'Corporate', description: 'Professional colors' },
        { value: 'vibrant', label: 'Vibrant', description: 'Bright, colorful theme' }
    ];

    // Handle search
    const handleSearchChange = (e) => {
        const value = e.target.value;
        setSearchTerm(value);
        onSearchChange?.(value);
    };

    // Handle layout change
    const handleLayoutChange = (layoutName) => {
        setSelectedLayout(layoutName);
        onLayoutChange?.(layoutName);
        
        if (cytoscapeRef?.current) {
            const cy = cytoscapeRef.current;
            const layoutOptions = getLayoutOptions(layoutName);
            
            cy.layout(layoutOptions).run();
        }
    };

    // Handle color scheme change
    const handleColorSchemeChange = (scheme) => {
        setSelectedColorScheme(scheme);
        onColorSchemeChange?.(scheme);
    };

    // Get layout options for Cytoscape
    const getLayoutOptions = (layoutName) => {
        const baseOptions = {
            name: layoutName,
            animate: true,
            animationDuration: 500,
            fit: true,
            padding: 30
        };

        switch (layoutName) {
            case 'cose':
                return {
                    ...baseOptions,
                    nodeRepulsion: 400000,
                    nodeOverlap: 20,
                    idealEdgeLength: 100,
                    edgeElasticity: 100,
                    nestingFactor: 5,
                    gravity: 80,
                    numIter: 1000,
                    initialTemp: 200,
                    coolingFactor: 0.95,
                    minTemp: 1.0
                };
            case 'grid':
                return {
                    ...baseOptions,
                    rows: undefined,
                    cols: undefined,
                    position: function(node) { return node.renderedPosition(); },
                    sort: undefined,
                    animate: true
                };
            case 'circle':
                return {
                    ...baseOptions,
                    radius: undefined,
                    startAngle: 3 / 2 * Math.PI,
                    sweep: undefined,
                    clockwise: true,
                    sort: undefined,
                    animate: true
                };
            case 'concentric':
                return {
                    ...baseOptions,
                    concentric: function(node) {
                        return node.degree();
                    },
                    levelWidth: function(nodes) {
                        return 2;
                    },
                    spacing: 30,
                    clockwise: true,
                    equidistant: false,
                    minNodeSpacing: 10
                };
            case 'breadthfirst':
                return {
                    ...baseOptions,
                    directed: true,
                    roots: undefined,
                    maximal: false,
                    circle: false,
                    spacingFactor: 1.75,
                    boundingBox: undefined,
                    avoidOverlap: true,
                    nodeDimensionsIncludeLabels: false
                };
            default:
                return baseOptions;
        }
    };

    // Handle zoom controls
    const handleZoom = (direction) => {
        if (!cytoscapeRef?.current) return;
        
        const cy = cytoscapeRef.current;
        const currentZoom = cy.zoom();
        const zoomFactor = direction === 'in' ? 1.2 : 0.8;
        const newZoom = currentZoom * zoomFactor;
        
        cy.zoom(newZoom);
        setZoomLevel(Math.round(newZoom * 100));
    };

    // Handle fit to view
    const handleFit = () => {
        if (!cytoscapeRef?.current) return;
        
        const cy = cytoscapeRef.current;
        cy.fit();
        setZoomLevel(Math.round(cy.zoom() * 100));
    };

    // Handle center view
    const handleCenter = () => {
        if (!cytoscapeRef?.current) return;
        
        const cy = cytoscapeRef.current;
        cy.center();
    };

    // Handle node type filter change
    const handleNodeTypeFilterChange = (nodeType, checked) => {
        const newFilters = checked 
            ? [...nodeTypeFilters, nodeType]
            : nodeTypeFilters.filter(type => type !== nodeType);
        
        setNodeTypeFilters(newFilters);
        onFilterChange?.({
            nodeTypes: newFilters,
            edgeTypes: edgeTypeFilters,
            statusFilter: statusFilters
        });
    };

    // Handle edge type filter change
    const handleEdgeTypeFilterChange = (edgeType, checked) => {
        const newFilters = checked 
            ? [...edgeTypeFilters, edgeType]
            : edgeTypeFilters.filter(type => type !== edgeType);
        
        setEdgeTypeFilters(newFilters);
        onFilterChange?.({
            nodeTypes: nodeTypeFilters,
            edgeTypes: newFilters,
            statusFilter: statusFilters
        });
    };

    // Handle status filter change
    const handleStatusFilterChange = (status, checked) => {
        const newFilters = checked 
            ? [...statusFilters, status]
            : statusFilters.filter(s => s !== status);
        
        setStatusFilters(newFilters);
        onFilterChange?.({
            nodeTypes: nodeTypeFilters,
            edgeTypes: edgeTypeFilters,
            statusFilter: newFilters
        });
    };

    // Clear all filters
    const handleClearFilters = () => {
        setNodeTypeFilters([]);
        setEdgeTypeFilters([]);
        setStatusFilters([]);
        setSearchTerm('');
        onFilterChange?.({
            nodeTypes: [],
            edgeTypes: [],
            statusFilter: []
        });
        onSearchChange?.('');
    };

    // Update zoom level when Cytoscape zoom changes
    useEffect(() => {
        if (!cytoscapeRef?.current) return;
        
        const cy = cytoscapeRef.current;
        const updateZoom = () => {
            setZoomLevel(Math.round(cy.zoom() * 100));
        };
        
        cy.on('zoom', updateZoom);
        return () => cy.off('zoom', updateZoom);
    }, [cytoscapeRef]);

    return (
        <div className={`graph-toolbar ${isExpanded ? 'expanded' : ''} ${className}`}>
            {/* Main Toolbar */}
            <div className="toolbar-main">
                {/* Search */}
                <div className="toolbar-section">
                    <div className="search-container">
                        <input
                            type="text"
                            placeholder="Search nodes and edges..."
                            value={searchTerm}
                            onChange={handleSearchChange}
                            className="search-input"
                        />
                        <button
                            className="search-clear"
                            onClick={() => handleSearchChange({ target: { value: '' } })}
                            title="Clear search"
                        >
                            ×
                        </button>
                    </div>
                </div>

                {/* Layout Controls */}
                <div className="toolbar-section">
                    <label className="toolbar-label">Layout:</label>
                    <select
                        value={selectedLayout}
                        onChange={(e) => handleLayoutChange(e.target.value)}
                        className="layout-select"
                    >
                        {layouts.map(layout => (
                            <option key={layout.value} value={layout.value}>
                                {layout.label}
                            </option>
                        ))}
                    </select>
                </div>

                {/* Zoom Controls */}
                <div className="toolbar-section zoom-controls">
                    <button onClick={() => handleZoom('out')} title="Zoom Out">−</button>
                    <span className="zoom-level">{zoomLevel}%</span>
                    <button onClick={() => handleZoom('in')} title="Zoom In">+</button>
                    <button onClick={handleFit} title="Fit to View">⌴</button>
                    <button onClick={handleCenter} title="Center View">○</button>
                </div>

                {/* Expand/Collapse Toggle */}
                <div className="toolbar-section">
                    <button
                        className="expand-toggle"
                        onClick={() => setIsExpanded(!isExpanded)}
                        title={isExpanded ? 'Collapse toolbar' : 'Expand toolbar'}
                    >
                        {isExpanded ? '▲' : '▼'}
                    </button>
                </div>
            </div>

            {/* Expanded Controls */}
            {isExpanded && (
                <div className="toolbar-expanded">
                    <div className="toolbar-row">
                        {/* Color Scheme */}
                        <div className="toolbar-section">
                            <label className="toolbar-label">Color Scheme:</label>
                            <select
                                value={selectedColorScheme}
                                onChange={(e) => handleColorSchemeChange(e.target.value)}
                                className="scheme-select"
                            >
                                {colorSchemes.map(scheme => (
                                    <option key={scheme.value} value={scheme.value}>
                                        {scheme.label}
                                    </option>
                                ))}
                            </select>
                        </div>

                        {/* Graph Stats */}
                        <div className="toolbar-section graph-stats">
                            <div className="stat-item">
                                <span className="stat-label">Nodes:</span>
                                <span className="stat-value">{graphStats.totalNodes || 0}</span>
                            </div>
                            <div className="stat-item">
                                <span className="stat-label">Edges:</span>
                                <span className="stat-value">{graphStats.totalEdges || 0}</span>
                            </div>
                        </div>
                    </div>

                    {/* Filters */}
                    <div className="toolbar-row">
                        {/* Node Type Filters */}
                        {graphStats.nodeTypes && Object.keys(graphStats.nodeTypes).length > 0 && (
                            <div className="toolbar-section filter-section">
                                <label className="toolbar-label">Node Types:</label>
                                <div className="filter-checkboxes">
                                    {Object.entries(graphStats.nodeTypes).map(([type, count]) => (
                                        <label key={type} className="filter-checkbox">
                                            <input
                                                type="checkbox"
                                                checked={nodeTypeFilters.includes(type)}
                                                onChange={(e) => handleNodeTypeFilterChange(type, e.target.checked)}
                                            />
                                            <span>{type} ({count})</span>
                                        </label>
                                    ))}
                                </div>
                            </div>
                        )}

                        {/* Edge Type Filters */}
                        {graphStats.edgeTypes && Object.keys(graphStats.edgeTypes).length > 0 && (
                            <div className="toolbar-section filter-section">
                                <label className="toolbar-label">Edge Types:</label>
                                <div className="filter-checkboxes">
                                    {Object.entries(graphStats.edgeTypes).map(([type, count]) => (
                                        <label key={type} className="filter-checkbox">
                                            <input
                                                type="checkbox"
                                                checked={edgeTypeFilters.includes(type)}
                                                onChange={(e) => handleEdgeTypeFilterChange(type, e.target.checked)}
                                            />
                                            <span>{type} ({count})</span>
                                        </label>
                                    ))}
                                </div>
                            </div>
                        )}

                        {/* Status Filters */}
                        {graphStats.statusDistribution && Object.keys(graphStats.statusDistribution).length > 0 && (
                            <div className="toolbar-section filter-section">
                                <label className="toolbar-label">Status:</label>
                                <div className="filter-checkboxes">
                                    {Object.entries(graphStats.statusDistribution).map(([status, count]) => (
                                        <label key={status} className="filter-checkbox">
                                            <input
                                                type="checkbox"
                                                checked={statusFilters.includes(status)}
                                                onChange={(e) => handleStatusFilterChange(status, e.target.checked)}
                                            />
                                            <span className={`status-${status.toLowerCase()}`}>
                                                {status} ({count})
                                            </span>
                                        </label>
                                    ))}
                                </div>
                            </div>
                        )}

                        {/* Clear Filters */}
                        <div className="toolbar-section">
                            <button
                                className="clear-filters-btn"
                                onClick={handleClearFilters}
                                title="Clear all filters and search"
                            >
                                Clear All Filters
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
};

export default GraphToolbar;
