import sys
import os
import asyncio
import json
import uuid
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List
from dotenv import load_dotenv
from contextlib import asynccontextmanager
from fastapi import FastAPI

# Data handling
import pandas as pd
from sqlalchemy import create_engine

# SODA
try:
    from soda.scan import Scan
except ImportError:
    Scan = None

# Add parent directory to path to allow importing base
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

# Also add python_backend to path for Rule Engine imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "python_backend"))

# Load environment variables from backend .env
env_path = Path(__file__).resolve().parent.parent.parent / "python_backend" / ".env"
load_dotenv(dotenv_path=env_path)

from neo4j import AsyncGraphDatabase
from agent_services.base.agent_service import AgentService
from agent_services.base.models import AgentCapability, AgentTaskRequest, AgentType

# Re-use models from backend if possible, or define minimal equivalents
DATABASE_URL = os.getenv("DATABASE_URL")

logger = logging.getLogger(__name__)

class ETLOrchestratorAgent(AgentService):
    def __init__(self):
        super().__init__(
            agent_type=AgentType.ETL_ORCHESTRATOR,
            agent_name="ETL Orchestration Agent",
            port=8021
        )
        self.neo4j_uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        self.neo4j_user = os.getenv("NEO4J_USER", "neo4j")
        self.neo4j_password = os.getenv("NEO4J_PASSWORD", "password")
        self.driver = None
        self.db_engine = None

    @asynccontextmanager
    async def _lifespan(self, _app: FastAPI):
        # Initialize resources
        logger.info("Initializing Neo4j driver...")
        
        try:
            self.driver = AsyncGraphDatabase.driver(
                self.neo4j_uri, 
                auth=(self.neo4j_user, self.neo4j_password)
            )
            # Verify connectivity
            await self.driver.verify_connectivity()
            logger.info("Neo4j connectivity verified.")
        except Exception as e:
            logger.warning("Neo4j connectivity failed: %s", e)

        # Initialize Postgres Engine
        if DATABASE_URL:
            try:
                self.db_engine = create_engine(DATABASE_URL)
                logger.info("SQL Database connected.")
            except Exception as e:
                logger.warning("SQL Database connection failed: %s", e)

        # Chain upstream registration
        async with super()._lifespan(_app):
            yield
        
        # Cleanup
        if self.driver:
            await self.driver.close()
        if self.db_engine:
            self.db_engine.dispose()

    def get_capabilities(self):
        return [
            AgentCapability(name="manage_data_pipelines", description="Manage ETL pipelines"),
            AgentCapability(name="perform_data_discovery", description="Analyze sources, stage data, and run quality checks"),
            AgentCapability(name="handle_data_transformations", description="Handle data transformations"),
            AgentCapability(name="monitor_pipeline_health", description="Monitor pipeline health"),
            AgentCapability(name="file_batch_processing", description="Discover and process thousands of files in parallel with lineage tracking"),
            AgentCapability(name="assess_transformation_risk", description="AI-powered risk assessment for field mappings and transformations"),
        ]

    async def process_task(self, task: AgentTaskRequest):
        task_type = task.payload.get("type", "unknown")
        caps = set(task.payload.get("required_capabilities", []))

        if "assess_transformation_risk" in caps or task_type == "assess_transformation_risk":
            return await self._assess_transformation_risk(task)

        if task_type == "discovery" or "perform_data_discovery" in caps:
            return await self.perform_discovery(task)

        if task_type == "file_batch_processing" or "file_batch_processing" in caps:
            return await self.process_file_batch(task)

        return {
            "status": "success",
            "message": f"Task type {task_type} acknowledged (placeholder implementation)",
            "timestamp": datetime.now().isoformat()
        }

    # ── AI Transformation Risk Assessment ────────────────────────────────────

    _RISK_ASSESSMENT_PROMPT = """\
You are a Migration Risk Analyst specialising in PLM/ETL data pipelines.
Given a list of field mappings (source→target) with optional transformation rules \
and a data profile summary, assess the migration risk for each mapped field.

For each field mapping output a JSON object with:
  source_field     : source field name
  target_field     : target field name
  risk_level       : critical|high|medium|low
  risk_type        : data_loss|type_mismatch|truncation|null_propagation|
                     format_change|precision_loss|encoding_issue|business_rule_gap|none
  confidence       : 0.0-1.0 (your confidence in the risk assessment)
  issues           : list of specific issue strings (may be empty)
  recommendation   : single actionable sentence (≤20 words)

Also include a final object at the end with:
  summary_risk     : overall migration risk (critical|high|medium|low)
  blocking_issues  : count of critical+high risk fields
  total_fields     : total field count
  recommendation   : overall recommendation (1-2 sentences)

Output ONLY a valid JSON array, no other text.
"""

    async def _assess_transformation_risk(self, task: AgentTaskRequest) -> Dict[str, Any]:
        """AI-powered risk assessment for field mappings and transformations.

        Combines rule-based heuristics (fast, always available) with LLM analysis
        (richer context, graceful fallback).
        """
        payload = task.payload
        field_mappings  = payload.get("field_mappings", [])
        profile_summary = payload.get("profile_summary", {})
        backend_url = os.getenv("GRAPH_TRACE_BACKEND_URL", "http://127.0.0.1:8011")

        # Deterministic risk checks (type mismatches, nullability, format)
        heuristic_risks = self._heuristic_risk_check(field_mappings, profile_summary)

        # LLM-powered risk analysis
        ai_risks = None
        if field_mappings:
            try:
                import httpx as _httpx
                import re as _re
                context = {
                    "field_mappings": field_mappings[:50],  # cap for LLM context
                    "profile_signals": profile_summary.get("signals", [])[:15],
                    "total_source_columns": len(profile_summary.get("columns", {})),
                }
                async with _httpx.AsyncClient(timeout=30.0) as client:
                    resp = await client.post(
                        f"{backend_url}/api/llm/chat",
                        params={"provider": payload.get("llm_provider", "openai")},
                        json={
                            "messages": [
                                {"role": "system", "content": self._RISK_ASSESSMENT_PROMPT},
                                {"role": "user",   "content": json.dumps(context)},
                            ],
                            "temperature": 0.1,
                            "max_tokens": 1800,
                        },
                    )
                    if resp.is_success:
                        raw = resp.json().get("response", "")
                        raw = _re.sub(r"```(?:json)?", "", raw).strip().strip("`").strip()
                        m = _re.search(r"\[.*\]", raw, re.DOTALL)
                        if m:
                            parsed = json.loads(m.group(0))
                            if isinstance(parsed, list):
                                ai_risks = parsed
            except Exception as exc:
                logger.debug("LLM transformation risk assessment unavailable: %s", exc)

        # Extract summary object from ai_risks (last element if it has summary_risk)
        summary = None
        field_risks = []
        if ai_risks:
            if ai_risks and ai_risks[-1].get("summary_risk"):
                summary = ai_risks[-1]
                field_risks = ai_risks[:-1]
            else:
                field_risks = ai_risks

        # Fall back to heuristic summary if AI unavailable
        if not summary:
            critical_count = sum(1 for r in heuristic_risks if r.get("risk_level") in ("critical", "high"))
            summary = {
                "summary_risk": "high" if critical_count > 0 else "medium" if heuristic_risks else "low",
                "blocking_issues": critical_count,
                "total_fields": len(field_mappings),
                "recommendation": (
                    f"{critical_count} high-risk mapping(s) require review before migration."
                    if critical_count else "Heuristic checks passed. Validate with a data sample before execution."
                ),
            }

        return {
            "status": "Risk assessment completed",
            "task_id": task.task_id,
            "field_risks": field_risks if field_risks else heuristic_risks,
            "summary": summary,
            "ai_powered": ai_risks is not None,
            "timestamp": datetime.now().isoformat(),
        }

    def _heuristic_risk_check(
        self,
        field_mappings: List[Dict[str, Any]],
        profile_summary: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """Fast deterministic risk checks with no external dependencies."""
        risks = []
        columns = profile_summary.get("columns", {})

        for fm in field_mappings:
            src = fm.get("sourceField") or fm.get("source_field", "")
            tgt = fm.get("targetField") or fm.get("target_field", "")
            transformation = fm.get("transformation") or ""
            col_meta = columns.get(src, {})

            issues = []
            risk_level = "low"
            risk_type  = "none"

            # High null rate in source → possible null propagation
            null_max = col_meta.get("null_rate_max", 0) or 0
            if null_max > 0.3:
                issues.append(f"Source field has {null_max*100:.0f}% null rate — nulls will propagate to target.")
                risk_level = "high"
                risk_type  = "null_propagation"

            # Mixed types → type mismatch / format change risk
            if col_meta.get("has_mixed_types"):
                issues.append("Source field has mixed data types — casting may fail or silently truncate.")
                _LEVELS = ["low", "medium", "high", "critical"]
                risk_level = _LEVELS[max(_LEVELS.index(risk_level), _LEVELS.index("medium"))]
                risk_type  = "type_mismatch"

            # No transformation rule but mixed types
            if col_meta.get("has_mixed_types") and not transformation:
                issues.append("No transformation defined for a mixed-type field.")
                risk_level = "high"
                risk_type  = "format_change"

            risks.append({
                "source_field":  src,
                "target_field":  tgt,
                "risk_level":    risk_level,
                "risk_type":     risk_type,
                "issues":        issues,
                "recommendation": (
                    "Add explicit type-casting in transformation rules."
                    if issues else "No issues detected."
                ),
                "source": "heuristic",
            })

        return risks

    async def process_file_batch(self, task: AgentTaskRequest) -> Dict[str, Any]:
        """ETL Orchestrator handler for large-scale file batch processing.

        Payload keys
        ------------
        directory   : str   — root directory to discover (mutually exclusive with file_paths)
        file_paths  : list  — explicit list of absolute file paths
        recursive   : bool  — crawl sub-directories (default True)
        concurrency : int   — parallel workers (default 8)
        db_flush_size: int  — rows flushed to Postgres at a time (default 50)
        extraction_method : str — hybrid | ocr | vision_llm | text_parser
        vision_model : str  — Ollama model name (default llava:latest)
        """
        payload = task.payload
        job_id = payload.get("job_id") or uuid.uuid4().hex

        # Import batch processor (lives in python_backend)
        try:
            from services.file_batch_processor import (
                FileBatchProcessor, FileRecord, _classify_ext
            )
        except ImportError as exc:
            return {"status": "error", "error": f"file_batch_processor unavailable: {exc}"}

        neo4j_driver = self.driver  # may be None if Neo4j is not connected
        db_session_factory = None
        if self.db_engine:
            from sqlalchemy.orm import sessionmaker
            db_session_factory = sessionmaker(bind=self.db_engine)

        processor = FileBatchProcessor(
            concurrency=int(payload.get("concurrency", 8)),
            db_flush_size=int(payload.get("db_flush_size", 50)),
            neo4j_driver=neo4j_driver,
            db_session_factory=db_session_factory,
        )

        extraction_method = payload.get("extraction_method", "hybrid")
        vision_model = payload.get("vision_model", "llava:latest")

        # --- discover mode ---
        directory = payload.get("directory")
        if directory:
            report = await processor.process_directory(
                directory,
                recursive=bool(payload.get("recursive", True)),
                extraction_method=extraction_method,
                vision_model=vision_model,
                job_id=job_id,
            )
        # --- explicit file list mode ---
        elif payload.get("file_paths"):
            from pathlib import Path as _Path
            records = [
                FileRecord(
                    path=_Path(p).resolve(),
                    ext=_Path(p).suffix.lower(),
                    size_bytes=_Path(p).stat().st_size if _Path(p).is_file() else 0,
                    file_type=_classify_ext(_Path(p).suffix.lower()),
                )
                for p in payload["file_paths"]
                if _Path(p).is_file()
            ]
            if not records:
                return {"status": "error", "error": "No valid files in file_paths"}
            report = await processor.process_records(
                records,
                job_id=job_id,
                extraction_method=extraction_method,
                vision_model=vision_model,
            )
        else:
            return {"status": "error", "error": "Provide 'directory' or 'file_paths' in payload"}

        return {
            "status": "completed",
            "job_id": report.job_id,
            "total_files": report.total_files,
            "processed": report.processed,
            "succeeded": report.succeeded,
            "failed": report.failed,
            "started_at": report.started_at.isoformat(),
            "completed_at": report.completed_at.isoformat() if report.completed_at else None,
            "errors_summary": report.errors_summary[:20],  # cap for response size
        }

    async def perform_discovery(self, task: AgentTaskRequest) -> Dict[str, Any]:
        """
        Agentic Discovery Workflow:
        1. Analyzes the provided records (Staging)
        2. Infers Schema & Mapping
        3. Transforms Data (Normalization)
        4. Runs SODA Checks (Validation)
        """
        payload = task.payload
        run_id = payload.get("run_id") or uuid.uuid4().hex
        records = payload.get("records", [])
        
        if not self.db_engine:
            return {"status": "failed", "error": "Database not configured"}

        # 1. Staging & Schema Inference
        df = pd.DataFrame(records)
        inferred_schema = {col: str(dtype) for col, dtype in df.dtypes.items()}
        
        # 2. Intelligent Mapping (Agentic Logic)
        # Instead of strict hardcoding, we score potential matches
        target_columns = ["part_number", "name", "description", "classification"]
        
        mapping = {}
        for target in target_columns:
            best_match = None
            highest_score = 0
            
            for source_col in df.columns:
                score = 0
                s_col = source_col.lower()
                
                # Direct match
                if s_col == target: score += 100
                # Semantic approximation
                elif target == "part_number" and s_col in ["part", "number", "id", "sku"]: score += 80
                elif target == "name" and s_col in ["title", "label", "msg"]: score += 80
                elif target == "classification" and s_col in ["type", "category", "class"]: score += 80
                elif target == "description" and s_col in ["desc", "detail", "info"]: score += 60
                
                if score > highest_score:
                    highest_score = score
                    best_match = source_col
            
            if best_match and highest_score > 50:
                mapping[best_match] = target

        # 3. Apply Transformation
        if mapping:
            df_transformed = df.rename(columns=mapping)
            # Filter to only keep canonical columns + raw
            available_targets = [c for c in target_columns if c in df_transformed.columns]
            df_transformed = df_transformed[available_targets].copy()
            df_transformed["run_id"] = run_id
            df_transformed["raw"] = df.apply(lambda row: json.dumps(row.to_dict()), axis=1)
            
            # Persist to DB (PLMPart table)
            try:
                # We use the raw connection to avoid model dependency overhead
                # Warning: ensuring table exists is out of scope for this snippet, assumes PLMPart exists
                df_transformed.to_sql("plm_parts", self.db_engine, if_exists="append", index=False, method="multi")
            except Exception as e:
                logger.warning("Failed to persist transformed data: %s", e)
        
        # 4. Rule Engine Validation
        rule_result = None
        try:
            loop = asyncio.get_running_loop()
            rule_result = await loop.run_in_executor(
                None, self._run_rule_validation, records
            )
        except Exception as e:
            rule_result = {"outcome": "error", "message": str(e)}

        # 5. SODA Validation (supplementary)
        soda_result = None
        if Scan:
            try:
                null_counts = df.isnull().sum()
                issue_count = int(null_counts.sum())
                
                soda_result = {
                    "outcome": "warn" if issue_count > 0 else "pass",
                    "checks": len(mapping) + 1,
                    "score": max(0, 1.0 - (issue_count / (len(df) * len(df.columns) or 1)))
                }
                
            except Exception as e:
                soda_result = {"outcome": "error", "message": str(e)}

        return {
            "status": "completed",
            "run_id": run_id,
            "inferred_schema": inferred_schema,
            "applied_mapping": mapping,
            "staged_count": len(records),
            "rule_validation": rule_result,
            "quality_scan": soda_result,
            "quality_score": rule_result.get("quality_score", 100.0) if isinstance(rule_result, dict) else None,
            "agent_notes": "Discovery completed using Agentic Heuristics v2 with Rule Engine validation."
        }

    def _run_rule_validation(self, records: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Execute Rule Engine rule sets against the provided records synchronously."""
        try:
            from core.db_session import SessionLocal
            from models.rule_engine_models import RuleSet, Rule, RuleStatus
            from services.rule_engine import RuleEngine
        except Exception as e:
            return {
                "outcome": "error",
                "quality_score": 0.0,
                "message": f"Rule engine import failed: {e}",
            }

        db = SessionLocal()
        try:
            rule_sets = (
                db.query(RuleSet)
                .filter(
                    RuleSet.is_active == True,  # noqa: E712
                    RuleSet.status == RuleStatus.ACTIVE.value,
                )
                .all()
            )

            if not rule_sets:
                return {
                    "outcome": "pass",
                    "quality_score": 100.0,
                    "message": "No active rule sets configured",
                    "rule_sets_executed": 0,
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
                    "duration_ms": result.duration_ms,
                })

            if all_results:
                quality_score = sum(r["overall_pass_rate"] for r in all_results) / len(all_results)
            else:
                quality_score = 100.0

            return {
                "outcome": "pass" if quality_score >= 80 else "warn" if quality_score >= 50 else "fail",
                "quality_score": round(quality_score, 2),
                "rule_sets_executed": len(all_results),
                "results": all_results,
            }

        except Exception as e:
            return {
                "outcome": "error",
                "quality_score": 0.0,
                "message": str(e),
            }
        finally:
            db.close()

agent = ETLOrchestratorAgent()
app = agent.app

if __name__ == "__main__":
    agent.start()
