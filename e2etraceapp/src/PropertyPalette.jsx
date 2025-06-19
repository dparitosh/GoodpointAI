import React, { useState, useEffect } from 'react';
import { useLayout } from './LayoutContext';
import './PropertyPalette.css'; // We'll create this CSS file

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

const PropertyPalette = () => {
    const { layoutConfig, setLayoutConfig } = useLayout();

    const [selectedLayoutName, setSelectedLayoutName] = useState(layoutConfig.name);
    const [currentProps, setCurrentProps] = useState({});

    useEffect(() => {
        // Initialize currentProps when selectedLayoutName changes or on initial load
        const definition = layoutDefinitions[selectedLayoutName];
        if (definition) {
            const initialProps = {};
            definition.params.forEach(param => {
                // Use existing value from context if available for this layout, else default
                initialProps[param.name] = (layoutConfig.name === selectedLayoutName && layoutConfig[param.name] !== undefined)
                    ? layoutConfig[param.name]
                    : param.defaultValue;
            });
            setCurrentProps(initialProps);
        }
    }, [selectedLayoutName, layoutConfig]);

    const handleLayoutChange = (e) => {
        setSelectedLayoutName(e.target.value);
    };

    const handlePropChange = (paramName, value, type) => {
        setCurrentProps(prev => ({
            ...prev,
            [paramName]: type === 'number' ? parseFloat(value) : (type === 'boolean' ? (value === 'true' || value === true) : value),
        }));
    };

    const handleApplyChanges = () => {
        const newConfig = {
            name: selectedLayoutName,
            ...currentProps,
            fit: false, // Always ensure fit is false as App.jsx handles it
        };
        setLayoutConfig(newConfig);
        alert('Layout settings applied! Navigate back to see the changes.');
        // Optionally navigate back automatically: window.location.hash = '/';
    };

    const selectedDefinition = layoutDefinitions[selectedLayoutName];

    return (
        <div className="property-palette-container card-like"> {/* Added card-like for basic styling */}
            <h2>Graph Layout Settings</h2>
            <div className="palette-section">
                <div className="form-group">
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

            <div className="palette-controls">
                 {selectedDefinition && selectedDefinition.params.map(param => (
                    <div key={param.name} className="form-group">
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
                         {param.type === 'number' && <span className="param-value-display">{currentProps[param.name] !== undefined ? currentProps[param.name] : param.defaultValue}</span>}
                    </div>
                ))}
            </div>

            {/* NDL Theme Customization Section Removed */}
            {/* <hr className="palette-divider" />
            <h2>Theme Customization (NDL Overrides)</h2> ... */}

            <div className="palette-actions">
                <button className="palette-button apply" onClick={handleApplyChanges}>Apply Layout</button>
                <button className="palette-button back" onClick={() => window.location.hash = '/'}>Back to Graph</button>
            </div>
        </div>
    );
};

export default PropertyPalette;