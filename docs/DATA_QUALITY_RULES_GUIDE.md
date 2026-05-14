# Data Quality Rules Engine - User & Developer Guide

**Version 1.0** | Configurable, Row-wise Data Quality Validation with Feedback

---

## Table of Contents

1. [Overview](#overview)
2. [Features](#features)
3. [Rule Types](#rule-types)
4. [API Endpoints](#api-endpoints)
5. [Usage Examples](#usage-examples)
6. [Integration with Workflows](#integration-with-workflows)
7. [Best Practices](#best-practices)
8. [FAQ](#faq)

---

## Overview

The **Data Quality Rules Engine** provides:

- **Configurable Validation**: Define rules without code
- **Row-wise Scanning**: Evaluate each record independently
- **Feedback Column**: Automatic generation of validation results
- **Comprehensive Reports**: Statistics and violation summaries
- **Easy Integration**: REST API and Python SDK

### Key Capabilities

✅ Mandatory field validation (single and composite)  
✅ Uniqueness constraint checking (single and composite)  
✅ Dropdown/reference value validation  
✅ Format and pattern validation  
✅ Numeric range validation  
✅ Data type checking  
✅ Cross-field business rule validation  
✅ Detailed per-record feedback  
✅ Quality statistics and reporting  

---

## Features

### 1. Row-wise Processing

The engine processes datasets **row by row**, applying all rules to each record independently and collecting violations for accurate feedback.

### 2. Feedback Column Creation

A `Feedback` column is automatically added to output datasets with:
- Validation errors
- Business rule violations
- Data quality observations

**Example Output:**
```
| Part_Number | Unit | Feedback |
|------------|------|----------|
| P-10005 | NULL | Unit is mandatory; Duplicate Part_Number detected |
| P-10001 | EA | OK |
```

### 3. User-Driven Configuration

Before execution, users configure rules dynamically:
- Define which fields are mandatory
- Specify allowed values for dropdowns
- Set numeric ranges
- Create composite uniqueness constraints
- Define business logic rules

### 4. Pre-configured Templates

Ready-to-use templates for common scenarios:
- Mandatory fields
- Uniqueness constraints
- Dropdown validation
- Format validation

---

## Rule Types

### 1. Mandatory Field Rules

**Purpose**: Ensure critical fields contain values

**Configuration**:
```json
{
  "rule_name": "mandatory_unit",
  "fields": ["Unit"],
  "description": "Unit field is required",
  "composite": false
}
```

**Composite Example**:
```json
{
  "rule_name": "mandatory_part_revision",
  "fields": ["Part_Number", "Revision"],
  "composite": true,
  "description": "Both Part_Number and Revision must be present"
}
```

**Feedback**: `"Unit is mandatory"` | `"Part_Number + Revision combination required"`

---

### 2. Uniqueness Constraint Rules

**Purpose**: Prevent duplicate records

**Configuration**:
```json
{
  "rule_name": "unique_part_number",
  "fields": ["Part_Number"],
  "allow_null": true,
  "description": "Part_Number must be unique"
}
```

**Composite Example**:
```json
{
  "rule_name": "unique_part_revision",
  "fields": ["Part_Number", "Revision"],
  "allow_null": false
}
```

**Feedback**: `"Duplicate Part_Number: P-10001"` | `"Duplicate combination: P-10001 + A"`

---

### 3. Dropdown/Reference Value Rules

**Purpose**: Validate against predefined value lists

**Configuration**:
```json
{
  "rule_name": "lifecycle_validation",
  "field_name": "Lifecycle_State",
  "allowed_values": ["Released", "In Work", "Obsolete"],
  "case_sensitive": false,
  "allow_null": false
}
```

**Feedback**: `"Invalid Lifecycle_State: Approved. Allowed: Released, In Work, Obsolete"`

---

### 4. Format Validation Rules

**Purpose**: Validate data matches expected patterns

**Configuration**:
```json
{
  "rule_name": "part_number_format",
  "field_name": "Part_Number",
  "pattern": "^P-\\d{5}$",
  "allow_null": false,
  "description": "Part_Number must match P-XXXXX"
}
```

**Feedback**: `"Part_Number format invalid: P-ABC"`

---

### 5. Range Validation Rules

**Purpose**: Validate numeric values within bounds

**Configuration**:
```json
{
  "rule_name": "quantity_range",
  "field_name": "Quantity",
  "min_value": 0,
  "max_value": 10000,
  "allow_null": true
}
```

**Feedback**: `"Quantity value -5 is below minimum 0"`

---

### 6. Data Type Checking Rules

**Purpose**: Ensure values match expected types

**Configuration**:
```json
{
  "rule_name": "unit_cost_numeric",
  "field_name": "Unit_Cost",
  "expected_type": "float",
  "allow_null": true
}
```

**Supported Types**: `int`, `float`, `string`, `date`, `boolean`

**Feedback**: `"Unit_Cost expected float, got str"`

---

### 7. Cross-Field Rules

**Purpose**: Validate relationships between fields

**Configuration**:
```json
{
  "rule_name": "valid_date_range",
  "condition": "End_Date >= Start_Date",
  "error_message": "End_Date must be after or equal to Start_Date"
}
```

**Feedback**: `"End_Date must be after or equal to Start_Date"`

---

## API Endpoints

### Create Rule Set

**Endpoint**: `POST /api/quality-rules/rule-sets`

**Request**:
```json
{
  "name": "Parts Master Quality Rules",
  "description": "Complete quality validation for PLM parts",
  "enabled": true,
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
      "fields": ["Part_Number"]
    }
  ],
  "dropdown_rules": [
    {
      "rule_name": "lifecycle_state",
      "field_name": "Lifecycle_State",
      "allowed_values": ["Released", "In Work", "Obsolete"]
    }
  ]
}
```

**Response**: `201 Created` - Returns created rule set with ID

---

### List Rule Sets

**Endpoint**: `GET /api/quality-rules/rule-sets`

**Query Parameters**:
- `enabled_only` (bool): Return only enabled rule sets
- `skip` (int): Pagination offset
- `limit` (int): Max results (default 100)

**Response**: `200 OK` - Array of rule sets

---

### Get Rule Set Details

**Endpoint**: `GET /api/quality-rules/rule-sets/{rule_set_id}`

**Response**: `200 OK` - Complete rule set configuration

---

### Get Rule Set Summary

**Endpoint**: `GET /api/quality-rules/rule-sets/{rule_set_id}/summary`

**Response**:
```json
{
  "rule_set_name": "Parts Master Quality Rules",
  "rule_set_id": "ruleset_1234567890",
  "enabled": true,
  "rules": {
    "mandatory_fields": 1,
    "uniqueness_constraints": 1,
    "dropdown_values": 1,
    "format_checks": 0,
    "range_checks": 0,
    "data_type_checks": 0,
    "cross_field_rules": 0,
    "total": 3
  },
  "details": { ... }
}
```

---

### Validate Single Row

**Endpoint**: `POST /api/quality-rules/rule-sets/{rule_set_id}/validate-sample`

**Request**:
```json
{
  "Part_Number": "P-10001",
  "Unit": "EA",
  "Material": "Steel",
  "Lifecycle_State": "Released"
}
```

**Response**:
```json
{
  "row_number": 0,
  "is_valid": true,
  "violations": [],
  "feedback": "OK",
  "severity": "info"
}
```

---

### Validate Multiple Records

**Endpoint**: `POST /api/quality-rules/rule-sets/{rule_set_id}/validate-batch`

**Request**:
```json
[
  { "Part_Number": "P-001", "Unit": "EA", "Material": "Steel" },
  { "Part_Number": "P-002", "Unit": null, "Material": "Aluminum" },
  { "Part_Number": "P-001", "Unit": "EA", "Material": "Iron" }
]
```

**Response**:
```json
{
  "report_id": "dq_report_1234567890",
  "rule_set_id": "ruleset_1234567890",
  "total_records": 3,
  "valid_records": 1,
  "invalid_records": 2,
  "passed_percentage": 33.33,
  "failed_percentage": 66.67,
  "validation_results": [ ... ],
  "rule_violations": {
    "mandatory_unit": 1,
    "unique_part_number": 1
  },
  "most_common_issues": [
    ["Unit is mandatory", 1],
    ["Duplicate Part_Number: P-001", 1]
  ]
}
```

---

### Add Feedback Column to Dataset

**Endpoint**: `POST /api/quality-rules/rule-sets/{rule_set_id}/add-feedback-column`

**Request**:
```json
[
  { "Part_Number": "P-001", "Unit": "EA" },
  { "Part_Number": "P-002", "Unit": null }
]
```

**Response**:
```json
{
  "records": [
    { "Part_Number": "P-001", "Unit": "EA", "Feedback": "OK" },
    { "Part_Number": "P-002", "Unit": null, "Feedback": "Unit is mandatory" }
  ],
  "report": { ... },
  "summary": {
    "total_records": 2,
    "valid_records": 1,
    "invalid_records": 1,
    "passed_percentage": 50.0,
    "failed_percentage": 50.0
  }
}
```

---

### Create Template Rule Sets

**Mandatory Fields Template**:
```
POST /api/quality-rules/templates/mandatory-fields
?rule_name=parts_core_fields
&description=Core identification fields

Body: ["Part_Number", "Part_Name", "Unit"]
```

**Uniqueness Template**:
```
POST /api/quality-rules/templates/uniqueness
?rule_name=unique_parts
&allow_null=false

Body: ["Part_Number"]
```

**Dropdown Template**:
```
POST /api/quality-rules/templates/dropdown
?rule_name=lifecycle_states
&field_name=Lifecycle_State
&case_sensitive=false

Body: ["Released", "In Work", "Obsolete"]
```

---

## Usage Examples

### Example 1: Basic Mandatory Field Validation

```python
from models.data_quality_rules_models import (
    DataQualityRuleSet,
    MandatoryFieldRule
)
from services.data_quality_rules_engine import DataQualityRulesEngine
import pandas as pd

# Create rule set
rule_set = DataQualityRuleSet(
    name="Mandatory Fields Check",
    mandatory_rules=[
        MandatoryFieldRule(
            rule_name="mandatory_unit",
            fields=["Unit"],
            description="Unit must be specified"
        )
    ]
)

# Sample data
df = pd.DataFrame({
    'Part_Number': ['P-001', 'P-002', 'P-003'],
    'Unit': ['EA', None, 'EA']
})

# Validate
engine = DataQualityRulesEngine(rule_set)
report = engine.validate_dataset(df)

# Check results
for result in report.validation_results:
    print(f"Row {result.row_number}: {result.feedback}")
```

**Output**:
```
Row 1: OK
Row 2: Unit is mandatory
Row 3: OK
```

---

### Example 2: Comprehensive Validation with Feedback

```python
from services.data_quality_rules_engine import add_feedback_column

# Add feedback column to dataset
output_df, report = add_feedback_column(df, rule_set)

print(output_df[['Part_Number', 'Unit', 'Feedback']])
print(f"\nQuality Report: {report.passed_percentage}% passed")
```

---

### Example 3: Using API Client

```python
import requests

# Create rule set via API
rule_set = {
    "name": "Parts Master Quality",
    "mandatory_rules": [
        {
            "rule_name": "mandatory_unit",
            "fields": ["Unit"]
        }
    ]
}

response = requests.post(
    "http://localhost:8011/api/quality-rules/rule-sets",
    json=rule_set
)

rule_set_id = response.json()["rule_set_id"]

# Validate data
data = [
    {"Part_Number": "P-001", "Unit": "EA"},
    {"Part_Number": "P-002", "Unit": None}
]

result = requests.post(
    f"http://localhost:8011/api/quality-rules/rule-sets/{rule_set_id}/validate-batch",
    json=data
)

print(result.json()["summary"])
```

---

## Integration with Workflows

### Integration with Quality Step

In the Migration Wizard Step 4 (Quality Validation):

1. **User configures rules** before running quality check
2. **System applies rules** during quality scanning phase
3. **Feedback column generated** in output dataset
4. **Report displayed** in UI with violations breakdown

### Example Workflow Integration

```python
# In Quality Monitor Agent
from services.data_quality_rules_engine import DataQualityRulesEngine

def run_quality_check(workflow_id, data_df, rule_set_config):
    # Create engine
    engine = DataQualityRulesEngine(rule_set_config)
    
    # Validate data
    report = engine.validate_dataset(data_df)
    
    # Store results
    store_quality_report(workflow_id, report)
    
    # Add feedback to dataset
    data_df['Feedback'] = [r.feedback for r in report.validation_results]
    
    return data_df, report
```

---

## Best Practices

### 1. Rule Naming Convention

Use descriptive, lowercase names with underscores:
- ✅ `mandatory_part_number`
- ✅ `unique_part_revision`
- ✅ `valid_lifecycle_state`
- ❌ `rule1`, `check`, `validation`

### 2. Rule Organization

Group related rules by type:
```
- Mandatory Fields (critical)
- Uniqueness (data integrity)
- Reference Values (business rules)
- Format/Range (technical)
- Cross-Field (logic)
```

### 3. Error Messages

Make feedback clear and actionable:
- ✅ `"Unit is mandatory"`
- ✅ `"Quantity must be between 0 and 10000"`
- ✅ `"Duplicate Part_Number: P-10001"`
- ❌ `"FAIL"`, `"Error"`, `"Invalid"`

### 4. Performance Tips

- **Batch validation** is more efficient than row-by-row
- **Uniqueness checks** scan data once per rule set
- **Drop unused rules** to reduce overhead

### 5. Testing

Always test rule sets with sample data:
```python
# Test with valid data
valid_data = {...}
result = engine.validate_row(valid_data)
assert result.is_valid

# Test with invalid data
invalid_data = {...}
result = engine.validate_row(invalid_data)
assert not result.is_valid
assert len(result.violations) > 0
```

---

## FAQ

### Q: How are multiple violations combined?

**A**: Violations are concatenated with semicolons (`;`):
```
"Unit is mandatory; Duplicate Part_Number detected; Invalid Lifecycle_State"
```

### Q: Can I apply rules to real-time data?

**A**: Yes, use `validate_row()` for single records:
```python
result = engine.validate_row({"Part_Number": "P-001", "Unit": "EA"})
```

### Q: How do I handle NULL values?

**A**: Most rules support `allow_null` parameter:
```json
{
  "rule_name": "optional_material",
  "field_name": "Material",
  "allow_null": true
}
```

### Q: Can I modify rules after creation?

**A**: Yes, use the UPDATE endpoint:
```
PUT /api/quality-rules/rule-sets/{rule_set_id}
```

### Q: How do I export validation results?

**A**: The validation report includes:
- Total/valid/invalid counts
- Per-row results
- Rule violation statistics
- Most common issues

Export as JSON or convert to CSV:
```python
import json
with open('report.json', 'w') as f:
    json.dump(report.dict(), f, indent=2)
```

### Q: What's the maximum dataset size?

**A**: Limited by memory. For large datasets (>1M rows), process in batches:
```python
batch_size = 100000
for i in range(0, len(df), batch_size):
    batch_df = df.iloc[i:i+batch_size]
    report = engine.validate_dataset(batch_df)
```

---

## Summary

The Data Quality Rules Engine transforms PLM data validation into:

✅ **User-Friendly Configuration** - No coding required  
✅ **Comprehensive Coverage** - 7+ rule types  
✅ **Detailed Feedback** - Per-record validation messages  
✅ **Easy Integration** - REST API + Python SDK  
✅ **Rich Reporting** - Statistics and violation summaries  

Perfect for:
- Data migration quality assurance
- Ongoing data governance
- Business rule enforcement
- Data onboarding validation

---

**Questions?** Contact the development team or see the API documentation.
