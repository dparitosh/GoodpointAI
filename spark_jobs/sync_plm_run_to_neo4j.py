from __future__ import annotations

import argparse
import importlib
import os
import sys
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Tuple

from neo4j import GraphDatabase

# Type aliases to avoid requiring pyspark stubs in the backend editor environment.
SparkSession = Any
DataFrame = Any


@dataclass(frozen=True)
class PgJdbcConfig:
    url: str
    user: str
    password: str


def _die(msg: str, code: int = 2) -> None:
    print(msg, file=sys.stderr)
    raise SystemExit(code)


def _require_env(name: str) -> str:
    val = (os.getenv(name) or '').strip()
    if not val:
        _die(f"Missing required env var: {name}")
    return val


def _parse_database_url_to_jdbc(database_url: str) -> PgJdbcConfig:
    # Accept postgresql:// or postgres://
    if database_url.startswith('postgresql+psycopg://'):
        database_url = 'postgresql://' + database_url[len('postgresql+psycopg://'):]

    if database_url.startswith('postgres://'):
        database_url = 'postgresql://' + database_url[len('postgres://'):]

    if not database_url.startswith('postgresql://'):
        _die('DATABASE_URL must start with postgresql:// or postgres://')

    # Very small parser to avoid extra deps.
    # postgresql://user:pass@host:port/dbname
    rest = database_url[len('postgresql://'):]

    creds, _, host_and_db = rest.partition('@')
    if not _:
        _die('DATABASE_URL must include credentials and host (user:pass@host:port/db)')

    user, _, password = creds.partition(':')
    if not _:
        _die('DATABASE_URL must include password (user:pass@...)')

    host_port, _, dbname = host_and_db.partition('/')
    if not _ or not dbname:
        _die('DATABASE_URL must include database name (…/dbname)')

    host, _, port = host_port.partition(':')
    if not host:
        _die('DATABASE_URL missing host')

    port = port or '5432'

    jdbc_url = f"jdbc:postgresql://{host}:{port}/{dbname}"
    return PgJdbcConfig(url=jdbc_url, user=user, password=password)


def _read_plm_parts(spark: SparkSession, pg: PgJdbcConfig, run_id: str) -> DataFrame:
    query = (
        "(SELECT run_id, part_number, name, description, classification "
        " FROM plm_parts "
        f" WHERE run_id = '{run_id}'"  # run_id is server-generated uuid hex; still keep it simple.
        ") AS t"
    )
    return (
        spark.read.format('jdbc')
        .option('url', pg.url)
        .option('user', pg.user)
        .option('password', pg.password)
        .option('dbtable', query)
        .load()
    )


def _read_plm_bom(spark: SparkSession, pg: PgJdbcConfig, run_id: str) -> DataFrame:
    query = (
        "(SELECT run_id, parent_part_number, child_part_number, quantity "
        " FROM plm_bom_items "
        f" WHERE run_id = '{run_id}'"
        ") AS t"
    )
    return (
        spark.read.format('jdbc')
        .option('url', pg.url)
        .option('user', pg.user)
        .option('password', pg.password)
        .option('dbtable', query)
        .load()
    )


def _df_has_any_rows(df: DataFrame) -> bool:
    return df.limit(1).count() > 0


def _neo4j_write_parts(
    rows: Iterable[Tuple[str, Optional[str], Optional[str], Optional[str], str]],
    neo4j_uri: str,
    neo4j_user: str,
    neo4j_password: str,
) -> None:
    # rows: (part_number, name, description, classification, run_id)
    driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))
    try:
        with driver.session() as session:
            # Ensure a stable natural key for derived graph.
            session.run(
                "CREATE CONSTRAINT part_number_unique IF NOT EXISTS "
                "FOR (p:Part) REQUIRE p.part_number IS UNIQUE"
            )

            batch: List[Dict[str, Any]] = []
            for part_number, name, description, classification, run_id in rows:
                batch.append(
                    {
                        'part_number': part_number,
                        'name': name,
                        'description': description,
                        'classification': classification,
                        'run_id': run_id,
                    }
                )
                if len(batch) >= 1000:
                    session.run(
                        "UNWIND $rows AS row "
                        "MERGE (p:Part {part_number: row.part_number}) "
                        "SET p.name = row.name, "
                        "    p.description = row.description, "
                        "    p.classification = row.classification, "
                        "    p.last_seen_run_id = row.run_id",
                        rows=batch,
                    )
                    batch.clear()

            if batch:
                session.run(
                    "UNWIND $rows AS row "
                    "MERGE (p:Part {part_number: row.part_number}) "
                    "SET p.name = row.name, "
                    "    p.description = row.description, "
                    "    p.classification = row.classification, "
                    "    p.last_seen_run_id = row.run_id",
                    rows=batch,
                )
    finally:
        driver.close()


def _neo4j_write_bom(
    rows: Iterable[Tuple[str, str, Optional[float], str]],
    neo4j_uri: str,
    neo4j_user: str,
    neo4j_password: str,
) -> None:
    # rows: (parent_part_number, child_part_number, quantity, run_id)
    driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))
    try:
        with driver.session() as session:
            batch: List[Dict[str, Any]] = []
            for parent_pn, child_pn, quantity, run_id in rows:
                batch.append(
                    {
                        'parent_part_number': parent_pn,
                        'child_part_number': child_pn,
                        'quantity': quantity,
                        'run_id': run_id,
                    }
                )
                if len(batch) >= 1000:
                    session.run(
                        "UNWIND $rows AS row "
                        "MERGE (parent:Part {part_number: row.parent_part_number}) "
                        "MERGE (child:Part {part_number: row.child_part_number}) "
                        "MERGE (parent)-[r:HAS_CHILD {run_id: row.run_id}]->(child) "
                        "SET r.quantity = row.quantity",
                        rows=batch,
                    )
                    batch.clear()

            if batch:
                session.run(
                    "UNWIND $rows AS row "
                    "MERGE (parent:Part {part_number: row.parent_part_number}) "
                    "MERGE (child:Part {part_number: row.child_part_number}) "
                    "MERGE (parent)-[r:HAS_CHILD {run_id: row.run_id}]->(child) "
                    "SET r.quantity = row.quantity",
                    rows=batch,
                )
    finally:
        driver.close()


def main() -> None:
    parser = argparse.ArgumentParser(description='Sync a PLM ETL run from Postgres into Neo4j (derived graph)')
    parser.add_argument('--run-id', required=True)
    args = parser.parse_args()

    run_id = (args.run_id or '').strip()
    if not run_id:
        _die('run_id is required')

    database_url = _require_env('DATABASE_URL')
    neo4j_uri = _require_env('NEO4J_URI')
    neo4j_user = _require_env('NEO4J_USERNAME')
    neo4j_password = _require_env('NEO4J_PASSWORD')

    pg = _parse_database_url_to_jdbc(database_url)

    # Import pyspark only in the Spark job environment.
    pyspark_sql = importlib.import_module("pyspark.sql")
    _SparkSession = pyspark_sql.SparkSession

    spark = (
        _SparkSession.builder.appName(f"graphtrace-plm-sync-{run_id}")
        .config('spark.sql.session.timeZone', 'UTC')
        .getOrCreate()
    )

    try:
        parts_df = _read_plm_parts(spark, pg, run_id)
        bom_df = _read_plm_bom(spark, pg, run_id)

        if not _df_has_any_rows(parts_df) and not _df_has_any_rows(bom_df):
            _die('No plm_parts or plm_bom_items rows found for this run_id. Nothing to sync.')

        # Collect minimal columns only. For large runs, prefer connector-based writes.
        if _df_has_any_rows(parts_df):
            part_rows = (
                parts_df.select('part_number', 'name', 'description', 'classification', 'run_id')
                .dropna(subset=['part_number'])
                .distinct()
                .collect()
            )
            _neo4j_write_parts(
                ((r['part_number'], r['name'], r['description'], r['classification'], r['run_id']) for r in part_rows),
                neo4j_uri,
                neo4j_user,
                neo4j_password,
            )

        if _df_has_any_rows(bom_df):
            bom_rows = (
                bom_df.select('parent_part_number', 'child_part_number', 'quantity', 'run_id')
                .dropna(subset=['parent_part_number', 'child_part_number'])
                .distinct()
                .collect()
            )
            _neo4j_write_bom(
                (
                    (r['parent_part_number'], r['child_part_number'], r['quantity'], r['run_id'])
                    for r in bom_rows
                ),
                neo4j_uri,
                neo4j_user,
                neo4j_password,
            )

        print('OK: Neo4j sync completed')

    finally:
        spark.stop()


if __name__ == '__main__':
    main()
