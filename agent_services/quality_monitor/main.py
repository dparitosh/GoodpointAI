import sys
import os
import asyncio
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List
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
    async def _lifespan(self, app: FastAPI):
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

        async with super()._lifespan(app):
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

    def _run_rule_engine(self, records: List[Dict[str, Any]], entity_type: str = None) -> Dict[str, Any]:
        """Execute Rule Engine rule sets against the provided records.

        Loads active rule sets from Postgres, runs them synchronously, and
        returns a summary with quality_score.
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

            if all_results:
                quality_score = sum(r["overall_pass_rate"] for r in all_results) / len(all_results)
            else:
                quality_score = 100.0

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

    async def process_task(self, task: AgentTaskRequest):
        # Extract records and entity_type from payload
        records = task.payload.get("records", [])
        entity_type = task.payload.get("entity_type")

        # Run Rule Engine validation if records are provided
        rule_result: Dict[str, Any] = {}
        if records:
            loop = asyncio.get_running_loop()
            rule_result = await loop.run_in_executor(
                None, self._run_rule_engine, records, entity_type
            )

        quality_score = rule_result.get("quality_score", 100.0) if rule_result else 100.0

        return {
            "status": "Quality check completed", 
            "task_id": task.task_id,
            "quality_score": quality_score,
            "anomalies_found": rule_result.get("total_failures", 0)
                if rule_result else 0,
            "rule_validation": rule_result if rule_result else None,
            "timestamp": datetime.now().isoformat()
        }

if __name__ == "__main__":
    agent = QualityMonitorAgent()
    agent.start()
