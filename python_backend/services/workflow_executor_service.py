"""
Workflow Execution Service

Orchestrates workflow execution with DAG-based dependency resolution.
- Build directed acyclic graph (DAG) from workflow steps
- Execute steps in topological order
- Handle step failures and retries
- Track execution progress and metadata
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import httpx
from sqlalchemy import text as sql_text
from sqlalchemy.orm import Session

from models.workflow_models import (
    WorkflowDefinition,
    WorkflowExecution,
    WorkflowStep,
    WorkflowStepExecution,
    WorkflowStepStatus,
)
from services.rule_expression_executor import RuleExpressionExecutor

logger = logging.getLogger(__name__)


class DAGBuilder:
    """Build directed acyclic graph from workflow steps"""

    @staticmethod
    def build_dag(steps: List[WorkflowStep]) -> Dict[str, List[str]]:
        graph: Dict[str, List[str]] = {}
        all_step_ids = {step.id for step in steps}

        for step in steps:
            graph.setdefault(step.id, [])
            for dep_id in (step.depends_on or []):
                if dep_id in all_step_ids:
                    graph.setdefault(dep_id, []).append(step.id)

        return graph

    @staticmethod
    def topological_sort(graph: Dict[str, List[str]]) -> List[str]:
        in_degree = {node: 0 for node in graph}

        for node in graph:
            for neighbor in graph[node]:
                in_degree[neighbor] = in_degree.get(neighbor, 0) + 1

        queue = [node for node in graph if in_degree[node] == 0]
        result: List[str] = []

        while queue:
            node = queue.pop(0)
            result.append(node)

            for neighbor in graph[node]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if len(result) != len(graph):
            raise ValueError("Workflow contains circular dependencies")

        return result

    @staticmethod
    def validate_dag(steps: List[WorkflowStep]) -> Tuple[bool, Optional[str]]:
        graph = DAGBuilder.build_dag(steps)
        step_ids = set(graph.keys())

        for step in steps:
            for dep_id in (step.depends_on or []):
                if dep_id not in step_ids:
                    return False, f"Step {step.id} depends on non-existent step {dep_id}"

        try:
            DAGBuilder.topological_sort(graph)
            return True, None
        except ValueError as exc:
            return False, str(exc)


class WorkflowExecutor:
    """Execute workflows with step dependency resolution"""

    def __init__(self, db: Session):
        self.db = db
        self.dag_builder = DAGBuilder()
        self.expr_executor = RuleExpressionExecutor()

    async def execute_workflow(
        self,
        workflow_execution_id: str,
        max_parallel_steps: int = 1,
    ) -> bool:
        del max_parallel_steps  # reserved for future parallelism

        execution = self.db.query(WorkflowExecution).filter(
            WorkflowExecution.id == workflow_execution_id
        ).first()

        if not execution:
            logger.error("Workflow execution not found: %s", workflow_execution_id)
            return False

        try:
            workflow = self.db.query(WorkflowDefinition).filter(
                WorkflowDefinition.id == execution.workflow_id
            ).first()
            if not workflow:
                logger.error("Workflow definition not found: %s", execution.workflow_id)
                execution.status = WorkflowStepStatus.FAILED.value
                execution.error_message = "Workflow definition not found"
                execution.completed_at = datetime.now(timezone.utc)
                self.db.add(execution)
                self.db.commit()
                return False

            steps = self.db.query(WorkflowStep).filter(
                WorkflowStep.workflow_id == workflow.id
            ).order_by(WorkflowStep.sequence_order.asc()).all()

            is_valid, error = self.dag_builder.validate_dag(steps)
            if not is_valid:
                execution.status = WorkflowStepStatus.FAILED.value
                execution.error_message = error
                execution.completed_at = datetime.now(timezone.utc)
                self.db.add(execution)
                self.db.commit()
                return False

            execution_order = self.dag_builder.topological_sort(self.dag_builder.build_dag(steps))
            execution.status = WorkflowStepStatus.RUNNING.value
            execution.started_at = datetime.now(timezone.utc)
            execution.total_steps = len(steps)
            self.db.add(execution)
            self.db.commit()

            failed_steps: set[str] = set()
            results: Dict[str, Any] = {}

            step_map = {s.id: s for s in steps}
            for step_id in execution_order:
                step = step_map.get(step_id)
                if step is None:
                    continue

                dependency_failed = any(dep_id in failed_steps for dep_id in (step.depends_on or []))
                if dependency_failed:
                    failed_steps.add(step_id)
                    results[step_id] = {"success": False, "reason": "dependency_failed"}
                    continue

                success, result = await self._execute_step(step, execution.id)
                results[step_id] = result

                if not success and not step.allow_failure:
                    failed_steps.add(step_id)

                execution.completed_steps = len([r for r in results.values() if isinstance(r, dict) and r.get("success")])
                execution.failed_steps = len(failed_steps)
                execution.progress_percentage = (
                    (len(results) / len(steps)) * 100 if steps else 100.0
                )
                self.db.add(execution)
                self.db.commit()

            overall_success = len(failed_steps) == 0
            execution.status = (
                WorkflowStepStatus.COMPLETED.value if overall_success else WorkflowStepStatus.FAILED.value
            )
            execution.completed_at = datetime.now(timezone.utc)
            if execution.started_at:
                execution.duration_ms = int((execution.completed_at - execution.started_at).total_seconds() * 1000)
            execution.execution_metadata = {
                **(execution.execution_metadata or {}),
                "step_results": results,
                "execution_order": execution_order,
            }
            self.db.add(execution)
            self.db.commit()
            return overall_success

        except Exception as exc:  # pylint: disable=broad-exception-caught
            logger.error("Error executing workflow: %s", exc)
            execution.status = WorkflowStepStatus.FAILED.value
            execution.error_message = str(exc)
            execution.completed_at = datetime.now(timezone.utc)
            self.db.add(execution)
            self.db.commit()
            return False

    async def _execute_step(self, step: WorkflowStep, execution_id: str) -> Tuple[bool, Dict[str, Any]]:
        step_exec = WorkflowStepExecution(
            id=f"stepexec_{step.id}_{int(datetime.now(timezone.utc).timestamp())}",
            execution_id=execution_id,
            step_id=step.id,
            status=WorkflowStepStatus.RUNNING.value,
            started_at=datetime.now(timezone.utc),
            retry_count=0,
        )
        self.db.add(step_exec)
        self.db.commit()

        try:
            success, result_data = await self._dispatch_step(step)
            step_exec.status = WorkflowStepStatus.COMPLETED.value if success else WorkflowStepStatus.FAILED.value
            step_exec.completed_at = datetime.now(timezone.utc)
            step_exec.duration_ms = int((step_exec.completed_at - step_exec.started_at).total_seconds() * 1000)
            step_exec.result = {"success": success, **result_data}
            self.db.add(step_exec)
            self.db.commit()
            return success, {"success": success, **result_data}

        except Exception as exc:  # pylint: disable=broad-exception-caught
            step_exec.status = WorkflowStepStatus.FAILED.value
            step_exec.completed_at = datetime.now(timezone.utc)
            step_exec.error_message = str(exc)
            self.db.add(step_exec)
            self.db.commit()
            return False, {"success": False, "error": str(exc)}

    async def _dispatch_step(self, step: WorkflowStep) -> Tuple[bool, Dict[str, Any]]:
        step_type = (step.step_type or "").lower()

        if step_type == "sql":
            result = self.db.execute(sql_text(step.expression)).fetchall()
            return True, {"rows_affected": len(result)}

        if step_type == "python":
            result = self.expr_executor.evaluate_python_expression(
                step.expression,
                step.parameters or {},
            )
            return True, {"result": bool(result)}

        if step_type == "api":
            cfg = step.parameters or {}
            method = str(cfg.get("method", "GET")).upper()
            url = cfg.get("url")
            payload = cfg.get("payload", {})
            if not url:
                return False, {"error": "Missing API URL in parameters.url"}

            async with httpx.AsyncClient(timeout=30) as client:
                if method == "GET":
                    resp = await client.get(url)
                elif method == "POST":
                    resp = await client.post(url, json=payload)
                else:
                    return False, {"error": f"Unsupported HTTP method: {method}"}

            return resp.status_code < 400, {"status_code": resp.status_code}

        # Domain-specific step types currently map to metadata-only execution;
        # they are considered successful placeholders until concrete executors are added.
        if step_type in {"discovery", "profiling", "schema_mapping", "etl_execution", "validation"}:
            return True, {"stage": step.stage, "message": f"{step_type} placeholder executed"}

        return False, {"error": f"Unknown step type: {step.step_type}"}
