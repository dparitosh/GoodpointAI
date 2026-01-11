import logging
import json
import os
from json import JSONDecodeError
from typing import List, Dict, Optional
from fastapi import APIRouter, HTTPException, Query, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel
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
            with open(MAPPING_RULES_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        return []
    except (OSError, JSONDecodeError) as exc:
        logger.error("Error loading mapping rules: %s", exc)
        return []

def save_mapping_rules(rules: List[Dict]):
    """Save mapping rules to JSON file"""
    try:
        with open(MAPPING_RULES_FILE, 'w', encoding='utf-8') as f:
            json.dump(rules, f, indent=2, default=str)
    except (OSError, TypeError, ValueError) as exc:
        logger.error("Error saving mapping rules: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to save mapping rules") from exc

def load_mapping_templates() -> List[Dict]:
    """Load mapping templates from JSON file"""
    try:
        if os.path.exists(MAPPING_TEMPLATES_FILE):
            with open(MAPPING_TEMPLATES_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        return []
    except (OSError, JSONDecodeError) as exc:
        logger.error("Error loading mapping templates: %s", exc)
        return []

def save_mapping_templates(templates: List[Dict]):
    """Save mapping templates to JSON file"""
    try:
        with open(MAPPING_TEMPLATES_FILE, 'w', encoding='utf-8') as f:
            json.dump(templates, f, indent=2, default=str)
    except (OSError, TypeError, ValueError) as exc:
        logger.error("Error saving mapping templates: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to save mapping templates") from exc

# Mapping Rules Endpoints

@router.get(
    "/rules",
    response_model=List[MappingRule],
    summary="Get All Mapping Rules",
    description="Retrieve all data mapping rules."
)
async def get_mapping_rules(
    response: Response,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
):
    """Get all mapping rules"""
    rules = load_mapping_rules()
    response.headers["X-Total-Count"] = str(len(rules))
    return rules[skip : skip + limit]

@router.get(
    "/rules/{rule_id}",
    response_model=MappingRule,
    summary="Get Mapping Rule by ID",
    description="Retrieve a specific mapping rule by its ID."
)
async def get_mapping_rule(rule_id: str):
    """Get a specific mapping rule by ID"""
    rules = load_mapping_rules()
    rule = next((r for r in rules if r.get('id') == rule_id), None)
    if not rule:
        raise HTTPException(status_code=404, detail="Mapping rule not found")
    return rule

@router.post(
    "/rules",
    response_model=MappingRule,
    summary="Create Mapping Rule",
    description="Create a new data mapping rule."
)
async def create_mapping_rule(rule: MappingRule):
    """Create a new mapping rule"""
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

@router.put(
    "/rules/{rule_id}",
    response_model=MappingRule,
    summary="Update Mapping Rule",
    description="Update an existing mapping rule."
)
async def update_mapping_rule(rule_id: str, rule: MappingRule):
    """Update an existing mapping rule"""
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

@router.delete(
    "/rules/{rule_id}",
    summary="Delete Mapping Rule",
    description="Delete a mapping rule."
)
async def delete_mapping_rule(rule_id: str):
    """Delete a mapping rule"""
    rules = load_mapping_rules()

    # Find and remove the rule
    original_count = len(rules)
    rules = [r for r in rules if r.get('id') != rule_id]

    if len(rules) == original_count:
        raise HTTPException(status_code=404, detail="Mapping rule not found")

    # Save updated rules
    save_mapping_rules(rules)

    return {"status": "success", "message": "Mapping rule deleted successfully"}

# Mapping Templates Endpoints

@router.get(
    "/templates",
    response_model=List[MappingTemplate],
    summary="Get All Mapping Templates",
    description="Retrieve all mapping templates."
)
async def get_mapping_templates(
    response: Response,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
):
    """Get all mapping templates"""
    templates = load_mapping_templates()
    response.headers["X-Total-Count"] = str(len(templates))
    return templates[skip : skip + limit]

@router.post(
    "/templates",
    response_model=MappingTemplate,
    summary="Create Mapping Template",
    description="Create a new mapping template."
)
async def create_mapping_template(template: MappingTemplate):
    """Create a new mapping template"""
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

@router.post(
    "/templates/{template_id}/apply",
    response_model=MappingRule,
    summary="Apply Mapping Template",
    description="Create a new mapping rule from a template."
)
async def apply_mapping_template(template_id: str, source_system_id: str, target_system_id: str, rule_name: str):
    """Apply a mapping template to create a new rule"""
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

# Mapping Execution Endpoints

@router.post(
    "/rules/{rule_id}/execute",
    response_model=MappingResult,
    summary="Execute Mapping Rule",
    description="Execute a mapping rule to transform data between sources."
)
async def execute_mapping_rule(rule_id: str, execution: MappingExecution):
    """Execute a mapping rule"""
    _ = execution
    rules = load_mapping_rules()
    rule = next((r for r in rules if r.get('id') == rule_id), None)

    if not rule:
        raise HTTPException(status_code=404, detail="Mapping rule not found")

    # Fail-closed: execution requires real source/target connectors and a workflow runner.
    # We intentionally do not simulate/fabricate execution results.
    result = MappingResult(
        success=False,
        message="Mapping execution is unavailable: source/target connectors and an execution engine are not configured.",
        errors=["EXECUTION_NOT_CONFIGURED"],
    )
    return JSONResponse(status_code=503, content=result.dict())

@router.post(
    "/rules/{rule_id}/validate",
    response_model=MappingResult,
    summary="Validate Mapping Rule",
    description="Validate a mapping rule without executing transformation."
)
async def validate_mapping_rule(rule_id: str):
    """Validate a mapping rule"""
    rules = load_mapping_rules()
    rule = next((r for r in rules if r.get('id') == rule_id), None)

    if not rule:
        raise HTTPException(status_code=404, detail="Mapping rule not found")

    # Validate the mapping rule
    return await _validate_mapping(rule)

# Helper Functions

async def _validate_mapping(rule: Dict) -> MappingResult:
    """Validate mapping rule"""
    errors: List[str] = []
    warnings: List[str] = []

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

@router.get(
    "/field-suggestions/{source_system_id}",
    summary="Get Field Suggestions",
    description="Get field suggestions for a data source to help with mapping."
)
async def get_field_suggestions(source_system_id: str):
    """Get field suggestions for mapping"""
    _ = source_system_id

    # Fail-closed: schema introspection for arbitrary source systems is not configured.
    # Return empty suggestions rather than fabricated examples.
    return {"common_fields": [], "transformations": []}

@router.get(
    "/mapping-analytics",
    summary="Get Mapping Analytics",
    description="Get analytics and statistics about mapping rules and execution."
)
async def get_mapping_analytics():
    """Get mapping analytics"""
    rules = load_mapping_rules()
    templates = load_mapping_templates()

    # Calculate analytics
    total_rules = len(rules)
    active_rules = len([r for r in rules if r.get('status') == 'active'])
    draft_rules = len([r for r in rules if r.get('status') == 'draft'])

    # Count field mappings
    total_field_mappings = sum(len(r.get('field_mappings', [])) for r in rules)

    return {
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
