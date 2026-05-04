/**
 * MigrationWizard – Step 2 "Run Discovery" tests
 *
 * Covers:
 *  1. Real source sampling → real field names inferred via union-of-keys
 *  2. Multi-file schema: records with different keys → all keys shown
 *  3. Sampling fallback → synthetic records → "Source Fields Not Detected" UI
 *  4. SODA pass: DQ scan returns pass → insight shows "pass"
 *  5. SODA unavailable: DQ scan throws → "SODA scan not available" insight
 *  6. Agentic path succeeds: agent returns schema+mappings → skips legacy SODA
 *  7. ETL run creation fails → discovery status → 'failed', error shown
 *  8. Discovery button disabled while in-flight, re-enabled after
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

// ── Stubs (must be before component import — Vitest hoists vi.mock) ────────

vi.mock('../src/hooks/useToast.js', () => ({
  toast: {
    error: vi.fn(),
    success: vi.fn(),
    info: vi.fn(),
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

// ── Imports after vi.mock ──────────────────────────────────────────────────
import MigrationWizard from '../src/components/migration-wizard/MigrationWizard.jsx';
import { e2etraceFetchWithRetry } from '../src/api/e2etrace-api.js';

// ── Constants ─────────────────────────────────────────────────────────────

const SOURCE = { id: 'conn_local_folder_abc', name: 'sampletest', type: 'local_folder', status: 'active' };
const TARGET = { id: 'tgt-neo4j-1', name: 'Neo4j Target', type: 'neo4j', status: 'connected' };
const MOCK_SOURCES = [SOURCE, TARGET];

const DISCOVERY_RUN_ID = 'run_discovery_test_001';

// ── Helpers ───────────────────────────────────────────────────────────────

function ok(body) {
  return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(body) });
}

function fail(status, body = {}) {
  return Promise.resolve({ ok: false, status, json: () => Promise.resolve(body) });
}

function throws(msg = 'Network error') {
  return Promise.reject(new Error(msg));
}

/** Render the wizard inside a MemoryRouter */
const renderWizard = () =>
  render(
    <MemoryRouter>
      <MigrationWizard />
    </MemoryRouter>
  );

/**
 * Advance the wizard to Step 2 (Discovery) using the given mock implementation
 * for e2etraceFetchWithRetry.
 *
 * @param {Function} fetchImpl  - mock implementation used once step-1 Next is clicked
 */
async function advanceToStep2(fetchImpl) {
  // Step 1 loads data-sources on mount — serve the list
  e2etraceFetchWithRetry.mockImplementation((url) => {
    const u = String(url);
    if (u.includes('data-sources') || u.includes('datasources')) {
      return ok(MOCK_SOURCES);
    }
    return ok([]);
  });

  renderWizard();

  // Fill step 1
  const nameInput = await screen.findByLabelText(/workflow instance name/i);
  await act(async () => { fireEvent.change(nameInput, { target: { value: 'My Discovery Test' } }); });

  const [sourceSelect, targetSelect] = screen.getAllByRole('combobox');
  await act(async () => { fireEvent.change(sourceSelect, { target: { value: SOURCE.id } }); });
  await act(async () => { fireEvent.change(targetSelect, { target: { value: TARGET.id } }); });

  // Switch mock to the step-1→step-2 transition handler (workflow POST)
  vi.mocked(fetch).mockResolvedValue({ ok: true, status: 200, json: () => Promise.resolve({ id: 'wf_test_001', name: 'My Discovery Test' }) });

  const nextBtn = screen.getByRole('button', { name: /next/i });
  await act(async () => { fireEvent.click(nextBtn); });

  // Now on step 2 — switch mock to the fetchImpl for discovery calls
  e2etraceFetchWithRetry.mockImplementation(fetchImpl);
}

// ── Shared discovery fetch builder ────────────────────────────────────────

/**
 * Builds a fetch mock that covers the full discovery call chain.
 *
 * @param {object} opts
 *  - sampleRecords: array of records returned by /api/data-sources/.../sample
 *  - sampleSourceFiles: optional source_files array in the sample response (per-file metadata)
 *  - sodaResult: object returned by dq/scan  (null → endpoint throws)
 *  - agentResult: falsy = agent fails (503), object = agent succeeds
 *  - ingestResult: optional override for the Agent Director /discovery/ingest response
 */
function buildDiscoveryFetch({ sampleRecords = null, sampleSourceFiles = null, sodaResult = null, agentResult = null, ingestResult = null } = {}) {
  return (url, opts) => {
    const u = String(url);
    const method = (opts?.method || 'GET').toUpperCase();

    // Mount-time data-sources list
    if (u.includes('/api/data-sources') && !u.includes('/sample') && method === 'GET') {
      return ok(MOCK_SOURCES);
    }
    // Sample endpoint
    if (u.includes('/sample')) {
      if (sampleRecords) {
        const base = { records: sampleRecords, warnings: ['Sampled from: file.csv'] };
        if (sampleSourceFiles) base.source_files = sampleSourceFiles;
        return ok(base);
      }
      return ok({ records: [], warnings: ['No parseable files found'] });
    }
    // ETL run creation
    if (u.includes('/api/plm/etl/runs') && method === 'POST' && !u.includes('/stage') && !u.includes('/dq') && !u.includes('/gates')) {
      return ok({ run_id: DISCOVERY_RUN_ID, status: 'created' });
    }
    // Stage records
    if (u.includes('/stage') && method === 'POST') {
      return ok({ run_id: DISCOVERY_RUN_ID, staged_count: sampleRecords?.length ?? 3, status: 'staged' });
    }
    // Agentic task
    if (u.includes('/api/agentic/task')) {
      if (agentResult) return ok({ success: true, result: agentResult });
      return fail(503, { detail: 'MCP not running' });
    }
    // Agent Director ingest
    if (u.includes('/api/agentic/discovery/ingest') && method === 'POST') {
      return ok(ingestResult ?? {
        report_id: 'rpt_test_001',
        run_id: DISCOVERY_RUN_ID,
        recommended_actions: [],
        semantic_insights: {},
        mapping_suggestions: [],
        dq_violations: [],
        dq_violations_count: 0,
      });
    }
    // DQ scan (SODA legacy)
    if (u.includes('/dq/scan') && method === 'POST') {
      if (sodaResult) return ok(sodaResult);
      return throws('DQ scan unavailable');
    }
    // DQ gates
    if (u.includes('/dq/gates')) {
      return ok({ gates: [] });
    }
    // Templates, workflows, anything else
    return ok([]);
  };
}

// ── Setup / teardown ──────────────────────────────────────────────────────

beforeEach(() => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
    ok: true, status: 200, json: () => Promise.resolve({ id: 'wf_test_001', name: 'My Discovery Test' })
  }));
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.clearAllMocks();
});

// ── Tests ─────────────────────────────────────────────────────────────────

describe('MigrationWizard – Step 2 Run Discovery', () => {

  // ── 1. Real source sampling → real field names ──────────────────────────
  it('shows real inferred field names when sample endpoint returns records', async () => {
    const sampleRecords = [
      { 'labels(n)': '["XmlTag"]', 'n.name': 'AP242DataContainer', 'n._name': 'complexType' },
      { 'labels(n)': '["XmlTag"]', 'n.name': 'BasicData', 'n._name': 'simpleType' },
    ];

    await advanceToStep2(buildDiscoveryFetch({ sampleRecords, sodaResult: { overall_score: 1, status: 'pass', issues_count: 0 } }));

    const runBtn = screen.getByRole('button', { name: /run discovery/i });
    await act(async () => { fireEvent.click(runBtn); });

    await waitFor(() => {
      expect(screen.queryByText(/running discovery/i)).not.toBeInTheDocument();
    }, { timeout: 5000 });

    // Should NOT show "Source Fields Not Detected"
    expect(screen.queryByText(/source fields not detected/i)).not.toBeInTheDocument();

    // Should show the "Field Intelligence" section with all 3 keys
    // (fields appear in both field rows and sample table headers → use getAllByText)
    expect(screen.getByText('Field Intelligence')).toBeInTheDocument();
    expect(screen.getAllByText('labels(n)').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('n.name').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('n._name').length).toBeGreaterThanOrEqual(1);
  });

  // ── 2. Multi-file schema union ──────────────────────────────────────────
  it('shows union of all keys when records come from multiple files with different schemas', async () => {
    // Records from file 1 have cols A,B; records from file 2 have cols C,D
    const sampleRecords = [
      { part_number: 'PN-001', manufacturer: 'Acme' },
      { title: 'Bearing Assembly', mpn: 'BR-42' },
    ];

    await advanceToStep2(buildDiscoveryFetch({ sampleRecords, sodaResult: { overall_score: 1, status: 'pass', issues_count: 0 } }));

    const runBtn = screen.getByRole('button', { name: /run discovery/i });
    await act(async () => { fireEvent.click(runBtn); });

    await waitFor(() => {
      expect(screen.queryByText(/running discovery/i)).not.toBeInTheDocument();
    }, { timeout: 5000 });

    // All four keys from both records should appear
    // (fields appear in both chips and sample table headers → use getAllByText)
    expect(screen.getAllByText('part_number').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('manufacturer').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('title').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('mpn').length).toBeGreaterThanOrEqual(1);
  });

  // ── 3. Sampling fallback → synthetic → "Source Fields Not Detected" ─────
  it('shows "Source Fields Not Detected" when sampling returns empty records', async () => {
    // Sample endpoint returns empty → synthetic fallback → stagedFrom = 'synthetic'
    await advanceToStep2(buildDiscoveryFetch({
      sampleRecords: null,      // triggers synthetic fallback
      sodaResult: { overall_score: 1, status: 'pass', issues_count: 0 },
    }));

    const runBtn = screen.getByRole('button', { name: /run discovery/i });
    await act(async () => { fireEvent.click(runBtn); });

    await waitFor(() => {
      expect(screen.queryByText(/running discovery/i)).not.toBeInTheDocument();
    }, { timeout: 5000 });

    expect(screen.getByText(/source fields not detected/i)).toBeInTheDocument();
    expect(screen.getByText(/could not connect to the source system for live sampling/i)).toBeInTheDocument();
    // The inferred fields panel (with chip badges) should NOT appear
    expect(screen.queryByText(/inferred source fields/i)).not.toBeInTheDocument();
  });

  // ── 4. SODA pass ─────────────────────────────────────────────────────────
  it('shows SODA pass insight when DQ scan returns overall_score: 1, status: pass', async () => {
    const sodaResult = { overall_score: 1, status: 'pass', issues_count: 0 };
    await advanceToStep2(buildDiscoveryFetch({
      sampleRecords: [{ id: '1', name: 'Part A' }],
      sodaResult,
    }));

    const runBtn = screen.getByRole('button', { name: /run discovery/i });
    await act(async () => { fireEvent.click(runBtn); });

    await waitFor(() => {
      expect(screen.queryByText(/running discovery/i)).not.toBeInTheDocument();
    }, { timeout: 5000 });

    // KPI strip shows "Data Quality" label and "SODA gate: PASS" sub-text
    expect(screen.getByText('Data Quality')).toBeInTheDocument();
    expect(screen.getByText('SODA gate: PASS')).toBeInTheDocument();
  });

  // ── 5. SODA unavailable ───────────────────────────────────────────────────
  it('shows "SODA scan not available" insight when DQ scan endpoint throws', async () => {
    // sodaResult: null → fetch mock throws for /dq/scan
    await advanceToStep2(buildDiscoveryFetch({
      sampleRecords: [{ id: '1', name: 'Part A' }],
      sodaResult: null,
    }));

    const runBtn = screen.getByRole('button', { name: /run discovery/i });
    await act(async () => { fireEvent.click(runBtn); });

    await waitFor(() => {
      expect(screen.queryByText(/running discovery/i)).not.toBeInTheDocument();
    }, { timeout: 5000 });

    // KPI strip shows "Data Quality" label and "Not yet scanned" sub-text when SODA unavailable
    expect(screen.getByText('Data Quality')).toBeInTheDocument();
    expect(screen.getByText('Not yet scanned')).toBeInTheDocument();
  });

  // ── 6. Agentic path succeeds ──────────────────────────────────────────────
  it('uses agent-provided schema and mappings when agentic/task returns success', async () => {
    const agentResult = {
      quality_scan: { overall_score: 0.92, status: 'pass', issues_count: 1 },
      inferred_schema: { component_id: 'string', assembly_name: 'string', bom_level: 'integer' },
      applied_mapping: { component_id: 'node_id', assembly_name: 'label', bom_level: 'depth' },
    };

    await advanceToStep2(buildDiscoveryFetch({ agentResult }));

    const runBtn = screen.getByRole('button', { name: /run discovery/i });
    await act(async () => { fireEvent.click(runBtn); });

    await waitFor(() => {
      expect(screen.queryByText(/running discovery/i)).not.toBeInTheDocument();
    }, { timeout: 5000 });

    // Agent-inferred fields appear in both the chips panel and mapping rows
    expect(screen.getAllByText('component_id').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('assembly_name').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('bom_level').length).toBeGreaterThanOrEqual(1);

    // Agent-provided target mappings appear in mapping hints (inline field row + mapping section)
    expect(screen.getAllByText('node_id').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('label').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('depth').length).toBeGreaterThanOrEqual(1);
  });

  // ── 7. ETL run creation fails → discovery shows error ────────────────────
  it('sets discoveryStatus to failed when ETL run POST fails', async () => {
    await advanceToStep2((url, opts) => {
      const u = String(url);
      const method = (opts?.method || 'GET').toUpperCase();
      if (u.includes('/api/data-sources') && !u.includes('/sample')) return ok(MOCK_SOURCES);
      if (u.includes('/sample')) return ok({ records: [], warnings: [] });
      // ETL run creation → 500
      if (u.includes('/api/plm/etl/runs') && method === 'POST') return fail(500, { detail: 'DB error' });
      return ok([]);
    });

    const runBtn = screen.getByRole('button', { name: /run discovery/i });
    await act(async () => { fireEvent.click(runBtn); });

    await waitFor(() => {
      expect(screen.queryByText(/running discovery/i)).not.toBeInTheDocument();
    }, { timeout: 5000 });

    // "Continue Without Discovery" should appear (failed state)
    expect(screen.getByRole('button', { name: /continue without discovery/i })).toBeInTheDocument();
  });

  // ── 8. Button disabled during in-flight, re-enabled after ─────────────────
  it('disables the Run Discovery button while discovery is in-flight', async () => {
    // Use a never-resolving promise for ETL run creation to freeze mid-flight
    let resolveRun;
    const runPromise = new Promise((res) => { resolveRun = res; });

    await advanceToStep2((url, opts) => {
      const u = String(url);
      const method = (opts?.method || 'GET').toUpperCase();
      if (u.includes('/api/data-sources') && !u.includes('/sample')) return ok(MOCK_SOURCES);
      if (u.includes('/sample')) return ok({ records: [], warnings: [] });
      if (u.includes('/api/plm/etl/runs') && method === 'POST') return runPromise;
      return ok([]);
    });

    const runBtn = screen.getByRole('button', { name: /run discovery/i });
    await act(async () => { fireEvent.click(runBtn); });

    // While in-flight, button should show "Running Discovery..." and be disabled
    expect(screen.getByRole('button', { name: /running discovery/i })).toBeDisabled();

    // Resolve the run so the component can finish
    await act(async () => {
      resolveRun({ ok: false, status: 500, json: () => Promise.resolve({}) });
    });

    await waitFor(() => {
      expect(screen.queryByText(/running discovery/i)).not.toBeInTheDocument();
    }, { timeout: 5000 });

    // After completion, button is re-enabled
    expect(screen.getByRole('button', { name: /run discovery/i })).not.toBeDisabled();
  });

  // ── 9. Agent Director actions rendered in DiscoveryResults ───────────────
  it('shows Agent-recommended actions panel when ingest returns recommended_actions', async () => {
    const ingestResult = {
      report_id: 'rpt_test_002',
      run_id: DISCOVERY_RUN_ID,
      recommended_actions: [
        {
          priority: 2,
          action: 'resolve_dq_violations',
          label: 'Fix critical DQ violations',
          reason: '2 critical rule(s) violated',
          detail: 'null_check: null_rate 0.30 > threshold 0.10',
          severity: 'error',
        },
        {
          priority: 4,
          action: 'proceed_to_mapping',
          label: 'Proceed to Field Mapping',
          reason: 'Source registered and fields detected',
          detail: null,
          severity: 'success',
        },
      ],
      semantic_insights: {},
      mapping_suggestions: [],
      dq_violations: [],
      dq_violations_count: 0,
    };

    await advanceToStep2(buildDiscoveryFetch({
      sampleRecords: [{ id: '1', name: 'Part A' }],
      sodaResult: { overall_score: 0.9, status: 'pass', issues_count: 0 },
      ingestResult,
    }));

    const runBtn = screen.getByRole('button', { name: /run discovery/i });
    await act(async () => { fireEvent.click(runBtn); });

    await waitFor(() => {
      expect(screen.queryByText(/running discovery/i)).not.toBeInTheDocument();
    }, { timeout: 5000 });

    // The "Agent-recommended actions" panel heading
    expect(screen.getByText(/agent-recommended actions/i)).toBeInTheDocument();

    // Both action labels appear (first label also injected as an insight → getAllByText)
    expect(screen.getAllByText(/fix critical dq violations/i).length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText(/proceed to field mapping/i).length).toBeGreaterThanOrEqual(1);
  });

  // ── 10. Source File Inventory rendered for local_folder source ────────────
  it('shows Source File Inventory with per-file rows when sample returns source_files', async () => {
    const sampleRecords = [
      { part_number: 'PN-001', manufacturer: 'Acme', description: 'Bearing' },
      { supplier_id: 'SUP-1', name: 'Acme Corp', country: 'US' },
    ];
    const sampleSourceFiles = [
      { name: 'parts.csv',     type: 'csv', record_count: 48, field_count: 3, field_names: ['part_number', 'manufacturer', 'description'] },
      { name: 'suppliers.csv', type: 'csv', record_count: 22, field_count: 3, field_names: ['supplier_id', 'name', 'country'] },
    ];

    await advanceToStep2(buildDiscoveryFetch({
      sampleRecords,
      sampleSourceFiles,
      sodaResult: { overall_score: 1, status: 'pass', issues_count: 0 },
    }));

    const runBtn = screen.getByRole('button', { name: /run discovery/i });
    await act(async () => { fireEvent.click(runBtn); });

    await waitFor(() => {
      expect(screen.queryByText(/running discovery/i)).not.toBeInTheDocument();
    }, { timeout: 5000 });

    // Section heading should be "Source File Inventory" not "Entity Type Inventory"
    expect(screen.getByText('Source File Inventory')).toBeInTheDocument();
    expect(screen.queryByText('Entity Type Inventory')).not.toBeInTheDocument();

    // KPI strip should show "Files Scanned" not "Entity Types"
    expect(screen.getByText('Files Scanned')).toBeInTheDocument();

    // Each file name should appear in the scoreboard
    expect(screen.getByText('parts.csv')).toBeInTheDocument();
    expect(screen.getByText('suppliers.csv')).toBeInTheDocument();
  });

});
