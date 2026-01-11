/* eslint-env node */

import process from 'node:process';
import { describe, expect, test } from 'vitest';

const API_BASE = (process.env.E2E_API_BASE_URL || 'http://127.0.0.1:8011').replace(/\/$/, '');

async function fetchJson(path, { method = 'GET', body, timeoutMs = 15000 } = {}) {
  const url = `${API_BASE}${path}`;
  const controller = new AbortController();
  const t = setTimeout(() => controller.abort(), timeoutMs);

  const res = await fetch(url, {
    method,
    headers: body ? { 'Content-Type': 'application/json' } : undefined,
    body: body ? JSON.stringify(body) : undefined,
    signal: controller.signal,
  }).finally(() => clearTimeout(t));

  const text = await res.text();
  let json;
  try {
    json = text ? JSON.parse(text) : null;
  } catch {
    json = null;
  }

  return { res, text, json, url };
}

describe('Analytics Hub smoke: PG / N4J / OS / GQL', () => {
  test('backend /health responds 200', async () => {
    const { res, text, url } = await fetchJson('/health');
    expect(res.status, `GET ${url} -> ${res.status}\n${text}`).toBe(200);
  });

  describe('Query Builder endpoints', () => {
    test('PG: /api/analytics/sql', async () => {
      const { res, text, url, json } = await fetchJson('/api/analytics/sql', {
        method: 'POST',
        body: { sql: 'SELECT 1 AS ok' },
      });
      expect(res.status, `POST ${url} -> ${res.status}\n${text}`).toBe(200);
      expect(json && typeof json === 'object').toBe(true);
    });

    test('N4J: /api/lineage/cypher', async () => {
      const { res, text, url, json } = await fetchJson('/api/lineage/cypher', {
        method: 'POST',
        body: { cypher: 'MATCH (n) RETURN n LIMIT 1' },
      });
      expect(res.status, `POST ${url} -> ${res.status}\n${text}`).toBe(200);
      expect(json && typeof json === 'object').toBe(true);
      expect(typeof json.success).toBe('boolean');
      expect(Array.isArray(json.results)).toBe(true);
    }, 20000);

    test('OS: /api/opensearch/search/workflows', async () => {
      const { res, text, url, json } = await fetchJson('/api/opensearch/search/workflows', {
        method: 'POST',
        body: { query: { match_all: {} } },
      });
      expect(res.status, `POST ${url} -> ${res.status}\n${text}`).toBe(200);
      expect(json && typeof json === 'object').toBe(true);
      expect(json.hits && typeof json.hits === 'object').toBe(true);
    }, 20000);

    test('GQL: /api/graphql/db-query', async () => {
      const { res, text, url, json } = await fetchJson('/api/graphql/db-query', {
        method: 'POST',
        body: { query: '{ workflows { id } }', limit: 1 },
      });
      expect(res.status, `POST ${url} -> ${res.status}\n${text}`).toBe(200);
      expect(json && typeof json === 'object').toBe(true);
      expect('data' in json).toBe(true);
    });
  });

  describe('Natural Language (NLQ)', () => {
    test.each(['postgres', 'neo4j', 'opensearch', 'graphql'])(
      'NLQ responds for %s',
      async (datasource) => {
        const { res, text, url, json } = await fetchJson('/api/analytics/nlq', {
          method: 'POST',
          body: {
            query: 'Show recent workflows',
            datasource,
            context: { available_tables: [] },
          },
        });
        expect(res.status, `POST ${url} -> ${res.status}\n${text}`).toBe(200);
        expect(json && typeof json === 'object').toBe(true);
        expect(typeof json.success).toBe('boolean');
      },
      20000
    );
  });

  describe('Quality Reports', () => {
    test('GET /api/analytics/quality/reports', async () => {
      const { res, text, url, json } = await fetchJson('/api/analytics/quality/reports');
      expect(res.status, `GET ${url} -> ${res.status}\n${text}`).toBe(200);
      expect(Array.isArray(json)).toBe(true);
    });
  });

  describe('Saved Queries (GraphQL Catalogue)', () => {
    test('GET /api/graphql/catalogue/queries', async () => {
      const { res, text, url, json } = await fetchJson('/api/graphql/catalogue/queries?limit=1&offset=0');
      expect(res.status, `GET ${url} -> ${res.status}\n${text}`).toBe(200);
      expect(json && typeof json === 'object').toBe(true);
    });
  });
});
