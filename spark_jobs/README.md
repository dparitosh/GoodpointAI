# Spark Jobs (PySpark) — Neo4j openCypher sync

This folder is intentionally **separate** from the FastAPI backend runtime.

Goal: run Spark-scale transforms/exports while keeping:
- **Postgres as truth** (system of record)
- **Neo4j derived** (impact/structure substrate)
- **No mock/sample/demo data**

## What’s here

- `sync_plm_run_to_neo4j.py`: Reads PLM canonical tables for a `run_id` from Postgres and syncs nodes/relationships into Neo4j using **openCypher**.
- `run_sync_neo4j.ps1`: Windows helper to run the job with `spark-submit`.
- `requirements.txt`: Spark-job-only Python deps.

## Prerequisites

- Java + Spark installed and `spark-submit` available on PATH.
- A real Postgres instance reachable via `DATABASE_URL`.
- A real Neo4j instance reachable via `NEO4J_URI`, `NEO4J_USERNAME`, `NEO4J_PASSWORD`.

## Required environment variables

- `DATABASE_URL` (example format): `postgresql://user:pass@host:5433/dbname`
- `NEO4J_URI` (example): `bolt://localhost:7687`
- `NEO4J_USERNAME`
- `NEO4J_PASSWORD`

## Run (Windows)

```powershell
cd spark_jobs
python -m pip install -r requirements.txt

# set env vars in your shell first
.\run_sync_neo4j.ps1 -RunId <run_id>
```

## Notes

- This job **does not** invent data. If the run has no parts/BOM rows in Postgres, it fails with a clear error.
- Neo4j is treated as **derived**; rerunning for the same `run_id` is safe because writes use `MERGE`.
