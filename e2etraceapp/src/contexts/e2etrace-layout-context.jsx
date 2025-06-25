import React, { createContext, useState, useContext } from 'react';
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
});

export const E2ETraceLayoutProvider = ({ children }) => {
    const [layoutConfig, setLayoutConfig] = useState(initialLayoutConfig);

    return (
        <E2ETraceLayoutContext.Provider value={{ layoutConfig, setLayoutConfig }}>
            {children}
        </E2ETraceLayoutContext.Provider>
    );
};

export const e2etraceUseLayout = () => useContext(E2ETraceLayoutContext);