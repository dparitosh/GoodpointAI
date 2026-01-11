/**
 * XState Helper Utilities
 * Shared utilities for XState machines
 */

/**
 * Maximum number of errors to keep in state
 * Prevents memory leaks from unbounded error accumulation
 */
export const MAX_ERRORS = 50;

/**
 * Add an error to the errors array with limit
 * @param {Array} currentErrors - Current errors array
 * @param {string|Error} newError - New error to add
 * @returns {Array} Updated errors array (limited to MAX_ERRORS)
 */
export const addError = (currentErrors, newError) => {
  const errorMessage = typeof newError === 'string' 
    ? newError 
    : newError?.message || String(newError);
  
  const timestamp = new Date().toISOString();
  const errorWithTimestamp = { message: errorMessage, timestamp };
  
  // Keep only the most recent errors
  const updated = [...(currentErrors || []), errorWithTimestamp];
  return updated.slice(-MAX_ERRORS);
};

/**
 * Add error string to array with limit (simple version)
 * @param {Array} currentErrors - Current errors array
 * @param {string} errorMessage - Error message to add
 * @returns {Array} Updated errors array (limited to MAX_ERRORS)
 */
export const addErrorMessage = (currentErrors, errorMessage) => {
  const updated = [...(currentErrors || []), errorMessage];
  return updated.slice(-MAX_ERRORS);
};

/**
 * Clear errors older than specified duration
 * @param {Array} errors - Errors array with timestamps
 * @param {number} maxAgeMs - Maximum age in milliseconds (default: 1 hour)
 * @returns {Array} Filtered errors array
 */
export const clearOldErrors = (errors, maxAgeMs = 3600000) => {
  const cutoff = Date.now() - maxAgeMs;
  return (errors || []).filter(err => {
    if (typeof err === 'string') return true; // Keep string errors (no timestamp)
    const ts = err.timestamp ? new Date(err.timestamp).getTime() : 0;
    return ts > cutoff;
  });
};

/**
 * XState assign action for adding error with limit
 * Use: actions: [addErrorAction]
 */
export const createErrorAssign = (assign) => 
  assign({
    errors: (context, event) => 
      addErrorMessage(context.errors, event.data?.message || event.error || 'Unknown error')
  });

/**
 * XState assign action for clearing errors
 */
export const createClearErrorsAssign = (assign) =>
  assign({
    errors: () => []
  });

export default {
  MAX_ERRORS,
  addError,
  addErrorMessage,
  clearOldErrors,
  createErrorAssign,
  createClearErrorsAssign
};
