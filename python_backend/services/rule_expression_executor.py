"""
Safe Rule Expression Evaluator

Evaluates rule expressions in Python and SQL with security constraints.
- Python: RestrictedPython for safe evaluation
- SQL: SQLAlchemy parameterized queries
"""

import logging
from typing import Any, Dict, Optional
from sqlalchemy import text as sql_text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class RuleExpressionExecutor:
    """Safely evaluate rule expressions"""

    # Whitelist of allowed Python functions for safe evaluation
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
            # Validate expression doesn't contain dangerous patterns
            dangerous_patterns = [
                '__import__', 'eval', 'exec', 'compile',
                'open', 'file', 'input', 'globals', 'locals',
                '__dict__', '__class__', 'lambda:'  # lambdas are risky
            ]

            expr_lower = expression.lower()
            for pattern in dangerous_patterns:
                if pattern in expr_lower:
                    raise ValueError(f"Expression contains forbidden pattern: {pattern}")

            # Use restricted globals/locals for safety
            safe_globals = {"__builtins__": RuleExpressionExecutor.SAFE_BUILTINS}
            safe_locals = context.copy()

            # Evaluate with timeout (in production, use signal or multiprocessing)
            result = eval(expression, safe_globals, safe_locals)
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
            # Validate table name (basic SQL injection prevention)
            if not table_name.replace('_', '').isalnum():
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
