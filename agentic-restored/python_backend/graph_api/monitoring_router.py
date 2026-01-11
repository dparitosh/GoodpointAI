import logging
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from typing import List, Dict, Any
from datetime import datetime
import neo4j
from pydantic import BaseModel

from .dependencies import get_driver
from core.config import NEO4J_DATABASE

# pylint: disable=broad-exception-caught

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/monitoring", tags=["Monitoring & Data Quality"])

class AlertModel(BaseModel):
    id: int
    level: str  # warning, error, info
    message: str
    timestamp: str
    component: str

class FlowStatusModel(BaseModel):
    id: str
    name: str
    status: str
    throughput: str
    lastActivity: str
    health: str

class DataQualityMetrics(BaseModel):
    totalRecords: int
    validRecords: int
    duplicates: int
    nullValues: int
    qualityScore: float
    issues: List[Dict[str, Any]]

@router.get(
    "/alerts",
    response_model=List[AlertModel],
    summary="Get System Alerts",
    description="Fetches current system alerts and notifications."
)
async def get_system_alerts(
    response: Response,
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    driver_instance: neo4j.AsyncDriver = Depends(get_driver)
):
    """Get system alerts from Neo4j monitoring data"""
    alerts: list[AlertModel] = []
    
    try:
        count_query = """
        MATCH (n)
        WHERE n.status = 'error' OR n.health = 'warning'
        RETURN COUNT(n) as total
        """

        # Query for data quality issues
        quality_query = """
        MATCH (n)
        WHERE n.status = 'error' OR n.health = 'warning'
        RETURN n.id as component, n.status as status, n.lastUpdate as lastUpdate
        SKIP $skip
        LIMIT $limit
        """

        count_results = await driver_instance.execute_query(
            count_query, database_=NEO4J_DATABASE, routing_="r"
        )
        total_count = 0
        if count_results.records:
            total_count = int(count_results.records[0].get("total", 0) or 0)
        response.headers["X-Total-Count"] = str(total_count)
        
        results = await driver_instance.execute_query(
            quality_query, database_=NEO4J_DATABASE, routing_="r"
            , parameters_={"skip": skip, "limit": limit}
        )
        
        alert_id = 1
        for record in results.records:
            component = record.get("component", "unknown")
            status = record.get("status", "info")
            last_update = record.get("lastUpdate")
            
            if status == "error":
                alerts.append(AlertModel(
                    id=alert_id,
                    level="error",
                    message=f"Component {component} has reported an error condition",
                    timestamp=(last_update or datetime.now()).isoformat(),
                    component=str(component)
                ))
            elif status == "warning":
                alerts.append(AlertModel(
                    id=alert_id,
                    level="warning", 
                    message=f"Component {component} requires attention",
                    timestamp=(last_update or datetime.now()).isoformat(),
                    component=str(component)
                ))
            
            alert_id += 1
            
    except (neo4j.exceptions.Neo4jError, RuntimeError, OSError, ValueError, TypeError) as e:
        logger.error("Error fetching alerts: %s", e)
        alerts = []
        response.headers["X-Total-Count"] = "0"
    
    return alerts

@router.get(
    "/flow-status",
    response_model=List[FlowStatusModel],
    summary="Get Flow Status", 
    description="Get status of data flows and pipelines."
)
async def get_flow_status(
    response: Response,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=200),
    driver_instance: neo4j.AsyncDriver = Depends(get_driver)
):
    """Get flow status from Neo4j data"""
    flows: list[FlowStatusModel] = []
    
    try:
        count_query = """
        MATCH (p:Pipeline)
        RETURN COUNT(p) as total
        """

        # Query for pipeline/flow information
        flow_query = """
        MATCH (p:Pipeline)
        OPTIONAL MATCH (p)-[:PROCESSES]->(n)
        WITH p, COUNT(n) as nodeCount
        RETURN p.id as id, p.name as name, p.status as status, 
               p.throughput as throughput, p.lastActivity as lastActivity,
               p.health as health, nodeCount
        ORDER BY p.lastActivity DESC
        SKIP $skip
        LIMIT $limit
        """

        count_results = await driver_instance.execute_query(
            count_query, database_=NEO4J_DATABASE, routing_="r"
        )
        total_count = 0
        if count_results.records:
            total_count = int(count_results.records[0].get("total", 0) or 0)
        response.headers["X-Total-Count"] = str(total_count)
        
        results = await driver_instance.execute_query(
            flow_query, database_=NEO4J_DATABASE, routing_="r"
            , parameters_={"skip": skip, "limit": limit}
        )
        
        for record in results.records:
            flows.append(FlowStatusModel(
                id=record.get("id", f"flow-{len(flows)+1}"),
                name=record.get("name", f"Data Pipeline {len(flows)+1}"),
                status=record.get("status", "running"),
                throughput=record.get("throughput", f"{1000 + len(flows)*200} records/min"),
                lastActivity=record.get("lastActivity", "Active"),
                health=record.get("health", "healthy")
            ))
            
    except (neo4j.exceptions.Neo4jError, RuntimeError, OSError, ValueError, TypeError) as e:
        logger.error("Error fetching flow status: %s", e)
        flows = []
        response.headers["X-Total-Count"] = "0"
    
    return flows

@router.get(
    "/data-quality",
    response_model=DataQualityMetrics,
    summary="Get Data Quality Metrics",
    description="Get comprehensive data quality assessment."
)
async def get_data_quality_metrics(
    driver_instance: neo4j.AsyncDriver = Depends(get_driver)
):
    """Get data quality metrics from Neo4j"""
    
    try:
        # Query for data quality assessment
        quality_query = """
        MATCH (n)
        WITH COUNT(n) as totalNodes
        MATCH (n) WHERE n IS NOT NULL
        WITH totalNodes, COUNT(n) as validNodes
        MATCH (n) WHERE n.id IS NOT NULL
        WITH totalNodes, validNodes, COUNT(n) as nodesWithId
        OPTIONAL MATCH (n) WHERE n.status = 'duplicate'
        WITH totalNodes, validNodes, nodesWithId, COUNT(n) as duplicateNodes
        OPTIONAL MATCH (n) WHERE ANY(prop IN keys(n) WHERE n[prop] IS NULL)
        WITH totalNodes, validNodes, nodesWithId, duplicateNodes, COUNT(DISTINCT n) as nodesWithNulls
        RETURN totalNodes, validNodes, nodesWithId, duplicateNodes, nodesWithNulls
        """
        
        results = await driver_instance.execute_query(
            quality_query, database_=NEO4J_DATABASE, routing_="r"
        )
        
        if results.records:
            record = results.records[0]
            total = record.get("totalNodes", 0)
            valid = record.get("validNodes", 0) 
            duplicates = record.get("duplicateNodes", 0)
            null_values = record.get("nodesWithNulls", 0)
            
            quality_score = (valid / max(total, 1)) * 100 if total > 0 else 100
            
            # Find specific quality issues
            issues_query = """
            MATCH (n) WHERE n.status IN ['error', 'invalid', 'duplicate']
            RETURN n.id as nodeId, n.status as issue, labels(n) as nodeType
            LIMIT 10
            """
            
            issues_results = await driver_instance.execute_query(
                issues_query, database_=NEO4J_DATABASE, routing_="r"
            )
            
            issues = []
            for issue_record in issues_results.records:
                issues.append({
                    "nodeId": issue_record.get("nodeId"),
                    "issue": issue_record.get("issue"),
                    "nodeType": issue_record.get("nodeType", [])
                })
            
            return DataQualityMetrics(
                totalRecords=total,
                validRecords=valid,
                duplicates=duplicates,
                nullValues=null_values,
                qualityScore=quality_score,
                issues=issues
            )
            
    except (neo4j.exceptions.Neo4jError, RuntimeError, OSError, ValueError, TypeError) as e:
        logger.error("Error fetching data quality metrics: %s", e)
        raise HTTPException(
            status_code=503,
            detail="Data quality metrics are unavailable (Neo4j query failed)",
        ) from e

@router.get(
    "/performance-metrics",
    summary="Get Performance Metrics",
    description="Get system performance metrics over time."
)
async def get_performance_metrics(
    time_range: str = "1h",
    driver_instance: neo4j.AsyncDriver = Depends(get_driver)
):
    """Get performance metrics from Neo4j monitoring"""
    
    try:
        # Query for performance data
        perf_query = """
        MATCH (m:Metric) 
        WHERE m.timestamp > datetime() - duration('PT1H')
        RETURN m.timestamp as timestamp, m.cpu_load as cpuLoad, 
               m.memory_used as memoryUsed, m.throughput as throughput,
               m.latency as latency
        ORDER BY m.timestamp DESC
        LIMIT 100
        """
        
        results = await driver_instance.execute_query(
            perf_query, database_=NEO4J_DATABASE, routing_="r"
        )
        
        metrics = []
        for record in results.records:
            metrics.append({
                "timestamp": record.get("timestamp", datetime.now()).isoformat(),
                "cpuLoad": record.get("cpuLoad", 0),
                "memoryUsed": record.get("memoryUsed", 0),
                "throughput": record.get("throughput", 0),
                "latency": record.get("latency", 0)
            })
            
        return {
            "timeRange": time_range,
            "metrics": metrics,
            "summary": {
                "avgCpuLoad": sum(m["cpuLoad"] for m in metrics) / max(len(metrics), 1),
                "avgThroughput": sum(m["throughput"] for m in metrics) / max(len(metrics), 1),
                "avgLatency": sum(m["latency"] for m in metrics) / max(len(metrics), 1)
            }
        }
        
    except (neo4j.exceptions.Neo4jError, RuntimeError, OSError, ValueError, TypeError) as e:
        logger.error("Error fetching performance metrics: %s", e)

        return {
            "timeRange": time_range,
            "metrics": [],
            "summary": {
                "avgCpuLoad": 0.0,
                "avgThroughput": 0.0,
                "avgLatency": 0.0
            }
        }

@router.get(
    "/templates",
    summary="Get Data Mapping Templates",
    description="Get available data mapping templates from Neo4j."
)
async def get_mapping_templates(
    response: Response,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    driver_instance: neo4j.AsyncDriver = Depends(get_driver)
):
    """Get data mapping templates from Neo4j"""
    
    try:
        count_query = """
        MATCH (t:Template)
        RETURN COUNT(t) as total
        """

        # Query for mapping templates
        template_query = """
        MATCH (t:Template)
        OPTIONAL MATCH (t)-[:HAS_FIELD]->(f:Field)
        WITH t, COLLECT(f.name) as fields
        RETURN t.id as id, t.name as name, t.description as description,
               t.category as category, fields
        ORDER BY t.name
        SKIP $skip
        LIMIT $limit
        """

        count_results = await driver_instance.execute_query(
            count_query, database_=NEO4J_DATABASE, routing_="r"
        )
        total_count = 0
        if count_results.records:
            total_count = int(count_results.records[0].get("total", 0) or 0)
        response.headers["X-Total-Count"] = str(total_count)
        
        results = await driver_instance.execute_query(
            template_query,
            database_=NEO4J_DATABASE,
            routing_="r",
            parameters_={"skip": skip, "limit": limit},
        )
        
        templates = []
        for record in results.records:
            templates.append({
                "id": record.get("id"),
                "name": record.get("name"),
                "description": record.get("description"),
                "category": record.get("category", "General"),
                "fields": record.get("fields", [])
            })
            
        return templates
        
    except (neo4j.exceptions.Neo4jError, RuntimeError, OSError, ValueError, TypeError) as e:
        logger.error("Error fetching templates: %s", e)

        response.headers["X-Total-Count"] = "0"
        return []
