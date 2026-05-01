/**
 * API Client Utility
 *
 * Centralized API client with:
 * - Automatic timeout handling
 * - Safe error body parsing (JSON + text fallback)
 * - Only retries on transient server errors (502/503/504/408)
 */

// Prefer VITE_API_BASE_URL (documented and used elsewhere); keep VITE_API_URL as a legacy fallback.
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || import.meta.env.VITE_API_URL || '';
const DEFAULT_TIMEOUT = 30000; // 30 seconds

/**
 * Parse an error response body safely.
 * Checks Content-Type before attempting JSON parse; falls back to plain text.
 * @param {Response} response
 * @returns {Promise<string>} Human-readable error message
 */
async function _parseErrorBody(response) {
  try {
    const contentType = response.headers.get('content-type') || '';
    if (contentType.includes('application/json')) {
      const body = await response.json();
      return body?.detail || body?.message || body?.error || JSON.stringify(body);
    }
    const text = await response.text();
    return text.slice(0, 500) || `HTTP ${response.status}: ${response.statusText}`;
  } catch {
    return `HTTP ${response.status}: ${response.statusText}`;
  }
}

/**
 * Fetch with timeout support
 * @param {string} url
 * @param {Object} options - Fetch options
 * @param {number} timeout - Timeout in milliseconds
 * @returns {Promise<Response>}
 */
export async function fetchWithTimeout(url, options = {}, timeout = DEFAULT_TIMEOUT) {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeout);

  try {
    const response = await fetch(url, {
      ...options,
      signal: controller.signal,
    });
    clearTimeout(timeoutId);
    return response;
  } catch (error) {
    clearTimeout(timeoutId);
    if (error.name === 'AbortError') {
      throw new Error(`Request timed out after ${timeout}ms`);
    }
    throw error;
  }
}

/**
 * API Client class with common methods
 */
class APIClient {
  constructor(baseURL = API_BASE_URL, timeout = DEFAULT_TIMEOUT) {
    this.baseURL = baseURL;
    this.timeout = timeout;
  }

  /** Build full URL — tolerates leading slashes on the endpoint */
  buildURL(endpoint) {
    const cleanEndpoint = endpoint.startsWith('/') ? endpoint.slice(1) : endpoint;
    return this.baseURL ? `${this.baseURL}/${cleanEndpoint}` : `/${cleanEndpoint}`;
  }

  /** GET request */
  async get(endpoint, options = {}) {
    const url = this.buildURL(endpoint);
    const response = await fetchWithTimeout(
      url,
      { method: 'GET', headers: { 'Content-Type': 'application/json', ...options.headers }, ...options },
      options.timeout || this.timeout,
    );

    if (!response.ok) {
      const detail = await _parseErrorBody(response);
      throw new Error(detail);
    }
    return response.json();
  }

  /** POST request */
  async post(endpoint, data = null, options = {}) {
    const url = this.buildURL(endpoint);
    const response = await fetchWithTimeout(
      url,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...options.headers },
        body: data !== null ? JSON.stringify(data) : null,
        ...options,
      },
      options.timeout || this.timeout,
    );

    if (!response.ok) {
      const detail = await _parseErrorBody(response);
      throw new Error(detail);
    }
    return response.json();
  }

  /** PUT request */
  async put(endpoint, data = null, options = {}) {
    const url = this.buildURL(endpoint);
    const response = await fetchWithTimeout(
      url,
      {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json', ...options.headers },
        body: data !== null ? JSON.stringify(data) : null,
        ...options,
      },
      options.timeout || this.timeout,
    );

    if (!response.ok) {
      const detail = await _parseErrorBody(response);
      throw new Error(detail);
    }
    return response.json();
  }

  /** DELETE request */
  async delete(endpoint, options = {}) {
    const url = this.buildURL(endpoint);
    const response = await fetchWithTimeout(
      url,
      { method: 'DELETE', headers: { 'Content-Type': 'application/json', ...options.headers }, ...options },
      options.timeout || this.timeout,
    );

    if (!response.ok) {
      const detail = await _parseErrorBody(response);
      throw new Error(detail);
    }
    // 204 No Content → return null; otherwise parse JSON
    return response.status === 204 ? null : response.json();
  }
}

// Export singleton instance
export const apiClient = new APIClient();

// Export class for custom instances
export default APIClient;
