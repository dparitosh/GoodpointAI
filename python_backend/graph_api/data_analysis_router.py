"""Enhanced FastAPI endpoints for Neo4j Data Analysis and Migration."""
import logging
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query, Response
from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field
from datetime import datetime

from neo4j.exceptions import Neo4jError

from .dependencies import get_driver

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["Data Analysis & Migration"])

# Pydantic Models for Data Analysis
class DataAnalyticsResponse(BaseModel):
    nodeDistribution: List[Dict[str, Any]]
    qualityMetrics: List[float]
    summary: Dict[str, Any]

class MigrationPlan(BaseModel):
    id: Optional[str] = None
    name: str
    sourceData: List[List[str]]
    targetSystem: str
    mappingRules: List[Dict[str, str]]
    status: Optional[str] = "pending"
    createdAt: Optional[datetime] = None

class DataMapping(BaseModel):
    sourceField: str
    targetField: str
    transformation: str
    validation: str

class ScrubConfig(BaseModel):
    rules: List[Dict[str, Any]]
    dryRun: bool = True

# Data Analytics Endpoints
@router.get("/analytics", response_model=DataAnalyticsResponse)
async def get_data_analytics(
    filters: Optional[str] = None,
    driver_instance = Depends(get_driver)
):
    """Get comprehensive data analytics from Neo4j"""
    try:
        if filters:
            logger.debug("Analytics filters provided but currently unused: %s", filters)

        # Node distribution query
        node_dist_query = """
        MATCH (n)
        RETURN labels(n) as nodeTypes, count(n) as count
        ORDER BY count DESC
        """
        
        results = await driver_instance.execute_query(
            node_dist_query, database_="neo4j", routing_="r"
        )
        
        node_distribution = []
        total_nodes = 0
        
        for record in results.records:
            labels = record["nodeTypes"]
            count = record["count"]
            total_nodes += count
            
            if labels:
                node_distribution.append({
                    "name": labels[0] if labels else "Unknown",
                    "value": count
                })
        
        # Derive quality metrics from real graph statistics (no seeded placeholder values)
        stats_query = """
        MATCH (n)
        RETURN
            count(n) as total,
            sum(CASE WHEN size(labels(n)) > 0 THEN 1 ELSE 0 END) as withLabels,
            sum(CASE WHEN size(keys(n)) > 0 THEN 1 ELSE 0 END) as withProps,
            avg(size(keys(n))) as avgProps,
            max(size(keys(n))) as maxProps
        """

        rel_stats_query = """
        MATCH (n)
        OPTIONAL MATCH (n)-[r]-()
        WITH n, count(r) as relCount
        RETURN
            count(n) as total,
            sum(CASE WHEN relCount > 0 THEN 1 ELSE 0 END) as withRels,
            avg(relCount) as avgRels,
            max(relCount) as maxRels
        """

        stats_result = await driver_instance.execute_query(
            stats_query, database_="neo4j", routing_="r"
        )
        rel_stats_result = await driver_instance.execute_query(
            rel_stats_query, database_="neo4j", routing_="r"
        )

        total_nodes_for_quality = 0
        with_labels = 0
        with_props = 0
        avg_props = 0.0
        max_props = 0.0
        if stats_result.records:
            record = stats_result.records[0]
            total_nodes_for_quality = int(record.get("total", 0) or 0)
            with_labels = int(record.get("withLabels", 0) or 0)
            with_props = int(record.get("withProps", 0) or 0)
            avg_props = float(record.get("avgProps", 0) or 0)
            max_props = float(record.get("maxProps", 0) or 0)

        total_nodes_for_rels = 0
        with_rels = 0
        avg_rels = 0.0
        max_rels = 0.0
        if rel_stats_result.records:
            record = rel_stats_result.records[0]
            total_nodes_for_rels = int(record.get("total", 0) or 0)
            with_rels = int(record.get("withRels", 0) or 0)
            avg_rels = float(record.get("avgRels", 0) or 0)
            max_rels = float(record.get("maxRels", 0) or 0)

        denom_nodes = max(total_nodes_for_quality, 1)
        denom_nodes_rels = max(total_nodes_for_rels, 1)

        labels_pct = (with_labels / denom_nodes) * 100.0
        props_pct = (with_props / denom_nodes) * 100.0
        rels_pct = (with_rels / denom_nodes_rels) * 100.0

        props_density_pct = (avg_props / max(max_props, 1.0)) * 100.0
        rels_density_pct = (avg_rels / max(max_rels, 1.0)) * 100.0

        quality_metrics: List[float] = [
            round(props_pct, 2),
            round(labels_pct, 2),
            round(rels_pct, 2),
            round(props_density_pct, 2),
            round(rels_density_pct, 2),
        ]
        
        # Summary statistics
        summary = {
            "totalNodes": total_nodes,
            "totalRelationships": await get_relationship_count(driver_instance),
            "nodeTypes": len(node_distribution),
            "averageQuality": sum(quality_metrics) / len(quality_metrics),
            "lastUpdated": datetime.now().isoformat()
        }
        
        return DataAnalyticsResponse(
            nodeDistribution=node_distribution,
            qualityMetrics=quality_metrics,
            summary=summary
        )
        
    except Neo4jError as e:
        logger.error("Error getting analytics: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e

async def get_relationship_count(driver_instance):
    """Helper function to get relationship count"""
    try:
        result = await driver_instance.execute_query(
            "MATCH ()-[r]-() RETURN count(r) as count",
            database_="neo4j", routing_="r"
        )
        return result.records[0]["count"] if result.records else 0
    except (Neo4jError, IndexError, KeyError, TypeError, RuntimeError):
        return 0

@router.get("/analytics/nodes/{node_type}")
async def get_node_statistics(
    node_type: str,
    driver_instance = Depends(get_driver)
):
    """Get statistics for specific node type"""
    try:
        query = f"""
        MATCH (n:{node_type})
        RETURN count(n) as total,
               avg(size(keys(n))) as avgProperties,
               collect(distinct keys(n)) as allProperties
        """
        
        result = await driver_instance.execute_query(
            query, database_="neo4j", routing_="r"
        )
        
        if result.records:
            record = result.records[0]
            return {
                "nodeType": node_type,
                "total": record["total"],
                "averageProperties": record["avgProperties"],
                "allProperties": record["allProperties"],
                "timestamp": datetime.now().isoformat()
            }
        
        return {"nodeType": node_type, "total": 0}
        
    except Neo4jError as e:
        logger.error("Error getting node statistics for %s: %s", node_type, e)
        raise HTTPException(status_code=500, detail=str(e)) from e

# Migration Endpoints
migration_plans_storage: List[MigrationPlan] = []  # Deprecated: demo-only storage retained for backward compatibility.

@router.get("/migration/plans")
async def get_migration_plans(
    response: Response,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
):
    """Get all migration plans.

    This feature is intentionally not implemented here (no mock/demo behavior).
    """
    raise HTTPException(
        status_code=501,
        detail="Migration plans are not implemented in this service. Configure a real migration engine/integration.",
    )

@router.post("/migration/plans")
async def create_migration_plan(plan: MigrationPlan):
    """Create a new migration plan.

    This feature is intentionally not implemented here (no mock/demo behavior).
    """
    raise HTTPException(
        status_code=501,
        detail="Migration plan creation is not implemented in this service. Configure a real migration engine/integration.",
    )

@router.post("/migration/plans/{plan_id}/execute")
async def execute_migration_plan(
    plan_id: str,
    background_tasks: BackgroundTasks,
    driver_instance = Depends(get_driver)
):
    """Execute a migration plan.

    This feature is intentionally not implemented here (no mock/demo behavior).
    """
    _ = plan_id, background_tasks, driver_instance
    raise HTTPException(
        status_code=501,
        detail="Migration execution is not implemented in this service. Configure a real migration engine/integration.",
    )

async def run_migration_background(plan: MigrationPlan, _driver_instance):
    """Deprecated demo hook kept to avoid import errors in older code paths."""
    _ = plan, _driver_instance
    return

@router.get("/migration/plans/{plan_id}/status")
async def get_migration_status(plan_id: str):
    """Get migration plan status.

    This feature is intentionally not implemented here (no mock/demo behavior).
    """
    _ = plan_id
    raise HTTPException(
        status_code=501,
        detail="Migration status is not implemented in this service. Configure a real migration engine/integration.",
    )

# Data Mapping Endpoints
data_mappings_storage: List[Dict[str, Any]] = []  # Deprecated: demo-only storage retained for backward compatibility.

@router.get("/mappings")
async def get_data_mappings(
    response: Response,
    source: Optional[str] = None,
    target: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
):
    """Get data mappings.

    This feature is intentionally not implemented here (no mock/demo behavior).
    """
    _ = response, source, target, skip, limit
    raise HTTPException(
        status_code=501,
        detail="Data mappings are not implemented in this service. Use /api/data-mapping/* for rule configuration.",
    )

@router.post("/mappings")
async def create_data_mapping(mapping_data: Dict[str, Any]):
    """Create a new data mapping.

    This feature is intentionally not implemented here (no mock/demo behavior).
    """
    _ = mapping_data
    raise HTTPException(
        status_code=501,
        detail="Data mapping creation is not implemented in this service. Use /api/data-mapping/* for rule configuration.",
    )

@router.post("/mappings/{mapping_id}/validate")
async def validate_mapping(mapping_id: str):
    """Validate a data mapping.

    This feature is intentionally not implemented here (no mock/demo behavior).
    """
    _ = mapping_id
    raise HTTPException(
        status_code=501,
        detail="Mapping validation is not implemented in this service. Use /api/data-mapping/rules/{id}/validate.",
    )

# Data Quality and Scrubbing Endpoints
@router.get("/data-quality/rules")
async def get_data_quality_rules(
    response: Response,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
):
    """Get available data quality rules.

    This legacy endpoint returned hard-coded rules; it is now disabled to avoid demo/mock behavior.
    Use the real Postgres-backed rules under /api/analytics/quality/*.
    """
    _ = response, skip, limit
    raise HTTPException(
        status_code=501,
        detail="Legacy data quality rules endpoint is disabled. Use /api/analytics/quality/rules.",
    )

@router.post("/data-quality/scrub")
async def apply_data_scrubbing(
    scrub_config: ScrubConfig,
    background_tasks: BackgroundTasks,
    driver_instance = Depends(get_driver)
):
    """Apply data scrubbing rules.

    This legacy endpoint previously returned simulated results; it is now disabled.
    """
    _ = scrub_config, background_tasks, driver_instance
    raise HTTPException(
        status_code=501,
        detail="Legacy data scrubbing endpoint is disabled. Implement scrubbing via real workflow execution.",
    )

async def run_data_scrubbing(scrub_config: ScrubConfig, _driver_instance):
    """Deprecated demo hook kept to avoid import errors in older code paths."""
    _ = scrub_config, _driver_instance
    return

@router.get("/data-quality/duplicates")
async def get_duplicate_analysis(driver_instance = Depends(get_driver)):
    """Analyze potential duplicates in the database"""
    try:
        # Simple duplicate detection query
        query = """
        MATCH (n)
        WHERE n.name IS NOT NULL
        WITH n.name as name, collect(n) as nodes
        WHERE size(nodes) > 1
        RETURN name, size(nodes) as duplicateCount, 
               [node in nodes | id(node)] as nodeIds
        LIMIT 100
        """
        
        result = await driver_instance.execute_query(
            query, database_="neo4j", routing_="r"
        )
        
        duplicates = []
        for record in result.records:
            duplicates.append({
                "name": record["name"],
                "count": record["duplicateCount"],
                "nodeIds": record["nodeIds"]
            })
        
        return {
            "duplicateGroups": duplicates,
            "totalDuplicateGroups": len(duplicates),
            "analyzedAt": datetime.now().isoformat()
        }
        
    except Neo4jError as e:
        logger.error("Error analyzing duplicates: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e

# Target Applications Endpoints
target_applications: List[Dict[str, Any]] = []

@router.get("/target-apps")
async def get_target_applications(
    response: Response,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
):
    """Get available target applications.

    This endpoint previously returned hard-coded sample apps; it is now disabled.
    """
    _ = response, skip, limit
    raise HTTPException(
        status_code=501,
        detail="Target applications are not configured. Use external integrations to register real targets.",
    )

@router.post("/target-apps/{app_id}/sync")
async def sync_to_target_app(
    app_id: str,
    sync_data: Dict[str, Any],
    background_tasks: BackgroundTasks
):
    """Synchronize data to target application.

    Disabled (no mock/demo execution).
    """
    _ = app_id, sync_data, background_tasks
    raise HTTPException(
        status_code=501,
        detail="Target synchronization is not implemented. Configure a real integration connector and workflow runner.",
    )

async def run_target_sync(app_id: str, _sync_data: Dict[str, Any]):
    """Deprecated demo hook kept to avoid import errors in older code paths."""
    _ = app_id, _sync_data
    return

# Bulk Operations Endpoints
@router.post("/bulk/import")
async def bulk_import_data(
    import_request: Dict[str, Any],
    background_tasks: BackgroundTasks,
    driver_instance = Depends(get_driver)
):
    """Bulk import data from spreadsheet.

    Disabled: previously a stub/background task with no real execution.
    """
    _ = import_request, background_tasks, driver_instance
    raise HTTPException(
        status_code=501,
        detail="Bulk import is not implemented. Use a real ingestion workflow and persist results to Postgres/Neo4j.",
    )

async def run_bulk_import(data: List[List[str]], _config: Dict[str, Any], _driver_instance):
    """Deprecated demo hook kept to avoid import errors in older code paths."""
    _ = data, _config, _driver_instance
    return

@router.post("/bulk/export")
async def bulk_export_data(
    export_config: Dict[str, Any],
    driver_instance = Depends(get_driver)
):
    """Bulk export data for spreadsheet"""
    try:
        # Build export query based on configuration
        query = export_config.get("query", "MATCH (n) RETURN n LIMIT 1000")
        
        result = await driver_instance.execute_query(
            query, database_="neo4j", routing_="r"
        )
        
        # Convert results to spreadsheet format
        export_data = []
        if result.records:
            # Extract headers from first record
            first_record = result.records[0]
            headers = list(first_record.keys())
            export_data.append(headers)
            
            # Extract data rows
            for record in result.records:
                row = []
                for header in headers:
                    value = record[header]
                    # Convert complex objects to strings
                    try:
                        row.append(str(dict(value)))
                    except TypeError:
                        row.append(str(value))
                export_data.append(row)
        
        return {
            "data": export_data,
            "recordCount": len(export_data) - 1 if export_data else 0,
            "exportedAt": datetime.now().isoformat()
        }
        
    except Neo4jError as e:
        logger.error("Bulk export failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/export/formats")
async def get_export_formats():
    """Return supported export formats (UI convenience endpoint)."""
    return {
        "formats": ["excel", "csv", "json"],
        "default": "excel",
    }


@router.get("/export/history")
async def get_export_history(
    response: Response,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
):
    """Return export history.

    The current UI can render an empty list; this endpoint prevents 404s.
    """
    items: List[Dict[str, Any]] = []
    response.headers["X-Total-Count"] = str(len(items))
    return items[skip : skip + limit]

# Schema Information Endpoints
@router.get("/schema")
async def get_database_schema(driver_instance = Depends(get_driver)):
    """Get complete database schema information"""
    try:
        # Get node labels
        labels_result = await driver_instance.execute_query(
            "CALL db.labels()", database_="neo4j", routing_="r"
        )
        labels = [record["label"] for record in labels_result.records]
        
        # Get relationship types
        rel_types_result = await driver_instance.execute_query(
            "CALL db.relationshipTypes()", database_="neo4j", routing_="r"
        )
        relationship_types = [record["relationshipType"] for record in rel_types_result.records]
        
        # Get property keys
        props_result = await driver_instance.execute_query(
            "CALL db.propertyKeys()", database_="neo4j", routing_="r"
        )
        property_keys = [record["propertyKey"] for record in props_result.records]
        
        return {
            "nodeLabels": labels,
            "relationshipTypes": relationship_types,
            "propertyKeys": property_keys,
            "retrievedAt": datetime.now().isoformat()
        }
        
    except Neo4jError as e:
        logger.error("Error retrieving schema: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e

@router.get("/schema/labels")
async def get_node_labels(driver_instance = Depends(get_driver)):
    """Get all node labels with counts"""
    try:
        # Get labels
        labels_result = await driver_instance.execute_query(
            "CALL db.labels()", database_="neo4j", routing_="r"
        )
        labels = [record["label"] for record in labels_result.records]
        
        # Get total node count
        count_result = await driver_instance.execute_query(
            "MATCH (n) RETURN count(n) as totalNodes", database_="neo4j", routing_="r"
        )
        total_count = count_result.records[0]["totalNodes"] if count_result.records else 0
        
        return {
            "labels": labels,
            "count": total_count
        }
    except Neo4jError as e:
        logger.error("Error getting node labels: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e

@router.get("/schema/relationships")
async def get_relationship_types(driver_instance = Depends(get_driver)):
    """Get all relationship types with counts"""
    try:
        # Get relationship types
        types_result = await driver_instance.execute_query(
            "CALL db.relationshipTypes()", database_="neo4j", routing_="r"
        )
        types = [record["relationshipType"] for record in types_result.records]
        
        # Get total relationship count
        count_result = await driver_instance.execute_query(
            "MATCH ()-[r]->() RETURN count(r) as totalRelationships", database_="neo4j", routing_="r"
        )
        total_count = count_result.records[0]["totalRelationships"] if count_result.records else 0
        
        return {
            "types": types,
            "count": total_count
        }
    except Neo4jError as e:
        logger.error("Error getting relationship types: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e

@router.get("/schema/properties")
async def get_property_keys(
    response: Response,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    driver_instance = Depends(get_driver),
):
    """Get all property keys"""
    try:
        result = await driver_instance.execute_query(
            "CALL db.propertyKeys()", database_="neo4j", routing_="r"
        )
        keys = [record["propertyKey"] for record in result.records]
        response.headers["X-Total-Count"] = str(len(keys))
        return keys[skip : skip + limit]
    except Neo4jError as e:
        logger.error("Error getting property keys: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e

# Data Conversion Endpoints for Spreadsheet Tool

class DataConversionRequest(BaseModel):
    sourceData: str
    sourceFormat: str  # json, xml, csv
    targetFormat: str  # csv, json, xml
    mappingRules: Optional[List[Dict[str, Any]]] = Field(default_factory=lambda: [])

class DataConversionResponse(BaseModel):
    success: bool
    convertedData: List[List[str]]
    validationResults: Optional[List[Dict[str, Any]]] = None
    message: str

@router.post("/convert", response_model=DataConversionResponse)
async def convert_data(request: DataConversionRequest):
    """Convert data between formats with optional mapping rules"""
    try:
        # Basic conversion logic (can be enhanced)
        if request.sourceFormat == 'json' and request.targetFormat == 'csv':
            import json
            parsed_data = json.loads(request.sourceData)
            if not isinstance(parsed_data, list) or len(parsed_data) == 0:
                raise ValueError("Invalid JSON array")
            
            # Extract headers
            headers = list(parsed_data[0].keys())
            converted_data = [headers]
            
            # Convert rows
            for row in parsed_data:
                converted_row = [str(row.get(h, '')) for h in headers]
                converted_data.append(converted_row)
            
            return DataConversionResponse(
                success=True,
                convertedData=converted_data,
                message=f"Successfully converted {len(parsed_data)} rows from JSON to CSV"
            )
        
        # Add more conversion logic as needed
        return DataConversionResponse(
            success=False,
            convertedData=[],
            message=f"Conversion from {request.sourceFormat} to {request.targetFormat} not yet implemented"
        )
        
    except (ValueError, TypeError) as e:
        logger.error("Data conversion failed: %s", e)
        return DataConversionResponse(
            success=False,
            convertedData=[],
            message=f"Conversion failed: {str(e)}"
        )

# Data Validation Endpoints
class DataValidationRequest(BaseModel):
    data: List[List[str]]
    validationRules: Optional[List[Dict[str, Any]]] = Field(default_factory=lambda: [])

class DataValidationResponse(BaseModel):
    results: List[Dict[str, Any]]
    overallScore: float
    issues: List[str]

@router.post("/validate", response_model=DataValidationResponse)
async def validate_data(request: DataValidationRequest):
    """Validate data quality and consistency"""
    try:
        if not request.data or len(request.data) < 2:
            raise ValueError("Insufficient data for validation")
        
        headers = request.data[0]
        rows = request.data[1:]
        results: List[Dict[str, Any]] = []
        
        for col_index, header in enumerate(headers):
            column_data = [row[col_index] if col_index < len(row) else '' for row in rows]
            
            # Calculate completeness
            non_empty_count = sum(1 for cell in column_data if cell and str(cell).strip())
            completeness = (non_empty_count / len(column_data)) * 100 if column_data else 0
            
            # Check type consistency
            types = set()
            for cell in column_data:
                if cell and str(cell).strip():
                    if str(cell).replace('.', '').replace('-', '').isdigit():
                        types.add('number')
                    elif cell in ['true', 'false', 'True', 'False', '1', '0']:
                        types.add('boolean')
                    else:
                        types.add('string')
            
            type_consistency = 'Good' if len(types) <= 1 else 'Mixed'
            unique_count = len(set(column_data))
            
            results.append({
                'column': header,
                'index': col_index,
                'completeness': f"{completeness:.1f}",
                'typeConsistency': type_consistency,
                'uniqueValues': unique_count,
                'issues': []
            })
        
        completeness_scores: List[float] = [
            float(str(r.get("completeness", 0.0))) for r in results
        ]
        overall_score = (sum(completeness_scores) / len(completeness_scores)) if completeness_scores else 0.0
        
        return DataValidationResponse(
            results=results,
            overallScore=overall_score,
            issues=[]
        )
        
    except (ValueError, TypeError) as e:
        logger.error("Data validation failed: %s", e)
        raise HTTPException(status_code=400, detail=str(e)) from e
