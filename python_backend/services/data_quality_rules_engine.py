"""
Data Quality Rules Engine - Execution & Validation Logic

Provides:
- Row-wise validation
- Dynamic rule evaluation
- Feedback generation per record
- Integration with existing quality monitoring
"""

import re
import pandas as pd
from typing import Dict, List, Optional, Any, Set, Tuple
from datetime import datetime
import logging

from models.data_quality_rules_models import (
    DataQualityRuleSet,
    ValidationResult,
    DataQualityReport,
    MandatoryFieldRule,
    UniqueConstraintRule,
    DropdownValueRule,
    FormatCheckRule,
    RangeCheckRule,
    DataTypeCheckRule,
    CrossFieldRule,
)

logger = logging.getLogger(__name__)


class DataQualityRulesEngine:
    """
    Main engine for executing configurable data quality rules
    
    Features:
    - Row-wise scanning of datasets
    - Configurable mandatory field validation
    - Uniqueness constraint checking
    - Dropdown/reference value validation
    - Format, range, and data type checks
    - Cross-field validation
    - Detailed feedback per record
    """
    
    def __init__(self, rule_set: DataQualityRuleSet):
        """Initialize engine with rule set"""
        self.rule_set = rule_set
        self.validation_results: List[ValidationResult] = []
        self.rule_violation_counts: Dict[str, int] = {}
        
    def validate_dataset(self, df: pd.DataFrame) -> DataQualityReport:
        """
        Validate entire dataset against rule set
        
        Args:
            df: Input DataFrame to validate
            
        Returns:
            DataQualityReport with all validation results
        """
        logger.info(f"Starting validation with rule set: {self.rule_set.name}")
        
        self.validation_results = []
        self.rule_violation_counts = {}
        
        # Build lookup for uniqueness checks (scan all values first)
        unique_field_values: Dict[str, Set] = {}
        composite_unique_values: Dict[str, Set[Tuple]] = {}
        
        for rule in self.rule_set.uniqueness_rules:
            if len(rule.fields) == 1:
                unique_field_values[rule.fields[0]] = set()
            else:
                unique_field_values[tuple(rule.fields)] = set()
        
        # Process each row
        for idx, row in df.iterrows():
            result = ValidationResult(
                row_number=idx + 1,  # 1-based indexing for user
                is_valid=True,
                violations=[],
                feedback=""
            )
            
            # Apply rules in order
            self._validate_mandatory_fields(row, result)
            self._validate_format_checks(row, result)
            self._validate_data_types(row, result)
            self._validate_range_checks(row, result)
            self._validate_dropdown_values(row, result)
            self._validate_uniqueness(row, result, unique_field_values, idx)
            self._validate_cross_field(row, result)
            
            # Generate final feedback
            result.feedback = "; ".join(result.violations) if result.violations else "OK"
            self.validation_results.append(result)
            
            logger.debug(f"Row {idx + 1}: {result.feedback}")
        
        # Generate report
        report = self._generate_report()
        logger.info(f"Validation complete: {report.valid_records}/{report.total_records} passed")
        
        return report
    
    def validate_row(self, row_data: Dict[str, Any]) -> ValidationResult:
        """
        Validate a single row of data
        
        Args:
            row_data: Dictionary of column values
            
        Returns:
            ValidationResult for this row
        """
        result = ValidationResult(
            row_number=0,
            is_valid=True,
            violations=[],
            feedback=""
        )
        
        # Apply all rules
        self._validate_mandatory_fields(row_data, result)
        self._validate_format_checks(row_data, result)
        self._validate_data_types(row_data, result)
        self._validate_range_checks(row_data, result)
        self._validate_dropdown_values(row_data, result)
        self._validate_cross_field(row_data, result)
        
        # Generate feedback
        result.feedback = "; ".join(result.violations) if result.violations else "OK"
        
        return result
    
    def _validate_mandatory_fields(self, row: Any, result: ValidationResult):
        """Check mandatory field rules"""
        for rule in self.rule_set.mandatory_rules:
            try:
                missing_fields = []
                
                for field in rule.fields:
                    value = self._get_field_value(row, field)
                    if value is None or (isinstance(value, str) and value.strip() == ""):
                        missing_fields.append(field)
                
                if missing_fields:
                    if rule.composite and len(missing_fields) < len(rule.fields):
                        # Only some fields missing in composite rule
                        msg = f"{', '.join(missing_fields)} required (part of mandatory combination)"
                    elif len(missing_fields) == 1:
                        msg = f"{missing_fields[0]} is mandatory"
                    else:
                        msg = f"Mandatory fields missing: {', '.join(missing_fields)}"
                    
                    result.add_violation(msg)
                    self._increment_rule_violation(rule.rule_name)
                    
            except Exception as e:
                logger.error(f"Error in mandatory field rule '{rule.rule_name}': {str(e)}")
    
    def _validate_uniqueness(self, row: Any, result: ValidationResult, 
                            unique_field_values: Dict, row_idx: int):
        """Check uniqueness constraint rules"""
        for rule in self.rule_set.uniqueness_rules:
            try:
                # Get field values
                values = []
                has_null = False
                
                for field in rule.fields:
                    value = self._get_field_value(row, field)
                    if value is None or (isinstance(value, str) and value.strip() == ""):
                        has_null = True
                        break
                    values.append(value)
                
                # Check if already seen
                if has_null and not rule.allow_null:
                    msg = f"NULL not allowed in {rule.fields[0] if len(rule.fields) == 1 else 'combination'}"
                    result.add_violation(msg)
                    self._increment_rule_violation(rule.rule_name)
                elif not has_null:
                    key = tuple(values) if len(values) > 1 else values[0]
                    
                    if key in unique_field_values.get(rule.fields[0] if len(rule.fields) == 1 else tuple(rule.fields), set()):
                        field_str = rule.fields[0] if len(rule.fields) == 1 else f"{' + '.join(rule.fields)}"
                        msg = f"Duplicate {field_str}: {key}"
                        result.add_violation(msg)
                        self._increment_rule_violation(rule.rule_name)
                    else:
                        # Mark as seen
                        if len(rule.fields) == 1:
                            unique_field_values[rule.fields[0]].add(key)
                        else:
                            unique_field_values[tuple(rule.fields)].add(key)
                            
            except Exception as e:
                logger.error(f"Error in uniqueness rule '{rule.rule_name}': {str(e)}")
    
    def _validate_dropdown_values(self, row: Any, result: ValidationResult):
        """Check dropdown/reference value rules"""
        for rule in self.rule_set.dropdown_rules:
            try:
                value = self._get_field_value(row, rule.field_name)
                
                if value is None or (isinstance(value, str) and value.strip() == ""):
                    if not rule.allow_null:
                        msg = f"{rule.field_name} cannot be empty"
                        result.add_violation(msg)
                        self._increment_rule_violation(rule.rule_name)
                else:
                    # Check if value in allowed list
                    allowed = rule.allowed_values
                    if not rule.case_sensitive:
                        allowed = [v.lower() if isinstance(v, str) else v for v in allowed]
                        check_value = value.lower() if isinstance(value, str) else value
                    else:
                        check_value = value
                    
                    if check_value not in allowed:
                        msg = f"Invalid {rule.field_name}: {value}. Allowed values: {', '.join(str(v) for v in rule.allowed_values)}"
                        result.add_violation(msg)
                        self._increment_rule_violation(rule.rule_name)
                        
            except Exception as e:
                logger.error(f"Error in dropdown rule '{rule.rule_name}': {str(e)}")
    
    def _validate_format_checks(self, row: Any, result: ValidationResult):
        """Check format/pattern rules"""
        for rule in self.rule_set.format_rules:
            try:
                value = self._get_field_value(row, rule.field_name)
                
                if value is None or (isinstance(value, str) and value.strip() == ""):
                    if not rule.allow_null:
                        msg = f"{rule.field_name} cannot be empty"
                        result.add_violation(msg)
                        self._increment_rule_violation(rule.rule_name)
                else:
                    if not re.match(rule.pattern, str(value)):
                        msg = f"{rule.field_name} format invalid: {value}"
                        result.add_violation(msg)
                        self._increment_rule_violation(rule.rule_name)
                        
            except Exception as e:
                logger.error(f"Error in format rule '{rule.rule_name}': {str(e)}")
    
    def _validate_range_checks(self, row: Any, result: ValidationResult):
        """Check numeric range rules"""
        for rule in self.rule_set.range_rules:
            try:
                value = self._get_field_value(row, rule.field_name)
                
                if value is None or (isinstance(value, str) and value.strip() == ""):
                    if not rule.allow_null:
                        msg = f"{rule.field_name} cannot be empty"
                        result.add_violation(msg)
                        self._increment_rule_violation(rule.rule_name)
                else:
                    try:
                        num_value = float(value)
                        
                        if rule.min_value is not None and num_value < rule.min_value:
                            msg = f"{rule.field_name} value {num_value} is below minimum {rule.min_value}"
                            result.add_violation(msg)
                            self._increment_rule_violation(rule.rule_name)
                        elif rule.max_value is not None and num_value > rule.max_value:
                            msg = f"{rule.field_name} value {num_value} is above maximum {rule.max_value}"
                            result.add_violation(msg)
                            self._increment_rule_violation(rule.rule_name)
                    except (ValueError, TypeError):
                        msg = f"{rule.field_name} is not a valid number: {value}"
                        result.add_violation(msg)
                        self._increment_rule_violation(rule.rule_name)
                        
            except Exception as e:
                logger.error(f"Error in range rule '{rule.rule_name}': {str(e)}")
    
    def _validate_data_types(self, row: Any, result: ValidationResult):
        """Check data type rules"""
        for rule in self.rule_set.datatype_rules:
            try:
                value = self._get_field_value(row, rule.field_name)
                
                if value is None or (isinstance(value, str) and value.strip() == ""):
                    if not rule.allow_null:
                        msg = f"{rule.field_name} cannot be empty"
                        result.add_violation(msg)
                        self._increment_rule_violation(rule.rule_name)
                else:
                    if not self._check_data_type(value, rule.expected_type):
                        msg = f"{rule.field_name} expected {rule.expected_type}, got {type(value).__name__}"
                        result.add_violation(msg)
                        self._increment_rule_violation(rule.rule_name)
                        
            except Exception as e:
                logger.error(f"Error in data type rule '{rule.rule_name}': {str(e)}")
    
    def _validate_cross_field(self, row: Any, result: ValidationResult):
        """Check cross-field validation rules"""
        for rule in self.rule_set.cross_field_rules:
            try:
                # Build evaluation context
                eval_context = {}
                if isinstance(row, dict):
                    eval_context = row.copy()
                else:
                    # Convert Series to dict
                    eval_context = row.to_dict() if hasattr(row, 'to_dict') else dict(row)
                
                # Evaluate condition
                try:
                    result_bool = eval(rule.condition, {"__builtins__": {}}, eval_context)
                    if not result_bool:
                        result.add_violation(rule.error_message)
                        self._increment_rule_violation(rule.rule_name)
                except Exception as eval_error:
                    logger.error(f"Error evaluating condition in rule '{rule.rule_name}': {str(eval_error)}")
                    msg = f"Cross-field validation error: {str(eval_error)}"
                    result.add_violation(msg)
                    
            except Exception as e:
                logger.error(f"Error in cross-field rule '{rule.rule_name}': {str(e)}")
    
    @staticmethod
    def _get_field_value(row: Any, field_name: str) -> Any:
        """Safely get field value from row"""
        try:
            if isinstance(row, dict):
                return row.get(field_name)
            else:
                # Pandas Series
                return row.get(field_name) if hasattr(row, 'get') else getattr(row, field_name, None)
        except:
            return None
    
    @staticmethod
    def _check_data_type(value: Any, expected_type: str) -> bool:
        """Check if value matches expected data type"""
        try:
            if expected_type.lower() == 'int':
                int(value)
                return True
            elif expected_type.lower() == 'float':
                float(value)
                return True
            elif expected_type.lower() == 'string':
                return isinstance(value, str)
            elif expected_type.lower() == 'boolean':
                return isinstance(value, bool) or value.lower() in ['true', 'false']
            elif expected_type.lower() == 'date':
                pd.to_datetime(value)
                return True
            return True
        except:
            return False
    
    def _increment_rule_violation(self, rule_name: str):
        """Track violation count per rule"""
        if rule_name not in self.rule_violation_counts:
            self.rule_violation_counts[rule_name] = 0
        self.rule_violation_counts[rule_name] += 1
    
    def _generate_report(self) -> DataQualityReport:
        """Generate comprehensive validation report"""
        report = DataQualityReport(
            rule_set_id=self.rule_set.rule_set_id,
            total_records=len(self.validation_results),
            validation_results=self.validation_results,
            rule_violations=self.rule_violation_counts
        )
        
        report.calculate_statistics()
        
        # Find most common issues
        violation_counts: Dict[str, int] = {}
        for result in self.validation_results:
            for violation in result.violations:
                violation_counts[violation] = violation_counts.get(violation, 0) + 1
        
        report.most_common_issues = sorted(
            violation_counts.items(),
            key=lambda x: x[1],
            reverse=True
        )[:10]
        
        return report


def add_feedback_column(df: pd.DataFrame, rule_set: DataQualityRuleSet) -> pd.DataFrame:
    """
    Add feedback column to dataset with validation results
    
    Args:
        df: Input DataFrame
        rule_set: DataQualityRuleSet to apply
        
    Returns:
        DataFrame with 'Feedback' column added
    """
    engine = DataQualityRulesEngine(rule_set)
    report = engine.validate_dataset(df)
    
    # Create output dataframe
    output_df = df.copy()
    output_df['Feedback'] = [result.feedback for result in report.validation_results]
    
    return output_df, report


def get_rule_configuration_summary(rule_set: DataQualityRuleSet) -> Dict[str, Any]:
    """Get human-readable summary of rule configuration"""
    summary = {
        "rule_set_name": rule_set.name,
        "rule_set_id": rule_set.rule_set_id,
        "enabled": rule_set.enabled,
        "rules": {
            "mandatory_fields": len(rule_set.mandatory_rules),
            "uniqueness_constraints": len(rule_set.uniqueness_rules),
            "dropdown_values": len(rule_set.dropdown_rules),
            "format_checks": len(rule_set.format_rules),
            "range_checks": len(rule_set.range_rules),
            "data_type_checks": len(rule_set.datatype_rules),
            "cross_field_rules": len(rule_set.cross_field_rules),
            "total": (
                len(rule_set.mandatory_rules) +
                len(rule_set.uniqueness_rules) +
                len(rule_set.dropdown_rules) +
                len(rule_set.format_rules) +
                len(rule_set.range_rules) +
                len(rule_set.datatype_rules) +
                len(rule_set.cross_field_rules)
            )
        },
        "details": {
            "mandatory_fields": [
                {
                    "rule": r.rule_name,
                    "description": r.description,
                    "fields": r.fields,
                    "composite": r.composite
                }
                for r in rule_set.mandatory_rules
            ],
            "uniqueness_constraints": [
                {
                    "rule": r.rule_name,
                    "description": r.description,
                    "fields": r.fields,
                    "allow_null": r.allow_null
                }
                for r in rule_set.uniqueness_rules
            ],
            "dropdown_values": [
                {
                    "rule": r.rule_name,
                    "description": r.description,
                    "field": r.field_name,
                    "allowed_values": r.allowed_values,
                    "case_sensitive": r.case_sensitive
                }
                for r in rule_set.dropdown_rules
            ]
        }
    }
    
    return summary
