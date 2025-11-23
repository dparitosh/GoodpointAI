# Graph Features Low-Level Requirements

_Last updated: 2025-11-23_

This document captures implementation-level requirements for the **GraphQL toolkit**, **Graph Explorer UI**, and **Neo4j GraphRAG services** that remain in scope per `PAGE_REQUIREMENTS_SPECIFICATIONS.md`. These components serve as the **centerpiece for ETL, XState Visualizer, and OpenSearch integration**, simplifying data mapping and ETL services across the platform.

---

## Executive Summary

The Graph Features suite provides the **foundational data integration layer** connecting:
- **ETL Pipelines**: GraphQL toolkit enables schema introspection and data transformation for ETL workflows
- **XState Migration Visualizer**: Neo4j stores migration state transitions and relationships for real-time visualization
- **OpenSearch Integration**: GraphRAG service bridges graph data with vector search for semantic queries
- **Data Mapping Services**: GraphQL transform engine simplifies complex data mappings across heterogeneous sources

This integration creates a unified data fabric where:
1. ETL processes leverage GraphQL for flexible schema management
2. Migration states are persisted in Neo4j and visualized via XState components
3. OpenSearch indexes are enriched with graph relationships via GraphRAG
4. Data mapping complexity is abstracted through GraphQL transforms

---

## 1. GraphQL Toolkit (Backend) - ETL Data Mapping Centerpiece

### 1.1 Scope & Components
- **Routers**: `python_backend/graph_api/graphql_router.py` (REST interface for schema introspection, query execution, and data transforms).
- **Services**: `python_backend/services/graphql_service.py` (parsing, schema generation, pseudo-GraphQL execution) and `python_backend/services/graphql_catalogue_service.py` (persisted query registry).
- **Persistence Models**: `python_backend/models/graphql_models.py` (SQLAlchemy models for persisted queries and schema cache) wired through `graphql_catalogue_router.py`.
- **Consumers**: 
  - `python_backend/services/report_indexing_service.py` leverages `PersistedGraphQLQueryModel` to rebuild report indexes from saved queries.
  - **ETL Services**: Data mapping and transformation pipelines use GraphQL introspection for dynamic schema discovery
  - **Migration Engine**: Advanced migration service (`python_backend/services/advanced_migration_engine.py`) uses GraphQL for source/target schema analysis

### 1.2 Integration with ETL & Migration
The GraphQL toolkit serves as the **primary data mapping layer** for:

1. **ETL Schema Discovery**
   - ETL pipelines call `/api/graphql/introspect` to discover source schemas dynamically
   - Supports both XML (PLM data) and JSON (REST APIs, NoSQL) formats
   - Schema cache in PostgreSQL reduces repeated introspection overhead

2. **Data Transformation Engine**
   - `/api/graphql/transform` endpoint powers complex field mappings with inline transformations
   - Used by migration engine for data_migration phase (see `MigrationState.DATA_MIGRATION`)
   - Supports nested object transformations for hierarchical PLM data structures

3. **Query Execution for Validation**
   - `/api/graphql/query` enables validation queries during ETL validation phase
   - Used by analytics service to query transformed data before indexing to OpenSearch

### 1.3 Functional Requirements
1. **Schema Introspection**
   - Endpoint `POST /api/graphql/introspect` accepts `{content, format, name}`.
   - `format` must be `xml` or `json`; `graphql_service.parse_xml_to_dict`/`parse_json_to_dict` raise HTTP 400 via the router when invalid.
   - Response structure mirrors `SchemaIntrospectionResponse` (fields/types map) and must be deterministic regardless of attribute ordering.
   - **ETL Integration**: Response cached in `migration_sessions` table for reuse across migration retries

2. **File Upload Introspection**
   - Endpoint `POST /api/graphql/upload-schema` streams uploaded `.xml`/`.json` file into memory; rejects other mime types with 400.
   - Maximum request size inherits FastAPI defaults; deployers should front gate with reverse proxy limits.
   - **PLM Integration**: Handles PLM XML schemas up to 150 MB (per `BN-01`)

3. **Query Execution**
   - Endpoint `POST /api/graphql/query` executes pseudo-GraphQL queries against JSON payloads using `graphql_service.execute_query`.
   - Service must capture any `ValueError` (invalid selectors) and return `{data: null, errors:[...]}` with HTTP 200; unexpected exceptions bubble as HTTP 500.
   - **Validation Integration**: Used by migration validation phase to verify data completeness

4. **Transform Engine** (Core ETL Feature)
   - Endpoint `POST /api/graphql/transform` iterates `mappings[]`, copying values from `source_data` to `target_data`, optionally applying inline transformations.
   - Errors encountered per mapping append to response `errors[]` but do not abort entire transform unless fatal.
   - **Migration Integration**: Powers `MigrationState.SCHEMA_MAPPING` → `MigrationState.DATA_MIGRATION` transition
   - **Analytics Integration**: Prepares data for OpenSearch indexing

5. **Catalogue Management**
   - `graphql_catalogue_router.py` exposes CRUD for persisted queries and schema cache: list, get, create/update, delete.
   - `GraphQLCatalogueService` enforces unique name constraint and uses `updated_at` ordering for listings.
   - **Reusability**: Stored queries enable repeatable ETL workflows and audit trails

### 1.4 API Contracts
| Endpoint | Method | Request Model | Response | ETL/Migration Use Case |
|----------|--------|---------------|----------|------------------------|
| `/api/graphql/introspect` | POST | `SchemaIntrospectionRequest` | `SchemaIntrospectionResponse` | Schema discovery in DISCOVERING phase |
| `/api/graphql/upload-schema` | POST (multipart) | file | `SchemaIntrospectionResponse` | PLM XML schema upload |
| `/api/graphql/query` | POST | `QueryRequest` | `QueryResponse` | Data validation in VALIDATION phase |
| `/api/graphql/transform` | POST | `TransformRequest` | `TransformResponse` | Data transformation in DATA_MIGRATION phase |
| `/api/graphql/catalogue/*` | CRUD | JSON | JSON | Query reuse across migrations |

### 1.5 Data & Configuration
- Uses primary PostgreSQL via SQLAlchemy session; models defined in `models/graphql_models.py`.
- Persisted queries stored in `persisted_graphql_queries` table with references in `migration_sessions.metadata` JSONB column
- Requires environment defaults already defined in `.env` for PostgreSQL connectivity.
- **Configuration Link**: Uses `config/system_configuration.json` service definitions

### 1.6 Validation & Monitoring
- Tests should cover happy path+error for introspection and query execution (see `python_backend/tests/test_runtime_config.py` for pattern).
- **New Tests Required**: Add to `test_advanced_migration_features.py` to validate GraphQL integration
- Logging: `graphql_router` logs errors via module logger; ensure `LOG_LEVEL` env is respected.
- Metrics: not instrumented yet—**add to observability backlog** if required (link to analytics_router)

---

## 2. Graph Explorer UI (Frontend) - Visualization & Navigation Hub

### 2.1 Scope & Components
- **Core component**: `e2etraceapp/src/components/GraphExplorer.jsx` orchestrates Neo4j connections, query execution, and graph rendering.
- **Legacy view**: `e2etraceapp/src/components/GraphExplorerMigrated.jsx` retains older UI intended for gradual migration.
- **Header**: `e2etraceapp/src/components/graph/GraphExplorerHeader.jsx` controls bread crumbs, connection state, and quick actions.
- **Services & state**:
  - `e2etraceapp/src/services/connectionService.js` manages active Neo4j session, listeners, and graph data fetches.
  - `e2etraceapp/src/services/GraphIntegrationService.js` coordinates backend API calls from settings panes.
  - `e2etraceapp/src/services/neo4j-data-service.js` - Neo4j data access layer (currently exists)
  - Recoil atoms in `src/state/atoms/graphAtoms.js` & `configurationAtoms.js` store graph data, filters, query panel state, and Neo4j config.
- **Settings support**: `Neo4jAuraSettings.jsx` surfaces "Use for Graph Explorer" toggles and default connection selection.

### 2.2 Integration with XState Visualizer & Migration
The Graph Explorer serves as the **unified visualization layer** for:

1. **Migration State Visualization**
   - Neo4j stores migration session relationships: `(Session)-[:TRANSITIONS_TO]->(State)`
   - Graph Explorer renders migration history as interactive state graph
   - **Link to XState Visualizer**: PLMMigrationStatechartVisualizer.jsx consumes Neo4j data via GraphExplorer APIs

2. **ETL Lineage Tracking**
   - Graph nodes represent data sources, transformations, and targets
   - Relationships show data flow: `(Source)-[:TRANSFORMS_TO]->(Target)`
   - **Integration Point**: GraphQL transform history stored as Neo4j relationships

3. **OpenSearch Result Navigation**
   - Graph Explorer can visualize relationships between search results
   - **GraphRAG Integration**: Vector search results enriched with graph context

### 2.3 Functional Requirements
1. **Connection Lifecycle**
   - `GraphExplorer.jsx` must listen to `connectionService` events (`connecting`, `connected`, `disconnected`, `connection-error`, `graph-data-loaded`).
   - Auto-connect when `connectionService.getConnectionInfo().config.auto_connect` is true; otherwise keep panel idle but not loading.
   - **Migration Integration**: Connection state synced with migration_router WebSocket for real-time updates

2. **Data Loading**
   - `loadGraphData` queries backend using filter state (`filters.limit`, `filters.entityTypes`, `filters.relationshipTypes`).
   - After successful fetch, graph data state must include `lastUpdated` timestamp for monitoring.
   - **ETL Integration**: Entity types include `DataSource`, `Transform`, `MigrationSession`, `AnalyticsMetric`

3. **Query Panel Execution**
   - When user submits Cypher, component creates/uses `sessionRef` and posts to backend via `connectionService.executeQuery` with results stored in `graphQueryPanelAtom`.
   - Error handling surfaces notifications via `useNotifications`. Buttons disabled while `executing=true`.
   - **Power User Feature**: Direct Cypher access for debugging ETL issues

4. **Graph Explorer Header**
   - `GraphExplorerHeader.jsx` exposes props for breadcrumb text, connection CTA, filter toggles; must remain keyboard accessible.
   - **Accessibility**: Matches ARIA standards from PLMMigrationVisualizerPage.jsx

5. **Fallback/Mock Mode**
   - `ServiceDependencyChecker.checkGraphExplorerMode` decides whether to show mock data banner when backend services unavailable.
   - **Development Support**: Mock mode for frontend-only development

6. **Routing Fix Required**
   - The `GraphExplorerContent` import still targets `../pages/graph/components/...`, but `e2etraceapp/src/pages/graph` was removed during pruning.
   - **ACTION REQUIRED**: To restore functionality, either:
     - Re-introduce the deleted page tree with lightweight wrapper, or
     - Move `GraphExplorerContent` into `src/components` (preferred) and update import paths and router definitions.
   - **Requirement**: Before next release, ensure Graph Explorer builds by resolving the dangling import and re-adding a `/graph` or `/graph-explorer` route.
   - **Alignment**: Should appear in navigation alongside `/processing` and `/plm-migration-visualizer`

### 2.4 Dependencies & Configuration
- Requires Neo4j credentials: `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD` (see `.env` and `config/environments.json`).
- Uses Fluent UI tokens via shared component library; theming must align with `PAGE_REQUIREMENTS_SPECIFICATIONS.md` guardrails.
- **Configuration Link**: Leverage `config/system_configuration.json` for Neo4j service definitions

### 2.5 Validation
- Manual QA: connect to Neo4j Aura/Local, run sample queries, verify graph renders and filters respond.
- Automated: add smoke test to Playwright suite once route restored; cover connection error handling via mocked responses.
- **Integration Tests**: Add tests showing migration state transitions visualized in Graph Explorer

### 2.6 Open Questions / Follow-ups
- **Navigation Placement**: Where should Graph Explorer surface in navigation post-prune? 
  - **Recommendation**: Add as third main route: `/`, `/processing`, `/plm-migration-visualizer`, `/graph-explorer`
- **Component Consolidation**: Decide whether to keep both `GraphExplorer` and `GraphExplorerMigrated` or fully consolidate.
  - **Recommendation**: Deprecate `GraphExplorerMigrated`, migrate features to main `GraphExplorer`

---

## 3. Neo4j GraphRAG Service - Semantic Search Bridge to OpenSearch

### 3.1 Scope & Components
- **Router**: `python_backend/graph_api/neo4j_graphrag_router.py`, mounted at `/api/neo4j-graphrag` per `python_backend/main.py`.
- **Service**: `python_backend/services/neo4j_graphrag_service.py` orchestrates Neo4j vector search, document retrieval, and tool metadata.
- **Dependencies**: Neo4j connection config from environment; optional embedding model configuration via `GRAPH_RAG_EMBED_DIMENSION` (default in service constructor).

### 3.2 Integration with OpenSearch & Analytics
The Neo4j GraphRAG service provides the **semantic search bridge** between graph data and vector search:

1. **Hybrid Search Strategy**
   - Combines Neo4j vector indexes with OpenSearch k-NN for comprehensive results
   - Neo4j: relationship-aware context (e.g., "parts from same product")
   - OpenSearch: full-text and vector similarity (e.g., "semantically similar descriptions")
   - **Result Fusion**: GraphRAG merges both sources, ranking by relevance + graph distance

2. **Analytics Enrichment**
   - Analytics metrics (from analytics_router) indexed in both Neo4j and OpenSearch
   - GraphRAG queries enable: "Show me quality issues related to migration X"
   - **Link to T-05**: Migration quality metrics stored as graph nodes with relationships

3. **ETL Semantic Validation**
   - During `MigrationState.VALIDATION`, GraphRAG can find semantically similar records
   - Helps detect duplicate data or similar entities across sources
   - **Quality Gate**: Configurable similarity threshold in `config/monitoring_thresholds.json`

### 3.3 Functional Requirements
1. **Health Endpoint**
   - `GET /api/neo4j-graphrag/health` initializes service on-demand and returns `{status, neo4j_connected, embedding_dimension}`; handles import errors gracefully.
   - **Integration**: Called by analytics_router health check for comprehensive status

2. **Query Endpoint** (Core Search Feature)
   - `POST /api/neo4j-graphrag/query` consumes `GraphRAGQueryRequest` with `question`, `context`, optional `tools[]`, `top_k`, and `include_paths` flags.
   - `Neo4jGraphRAGService.run_query` must:
     - Generate embeddings for question/context.
     - Execute hybrid search (vector + metadata) against Neo4j indexes.
     - **Optional**: Query OpenSearch for supplementary results if `include_opensearch=true`
     - Return structured response with `answers[]`, `sources[]`, `tools_invoked[]`, and latency metrics.
   - Router wraps service errors into HTTP 500 with descriptive message.
   - **Migration Integration**: Used during profiling phase to understand source data semantics

3. **Tool Metadata**
   - Service exposes `list_tools()` for UI integration (future). 
   - **Requirement**: Keep method ready even if router doesn't expose yet, to satisfy `GraphStack` roadmap.
   - **ETL Tools**: Register GraphQL transforms as "tools" for agent-based workflows

4. **Observability**
   - Service logs initialization parameters and query outcomes via module logger; ensure log entries include `trace_id` when available.
   - **Analytics Integration**: Query metrics sent to analytics_storage_service for dashboard
   - **Correlation IDs**: Propagate `X-Trace-Id` from migration WebSocket sessions

### 3.4 Data & Configuration
- Neo4j index requirements: nodes must store both dense vectors (embedding) and textual summaries for fallback search.
- **Index Types**:
  - `MigrationSession` nodes with state transition vectors
  - `DataSource` nodes with schema embedding
  - `TransformOperation` nodes with semantic description
  - `QualityMetric` nodes with error pattern vectors
- Environment variables (defaults shown in code):
  - `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD` – connection (from `config/environments.json`)
  - `GRAPH_RAG_EMBED_DIMENSION` (optional) – defaults to 1536.
  - `GRAPH_RAG_TOOLS_CONFIG` (optional JSON) – custom tool definitions (link to GraphQL catalogue)
  - `OPENSEARCH_HYBRID_MODE` (optional) – enable OpenSearch result fusion

### 3.5 Validation
- Unit tests TBD (none currently in `python_backend/tests`). 
- **Required Test Scenarios**:
  1. Health check returns disconnected when Neo4j unreachable (mock driver).
  2. Query returns answers with stubbed Neo4j responses and ensures `top_k` respected.
  3. Hybrid mode correctly merges Neo4j and OpenSearch results
  4. Tool invocation logs properly to analytics service
- Integration: run against dev Neo4j with seeded vector data; confirm latency <1 s for top-5 queries as per stakeholder expectations.
- **Add to**: `python_backend/tests/test_neo4j_graphrag.py` (new file)

### 3.6 Risks / Follow-ups
- **Dependency loading**: router lazily imports service inside handlers; ensure cold-start penalties are acceptable or refactor to module-level singletons.
  - **Recommendation**: Initialize in main.py startup event alongside migration_engine
- **Security**: No auth guard currently on `/api/neo4j-graphrag`; align with platform auth middleware before exposing externally.
  - **Action**: Add to security audit backlog (reference: `FR-OPS-01` from PAGE_REQUIREMENTS_SPECIFICATIONS.md)

---

## 4. Integration Architecture: The Unified Data Fabric

### 4.1 Data Flow: ETL → Graph → Search

```
1. ETL Ingestion Phase
   ├─→ GraphQL introspect schemas (XML/JSON)
   ├─→ Store schema in PostgreSQL catalogue
   └─→ Create Neo4j nodes for DataSource entities

2. Transformation Phase  
   ├─→ GraphQL transform applies mappings
   ├─→ Store transform metadata in Neo4j as relationships
   └─→ Migration engine tracks state: DATA_MIGRATION

3. Validation Phase
   ├─→ GraphQL query validates completeness
   ├─→ GraphRAG finds semantic duplicates
   └─→ Analytics service records quality metrics

4. Indexing Phase
   ├─→ OpenSearch indexes transformed data
   ├─→ Neo4j stores relationships for context
   └─→ GraphRAG enables hybrid search

5. Visualization Phase
   ├─→ XState visualizer shows migration state (T-04)
   ├─→ Graph Explorer shows data lineage
   └─→ Analytics dashboard aggregates metrics (T-05)
```

### 4.2 Component Interactions

| Component | Produces | Consumes | Storage |
|-----------|----------|----------|---------|
| GraphQL Toolkit | Schema metadata, Transforms | Source schemas (XML/JSON) | PostgreSQL (catalogue) |
| Migration Engine | State transitions, Quality scores | GraphQL transforms | PostgreSQL (sessions), Neo4j (history) |
| Neo4j GraphRAG | Semantic answers, Graph context | Question + Neo4j data | Neo4j (vectors) |
| OpenSearch | Search results, Aggregations | Transformed data | OpenSearch (indexes) |
| Analytics Service | Metrics, Health data | All service outputs | PostgreSQL (analytics schema) |
| Graph Explorer UI | Visualization, Cypher queries | Neo4j graph data | Browser state (Recoil) |
| XState Visualizer | State machine UI | Migration state WebSocket | Browser state (React) |

### 4.3 Configuration Alignment

All components reference:
- `config/system_configuration.json` - Service ports, timeouts
- `config/environments.json` - Environment-specific URLs
- `config/monitoring_thresholds.json` - Quality gates, alerts
- `.env` - Credentials (not committed)

### 4.4 API Surface Summary

| Service | Base Path | Key Endpoints | Documented In |
|---------|-----------|---------------|---------------|
| GraphQL Toolkit | `/api/graphql` | introspect, transform, query, catalogue/* | Section 1.4 |
| Migration Engine | `/api/migration/advanced` | start, events, history, ws | T-03 (PAGE_REQUIREMENTS_SPECIFICATIONS.md) |
| Analytics Storage | `/api/analytics` | upload-metric, service-health, uploads | T-05 (PAGE_REQUIREMENTS_SPECIFICATIONS.md) |
| Neo4j GraphRAG | `/api/neo4j-graphrag` | health, query | Section 3.3 |
| OpenSearch | `/api/opensearch` | health, indexes, search | C-OPEN (PAGE_REQUIREMENTS_SPECIFICATIONS.md) |

---

## 5. Next Steps & Action Items

### 5.1 Immediate (Pre-Release)
1. **Graph Explorer Route Fix** ⚠️ CRITICAL
   - [ ] Restore the missing `GraphExplorerContent` module or relocate component
   - [ ] Add `/graph-explorer` route to `e2etraceapp/src/routes/index.jsx`
   - [ ] Update navigation in `e2etrace-root-layout.jsx`
   - [ ] Update import paths in `GraphExplorer.jsx`
   - **Owner**: Frontend team
   - **Estimated effort**: 2-4 hours

2. **Integration Testing** ⚠️ HIGH PRIORITY
   - [ ] Add `python_backend/tests/test_neo4j_graphrag.py` with 5+ scenarios
   - [ ] Add GraphQL integration tests to `test_advanced_migration_features.py`
   - [ ] Add Playwright test for Graph Explorer once route restored
   - **Owner**: QA + Backend team
   - **Estimated effort**: 1-2 days

3. **Documentation Linking** 📝
   - [ ] Link this document from `PAGE_REQUIREMENTS_SPECIFICATIONS.md` Section 10
   - [ ] Update API reference table with GraphQL and GraphRAG endpoints
   - [ ] Add sequence diagrams for ETL → Graph → Search flow
   - **Owner**: Technical writer + Platform PM
   - **Estimated effort**: 4 hours

### 5.2 Short-Term (Next Sprint)
4. **Security Hardening** 🔒
   - [ ] Add auth guards to `/api/neo4j-graphrag` endpoints
   - [ ] Add rate limiting to GraphQL transform endpoint (prevent abuse)
   - [ ] Audit GraphQL query endpoint for injection risks
   - **Owner**: Security + Backend team
   - **Estimated effort**: 2-3 days

5. **Performance Optimization** ⚡
   - [ ] Implement GraphQL schema cache with TTL
   - [ ] Add connection pooling for Neo4j in GraphRAG service
   - [ ] Lazy-load GraphRAG service at startup instead of per-request
   - **Owner**: Backend team
   - **Estimated effort**: 3-4 days

6. **Observability Enhancement** 📊
   - [ ] Add Prometheus metrics for GraphQL transform throughput
   - [ ] Add tracing spans for GraphRAG query pipeline
   - [ ] Link analytics dashboard to GraphQL catalogue usage
   - **Owner**: DevOps + Backend team
   - **Estimated effort**: 2 days

### 5.3 Medium-Term (Next Quarter)
7. **Feature Enhancements** ✨
   - [ ] Implement GraphQL subscription support for real-time transforms
   - [ ] Add GraphRAG tool registration API for dynamic ETL agents
   - [ ] Build Graph Explorer plugins for custom visualizations
   - **Owner**: Product + Engineering
   - **Estimated effort**: 2-4 weeks

8. **Migration Consolidation** 🔄
   - [ ] Deprecate `GraphExplorerMigrated.jsx` after feature parity verified
   - [ ] Migrate all Cypher queries to use GraphQL catalogue
   - [ ] Unify connection management across all graph-dependent components
   - **Owner**: Frontend team
   - **Estimated effort**: 1-2 weeks

### 5.4 Long-Term (Roadmap)
9. **Advanced Capabilities** 🚀
   - [ ] Multi-graph federation (connect multiple Neo4j instances)
   - [ ] GraphQL federation with OpenSearch (unified query language)
   - [ ] AI-powered schema mapping suggestions via GraphRAG
   - [ ] Real-time collaborative graph editing in Graph Explorer
   - **Owner**: Product + Research
   - **Estimated effort**: 3-6 months

---

## 6. Alignment Verification Checklist

### 6.1 ETL Integration ✅
- [x] GraphQL toolkit documented as primary data mapping layer
- [x] Transform endpoint linked to migration engine DATA_MIGRATION state
- [x] Schema introspection integrated with DISCOVERING phase
- [x] Query execution linked to VALIDATION phase
- [x] Catalogue management enables repeatable ETL workflows

### 6.2 XState Visualizer Integration ✅
- [x] Neo4j storage for migration state transitions specified
- [x] Graph Explorer visualization of state history described
- [x] PLMMigrationStatechartVisualizer.jsx integration documented
- [x] WebSocket synchronization with migration_router explained
- [x] CSV export feature leverages Neo4j query history

### 6.3 OpenSearch Integration ✅
- [x] GraphRAG hybrid search strategy defined
- [x] Neo4j + OpenSearch result fusion architecture documented
- [x] Analytics metrics indexing in both systems specified
- [x] Semantic validation during ETL explained
- [x] Configuration alignment across all services verified

### 6.4 Data Mapping Simplification ✅
- [x] GraphQL transform engine as core mapping tool
- [x] Visual schema mapping via Graph Explorer (future)
- [x] Persisted mapping catalogue for reuse
- [x] Error handling and partial transform support
- [x] Integration with analytics for mapping quality metrics

---

## 7. Glossary

- **GraphRAG**: Graph Retrieval-Augmented Generation - hybrid search combining graph traversal with vector similarity
- **Pseudo-GraphQL**: Simplified GraphQL-like query syntax for JSON data (not full GraphQL spec compliance)
- **Schema Cache**: Cached schema metadata in PostgreSQL to avoid repeated introspection
- **Hybrid Search**: Search strategy combining multiple indexes (Neo4j vector + OpenSearch k-NN)
- **Transform Mapping**: Field-level mapping with optional transformation function applied during data migration
- **State Transition Graph**: Neo4j representation of migration state changes over time
- **Cypher**: Neo4j's graph query language (analogous to SQL for relational databases)
- **Vector Embedding**: Dense numerical representation of text/data for semantic similarity search
- **XState Machine**: Finite state machine definition used by visualizer components

---

## 8. References

### 8.1 Internal Documentation
- `PAGE_REQUIREMENTS_SPECIFICATIONS.md` - Parent requirements document
- `TASK_COMPLETION_VERIFICATION.md` - Implementation verification report
- `config/system_configuration.json` - Service configuration
- `config/monitoring_thresholds.json` - Quality gates and alerts

### 8.2 Code Artifacts
- Backend: `python_backend/graph_api/graphql_router.py`, `python_backend/services/neo4j_graphrag_service.py`
- Frontend: `e2etraceapp/src/components/GraphExplorer.jsx`, `e2etraceapp/src/services/neo4j-data-service.js`
- Tests: `python_backend/tests/test_advanced_migration_features.py`, `python_backend/tests/test_analytics_storage.py`

### 8.3 External Resources
- Neo4j Documentation: https://neo4j.com/docs/
- OpenSearch Documentation: https://opensearch.org/docs/
- GraphQL Specification: https://spec.graphql.org/
- XState Documentation: https://xstate.js.org/docs/

---

_This document should be checked into version control alongside `PAGE_REQUIREMENTS_SPECIFICATIONS.md` and updated whenever GraphQL, Graph Explorer, or GraphRAG features change. Last reviewed: 2025-11-23 by Platform Engineering team._
