import React, { useMemo } from 'react';
import { E2ETraceUIPanel } from '../../../components/e2etrace-ui-panel';

export const E2ETraceGraphLegend = ({ stylesheet }) => {
    // Extract unique node group styles from the stylesheet
    const nodeGroupStyles = useMemo(() => {
        const groups = {};
        stylesheet.forEach(rule => {
            if (rule.selector.startsWith('node[group="')) {
                const groupName = rule.selector.match(/node\[group="([^"]+)"\]/)[1];
                groups[groupName] = {
                    backgroundColor: rule.style['background-color'],
                    shape: rule.style.shape,
                    color: rule.style.color, // Text color
                };
            } else if (rule.selector === 'node') {
                // Default node style
                groups['Default Node'] = {
                    backgroundColor: rule.style['background-color'],
                    shape: rule.style.shape,
                    color: rule.style.color,
                };
            } else if (rule.selector === 'node[group="DataQualityIssue"]') {
                groups['Data Quality Issue'] = {
                    backgroundColor: rule.style['background-color'],
                    shape: rule.style.shape,
                    color: rule.style.color,
                };
            }
        });
        return groups;
    }, [stylesheet]);

    return (
        <E2ETraceUIPanel className="e2etrace-graph-legend">
            <h3>Graph Legend</h3>
            <div className="e2etrace-legend-items">
                {Object.entries(nodeGroupStyles).map(([group, style]) => (
                    <div key={group} className="e2etrace-legend-item">
                        <div
                            className={`e2etrace-legend-shape ${style.shape}`}
                            style={{ backgroundColor: style.backgroundColor, borderColor: style.backgroundColor }}
                        >
                            {style.shape === 'diamond' && <i className="fas fa-square" style={{transform: 'rotate(45deg)'}} aria-hidden="true" />} {/* Simple representation for diamond */}
                            {/* Add more specific shape representations if needed */}
                        </div>
                        <span>{group}</span>
                    </div>
                ))}
                {/* Add edge legend if needed */}
                <div className="e2etrace-legend-item">
                    <div className="e2etrace-legend-color-box" style={{ backgroundColor: 'var(--cy-critical-color)' }}></div>
                    <span>Critical Relationship</span>
                </div>
            </div>
        </E2ETraceUIPanel>
    );
};