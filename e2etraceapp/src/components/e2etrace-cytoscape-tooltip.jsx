import React, { useState, useEffect, useRef } from 'react';
import './e2etrace-cytoscape-tooltip.css';

/**
 * Cytoscape Tooltip Component
 * Provides rich tooltips for nodes and edges in Cytoscape graphs
 */
const CytoscapeTooltip = ({ cytoscapeRef }) => {
    const [tooltip, setTooltip] = useState({
        visible: false,
        x: 0,
        y: 0,
        content: null,
        type: null
    });
    
    const tooltipRef = useRef(null);
    const timeoutRef = useRef(null);

    useEffect(() => {
        if (!cytoscapeRef?.current) return;

        const cy = cytoscapeRef.current;

        // Helper function to get node tooltip content
        const getNodeTooltipContent = (node) => {
            const data = node.data();
            const position = node.renderedPosition();
            
            return {
                type: 'node',
                title: data.label || data.id,
                content: {
                    id: data.id,
                    type: data.type || data.group || 'Unknown',
                    status: data.status,
                    properties: data.properties || {},
                    description: data.description,
                    metrics: data.metrics || {}
                },
                position: {
                    x: position.x,
                    y: position.y
                }
            };
        };

        // Helper function to get edge tooltip content
        const getEdgeTooltipContent = (edge) => {
            const data = edge.data();
            const midpoint = edge.renderedMidpoint();
            
            return {
                type: 'edge',
                title: data.label || `${data.source} → ${data.target}`,
                content: {
                    id: data.id,
                    source: data.source,
                    target: data.target,
                    type: data.type || 'connection',
                    weight: data.weight,
                    properties: data.properties || {},
                    description: data.description
                },
                position: {
                    x: midpoint.x,
                    y: midpoint.y
                }
            };
        };

        // Show tooltip on hover
        const showTooltip = (evt) => {
            if (timeoutRef.current) {
                clearTimeout(timeoutRef.current);
            }

            timeoutRef.current = setTimeout(() => {
                const target = evt.target;
                let tooltipData;

                if (target === cy) return;

                if (target.isNode()) {
                    tooltipData = getNodeTooltipContent(target);
                } else if (target.isEdge()) {
                    tooltipData = getEdgeTooltipContent(target);
                } else {
                    return;
                }

                setTooltip({
                    visible: true,
                    x: tooltipData.position.x,
                    y: tooltipData.position.y,
                    content: tooltipData.content,
                    title: tooltipData.title,
                    type: tooltipData.type
                });
            }, 500); // 500ms delay before showing tooltip
        };

        // Hide tooltip
        const hideTooltip = () => {
            if (timeoutRef.current) {
                clearTimeout(timeoutRef.current);
            }
            setTooltip(prev => ({ ...prev, visible: false }));
        };

        // Event listeners
        cy.on('mouseover', 'node, edge', showTooltip);
        cy.on('mouseout', 'node, edge', hideTooltip);
        cy.on('pan zoom', hideTooltip);
        cy.on('select unselect', hideTooltip);

        return () => {
            cy.off('mouseover', 'node, edge', showTooltip);
            cy.off('mouseout', 'node, edge', hideTooltip);
            cy.off('pan zoom', hideTooltip);
            cy.off('select unselect', hideTooltip);
            if (timeoutRef.current) {
                clearTimeout(timeoutRef.current);
            }
        };
    }, [cytoscapeRef]);

    // Position the tooltip to avoid going off-screen
    useEffect(() => {
        if (tooltip.visible && tooltipRef.current) {
            const tooltipEl = tooltipRef.current;
            const rect = tooltipEl.getBoundingClientRect();
            const viewportWidth = window.innerWidth;
            const viewportHeight = window.innerHeight;

            let adjustedX = tooltip.x;
            let adjustedY = tooltip.y - 10; // Offset above cursor

            // Adjust horizontal position
            if (adjustedX + rect.width > viewportWidth - 20) {
                adjustedX = tooltip.x - rect.width - 20;
            }

            // Adjust vertical position
            if (adjustedY + rect.height > viewportHeight - 20) {
                adjustedY = tooltip.y - rect.height - 20;
            }

            tooltipEl.style.left = `${Math.max(10, adjustedX)}px`;
            tooltipEl.style.top = `${Math.max(10, adjustedY)}px`;
        }
    }, [tooltip]);

    if (!tooltip.visible || !tooltip.content) {
        return null;
    }

    const renderNodeTooltip = () => (
        <div className="tooltip-content">
            <div className="tooltip-header">
                <h4 className="tooltip-title">{tooltip.title}</h4>
                <span className={`tooltip-type tooltip-type-${tooltip.content.type?.toLowerCase()}`}>
                    {tooltip.content.type}
                </span>
            </div>
            
            <div className="tooltip-body">
                {tooltip.content.status && (
                    <div className="tooltip-field">
                        <span className="tooltip-label">Status:</span>
                        <span className={`tooltip-status tooltip-status-${tooltip.content.status?.toLowerCase()}`}>
                            {tooltip.content.status}
                        </span>
                    </div>
                )}
                
                <div className="tooltip-field">
                    <span className="tooltip-label">ID:</span>
                    <span className="tooltip-value">{tooltip.content.id}</span>
                </div>
                
                {tooltip.content.description && (
                    <div className="tooltip-field">
                        <span className="tooltip-label">Description:</span>
                        <span className="tooltip-value">{tooltip.content.description}</span>
                    </div>
                )}
                
                {Object.keys(tooltip.content.properties).length > 0 && (
                    <div className="tooltip-section">
                        <div className="tooltip-section-title">Properties</div>
                        {Object.entries(tooltip.content.properties).map(([key, value]) => (
                            <div key={key} className="tooltip-field">
                                <span className="tooltip-label">{key}:</span>
                                <span className="tooltip-value">
                                    {typeof value === 'object' ? JSON.stringify(value, null, 2) : String(value)}
                                </span>
                            </div>
                        ))}
                    </div>
                )}
                
                {Object.keys(tooltip.content.metrics).length > 0 && (
                    <div className="tooltip-section">
                        <div className="tooltip-section-title">Metrics</div>
                        {Object.entries(tooltip.content.metrics).map(([key, value]) => (
                            <div key={key} className="tooltip-field">
                                <span className="tooltip-label">{key}:</span>
                                <span className="tooltip-value">{value}</span>
                            </div>
                        ))}
                    </div>
                )}
            </div>
        </div>
    );

    const renderEdgeTooltip = () => (
        <div className="tooltip-content">
            <div className="tooltip-header">
                <h4 className="tooltip-title">{tooltip.title}</h4>
                <span className={`tooltip-type tooltip-type-${tooltip.content.type?.toLowerCase()}`}>
                    {tooltip.content.type}
                </span>
            </div>
            
            <div className="tooltip-body">
                <div className="tooltip-field">
                    <span className="tooltip-label">From:</span>
                    <span className="tooltip-value">{tooltip.content.source}</span>
                </div>
                
                <div className="tooltip-field">
                    <span className="tooltip-label">To:</span>
                    <span className="tooltip-value">{tooltip.content.target}</span>
                </div>
                
                {tooltip.content.weight !== undefined && (
                    <div className="tooltip-field">
                        <span className="tooltip-label">Weight:</span>
                        <span className="tooltip-value">{tooltip.content.weight}</span>
                    </div>
                )}
                
                {tooltip.content.description && (
                    <div className="tooltip-field">
                        <span className="tooltip-label">Description:</span>
                        <span className="tooltip-value">{tooltip.content.description}</span>
                    </div>
                )}
                
                {Object.keys(tooltip.content.properties).length > 0 && (
                    <div className="tooltip-section">
                        <div className="tooltip-section-title">Properties</div>
                        {Object.entries(tooltip.content.properties).map(([key, value]) => (
                            <div key={key} className="tooltip-field">
                                <span className="tooltip-label">{key}:</span>
                                <span className="tooltip-value">
                                    {typeof value === 'object' ? JSON.stringify(value, null, 2) : String(value)}
                                </span>
                            </div>
                        ))}
                    </div>
                )}
            </div>
        </div>
    );

    return (
        <div
            ref={tooltipRef}
            className={`cytoscape-tooltip ${tooltip.visible ? 'visible' : ''} tooltip-${tooltip.type}`}
            style={{
                position: 'fixed',
                left: tooltip.x,
                top: tooltip.y,
                pointerEvents: 'none',
                zIndex: 10000
            }}
        >
            {tooltip.type === 'node' ? renderNodeTooltip() : renderEdgeTooltip()}
        </div>
    );
};

export default CytoscapeTooltip;
