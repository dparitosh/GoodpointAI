/**
 * Admin Configuration Manager (Refactored)
 * 
 * Decomposed from monolithic 2,324-line component into modular architecture
 * - State management via custom hooks (useAdminConfigState)
 * - API operations via custom hooks (useConfigAPI)
 * - Sub-components extracted to separate files
 * - Utility functions extracted to modules
 * - Forms extracted to separate components
 * 
 * This component is now ~250 lines focusing on layout and orchestration
 */

import React, { useEffect } from 'react';

// Import hooks for state and API
import { useAdminConfigState, useConfigAPI } from './hooks';

// Import shared components
import { TabNavigation, Modal } from './components';

// Import table components
import {
  LLMProvidersTable,
  EmbeddingModelsTable,
  ConnectionsTable,
  SystemSettingsTable,
  FeatureFlagsTable
} from './components/Tables';

// Import form components
import {
  EmbeddingModelForm,
  LLMProviderForm,
  SystemSettingForm,
  FeatureFlagForm,
  ConnectionForm
} from './forms';

// Import validators
import { getSaveDisabledReason } from './utils/validators';

export function AdminConfigManager() {
  // Initialize state management hook
  const state = useAdminConfigState();
  
  // Get API operations hook
  const api = useConfigAPI(state, state.showMessage);

  // Fetch data on component mount
  useEffect(() => {
    api.fetchData();
  }, [api]);

  // Tab configuration
  const tabs = [
    { 
      id: 'llm', 
      label: 'LLM Providers', 
      icon: 'fas fa-brain', 
      count: state.data.llmProviders.length 
    },
    { 
      id: 'embedding', 
      label: 'Embedding Models', 
      icon: 'fas fa-vector-square', 
      count: state.data.embeddingModels.length 
    },
    { 
      id: 'connections', 
      label: 'Connection Settings (Data Sources)', 
      icon: 'fas fa-plug', 
      count: state.data.connections.length 
    },
    { 
      id: 'settings', 
      label: 'System Settings', 
      icon: 'fas fa-cog', 
      count: state.data.systemConfigs.length 
    },
    { 
      id: 'flags', 
      label: 'Feature Flags', 
      icon: 'fas fa-flag', 
      count: state.data.featureFlags.length 
    }
  ];

  // Open modal with optional item for editing
  const openModal = (type, item = null) => {
    state.setModalType(type);
    if (type === 'connection' && item) {
      const sanitized = { ...item };
      // Avoid accidentally persisting masked secrets back to the server
      if (typeof sanitized.connection_string === 'string' && sanitized.connection_string.includes('*')) {
        sanitized.connection_string = '';
      }
      state.setEditItem({ ...sanitized, _isNew: false });
    } else {
      if (item) {
        state.setEditItem({ ...item, _isNew: false });
      } else {
        state.setEditItem({ _isNew: true });
      }
    }
    state.setModalOpen(true);
  };

  // Render content based on active tab
  const renderContent = () => {
    switch (state.activeTab) {
      case 'llm':
        return (
          <div className="admin-config-content">
            <div className="config-section-header">
              <h3>LLM Provider Configurations</h3>
              <button className="btn-primary" onClick={() => openModal('llm')}>
                <i className="fas fa-plus"></i> Add Provider
              </button>
            </div>
            <LLMProvidersTable
              providers={state.data.llmProviders}
              onEdit={(p) => openModal('llm', p)}
              onDelete={(id) => api.handleDelete('llm', id)}
              onTest={api.handleTestLLM}
              testingId={state.testingId}
            />
          </div>
        );

      case 'embedding':
        return (
          <div className="admin-config-content">
            <div className="config-section-header">
              <h3>Embedding Model Configurations</h3>
              <button className="btn-primary" onClick={() => openModal('embedding')}>
                <i className="fas fa-plus"></i> Add Model
              </button>
            </div>
            <EmbeddingModelsTable
              models={state.data.embeddingModels}
              onEdit={(m) => openModal('embedding', m)}
              onDelete={(id) => api.handleDelete('embedding', id)}
              onTest={api.handleTestEmbedding}
              testingId={state.testingId}
            />
          </div>
        );

      case 'connections':
        return (
          <div className="admin-config-content">
            <div className="config-section-header">
              <h3>Connection Configurations</h3>
              <button className="btn-primary" onClick={() => openModal('connection')}>
                <i className="fas fa-plus"></i> Add Connection
              </button>
            </div>
            <ConnectionsTable
              connections={state.data.connections}
              onEdit={(c) => openModal('connection', c)}
              onDelete={(id) => api.handleDelete('connection', id)}
              onTest={(id) => api.handleTestConnection(id)}
              testingId={state.testingId}
              testResults={state.testResults}
            />
          </div>
        );

      case 'settings':
        return (
          <div className="admin-config-content">
            <div className="config-section-header">
              <h3>System Settings</h3>
              <button className="btn-primary" onClick={() => openModal('setting')}>
                <i className="fas fa-plus"></i> Add Setting
              </button>
            </div>
            <div style={{ padding: '16px 24px' }}>
              <SystemSettingsTable
                settings={state.data.systemConfigs}
                onEdit={(s) => openModal('setting', s)}
                onDelete={(id) => api.handleDelete('setting', id)}
              />
            </div>
          </div>
        );

      case 'flags':
        return (
          <div className="admin-config-content">
            <div className="config-section-header">
              <h3>Feature Flags</h3>
              <button className="btn-primary" onClick={() => openModal('flag')}>
                <i className="fas fa-plus"></i> Add Flag
              </button>
            </div>
            <FeatureFlagsTable
              flags={state.data.featureFlags}
              onToggle={api.handleToggleFlag}
              onEdit={(f) => openModal('flag', f)}
              onDelete={(id) => api.handleDelete('flag', id)}
            />
          </div>
        );

      default:
        return null;
    }
  };

  // Render modal content based on type
  const renderModalContent = () => {
    switch (state.modalType) {
      case 'llm':
        return <LLMProviderForm provider={state.editItem} onChange={state.setEditItem} />;
      case 'embedding':
        return <EmbeddingModelForm model={state.editItem} onChange={state.setEditItem} />;
      case 'connection':
        return <ConnectionForm connection={state.editItem} onChange={state.setEditItem} />;
      case 'setting':
        return <SystemSettingForm setting={state.editItem} onChange={state.setEditItem} />;
      case 'flag':
        return <FeatureFlagForm flag={state.editItem} onChange={state.setEditItem} />;
      default:
        return <p>Form not implemented for this type</p>;
    }
  };

  // Loading state
  if (state.loading) {
    return (
      <div className="admin-config-manager">
        <div className="loading-overlay">
          <div className="loading-spinner"></div>
          <span>Loading configuration...</span>
        </div>
      </div>
    );
  }

  const saveDisabledReason = getSaveDisabledReason(state.modalOpen, state.modalType, state.editItem);

  return (
    <div className="admin-config-manager">
      {/* Alert messages */}
      {state.error && (
        <div className="alert alert-error">
          <i className="fas fa-exclamation-circle"></i> {state.error}
        </div>
      )}
      {state.success && (
        <div className="alert alert-success">
          <i className="fas fa-check-circle"></i> {state.success}
        </div>
      )}

      {/* Tab navigation */}
      <TabNavigation
        tabs={tabs}
        activeTab={state.activeTab}
        onTabChange={state.setActiveTab}
      />

      {/* Tab content */}
      {renderContent()}

      {/* Configuration modal */}
      <Modal
        isOpen={state.modalOpen}
        onClose={() => state.setModalOpen(false)}
        title={`${state.editItem?._isNew !== false ? 'Add' : 'Edit'} ${state.modalType?.toUpperCase() || ''}`}
        footer={
          <div style={{ display: 'flex', gap: '8px', justifyContent: 'flex-end' }}>
            <button
              className="btn-secondary"
              onClick={() => state.setModalOpen(false)}
            >
              Cancel
            </button>
            <button
              className="btn-primary"
              onClick={() => api.handleSave(state.editItem, state.modalType, state.editItem?._isNew !== false)}
              disabled={!!saveDisabledReason}
              title={saveDisabledReason || ''}
            >
              Save
            </button>
          </div>
        }
      >
        {renderModalContent()}
      </Modal>
    </div>
  );
}

export default AdminConfigManager;
