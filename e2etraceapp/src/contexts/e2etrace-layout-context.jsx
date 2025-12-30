import React, { createContext, useEffect, useState, useContext } from 'react';
// Keep the rest of the file minimal or commented out for testing

// Define initial layout options, similar to what's in App.jsx
const initialLayoutConfig = {
    name: 'cose-bilkent', // Defaulting to cose-bilkent as per recent request
    animate: true,
    fit: false, // features/dashboard/App.jsx handles fitting manually
    nodeDimensionsIncludeLabels: true,
    // Common parameters for cose-bilkent
    idealEdgeLength: 120,
    nodeRepulsion: 5500,
    edgeElasticity: 0.45,
    nestingFactor: 0.1, // Typically lower for cose-bilkent for tighter compound nodes
    gravity: 0.25, // Default gravity
    numIter: 2500, // Number of iterations
    tile: true, // Tile disconnected components
    // randomize: false, // Not typically needed for cose-bilkent
    padding: 50, // Default padding, can be overridden by PropertyPalette
};

const E2ETraceLayoutContext = createContext({
    layoutConfig: initialLayoutConfig,
    setLayoutConfig: () => {},
    // Add a function to reset to default if needed
    resetLayoutConfig: () => {},
});

export const E2ETraceLayoutProvider = ({ children }) => {
    const [layoutConfig, setLayoutConfig] = useState(() => {
        try {
            const raw = localStorage.getItem('e2etrace-layout-config');
            if (!raw) return initialLayoutConfig;
            const parsed = JSON.parse(raw);
            if (!parsed || typeof parsed !== 'object') return initialLayoutConfig;
            return { ...initialLayoutConfig, ...parsed };
        } catch {
            return initialLayoutConfig;
        }
    });

    useEffect(() => {
        try {
            localStorage.setItem('e2etrace-layout-config', JSON.stringify(layoutConfig));
        } catch {
            // ignore storage failures (private mode, quota, etc)
        }
    }, [layoutConfig]);

    const resetLayoutConfig = () => setLayoutConfig(initialLayoutConfig);

    return (
        <E2ETraceLayoutContext.Provider value={{ layoutConfig, setLayoutConfig, resetLayoutConfig }}>
            {children}
        </E2ETraceLayoutContext.Provider>
    );
};

export const useE2ETraceLayout = () => useContext(E2ETraceLayoutContext);

export const e2etraceUseLayout = useE2ETraceLayout;