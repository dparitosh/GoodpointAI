import sys
import os
import json
import logging
import re
import httpx
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv
from contextlib import asynccontextmanager
from fastapi import FastAPI

# Add parent directory to path to allow importing base
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

# Also add python_backend to path for Rule Engine imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "python_backend"))

# Load environment variables from backend .env
env_path = Path(__file__).resolve().parent.parent.parent / "python_backend" / ".env"
load_dotenv(dotenv_path=env_path)

logger = logging.getLogger(__name__)

from neo4j import AsyncGraphDatabase
from agent_services.base.agent_service import AgentService
from agent_services.base.models import AgentCapability, AgentTaskRequest, AgentType

# All DB access goes through the backend API — no direct ORM imports
BACKEND_URL = os.getenv("GRAPH_TRACE_BACKEND_URL", "http://localhost:8011")

# ── LLM prompt for AI-powered rule recommendations ────────────────────────────
_RULE_RECOMMENDATION_PROMPT = """\
You are a Data Quality Rules Advisor for PLM/ETL migration pipelines.
You receive column-level profile statistics from a data discovery run and must \
recommend specific, actionable DQ rules that should be applied to this dataset.

For each recommended rule output a JSON object with:
  rule_type       : completeness|uniqueness|range|pattern|freshness|allowed_values|referential_integrity|format
  column          : exact column name (or "*" for dataset-level rules)
  threshold       : numeric threshold (null if not applicable)
  expression_hint : short Python expression hint using is_empty/matches_regex/in_range/in_list helpers
  rationale       : one sentence explaining WHY this rule matters for THIS specific data
  priority        : critical|high|medium|low
  severity        : critical|warning|info

Output ONLY a valid JSON array of rule recommendation objects. No other text.
"""

class QualityMonitorAgent(AgentService):
    def __init__(self):
        super().__init__(
            agent_type=AgentType.QUALITY_MONITOR,
            agent_name="Quality Monitor Agent",
            port=8024
        )
        self.neo4j_uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        self.neo4j_user = os.getenv("NEO4J_USER", "neo4j")
        self.neo4j_password = os.getenv("NEO4J_PASSWORD", "password")
        self.driver = None

    @asynccontextmanager
    async def _lifespan(self, _app: FastAPI):
        # Initialize resources
        try:
            self.driver = AsyncGraphDatabase.driver(
                self.neo4j_uri, 
                auth=(self.neo4j_user, self.neo4j_password)
            )
            await self.driver.verify_connectivity()
            logger.info("Neo4j connectivity verified.")
        except Exception as e:
            logger.warning("Neo4j connectivity failed: %s", e)

        async with super()._lifespan(_app):
            yield
        
        if self.driver:
            await self.driver.close()

    def get_capabilities(self):
        return [
            AgentCapability(name="monitor_data_quality", description="Monitor data quality metrics"),
            AgentCapability(name="detect_anomalies", description="Detect data anomalies"),
            AgentCapability(name="validate_transformations", description="Validate data transformations"),
            AgentCapability(name="generate_quality_reports", description="Generate quality reports"),
            AgentCapability(name="execute_rules", description="Execute Rule Engine rule sets against data"),
            AgentCapability(name="recommend_rules", description="AI-powered DQ rule recommendations from profile data"),
        ]

    async def process_task(self, task: AgentTaskRequest):
        caps = set(task.payload.get("required_capabilities", []))
        profile_summary = task.payload.get("profile_summary")

        # AI rule recommendation — can be requested explicitly or triggered by
        # profile data arriving in the payload (from data_discovery handoff).
        if "recommend_rules" in caps or (profile_summary and not task.payload.get("source_id") and not task.payload.get("folder_path")):
            return await self._handle_rule_recommendation(task)

        # Route to datasource quality scan (folder or registered source_id)
        if "scan_datasource_quality" in caps or task.payload.get("source_id") or task.payload.get("folder_path"):
            return await self._scan_datasource_via_backend(task)

        # Default: rule-engine based quality check on records in payload
        records = task.payload.get("records", [])
        entity_type = task.payload.get("entity_type")

        rule_result: Dict[str, Any] = {}
        if records:
            rule_result = await self._run_rule_engine_via_api(records, entity_type)

        quality_score = rule_result.get("quality_score", 100.0) if rule_result else 100.0

        return {
            "status": "Quality check completed",
            "task_id": task.task_id,
            "quality_score": quality_score,
            "anomalies_found": rule_result.get("total_failures", 0) if rule_result else 0,
            "rule_validation": rule_result if rule_result else None,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    async def _handle_rule_recommendation(self, task: AgentTaskRequest) -> Dict[str, Any]:
        """Entry point for the recommend_rules capability.

        Combines deterministic signal-based recommendations (always runs) with
        optional AI/LLM recommendations (graceful fallback when LLM unavailable).
        """
        profile_summary = task.payload.get("profile_summary", {})
        deterministic = self._recommend_rules_from_profile(profile_summary)
        ai_recs = await self._recommend_rules_with_llm(profile_summary, task.payload)

        # Merge: AI recs go first (richer rationale), then deterministic for columns
        # not already covered by the AI output.
        ai_columns = {r.get("column") for r in (ai_recs or [])}
        extra = [r for r in deterministic if r.get("column") not in ai_columns]
        recommended_rules = (ai_recs or []) + extra

        return {
            "status": "Rule recommendations generated",
            "task_id": task.task_id,
            "recommended_rules": recommended_rules,
            "rule_count": len(recommended_rules),
            "ai_powered": ai_recs is not None,
            "profile_signals": len(profile_summary.get("signals", [])),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def _recommend_rules_from_profile(
        self, profile_summary: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Deterministic rule recommendations derived from column profile statistics.

        Always runs regardless of LLM availability. Covers the most important
        signal types so operators get useful recommendations even when AI is off.
        """
        recommendations: List[Dict[str, Any]] = []
        columns = profile_summary.get("columns", {})
        signals = profile_summary.get("signals", [])

        # Index signals by type for quick lookup
        signal_by_col: Dict[str, List[Dict[str, Any]]] = {}
        for s in signals:
            col = s.get("column", "*")
            signal_by_col.setdefault(col, []).append(s)

        for col_name, meta in columns.items():
            null_max = meta.get("null_rate_max", 0) or 0
            null_avg = meta.get("null_rate_avg", 0) or 0
            cr_avg   = meta.get("cardinality_ratio_avg", 0) or 0
            is_id    = meta.get("is_identifier", False)
            dtypes   = meta.get("dtypes", [])
            semtypes = meta.get("semantic_types", [])

            # Completeness — high null rate
            if null_max > 0.05:
                priority = "critical" if null_max > 0.5 else "high" if null_max > 0.2 else "medium"
                recommendations.append({
                    "rule_type": "completeness",
                    "column": col_name,
                    "threshold": round(1 - null_max, 2),
                    "expression_hint": f"not is_empty(record.get('{col_name}'))",
                    "rationale": (
                        f"Column '{col_name}' has up to {null_max*100:.0f}% missing values — "
                        "a completeness rule enforces a minimum fill rate."
                    ),
                    "priority": priority,
                    "severity": "critical" if priority == "critical" else "warning",
                    "source": "deterministic",
                })

            # Uniqueness — identifier column with low cardinality
            if is_id and cr_avg < 0.99:
                recommendations.append({
                    "rule_type": "uniqueness",
                    "column": col_name,
                    "threshold": None,
                    "expression_hint": (
                        f"len(set(r.get('{col_name}') for r in _related.get('all_records',[]))) "
                        f"== len(_related.get('all_records',[]))"
                    ),
                    "rationale": (
                        f"Column '{col_name}' is classified as an identifier "
                        f"but has only {cr_avg*100:.0f}% distinct values — duplicates detected."
                    ),
                    "priority": "critical",
                    "severity": "critical",
                    "source": "deterministic",
                })

            # Allowed values — very low cardinality non-identifier (enum/flag)
            if cr_avg < 0.01 and not is_id and null_avg < 0.5:
                samples = meta.get("sample_values", [])
                if 1 <= len(samples) <= 15:
                    recommendations.append({
                        "rule_type": "allowed_values",
                        "column": col_name,
                        "threshold": None,
                        "expression_hint": f"in_list(record.get('{col_name}'), {samples!r})",
                        "rationale": (
                            f"Column '{col_name}' has only {len(samples)} distinct value(s) — "
                            "an allowed-values rule prevents unexpected entries."
                        ),
                        "priority": "medium",
                        "severity": "warning",
                        "source": "deterministic",
                    })

            # Format — date/timestamp stored as text
            if any("datetime" in s or "date" in s for s in semtypes):
                recommendations.append({
                    "rule_type": "format",
                    "column": col_name,
                    "threshold": None,
                    "expression_hint": (
                        f"matches_regex(str(record.get('{col_name}','')), "
                        r"r'^\d{4}-\d{2}-\d{2}')"
                    ),
                    "rationale": (
                        f"Column '{col_name}' contains date/time data — "
                        "a format rule validates ISO-8601 date strings and catches corrupt values."
                    ),
                    "priority": "medium",
                    "severity": "warning",
                    "source": "deterministic",
                })

            # Mixed type — data type inconsistency
            if meta.get("has_mixed_types") and len(dtypes) > 1:
                recommendations.append({
                    "rule_type": "pattern",
                    "column": col_name,
                    "threshold": None,
                    "expression_hint": f"isinstance(record.get('{col_name}'), str)",
                    "rationale": (
                        f"Column '{col_name}' has mixed dtypes ({', '.join(dtypes)}) — "
                        "a type-consistency rule ensures all values are the same type before loading."
                    ),
                    "priority": "high",
                    "severity": "warning",
                    "source": "deterministic",
                })

        # Dataset-level: flag when parse errors exist
        if profile_summary.get("total_files", 0) > profile_summary.get("parseable_files", 0):
            unparseable = (
                profile_summary.get("total_files", 0)
                - profile_summary.get("parseable_files", 0)
            )
            recommendations.append({
                "rule_type": "completeness",
                "column": "*",
                "threshold": None,
                "expression_hint": "True",
                "rationale": (
                    f"{unparseable} file(s) could not be parsed — "
                    "investigate encoding or format issues before migration."
                ),
                "priority": "critical",
                "severity": "critical",
                "source": "deterministic",
            })

        return recommendations

    async def _recommend_rules_with_llm(
        self, profile_summary: Dict[str, Any], payload: Dict[str, Any]
    ) -> Optional[List[Dict[str, Any]]]:
        """Call the backend LLM endpoint to generate AI-powered DQ rule recommendations.

        Returns a list of rule recommendation dicts on success, or None when the
        LLM is unavailable (caller falls back to deterministic recommendations only).
        """
        if not profile_summary:
            return None

        # Send a condensed context — just column stats and top signals
        context = {
            "total_files":    profile_summary.get("total_files", 0),
            "total_rows":     profile_summary.get("total_rows", 0),
            "column_stats": [
                {
                    "name":              name,
                    "null_rate_max":     meta.get("null_rate_max", 0),
                    "null_rate_avg":     meta.get("null_rate_avg", 0),
                    "cardinality_ratio": meta.get("cardinality_ratio_avg", 0),
                    "semantic_types":    meta.get("semantic_types", []),
                    "dtypes":            meta.get("dtypes", []),
                    "is_identifier":     meta.get("is_identifier", False),
                    "has_mixed_types":   meta.get("has_mixed_types", False),
                    "sample_values":     meta.get("sample_values", [])[:5],
                }
                for name, meta in list(profile_summary.get("columns", {}).items())[:30]
            ],
            "signals": profile_summary.get("signals", [])[:15],
        }

        try:
            llm_provider = payload.get("llm_provider", "openai")
            async with httpx.AsyncClient(timeout=25.0) as client:
                resp = await client.post(
                    f"{BACKEND_URL}/api/llm/chat",
                    params={"provider": llm_provider},
                    json={
                        "messages": [
                            {"role": "system", "content": _RULE_RECOMMENDATION_PROMPT},
                            {"role": "user",   "content": json.dumps(context)},
                        ],
                        "temperature": 0.1,
                        "max_tokens": 1500,
                    },
                )
                if not resp.is_success:
                    logger.debug(
                        "LLM rule recommendations returned %d — falling back to deterministic",
                        resp.status_code,
                    )
                    return None

                raw = resp.json().get("response", "")
                raw = re.sub(r"```(?:json)?", "", raw).strip().strip("`").strip()
                m = re.search(r"\[.*\]", raw, re.DOTALL)
                if not m:
                    return None
                recs = json.loads(m.group(0))
                if not isinstance(recs, list):
                    return None
                # Annotate source + sanitise
                valid = []
                for r in recs:
                    if isinstance(r, dict) and r.get("rule_type") and r.get("column"):
                        r["source"] = "ai"
                        valid.append(r)
                logger.info(
                    "LLM generated %d DQ rule recommendations for %d columns",
                    len(valid),
                    len(profile_summary.get("columns", {})),
                )
                return valid or None
        except Exception as exc:
            logger.debug("LLM rule recommendation unavailable: %s", exc)
            return None

    async def _scan_datasource_via_backend(self, task: AgentTaskRequest) -> Dict[str, Any]:
        """Call the backend quality scan endpoint — no direct DB access from agent."""
        payload = task.payload
        source_id = payload.get("source_id")
        folder_path = payload.get("folder_path")
        scan_type = payload.get("scan_type", "full")

        # Resolve folder path from source_id if needed
        if source_id and not folder_path:
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    resp = await client.get(f"{BACKEND_URL}/api/datasources/{source_id}")
                    if resp.status_code == 200:
                        ds = resp.json()
                        folder_path = ds.get("connection_string") or ds.get("path") or ds.get("host")
            except Exception as exc:
                return {"status": "error", "error": f"Could not resolve source {source_id}: {exc}"}

        if not folder_path:
            return {"status": "error", "error": "No folder path resolved"}

        scan_request = {
            "datasource": "folder",
            "table_name": folder_path,
            "scan_type": scan_type,
            "data_source": folder_path,
        }
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                resp = await client.post(f"{BACKEND_URL}/api/analytics/quality/scan", json=scan_request)
                if resp.status_code == 200:
                    result = resp.json()
                    result["routed_via"] = "quality_monitor_agent"
                    result["source_id"] = source_id
                    # ── AI rule recommendations augmentation ───────────────────
                    # When the discovery agent forwarded a profile_summary, use it to
                    # generate rule recommendations alongside the quality scan result.
                    profile_summary = payload.get("profile_summary")
                    if profile_summary and profile_summary.get("columns"):
                        deterministic = self._recommend_rules_from_profile(profile_summary)
                        ai_recs = await self._recommend_rules_with_llm(profile_summary, payload)
                        ai_cols = {r.get("column") for r in (ai_recs or [])}
                        extra = [r for r in deterministic if r.get("column") not in ai_cols]
                        result["recommended_rules"] = (ai_recs or []) + extra
                        result["ai_powered_recommendations"] = ai_recs is not None
                        result["recommendation_count"] = len(result["recommended_rules"])
                    return result
                return {
                    "status": "error",
                    "error": f"Backend scan returned {resp.status_code}: {resp.text[:300]}",
                }
        except Exception as exc:
            return {"status": "error", "error": str(exc)}

    async def _run_rule_engine_via_api(self, records: List[Dict[str, Any]], entity_type: Optional[str] = None) -> Dict[str, Any]:
        """Call the backend rule engine execution endpoint."""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    f"{BACKEND_URL}/api/rules/execute",
                    json={"records": records, "entity_type": entity_type},
                )
                if resp.status_code == 200:
                    return resp.json()
        except Exception as exc:
            logger.warning("Rule engine API call failed: %s; falling back to direct execution", exc)

        # Direct ORM fallback (only when backend API unavailable)
        return self._run_rule_engine_direct(records, entity_type)

    def _run_rule_engine_direct(self, records: List[Dict[str, Any]], entity_type: Optional[str] = None) -> Dict[str, Any]:
        """Execute Rule Engine rule sets against the provided records (direct ORM fallback).

        Used only when the backend API is unavailable.
        """
        try:
            from core.db_session import SessionLocal
            from models.rule_engine_models import RuleSet, Rule, RuleStatus
            from services.rule_engine import RuleEngine
        except Exception as e:
            return {
                "quality_score": 0.0,
                "error": f"Rule engine import failed: {e}",
                "rule_sets_executed": 0,
            }

        db = SessionLocal()
        try:
            query = db.query(RuleSet).filter(
                RuleSet.is_active == True,  # noqa: E712
                RuleSet.status == RuleStatus.ACTIVE.value,
            )
            if entity_type:
                from sqlalchemy import or_
                query = query.filter(
                    or_(
                        RuleSet.target_entity_type == entity_type,
                        RuleSet.target_entity_type == None,  # noqa: E711
                    )
                )
            rule_sets = query.all()

            if not rule_sets:
                return {
                    "quality_score": 100.0,
                    "rule_sets_executed": 0,
                    "message": "No active rule sets configured",
                }

            engine = RuleEngine(db)
            all_results = []

            for rs in rule_sets:
                rules = (
                    db.query(Rule)
                    .filter(
                        Rule.rule_set_id == rs.id,
                        Rule.status == RuleStatus.ACTIVE.value,
                        Rule.enabled == True,  # noqa: E712
                    )
                    .order_by(Rule.sequence_order)
                    .all()
                )
                if not rules:
                    continue

                rule_set_dict = {
                    "id": rs.id,
                    "name": rs.name,
                    "execution_mode": rs.execution_mode,
                    "stop_on_critical": rs.stop_on_critical,
                }
                rules_dict = [
                    {
                        "id": r.id,
                        "name": r.name,
                        "expression": r.expression,
                        "level": r.level or "entity",
                        "severity": r.severity or "warning",
                        "action_on_fail": r.action_on_fail or "log",
                        "parent_rule_id": r.parent_rule_id,
                        "dependency_condition": r.dependency_condition,
                        "sequence_order": r.sequence_order,
                        "parameters": r.parameters or {},
                    }
                    for r in rules
                ]

                result = engine.execute_rule_set(
                    rule_set_dict, rules_dict, records,
                    stop_on_critical=rs.stop_on_critical,
                )
                all_results.append({
                    "rule_set_id": rs.id,
                    "rule_set_name": rs.name,
                    "status": result.status,
                    "overall_pass_rate": round(result.overall_pass_rate, 2),
                    "rules_passed": result.rules_passed,
                    "rules_failed": result.rules_failed,
                    "total_failures": result.total_failures,
                    "duration_ms": result.duration_ms,
                })

            quality_score = (
                sum(r["overall_pass_rate"] for r in all_results) / len(all_results)
                if all_results else 100.0
            )

            return {
                "quality_score": round(quality_score, 2),
                "rule_sets_executed": len(all_results),
                "results": all_results,
            }

        except Exception as e:
            return {
                "quality_score": 0.0,
                "error": str(e),
                "rule_sets_executed": 0,
            }
        finally:
            db.close()


agent = QualityMonitorAgent()
app = agent.app

if __name__ == "__main__":
    agent.start()

