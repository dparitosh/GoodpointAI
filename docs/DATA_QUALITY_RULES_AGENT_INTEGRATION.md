# Data Quality Rules Engine - Agent & Workflow Integration

**Integration Guide for GoodpointAI Migration Wizard & Quality Monitor Agent**

---

## Architecture Overview

```
Migration Wizard (Step 4: Quality)
    │
    ├─→ Quality Monitor Agent
    │       │
    │       ├─→ Data Quality Rules Engine
    │       │   (configurable rule evaluation)
    │       │
    │       ├─→ SODA Integration (optional)
    │       │   (data profiling + quality scans)
    │       │
    │       └─→ Report Generation
    │           (feedback + violations)
    │
    └─→ UI Feedback
        - Feedback column display
        - Violation breakdown
        - Pass/fail statistics
```

---

## Component Integration Points

### 1. Migration Wizard - Quality Step (Step 4)

**Flow**:
```
1. User selects dataset in Step 2
2. System discovers schema in Step 3
3. User configures quality rules in Step 4 (NEW)
4. System runs configured rules + standard checks
5. Output: Dataset with Feedback column + Report
6. User reviews violations before proceeding
```

**Rule Configuration UI Elements**:
- Mandatory Fields dropdown + selector
- Uniqueness constraints builder
- Dropdown values configurator
- Pattern/format editor
- Numeric range inputs
- Cross-field condition builder

### 2. Quality Monitor Agent Integration

**Agent Responsibilities**:

```python
class QualityMonitorAgent(BaseAgent):
    """
    Runs comprehensive data quality checks
    
    Tasks:
    - Load user-configured rule set
    - Validate data against rules
    - Generate quality report
    - Add feedback column
    - Create actionable recommendations
    """
    
    async def run_quality_check(self, workflow_id: str, dataset_df: pd.DataFrame):
        # 1. Load configured rules
        rule_set = await self.load_rule_set(workflow_id)
        
        # 2. Run rules engine
        engine = DataQualityRulesEngine(rule_set)
        report = engine.validate_dataset(dataset_df)
        
        # 3. Enhance with feedback
        output_df, enhanced_report = self.add_feedback_and_recommendations(
            dataset_df, report
        )
        
        # 4. Store results
        await self.store_quality_results(workflow_id, {
            'dataset': output_df,
            'report': enhanced_report,
            'violations_by_rule': report.rule_violations,
            'common_issues': report.most_common_issues
        })
        
        return output_df, enhanced_report
```

### 3. Workflow State Management

**Quality Step State**:
```json
{
  "step_number": 4,
  "step_name": "Quality Validation",
  "status": "in_progress",
  "rule_set_id": "ruleset_abc123",
  "rule_configuration": {
    "mandatory_fields": ["Part_Number", "Unit"],
    "unique_fields": ["Part_Number"],
    "dropdown_rules": {
      "Lifecycle_State": ["Released", "In Work", "Obsolete"]
    }
  },
  "validation_results": {
    "total_records": 1000,
    "valid_records": 950,
    "invalid_records": 50,
    "passed_percentage": 95.0,
    "violations": {
      "missing_unit": 30,
      "duplicate_part": 20
    }
  },
  "user_accepted": false
}
```

---

## API Integration

### Workflow Manager Integration

**New Endpoints Added**:

```
POST   /api/workflows/{workflow_id}/quality-rules
       Create/update quality rules for workflow

GET    /api/workflows/{workflow_id}/quality-rules
       Get configured rules

POST   /api/workflows/{workflow_id}/quality-rules/validate
       Run validation and generate report

GET    /api/workflows/{workflow_id}/quality-report
       Retrieve validation report

POST   /api/workflows/{workflow_id}/quality-rules/accept
       User accepts quality violations and proceeds
```

### Quality Rules Router Integration

```
POST   /api/quality-rules/rule-sets
       Create rule set

GET    /api/quality-rules/rule-sets/{id}
       Get rule set details

POST   /api/quality-rules/rule-sets/{id}/validate-batch
       Run validation (used by agent)

POST   /api/quality-rules/rule-sets/{id}/add-feedback-column
       Add feedback to dataset
```

---

## Agent Task Execution Flow

### QualityMonitorAgent.run_quality_checks()

```python
async def run_quality_checks(
    self,
    workflow_id: str,
    dataset_df: pd.DataFrame,
    rule_set_config: DataQualityRuleSet
) -> Dict[str, Any]:
    """
    Main task: Execute quality monitoring with configurable rules
    
    Steps:
    1. Validate rule set configuration
    2. Execute data quality rules
    3. Generate detailed report
    4. Identify root causes of violations
    5. Suggest remediation actions
    """
    
    # Step 1: Validate rule set
    logger.info(f"Validating rule set for workflow {workflow_id}")
    summary = get_rule_configuration_summary(rule_set_config)
    logger.info(f"Rules: {summary['rules']['total']} configured")
    
    # Step 2: Run rules engine
    engine = DataQualityRulesEngine(rule_set_config)
    report = engine.validate_dataset(dataset_df)
    
    # Step 3: Add feedback column
    output_df = dataset_df.copy()
    output_df['Feedback'] = [r.feedback for r in report.validation_results]
    
    # Step 4: Generate detailed report
    detailed_report = {
        'summary': {
            'total_records': report.total_records,
            'valid_records': report.valid_records,
            'invalid_records': report.invalid_records,
            'pass_rate_percentage': report.passed_percentage,
        },
        'violations_by_rule': report.rule_violations,
        'most_common_issues': report.most_common_issues,
        'violation_details': [
            {
                'row_number': r.row_number,
                'feedback': r.feedback,
                'severity': 'error' if r.violations else 'info',
                'violations': r.violations
            }
            for r in report.validation_results
            if not r.is_valid
        ]
    }
    
    # Step 5: Generate recommendations
    recommendations = self.generate_remediation_recommendations(
        report, detailed_report
    )
    
    # Step 6: Update workflow state
    await self.update_workflow_state(workflow_id, {
        'quality_status': 'completed',
        'quality_report': detailed_report,
        'recommendations': recommendations,
        'output_dataset_id': await self.store_dataset(output_df)
    })
    
    return {
        'status': 'success',
        'report': detailed_report,
        'dataset_with_feedback': output_df,
        'recommendations': recommendations
    }
```

---

## Migration Wizard Integration

### Step 4 Quality Tab - User Flow

```
┌─────────────────────────────────────────┐
│  Step 4: Quality Validation             │
├─────────────────────────────────────────┤
│                                         │
│  ┌─ Configure Quality Rules ──────────┐ │
│  │                                    │ │
│  │  ☑ Mandatory Fields                │ │
│  │    [✕] Part_Number, Unit, Material │ │
│  │                                    │ │
│  │  ☑ Uniqueness Constraints          │ │
│  │    [✕] Part_Number                 │ │
│  │    [✕] Part_Number + Revision      │ │
│  │                                    │ │
│  │  ☑ Reference Values                │ │
│  │    Lifecycle_State: [Released...]  │ │
│  │                                    │ │
│  └────────────────────────────────────┘ │
│                                         │
│  ┌─ Run Quality Check ────────────────┐ │
│  │ [⚙ Run Quality Scan] (Running...) │ │
│  └────────────────────────────────────┘ │
│                                         │
│  ┌─ Quality Report ──────────────────┐ │
│  │                                    │ │
│  │  📊 Results: 950/1000 passed (95%) │ │
│  │                                    │ │
│  │  ⚠️  Violations Found:              │ │
│  │  • Missing Unit (30 records)       │ │
│  │  • Duplicate Part_Number (20)      │ │
│  │                                    │ │
│  │  [View Detailed Report]            │ │
│  │  [Download Violations CSV]         │ │
│  │                                    │ │
│  └────────────────────────────────────┘ │
│                                         │
│         [◀ Previous] [Next ▶]          │
│              (Accept & Continue)        │
└─────────────────────────────────────────┘
```

### Code Integration - MigrationWizard.jsx

```javascript
// Step 4 Component - Quality Validation
async function runQualityChecks() {
  const ruleSet = {
    name: 'Migration Quality Rules',
    mandatory_rules: [
      { rule_name: 'mandatory_unit', fields: ['Unit'] },
      { rule_name: 'mandatory_material', fields: ['Material'] }
    ],
    uniqueness_rules: [
      { rule_name: 'unique_part', fields: ['Part_Number'] }
    ],
    dropdown_rules: [
      {
        rule_name: 'lifecycle_state',
        field_name: 'Lifecycle_State',
        allowed_values: ['Released', 'In Work', 'Obsolete']
      }
    ]
  };
  
  // Create rule set
  const ruleSetResponse = await fetch('/api/quality-rules/rule-sets', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(ruleSet)
  });
  
  const createdRuleSet = await ruleSetResponse.json();
  
  // Run validation
  const validationResponse = await fetch(
    `/api/quality-rules/rule-sets/${createdRuleSet.rule_set_id}/validate-batch`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(wizardData.discoveryData)
    }
  );
  
  const report = await validationResponse.json();
  
  // Update state with results
  setQualityReport({
    total_records: report.total_records,
    valid_records: report.valid_records,
    invalid_records: report.invalid_records,
    passed_percentage: report.passed_percentage,
    violations: report.most_common_issues,
    detailed_results: report.validation_results
  });
  
  // Add feedback column to discovery data
  const feedbackResponse = await fetch(
    `/api/quality-rules/rule-sets/${createdRuleSet.rule_set_id}/add-feedback-column`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(wizardData.discoveryData)
    }
  );
  
  const { records: recordsWithFeedback } = await feedbackResponse.json();
  
  // Update wizard state
  setWizardData(prev => ({
    ...prev,
    qualityResults: recordsWithFeedback,
    qualityPassed: report.passed_percentage >= 90
  }));
}
```

---

## Rule Set Persistence

### Storing Rules in Workflow

**Database Schema**:
```sql
CREATE TABLE workflow_quality_rules (
    id UUID PRIMARY KEY,
    workflow_id UUID NOT NULL,
    rule_set_id VARCHAR(255) NOT NULL,
    rule_configuration JSONB NOT NULL,
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    created_by VARCHAR(255),
    
    FOREIGN KEY (workflow_id) REFERENCES workflows(id)
);

CREATE TABLE quality_validation_results (
    id UUID PRIMARY KEY,
    workflow_id UUID NOT NULL,
    rule_set_id VARCHAR(255) NOT NULL,
    total_records INTEGER,
    valid_records INTEGER,
    invalid_records INTEGER,
    passed_percentage FLOAT,
    violation_details JSONB,
    created_at TIMESTAMP,
    
    FOREIGN KEY (workflow_id) REFERENCES workflows(id)
);
```

### API Usage

```python
# Store rules for workflow
POST /api/workflows/{workflow_id}/quality-rules
{
  "rule_set_id": "ruleset_abc123",
  "rule_configuration": {...}
}

# Retrieve stored rules
GET /api/workflows/{workflow_id}/quality-rules

# Update rules
PUT /api/workflows/{workflow_id}/quality-rules
{
  "rule_set_id": "ruleset_xyz789",
  "rule_configuration": {...}
}

# Run validation on stored rules
POST /api/workflows/{workflow_id}/quality-rules/validate
{
  "data": [...]
}
```

---

## Performance Considerations

### Batch Processing

For large datasets (>100K records):

```python
def validate_large_dataset(dataset_path, rule_set, batch_size=10000):
    """Process large datasets in batches"""
    
    engine = DataQualityRulesEngine(rule_set)
    all_results = []
    
    for batch_df in pd.read_csv(dataset_path, chunksize=batch_size):
        report = engine.validate_dataset(batch_df)
        all_results.extend(report.validation_results)
    
    # Combine reports
    combined_report = DataQualityReport(
        rule_set_id=rule_set.rule_set_id,
        total_records=sum(r.total_records for r in all_results),
        validation_results=all_results
    )
    
    return combined_report
```

### Caching

```python
@cache(ttl=3600)  # Cache for 1 hour
def get_rule_set_summary(rule_set_id: str):
    """Cached rule set summary"""
    rule_set = load_rule_set(rule_set_id)
    return get_rule_configuration_summary(rule_set)
```

---

## Error Handling

### Graceful Degradation

```python
async def run_quality_checks_with_fallback(workflow_id, dataset):
    try:
        # Try to run configured rules
        rule_set = await load_workflow_rules(workflow_id)
        report = DataQualityRulesEngine(rule_set).validate_dataset(dataset)
    except RuleSetNotFound:
        # Fall back to standard quality checks
        logger.warning(f"No rules for {workflow_id}, using defaults")
        report = run_standard_quality_checks(dataset)
    except DataQualityEngineError as e:
        # Log error, return partial results
        logger.error(f"Quality check failed: {str(e)}")
        report = DataQualityReport(
            rule_set_id="error",
            total_records=len(dataset),
            validation_results=[],
            error=str(e)
        )
    
    return report
```

---

## Monitoring & Logging

### Quality Metrics

```python
# Track rule violations over time
quality_metrics = {
    'workflow_id': workflow_id,
    'timestamp': datetime.utcnow(),
    'total_records': report.total_records,
    'passed_percentage': report.passed_percentage,
    'top_violations': report.most_common_issues[:5],
    'rules_triggered': report.rule_violations
}

# Store for dashboard/analytics
store_quality_metric(quality_metrics)
```

### Audit Trail

```python
# Log rule changes
audit_log = {
    'event': 'rule_set_updated',
    'workflow_id': workflow_id,
    'rule_set_id': rule_set_id,
    'changed_by': current_user,
    'timestamp': datetime.utcnow(),
    'changes': {
        'added_rules': [...],
        'removed_rules': [...],
        'modified_rules': [...]
    }
}
```

---

## Testing Strategy

### Unit Tests

```python
def test_mandatory_field_validation():
    rule_set = DataQualityRuleSet(
        mandatory_rules=[
            MandatoryFieldRule(rule_name="unit", fields=["Unit"])
        ]
    )
    
    result = DataQualityRulesEngine(rule_set).validate_row({
        "Part_Number": "P-001",
        "Unit": None
    })
    
    assert not result.is_valid
    assert "Unit is mandatory" in result.feedback
```

### Integration Tests

```python
def test_workflow_quality_step():
    # Create workflow
    workflow = create_workflow()
    
    # Configure rules
    rule_set = create_test_rule_set()
    
    # Run quality check
    dataset = pd.DataFrame([...])
    report = run_quality_check(workflow.id, dataset, rule_set)
    
    # Verify results
    assert report.total_records == len(dataset)
    assert report.passed_percentage >= 0
    assert 'Feedback' in report.validation_results[0]
```

### End-to-End Tests

```python
def test_migration_wizard_with_quality():
    # Navigate wizard Steps 1-3
    # Configure quality rules in Step 4
    # Run quality scan
    # Verify feedback column
    # Proceed to next step
```

---

## Summary

The Data Quality Rules Engine provides:

✅ **Tight Integration** with Migration Wizard & Quality Monitor Agent  
✅ **User-Driven Configuration** without code changes  
✅ **Comprehensive Feedback** per record  
✅ **Performance Optimized** for large datasets  
✅ **Audit Trail** for compliance  
✅ **Extensible Framework** for future rule types  

Perfect for PLM data migration quality assurance!

---

**Next Steps**:
1. Deploy rules engine to backend
2. Update Migration Wizard Step 4 UI
3. Train users on rule configuration
4. Monitor quality metrics
5. Iterate on rule sets based on feedback
