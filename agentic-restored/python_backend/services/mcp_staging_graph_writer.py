"""MCP staging graph writer.

Implements the missing P0 piece: taking *staged samples* from an MCP migration
run and writing them into Neo4j as a canonical intermediate graph.

Design goals:
- Best-effort and safe by default: only writes the staged *sample* payloads.
- Idempotent upsert semantics via MERGE (run_id + entity + record_key).
- Adds minimal provenance/audit nodes so staged entities can be traced.

This does NOT attempt to model full PLM semantics yet. It simply makes staged
records visible in Neo4j for downstream analysis, mapping proposals, and HITL.
"""

# pylint: disable=broad-exception-caught

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import neo4j

from core.config import NEO4J_DATABASE


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def stable_record_key(entity: str, record: Dict[str, Any]) -> str:
    """Stable content hash for a staged record.

    We include the `entity` name so keys don't collide across entity types.
    """
    try:
        payload = json.dumps(record, sort_keys=True, ensure_ascii=False, default=str)
    except Exception:
        payload = str(record)
    raw = f"{entity}|{payload}".encode("utf-8", errors="replace")
    return hashlib.sha1(raw).hexdigest()  # noqa: S324 (non-crypto use: idempotent key)


# Backwards-compatible alias (internal name used previously).
_stable_record_key = stable_record_key


class MCPStagingGraphWriter:
    """Writes staged MCP run samples to Neo4j."""

    def __init__(self, driver: neo4j.AsyncDriver, *, database: Optional[str] = None):
        self._driver = driver
        self._database = database or NEO4J_DATABASE

    async def materialize_run_samples(
        self,
        *,
        run_payload: Dict[str, Any],
        entities: Optional[List[str]] = None,
        batch_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Materialize staged samples from `run_payload["staged"]` into Neo4j.

        Returns a small summary: which entities were written and how many sample
        nodes were upserted.
        """
        run_id = str(run_payload.get("run_id") or "").strip()
        if not run_id:
            raise ValueError("run_payload.run_id is required")

        staged = run_payload.get("staged")
        if not isinstance(staged, dict) or not staged:
            return {"run_id": run_id, "written_entities": [], "sample_nodes": 0}

        wanted = None
        if entities:
            wanted = {str(e).strip() for e in entities if str(e).strip()}

        b_id = (batch_id or "").strip() or f"materialize_{_utcnow_iso()}"
        now = _utcnow_iso()

        total_nodes = 0
        written_entities: List[str] = []

        async with self._driver.session(database=self._database) as session:
            # 1) Upsert run node
            await session.run(
                """
                MERGE (r:MCPMigrationRun {run_id: $run_id})
                ON CREATE SET r.created_at = $created_at
                SET r.updated_at = $updated_at,
                    r.workflow_name = $workflow_name,
                    r.source_id = $source_id,
                    r.target_id = $target_id,
                    r.status = $status
                """,
                run_id=run_id,
                created_at=str(run_payload.get("created_at") or now),
                updated_at=now,
                workflow_name=str(run_payload.get("workflow_name") or ""),
                source_id=(run_payload.get("source_id") if run_payload.get("source_id") else None),
                target_id=(run_payload.get("target_id") if run_payload.get("target_id") else None),
                status=str(run_payload.get("status") or "created"),
            )

            # 2) Upsert entity sample nodes + provenance
            for entity, entry in staged.items():
                ent = str(entity or "").strip()
                if not ent:
                    continue
                if wanted is not None and ent not in wanted:
                    continue

                sample: List[Dict[str, Any]] = []
                if isinstance(entry, dict):
                    sample_val = entry.get("sample")
                    if isinstance(sample_val, list):
                        sample = [r for r in sample_val if isinstance(r, dict)]

                if not sample:
                    continue

                records_payload = []
                for rec in sample:
                    rec_key = stable_record_key(ent, rec)
                    try:
                        payload_json = json.dumps(rec, ensure_ascii=False, default=str)
                    except Exception:
                        payload_json = json.dumps({"_repr": str(rec)})

                    records_payload.append(
                        {
                            "record_key": rec_key,
                            "payload": payload_json,
                            "staged_at": str(entry.get("staged_at") or now),
                        }
                    )

                await session.run(
                    """
                    MATCH (r:MCPMigrationRun {run_id: $run_id})
                    UNWIND $records AS rec
                    MERGE (e:MCPStagedEntity {run_id: $run_id, entity: $entity, record_key: rec.record_key})
                    ON CREATE SET e.created_at = $now
                    SET e.updated_at = $now,
                        e.batch_id = $batch_id,
                        e.source_id = $source_id,
                        e.target_id = $target_id,
                        e.staged_at = rec.staged_at,
                        e.payload = rec.payload
                    MERGE (r)-[:HAS_STAGED]->(e)
                    MERGE (p:MCPProvenance {run_id: $run_id, entity: $entity, record_key: rec.record_key})
                    ON CREATE SET p.first_seen = $now
                    SET p.last_seen = $now,
                        p.batch_id = $batch_id,
                        p.source_id = $source_id,
                        p.target_id = $target_id
                    MERGE (e)-[:PROVENANCE]->(p)
                    """,
                    run_id=run_id,
                    entity=ent,
                    records=records_payload,
                    now=now,
                    batch_id=b_id,
                    source_id=(run_payload.get("source_id") if run_payload.get("source_id") else None),
                    target_id=(run_payload.get("target_id") if run_payload.get("target_id") else None),
                )

                total_nodes += len(records_payload)
                written_entities.append(ent)

        return {"run_id": run_id, "written_entities": written_entities, "sample_nodes": total_nodes, "batch_id": b_id}

    async def record_published_documents(
        self,
        *,
        run_id: str,
        target_id: Optional[str],
        target_kind: str,
        index: str,
        documents: List[Dict[str, Any]],
        batch_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Record target publish events in Neo4j for lineage/traceability.

        `documents` entries should include:
          - entity (str)
          - record_key (str)
          - target_ref (str)  # e.g., OpenSearch doc id
        """
        rid = (run_id or "").strip()
        if not rid:
            raise ValueError("run_id is required")

        docs = [d for d in (documents or []) if isinstance(d, dict)]
        if not docs:
            return {"run_id": rid, "published": 0}

        now = _utcnow_iso()
        b_id = (batch_id or "").strip() or f"publish_{now}"

        async with self._driver.session(database=self._database) as session:
            await session.run(
                """
                MERGE (r:MCPMigrationRun {run_id: $run_id})
                SET r.updated_at = $now
                """,
                run_id=rid,
                now=now,
            )

            await session.run(
                """
                MATCH (r:MCPMigrationRun {run_id: $run_id})
                UNWIND $docs AS doc
                MERGE (t:MCPTargetDocument {
                    run_id: $run_id,
                    target_id: $target_id,
                    target_kind: $target_kind,
                    target_index: $target_index,
                    entity: doc.entity,
                    record_key: doc.record_key
                })
                ON CREATE SET t.created_at = $now
                SET t.updated_at = $now,
                    t.batch_id = $batch_id,
                    t.target_ref = doc.target_ref,
                    t.published_at = $now
                MERGE (r)-[:PUBLISHED]->(t)
                WITH t, doc
                OPTIONAL MATCH (e:MCPStagedEntity {run_id: $run_id, entity: doc.entity, record_key: doc.record_key})
                FOREACH (_ IN CASE WHEN e IS NULL THEN [] ELSE [1] END |
                    MERGE (e)-[:PUBLISHED_AS]->(t)
                )
                """,
                run_id=rid,
                target_id=(str(target_id).strip() if target_id else None),
                target_kind=(target_kind or "").strip() or "unknown",
                target_index=(index or "").strip() or "unknown",
                docs=docs,
                now=now,
                batch_id=b_id,
            )

        return {"run_id": rid, "published": len(docs), "batch_id": b_id}
