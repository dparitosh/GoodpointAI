import argparse
import json
import time
import urllib.error
import urllib.request


def _json_get(url: str):
    with urllib.request.urlopen(url) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _json_post(url: str, payload: dict):
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify lineage auto-capture by running a workflow and querying /api/lineage"
    )
    parser.add_argument("--base", default="http://localhost:8000", help="FastAPI base URL")
    parser.add_argument(
        "--workflow-id",
        default=None,
        help="Workflow id to execute. If omitted, uses first from /api/workflows.",
    )
    parser.add_argument("--sleep", type=float, default=0.6, help="Seconds to sleep between actions")
    parser.add_argument(
        "--max-wait",
        type=float,
        default=6.0,
        help="Max seconds to wait for migration_session_id to appear",
    )
    args = parser.parse_args()

    base = args.base.rstrip("/")

    def http_error_detail(e: urllib.error.HTTPError) -> str:
        body = ""
        try:
            body = e.read().decode("utf-8")
        except (OSError, UnicodeDecodeError):
            body = "<unreadable>"
        return f"HTTPError {e.code}: {e.reason} body={body}"

    try:
        workflow_id = args.workflow_id
        if not workflow_id:
            workflows = _json_get(f"{base}/api/workflows/?skip=0&limit=1")
            if not workflows:
                print("No workflows returned from /api/workflows")
                return 2
            workflow_id = workflows[0].get("id")

        if not workflow_id:
            print("workflow_id not provided and not found")
            return 2

        print("workflow_id", workflow_id)

        def get_wf():
            return _json_get(f"{base}/api/workflows/{workflow_id}")

        def execute(action: str):
            payload = {
                "action": action,
                "execution_params": {"strategy": "incremental"} if action == "start" else {},
            }
            return _json_post(f"{base}/api/workflows/{workflow_id}/execute", payload)

        try:
            print("start_resp", execute("start"))
        except urllib.error.HTTPError as e:
            # If workflow is already running, that's fine for lineage verification.
            if e.code == 400:
                print("start_resp", "skipped (already running)")
            else:
                raise
        time.sleep(args.sleep)

        migration_session_id = None
        deadline = time.time() + max(0.1, float(args.max_wait))
        while time.time() < deadline:
            wf = get_wf()
            meta = wf.get("execution_metadata") or {}
            migration_session_id = meta.get("migration_session_id")
            if migration_session_id:
                break
            time.sleep(0.2)

        if not migration_session_id:
            print("No migration_session_id found in workflow.execution_metadata")
            return 2

        mig_node_id = f"mig:{migration_session_id}"
        print("migration_session_id", migration_session_id)
        print("mig_node_id", mig_node_id)

        # 1) Fetch workflow graph (fast check that nodes exist for this workflow)
        try:
            graph = _json_get(f"{base}/api/lineage/workflows/{workflow_id}/lineage-graph")
        except urllib.error.HTTPError as e:
            # If Neo4j isn't configured/up, dependency returns 503.
            if e.code == 503:
                print("SKIP: Neo4j not available (503 from lineage endpoints)")
                return 0
            print(http_error_detail(e))
            return 1

        nodes = graph.get("nodes") or []
        rels = graph.get("relationships") or []

        has_mig_node = any((n.get("id") == mig_node_id) for n in nodes if isinstance(n, dict))
        print("lineage_graph_nodes", len(nodes))
        print("lineage_graph_relationships", len(rels))
        print("lineage_graph_has_mig_node", bool(has_mig_node))

        # 2) Trace from migration node (should return some nodes/relationships)
        try:
            trace = _json_post(
                f"{base}/api/lineage/trace",
                {"record_id": mig_node_id, "direction": "both", "max_depth": 3},
            )
        except urllib.error.HTTPError as e:
            if e.code == 503:
                print("SKIP: Neo4j not available (503 from lineage endpoints)")
                return 0
            print(http_error_detail(e))
            return 1

        trace_nodes = trace.get("nodes") or {}
        trace_relationships = trace.get("relationships") or []

        print("trace_nodes", len(trace_nodes))
        print("trace_relationships", len(trace_relationships))

        if not has_mig_node:
            print("FAIL: migration node missing from workflow lineage graph")
            return 3
        if len(trace_nodes) < 1:
            print("FAIL: trace returned no nodes")
            return 3

        print("OK: lineage auto-capture verified")
        return 0

    except urllib.error.HTTPError as e:
        print(http_error_detail(e))
        return 1
    except urllib.error.URLError as e:
        print(f"URLError: {e}")
        return 1
    except (json.JSONDecodeError, OSError, TypeError, ValueError, KeyError) as e:
        print(f"Error: {e}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
