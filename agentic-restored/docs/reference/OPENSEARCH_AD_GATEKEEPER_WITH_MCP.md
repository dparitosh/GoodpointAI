# OpenSearch AD (RCF) + “DQ Gatekeeper” + MCP (No Soda Cloud)

This repo supports an agentic anomaly-response workflow where:

- **OpenSearch Anomaly Detection (RCF)** does the real-time ML detection.
- **Goodpoint backend** queries the detector’s *custom result index* and records a **Data Quality scan report** (pass/fail) that the UI and agents can consume.
- **MCP tools** let an AI agent (or automation) run the check and investigate anomalies.

> Why not query the OpenSearch AD result index directly from Soda?
>
> Soda’s open-source/Core model is SQL-centric and its documented connectors target SQL / Spark / Pandas-style sources. OpenSearch is a search engine with Query DSL, not a SQL warehouse. So in this repo, Soda remains useful for **database tables**, while OpenSearch-native detection is “gated” via a backend endpoint that produces the *same DQ report shape*.

---

## Phase 1 — Configure OpenSearch native anomaly detector

In OpenSearch Dashboards:

1. Go to **Anomaly Detection** → **Create detector**.
2. Select the **feature field** (e.g., `order_count`, `cpu_usage`) and aggregation (e.g., `sum`, `avg`).
3. **Enable custom result index** (critical):
   - Check **Enable custom result index**
   - Pick a name, e.g. `orders-anomalies`
   - OpenSearch will write results to a non-system index like:
     - `opensearch-ad-plugin-result-orders-anomalies`
4. Start the **real-time detector** job.

The custom result index is what external systems should query.

---

## Phase 2 — Gatekeeper check (backend)

The backend exposes an endpoint that:

- Queries the AD custom result index for the last *N minutes*
- Computes `max(anomaly_grade)`
- Fails if `max(anomaly_grade) >= threshold`
- Persists a standard `dq_scan_reports` record so:
  - The UI can show it
  - MCP tools can fetch/analyze it

Endpoint:

- `POST /api/analytics/quality/opensearch-ad/gate/{result_index}`

Request body:

- `threshold` (default `0.9`)
- `lookback_minutes` (default `10`)
- `grade_field` (default `anomaly_grade`)
- `time_field` (default `data_end_time`)
- `time_field_is_epoch_millis` (default `true`)

Notes:

- The report is stored with `data_source = "opensearch_ad"`.
- The report’s `table_name` is the OpenSearch index name.

---

## Phase 3 — Agentic action via MCP

### 1) Soda MCP server (this repo)

The MCP server in this repo now exposes:

- `run_soda_scan` (Postgres tables)
- `get_scan_results` (persisted DQ reports)
- `analyze_anomaly` (trend analysis over persisted DQ reports)
- `check_opensearch_ad_results` (OpenSearch AD gatekeeper)

`check_opensearch_ad_results` calls the backend endpoint above and returns the persisted report payload.

### 2) OpenSearch MCP server (official)

OpenSearch provides an official MCP server:

- https://github.com/opensearch-project/opensearch-mcp-server-py

It exposes tools like `SearchIndexTool` that accept OpenSearch Query DSL.

Typical agent flow:

1. **Trigger**: agent calls `check_opensearch_ad_results` and sees a failure.
2. **Investigate**: agent calls OpenSearch MCP `SearchIndexTool` on:
   - the AD results index to pull the top anomaly docs
   - the raw/source data index around the anomaly time window
3. **Correlate**: agent correlates with deployment logs or pipeline changes.
4. **Act**: agent can open an incident, recommend rollback, or execute a remediation playbook.

---

## Troubleshooting

- If the gate endpoint returns **503 OpenSearch not configured**:
  - Configure OpenSearch in the Admin Connection Settings (`connection_type: opensearch`) or set `OPENSEARCH_URL` (+ optional auth env vars).

- If the detector uses a date field (not epoch millis):
  - Call the gate endpoint with `time_field_is_epoch_millis=false`.
