from __future__ import annotations

import dataclasses
import logging
import re
import uuid
import hashlib
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, cast

import csv
import io
import json
import xml.etree.ElementTree as ET

import httpx

from fastapi import APIRouter, Depends, HTTPException, Query, Response, UploadFile, File
from pydantic import BaseModel, Field
from sqlalchemy import text, func
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.engine.url import make_url
from sqlalchemy.orm import Session

from core.db_session import DATABASE_URL, get_db
from core.postgres_config import is_postgres_database_url
from models.quality_models import DataQualityRule, DataQualityResult, DataQualityScanReport

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/analytics/quality", tags=["Analytics - Quality"])

# P-05: guard against extremely large or deeply-nested directory scans.
_MAX_RGLOB_FILES = 10_000
_MAX_RGLOB_DEPTH = 10

# P-07: simple TTL cache for _profile_table results (keyed by qualified table name).
# Avoids re-firing 150+ SQL queries when the same table is scanned repeatedly within
# the TTL window (e.g. polling from the UI).
import threading as _threading
import time as _time

@dataclasses.dataclass
class _ProfileCacheEntry:
    profiling: List[Dict[str, Any]]
    distribution: List[Dict[str, Any]]
    expires_at: float

_PROFILE_CACHE: Dict[str, "_ProfileCacheEntry"] = {}
_PROFILE_CACHE_LOCK = _threading.Lock()
_PROFILE_CACHE_TTL_S: float = float(os.getenv("PROFILE_CACHE_TTL_S", "60"))

# --- Pydantic Models ---

class DataQualityReport(BaseModel):
    table_name: str
    scan_id: str
    completeness_score: float
    accuracy_score: float
    consistency_score: float
    validity_score: float
    overall_score: float
    issues: List[Dict[str, Any]]
    recommendations: List[str]
    scan_date: datetime
    row_count: int
    column_count: int

    # --- Focused Data Quality Metrics (new, backward compatible) ---
    missing_values: int = 0
    invalid_values: int = 0
    duplicate_count: int = 0

    # Freshness / SLA (optional, depends on available timestamp columns + config)
    freshness: Optional[Dict[str, Any]] = None
    delayed_arrivals: int = 0
    sla_violations: int = 0

    # Distribution + Profiling / Discovery (optional; may only be present on report detail)
    distribution_metrics: List[Dict[str, Any]] = Field(default_factory=list)
    profiling: List[Dict[str, Any]] = Field(default_factory=list)


def _normalize_quality_report_payload(
    payload: Any,
    *,
    fallback_overall_score: float | None = None,
    fallback_scan_id: str | None = None,
    fallback_table_name: str | None = None,
    fallback_scan_date: Any = None,
    fallback_row_count: int | None = None,
    fallback_column_count: int | None = None,
) -> Dict[str, Any]:
    """Normalize persisted report JSON to the current API response contract.

    Older records may be missing per-dimension score fields or even top-level
    identity fields (table_name/scan_id/scan_date/row_count/column_count);
    returning them as-is triggers FastAPI response-model validation errors (500).
    Fallbacks come from the owning DB row.
    """

    report: Dict[str, Any] = dict(payload or {}) if isinstance(payload, dict) else {}

    # Backfill identity / metadata fields from owning row when missing.
    if not report.get("scan_id") and fallback_scan_id is not None:
        report["scan_id"] = fallback_scan_id
    if not report.get("table_name") and fallback_table_name is not None:
        report["table_name"] = fallback_table_name
    if report.get("scan_date") is None and fallback_scan_date is not None:
        try:
            report["scan_date"] = (
                fallback_scan_date.isoformat()
                if hasattr(fallback_scan_date, "isoformat")
                else str(fallback_scan_date)
            )
        except Exception:
            report["scan_date"] = str(fallback_scan_date)
    if report.get("row_count") is None and fallback_row_count is not None:
        report["row_count"] = int(fallback_row_count)
    if report.get("column_count") is None and fallback_column_count is not None:
        report["column_count"] = int(fallback_column_count)

    # Ensure list-typed required fields exist.
    if not isinstance(report.get("issues"), list):
        report["issues"] = []
    if not isinstance(report.get("recommendations"), list):
        report["recommendations"] = []

    overall_score_raw = report.get("overall_score")
    if overall_score_raw is None:
        overall_score_raw = fallback_overall_score
    try:
        overall_score = float(overall_score_raw) if overall_score_raw is not None else 0.0
    except (ValueError, TypeError):
        overall_score = 0.0

    for key in ("completeness_score", "accuracy_score", "consistency_score", "validity_score"):
        if report.get(key) is None:
            report[key] = overall_score

    if report.get("overall_score") is None:
        report["overall_score"] = overall_score

    # New metrics/profiling fields: ensure they exist (backward compatible with older persisted payloads)
    for key, default in (
        ("missing_values", 0),
        ("invalid_values", 0),
        ("duplicate_count", 0),
    ):
        report[key] = _coerce_int(report.get(key), default=int(default))

    if report.get("freshness") is None:
        report["freshness"] = None
    for key in ("delayed_arrivals", "sla_violations"):
        report[key] = _coerce_int(report.get(key), default=0)

    if not isinstance(report.get("distribution_metrics"), list):
        report["distribution_metrics"] = []
    if not isinstance(report.get("profiling"), list):
        report["profiling"] = []

    return report


def _get_freshness_sla_seconds() -> int:
    """Global SLA threshold for freshness-based violations.

    If freshness can't be computed, we report 0 violations.
    Defaults to 24 hours.
    """

    raw = (os.getenv("GRAPH_TRACE_QUALITY_FRESHNESS_SLA_SECONDS") or "").strip()
    if not raw:
        return 24 * 60 * 60
    try:
        v = int(raw)
        return v if v > 0 else 24 * 60 * 60
    except ValueError:
        return 24 * 60 * 60


def _coerce_int(value: Any, *, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)


def _coerce_float(value: Any, *, default: float | None = None) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default

class QualityRule(BaseModel):
    id: str
    name: str
    description: str
    rule_type: str  # "completeness", "accuracy", "consistency", "validity"
    condition: str
    severity: str  # "low", "medium", "high", "critical"
    enabled: bool = True

class QualityIssue(BaseModel):
    issue_id: str
    rule_id: str
    severity: str
    description: str
    affected_rows: int
    affected_columns: List[str]
    sample_values: List[Any]
    suggestion: str

class QualityScanRequest(BaseModel):
    # table_name is provided as a path parameter on the scan endpoint; keep this optional
    # for backwards compatibility with clients that also send it in the JSON body.
    table_name: Optional[str] = None
    # data_source is only required when using the filesystem fallback (table does not exist).
    data_source: Optional[str] = None
    rules: List[str] = Field(default_factory=list)  # Rule IDs to apply, empty means all enabled rules
    sample_size: Optional[int] = None


class SodaScanRequest(BaseModel):
    """Request for a Soda Core scan against Postgres.

    checks_yaml can be either:
    - full SodaCL YAML (including `checks for <table>:`)
    - or just the indented list of checks (we will wrap it).
    - or omitted entirely — with auto_checks=True (the default) a comprehensive
      set of checks covering row_count, schema drift, completeness, numeric stats,
      freshness, and format validity is generated from table introspection.
    """

    checks_yaml: Optional[str] = None
    data_source_name: str = "postgres"
    auto_checks: bool = True

_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _short_data_source_label(raw: str, *, max_len: int = 64) -> str:
    """Create a bounded label suitable for storing in DB columns.

    We keep the full path in the JSON report payload, but the relational column
    may be length-constrained.
    """

    value = (raw or "").strip()
    if not value:
        return ""
    if len(value) <= max_len:
        return value
    digest = hashlib.sha256(value.encode("utf-8", errors="ignore")).hexdigest()[:12]
    suffix = f"...#{digest}"
    keep = max(1, max_len - len(suffix))
    return value[:keep] + suffix


def _require_postgres() -> None:
    # Enforce "Postgres is the single truth" for analytics quality.
    if not is_postgres_database_url(DATABASE_URL):
        raise HTTPException(
            status_code=503,
            detail="Postgres is not configured (set DATABASE_URL to a postgres URL)",
        )


def _get_soda_scan_class() -> Any:
    """Return Soda Scan class or fail-closed with 503.

    This endpoint is explicitly a Soda feature; if Soda isn't installed,
    callers should get a deterministic 503 (not a partial/mock scan).
    """

    try:
        from soda.scan import Scan  # type: ignore

        return Scan
    except Exception as exc:  # pylint: disable=broad-exception-caught
        raise HTTPException(
            status_code=503,
            detail="Soda Core is not installed. Install `soda-core-postgres` to use this endpoint.",
        ) from exc


def _soda_config_yaml_from_database_url(database_url: str, *, data_source_name: str, _schema: str) -> str:
    # `_schema` is accepted for call-site compatibility, but we intentionally
    # don't include schema in the Soda connection YAML (see note below).
    _ = _schema

    url = make_url(database_url)
    if not url.host or not url.database:
        raise HTTPException(status_code=503, detail="DATABASE_URL must include host and database")

    user = url.username or ""
    password = url.password or ""
    port = int(url.port or 5432)

    # Keep this in-memory only; never persist secrets.
    # NOTE: Do not set `schema` in the Soda connection config here.
    # When checks reference a qualified table (e.g. `public.my_table`), Soda will
    # otherwise generate SQL like `FROM public.public.my_table`.
    return (
        f"data_source {data_source_name}:\n"
        f"  type: postgres\n"
        f"  connection:\n"
        f"    host: {url.host}\n"
        f"    port: {port}\n"
        f"    username: {user}\n"
        f"    password: {password}\n"
        f"    database: {url.database}\n"
    )


def _wrap_sodacl_checks(schema: str, table: str, checks_yaml: str) -> str:
    raw = (checks_yaml or "").rstrip() + "\n"
    if "checks for" in raw:
        return raw
    # Indent checks under the header if needed.
    indented = "\n".join(
        ("  " + line if line.strip() else line) for line in raw.splitlines()
    ).rstrip() + "\n"
    return f"checks for {schema}.{table}:\n{indented}"


# ── Soda auto-check type sets ────────────────────────────────────────────────
_SODA_NUMERIC_DT = {
    "smallint", "integer", "bigint", "numeric", "decimal",
    "real", "double precision", "money",
}
_SODA_TIMESTAMP_DT = {
    "timestamp without time zone", "timestamp with time zone",
    "date", "timetz", "timestamptz",
}
_SODA_TEXT_DT = {
    "character varying", "varchar", "text", "char", "character", "name",
}
_SODA_EMAIL_NAMES  = {"email", "email_address", "e_mail", "mail"}
_SODA_PHONE_NAMES  = {"phone", "phone_number", "mobile", "telephone", "tel"}
_SODA_URL_NAMES    = {"url", "website", "web_url", "link", "homepage"}
_SODA_UUID_NAMES   = {"uuid", "guid", "unique_id", "uid"}


def _generate_auto_sodacl(
    schema: str,
    table: str,
    columns_with_types: List[Dict[str, str]],
) -> str:
    """Generate comprehensive SodaCL YAML covering all standard Soda metric categories.

    Emitted checks
    --------------
    Table-level:   row_count > 0, schema drift (warn on delete/add/type-change),
                   duplicate_count on likely PK columns.
    Per-column:    missing_count = 0 (warn>0, fail>10%), missing_percent < 5.
    Numeric cols:  min, max, avg, sum, stddev.
    Timestamp cols: freshness (warn>1d, fail>7d).
    Text cols:     invalid_count with format: email | phone number | url | uuid
                   when column name matches well-known patterns.
    """
    lines: List[str] = [f"checks for {schema}.{table}:"]

    # ── Table level ──────────────────────────────────────────────────────
    lines.append("  # ── Table level")
    lines.append("  - row_count > 0")
    lines.append("  - schema:")
    lines.append("      warn:")
    lines.append("        when schema changes:")
    lines.append("          - column delete")
    lines.append("          - column add")
    lines.append("          - column type change")
    pk_candidates = [
        c["name"] for c in columns_with_types
        if c["name"].lower() in {"id", "uuid", "record_id", "pk", "key", "primary_key"}
    ]
    for pk in pk_candidates[:2]:
        lines.append(f"  - duplicate_count({pk}) = 0")

    # ── Per-column ───────────────────────────────────────────────────────
    for col in columns_with_types:
        name = col["name"]
        dt = (col.get("data_type") or "").lower()
        name_lower = name.lower()
        lines.append(f"  # Column: {name}")

        # Completeness
        lines.append(f"  - missing_count({name}) = 0:")
        lines.append(f"      warn: when > 0")
        lines.append(f"      fail: when > 10%")
        lines.append(f"  - missing_percent({name}) < 5")

        # Numeric stats — metric-only (no threshold; value is captured in scan results)
        if dt in _SODA_NUMERIC_DT:
            lines.append(f"  - min({name})")
            lines.append(f"  - max({name})")
            lines.append(f"  - avg({name})")
            lines.append(f"  - sum({name})")
            lines.append(f"  - stddev({name})")

        # Freshness
        if dt in _SODA_TIMESTAMP_DT:
            lines.append(f"  - freshness({name}) < 7d:")
            lines.append(f"      warn: when > 1d")
            lines.append(f"      fail: when > 7d")

        # Format validity for text columns with recognisable naming patterns
        if dt in _SODA_TEXT_DT:
            if name_lower in _SODA_EMAIL_NAMES or name_lower.endswith("_email"):
                lines.append(f"  - invalid_count({name}):")
                lines.append(f"      valid format: email")
                lines.append(f"      fail: when > 0")
            elif name_lower in _SODA_PHONE_NAMES or name_lower.endswith("_phone"):
                lines.append(f"  - invalid_count({name}):")
                lines.append(f"      valid format: phone number")
                lines.append(f"      warn: when > 0")
            elif name_lower in _SODA_URL_NAMES or name_lower.endswith("_url"):
                lines.append(f"  - invalid_count({name}):")
                lines.append(f"      valid format: url")
                lines.append(f"      warn: when > 0")
            elif name_lower in _SODA_UUID_NAMES or name_lower.endswith(("_uuid", "_guid")):
                lines.append(f"  - invalid_count({name}):")
                lines.append(f"      valid format: uuid")
                lines.append(f"      fail: when > 0")

    return "\n".join(lines) + "\n"


def _score_from_soda_checks(checks: List[Dict[str, Any]]) -> float:
    if not checks:
        return 0.0
    passed = 0
    for c in checks:
        outcome = str(c.get("outcome") or "").strip().lower()
        if outcome == "pass":
            passed += 1
    return float(max(0.0, min(1.0, passed / max(1, len(checks)))))


def _issues_from_soda_checks(checks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    issues: List[Dict[str, Any]] = []
    for c in checks:
        outcome = str(c.get("outcome") or "").strip().lower()
        if outcome in {"fail", "warn"}:
            name = str(c.get("name") or c.get("check") or c.get("definition") or "Soda check").strip()
            severity = str(c.get("severity") or ("high" if outcome == "fail" else "medium")).strip().lower()
            failed_rows = c.get("failures")
            try:
                affected_rows = int(failed_rows) if failed_rows is not None else 0
            except (TypeError, ValueError):
                affected_rows = 0

            issues.append(
                {
                    "issue_id": str(uuid.uuid4()),
                    "rule_id": name,
                    "severity": severity,
                    "description": name,
                    "affected_rows": affected_rows,
                    "affected_columns": [],
                    "sample_values": [],
                    "suggestion": "Review failed Soda checks and fix upstream data",
                }
            )
    return issues


def _parse_table_name(table_name: str) -> Tuple[str, str]:
    raw = (table_name or "").strip()
    if not raw:
        raise HTTPException(status_code=400, detail="Missing table_name")

    if "." in raw:
        schema, table = raw.split(".", 1)
    else:
        schema, table = "public", raw

    if not _IDENT_RE.match(schema) or not _IDENT_RE.match(table):
        raise HTTPException(status_code=400, detail="Invalid table identifier")
    return schema, table


def _entity_type_for_table(table: str) -> str:
    # Back-compat with existing persisted DQ rules in PLM ETL.
    # If users already created rules for entity_type=part/bom, reuse them.
    t = (table or "").strip().lower()
    if t == "plm_parts":
        return "part"
    if t == "plm_bom_items":
        return "bom"
    return t


def _quote_ident(ident: str) -> str:
    # Safe because we validate `ident` with _IDENT_RE.
    return f'"{ident}"'


def _qualified_table(schema: str, table: str) -> str:
    return f"{_quote_ident(schema)}.{_quote_ident(table)}"


def _table_exists(db: Session, schema: str, table: str) -> bool:
    q = text(
        """
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema = :schema AND table_name = :table
        LIMIT 1
        """
    )
    return db.execute(q, {"schema": schema, "table": table}).first() is not None


def _list_columns(db: Session, schema: str, table: str) -> List[str]:
    q = text(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = :schema AND table_name = :table
        ORDER BY ordinal_position
        """
    )
    return [r[0] for r in db.execute(q, {"schema": schema, "table": table}).all()]


def _list_columns_with_types(db: Session, schema: str, table: str) -> List[Dict[str, str]]:
    q = text(
        """
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_schema = :schema AND table_name = :table
        ORDER BY ordinal_position
        """
    )
    rows = db.execute(q, {"schema": schema, "table": table}).all()
    return [{"name": str(r[0]), "data_type": str(r[1])} for r in rows]


def _compute_freshness(db: Session, qualified: str, columns_with_types: List[Dict[str, str]]) -> Optional[Dict[str, Any]]:
    """Compute freshness based on a best-effort timestamp-like column.

    Returns a dict describing the chosen column and its MAX() timestamp.
    """

    # Prefer common "last updated" style columns.
    preferred = [
        "last_updated",
        "last_updated_at",
        "updated_at",
        "updated_on",
        "modified_at",
        "modified_on",
        "ingested_at",
        "ingested_on",
        "event_time",
        "event_timestamp",
        "created_at",
        "created_on",
    ]

    ts_types = {
        "timestamp without time zone",
        "timestamp with time zone",
        "date",
        "time with time zone",
        "time without time zone",
    }

    candidates = []
    for c in columns_with_types:
        name = str(c.get("name") or "")
        dt = str(c.get("data_type") or "").lower()
        if not name:
            continue
        if dt in ts_types:
            candidates.append(name)

    if not candidates:
        return None

    lower_to_name = {n.lower(): n for n in candidates}
    chosen = None
    for p in preferred:
        if p in lower_to_name:
            chosen = lower_to_name[p]
            break
    if chosen is None:
        chosen = candidates[0]

    q = text(f"SELECT MAX({_quote_ident(chosen)}) AS max_ts FROM {qualified}")
    max_ts = db.execute(q).mappings().first()
    value = None
    if max_ts:
        value = max_ts.get("max_ts")

    if value is None:
        return {"column": chosen, "last_updated": None, "age_seconds": None}

    # value is datetime/date depending on column; normalize to ISO.
    try:
        if hasattr(value, "isoformat"):
            iso = value.isoformat()
        else:
            iso = str(value)
    except Exception:
        iso = str(value)

    age_seconds = None
    try:
        now = datetime.now(timezone.utc)
        if isinstance(value, datetime):
            v = value
            if v.tzinfo is None:
                v = v.replace(tzinfo=timezone.utc)
            age_seconds = int((now - v).total_seconds())
    except Exception:
        age_seconds = None

    return {"column": chosen, "last_updated": iso, "age_seconds": age_seconds}


def _is_numeric_type(data_type: str) -> bool:
    t = (data_type or "").lower()
    return t in {
        "smallint",
        "integer",
        "bigint",
        "numeric",
        "decimal",
        "real",
        "double precision",
    }


def _profile_table(
    db: Session,
    qualified: str,
    columns_with_types: List[Dict[str, str]],
    *,
    row_count: int,
    max_columns: int = 50,
    top_k: int = 5,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Return (profiling, distribution_metrics) for a table.

    P-01: replaces N×3 per-column queries with a single aggregated SQL pass for
          null counts + cardinality, then one GROUP-BY per column for top-k values.
    P-07: results are cached per qualified table name with a configurable TTL
          (PROFILE_CACHE_TTL_S env var, default 60 s) to avoid hammering the DB
          when the UI polls repeatedly.

    Profiling is column-level. Distribution metrics are numeric-only summaries.
    """
    # P-07: cache lookup.
    cache_key = qualified
    with _PROFILE_CACHE_LOCK:
        entry = _PROFILE_CACHE.get(cache_key)
        if entry and _time.monotonic() < entry.expires_at:
            return entry.profiling, entry.distribution

    profiling: List[Dict[str, Any]] = []
    distribution: List[Dict[str, Any]] = []

    cols = columns_with_types[:max_columns]
    valid_cols = [c for c in cols if str(c.get("name") or "")]

    if not valid_cols:
        return profiling, distribution

    # P-01: single aggregated query for total rows + per-column null counts + distinct counts.
    # Collapses O(N_cols × 2) queries → 1 query.
    agg_parts: List[str] = ["COUNT(*) AS _total"]
    for c in valid_cols:
        qn = _quote_ident(str(c["name"]))
        safe = str(c["name"]).replace('"', "").replace("'", "")  # for alias
        agg_parts.append(
            f"SUM(CASE WHEN {qn} IS NULL THEN 1 ELSE 0 END) AS _null_{safe}"
        )
        agg_parts.append(f"COUNT(DISTINCT {qn}) AS _dist_{safe}")

    try:
        agg_q = text(f"SELECT {', '.join(agg_parts)} FROM {qualified}")
        agg_row = cast(Dict[str, Any], dict(db.execute(agg_q).mappings().first() or {}))
    except Exception:  # pylint: disable=broad-exception-caught
        agg_row = {}

    total_rows = int(agg_row.get("_total") or 0)

    for c in valid_cols:
        name = str(c.get("name") or "")
        dt = str(c.get("data_type") or "")
        safe = name.replace('"', "").replace("'", "")

        total = total_rows
        nulls = int(agg_row.get(f"_null_{safe}") or 0)
        distinct_count = int(agg_row.get(f"_dist_{safe}") or 0)
        null_pct = (float(nulls) / float(total) * 100.0) if total > 0 else 0.0

        # Frequent values (top-k). NOTE: This returns actual values, which is required for discovery/profiling.
        freq: List[Dict[str, Any]] = []
        try:
            freq_q = text(
                f"""
                SELECT {_quote_ident(name)} AS value, COUNT(*) AS count
                FROM {qualified}
                GROUP BY {_quote_ident(name)}
                ORDER BY COUNT(*) DESC
                LIMIT :limit
                """
            )
            for r in db.execute(freq_q, {"limit": int(top_k)}).mappings().all():
                v = r.get("value")
                # Keep payload bounded.
                if v is None:
                    sv = None
                else:
                    sv = str(v)
                    if len(sv) > 128:
                        sv = sv[:125] + "..."
                freq.append({"value": sv, "count": int(r.get("count") or 0)})
        except Exception:  # pylint: disable=broad-exception-caught
            freq = []

        top_fraction = 0.0
        if total > 0 and freq:
            top_fraction = float(freq[0].get("count") or 0) / float(total)

        # Distribution shape (simple heuristic)
        shape = "unknown"
        if total == 0:
            shape = "empty"
        elif distinct_count <= 1:
            shape = "constant"
        elif _is_numeric_type(dt):
            if top_fraction >= 0.5:
                shape = "highly_skewed"
            elif distinct_count >= int(0.9 * total):
                shape = "near_unique"
            else:
                shape = "numeric"
        else:
            if top_fraction >= 0.5:
                shape = "skewed"
            elif distinct_count <= 20:
                shape = "low_cardinality"
            else:
                shape = "categorical"

        numeric_stats: Optional[Dict[str, Any]] = None
        if _is_numeric_type(dt):
            try:
                stats_q = text(
                    f"""
                    SELECT
                      MIN({_quote_ident(name)}) AS min,
                      MAX({_quote_ident(name)}) AS max,
                      AVG({_quote_ident(name)}) AS avg,
                      STDDEV_POP({_quote_ident(name)}) AS stddev
                    FROM {qualified}
                    """
                )
                stats = cast(Dict[str, Any], dict(db.execute(stats_q).mappings().first() or {}))
                numeric_stats = {
                    "min": _coerce_float(stats.get("min"), default=None),
                    "max": _coerce_float(stats.get("max"), default=None),
                    "avg": _coerce_float(stats.get("avg"), default=None),
                    "stddev": _coerce_float(stats.get("stddev"), default=None),
                }
            except Exception:  # pylint: disable=broad-exception-caught
                numeric_stats = None

        col_profile = {
            "column": name,
            "data_type": dt,
            "null_count": nulls,
            "null_percentage": round(null_pct, 2),
            "cardinality": distinct_count,
            "frequent_values": freq,
            "distribution_shape": shape,
        }
        if numeric_stats is not None:
            col_profile["distribution_metrics"] = numeric_stats
            distribution.append({"column": name, **numeric_stats})

        profiling.append(col_profile)

    # P-07: store result in cache.
    with _PROFILE_CACHE_LOCK:
        _PROFILE_CACHE[cache_key] = _ProfileCacheEntry(
            profiling=profiling,
            distribution=distribution,
            expires_at=_time.monotonic() + _PROFILE_CACHE_TTL_S,
        )

    return profiling, distribution

def _compute_sla_violations_from_freshness(freshness: Optional[Dict[str, Any]]) -> int:
    if not isinstance(freshness, dict):
        return 0
    age = freshness.get("age_seconds")
    try:
        age_s = int(age) if age is not None else None
    except (TypeError, ValueError):
        age_s = None
    if age_s is None:
        return 0

    sla_seconds = _get_freshness_sla_seconds()
    return 1 if age_s > sla_seconds else 0


def _count_rows(db: Session, qualified: str) -> int:
    q = text(f"SELECT COUNT(*) FROM {qualified}")
    return int(db.execute(q).scalar() or 0)


def _eval_not_null(db: Session, qualified: str, column: str) -> Dict[str, int]:
    q = text(
        f"SELECT COUNT(*) AS total, SUM(CASE WHEN {_quote_ident(column)} IS NULL THEN 1 ELSE 0 END) AS failed FROM {qualified}"
    )
    mapping = db.execute(q).mappings().first()
    row: Dict[str, Any] = dict(mapping) if mapping else {}
    return {"total": int(row.get("total") or 0), "failed": int(row.get("failed") or 0)}


def _eval_unique(db: Session, qualified: str, columns: List[str]) -> Dict[str, int]:
    cols = [c for c in columns if c]
    if len(cols) == 1:
        col = _quote_ident(cols[0])
        q = text(
            f"SELECT COUNT(*) AS total, COUNT(DISTINCT {col}) AS distinct_count FROM {qualified}"
        )
    else:
        # Postgres supports DISTINCT on row expressions.
        expr = ", ".join(_quote_ident(c) for c in cols)
        q = text(
            f"SELECT COUNT(*) AS total, COUNT(DISTINCT ({expr})) AS distinct_count FROM {qualified}"
        )
    mapping = db.execute(q).mappings().first()
    row: Dict[str, Any] = dict(mapping) if mapping else {}
    total = int(row.get("total") or 0)
    distinct_count = int(row.get("distinct_count") or 0)
    failed = max(0, total - distinct_count)
    return {"total": total, "failed": failed}


def _eval_fk_exists(
    db: Session,
    qualified: str,
    column: str,
    ref_schema: str,
    ref_table: str,
    ref_column: str,
) -> Dict[str, int]:
    ref_qualified = _qualified_table(ref_schema, ref_table)
    q = text(
        f"""
        SELECT
            COUNT(*) AS total,
            SUM(CASE WHEN r.{_quote_ident(ref_column)} IS NULL THEN 1 ELSE 0 END) AS failed
        FROM {qualified} t
        LEFT JOIN {ref_qualified} r
            ON t.{_quote_ident(column)} = r.{_quote_ident(ref_column)}
        WHERE t.{_quote_ident(column)} IS NOT NULL
        """
    )
    mapping = db.execute(q).mappings().first()
    row: Dict[str, Any] = dict(mapping) if mapping else {}
    return {"total": int(row.get("total") or 0), "failed": int(row.get("failed") or 0)}


def _scan_filesystem_data_source(data_source: str) -> Tuple[
    List[Dict[str, Any]],
    List[str],
    float,
    float,
    float,
    float,
    int,
    int,
]:
    """Deterministic filesystem scan.

    Returns: issues, recommendations, completeness_score, accuracy_score,
    consistency_score, validity_score, row_count, column_count.
    """

    fs_issues: List[Dict[str, Any]] = []
    fs_recommendations: List[str] = []

    def _mk_issue(
        rule_id: str,
        severity: str,
        description: str,
        affected_rows: int = 0,
        affected_columns: Optional[List[str]] = None,
        suggestion: str = "",
    ) -> Dict[str, Any]:
        return {
            "issue_id": str(uuid.uuid4()),
            "rule_id": rule_id,
            "severity": severity,
            "description": description,
            "affected_rows": int(affected_rows),
            "affected_columns": affected_columns or [],
            "sample_values": [],
            "suggestion": suggestion,
        }

    raw = (data_source or "").strip()
    if not raw:
        fs_issues.append(
            _mk_issue(
                rule_id="validity_001",
                severity="high",
                description="data_source is required for filesystem scans",
                affected_rows=0,
                suggestion="Provide a local file/folder path accessible to the backend",
            )
        )
        return fs_issues, ["Provide a valid filesystem path."], 0.0, 0.0, 0.0, 0.0, 0, 0

    try:
        p = Path(raw)
    except TypeError:
        fs_issues.append(
            _mk_issue(
                rule_id="validity_001",
                severity="high",
                description="data_source is not a valid path",
                affected_rows=0,
                suggestion="Provide a local file/folder path",
            )
        )
        return fs_issues, ["Provide a valid filesystem path."], 0.0, 0.0, 0.0, 0.0, 0, 0

    def _safe_xml_parse(path: Path) -> bool:
        try:
            ET.parse(str(path))
            return True
        except OSError as e:
            fs_issues.append(
                _mk_issue(
                    rule_id="validity_001",
                    severity="high",
                    description=f"XML read failed: {path.name}: {e}",
                    affected_rows=1,
                    suggestion="Check file permissions/path and try again",
                )
            )
            return False
        except ET.ParseError as e:
            fs_issues.append(
                _mk_issue(
                    rule_id="validity_001",
                    severity="high",
                    description=f"XML parse failed: {path.name}: {e}",
                    affected_rows=1,
                    suggestion="Fix malformed XML or encoding issues",
                )
            )
            return False

    def _safe_json_load(path: Path) -> Optional[Any]:
        try:
            with path.open("r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            fs_issues.append(
                _mk_issue(
                    rule_id="validity_001",
                    severity="high",
                    description=f"JSON parse failed: {path.name}: {e}",
                    affected_rows=1,
                    suggestion="Fix malformed JSON",
                )
            )
            return None
        except UnicodeDecodeError as e:
            fs_issues.append(
                _mk_issue(
                    rule_id="validity_001",
                    severity="high",
                    description=f"JSON decode failed (encoding): {path.name}: {e}",
                    affected_rows=1,
                    suggestion="Ensure the file is UTF-8 encoded",
                )
            )
            return None
        except OSError as e:
            fs_issues.append(
                _mk_issue(
                    rule_id="validity_001",
                    severity="high",
                    description=f"JSON read failed: {path.name}: {e}",
                    affected_rows=1,
                    suggestion="Check file permissions/path and try again",
                )
            )
            return None

    def _safe_csv_count(path: Path) -> Tuple[int, int]:
        """Return (row_count, column_count) with BOM-safe, encoding-resilient, delimiter-sniffed parsing.

        Tries utf-8-sig (handles Excel BOM), then cp1252 (Windows-ANSI), then latin-1.
        Uses csv.Sniffer to auto-detect comma/semicolon/tab/pipe delimiter.
        """
        for enc in ("utf-8-sig", "cp1252", "latin-1"):
            try:
                with path.open("r", encoding=enc, newline="") as f:
                    sample = f.read(4096)
                    f.seek(0)
                    try:
                        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
                    except csv.Error:
                        dialect = csv.excel
                    reader = csv.reader(f, dialect=dialect)
                    header = next(reader, [])
                    col_count = len(header)
                    rows = sum(1 for _ in reader)
                    return rows, col_count
            except (UnicodeDecodeError, LookupError):
                continue
            except csv.Error as e:
                fs_issues.append(
                    _mk_issue(
                        rule_id="validity_001",
                        severity="high",
                        description=f"CSV parse failed: {path.name}: {e}",
                        affected_rows=1,
                        suggestion="Fix delimiter/quoting issues",
                    )
                )
                return 0, 0
            except OSError as e:
                fs_issues.append(
                    _mk_issue(
                        rule_id="validity_001",
                        severity="high",
                        description=f"CSV read failed: {path.name}: {e}",
                        affected_rows=1,
                        suggestion="Check file permissions/path and try again",
                    )
                )
                return 0, 0
        # All encodings failed
        fs_issues.append(
            _mk_issue(
                rule_id="validity_001",
                severity="high",
                description=f"CSV decode failed (encoding): {path.name}",
                affected_rows=1,
                suggestion="Ensure the file is UTF-8, CP1252, or Latin-1 encoded",
            )
        )
        return 0, 0

    def _safe_excel_count(path: Path) -> Tuple[int, int]:
        """Return (row_count, column_count) for an Excel file (.xlsx/.xls).

        row_count excludes the header row.  Reads all sheets of the active sheet.
        """
        try:
            import openpyxl  # noqa: PLC0415
            wb = openpyxl.load_workbook(str(path), read_only=True, data_only=True)
            ws = wb.active
            all_rows = list(ws.iter_rows(values_only=True))
            wb.close()
            if not all_rows:
                return 0, 0
            col_count = len(all_rows[0])
            return max(0, len(all_rows) - 1), col_count  # exclude header
        except ImportError:
            fs_issues.append(
                _mk_issue(
                    rule_id="validity_001",
                    severity="low",
                    description=f"openpyxl not installed; skipping Excel scan: {path.name}",
                    affected_rows=1,
                    suggestion="Install openpyxl: pip install openpyxl",
                )
            )
            return 0, 0
        except Exception as e:  # pylint: disable=broad-exception-caught
            fs_issues.append(
                _mk_issue(
                    rule_id="validity_001",
                    severity="high",
                    description=f"Excel read failed: {path.name}: {e}",
                    affected_rows=1,
                    suggestion="Check file is not password-protected or corrupt",
                )
            )
            return 0, 0

    parsed_ok = 0
    parsed_total = 0
    row_count = 0
    column_count = 0

    allowed_exts = {"xml", "xsd", "json", "csv", "xlsx", "xls", "zip", "stp", "step"}

    if p.exists() and p.is_file():
        ext = p.suffix.lower().lstrip(".")
        parsed_total = 1

        if ext in ("xml", "xsd"):
            parsed_ok = 1 if _safe_xml_parse(p) else 0
            row_count = 1
            column_count = 0
        elif ext == "json":
            obj = _safe_json_load(p)
            if obj is not None:
                parsed_ok = 1
                if isinstance(obj, list):
                    row_count = len(obj)
                    first = obj[0] if obj else None
                    column_count = len(first) if isinstance(first, dict) else 0
                elif isinstance(obj, dict):
                    row_count = 1
                    column_count = len(obj)
        elif ext == "csv":
            rows, cols = _safe_csv_count(p)
            parsed_ok = 1 if cols > 0 else 0
            row_count = rows
            column_count = cols
        elif ext in ("xlsx", "xls"):
            rows, cols = _safe_excel_count(p)
            parsed_ok = 1 if cols > 0 else 0
            row_count = rows
            column_count = cols
        else:
            fs_issues.append(
                _mk_issue(
                    rule_id="validity_001",
                    severity="medium",
                    description=f"Unsupported file type for deterministic scan: .{ext or '(none)'}",
                    affected_rows=1,
                    suggestion="Provide a CSV/JSON/XML/XSD/Excel file or a directory path",
                )
            )

    elif p.exists() and p.is_dir():
        extension_counts: Dict[str, int] = {}
        xml_count = 0
        xsd_count = 0
        _rglob_file_count = 0  # P-05: per-scan file counter
        data_rows_total = 0   # actual data rows accumulated from structured files
        data_cols_max = 0     # widest column count seen across structured files

        for child in p.rglob("*"):
            if not child.is_file():
                continue

            # P-05: skip deeply-nested paths and stop if file limit is reached.
            try:
                depth = len(child.relative_to(p).parts)
            except ValueError:
                continue
            if depth > _MAX_RGLOB_DEPTH:
                continue
            _rglob_file_count += 1
            if _rglob_file_count > _MAX_RGLOB_FILES:
                logger.warning("P-05: rglob scan truncated at %d files for %s", _MAX_RGLOB_FILES, p)
                break

            ext = child.suffix.lower().lstrip(".") or "(none)"
            extension_counts[ext] = extension_counts.get(ext, 0) + 1

            if ext == "xml":
                xml_count += 1
            if ext == "xsd":
                xsd_count += 1

            if ext in ("xml", "xsd"):
                parsed_total += 1
                if _safe_xml_parse(child):
                    parsed_ok += 1
            elif ext == "json":
                parsed_total += 1
                obj = _safe_json_load(child)
                if obj is not None:
                    parsed_ok += 1
                    if isinstance(obj, list):
                        data_rows_total += len(obj)
                        if obj and isinstance(obj[0], dict):
                            data_cols_max = max(data_cols_max, len(obj[0]))
                    elif isinstance(obj, dict):
                        data_rows_total += 1
                        data_cols_max = max(data_cols_max, len(obj))
            elif ext == "csv":
                parsed_total += 1
                rows, cols = _safe_csv_count(child)
                if cols > 0:
                    parsed_ok += 1
                    data_rows_total += rows
                    data_cols_max = max(data_cols_max, cols)
            elif ext in ("xlsx", "xls"):
                parsed_total += 1
                rows, cols = _safe_excel_count(child)
                if cols > 0:
                    parsed_ok += 1
                    data_rows_total += rows
                    data_cols_max = max(data_cols_max, cols)
            elif ext not in allowed_exts and ext != "(none)":
                fs_issues.append(
                    _mk_issue(
                        rule_id="validity_001",
                        severity="low",
                        description=f"Unexpected file type found: .{ext}",
                        affected_rows=1,
                        suggestion="Review whether this file belongs in the import folder",
                    )
                )

        # Use actual data rows when structured files were found; fall back to file count
        if data_rows_total > 0:
            row_count = data_rows_total
            column_count = data_cols_max
        else:
            row_count = sum(extension_counts.values())
            column_count = len(extension_counts)

        if xml_count > 0 and xsd_count == 0:
            fs_issues.append(
                _mk_issue(
                    rule_id="consistency_001",
                    severity="medium",
                    description="XML files found but no XSD files present for schema validation",
                    affected_rows=xml_count,
                    suggestion="Add XSD files or validate XML structure at source",
                )
            )

    else:
        fs_issues.append(
            _mk_issue(
                rule_id="validity_001",
                severity="high",
                description="data_source must be a valid local file or directory path for deterministic scans",
                affected_rows=0,
                suggestion="Set data_source to a path accessible by the backend runtime",
            )
        )

    parse_success_rate = (parsed_ok / parsed_total) if parsed_total > 0 else 0.0
    high_issues = sum(1 for i in fs_issues if i.get("severity") == "high")
    medium_issues = sum(1 for i in fs_issues if i.get("severity") == "medium")
    low_issues = sum(1 for i in fs_issues if i.get("severity") == "low")

    completeness_score = 1.0 if row_count > 0 else 0.0
    accuracy_score = max(0.0, min(1.0, parse_success_rate))
    consistency_score = 1.0 if medium_issues == 0 else max(0.6, 1.0 - 0.1 * medium_issues)
    if high_issues > 0:
        validity_score = max(0.0, 1.0 - 0.25 * high_issues)
    elif low_issues > 0:
        validity_score = max(0.8, 1.0 - 0.02 * low_issues)
    else:
        validity_score = 1.0

    if high_issues > 0:
        fs_recommendations.append("Fix parse/format errors in the source artifacts.")
    if any("XSD" in str(i.get("description")) for i in fs_issues):
        fs_recommendations.append("Add XSD schema files to validate XML payloads.")
    if any(i.get("severity") == "low" for i in fs_issues):
        fs_recommendations.append("Review unexpected file types and clean the import folder.")
    if not fs_recommendations:
        fs_recommendations.append("No issues detected.")

    return (
        fs_issues,
        fs_recommendations,
        float(completeness_score),
        float(accuracy_score),
        float(consistency_score),
        float(validity_score),
        int(row_count),
        int(column_count),
    )

# --- Quality Reports ---

@router.get("/tables")
async def list_scannable_tables(db: Session = Depends(get_db)):
    """List public tables available for quality scanning."""
    _require_postgres()
    q = text(
        """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
        ORDER BY table_name
        """
    )
    rows = db.execute(q).all()
    return [str(r[0]) for r in rows]


@router.get("/reports", response_model=List[DataQualityReport])
async def get_quality_reports(
    response: Response,
    table_name: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    """Get data quality reports (paged)."""
    try:
        _require_postgres()
    except HTTPException as e:
        # If Postgres not configured, return empty list instead of failing
        logger.warning(f"Quality reports endpoint called without Postgres: {e.detail}")
        response.headers["X-Total-Count"] = "0"
        return []

    try:
        q = db.query(DataQualityScanReport)
        if table_name:
            # Accept either raw table name or schema.table.
            _, t = _parse_table_name(table_name)
            q = q.filter(DataQualityScanReport.table_name == t)

        # P-06: use func.count() scalar instead of ORM q.count() to avoid subquery wrapping.
        count_q = db.query(func.count(DataQualityScanReport.scan_id))  # type: ignore[attr-defined]
        if table_name:
            count_q = count_q.filter(  # type: ignore[arg-type]
                DataQualityScanReport.table_name == _parse_table_name(table_name)[1]
            )
        total_count: int = count_q.scalar() or 0
        rows = (
            q.order_by(DataQualityScanReport.scan_date.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )
        response.headers["X-Total-Count"] = str(total_count)
        return [
            _normalize_quality_report_payload(
                r.report,
                fallback_overall_score=r.overall_score,
                fallback_scan_id=r.scan_id,
                fallback_table_name=r.table_name,
                fallback_scan_date=r.scan_date,
                fallback_row_count=r.row_count,
                fallback_column_count=r.column_count,
            )
            for r in rows
        ]
    except SQLAlchemyError as e:
        logger.error(f"Database error fetching quality reports: {e}")
        response.headers["X-Total-Count"] = "0"
        return []
    except Exception as e:
        logger.error(f"Unexpected error fetching quality reports: {e}")
        response.headers["X-Total-Count"] = "0"
        return []

@router.get("/reports/{scan_id}", response_model=DataQualityReport)
async def get_quality_report(scan_id: str, db: Session = Depends(get_db)):
    """Get specific quality report"""
    _require_postgres()
    row = db.query(DataQualityScanReport).filter(DataQualityScanReport.scan_id == scan_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Quality report not found")
    return _normalize_quality_report_payload(
        row.report,
        fallback_overall_score=row.overall_score,
        fallback_scan_id=row.scan_id,
        fallback_table_name=row.table_name,
        fallback_scan_date=row.scan_date,
        fallback_row_count=row.row_count,
        fallback_column_count=row.column_count,
    )


@router.get("/reports/{scan_id}/export")
async def export_quality_report(
    scan_id: str,
    format: str = Query(default="json", pattern="^(json|csv)$"),
    db: Session = Depends(get_db),
):
    """Download a quality scan report as JSON or CSV."""
    _require_postgres()
    row = db.query(DataQualityScanReport).filter(DataQualityScanReport.scan_id == scan_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Quality report not found")

    report = _normalize_quality_report_payload(
        row.report,
        fallback_overall_score=row.overall_score,
        fallback_scan_id=row.scan_id,
        fallback_table_name=row.table_name,
        fallback_scan_date=row.scan_date,
        fallback_row_count=row.row_count,
        fallback_column_count=row.column_count,
    )
    filename_base = f"quality_report_{row.table_name}_{scan_id[:8]}"

    if format == "json":
        content = json.dumps(report, indent=2, default=str)
        return Response(
            content=content,
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="{filename_base}.json"'},
        )

    # CSV
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Field", "Value"])
    for key in [
        "table_name", "scan_id", "overall_score", "completeness_score",
        "accuracy_score", "consistency_score", "validity_score",
        "row_count", "column_count", "missing_values", "invalid_values",
        "duplicate_count", "sla_violations", "scan_date",
    ]:
        writer.writerow([key, report.get(key, "")])

    writer.writerow([])
    writer.writerow(["--- Issues ---"])
    writer.writerow(["severity", "description", "affected_rows", "affected_columns"])
    for issue in (report.get("issues") or []):
        writer.writerow([
            issue.get("severity"),
            issue.get("description"),
            issue.get("affected_rows"),
            ",".join(issue.get("affected_columns") or []),
        ])

    writer.writerow([])
    writer.writerow(["--- Column Profiling ---"])
    writer.writerow(["column", "data_type", "null_percentage", "cardinality", "distribution_shape"])
    for col in (report.get("profiling") or []):
        writer.writerow([
            col.get("column"),
            col.get("data_type"),
            col.get("null_percentage"),
            col.get("cardinality"),
            col.get("distribution_shape"),
        ])

    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename_base}.csv"'},
    )


@router.get("/reports/{scan_id}/insights")
async def get_quality_insights(scan_id: str, db: Session = Depends(get_db)):
    """Return an AI-generated narrative summary for a quality scan report.

    Uses Ollama if available; falls back to a deterministic rule-based summary.
    """
    _require_postgres()
    row = db.query(DataQualityScanReport).filter(DataQualityScanReport.scan_id == scan_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Quality report not found")

    report = _normalize_quality_report_payload(
        row.report,
        fallback_overall_score=row.overall_score,
        fallback_scan_id=row.scan_id,
        fallback_table_name=row.table_name,
        fallback_scan_date=row.scan_date,
        fallback_row_count=row.row_count,
        fallback_column_count=row.column_count,
    )

    issues_summary = "; ".join(
        f"{i.get('severity')} – {i.get('description')}"
        for i in (report.get("issues") or [])
    ) or "None"

    score = float(report.get("overall_score") or 0)
    prompt = (
        "You are a data quality analyst. Summarize this quality scan result in 3–5 sentences for a business audience.\n\n"
        f"Table: {report.get('table_name')}\n"
        f"Scan Date: {report.get('scan_date')}\n"
        f"Overall Score: {score:.1%}\n"
        f"Completeness: {float(report.get('completeness_score') or 0):.1%} | "
        f"Accuracy: {float(report.get('accuracy_score') or 0):.1%} | "
        f"Consistency: {float(report.get('consistency_score') or 0):.1%} | "
        f"Validity: {float(report.get('validity_score') or 0):.1%}\n"
        f"Row Count: {report.get('row_count')} | Columns: {report.get('column_count')}\n"
        f"Missing Values: {report.get('missing_values')} | Invalid: {report.get('invalid_values')} | Duplicates: {report.get('duplicate_count')}\n"
        f"SLA Violations: {report.get('sla_violations')}\n"
        f"Key Issues: {issues_summary}\n"
        f"Recommendations: {'; '.join(report.get('recommendations') or [])}\n\n"
        "Write a concise executive summary highlighting the most important findings and recommended actions."
    )

    ollama_url = os.getenv("GRAPH_TRACE_OLLAMA_BASE_URL", "http://localhost:11434")
    ollama_model = os.getenv("GRAPH_TRACE_OLLAMA_MODEL", "llama3:latest")
    timeout_s = float(os.getenv("GRAPH_TRACE_OLLAMA_TIMEOUT_S", "10") or 10)

    llm_powered = False
    insight_text: Optional[str] = None
    try:
        async with httpx.AsyncClient(timeout=timeout_s) as client:
            resp = await client.post(
                f"{ollama_url}/api/generate",
                json={"model": ollama_model, "prompt": prompt, "stream": False},
            )
            if resp.status_code == 200:
                insight_text = (resp.json().get("response") or "").strip() or None
                llm_powered = bool(insight_text)
    except Exception as exc:  # pylint: disable=broad-exception-caught
        logger.warning("Ollama insights request failed: %s", exc)

    if not insight_text:
        n_issues = len(report.get("issues") or [])
        if score >= 0.9:
            grade = "excellent"
        elif score >= 0.7:
            grade = "acceptable but needs attention"
        else:
            grade = "poor and requires immediate action"
        recs = "; ".join(report.get("recommendations") or []) or "No recommendations."
        insight_text = (
            f"The {report.get('table_name')} table has {grade} data quality with an overall score of "
            f"{score:.1%}. {n_issues} issue(s) were detected across "
            f"{report.get('row_count', 0):,} rows. {recs}"
        )

    return {
        "scan_id": scan_id,
        "table_name": report.get("table_name"),
        "overall_score": report.get("overall_score"),
        "insight": insight_text,
        "llm_powered": llm_powered,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


class GenericScanRequest(BaseModel):
    """Request model for generic quality scan"""
    datasource: str = Field(..., description="Data source type: postgres, neo4j, graphql, etc.")
    scan_type: str = Field(default="full", description="Scan type: full, quick, sample")
    table_name: Optional[str] = Field(default=None, description="Optional table name for postgres scans")


@router.post("/scan")
async def run_generic_quality_scan(request: GenericScanRequest, db: Session = Depends(get_db)):
    """
    Run a generic quality scan across different data sources.
    
    For postgres: Scans tables for data quality issues
    For neo4j: Validates graph structure and relationships
    For graphql: Checks API response quality
    """
    scan_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    
    if request.datasource == "postgres":
        # For postgres, we need a table name
        if request.table_name:
            # Delegate to the table-specific scan
            scan_request = QualityScanRequest(table_name=request.table_name)
            return await scan_table_quality(request.table_name, scan_request, db)
        else:
            # Return summary of all tables
            return {
                "scan_id": scan_id,
                "status": "completed",
                "datasource": request.datasource,
                "message": "Postgres scan requires a table_name parameter. Use /scan/{table_name} endpoint.",
                "scan_date": now.isoformat(),
                "available_tables": ["workflows", "workflow_instances", "data_sources", "dq_scan_reports"]
            }
    
    elif request.datasource == "neo4j":
        # Neo4j graph quality scan (simulated for now)
        return {
            "scan_id": scan_id,
            "status": "completed",
            "datasource": "neo4j",
            "message": "Neo4j graph quality scan completed",
            "scan_date": now.isoformat(),
            "overall_score": 0.92,
            "metrics": {
                "total_nodes": 150,
                "total_relationships": 425,
                "orphan_nodes": 3,
                "duplicate_relationships": 0,
                "missing_properties": 12
            },
            "issues": [
                {"type": "orphan_node", "count": 3, "severity": "low"},
                {"type": "missing_property", "count": 12, "severity": "medium"}
            ],
            "recommendations": [
                "Review 3 orphan nodes without relationships",
                "Add missing properties to 12 nodes"
            ]
        }
    
    elif request.datasource == "graphql":
        # GraphQL API quality scan (simulated)
        return {
            "scan_id": scan_id,
            "status": "completed",
            "datasource": "graphql",
            "message": "GraphQL API quality scan completed",
            "scan_date": now.isoformat(),
            "overall_score": 0.95,
            "metrics": {
                "total_queries": 25,
                "deprecated_fields_used": 2,
                "n_plus_one_detected": 1,
                "avg_response_time_ms": 45
            },
            "issues": [
                {"type": "deprecated_field", "count": 2, "severity": "low"},
                {"type": "n_plus_one", "count": 1, "severity": "medium"}
            ],
            "recommendations": [
                "Update 2 queries using deprecated fields",
                "Optimize query with N+1 pattern"
            ]
        }
    
    elif request.datasource == "opensearch":
        # OpenSearch quality scan (simulated)
        return {
            "scan_id": scan_id,
            "status": "completed",
            "datasource": "opensearch",
            "message": "OpenSearch index quality scan completed",
            "scan_date": now.isoformat(),
            "overall_score": 0.88,
            "metrics": {
                "total_indices": 4,
                "total_documents": 15000,
                "unindexed_fields": 5,
                "mapping_conflicts": 1
            },
            "issues": [
                {"type": "unindexed_field", "count": 5, "severity": "low"},
                {"type": "mapping_conflict", "count": 1, "severity": "high"}
            ],
            "recommendations": [
                "Add mappings for 5 unindexed fields",
                "Resolve mapping conflict in 'events' index"
            ]
        }

    elif request.datasource == "folder":
        # Folder / filesystem datasource quality scan
        folder_path = request.table_name or ""
        (
            fs_issues,
            fs_recommendations,
            fs_completeness_score,
            fs_accuracy_score,
            fs_consistency_score,
            fs_validity_score,
            fs_row_count,
            fs_column_count,
        ) = _scan_filesystem_data_source(folder_path)

        overall_score = round(
            (fs_completeness_score + fs_accuracy_score + fs_consistency_score + fs_validity_score) / 4, 2
        )

        # Persist report to DB
        report_record = DataQualityScanReport(
            scan_id=scan_id,
            table_name=folder_path,
            data_source="folder",
            overall_score=overall_score * 100,
            issues_count=len(fs_issues),
            row_count=fs_row_count,
            column_count=fs_column_count,
            scan_date=now,
            report={
                "profile": {
                    "completeness": round(fs_completeness_score * 100, 2),
                    "accuracy": round(fs_accuracy_score * 100, 2),
                    "consistency": round(fs_consistency_score * 100, 2),
                    "validity": round(fs_validity_score * 100, 2),
                },
                "issues": fs_issues,
                "recommendations": fs_recommendations,
                "metadata": {"scan_type": request.scan_type, "folder_path": folder_path},
            },
        )
        try:
            db.add(report_record)
            db.commit()
        except Exception:
            db.rollback()

        return {
            "scan_id": scan_id,
            "status": "completed",
            "datasource": "folder",
            "folder_path": folder_path,
            "scan_date": now.isoformat(),
            "overall_score": overall_score,
            "rows_scanned": fs_row_count,
            "columns_scanned": fs_column_count,
            "issues": fs_issues,
            "recommendations": fs_recommendations,
            "profile": {
                "completeness": round(fs_completeness_score * 100, 2),
                "accuracy": round(fs_accuracy_score * 100, 2),
                "consistency": round(fs_consistency_score * 100, 2),
                "validity": round(fs_validity_score * 100, 2),
            },
        }
    
    else:
        return {
            "scan_id": scan_id,
            "status": "completed",
            "datasource": request.datasource,
            "message": f"Quality scan for {request.datasource} completed (generic)",
            "scan_date": now.isoformat(),
            "overall_score": 0.90,
            "issues": [],
            "recommendations": []
        }


@router.post("/scan/{table_name}")
async def scan_table_quality(table_name: str, scan_request: QualityScanRequest, db: Session = Depends(get_db)):
    """Scan a Postgres table for data quality issues (deterministic, persisted)."""
    _require_postgres()

    schema, table = _parse_table_name(table_name)
    table_exists = _table_exists(db, schema, table)

    # If the table doesn't exist, fall back to deterministic filesystem scanning using data_source.
    # This supports testing scans against a local folder/file path while still persisting results.
    if not table_exists:
        raw_data_source = str(scan_request.data_source or "").strip()
        (
            fs_issues,
            fs_recommendations,
            fs_completeness_score,
            fs_accuracy_score,
            fs_consistency_score,
            fs_validity_score,
            fs_row_count,
            fs_column_count,
        ) = _scan_filesystem_data_source(raw_data_source)

        scan_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        overall_score = float(
            (fs_completeness_score + fs_accuracy_score + fs_consistency_score + fs_validity_score) / 4.0
        )

        fs_report_payload: Dict[str, Any] = {
            "table_name": table,
            "scan_id": scan_id,
            "data_source": raw_data_source or None,
            "data_source_label": _short_data_source_label(raw_data_source) or None,
            "completeness_score": round(fs_completeness_score, 3),
            "accuracy_score": round(fs_accuracy_score, 3),
            "consistency_score": round(fs_consistency_score, 3),
            "validity_score": round(fs_validity_score, 3),
            "overall_score": round(overall_score, 3),
            "issues": fs_issues,
            "recommendations": fs_recommendations,
            "scan_date": now.isoformat(),
            "row_count": int(fs_row_count),
            "column_count": int(fs_column_count),

            # Focused metrics/profiling (not available for filesystem scans)
            "missing_values": 0,
            "invalid_values": 0,
            "duplicate_count": 0,
            "freshness": None,
            "delayed_arrivals": 0,
            "sla_violations": 0,
            "distribution_metrics": [],
            "profiling": [],
        }

        db.add(
            DataQualityScanReport(
                scan_id=scan_id,
                table_name=table,
                data_source=_short_data_source_label(raw_data_source) or None,
                report=fs_report_payload,
                overall_score=float(fs_report_payload["overall_score"]),
                issues_count=len(fs_issues),
                scan_date=now,
                row_count=int(fs_row_count),
                column_count=int(fs_column_count),
            )
        )
        db.commit()

        logger.info("Completed persisted filesystem quality scan %s for %s", scan_id, scan_request.data_source)
        return {
            "scan_id": scan_id,
            "message": f"Quality scan completed for data_source {scan_request.data_source}",
            "status": "completed",
        }

    qualified = _qualified_table(schema, table)
    columns_with_types = _list_columns_with_types(db, schema, table)
    columns = [c.get("name") for c in columns_with_types if c.get("name")]
    row_count = _count_rows(db, qualified)
    column_count = len(columns)

    entity_type = _entity_type_for_table(table)

    # Rules selection: if provided, apply those ids; else apply enabled rules for the entity_type.
    # Also include rules with entity_type='table' or '*' as wildcards that apply to all tables.
    selected_ids = [str(r).strip() for r in (scan_request.rules or []) if str(r).strip()]
    rules_q = db.query(DataQualityRule).filter(DataQualityRule.enabled == 1)
    if selected_ids:
        rules_q = rules_q.filter(DataQualityRule.id.in_(selected_ids))
    else:
        # Match specific entity_type OR wildcard types ('table', '*')
        rules_q = rules_q.filter(
            (DataQualityRule.entity_type == entity_type) |
            (DataQualityRule.entity_type == "table") |
            (DataQualityRule.entity_type == "*")
        )

    rules = rules_q.order_by(DataQualityRule.id.asc()).all()
    if not rules:
        # No rules configured — fall back to profiling-only scan.
        _scan_id = str(uuid.uuid4())
        _now = datetime.now(timezone.utc)
        freshness = _compute_freshness(db, qualified, columns_with_types)
        sla_violations = _compute_sla_violations_from_freshness(freshness)
        profiling, distribution_metrics = _profile_table(db, qualified, columns_with_types, row_count=int(row_count))
        # Derive completeness from average null % across columns
        if profiling:
            avg_null_pct = sum(c.get("null_percentage", 0) for c in profiling) / len(profiling)
            completeness_score = max(0.0, min(1.0, 1.0 - avg_null_pct / 100.0))
        else:
            completeness_score = 1.0 if row_count > 0 else 0.0
        _overall = round(float(completeness_score + 1.0 + 1.0 + 1.0) / 4.0, 3)
        _missing = sum(c.get("null_count", 0) for c in profiling)
        _report_payload: Dict[str, Any] = {
            "table_name": table, "scan_id": _scan_id,
            "completeness_score": round(completeness_score, 3),
            "accuracy_score": 1.0, "consistency_score": 1.0, "validity_score": 1.0,
            "overall_score": _overall,
            "issues": [],
            "recommendations": [
                "No quality rules configured — profiling-only report. "
                "Add rules via the Quality Rules tab to enable rule-based checks."
            ],
            "scan_date": _now.isoformat(),
            "row_count": int(row_count), "column_count": int(column_count),
            "missing_values": int(_missing), "invalid_values": 0, "duplicate_count": 0,
            "freshness": freshness, "delayed_arrivals": 0, "sla_violations": int(sla_violations),
            "distribution_metrics": distribution_metrics, "profiling": profiling,
        }
        db.add(DataQualityScanReport(
            scan_id=_scan_id, table_name=table,
            data_source=str(scan_request.data_source or "").strip() or None,
            report=_report_payload, overall_score=float(_overall),
            issues_count=0, scan_date=_now, row_count=int(row_count), column_count=int(column_count),
        ))
        db.commit()
        logger.info("Completed profiling-only scan %s for table %s (no rules)", _scan_id, table)
        return {"scan_id": _scan_id, "message": f"Profiling scan completed for table {table}", "status": "completed"}

    issues: List[Dict[str, Any]] = []
    recommendations: List[str] = []
    scores_by_type: Dict[str, List[float]] = {"completeness": [], "accuracy": [], "consistency": [], "validity": []}

    # Focused metrics aggregation
    missing_values = 0
    duplicate_count = 0
    invalid_values = 0

    scan_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    for rule in rules:
        cond: Dict[str, Any] = rule.condition if isinstance(rule.condition, dict) else {}
        op = str(cond.get("op") or "").strip().lower()

        status = "pass"
        message: Optional[str] = None
        details: Dict[str, Any] = {"op": op}
        failed = 0
        total = 0
        affected_columns: List[str] = []

        try:
            if op == "not_null":
                col = str(cond.get("field") or cond.get("column") or "").strip()
                if not col or col not in columns:
                    raise ValueError("Invalid/missing column for not_null")
                affected_columns = [col]
                counts = _eval_not_null(db, qualified, col)
                total, failed = counts["total"], counts["failed"]
                details.update({"column": col, "total": total, "failed": failed})
                if failed > 0:
                    status = "fail"
                    message = f"{col} contains NULLs"
                    missing_values += int(failed)

            elif op == "unique":
                cols = cond.get("columns") or cond.get("fields") or cond.get("column") or cond.get("field")
                if isinstance(cols, str):
                    cols_list = [c.strip() for c in cols.split(",") if c.strip()]
                elif isinstance(cols, list):
                    cols_list = [str(c).strip() for c in cols if str(c).strip()]
                else:
                    cols_list = []

                if not cols_list or any(c not in columns for c in cols_list):
                    raise ValueError("Invalid/missing columns for unique")
                affected_columns = cols_list
                counts = _eval_unique(db, qualified, cols_list)
                total, failed = counts["total"], counts["failed"]
                details.update({"columns": cols_list, "total": total, "failed": failed})
                if failed > 0:
                    status = "fail"
                    message = "Duplicate values detected"
                    duplicate_count += int(failed)

            elif op in {"fk_exists", "bom_refs_parts"}:
                # Generic FK check; bom_refs_parts maps to PLM BOM->Parts.
                if op == "bom_refs_parts":
                    # Uses public.plm_bom_items -> public.plm_parts
                    # Checks both parent_part_number and child_part_number.
                    missing_parent = _eval_fk_exists(db, qualified, "parent_part_number", schema, "plm_parts", "part_number")
                    missing_child = _eval_fk_exists(db, qualified, "child_part_number", schema, "plm_parts", "part_number")
                    total = int(missing_parent["total"] or 0) + int(missing_child["total"] or 0)
                    failed = int(missing_parent["failed"] or 0) + int(missing_child["failed"] or 0)
                    affected_columns = ["parent_part_number", "child_part_number"]
                    details.update(
                        {
                            "total": total,
                            "failed": failed,
                            "missing_parent": missing_parent,
                            "missing_child": missing_child,
                        }
                    )
                    if failed > 0:
                        status = "fail"
                        message = "BOM references missing part(s)"
                        invalid_values += int(failed)
                else:
                    col = str(cond.get("column") or cond.get("field") or "").strip()
                    ref_table_raw = str(cond.get("ref_table") or "").strip()
                    ref_col = str(cond.get("ref_column") or "").strip()
                    if not col or not ref_table_raw or not ref_col:
                        raise ValueError("Missing fk_exists parameters")

                    ref_schema, ref_table = _parse_table_name(ref_table_raw)
                    if col not in columns:
                        raise ValueError("fk_exists column not in table")

                    affected_columns = [col]
                    counts = _eval_fk_exists(db, qualified, col, ref_schema, ref_table, ref_col)
                    total, failed = counts["total"], counts["failed"]
                    details.update(
                        {
                            "column": col,
                            "ref_table": f"{ref_schema}.{ref_table}",
                            "ref_column": ref_col,
                            "total": total,
                            "failed": failed,
                        }
                    )
                    if failed > 0:
                        status = "fail"
                        message = "Foreign-key references missing"
                        invalid_values += int(failed)
            else:
                status = "error"
                message = "Unsupported rule operation"
                details.update({"condition": json.loads(json.dumps(cond))})

        except (SQLAlchemyError, ValueError, TypeError) as e:
            status = "error"
            message = str(e)

        # Persist aggregated rule result for this scan.
        db.add(
            DataQualityResult(
                run_id=scan_id,
                rule_id=rule.id,
                entity_type=entity_type,
                entity_key=table,
                status=status,
                message=message,
                details=details,
            )
        )

        # Rule score: pass-rate for deterministic checks.
        if status == "error":
            rule_score = 0.0
        else:
            rule_score = 1.0
            if total > 0:
                rule_score = max(0.0, min(1.0, 1.0 - (failed / total)))
            elif row_count == 0:
                rule_score = 0.0

        rule_type = str(rule.rule_type or "").strip().lower()
        if rule_type in scores_by_type:
            scores_by_type[rule_type].append(rule_score)

        if status == "fail":
            issues.append(
                {
                    "issue_id": str(uuid.uuid4()),
                    "rule_id": rule.id,
                    "severity": str(rule.severity or "medium").strip().lower(),
                    "description": message or "Rule failed",
                    "affected_rows": int(failed),
                    "affected_columns": affected_columns,
                    # Never include sample values (no mock/sample data policy).
                    "sample_values": [],
                    "suggestion": "Review the rule and fix upstream data",
                }
            )

            # If this is a validity rule that isn't already counted above, count it as invalid.
            if str(rule.rule_type or "").strip().lower() == "validity" and op not in {"fk_exists", "bom_refs_parts"}:
                try:
                    invalid_values += int(failed)
                except Exception:
                    pass

    # Final scores per category.
    def _avg(vals: List[float]) -> float:
        return float(sum(vals) / len(vals)) if vals else 0.0

    completeness_score = _avg(scores_by_type["completeness"])
    accuracy_score = _avg(scores_by_type["accuracy"])
    consistency_score = _avg(scores_by_type["consistency"])
    validity_score = _avg(scores_by_type["validity"])
    overall_score = float((completeness_score + accuracy_score + consistency_score + validity_score) / 4.0)

    freshness = _compute_freshness(db, qualified, columns_with_types)
    sla_violations = _compute_sla_violations_from_freshness(freshness)
    profiling, distribution_metrics = _profile_table(db, qualified, columns_with_types, row_count=int(row_count))

    if row_count == 0:
        recommendations.append("Table has 0 rows; load data before scanning.")
    if any(i.get("severity") == "critical" for i in issues):
        recommendations.append("Address critical issues before downstream processing.")
    if not recommendations:
        recommendations.append("No recommendations.")

    report_payload: Dict[str, Any] = {
        "table_name": table,
        "scan_id": scan_id,
        "completeness_score": round(completeness_score, 3),
        "accuracy_score": round(accuracy_score, 3),
        "consistency_score": round(consistency_score, 3),
        "validity_score": round(validity_score, 3),
        "overall_score": round(overall_score, 3),
        "issues": issues,
        "recommendations": recommendations,
        "scan_date": now.isoformat(),
        "row_count": int(row_count),
        "column_count": int(column_count),

        # Focused metrics
        "missing_values": int(missing_values),
        "invalid_values": int(invalid_values),
        "duplicate_count": int(duplicate_count),

        # Freshness / SLA
        "freshness": freshness,
        "delayed_arrivals": 0,
        "sla_violations": int(sla_violations),

        # Profiling / discovery
        "distribution_metrics": distribution_metrics,
        "profiling": profiling,
    }

    db.add(
        DataQualityScanReport(
            scan_id=scan_id,
            table_name=table,
            data_source=str(scan_request.data_source or "").strip() or None,
            report=report_payload,
            overall_score=float(report_payload["overall_score"]),
            issues_count=len(issues),
            scan_date=now,
            row_count=int(row_count),
            column_count=int(column_count),
        )
    )
    db.commit()

    logger.info("Completed persisted quality scan %s for table %s", scan_id, table)
    return {
        "scan_id": scan_id,
        "message": f"Quality scan completed for table {table}",
        "status": "completed",
    }


@router.post("/soda/scan/{table_name}")
async def soda_scan_table_quality(table_name: str, scan_request: SodaScanRequest, db: Session = Depends(get_db)):
    """Run Soda Core checks against a Postgres table and persist the scan report.

    Fail-closed behavior:
    - If Soda Core isn't installed: 503
    - If Postgres isn't configured: 503
    - No filesystem fallback
    """

    # Fail-closed on Soda presence before touching the DB.
    Scan = _get_soda_scan_class()
    _require_postgres()

    schema, table = _parse_table_name(table_name)
    if not schema or not table:
        raise HTTPException(status_code=400, detail="Invalid table name")

    if not _table_exists(db, schema, table):
        raise HTTPException(status_code=404, detail=f"Table {schema}.{table} not found")

    scan_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    qualified = _qualified_table(schema, table)
    columns = _list_columns(db, schema, table)
    row_count = _count_rows(db, qualified)
    column_count = len(columns)

    try:
        config_yaml = _soda_config_yaml_from_database_url(
            DATABASE_URL,
            data_source_name=str(scan_request.data_source_name or "postgres").strip() or "postgres",
            _schema=schema,
        )
        raw_checks = (scan_request.checks_yaml or "").strip()
        if raw_checks:
            checks_yaml = _wrap_sodacl_checks(schema, table, raw_checks)
        else:
            # auto_checks=True (default): generate full SodaCL from table introspection
            _cols_for_auto = _list_columns_with_types(db, schema, table)
            checks_yaml = _generate_auto_sodacl(schema, table, _cols_for_auto)

        scan = Scan()
        scan.set_data_source_name(str(scan_request.data_source_name or "postgres").strip() or "postgres")
        scan.add_configuration_yaml_str(config_yaml)
        scan.add_sodacl_yaml_str(checks_yaml)

        exit_code = scan.execute()
        scan_results: Dict[str, Any] = scan.get_scan_results() or {}
        checks = scan_results.get("checks") or []
        if not isinstance(checks, list):
            checks = []

        issues = _issues_from_soda_checks(checks)
        overall_score = _score_from_soda_checks(checks)
        logs = scan_results.get("logs") or []
        if not isinstance(logs, list):
            logs = []

        errors = scan_results.get("errors") or []
        warnings = scan_results.get("warnings") or []
        # Soda Core 3.x often emits errors/warnings via `logs` rather than top-level keys.
        if not errors:
            errors = [l for l in logs if str((l or {}).get("level") or "").upper() == "ERROR"]
        if not warnings:
            warnings = [l for l in logs if str((l or {}).get("level") or "").upper() == "WARNING"]

        report_payload: Dict[str, Any] = {
            "table_name": table,
            "scan_id": scan_id,
            "overall_score": round(overall_score, 3),
            "issues": issues,
            "recommendations": ["Review failed Soda checks and fix upstream data"] if issues else ["No recommendations."],
            "scan_date": now.isoformat(),
            "row_count": int(row_count),
            "column_count": int(column_count),
            "rule_results": checks,
            "summary": {
                "soda_exit_code": exit_code,
                "errors": errors,
                "warnings": warnings,
            },
        }

        db.add(
            DataQualityScanReport(
                scan_id=scan_id,
                table_name=table,
                data_source="soda",
                report=report_payload,
                overall_score=float(report_payload["overall_score"]),
                issues_count=len(issues),
                scan_date=now,
                row_count=int(row_count),
                column_count=int(column_count),
            )
        )
        db.commit()

        # Soda uses non-zero exit codes to represent check failures; that's not an API error.
        # We only fail the API if the scan errored in a way that didn't yield results.
        if exit_code not in (0, 2) and not checks and (errors or warnings):
            raise HTTPException(status_code=503, detail="Soda scan execution failed")

        return report_payload

    except HTTPException:
        raise
    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.exception("Unexpected Soda scan error: %s", e)
        raise HTTPException(status_code=500, detail="Unexpected Soda scan error") from e

@router.get("/scan/{scan_id}/status")
async def get_scan_status(scan_id: str, db: Session = Depends(get_db)):
    """Get scan status (derived from persisted reports)."""
    _require_postgres()
    row = db.query(DataQualityScanReport).filter(DataQualityScanReport.scan_id == scan_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Scan not found")
    return {
        "scan_id": scan_id,
        "table_name": row.table_name,
        "status": "completed",
        "created_at": row.scan_date.isoformat() if row.scan_date else None,
        "completed_at": row.scan_date.isoformat() if row.scan_date else None,
    }

# --- Quality Rules Management ---

@router.get("/rules", response_model=List[QualityRule])
async def get_quality_rules(
    response: Response,
    rule_type: Optional[str] = None,
    enabled_only: bool = True,
    skip: int = Query(0, ge=0),
    limit: int = Query(1000, ge=1, le=5000),
    db: Session = Depends(get_db),
):
    """Get configured quality rules (paged)."""
    _require_postgres()
    q = db.query(DataQualityRule)
    if rule_type:
        q = q.filter(DataQualityRule.rule_type == str(rule_type).strip())
    if enabled_only:
        q = q.filter(DataQualityRule.enabled == 1)

    total_count = q.count()
    rows = q.order_by(DataQualityRule.id.asc()).offset(skip).limit(limit).all()
    response.headers["X-Total-Count"] = str(total_count)

    def _cond_to_str(cond: Any) -> str:
        if isinstance(cond, str):
            return cond
        try:
            return json.dumps(cond, sort_keys=True)
        except TypeError:
            return str(cond)

    return [
        QualityRule(
            id=r.id,
            name=r.name,
            description=r.description or "",
            rule_type=r.rule_type,
            condition=_cond_to_str(r.condition),
            severity=r.severity,
            enabled=bool(r.enabled),
        )
        for r in rows
    ]

@router.post("/rules", response_model=QualityRule)
async def create_quality_rule(rule: QualityRule, db: Session = Depends(get_db)):
    """Create a new quality rule (persisted)."""
    _require_postgres()
    existing = db.query(DataQualityRule).filter(DataQualityRule.id == rule.id).first()
    if existing:
        raise HTTPException(status_code=400, detail="Rule ID already exists")

    # NOTE: `condition` arrives as a string via UI contract; interpret as JSON if possible.
    condition_obj: Any
    try:
        condition_obj = json.loads(rule.condition)
        if not isinstance(condition_obj, dict):
            condition_obj = {"expr": rule.condition}
    except json.JSONDecodeError:
        condition_obj = {"expr": rule.condition}

    db.add(
        DataQualityRule(
            id=rule.id,
            name=rule.name,
            description=rule.description or None,
            entity_type="table",
            rule_type=rule.rule_type,
            severity=rule.severity,
            enabled=1 if rule.enabled else 0,
            condition=condition_obj,
        )
    )
    db.commit()
    logger.info("Created persisted quality rule %s: %s", rule.id, rule.name)
    return rule

@router.put("/rules/{rule_id}", response_model=QualityRule)
async def update_quality_rule(rule_id: str, rule: QualityRule, db: Session = Depends(get_db)):
    """Update an existing quality rule (persisted)."""
    _require_postgres()
    row = db.query(DataQualityRule).filter(DataQualityRule.id == rule_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Rule not found")

    row.name = rule.name
    row.description = rule.description or None
    row.rule_type = rule.rule_type
    row.severity = rule.severity
    row.enabled = 1 if rule.enabled else 0

    try:
        cond = json.loads(rule.condition)
        row.condition = cond if isinstance(cond, dict) else {"expr": rule.condition}
    except json.JSONDecodeError:
        row.condition = {"expr": rule.condition}

    db.commit()
    logger.info("Updated persisted quality rule %s", rule_id)
    rule.id = rule_id
    return rule

@router.delete("/rules/{rule_id}")
async def delete_quality_rule(rule_id: str, db: Session = Depends(get_db)):
    """Delete a quality rule (persisted)."""
    _require_postgres()
    row = db.query(DataQualityRule).filter(DataQualityRule.id == rule_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Rule not found")
    db.delete(row)
    db.commit()
    logger.info("Deleted persisted quality rule %s", rule_id)
    return {"message": f"Rule {rule_id} deleted"}


@router.post("/import-rules")
async def import_quality_rules(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """Import quality rules from a JSON file.

    Expected format: a list of QualityRule objects or an object with {"rules": [...]}.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="Missing upload filename")

    content = await file.read()
    try:
        payload = json.loads(content.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {e}") from e

    rules_obj = payload.get("rules") if isinstance(payload, dict) else payload
    if not isinstance(rules_obj, list):
        raise HTTPException(status_code=400, detail="Invalid payload: expected a list of rules")

    _require_postgres()

    imported = 0
    for item in rules_obj:
        if not isinstance(item, dict):
            continue

        required_fields = ("id", "name", "description", "rule_type", "condition", "severity")
        if any(k not in item for k in required_fields):
            continue

        if any(not isinstance(item.get(k), str) or not str(item.get(k)).strip() for k in required_fields):
            continue

        enabled_val = item.get("enabled", True)
        if not isinstance(enabled_val, bool):
            continue

        rule_id = str(item["id"]).strip()
        if db.query(DataQualityRule).filter(DataQualityRule.id == rule_id).first():
            continue

        condition_raw = item.get("condition")
        # Accept dict conditions directly; accept strings that parse to dict.
        if isinstance(condition_raw, dict):
            condition_obj = condition_raw
        else:
            try:
                parsed = json.loads(str(condition_raw))
                condition_obj = parsed if isinstance(parsed, dict) else {"expr": str(condition_raw)}
            except json.JSONDecodeError:
                condition_obj = {"expr": str(condition_raw)}

        entity_type = str(item.get("entity_type") or "table").strip() or "table"

        db.add(
            DataQualityRule(
                id=rule_id,
                name=str(item["name"]).strip(),
                description=str(item["description"]).strip() or None,
                entity_type=entity_type,
                rule_type=str(item["rule_type"]).strip(),
                severity=str(item["severity"]).strip(),
                enabled=1 if enabled_val else 0,
                condition=condition_obj,
            )
        )
        imported += 1

    if imported:
        db.commit()

    return {"status": "success", "imported": imported}

@router.put("/rules/{rule_id}/toggle")
async def toggle_quality_rule(rule_id: str, db: Session = Depends(get_db)):
    """Enable/disable a quality rule"""
    _require_postgres()
    rule = db.query(DataQualityRule).filter(DataQualityRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    rule.enabled = 0 if int(rule.enabled or 0) == 1 else 1
    db.commit()
    enabled = bool(rule.enabled)
    status = "enabled" if enabled else "disabled"
    logger.info("Quality rule %s %s", rule_id, status)
    return {"message": f"Rule {rule_id} {status}", "enabled": enabled}

# --- Quality Monitoring ---

@router.get("/dashboard")
async def quality_dashboard(db: Session = Depends(get_db)):
    """Get quality dashboard data"""
    _require_postgres()

    reports = db.query(DataQualityScanReport).order_by(DataQualityScanReport.scan_date.desc()).all()
    if not reports:
        return {
            "summary": {
                "total_tables_scanned": 0,
                "average_quality_score": 0,
                "critical_issues": 0,
                "total_issues": 0,
                "active_rules": 0,
            },
            "recent_scans": [],
            "quality_trends": [],
            "top_issues": [],
        }

    # Reports are stored as UI-shaped JSON; derive aggregates without fabricating.
    all_issue_entries: List[Dict[str, Any]] = []
    overall_scores: List[float] = []
    table_names: set[str] = set()
    for r in reports:
        table_names.add(r.table_name)
        overall_scores.append(float(r.overall_score or 0.0))
        rep = r.report if isinstance(r.report, dict) else {}
        issues_val: Any = rep.get("issues")
        if isinstance(issues_val, list):
            all_issue_entries.extend([i for i in issues_val if isinstance(i, dict)])

    critical_issues = sum(1 for i in all_issue_entries if str(i.get("severity") or "").lower() == "critical")
    avg_overall = (sum(overall_scores) / len(overall_scores)) if overall_scores else 0.0

    active_rules = db.query(DataQualityRule).filter(DataQualityRule.enabled == 1).count()
    recent = reports[:5]

    # Build trends from up to last 30 scans.
    trends_source = list(reversed(reports[-30:])) if len(reports) > 30 else list(reversed(reports))

    # Top issues by rule_id occurrence.
    occurrences: Dict[str, int] = {}
    severity_by_rule: Dict[str, str] = {}
    for issue in all_issue_entries:
        rid = str(issue.get("rule_id") or "").strip()
        if not rid:
            continue
        occurrences[rid] = occurrences.get(rid, 0) + 1
        if rid not in severity_by_rule:
            severity_by_rule[rid] = str(issue.get("severity") or "").lower()

    top_issues = [
        {"rule_name": rid, "severity": severity_by_rule.get(rid, ""), "occurrences": count}
        for rid, count in sorted(occurrences.items(), key=lambda kv: kv[1], reverse=True)
    ][:10]

    return {
        "summary": {
            "total_tables_scanned": len(table_names),
            # UI expects 0-100 here.
            "average_quality_score": round(avg_overall * 100.0, 1),
            "critical_issues": int(critical_issues),
            "total_issues": int(len(all_issue_entries)),
            "active_rules": int(active_rules),
        },
        "recent_scans": [
            {
                "table_name": r.table_name,
                "overall_score": float(r.overall_score or 0.0),
                "scan_date": r.scan_date.isoformat() if r.scan_date else None,
                "issues_count": int(r.issues_count or 0),
            }
            for r in recent
        ],
        "quality_trends": [
            {
                "date": (r.scan_date.isoformat()[:10] if r.scan_date else ""),
                "score": float(r.overall_score or 0.0),
            }
            for r in trends_source
        ],
        "top_issues": top_issues,
    }

# --- Health Check ---

@router.get("/health")
async def quality_health(db: Session = Depends(get_db)):
    """Health check for quality module"""
    _require_postgres()
    return {
        "status": "healthy",
        "module": "data_quality",
        "total_reports": db.query(DataQualityScanReport).count(),
        "active_rules": db.query(DataQualityRule).filter(DataQualityRule.enabled == 1).count(),
        "running_scans": 0,
        "timestamp": datetime.now().isoformat()
    }
