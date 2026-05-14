"""
Data Quality Rules Router - API Endpoints

Provides REST endpoints for:
- Creating and configuring data quality rules
- Applying rules to workflows
- Generating validation reports
- Managing rule sets
"""

from fastapi import APIRouter, HTTPException, Query, Body
from typing import List, Optional, Dict
import json
import logging
from datetime import datetime

from models.data_quality_rules_models import (
    DataQualityRuleSet,
    MandatoryFieldRule,
    UniqueConstraintRule,
    DropdownValueRule,
    FormatCheckRule,
    RangeCheckRule,
    DataTypeCheckRule,
    CrossFieldRule,
    ValidationResult,
    DataQualityReport,
)
from services.data_quality_rules_engine import (
    DataQualityRulesEngine,
    add_feedback_column,
    get_rule_configuration_summary,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/quality-rules", tags=["data-quality-rules"])

# In-memory storage for rule sets (would be database in production)
rule_sets_db: Dict[str, DataQualityRuleSet] = {}


@router.post("/rule-sets", response_model=DataQualityRuleSet, status_code=201)
async def create_rule_set(
    rule_set: DataQualityRuleSet = Body(..., description="Rule set configuration")
):
    """
    Create a new data quality rule set
    
    Supports:
    - Mandatory field validation
    - Uniqueness constraints
    - Dropdown/reference values
    - Format checks
    - Range validation
    - Data type checks
    - Cross-field rules
    """
    try:
        rule_set.created_at = datetime.utcnow().isoformat()
        rule_set.updated_at = datetime.utcnow().isoformat()
        
        rule_sets_db[rule_set.rule_set_id] = rule_set
        logger.info(f"Created rule set: {rule_set.rule_set_id} ({rule_set.name})")
        
        return rule_set
    except Exception as e:
        logger.error(f"Error creating rule set: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/rule-sets", response_model=List[DataQualityRuleSet])
async def list_rule_sets(
    enabled_only: bool = Query(False, description="Return only enabled rule sets"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000)
):
    """List all available rule sets"""
    try:
        sets = list(rule_sets_db.values())
        
        if enabled_only:
            sets = [s for s in sets if s.enabled]
        
        return sets[skip : skip + limit]
    except Exception as e:
        logger.error(f"Error listing rule sets: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/rule-sets/{rule_set_id}", response_model=DataQualityRuleSet)
async def get_rule_set(rule_set_id: str):
    """Get specific rule set by ID"""
    try:
        if rule_set_id not in rule_sets_db:
            raise HTTPException(status_code=404, detail=f"Rule set not found: {rule_set_id}")
        
        return rule_sets_db[rule_set_id]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting rule set: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/rule-sets/{rule_set_id}", response_model=DataQualityRuleSet)
async def update_rule_set(
    rule_set_id: str,
    rule_set_update: DataQualityRuleSet = Body(...)
):
    """Update an existing rule set"""
    try:
        if rule_set_id not in rule_sets_db:
            raise HTTPException(status_code=404, detail=f"Rule set not found: {rule_set_id}")
        
        rule_set_update.rule_set_id = rule_set_id
        rule_set_update.updated_at = datetime.utcnow().isoformat()
        
        rule_sets_db[rule_set_id] = rule_set_update
        logger.info(f"Updated rule set: {rule_set_id}")
        
        return rule_set_update
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating rule set: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/rule-sets/{rule_set_id}", status_code=204)
async def delete_rule_set(rule_set_id: str):
    """Delete a rule set"""
    try:
        if rule_set_id not in rule_sets_db:
            raise HTTPException(status_code=404, detail=f"Rule set not found: {rule_set_id}")
        
        del rule_sets_db[rule_set_id]
        logger.info(f"Deleted rule set: {rule_set_id}")
        
        return {"message": "Rule set deleted"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting rule set: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/rule-sets/{rule_set_id}/summary")
async def get_rule_set_summary(rule_set_id: str):
    """Get human-readable summary of rule configuration"""
    try:
        if rule_set_id not in rule_sets_db:
            raise HTTPException(status_code=404, detail=f"Rule set not found: {rule_set_id}")
        
        rule_set = rule_sets_db[rule_set_id]
        summary = get_rule_configuration_summary(rule_set)
        
        return summary
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting rule set summary: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/rule-sets/{rule_set_id}/validate-sample", response_model=ValidationResult)
async def validate_sample_row(
    rule_set_id: str,
    row_data: Dict = Body(..., description="Single row of data to validate")
):
    """
    Validate a single row of data against rule set
    
    Example:
    ```json
    {
      "Part_Number": "P-10001",
      "Unit": "EA",
      "Material": "Steel",
      "Lifecycle_State": "Released"
    }
    ```
    """
    try:
        if rule_set_id not in rule_sets_db:
            raise HTTPException(status_code=404, detail=f"Rule set not found: {rule_set_id}")
        
        rule_set = rule_sets_db[rule_set_id]
        engine = DataQualityRulesEngine(rule_set)
        
        result = engine.validate_row(row_data)
        
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error validating sample row: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/rule-sets/{rule_set_id}/validate-batch", response_model=DataQualityReport)
async def validate_batch(
    rule_set_id: str,
    records: List[Dict] = Body(..., description="Array of records to validate")
):
    """
    Validate multiple records and generate quality report
    
    Returns:
    - Total and valid record counts
    - Detailed validation results per row
    - Rule violation statistics
    - Most common issues summary
    """
    try:
        if rule_set_id not in rule_sets_db:
            raise HTTPException(status_code=404, detail=f"Rule set not found: {rule_set_id}")
        
        if not records:
            raise HTTPException(status_code=400, detail="No records provided")
        
        rule_set = rule_sets_db[rule_set_id]
        engine = DataQualityRulesEngine(rule_set)
        
        # Convert to DataFrame and validate
        import pandas as pd
        df = pd.DataFrame(records)
        
        report = engine.validate_dataset(df)
        
        logger.info(f"Batch validation complete: {report.valid_records}/{report.total_records} passed")
        
        return report
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error validating batch: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/rule-sets/{rule_set_id}/add-feedback-column")
async def add_feedback_to_dataset(
    rule_set_id: str,
    records: List[Dict] = Body(..., description="Dataset records")
):
    """
    Add Feedback column to dataset with validation results
    
    Returns:
    - Updated records with Feedback column
    - Quality report with statistics
    """
    try:
        if rule_set_id not in rule_sets_db:
            raise HTTPException(status_code=404, detail=f"Rule set not found: {rule_set_id}")
        
        if not records:
            raise HTTPException(status_code=400, detail="No records provided")
        
        rule_set = rule_sets_db[rule_set_id]
        
        # Convert to DataFrame
        import pandas as pd
        df = pd.DataFrame(records)
        
        # Add feedback column
        output_df, report = add_feedback_column(df, rule_set)
        
        # Convert back to records with feedback
        output_records = output_df.to_dict('records')
        
        return {
            "records": output_records,
            "report": report.dict(),
            "summary": {
                "total_records": report.total_records,
                "valid_records": report.valid_records,
                "invalid_records": report.invalid_records,
                "passed_percentage": round(report.passed_percentage, 2),
                "failed_percentage": round(report.failed_percentage, 2)
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding feedback column: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/templates/mandatory-fields", response_model=DataQualityRuleSet)
async def create_mandatory_fields_template(
    rule_name: str = Query(...),
    fields: List[str] = Body(...),
    description: Optional[str] = None
):
    """Create a template rule set for mandatory field validation"""
    try:
        rule = MandatoryFieldRule(
            rule_name=rule_name,
            fields=fields,
            description=description or f"Mandatory: {', '.join(fields)}"
        )
        
        rule_set = DataQualityRuleSet(
            name=f"Mandatory Fields - {rule_name}",
            description=description,
            mandatory_rules=[rule]
        )
        
        rule_sets_db[rule_set.rule_set_id] = rule_set
        
        return rule_set
    except Exception as e:
        logger.error(f"Error creating template: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/templates/uniqueness", response_model=DataQualityRuleSet)
async def create_uniqueness_template(
    rule_name: str = Query(...),
    fields: List[str] = Body(...),
    allow_null: bool = Query(True),
    description: Optional[str] = None
):
    """Create a template rule set for uniqueness validation"""
    try:
        rule = UniqueConstraintRule(
            rule_name=rule_name,
            fields=fields,
            allow_null=allow_null,
            description=description or f"Unique: {' + '.join(fields)}"
        )
        
        rule_set = DataQualityRuleSet(
            name=f"Uniqueness - {rule_name}",
            description=description,
            uniqueness_rules=[rule]
        )
        
        rule_sets_db[rule_set.rule_set_id] = rule_set
        
        return rule_set
    except Exception as e:
        logger.error(f"Error creating template: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/templates/dropdown", response_model=DataQualityRuleSet)
async def create_dropdown_template(
    rule_name: str = Query(...),
    field_name: str = Query(...),
    allowed_values: List[str] = Body(...),
    case_sensitive: bool = Query(False),
    description: Optional[str] = None
):
    """Create a template rule set for dropdown value validation"""
    try:
        rule = DropdownValueRule(
            rule_name=rule_name,
            field_name=field_name,
            allowed_values=allowed_values,
            case_sensitive=case_sensitive,
            description=description
        )
        
        rule_set = DataQualityRuleSet(
            name=f"Dropdown - {field_name}",
            description=description,
            dropdown_rules=[rule]
        )
        
        rule_sets_db[rule_set.rule_set_id] = rule_set
        
        return rule_set
    except Exception as e:
        logger.error(f"Error creating template: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


# Export router for inclusion in main app
__all__ = ["router"]
