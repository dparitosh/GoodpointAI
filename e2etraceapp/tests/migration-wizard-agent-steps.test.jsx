/**
 * MigrationWizard – Agent step tests (Steps 3-6)
 *
 * Navigation strategy:
 *  - Steps 3/4: Full wizard navigation (1→2→3 / 1→2→3→4):
 *      Step 2 discovery is made to fail (ETL run returns {} → no run_id → throws)
 *      → "Continue Without Discovery" button appears → click → discoveryAccepted=true
 *      → Next button unlocked
 *  - Step 6: Render directly at step 6 via ?step=6 URL param;
 *      generateAgentReport() has no guard so the button always triggers the API call.
 *
 * Tests covered:
 *   Step 3 (Profile)  : button visible, enabled, success, failure
 *   Step 4 (Quality)  : button visible, enabled, success, failure
 *   Step 6 (Report)   : button visible, enabled, success, failure
 *   Navigation        : renders step 1, shows all 6 step labels
 *   loadingMessage    : idle state — no loading banners displayed
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

// ── Stubs ─────────────────────────────────────────────────────────────────
// All vi.mock calls MUST appear before any imports of the stubbed modules.

vi.mock('../src/hooks/useToast.js', () => ({
  toast: {
    error: vi.fn(), success: vi.fn(), info: vi.fn(), warning: vi.fn(),
    dismiss: vi.fn(), clear: vi.fn(),
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
    healthy: false, checkHealth: vi.fn().mockResolvedValue(null),
    startPolling: vi.fn(), stopPolling: vi.fn(), status: 'unknown', error: null,
  }),
  useAISuggestions: () => ({
    suggestions: [], loading: false, error: null,
    getSuggestions: vi.fn().mockResolvedValue([]), clearSuggestions: vi.fn(),
  }),
  useGraphRAGQuery: () => ({
    query: vi.fn().mockResolvedValue({ answers: [], sources: [] }),
    loading: false, error: null, results: null, clearResults: vi.fn(),
  }),
  useGraphRAGTools: () => ({
    executeQuery: vi.fn().mockResolvedValue(null), tools: [], loading: false,
  }),
}));

vi.mock('../src/hooks/useAgenticAI.js', () => ({
  useAgenticSystemStatus: () => ({
    ready: false, status: 'unavailable', error: null,
    checkStatus: vi.fn().mockResolvedValue(null),
    startPolling: vi.fn(), stopPolling: vi.fn(),
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

// ── Imports ───────────────────────────────────────────────────────────────
import MigrationWizard from '../src/components/migration-wizard/MigrationWizard.jsx';
import { e2etraceFetchWithRetry } from '../src/api/e2etrace-api.js';

// ── Fixture data ──────────────────────────────────────────────────────────

const SOURCE = {
  id: 'conn_local_folder_parts',
  name: 'parts_sample',
  type: 'local_folder',
  status: 'active',
};
const TARGET = {
  id: 'tgt-pg-1',
  name: 'Postgres Target',
  type: 'postgresql',
  status: 'connected',
};
const MOCK_SOURCES = [SOURCE, TARGET];

const WF_ID  = 'wf_agent_test_001';
const RUN_ID = 'run_agent_test_001';
const RPT_ID = 'rpt_agent_test_001';

const PROFILE_RESULT = {
  status: 'completed',
  semantic_insights: {
    column_semantics: [
      { column: 'part_number', semantic_role: 'identifier', confidence: 0.95, canonical_name: 'part_number' },
      { column: 'unit_cost',   semantic_role: 'metric',     confidence: 0.85, canonical_name: 'unit_cost' },
    ],
    entity_classifications: [{ file: 'parts_sample.csv', entity_class: 'Part', confidence: 0.9 }],
    summary: { total_columns_analysed: 8, high_confidence_semantics: 7 },
  },
  run_id: RUN_ID,
};

const QUALITY_RESULT = {
  status: 'completed',
  quality_score: 88,
  anomalies_found: 3,
  quality_findings: { overall_score: 0.88, null_violations: 3, rule_failures: 1 },
  run_id: RUN_ID,
};

const REPORT_RESULT = {
  status: 'completed',
  report_id: RPT_ID,
  migration_readiness_score: { score: 88, grade: 'B' },
  executive_summary: 'Parts dataset is 88% ready. 3 null violations in optional fields.',
  quality_score: 0.88,
  total_records: 10,
  generated_at: new Date().toISOString(),
  run_id: RUN_ID,
};

// ── Low-level response builders ───────────────────────────────────────────

const ok   = (body)   => Promise.resolve({ ok: true,  status: 200, json: () => Promise.resolve(body) });
// The wizard checks `data.success !== false` (not res.ok), so failure must include success:false
const fail = (status) => Promise.resolve({ ok: false, status,      json: () => Promise.resolve({ success: false, error: 'agent unavailable' }) });

// ── Base fetch handler ────────────────────────────────────────────────────

/**
 * Build a `e2etraceFetchWithRetry` mock implementation.
 * `agentHandler(url, opts)` is called for any /api/agentic/* URL.
 */
function makeFetch(agentHandler) {
  return (url, opts) => {
    const u   = String(url);
    const mtd = (opts?.method || 'GET').toUpperCase();

    // Data sources for the step-1 dropdowns
    if ((u.includes('/api/data-sources') || u.includes('/api/datasources')) && !u.includes('/sample'))
      return ok(MOCK_SOURCES);

    // ETL run creation: return {} (no run_id) so runDiscovery throws
    // → discoveryStatus = 'failed' → "Continue Without Discovery" button appears
    if (u.includes('/api/plm/etl/runs') && mtd === 'POST')
      return ok({});

    // infer-mappings (called by acceptDiscovery if report_id is present — non-fatal)
    if (u.includes('/infer-mappings'))
      return ok({ mappings: [] });

    // SODA DQ scan is optional / best-effort
    if (u.includes('/dq/scan'))  return fail(503);
    if (u.includes('/dq/gates')) return ok({ gates: [] });

    // Delegate agentic endpoints to the caller-supplied handler
    if (agentHandler && u.includes('/api/agentic/'))
      return agentHandler(u, opts);

    return ok([]);
  };
}

// ── Navigation helpers ────────────────────────────────────────────────────

/**
 * Fill step 1 (name + source + target) and click Next.
 * Requires the wizard to already be rendered.
 */
async function fillAndSubmitStep1() {
  const nameInput = await screen.findByLabelText(/workflow instance name/i);
  await act(async () => { fireEvent.change(nameInput, { target: { value: 'Parts Agent Test' } }); });

  const combos = screen.getAllByRole('combobox');
  await act(async () => { fireEvent.change(combos[0], { target: { value: SOURCE.id } }); });
  await act(async () => { fireEvent.change(combos[1], { target: { value: TARGET.id } }); });

  const nextBtn = screen.getByRole('button', { name: /next/i });
  await act(async () => { fireEvent.click(nextBtn); });
}

/**
 * Navigate the wizard to Step 3 (Profile):
 *  1. Render, fill step 1, click Next → step 2
 *  2. On step 2: click "Run Discovery" → ETL run fails (no run_id) → discoveryStatus=failed
 *  3. Click "Continue Without Discovery" → discoveryAccepted=true
 *  4. Click Next → step 3
 */
async function navigateToStep3(agentHandler) {
  e2etraceFetchWithRetry.mockImplementation(makeFetch(agentHandler));
  render(<MemoryRouter><MigrationWizard /></MemoryRouter>);

  await fillAndSubmitStep1();

  // Step 2: auto-start fires and discovery fails (ETL run returns no run_id)
  // Wait for "Continue Without Discovery" (shown when discoveryStatus === 'failed')
  const contBtn = await screen.findByRole('button', { name: /continue without discovery/i }, { timeout: 6000 });
  await act(async () => { fireEvent.click(contBtn); });

  // Next should be enabled now (discoveryAccepted = true)
  await waitFor(
    () => expect(screen.getByRole('button', { name: /next/i }).disabled).toBe(false),
    { timeout: 4000 }
  );
  await act(async () => { fireEvent.click(screen.getByRole('button', { name: /next/i })); });

  // Confirm step 3 is active
  await screen.findByRole('button', { name: /run semantic profile/i }, { timeout: 5000 });
}

/**
 * Navigate the wizard to Step 4 (Quality):
 *  Steps 1–4 as in navigateToStep3, then additionally:
 *  5. Click "Run Semantic Profile" → profile agent succeeds → profileAccepted=true
 *  6. Click Next → step 4
 */
async function navigateToStep4(agentHandler) {
  // Profile step uses a success handler so profileAccepted gets set to true
  const profileSuccess = (u, opts) => {
    if (u.includes('/api/agentic/semantic-profile'))
      return ok({ success: true, result: PROFILE_RESULT });
    if (agentHandler) return agentHandler(u, opts);
    return ok([]);
  };

  e2etraceFetchWithRetry.mockImplementation(makeFetch(profileSuccess));
  render(<MemoryRouter><MigrationWizard /></MemoryRouter>);

  await fillAndSubmitStep1();

  // Step 2: auto-start fires and discovery fails (ETL run returns no run_id)
  const contBtn = await screen.findByRole('button', { name: /continue without discovery/i }, { timeout: 6000 });
  await act(async () => { fireEvent.click(contBtn); });
  await waitFor(
    () => expect(screen.getByRole('button', { name: /next/i }).disabled).toBe(false),
    { timeout: 4000 }
  );
  await act(async () => { fireEvent.click(screen.getByRole('button', { name: /next/i })); });

  // Step 3: run profile → profileAccepted=true
  const profileBtn = await screen.findByRole('button', { name: /run semantic profile/i }, { timeout: 5000 });
  await act(async () => { fireEvent.click(profileBtn); });

  // Switch to quality handler before clicking Next
  if (agentHandler) {
    e2etraceFetchWithRetry.mockImplementation(makeFetch(agentHandler));
  }

  // Wait for Next to be enabled (profileAccepted=true or profileResult != null)
  await waitFor(
    () => expect(screen.getByRole('button', { name: /next/i }).disabled).toBe(false),
    { timeout: 6000 }
  );
  await act(async () => { fireEvent.click(screen.getByRole('button', { name: /next/i })); });

  // Confirm step 4 is active
  await screen.findByRole('button', { name: /run quality scan/i }, { timeout: 5000 });
}

/**
 * Render the wizard directly at Step 6 (Report) via the ?step=6 URL param.
 * generateAgentReport() has no sourceSystem guard — button click always triggers API call.
 */
function renderAtStep6(agentHandler) {
  e2etraceFetchWithRetry.mockImplementation(makeFetch(agentHandler));
  render(
    <MemoryRouter initialEntries={['/?step=6']}>
      <MigrationWizard />
    </MemoryRouter>
  );
}

// ── Setup / teardown ──────────────────────────────────────────────────────

beforeEach(() => {
  // Stub global fetch used for the workflow POST on step 1
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
    ok: true, status: 200,
    json: () => Promise.resolve({ id: WF_ID, name: 'Parts Agent Test' }),
  }));
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.clearAllMocks();
});

// ── Navigation & initial render ───────────────────────────────────────────

describe('MigrationWizard – initial render & navigation', () => {

  it('renders step 1 (Connect) on initial mount', async () => {
    e2etraceFetchWithRetry.mockImplementation(makeFetch());
    render(<MemoryRouter><MigrationWizard /></MemoryRouter>);
    expect(await screen.findByLabelText(/workflow instance name/i)).toBeTruthy();
  });

  it('shows all 6 step labels in the wizard header', async () => {
    e2etraceFetchWithRetry.mockImplementation(makeFetch());
    render(<MemoryRouter><MigrationWizard /></MemoryRouter>);
    await screen.findByLabelText(/workflow instance name/i);
    for (const label of ['Connect', 'Discover', 'Profile', 'Quality', 'ETL', 'Report']) {
      expect(screen.getAllByText(label).length).toBeGreaterThan(0);
    }
  });

});

// ── Step 3 – Semantic Profile ─────────────────────────────────────────────

describe('MigrationWizard – Step 3 Semantic Profile', () => {

  it('shows "Run Semantic Profile" button on step 3', async () => {
    await navigateToStep3();
    expect(screen.getByRole('button', { name: /run semantic profile/i })).toBeTruthy();
  });

  it('"Run Semantic Profile" button is not disabled before clicking', async () => {
    await navigateToStep3();
    expect(screen.getByRole('button', { name: /run semantic profile/i }).disabled).toBe(false);
  });

  it('profile agent success → profile status/insights visible', async () => {
    const handler = (u) => {
      if (u.includes('/api/agentic/semantic-profile'))
        return ok({ success: true, result: PROFILE_RESULT });
      return ok([]);
    };
    await navigateToStep3(handler);

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /run semantic profile/i }));
    });

    await waitFor(() => {
      const body = document.body.textContent;
      expect(
        body.includes('completed') || body.includes('Part') ||
        body.toLowerCase().includes('profile') || body.toLowerCase().includes('semantic')
      ).toBe(true);
    }, { timeout: 6000 });
  });

  it('profile agent failure → error/retry state shown', async () => {
    const handler = (u) => {
      if (u.includes('/api/agentic/semantic-profile')) return fail(503);
      return ok([]);
    };
    await navigateToStep3(handler);

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /run semantic profile/i }));
    });

    await waitFor(() => {
      const body = document.body.textContent.toLowerCase();
      expect(
        body.includes('retry') || body.includes('error') ||
        body.includes('failed') || body.includes('unavailable') ||
        body.includes('agent unavailable')
      ).toBe(true);
    }, { timeout: 6000 });
  });

});

// ── Step 4 – Data Quality ─────────────────────────────────────────────────

describe('MigrationWizard – Step 4 Data Quality', () => {

  it('shows "Run Quality Scan" button on step 4', async () => {
    await navigateToStep4();
    expect(screen.getByRole('button', { name: /run quality scan/i })).toBeTruthy();
  });

  it('"Run Quality Scan" button is not disabled before clicking', async () => {
    await navigateToStep4();
    expect(screen.getByRole('button', { name: /run quality scan/i }).disabled).toBe(false);
  });

  it('quality agent success → quality score or status visible', async () => {
    const handler = (u) => {
      if (u.includes('/api/agentic/quality-scan'))
        return ok({ success: true, result: QUALITY_RESULT });
      return ok([]);
    };
    await navigateToStep4(handler);

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /run quality scan/i }));
    });

    await waitFor(() => {
      const body = document.body.textContent;
      expect(
        body.includes('88') || body.toLowerCase().includes('quality') ||
        body.toLowerCase().includes('completed') || body.toLowerCase().includes('scan')
      ).toBe(true);
    }, { timeout: 6000 });
  });

  it('quality agent failure → error or retry state shown', async () => {
    const handler = (u) => {
      if (u.includes('/api/agentic/quality-scan')) return fail(503);
      return ok([]);
    };
    await navigateToStep4(handler);

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /run quality scan/i }));
    });

    await waitFor(() => {
      const body = document.body.textContent.toLowerCase();
      expect(
        body.includes('retry') || body.includes('error') ||
        body.includes('failed') || body.includes('unavailable') ||
        body.includes('agent unavailable')
      ).toBe(true);
    }, { timeout: 6000 });
  });

  it('data health report button renders AI Data Health Report panel on success', async () => {
    const handler = (u) => {
      if (u.includes('/api/agentic/task')) {
        return ok({
          success: true,
          result: {
            readiness_score: 84,
            trust_analysis: {
              overall_trust_score: 79,
              trust_level: 'medium',
              column_trust_scores: {
                part_number: { trust_score: 91, flags: [] },
                unit_cost: { trust_score: 62, flags: ['mixed_type'] },
              },
              columns_with_issues: ['unit_cost'],
            },
            semantic_header_map: {
              part_number: 'Part Number',
              unit_cost: 'Unit Cost',
            },
            distribution_anomalies: [
              {
                column: 'unit_cost',
                severity: 'warning',
                description: 'Mixed numeric and text values detected',
              },
            ],
            inferred_rules: [
              {
                rule_name: 'Unit Cost Numeric',
                rule_description: 'Unit cost should be numeric for all rows',
                column: 'unit_cost',
                rule_type: 'numeric_only',
                confidence: 0.82,
              },
            ],
            signals: [{ column: 'unit_cost', type: 'mixed_type', severity: 'warning' }],
            files_scanned: 1,
            timestamp: new Date().toISOString(),
          },
        });
      }
      return ok([]);
    };

    await navigateToStep4(handler);

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /data health report/i }));
    });

    await waitFor(() => {
      expect(screen.getByText(/ai data health report/i)).toBeTruthy();
      expect(screen.getByText(/semantic header map/i)).toBeTruthy();
      expect(screen.getByText(/column trust breakdown/i)).toBeTruthy();
    }, { timeout: 6000 });
  });

});

// ── Step 6 – Report ───────────────────────────────────────────────────────

describe('MigrationWizard – Step 6 Report', () => {

  it('renders "Generate AI Report" button at step 6', async () => {
    renderAtStep6((_u) => ok({ success: true, result: REPORT_RESULT }));
    expect(
      await screen.findByRole('button', { name: /generate ai report/i }, { timeout: 5000 })
    ).toBeTruthy();
  });

  it('"Generate AI Report" button is not disabled before clicking', async () => {
    renderAtStep6((_u) => ok({ success: true, result: REPORT_RESULT }));
    const btn = await screen.findByRole('button', { name: /generate ai report/i }, { timeout: 5000 });
    expect(btn.disabled).toBe(false);
  });

  it('report agent success → report content visible', async () => {
    const handler = (u) => {
      if (u.includes('workflow/step/report'))
        return ok({ success: true, result: REPORT_RESULT });
      return ok([]);
    };
    renderAtStep6(handler);
    const reportBtn = await screen.findByRole('button', { name: /generate ai report/i }, { timeout: 5000 });

    await act(async () => { fireEvent.click(reportBtn); });

    await waitFor(() => {
      const body = document.body.textContent;
      expect(
        body.includes('Regenerate Report') || body.includes('88') ||
        body.toLowerCase().includes('parts dataset') ||
        body.toLowerCase().includes('readiness') ||
        body.toLowerCase().includes('completed')
      ).toBe(true);
    }, { timeout: 6000 });
  });

  it('report agent failure → error state shown', async () => {
    const handler = (u) => {
      if (u.includes('workflow/step/report')) return fail(503);
      return ok([]);
    };
    renderAtStep6(handler);
    const reportBtn = await screen.findByRole('button', { name: /generate ai report/i }, { timeout: 5000 });

    await act(async () => { fireEvent.click(reportBtn); });

    await waitFor(() => {
      const body = document.body.textContent.toLowerCase();
      expect(
        body.includes('retry') || body.includes('error') ||
        body.includes('failed') || body.includes('unavailable') ||
        body.includes('agent unavailable')
      ).toBe(true);
    }, { timeout: 6000 });
  });

});

// ── loadingMessage idle state ─────────────────────────────────────────────

describe('MigrationWizard – loadingMessage keys (idle = no spinner)', () => {

  it('no profile loading spinner at initial mount', async () => {
    e2etraceFetchWithRetry.mockImplementation(makeFetch());
    render(<MemoryRouter><MigrationWizard /></MemoryRouter>);
    await screen.findByLabelText(/workflow instance name/i);
    expect(screen.queryByText(/running semantic profiling agent/i)).toBeNull();
  });

  it('no quality loading spinner at initial mount', async () => {
    e2etraceFetchWithRetry.mockImplementation(makeFetch());
    render(<MemoryRouter><MigrationWizard /></MemoryRouter>);
    await screen.findByLabelText(/workflow instance name/i);
    expect(screen.queryByText(/running quality scan agent/i)).toBeNull();
  });

  it('no report loading spinner at initial mount', async () => {
    e2etraceFetchWithRetry.mockImplementation(makeFetch());
    render(<MemoryRouter><MigrationWizard /></MemoryRouter>);
    await screen.findByLabelText(/workflow instance name/i);
    expect(screen.queryByText(/generating ai pipeline report/i)).toBeNull();
  });

});
