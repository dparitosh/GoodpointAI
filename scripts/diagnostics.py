import os
import sys
import subprocess
from typing import Dict


def _repo_root() -> str:
    """Resolve repository root based on this file location."""

    return os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def _backend_dir() -> str:
    return os.path.join(_repo_root(), "python_backend")


def _backend_env_paths() -> tuple[str, str]:
    root = _repo_root()
    env_file = os.path.join(root, "python_backend", ".env")
    env_example = os.path.join(root, "python_backend", ".env.example")
    return env_file, env_example


def _parse_dotenv(text: str) -> Dict[str, str]:
    """Very small .env parser fallback (used only if python-dotenv is missing)."""
    out: Dict[str, str] = {}
    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        k, v = line.split("=", 1)
        k = k.strip()
        v = v.strip().strip('"').strip("'")
        if k:
            out[k] = v
    return out


def _load_env_file(env_file: str) -> None:
    """Load python_backend/.env into the current process environment."""
    if not os.path.exists(env_file):
        return

    # Prefer python-dotenv when available.
    try:
        from dotenv import load_dotenv  # type: ignore
    except ImportError:
        load_dotenv = None  # type: ignore

    if load_dotenv is not None:
        # If python-dotenv exists, use it.
        load_dotenv(dotenv_path=env_file, override=False)
        return

    # Fallback: minimal parser.
    with open(env_file, "r", encoding="utf-8") as f:
        env_map = _parse_dotenv(f.read())
    for k, v in env_map.items():
        os.environ.setdefault(k, v)

def check_command(cmd, name):
    try:
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True, shell=(os.name == "nt"))
        print(f"[OK] {name} is installed.")
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        print(f"[FAIL] {name} is missing or not in PATH!")
        return False

def check_env_vars():
    env_file, env_example = _backend_env_paths()
    print(f"\n--- Checking Environment Configuration ({env_file}) ---")
    if not os.path.exists(env_file):
        if os.path.exists(env_example):
            print(f"[WARN] {env_file} does not exist. Copying from {env_example}...")
            os.makedirs(os.path.dirname(env_file), exist_ok=True)
            with open(env_example, "r", encoding="utf-8") as src, open(env_file, "w", encoding="utf-8") as dst:
                dst.write(src.read())
        else:
            print(f"[WARN] {env_file} does not exist and no .env.example found. Creating a minimal template...")
            os.makedirs(os.path.dirname(env_file), exist_ok=True)
            with open(env_file, "w", encoding="utf-8") as f:
                # Template only — user must edit. Standard PostgreSQL port is 5432.
                f.write("DATABASE_URL=postgresql://postgres:yourpassword@127.0.0.1:5432/graphtrace\n")
                f.write("# NEO4J_URI=bolt://localhost:7687\n")
                f.write("# OPENSEARCH_URL=http://localhost:9200\n")

    # Ensure backend-style dotenv loading is enabled for local dev.
    os.environ.setdefault("GRAPH_TRACE_LOAD_DOTENV", "true")
    _load_env_file(env_file)

    with open(env_file, "r", encoding="utf-8") as f:
        content = f.read()

    # Auto-generate encryption key if completely missing #
    if "GRAPH_TRACE_CONFIG_ENCRYPTION_KEY=" not in content:
        try:
            from cryptography.fernet import Fernet
            key = Fernet.generate_key().decode()
            with open(env_file, "a", encoding="utf-8") as f:
                f.write(f"\\nGRAPH_TRACE_CONFIG_ENCRYPTION_KEY={key}\\n")
            print("[AUTO-FIX] Generated and injected GRAPH_TRACE_CONFIG_ENCRYPTION_KEY")
            content += f"\\nGRAPH_TRACE_CONFIG_ENCRYPTION_KEY={key}\\n"
        except ImportError:
            print("[WARN] python cryptography library missing. Cannot auto-generate Encryption Key.")

    # Required for a functional backend.
    required_keys = ["DATABASE_URL", "GRAPH_TRACE_CONFIG_ENCRYPTION_KEY"]

    # Optional integrations.
    optional_keys = ["NEO4J_URI", "OPENSEARCH_URL"]
    
    all_good = True
    # Validate from the environment (loaded from python_backend/.env), not via string matching.
    for key in required_keys:
        val = (os.getenv(key) or "").strip()
        if not val:
            print(f"[WARN] {key} is missing!")
            all_good = False
            continue

        if key == "DATABASE_URL" and ("yourpassword" in val.lower() or ":password@" in val.lower()):
            print(f"[WARN] {key} is using placeholder credentials (edit python_backend/.env)!")
            all_good = False
            continue

        print(f"[OK] {key} is configured.")

    for key in optional_keys:
        if f"{key}=" in content and not f"{key}=\n" in content:
            print(f"[OK] {key} is set (optional).")
        else:
            print(f"[INFO] {key} is not set (optional).")

    # DB connectivity check (required unless explicitly skipped).
    if (os.getenv("GRAPH_TRACE_SKIP_DB_CHECK") or "").strip().lower() in {"1", "true", "yes"}:
        print("[INFO] Skipping DB connectivity check (GRAPH_TRACE_SKIP_DB_CHECK=true).")
        return all_good

    try:
        # Make python_backend importable.
        backend_dir = _backend_dir()
        if backend_dir not in sys.path:
            sys.path.insert(0, backend_dir)

        from core.db_session import redacted_database_url, verify_database_connectivity  # type: ignore

        print(f"[INFO] DB URL (redacted): {redacted_database_url()}")
        err = verify_database_connectivity(timeout_s=5.0)
        if err is None:
            print("[OK] Postgres connectivity check passed.")
        else:
            print(f"[FAIL] Postgres connectivity check failed: {err}")
            all_good = False
    except Exception as exc:  # pylint: disable=broad-exception-caught
        print(f"[FAIL] Postgres connectivity check could not be performed: {type(exc).__name__}: {exc}")
        all_good = False
            
    return all_good

def main():
    print("====================================")
    print("   GraphTrace Health & Diagnostics  ")
    print("====================================")
    
    sys_ok = all([
        check_command(["python", "--version"], "Python"),
        check_command(["node", "--version"], "Node.js"),
        check_command(["npm", "--version"], "NPM")
    ])
    
    env_ok = check_env_vars()
    
    print("\\n====================================")
    if sys_ok and env_ok:
        print("Diagnostics Passed! You are ready to run.")
        sys.exit(0)
    else:
        print("Diagnostics Failed! Please fix the warnings above.")
        sys.exit(1)

if __name__ == "__main__":
    main()

