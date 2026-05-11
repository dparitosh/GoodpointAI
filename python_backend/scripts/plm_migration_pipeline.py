"""PLM Data Migration Pipeline — GraphTrace / GoodpointAI
=============================================================
Generated artifact for the PLM Data Migration Specialist workflow.

This module implements the four canonical ETL stages that mirror the
MigrationWizard / WorkflowDetailPage execution model:

    extract()   → pull raw records from the configured source
    transform() → apply field mappings + row-level transformations
    load()      → persist canonical PLM entities to Postgres
    validate()  → run Soda Core quality gates against the loaded data

Execution can be called as a standalone script (python -m scripts.plm_migration_pipeline)
or imported and driven by _run_plm_etl_for_workflow() in workflow_manager_router.py.

UI Config → Code Mapping
─────────────────────────
  Wizard Step 1 "Connect"  →  MigrationConfig dataclass (source_id, target_id, …)
  Wizard Step 2 "Discovery" →  extract()  (data source sample + _normalize_plm_records)
  Wizard Step 3 "Map"       →  transform() (part_mapping / bom_mapping dicts)
  Wizard Step 4 "Validate"  →  validate() (Soda scan + deterministic DQ rules)
  Wizard Step 5 "Execute"   →  load()    (PLMPart / PLMBOMItem inserts)
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import sys
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

# ── Adjust the path so this script resolves the app's modules whether run
#    as `python scripts/plm_migration_pipeline.py` or as a module.
_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from models.plm_models import PLMIngestionRun, PLMStagedRecord  # noqa: E402
from models.quality_models import DataQualityGateResult  # noqa: E402

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# Configuration dataclass  (populated from Wizard Step 1 "Connect" UI fields)
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class MigrationConfig:
    """Mirrors the WorkflowInstanceCreate Pydantic model fields surfaced in
    the MigrationWizard "Connect" step (Step 1).

    UI field mapping
    ─────────────────
    workflowName       → name
    sourceSystem.id    → source_id
    sourceSystem.name  → source_name
    sourceSystem.type  → source_type   (teamcenter | windchill | filesystem | …)
    targetSystem.id    → target_id
    targetSystem.name  → target_name
    targetSystem.type  → target_type   (neo4j | postgresql | opensearch | …)
    """

    # ── Workflow identity (Wizard Step 1 "Workflow Name" field)
    name: str = "plm_migration"
    run_id: str = field(default_factory=lambda: uuid.uuid4().hex)

    # ── Source (Wizard Step 1 "Source System" selector)
    source_id: str = ""
    source_name: str = ""
    source_type: str = "filesystem"          # See WorkflowInstance.ck_valid_source_type
    source_connection: Dict[str, Any] = field(default_factory=dict)

    # ── Target (Wizard Step 1 "Target System" selector)
    target_id: str = ""
    target_name: str = ""
    target_type: str = "postgresql"          # See WorkflowInstance.ck_valid_target_type
    target_connection: Dict[str, Any] = field(default_factory=dict)

    # ── Column mappings (Wizard Step 3 "Map" — fieldMappings array)
    #    Keys are source column names; values are canonical PLM field names.
    #    Canonical PLM Part fields: part_number, name, description, classification
    part_mapping: Dict[str, str] = field(default_factory=dict)

    #    BOM mapping: source_parent → parent_part_number, source_child → child_part_number
    bom_mapping: Dict[str, str] = field(default_factory=dict)

    # ── Validation (Wizard Step 4 "Validate" — validationResults / qualityChecks)
    quality_threshold: float = 80.0           # Minimum quality score to pass gate
    max_failed_records: int = 0               # 0 = zero-tolerance for failures
    soda_checks_file: str = "scripts/checks.yml"   # Path to SodaCL file


# ──────────────────────────────────────────────────────────────────────────────
# Database helpers
# ──────────────────────────────────────────────────────────────────────────────

def _make_session(database_url: Optional[str] = None) -> Session:
    """Create a SQLAlchemy session from DATABASE_URL env var or the supplied URL.

    UI Config: populated from Admin Settings → Database Configuration
                (DB-backed config key 'database_url', decrypted by core/crypto.py)
    """
    url = database_url or os.environ.get("DATABASE_URL", "")
    if not url:
        raise EnvironmentError(
            "DATABASE_URL is not set. "
            "Set it in python_backend/.env (GRAPH_TRACE_LOAD_DOTENV=true) "
            "or supply it explicitly."
        )
    engine = create_engine(url, pool_pre_ping=True)
    Factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    return Factory()


def _content_hash(record: Dict[str, Any]) -> str:
    """SHA-256 of canonical JSON for deduplication (PLMStagedRecord.content_hash, DQ-02)."""
    canonical = json.dumps(record, sort_keys=True, default=str).encode()
    return hashlib.sha256(canonical).hexdigest()


# ──────────────────────────────────────────────────────────────────────────────
# EXTRACT — Wizard Step 2 "Discovery"
# ──────────────────────────────────────────────────────────────────────────────

def extract(config: MigrationConfig) -> pd.DataFrame:
    """Extract raw records from the configured source system.

    UI Config links
    ───────────────
    config.source_type         ← Wizard Step 1 "Source System" type selector
    config.source_connection   ← Wizard Step 1 source connection_details JSON
    config.source_id           ← data_sources.id (Admin → Data Sources page)

    Supported source_type values (mirrors WorkflowInstance.ck_valid_source_type):
      filesystem  — read CSV / JSON / XML files from a local or mounted path
      database    — execute a SQL query against a relational DB
      odata       — call an OData service (Teamcenter, Windchill, etc.)
      api / rest  — call a REST endpoint

    Returns a raw pandas DataFrame ready for transform().
    """
    src_type = (config.source_type or "").lower()
    conn = config.source_connection

    logger.info("[EXTRACT] source_id=%s type=%s", config.source_id, src_type)

    if src_type == "filesystem":
        return _extract_filesystem(conn)

    if src_type in ("database", "postgresql"):
        return _extract_database(conn)

    if src_type in ("odata", "teamcenter", "windchill", "plm"):
        return _extract_odata(conn)

    if src_type in ("api", "rest"):
        return _extract_rest(conn)

    raise NotImplementedError(
        f"Source type '{src_type}' is not yet implemented in this pipeline script. "
        "See Clarifications Needed section in the module docstring."
    )


def _extract_filesystem(conn: Dict[str, Any]) -> pd.DataFrame:
    """Read structured files from the filesystem.

    UI Config: source_connection.file_path  (DataDiscoveryPage file selector)
    """
    file_path = conn.get("file_path", "")
    if not file_path:
        raise ValueError("source_connection.file_path is required for filesystem sources")

    path = Path(file_path)
    suffix = path.suffix.lower()

    if suffix == ".csv":
        df = pd.read_csv(path, dtype=str)
    elif suffix in (".json", ".jsonl"):
        df = pd.read_json(path, lines=(suffix == ".jsonl"), dtype=str)
    elif suffix in (".xlsx", ".xls"):
        df = pd.read_excel(path, dtype=str)
    elif suffix == ".xml":
        import xmltodict
        with open(path, "rb") as fh:
            raw = xmltodict.parse(fh)
        # Flatten top-level list; heuristic mirrors _normalize_plm_records()
        records: List[Dict[str, Any]] = []
        _flatten_xml(raw, records)
        df = pd.DataFrame(records)
    else:
        raise ValueError(f"Unsupported file type '{suffix}'. Supported: csv, json, jsonl, xlsx, xls, xml")

    logger.info("[EXTRACT] filesystem: %d rows, %d columns from %s", len(df), len(df.columns), path)
    return df


def _flatten_xml(node: Any, out: List[Dict[str, Any]], depth: int = 0) -> None:
    """Recursive helper that mirrors _normalize_plm_records() logic."""
    if depth > 10:
        return
    if isinstance(node, dict):
        if any(k in node for k in ("IDENTIFIER", "identifier", "part_number", "PartNumber")):
            out.append(node)
            return
        for v in node.values():
            _flatten_xml(v, out, depth + 1)
    elif isinstance(node, list):
        for item in node:
            _flatten_xml(item, out, depth + 1)


def _extract_database(conn: Dict[str, Any]) -> pd.DataFrame:
    """Execute a SQL query against a relational database source.

    UI Config:
      source_connection.database_url  ← Admin → Data Sources → connection string
      source_connection.query         ← Wizard Step 3 custom query (optional)
      source_connection.table         ← Wizard Step 1 source table
    """
    db_url = conn.get("database_url", "")
    query = conn.get("query") or f"SELECT * FROM {conn.get('table', 'parts')}"
    if not db_url:
        raise ValueError("source_connection.database_url is required for database sources")

    engine = create_engine(db_url, pool_pre_ping=True)
    with engine.connect() as cx:
        df = pd.read_sql_query(text(query), cx)
    df = df.astype(str)
    logger.info("[EXTRACT] database: %d rows from query", len(df))
    return df


def _extract_odata(conn: Dict[str, Any]) -> pd.DataFrame:
    """Call an OData v2/v4 service (Teamcenter, Windchill, SAP PLM…).

    UI Config:
      source_connection.url           ← OData service root URL
      source_connection.entity_set    ← Entity set name (e.g., 'Items')
      source_connection.username      ← credential reference (decrypted upstream)
      source_connection.password      ← credential reference (decrypted upstream)
      source_connection.filter        ← $filter expression (optional)
    """
    import requests  # already in requirements.txt

    base_url = conn.get("url", "").rstrip("/")
    entity = conn.get("entity_set", "Items")
    odata_filter = conn.get("filter", "")

    if not base_url:
        raise ValueError("source_connection.url is required for OData sources")

    params: Dict[str, str] = {"$format": "json"}
    if odata_filter:
        params["$filter"] = odata_filter

    auth = None
    if conn.get("username"):
        auth = (conn["username"], conn.get("password", ""))

    resp = requests.get(f"{base_url}/{entity}", params=params, auth=auth, timeout=120)
    resp.raise_for_status()

    payload = resp.json()
    records = payload.get("value") or payload.get("d", {}).get("results", [])
    df = pd.DataFrame(records).astype(str)
    logger.info("[EXTRACT] odata: %d rows from %s/%s", len(df), base_url, entity)
    return df


def _extract_rest(conn: Dict[str, Any]) -> pd.DataFrame:
    """Call a generic REST/JSON endpoint.

    UI Config:
      source_connection.url      ← endpoint URL
      source_connection.headers  ← dict of HTTP headers (e.g. {"Authorization": "Bearer …"})
      source_connection.params   ← dict of query parameters
    """
    import requests

    url = conn.get("url", "")
    if not url:
        raise ValueError("source_connection.url is required for REST sources")

    resp = requests.get(
        url,
        headers=conn.get("headers") or {},
        params=conn.get("params") or {},
        timeout=120,
    )
    resp.raise_for_status()
    data = resp.json()

    # Unpack common envelope shapes
    if isinstance(data, list):
        records = data
    elif isinstance(data, dict):
        for key in ("data", "results", "items", "records", "value"):
            if isinstance(data.get(key), list):
                records = data[key]
                break
        else:
            records = [data]
    else:
        raise ValueError(f"Unexpected REST response type: {type(data)}")

    df = pd.DataFrame(records).astype(str)
    logger.info("[EXTRACT] rest: %d rows from %s", len(df), url)
    return df


# ──────────────────────────────────────────────────────────────────────────────
# TRANSFORM — Wizard Step 3 "Map"
# ──────────────────────────────────────────────────────────────────────────────

def transform(
    df: pd.DataFrame,
    config: MigrationConfig,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Apply field mappings and row-level transformations.

    UI Config links
    ───────────────
    config.part_mapping    ← Wizard Step 3 fieldMappings list
                              (source_field → target_field)
    config.bom_mapping     ← Wizard Step 3 BOM relationship mappings

    Returns
    ───────
    parts_df  : DataFrame with canonical columns (part_number, name, description, classification)
    bom_df    : DataFrame with canonical columns (parent_part_number, child_part_number, quantity)
                May be empty if no bom_mapping is configured.

    Transformation catalogue (matches WizardRuleEngine phase "pre"):
    ───────────────────────────────────────────────────────────────
      UPPER        → str.upper()
      LOWER        → str.lower()
      TRIM         → str.strip()
      NUMBER       → pd.to_numeric(..., errors='coerce')
      TIMESTAMP    → pd.to_datetime(..., errors='coerce')
      NULLIFY_EMPTY → replace empty string with NaN
    """
    logger.info("[TRANSFORM] raw columns: %s", list(df.columns))

    # ── If no mapping provided, attempt heuristic auto-mapping (mirrors
    #    _run_plm_etl_for_workflow() logic in workflow_manager_router.py)
    part_map = config.part_mapping or _infer_part_mapping(df)
    bom_map = config.bom_mapping or _infer_bom_mapping(df)

    logger.info("[TRANSFORM] part_mapping=%s  bom_mapping=%s", part_map, bom_map)

    # ── Build parts DataFrame
    parts_df = _apply_mapping(df, part_map)
    parts_df = _apply_builtin_transformations(parts_df)

    # ── Build BOM DataFrame (may be empty)
    bom_df = _apply_mapping(df, bom_map) if bom_map else pd.DataFrame(
        columns=["parent_part_number", "child_part_number", "quantity"]
    )
    if not bom_df.empty:
        bom_df = _apply_builtin_transformations(bom_df)
        if "quantity" in bom_df.columns:
            bom_df["quantity"] = pd.to_numeric(bom_df["quantity"], errors="coerce")

    logger.info(
        "[TRANSFORM] parts=%d rows, bom_items=%d rows",
        len(parts_df),
        len(bom_df),
    )
    return parts_df, bom_df


def _infer_part_mapping(df: pd.DataFrame) -> Dict[str, str]:
    """Heuristic column → canonical_field mapping.

    Mirrors the _pick() logic inside _run_plm_etl_for_workflow().
    UI equivalent: auto-suggestions shown in Wizard Step 3 AI mapping panel.
    """
    keys_l = {c.lower(): c for c in df.columns}

    def _pick(*candidates: str) -> Optional[str]:
        for c in candidates:
            if c.lower() in keys_l:
                return keys_l[c.lower()]
        return None

    mapping: Dict[str, str] = {}

    # part_number (UI: "Part Number" target field — required)
    src = _pick(
        "part_number", "partnumber", "pn", "number",
        "part no", "part_no", "part id", "part_id",
        "id", "identifier", "code",
    )
    if src:
        mapping[src] = "part_number"

    # name
    src = _pick("name", "part_name", "title", "long-name", "long_name", "longname")
    if src:
        mapping[src] = "name"

    # description
    src = _pick("description", "desc", "remarks", "comment")
    if src:
        mapping[src] = "description"

    # classification
    src = _pick("classification", "class", "category", "type")
    if src:
        mapping[src] = "classification"

    if not mapping:
        raise ValueError(
            "Cannot infer a part_mapping from source columns. "
            "Please configure explicit mappings in Wizard Step 3 → Field Mappings."
        )
    return mapping


def _infer_bom_mapping(df: pd.DataFrame) -> Dict[str, str]:
    """Heuristic BOM mapping — returns empty dict if no BOM columns detected."""
    keys_l = {c.lower(): c for c in df.columns}

    def _pick(*candidates: str) -> Optional[str]:
        for c in candidates:
            if c.lower() in keys_l:
                return keys_l[c.lower()]
        return None

    parent = _pick("parent_part_number", "parent", "parent_id", "parent_pn")
    child = _pick("child_part_number", "child", "child_id", "child_pn", "component")
    if not (parent and child):
        return {}

    mapping: Dict[str, str] = {parent: "parent_part_number", child: "child_part_number"}
    qty = _pick("quantity", "qty", "amount", "count")
    if qty:
        mapping[qty] = "quantity"
    return mapping


def _apply_mapping(df: pd.DataFrame, mapping: Dict[str, str]) -> pd.DataFrame:
    """Select + rename columns per the UI-configured fieldMappings array."""
    available = {k: v for k, v in mapping.items() if k in df.columns}
    if not available:
        return pd.DataFrame()
    return df[list(available.keys())].rename(columns=available)


_BUILTIN_TRANSFORMS = {
    # Applied unconditionally to string columns — mirrors WizardRuleEngine "TRIM"
    "trim": lambda s: s.str.strip() if hasattr(s, "str") else s,
    "nullify_empty": lambda s: s.replace("", pd.NA) if hasattr(s, "replace") else s,
    "nan_str": lambda s: s.replace("nan", pd.NA).replace("None", pd.NA) if hasattr(s, "replace") else s,
}


def _apply_builtin_transformations(df: pd.DataFrame) -> pd.DataFrame:
    """Apply safe default transformations to all string columns.

    UI equivalent: WizardRuleEngine pre-transform phase (phase='pre').
    """
    for col in df.columns:
        if df[col].dtype == object:
            df[col] = df[col].str.strip()
            df[col] = df[col].replace("", pd.NA).replace("nan", pd.NA).replace("None", pd.NA)
    return df


# ──────────────────────────────────────────────────────────────────────────────
# LOAD — Wizard Step 5 "Execute"
# ──────────────────────────────────────────────────────────────────────────────

def load(
    parts_df: pd.DataFrame,
    bom_df: pd.DataFrame,
    config: MigrationConfig,
    db: Optional[Session] = None,
) -> Dict[str, int]:
    """Persist transformed PLM entities to the target PostgreSQL store.

    UI Config links
    ───────────────
    config.run_id        ← generated; stored in workflow execution_metadata.plm_run_id
    config.target_type   ← Wizard Step 1 "Target System" type selector
                           Currently supports: postgresql (default), neo4j (stub)

    DB Tables written (mirrors models/plm_models.py):
    ──────────────────────────────────────────────────
    plm_ingestion_runs   — one row per run (run_id, source_system, target_system, status)
    plm_staged_records   — raw payload per record (DQ-01 dedup via content_hash)
    plm_parts            — canonical Part rows (part_number, name, description, classification)
    plm_bom_items        — BOM edges (parent_part_number, child_part_number, quantity)

    Returns a stats dict:  {staged, parts_written, bom_written, failed}
    """
    own_session = db is None
    if own_session:
        db = _make_session()

    stats = {"staged": 0, "parts_written": 0, "bom_written": 0, "failed": 0}

    try:
        # ── 1. Create ingestion run record
        run = PLMIngestionRun(
            id=config.run_id,
            source_system=config.source_name or config.source_id,
            target_system=config.target_name or config.target_id,
            status="running",
        )
        db.merge(run)
        db.flush()
        logger.info("[LOAD] PLMIngestionRun created: run_id=%s", config.run_id)

        # ── 2. Stage raw records (plm_staged_records, DQ-01/DQ-02)
        stats["staged"] = _stage_records(db, config.run_id, parts_df, "part")
        if not bom_df.empty:
            stats["staged"] += _stage_records(db, config.run_id, bom_df, "bom")

        # ── 3. Write canonical PLMPart rows
        stats["parts_written"], stats["failed"] = _write_parts(db, config.run_id, parts_df)

        # ── 4. Write PLMBOMItem rows (if BOM data present)
        if not bom_df.empty and "parent_part_number" in bom_df.columns:
            stats["bom_written"] = _write_bom_items(db, config.run_id, bom_df)

        # ── 5. Mark run as completed
        db.execute(
            text("UPDATE plm_ingestion_runs SET status='completed', updated_at=NOW() WHERE id=:rid"),
            {"rid": config.run_id},
        )
        db.commit()
        logger.info(
            "[LOAD] completed: staged=%d parts=%d bom=%d failed=%d",
            stats["staged"], stats["parts_written"], stats["bom_written"], stats["failed"],
        )

    except Exception:
        db.rollback()
        db.execute(
            text("UPDATE plm_ingestion_runs SET status='failed', updated_at=NOW() WHERE id=:rid"),
            {"rid": config.run_id},
        )
        db.commit()
        raise
    finally:
        if own_session:
            db.close()

    return stats


def _stage_records(db: Session, run_id: str, df: pd.DataFrame, object_type: str) -> int:
    """Insert raw records into plm_staged_records with dedup via content_hash (DQ-01/DQ-02)."""
    written = 0
    records = df.where(df.notna(), None).to_dict(orient="records")

    for rec in records:
        h = _content_hash(rec)
        exists = db.execute(
            text("SELECT 1 FROM plm_staged_records WHERE run_id=:rid AND content_hash=:h"),
            {"rid": run_id, "h": h},
        ).first()
        if exists:
            continue  # DQ-01: skip duplicate
        row = PLMStagedRecord(
            run_id=run_id,
            object_type=object_type,
            payload=rec,
            source_object_id=str(rec.get("part_number") or rec.get("parent_part_number") or ""),
            content_hash=h,
        )
        db.add(row)
        written += 1

    db.flush()
    return written


def _write_parts(db: Session, run_id: str, df: pd.DataFrame) -> Tuple[int, int]:
    """Upsert rows into plm_parts.

    UI Config: Wizard Step 3 fieldMappings — canonical target columns are
    part_number (required), name, description, classification.
    """
    written = failed = 0
    required_col = "part_number"

    if required_col not in df.columns:
        raise ValueError(
            "parts_df is missing 'part_number' column. "
            "Check your part_mapping configuration in Wizard Step 3."
        )

    records = df.where(df.notna(), None).to_dict(orient="records")
    for rec in records:
        pn = rec.get("part_number")
        if not pn or str(pn).strip() in ("", "nan", "None"):
            # DQ-03: skip records without a part number (mirrors DataQualityRule not_null check)
            failed += 1
            continue
        try:
            # ON CONFLICT update so re-runs are idempotent (idx_plm_parts_run_part is UNIQUE)
            db.execute(
                text("""
                    INSERT INTO plm_parts (run_id, part_number, name, description, classification, raw)
                    VALUES (:run_id, :pn, :name, :desc, :cls, :raw)
                    ON CONFLICT (run_id, part_number) DO UPDATE
                        SET name=EXCLUDED.name,
                            description=EXCLUDED.description,
                            classification=EXCLUDED.classification,
                            raw=EXCLUDED.raw
                """),
                {
                    "run_id": run_id,
                    "pn": str(pn),
                    "name": rec.get("name"),
                    "desc": rec.get("description"),
                    "cls": rec.get("classification"),
                    "raw": json.dumps(rec),
                },
            )
            written += 1
        except Exception as exc:
            logger.warning("[LOAD] Part insert failed pn=%s: %s", pn, exc)
            failed += 1

    db.flush()
    return written, failed


def _write_bom_items(db: Session, run_id: str, df: pd.DataFrame) -> int:
    """Upsert rows into plm_bom_items.

    UI Config: Wizard Step 3 BOM mapping →
      parent_part_number (required), child_part_number (required), quantity
    DQ-04: uniqueness on (run_id, parent_part_number, child_part_number).
    """
    written = 0
    records = df.where(df.notna(), None).to_dict(orient="records")
    for rec in records:
        parent = rec.get("parent_part_number")
        child = rec.get("child_part_number")
        if not parent or not child:
            continue
        try:
            db.execute(
                text("""
                    INSERT INTO plm_bom_items (run_id, parent_part_number, child_part_number, quantity, raw)
                    VALUES (:rid, :parent, :child, :qty, :raw)
                    ON CONFLICT (run_id, parent_part_number, child_part_number) DO UPDATE
                        SET quantity=EXCLUDED.quantity,
                            raw=EXCLUDED.raw
                """),
                {
                    "rid": run_id,
                    "parent": str(parent),
                    "child": str(child),
                    "qty": rec.get("quantity"),
                    "raw": json.dumps(rec),
                },
            )
            written += 1
        except Exception as exc:
            logger.warning("[LOAD] BOM insert failed %s→%s: %s", parent, child, exc)

    db.flush()
    return written


# ──────────────────────────────────────────────────────────────────────────────
# VALIDATE — Wizard Step 4 "Validate" + Soda Core gate
# ──────────────────────────────────────────────────────────────────────────────

def validate(
    config: MigrationConfig,
    db: Optional[Session] = None,
) -> Dict[str, Any]:
    """Run Soda Core quality gates against the loaded data.

    UI Config links
    ───────────────
    config.soda_checks_file   ← path to checks.yml (this repo: scripts/checks.yml)
    config.quality_threshold  ← Wizard Step 4 "Minimum Quality Score" slider
    config.max_failed_records ← Wizard Step 4 "Zero Tolerance" toggle

    Returns
    ───────
    {
        "passed": bool,
        "overall_score": float,      # 0–100
        "checks_passed": int,
        "checks_failed": int,
        "checks_warned": int,
        "blocked": bool,             # True if gate blocks the load
        "details": list[dict],       # Per-check results
    }
    """
    try:
        from soda.scan import Scan  # type: ignore[import-untyped]
    except ImportError:
        logger.warning("[VALIDATE] soda-core not installed — skipping Soda scan")
        return _run_deterministic_dq(config, db)

    checks_file = Path(_BACKEND_ROOT) / config.soda_checks_file
    if not checks_file.exists():
        logger.warning("[VALIDATE] checks.yml not found at %s — using deterministic DQ only", checks_file)
        return _run_deterministic_dq(config, db)

    database_url = os.environ.get("DATABASE_URL", "")
    if not database_url:
        raise EnvironmentError("DATABASE_URL must be set for Soda Core scans")

    scan = Scan()
    scan.set_scan_definition_name(f"graphtrace_plm_{config.run_id[:8]}")
    scan.set_data_source_name("graphtrace_pg")

    # Inject the DATABASE_URL as a Soda connection variable so checks.yml can
    # use variable substitution (${SODA_DB_HOST}, etc.) without hardcoded secrets.
    scan.add_variables({"run_id": config.run_id, "database_url": database_url})

    scan.add_sodacl_yaml_file(str(checks_file))
    scan.execute()

    logs = scan.get_scan_results() or {}
    checks = logs.get("checks", [])

    passed_count = sum(1 for c in checks if c.get("outcome") == "pass")
    failed_count = sum(1 for c in checks if c.get("outcome") == "fail")
    warned_count = sum(1 for c in checks if c.get("outcome") == "warn")

    total = max(len(checks), 1)
    overall_score = round(100.0 * passed_count / total, 2)
    blocked = failed_count > 0 or overall_score < config.quality_threshold

    result = {
        "passed": not blocked,
        "overall_score": overall_score,
        "checks_passed": passed_count,
        "checks_failed": failed_count,
        "checks_warned": warned_count,
        "blocked": blocked,
        "details": checks,
    }

    # Persist gate result to DB (mirrors DataQualityGateResult model)
    if db:
        _persist_gate_result(db, config, result, tool="soda")

    logger.info(
        "[VALIDATE] Soda: score=%.1f passed=%d failed=%d blocked=%s",
        overall_score, passed_count, failed_count, blocked,
    )
    return result


def _run_deterministic_dq(config: MigrationConfig, db: Optional[Session]) -> Dict[str, Any]:
    """Fallback DQ without Soda: run deterministic SQL checks directly.

    UI Config: mirrors DataQualityRule conditions stored in dq_rules table.
    """
    if db is None:
        db = _make_session()

    checks = [
        # DQ-03: part_number not null
        (
            "part_number_not_null",
            text("SELECT COUNT(*) FROM plm_parts WHERE run_id=:rid AND part_number IS NULL"),
            "fail",
        ),
        # DQ-06: name completeness ≥ 80 %
        (
            "name_completeness",
            text("""
                SELECT CASE WHEN COUNT(*) = 0 THEN 0
                       ELSE 100.0 * SUM(CASE WHEN name IS NOT NULL AND name <> '' THEN 1 ELSE 0 END) / COUNT(*)
                       END
                FROM plm_parts WHERE run_id=:rid
            """),
            "warn",
        ),
        # DQ-07: no duplicate part numbers in same run
        (
            "no_duplicate_part_numbers",
            text("""
                SELECT COUNT(*) FROM (
                    SELECT part_number, COUNT(*) cnt FROM plm_parts WHERE run_id=:rid
                    GROUP BY part_number HAVING COUNT(*) > 1
                ) dups
            """),
            "fail",
        ),
        # DQ-04: BOM uniqueness (parent, child per run)
        (
            "bom_no_duplicate_edges",
            text("""
                SELECT COUNT(*) FROM (
                    SELECT parent_part_number, child_part_number, COUNT(*) cnt
                    FROM plm_bom_items WHERE run_id=:rid
                    GROUP BY parent_part_number, child_part_number HAVING COUNT(*) > 1
                ) dups
            """),
            "fail",
        ),
    ]

    results = []
    passed = failed = warned = 0

    for name, query, severity in checks:
        val = db.execute(query, {"rid": config.run_id}).scalar() or 0
        # Checks that count violations → pass when 0
        ok = float(val) == 0.0 if severity in ("fail", "warn") else float(val) >= 80.0
        outcome = "pass" if ok else severity
        results.append({"check": name, "value": float(val), "outcome": outcome})

        if outcome == "pass":
            passed += 1
        elif outcome == "fail":
            failed += 1
        else:
            warned += 1

    total = max(len(results), 1)
    overall_score = round(100.0 * passed / total, 2)
    blocked = failed > 0 or overall_score < config.quality_threshold

    result = {
        "passed": not blocked,
        "overall_score": overall_score,
        "checks_passed": passed,
        "checks_failed": failed,
        "checks_warned": warned,
        "blocked": blocked,
        "details": results,
    }

    if db:
        _persist_gate_result(db, config, result, tool="deterministic")

    return result


def _persist_gate_result(
    db: Session,
    config: MigrationConfig,
    result: Dict[str, Any],
    tool: str,
) -> None:
    """Persist DataQualityGateResult row (mirrors quality_models.DataQualityGateResult)."""
    try:
        gate = DataQualityGateResult(
            id=uuid.uuid4().hex,
            run_id=config.run_id,
            stage="transformed",
            tool=tool,
            table_name="public.plm_parts",
            status="pass" if result.get("passed") else "fail",
            overall_score=result.get("overall_score"),
            issues_count=result.get("checks_failed", 0) + result.get("checks_warned", 0),
            details=result,
        )
        db.add(gate)
        db.commit()
    except Exception as exc:
        logger.warning("[VALIDATE] Could not persist gate result: %s", exc)
        try:
            db.rollback()
        except Exception:
            pass


# ──────────────────────────────────────────────────────────────────────────────
# Orchestrator — run all four stages in sequence
# ──────────────────────────────────────────────────────────────────────────────

def run_migration(config: MigrationConfig) -> Dict[str, Any]:
    """Run the full Extract → Transform → Load → Validate pipeline.

    This mirrors _run_plm_etl_for_workflow() in workflow_manager_router.py
    but is callable standalone without the FastAPI / asyncio runtime.

    Progress stages map to WorkflowStage enum:
      EXTRACTING   (0 – 25 %)
      TRANSFORMING (25 – 55 %)
      LOADING      (55 – 80 %)   ← corresponds to WorkflowStage.LOADING
      VALIDATING   (80 – 100 %)
    """
    db = _make_session()
    summary: Dict[str, Any] = {"run_id": config.run_id, "status": "failed"}

    try:
        logger.info("=== PLM Migration START run_id=%s ===", config.run_id)

        # Extract
        raw_df = extract(config)
        logger.info("[PIPELINE] Extract complete: %d rows", len(raw_df))

        # Transform
        parts_df, bom_df = transform(raw_df, config)
        logger.info("[PIPELINE] Transform complete: %d parts, %d BOM items", len(parts_df), len(bom_df))

        # Load
        stats = load(parts_df, bom_df, config, db=db)
        logger.info("[PIPELINE] Load complete: %s", stats)

        # Validate
        dq = validate(config, db=db)
        logger.info("[PIPELINE] Validate complete: score=%.1f blocked=%s", dq["overall_score"], dq["blocked"])

        summary = {
            "run_id": config.run_id,
            "status": "completed" if not dq["blocked"] else "blocked_by_dq",
            "extract_rows": len(raw_df),
            "stats": stats,
            "quality": dq,
        }

    except Exception as exc:
        logger.exception("[PIPELINE] Migration failed: %s", exc)
        summary["error"] = str(exc)
    finally:
        db.close()

    return summary


# ──────────────────────────────────────────────────────────────────────────────
# CLI entry point
# ──────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(name)s  %(message)s")

    parser = argparse.ArgumentParser(description="PLM Data Migration Pipeline — GraphTrace")
    parser.add_argument("--source-type", default="filesystem", help="Source system type")
    parser.add_argument("--source-file", default="", help="File path (filesystem sources)")
    parser.add_argument("--source-url", default="", help="URL (OData / REST sources)")
    parser.add_argument("--source-db-url", default="", help="Database URL (database sources)")
    parser.add_argument("--source-table", default="parts", help="Table name (database sources)")
    parser.add_argument("--target-type", default="postgresql", help="Target system type")
    parser.add_argument("--name", default="cli_migration", help="Workflow name")
    parser.add_argument("--quality-threshold", type=float, default=80.0, help="Min quality score to pass (0-100)")
    args = parser.parse_args()

    src_conn: Dict[str, Any] = {}
    if args.source_file:
        src_conn["file_path"] = args.source_file
    if args.source_url:
        src_conn["url"] = args.source_url
    if args.source_db_url:
        src_conn["database_url"] = args.source_db_url
        src_conn["table"] = args.source_table

    cfg = MigrationConfig(
        name=args.name,
        source_type=args.source_type,
        source_connection=src_conn,
        target_type=args.target_type,
        quality_threshold=args.quality_threshold,
    )

    result = run_migration(cfg)
    print(json.dumps(result, indent=2, default=str))
    sys.exit(0 if result.get("status") == "completed" else 1)
