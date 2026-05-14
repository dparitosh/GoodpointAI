/**
 * MigrationWizard – workflow name uniqueness tests
 *
 * Replicates the bug where a 409 response from POST /api/workflows/ was
 * silently swallowed (showToast was undefined → ReferenceError → caught by the
 * network-error catch → wizard advanced to step 2 anyway).
 *
 * After the fix both handlers correctly call toast.error() and return early,
 * keeping the wizard on step 1.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

// ── Stubs must be declared before any component import (Vitest hoists vi.mock) ─

const mockToastError = vi.fn();
const mockToastSuccess = vi.fn();
const mockToastInfo = vi.fn();

vi.mock('../src/hooks/useToast.js', () => ({
  toast: {
    error: (...args) => mockToastError(...args),
    success: (...args) => mockToastSuccess(...args),
    info: (...args) => mockToastInfo(...args),
    warning: vi.fn(),
    dismiss: vi.fn(),
    clear: vi.fn(),
  },
  useToast: () => ({ toasts: [], dismissToast: vi.fn() }),
  showToast: vi.fn(),
  clearAllToasts: vi.fn(),
  dismissToast: vi.fn(),
  TOAST_TYPES: { SUCCESS: 'success', ERROR: 'error', INFO: 'info', WARNING: 'warning' },
}));

vi.mock('../src/hooks/useGraphQL.js', () => ({
  useGraphQLTransform: () => ({ transform: vi.fn(), loading: false, error: null }),
}));

vi.mock('../src/hooks/useGraphRAG.js', () => ({
  useGraphRAGHealth: () => ({
    healthy: false,
    checkHealth: vi.fn().mockResolvedValue(null),
    startPolling: vi.fn(),
    stopPolling: vi.fn(),
    status: 'unknown',
    error: null,
  }),
  useAISuggestions: () => ({
    suggestions: [],
    loading: false,
    error: null,
    getSuggestions: vi.fn().mockResolvedValue([]),
    clearSuggestions: vi.fn(),
  }),
  useGraphRAGQuery: () => ({
    query: vi.fn().mockResolvedValue({ answers: [], sources: [] }),
    loading: false,
    error: null,
    results: null,
    clearResults: vi.fn(),
  }),
  useGraphRAGTools: () => ({
    executeQuery: vi.fn().mockResolvedValue(null),
    tools: [],
    loading: false,
  }),
}));

vi.mock('../src/hooks/useAgenticAI.js', () => ({
  useAgenticSystemStatus: () => ({
    ready: false,
    status: 'unavailable',
    error: null,
    checkStatus: vi.fn().mockResolvedValue(null),
    startPolling: vi.fn(),
    stopPolling: vi.fn(),
  }),
}));

vi.mock('../src/api/e2etrace-api.js', () => ({
  e2etraceFetchWithRetry: vi.fn(),
}));

vi.mock('../src/components/xstate-visualizer/XStateVisualizer.jsx', () => ({
  XStateVisualizer: () => null,
}));

vi.mock('../src/components/migration-wizard/WizardRuleEngine.jsx', () => ({
  default: () => null,
}));

// ── Component + mocked API import (after vi.mock declarations) ─────────────
import MigrationWizard from '../src/components/migration-wizard/MigrationWizard.jsx';
import { e2etraceFetchWithRetry } from '../src/api/e2etrace-api.js';

// ── Helpers ────────────────────────────────────────────────────────────────

const MOCK_SOURCES = [
  { id: 'src-1', name: 'PLM Source', type: 'rest', status: 'connected' },
  { id: 'tgt-1', name: 'Neo4j Target', type: 'neo4j', status: 'connected' },
];

/** Build a minimal fetch() Response-like object */
function mockFetchResponse(status, body = {}) {
  return Promise.resolve({
    ok: status >= 200 && status < 300,
    status,
    json: () => Promise.resolve(body),
  });
}

/** Render inside a MemoryRouter so useSearchParams works */
const renderWizard = () =>
  render(
    <MemoryRouter>
      <MigrationWizard />
    </MemoryRouter>
  );

/**
 * Fill in the step-1 form and return the "Next" button element.
 * Requires sources to already be rendered in the dropdowns.
 */
async function fillStep1(workflowName = 'Test Workflow') {
  // Workflow name
  const nameInput = await screen.findByLabelText(/workflow instance name/i);
  await act(async () => {
    fireEvent.change(nameInput, { target: { value: workflowName } });
  });

  // Source dropdown
  const [sourceSelect, targetSelect] = screen.getAllByRole('combobox');
  await act(async () => {
    fireEvent.change(sourceSelect, { target: { value: 'src-1' } });
  });
  await act(async () => {
    fireEvent.change(targetSelect, { target: { value: 'tgt-1' } });
  });

  return screen.getByRole('button', { name: /next/i });
}

// ── Setup / teardown ───────────────────────────────────────────────────────

beforeEach(() => {
  mockToastError.mockClear();
  mockToastSuccess.mockClear();
  mockToastInfo.mockClear();

  // Mock e2etraceFetchWithRetry for data-source/template loads on mount
  e2etraceFetchWithRetry.mockImplementation((url) => {
    const urlStr = String(url);
    if (urlStr.includes('data-sources') || urlStr.includes('datasources')) {
      return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(MOCK_SOURCES) });
    }
    // mapping-templates and anything else → empty array
    return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve([]) });
  });

  // Stub global fetch — tests override this per-scenario
  vi.stubGlobal('fetch', vi.fn());
});

afterEach(() => {
  vi.unstubAllGlobals();
});

// ── Tests ──────────────────────────────────────────────────────────────────

describe('MigrationWizard – workflow name uniqueness (step 1 → step 2 navigation)', () => {

  it('POST 409: stays on step 1 and shows an error toast when name already exists', async () => {
    // Arrange: backend returns 409 for the new-workflow POST
    vi.mocked(fetch).mockImplementation(() =>
      mockFetchResponse(409, { detail: 'A workflow named "Test Workflow" already exists.' })
    );

    renderWizard();
    const nextBtn = await fillStep1('Test Workflow');

    // Act: click Next (triggers nextStep → POST → 409)
    await act(async () => {
      fireEvent.click(nextBtn);
    });

    // Assert: toast.error was called with the duplicate-name message
    expect(mockToastError).toHaveBeenCalledOnce();
    expect(mockToastError.mock.calls[0][0]).toMatch(/Test Workflow/);

    // Assert: wizard did NOT advance — step 1 heading still visible
    expect(screen.getByText('Configure Data Sources')).toBeInTheDocument();
    expect(screen.queryByText('Data Discovery')).not.toBeInTheDocument();
  });

  it('POST 409: uses the generic fallback message when backend returns no detail', async () => {
    vi.mocked(fetch).mockImplementation(() =>
      mockFetchResponse(409, {})  // empty body — no .detail field
    );

    renderWizard();
    const nextBtn = await fillStep1('Duplicate Name');

    await act(async () => {
      fireEvent.click(nextBtn);
    });

    expect(mockToastError).toHaveBeenCalledOnce();
    expect(mockToastError.mock.calls[0][0]).toMatch(/already exists/i);

    // Still on step 1
    expect(screen.getByText('Configure Data Sources')).toBeInTheDocument();
  });

  it('POST 200: advances to step 2 when the workflow name is unique', async () => {
    vi.mocked(fetch).mockImplementation(() =>
      mockFetchResponse(200, { id: 'wf-new-1', name: 'New Workflow' })
    );

    renderWizard();
    const nextBtn = await fillStep1('New Workflow');

    await act(async () => {
      fireEvent.click(nextBtn);
    });

    // No error toast
    expect(mockToastError).not.toHaveBeenCalled();

    // Wizard moved to step 2
    await waitFor(() =>
      expect(screen.getByText('Data Discovery')).toBeInTheDocument()
    );
  });

  it('PATCH 409: stays on step 1 and shows an error toast when renaming to a duplicate', async () => {
    // First POST succeeds — saves workflow id 'wf-existing'
    vi.mocked(fetch)
      .mockImplementationOnce(() => mockFetchResponse(200, { id: 'wf-existing', name: 'Original Name' }))
      // Go back to step 1, then PATCH → 409
      .mockImplementationOnce(() =>
        mockFetchResponse(409, { detail: 'A workflow named "Taken Name" already exists.' })
      );

    renderWizard();

    // Step 1 → step 2 (POST 200)
    let nextBtn = await fillStep1('Original Name');
    await act(async () => { fireEvent.click(nextBtn); });
    await waitFor(() => expect(screen.getByText('Data Discovery')).toBeInTheDocument());

    // Go back to step 1
    const prevBtn = screen.getByRole('button', { name: /previous/i });
    await act(async () => { fireEvent.click(prevBtn); });
    await waitFor(() => expect(screen.getByText('Configure Data Sources')).toBeInTheDocument());

    // Change workflow name and try to proceed again (PATCH path)
    const nameInput = screen.getByLabelText(/workflow instance name/i);
    await act(async () => {
      fireEvent.change(nameInput, { target: { value: 'Taken Name' } });
    });

    nextBtn = screen.getByRole('button', { name: /next/i });
    await act(async () => { fireEvent.click(nextBtn); });

    // toast.error called for the rename conflict
    await waitFor(() => expect(mockToastError).toHaveBeenCalledOnce());
    expect(mockToastError.mock.calls[0][0]).toMatch(/Taken Name/);

    // Still on step 1
    expect(screen.getByText('Configure Data Sources')).toBeInTheDocument();
    expect(screen.queryByText('Data Discovery')).not.toBeInTheDocument();
  });

  it('network error on POST: wizard still advances (non-fatal path)', async () => {
    // Simulate a network failure — fetch throws
    vi.mocked(fetch).mockRejectedValue(new Error('Network error'));

    renderWizard();
    const nextBtn = await fillStep1('Network Fail Workflow');

    await act(async () => {
      fireEvent.click(nextBtn);
    });

    // Network errors are intentionally non-fatal — no toast, wizard advances
    expect(mockToastError).not.toHaveBeenCalled();
    await waitFor(() =>
      expect(screen.getByText('Data Discovery')).toBeInTheDocument()
    );
  });

});
