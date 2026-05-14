"""
Comprehensive Test Suite for Data Quality Rules Engine

Run with: pytest python_backend/tests/test_data_quality_rules_comprehensive.py -v
"""

import pytest
import pandas as pd
from datetime import datetime, timedelta

from models.data_quality_rules_models import (
    DataQualityRuleSet,
    MandatoryFieldRule,
    UniqueConstraintRule,
    DropdownValueRule,
    FormatCheckRule,
    RangeCheckRule,
    DataTypeCheckRule,
    CrossFieldRule,
)
from services.data_quality_rules_engine import (
    DataQualityRulesEngine,
    add_feedback_column,
    get_rule_configuration_summary,
)


class TestMandatoryFieldRules:
    """Test mandatory field validation"""
    
    def test_single_mandatory_field_present(self):
        """Valid: Required field is present"""
        rule_set = DataQualityRuleSet(
            name="Test",
            mandatory_rules=[
                MandatoryFieldRule(rule_name="unit", fields=["Unit"])
            ]
        )
        
        engine = DataQualityRulesEngine(rule_set)
        result = engine.validate_row({"Part_Number": "P-001", "Unit": "EA"})
        
        assert result.is_valid
        assert result.feedback == "OK"
    
    def test_single_mandatory_field_missing(self):
        """Invalid: Required field is missing"""
        rule_set = DataQualityRuleSet(
            name="Test",
            mandatory_rules=[
                MandatoryFieldRule(rule_name="unit", fields=["Unit"])
            ]
        )
        
        engine = DataQualityRulesEngine(rule_set)
        result = engine.validate_row({"Part_Number": "P-001", "Unit": None})
        
        assert not result.is_valid
        assert "Unit is mandatory" in result.feedback
    
    def test_composite_mandatory_both_present(self):
        """Valid: Both fields in composite rule present"""
        rule_set = DataQualityRuleSet(
            name="Test",
            mandatory_rules=[
                MandatoryFieldRule(
                    rule_name="part_revision",
                    fields=["Part_Number", "Revision"],
                    composite=True
                )
            ]
        )
        
        engine = DataQualityRulesEngine(rule_set)
        result = engine.validate_row({
            "Part_Number": "P-001",
            "Revision": "A"
        })
        
        assert result.is_valid
    
    def test_composite_mandatory_partial_missing(self):
        """Invalid: One field missing in composite rule"""
        rule_set = DataQualityRuleSet(
            name="Test",
            mandatory_rules=[
                MandatoryFieldRule(
                    rule_name="part_revision",
                    fields=["Part_Number", "Revision"],
                    composite=True
                )
            ]
        )
        
        engine = DataQualityRulesEngine(rule_set)
        result = engine.validate_row({"Part_Number": "P-001", "Revision": None})
        
        assert not result.is_valid
        assert "mandatory" in result.feedback.lower()


class TestUniquenessRules:
    """Test uniqueness constraint validation"""
    
    def test_single_field_unique(self):
        """Valid: No duplicate values"""
        rule_set = DataQualityRuleSet(
            name="Test",
            uniqueness_rules=[
                UniqueConstraintRule(rule_name="unique_part", fields=["Part_Number"])
            ]
        )
        
        df = pd.DataFrame({
            'Part_Number': ['P-001', 'P-002', 'P-003']
        })
        
        engine = DataQualityRulesEngine(rule_set)
        report = engine.validate_dataset(df)
        
        assert report.valid_records == 3
        assert report.invalid_records == 0
    
    def test_single_field_duplicate(self):
        """Invalid: Duplicate value detected"""
        rule_set = DataQualityRuleSet(
            name="Test",
            uniqueness_rules=[
                UniqueConstraintRule(rule_name="unique_part", fields=["Part_Number"])
            ]
        )
        
        df = pd.DataFrame({
            'Part_Number': ['P-001', 'P-002', 'P-001']  # Duplicate
        })
        
        engine = DataQualityRulesEngine(rule_set)
        report = engine.validate_dataset(df)
        
        assert report.valid_records == 2
        assert report.invalid_records == 1
        assert report.validation_results[2].violations[0].startswith("Duplicate")
    
    def test_composite_unique(self):
        """Valid: Composite uniqueness"""
        rule_set = DataQualityRuleSet(
            name="Test",
            uniqueness_rules=[
                UniqueConstraintRule(
                    rule_name="unique_combo",
                    fields=["Part_Number", "Revision"]
                )
            ]
        )
        
        df = pd.DataFrame({
            'Part_Number': ['P-001', 'P-001', 'P-002'],
            'Revision': ['A', 'B', 'A']  # Combinations are unique
        })
        
        engine = DataQualityRulesEngine(rule_set)
        report = engine.validate_dataset(df)
        
        assert report.valid_records == 3
    
    def test_composite_duplicate(self):
        """Invalid: Duplicate composite key"""
        rule_set = DataQualityRuleSet(
            name="Test",
            uniqueness_rules=[
                UniqueConstraintRule(
                    rule_name="unique_combo",
                    fields=["Part_Number", "Revision"]
                )
            ]
        )
        
        df = pd.DataFrame({
            'Part_Number': ['P-001', 'P-001', 'P-001'],
            'Revision': ['A', 'A', 'B']  # First two are duplicate
        })
        
        engine = DataQualityRulesEngine(rule_set)
        report = engine.validate_dataset(df)
        
        assert report.invalid_records == 1


class TestDropdownRules:
    """Test dropdown/reference value validation"""
    
    def test_valid_dropdown_value(self):
        """Valid: Value is in allowed list"""
        rule_set = DataQualityRuleSet(
            name="Test",
            dropdown_rules=[
                DropdownValueRule(
                    rule_name="lifecycle",
                    field_name="Lifecycle_State",
                    allowed_values=["Released", "In Work", "Obsolete"]
                )
            ]
        )
        
        engine = DataQualityRulesEngine(rule_set)
        result = engine.validate_row({
            "Part_Number": "P-001",
            "Lifecycle_State": "Released"
        })
        
        assert result.is_valid
    
    def test_invalid_dropdown_value(self):
        """Invalid: Value not in allowed list"""
        rule_set = DataQualityRuleSet(
            name="Test",
            dropdown_rules=[
                DropdownValueRule(
                    rule_name="lifecycle",
                    field_name="Lifecycle_State",
                    allowed_values=["Released", "In Work", "Obsolete"]
                )
            ]
        )
        
        engine = DataQualityRulesEngine(rule_set)
        result = engine.validate_row({
            "Part_Number": "P-001",
            "Lifecycle_State": "Approved"
        })
        
        assert not result.is_valid
        assert "Invalid" in result.feedback
    
    def test_case_insensitive_dropdown(self):
        """Valid: Case-insensitive matching"""
        rule_set = DataQualityRuleSet(
            name="Test",
            dropdown_rules=[
                DropdownValueRule(
                    rule_name="lifecycle",
                    field_name="Lifecycle_State",
                    allowed_values=["Released", "In Work"],
                    case_sensitive=False
                )
            ]
        )
        
        engine = DataQualityRulesEngine(rule_set)
        result = engine.validate_row({
            "Lifecycle_State": "RELEASED"  # Uppercase
        })
        
        assert result.is_valid


class TestFormatRules:
    """Test format/pattern validation"""
    
    def test_valid_pattern(self):
        """Valid: Value matches pattern"""
        rule_set = DataQualityRuleSet(
            name="Test",
            format_rules=[
                FormatCheckRule(
                    rule_name="part_format",
                    field_name="Part_Number",
                    pattern=r"^P-\d{5}$"
                )
            ]
        )
        
        engine = DataQualityRulesEngine(rule_set)
        result = engine.validate_row({"Part_Number": "P-00001"})
        
        assert result.is_valid
    
    def test_invalid_pattern(self):
        """Invalid: Value doesn't match pattern"""
        rule_set = DataQualityRuleSet(
            name="Test",
            format_rules=[
                FormatCheckRule(
                    rule_name="part_format",
                    field_name="Part_Number",
                    pattern=r"^P-\d{5}$"
                )
            ]
        )
        
        engine = DataQualityRulesEngine(rule_set)
        result = engine.validate_row({"Part_Number": "P-ABC"})
        
        assert not result.is_valid
        assert "format invalid" in result.feedback


class TestRangeRules:
    """Test numeric range validation"""
    
    def test_within_range(self):
        """Valid: Value within range"""
        rule_set = DataQualityRuleSet(
            name="Test",
            range_rules=[
                RangeCheckRule(
                    rule_name="quantity_range",
                    field_name="Quantity",
                    min_value=0,
                    max_value=10000
                )
            ]
        )
        
        engine = DataQualityRulesEngine(rule_set)
        result = engine.validate_row({"Quantity": 100})
        
        assert result.is_valid
    
    def test_below_minimum(self):
        """Invalid: Value below minimum"""
        rule_set = DataQualityRuleSet(
            name="Test",
            range_rules=[
                RangeCheckRule(
                    rule_name="quantity_range",
                    field_name="Quantity",
                    min_value=0,
                    max_value=10000
                )
            ]
        )
        
        engine = DataQualityRulesEngine(rule_set)
        result = engine.validate_row({"Quantity": -5})
        
        assert not result.is_valid
        assert "below minimum" in result.feedback
    
    def test_above_maximum(self):
        """Invalid: Value above maximum"""
        rule_set = DataQualityRuleSet(
            name="Test",
            range_rules=[
                RangeCheckRule(
                    rule_name="quantity_range",
                    field_name="Quantity",
                    min_value=0,
                    max_value=10000
                )
            ]
        )
        
        engine = DataQualityRulesEngine(rule_set)
        result = engine.validate_row({"Quantity": 15000})
        
        assert not result.is_valid
        assert "above maximum" in result.feedback


class TestDataTypeRules:
    """Test data type validation"""
    
    def test_valid_integer(self):
        """Valid: Integer type"""
        rule_set = DataQualityRuleSet(
            name="Test",
            datatype_rules=[
                DataTypeCheckRule(
                    rule_name="quantity_int",
                    field_name="Quantity",
                    expected_type="int"
                )
            ]
        )
        
        engine = DataQualityRulesEngine(rule_set)
        result = engine.validate_row({"Quantity": 100})
        
        assert result.is_valid
    
    def test_valid_float(self):
        """Valid: Float type"""
        rule_set = DataQualityRuleSet(
            name="Test",
            datatype_rules=[
                DataTypeCheckRule(
                    rule_name="cost_float",
                    field_name="Unit_Cost",
                    expected_type="float"
                )
            ]
        )
        
        engine = DataQualityRulesEngine(rule_set)
        result = engine.validate_row({"Unit_Cost": 99.99})
        
        assert result.is_valid


class TestCrossFieldRules:
    """Test cross-field validation"""
    
    def test_valid_cross_field_condition(self):
        """Valid: Cross-field condition satisfied"""
        rule_set = DataQualityRuleSet(
            name="Test",
            cross_field_rules=[
                CrossFieldRule(
                    rule_name="date_logic",
                    condition="End_Date >= Start_Date",
                    error_message="End must be after Start"
                )
            ]
        )
        
        engine = DataQualityRulesEngine(rule_set)
        result = engine.validate_row({
            "Start_Date": "2024-01-01",
            "End_Date": "2024-12-31"
        })
        
        assert result.is_valid
    
    def test_invalid_cross_field_condition(self):
        """Invalid: Cross-field condition failed"""
        rule_set = DataQualityRuleSet(
            name="Test",
            cross_field_rules=[
                CrossFieldRule(
                    rule_name="date_logic",
                    condition="End_Date >= Start_Date",
                    error_message="End must be after Start"
                )
            ]
        )
        
        engine = DataQualityRulesEngine(rule_set)
        result = engine.validate_row({
            "Start_Date": "2024-12-31",
            "End_Date": "2024-01-01"
        })
        
        assert not result.is_valid
        assert "End must be after Start" in result.feedback


class TestCombinedRules:
    """Test multiple rule types together"""
    
    def test_all_rules_passing(self):
        """Valid: All rule types pass"""
        rule_set = DataQualityRuleSet(
            name="Comprehensive",
            mandatory_rules=[
                MandatoryFieldRule(rule_name="unit", fields=["Unit"])
            ],
            uniqueness_rules=[
                UniqueConstraintRule(rule_name="unique_part", fields=["Part_Number"])
            ],
            dropdown_rules=[
                DropdownValueRule(
                    rule_name="lifecycle",
                    field_name="Lifecycle_State",
                    allowed_values=["Released", "In Work"]
                )
            ]
        )
        
        df = pd.DataFrame({
            'Part_Number': ['P-001', 'P-002'],
            'Unit': ['EA', 'EA'],
            'Lifecycle_State': ['Released', 'In Work']
        })
        
        engine = DataQualityRulesEngine(rule_set)
        report = engine.validate_dataset(df)
        
        assert report.valid_records == 2
        assert report.invalid_records == 0
    
    def test_multiple_violations_per_row(self):
        """Invalid: Multiple violations in single row"""
        rule_set = DataQualityRuleSet(
            name="Comprehensive",
            mandatory_rules=[
                MandatoryFieldRule(rule_name="unit", fields=["Unit"]),
                MandatoryFieldRule(rule_name="material", fields=["Material"])
            ],
            dropout_rules=[
                DropdownValueRule(
                    rule_name="lifecycle",
                    field_name="Lifecycle_State",
                    allowed_values=["Released", "In Work"]
                )
            ]
        )
        
        engine = DataQualityRulesEngine(rule_set)
        result = engine.validate_row({
            "Part_Number": "P-001",
            "Unit": None,
            "Material": None,
            "Lifecycle_State": "INVALID"
        })
        
        assert not result.is_valid
        assert len(result.violations) > 0


class TestReportGeneration:
    """Test report generation and statistics"""
    
    def test_report_statistics(self):
        """Report calculates correct statistics"""
        rule_set = DataQualityRuleSet(
            name="Test",
            mandatory_rules=[
                MandatoryFieldRule(rule_name="unit", fields=["Unit"])
            ]
        )
        
        df = pd.DataFrame({
            'Part_Number': ['P-001', 'P-002', 'P-003', 'P-004'],
            'Unit': ['EA', None, 'EA', None]
        })
        
        engine = DataQualityRulesEngine(rule_set)
        report = engine.validate_dataset(df)
        
        assert report.total_records == 4
        assert report.valid_records == 2
        assert report.invalid_records == 2
        assert report.passed_percentage == 50.0
        assert report.failed_percentage == 50.0
    
    def test_most_common_issues(self):
        """Report identifies most common issues"""
        rule_set = DataQualityRuleSet(
            name="Test",
            mandatory_rules=[
                MandatoryFieldRule(rule_name="unit", fields=["Unit"])
            ]
        )
        
        df = pd.DataFrame({
            'Unit': [None, None, 'EA', None, 'EA']
        })
        
        engine = DataQualityRulesEngine(rule_set)
        report = engine.validate_dataset(df)
        
        assert len(report.most_common_issues) > 0
        assert report.most_common_issues[0][1] == 3  # 3 occurrences


class TestFeedbackColumn:
    """Test feedback column generation"""
    
    def test_feedback_column_added(self):
        """Feedback column added to output"""
        rule_set = DataQualityRuleSet(
            name="Test",
            mandatory_rules=[
                MandatoryFieldRule(rule_name="unit", fields=["Unit"])
            ]
        )
        
        df = pd.DataFrame({
            'Part_Number': ['P-001', 'P-002'],
            'Unit': ['EA', None]
        })
        
        output_df, report = add_feedback_column(df, rule_set)
        
        assert 'Feedback' in output_df.columns
        assert output_df.loc[0, 'Feedback'] == "OK"
        assert "mandatory" in output_df.loc[1, 'Feedback'].lower()
    
    def test_feedback_column_content(self):
        """Feedback column contains correct messages"""
        rule_set = DataQualityRuleSet(
            name="Test",
            mandatory_rules=[
                MandatoryFieldRule(rule_name="unit", fields=["Unit"]),
                MandatoryFieldRule(rule_name="material", fields=["Material"])
            ]
        )
        
        df = pd.DataFrame({
            'Part_Number': ['P-001'],
            'Unit': [None],
            'Material': [None]
        })
        
        output_df, report = add_feedback_column(df, rule_set)
        feedback = output_df.loc[0, 'Feedback']
        
        assert "Unit" in feedback
        assert "Material" in feedback


class TestRuleSetSummary:
    """Test rule set summary generation"""
    
    def test_summary_counts_rules(self):
        """Summary counts all rule types"""
        rule_set = DataQualityRuleSet(
            name="Test",
            mandatory_rules=[
                MandatoryFieldRule(rule_name="r1", fields=["Field1"]),
                MandatoryFieldRule(rule_name="r2", fields=["Field2"])
            ],
            uniqueness_rules=[
                UniqueConstraintRule(rule_name="r3", fields=["Field3"])
            ]
        )
        
        summary = get_rule_configuration_summary(rule_set)
        
        assert summary['rules']['mandatory_fields'] == 2
        assert summary['rules']['uniqueness_constraints'] == 1
        assert summary['rules']['total'] == 3


# Fixtures for common test data

@pytest.fixture
def sample_parts_dataframe():
    """Sample parts data for testing"""
    return pd.DataFrame({
        'Part_Number': ['P-00001', 'P-00002', 'P-00003'],
        'Part_Name': ['Bolt', 'Screw', 'Washer'],
        'Unit': ['EA', 'EA', 'EA'],
        'Lifecycle_State': ['Released', 'In Work', 'Released'],
        'Min_Quantity': [100, 50, 200]
    })


@pytest.fixture
def comprehensive_rule_set():
    """Comprehensive rule set for testing"""
    return DataQualityRuleSet(
        name="Parts Master Rules",
        mandatory_rules=[
            MandatoryFieldRule(rule_name="core", fields=["Part_Number", "Unit"])
        ],
        uniqueness_rules=[
            UniqueConstraintRule(rule_name="unique_part", fields=["Part_Number"])
        ],
        dropdown_rules=[
            DropdownValueRule(
                rule_name="lifecycle",
                field_name="Lifecycle_State",
                allowed_values=["Released", "In Work", "Obsolete"]
            )
        ],
        range_rules=[
            RangeCheckRule(
                rule_name="quantity",
                field_name="Min_Quantity",
                min_value=0,
                max_value=100000
            )
        ]
    )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
