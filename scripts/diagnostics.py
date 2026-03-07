import os
import sys
import subprocess
import logging

def check_command(cmd, name):
    try:
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        print(f"[OK] {name} is installed.")
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        print(f"[FAIL] {name} is missing or not in PATH!")
        return False

def check_env_vars():
    env_file = "python_backend/.env"
    print(f"\\n--- Checking Environment Configuration ({env_file}) ---")
    if not os.path.exists(env_file):
        print(f"[WARN] {env_file} does not exist. Creating default from template...")
        with open(env_file, "w") as f:
            f.write("DATABASE_URL=postgresql://postgres:yourpassword@127.0.0.1:5432/graphtrace\\n")
            f.write("NEO4J_URI=bolt://localhost:7687\\n")
            f.write("OPENSEARCH_URL=http://localhost:9200\\n")
    
    with open(env_file, "r") as f:
        content = f.read()

    # Auto-generate encryption key if completely missing #
    if "GRAPH_TRACE_CONFIG_ENCRYPTION_KEY=" not in content:
        try:
            from cryptography.fernet import Fernet
            key = Fernet.generate_key().decode()
            with open(env_file, "a") as f:
                f.write(f"\\nGRAPH_TRACE_CONFIG_ENCRYPTION_KEY={key}\\n")
            print("[AUTO-FIX] Generated and injected GRAPH_TRACE_CONFIG_ENCRYPTION_KEY")
            content += f"\\nGRAPH_TRACE_CONFIG_ENCRYPTION_KEY={key}\\n"
        except ImportError:
            print("[WARN] python cryptography library missing. Cannot auto-generate Encryption Key.")

    required_keys = [
        "DATABASE_URL",
        "GRAPH_TRACE_CONFIG_ENCRYPTION_KEY",
        "NEO4J_URI"
    ]
    
    all_good = True
    for key in required_keys:
        if f"{key}=" in content and not f"{key}=your" in content.lower() and not f"{key}=\\n" in content:
            print(f"[OK] {key} is configured.")
        else:
            print(f"[WARN] {key} is missing or using a default placeholder (like \"yourpassword\")!")
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

