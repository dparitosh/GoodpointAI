import sys
import os
import httpx
from datetime import datetime
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

from neo4j import AsyncGraphDatabase
from agent_services.base.agent_service import AgentService
from agent_services.base.models import AgentCapability, AgentTaskRequest, AgentType

# All DB access goes through the backend API — no direct ORM imports
BACKEND_URL = os.getenv("GRAPH_TRACE_BACKEND_URL", "http://localhost:8011")

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
        logger_name = f"{self.agent_name}.lifespan"
        try:
            self.driver = AsyncGraphDatabase.driver(
                self.neo4j_uri, 
                auth=(self.neo4j_user, self.neo4j_password)
            )
            await self.driver.verify_connectivity()
            print(f"[{logger_name}] Neo4j connectivity verified.")
        except Exception as e:
            print(f"[{logger_name}] WARNING: Neo4j connectivity failed: {e}")

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
        ]

    async def process_task(self, task: AgentTaskRequest):
        caps = set(task.payload.get("required_capabilities", []))

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
            "timestamp": datetime.now().isoformat(),
        }

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
                # Fall back to direct ORM if API route not available
        except Exception:
            pass

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

