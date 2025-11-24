/**
 * XState Visualizer Demo Page
 * Demonstrates the XState visualizer with sample migration state machine
 */

import React, { useState } from 'react';
import XStateVisualizer from '../../components/XStateVisualizer';
import './XStateVisualizerPage.css';

const XStateVisualizerPage = () => {
  const [selectedExample, setSelectedExample] = useState('migration');

  // Sample state machines
  const examples = {
    migration: {
      name: 'Migration State Machine',
      states: [
        { id: 'idle', name: 'Idle', type: 'initial' },
        { id: 'discovering', name: 'Discovering', type: 'normal', metadata: { phase: 'discovery' } },
        { id: 'validating', name: 'Validating', type: 'normal', metadata: { phase: 'validation' } },
        { id: 'migrating', name: 'Migrating', type: 'active', metadata: { phase: 'migration' } },
        { id: 'verifying', name: 'Verifying', type: 'normal', metadata: { phase: 'verification' } },
        { id: 'completed', name: 'Completed', type: 'final' },
        { id: 'failed', name: 'Failed', type: 'final' }
      ],
      transitions: [
        { from: 'idle', to: 'discovering', event: 'START' },
        { from: 'discovering', to: 'validating', event: 'DISCOVERED' },
        { from: 'discovering', to: 'failed', event: 'ERROR' },
        { from: 'validating', to: 'migrating', event: 'VALIDATED' },
        { from: 'validating', to: 'failed', event: 'INVALID' },
        { from: 'migrating', to: 'verifying', event: 'MIGRATED' },
        { from: 'migrating', to: 'failed', event: 'ERROR' },
        { from: 'migrating', to: 'migrating', event: 'PROGRESS' },
        { from: 'verifying', to: 'completed', event: 'VERIFIED' },
        { from: 'verifying', to: 'failed', event: 'VERIFICATION_FAILED' },
        { from: 'failed', to: 'idle', event: 'RESET' },
        { from: 'completed', to: 'idle', event: 'RESET' }
      ]
    },
    
    dataProcessing: {
      name: 'Data Processing Pipeline',
      states: [
        { id: 'pending', name: 'Pending', type: 'initial' },
        { id: 'extracting', name: 'Extracting', type: 'normal' },
        { id: 'transforming', name: 'Transforming', type: 'normal' },
        { id: 'loading', name: 'Loading', type: 'normal' },
        { id: 'success', name: 'Success', type: 'final' },
        { id: 'error', name: 'Error', type: 'final' }
      ],
      transitions: [
        { from: 'pending', to: 'extracting', event: 'START' },
        { from: 'extracting', to: 'transforming', event: 'EXTRACTED' },
        { from: 'extracting', to: 'error', event: 'EXTRACT_FAILED' },
        { from: 'transforming', to: 'loading', event: 'TRANSFORMED' },
        { from: 'transforming', to: 'error', event: 'TRANSFORM_FAILED' },
        { from: 'loading', to: 'success', event: 'LOADED' },
        { from: 'loading', to: 'error', event: 'LOAD_FAILED' },
        { from: 'error', to: 'pending', event: 'RETRY' }
      ]
    },

    graphQL: {
      name: 'GraphQL Query Lifecycle',
      states: [
        { id: 'init', name: 'Init', type: 'initial' },
        { id: 'parsing', name: 'Parsing', type: 'normal' },
        { id: 'validating', name: 'Validating', type: 'normal' },
        { id: 'executing', name: 'Executing', type: 'normal' },
        { id: 'resolving', name: 'Resolving', type: 'normal' },
        { id: 'complete', name: 'Complete', type: 'final' },
        { id: 'error', name: 'Error', type: 'final' }
      ],
      transitions: [
        { from: 'init', to: 'parsing', event: 'QUERY_RECEIVED' },
        { from: 'parsing', to: 'validating', event: 'PARSED' },
        { from: 'parsing', to: 'error', event: 'PARSE_ERROR' },
        { from: 'validating', to: 'executing', event: 'VALID' },
        { from: 'validating', to: 'error', event: 'VALIDATION_ERROR' },
        { from: 'executing', to: 'resolving', event: 'QUERY_EXECUTED' },
        { from: 'executing', to: 'error', event: 'EXECUTION_ERROR' },
        { from: 'resolving', to: 'complete', event: 'RESOLVED' },
        { from: 'resolving', to: 'error', event: 'RESOLUTION_ERROR' }
      ]
    }
  };

  const handleNodeClick = (nodeData) => {
    console.log('Node clicked:', nodeData);
  };

  return (
    <div className="xstate-visualizer-page">
      <div className="page-header">
        <h1><i className="fas fa-bolt"></i> World-Class XState Visualizer</h1>
        <p>Graph-as-UI Experience • Living Circuit Board • Semantic Zoom Canvas</p>
      </div>

      <div className="example-selector">
        <h3>Select State Machine Example:</h3>
        <div className="selector-buttons">
          {Object.entries(examples).map(([key, example]) => (
            <button
              key={key}
              className={`selector-btn ${selectedExample === key ? 'active' : ''}`}
              onClick={() => setSelectedExample(key)}
            >
              {example.name}
            </button>
          ))}
        </div>
      </div>

      <div className="visualizer-container">
        <XStateVisualizer
          stateData={examples[selectedExample]}
          onNodeClick={handleNodeClick}
        />
      </div>

      <div className="legend">
        <h3>State Semantics</h3>
        <div className="legend-items">
          <div className="legend-item">
            <div className="legend-color node-state-initial"></div>
            <span className="legend-label">Initial State</span>
          </div>
          <div className="legend-item">
            <div className="legend-color node-state-active"></div>
            <span className="legend-label">Active/Current State</span>
          </div>
          <div className="legend-item">
            <div className="legend-color node-state-success"></div>
            <span className="legend-label">Success State</span>
          </div>
          <div className="legend-item">
            <div className="legend-color node-state-error"></div>
            <span className="legend-label">Error State</span>
          </div>
          <div className="legend-item">
            <div className="legend-color node-state-final"></div>
            <span className="legend-label">Final State</span>
          </div>
          <div className="legend-item">
            <div className="legend-color node-state-compound"></div>
            <span className="legend-label">Compound State</span>
          </div>
        </div>
      </div>

      <div className="features">
        <h3><i className="fas fa-gamepad"></i> Game-Like Features</h3>
        <ul>
          <li>Semantic Zoom Canvas (Infinite pan & zoom)</li>
          <li>Fog of War Progressive Disclosure</li>
          <li>Living Circuit Board Metaphor</li>
          <li>Edge-as-Action Interaction</li>
          <li>Data-Rich Node Architecture</li>
          <li>Guard Violation Feedback</li>
          <li>Context Inspector HUD</li>
          <li>Multiple Layout Algorithms</li>
          <li>Export to PNG with Effects</li>
          <li>Mobile Stack Adaptation</li>
        </ul>
      </div>
    </div>
  );
};

export default XStateVisualizerPage;
