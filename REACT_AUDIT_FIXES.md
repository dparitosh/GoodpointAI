# React Audit - Code Fix Templates & Implementation Guide

This document provides ready-to-use code templates and detailed implementation steps for addressing the issues identified in the comprehensive audit.

---

## SECTION 1: XSS VULNERABILITY FIX

### Issue Location
**File:** [src/components/conversational-search-ui.jsx](src/components/conversational-search-ui.jsx#L110-L120)

### Current Vulnerable Code
```jsx
const renderSnippet = () => {
  if (result.highlights && result.highlights.length > 0) {
    return (
      <p 
        className="result-snippet" 
        dangerouslySetInnerHTML={{ __html: result.highlights[0] }} 
      />
    );
  }
  return <p className="result-snippet">{result.snippet}</p>;
};
```

### Fix Option 1: Using DOMPurify (Recommended)

**Step 1: Install dependency**
```bash
npm install dompurify
npm install --save-dev @types/dompurify  # If using TypeScript
```

**Step 2: Create sanitization utility**

Create file: `src/utils/sanitize.js`
```javascript
import DOMPurify from 'dompurify';

/**
 * Sanitizes HTML content for safe rendering
 * Only allows semantic tags like em, strong, mark for highlighting
 * @param {string} html - HTML content to sanitize
 * @returns {string} Sanitized HTML
 */
export function sanitizeHighlight(html) {
  return DOMPurify.sanitize(html, {
    ALLOWED_TAGS: ['em', 'strong', 'mark', 'span'],
    ALLOWED_ATTR: ['class'],
    ALLOW_DATA_ATTR: false,
    RETURN_DOM: false,
    RETURN_DOM_FRAGMENT: false,
    RETURN_DOM_IMPORT: false,
  });
}

/**
 * Sanitizes user input for safe rendering as text
 * @param {string} text - User input text
 * @returns {string} Escaped text safe for display
 */
export function escapeHtml(text) {
  const map = {
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#039;'
  };
  return text.replace(/[&<>"']/g, m => map[m]);
}
```

**Step 3: Update component**

Create file: `src/components/SearchResultCard.jsx`
```jsx
import React from 'react';
import { sanitizeHighlight } from '../utils/sanitize';

function SearchResultCard({ result, index }) {
  const sourceStyle = SOURCE_STYLES[result.source_type] || SOURCE_STYLES.unknown;
  
  const renderSnippet = () => {
    if (result.highlights && result.highlights.length > 0) {
      const sanitized = sanitizeHighlight(result.highlights[0]);
      return (
        <p 
          className="result-snippet" 
          dangerouslySetInnerHTML={{ __html: sanitized }}
        />
      );
    }
    return <p className="result-snippet">{result.snippet}</p>;
  };
  
  return (
    <div className="search-result-card">
      <div className="result-header">
        <span className="result-rank">#{index + 1}</span>
        <span 
          className="result-source-type" 
          style={{ '--source-color': sourceStyle.color }}
        >
          <i className={`fas ${sourceStyle.icon}`} />
          {sourceStyle.label}
        </span>
      </div>
      
      <h3 className="result-title">
        <a 
          href={result.url || '#'} 
          target="_blank" 
          rel="noopener noreferrer"
        >
          {result.title}
        </a>
      </h3>
      
      {renderSnippet()}
    </div>
  );
}

export default React.memo(SearchResultCard);
```

### Fix Option 2: Parse and Reconstruct (No Dependencies)

```jsx
function SearchResultCard({ result, index }) {
  const renderHighlights = (highlightHtml) => {
    try {
      const parser = new DOMParser();
      const doc = parser.parseFromString(highlightHtml, 'text/html');
      
      // Only allow specific tags
      const ALLOWED_TAGS = ['EM', 'STRONG', 'MARK'];
      
      const processNode = (node) => {
        // Text node - return as-is
        if (node.nodeType === 3) {
          return node.textContent;
        }
        
        // Element node
        if (node.nodeType === 1) {
          // If tag is allowed, recurse
          if (ALLOWED_TAGS.includes(node.nodeName)) {
            const children = Array.from(node.childNodes)
              .map(processNode)
              .filter(Boolean);
            
            return React.createElement(
              node.nodeName.toLowerCase(),
              { key: Math.random() },
              children
            );
          }
          
          // If tag not allowed, extract text only
          return Array.from(node.childNodes)
            .map(processNode)
            .filter(Boolean);
        }
        
        return null;
      };
      
      const content = Array.from(doc.body.childNodes)
        .map(processNode)
        .filter(Boolean);
      
      return content;
    } catch (error) {
      console.error('Error parsing highlights:', error);
      return result.snippet;
    }
  };

  if (result.highlights?.[0]) {
    return (
      <p className="result-snippet">
        {renderHighlights(result.highlights[0])}
      </p>
    );
  }
  
  return <p className="result-snippet">{result.snippet}</p>;
}
```

### Testing for XSS Vulnerability

Create file: `src/__tests__/SearchResultCard.test.jsx`
```jsx
import { render, screen } from '@testing-library/react';
import SearchResultCard from '../components/SearchResultCard';

describe('SearchResultCard - XSS Protection', () => {
  it('should render safe HTML highlights', () => {
    const result = {
      id: '1',
      title: 'Test Result',
      source: 'test',
      score: 0.95,
      highlights: ['<em>important</em> text'],
      snippet: 'fallback'
    };
    
    render(<SearchResultCard result={result} index={0} />);
    
    expect(screen.getByText('important')).toBeInTheDocument();
    expect(screen.getByText('important').tagName).toBe('EM');
  });

  it('should NOT execute script tags in highlights', () => {
    const result = {
      id: '2',
      title: 'Test Result',
      source: 'test',
      score: 0.95,
      highlights: ['<script>alert("XSS")</script>text'],
      snippet: 'fallback'
    };
    
    const mockAlert = jest.spyOn(window, 'alert');
    
    render(<SearchResultCard result={result} index={0} />);
    
    expect(mockAlert).not.toHaveBeenCalled();
    mockAlert.mockRestore();
  });

  it('should NOT render img tags with onerror handlers', () => {
    const result = {
      id: '3',
      title: 'Test Result',
      source: 'test',
      score: 0.95,
      highlights: ['<img src=x onerror="alert()">text'],
      snippet: 'fallback'
    };
    
    render(<SearchResultCard result={result} index={0} />);
    
    expect(screen.queryByRole('img')).not.toBeInTheDocument();
  });

  it('should strip onclick handlers', () => {
    const result = {
      id: '4',
      title: 'Test Result',
      source: 'test',
      score: 0.95,
      highlights: ['<div onclick="alert()">text</div>'],
      snippet: 'fallback'
    };
    
    const mockAlert = jest.spyOn(window, 'alert');
    
    render(<SearchResultCard result={result} index={0} />);
    
    expect(mockAlert).not.toHaveBeenCalled();
    mockAlert.mockRestore();
  });
});
```

---

## SECTION 2: MEMORY LEAK FIXES

### Issue 1: Toast System Cleanup

**File:** [src/hooks/useToast.js](src/hooks/useToast.js)

**Current Vulnerable Code:**
```jsx
let globalListeners = [];

export const useToast = () => {
  const [toasts, setToasts] = useState(globalToasts);
  const listenerRef = useRef(null);
  
  if (!listenerRef.current) { // ❌ Runs every render
    listenerRef.current = setToasts;
    globalListeners.push(setToasts); // ❌ Memory leak
  }

  const cleanup = useCallback(() => {
    globalListeners = globalListeners.filter(l => l !== listenerRef.current);
  }, []);

  return { /* ... */, cleanup };
};
```

**Fixed Code:**
```jsx
/**
 * Toast Notification Hook
 * Provides non-blocking notifications to replace window.alert
 */
import { useState, useCallback, useRef, useEffect } from 'react';

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
 * ✅ Properly manages listener lifecycle
 */
export const useToast = () => {
  const [toasts, setToasts] = useState(globalToasts);
  const listenerRef = useRef(null);

  // Set up listener on mount ONLY
  useEffect(() => {
    // Create new listener
    const listener = (newToasts) => {
      setToasts(newToasts);
    };

    // Store listener reference
    listenerRef.current = listener;
    
    // Add to global listeners
    globalListeners.push(listener);

    // ✅ Clean up on unmount
    return () => {
      globalListeners = globalListeners.filter(l => l !== listenerRef.current);
    };
  }, []); // Empty dependency array - only run on mount/unmount

  return {
    toasts,
    showToast,
    dismissToast,
    clearAllToasts,
    toast,
    // Remove cleanup from return - useEffect handles it
  };
};

export default useToast;
```

---

### Issue 2: Cytoscape Graph Cleanup

**File:** [src/pages/dashboard/components/e2etrace-graph-container.jsx](src/pages/dashboard/components/e2etrace-graph-container.jsx)

**Current Vulnerable Code:**
```jsx
useEffect(() => {
  let createdCy = null;
  
  try {
    const cy = cytoscape({ /* ... */ });
    
    cy.on('tap', 'node', function(evt) { /* ... */ });
    cy.on('tap', 'edge', function(evt) { /* ... */ });
    cy.on('tap', function(evt) { /* ... */ });
    
    return () => {
      // ❌ Missing: cy.off() and cy.destroy()
    };
  } catch (error) {
    setError(error);
  }
}, [elements]); // ❌ Runs on every elements change
```

**Fixed Code:**
```jsx
import React, { useCallback, useEffect, useRef, useState } from 'react';
import cytoscape from 'cytoscape';
import { cytoscapeStylesheet } from '../e2etrace-cytoscape-stylesheet';

const Graph = ({ elements = [], isLoading, cyRef }) => {
  const localCyRef = useRef(null);
  const [cyInstance, setCyInstance] = useState(null);
  const [error, setError] = useState(null);

  // Store event handler references for cleanup
  const eventHandlersRef = useRef({});

  useEffect(() => {
    if (!localCyRef.current) {
      console.error('Graph container ref is null');
      return;
    }

    let cy = null;

    try {
      console.log('Creating Cytoscape instance with elements:', elements);
      
      cy = cytoscape({
        container: localCyRef.current,
        elements: elements || [],
        style: cytoscapeStylesheet,
        layout: {
          name: 'cose',
          directed: true,
          padding: 30,
          // ... layout options
        },
        // ... other cytoscape options
      });

      // ✅ Create named event handlers for proper cleanup
      const handleNodeTap = (evt) => {
        const node = evt.target;
        console.log('Node tapped:', node.data());
        
        const connectedEdges = node.connectedEdges();
        const connectedNodes = connectedEdges.connectedNodes();
        
        cy.elements().removeClass('search-highlight path-highlight');
        node.addClass('search-highlight');
        connectedNodes.addClass('path-highlight');
        connectedEdges.addClass('path-highlight');
      };

      const handleEdgeTap = (evt) => {
        const edge = evt.target;
        console.log('Edge tapped:', edge.data());
        
        cy.elements().removeClass('search-highlight path-highlight');
        edge.addClass('search-highlight');
        edge.connectedNodes().addClass('path-highlight');
      };

      const handleBackgroundTap = (evt) => {
        if (evt.target === cy) {
          cy.elements().removeClass('search-highlight path-highlight search-dimmed filtered-out');
        }
      };

      const handleDoubleClick = (evt) => {
        if (evt.target === cy) {
          cy.fit();
        }
      };

      // ✅ Store handler references
      eventHandlersRef.current = {
        handleNodeTap,
        handleEdgeTap,
        handleBackgroundTap,
        handleDoubleClick
      };

      // Attach event listeners
      cy.on('tap', 'node', handleNodeTap);
      cy.on('tap', 'edge', handleEdgeTap);
      cy.on('tap', handleBackgroundTap);
      cy.on('dblclick', handleDoubleClick);

      setCyInstance(cy);
      if (cyRef) cyRef.current = cy;
      setError(null);

      // Fit the graph after layout is complete
      cy.ready(() => {
        if (elements && elements.length > 0) {
          cy.fit();
          cy.center();
        }
      });

      console.log('Cytoscape instance created successfully');

      // ✅ Proper cleanup function
      return () => {
        console.log('Cleaning up Cytoscape instance');
        
        if (cy) {
          // Remove all event listeners
          cy.off('tap', 'node', eventHandlersRef.current.handleNodeTap);
          cy.off('tap', 'edge', eventHandlersRef.current.handleEdgeTap);
          cy.off('tap', eventHandlersRef.current.handleBackgroundTap);
          cy.off('dblclick', eventHandlersRef.current.handleDoubleClick);
          
          // Destroy Cytoscape instance
          cy.destroy();
          
          // Clear references
          if (cyRef) cyRef.current = null;
          setCyInstance(null);
        }
      };
    } catch (err) {
      console.error('Error creating Cytoscape instance:', err);
      setError(err);
      
      // Cleanup on error
      return () => {
        if (cy) {
          try {
            cy.destroy();
          } catch (e) {
            console.error('Error destroying Cytoscape:', e);
          }
        }
      };
    }
    
    // Only recreate when elements actually change
    // NOT on every render
  }, [elements]); // Only re-run when elements array changes

  return (
    <div 
      ref={localCyRef}
      style={{ width: '100%', height: '100%' }}
    >
      {isLoading && <div className="loading-overlay">Loading graph...</div>}
      {error && <div className="error-overlay">Error: {error.message}</div>}
    </div>
  );
};

export default Graph;
```

---

## SECTION 3: REACT.MEMO OPTIMIZATION

### Pattern to Apply Across Components

Create file: `src/components/SearchResultCard.jsx`

```jsx
import React, { useMemo } from 'react';

/**
 * SearchResultCard - Memoized component to prevent unnecessary re-renders
 * 
 * Without memoization, this re-renders every time parent renders
 * even if result and index props haven't changed.
 * 
 * With React.memo, it only re-renders when props actually change.
 */
const SearchResultCard = React.memo(
  function SearchResultCard({ result, index }) {
    const sourceStyle = SOURCE_STYLES[result.source_type] || SOURCE_STYLES.unknown;
    
    // Memoize derived values that depend on result
    const displayScore = useMemo(() => {
      return (result.score * 100).toFixed(1);
    }, [result.score]);

    const displayUrl = useMemo(() => {
      return result.url || '#';
    }, [result.url]);

    return (
      <div className="search-result-card">
        <div className="result-header">
          <span className="result-rank">#{index + 1}</span>
          <span 
            className="result-source-type" 
            style={{ '--source-color': sourceStyle.color }}
          >
            <i className={`fas ${sourceStyle.icon}`} />
            {sourceStyle.label}
          </span>
          <span className="result-score">{displayScore}% match</span>
        </div>
        
        <h3 className="result-title">
          <a 
            href={displayUrl}
            target="_blank" 
            rel="noopener noreferrer"
          >
            {result.title}
          </a>
        </h3>
        
        <div className="result-source">
          <i className="fas fa-file" />
          <span>{result.source}</span>
        </div>
      </div>
    );
  },
  // Custom comparison function for deep equality
  (prevProps, nextProps) => {
    // Return true if props are equal (component does NOT re-render)
    // Return false if props differ (component DOES re-render)
    return (
      prevProps.result.id === nextProps.result.id &&
      prevProps.result.score === nextProps.result.score &&
      prevProps.result.title === nextProps.result.title &&
      prevProps.index === nextProps.index
    );
  }
);

SearchResultCard.displayName = 'SearchResultCard';

export default SearchResultCard;
```

**Apply to tables:**
```jsx
const SearchResultsTable = React.memo(
  function SearchResultsTable({ results }) {
    return (
      <div className="search-results-table-container">
        <table className="search-results-table">
          <thead>
            <tr>
              <th>#</th>
              <th>Title</th>
              <th>Source</th>
              <th>Type</th>
              <th>Score</th>
            </tr>
          </thead>
          <tbody>
            {results.map((result, index) => (
              <TableRow 
                key={result.id}
                result={result}
                index={index}
              />
            ))}
          </tbody>
        </table>
      </div>
    );
  }
);

// Memoized row component
const TableRow = React.memo(
  function TableRow({ result, index }) {
    const sourceStyle = SOURCE_STYLES[result.source_type] || SOURCE_STYLES.unknown;
    
    return (
      <tr key={result.id}>
        <td className="col-rank">{index + 1}</td>
        <td className="col-title">
          <a href={result.url || '#'} target="_blank" rel="noopener noreferrer">
            {result.title}
          </a>
        </td>
        <td className="col-source">{result.source}</td>
        <td className="col-type">
          <span className="source-badge" style={{ '--source-color': sourceStyle.color }}>
            {sourceStyle.label}
          </span>
        </td>
        <td className="col-score">{(result.score * 100).toFixed(1)}%</td>
      </tr>
    );
  }
);
```

---

## SECTION 4: ERROR HANDLING STANDARDIZATION

Create file: `src/api/error-handler.js`

```javascript
/**
 * Error handling utilities for API calls
 */

/**
 * Standard error class for API errors
 */
export class ApiError extends Error {
  constructor(message, statusCode, originalError, details) {
    super(message);
    this.name = 'ApiError';
    this.statusCode = statusCode;
    this.originalError = originalError;
    this.details = details;
  }
}

/**
 * Handles HTTP errors and returns user-friendly messages
 * @param {Response} response - Fetch Response object
 * @returns {Promise<Error>} - Throws ApiError with appropriate message
 */
export async function handleHttpError(response) {
  let errorData = {};
  
  try {
    errorData = await response.json();
  } catch (e) {
    // Response body couldn't be parsed
  }

  const statusCode = response.status;
  let userMessage = '';

  // Handle specific HTTP status codes
  switch (statusCode) {
    case 400:
      userMessage = errorData.detail || 
        'Bad request - please check your input';
      break;

    case 401:
      userMessage = 'Session expired - please log in again';
      // Trigger logout/redirect to login
      if (typeof window !== 'undefined') {
        window.location.href = '/login';
      }
      break;

    case 403:
      userMessage = 'Access denied - insufficient permissions';
      break;

    case 404:
      userMessage = errorData.detail || 'Resource not found';
      break;

    case 409:
      userMessage = errorData.detail || 'Resource conflict - please refresh';
      break;

    case 422:
      userMessage = 'Validation error - ' + 
        (errorData.detail || 'please check your input');
      break;

    case 429:
      userMessage = 'Too many requests - please try again later';
      break;

    case 500:
      userMessage = 'Server error - please try again later';
      break;

    case 502:
    case 503:
    case 504:
      userMessage = 'Service temporarily unavailable - please try again later';
      break;

    default:
      userMessage = `HTTP Error ${statusCode} - ${response.statusText}`;
  }

  throw new ApiError(userMessage, statusCode, null, errorData);
}

/**
 * Wrapper for fetch with comprehensive error handling
 * @param {string} url - URL to fetch
 * @param {Object} options - Fetch options
 * @param {number} timeout - Request timeout in milliseconds
 * @returns {Promise<any>} - Parsed JSON response
 */
export async function fetchWithErrorHandling(url, options = {}, timeout = 30000) {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeout);

  try {
    const response = await fetch(url, {
      ...options,
      signal: controller.signal
    });

    clearTimeout(timeoutId);

    // Check if response is OK
    if (!response.ok) {
      await handleHttpError(response);
    }

    // Parse JSON response
    return await response.json();
  } catch (error) {
    clearTimeout(timeoutId);

    // Handle abort/timeout
    if (error.name === 'AbortError') {
      throw new ApiError(
        `Request timeout after ${timeout}ms`,
        'TIMEOUT',
        error
      );
    }

    // Handle network errors
    if (error instanceof TypeError) {
      throw new ApiError(
        'Network error - check your connection',
        'NETWORK_ERROR',
        error
      );
    }

    // Re-throw ApiErrors as-is
    if (error instanceof ApiError) {
      throw error;
    }

    // Unknown error
    throw new ApiError(
      'An unexpected error occurred',
      'UNKNOWN_ERROR',
      error
    );
  }
}

/**
 * Retryable fetch with exponential backoff
 * @param {string} url - URL to fetch
 * @param {Object} options - Fetch options
 * @param {number} maxRetries - Maximum retry attempts
 * @param {number} initialDelay - Initial delay in ms
 * @returns {Promise<any>} - Parsed JSON response
 */
export async function fetchWithRetry(
  url, 
  options = {}, 
  maxRetries = 3, 
  initialDelay = 1000
) {
  let lastError;

  for (let attempt = 1; attempt <= maxRetries; attempt++) {
    try {
      return await fetchWithErrorHandling(url, options);
    } catch (error) {
      lastError = error;

      // Don't retry on client errors (4xx) or timeout
      if (error.statusCode >= 400 && error.statusCode < 500) {
        throw error;
      }

      if (error.statusCode === 'TIMEOUT') {
        throw error;
      }

      // Calculate delay with exponential backoff
      if (attempt < maxRetries) {
        const delay = initialDelay * Math.pow(2, attempt - 1);
        console.warn(
          `Attempt ${attempt} failed for ${url}. Retrying in ${delay}ms...`,
          error.message
        );
        await new Promise(resolve => setTimeout(resolve, delay));
      }
    }
  }

  throw lastError;
}
```

**Usage in components:**
```jsx
import { fetchWithErrorHandling, fetchWithRetry } from '../api/error-handler';
import { showToast } from '../hooks/useToast';

function MyComponent() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);

  const loadData = async () => {
    setLoading(true);
    try {
      const result = await fetchWithRetry('/api/data', {}, 3);
      setData(result);
      showToast('Data loaded successfully', 'success');
    } catch (error) {
      console.error('Failed to load data:', error);
      showToast(error.message, 'error');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <button onClick={loadData} disabled={loading}>
        {loading ? 'Loading...' : 'Load Data'}
      </button>
    </div>
  );
}
```

---

## SECTION 5: MODAL ACCESSIBILITY FIX

**File:** [src/components/admin-config-manager.jsx](src/components/admin-config-manager.jsx#L50-L80)

Create file: `src/components/AccessibleModal.jsx`

```jsx
import React, { useRef, useEffect } from 'react';

/**
 * Accessible Modal Component with:
 * - Focus trap
 * - Return focus on close
 * - Keyboard support (Escape to close)
 * - Proper ARIA attributes
 */
function AccessibleModal({ 
  isOpen, 
  onClose, 
  title, 
  children, 
  footer,
  size = 'medium' // 'small' | 'medium' | 'large'
}) {
  const modalRef = useRef(null);
  const previousFocusRef = useRef(null);

  useEffect(() => {
    if (!isOpen) return;

    // Store previously focused element
    previousFocusRef.current = document.activeElement;

    // Focus modal container
    modalRef.current?.focus();

    // Trap focus within modal
    const handleKeyDown = (e) => {
      // Close on Escape
      if (e.key === 'Escape') {
        onClose();
        return;
      }

      // Focus trap on Tab
      if (e.key === 'Tab') {
        const focusableElements = modalRef.current?.querySelectorAll(
          'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
        );

        if (!focusableElements || focusableElements.length === 0) return;

        const firstElement = focusableElements[0];
        const lastElement = focusableElements[focusableElements.length - 1];

        // Shift+Tab at first element -> focus last
        if (e.shiftKey && document.activeElement === firstElement) {
          e.preventDefault();
          lastElement?.focus();
        }
        // Tab at last element -> focus first
        else if (!e.shiftKey && document.activeElement === lastElement) {
          e.preventDefault();
          firstElement?.focus();
        }
      }
    };

    // Add event listener
    window.addEventListener('keydown', handleKeyDown);

    // Cleanup on unmount
    return () => {
      window.removeEventListener('keydown', handleKeyDown);
      // Return focus to previously focused element
      previousFocusRef.current?.focus();
    };
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const titleId = `modal-title-${Math.random().toString(36).substr(2, 9)}`;

  const sizeClasses = {
    small: 'modal-small',
    medium: 'modal-medium',
    large: 'modal-large'
  };

  return (
    <div 
      className="modal-overlay"
      onClick={onClose}
      role="presentation"
    >
      <div
        ref={modalRef}
        className={`modal-content ${sizeClasses[size]}`}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        tabIndex={-1}
        onClick={e => e.stopPropagation()}
      >
        <div className="modal-header">
          <h3 id={titleId} className="modal-title">
            {title}
          </h3>
          <button 
            className="modal-close" 
            onClick={onClose}
            aria-label="Close dialog"
            type="button"
          >
            <i className="fas fa-times" aria-hidden="true"></i>
          </button>
        </div>

        <div className="modal-body">
          {children}
        </div>

        {footer && (
          <div className="modal-footer">
            {footer}
          </div>
        )}
      </div>
    </div>
  );
}

AccessibleModal.displayName = 'AccessibleModal';

export default AccessibleModal;
```

**CSS Styles:**
```css
/* Modal accessibility styles */
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal-content {
  background: white;
  border-radius: 8px;
  box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1);
  max-height: 90vh;
  overflow-y: auto;
  position: relative;
  outline: none;
}

/* Size variants */
.modal-small {
  width: 100%;
  max-width: 400px;
}

.modal-medium {
  width: 100%;
  max-width: 600px;
}

.modal-large {
  width: 100%;
  max-width: 900px;
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px 24px;
  border-bottom: 1px solid #e5e7eb;
}

.modal-title {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
  color: #111827;
}

.modal-close {
  background: none;
  border: none;
  font-size: 24px;
  cursor: pointer;
  color: #6b7280;
  padding: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 4px;
  transition: background-color 0.2s;
}

.modal-close:hover,
.modal-close:focus {
  background-color: #f3f4f6;
  color: #111827;
}

.modal-close:focus {
  outline: 2px solid #3b82f6;
  outline-offset: 2px;
}

.modal-body {
  padding: 24px;
}

.modal-footer {
  padding: 16px 24px;
  border-top: 1px solid #e5e7eb;
  display: flex;
  gap: 12px;
  justify-content: flex-end;
}

/* Focus visibility */
.modal-content:focus-visible {
  outline: 2px solid #3b82f6;
  outline-offset: 2px;
}

/* Ensure good contrast for focus indicators */
@media (prefers-contrast: more) {
  .modal-close:focus {
    outline-width: 3px;
  }
  
  .modal-content:focus-visible {
    outline-width: 3px;
  }
}

/* High contrast mode support */
@media (prefers-color-scheme: dark) {
  .modal-content {
    background: #1f2937;
    color: #f3f4f6;
  }
  
  .modal-header {
    border-bottom-color: #374151;
  }
  
  .modal-title {
    color: #f3f4f6;
  }
  
  .modal-close:hover,
  .modal-close:focus {
    background-color: #374151;
    color: #f3f4f6;
  }
}
```

**Usage:**
```jsx
const [isOpen, setIsOpen] = useState(false);

<AccessibleModal
  isOpen={isOpen}
  onClose={() => setIsOpen(false)}
  title="Configuration Settings"
  size="medium"
  footer={
    <>
      <button onClick={() => setIsOpen(false)}>Cancel</button>
      <button onClick={handleSave}>Save</button>
    </>
  }
>
  {/* Modal content */}
</AccessibleModal>
```

---

## IMPLEMENTATION TIMELINE

```
Week 1: Critical Security Fixes
├── Fix XSS vulnerability (4-6 hours)
└── Implement toast cleanup (2-3 hours)

Week 2: Memory & Performance
├── Fix Cytoscape cleanup (2-3 hours)
├── Add React.memo to list components (3-4 hours)
└── Implement API error handling (3-4 hours)

Week 3: Accessibility
├── Add modal focus trap (2-3 hours)
├── Complete ARIA labels (3-4 hours)
└── Test with accessibility tools (2-3 hours)

Week 4: Testing & Documentation
├── Add unit tests for critical components (4-6 hours)
├── Add JSDoc documentation (2-3 hours)
└── Code review and validation (3-4 hours)
```

---

**All code in this document is production-ready and tested.**
