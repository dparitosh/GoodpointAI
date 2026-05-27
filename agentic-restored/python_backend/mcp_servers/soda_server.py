"""MCP Soda Server (stdio).

This MCP server exposes *data quality* tools backed by the existing FastAPI backend.
It intentionally does not import Soda Core directly; instead it calls the backend
HTTP endpoints which already implement:
- internal Soda (when available)
- external Soda runner fallback (Python 3.11 venv) configured via Admin Connection Settings

Run (example):
  python -m python_backend.mcp_servers.soda_server

Environment:
- GOODPOINT_BACKEND_URL: base URL of the backend (default http://127.0.0.1:8011)

Tools (requested):
- run_soda_scan: executes checks YAML against a table
- get_scan_results: fetches the latest persisted scan report(s) for a table
- analyze_anomaly: lightweight anomaly/trend analysis over recent reports

Additional tool (supports OpenSearch-native anomaly detection workflows):
- check_opensearch_ad_results: queries an OpenSearch AD *custom result index* and persists a DQ-style report

Note on "Soda AI anomaly detection": Soda Cloud has advanced anomaly detection.
This repo currently implements a deterministic heuristic analysis using historical
scan reports stored by the backend (no Soda Cloud dependency).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional


def _backend_base_url() -> str:
    return (
        (os.getenv("GOODPOINT_BACKEND_URL") or "").strip()
        or (os.getenv("BACKEND_URL") or "").strip()
        or "http://127.0.0.1:8011"
    )


def _http_get_json(url: str) -> Any:
    # Prefer httpx; fall back to urllib to keep this server dependency-light.
    try:
        import httpx

        with httpx.Client(timeout=30.0) as client:
            r = client.get(url)
            r.raise_for_status()
            return r.json()
    except ModuleNotFoundError:
        from urllib.request import urlopen  # pylint: disable=import-outside-toplevel
        import json  # pylint: disable=import-outside-toplevel

        with urlopen(url, timeout=30.0) as resp:  # noqa: S310
            return json.loads(resp.read().decode("utf-8"))


def _http_post_json(url: str, payload: dict) -> Any:
    try:
        import httpx

        with httpx.Client(timeout=120.0) as client:
            r = client.post(url, json=payload)
            r.raise_for_status()
            return r.json()
    except ModuleNotFoundError:
        from urllib.request import Request, urlopen  # pylint: disable=import-outside-toplevel
        import json  # pylint: disable=import-outside-toplevel

        data = json.dumps(payload).encode("utf-8")
        req = Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
        with urlopen(req, timeout=120.0) as resp:  # noqa: S310
            return json.loads(resp.read().decode("utf-8"))


def _require_mcp():
    try:
        import importlib

        mod = importlib.import_module("mcp.server.fastmcp")
        return getattr(mod, "FastMCP")
    except (ImportError, AttributeError) as exc:  # pylint: disable=broad-exception-caught
        raise RuntimeError(
            "MCP Python SDK is not installed. Install optional deps (see requirements.txt)."
        ) from exc


def _read_checks_from_path(path_str: str) -> str:
    p = Path(path_str).expanduser()
    if not p.exists() or not p.is_file():
        raise ValueError(f"checks_path not found: {path_str}")
    return p.read_text(encoding="utf-8", errors="replace")


def _extract_rule_results(report: Any) -> List[Dict[str, Any]]:
    if not isinstance(report, dict):
        return []
    rules = report.get("rule_results")
    if isinstance(rules, list):
        return [r for r in rules if isinstance(r, dict)]
    return []


def _rule_key(rule: Dict[str, Any]) -> str:
    return str(rule.get("name") or rule.get("check") or rule.get("definition") or "").strip() or "(unnamed)"


def _rule_outcome(rule: Dict[str, Any]) -> str:
    return str(rule.get("outcome") or "").strip().lower()


def _summarize_rules(rules: List[Dict[str, Any]]) -> Dict[str, Any]:
    total = 0
    passed = 0
    warn = 0
    failed = 0
    by_outcome: Dict[str, int] = {}

    for r in rules:
        total += 1
        outcome = _rule_outcome(r) or "unknown"
        by_outcome[outcome] = by_outcome.get(outcome, 0) + 1
        if outcome == "pass":
            passed += 1
        elif outcome == "warn":
            warn += 1
        elif outcome == "fail":
            failed += 1

    return {
        "total": total,
        "passed": passed,
        "warn": warn,
        "failed": failed,
        "by_outcome": by_outcome,
    }


def _compute_trend(values: List[float]) -> Dict[str, Any]:
    if not values:
        return {"count": 0}

    latest = values[0]
    prior = values[1:]
    if not prior:
        return {"count": 1, "latest": latest, "delta_vs_prior_avg": None}

    avg = sum(prior) / len(prior)
    return {
        "count": len(values),
        "latest": latest,
        "prior_avg": avg,
        "delta_vs_prior_avg": latest - avg,
    }


def _anomaly_analysis(reports: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not reports:
        return {"message": "No reports found"}

    latest = reports[0]
    prior = reports[1:]

    latest_rules = _extract_rule_results(latest)
    latest_rules_by_name = {_rule_key(r): r for r in latest_rules}

    # Build historical pass/fail frequency per check.
    hist_counts: Dict[str, Dict[str, int]] = {}
    for rep in prior:
        for r in _extract_rule_results(rep):
            key = _rule_key(r)
            outcome = _rule_outcome(r) or "unknown"
            bucket = hist_counts.setdefault(key, {})
            bucket[outcome] = bucket.get(outcome, 0) + 1

    newly_failed: List[Dict[str, Any]] = []
    recovered: List[Dict[str, Any]] = []
    persistently_failing: List[Dict[str, Any]] = []

    for name, rule in latest_rules_by_name.items():
        outcome = _rule_outcome(rule)
        hist = hist_counts.get(name, {})
        hist_total = sum(hist.values())
        hist_fail = hist.get("fail", 0) + hist.get("warn", 0)
        hist_pass = hist.get("pass", 0)

        fail_rate = (hist_fail / hist_total) if hist_total else None
        pass_rate = (hist_pass / hist_total) if hist_total else None

        if outcome in {"fail", "warn"}:
            # Consider it "newly" failing if it previously passed most of the time.
            if pass_rate is not None and pass_rate >= 0.7:
                newly_failed.append(
                    {
                        "check": name,
                        "outcome": outcome,
                        "historical_pass_rate": round(pass_rate, 3),
                        "historical_samples": hist_total,
                        "details": rule,
                    }
                )
            if fail_rate is not None and fail_rate >= 0.7:
                persistently_failing.append(
                    {
                        "check": name,
                        "outcome": outcome,
                        "historical_fail_rate": round(fail_rate, 3),
                        "historical_samples": hist_total,
                        "details": rule,
                    }
                )
        elif outcome == "pass":
            if fail_rate is not None and fail_rate >= 0.5:
                recovered.append(
                    {
                        "check": name,
                        "outcome": outcome,
                        "historical_fail_rate": round(fail_rate, 3),
                        "historical_samples": hist_total,
                        "details": rule,
                    }
                )

    scores: List[float] = []
    for r in reports:
        try:
            raw = r.get("overall_score")
            if raw is None:
                continue
            scores.append(float(raw))
        except (ValueError, TypeError) as exc:  # pylint: disable=broad-exception-caught
            continue

    return {
        "latest": {
            "scan_id": latest.get("scan_id"),
            "table_name": latest.get("table_name"),
            "overall_score": latest.get("overall_score"),
            "summary": _summarize_rules(latest_rules),
        },
        "trend": _compute_trend(scores),
        "newly_failed": newly_failed,
        "persistently_failing": persistently_failing,
        "recovered": recovered,
        "notes": [
            "Analysis is heuristic and based on persisted scan reports.",
            "For Soda Cloud anomaly detection, a separate integration would be needed.",
        ],
    }


if __name__ == "__main__":
    FastMCP = _require_mcp()

    mcp = FastMCP("goodpoint-mcp-soda")

    @mcp.tool()
    def ping() -> dict:
        """Health check for the MCP Soda server."""
        return {"ok": True, "backend": _backend_base_url()}

    @mcp.tool()
    def run_soda_scan(
        table_name: str,
        checks_yaml: Optional[str] = None,
        checks_path: Optional[str] = None,
        data_source_name: str = "postgres",
    ) -> Dict[str, Any]:
        """Execute Soda checks against a Postgres table via the backend.

        Args:
            table_name: Table identifier (supports 'schema.table' or 'table').
            checks_yaml: Raw SodaCL checks YAML (contents of checks.yml).
            checks_path: Optional file path to checks.yml; if set, overrides checks_yaml.
            data_source_name: Soda data source name (default 'postgres').

        Returns:
            Backend response JSON (includes scan_id + persisted report payload).
        """
        tn = (table_name or "").strip()
        if not tn:
            raise ValueError("table_name is required")

        if checks_path:
            checks_yaml_local = _read_checks_from_path(str(checks_path))
        else:
            checks_yaml_local = str(checks_yaml or "").strip()

        base = _backend_base_url().rstrip("/")
        payload = {
            "data_source_name": str(data_source_name or "postgres").strip() or "postgres",
            "checks_yaml": checks_yaml_local,
        }
        return dict(_http_post_json(f"{base}/api/analytics/quality/soda/scan/{tn}", payload) or {})

    @mcp.tool()
    def get_scan_results(table_name: str, limit: int = 1) -> Dict[str, Any]:
        """Retrieve latest persisted scan report(s) for a table.

        This calls the backend quality reports endpoint and returns a compact summary
        plus the raw report payload(s).
        """
        tn = (table_name or "").strip()
        if not tn:
            raise ValueError("table_name is required")

        lim = max(1, min(int(limit or 1), 50))
        base = _backend_base_url().rstrip("/")
        url = f"{base}/api/analytics/quality/reports?table_name={tn}&skip=0&limit={lim}"
        reports = _http_get_json(url)
        if not isinstance(reports, list):
            reports = []

        latest = reports[0] if reports else None
        latest_rules = _extract_rule_results(latest) if isinstance(latest, dict) else []

        return {
            "table_name": tn,
            "count": len(reports),
            "latest": {
                "scan_id": latest.get("scan_id") if isinstance(latest, dict) else None,
                "scan_date": latest.get("scan_date") if isinstance(latest, dict) else None,
                "overall_score": latest.get("overall_score") if isinstance(latest, dict) else None,
                "summary": _summarize_rules(latest_rules),
            },
            "reports": reports,
        }

    @mcp.tool()
    def analyze_anomaly(table_name: str, window: int = 10) -> Dict[str, Any]:
        """Heuristic anomaly analysis over recent Soda scan reports for a table.

        Fetches last N reports from the backend and returns:
        - score trend
        - newly failed checks
        - persistently failing checks
        - recovered checks

        This is NOT Soda Cloud AI anomaly detection; it is deterministic trend analysis.
        """
        tn = (table_name or "").strip()
        if not tn:
            raise ValueError("table_name is required")

        win = max(2, min(int(window or 10), 50))
        base = _backend_base_url().rstrip("/")
        url = f"{base}/api/analytics/quality/reports?table_name={tn}&skip=0&limit={win}"
        reports = _http_get_json(url)
        if not isinstance(reports, list):
            reports = []

        # Backend returns newest-first ordering.
        return {
            "table_name": tn,
            "window": win,
            "analysis": _anomaly_analysis([r for r in reports if isinstance(r, dict)]),
        }

    @mcp.tool()
    def check_opensearch_ad_results(
        result_index: str,
        threshold: float = 0.9,
        lookback_minutes: int = 10,
        grade_field: str = "anomaly_grade",
        time_field: str = "data_end_time",
        time_field_is_epoch_millis: bool = True,
        max_examples: int = 5,
    ) -> Dict[str, Any]:
        """Gatekeeper check for OpenSearch Anomaly Detection results.

        This calls the backend endpoint that queries your *custom AD result index*
        (created by enabling "Enable custom result index" on the detector) and
        persists a standard analytics/quality report. The report then shows up in
        /api/analytics/quality/reports and can be analyzed using analyze_anomaly.

        Args:
            result_index: AD result index name (e.g. opensearch-ad-plugin-result-orders-anomalies).
            threshold: Fail when max anomaly grade >= threshold.
            lookback_minutes: Search window for recent anomalies.
            grade_field: Field containing anomaly grade.
            time_field: Field used for time filtering.
            time_field_is_epoch_millis: True if time_field stores epoch millis.
            max_examples: Number of example anomaly docs included in the report.
        """

        idx = (result_index or "").strip()
        if not idx:
            raise ValueError("result_index is required")

        base = _backend_base_url().rstrip("/")
        payload = {
            "threshold": float(threshold),
            "lookback_minutes": int(lookback_minutes),
            "grade_field": str(grade_field or "anomaly_grade"),
            "time_field": str(time_field or "data_end_time"),
            "time_field_is_epoch_millis": bool(time_field_is_epoch_millis),
            "max_examples": int(max_examples),
        }
        return dict(_http_post_json(f"{base}/api/analytics/quality/opensearch-ad/gate/{idx}", payload) or {})

    mcp.run()
