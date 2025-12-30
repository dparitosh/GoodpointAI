from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from core.crypto import encrypt_json
from core.db_session import SessionLocal, init_db
from models.configuration_models import EncryptedConfig

logger = logging.getLogger(__name__)


def _load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _upsert_encrypted(db, *, key: str, payload: Dict[str, Any]) -> None:
    row = db.get(EncryptedConfig, key)
    if row is None:
        row = EncryptedConfig(key=key, ciphertext=encrypt_json(payload))
        db.add(row)
    else:
        row.ciphertext = encrypt_json(payload)


def seed_defaults(
    *,
    system_config: Optional[Union[str, Path]] = None,
    force: bool = False,
) -> List[str]:
    """Seed DB-backed configuration keys if missing.

    Returns a list of keys that were written.
    """

    init_db()

    system_path = Path(system_config) if system_config else (Path(__file__).resolve().parents[2] / "config" / "system_configuration.json")
    if not system_path.exists():
        raise FileNotFoundError(f"System config file not found: {system_path}")

    system_cfg = _load_json(system_path)
    neo4j_ports = (system_cfg.get("databases") or {}).get("neo4j") or {}
    opensearch_ports = (system_cfg.get("databases") or {}).get("opensearch") or {}
    cors_cfg = system_cfg.get("cors") or {}

    neo4j_bolt_port = int(neo4j_ports.get("bolt_port") or 7687)
    opensearch_port = int(opensearch_ports.get("port") or 9200)

    # Default, install-friendly values. Passwords remain empty until user sets them via UI.
    neo4j_payload = {
        "uri": f"neo4j://127.0.0.1:{neo4j_bolt_port}",
        "username": "neo4j",
        "password": "",
        "database": "neo4j",
    }
    opensearch_payload = {
        "url": f"http://127.0.0.1:{opensearch_port}",
        "username": None,
        "password": "",
        "verify_certs": True,
        "timeout_s": 5.0,
    }

    workflow_defaults_payload = {
        "source_endpoint_placeholder": "https://<host>/api",
        "source_endpoints": {
            "teamcenter": "",
            "windchill": "",
            "catia": "",
            "nx": "",
            "creo": "",
        },
        "target_endpoints": {
            "cloud_plm": "",
            "opensearch": "",
        },
    }

    written: List[str] = []
    db = SessionLocal()
    try:
        def should_write(key: str) -> bool:
            return force or (db.get(EncryptedConfig, key) is None)

        if should_write("system_configuration"):
            _upsert_encrypted(db, key="system_configuration", payload=system_cfg)
            written.append("system_configuration")

        if should_write("neo4j"):
            _upsert_encrypted(db, key="neo4j", payload=neo4j_payload)
            written.append("neo4j")

        if should_write("opensearch"):
            _upsert_encrypted(db, key="opensearch", payload=opensearch_payload)
            written.append("opensearch")

        if cors_cfg and should_write("cors"):
            _upsert_encrypted(db, key="cors", payload=cors_cfg)
            written.append("cors")

        if should_write("workflow_defaults"):
            _upsert_encrypted(db, key="workflow_defaults", payload=workflow_defaults_payload)
            written.append("workflow_defaults")

        if written:
            db.commit()
    finally:
        db.close()

    for key in written:
        logger.info("Seeded %s", key)
    return written


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Seed DB-backed configuration for GraphTrace")
    parser.add_argument(
        "--system-config",
        default=str(Path(__file__).resolve().parents[2] / "config" / "system_configuration.json"),
        help="Path to system_configuration.json",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing keys (otherwise only fill missing keys)",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO)
    seed_defaults(system_config=args.system_config, force=bool(args.force))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
