/**
 * PLM Migration Statechart Visualizer Component
 * Renders an interactive state machine visualization
 */
import React, { useState, useEffect, useRef } from 'react';
import { plmMigrationMachine, getStateConfig, getAvailableActions } from '../../machines/plmMigrationMachine.js';
import './PLMMigrationStatechartVisualizer.css';

const PLMMigrationStatechartVisualizer = ({ currentState, onNavigate }) => {
  const [hoveredState, setHoveredState] = useState(null);
  const [selectedState, setSelectedState] = useState(null);
  const containerRef = useRef(null);

  useEffect(() => {
    setSelectedState(currentState);
  }, [currentState]);

  const handleStateClick = (stateName, stateConfig) => {
    setSelectedState(stateName);
    
    // Navigate to configuration page if available
    if (stateConfig.metadata?.configPage && onNavigate) {
      onNavigate(stateConfig.metadata.configPage);
    }
  };

  const handleKeyPress = (e, stateName, stateConfig) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      handleStateClick(stateName, stateConfig);
    }
  };

  const renderStateNode = (stateName, stateConfig) => {
    const isActive = stateName === currentState;
    const isHovered = stateName === hoveredState;
    const isSelected = stateName === selectedState;
    const isFinal = stateConfig.metadata?.final;
    const isError = stateConfig.metadata?.error;
    const hasProgress = stateConfig.metadata?.progress;

    const className = [
      'state-node',
      isActive && 'state-node-active',
      isHovered && 'state-node-hovered',
      isSelected && 'state-node-selected',
      isFinal && 'state-node-final',
      isError && 'state-node-error'
    ].filter(Boolean).join(' ');

    return (
      <div
        key={stateName}
        className={className}
        style={{
          backgroundColor: isActive ? stateConfig.color : 'transparent',
          borderColor: stateConfig.color
        }}
        onClick={() => handleStateClick(stateName, stateConfig)}
        onMouseEnter={() => setHoveredState(stateName)}
        onMouseLeave={() => setHoveredState(null)}
        onKeyPress={(e) => handleKeyPress(e, stateName, stateConfig)}
        tabIndex={0}
        role="button"
        aria-label={`${stateConfig.label} state. ${stateConfig.description}`}
        aria-pressed={isActive}
      >
        <div className="state-node-content">
          <div className="state-node-label">{stateConfig.label}</div>
          {hasProgress && isActive && (
            <div className="state-node-spinner">
              <div className="spinner-border spinner-border-sm" role="status">
                <span className="visually-hidden">Loading...</span>
              </div>
            </div>
          )}
        </div>
        {(isHovered || isSelected) && (
          <div className="state-node-tooltip">
            {stateConfig.description}
            {stateConfig.metadata?.configPage && (
              <div className="state-node-tooltip-action">
                Click to configure
              </div>
            )}
          </div>
        )}
      </div>
    );
  };

  const renderStateTransition = (fromState, toState, event) => {
    const fromConfig = getStateConfig(fromState);
    const toConfig = getStateConfig(toState);
    
    if (!fromConfig || !toConfig) return null;

    return (
      <div key={`${fromState}-${toState}`} className="state-transition">
        <div className="transition-arrow" aria-hidden="true">→</div>
        <div className="transition-label">{event}</div>
      </div>
    );
  };

  return (
    <div className="plm-migration-statechart" ref={containerRef}>
      <div className="statechart-header">
        <h3>Migration State Flow</h3>
        <div className="statechart-legend">
          <div className="legend-item">
            <div className="legend-dot" style={{ backgroundColor: '#007bff' }}></div>
            <span>In Progress</span>
          </div>
          <div className="legend-item">
            <div className="legend-dot" style={{ backgroundColor: '#28a745' }}></div>
            <span>Completed</span>
          </div>
          <div className="legend-item">
            <div className="legend-dot" style={{ backgroundColor: '#dc3545' }}></div>
            <span>Error</span>
          </div>
          <div className="legend-item">
            <div className="legend-dot" style={{ backgroundColor: '#ffc107' }}></div>
            <span>Paused</span>
          </div>
        </div>
      </div>

      <div className="statechart-container">
        {/* Initial states */}
        <div className="state-row">
          {renderStateNode('idle', plmMigrationMachine.states.idle)}
          {renderStateNode('initializing', plmMigrationMachine.states.initializing)}
        </div>

        {/* Processing states */}
        <div className="state-row">
          {renderStateNode('discovering', plmMigrationMachine.states.discovering)}
          {renderStateNode('profiling', plmMigrationMachine.states.profiling)}
          {renderStateNode('schema_mapping', plmMigrationMachine.states.schema_mapping)}
        </div>

        <div className="state-row">
          {renderStateNode('data_migration', plmMigrationMachine.states.data_migration)}
          {renderStateNode('validation', plmMigrationMachine.states.validation)}
        </div>

        {/* Terminal states */}
        <div className="state-row">
          {renderStateNode('paused', plmMigrationMachine.states.paused)}
          {renderStateNode('completed', plmMigrationMachine.states.completed)}
          {renderStateNode('failed', plmMigrationMachine.states.failed)}
          {renderStateNode('cancelled', plmMigrationMachine.states.cancelled)}
        </div>
      </div>

      {/* State details panel */}
      {selectedState && (
        <div className="state-details-panel">
          <h4>{getStateConfig(selectedState)?.label}</h4>
          <p>{getStateConfig(selectedState)?.description}</p>
          {getStateConfig(selectedState)?.metadata?.configPage && (
            <div className="state-details-actions">
              <button
                className="btn btn-sm btn-primary"
                onClick={() => onNavigate && onNavigate(getStateConfig(selectedState).metadata.configPage)}
              >
                Configure
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default PLMMigrationStatechartVisualizer;
