import React from 'react';
import { E2ETraceUIPanel } from '../../../components/e2etrace-ui-panel';

export const E2ETraceGraphFilter = ({ filterText, onFilterTextChange }) => {
    return (
        <E2ETraceUIPanel className="e2etrace-graph-filter-panel">
            <h3>Graph Filter</h3>
            <input
                type="text"
                placeholder="Filter graph by ID, label, group, or properties..."
                value={filterText}
                onChange={(e) => onFilterTextChange(e.target.value)}
                aria-label="Graph filter input"
            />
        </E2ETraceUIPanel>
    );
};