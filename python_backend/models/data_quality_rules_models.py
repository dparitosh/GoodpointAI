"""
Data Quality Rules Configuration Models

Supports configurable validation rules including:
- Mandatory fields (single and composite)
- Uniqueness constraints (single and composite)
- Dropdown/reference values
- Standard validation rules
"""

from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Set, Tuple
from enum import Enum


class RuleType(str, Enum):
    """Enumeration of rule types"""
    MANDATORY_FIELD = "mandatory_field"
    UNIQUE_CONSTRAINT = "unique_constraint"
    DROPDOWN_VALUE = "dropdown_value"
    FORMAT_CHECK = "format_check"
    DATA_TYPE_CHECK = "data_type_check"
    RANGE_CHECK = "range_check"
    PATTERN_MATCH = "pattern_match"
    CROSS_FIELD = "cross_field"
    CUSTOM = "custom"


class MandatoryFieldRule(BaseModel):
    """Single or composite mandatory field validation"""
    rule_name: str = Field(..., description="Unique rule identifier")
    description: Optional[str] = None
    fields: List[str] = Field(..., description="List of field names that must be non-null")
    composite: bool = Field(default=False, description="If True, all fields must be present together")
    
    class Config:
        example = {
            "rule_name": "mandatory_unit",
            "fields": ["Unit"],
            "composite": False,
            "description": "Unit field must have a value"
        }


class UniqueConstraintRule(BaseModel):
    """Single or composite uniqueness validation"""
    rule_name: str = Field(..., description="Unique rule identifier")
    description: Optional[str] = None
    fields: List[str] = Field(..., description="Field(s) that must be unique")
    allow_null: bool = Field(default=True, description="Whether NULL values are allowed (always unique)")
    
    class Config:
        example = {
            "rule_name": "unique_part_number",
            "fields": ["Part_Number"],
            "description": "Part_Number must be unique across dataset"
        }


class DropdownValueRule(BaseModel):
    """Reference value / dropdown validation"""
    rule_name: str = Field(..., description="Unique rule identifier")
    description: Optional[str] = None
    field_name: str = Field(..., description="Field to validate")
    allowed_values: List[str] = Field(..., description="List of allowed values")
    case_sensitive: bool = Field(default=False, description="Case sensitivity for matching")
    allow_null: bool = Field(default=False, description="Whether NULL is a valid value")
    
    class Config:
        example = {
            "rule_name": "lifecycle_state_validation",
            "field_name": "Lifecycle_State",
            "allowed_values": ["Released", "In Work", "Obsolete"],
            "description": "Lifecycle_State must be one of the predefined values"
        }


class FormatCheckRule(BaseModel):
    """Pattern-based validation"""
    rule_name: str = Field(..., description="Unique rule identifier")
    description: Optional[str] = None
    field_name: str = Field(..., description="Field to validate")
    pattern: str = Field(..., description="Regex pattern for validation")
    allow_null: bool = Field(default=True, description="Whether NULL values are allowed")
    
    class Config:
        example = {
            "rule_name": "part_number_format",
            "field_name": "Part_Number",
            "pattern": r"^P-\d{5}$",
            "description": "Part_Number must match format P-XXXXX"
        }


class RangeCheckRule(BaseModel):
    """Numeric range validation"""
    rule_name: str = Field(..., description="Unique rule identifier")
    description: Optional[str] = None
    field_name: str = Field(..., description="Field to validate")
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    allow_null: bool = Field(default=True)
    
    class Config:
        example = {
            "rule_name": "quantity_range",
            "field_name": "Quantity",
            "min_value": 0,
            "max_value": 10000,
            "description": "Quantity must be between 0 and 10000"
        }


class DataTypeCheckRule(BaseModel):
    """Data type validation"""
    rule_name: str = Field(..., description="Unique rule identifier")
    description: Optional[str] = None
    field_name: str = Field(..., description="Field to validate")
    expected_type: str = Field(..., description="Expected data type (int, float, string, date, boolean)")
    allow_null: bool = Field(default=True)
    
    class Config:
        example = {
            "rule_name": "unit_cost_numeric",
            "field_name": "Unit_Cost",
            "expected_type": "float"
        }


class CrossFieldRule(BaseModel):
    """Cross-field validation logic"""
    rule_name: str = Field(..., description="Unique rule identifier")
    description: Optional[str] = None
    condition: str = Field(..., description="Python expression comparing fields (e.g., 'End_Date > Start_Date')")
    error_message: str = Field(..., description="Message when condition fails")
    
    class Config:
        example = {
            "rule_name": "date_range_validation",
            "condition": "End_Date >= Start_Date",
            "error_message": "End_Date must be after or equal to Start_Date"
        }


class DataQualityRuleSet(BaseModel):
    """Complete rule set for data quality validation"""
    rule_set_id: str = Field(default_factory=lambda: f"ruleset_{int(__import__('time').time() * 1000)}")
    name: str = Field(..., description="Descriptive name for the rule set")
    description: Optional[str] = None
    enabled: bool = Field(default=True)
    
    # Configurable rules
    mandatory_rules: List[MandatoryFieldRule] = Field(default_factory=list)
    uniqueness_rules: List[UniqueConstraintRule] = Field(default_factory=list)
    dropdown_rules: List[DropdownValueRule] = Field(default_factory=list)
    format_rules: List[FormatCheckRule] = Field(default_factory=list)
    range_rules: List[RangeCheckRule] = Field(default_factory=list)
    datatype_rules: List[DataTypeCheckRule] = Field(default_factory=list)
    cross_field_rules: List[CrossFieldRule] = Field(default_factory=list)
    
    # Metadata
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    created_by: Optional[str] = None
    
    class Config:
        example = {
            "name": "Parts Master Quality Rules",
            "description": "Quality rules for PLM parts data",
            "mandatory_rules": [
                {
                    "rule_name": "mandatory_unit",
                    "fields": ["Unit"],
                    "description": "Unit is required"
                }
            ],
            "uniqueness_rules": [
                {
                    "rule_name": "unique_part_number",
                    "fields": ["Part_Number"],
                    "description": "Part_Number must be unique"
                }
            ],
            "dropdown_rules": [
                {
                    "rule_name": "lifecycle_validation",
                    "field_name": "Lifecycle_State",
                    "allowed_values": ["Released", "In Work", "Obsolete"]
                }
            ]
        }


class ValidationResult(BaseModel):
    """Result of validating a single row"""
    row_number: int = Field(..., description="Row index in dataset")
    is_valid: bool = Field(..., description="Whether row passed all validations")
    violations: List[str] = Field(default_factory=list, description="List of validation violations")
    feedback: str = Field(default="", description="Concatenated feedback message")
    severity: str = Field(default="warning", description="Severity level: info, warning, error")
    
    def add_violation(self, message: str):
        """Add a violation and update feedback"""
        self.violations.append(message)
        self.feedback = "; ".join(self.violations)
        self.is_valid = False


class DataQualityReport(BaseModel):
    """Complete data quality validation report"""
    report_id: str = Field(default_factory=lambda: f"dq_report_{int(__import__('time').time() * 1000)}")
    rule_set_id: str
    total_records: int
    valid_records: int
    invalid_records: int
    validation_results: List[ValidationResult] = Field(default_factory=list)
    
    # Summary statistics
    passed_percentage: float = Field(default=0.0)
    failed_percentage: float = Field(default=0.0)
    
    # Rule-level statistics
    rule_violations: Dict[str, int] = Field(default_factory=dict, description="Count of violations per rule")
    
    # Feedback summary
    most_common_issues: List[Tuple[str, int]] = Field(default_factory=list)
    
    class Config:
        arbitrary_types_allowed = True
    
    def calculate_statistics(self):
        """Calculate percentage statistics"""
        if self.total_records > 0:
            self.valid_records = len([r for r in self.validation_results if r.is_valid])
            self.invalid_records = self.total_records - self.valid_records
            self.passed_percentage = (self.valid_records / self.total_records) * 100
            self.failed_percentage = (self.invalid_records / self.total_records) * 100
