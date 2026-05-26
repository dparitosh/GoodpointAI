/**
 * Custom hook for managing admin configuration state
 */
import { useState, useCallback } from 'react';

export const useAdminConfigState = () => {
  const [activeTab, setActiveTab] = useState('llm');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);
  const [data, setData] = useState({
    llmProviders: [],
    embeddingModels: [],
    connections: [],
    systemConfigs: [],
    featureFlags: []
  });
  const [health, setHealth] = useState(null);
  const [modalOpen, setModalOpen] = useState(false);
  const [modalType, setModalType] = useState(null);
  const [editItem, setEditItem] = useState(null);
  const [testingId, setTestingId] = useState(null);
  const [testResults, setTestResults] = useState({});

  const showMessage = useCallback((msg, isError = false) => {
    if (isError) {
      setError(msg);
      setSuccess(null);
    } else {
      setSuccess(msg);
      setError(null);
    }
    
    // Auto-clear message after 5 seconds
    setTimeout(() => {
      setError(null);
      setSuccess(null);
    }, 5000);
  }, []);

  return {
    // State
    activeTab,
    loading,
    error,
    success,
    data,
    health,
    modalOpen,
    modalType,
    editItem,
    testingId,
    testResults,
    // Setters
    setActiveTab,
    setLoading,
    setError,
    setSuccess,
    setData,
    setHealth,
    setModalOpen,
    setModalType,
    setEditItem,
    setTestingId,
    setTestResults,
    // Methods
    showMessage
  };
};
