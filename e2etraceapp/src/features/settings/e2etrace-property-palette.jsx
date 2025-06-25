import React, { useState, useEffect } from 'react';
import { e2etraceUseLayout } from '../../contexts/e2etrace-layout-context'; // Corrected hook name
import './e2etrace-property-palette.css';
import { E2ETraceUIPanel } from '../../components/e2etrace-ui-panel';
import { e2etraceUseDebounce } from '../../hooks/e2etrace-use-debounce'; // For real-time updates

const layoutDefinitions = {
    'fcose': { // Corrected key for fCOSE
        displayName: 'fCOSE',
        params: [
            { name: 'quality', type: 'select', options: ['default', 'proof'], defaultValue: 'default' },
            { name: 'idealEdgeLength', type: 'number', defaultValue: 100, min: 10, max: 500, step: 10 },
            { name: 'nodeRepulsion', type: 'number', defaultValue: 4500, min: 100, max: 50000, step: 100 },
            { name: 'edgeElasticity', type: 'number', defaultValue: 0.45, min: 0.01, max: 1, step: 0.01 },
            { name: 'gravity', type: 'number', defaultValue: 0.25, min: 0, max: 1, step: 0.01 },
            { name: 'padding', type: 'number', defaultValue: 50, min: 0, max: 200, step: 5 },
            { name: 'nodeDimensionsIncludeLabels', type: 'boolean', defaultValue: true },
            { name: 'animate', type: 'boolean', defaultValue: true },
        ],
    },
    'cose-bilkent': { // Corrected definition for COSE Bilkent
        displayName: 'COSE Bilkent',
        params: [
            { name: 'idealEdgeLength', type: 'number', defaultValue: 120, min: 10, max: 500, step: 10 },
            { name: 'nodeRepulsion', type: 'number', defaultValue: 5500, min: 100, max: 50000, step: 100 },
            { name: 'edgeElasticity', type: 'number', defaultValue: 0.45, min: 0.01, max: 1, step: 0.01 },
            { name: 'nestingFactor', type: 'number', defaultValue: 0.1, min: 0, max: 1, step: 0.01 },
            { name: 'gravity', type: 'number', defaultValue: 0.25, min: 0, max: 1, step: 0.01 },
            { name: 'numIter', type: 'number', defaultValue: 2500, min: 100, max: 10000, step: 100 },
            { name: 'padding', type: 'number', defaultValue: 50, min: 0, max: 200, step: 5 },
            { name: 'nodeDimensionsIncludeLabels', type: 'boolean', defaultValue: true },
            { name: 'tile', type: 'boolean', defaultValue: true }, // Whether to tile disconnected components
            { name: 'animate', type: 'boolean', defaultValue: true },
        ],
    },
};

const E2ETracePropertyPalette = () => {
    const { layoutConfig, setLayoutConfig } = e2etraceUseLayout();

    const [selectedLayoutName, setSelectedLayoutName] = useState(layoutConfig.name);
    const [currentProps, setCurrentProps] = useState({});
    const debouncedProps = e2etraceUseDebounce(currentProps, 500); // Debounce changes for 500ms

    useEffect(() => {
        // Initialize currentProps when selectedLayoutName changes or on initial load
        const definition = layoutDefinitions[selectedLayoutName];
        if (definition) {
            const initialProps = {};
            definition.params.forEach(param => {
                // When switching layouts, always start with the new layout's defaults
                initialProps[param.name] = param.defaultValue;
            });
            setCurrentProps(initialProps);
        }
    }, [selectedLayoutName]); // Rerun only when the layout *name* changes

    // This effect listens for debounced changes and applies them to the global context
    useEffect(() => {
        if (Object.keys(debouncedProps).length > 0) {
            setLayoutConfig({
                name: selectedLayoutName,
                ...debouncedProps,
                fit: false, // Always ensure fit is false as App.jsx handles it
            });
        }
    }, [debouncedProps, selectedLayoutName, setLayoutConfig]);

    const handleLayoutChange = (e) => {
        setSelectedLayoutName(e.target.value);
    };

    const handlePropChange = (paramName, value, type) => {
        setCurrentProps(prev => ({
            ...prev,
            [paramName]: type === 'number' ? parseFloat(value) : (type === 'boolean' ? (value === 'true' || value === true) : value),
        }));
    };

    const selectedDefinition = layoutDefinitions[selectedLayoutName];

    return (
        <E2ETraceUIPanel className="e2etrace-property-palette-container e2etrace-card-like"> {/* Use the new Panel component */}
            <h2>E2ETrace Graph Layout Settings</h2>
            <div className="e2etrace-palette-section"> {/* Corrected class name */}
                <div className="e2etrace-form-group"> {/* Corrected class name */}
                    <label htmlFor="layout-select">Select Layout:</label>
                    <select
                        id="layout-select"
                        value={selectedLayoutName}
                        onChange={handleLayoutChange}
                    >
                        {Object.entries(layoutDefinitions).map(([name, def]) => (
                            <option key={name} value={name}>
                                {def.displayName}
                            </option>
                        ))}
                    </select>
                </div>
            </div>

            <div className="e2etrace-palette-controls"> {/* Corrected class name */}
                 {selectedDefinition && selectedDefinition.params.map(param => (
                    <div key={param.name} className="e2etrace-form-group"> {/* Corrected class name */}
                        <label htmlFor={`param-${param.name}`}>{param.name}:</label>
                        {param.type === 'number' && (
                            <input
                                type="range" // Using range for slider-like behavior
                                id={`param-${param.name}`}
                                value={currentProps[param.name] || param.defaultValue}
                                min={param.min}
                                max={param.max}
                                step={param.step}
                                onChange={(e) => handlePropChange(param.name, e.target.value, 'number')}
                            />
                        )}
                        {param.type === 'boolean' && (
                            <input
                                type="checkbox"
                                id={`param-${param.name}`}
                                checked={currentProps[param.name] === undefined ? param.defaultValue : currentProps[param.name]}
                                onChange={(e) => handlePropChange(param.name, e.target.checked, 'boolean')}
                            />
                        )}
                        {param.type === 'select' && (
                             <select
                                id={`param-${param.name}`}
                                value={currentProps[param.name] || param.defaultValue}
                                onChange={(e) => handlePropChange(param.name, e.target.value, 'select')}
                            >
                                {param.options.map(opt => <option key={opt} value={opt}>{opt}</option>)}
                            </select>
                        )}
                         {param.type === 'number' && <span className="e2etrace-param-value-display">{currentProps[param.name] !== undefined ? currentProps[param.name] : param.defaultValue}</span>} {/* Corrected class name */}
                    </div>
                ))}
            </div>

            {/* NDL Theme Customization Section Removed */}
            {/* <hr className="palette-divider" />
            <h2>Theme Customization (NDL Overrides)</h2> ... */}

            <div className="e2etrace-palette-actions"> {/* Corrected class name */}
                <span className="e2etrace-autosave-indicator">Settings are applied automatically.</span> {/* Corrected class name */}
                <button className="e2etrace-palette-button e2etrace-back" onClick={() => window.location.hash = '/'}>Back to Graph</button> {/* Corrected class name */}
            </div> 
        </E2ETraceUIPanel>
    );
};

export default E2ETracePropertyPalette;