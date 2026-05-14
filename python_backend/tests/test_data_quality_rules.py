"""
Data Quality Rules Engine - Examples & Testing

Demonstrates:
- Creating rule sets programmatically
- Validating datasets
- Generating feedback columns
- Using API templates
- Integration with workflows
"""

import pandas as pd
from typing import List, Dict
import json

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


class DataQualityRulesExamples:
    """Collection of examples for data quality rules"""
    
    @staticmethod
    def example_1_mandatory_fields():
        """Example 1: Mandatory Field Validation"""
        print("\n" + "="*80)
        print("EXAMPLE 1: Mandatory Field Validation")
        print("="*80)
        
        # Create rule set
        rule_set = DataQualityRuleSet(
            name="Parts Master - Mandatory Fields",
            description="Ensures critical fields are populated",
            mandatory_rules=[
                MandatoryFieldRule(
                    rule_name="mandatory_unit",
                    fields=["Unit"],
                    description="Unit must be specified"
                ),
                MandatoryFieldRule(
                    rule_name="mandatory_material",
                    fields=["Material"],
                    description="Material must be specified"
                ),
                MandatoryFieldRule(
                    rule_name="mandatory_part_revision",
                    fields=["Part_Number", "Revision"],
                    composite=True,
                    description="Part_Number and Revision must both be present"
                ),
            ]
        )
        
        # Sample data
        data = {
            'Part_Number': ['P-001', 'P-002', 'P-003', None],
            'Revision': ['A', 'B', None, 'D'],
            'Unit': ['EA', None, 'EA', 'EA'],
            'Material': ['Steel', 'Aluminum', 'Steel', None],
        }
        df = pd.DataFrame(data)
        
        # Validate
        engine = DataQualityRulesEngine(rule_set)
        report = engine.validate_dataset(df)
        
        # Display results
        print("\nInput Data:")
        print(df)
        print("\nValidation Results:")
        for result in report.validation_results:
            status = "✓ PASS" if result.is_valid else "✗ FAIL"
            print(f"Row {result.row_number}: {status}")
            if result.violations:
                for violation in result.violations:
                    print(f"  • {violation}")
        
        print(f"\nSummary: {report.valid_records}/{report.total_records} rows passed ({report.passed_percentage:.1f}%)")
        
        return rule_set, df, report
    
    @staticmethod
    def example_2_uniqueness_constraints():
        """Example 2: Uniqueness Constraints"""
        print("\n" + "="*80)
        print("EXAMPLE 2: Uniqueness Constraints")
        print("="*80)
        
        # Create rule set
        rule_set = DataQualityRuleSet(
            name="Parts Master - Uniqueness",
            description="Ensures no duplicate parts",
            uniqueness_rules=[
                UniqueConstraintRule(
                    rule_name="unique_part_number",
                    fields=["Part_Number"],
                    description="Part_Number must be unique"
                ),
                UniqueConstraintRule(
                    rule_name="unique_part_revision",
                    fields=["Part_Number", "Revision"],
                    description="Part_Number + Revision combination must be unique"
                ),
            ]
        )
        
        # Sample data with duplicates
        data = {
            'Part_Number': ['P-001', 'P-001', 'P-002', 'P-003', 'P-001'],
            'Revision': ['A', 'A', 'A', 'B', 'B'],
            'Name': ['Bolt', 'Bolt', 'Screw', 'Washer', 'Bolt'],
        }
        df = pd.DataFrame(data)
        
        # Validate
        engine = DataQualityRulesEngine(rule_set)
        report = engine.validate_dataset(df)
        
        # Display results
        print("\nInput Data:")
        print(df)
        print("\nValidation Results:")
        for result in report.validation_results:
            status = "✓ PASS" if result.is_valid else "✗ FAIL"
            print(f"Row {result.row_number}: {status}")
            if result.feedback and result.feedback != "OK":
                print(f"  Feedback: {result.feedback}")
        
        print(f"\nSummary: {report.valid_records}/{report.total_records} rows passed")
        
        return rule_set, df, report
    
    @staticmethod
    def example_3_dropdown_validation():
        """Example 3: Dropdown/Reference Value Validation"""
        print("\n" + "="*80)
        print("EXAMPLE 3: Dropdown/Reference Value Validation")
        print("="*80)
        
        # Create rule set
        rule_set = DataQualityRuleSet(
            name="Parts Master - Reference Values",
            description="Validates field values against allowed lists",
            dropdown_rules=[
                DropdownValueRule(
                    rule_name="lifecycle_validation",
                    field_name="Lifecycle_State",
                    allowed_values=["Released", "In Work", "Obsolete"],
                    case_sensitive=False,
                    description="Lifecycle_State must be a predefined value"
                ),
                DropdownValueRule(
                    rule_name="part_type_validation",
                    field_name="Part_Type",
                    allowed_values=["Standard Part", "Assembly", "Raw Material"],
                    description="Part_Type must match allowed values"
                ),
            ]
        )
        
        # Sample data
        data = {
            'Part_Number': ['P-001', 'P-002', 'P-003', 'P-004'],
            'Lifecycle_State': ['Released', 'In Work', 'RELEASED', 'Approved'],  # Last one invalid
            'Part_Type': ['Standard Part', 'Assembly', 'Custom Item', 'Assembly'],  # One invalid
        }
        df = pd.DataFrame(data)
        
        # Validate
        engine = DataQualityRulesEngine(rule_set)
        report = engine.validate_dataset(df)
        
        # Display results
        print("\nInput Data:")
        print(df)
        print("\nValidation Results:")
        for result in report.validation_results:
            status = "✓ PASS" if result.is_valid else "✗ FAIL"
            print(f"Row {result.row_number}: {status}")
            if result.feedback and result.feedback != "OK":
                print(f"  {result.feedback}")
        
        return rule_set, df, report
    
    @staticmethod
    def example_4_format_validation():
        """Example 4: Format/Pattern Validation"""
        print("\n" + "="*80)
        print("EXAMPLE 4: Format/Pattern Validation")
        print("="*80)
        
        # Create rule set
        rule_set = DataQualityRuleSet(
            name="Parts Master - Format Validation",
            description="Validates data format and patterns",
            format_rules=[
                FormatCheckRule(
                    rule_name="part_number_format",
                    field_name="Part_Number",
                    pattern=r"^P-\d{5}$",
                    description="Part_Number must match P-XXXXX format"
                ),
                FormatCheckRule(
                    rule_name="serial_number_format",
                    field_name="Serial_Number",
                    pattern=r"^SN[A-Z0-9]{8}$",
                    description="Serial_Number must match SNXXXXXXXX format"
                ),
            ]
        )
        
        # Sample data
        data = {
            'Part_Number': ['P-00001', 'P-00002', 'P-123', 'P-00004'],  # Third is invalid
            'Serial_Number': ['SNA1B2C3D4', 'SNX9Y8Z7W6', 'INVALID', 'SN12345678'],
        }
        df = pd.DataFrame(data)
        
        # Validate
        engine = DataQualityRulesEngine(rule_set)
        report = engine.validate_dataset(df)
        
        # Display results
        print("\nInput Data:")
        print(df)
        print("\nValidation Results:")
        for result in report.validation_results:
            status = "✓ PASS" if result.is_valid else "✗ FAIL"
            print(f"Row {result.row_number}: {status}")
            if result.feedback and result.feedback != "OK":
                print(f"  {result.feedback}")
        
        return rule_set, df, report
    
    @staticmethod
    def example_5_range_validation():
        """Example 5: Numeric Range Validation"""
        print("\n" + "="*80)
        print("EXAMPLE 5: Numeric Range Validation")
        print("="*80)
        
        # Create rule set
        rule_set = DataQualityRuleSet(
            name="Parts Master - Range Validation",
            description="Validates numeric values are within acceptable ranges",
            range_rules=[
                RangeCheckRule(
                    rule_name="quantity_range",
                    field_name="Quantity",
                    min_value=0,
                    max_value=10000,
                    description="Quantity must be between 0 and 10000"
                ),
                RangeCheckRule(
                    rule_name="unit_cost_range",
                    field_name="Unit_Cost",
                    min_value=0.01,
                    max_value=99999.99,
                    description="Unit_Cost must be between 0.01 and 99999.99"
                ),
            ]
        )
        
        # Sample data
        data = {
            'Part_Number': ['P-00001', 'P-00002', 'P-00003', 'P-00004'],
            'Quantity': [100, -5, 15000, 50],  # Second and third are invalid
            'Unit_Cost': [10.50, 25.00, 0.001, 100000],
        }
        df = pd.DataFrame(data)
        
        # Validate
        engine = DataQualityRulesEngine(rule_set)
        report = engine.validate_dataset(df)
        
        # Display results
        print("\nInput Data:")
        print(df)
        print("\nValidation Results:")
        for result in report.validation_results:
            status = "✓ PASS" if result.is_valid else "✗ FAIL"
            print(f"Row {result.row_number}: {status}")
            if result.feedback and result.feedback != "OK":
                print(f"  {result.feedback}")
        
        return rule_set, df, report
    
    @staticmethod
    def example_6_cross_field_validation():
        """Example 6: Cross-Field Validation"""
        print("\n" + "="*80)
        print("EXAMPLE 6: Cross-Field Validation")
        print("="*80)
        
        # Create rule set
        rule_set = DataQualityRuleSet(
            name="Parts Master - Cross-Field Validation",
            description="Validates relationships between fields",
            cross_field_rules=[
                CrossFieldRule(
                    rule_name="end_after_start",
                    condition="End_Date >= Start_Date",
                    error_message="End_Date must be after or equal to Start_Date"
                ),
                CrossFieldRule(
                    rule_name="revised_date_after_created",
                    condition="Revised_Date >= Created_Date or Revised_Date is None",
                    error_message="Revised_Date must be after Created_Date"
                ),
            ]
        )
        
        # Sample data
        data = {
            'Part_Number': ['P-001', 'P-002', 'P-003'],
            'Start_Date': ['2024-01-01', '2024-01-01', '2024-01-01'],
            'End_Date': ['2024-12-31', '2023-12-31', '2024-12-31'],  # Second is invalid
            'Created_Date': ['2024-01-01', '2024-01-01', '2024-01-01'],
            'Revised_Date': ['2024-06-01', '2024-06-01', '2023-06-01'],  # Third is invalid
        }
        df = pd.DataFrame(data)
        
        # Validate
        engine = DataQualityRulesEngine(rule_set)
        report = engine.validate_dataset(df)
        
        # Display results
        print("\nInput Data:")
        print(df)
        print("\nValidation Results:")
        for result in report.validation_results:
            status = "✓ PASS" if result.is_valid else "✗ FAIL"
            print(f"Row {result.row_number}: {status}")
            if result.feedback and result.feedback != "OK":
                print(f"  {result.feedback}")
        
        return rule_set, df, report
    
    @staticmethod
    def example_7_combined_rules():
        """Example 7: Combined Rule Set (All Rule Types)"""
        print("\n" + "="*80)
        print("EXAMPLE 7: Combined Rule Set - Comprehensive Parts Data Validation")
        print("="*80)
        
        # Create comprehensive rule set
        rule_set = DataQualityRuleSet(
            name="Parts Master - Comprehensive Quality Rules",
            description="Complete data quality validation for PLM parts",
            
            mandatory_rules=[
                MandatoryFieldRule(
                    rule_name="mandatory_core_fields",
                    fields=["Part_Number", "Part_Name", "Unit"],
                    description="Core identification fields are mandatory"
                ),
            ],
            
            uniqueness_rules=[
                UniqueConstraintRule(
                    rule_name="unique_part_id",
                    fields=["Part_Number"],
                    description="Part_Number must be unique"
                ),
            ],
            
            dropdown_rules=[
                DropdownValueRule(
                    rule_name="lifecycle_state",
                    field_name="Lifecycle_State",
                    allowed_values=["Released", "In Work", "Obsolete"],
                    description="Valid lifecycle states"
                ),
            ],
            
            format_rules=[
                FormatCheckRule(
                    rule_name="part_number_format",
                    field_name="Part_Number",
                    pattern=r"^P-\d{5}$",
                    description="Part_Number format: P-XXXXX"
                ),
            ],
            
            range_rules=[
                RangeCheckRule(
                    rule_name="quantity_check",
                    field_name="Min_Quantity",
                    min_value=0,
                    max_value=100000,
                    description="Min_Quantity must be non-negative"
                ),
            ],
            
            cross_field_rules=[
                CrossFieldRule(
                    rule_name="valid_date_range",
                    condition="Release_Date <= Obsolete_Date or Obsolete_Date is None",
                    error_message="Obsolete_Date must be after Release_Date"
                ),
            ]
        )
        
        # Sample data
        data = {
            'Part_Number': ['P-00001', 'P-00002', 'P-00003', 'P-00004', 'P-00001'],
            'Part_Name': ['Bolt', 'Screw', None, 'Washer', 'Bolt'],
            'Unit': ['EA', 'EA', 'EA', None, 'EA'],
            'Lifecycle_State': ['Released', 'In Work', 'Released', 'Approved', 'Released'],
            'Min_Quantity': [100, 50, -10, 200, 100],
            'Release_Date': ['2024-01-01', '2024-01-15', '2024-02-01', '2024-03-01', '2024-01-01'],
            'Obsolete_Date': ['2025-01-01', '2024-01-20', '2024-01-15', None, '2025-01-01'],
        }
        df = pd.DataFrame(data)
        
        # Add feedback column
        output_df, report = add_feedback_column(df, rule_set)
        
        # Display results
        print("\nInput Data:")
        print(df[['Part_Number', 'Part_Name', 'Unit', 'Lifecycle_State']])
        
        print("\nOutput with Feedback:")
        print(output_df[['Part_Number', 'Feedback']])
        
        print(f"\nQuality Report:")
        print(f"  Total Records: {report.total_records}")
        print(f"  Valid Records: {report.valid_records}")
        print(f"  Invalid Records: {report.invalid_records}")
        print(f"  Pass Rate: {report.passed_percentage:.1f}%")
        
        if report.most_common_issues:
            print(f"\nMost Common Issues:")
            for issue, count in report.most_common_issues[:5]:
                print(f"  • {issue} ({count} occurrences)")
        
        return rule_set, df, output_df, report


def run_all_examples():
    """Run all examples"""
    examples = DataQualityRulesExamples()
    
    examples.example_1_mandatory_fields()
    examples.example_2_uniqueness_constraints()
    examples.example_3_dropdown_validation()
    examples.example_4_format_validation()
    examples.example_5_range_validation()
    examples.example_6_cross_field_validation()
    examples.example_7_combined_rules()
    
    print("\n" + "="*80)
    print("All examples completed!")
    print("="*80)


if __name__ == "__main__":
    run_all_examples()
