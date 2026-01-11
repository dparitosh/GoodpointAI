"""
PLM Rule Engine - Core Execution Engine

Supports:
- Hierarchical rule execution (DAG-based)
- Three rule levels: Attribute, Entity, Relationship
- Multiple expression languages: Python, SQL, SparkSQL, Cypher
- Actions: Log, Warn, Quarantine, Reject, Transform, Escalate
"""

import logging
import re
import uuid
import json
import operator
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple, Callable
from dataclasses import dataclass, field
from collections import defaultdict
from functools import reduce
import ast

logger = logging.getLogger(__name__)


# ============================================================================
# EXPRESSION EVALUATORS
# ============================================================================

class SafeExpressionEvaluator:
    """
    Safe expression evaluator with sandboxed execution.
    Supports common PLM/ETL validation patterns.
    """
    
    # Allowed built-in functions
    SAFE_BUILTINS = {
        'len': len,
        'str': str,
        'int': int,
        'float': float,
        'bool': bool,
        'abs': abs,
        'min': min,
        'max': max,
        'sum': sum,
        'round': round,
        'sorted': sorted,
        'list': list,
        'dict': dict,
        'set': set,
        'tuple': tuple,
        'any': any,
        'all': all,
        'enumerate': enumerate,
        'zip': zip,
        'range': range,
        'isinstance': isinstance,
        'type': type,
    }
    
    # Custom PLM/ETL functions
    @staticmethod
    def size(obj: Any) -> int:
        """Get size of collection or string."""
        if obj is None:
            return 0
        return len(obj) if hasattr(obj, '__len__') else 0
    
    @staticmethod
    def is_empty(obj: Any) -> bool:
        """Check if value is empty/null."""
        if obj is None:
            return True
        if isinstance(obj, (str, list, dict, set)):
            return len(obj) == 0
        return False
    
    @staticmethod
    def is_not_null(obj: Any) -> bool:
        """Check if value is not null."""
        return obj is not None
    
    @staticmethod
    def matches_regex(value: str, pattern: str) -> bool:
        """Check if string matches regex pattern."""
        if value is None:
            return False
        try:
            return bool(re.match(pattern, str(value)))
        except re.error:
            return False
    
    @staticmethod
    def in_range(value: float, min_val: float, max_val: float) -> bool:
        """Check if numeric value is in range."""
        if value is None:
            return False
        try:
            return min_val <= float(value) <= max_val
        except (ValueError, TypeError):
            return False
    
    @staticmethod
    def in_list(value: Any, allowed: List[Any]) -> bool:
        """Check if value is in allowed list."""
        return value in allowed
    
    @staticmethod
    def starts_with(value: str, prefix: str) -> bool:
        """Check if string starts with prefix."""
        if value is None:
            return False
        return str(value).startswith(prefix)
    
    @staticmethod
    def ends_with(value: str, suffix: str) -> bool:
        """Check if string ends with suffix."""
        if value is None:
            return False
        return str(value).endswith(suffix)
    
    @staticmethod
    def contains(value: str, substring: str) -> bool:
        """Check if string contains substring."""
        if value is None:
            return False
        return substring in str(value)
    
    @staticmethod
    def sum_of(items: List[Any], field: str) -> float:
        """Sum a field across list of items."""
        total = 0.0
        for item in items or []:
            if isinstance(item, dict) and field in item:
                try:
                    total += float(item[field])
                except (ValueError, TypeError):
                    pass
        return total
    
    @staticmethod
    def count_where(items: List[Any], field: str, value: Any) -> int:
        """Count items where field equals value."""
        count = 0
        for item in items or []:
            if isinstance(item, dict) and item.get(field) == value:
                count += 1
        return count
    
    @staticmethod
    def has_circular_dependency(nodes: List[Dict], id_field: str = "id", ref_field: str = "parent_id") -> bool:
        """Detect circular dependencies in hierarchical data."""
        visited = set()
        rec_stack = set()
        
        # Build adjacency list
        graph = defaultdict(list)
        for node in nodes or []:
            node_id_raw = node.get(id_field)
            ref_id_raw = node.get(ref_field)
            if node_id_raw is not None and ref_id_raw is not None:
                node_id = str(node_id_raw)
                ref_id = str(ref_id_raw)
                if node_id and ref_id:
                    graph[ref_id].append(node_id)
        
        def has_cycle(node: str) -> bool:
            visited.add(node)
            rec_stack.add(node)
            
            for neighbor in graph[node]:
                if neighbor not in visited:
                    if has_cycle(neighbor):
                        return True
                elif neighbor in rec_stack:
                    return True
            
            rec_stack.discard(node)
            return False
        
        for node_id in {str(n.get(id_field)) for n in nodes or [] if n.get(id_field) is not None}:
            if node_id and node_id not in visited:
                if has_cycle(node_id):
                    return True
        return False
    
    def __init__(self):
        """Initialize evaluator with custom functions."""
        self.custom_functions = {
            'size': self.size,
            'is_empty': self.is_empty,
            'is_not_null': self.is_not_null,
            'matches_regex': self.matches_regex,
            'in_range': self.in_range,
            'in_list': self.in_list,
            'starts_with': self.starts_with,
            'ends_with': self.ends_with,
            'contains': self.contains,
            'sum_of': self.sum_of,
            'count_where': self.count_where,
            'has_circular_dependency': self.has_circular_dependency,
        }
    
    def evaluate(self, expression: str, context: Dict[str, Any]) -> Tuple[bool, Any, Optional[str]]:
        """
        Safely evaluate an expression.
        
        Returns:
            Tuple of (success, result, error_message)
        """
        try:
            # Build safe namespace
            safe_globals = {
                '__builtins__': self.SAFE_BUILTINS,
                **self.custom_functions,
            }
            
            # Add context variables
            safe_locals = dict(context)
            
            # Evaluate expression
            result = eval(expression, safe_globals, safe_locals)
            
            return True, result, None
            
        except Exception as e:
            logger.warning("Expression evaluation failed: %s - %s", expression[:100], str(e))
            return False, None, str(e)


# ============================================================================
# RULE EXECUTION CONTEXT
# ============================================================================

@dataclass
class RuleContext:
    """Context for rule execution."""
    record: Dict[str, Any] = field(default_factory=dict)
    record_id: Optional[str] = None
    parent_records: List[Dict[str, Any]] = field(default_factory=list)
    child_records: List[Dict[str, Any]] = field(default_factory=list)
    related_records: Dict[str, List[Dict[str, Any]]] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_eval_context(self) -> Dict[str, Any]:
        """Convert to evaluation context dict."""
        ctx = dict(self.record)
        ctx['_record'] = self.record
        ctx['_record_id'] = self.record_id
        ctx['_parent_records'] = self.parent_records
        ctx['_child_records'] = self.child_records
        ctx['_related'] = self.related_records
        ctx['_meta'] = self.metadata
        return ctx


@dataclass
class RuleResult:
    """Result of a single rule evaluation."""
    rule_id: str
    passed: bool
    value: Any = None
    error: Optional[str] = None
    records_checked: int = 0
    records_failed: int = 0
    failure_samples: List[Dict] = field(default_factory=list)
    duration_ms: int = 0
    action_taken: Optional[str] = None
    records_affected: int = 0


@dataclass 
class RuleSetResult:
    """Result of a rule set execution."""
    rule_set_id: str
    execution_id: str
    status: str = "pending"
    total_rules: int = 0
    rules_passed: int = 0
    rules_failed: int = 0
    rules_skipped: int = 0
    rules_error: int = 0
    total_records: int = 0
    total_failures: int = 0
    overall_pass_rate: float = 0.0
    rule_results: List[RuleResult] = field(default_factory=list)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_ms: int = 0
    error_message: Optional[str] = None


# ============================================================================
# RULE ENGINE
# ============================================================================

class RuleEngine:
    """
    PLM Rule Engine - Executes hierarchical rules against data.
    
    Supports:
    - DAG-based rule dependencies
    - Three rule levels (Attribute, Entity, Relationship)
    - Multiple execution modes (sequential, parallel, DAG)
    - Actions on failure (log, warn, quarantine, reject, transform)
    """
    
    def __init__(self, db_session=None):
        """Initialize rule engine."""
        self.db = db_session
        self.evaluator = SafeExpressionEvaluator()
        self._rule_cache: Dict[str, Any] = {}
        self._execution_results: Dict[str, RuleResult] = {}
    
    def execute_rule(
        self,
        rule: Dict[str, Any],
        context: RuleContext,
        parameters: Optional[Dict[str, Any]] = None
    ) -> RuleResult:
        """
        Execute a single rule against a context.
        
        Args:
            rule: Rule definition dict
            context: Execution context with record data
            parameters: Optional parameter overrides
            
        Returns:
            RuleResult with execution details
        """
        import time
        start_time = time.time()
        
        rule_id = rule.get('id', 'unknown')
        expression = rule.get('expression', 'True')
        
        # Merge parameters
        params = {**rule.get('parameters', {}), **(parameters or {})}
        
        # Build evaluation context
        eval_ctx = context.to_eval_context()
        eval_ctx.update(params)
        
        # Evaluate expression
        success, result, error = self.evaluator.evaluate(expression, eval_ctx)
        
        duration_ms = int((time.time() - start_time) * 1000)
        
        if not success:
            return RuleResult(
                rule_id=rule_id,
                passed=False,
                error=error,
                records_checked=1,
                records_failed=1,
                duration_ms=duration_ms
            )
        
        # Determine pass/fail based on result
        passed = bool(result)
        
        return RuleResult(
            rule_id=rule_id,
            passed=passed,
            value=result,
            records_checked=1,
            records_failed=0 if passed else 1,
            failure_samples=[context.record] if not passed else [],
            duration_ms=duration_ms
        )
    
    def execute_rule_batch(
        self,
        rule: Dict[str, Any],
        records: List[Dict[str, Any]],
        parameters: Optional[Dict[str, Any]] = None,
        max_failures: int = 100
    ) -> RuleResult:
        """
        Execute a rule against a batch of records.
        
        Args:
            rule: Rule definition
            records: List of records to check
            parameters: Optional parameters
            max_failures: Max failure samples to collect
            
        Returns:
            Aggregated RuleResult
        """
        import time
        start_time = time.time()
        
        rule_id = rule.get('id', 'unknown')
        
        passed_count = 0
        failed_count = 0
        failure_samples = []
        
        for record in records:
            ctx = RuleContext(record=record, record_id=str(record.get('id', '')))
            result = self.execute_rule(rule, ctx, parameters)
            
            if result.passed:
                passed_count += 1
            else:
                failed_count += 1
                if len(failure_samples) < max_failures:
                    failure_samples.append({
                        'record': record,
                        'error': result.error
                    })
        
        duration_ms = int((time.time() - start_time) * 1000)
        total = passed_count + failed_count
        
        return RuleResult(
            rule_id=rule_id,
            passed=failed_count == 0,
            records_checked=total,
            records_failed=failed_count,
            failure_samples=failure_samples,
            duration_ms=duration_ms
        )
    
    def _build_rule_dag(self, rules: List[Dict[str, Any]]) -> Dict[str, List[str]]:
        """Build DAG of rule dependencies."""
        dag = defaultdict(list)
        for rule in rules:
            parent_id = rule.get('parent_rule_id')
            if parent_id:
                dag[parent_id].append(rule['id'])
        return dag
    
    def _topological_sort(self, rules: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Sort rules in topological order based on dependencies."""
        # Build lookup and dependency graph
        rule_map = {r['id']: r for r in rules}
        in_degree = defaultdict(int)
        dag = defaultdict(list)
        
        for rule in rules:
            rule_id = rule['id']
            parent_id = rule.get('parent_rule_id')
            if parent_id and parent_id in rule_map:
                dag[parent_id].append(rule_id)
                in_degree[rule_id] += 1
        
        # Find roots (no dependencies)
        queue = [r for r in rules if in_degree[r['id']] == 0]
        queue.sort(key=lambda x: x.get('sequence_order', 0))
        
        sorted_rules = []
        while queue:
            rule = queue.pop(0)
            sorted_rules.append(rule)
            
            for child_id in dag[rule['id']]:
                in_degree[child_id] -= 1
                if in_degree[child_id] == 0:
                    queue.append(rule_map[child_id])
            
            queue.sort(key=lambda x: x.get('sequence_order', 0))
        
        # Check for cycles
        if len(sorted_rules) != len(rules):
            logger.warning("Circular dependency detected in rules")
            # Return original order for non-DAG rules
            return sorted(rules, key=lambda x: x.get('sequence_order', 0))
        
        return sorted_rules
    
    def execute_rule_set(
        self,
        rule_set: Dict[str, Any],
        rules: List[Dict[str, Any]],
        records: List[Dict[str, Any]],
        stop_on_critical: bool = True
    ) -> RuleSetResult:
        """
        Execute a complete rule set against records.
        
        Args:
            rule_set: Rule set definition
            rules: List of rules in the set
            records: Records to validate
            stop_on_critical: Stop execution if critical rule fails
            
        Returns:
            RuleSetResult with all execution details
        """
        import time
        start_time = time.time()
        
        execution_id = str(uuid.uuid4())
        result = RuleSetResult(
            rule_set_id=rule_set.get('id', 'unknown'),
            execution_id=execution_id,
            status='running',
            total_rules=len(rules),
            total_records=len(records),
            started_at=datetime.now(timezone.utc)
        )
        
        # Sort rules by dependency and sequence
        sorted_rules = self._topological_sort(rules)
        
        # Track parent rule results for dependency checking
        self._execution_results.clear()
        
        try:
            for rule in sorted_rules:
                # Check if rule should be skipped based on parent result
                if not self._should_execute_rule(rule):
                    result.rules_skipped += 1
                    continue
                
                # Execute rule against all records
                rule_result = self.execute_rule_batch(rule, records)
                self._execution_results[rule['id']] = rule_result
                result.rule_results.append(rule_result)
                
                # Update counters
                if rule_result.error:
                    result.rules_error += 1
                elif rule_result.passed:
                    result.rules_passed += 1
                else:
                    result.rules_failed += 1
                    result.total_failures += rule_result.records_failed
                    
                    # Check for critical failure
                    if stop_on_critical and rule.get('severity') == 'critical':
                        logger.warning("Critical rule %s failed, stopping execution", rule['id'])
                        break
            
            # Calculate overall pass rate
            if result.total_records > 0 and result.total_rules > 0:
                result.overall_pass_rate = (
                    (result.total_records * result.rules_passed - result.total_failures) /
                    (result.total_records * (result.rules_passed + result.rules_failed))
                    if (result.rules_passed + result.rules_failed) > 0 else 0.0
                ) * 100
            
            result.status = 'completed'
            
        except Exception as e:
            logger.error("Rule set execution failed: %s", e, exc_info=True)
            result.status = 'error'
            result.error_message = str(e)
        
        result.completed_at = datetime.now(timezone.utc)
        result.duration_ms = int((time.time() - start_time) * 1000)
        
        return result
    
    def _should_execute_rule(self, rule: Dict[str, Any]) -> bool:
        """Check if rule should execute based on parent dependencies."""
        parent_id = rule.get('parent_rule_id')
        if not parent_id:
            return True
        
        parent_result = self._execution_results.get(parent_id)
        if not parent_result:
            return True  # Parent not executed yet, proceed
        
        dependency_condition = rule.get('dependency_condition', 'parent_pass')
        
        if dependency_condition == 'parent_pass':
            return parent_result.passed
        elif dependency_condition == 'parent_fail':
            return not parent_result.passed
        elif dependency_condition == 'always':
            return True
        
        return True


# ============================================================================
# PREDEFINED RULE TEMPLATES
# ============================================================================

SYSTEM_RULE_TEMPLATES = [
    {
        "id": "NOT_NULL",
        "name": "Not Null Check",
        "description": "Validates that a field is not null or empty",
        "category": "data_quality",
        "level": "attribute",
        "expression_template": "is_not_null({{field}})",
        "parameter_schema": {
            "type": "object",
            "properties": {
                "field": {"type": "string", "description": "Field name to check"}
            },
            "required": ["field"]
        },
        "default_severity": "warning",
        "default_action": "log"
    },
    {
        "id": "UNIQUE",
        "name": "Uniqueness Check",
        "description": "Validates field values are unique across records",
        "category": "data_quality",
        "level": "entity",
        "expression_template": "len(set([r.get('{{field}}') for r in _related.get('all_records', [])])) == len(_related.get('all_records', []))",
        "parameter_schema": {
            "type": "object",
            "properties": {
                "field": {"type": "string"}
            },
            "required": ["field"]
        },
        "default_severity": "critical",
        "default_action": "reject"
    },
    {
        "id": "REGEX_MATCH",
        "name": "Regex Pattern Match",
        "description": "Validates field matches a regex pattern",
        "category": "data_quality",
        "level": "attribute",
        "expression_template": "matches_regex({{field}}, '{{pattern}}')",
        "parameter_schema": {
            "type": "object",
            "properties": {
                "field": {"type": "string"},
                "pattern": {"type": "string"}
            },
            "required": ["field", "pattern"]
        },
        "default_severity": "warning",
        "default_action": "log"
    },
    {
        "id": "RANGE_CHECK",
        "name": "Numeric Range Check",
        "description": "Validates numeric field is within range",
        "category": "data_quality",
        "level": "attribute",
        "expression_template": "in_range({{field}}, {{min}}, {{max}})",
        "parameter_schema": {
            "type": "object",
            "properties": {
                "field": {"type": "string"},
                "min": {"type": "number"},
                "max": {"type": "number"}
            },
            "required": ["field", "min", "max"]
        },
        "default_severity": "warning",
        "default_action": "log"
    },
    {
        "id": "IN_LIST",
        "name": "Value in Allowed List",
        "description": "Validates field value is in allowed list",
        "category": "data_quality",
        "level": "attribute",
        "expression_template": "in_list({{field}}, {{allowed_values}})",
        "parameter_schema": {
            "type": "object",
            "properties": {
                "field": {"type": "string"},
                "allowed_values": {"type": "array"}
            },
            "required": ["field", "allowed_values"]
        },
        "default_severity": "warning",
        "default_action": "log"
    },
    {
        "id": "FK_EXISTS",
        "name": "Foreign Key Exists",
        "description": "Validates foreign key reference exists",
        "category": "referential_integrity",
        "level": "relationship",
        "expression_template": "{{fk_field}} in [r.get('{{pk_field}}') for r in _related.get('{{target_entity}}', [])]",
        "parameter_schema": {
            "type": "object",
            "properties": {
                "fk_field": {"type": "string"},
                "pk_field": {"type": "string"},
                "target_entity": {"type": "string"}
            },
            "required": ["fk_field", "pk_field", "target_entity"]
        },
        "default_severity": "critical",
        "default_action": "quarantine"
    },
    {
        "id": "NO_CIRCULAR_DEPENDENCY",
        "name": "No Circular Dependencies",
        "description": "Detects circular dependencies in hierarchical data",
        "category": "business_logic",
        "level": "relationship",
        "expression_template": "not has_circular_dependency(_related.get('{{entity}}', []), '{{id_field}}', '{{parent_field}}')",
        "parameter_schema": {
            "type": "object",
            "properties": {
                "entity": {"type": "string"},
                "id_field": {"type": "string", "default": "id"},
                "parent_field": {"type": "string", "default": "parent_id"}
            },
            "required": ["entity"]
        },
        "default_severity": "blocker",
        "default_action": "reject"
    },
    {
        "id": "BOM_WEIGHT_SUM",
        "name": "BOM Weight Validation",
        "description": "Assembly weight must equal sum of component weights",
        "category": "business_logic",
        "level": "entity",
        "expression_template": "abs(weight - sum_of(_child_records, 'weight')) < {{tolerance}}",
        "parameter_schema": {
            "type": "object",
            "properties": {
                "tolerance": {"type": "number", "default": 0.01}
            }
        },
        "default_severity": "warning",
        "default_action": "warn"
    },
    {
        "id": "RELEASED_PART_COMPLETE",
        "name": "Released Part Completeness",
        "description": "Released parts must have all required attributes",
        "category": "business_logic",
        "level": "entity",
        "expression_template": "lifecycle_state != 'RELEASED' or (is_not_null(weight) and weight > 0 and size(cad_links) > 0)",
        "parameter_schema": {},
        "default_severity": "critical",
        "default_action": "quarantine"
    },
    {
        "id": "REVISION_FORMAT",
        "name": "Revision Format",
        "description": "Part revision must match standard format",
        "category": "compliance",
        "level": "attribute",
        "expression_template": "matches_regex(revision, '^[A-Z]{1,2}$')",
        "parameter_schema": {},
        "default_severity": "warning",
        "default_action": "log"
    }
]


def get_system_templates() -> List[Dict[str, Any]]:
    """Get all system rule templates."""
    return SYSTEM_RULE_TEMPLATES
