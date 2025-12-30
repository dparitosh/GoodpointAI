# Spark + Neo4j + openCypher (PySpark) — Repo-Aligned Recipe

This doc explains how to use **PySpark with openCypher** in a way that fits this repository’s operating model:

- **Postgres is the system of record (truth).**
- **Neo4j is derived (impact/structure substrate).**
- **OpenSearch is optional retrieval only** (fail-closed if not configured).
- **No mock/sample/demo data.** If a dependency is required and not configured, endpoints fail closed (HTTP 503) and UI shows N/A.

## 1) What “PySpark + openCypher” means in practice

PySpark does not execute Cypher by itself.

You get “Spark + Cypher” by using Neo4j as the Cypher engine and Spark as the distributed compute engine:

- Spark sends a **Cypher query** to Neo4j.
- Neo4j executes the Cypher query.
- Spark receives the result as a DataFrame.

That integration is typically done using the **Neo4j Spark Connector**.

## 2) Recommended integration pattern (production-stable)

### Pattern A — Spark ↔ Neo4j via Neo4j Spark Connector (recommended)

**Use this when:**
- You want scalable transformations/analytics in Spark.
- You want to read/write Neo4j using Cypher.
- You want Neo4j to remain the Cypher execution engine.

**What you install where:**
- **Backend (FastAPI):** do not install PySpark. Backend orchestrates runs and reads/writes Postgres.
- **Spark job environment:** install PySpark (Python) and attach the Neo4j Spark Connector (JVM).

The repository already keeps backend runtime deps in `python_backend/requirement.txt` and external/optional deps in `python_backend/requirements_external_integrations.txt`.

## 3) Architecture aligned to this repo (single Postgres truth)

### Data flow

1. **FastAPI** creates a run (`run_id`) and stages source payloads into Postgres.
2. **Spark job** reads canonical/staged tables from Postgres for that `run_id`.
3. Spark performs transforms and large-scale validations.
4. Spark persists outputs and DQ results back into Postgres.
5. Spark optionally syncs derived structure into Neo4j (nodes/relationships).

### Fail-closed policy

- If Postgres is not configured: ETL/DQ endpoints must return **503**.
- If Neo4j is not configured:
  - If Neo4j is optional for the endpoint, do “best-effort emit” and continue.
  - If Neo4j is required for the endpoint’s semantics, return **503**.

## 4) How to run Cypher from Spark (Neo4j Spark Connector)

You typically configure the connector at submit time.

### Example: read DataFrame via Cypher

Pseudo-code (PySpark):

```python
df = (
    spark.read.format("org.neo4j.spark.DataSource")
    .option("url", "bolt://<neo4j-host>:7687")
    .option("authentication.type", "basic")
    .option("authentication.basic.username", "<user>")
    .option("authentication.basic.password", "<pass>")
    .option(
        "query",
        """
        MATCH (p:Part)-[:HAS_REVISION]->(r:Revision)
        RETURN p.id AS partId, r.state AS state
        """,
    )
    .load()
)
```

### Example: write nodes/relationships

You can write DataFrames to Neo4j (nodes or relationships) depending on connector options. The details vary by connector major version.

**Important:** treat Neo4j as a derived store. The Spark job should always persist the authoritative result into Postgres first.

## 5) Where Spark fits with PLM ETL + DQ

This repo already has a Postgres-backed “happy path” for PLM ETL + persisted DQ results.

Spark can be used to:
- Scale transforms (joins, dedup, normalization)
- Run bulk integrity checks
- Compute graph export tables (node/edge tables) to load into Neo4j

### Practical contract

- Spark reads **only** from Postgres tables for a given `run_id`.
- Spark writes:
  - canonical outputs (truth) back to Postgres
  - DQ outcomes into persisted tables (truth)
  - derived graph projection into Neo4j (optional / derived)

## 6) Dependency note (why PySpark is optional)

Installing PySpark into the FastAPI runtime:
- increases image size and startup time
- adds Java runtime requirements
- couples API service uptime to Spark runtime concerns

So the recommended model is:
- FastAPI backend stays lean and deterministic
- Spark runs as a separate worker/job system

For local experimentation only, `pyspark` is listed as optional in `python_backend/requirements_external_integrations.txt`.

## 7) “Latest versions” guidance (without breaking upgradeability)

Exact versions for Spark/connector must be chosen to match:
- your Spark cluster version
- your Scala version (2.12 vs 2.13)
- your Neo4j major version

For this repo, the best practice is:
- keep backend dependencies pinned (reproducible)
- keep Spark-side dependencies version-ranged or pinned per environment

## 8) What to implement next (when you’re ready)

- A minimal `spark_jobs/` folder exists now under `agentic-restored/spark_jobs/`.
  - `sync_plm_run_to_neo4j.py` takes `run_id` as input
  - reads Postgres via JDBC (derived from `DATABASE_URL`)
  - syncs a derived graph to Neo4j via **openCypher** (Neo4j Python driver)

If you want me to implement this wiring (job skeleton + a minimal run orchestration endpoint) I can, but I’ll keep it fail-closed and will not add any sample/demo data.