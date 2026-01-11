const API_BASE = process.env.SMOKE_API_BASE || 'http://127.0.0.1:8011';
const TIMEOUT_MS = Number(process.env.SMOKE_TIMEOUT_MS || '15000');
const ALLOW_MOCK_OPENSEARCH = (process.env.SMOKE_ALLOW_MOCK_OPENSEARCH || '').toLowerCase() === '1' || (process.env.SMOKE_ALLOW_MOCK_OPENSEARCH || '').toLowerCase() === 'true';
const REQUIRE_NEO4J = (process.env.SMOKE_REQUIRE_NEO4J || '').toLowerCase() === '1' || (process.env.SMOKE_REQUIRE_NEO4J || '').toLowerCase() === 'true';
const REQUIRE_OPENSEARCH = (process.env.SMOKE_REQUIRE_OPENSEARCH || '').toLowerCase() === '1' || (process.env.SMOKE_REQUIRE_OPENSEARCH || '').toLowerCase() === 'true';

function withTimeout(promise, timeoutMs, label) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);

  const wrapped = (async () => {
    try {
      return await promise(controller.signal);
    } finally {
      clearTimeout(timeout);
    }
  })();

  wrapped.controller = controller;
  wrapped.label = label;
  return wrapped;
}

async function requestJson(method, path, body, timeoutMs = TIMEOUT_MS) {
  return await withTimeout(async (signal) => {
    const res = await fetch(`${API_BASE}${path}`, {
      method,
      headers: {
        'content-type': 'application/json',
      },
      body: body ? JSON.stringify(body) : undefined,
      signal,
    });

    const text = await res.text();
    let json;
    try {
      json = text ? JSON.parse(text) : null;
    } catch {
      json = { _raw: text };
    }

    return { ok: res.ok, status: res.status, json };
  }, timeoutMs, `${method} ${path}`);
}

let cachedHealth = null;
async function getApiHealth() {
  if (cachedHealth) return cachedHealth;
  const res = await requestJson('GET', '/health');
  cachedHealth = res;
  return res;
}

function pad(str, len) {
  const s = String(str);
  return s.length >= len ? s : s + ' '.repeat(len - s.length);
}

function normalizeError(err) {
  if (!err) return 'Unknown error';
  if (err.name === 'AbortError') return `Timed out after ${TIMEOUT_MS}ms`;
  return err?.message || String(err);
}

async function runCheck(name, fn) {
  const startedAt = Date.now();
  try {
    const result = await fn();
    const ms = Date.now() - startedAt;
    return { name, ...result, ms };
  } catch (err) {
    const ms = Date.now() - startedAt;
    return { name, status: 'FAIL', details: normalizeError(err), ms };
  }
}

function statusRank(status) {
  switch (status) {
    case 'PASS':
      return 0;
    case 'WARN':
      return 1;
    case 'FAIL':
      return 2;
    default:
      return 3;
  }
}

const checks = [
  {
    name: 'Health',
    fn: async () => {
      const res = await getApiHealth();
      if (!res.ok) return { status: 'FAIL', details: `HTTP ${res.status}` };
      const deps = res.json?.dependencies;
      const dbOk = deps?.postgres?.ok;
      const neo4jOk = deps?.neo4j?.ok;
      const overall = res.json?.status || 'unknown';
      return { status: 'PASS', details: `status=${overall} postgres=${Boolean(dbOk)} neo4j=${Boolean(neo4jOk)}` };
    },
  },
  {
    name: 'OpenSearch: Health',
    fn: async () => {
      const res = await requestJson('GET', '/api/opensearch/health');
      if (!res.ok) return { status: REQUIRE_OPENSEARCH ? 'FAIL' : 'WARN', details: `HTTP ${res.status}` };
      const connected = Boolean(res.json?.connected);
      if (!connected) {
        return {
          status: REQUIRE_OPENSEARCH ? 'FAIL' : 'WARN',
          details: res.json?.error ? `Not connected (${res.json.error})` : 'Not connected',
        };
      }
      return { status: 'PASS', details: `Connected (${res.json?.version || 'unknown'})` };
    },
  },
  {
    name: 'Query Builder: Postgres SQL',
    fn: async () => {
      const res = await requestJson('POST', '/api/analytics/sql', {
        sql: 'SELECT id, name, status, created_at FROM workflows ORDER BY created_at DESC LIMIT 5',
        limit: 5,
        offset: 0,
      });
      if (!res.ok) return { status: 'FAIL', details: `HTTP ${res.status}` };
      const count = res.json?.count;
      return { status: 'PASS', details: `Returned ${typeof count === 'number' ? count : 'n/a'} rows` };
    },
  },
  {
    name: 'Query Builder: Neo4j Cypher',
    fn: async () => {
      const health = await getApiHealth();
      const neo4jOk = Boolean(health.json?.dependencies?.neo4j?.ok);
      if (!neo4jOk) {
        return { status: REQUIRE_NEO4J ? 'FAIL' : 'WARN', details: 'Neo4j marked unhealthy; skipped' };
      }
      const res = await requestJson('POST', '/api/lineage/cypher', {
        cypher: 'MATCH (n) RETURN labels(n)[0] AS label, count(*) AS count ORDER BY count DESC LIMIT 5',
      });
      if (!res.ok) return { status: 'FAIL', details: `HTTP ${res.status}` };
      if (res.json?.success !== true) {
        return { status: REQUIRE_NEO4J ? 'FAIL' : 'WARN', details: res.json?.error || 'Neo4j query failed' };
      }
      return { status: 'PASS', details: `Returned ${res.json?.count ?? 'n/a'} rows` };
    },
  },
  {
    name: 'Query Builder: OpenSearch',
    fn: async () => {
      const health = await requestJson('GET', '/api/opensearch/health');
      const connected = Boolean(health.ok && health.json?.connected);
      if (!connected && !REQUIRE_OPENSEARCH) {
        return { status: 'WARN', details: 'OpenSearch not connected; skipped' };
      }

      const res = await requestJson('POST', '/api/opensearch/search/workflows', {
        query: { match_all: {} },
      });
      if (!res.ok) return { status: REQUIRE_OPENSEARCH ? 'FAIL' : 'WARN', details: `HTTP ${res.status}` };

      const isMock = Boolean(res.json?._mock);
      if (isMock && !ALLOW_MOCK_OPENSEARCH) {
        return {
          status: REQUIRE_OPENSEARCH ? 'FAIL' : 'WARN',
          details: 'OpenSearch not configured (mock response). Set SMOKE_ALLOW_MOCK_OPENSEARCH=1 to treat as WARN.',
        };
      }

      if (isMock) {
        return { status: 'WARN', details: 'Mock response (OpenSearch not configured)' };
      }

      const total = res.json?.hits?.total?.value;
      return { status: 'PASS', details: `hits.total=${typeof total === 'number' ? total : 'n/a'}` };
    },
  },
  {
    name: 'Query Builder: GraphQL DB Query',
    fn: async () => {
      const res = await requestJson('POST', '/api/graphql/db-query', {
        query: '{ workflows { id name status created_at } }',
        limit: 5,
        offset: 0,
      });
      if (!res.ok) return { status: 'FAIL', details: `HTTP ${res.status}` };
      if (Array.isArray(res.json?.errors) && res.json.errors.length) {
        return { status: 'FAIL', details: res.json.errors[0]?.message || 'GraphQL errors present' };
      }
      const rows = res.json?.data?.workflows;
      return { status: 'PASS', details: `Returned ${Array.isArray(rows) ? rows.length : 'n/a'} rows` };
    },
  },
  {
    name: 'NLQ: Postgres',
    fn: async () => {
      const res = await requestJson('POST', '/api/analytics/nlq', {
        query: 'How many workflows are there?',
        datasource: 'postgres',
      });
      if (!res.ok) return { status: 'FAIL', details: `HTTP ${res.status}` };
      return { status: res.json?.success ? 'PASS' : 'FAIL', details: res.json?.success ? 'OK' : (res.json?.error || 'NLQ failed') };
    },
  },
  {
    name: 'NLQ: Neo4j',
    fn: async () => {
      const res = await requestJson('POST', '/api/analytics/nlq', {
        query: 'Show relationship counts',
        datasource: 'neo4j',
      });
      if (!res.ok) return { status: 'FAIL', details: `HTTP ${res.status}` };
      return { status: res.json?.success ? 'PASS' : 'FAIL', details: res.json?.success ? 'OK' : (res.json?.error || 'NLQ failed') };
    },
  },
  {
    name: 'NLQ: OpenSearch',
    fn: async () => {
      const res = await requestJson('POST', '/api/analytics/nlq', {
        query: 'Find parts',
        datasource: 'opensearch',
      });
      if (!res.ok) return { status: 'FAIL', details: `HTTP ${res.status}` };
      return { status: res.json?.success ? 'PASS' : 'FAIL', details: res.json?.success ? 'OK' : (res.json?.error || 'NLQ failed') };
    },
  },
  {
    name: 'NLQ: GraphQL',
    fn: async () => {
      const res = await requestJson('POST', '/api/analytics/nlq', {
        query: 'List workflows',
        datasource: 'graphql',
      });
      if (!res.ok) return { status: 'FAIL', details: `HTTP ${res.status}` };
      return { status: res.json?.success ? 'PASS' : 'FAIL', details: res.json?.success ? 'OK' : (res.json?.error || 'NLQ failed') };
    },
  },
  {
    name: 'Quality Reports: List',
    fn: async () => {
      const res = await requestJson('GET', '/api/analytics/quality/reports');
      if (!res.ok) return { status: 'FAIL', details: `HTTP ${res.status}` };
      const reports = Array.isArray(res.json) ? res.json : res.json?.reports;
      const n = Array.isArray(reports) ? reports.length : 0;
      if (n === 0) return { status: 'WARN', details: 'No reports returned' };
      return { status: 'PASS', details: `Returned ${n} reports` };
    },
  },
  {
    name: 'Quality Reports: Detail (first scan_id)',
    fn: async () => {
      const list = await requestJson('GET', '/api/analytics/quality/reports');
      if (!list.ok) return { status: 'FAIL', details: `HTTP ${list.status}` };
      const reports = Array.isArray(list.json) ? list.json : list.json?.reports;
      const first = Array.isArray(reports) ? reports[0] : null;
      const scanId = first?.scan_id || first?.id;
      if (!scanId) return { status: 'WARN', details: 'No scan_id found to fetch detail' };

      const detail = await requestJson('GET', `/api/analytics/quality/reports/${encodeURIComponent(scanId)}`);
      if (!detail.ok) return { status: 'FAIL', details: `HTTP ${detail.status}` };
      const tableName = detail.json?.table_name || detail.json?.table || '(unknown)';
      return { status: 'PASS', details: `OK (${tableName})` };
    },
  },
  {
    name: 'Saved Queries: List',
    fn: async () => {
      const res = await requestJson('GET', '/api/graphql/catalogue/queries');
      if (!res.ok) return { status: 'FAIL', details: `HTTP ${res.status}` };
      const items = Array.isArray(res.json) ? res.json : res.json?.queries;
      const n = Array.isArray(items) ? items.length : 0;
      if (n === 0) return { status: 'WARN', details: 'No saved queries returned' };
      return { status: 'PASS', details: `Returned ${n} saved queries` };
    },
  },
];

const results = [];
for (const c of checks) {
  results.push(await runCheck(c.name, c.fn));
}

results.sort((a, b) => statusRank(a.status) - statusRank(b.status));

const nameWidth = Math.min(
  60,
  Math.max(...results.map((r) => r.name.length))
);

console.log(`\nSmoke analytics against ${API_BASE}`);
console.log('-'.repeat(Math.min(120, nameWidth + 50)));
for (const r of results) {
  console.log(`${pad(r.status, 5)}  ${pad(r.name, nameWidth)}  ${pad(`${r.ms}ms`, 8)}  ${r.details || ''}`);
}
console.log('-'.repeat(Math.min(120, nameWidth + 50)));

const failed = results.filter((r) => r.status === 'FAIL');
if (failed.length) {
  console.error(`\nFAILED (${failed.length}) check(s).`);
  process.exitCode = 1;
} else {
  console.log('\nAll required checks passed (WARNs may indicate missing data/config).');
}
