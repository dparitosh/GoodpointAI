"""
DataProfilerAgent  —  port 8031
================================
LLM Tool Prompt contract for semantic dataset profiling:

  Analyze the provided dataset profiles and infer:
    - Column semantic meaning  (e.g., part_id, supplier_id)
    - Potential relationships  between datasets
    - Entity classification    (Part, BOM, Supplier, Document)

  Use statistical signals:
    - High cardinality → identifier
    - Shared values across files → relationships
    - Similar column names → schema alignment

  Return structured insights with confidence scores.

Embedded across:
  ChatCoordinator  — intent routing ("semantic profile", "infer columns", …)
  TaskDecomposer   — Layer 2.5 node in PLM profiling DAG
  DataProfilerAgent — this file, the analysis core
  ReportingAgent   — consumes `semantic_insights` from payload
"""
from __future__ import annotations

import logging
import os
import sys
import uuid
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
from dotenv import load_dotenv
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

env_path = Path(__file__).resolve().parent.parent.parent / "python_backend" / ".env"
load_dotenv(dotenv_path=env_path)

from agent_services.base.agent_service import AgentService
from agent_services.base.models import AgentCapability, AgentTaskRequest, AgentType

logger = logging.getLogger("data_profiler")

# ── Semantic vocabulary ────────────────────────────────────────────────────────

# entity_type → canonical column name fragments
_ENTITY_SIGNALS: Dict[str, List[str]] = {
    "Part": [
        "part", "item", "component", "assembly", "pn", "part_no",
        "part_number", "part_id", "item_id", "item_no",
    ],
    "BOM": [
        "bom", "bill_of_material", "bill of material", "parent", "child",
        "qty", "quantity", "level", "bom_line", "bom_id", "structure",
    ],
    "Supplier": [
        "supplier", "vendor", "manufacturer", "mfr", "source",
        "supplier_id", "vendor_id", "mfr_id", "mfr_code",
    ],
    "Document": [
        "doc", "document", "drawing", "dwg", "spec", "specification",
        "doc_id", "doc_no", "drawing_no", "revision", "rev",
    ],
    "ECO": [
        "eco", "change_order", "engineering_change", "eco_id",
        "ec_no", "change", "change_id",
    ],
    "Revision": [
        "revision", "rev", "version", "ver", "release", "effectivity",
        "effective_date", "rev_id",
    ],
}

# Semantic role → column name patterns
_ROLE_SIGNALS: Dict[str, List[str]] = {
    "identifier":    ["_id", "_no", "_number", "_key", "_pk", "_code", "_ref", "id", "no"],
    "foreign_key":   ["_fk", "_ref", "_id", "_no", "_code", "parent_", "child_"],
    "name":          ["_name", "name", "label", "title", "description", "desc", "text"],
    "date":          ["_date", "_time", "_at", "_on", "date", "time", "created", "modified", "updated"],
    "quantity":      ["qty", "quantity", "amount", "count", "total", "num_", "number_of"],
    "status":        ["status", "state", "flag", "active", "enabled", "type", "category"],
    "metric":        ["_rate", "_ratio", "_pct", "_percent", "_score", "_value", "_amount"],
}

# Canonical name mapping — normalize common variants to a preferred form
_CANONICAL_MAP: Dict[str, str] = {
    "part_no":      "part_number",
    "pn":           "part_number",
    "item_no":      "item_number",
    "mfr":          "manufacturer",
    "mfr_code":     "manufacturer_code",
    "dwg":          "drawing_number",
    "rev":          "revision",
    "qty":          "quantity",
    "desc":         "description",
    "dt":           "date",
}

# ── Pure helpers ───────────────────────────────────────────────────────────────

def _name_similarity(a: str, b: str) -> float:
    """Normalised edit-distance similarity in [0, 1]."""
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def _column_names_from_profiles(file_profiles: List[Dict[str, Any]]) -> Dict[str, List[str]]:
    """Return {file_path: [column_names]} from file_profiles."""
    result: Dict[str, List[str]] = {}
    for fp in file_profiles:
        fname = fp.get("file") or fp.get("file_path") or fp.get("source") or ""
        cols: List[str] = []
        for c in fp.get("columns", []):
            if isinstance(c, str):
                name = c.strip()
            else:
                name = (c.get("name") or c.get("column_name") or "").strip()
            if name:
                cols.append(name)
        if not cols and fp.get("column_names"):
            cols = list(fp["column_names"])
        if fname:
            result[fname] = cols
    return result


def _infer_column_semantics(
    column_name: str,
    dtype: str = "",
    cardinality_ratio: float = 0.0,
    null_rate: float = 0.0,
) -> Dict[str, Any]:
    """
    LLM TOOL PROMPT logic (statistical signals):
    - High cardinality → identifier
    - _id / _no suffix → foreign/primary key candidate
    - Similar name fragments → entity classification
    Returns: {semantic_role, entity_hint, canonical_name, confidence, signals}
    """
    col_lower = column_name.lower()

    # Statistical signal: cardinality
    cardinality_signal  = "high"  if cardinality_ratio >= 0.9 else \
                          "medium" if cardinality_ratio >= 0.3 else "low"

    # Role inference — score each role by matching suffix/prefix fragments
    role_scores: Dict[str, float] = {r: 0.0 for r in _ROLE_SIGNALS}
    for role, patterns in _ROLE_SIGNALS.items():
        for pat in patterns:
            if col_lower == pat or col_lower.startswith(pat) or col_lower.endswith(pat):
                role_scores[role] += 0.4
            elif pat in col_lower:
                role_scores[role] += 0.2

    # Boost identifier score with cardinality signal
    if cardinality_signal == "high":
        role_scores["identifier"] = min(1.0, role_scores["identifier"] + 0.35)
        role_scores["foreign_key"] = min(1.0, role_scores["foreign_key"] + 0.20)

    # Numeric dtype → metric hint
    if dtype.lower() in ("int", "integer", "bigint", "float", "double", "decimal", "numeric"):
        role_scores["quantity"] = min(1.0, role_scores["quantity"] + 0.15)
        role_scores["metric"]   = min(1.0, role_scores["metric"] + 0.10)

    # Date dtype → date hint
    if "date" in dtype.lower() or "time" in dtype.lower() or "timestamp" in dtype.lower():
        role_scores["date"] = min(1.0, role_scores["date"] + 0.50)

    best_role  = max(role_scores, key=lambda r: role_scores[r])
    role_conf  = round(role_scores[best_role], 3)

    # Entity hint — find which entity type column name best signals
    entity_scores: Dict[str, float] = {e: 0.0 for e in _ENTITY_SIGNALS}
    for entity, tokens in _ENTITY_SIGNALS.items():
        for tok in tokens:
            if tok in col_lower:
                entity_scores[entity] += 0.5
            elif _name_similarity(tok, col_lower) >= 0.80:
                entity_scores[entity] += 0.3

    best_entity = max(entity_scores, key=lambda e: entity_scores[e])
    entity_conf = round(entity_scores[best_entity], 3)

    # Canonical name lookup
    canonical = _CANONICAL_MAP.get(col_lower, col_lower)

    # Overall confidence
    confidence = round(
        0.4 * min(role_conf, 1.0) +
        0.3 * min(entity_conf, 1.0) +
        0.3 * (1.0 - null_rate),
        3,
    )

    return {
        "column":        column_name,
        "canonical_name": canonical,
        "semantic_role": best_role if role_conf > 0.1 else "unknown",
        "entity_hint":   best_entity if entity_conf > 0.1 else "unknown",
        "confidence":    confidence,
        "signals": {
            "cardinality":          cardinality_signal,
            "null_rate":            round(null_rate, 3),
            "dtype":                dtype or "unknown",
            "role_score":           role_conf,
            "entity_score":         entity_conf,
        },
    }


def _infer_file_entity_class(
    file_path: str,
    column_semantics: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Classify a file as Part / BOM / Supplier / Document / ECO / Revision
    using entity_hint votes from its column-level semantic analysis.
    Returns: {entity_class, confidence, vote_breakdown, reasoning}
    """
    votes: Dict[str, float] = {e: 0.0 for e in _ENTITY_SIGNALS}

    for cs in column_semantics:
        hint = cs.get("entity_hint", "unknown")
        conf = cs.get("confidence", 0.0)
        if hint in votes:
            votes[hint] += conf

    # Normalise
    total = sum(votes.values()) or 1.0
    normalised = {e: round(v / total, 3) for e, v in votes.items()}

    best = max(normalised, key=lambda e: normalised[e])
    best_score = normalised[best]

    # Derive from file name if no votes are convincing
    fname_lower = Path(file_path).stem.lower()
    if best_score < 0.30:
        for entity, tokens in _ENTITY_SIGNALS.items():
            for tok in tokens:
                if tok in fname_lower:
                    best       = entity
                    best_score = max(best_score, 0.45)
                    break

    # Build reasoning string
    top3 = sorted(normalised.items(), key=lambda x: -x[1])[:3]
    reasoning = "; ".join(f"{e}={s:.0%}" for e, s in top3 if s > 0.0)

    return {
        "file":         file_path,
        "entity_class": best,
        "confidence":   round(best_score, 3),
        "vote_breakdown": normalised,
        "reasoning":    reasoning or "no strong signal",
    }


def _detect_cross_file_relationships(
    file_columns: Dict[str, List[str]],
    min_similarity: float = 0.85,
) -> List[Dict[str, Any]]:
    """
    LLM TOOL PROMPT — Shared values / similar column names → relationships.

    For every pair of (file_a, col_a) × (file_b, col_b) where name_similarity
    meets the threshold, emit a candidate relationship.

    Returns list of {from_file, from_column, to_file, to_column, similarity,
                     relationship_type, confidence}
    """
    files = list(file_columns.keys())
    relationships: List[Dict[str, Any]] = []
    seen: set = set()

    for i, fa in enumerate(files):
        for fb in files[i + 1:]:
            for ca in file_columns[fa]:
                for cb in file_columns[fb]:
                    sim = _name_similarity(ca, cb)
                    if sim < min_similarity:
                        continue
                    key = (fa, ca, fb, cb)
                    if key in seen:
                        continue
                    seen.add(key)

                    ca_l, cb_l = ca.lower(), cb.lower()
                    # Relationship type heuristic
                    if ca_l == cb_l:
                        rel_type = "exact_column_match"
                        conf = round(min(1.0, sim + 0.10), 3)
                    elif any(s in ca_l or s in cb_l
                             for s in ("_id", "_no", "_fk", "_key", "_ref")):
                        rel_type = "foreign_key_candidate"
                        conf = round(sim * 0.90, 3)
                    else:
                        rel_type = "schema_alignment"
                        conf = round(sim * 0.75, 3)

                    relationships.append({
                        "from_file":         fa,
                        "from_column":       ca,
                        "to_file":           fb,
                        "to_column":         cb,
                        "similarity":        round(sim, 3),
                        "relationship_type": rel_type,
                        "confidence":        conf,
                    })

    # Sort: exact matches first, then by confidence desc
    relationships.sort(key=lambda r: (-int(r["relationship_type"] == "exact_column_match"),
                                      -r["confidence"]))
    return relationships[:200]   # cap to prevent payload explosion


def _build_semantic_insights(
    file_profiles:     List[Dict[str, Any]],
    column_corpus:     List[Dict[str, Any]],
    entity_inference:  Dict[str, Any],
) -> Dict[str, Any]:
    """
    Aggregate column semantics + entity classification + cross-file
    relationships into the `semantic_insights` block consumed by ReportingAgent.

    Output shape:
    {
        "column_semantics":       [{column, canonical_name, semantic_role,
                                    entity_hint, confidence, signals}, …],
        "entity_classifications": [{file, entity_class, confidence,
                                    vote_breakdown, reasoning}, …],
        "cross_file_relationships": [{from_file, from_column, to_file,
                                      to_column, similarity,
                                      relationship_type, confidence}, …],
        "schema_alignment_groups":  [{representative_col, aligned_cols,
                                      avg_similarity, files}, …],
        "summary": {
            "total_columns_analysed",    "high_confidence_semantics",
            "entity_class_distribution", "relationship_count",
            "top_entity_class",
        }
    }
    """
    # ── Per-column semantics from corpus ──────────────────────────────────
    col_semantics: List[Dict[str, Any]] = []
    for entry in column_corpus:
        cname    = entry.get("column_name") or entry.get("name") or ""
        dtype    = entry.get("dtype") or entry.get("data_type") or ""
        card     = float(entry.get("cardinality_ratio", 0.0))
        null_r   = float(entry.get("null_rate", 0.0))
        if cname:
            col_semantics.append(_infer_column_semantics(cname, dtype, card, null_r))

    # ── Per-column semantics from file profile columns (fill gaps) ────────
    already: set = {cs["column"].lower() for cs in col_semantics}
    for fp in file_profiles:
        for col in fp.get("columns", []):
            if isinstance(col, str):
                cname = col
            else:
                cname = col.get("name") or col.get("column_name") or ""
            if cname and cname.lower() not in already:
                dtype  = col.get("dtype") or col.get("data_type") or "" if isinstance(col, dict) else ""
                card   = float(col.get("cardinality_ratio", 0.0)) if isinstance(col, dict) else 0.0
                null_r = float(col.get("null_rate", 0.0)) if isinstance(col, dict) else 0.0
                col_semantics.append(_infer_column_semantics(cname, dtype, card, null_r))
                already.add(cname.lower())

    # ── Per-file entity classification ────────────────────────────────────
    file_columns = _column_names_from_profiles(file_profiles)
    entity_classifications: List[Dict[str, Any]] = []

    # Use entity_inference output from TaskDecomposer Layer 5 if provided
    known_classes: Dict[str, str] = {}
    for inf in entity_inference.get("entity_assignments", []):
        known_classes[inf.get("file", "")] = inf.get("entity_class", "")

    for fpath, cols in file_columns.items():
        file_col_semantics = [
            cs for cs in col_semantics if cs["column"].lower() in {c.lower() for c in cols}
        ]
        ec = _infer_file_entity_class(fpath, file_col_semantics)
        # Override with confirmed assignment from DAG Layer 5
        if fpath in known_classes:
            ec["entity_class"] = known_classes[fpath]
            ec["confidence"]   = max(ec["confidence"], 0.80)
            ec["reasoning"]   += " (confirmed by schema_intelligence layer)"
        entity_classifications.append(ec)

    # ── Cross-file relationship detection ─────────────────────────────────
    cross_file_rels = _detect_cross_file_relationships(file_columns)

    # ── Schema alignment groups ────────────────────────────────────────────
    # Group columns by high similarity into alignment clusters
    alignment_groups: List[Dict[str, Any]] = []
    processed: set = set()
    for cs in col_semantics:
        rep = cs["column"]
        if rep.lower() in processed:
            continue
        group = [rep]
        group_files: set = set()
        for fpath, cols in file_columns.items():
            if rep.lower() in {c.lower() for c in cols}:
                group_files.add(fpath)
        similarities: List[float] = [1.0]
        for other in col_semantics:
            if other["column"] == rep or other["column"].lower() in processed:
                continue
            sim = _name_similarity(rep, other["column"])
            if sim >= 0.85 and sim < 1.0:
                group.append(other["column"])
                similarities.append(sim)
                processed.add(other["column"].lower())
        if len(group) > 1:
            alignment_groups.append({
                "representative_col": cs["canonical_name"],
                "aligned_cols":       group,
                "avg_similarity":     round(sum(similarities) / len(similarities), 3),
                "files":              sorted(group_files),
            })
        processed.add(rep.lower())

    # ── Summary ───────────────────────────────────────────────────────────
    high_conf = sum(1 for cs in col_semantics if cs["confidence"] >= 0.65)
    entity_dist: Dict[str, int] = {}
    for ec in entity_classifications:
        cls = ec["entity_class"]
        entity_dist[cls] = entity_dist.get(cls, 0) + 1
    top_entity = max(entity_dist, key=lambda e: entity_dist[e]) if entity_dist else "unknown"

    return {
        "column_semantics":         col_semantics,
        "entity_classifications":   entity_classifications,
        "cross_file_relationships": cross_file_rels,
        "schema_alignment_groups":  alignment_groups,
        "summary": {
            "total_columns_analysed":    len(col_semantics),
            "high_confidence_semantics": high_conf,
            "entity_class_distribution": entity_dist,
            "relationship_count":        len(cross_file_rels),
            "top_entity_class":          top_entity,
        },
    }


# ── LLM tool call helper ───────────────────────────────────────────────────────

async def _invoke_agent(agent_name: str, task_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Fire-and-forget agent HTTP call — returns {} on failure."""
    base_urls: Dict[str, str] = {
        "data_discovery": os.getenv("DATA_DISCOVERY_URL", "http://127.0.0.1:8026"),
        "schema_correlator": os.getenv("SCHEMA_CORRELATOR_URL", "http://127.0.0.1:8028"),
    }
    url = base_urls.get(agent_name)
    if not url:
        return {}
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                f"{url}/execute",
                json={
                    "task_id":   f"dp_{uuid.uuid4().hex[:8]}",
                    "task_type": task_type,
                    "payload":   payload,
                    "priority":  7,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("result", data)
    except Exception as exc:   # noqa: BLE001
        logger.warning("DataProfiler → %s/%s failed: %s", agent_name, task_type, exc)
        return {}


# ── Request model ─────────────────────────────────────────────────────────────

class ProfileRequest(BaseModel):
    """Payload accepted by POST /profile and process_task('semantic_profile')."""

    source_name:      Optional[str] = None
    folder_path:      Optional[str] = None
    file_profiles:    List[Dict[str, Any]] = Field(default_factory=list)
    column_corpus:    List[Dict[str, Any]] = Field(default_factory=list)
    entity_inference: Dict[str, Any]       = Field(default_factory=dict)
    # Statistical thresholds
    min_relationship_similarity: float = Field(default=0.85, ge=0.5, le=1.0)
    entity_confidence_threshold: float = Field(default=0.30, ge=0.0, le=1.0)
    # If True, enrich input by calling SchemaCorrelator for column corpus
    enrich_from_schema_correlator: bool = False
    # If True, fetch live profiles from DataDiscovery
    fetch_live_profiles: bool = False
    sample_rows: int = Field(default=500, ge=1, le=10_000)


# ── Agent class ───────────────────────────────────────────────────────────────

class DataProfilerAgent(AgentService):
    """
    Semantic dataset profiling agent.

    Implements the LLM TOOL PROMPT contract:
      Analyze dataset profiles → infer column semantics, relationships,
      entity classification (Part/BOM/Supplier/Document/ECO/Revision).

    Capabilities
    ────────────
    semantic_profile        — full analysis pipeline (main entry point)
    infer_column_semantics  — column-level semantic role + entity hint
    classify_entities       — per-file entity classification
    detect_relationships    — cross-file column similarity relationships
    align_schemas           — schema alignment group detection
    """

    def __init__(self) -> None:
        super().__init__(
            agent_type=AgentType.DATA_PROFILER,
            agent_name="Data Profiler Agent",
            port=8031,
        )
        self._register_extra_routes()

    def _register_extra_routes(self) -> None:
        @self.app.post("/profile")
        async def profile_endpoint(req: ProfileRequest):
            try:
                result = await self._run_profile(req)
                return JSONResponse(content=result)
            except Exception as exc:   # noqa: BLE001
                logger.exception("DataProfiler /profile error")
                return JSONResponse(status_code=500, content={"error": str(exc)})

    def get_capabilities(self) -> List[AgentCapability]:
        return [
            AgentCapability(
                name="semantic_profile",
                description=(
                    "Analyze dataset profiles and infer column semantic meaning, "
                    "cross-file relationships, and entity classification "
                    "(Part, BOM, Supplier, Document, ECO, Revision) with confidence scores"
                ),
            ),
            AgentCapability(
                name="infer_column_semantics",
                description=(
                    "For each column: infer semantic role (identifier, FK, name, date, …), "
                    "entity hint, and canonical name using statistical cardinality + null-rate signals"
                ),
            ),
            AgentCapability(
                name="classify_entities",
                description=(
                    "Vote-based file-level entity classification: "
                    "Part / BOM / Supplier / Document / ECO / Revision"
                ),
            ),
            AgentCapability(
                name="detect_relationships",
                description=(
                    "Detect cross-file FK/alignment relationships using column name similarity ≥ threshold"
                ),
            ),
            AgentCapability(
                name="align_schemas",
                description=(
                    "Group semantically equivalent column names across files into alignment clusters"
                ),
            ),
        ]

    async def process_task(self, task: AgentTaskRequest) -> Dict[str, Any]:
        logger.info("DataProfilerAgent received task %s (type=%s)", task.task_id, task.task_type)
        cap = task.payload.get("capability", task.task_type)

        # Build a ProfileRequest from the task payload
        req_fields = {k: v for k, v in task.payload.items()
                      if k in ProfileRequest.model_fields}
        req = ProfileRequest(**req_fields)

        if cap in ("infer_column_semantics",):
            return self._handle_column_semantics(task.payload)

        if cap in ("classify_entities",):
            return self._handle_classify_entities(req)

        if cap in ("detect_relationships",):
            return self._handle_detect_relationships(req)

        if cap in ("align_schemas",):
            return self._handle_align_schemas(req)

        # Default: full semantic_profile pipeline
        return await self._run_profile(req)

    # ── Capability handlers ───────────────────────────────────────────────────

    def _handle_column_semantics(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        columns = payload.get("columns", [])
        results = []
        for col in columns:
            if isinstance(col, str):
                results.append(_infer_column_semantics(col))
            else:
                results.append(_infer_column_semantics(
                    col.get("name") or col.get("column_name") or "",
                    col.get("dtype", ""),
                    float(col.get("cardinality_ratio", 0.0)),
                    float(col.get("null_rate", 0.0)),
                ))
        return {"column_semantics": results, "count": len(results)}

    def _handle_classify_entities(self, req: ProfileRequest) -> Dict[str, Any]:
        file_columns = _column_names_from_profiles(req.file_profiles)
        col_semantics = [
            _infer_column_semantics(
                e.get("column_name") or e.get("name") or "",
                e.get("dtype", ""),
                float(e.get("cardinality_ratio", 0.0)),
                float(e.get("null_rate", 0.0)),
            )
            for e in req.column_corpus
            if e.get("column_name") or e.get("name")
        ]
        classifications = [
            _infer_file_entity_class(fp, col_semantics)
            for fp in file_columns
        ]
        return {"entity_classifications": classifications, "count": len(classifications)}

    def _handle_detect_relationships(self, req: ProfileRequest) -> Dict[str, Any]:
        file_columns = _column_names_from_profiles(req.file_profiles)
        rels = _detect_cross_file_relationships(file_columns, req.min_relationship_similarity)
        return {"cross_file_relationships": rels, "count": len(rels)}

    def _handle_align_schemas(self, req: ProfileRequest) -> Dict[str, Any]:
        insights = _build_semantic_insights(req.file_profiles, req.column_corpus, req.entity_inference)
        return {
            "schema_alignment_groups": insights["schema_alignment_groups"],
            "count": len(insights["schema_alignment_groups"]),
        }

    async def _run_profile(self, req: ProfileRequest) -> Dict[str, Any]:
        """
        Full LLM TOOL PROMPT pipeline:
          1. Optionally enrich with live SchemaCorrelator corpus
          2. Optionally fetch live DataDiscovery profiles
          3. Run column semantics + entity classification + relationship detection
          4. Return semantic_insights dict
        """
        file_profiles = list(req.file_profiles)
        column_corpus = list(req.column_corpus)
        entity_inference = dict(req.entity_inference)

        # Step 1: enrich column corpus from SchemaCorrelator if requested
        if req.enrich_from_schema_correlator and not column_corpus:
            sc_result = await _invoke_agent(
                "schema_correlator", "schema_correlation",
                {
                    "capability":       "correlate_schemas",
                    "folder_path":      req.folder_path or req.source_name or "",
                    "include_corpus":   True,
                    "sample_rows":      req.sample_rows,
                },
            )
            if sc_result.get("column_corpus"):
                column_corpus = sc_result["column_corpus"]
            if sc_result.get("file_profiles") and not file_profiles:
                file_profiles = sc_result["file_profiles"]

        # Step 2: fetch live profiles if requested
        if req.fetch_live_profiles and not file_profiles:
            dd_result = await _invoke_agent(
                "data_discovery", "data_discovery",
                {
                    "capability":   "profile_files",
                    "folder_path":  req.folder_path or req.source_name or "",
                    "sample_rows":  req.sample_rows,
                    "include_stats": True,
                },
            )
            if dd_result.get("file_profiles"):
                file_profiles = dd_result["file_profiles"]

        insights = _build_semantic_insights(file_profiles, column_corpus, entity_inference)

        # ── LLM semantic enrichment pass ──────────────────────────────────────
        # For columns where heuristic confidence is low, ask the LLM for
        # a richer semantic interpretation before returning the insights.
        low_conf_cols = [
            cs for cs in insights["column_semantics"] if cs["confidence"] < 0.4
        ]
        if low_conf_cols:
            backend_url = os.getenv("GRAPH_TRACE_BACKEND_URL", "http://127.0.0.1:8011")
            _SEMANTIC_PROMPT = (
                "You are a PLM data engineer expert. Given column names and statistics "
                "from a dataset, infer the semantic role and entity type for each column. "
                "Return a JSON array where each element has: "
                "column (string), canonical_name (string), semantic_role (string), "
                "entity_hint (string), confidence (float 0-1), and reasoning (string). "
                "Only return the JSON array, no extra text."
            )
            col_summary = [
                {
                    "column": cs["column"],
                    "dtype": cs.get("dtype", ""),
                    "cardinality_ratio": cs.get("cardinality_ratio", 0.0),
                    "null_rate": cs.get("null_rate", 0.0),
                }
                for cs in low_conf_cols
            ]
            try:
                import json as _json
                llm_result = await self._adaptive_llm_call(
                    backend_url=backend_url,
                    system_prompt=_SEMANTIC_PROMPT,
                    user_content=_json.dumps(col_summary),
                    temperature=0.1,
                    max_tokens=1200,
                )
                if isinstance(llm_result, list):
                    # Merge LLM-enriched semantics back by column name
                    llm_by_col = {item["column"]: item for item in llm_result if isinstance(item, dict) and "column" in item}
                    for cs in insights["column_semantics"]:
                        enriched = llm_by_col.get(cs["column"])
                        if enriched and float(enriched.get("confidence", 0)) > cs["confidence"]:
                            cs.update({
                                "canonical_name": enriched.get("canonical_name", cs["canonical_name"]),
                                "semantic_role":  enriched.get("semantic_role", cs["semantic_role"]),
                                "entity_hint":    enriched.get("entity_hint", cs["entity_hint"]),
                                "confidence":     float(enriched.get("confidence", cs["confidence"])),
                                "llm_reasoning":  enriched.get("reasoning", ""),
                            })
                    logger.info(
                        "DataProfilerAgent: LLM enriched %d low-confidence columns",
                        len(llm_by_col),
                    )
            except Exception as llm_err:
                logger.debug("DataProfilerAgent: LLM enrichment skipped: %s", llm_err)
        # ── End LLM enrichment ────────────────────────────────────────────────

        logger.info(
            "DataProfilerAgent: %d columns, %d entity classifications, %d relationships",
            insights["summary"]["total_columns_analysed"],
            len(insights["entity_classifications"]),
            insights["summary"]["relationship_count"],
        )
        return {
            "status":          "completed",
            "source_name":     req.source_name,
            "semantic_insights": insights,
            "generated_at":    datetime.utcnow().isoformat() + "Z",
        }


# ── Module-level export ────────────────────────────────────────────────────────
agent = DataProfilerAgent()
app   = agent.app

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8031)
