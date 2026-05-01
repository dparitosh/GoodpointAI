/**
 * useFileFormats — fetches supported file extensions from the backend once
 * and exposes helpers used by file-upload inputs throughout the UI.
 *
 * The backend endpoint is GET /api/multimodal/supported-formats which returns:
 * {
 *   images: [".jpg", ".png", ...],
 *   pdf:    [".pdf"],
 *   excel:  [".xlsx", ".xls", ".xlsm", ".csv", ".tsv"],
 *   word:   [".docx", ".doc"],
 *   cad:    [".dwg", ".dxf", ".step", ".stp", ".iges", ".igs"],
 *   video:  [".mp4", ".avi", ".mov", ".mkv"]
 * }
 *
 * Returned helpers:
 *   allExtensions   – flat sorted string[]  e.g. [".csv", ".docx", ...]
 *   acceptAll       – HTML accept attr string for all types
 *   acceptTabular   – accept string for spreadsheet/tabular types (excel + csv + tsv)
 *   acceptAnalytics – accept string for analytics file imports (json/csv/txt/xml/xlsx)
 *   extsByCategory  – the raw backend response object
 *   loading         – boolean
 *   error           – Error | null
 *
 * Results are cached in module scope so parallel consumers share one request.
 */

import { useState, useEffect } from 'react';
import API_CONFIG from '../config/api-config.js';
import { apiClient } from '../utils/apiClient.js';

// Module-level cache so multiple components share a single fetch
let _cache = null;
let _inflight = null;

async function loadFormats() {
  if (_cache) return _cache;
  if (_inflight) return _inflight;

  _inflight = apiClient
    .get(API_CONFIG.ENDPOINTS.MULTIMODAL_SUPPORTED_FORMATS)
    .then((data) => {
      _cache = data;
      _inflight = null;
      return data;
    })
    .catch((err) => {
      _inflight = null;
      throw err;
    });

  return _inflight;
}

/**
 * Convert an array of extensions into an HTML <input accept="..."> string.
 * Deduplicates and sorts the result.
 */
export function toAcceptString(extensions) {
  return [...new Set(extensions)].sort().join(',');
}

/**
 * Fallback format map used when the backend is unreachable.
 * Keep this in sync with python_backend/graph_api/multimodal_router.py
 */
export const FALLBACK_FORMATS = {
  images: ['.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.webp'],
  pdf:    ['.pdf'],
  excel:  ['.xlsx', '.xls', '.xlsm', '.csv', '.tsv'],
  word:   ['.docx', '.doc'],
  cad:    ['.dwg', '.dxf', '.step', '.stp', '.iges', '.igs'],
  video:  ['.mp4', '.avi', '.mov', '.mkv'],
};

/**
 * Derive commonly-used accept-string subsets from a formats object.
 */
function buildHelpers(fmt) {
  const allExtensions = Object.values(fmt)
    .flat()
    .map((e) => (e.startsWith('.') ? e : `.${e}`));

  return {
    extsByCategory: fmt,
    allExtensions,
    acceptAll: toAcceptString(allExtensions),
    // Spreadsheet / tabular (xlsx, xls, xlsm, csv, tsv)
    acceptTabular: toAcceptString([
      ...(fmt.excel || FALLBACK_FORMATS.excel),
    ]),
    // Analytics file-panel (json, csv, txt, xml, xlsx, tsv)
    acceptAnalytics: toAcceptString([
      '.json', '.csv', '.txt', '.xml', '.tsv',
      ...(fmt.excel || FALLBACK_FORMATS.excel),
    ]),
  };
}

/**
 * React hook. Returns format helpers derived from the backend's
 * /api/multimodal/supported-formats response.
 */
export function useFileFormats() {
  const [state, setState] = useState(() => ({
    ...buildHelpers(FALLBACK_FORMATS),
    loading: true,
    error: null,
  }));

  useEffect(() => {
    let cancelled = false;

    loadFormats()
      .then((data) => {
        if (!cancelled) {
          setState({ ...buildHelpers(data), loading: false, error: null });
        }
      })
      .catch((err) => {
        if (!cancelled) {
          // Keep fallback values so the UI remains functional
          setState((prev) => ({ ...prev, loading: false, error: err }));
        }
      });

    return () => { cancelled = true; };
  }, []);

  return state;
}

export default useFileFormats;
