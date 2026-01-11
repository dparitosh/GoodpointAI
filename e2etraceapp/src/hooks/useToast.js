/**
 * Toast Notification Hook
 * Provides non-blocking notifications to replace window.alert
 */
import { useState, useCallback, useRef } from 'react';

// Global toast state for singleton pattern
let globalToasts = [];
let globalListeners = [];

const notifyListeners = () => {
  globalListeners.forEach(listener => listener([...globalToasts]));
};

/**
 * Generate unique ID for toast
 */
const generateId = () => `toast-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;

/**
 * Toast types for styling
 */
export const TOAST_TYPES = {
  SUCCESS: 'success',
  ERROR: 'error',
  WARNING: 'warning',
  INFO: 'info'
};

/**
 * Add a toast notification globally
 * @param {string} message - Toast message
 * @param {string} type - Toast type (success, error, warning, info)
 * @param {number} duration - Auto-dismiss duration in ms (0 = no auto-dismiss)
 */
export const showToast = (message, type = TOAST_TYPES.INFO, duration = 5000) => {
  const id = generateId();
  const toast = {
    id,
    message,
    type,
    createdAt: Date.now()
  };

  // Limit max toasts to prevent memory issues
  if (globalToasts.length >= 5) {
    globalToasts = globalToasts.slice(-4);
  }

  globalToasts = [...globalToasts, toast];
  notifyListeners();

  // Auto-dismiss
  if (duration > 0) {
    setTimeout(() => {
      dismissToast(id);
    }, duration);
  }

  return id;
};

/**
 * Dismiss a toast by ID
 */
export const dismissToast = (id) => {
  globalToasts = globalToasts.filter(t => t.id !== id);
  notifyListeners();
};

/**
 * Clear all toasts
 */
export const clearAllToasts = () => {
  globalToasts = [];
  notifyListeners();
};

/**
 * Convenience methods
 */
export const toast = {
  success: (message, duration) => showToast(message, TOAST_TYPES.SUCCESS, duration),
  error: (message, duration) => showToast(message, TOAST_TYPES.ERROR, duration ?? 8000),
  warning: (message, duration) => showToast(message, TOAST_TYPES.WARNING, duration),
  info: (message, duration) => showToast(message, TOAST_TYPES.INFO, duration),
  dismiss: dismissToast,
  clear: clearAllToasts
};

/**
 * React hook for toast notifications
 */
export const useToast = () => {
  const [toasts, setToasts] = useState(globalToasts);

  // Register listener on mount
  const listenerRef = useRef(null);
  
  if (!listenerRef.current) {
    listenerRef.current = setToasts;
    globalListeners.push(setToasts);
  }

  // Cleanup on unmount
  const cleanup = useCallback(() => {
    globalListeners = globalListeners.filter(l => l !== listenerRef.current);
  }, []);

  return {
    toasts,
    showToast,
    dismissToast,
    clearAllToasts,
    toast,
    cleanup
  };
};

export default useToast;
