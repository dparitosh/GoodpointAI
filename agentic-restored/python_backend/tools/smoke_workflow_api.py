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
    parser = argparse.ArgumentParser(description="Smoke test /api/workflows execution lifecycle")
    parser.add_argument("--base", default="http://localhost:8011", help="FastAPI base URL")
    parser.add_argument("--sleep", type=float, default=0.4, help="Seconds to sleep between actions")
    args = parser.parse_args()

    base = args.base.rstrip("/")

    try:
        workflows = _json_get(f"{base}/api/workflows/?skip=0&limit=3")
        if not workflows:
            print("No workflows returned from /api/workflows")
            return 2

        workflow_id = workflows[0].get("id")
        if not workflow_id:
            print("First workflow missing id field")
            return 2

        print("workflow_id", workflow_id)

        def get_wf():
            return _json_get(f"{base}/api/workflows/{workflow_id}")

        def do(action: str):
            payload = {
                "action": action,
                "execution_params": {"strategy": "incremental"} if action == "start" else {},
            }
            return _json_post(f"{base}/api/workflows/{workflow_id}/execute", payload)

        print("start_resp", do("start"))
        time.sleep(args.sleep)
        wf = get_wf()
        print("after_start", wf.get("status"), wf.get("current_stage"), wf.get("progress_percentage"))

        print("pause_resp", do("pause"))
        time.sleep(args.sleep)
        wf = get_wf()
        print("after_pause", wf.get("status"), wf.get("current_stage"), wf.get("progress_percentage"))

        print("resume_resp", do("resume"))
        time.sleep(args.sleep)
        wf = get_wf()
        print("after_resume", wf.get("status"), wf.get("current_stage"), wf.get("progress_percentage"))

        print("cancel_resp", do("cancel"))
        time.sleep(args.sleep)
        wf = get_wf()
        print("after_cancel", wf.get("status"), wf.get("current_stage"), wf.get("progress_percentage"))

        return 0

    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8")
        except (OSError, UnicodeDecodeError):
            body = "<unreadable>"
        print(f"HTTPError {e.code}: {e.reason} body={body}")
        return 1
    except urllib.error.URLError as e:
        print(f"URLError: {e}")
        return 1
    except (json.JSONDecodeError, OSError, TypeError, ValueError, KeyError) as e:
        print(f"Error: {e}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
