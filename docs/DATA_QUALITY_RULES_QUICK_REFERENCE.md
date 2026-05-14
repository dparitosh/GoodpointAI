# Data Quality Rules Engine - Quick Reference Guide

**TL;DR - Get started in 5 minutes**

---

## Rule Types at a Glance

| Rule Type | Purpose | Example |
|-----------|---------|---------|
| **Mandatory** | Required fields | `Part_Number`, `Unit` must be present |
| **Uniqueness** | No duplicates | `Part_Number` must be unique across dataset |
| **Dropdown** | Value from list | `Lifecycle_State` must be one of: Released, In Work, Obsolete |
| **Format** | Pattern matching | `Part_Number` matches `P-\d{5}` |
| **Range** | Numeric bounds | `Quantity` between 0 and 10,000 |
| **DataType** | Type checking | `Unit_Cost` must be float |
| **CrossField** | Multi-field logic | `End_Date >= Start_Date` |

---

## API Quick Start

### 1. Create Rule Set
```bash
curl -X POST http://localhost:8011/api/quality-rules/rule-sets \
  -H "Content-Type: application/json" \
  -d '{
    "name": "My Quality Rules",
    "mandatory_rules": [
      {
        "rule_name": "mandatory_unit",
        "fields": ["Unit"],
        "description": "Unit is required"
      }
    ]
  }'
```

### 2. Validate Data
```bash
curl -X POST http://localhost:8011/api/quality-rules/rule-sets/{id}/validate-batch \
  -H "Content-Type: application/json" \
  -d '[
    {"Part_Number": "P-001", "Unit": "EA"},
    {"Part_Number": "P-002", "Unit": null}
  ]'
```

### 3. Add Feedback Column
```bash
curl -X POST http://localhost:8011/api/quality-rules/rule-sets/{id}/add-feedback-column \
  -H "Content-Type: application/json" \
  -d '[{"Part_Number": "P-001", "Unit": null}]'
```

---

## Python SDK Quick Start

```python
from models.data_quality_rules_models import *
from services.data_quality_rules_engine import DataQualityRulesEngine
import pandas as pd

# Create rule set
rules = DataQualityRuleSet(
    name="My Rules",
    mandatory_rules=[
        MandatoryFieldRule(rule_name="unit", fields=["Unit"])
    ]
)

# Load data
df = pd.DataFrame([
    {"Part_Number": "P-001", "Unit": "EA"},
    {"Part_Number": "P-002", "Unit": None}
])

# Validate
engine = DataQualityRulesEngine(rules)
report = engine.validate_dataset(df)

# View results
print(f"Passed: {report.passed_percentage}%")
for r in report.validation_results:
    print(f"Row {r.row_number}: {r.feedback}")
```

---

## Common Patterns

### Mandatory + Unique
```json
{
  "name": "Parts Quality",
  "mandatory_rules": [
    {
      "rule_name": "core_fields",
      "fields": ["Part_Number", "Unit"]
    }
  ],
  "uniqueness_rules": [
    {
      "rule_name": "unique_part",
      "fields": ["Part_Number"]
    }
  ]
}
```

### Composite Constraints
```json
{
  "rule_name": "unique_combination",
  "fields": ["Part_Number", "Revision"],
  "composite": true
}
```

### Dropdown with Case Insensitivity
```json
{
  "rule_name": "lifecycle",
  "field_name": "Lifecycle_State",
  "allowed_values": ["Released", "In Work", "Obsolete"],
  "case_sensitive": false
}
```

### Cross-Field Logic
```json
{
  "rule_name": "date_sequence",
  "condition": "End_Date >= Start_Date",
  "error_message": "End must be after Start"
}
```

---

## Response Structure

### Single Row Validation
```json
{
  "row_number": 1,
  "is_valid": false,
  "violations": ["Unit is mandatory"],
  "feedback": "Unit is mandatory",
  "severity": "error"
}
```

### Batch Validation Report
```json
{
  "rule_set_id": "ruleset_123",
  "total_records": 1000,
  "valid_records": 950,
  "invalid_records": 50,
  "passed_percentage": 95.0,
  "rule_violations": {
    "mandatory_unit": 30,
    "duplicate_part": 20
  },
  "most_common_issues": [
    ["Unit is mandatory", 30],
    ["Duplicate Part_Number", 20]
  ]
}
```

---

## Error Messages to Expect

| Error | Meaning | Fix |
|-------|---------|-----|
| `"Unit is mandatory"` | Required field missing | Add Unit value |
| `"Duplicate Part_Number: P-001"` | Value seen before | Ensure unique value |
| `"Invalid Lifecycle_State: Approved"` | Not in allowed list | Choose from list |
| `"Part_Number format invalid"` | Pattern mismatch | Match P-XXXXX |
| `"Quantity value -5 below minimum 0"` | Out of range | Use 0-10000 |
| `"End_Date must be after Start_Date"` | Logic violation | Fix date order |

---

## Common Operations

### Get Rule Set Details
```python
GET /api/quality-rules/rule-sets/{id}
```

### List All Rule Sets
```python
GET /api/quality-rules/rule-sets?enabled_only=true&limit=10
```

### Get Rule Summary
```python
GET /api/quality-rules/rule-sets/{id}/summary
```

### Update Rule Set
```python
PUT /api/quality-rules/rule-sets/{id}
```

### Delete Rule Set
```python
DELETE /api/quality-rules/rule-sets/{id}
```

### Validate Single Row
```python
POST /api/quality-rules/rule-sets/{id}/validate-sample
Body: {"Part_Number": "P-001", "Unit": "EA"}
```

---

## Workflow Integration

### In Migration Wizard Step 4

```python
# Configure rules before validation
async def setup_quality_rules(workflow_id):
    rule_set = DataQualityRuleSet(
        name=f"Quality Rules - {workflow_id}",
        mandatory_rules=[...],
        uniqueness_rules=[...],
        dropdown_rules=[...]
    )
    return rule_set

# Run validation
async def run_quality_step(workflow_id, data):
    rule_set = await setup_quality_rules(workflow_id)
    engine = DataQualityRulesEngine(rule_set)
    report = engine.validate_dataset(data)
    return report
```

---

## Tips & Tricks

### 1. Test Single Row First
```python
# Quick validation of one record
result = engine.validate_row({"Part_Number": "P-001", "Unit": None})
assert not result.is_valid  # Should fail
```

### 2. Use Case-Insensitive Dropdowns
```json
{
  "allowed_values": ["Released", "In Work"],
  "case_sensitive": false  // Accepts "released", "RELEASED", etc.
}
```

### 3. Allow Null for Optional Fields
```json
{
  "field_name": "Material",
  "allow_null": true  // NULL values are OK
}
```

### 4. Combine Multiple Validations
```python
# Run batch with multiple rules
report = engine.validate_dataset(df)
print(f"Valid: {report.valid_records}")
print(f"Issues: {report.most_common_issues}")
```

### 5. Export Report to JSON
```python
import json
report_dict = report.dict()
with open('report.json', 'w') as f:
    json.dump(report_dict, f, indent=2)
```

---

## Performance Tips

| Operation | Speed | Tip |
|-----------|-------|-----|
| Single row | ~1ms | Validate_row() for real-time |
| 1K rows | ~100ms | Batch operations are efficient |
| 100K rows | ~10s | Process in chunks for large files |
| Rule creation | ~50ms | Cache rule sets when possible |

---

## Troubleshooting

**Q: Rule not triggering**
- Check rule is enabled: `"enabled": true`
- Verify field names match exactly
- Test with validate-sample first

**Q: Unexpected violations**
- Review null handling: `allow_null: true/false`
- Check case sensitivity for dropdowns
- Validate regex patterns with online tools

**Q: Performance slow**
- Use batch validation, not row-by-row
- Reduce number of uniqueness rules
- Cache rule set summaries

**Q: Feedback not generated**
- Check output has 'Feedback' column
- Ensure add-feedback-column endpoint used
- Validate rule set is enabled

---

## File Locations

| File | Purpose |
|------|---------|
| `python_backend/models/data_quality_rules_models.py` | Rule & report models |
| `python_backend/services/data_quality_rules_engine.py` | Validation engine |
| `python_backend/routers/data_quality_rules_router.py` | API endpoints |
| `python_backend/tests/test_data_quality_rules.py` | Examples & tests |
| `docs/DATA_QUALITY_RULES_GUIDE.md` | Full documentation |
| `docs/DATA_QUALITY_RULES_AGENT_INTEGRATION.md` | Agent integration |

---

## Default Templates

### Template: Mandatory Core Fields
```bash
POST /api/quality-rules/templates/mandatory-fields
  ?rule_name=core_fields
Body: ["Part_Number", "Unit", "Material"]
```

### Template: Uniqueness Check
```bash
POST /api/quality-rules/templates/uniqueness
  ?rule_name=unique_parts
  &allow_null=false
Body: ["Part_Number"]
```

### Template: Lifecycle States
```bash
POST /api/quality-rules/templates/dropdown
  ?rule_name=lifecycle
  &field_name=Lifecycle_State
Body: ["Released", "In Work", "Obsolete"]
```

---

## Example Response Flow

```
User Input: Part_Number="P-001", Unit=null
            ↓
Mandatory Rule: "Unit is mandatory" → VIOLATION
            ↓
Uniqueness Rule: P-001 not seen before → OK
            ↓
Feedback Generated: "Unit is mandatory"
            ↓
Result: is_valid=false, violations=["Unit is mandatory"]
```

---

## Getting Help

1. **API Docs**: `GET /docs` (Swagger UI)
2. **Examples**: See `test_data_quality_rules.py`
3. **Integration**: See `DATA_QUALITY_RULES_AGENT_INTEGRATION.md`
4. **Full Guide**: See `DATA_QUALITY_RULES_GUIDE.md`

---

**Last Updated**: 2024 | Data Quality Rules Engine v1.0
