"""
Safe Rule Expression Evaluator

Evaluates rule expressions in Python and SQL with security constraints.
- Python: RestrictedPython for safe evaluation
- SQL: SQLAlchemy parameterized queries
"""

import logging
import re as _re
from collections import defaultdict
from typing import Any, Dict, List, Optional
from sqlalchemy import text as sql_text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class RuleExpressionExecutor:
    """Safely evaluate rule expressions"""

    # Whitelist of allowed Python functions for safe evaluation.
    # Mirrors SafeExpressionEvaluator.SAFE_BUILTINS in rule_engine.py so both
    # code paths share the same expression namespace.
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

    # Custom PLM/DQ helper functions available in rule expressions
    @staticmethod
    def _is_empty(obj) -> bool:
        """Check if value is empty/null."""
        if obj is None:
            return True
        if isinstance(obj, (str, list, dict, set)):
            return len(obj) == 0
        return False

    @staticmethod
    def _is_not_null(obj) -> bool:
        return obj is not None

    @staticmethod
    def _matches_regex(value, pattern: str) -> bool:
        import re as _re
        if value is None:
            return False
        try:
            return bool(_re.match(pattern, str(value)))
        except _re.error:
            return False

    @staticmethod
    def _contains(value, substring: str) -> bool:
        if value is None:
            return False
        return substring in str(value)

    @staticmethod
    def _in_range(value, min_val, max_val) -> bool:
        if value is None:
            return False
        try:
            return float(min_val) <= float(value) <= float(max_val)
        except (ValueError, TypeError):
            return False

    @staticmethod
    def _in_list(value, allowed) -> bool:
        return value in allowed

    @staticmethod
    def _size(obj) -> int:
        if obj is None:
            return 0
        return len(obj) if hasattr(obj, '__len__') else 0

    @staticmethod
    def _starts_with(value, prefix: str) -> bool:
        if value is None:
            return False
        return str(value).startswith(prefix)

    @staticmethod
    def _ends_with(value, suffix: str) -> bool:
        if value is None:
            return False
        return str(value).endswith(suffix)

    @staticmethod
    def _sum_of(items, field: str) -> float:
        total = 0.0
        for item in items or []:
            if isinstance(item, dict) and field in item:
                try:
                    total += float(item[field])
                except (ValueError, TypeError):
                    pass
        return total

    @staticmethod
    def _count_where(items, field: str, value) -> int:
        return sum(
            1 for item in (items or [])
            if isinstance(item, dict) and item.get(field) == value
        )

    @staticmethod
    def _has_circular_dependency(
        nodes: list,
        id_field: str = "id",
        ref_field: str = "parent_id",
    ) -> bool:
        """Detect circular dependencies in hierarchical data (iterative DFS).

        Mirrors SafeExpressionEvaluator.has_circular_dependency so both
        evaluator code-paths expose the same namespace to rule expressions.
        """
        graph: dict = defaultdict(list)
        for node in nodes or []:
            node_id_raw = node.get(id_field)
            ref_id_raw = node.get(ref_field)
            if node_id_raw is not None and ref_id_raw is not None:
                graph[str(ref_id_raw)].append(str(node_id_raw))

        all_ids = {
            str(n.get(id_field))
            for n in nodes or []
            if n.get(id_field) is not None
        }
        visited: set = set()
        for start in all_ids:
            if start in visited:
                continue
            stack: list = [(start, iter(graph[start]), {start})]
            while stack:
                node, children, ancestors = stack[-1]
                try:
                    child: str = next(children)
                    if child in ancestors:
                        return True
                    if child not in visited:
                        stack.append((child, iter(graph[child]), ancestors | {child}))
                except StopIteration:
                    visited.add(node)
                    stack.pop()
        return False

    @classmethod
    def _custom_functions(cls) -> dict:
        return {
            'is_empty':               cls._is_empty,
            'is_not_null':            cls._is_not_null,
            'matches_regex':          cls._matches_regex,
            'contains':               cls._contains,
            'in_range':               cls._in_range,
            'in_list':                cls._in_list,
            'size':                   cls._size,
            'starts_with':            cls._starts_with,
            'ends_with':              cls._ends_with,
            'sum_of':                 cls._sum_of,
            'count_where':            cls._count_where,
            # Parity with SafeExpressionEvaluator — required by NO_CIRCULAR_DEPENDENCY template
            'has_circular_dependency': cls._has_circular_dependency,
        }

    @staticmethod
    def evaluate_python_expression(
        expression: str,
        context: Dict[str, Any],
        timeout_seconds: float = 5.0
    ) -> bool:
        """
        Safely evaluate a Python expression.

        Args:
            expression: Python expression to evaluate (e.g., "value > 0 and value < 100")
            context: Dictionary of variables available in expression (field values)
            timeout_seconds: Max execution time

        Returns:
            Boolean result of expression

        Raises:
            ValueError: If expression is invalid or uses unsafe constructs
        """
        try:
            # Block patterns that can escape the sandbox via attribute traversal
            # or dynamic code execution, including dunder-access bypass routes.
            dangerous_patterns = [
                '__import__', 'eval', 'exec', 'compile',
                'open', 'file', 'input', 'globals', 'locals',
                '__dict__', '__class__', '__bases__', '__subclasses__',
                '__mro__', '__builtins__', '__code__', '__globals__',
                'getattr', 'setattr', 'delattr', 'hasattr',
                'lambda:',  # lambdas are risky
            ]

            expr_lower = expression.lower()
            for pattern in dangerous_patterns:
                if pattern in expr_lower:
                    raise ValueError(f"Expression contains forbidden pattern: {pattern}")

            # Use restricted globals/locals for safety
            safe_globals = {
                "__builtins__": RuleExpressionExecutor.SAFE_BUILTINS,
                **RuleExpressionExecutor._custom_functions(),
            }
            safe_locals = context.copy()

            # Pre-compile for performance; also surfaces SyntaxError early with
            # a cleaner message before eval() is called.
            compiled = compile(expression, "<rule>", "eval")
            result = eval(compiled, safe_globals, safe_locals)  # noqa: S307
            return bool(result)

        except TimeoutError:
            logger.error("Rule expression evaluation timed out: %s", expression)
            raise ValueError(f"Expression took too long to evaluate (>{timeout_seconds}s)")
        except SyntaxError as e:
            logger.error("Invalid rule expression syntax: %s - %s", expression, e)
            raise ValueError(f"Invalid expression syntax: {e}")
        except NameError as e:
            logger.error("Undefined variable in expression: %s - %s", expression, e)
            raise ValueError(f"Undefined variable in expression: {e}")
        except Exception as e:
            logger.error("Error evaluating rule expression: %s - %s", expression, e)
            raise ValueError(f"Error evaluating expression: {e}")

    @staticmethod
    def evaluate_sql_expression(
        expression: str,
        db: Session,
        table_name: str,
        entity_id: Optional[str] = None,
        params: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Safely evaluate a SQL expression using parameterized queries.

        Args:
            expression: SQL boolean expression (e.g., "weight > 0 AND weight < 1000")
            db: SQLAlchemy session
            table_name: Table to evaluate against
            entity_id: Optional entity ID to filter single row
            params: Additional parameters for expression

        Returns:
            Boolean result

        Raises:
            ValueError: If SQL is invalid or unsafe
        """
        try:
            # Validate table name against a strict identifier pattern rather than
            # relying on isalnum() alone, which allows schema-qualified names like
            # "public.plm_parts" and rejects injection attempts.
            import re as _re
            if not _re.fullmatch(r'[A-Za-z_][A-Za-z0-9_.]{0,127}', table_name):
                raise ValueError(f"Invalid table name: {table_name}")

            # Build parameterized query
            if entity_id:
                query = f"SELECT 1 FROM {table_name} WHERE id = :entity_id AND ({expression}) LIMIT 1"
                bind_params = {'entity_id': entity_id}
            else:
                query = f"SELECT COUNT(*) FROM {table_name} WHERE {expression}"
                bind_params = params or {}

            # Execute with SQLAlchemy to prevent injection
            result = db.execute(sql_text(query), bind_params).scalar()
            return bool(result)

        except Exception as e:
            logger.error("Error evaluating SQL expression: %s - %s", expression, e)
            raise ValueError(f"Error evaluating SQL expression: {e}")

    @staticmethod
    def evaluate_null_check(value: Any) -> bool:
        """Check if value is null/None/empty string"""
        return value is None or value == ""

    @staticmethod
    def evaluate_uniqueness(values: list) -> bool:
        """Check if all values are unique"""
        return len(values) == len(set(str(v) for v in values))

    @staticmethod
    def evaluate_regex_match(pattern: str, value: str) -> bool:
        """Check if value matches regex pattern"""
        import re
        try:
            return bool(re.match(pattern, str(value)))
        except Exception as e:
            logger.error("Regex match failed: pattern=%s, error=%s", pattern, e)
            return False

    @staticmethod
    def evaluate_value_range(value: Any, min_val: Any = None, max_val: Any = None) -> bool:
        """Check if value is within range"""
        try:
            num_value = float(value)
            if min_val is not None and num_value < float(min_val):
                return False
            if max_val is not None and num_value > float(max_val):
                return False
            return True
        except (TypeError, ValueError):
            return False


class ExpressionEvaluationError(Exception):
    """Error evaluating rule expression"""
    pass


class RuleRegistry:
    """Pre-compiles a list of Rule expression strings once for efficient batch evaluation.

    Build one registry before the batch loop begins; the compiled code objects are
    then reused across every record, eliminating repeated parse overhead.

    Usage::
        registry = RuleRegistry(rules)
        for record in records:
            violations = registry.evaluate(record)

    ``compile_errors`` holds any rules that could not be compiled (SyntaxError at
    rule-creation time); they are skipped during ``evaluate`` and reported back so
    the caller can include them in the run-level error log.
    """

    def __init__(self, rules: list) -> None:
        self._safe_globals: Dict[str, Any] = {
            "__builtins__": RuleExpressionExecutor.SAFE_BUILTINS,
            **RuleExpressionExecutor._custom_functions(),
        }
        # List of (rule_obj, compiled_code) pairs ready for eval
        self._compiled: list = []
        # Rules that failed to compile — reported but never executed
        self.compile_errors: List[Dict[str, Any]] = []

        for rule in rules:
            try:
                code_obj = compile(
                    getattr(rule, "expression", "True"),
                    f"<rule:{getattr(rule, 'id', 'unknown')}>",
                    "eval",
                )
                self._compiled.append((rule, code_obj))
            except SyntaxError as exc:
                self.compile_errors.append({
                    "rule_id":       getattr(rule, "id", "unknown"),
                    "rule_name":     getattr(rule, "name", "unknown"),
                    "exception_type": "SyntaxError",
                    "detail":        str(exc),
                })

    def evaluate(self, record: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Evaluate all compiled rules against one record.

        Returns a list of violation dicts (empty list = all rules passed).

        Each violation dict contains:
          rule_id, rule_name, severity, action,
          exception_type (None for a logic failure, class name for a runtime error),
          detail (present only for runtime errors).
        """
        violations: List[Dict[str, Any]] = []
        safe_locals: Dict[str, Any] = {"record": record, **record}
        for rule, code_obj in self._compiled:
            try:
                passed = bool(eval(code_obj, self._safe_globals, safe_locals))  # noqa: S307
                if not passed:
                    violations.append({
                        "rule_id":       getattr(rule, "id", "unknown"),
                        "rule_name":     getattr(rule, "name", "unknown"),
                        "severity":      getattr(rule, "severity", "warning"),
                        "action":        getattr(rule, "action_on_fail", "log"),
                        "exception_type": None,
                    })
            except Exception as exc:  # noqa: BLE001
                violations.append({
                    "rule_id":       getattr(rule, "id", "unknown"),
                    "rule_name":     getattr(rule, "name", "unknown"),
                    "severity":      "error",
                    "action":        "log",
                    "exception_type": type(exc).__name__,
                    "detail":        str(exc),
                })
        return violations
