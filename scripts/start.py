import subprocess
import sys
import os
import threading
import queue
import time

# Enforce environment context
os.environ["GRAPH_TRACE_LOAD_DOTENV"] = "true"
os.environ["PYTHONPATH"] = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
backend_dir = os.path.join(os.environ["PYTHONPATH"], "python_backend")
os.environ["PYTHONPATH"] += os.pathsep + backend_dir

print("\\033[96m[System] Bootstrapping GraphTrace Database/Schema...\\033[0m")
try:
    # Run the init_db_schema securely before bootstrapping
    subprocess.run([sys.executable, "-m", "scripts.init_db_schema"], cwd=backend_dir, check=True)
    print("\\033[92m[System] Database OK! Schema and Settings seeded.\\033[0m")
except subprocess.CalledProcessError as e:
    print(f"\\033[93m[System] WARNING: Database Sync Issue (Is Postgres Running?) -> {e}\\033[0m")
    print("\\033[93m[System] We will attempt to continue, but backend features may crash.\\033[0m")

agents = [
    "chat_coordinator", "data_analyst", "data_discovery",
    "etl_orchestrator", "quality_monitor", "query_planner", 
    "visualization_agent", "task_decomposer"
]

processes_to_start = [
    {"name": "Frontend", "cmd": "npm run dev", "cwd": "e2etraceapp", "color": "\\033[96m"},
    {"name": "Backend", "cmd": f"{sys.executable} -m uvicorn main:app --port 8011", "cwd": "python_backend", "color": "\\033[92m"},
    {"name": "MCP_Srv", "cmd": f"{sys.executable} -m uvicorn mcp_server.main:app --port 8012", "cwd": ".", "color": "\\033[95m"}
]

for idx, agent in enumerate(agents):
    processes_to_start.append({
        "name": f"A:{agent[:4]}",
        "cmd": f"{sys.executable} -m agent_services.{agent}.main",
        "cwd": ".",
        "color": f"\\033[38;5;{214 + (idx % 15)}m"
    })

processes = []
running = True

def enqueue_output(out, queue_obj, prefix, color):
    for line in iter(out.readline, ""):
        if not running: break
        val = line.strip()
        if val: queue_obj.put(f"{color}[{prefix}]\\033[0m {val}")
    out.close()

def main():
    global running
    print(f"\\n\\033[92m[System] Launching Multiplexer ({len(processes_to_start)} microservices)...\\033[0m")
    
    q = queue.Queue()
    for p_info in processes_to_start:
        p = subprocess.Popen(
            p_info["cmd"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            cwd=p_info["cwd"], env=os.environ, shell=True, text=True, bufsize=1
        )
        processes.append((p_info["name"], p))
        t = threading.Thread(target=enqueue_output, args=(p.stdout, q, p_info["name"], p_info["color"]), daemon=True)
        t.start()
        time.sleep(0.3)

    print("\\033[93m[System] Stack Live! Press Ctrl+C to abort all services.\\033[0m\\n")
    try:
        while running:
            try:
                print(q.get(timeout=0.1))
            except queue.Empty:
                pass
    except KeyboardInterrupt:
        print("\\n\\033[91m[System] Interrupt received. Terminating cluster...\\033[0m")
        running = False
        for name, p in processes:
            p.terminate()
        print("\\033[92m[System] Offline.\\033[0m")

if __name__ == "__main__":
    main()

