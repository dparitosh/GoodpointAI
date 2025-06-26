import React, { useState } from 'react';
import { E2ETraceGraphLegend } from '../pages/dashboard/components/e2etrace-graph-legend';
import './e2etrace-graph-legend-dropdown.css';

export function E2ETraceGraphLegendDropdown({ stylesheet }) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <button
        className="e2etrace-legend-dropdown-toggle"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        aria-label="Show graph legend"
      >
        Legend
      </button>
      {open && (
        <div className="e2etrace-legend-dropdown-overlay">
          <E2ETraceGraphLegend stylesheet={stylesheet} />
        </div>
      )}
    </>
  );
}
