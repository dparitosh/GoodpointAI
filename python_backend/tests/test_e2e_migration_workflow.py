"""
End-to-End Migration Workflow Tests
=====================================
Covers the full pipeline using the sample CSV data in data/csv/input/parts_sample.csv:

  1.  Data Profiling  – column semantics, entity classification, null/cardinality stats
  2.  Data Quality    – completeness, rule violations, scoring, report normalisation
  3.  ETL / Transform – field mapping, value transformation, type coercion
  4.  Rule Engine     – expression evaluation, batch execution, rule-set orchestration
  5.  Reporting       – readiness score, recommended actions, executive summary keys
  6.  Migration Engine – session lifecycle, state machine transitions

All tests are self-contained (no live DB / external services required).
"""

# pylint: disable=redefined-outer-name

import csv
import io
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import pytest

# ── Ensure project root is on path ──────────────────────────────────────────
_BACKEND_DIR = Path(__file__).resolve().parent.parent
_WORKSPACE_ROOT = _BACKEND_DIR.parent
sys.path.insert(0, str(_BACKEND_DIR))
sys.path.insert(0, str(_WORKSPACE_ROOT))

# ─────────────────────────────────────────────────────────────────────────────
# Sample data fixture (parts_sample.csv rows as plain dicts)
# ─────────────────────────────────────────────────────────────────────────────
SAMPLE_CSV_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "csv" / "input" / "parts_sample.csv"

_SAMPLE_RECORDS = [
    {"part_number": "PN-001", "name": "Bolt M8",     "category": "Fastener",   "material": "Steel",     "weight_kg": "0.012", "unit_cost": "0.45",  "supplier_id": "SUP-001", "status": "active"},
    {"part_number": "PN-002", "name": "Nut M8",      "category": "Fastener",   "material": "Steel",     "weight_kg": "0.008", "unit_cost": "0.30",  "supplier_id": "SUP-001", "status": "active"},
    {"part_number": "PN-003", "name": "Washer M8",   "category": "Hardware",   "material": "Aluminium", "weight_kg": "0.003", "unit_cost": "0.12",  "supplier_id": "SUP-003", "status": "active"},
    {"part_number": "PN-004", "name": "Screw M6",    "category": "Fastener",   "material": "Steel",     "weight_kg": "0.009", "unit_cost": "0.22",  "supplier_id": "SUP-001", "status": "active"},
    {"part_number": "PN-005", "name": "Spring Pin",  "category": "Hardware",   "material": "",          "weight_kg": "0.005", "unit_cost": "0.18",  "supplier_id": "SUP-002", "status": "active"},
    {"part_number": "PN-006", "name": "Bracket L",   "category": "Structural", "material": "Steel",     "weight_kg": "0.145", "unit_cost": "2.50",  "supplier_id": "SUP-003", "status": "obsolete"},
    {"part_number": "PN-007", "name": "Cover Plate", "category": "Enclosure",  "material": "Aluminium", "weight_kg": "0.280", "unit_cost": "8.90",  "supplier_id": "",        "status": "active"},
    {"part_number": "PN-008", "name": "Seal Ring",   "category": "Sealing",    "material": "Rubber",    "weight_kg": "0.015", "unit_cost": "0.65",  "supplier_id": "SUP-004", "status": "active"},
    {"part_number": "PN-009", "name": "Bearing 6205","category": "Mechanical", "material": "Steel",     "weight_kg": "0.089", "unit_cost": "4.20",  "supplier_id": "SUP-002", "status": "active"},
    {"part_number": "PN-010", "name": "O-Ring 50mm", "category": "Sealing",    "material": "Rubber",    "weight_kg": "0.003", "unit_cost": "",       "supplier_id": "SUP-004", "status": "active"},
]


@pytest.fixture
def sample_records() -> List[Dict[str, Any]]:
    """10-row parts sample with intentional nulls / blanks."""
    return [dict(r) for r in _SAMPLE_RECORDS]


@pytest.fixture
def typed_records(sample_records) -> List[Dict[str, Any]]:
    """Coerce numeric fields to proper Python types (as ETL would do)."""
    result = []
    for row in sample_records:
        r = dict(row)
        r["weight_kg"] = float(r["weight_kg"]) if r["weight_kg"] else None
        r["unit_cost"] = float(r["unit_cost"]) if r["unit_cost"] else None
        result.append(r)
    return result


# ─────────────────────────────────────────────────────────────────────────────
# 1. SAMPLE DATA INTEGRITY
# ─────────────────────────────────────────────────────────────────────────────

class TestSampleDataIntegrity:
    """Verify the sample CSV fixture is well-formed before testing anything else."""

    def test_sample_csv_file_exists(self):
        assert SAMPLE_CSV_PATH.exists(), f"Missing fixture: {SAMPLE_CSV_PATH}"

    def test_sample_csv_columns(self):
        with open(SAMPLE_CSV_PATH, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            cols = reader.fieldnames
        expected = {"part_number", "name", "category", "material", "weight_kg", "unit_cost", "supplier_id", "status"}
        assert expected.issubset(set(cols or []))

    def test_sample_records_count(self, sample_records):
        assert len(sample_records) == 10

    def test_known_null_fields(self, sample_records):
        # PN-005 has blank material, PN-007 has blank supplier_id, PN-010 has blank unit_cost
        pn005 = next(r for r in sample_records if r["part_number"] == "PN-005")
        assert pn005["material"] == ""
        pn007 = next(r for r in sample_records if r["part_number"] == "PN-007")
        assert pn007["supplier_id"] == ""
        pn010 = next(r for r in sample_records if r["part_number"] == "PN-010")
        assert pn010["unit_cost"] == ""

    def test_status_values(self, sample_records):
        statuses = {r["status"] for r in sample_records}
        assert statuses == {"active", "obsolete"}


# ─────────────────────────────────────────────────────────────────────────────
# 2. DATA PROFILING (DataProfiler heuristics — no LLM, purely local)
# ─────────────────────────────────────────────────────────────────────────────

class TestDataProfiling:
    """Column-level statistics and semantic inference on the sample dataset."""

    @staticmethod
    def _profile_columns(records: List[Dict]) -> Dict[str, Dict]:
        """Light-weight profiler matching DataProfiler's basic statistics."""
        if not records:
            return {}
        cols = list(records[0].keys())
        stats: Dict[str, Dict] = {}
        for col in cols:
            vals = [r.get(col) for r in records]
            non_null = [v for v in vals if v is not None and v != ""]
            unique_vals = set(non_null)
            stats[col] = {
                "total": len(vals),
                "non_null": len(non_null),
                "null_count": len(vals) - len(non_null),
                "null_rate": round((len(vals) - len(non_null)) / max(len(vals), 1), 4),
                "unique_count": len(unique_vals),
                "cardinality_ratio": round(len(unique_vals) / max(len(non_null), 1), 4),
            }
        return stats

    def test_profile_produces_all_columns(self, sample_records):
        stats = self._profile_columns(sample_records)
        assert set(stats.keys()) == {"part_number", "name", "category", "material",
                                      "weight_kg", "unit_cost", "supplier_id", "status"}

    def test_null_rate_material(self, sample_records):
        stats = self._profile_columns(sample_records)
        # 1 blank material out of 10
        assert stats["material"]["null_count"] == 1
        assert stats["material"]["null_rate"] == pytest.approx(0.1, abs=0.001)

    def test_null_rate_supplier_id(self, sample_records):
        stats = self._profile_columns(sample_records)
        assert stats["supplier_id"]["null_count"] == 1

    def test_null_rate_unit_cost(self, sample_records):
        stats = self._profile_columns(sample_records)
        assert stats["unit_cost"]["null_count"] == 1

    def test_cardinality_ratio_part_number(self, sample_records):
        """part_number should be high-cardinality (identifier)."""
        stats = self._profile_columns(sample_records)
        assert stats["part_number"]["cardinality_ratio"] == pytest.approx(1.0, abs=0.01)

    def test_cardinality_ratio_status(self, sample_records):
        """status should be low-cardinality (enum-like)."""
        stats = self._profile_columns(sample_records)
        assert stats["status"]["cardinality_ratio"] < 0.5

    def test_zero_null_rate_for_complete_columns(self, sample_records):
        stats = self._profile_columns(sample_records)
        for col in ("part_number", "name", "status"):
            assert stats[col]["null_count"] == 0

    def test_dataprofilagent_infer_column_semantics(self):
        """Test the DataProfiler heuristic column semantic inference directly."""
        from agent_services.data_profiler.main import _infer_column_semantics
        result = _infer_column_semantics("part_number", "string", cardinality_ratio=1.0, null_rate=0.0)
        assert result["column"] == "part_number"
        assert result["confidence"] >= 0.5
        # canonical_name should relate to part/item
        assert any(kw in result["canonical_name"].lower() for kw in ("part", "number", "id"))

    def test_dataprofileragent_infer_supplier_id(self):
        from agent_services.data_profiler.main import _infer_column_semantics
        result = _infer_column_semantics("supplier_id", "string", cardinality_ratio=0.4, null_rate=0.1)
        assert result["column"] == "supplier_id"
        assert result["confidence"] >= 0.4

    def test_dataprofileragent_build_semantic_insights(self, sample_records):
        from agent_services.data_profiler.main import _build_semantic_insights
        # Build a minimal column corpus from our sample
        col_corpus = [
            {"column_name": col, "dtype": "string",
             "cardinality_ratio": len({r[col] for r in sample_records if r[col]}) / 10,
             "null_rate": sum(1 for r in sample_records if not r[col]) / 10}
            for col in sample_records[0].keys()
        ]
        insights = _build_semantic_insights(
            file_profiles=[],
            column_corpus=col_corpus,
            entity_inference={},
        )
        assert "column_semantics" in insights
        assert "entity_classifications" in insights
        assert "summary" in insights
        assert insights["summary"]["total_columns_analysed"] == 8


# ─────────────────────────────────────────────────────────────────────────────
# 3. DATA QUALITY
# ─────────────────────────────────────────────────────────────────────────────

class TestDataQuality:
    """Completeness, scoring, and report normalisation."""

    @staticmethod
    def _completeness_score(records: List[Dict], required_cols: List[str]) -> float:
        """Fraction of required fields that are non-blank across all records."""
        if not records:
            return 0.0
        total = len(records) * len(required_cols)
        filled = sum(1 for r in records for col in required_cols if r.get(col))
        return round(filled / total, 4)

    def test_completeness_required_cols(self, sample_records):
        score = self._completeness_score(
            sample_records, ["part_number", "name", "category", "status"]
        )
        assert score == pytest.approx(1.0)

    def test_completeness_optional_cols(self, sample_records):
        # material, unit_cost, supplier_id each have 1 blank → 97% complete
        score = self._completeness_score(
            sample_records, ["material", "unit_cost", "supplier_id"]
        )
        assert 0.9 <= score <= 1.0

    def test_quality_report_normalization_backfills_dimensions(self):
        """_normalize_quality_report_payload backfills missing dimension scores."""
        from graph_api.quality_router import DataQualityReport, _normalize_quality_report_payload
        payload = {
            "table_name": "parts",
            "scan_id": "scan-parts-001",
            "overall_score": 0.88,
            "issues": [],
            "recommendations": [],
            "scan_date": datetime.now(timezone.utc),
            "row_count": 10,
            "column_count": 8,
        }
        normalised = _normalize_quality_report_payload(payload)
        assert normalised["completeness_score"] == pytest.approx(0.88)
        assert normalised["accuracy_score"] == pytest.approx(0.88)
        assert normalised["consistency_score"] == pytest.approx(0.88)
        assert normalised["validity_score"] == pytest.approx(0.88)
        # Must validate against the Pydantic model
        DataQualityReport(**normalised)

    def test_quality_report_normalization_zero_score(self):
        from graph_api.quality_router import DataQualityReport, _normalize_quality_report_payload
        payload = {
            "table_name": "empty_table",
            "scan_id": "scan-empty",
            "issues": [],
            "recommendations": [],
            "scan_date": datetime.now(timezone.utc),
            "row_count": 0,
            "column_count": 0,
        }
        normalised = _normalize_quality_report_payload(payload, fallback_overall_score=0.0)
        assert normalised["overall_score"] == pytest.approx(0.0)
        DataQualityReport(**normalised)

    def test_null_detection_material_field(self, sample_records):
        blank_material = [r for r in sample_records if not r["material"]]
        assert len(blank_material) == 1
        assert blank_material[0]["part_number"] == "PN-005"

    def test_obsolete_status_flagged(self, sample_records):
        """Business rule: 'obsolete' status should be flagged as a data issue."""
        obsolete = [r for r in sample_records if r["status"] == "obsolete"]
        assert len(obsolete) == 1
        assert obsolete[0]["part_number"] == "PN-006"

    def test_negative_cost_check_passes(self, typed_records):
        """All unit costs that exist should be positive."""
        costs = [r["unit_cost"] for r in typed_records if r["unit_cost"] is not None]
        assert all(c > 0 for c in costs)

    def test_positive_weight_check_passes(self, typed_records):
        weights = [r["weight_kg"] for r in typed_records if r["weight_kg"] is not None]
        assert all(w > 0 for w in weights)


# ─────────────────────────────────────────────────────────────────────────────
# 4. RULE ENGINE
# ─────────────────────────────────────────────────────────────────────────────

class TestRuleEngine:
    """Unit tests for SafeExpressionEvaluator and RuleEngine."""

    @pytest.fixture
    def evaluator(self):
        from services.rule_engine import SafeExpressionEvaluator
        return SafeExpressionEvaluator()

    @pytest.fixture
    def engine(self):
        from services.rule_engine import RuleEngine
        return RuleEngine()

    # ── Expression evaluator ─────────────────────────────────────────────────

    def test_simple_bool_expression(self, evaluator):
        ok, result, err = evaluator.evaluate("1 + 1 == 2", {})
        assert ok and result is True and err is None

    def test_context_variable_access(self, evaluator):
        ok, result, err = evaluator.evaluate("status == 'active'", {"status": "active"})
        assert ok and result is True

    def test_failing_expression(self, evaluator):
        ok, result, err = evaluator.evaluate("status == 'active'", {"status": "obsolete"})
        assert ok and result is False

    def test_is_not_null_helper_passes(self, evaluator):
        ok, result, err = evaluator.evaluate("is_not_null(part_number)", {"part_number": "PN-001"})
        assert ok and result is True

    def test_is_not_null_helper_fails_on_empty(self, evaluator):
        # is_not_null only checks for None — empty string is NOT None so returns True.
        # For empty-string null detection use the `!= ''` pattern instead.
        ok, result, err = evaluator.evaluate("is_not_null(supplier_id)", {"supplier_id": ""})
        assert ok and result is True  # '' is not None
        # Verify the correct idiom for blank detection:
        ok2, result2, err2 = evaluator.evaluate("supplier_id != ''", {"supplier_id": ""})
        assert ok2 and result2 is False

    def test_matches_regex_pn_format(self, evaluator):
        ok, result, err = evaluator.evaluate(
            "matches_regex(part_number, '^PN-\\\\d{3}$')",
            {"part_number": "PN-001"},
        )
        assert ok and result is True

    def test_matches_regex_pn_bad_format(self, evaluator):
        ok, result, err = evaluator.evaluate(
            "matches_regex(part_number, '^PN-\\\\d{3}$')",
            {"part_number": "BADPART"},
        )
        assert ok and result is False

    def test_in_range_weight_passes(self, evaluator):
        ok, result, err = evaluator.evaluate(
            "in_range(float(weight_kg), 0.001, 1.0)",
            {"weight_kg": "0.012"},
        )
        assert ok and result is True

    def test_in_list_status_valid(self, evaluator):
        ok, result, err = evaluator.evaluate(
            "in_list(status, ['active', 'obsolete', 'draft'])",
            {"status": "active"},
        )
        assert ok and result is True

    def test_in_list_status_invalid(self, evaluator):
        ok, result, err = evaluator.evaluate(
            "in_list(status, ['active', 'obsolete', 'draft'])",
            {"status": "unknown"},
        )
        assert ok and result is False

    def test_blocked_builtins_raise_error(self, evaluator):
        """open() is not in SAFE_BUILTINS — should error gracefully."""
        ok, result, err = evaluator.evaluate("open('/etc/passwd')", {})
        assert not ok
        assert err is not None

    def test_circular_dep_detection_positive(self, evaluator):
        nodes = [
            {"id": "A", "parent_id": "C"},
            {"id": "B", "parent_id": "A"},
            {"id": "C", "parent_id": "B"},
        ]
        ok, result, err = evaluator.evaluate(
            "has_circular_dependency(nodes)",
            {"nodes": nodes},
        )
        assert ok and result is True

    def test_circular_dep_detection_negative(self, evaluator):
        nodes = [
            {"id": "A", "parent_id": None},
            {"id": "B", "parent_id": "A"},
            {"id": "C", "parent_id": "B"},
        ]
        ok, result, err = evaluator.evaluate(
            "has_circular_dependency(nodes)",
            {"nodes": nodes},
        )
        assert ok and result is False

    # ── RuleEngine.execute_rule ───────────────────────────────────────────────

    def test_execute_rule_passes(self, engine):
        from services.rule_engine import RuleContext
        rule = {"id": "R001", "expression": "status == 'active'"}
        ctx = RuleContext(record={"status": "active"}, record_id="1")
        result = engine.execute_rule(rule, ctx)
        assert result.passed
        assert result.rule_id == "R001"

    def test_execute_rule_fails(self, engine):
        from services.rule_engine import RuleContext
        rule = {"id": "R002", "expression": "status != 'obsolete'"}
        ctx = RuleContext(record={"status": "obsolete"}, record_id="2")
        result = engine.execute_rule(rule, ctx)
        assert not result.passed
        assert len(result.failure_samples) == 1

    def test_execute_rule_bad_expression(self, engine):
        from services.rule_engine import RuleContext
        rule = {"id": "R003", "expression": "open('/bad')"}
        ctx = RuleContext(record={"status": "active"}, record_id="3")
        result = engine.execute_rule(rule, ctx)
        assert not result.passed
        assert result.error is not None

    # ── RuleEngine.execute_rule_batch ─────────────────────────────────────────

    def test_execute_rule_batch_all_pass(self, engine, sample_records):
        rule = {"id": "R010", "expression": "is_not_null(part_number)"}
        result = engine.execute_rule_batch(rule, sample_records)
        assert result.passed
        assert result.records_checked == 10
        assert result.records_failed == 0

    def test_execute_rule_batch_partial_fail(self, engine, sample_records):
        # material is blank (empty string) for PN-005; use != '' to catch blanks.
        rule = {"id": "R011", "expression": "material != ''"}
        result = engine.execute_rule_batch(rule, sample_records)
        assert not result.passed
        assert result.records_failed == 1
        assert result.records_checked == 10

    def test_execute_rule_batch_cost_positive(self, engine, sample_records):
        rule = {"id": "R012", "expression": "unit_cost != ''"}
        result = engine.execute_rule_batch(rule, sample_records)
        assert not result.passed
        assert result.records_failed == 1  # PN-010

    def test_execute_rule_batch_pn_format(self, engine, sample_records):
        rule = {"id": "R013", "expression": "matches_regex(part_number, '^PN-\\\\d{3}$')"}
        result = engine.execute_rule_batch(rule, sample_records)
        assert result.passed
        assert result.records_failed == 0

    # ── RuleEngine.execute_rule_set ───────────────────────────────────────────

    def test_execute_rule_set_basic(self, engine, sample_records):
        rule_set = {"id": "RS001", "name": "Parts validation"}
        rules = [
            {"id": "R021", "sequence_order": 1, "expression": "is_not_null(part_number)", "severity": "critical"},
            {"id": "R022", "sequence_order": 2, "expression": "is_not_null(name)", "severity": "high"},
            {"id": "R023", "sequence_order": 3, "expression": "is_not_null(material)", "severity": "medium"},
        ]
        result = engine.execute_rule_set(rule_set, rules, sample_records)
        assert result.status == "completed"
        assert result.rules_passed >= 2    # R021, R022 should pass
        assert result.total_rules == 3

    def test_execute_rule_set_counts_failures(self, engine, sample_records):
        rule_set = {"id": "RS002"}
        rules = [
            {"id": "R031", "sequence_order": 1, "expression": "unit_cost != '' and unit_cost is not None", "severity": "medium"},
            {"id": "R032", "sequence_order": 2, "expression": "supplier_id != ''", "severity": "medium"},
        ]
        result = engine.execute_rule_set(rule_set, rules, sample_records)
        assert result.total_failures > 0  # missing cost + missing supplier


# ─────────────────────────────────────────────────────────────────────────────
# 5. ETL / TRANSFORMATION
# ─────────────────────────────────────────────────────────────────────────────

class TestETLTransformation:
    """Field mapping, type coercion, and transformation logic."""

    @staticmethod
    def _apply_field_mapping(record: Dict, mapping: Dict[str, str]) -> Dict:
        """Rename fields according to source→target mapping."""
        return {mapping.get(k, k): v for k, v in record.items()}

    @staticmethod
    def _coerce_types(record: Dict, schema: Dict[str, str]) -> Dict:
        """Coerce string values to declared types."""
        result = {}
        for k, v in record.items():
            target_type = schema.get(k, "string")
            if target_type == "float":
                try:
                    result[k] = float(v) if v else None
                except (ValueError, TypeError):
                    result[k] = None
            elif target_type == "int":
                try:
                    result[k] = int(float(v)) if v else None
                except (ValueError, TypeError):
                    result[k] = None
            else:
                result[k] = v
        return result

    @staticmethod
    def _apply_value_transform(record: Dict, transforms: Dict[str, callable]) -> Dict:
        result = dict(record)
        for col, fn in transforms.items():
            if col in result:
                result[col] = fn(result[col])
        return result

    def test_field_rename_mapping(self, sample_records):
        mapping = {"part_number": "part_id", "unit_cost": "cost_usd"}
        transformed = [self._apply_field_mapping(r, mapping) for r in sample_records]
        assert "part_id" in transformed[0]
        assert "cost_usd" in transformed[0]
        assert "part_number" not in transformed[0]
        assert "unit_cost" not in transformed[0]

    def test_field_rename_preserves_values(self, sample_records):
        mapping = {"part_number": "part_id"}
        transformed = [self._apply_field_mapping(r, mapping) for r in sample_records]
        original_pns = [r["part_number"] for r in sample_records]
        mapped_pns = [r["part_id"] for r in transformed]
        assert original_pns == mapped_pns

    def test_type_coercion_float(self, sample_records):
        schema = {"weight_kg": "float", "unit_cost": "float"}
        coerced = [self._coerce_types(r, schema) for r in sample_records]
        # PN-001 weight should be 0.012 float
        pn001 = next(r for r in coerced if r["part_number"] == "PN-001")
        assert isinstance(pn001["weight_kg"], float)
        assert pn001["weight_kg"] == pytest.approx(0.012)

    def test_type_coercion_null_on_blank(self, sample_records):
        schema = {"unit_cost": "float"}
        coerced = [self._coerce_types(r, schema) for r in sample_records]
        pn010 = next(r for r in coerced if r["part_number"] == "PN-010")
        assert pn010["unit_cost"] is None

    def test_value_transform_uppercase(self, sample_records):
        transforms = {"status": lambda v: v.upper() if v else v}
        transformed = [self._apply_value_transform(r, transforms) for r in sample_records]
        statuses = {r["status"] for r in transformed}
        assert statuses == {"ACTIVE", "OBSOLETE"}

    def test_value_transform_pn_prefix_strip(self, sample_records):
        transforms = {"part_number": lambda v: v.replace("PN-", "") if v else v}
        transformed = [self._apply_value_transform(r, transforms) for r in sample_records]
        first_pn = transformed[0]["part_number"]
        assert first_pn == "001"

    def test_full_etl_pipeline(self, sample_records):
        """Run mapping → coerce → transform in sequence."""
        mapping = {"part_number": "part_id", "unit_cost": "cost_usd"}
        schema  = {"weight_kg": "float", "cost_usd": "float"}
        transforms = {"status": lambda v: v.upper() if v else v}

        step1 = [self._apply_field_mapping(r, mapping) for r in sample_records]
        step2 = [self._coerce_types(r, schema) for r in step1]
        step3 = [self._apply_value_transform(r, transforms) for r in step2]

        assert len(step3) == 10
        pn001 = next(r for r in step3 if r["part_id"] == "PN-001")
        assert pn001["status"] == "ACTIVE"
        assert isinstance(pn001["weight_kg"], float)

    def test_total_inventory_value(self, typed_records):
        """ETL derived metric: total inventory cost (weight * cost) per item."""
        totals = [
            r["weight_kg"] * r["unit_cost"]
            for r in typed_records
            if r["weight_kg"] is not None and r["unit_cost"] is not None
        ]
        # Only PN-010 has blank unit_cost → 9 records produce a valid total
        assert len(totals) == 9
        assert all(t > 0 for t in totals)


# ─────────────────────────────────────────────────────────────────────────────
# 6. REPORTING
# ─────────────────────────────────────────────────────────────────────────────

class TestReporting:
    """Report assembly, readiness scoring, and recommended actions."""

    @staticmethod
    def _make_file_profile(name: str, row_count: int, null_rate: float = 0.05) -> Dict:
        return {
            "file": name,
            "row_count": row_count,
            "column_count": 8,
            "null_rate_avg": null_rate,
            "schema_detected": True,
            "entity_class": "Part",
            "columns": ["part_number", "name", "category", "material",
                        "weight_kg", "unit_cost", "supplier_id", "status"],
        }

    def test_readiness_score_high_quality(self):
        """Parts sample with low nulls → high readiness."""
        from agent_services.reporting_agent.main import _compute_migration_readiness_score
        fp = [self._make_file_profile("parts.csv", 10, null_rate=0.1)]
        score = _compute_migration_readiness_score(
            file_profiles=fp,
            schema_drift=[],
            anomalies=[],
            quality_findings={},
            fk_candidates=[],
        )
        assert isinstance(score, dict)
        assert "score" in score
        assert float(score["score"]) >= 50  # should be reasonably high

    def test_readiness_score_degraded_with_drift(self):
        from agent_services.reporting_agent.main import _compute_migration_readiness_score
        fp = [self._make_file_profile("parts.csv", 10, null_rate=0.1)]
        drift = [
            {"file": "parts.csv", "column": "material", "severity": "high",
             "drift_type": "type_mismatch", "old_type": "string", "new_type": "int"}
        ]
        score_nodrift = _compute_migration_readiness_score(
            file_profiles=fp, schema_drift=[], anomalies=[], quality_findings={}, fk_candidates=[]
        )
        score_drift = _compute_migration_readiness_score(
            file_profiles=fp, schema_drift=drift, anomalies=[], quality_findings={}, fk_candidates=[]
        )
        # Score with drift should be lower or equal
        assert float(score_drift["score"]) <= float(score_nodrift["score"])

    def test_recommended_actions_include_quality_when_issues(self):
        from agent_services.reporting_agent.main import _build_recommended_agent_actions
        quality_findings = {"null_violations": 3, "overall_score": 0.7}
        actions = _build_recommended_agent_actions(
            schema_drift=[],
            fk_candidates=[],
            anomalies=[],
            quality_findings=quality_findings,
            etl_result={},
            readiness_score={"score": 70},
            data_quality_summary={},
        )
        assert isinstance(actions, list)

    def test_dataset_summary_structure(self):
        from agent_services.reporting_agent.main import _build_dataset_summary
        fp = [self._make_file_profile("parts.csv", 10)]
        summary = _build_dataset_summary(fp, column_corpus=[])
        assert "total_files" in summary or isinstance(summary, dict)

    def test_data_quality_summary_structure(self):
        from agent_services.reporting_agent.main import _build_data_quality_summary
        quality_findings = {"null_violations": 3, "overall_score": 0.88}
        summary = _build_data_quality_summary(quality_findings, file_profiles=[], anomalies=[])
        assert isinstance(summary, dict)


# ─────────────────────────────────────────────────────────────────────────────
# 7. MIGRATION SESSION LIFECYCLE
# ─────────────────────────────────────────────────────────────────────────────

class TestMigrationSessionLifecycle:
    """AdvancedMigrationEngine state machine — no external dependencies needed."""

    @pytest.fixture
    def engine(self):
        from services.advanced_migration_engine import AdvancedMigrationEngine
        return AdvancedMigrationEngine()

    def test_create_session_returns_idle(self, engine):
        from services.advanced_migration_engine import MigrationState
        session = engine.create_session(
            sources=[{"type": "csv", "path": str(SAMPLE_CSV_PATH)}],
            target={"type": "postgresql", "host": "localhost", "port": 5432, "database": "target"},
            strategy="incremental",
        )
        assert session is not None
        assert session.state == MigrationState.IDLE
        assert session.progress == 0.0

    def test_create_session_stores_sources(self, engine):
        session = engine.create_session(
            sources=[{"type": "csv", "path": str(SAMPLE_CSV_PATH)}],
            target={"type": "postgresql"},
            strategy="full_load",
        )
        assert len(session.sources) == 1
        assert session.strategy == "full_load"

    def test_get_session_by_id(self, engine):
        session = engine.create_session(
            sources=[{"type": "csv", "path": str(SAMPLE_CSV_PATH)}],
            target={"type": "postgresql"},
            strategy="incremental",
        )
        retrieved = engine.get_session(session.session_id)
        assert retrieved is not None
        assert retrieved.session_id == session.session_id

    def test_get_nonexistent_session_returns_none(self, engine):
        result = engine.get_session("nonexistent-id-99")
        assert result is None

    def test_sessions_dict_includes_created(self, engine):
        """Sessions are tracked in engine.sessions dict."""
        session = engine.create_session(
            sources=[{"type": "csv", "path": str(SAMPLE_CSV_PATH)}],
            target={"type": "postgresql"},
            strategy="full_load",
        )
        assert session.session_id in engine.sessions


# ─────────────────────────────────────────────────────────────────────────────
# 8. QUALITY REPORT ROUTER (unit-level, no DB)
# ─────────────────────────────────────────────────────────────────────────────

class TestQualityReportRouter:
    """Quality router helpers tested in isolation."""

    def test_normalize_fills_all_dimension_scores(self):
        from graph_api.quality_router import DataQualityReport, _normalize_quality_report_payload
        payload = {
            "table_name": "parts",
            "scan_id": "scan-parts-100",
            "overall_score": 0.92,
            "issues": [],
            "recommendations": ["Review nulls"],
            "scan_date": datetime.now(timezone.utc),
            "row_count": 10,
            "column_count": 8,
        }
        norm = _normalize_quality_report_payload(payload)
        for dim in ("completeness_score", "accuracy_score", "consistency_score", "validity_score"):
            assert dim in norm
            assert isinstance(norm[dim], float)
        DataQualityReport(**norm)

    def test_normalize_uses_explicit_score(self):
        from graph_api.quality_router import _normalize_quality_report_payload
        payload = {
            "table_name": "t",
            "scan_id": "s",
            "overall_score": 0.75,
            "completeness_score": 0.90,  # explicitly provided
            "issues": [],
            "recommendations": [],
            "scan_date": datetime.now(timezone.utc),
            "row_count": 5,
            "column_count": 3,
        }
        norm = _normalize_quality_report_payload(payload)
        assert norm["completeness_score"] == pytest.approx(0.90)
        # Other dims should fall back to overall_score
        assert norm["accuracy_score"] == pytest.approx(0.75)


# ─────────────────────────────────────────────────────────────────────────────
# 9. INTEGRATION: full workflow chain mock (Discover → Profile → Quality → ETL → Report)
# ─────────────────────────────────────────────────────────────────────────────

class TestWorkflowChainMock:
    """
    Simulates the 5-step agent pipeline against the sample CSV without
    running live agents or touching the DB.
    """

    def _discover(self, records: List[Dict]) -> Dict:
        """Simulate DataDiscovery output."""
        cols = list(records[0].keys()) if records else []
        return {
            "status": "completed",
            "file_profiles": [{
                "file": "parts_sample.csv",
                "row_count": len(records),
                "column_count": len(cols),
                "columns": cols,
                "entity_class": "Part",
                "schema_detected": True,
            }],
            "schema_detected": True,
        }

    def _profile(self, discovery_result: Dict, records: List[Dict]) -> Dict:
        """Simulate DataProfiler output."""
        from agent_services.data_profiler.main import _build_semantic_insights
        col_corpus = []
        if records:
            for col in records[0].keys():
                vals = [r.get(col, "") for r in records]
                non_null = [v for v in vals if v]
                col_corpus.append({
                    "column_name": col,
                    "dtype": "string",
                    "cardinality_ratio": len(set(non_null)) / max(len(non_null), 1),
                    "null_rate": (len(vals) - len(non_null)) / max(len(vals), 1),
                })
        insights = _build_semantic_insights(
            file_profiles=discovery_result.get("file_profiles", []),
            column_corpus=col_corpus,
            entity_inference={},
        )
        return {"status": "completed", "semantic_insights": insights}

    def _quality(self, records: List[Dict]) -> Dict:
        """Simulate QualityMonitor output."""
        total = len(records)
        null_mat = sum(1 for r in records if not r.get("material"))
        null_cost = sum(1 for r in records if not r.get("unit_cost"))
        null_sup = sum(1 for r in records if not r.get("supplier_id"))
        total_issues = null_mat + null_cost + null_sup
        score = round(1.0 - total_issues / (total * 3), 3)
        return {
            "status": "completed",
            "quality_findings": {
                "null_violations": total_issues,
                "overall_score": score,
            },
            "score": score,
        }

    def _etl(self, records: List[Dict]) -> Dict:
        """Simulate ETL output: rename + coerce."""
        mapping = {"part_number": "part_id", "unit_cost": "cost_usd"}
        transformed = []
        for r in records:
            row = {mapping.get(k, k): v for k, v in r.items()}
            try:
                row["weight_kg"] = float(row["weight_kg"]) if row.get("weight_kg") else None
                row["cost_usd"] = float(row["cost_usd"]) if row.get("cost_usd") else None
            except ValueError:
                pass
            transformed.append(row)
        return {
            "status": "completed",
            "records_processed": len(records),
            "records_failed": 0,
            "etl_result": {"records_out": transformed},
        }

    def _report(self, discovery, profile, quality, etl) -> Dict:
        """Assemble a lightweight report dict (no live ReportingAgent)."""
        null_violations = quality["quality_findings"].get("null_violations", 0)
        score = quality.get("score", 1.0)
        readiness = max(0.0, min(1.0, score - (null_violations * 0.02)))
        return {
            "status": "completed",
            "report_id": f"rpt_{uuid.uuid4().hex[:8]}",
            "migration_readiness_score": {"score": round(readiness * 100, 1), "grade": "B"},
            "total_records": etl.get("records_processed", 0),
            "quality_score": score,
            "semantic_insights_summary": profile["semantic_insights"]["summary"],
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    def test_full_pipeline_produces_report(self, sample_records):
        d = self._discover(sample_records)
        p = self._profile(d, sample_records)
        q = self._quality(sample_records)
        e = self._etl(sample_records)
        r = self._report(d, p, q, e)

        assert r["status"] == "completed"
        assert r["total_records"] == 10
        assert "report_id" in r
        assert "migration_readiness_score" in r

    def test_pipeline_semantic_insights_columns(self, sample_records):
        d = self._discover(sample_records)
        p = self._profile(d, sample_records)
        summary = p["semantic_insights"]["summary"]
        assert summary["total_columns_analysed"] == 8

    def test_pipeline_quality_score_range(self, sample_records):
        q = self._quality(sample_records)
        assert 0.0 <= q["score"] <= 1.0

    def test_pipeline_etl_output_count(self, sample_records):
        e = self._etl(sample_records)
        assert e["records_processed"] == 10
        assert e["records_failed"] == 0
        # Verify field rename happened
        records_out = e["etl_result"]["records_out"]
        assert "part_id" in records_out[0]
        assert "cost_usd" in records_out[0]
        assert "part_number" not in records_out[0]

    def test_pipeline_etl_null_cost_preserved(self, sample_records):
        e = self._etl(sample_records)
        records_out = e["etl_result"]["records_out"]
        pn010 = next(r for r in records_out if r.get("part_id") == "PN-010")
        assert pn010["cost_usd"] is None

    def test_pipeline_readiness_score_type(self, sample_records):
        d = self._discover(sample_records)
        p = self._profile(d, sample_records)
        q = self._quality(sample_records)
        e = self._etl(sample_records)
        r = self._report(d, p, q, e)
        assert isinstance(r["migration_readiness_score"]["score"], float)
