from __future__ import annotations

import io
import json
import logging
import sys
from pathlib import Path

# PowerShell 5 / cp1252 compatibility
if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "buffer"):
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.crypto import decrypt_json
from core.db_session import SessionLocal, redacted_database_url, verify_database_connectivity


logger = logging.getLogger(__name__)


def _print_db_recovery(err: str) -> None:
    err_lower = err.lower()
    print()
    if "password" in err_lower or "authentication" in err_lower or "auth" in err_lower:
        print("  Cause: Database authentication failed. Wrong username or password.")
        print("  Fix:   Check DATABASE_URL in python_backend/.env.")
        print("         Example: postgresql+psycopg://postgres:yourpassword@127.0.0.1:5432/graphtrace")
    elif "connection refused" in err_lower or "could not connect" in err_lower:
        print("  Cause: PostgreSQL is not running or is not listening on the configured port.")
        print("  Fix:   Start PostgreSQL, then verify the host/port in DATABASE_URL.")
        print("         Check with: pg_isready -h 127.0.0.1 -p 5432")
        print("         Or with Docker: docker ps | findstr postgres")
    elif "does not exist" in err_lower or "database" in err_lower:
        print("  Cause: The target database does not exist in PostgreSQL.")
        print("  Fix:   Create it: createdb -U postgres graphtrace")
        print("         Then seed schema: python -m scripts.init_db_schema")
    elif "timeout" in err_lower:
        print("  Cause: PostgreSQL connection timed out. Host may be unreachable.")
        print("  Fix:   Verify the host/port in DATABASE_URL and check firewall rules.")
    else:
        print("  Fix:   Check DATABASE_URL in python_backend/.env.")
        print("         Then run: python -m scripts.init_db_schema")
    print()


def main() -> int:
    logging.basicConfig(level=logging.WARNING)  # suppress INFO noise; we print manually

    url_redacted = redacted_database_url()
    print(f"DATABASE_URL (redacted): {url_redacted}")

    err = verify_database_connectivity(timeout_s=5.0)
    if err is not None:
        print(f"[FAIL] DB connectivity: {err}")
        _print_db_recovery(err)
        return 2

    print("[OK]  DB connectivity: OK")

    # Basic table/config checks (do not print secrets)
    from models.configuration_models import EncryptedConfig  # ensure model import

    db = SessionLocal()
    try:
        keys = [r.key for r in db.query(EncryptedConfig).all()]
        if keys:
            print(f"[OK]  EncryptedConfig keys present: {', '.join(sorted(keys))}")
        else:
            print("[WARN] EncryptedConfig table is empty. Run: python -m scripts.init_db_schema")

        decrypt_failures = 0
        for key in ("system_configuration", "cors", "workflow_defaults"):
            row = db.get(EncryptedConfig, key)
            if row is None:
                print(f"[WARN] Missing config key: {key}")
                print("       Fix: python -m scripts.init_db_schema  (seeds default values)")
                continue
            try:
                payload = decrypt_json(row.ciphertext)
                print(f"[OK]  Decrypt OK: {key} (type={type(payload).__name__})")
            except Exception as exc:
                print(f"[FAIL] Decrypt FAIL: {key}: {exc}")
                print("  Cause: GRAPH_TRACE_CONFIG_ENCRYPTION_KEY does not match the key used")
                print("         when this config value was originally encrypted.")
                print("  Fix 1: Restore the original encryption key in python_backend/.env.")
                print("  Fix 2: If the key is lost, reset encrypted config:")
                print("           Set GRAPH_TRACE_ALLOW_RESET_ENCRYPTED_CONFIG=true in .env")
                print("           Then run: python -m scripts.init_db_schema")
                decrypt_failures += 1

        if decrypt_failures:
            return 3

        # Neo4j/OpenSearch exist check (do not decrypt/print secrets)
        for key in ("neo4j", "opensearch"):
            row = db.get(EncryptedConfig, key)
            status = "[OK]  " if row else "[INFO]"
            present = "present" if row else "not set (optional)"
            print(f"{status} {key} config: {present}")

    finally:
        db.close()

    # Emit a compact JSON summary for tools.
    print(
        json.dumps(
            {
                "db_ok": True,
                "database_url_redacted": url_redacted,
            },
            indent=2,
        )
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

