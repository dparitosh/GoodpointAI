"""Soda scan smoke script (HTTP).

Prereq:
- Backend running
- Postgres table `public.soda_test_table` exists (see `tools/smoke_create_soda_table.py`)
"""

import json
import os
import urllib.request


def main() -> None:
    base_url = (os.getenv("GRAPH_TRACE_BASE_URL") or "http://localhost:8011").rstrip("/")
    url = f"{base_url}/api/analytics/quality/soda/scan/public.soda_test_table"

    payload = {
        "checks_yaml": "- row_count > 0\n- missing_count(id) = 0\n",
        "data_source_name": "postgres",
    }

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=15) as resp:
        body = resp.read().decode("utf-8", errors="replace")
        print(body)


if __name__ == "__main__":
    main()
