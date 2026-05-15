/**
 * Shared Test Fixtures
 * ====================
 *
 * Centralized test data and fixtures for all frontend tests.
 * Eliminates duplication across DataDiscoveryPage.jsx, ReportingHubPage.jsx,
 * and test files. Use these fixtures in any test or demo scenario.
 */

// ============================================================
// DEMO DATA FOR DISCOVERY
// ============================================================

export const DEMO_FILES = [
  {
    name: 'parts_master.csv',
    path: '/data/plm/parts_master.csv',
    file_type: 'csv',
    size_bytes: 245760,
    row_count: 3412,
    column_count: 8,
    null_rate: 2.1,
    profile: {
      part_number: { type: 'string', null_rate: 0, sample: ['PN-001', 'PN-002', 'PN-003'] },
      name: { type: 'string', null_rate: 1.2, sample: ['Bolt M8', 'Nut M8', 'Washer'] },
      category: { type: 'string', null_rate: 4.5, sample: ['Fastener', 'Fastener', 'Hardware'] },
      material: { type: 'string', null_rate: 8.0, sample: ['Steel', 'Steel', 'Aluminium'] },
      weight_kg: { type: 'float', null_rate: 2.1, sample: [0.012, 0.008, 0.003] },
      unit_cost: { type: 'float', null_rate: 0, sample: [0.45, 0.30, 0.12] },
      supplier_id: { type: 'string', null_rate: 3.4, sample: ['SUP-001', 'SUP-001', 'SUP-003'] },
      status: { type: 'string', null_rate: 0, sample: ['active', 'active', 'obsolete'] },
    },
  },
  {
    name: 'bom_structure.json',
    path: '/data/plm/bom_structure.json',
    file_type: 'json',
    size_bytes: 89344,
    row_count: 1205,
    column_count: 6,
    null_rate: 0.8,
    profile: {},
  },
  {
    name: 'supplier_data.xlsx',
    path: '/data/suppliers/supplier_data.xlsx',
    file_type: 'xlsx',
    size_bytes: 512000,
    row_count: 876,
    column_count: 12,
    null_rate: 8.3,
    profile: {},
  },
  {
    name: 'transactions.parquet',
    path: '/data/warehouse/transactions.parquet',
    file_type: 'parquet',
    size_bytes: 1048576,
    row_count: 45231,
    column_count: 15,
    null_rate: 0.2,
    profile: {},
  },
  {
    name: 'revisions.csv',
    path: '/data/plm/revisions.csv',
    file_type: 'csv',
    size_bytes: 32768,
    row_count: 412,
    column_count: 5,
    null_rate: 12.4,
    profile: {},
  },
  {
    name: 'product_config.json',
    path: '/data/plm/product_config.json',
    file_type: 'json',
    size_bytes: 4096,
    row_count: null,
    column_count: null,
    null_rate: null,
    profile: {},
  },
];

export const DEMO_DISCOVERY_RESULT = {
  report_id: 'demo-001',
  result: {
    files: DEMO_FILES,
    by_type: { csv: 2, json: 2, xlsx: 1, parquet: 1 },
    catalog: { avg_row_count: 8427 },
    summary: { total_files: 6, total_size_bytes: 1932544 },
  },
};

// ============================================================
// DEMO DATA FOR DISCOVERY PAST RUNS
// ============================================================

const _ago = (hours) => new Date(Date.now() - hours * 3600 * 1000).toISOString();

export const DEMO_PAST_RUNS = [
  {
    report_id: 'demo-pr-001',
    label: 'PLM data folder — demo',
    source_id: null,
    folder_path: '/data/plm',
    total_files: 6,
    total_size_bytes: 1932544,
    created_at: _ago(2),
    result: DEMO_DISCOVERY_RESULT,
  },
  {
    report_id: 'demo-pr-002',
    label: 'Supplier exports — demo',
    source_id: null,
    folder_path: '/data/suppliers',
    total_files: 3,
    total_size_bytes: 620544,
    created_at: _ago(26),
    result: {
      report_id: 'demo-pr-002',
      result: {
        files: [
          {
            name: 'supplier_data.xlsx',
            path: '/data/suppliers/supplier_data.xlsx',
            file_type: 'xlsx',
            size_bytes: 512000,
            row_count: 876,
            column_count: 12,
            null_rate: 8.3,
            profile: {
              supplier_id: { type: 'string', null_rate: 0, sample: ['SUP-001', 'SUP-002', 'SUP-003'] },
              supplier_name: { type: 'string', null_rate: 1.2, sample: ['Acme Corp', 'Globex Ltd', 'Initech'] },
              country: { type: 'string', null_rate: 3.4, sample: ['USA', 'Germany', 'India'] },
              category: { type: 'string', null_rate: 5.7, sample: ['Electronics', 'Fasteners', 'Plastics'] },
              rating: { type: 'float', null_rate: 12.1, sample: [4.2, 3.8, 4.7] },
            },
          },
          {
            name: 'supplier_contacts.csv',
            path: '/data/suppliers/supplier_contacts.csv',
            file_type: 'csv',
            size_bytes: 65536,
            row_count: 342,
            column_count: 6,
            null_rate: 4.2,
            profile: {},
          },
          {
            name: 'supplier_catalog.json',
            path: '/data/suppliers/supplier_catalog.json',
            file_type: 'json',
            size_bytes: 43008,
            row_count: null,
            column_count: null,
            null_rate: null,
            profile: {},
          },
        ],
        by_type: { xlsx: 1, csv: 1, json: 1 },
        catalog: { avg_row_count: 609 },
        summary: { total_files: 3, total_size_bytes: 620544 },
      },
    },
  },
];

// ============================================================
// DEMO DATA FOR REPORTS (ALL TYPES)
// ============================================================

export const DEMO_REPORTS = [
  {
    report_id: 'demo-mig-001',
    report_type: 'migration',
    title: 'PLM Parts Master → Target DB (Run #42)',
    source_page: 'migration',
    workflow_id: 'wf-plm-001',
    run_id: 'run-42',
    status: 'pass',
    summary: { records_processed: 3412, errors: 0, quality_score: 96.2, duration_s: 47 },
    tags: ['migration', 'plm', 'parts-master'],
    created_at: _ago(1.5),
  },
  {
    report_id: 'demo-disc-001',
    report_type: 'discovery',
    title: 'Discovery: /data/plm',
    source_page: 'data-discovery',
    workflow_id: null,
    run_id: null,
    status: 'info',
    summary: { total_files: 6, total_size_bytes: 1932544, file_types: ['csv', 'json', 'xlsx', 'parquet'] },
    tags: ['discovery', 'plm'],
    created_at: _ago(2),
  },
  {
    report_id: 'demo-dq-001',
    report_type: 'dq_scan',
    title: 'DQ Scan: workflow_instances',
    source_page: 'dq-dashboard',
    workflow_id: null,
    run_id: null,
    status: 'warning',
    summary: { overall_score: 78.4, issues_count: 12, rows_scanned: 3412, table: 'workflow_instances' },
    tags: ['dq', 'workflow_instances'],
    created_at: _ago(3),
  },
  {
    report_id: 'demo-lin-001',
    report_type: 'lineage',
    title: 'Lineage Snapshot: PLM Workflow wf-plm-001',
    source_page: 'lineage',
    workflow_id: 'wf-plm-001',
    run_id: null,
    status: 'info',
    summary: { nodes: 14, edges: 18, node_types: ['source_system', 'transformation', 'target_system'] },
    tags: ['lineage', 'plm'],
    created_at: _ago(4),
  },
  {
    report_id: 'demo-analytics-001',
    report_type: 'analytics',
    title: 'Analytics: Quality Reports Query (PostgreSQL)',
    source_page: 'analytics',
    workflow_id: null,
    run_id: null,
    status: 'info',
    summary: { rows_returned: 25, data_source: 'postgres', query_type: 'SQL' },
    tags: ['analytics', 'quality'],
    created_at: _ago(5),
  },
  {
    report_id: 'demo-obs-001',
    report_type: 'observability',
    title: 'Observability Snapshot — 07 Mar 2026 10:00',
    source_page: 'observability',
    workflow_id: null,
    run_id: null,
    status: 'pass',
    summary: { quality_score: 91.5, active_alerts: 1, agentic_agents_ready: 7 },
    tags: ['observability', 'health'],
    created_at: _ago(6),
  },
];

// ============================================================
// STATUS & TYPE METADATA (COLOR/ICON MAPPINGS)
// ============================================================

export const STATUS_META = {
  pass: { color: '#22c55e', icon: 'check-circle', label: 'Pass' },
  fail: { color: '#ef4444', icon: 'x-circle', label: 'Fail' },
  warning: { color: '#eab308', icon: 'alert-circle', label: 'Warning' },
  info: { color: '#0ea5e9', icon: 'info-circle', label: 'Info' },
  running: { color: '#f59e0b', icon: 'loader', label: 'Running' },
};

export const TYPE_META = {
  csv: { color: '#22c55e', icon: 'file-text', label: 'CSV' },
  json: { color: '#3b82f6', icon: 'braces', label: 'JSON' },
  xml: { color: '#f59e0b', icon: 'code', label: 'XML' },
  xlsx: { color: '#10b981', icon: 'table', label: 'Excel' },
  parquet: { color: '#8b5cf6', icon: 'database', label: 'Parquet' },
  pdf: { color: '#dc2626', icon: 'file-pdf', label: 'PDF' },
  image: { color: '#ec4899', icon: 'image', label: 'Image' },
  video: { color: '#6366f1', icon: 'film', label: 'Video' },
};

export const REPORT_TYPE_META = {
  migration: { color: '#3b82f6', icon: 'arrow-right', label: 'Migration' },
  discovery: { color: '#8b5cf6', icon: 'search', label: 'Discovery' },
  dq_scan: { color: '#f59e0b', icon: 'activity', label: 'Data Quality' },
  lineage: { color: '#10b981', icon: 'gitbranch', label: 'Lineage' },
  analytics: { color: '#ec4899', icon: 'bar-chart', label: 'Analytics' },
  observability: { color: '#06b6d4', icon: 'eye', label: 'Observability' },
  self_healing: { color: '#14b8a6', icon: 'tool', label: 'Self-Healing' },
};

// ============================================================
// MOCK API RESPONSES
// ============================================================

export const MOCK_WORKFLOWS = [
  {
    id: 'wf-plm-001',
    name: 'PLM Parts Migration',
    source: { name: 'SAP PLM', id: 'src-sap-001' },
    target: { name: 'Enterprise DW', id: 'tgt-dw-001' },
    status: 'configured',
    last_run: null,
    created_at: new Date(Date.now() - 7 * 24 * 3600 * 1000).toISOString(),
  },
  {
    id: 'wf-supplier-001',
    name: 'Supplier Data Pipeline',
    source: { name: 'Supplier Portal', id: 'src-portal-001' },
    target: { name: 'Master DB', id: 'tgt-db-001' },
    status: 'running',
    progress: 65,
    last_run: new Date(Date.now() - 1 * 3600 * 1000).toISOString(),
    created_at: new Date(Date.now() - 14 * 24 * 3600 * 1000).toISOString(),
  },
];

export const MOCK_DATA_SOURCES = [
  {
    id: 'src-sap-001',
    name: 'SAP PLM',
    type: 'sap',
    endpoint: 'https://sap-plm.company.com',
    status: 'connected',
  },
  {
    id: 'src-portal-001',
    name: 'Supplier Portal',
    type: 'rest_api',
    endpoint: 'https://suppliers.company.com/api',
    status: 'connected',
  },
];

// ============================================================
// HELPER FUNCTIONS FOR TESTS
// ============================================================

/**
 * Get a random report from the demo reports.
 */
export function getRandomDemoReport() {
  return DEMO_REPORTS[Math.floor(Math.random() * DEMO_REPORTS.length)];
}

/**
 * Get demo report by type.
 */
export function getDemoReportsByType(type) {
  return DEMO_REPORTS.filter((r) => r.report_type === type);
}

/**
 * Create a mock report with custom overrides.
 */
export function createMockReport(overrides = {}) {
  const base = getRandomDemoReport();
  return { ...base, ...overrides, report_id: `test-${Date.now()}` };
}

/**
 * Create a mock workflow with custom overrides.
 */
export function createMockWorkflow(overrides = {}) {
  const base = MOCK_WORKFLOWS[0];
  return { ...base, ...overrides, id: `test-wf-${Date.now()}` };
}
