import logging
import json
import os
from typing import List, Dict, Optional, Any
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from datetime import datetime
import uuid

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/data-mapping", tags=["Data Mapping"])

class FieldMapping(BaseModel):
    source_field: str
    target_field: str
    transformation: Optional[str] = None  # e.g., "uppercase", "date_format", "concat"
    validation_rule: Optional[str] = None
    default_value: Optional[str] = None

class MappingRule(BaseModel):
    id: Optional[str] = None
    name: str
    description: Optional[str] = ""
    source_system_id: str
    target_system_id: str
    field_mappings: List[FieldMapping] = []
    status: str = "draft"  # draft, active, inactive
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    created_by: Optional[str] = None
    validation_enabled: bool = True
    transformation_enabled: bool = True

class MappingTemplate(BaseModel):
    id: Optional[str] = None
    name: str
    description: str
    category: str  # e.g., "ETL", "Migration", "Integration"
    source_type: str
    target_type: str
    field_mappings: List[FieldMapping] = []
    created_at: Optional[str] = None
    tags: List[str] = []

class MappingExecution(BaseModel):
    mapping_id: str
    execution_mode: str = "validate"  # validate, transform, execute
    batch_size: Optional[int] = 1000
    parallel_processing: bool = False

class MappingResult(BaseModel):
    success: bool
    message: str
    records_processed: Optional[int] = 0
    records_success: Optional[int] = 0
    records_failed: Optional[int] = 0
    errors: List[str] = []
    warnings: List[str] = []
    execution_time: Optional[float] = None

# File storage for mappings and templates
MAPPING_RULES_FILE = "mapping_rules.json"
MAPPING_TEMPLATES_FILE = "mapping_templates.json"

def load_mapping_rules() -> List[Dict]:
    """Load mapping rules from JSON file"""
    try:
        if os.path.exists(MAPPING_RULES_FILE):
            with open(MAPPING_RULES_FILE, 'r') as f:
                return json.load(f)
        return []
    except Exception as e:
        logger.error(f"Error loading mapping rules: {e}")
        return []

def save_mapping_rules(rules: List[Dict]):
    """Save mapping rules to JSON file"""
    try:
        with open(MAPPING_RULES_FILE, 'w') as f:
            json.dump(rules, f, indent=2, default=str)
    except Exception as e:
        logger.error(f"Error saving mapping rules: {e}")
        raise HTTPException(status_code=500, detail="Failed to save mapping rules")

def load_mapping_templates() -> List[Dict]:
    """Load mapping templates from JSON file"""
    try:
        if os.path.exists(MAPPING_TEMPLATES_FILE):
            with open(MAPPING_TEMPLATES_FILE, 'r') as f:
                return json.load(f)
        return []
    except Exception as e:
        logger.error(f"Error loading mapping templates: {e}")
        return []

def save_mapping_templates(templates: List[Dict]):
    """Save mapping templates to JSON file"""
    try:
        with open(MAPPING_TEMPLATES_FILE, 'w') as f:
            json.dump(templates, f, indent=2, default=str)
    except Exception as e:
        logger.error(f"Error saving mapping templates: {e}")
        raise HTTPException(status_code=500, detail="Failed to save mapping templates")

# Mapping Rules Endpoints

@router.get(
    "/rules",
    response_model=List[MappingRule],
    summary="Get All Mapping Rules",
    description="Retrieve all data mapping rules."
)
async def get_mapping_rules():
    """Get all mapping rules"""
    try:
        rules = load_mapping_rules()
        return rules
    except Exception as e:
        logger.error(f"Error fetching mapping rules: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch mapping rules")

@router.get(
    "/rules/{rule_id}",
    response_model=MappingRule,
    summary="Get Mapping Rule by ID",
    description="Retrieve a specific mapping rule by its ID."
)
async def get_mapping_rule(rule_id: str):
    """Get a specific mapping rule by ID"""
    try:
        rules = load_mapping_rules()
        rule = next((r for r in rules if r.get('id') == rule_id), None)
        if not rule:
            raise HTTPException(status_code=404, detail="Mapping rule not found")
        return rule
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching mapping rule {rule_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch mapping rule")

@router.post(
    "/rules",
    response_model=MappingRule,
    summary="Create Mapping Rule",
    description="Create a new data mapping rule."
)
async def create_mapping_rule(rule: MappingRule):
    """Create a new mapping rule"""
    try:
        rules = load_mapping_rules()
        
        # Generate ID if not provided
        if not rule.id:
            rule.id = str(uuid.uuid4())
        
        # Check if ID already exists
        if any(r.get('id') == rule.id for r in rules):
            raise HTTPException(status_code=400, detail="Mapping rule ID already exists")
        
        # Set timestamps
        rule.created_at = datetime.now().isoformat()
        rule.updated_at = datetime.now().isoformat()
        
        # Convert to dict and add to rules
        rule_dict = rule.dict()
        rules.append(rule_dict)
        
        # Save to file
        save_mapping_rules(rules)
        
        return rule_dict
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating mapping rule: {e}")
        raise HTTPException(status_code=500, detail="Failed to create mapping rule")

@router.put(
    "/rules/{rule_id}",
    response_model=MappingRule,
    summary="Update Mapping Rule",
    description="Update an existing mapping rule."
)
async def update_mapping_rule(rule_id: str, rule: MappingRule):
    """Update an existing mapping rule"""
    try:
        rules = load_mapping_rules()
        
        # Find the rule to update
        rule_index = next((i for i, r in enumerate(rules) if r.get('id') == rule_id), None)
        if rule_index is None:
            raise HTTPException(status_code=404, detail="Mapping rule not found")
        
        # Update the rule
        rule.id = rule_id
        rule.updated_at = datetime.now().isoformat()
        # Preserve created_at if it exists
        if 'created_at' in rules[rule_index]:
            rule.created_at = rules[rule_index]['created_at']
        
        rules[rule_index] = rule.dict()
        
        # Save to file
        save_mapping_rules(rules)
        
        return rules[rule_index]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating mapping rule {rule_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to update mapping rule")

@router.delete(
    "/rules/{rule_id}",
    summary="Delete Mapping Rule",
    description="Delete a mapping rule."
)
async def delete_mapping_rule(rule_id: str):
    """Delete a mapping rule"""
    try:
        rules = load_mapping_rules()
        
        # Find and remove the rule
        original_count = len(rules)
        rules = [r for r in rules if r.get('id') != rule_id]
        
        if len(rules) == original_count:
            raise HTTPException(status_code=404, detail="Mapping rule not found")
        
        # Save updated rules
        save_mapping_rules(rules)
        
        return {"status": "success", "message": "Mapping rule deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting mapping rule {rule_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete mapping rule")

# Mapping Templates Endpoints

@router.get(
    "/templates",
    response_model=List[MappingTemplate],
    summary="Get All Mapping Templates",
    description="Retrieve all mapping templates."
)
async def get_mapping_templates():
    """Get all mapping templates"""
    try:
        templates = load_mapping_templates()
        return templates
    except Exception as e:
        logger.error(f"Error fetching mapping templates: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch mapping templates")

@router.post(
    "/templates",
    response_model=MappingTemplate,
    summary="Create Mapping Template",
    description="Create a new mapping template."
)
async def create_mapping_template(template: MappingTemplate):
    """Create a new mapping template"""
    try:
        templates = load_mapping_templates()
        
        # Generate ID if not provided
        if not template.id:
            template.id = str(uuid.uuid4())
        
        # Check if ID already exists
        if any(t.get('id') == template.id for t in templates):
            raise HTTPException(status_code=400, detail="Template ID already exists")
        
        # Set timestamp
        template.created_at = datetime.now().isoformat()
        
        # Convert to dict and add to templates
        template_dict = template.dict()
        templates.append(template_dict)
        
        # Save to file
        save_mapping_templates(templates)
        
        return template_dict
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating mapping template: {e}")
        raise HTTPException(status_code=500, detail="Failed to create mapping template")

@router.post(
    "/templates/{template_id}/apply",
    response_model=MappingRule,
    summary="Apply Mapping Template",
    description="Create a new mapping rule from a template."
)
async def apply_mapping_template(template_id: str, source_system_id: str, target_system_id: str, rule_name: str):
    """Apply a mapping template to create a new rule"""
    try:
        templates = load_mapping_templates()
        template = next((t for t in templates if t.get('id') == template_id), None)
        
        if not template:
            raise HTTPException(status_code=404, detail="Template not found")
        
        # Create new rule from template
        new_rule = MappingRule(
            name=rule_name,
            description=f"Created from template: {template['name']}",
            source_system_id=source_system_id,
            target_system_id=target_system_id,
            field_mappings=template['field_mappings'],
            status="draft"
        )
        
        # Use the create_mapping_rule function
        return await create_mapping_rule(new_rule)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error applying template {template_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to apply template")

# Mapping Execution Endpoints

@router.post(
    "/rules/{rule_id}/execute",
    response_model=MappingResult,
    summary="Execute Mapping Rule",
    description="Execute a mapping rule to transform data between sources."
)
async def execute_mapping_rule(rule_id: str, execution: MappingExecution):
    """Execute a mapping rule"""
    try:
        rules = load_mapping_rules()
        rule = next((r for r in rules if r.get('id') == rule_id), None)
        
        if not rule:
            raise HTTPException(status_code=404, detail="Mapping rule not found")
        
        # Simulate mapping execution
        result = await _execute_mapping(rule, execution)
        
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error executing mapping rule {rule_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to execute mapping rule")

@router.post(
    "/rules/{rule_id}/validate",
    response_model=MappingResult,
    summary="Validate Mapping Rule",
    description="Validate a mapping rule without executing transformation."
)
async def validate_mapping_rule(rule_id: str):
    """Validate a mapping rule"""
    try:
        rules = load_mapping_rules()
        rule = next((r for r in rules if r.get('id') == rule_id), None)
        
        if not rule:
            raise HTTPException(status_code=404, detail="Mapping rule not found")
        
        # Validate the mapping rule
        validation_result = await _validate_mapping(rule)
        
        return validation_result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error validating mapping rule {rule_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to validate mapping rule")

# Helper Functions

async def _execute_mapping(rule: Dict, execution: MappingExecution) -> MappingResult:
    """Execute mapping transformation"""
    try:
        # This is a simulation - in a real implementation, you would:
        # 1. Connect to source system
        # 2. Extract data according to mapping rules
        # 3. Apply transformations
        # 4. Validate results
        # 5. Load to target system
        
        start_time = datetime.now()
        
        # Simulate processing
        import asyncio
        await asyncio.sleep(0.1)  # Simulate processing time
        
        end_time = datetime.now()
        execution_time = (end_time - start_time).total_seconds()
        
        return MappingResult(
            success=True,
            message="Mapping executed successfully (simulated)",
            records_processed=1000,
            records_success=980,
            records_failed=20,
            warnings=["Some records had validation warnings"],
            execution_time=execution_time
        )
        
    except Exception as e:
        return MappingResult(
            success=False,
            message=f"Mapping execution failed: {str(e)}",
            errors=[str(e)]
        )

async def _validate_mapping(rule: Dict) -> MappingResult:
    """Validate mapping rule"""
    try:
        errors = []
        warnings = []
        
        # Validate required fields
        if not rule.get('source_system_id'):
            errors.append("Source system ID is required")
        if not rule.get('target_system_id'):
            errors.append("Target system ID is required")
        if not rule.get('field_mappings'):
            warnings.append("No field mappings defined")
        
        # Validate field mappings
        for mapping in rule.get('field_mappings', []):
            if not mapping.get('source_field'):
                errors.append("Source field is required for all mappings")
            if not mapping.get('target_field'):
                errors.append("Target field is required for all mappings")
        
        success = len(errors) == 0
        
        return MappingResult(
            success=success,
            message="Validation completed" if success else "Validation failed",
            errors=errors,
            warnings=warnings
        )
        
    except Exception as e:
        return MappingResult(
            success=False,
            message=f"Validation failed: {str(e)}",
            errors=[str(e)]
        )

@router.get(
    "/field-suggestions/{source_system_id}",
    summary="Get Field Suggestions",
    description="Get field suggestions for a data source to help with mapping."
)
async def get_field_suggestions(source_system_id: str):
    """Get field suggestions for mapping"""
    try:
        # This would typically analyze the source system schema
        # For now, return some common field suggestions
        suggestions = {
            "common_fields": [
                {"name": "id", "type": "string", "description": "Unique identifier"},
                {"name": "name", "type": "string", "description": "Name field"},
                {"name": "email", "type": "string", "description": "Email address"},
                {"name": "created_at", "type": "datetime", "description": "Creation timestamp"},
                {"name": "updated_at", "type": "datetime", "description": "Last update timestamp"},
                {"name": "status", "type": "string", "description": "Status field"}
            ],
            "transformations": [
                {"name": "uppercase", "description": "Convert to uppercase"},
                {"name": "lowercase", "description": "Convert to lowercase"},
                {"name": "trim", "description": "Remove leading/trailing spaces"},
                {"name": "date_format", "description": "Format date/time"},
                {"name": "concat", "description": "Concatenate multiple fields"},
                {"name": "substring", "description": "Extract substring"},
                {"name": "default_value", "description": "Use default if null/empty"}
            ]
        }
        
        return suggestions
    except Exception as e:
        logger.error(f"Error getting field suggestions: {e}")
        raise HTTPException(status_code=500, detail="Failed to get field suggestions")

@router.get(
    "/mapping-analytics",
    summary="Get Mapping Analytics",
    description="Get analytics and statistics about mapping rules and execution."
)
async def get_mapping_analytics():
    """Get mapping analytics"""
    try:
        rules = load_mapping_rules()
        templates = load_mapping_templates()
        
        # Calculate analytics
        total_rules = len(rules)
        active_rules = len([r for r in rules if r.get('status') == 'active'])
        draft_rules = len([r for r in rules if r.get('status') == 'draft'])
        
        # Count field mappings
        total_field_mappings = sum(len(r.get('field_mappings', [])) for r in rules)
        
        analytics = {
            "summary": {
                "total_rules": total_rules,
                "active_rules": active_rules,
                "draft_rules": draft_rules,
                "total_templates": len(templates),
                "total_field_mappings": total_field_mappings
            },
            "status_distribution": {
                "active": active_rules,
                "draft": draft_rules,
                "inactive": total_rules - active_rules - draft_rules
            },
            "recent_activity": [
                {
                    "rule_name": rule.get('name'),
                    "status": rule.get('status'),
                    "updated_at": rule.get('updated_at')
                }
                for rule in sorted(rules, key=lambda x: x.get('updated_at', ''), reverse=True)[:5]
            ]
        }
        
        return analytics
    except Exception as e:
        logger.error(f"Error getting mapping analytics: {e}")
        raise HTTPException(status_code=500, detail="Failed to get mapping analytics")
