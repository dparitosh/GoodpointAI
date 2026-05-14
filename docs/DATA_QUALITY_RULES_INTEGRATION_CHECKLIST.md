# Data Quality Rules Engine - Integration Checklist

**Step-by-step guide to integrate the rules engine into your backend**

---

## Pre-Integration Checklist

- [ ] All files created successfully
- [ ] No import errors in Python IDE
- [ ] FastAPI backend running on port 8011
- [ ] PostgreSQL connected (optional for in-memory mode)

---

## Step 1: Register Router in FastAPI

### File: `python_backend/main.py`

**Add import**:
```python
from routers.data_quality_rules_router import router as dq_rules_router
```

**Add router to FastAPI app** (before app.mount or any other routers):
```python
# Register data quality rules router
app.include_router(dq_rules_router)
```

**Complete example** (where to place it):
```python
# main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# ... other imports ...
from routers.data_quality_rules_router import router as dq_rules_router
from routers.workflow_manager_router import router as workflow_router
from routers.agentic_router import router as agentic_router

app = FastAPI(title="GoodpointAI GraphTrace")

# ... CORS middleware ...

# Register all routers
app.include_router(dq_rules_router)        # NEW: Data Quality Rules
app.include_router(workflow_router)
app.include_router(agentic_router)

# ... rest of app ...
```

**Verification**:
```bash
# Start backend
python -m uvicorn --app-dir python_backend main:app --reload --port 8011

# Check API docs appear at:
# http://localhost:8011/docs
# You should see "data-quality-rules" tag in API explorer
```

---

## Step 2: Test API Endpoints

### Option A: Using curl

```bash
# 1. Create a rule set
curl -X POST http://localhost:8011/api/quality-rules/rule-sets \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Test Rule Set",
    "description": "Test validation",
    "enabled": true,
    "mandatory_rules": [
      {
        "rule_name": "unit_required",
        "fields": ["Unit"],
        "description": "Unit field is mandatory"
      }
    ]
  }'

# Response should include rule_set_id, save it
# Example: "rule_set_id": "ruleset_1234567890"

# 2. List rule sets
curl http://localhost:8011/api/quality-rules/rule-sets

# 3. Validate sample data
curl -X POST http://localhost:8011/api/quality-rules/rule-sets/{rule_set_id}/validate-batch \
  -H "Content-Type: application/json" \
  -d '[
    {"Part_Number": "P-001", "Unit": "EA"},
    {"Part_Number": "P-002", "Unit": null}
  ]'

# Should return report with valid_records=1, invalid_records=1
```

### Option B: Using Python requests

```python
import requests

BASE_URL = "http://localhost:8011/api/quality-rules"

# Create rule set
rule_set = {
    "name": "Test Rules",
    "mandatory_rules": [
        {
            "rule_name": "unit",
            "fields": ["Unit"]
        }
    ]
}

response = requests.post(f"{BASE_URL}/rule-sets", json=rule_set)
rule_set_id = response.json()["rule_set_id"]
print(f"Created rule set: {rule_set_id}")

# Validate data
data = [
    {"Part_Number": "P-001", "Unit": "EA"},
    {"Part_Number": "P-002", "Unit": None}
]

response = requests.post(
    f"{BASE_URL}/rule-sets/{rule_set_id}/validate-batch",
    json=data
)

report = response.json()
print(f"Valid: {report['valid_records']}/{report['total_records']}")
```

### Option C: Using Swagger UI

1. Open: `http://localhost:8011/docs`
2. Find "data-quality-rules" section
3. Expand `/api/quality-rules/rule-sets` (POST)
4. Click "Try it out"
5. Enter test data and execute

---

## Step 3: Run Unit Tests

```bash
# Run comprehensive test suite
cd python_backend
python -m pytest tests/test_data_quality_rules_comprehensive.py -v

# Run examples
python tests/test_data_quality_rules.py

# Run specific test class
python -m pytest tests/test_data_quality_rules_comprehensive.py::TestMandatoryFieldRules -v

# Run with coverage
python -m pytest tests/test_data_quality_rules_comprehensive.py --cov=services.data_quality_rules_engine
```

**Expected output**:
```
test_data_quality_rules_comprehensive.py::TestMandatoryFieldRules::test_single_mandatory_field_present PASSED
test_data_quality_rules_comprehensive.py::TestMandatoryFieldRules::test_single_mandatory_field_missing PASSED
...
40+ tests PASSED
```

---

## Step 4: Integrate with Migration Wizard

### File: `e2etraceapp/src/components/migration-wizard/MigrationWizard.jsx`

**Add quality rules configuration** to Step 4:

```javascript
// In Step 4 handler (Quality step)
async function runQualityChecks() {
  // Create rule set based on user configuration
  const ruleSet = {
    name: `Quality Rules - ${wizardData.workflowName}`,
    description: "Migration quality validation",
    enabled: true,
    
    // User selects mandatory fields
    mandatory_rules: [
      {
        rule_name: "core_fields",
        fields: userSelectedMandatoryFields,  // e.g., ["Part_Number", "Unit"]
        description: "Core identification fields"
      }
    ],
    
    // User selects uniqueness constraints
    uniqueness_rules: userSelectedUniquenessRules.map(rule => ({
      rule_name: rule.name,
      fields: rule.fields,
      allow_null: rule.allowNull
    })),
    
    // User configures dropdown values
    dropdown_rules: userSelectedDropdownRules.map(rule => ({
      rule_name: rule.name,
      field_name: rule.fieldName,
      allowed_values: rule.allowedValues,
      case_sensitive: rule.caseSensitive
    }))
  };
  
  // Create rule set via API
  const ruleResponse = await fetch('/api/quality-rules/rule-sets', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(ruleSet)
  });
  
  const createdRuleSet = await ruleResponse.json();
  const ruleSetId = createdRuleSet.rule_set_id;
  
  // Run validation on discovered data
  const validationResponse = await fetch(
    `/api/quality-rules/rule-sets/${ruleSetId}/validate-batch`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(wizardData.discoveryData)
    }
  );
  
  const report = await validationResponse.json();
  
  // Add feedback column
  const feedbackResponse = await fetch(
    `/api/quality-rules/rule-sets/${ruleSetId}/add-feedback-column`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(wizardData.discoveryData)
    }
  );
  
  const { records: dataWithFeedback } = await feedbackResponse.json();
  
  // Update wizard state
  setWizardData(prev => ({
    ...prev,
    qualityResults: {
      dataset: dataWithFeedback,
      report: report,
      ruleSetId: ruleSetId,
      passRate: report.passed_percentage
    },
    qualityPassed: report.passed_percentage >= 90
  }));
  
  // Show feedback in UI
  return report;
}
```

---

## Step 5: Create Quality Configuration UI Component

### New File: `e2etraceapp/src/components/migration-wizard/QualityRulesConfiguration.jsx`

```javascript
import React, { useState } from 'react';
import styles from './QualityRulesConfiguration.module.css';

export default function QualityRulesConfiguration({ onConfigurationChange }) {
  const [mandatoryFields, setMandatoryFields] = useState([]);
  const [uniqueFields, setUniqueFields] = useState([]);
  const [dropdownRules, setDropdownRules] = useState([]);
  
  const availableFields = [
    'Part_Number', 'Part_Name', 'Unit', 'Material',
    'Lifecycle_State', 'Revision', 'Description'
  ];
  
  const handleAddMandatoryField = (field) => {
    if (!mandatoryFields.includes(field)) {
      const updated = [...mandatoryFields, field];
      setMandatoryFields(updated);
      onConfigurationChange({ mandatoryFields: updated });
    }
  };
  
  const handleRemoveMandatoryField = (field) => {
    const updated = mandatoryFields.filter(f => f !== field);
    setMandatoryFields(updated);
    onConfigurationChange({ mandatoryFields: updated });
  };
  
  return (
    <div className={styles.container}>
      <h3>Configure Quality Rules</h3>
      
      {/* Mandatory Fields */}
      <div className={styles.section}>
        <h4>Mandatory Fields</h4>
        <div className={styles.fieldList}>
          {availableFields.map(field => (
            <label key={field}>
              <input
                type="checkbox"
                checked={mandatoryFields.includes(field)}
                onChange={(e) => {
                  if (e.target.checked) {
                    handleAddMandatoryField(field);
                  } else {
                    handleRemoveMandatoryField(field);
                  }
                }}
              />
              {field}
            </label>
          ))}
        </div>
      </div>
      
      {/* Uniqueness Constraints */}
      <div className={styles.section}>
        <h4>Uniqueness Constraints</h4>
        <label>
          <input
            type="checkbox"
            onChange={(e) => {
              if (e.target.checked) {
                setUniqueFields(['Part_Number']);
                onConfigurationChange({ uniqueFields: ['Part_Number'] });
              } else {
                setUniqueFields([]);
                onConfigurationChange({ uniqueFields: [] });
              }
            }}
          />
          Part_Number must be unique
        </label>
      </div>
      
      {/* Dropdown Rules */}
      <div className={styles.section}>
        <h4>Reference Values</h4>
        <div>
          <label>Lifecycle_State: </label>
          <select multiple defaultValue={['Released', 'In Work']}>
            <option value="Released">Released</option>
            <option value="In Work">In Work</option>
            <option value="Obsolete">Obsolete</option>
          </select>
        </div>
      </div>
    </div>
  );
}
```

---

## Step 6: Add Feedback Column Display

### Update: `e2etraceapp/src/components/migration-wizard/MigrationWizard.jsx`

**Display feedback in results table**:

```javascript
// In quality results section
<table>
  <thead>
    <tr>
      <th>Part_Number</th>
      <th>Unit</th>
      <th>Material</th>
      <th>Feedback</th>  {/* NEW */}
    </tr>
  </thead>
  <tbody>
    {qualityResults.dataset.map((row, idx) => (
      <tr key={idx} className={row.Feedback === 'OK' ? '' : styles.error}>
        <td>{row.Part_Number}</td>
        <td>{row.Unit}</td>
        <td>{row.Material}</td>
        <td className={styles.feedback}>{row.Feedback}</td>  {/* NEW */}
      </tr>
    ))}
  </tbody>
</table>

{/* Quality Report Summary */}
<div className={styles.qualitySummary}>
  <h4>Quality Report</h4>
  <p>Valid: {qualityResults.report.valid_records}/{qualityResults.report.total_records}</p>
  <p>Pass Rate: {qualityResults.report.passed_percentage.toFixed(1)}%</p>
  
  {qualityResults.report.most_common_issues && (
    <div>
      <h5>Common Issues:</h5>
      <ul>
        {qualityResults.report.most_common_issues.map(([issue, count]) => (
          <li key={issue}>{issue} ({count} records)</li>
        ))}
      </ul>
    </div>
  )}
</div>
```

---

## Step 7: Database Integration (Optional)

### Create Alembic Migration

```bash
# Generate migration
cd python_backend
alembic revision --autogenerate -m "Add data quality rules tables"

# In the generated migration file, add:
```

```python
def upgrade():
    op.create_table(
        'data_quality_rule_sets',
        sa.Column('id', sa.String(255), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text),
        sa.Column('rule_configuration', sa.JSON, nullable=False),
        sa.Column('enabled', sa.Boolean, default=True),
        sa.Column('created_by', sa.String(255)),
        sa.Column('created_at', sa.DateTime, default=datetime.utcnow),
        sa.Column('updated_at', sa.DateTime, onupdate=datetime.utcnow),
    )
    
    op.create_table(
        'quality_validation_results',
        sa.Column('id', sa.String(255), primary_key=True),
        sa.Column('workflow_id', sa.String(255), nullable=False),
        sa.Column('rule_set_id', sa.String(255), nullable=False),
        sa.Column('total_records', sa.Integer),
        sa.Column('valid_records', sa.Integer),
        sa.Column('invalid_records', sa.Integer),
        sa.Column('passed_percentage', sa.Float),
        sa.Column('violation_details', sa.JSON),
        sa.Column('created_at', sa.DateTime, default=datetime.utcnow),
    )

def downgrade():
    op.drop_table('quality_validation_results')
    op.drop_table('data_quality_rule_sets')
```

```bash
# Apply migration
alembic upgrade head
```

---

## Step 8: Verify Installation

### Checklist

- [ ] Router imported in main.py
- [ ] Router registered with app.include_router()
- [ ] Backend started without errors
- [ ] /docs shows data-quality-rules endpoints
- [ ] Create rule set endpoint works (POST)
- [ ] Validate batch endpoint works (POST)
- [ ] All tests pass (40+ test cases)
- [ ] No import errors in IDE
- [ ] API returns proper JSON responses
- [ ] Error handling works (test with invalid data)

### Quick Verification Script

```python
# test_integration.py
import requests

BASE_URL = "http://localhost:8011"

def test_integration():
    """Quick integration test"""
    
    # 1. Check router is loaded
    response = requests.get(f"{BASE_URL}/docs")
    assert "data-quality-rules" in response.text
    print("✓ Router registered")
    
    # 2. Create rule set
    response = requests.post(
        f"{BASE_URL}/api/quality-rules/rule-sets",
        json={
            "name": "Integration Test",
            "mandatory_rules": [
                {"rule_name": "unit", "fields": ["Unit"]}
            ]
        }
    )
    assert response.status_code == 201
    rule_set_id = response.json()["rule_set_id"]
    print("✓ Rule set creation works")
    
    # 3. Validate data
    response = requests.post(
        f"{BASE_URL}/api/quality-rules/rule-sets/{rule_set_id}/validate-batch",
        json=[
            {"Part_Number": "P-001", "Unit": "EA"},
            {"Part_Number": "P-002", "Unit": None}
        ]
    )
    assert response.status_code == 200
    report = response.json()
    assert report["valid_records"] == 1
    assert report["invalid_records"] == 1
    print("✓ Validation works")
    
    # 4. Add feedback column
    response = requests.post(
        f"{BASE_URL}/api/quality-rules/rule-sets/{rule_set_id}/add-feedback-column",
        json=[
            {"Part_Number": "P-001", "Unit": "EA"},
            {"Part_Number": "P-002", "Unit": None}
        ]
    )
    assert response.status_code == 200
    result = response.json()
    assert "Feedback" in result["records"][0]
    print("✓ Feedback column works")
    
    print("\n✅ All integration tests passed!")

if __name__ == "__main__":
    test_integration()
```

**Run it**:
```bash
python test_integration.py
```

---

## Troubleshooting

### Issue: ModuleNotFoundError: No module named 'models.data_quality_rules_models'

**Solution**: Ensure files are in correct location:
```
python_backend/
├── models/
│   └── data_quality_rules_models.py  ← Check exists
├── services/
│   └── data_quality_rules_engine.py  ← Check exists
├── routers/
│   └── data_quality_rules_router.py  ← Check exists
└── main.py                             ← Check import is here
```

### Issue: No "data-quality-rules" in /docs

**Solution**: Verify router registration:
```python
# In main.py, ensure this line exists:
app.include_router(dq_rules_router)

# Restart backend after making changes
```

### Issue: ValidationResult model expects 'created_at' field

**Solution**: Check you're using the latest models file. ValidationResult doesn't require created_at for response.

### Issue: Tests fail with "rule_set_id already exists"

**Solution**: Clear the in-memory rule_sets_db between tests or use unique IDs:
```python
# In test setup
rule_sets_db.clear()
```

---

## Next Steps After Integration

1. **Optional: Database Persistence**
   - Create migration script
   - Implement SQLAlchemy models
   - Add repository layer

2. **Optional: UI Components**
   - Build rule configuration UI
   - Add feedback column display
   - Create quality report dashboard

3. **Optional: Agent Integration**
   - Wire Quality Monitor Agent
   - Add remediation recommendations
   - Setup quality metrics tracking

4. **Optional: Advanced Features**
   - Custom rule types
   - Rule templates library
   - Quality metrics dashboard
   - Compliance reporting

---

## Summary

✅ **Integration Complete When**:
1. Router registered in main.py
2. /docs shows data-quality-rules endpoints
3. Create rule set endpoint returns 201
4. Validate batch endpoint returns report
5. Tests pass without errors
6. Frontend can call APIs successfully

✅ **Ready for Production When**:
1. Database persistence implemented
2. UI components created
3. Agent integration complete
4. Full E2E tests pass
5. Performance tested at scale
6. Security review passed

---

**Questions?** Refer to:
- `docs/DATA_QUALITY_RULES_GUIDE.md` - Comprehensive guide
- `docs/DATA_QUALITY_RULES_AGENT_INTEGRATION.md` - Deep integration
- `docs/DATA_QUALITY_RULES_QUICK_REFERENCE.md` - Quick lookup

**Support**: Check the example tests for complete working code patterns.
