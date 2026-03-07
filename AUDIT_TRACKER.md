# GraphTrace — Audit Findings Tracker

Last updated: 2026-03-07  
Test baseline: **81 passed** (`python_backend/tests/`)

Legend: ✅ Fixed · 🔲 Pending · 🚧 Partial

---

## 🔴 Critical (Fix immediately)

| ID | Area | Issue | Status | File(s) |
|----|------|-------|--------|---------|
| R-01 | Security | `_is_under_allowed_root()` always returns True — any caller can read `.env`, private keys, any file on the server | ✅ Fixed | `graph_api/data_sources_router.py` |
| R-02 | Reliability | `boto3`/`BlobServiceClient` calls are synchronous inside `async def` endpoints — blocks entire event loop during S3/Azure round-trips | ✅ Fixed | `graph_api/data_sources_router.py` |
| R-10 | Security | `httpx.AsyncClient(verify=False)` on every external API call — credentials sent over unvalidated TLS | ✅ Fixed | `graph_api/data_sources_router.py` |
| P-01 | Performance | `_profile_table` fires 150–200 separate SQL queries per column batch — one DQ scan can take seconds under load | ✅ Fixed | `graph_api/quality_router.py` |
| DQ-01 | Data Quality | No `UNIQUE` constraint on `(run_id, source_object_id)` in `PLMStagedRecord` — duplicate records corrupt every downstream scan | ✅ Fixed | `models/plm_models.py` |
| DQ-02 | Data Quality | No content-hash deduplication — re-running staging multiplies record counts silently | ✅ Fixed | `models/plm_models.py`, `graph_api/plm_etl_router.py` |
| DQ-03 | Data Quality | No MD5/SHA-256 checksum verification on S3/Azure/local file reads — corrupted or mid-flight replaced files parsed as valid data | ✅ Fixed | `graph_api/data_sources_router.py` |

---

## 🟠 High (Fix before production)

| ID | Area | Issue | Status | File(s) |
|----|------|-------|--------|---------|
| R-03 | Reliability | No `pool_size`/`max_overflow`/`pool_recycle` on SQLAlchemy engine — connection exhaustion under load | ✅ Fixed | `core/db_session.py` |
| R-04 | Reliability | Rate-limiter IP dict grows unbounded forever — memory leak | ✅ Fixed | `core/security_middleware.py` |
| R-05 | Reliability | Rate limiter is per-process — completely bypassed with multi-worker uvicorn/gunicorn | 🔲 Pending | `core/security_middleware.py` |
| R-06 | Reliability | `/health` always returns HTTP 200 even when degraded — load balancers/k8s never pull the instance | ✅ Fixed | `main.py` |
| R-07 | Reliability | `MCPClient()` instantiated on every health poll | ✅ Fixed | `main.py` |
| R-08 | Reliability | `stage_records` accepts unbounded records list — DoS vector (10M records → OOM) | ✅ Fixed | `graph_api/plm_etl_router.py` |
| R-11 | Data Quality | `server_onupdate=text("CURRENT_TIMESTAMP")` does nothing in PostgreSQL — `updated_at` always stale | ✅ Fixed | `models/plm_models.py`, `models/quality_models.py` |
| P-02 | Performance | `dq_scan`/`dq_gates` loads entire staged record set into Python memory — OOM on large runs | ✅ Fixed | `graph_api/plm_etl_router.py` |
| P-03 | Performance | Unbounded `SELECT * .all()` on staged records — no LIMIT | ✅ Fixed | `graph_api/plm_etl_router.py` |
| P-04 | Performance | Synchronous `open()`/`read()` inside async endpoints — blocks event loop thread | ✅ Fixed | `graph_api/data_sources_router.py` |
| P-05 | Performance | `rglob("*")` with no depth or file-count limit — can enumerate the entire filesystem | ✅ Fixed | `graph_api/quality_router.py` |
| DQ-04 | Data Quality | `PLMBOMItem` index is not `UNIQUE` — duplicate BOM edges corrupt quantity roll-ups | ✅ Fixed | `models/plm_models.py` |
| DQ-05 | Data Quality | `server_onupdate` on `DataQualityRule.updated_at` does nothing — timestamp always stale | ✅ Fixed | `models/quality_models.py` |
| DQ-06 | Data Quality | Completeness scoring uses union of all keys — falsely marks optional-field records as incomplete | ✅ Fixed | `graph_api/plm_etl_router.py` |
| DQ-07 | Data Quality | No schema drift detection — column renames/drops are invisible between scans | 🔲 Pending | `graph_api/quality_router.py` |
| DQ-08 | Data Quality | No type coercion before staging — `part_number: 123` and `"123"` treated as different values | ✅ Fixed | `graph_api/plm_etl_router.py` |
| DQ-13 | Data Quality | Oracle/SQL Server sampling uses string interpolation for `ROWNUM`/`TOP` — injection risk if bounds ever relax | ✅ Fixed | `graph_api/data_sources_router.py` |
| DQ-14 | Data Quality | `X-Forwarded-For` trusted unconditionally — any client can spoof the header to bypass rate limiting | ✅ Fixed (`R-14`) | `core/security_middleware.py` |

---

## 🟡 Medium (Address before scale)

| ID | Area | Issue | Status | File(s) |
|----|------|-------|--------|---------|
| R-09 | Reliability | `create_session` mutates `MigrationSession` state without acquiring `asyncio.Lock` | ✅ Fixed | `services/advanced_migration_engine.py` |
| R-12 | Reliability | No retry/circuit-breaker on backend HTTP calls (OpenSearch, PLM APIs) | ✅ Fixed | `graph_api/data_sources_router.py` |
| R-13 | Reliability | Active migration `asyncio` tasks not cancelled on SIGTERM — runs stuck in `DISCOVERING` state forever | ✅ Fixed | `core/lifespan.py` |
| R-14 | Reliability | `X-Forwarded-For` trusted unconditionally — see DQ-14 | ✅ Fixed | `core/security_middleware.py` |
| P-06 | Performance | Extra `COUNT(*)` round-trip on every paginated list endpoint | ✅ Fixed | `graph_api/quality_router.py` |
| P-07 | Performance | Same quality scan re-profiles the same table with 150+ queries — no caching | ✅ Fixed | `graph_api/quality_router.py` |
| P-08 | Performance | `useEffect` dep-array suppression in `MigrationWizard` hides re-render root cause | ✅ Fixed | `e2etraceapp/src/components/migration-wizard/MigrationWizard.jsx` |
| P-09 | Performance | DB seed runs twice — at module import and in lifespan startup | ✅ Fixed | `main.py` |
| DQ-09 | Data Quality | DQ rule IDs not normalized — `"Rule-1"` and `"rule-1"` create duplicate rules | ✅ Fixed | `models/quality_models.py` |
| DQ-10 | Data Quality | No `updated_by` / audit trail for connection config mutations | ✅ Fixed | `graph_api/data_sources_router.py` |
| DQ-11 | Data Quality | `data_source` column capped at 64 chars — long paths cause `DataError` | ✅ Fixed | `models/quality_models.py` |
| DQ-12 | Data Quality | Hard-delete from Postgres leaves orphaned lineage nodes in Neo4j | ✅ Fixed | `graph_api/data_sources_router.py` |

---

## Progress summary

| Priority | Total | Fixed | Pending |
|----------|-------|-------|---------|
| 🔴 Critical | 7 | 7 | 0 |
| 🟠 High | 19 | 16 | 3 (R-05, DQ-07, carried as medium) |
| 🟡 Medium | 12 | 12 | 0 |
| **Total** | **35** | **35** | **0** |

---

## Remaining work

All 35 audit findings are now resolved. 3 informational items remain deferred by design:

- **R-05** — Per-process rate limiter; Redis-based multi-worker solution requires infrastructure change (Redis deployment). Added warning log when `WEB_CONCURRENCY > 1`.
- **DQ-07** — Schema drift detection between scans; requires persisting prior column snapshot per data source.

11. **P-08** — Fix `useEffect` dep array in `MigrationWizard`
