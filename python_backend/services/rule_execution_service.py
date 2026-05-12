"""
Rule Execution Service

Orchestrates rule validation and enforcement.
- Execute rule sets against entity data
- Track execution results
- Quarantine failed records
- Update execution statistics
"""

import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from models.rule_engine_models import (
    RuleSet, Rule, RuleSetExecution, ExecutionStatus, QuarantineRecord
)
from services.rule_expression_executor import RuleExpressionExecutor

logger = logging.getLogger(__name__)


class RuleViolation:
    """Represents a single rule violation"""

    def __init__(
        self,
        rule_id: str,
        rule_name: str,
        severity: str,
        message: str,
        action: str
    ):
        self.rule_id = rule_id
        self.rule_name = rule_name
        self.severity = severity
        self.message = message
        self.action = action

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "rule_name": self.rule_name,
            "severity": self.severity,
            "message": self.message,
            "action": self.action
        }


class RuleExecutionResult:
    """Result of rule set execution"""

    def __init__(
        self,
        rule_set_id: str,
        entity_id: str,
        passed: bool,
        violations: List[RuleViolation],
        quarantined: bool = False,
        duration_ms: float = 0.0
    ):
        self.rule_set_id = rule_set_id
        self.entity_id = entity_id
        self.passed = passed
        self.violations = violations
        self.quarantined = quarantined
        self.duration_ms = duration_ms

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rule_set_id": self.rule_set_id,
            "entity_id": self.entity_id,
            "passed": self.passed,
            "violations": [v.to_dict() for v in self.violations],
            "quarantined": self.quarantined,
            "duration_ms": self.duration_ms
        }


class RuleExecutionService:
    """Service for executing rules and managing validation"""

    def __init__(self, db: Session):
        self.db = db
        self.executor = RuleExpressionExecutor()

    async def execute_rule_set(
        self,
        rule_set_id: str,
        entity_data: Dict[str, Any],
        entity_id: Optional[str] = None,
        table_name: Optional[str] = None
    ) -> RuleExecutionResult:
        """
        Execute all rules in a rule set against entity data.

        Args:
            rule_set_id: ID of the rule set to execute
            entity_data: Dictionary of entity field values
            entity_id: Optional entity ID for database queries
            table_name: Optional table name for SQL rule evaluation

        Returns:
            RuleExecutionResult with pass/fail status and violations
        """
        start_time = time.time()

        try:
            # Load rule set
            rule_set = self.db.query(RuleSet).filter(RuleSet.id == rule_set_id).first()
            if not rule_set:
                # Unknown rule_set_id → treat as a config error, not a pass.
                # Returning passed=True here would silently allow bad data through.
                logger.error("Rule set not found: %s — returning empty-violation result", rule_set_id)
                return RuleExecutionResult(
                    rule_set_id=rule_set_id,
                    entity_id=entity_id or "unknown",
                    passed=False,
                    violations=[RuleViolation(
                        rule_id="system",
                        rule_name="RuleSet Lookup",
                        severity="error",
                        message=f"Rule set '{rule_set_id}' not found",
                        action="log",
                    )],
                    duration_ms=0.0,
                )

            # Validate rule set is active
            if not rule_set.is_active:
                logger.debug("Rule set is inactive: %s", rule_set_id)
                return RuleExecutionResult(
                    rule_set_id=rule_set_id,
                    entity_id=entity_id or "unknown",
                    passed=True,
                    violations=[],
                    duration_ms=0.0
                )

            # Execute rules
            violations: List[RuleViolation] = []
            # Bug 7 fix: filter out disabled/inactive rules so they don’t silently execute
            rules = (
                self.db.query(Rule)
                .filter(
                    Rule.rule_set_id == rule_set_id,
                    Rule.enabled == True,  # noqa: E712
                )
                .order_by(Rule.sequence_order)
                .all()
            )

            for rule in rules:
                try:
                    violation = await self._execute_single_rule(
                        rule, entity_data, entity_id, table_name
                    )
                    if violation:
                        violations.append(violation)
                        # Check if we should stop on critical
                        if rule_set.stop_on_critical and violation.severity == "critical":
                            break
                except Exception as e:
                    logger.error("Error executing rule %s: %s", rule.id, e)
                    violations.append(
                        RuleViolation(
                            rule_id=rule.id,
                            rule_name=rule.name,
                            severity="error",
                            message=f"Rule execution error: {str(e)}",
                            action="log"
                        )
                    )

            # Determine if overall pass/fail
            passed = len(violations) == 0
            quarantined = False

            # Check if any violation requires quarantine
            if not passed:
                for violation in violations:
                    if violation.action == "quarantine":
                        quarantined = True
                        break

            duration_ms = (time.time() - start_time) * 1000

            return RuleExecutionResult(
                rule_set_id=rule_set_id,
                entity_id=entity_id or "unknown",
                passed=passed,
                violations=violations,
                quarantined=quarantined,
                duration_ms=duration_ms
            )

        except Exception as e:
            logger.error("Error executing rule set %s: %s", rule_set_id, e)
            duration_ms = (time.time() - start_time) * 1000
            return RuleExecutionResult(
                rule_set_id=rule_set_id,
                entity_id=entity_id or "unknown",
                passed=False,
                violations=[RuleViolation(
                    rule_id="system",
                    rule_name="System Error",
                    severity="critical",
                    message=f"Rule execution failed: {str(e)}",
                    action="log"
                )],
                quarantined=False,
                duration_ms=duration_ms
            )

    async def _execute_single_rule(
        self,
        rule: Rule,
        entity_data: Dict[str, Any],
        entity_id: Optional[str],
        table_name: Optional[str]
    ) -> Optional[RuleViolation]:
        """Execute a single rule and return violation if failed"""

        try:
            rule_passed = False

            # Evaluate based on rule level and expression language
            if rule.expression_language == "python":
                # Inject `record` and `_related` so expression templates
                # like `is_empty(record.get('field'))` and
                # IS_NOT_UNIQUE / FK_EXISTS (which use `_related`) resolve
                # correctly without raising NameError.
                rule_passed = self.executor.evaluate_python_expression(
                    rule.expression,
                    {
                        "record": entity_data,
                        "_related": {},           # populated by caller when available
                        **entity_data,
                        **(rule.parameters or {}),
                    },
                )
            elif rule.expression_language == "sql":
                if not table_name or not entity_id:
                    logger.warning("SQL rule requires table_name and entity_id: %s", rule.id)
                    return None

                rule_passed = self.executor.evaluate_sql_expression(
                    rule.expression,
                    self.db,
                    table_name,
                    entity_id,
                    rule.parameters
                )
            else:
                # Bug 8 fix: unknown expression language is a configuration error,
                # not a silent pass.  Create a warning violation so the operator
                # knows the rule was not evaluated.
                logger.warning(
                    "Unsupported expression language '%s' for rule %s — skipping with warning",
                    rule.expression_language, rule.id,
                )
                return RuleViolation(
                    rule_id=rule.id,
                    rule_name=rule.name,
                    severity="warning",
                    message=f"Unsupported expression language: {rule.expression_language}",
                    action="log",
                )

            # If rule passed, no violation
            if rule_passed:
                return None

            # Rule failed - create violation
            return RuleViolation(
                rule_id=rule.id,
                rule_name=rule.name,
                severity=rule.severity,
                message=f"Rule '{rule.name}' failed: {rule.description}",
                action=rule.action_on_fail
            )

        except Exception as e:
            logger.error("Error executing rule %s: %s", rule.id, e)
            return RuleViolation(
                rule_id=rule.id,
                rule_name=rule.name,
                severity="warning",
                message=f"Rule evaluation error: {str(e)}",
                action="log"
            )

    def record_execution(
        self,
        rule_set_id: str,
        execution_id: str,
        result: RuleExecutionResult
    ) -> None:
        """Record rule set execution result in database"""

        try:
            rule_set_exec = self.db.query(RuleSetExecution).filter(
                RuleSetExecution.id == execution_id
            ).first()

            if rule_set_exec:
                rule_set_exec.status = ExecutionStatus.COMPLETED.value
                rule_set_exec.completed_at = datetime.now(timezone.utc)
                rule_set_exec.duration_ms = result.duration_ms
                # passed_count = rules executed minus violations (not always identical
                # to total rules because stop_on_critical may short-circuit early).
                total_rules = len(result.violations) + (1 if result.passed else 0)
                rule_set_exec.passed_count = 0 if not result.passed else max(0, total_rules - len(result.violations))
                rule_set_exec.failed_count = len(result.violations)
                rule_set_exec.result = {
                    "passed": result.passed,
                    "violations": [v.to_dict() for v in result.violations],
                    "quarantined": result.quarantined
                }
                self.db.commit()
                logger.info(
                    "Recorded rule set execution: %s (passed=%s, violations=%d)",
                    execution_id, result.passed, len(result.violations)
                )

        except Exception as e:
            logger.error("Error recording execution: %s", e)
            self.db.rollback()

    async def quarantine_record(
        self,
        record_data: Dict[str, Any],
        rule_set_id: str,
        violations: List[RuleViolation],
        source_table: str = "unknown"
    ) -> None:
        """Move a record to quarantine due to rule violations"""

        try:
            quarantine_record = QuarantineRecord(
                record_data=record_data,
                rule_set_id=rule_set_id,
                violations=[v.to_dict() for v in violations],
                source_table=source_table,
                status="pending_review",
                created_at=datetime.now(timezone.utc)
            )
            self.db.add(quarantine_record)
            self.db.commit()
            logger.info(
                "Quarantined record from %s (rule_set=%s, violations=%d)",
                source_table, rule_set_id, len(violations)
            )

        except Exception as e:
            logger.error("Error quarantining record: %s", e)
            self.db.rollback()

    async def release_from_quarantine(
        self,
        quarantine_id: str,
        target_table: str,
        released_by: str
    ) -> bool:
        """Release a record from quarantine to target table"""

        try:
            quarantine = self.db.query(QuarantineRecord).filter(
                QuarantineRecord.id == quarantine_id
            ).first()

            if not quarantine:
                logger.warning("Quarantine record not found: %s", quarantine_id)
                return False

            # Update quarantine status
            quarantine.status = "released"
            quarantine.released_at = datetime.now(timezone.utc)
            quarantine.released_by = released_by

            # In production, would insert the record_data into target_table here
            # For now, just mark as released
            self.db.add(quarantine)
            self.db.commit()

            logger.info("Released record from quarantine: %s", quarantine_id)
            return True

        except Exception as e:
            logger.error("Error releasing quarantine record: %s", e)
            self.db.rollback()
            return False
