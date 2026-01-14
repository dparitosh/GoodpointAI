"""Install GraphTrace seeded schema (portable).

Goal: provide a single, deployment-friendly entrypoint for initializing the
Postgres schema and seeding the minimum required data for the UI to work.

This intentionally avoids optional integrations (OpenSearch indices, Neo4j schema)
unless explicitly requested.

Usage:
  python -m scripts.install_seeded_schema
  python -m scripts.install_seeded_schema --with-unstructured-workflows
  python -m scripts.install_seeded_schema --force

Exit codes:
  0 success
  2 refused / safety check failed
  3 partial failure (optional step)
  5 required step failed
"""

from __future__ import annotations

import argparse
import os
import sys
import logging

logger = logging.getLogger(__name__)


def _is_production() -> bool:
    env = (os.getenv("ENVIRONMENT") or os.getenv("GRAPH_TRACE_ENVIRONMENT") or "").strip().lower()
    return env in {"prod", "production"}


def _run_required(step_name: str, fn) -> None:
    logger.info("[%s] start", step_name)
    fn()
    logger.info("[%s] ok", step_name)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Install GraphTrace DB schema and seed required defaults")
    parser.add_argument("--force", action="store_true", help="Overwrite existing seeded records where supported")
    parser.add_argument(
        "--with-unstructured-workflows",
        action="store_true",
        help="Also seed sample workflows (and optionally OpenSearch/Neo4j via flags)",
    )
    parser.add_argument(
        "--with-opensearch",
        action="store_true",
        help="When used with --with-unstructured-workflows, also attempt OpenSearch index creation",
    )
    parser.add_argument(
        "--with-neo4j",
        action="store_true",
        help="When used with --with-unstructured-workflows, also attempt Neo4j schema seeding",
    )

    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO)

    # Required: schema + DB-backed config + admin config + pipeline config.
    try:
        from core.crypto import decrypt_json
        from core.db_session import SessionLocal, init_db
        from models.configuration_models import EncryptedConfig

        from scripts.seed_db_config import seed_defaults
        from scripts.seed_admin_configs import main as seed_admin_main
        from scripts.seed_pipeline_configs import seed_all as seed_pipeline_all
    except Exception as exc:  # pylint: disable=broad-exception-caught
        logger.error("Failed to import seeding modules: %s", exc)
        return 5

    try:
        # 1) Schema
        def _schema() -> None:
            init_db()

        _run_required("schema", _schema)

        # 2) Validate existing encrypted config can be decrypted (if present)
        # In production we fail-fast (deployment must provide a stable key).
        def _validate_encryption() -> None:
            db = SessionLocal()
            try:
                row = db.get(EncryptedConfig, "system_configuration")
                if row is None:
                    return
                try:
                    decrypt_json(row.ciphertext)
                except Exception as exc:  # pylint: disable=broad-exception-caught
                    if _is_production():
                        raise RuntimeError(
                            "EncryptedConfig rows exist but cannot be decrypted with the current key. "
                            "Set GRAPH_TRACE_CONFIG_ENCRYPTION_KEY to the original deployment key, "
                            "or explicitly reset encrypted config before re-seeding."
                        ) from exc
                    logger.warning(
                        "Encrypted config cannot be decrypted with current key (dev mode): %s",
                        type(exc).__name__,
                    )
            finally:
                db.close()

        _run_required("encryption_check", _validate_encryption)

        # 3) Seed DB-backed config keys (EncryptedConfig)
        def _seed_db_backed_config() -> None:
            seeded = seed_defaults(force=bool(args.force))
            logger.info("Seeded encrypted config keys: %s", ", ".join(seeded) if seeded else "(none)")

        _run_required("db_config_seed", _seed_db_backed_config)

        # 4) Admin config (LLM providers, embeddings, feature flags, system configs)
        _run_required("admin_seed", seed_admin_main)

        # 5) Pipeline config (file patterns, templates, search/index configs)
        def _seed_pipelines() -> None:
            # seed_all supports a force flag.
            seed_pipeline_all(force=bool(args.force))

        _run_required("pipeline_seed", _seed_pipelines)

    except Exception as exc:  # pylint: disable=broad-exception-caught
        logger.error("Required install step failed: %s", exc)
        return 5

    # Optional: sample workflows and/or integration seeds.
    if args.with_unstructured_workflows:
        try:
            from scripts.seed_unstructured_workflows import main as seed_workflows_main

            workflow_args: list[str] = []
            if args.force:
                workflow_args.append("--force")

            # Default for deployments: workflows only (avoid external deps/timeouts)
            if args.with_opensearch and not args.with_neo4j:
                workflow_args.append("--opensearch-only")
            elif args.with_neo4j and not args.with_opensearch:
                workflow_args.append("--neo4j-only")
            elif not args.with_opensearch and not args.with_neo4j:
                workflow_args.append("--workflows-only")

            logger.info("[workflows] start (%s)", " ".join(workflow_args) if workflow_args else "all")
            rc = int(seed_workflows_main(workflow_args))
            if rc != 0:
                logger.warning("[workflows] completed with rc=%s", rc)
                return 3
            logger.info("[workflows] ok")
        except Exception as exc:  # pylint: disable=broad-exception-caught
            logger.warning("Optional workflow seeding failed: %s", exc)
            return 3

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
