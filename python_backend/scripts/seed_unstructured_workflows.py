"""
Seed unstructured data workflows for OpenSearch and Neo4j.

This script loads PLM/CAD unstructured data workflows and populates:
1. Workflow instances via the existing workflow API
2. OpenSearch indices with PLM part documents
3. Neo4j nodes and relationships for graph lineage

Usage:
    python -m scripts.seed_unstructured_workflows [--force]
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Paths
FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"
WORKFLOWS_FILE = FIXTURES_DIR / "unstructured_workflows.json"

# SPLM source folder
#
# For portability, do not hard-code a developer-local path.
# Override with `SPLM_FOLDER` to point at a local directory containing *.stp/*.xml.
_splm_env = (os.getenv("SPLM_FOLDER") or "").strip()
SPLM_FOLDER = Path(_splm_env) if _splm_env else (FIXTURES_DIR / "SPLM")


def load_fixtures() -> dict[str, Any]:
    """Load the unstructured workflows fixture file."""
    if not WORKFLOWS_FILE.exists():
        raise FileNotFoundError(f"Fixtures file not found: {WORKFLOWS_FILE}")
    return json.loads(WORKFLOWS_FILE.read_text(encoding="utf-8"))


def parse_stp_filename(filename: str) -> Optional[dict[str, Any]]:
    """Parse STEP filename to extract part information."""
    # Pattern: 000678_A;1-SKF_6306-2Z7097_Prt2 (2022_12_17 03_45_52 UTC).stp
    match = re.match(r"(\d+)_([A-Z]);(\d+)-(.+?)\s*\((\d{4}_\d{2}_\d{2})", filename)
    if match:
        return {
            "part_number": match.group(1),
            "revision": match.group(2),
            "version": match.group(3),
            "name": match.group(4).replace("_", " "),
            "date_str": match.group(5).replace("_", "-")
        }
    # Alternative pattern: INDUCTION MOTOR ASSEMBLY 5HP (2022_12_17 01_44_39 UTC).stp
    match = re.match(r"(.+?)\s*\((\d{4}_\d{2}_\d{2})", filename)
    if match:
        return {
            "part_number": f"ASM_{hash(filename) % 10000:04d}",
            "revision": "A",
            "version": "1",
            "name": match.group(1).replace("_", " "),
            "date_str": match.group(2).replace("_", "-")
        }
    return None


def seed_opensearch_indices(fixtures: dict[str, Any], force: bool = False) -> int:
    """Seed OpenSearch indices with PLM part data."""
    try:
        from opensearchpy import OpenSearch
    except ImportError:
        logger.warning("opensearch-py not installed, skipping OpenSearch seeding")
        return 0

    os_config = fixtures.get("opensearch_indices", {})
    if not os_config:
        logger.info("No OpenSearch indices defined in fixtures")
        return 0

    # Connect to OpenSearch
    os_url = os.getenv("OPENSEARCH_URL", "http://localhost:9200")
    timeout_s = float((os.getenv("OPENSEARCH_TIMEOUT_S") or "10").strip() or 10)
    try:
        client = OpenSearch(
            hosts=[os_url],
            http_compress=True,
            use_ssl=False,
            verify_certs=False,
            ssl_show_warn=False,
            timeout=timeout_s,
        )
        info = client.info()
        logger.info("Connected to OpenSearch %s", info.get("version", {}).get("number", "unknown"))
    except Exception as e:
        logger.warning("Cannot connect to OpenSearch at %s: %s", os_url, e)
        return 0

    docs_indexed = 0

    # Create indices
    for index_name, index_config in os_config.items():
        try:
            if client.indices.exists(index=index_name):
                if force:
                    logger.info("Deleting existing index: %s", index_name)
                    client.indices.delete(index=index_name)
                else:
                    logger.info("Index %s already exists, skipping creation", index_name)
                    continue

            logger.info("Creating index: %s", index_name)
            client.indices.create(
                index=index_name,
                body={
                    "settings": index_config.get("settings", {}),
                    "mappings": index_config.get("mappings", {})
                }
            )
        except Exception as e:
            logger.error("Failed to create index %s: %s", index_name, e)
            continue

    # Index PLM parts from SPLM folder
    if SPLM_FOLDER.exists():
        logger.info("Scanning SPLM folder: %s", SPLM_FOLDER)
        
        stp_files = list(SPLM_FOLDER.glob("*.stp"))
        unique_parts: dict[str, dict[str, Any]] = {}

        for stp_file in stp_files:
            info = parse_stp_filename(stp_file.name)
            if info:
                part_key = f"{info['part_number']}_{info['revision']}"
                if part_key not in unique_parts:
                    unique_parts[part_key] = {
                        "part_id": f"part_{info['part_number']}_{info['revision']}",
                        "part_number": info["part_number"],
                        "name": info["name"],
                        "revision": info["revision"],
                        "version": info["version"],
                        "type": "STEP",
                        "file_type": "stp",
                        "file_size": stp_file.stat().st_size,
                        "source_file": stp_file.name,
                        "application": "Siemens PLM",
                        "created_at": datetime.now(timezone.utc).isoformat(),
                        "description": f"STEP file: {info['name']}, Rev {info['revision']}",
                        "metadata": {
                            "date_extracted": info["date_str"],
                            "format": "AP242"
                        }
                    }

        # Bulk index parts
        if unique_parts and "plm_parts" in os_config:
            for part_id, doc in unique_parts.items():
                try:
                    client.index(index="plm_parts", id=doc["part_id"], body=doc)
                    docs_indexed += 1
                except Exception as e:
                    logger.error("Failed to index part %s: %s", part_id, e)

            client.indices.refresh(index="plm_parts")
            logger.info("Indexed %d parts to plm_parts", docs_indexed)

        # Index assemblies
        xml_files = list(SPLM_FOLDER.glob("*.xml"))
        assemblies: dict[str, dict[str, Any]] = {}

        for xml_file in xml_files:
            name_match = re.match(r"(\d+_[A-Z]_\d+)?-?(.+?)\s*\(", xml_file.name)
            if name_match:
                assembly_name = name_match.group(2) or xml_file.stem
            else:
                assembly_name = xml_file.stem

            asm_id = f"asm_{hash(assembly_name) % 100000:05d}"
            if asm_id not in assemblies:
                assemblies[asm_id] = {
                    "assembly_id": asm_id,
                    "name": assembly_name.replace("_", " "),
                    "description": f"PLM Assembly from {xml_file.name}",
                    "revision": "A",
                    "part_count": len(unique_parts),
                    "components": list(unique_parts.keys())[:20],
                    "source_file": xml_file.name,
                    "application": "Teamcenter",
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "metadata": {"format": "AP242 PLM XML"}
                }

        if assemblies and "plm_assemblies" in os_config:
            for asm_id, doc in assemblies.items():
                try:
                    client.index(index="plm_assemblies", id=doc["assembly_id"], body=doc)
                    docs_indexed += 1
                except Exception as e:
                    logger.error("Failed to index assembly %s: %s", asm_id, e)

            client.indices.refresh(index="plm_assemblies")
            logger.info("Indexed %d assemblies to plm_assemblies", len(assemblies))

    else:
        logger.warning("SPLM folder not found: %s", SPLM_FOLDER)

    return docs_indexed


def seed_neo4j_schema(fixtures: dict[str, Any], force: bool = False) -> int:
    """Seed Neo4j schema (constraints and indexes)."""
    neo4j_schema = fixtures.get("neo4j_schema", {})
    if not neo4j_schema:
        logger.info("No Neo4j schema defined in fixtures")
        return 0

    try:
        from neo4j import GraphDatabase
    except ImportError:
        logger.warning("neo4j driver not installed, skipping Neo4j seeding")
        return 0

    neo4j_uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    neo4j_user = os.getenv("NEO4J_USER", "neo4j")
    neo4j_password = os.getenv("NEO4J_PASSWORD", "")

    if not neo4j_password:
        logger.warning("NEO4J_PASSWORD not set, skipping Neo4j seeding")
        return 0

    try:
        driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))
        with driver.session() as session:
            # Verify connection
            session.run("RETURN 1")
            logger.info("Connected to Neo4j at %s", neo4j_uri)
    except Exception as e:
        logger.warning("Cannot connect to Neo4j at %s: %s", neo4j_uri, e)
        return 0

    created = 0

    try:
        with driver.session() as session:
            # Create constraints
            for constraint in neo4j_schema.get("constraints", []):
                try:
                    session.run(constraint)
                    logger.info("Created constraint: %s", constraint[:60])
                    created += 1
                except Exception as e:
                    if "already exists" in str(e).lower():
                        logger.debug("Constraint already exists: %s", constraint[:60])
                    else:
                        logger.error("Failed to create constraint: %s", e)

            # Create indexes
            for index in neo4j_schema.get("indexes", []):
                try:
                    session.run(index)
                    logger.info("Created index: %s", index[:60])
                    created += 1
                except Exception as e:
                    if "already exists" in str(e).lower():
                        logger.debug("Index already exists: %s", index[:60])
                    else:
                        logger.error("Failed to create index: %s", e)

            # Create sample nodes from workflows
            workflows = fixtures.get("workflows", [])
            for wf in workflows:
                if wf.get("target", {}).get("type") == "neo4j":
                    wf_config = wf.get("workflow_config", {})
                    nodes = wf_config.get("nodes", [])
                    edges = wf_config.get("edges", [])

                    # Create nodes
                    for node in nodes:
                        node_type = node.get("type", "Part")
                        try:
                            session.run(
                                f"MERGE (n:{node_type} {{id: $id}}) "
                                f"SET n.name = $name, n.label = $label, n.updated_at = datetime()",
                                id=node["id"],
                                name=node.get("label", node["id"]),
                                label=node.get("label", "")
                            )
                            created += 1
                        except Exception as e:
                            logger.error("Failed to create node %s: %s", node["id"], e)

                    # Create relationships
                    for edge in edges:
                        try:
                            rel_type = edge.get("label", "RELATES_TO").upper().replace(" ", "_")
                            session.run(
                                f"MATCH (a {{id: $source}}), (b {{id: $target}}) "
                                f"MERGE (a)-[r:{rel_type}]->(b) "
                                f"SET r.type = $edge_type",
                                source=edge["source"],
                                target=edge["target"],
                                edge_type=edge.get("type", "default")
                            )
                            created += 1
                        except Exception as e:
                            logger.error("Failed to create edge %s->%s: %s", edge["source"], edge["target"], e)

    finally:
        driver.close()

    logger.info("Created %d Neo4j schema elements and graph objects", created)
    return created


def seed_workflows(fixtures: dict[str, Any], force: bool = False) -> int:
    """Seed workflow instances via the workflow API."""
    workflows = fixtures.get("workflows", [])
    if not workflows:
        logger.info("No workflows defined in fixtures")
        return 0

    # Import DB session and models
    try:
        from core.db_session import SessionLocal, init_db
        from models.workflow_models import WorkflowInstance, WorkflowStatus, WorkflowStage
    except ImportError as e:
        logger.error("Cannot import workflow models: %s", e)
        return 0

    init_db()
    db = SessionLocal()
    created = 0

    try:
        for wf_data in workflows:
            wf_name = wf_data.get("name", "")
            
            # Check if workflow already exists
            existing = db.query(WorkflowInstance).filter(WorkflowInstance.name == wf_name).first()
            if existing and not force:
                logger.info("Workflow '%s' already exists, skipping", wf_name)
                continue
            elif existing and force:
                logger.info("Deleting existing workflow '%s'", wf_name)
                db.delete(existing)
                db.commit()

            # Create workflow instance
            import uuid
            workflow_id = f"wf_seed_{uuid.uuid4().hex[:8]}"
            
            source = wf_data.get("source", {})
            target = wf_data.get("target", {})
            
            workflow = WorkflowInstance(
                id=workflow_id,
                name=wf_name,
                description=wf_data.get("description", ""),
                source_id=source.get("id", ""),
                source_name=source.get("name", ""),
                source_type=source.get("type", ""),
                source_config={
                    "connection_details": source.get("connection_details", {}),
                    "extraction_config": source.get("extraction_config", {})
                },
                target_id=target.get("id", ""),
                target_name=target.get("name", ""),
                target_type=target.get("type", ""),
                target_config={
                    "connection_details": target.get("connection_details", {}),
                    "load_config": target.get("load_config", {})
                },
                workflow_config=wf_data.get("workflow_config", {"nodes": [], "edges": [], "ai_agents": []}),
                ai_agents_enabled=wf_data.get("ai_agents_enabled", []),
                status=WorkflowStatus.CONFIGURED,
                current_stage=WorkflowStage.IDLE,
                progress_percentage=0.0,
                created_by=wf_data.get("created_by", "seed_script"),
                schedule_enabled=wf_data.get("schedule_enabled", False),
                execution_metadata=wf_data.get("metadata", {})
            )
            
            db.add(workflow)
            db.commit()
            logger.info("Created workflow: %s (%s)", wf_name, workflow_id)
            created += 1

    except Exception as e:
        logger.error("Failed to seed workflows: %s", e)
        db.rollback()
    finally:
        db.close()

    return created


def main(argv: Optional[list[str]] = None) -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Seed unstructured data workflows")
    parser.add_argument("--force", action="store_true", help="Force re-creation of existing data")
    parser.add_argument("--workflows-only", action="store_true", help="Only seed workflow instances")
    parser.add_argument("--opensearch-only", action="store_true", help="Only seed OpenSearch indices")
    parser.add_argument("--neo4j-only", action="store_true", help="Only seed Neo4j schema")
    args = parser.parse_args(argv)

    logger.info("=" * 60)
    logger.info("Seeding Unstructured Data Workflows")
    logger.info("=" * 60)

    fixtures = load_fixtures()
    total = 0

    do_all = not (args.workflows_only or args.opensearch_only or args.neo4j_only)

    if do_all or args.workflows_only:
        logger.info("\n--- Seeding Workflow Instances ---")
        total += seed_workflows(fixtures, force=args.force)

    if do_all or args.opensearch_only:
        logger.info("\n--- Seeding OpenSearch Indices ---")
        total += seed_opensearch_indices(fixtures, force=args.force)

    if do_all or args.neo4j_only:
        logger.info("\n--- Seeding Neo4j Schema ---")
        total += seed_neo4j_schema(fixtures, force=args.force)

    logger.info("\n" + "=" * 60)
    logger.info("Seeding Complete! Total objects created: %d", total)
    logger.info("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())
