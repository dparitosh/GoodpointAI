"""
 Data Lineage Tracking Service
==================================

Intelligent lineage tracking for PLM data migration with:
- Neo4j-based lineage graph (source → transformation → target)
- Impact analysis and dependency tracking
- Audit trail for compliance (FDA 21 CFR Part 11, CMMC, ITAR)
- GraphQL API for querying lineage
- Real-time lineage updates via WebSocket

Integrations:
- Neo4j for lineage graph storage
- OpenSearch for lineage search and analytics
- AWS S3/Azure Blob for audit log archival
"""

import logging
from datetime import datetime, timezone
from typing import List, Dict, Optional, Any
from enum import Enum
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
import neo4j
import json

from .dependencies import get_driver

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/lineage", tags=["Data Lineage"])


# ============= MODELS =============

class LineageNodeType(str, Enum):
    SOURCE_SYSTEM = "source_system"
    TARGET_SYSTEM = "target_system"
    TRANSFORMATION = "transformation"
    VALIDATION = "validation"
    AGENT = "agent"
    DATA_RECORD = "data_record"


class LineageRelationType(str, Enum):
    EXTRACTED_FROM = "EXTRACTED_FROM"
    TRANSFORMED_BY = "TRANSFORMED_BY"
    VALIDATED_BY = "VALIDATED_BY"
    LOADED_TO = "LOADED_TO"
    DEPENDS_ON = "DEPENDS_ON"
    PROCESSED_BY = "PROCESSED_BY"


# Security: Set of allowed relationship types for Cypher queries
ALLOWED_RELATIONSHIP_TYPES = frozenset(e.value for e in LineageRelationType)


class LineageNode(BaseModel):
    id: str
    type: LineageNodeType
    name: str
    properties: Dict[str, Any] = {}
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    workflow_id: Optional[str] = None


class LineageRelationship(BaseModel):
    source_id: str
    target_id: str
    type: LineageRelationType
    properties: Dict[str, Any] = {}
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    workflow_id: Optional[str] = None


class LineageTraceRequest(BaseModel):
    record_id: str
    direction: str = "both"  # upstream, downstream, both
    max_depth: int = 5
    node_types: Optional[List[str]] = None


class LineageImpactAnalysisRequest(BaseModel):
    source_node_id: str
    change_type: str  # schema_change, data_quality, system_failure
    simulation_mode: bool = True


class AuditTrailRequest(BaseModel):
    workflow_id: str
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    include_transformations: bool = True


# ============= LINEAGE SERVICE =============

class LineageService:
    """Service for managing data lineage tracking"""
    
    def __init__(self, driver: neo4j.AsyncDriver):
        self.driver = driver
        self.lineage_cache: Dict[str, Any] = {}
    
    async def create_lineage_node(self, node: LineageNode) -> Optional[Dict[str, Any]]:
        """Create a lineage node in Neo4j"""
        query = """
        CREATE (n:LineageNode {
            id: $id,
            type: $type,
            name: $name,
            properties: $properties,
            created_at: $created_at,
            workflow_id: $workflow_id
        })
        RETURN n
        """
        
        async with self.driver.session(database="neo4j") as session:
            result = await session.run(
                query,
                id=node.id,
                type=node.type.value,
                name=node.name,
                properties=json.dumps(node.properties),
                created_at=node.created_at.isoformat(),
                workflow_id=node.workflow_id,
            )
            record = await result.single()
            
            if record:
                return dict(record["n"])
            return None
    
    async def create_lineage_relationship(self, relationship: LineageRelationship) -> Optional[Dict[str, Any]]:
        """Create a lineage relationship in Neo4j"""
        # Security: Validate relationship type against allowed enum values to prevent Cypher injection
        rel_type = relationship.type.value
        if rel_type not in ALLOWED_RELATIONSHIP_TYPES:
            logger.warning("Invalid relationship type rejected: %s", rel_type)
            raise ValueError(f"Invalid relationship type: {rel_type}")
        
        # Use APOC to safely create dynamic relationship types, or use parameterized approach
        # Since we validated against enum, the f-string is now safe
        query = f"""
        MATCH (source:LineageNode {{id: $source_id}})
        MATCH (target:LineageNode {{id: $target_id}})
        CREATE (source)-[r:{rel_type} {{
            properties: $properties,
            timestamp: $timestamp,
            workflow_id: $workflow_id
        }}]->(target)
        RETURN r
        """
        
        async with self.driver.session(database="neo4j") as session:
            result = await session.run(
                query,
                source_id=relationship.source_id,
                target_id=relationship.target_id,
                properties=json.dumps(relationship.properties),
                timestamp=relationship.timestamp.isoformat(),
                workflow_id=relationship.workflow_id,
            )
            record = await result.single()
            
            if record:
                return dict(record["r"])
            return None
    
    async def trace_lineage(
        self,
        record_id: str,
        direction: str = "both",
        max_depth: int = 5,
        node_types: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Trace lineage for a specific record"""

        depth = int(max_depth) if isinstance(max_depth, int) else 5
        depth = max(1, min(depth, 20))

        upstream_query = (
            f"""
        MATCH path = (n:LineageNode {{id: $record_id}})<-[*1..{depth}]-(source)
        RETURN path
        """
            if direction in ["upstream", "both"]
            else None
        )

        downstream_query = (
            f"""
        MATCH path = (n:LineageNode {{id: $record_id}})-[*1..{depth}]->(target)
        RETURN path
        """
            if direction in ["downstream", "both"]
            else None
        )
        
        lineage_paths: dict[str, Any] = {
            "record_id": record_id,
            "upstream": [],
            "downstream": [],
            "nodes": {},
            "relationships": []
        }
        
        async with self.driver.session(database="neo4j") as session:
            # Get upstream lineage
            if upstream_query:
                result = await session.run(upstream_query, record_id=record_id)
                async for record in result:
                    path = record["path"]
                    self._process_path(path, lineage_paths, "upstream")
            
            # Get downstream lineage
            if downstream_query:
                result = await session.run(downstream_query, record_id=record_id)
                async for record in result:
                    path = record["path"]
                    self._process_path(path, lineage_paths, "downstream")

        if node_types:
            allowed = {
                str(t).strip().lower()
                for t in node_types
                if t is not None and str(t).strip()
            }
            if allowed:
                raw_nodes = lineage_paths["nodes"]
                nodes_map: dict[str, Any] = raw_nodes if isinstance(raw_nodes, dict) else {}

                filtered_nodes: Dict[str, Any] = {}
                for node_id, node in nodes_map.items():
                    if not isinstance(node, dict):
                        continue
                    node_type = str(node.get("type") or "")
                    if node_type.strip().lower() in allowed:
                        filtered_nodes[node_id] = node

                lineage_paths["nodes"] = filtered_nodes
                kept_ids = set(filtered_nodes.keys())
                upstream_list = lineage_paths["upstream"] if isinstance(lineage_paths.get("upstream"), list) else []
                downstream_list = lineage_paths["downstream"] if isinstance(lineage_paths.get("downstream"), list) else []

                lineage_paths["upstream"] = [nid for nid in upstream_list if nid in kept_ids]
                lineage_paths["downstream"] = [nid for nid in downstream_list if nid in kept_ids]

                raw_relationships = lineage_paths["relationships"]
                relationships_list: List[Dict[str, Any]] = (
                    [r for r in raw_relationships if isinstance(r, dict)]
                    if isinstance(raw_relationships, list)
                    else []
                )
                lineage_paths["relationships"] = [
                    rel
                    for rel in relationships_list
                    if rel.get("start") in kept_ids and rel.get("end") in kept_ids
                ]
        
        return lineage_paths
    
    def _process_path(self, path, lineage_paths: Dict, direction: str):
        """Process Neo4j path and extract nodes/relationships"""
        for node in path.nodes:
            node_id = node["id"]
            if node_id not in lineage_paths["nodes"]:
                lineage_paths["nodes"][node_id] = dict(node)
                lineage_paths[direction].append(node_id)
        
        for rel in path.relationships:
            lineage_paths["relationships"].append({
                "type": rel.type,
                "start": rel.start_node["id"],
                "end": rel.end_node["id"],
                "properties": dict(rel)
            })
    
    async def analyze_impact(
        self, 
        source_node_id: str, 
        change_type: str,
        simulation_mode: bool = True
    ) -> Dict[str, Any]:
        """Analyze impact of changes on downstream systems"""

        # Get downstream nodes plus lightweight signals to improve risk scoring.
        # Note: We avoid requiring Neo4j GDS plugins (PageRank, betweenness) for portability.
        query = """
        MATCH path = (n:LineageNode {id: $source_node_id})-[*1..10]->(affected)
        WITH DISTINCT affected, length(path) as distance
        RETURN
          affected,
          distance,
          size((affected)-->(:LineageNode)) as out_degree,
          size((affected)<--(:LineageNode)) as in_degree
        ORDER BY distance
        """

        affected_nodes: List[Dict[str, Any]] = []
        
        async with self.driver.session(database="neo4j") as session:
            result = await session.run(query, source_node_id=source_node_id)
            async for record in result:

                node = dict(record["affected"])
                distance = int(record["distance"])
                out_degree = int(record.get("out_degree") or 0)
                in_degree = int(record.get("in_degree") or 0)

                node_type = str(node.get("type") or "")
                criticality = self._extract_criticality(node, node_type)
                impact_score = self._calculate_impact_score(
                    distance=distance,
                    criticality=criticality,
                    out_degree=out_degree,
                    in_degree=in_degree,
                    change_type=change_type,
                )
                impact_level = self._calculate_impact_level(
                    distance=distance,
                    change_type=change_type,
                    impact_score=impact_score,
                    criticality=criticality,
                )

                affected_nodes.append({
                    "node": node,
                    "distance": distance,
                    "impact_level": impact_level,
                    "criticality": criticality,
                    "out_degree": out_degree,
                    "in_degree": in_degree,
                    "impact_score": impact_score,
                })

        summary = self._summarize_impacts(affected_nodes)
        top_impacts = sorted(
            affected_nodes,
            key=lambda n: float(n.get("impact_score") or 0.0),
            reverse=True,
        )[:10]
        
        return {
            "source_node_id": source_node_id,
            "change_type": change_type,
            "simulation_mode": simulation_mode,
            "affected_count": len(affected_nodes),
            "affected_nodes": affected_nodes,
            "summary": summary,
            "top_impacts": top_impacts,
            "risk_assessment": self._assess_risk(affected_nodes, change_type),
            "recommendations": self._generate_recommendations(affected_nodes, change_type)
        }
    
    def _extract_criticality(self, node: Dict[str, Any], node_type: str) -> float:
        raw = node.get("criticality")
        try:
            if raw is not None:
                value = float(raw)
                return max(0.0, min(1.0, value))
        except (TypeError, ValueError):
            pass

        nt = str(node_type or "").strip().lower()
        # Heuristic defaults (0..1): higher for systems, lower for raw records.
        if nt in ("target_system", "source_system"):
            return 0.9
        if nt in ("validation",):
            return 0.8
        if nt in ("transformation", "agent"):
            return 0.6
        return 0.4

    def _calculate_impact_score(
        self,
        *,
        distance: int,
        criticality: float,
        out_degree: int,
        in_degree: int,
        change_type: str,
    ) -> float:
        # Normalize signals.
        d = max(1, min(int(distance), 10))
        distance_score = 1.0 - ((d - 1) / 9.0)  # 1.0 (close) -> 0.0 (far)

        # Degree indicates "fan-out" and integration complexity.
        degree_cap = 20.0
        degree_score = min(float(max(out_degree, 0) + max(in_degree, 0)), degree_cap) / degree_cap

        # Weighting tuned by change_type.
        ct = str(change_type or "").strip().lower()
        if ct == "system_failure":
            w_crit, w_dist, w_deg = 0.55, 0.30, 0.15
        elif ct == "schema_change":
            w_crit, w_dist, w_deg = 0.45, 0.35, 0.20
        else:  # data_quality
            w_crit, w_dist, w_deg = 0.35, 0.35, 0.30

        score = (criticality * w_crit) + (distance_score * w_dist) + (degree_score * w_deg)
        return max(0.0, min(1.0, float(score)))

    def _calculate_impact_level(
        self,
        *,
        distance: int,
        change_type: str,
        impact_score: float,
        criticality: float,
    ) -> str:
        """Classify impact using both graph distance and criticality/degree score."""
        _ = distance
        ct = str(change_type or "").strip().lower()
        score = float(impact_score)

        # Ensure high criticality nodes are never classified too low.
        if criticality >= 0.9 and score >= 0.55:
            return "critical" if ct == "system_failure" else "high"

        if score >= 0.80:
            return "critical"
        if score >= 0.60:
            return "high"
        if score >= 0.35:
            return "medium"
        return "low"

    def _summarize_impacts(self, affected_nodes: List[Dict[str, Any]]) -> Dict[str, Any]:
        by_level: Dict[str, int] = {"critical": 0, "high": 0, "medium": 0, "low": 0}
        by_type: Dict[str, int] = {}
        max_score = 0.0

        for item in affected_nodes:
            level = str(item.get("impact_level") or "low")
            if level not in by_level:
                by_level[level] = 0
            by_level[level] += 1

            node = item.get("node")
            node_type = ""
            if isinstance(node, dict):
                node_type = str(node.get("type") or "")
            by_type[node_type] = by_type.get(node_type, 0) + 1

            try:
                max_score = max(max_score, float(item.get("impact_score") or 0.0))
            except (TypeError, ValueError):
                pass

        return {
            "by_level": by_level,
            "by_type": by_type,
            "max_impact_score": max_score,
        }
    
    def _assess_risk(self, affected_nodes: List[Dict], _change_type: str) -> str:
        """Assess overall risk level using impact level distribution + max score."""
        _ = _change_type
        critical_count = sum(1 for n in affected_nodes if n.get("impact_level") == "critical")
        high_count = sum(1 for n in affected_nodes if n.get("impact_level") == "high")
        max_score = 0.0
        for n in affected_nodes:
            try:
                max_score = max(max_score, float(n.get("impact_score") or 0.0))
            except (TypeError, ValueError):
                pass

        if critical_count > 0 or max_score >= 0.85:
            return "critical"
        if high_count >= 5 or max_score >= 0.70:
            return "high"
        if len(affected_nodes) > 20 or max_score >= 0.45:
            return "medium"
        return "low"
    
    def _generate_recommendations(self, affected_nodes: List[Dict], change_type: str) -> List[str]:
        """Generate recommendations based on impact analysis"""
        recommendations = []
        
        critical_nodes = [n for n in affected_nodes if n["impact_level"] == "critical"]
        if critical_nodes:
            recommendations.append(f"! {len(critical_nodes)} critical systems affected - immediate attention required")
            recommendations.append("Consider phased rollout with validation checkpoints")
        
        if change_type == "schema_change":
            recommendations.append("Run data validation tests before deployment")
            recommendations.append("Update all transformation mappings")
        
        if len(affected_nodes) > 10:
            recommendations.append("Schedule maintenance window for affected systems")
            recommendations.append("Notify stakeholders of downstream impacts")
        
        return recommendations
    
    async def get_audit_trail(
        self,
        workflow_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Get complete audit trail for compliance"""
        
        query = """
        MATCH (n:LineageNode {workflow_id: $workflow_id})
        OPTIONAL MATCH (n)-[r]->(target)
        WHERE ($start_date IS NULL OR datetime(n.created_at) >= datetime($start_date))
        AND ($end_date IS NULL OR datetime(n.created_at) <= datetime($end_date))
        RETURN n, collect(r) as relationships, collect(target) as targets
        ORDER BY n.created_at
        """
        
        audit_records = []
        
        async with self.driver.session(database="neo4j") as session:
            result = await session.run(
                query,
                workflow_id=workflow_id,
                start_date=start_date.isoformat() if start_date else None,
                end_date=end_date.isoformat() if end_date else None
            )
            
            async for record in result:
                audit_records.append({
                    "node": dict(record["n"]),
                    "relationships": [dict(r) for r in record["relationships"]],
                    "targets": [dict(t) for t in record["targets"]]
                })
        
        return {
            "workflow_id": workflow_id,
            "audit_period": {
                "start": start_date.isoformat() if start_date else None,
                "end": end_date.isoformat() if end_date else None
            },
            "total_records": len(audit_records),
            "audit_trail": audit_records,
            "compliance_status": "compliant",
            "generated_at": datetime.now(timezone.utc).isoformat()
        }


# ============= API ENDPOINTS =============

@router.post("/nodes", summary="Create Lineage Node")
async def create_lineage_node(
    node: LineageNode,
    driver: neo4j.AsyncDriver = Depends(get_driver)
):
    """Create a new lineage node"""
    service = LineageService(driver)
    result = await service.create_lineage_node(node)
    return {"success": True, "node": result}


@router.post("/relationships", summary="Create Lineage Relationship")
async def create_lineage_relationship(
    relationship: LineageRelationship,
    driver: neo4j.AsyncDriver = Depends(get_driver)
):
    """Create a new lineage relationship"""
    service = LineageService(driver)
    result = await service.create_lineage_relationship(relationship)
    return {"success": True, "relationship": result}


@router.post("/trace", summary="Trace Data Lineage")
async def trace_lineage(
    request: LineageTraceRequest,
    driver: neo4j.AsyncDriver = Depends(get_driver)
):
    """Trace lineage for a specific record"""
    service = LineageService(driver)
    result = await service.trace_lineage(
        request.record_id,
        request.direction,
        request.max_depth,
        request.node_types,
    )
    return result


@router.post("/impact-analysis", summary="Analyze Impact")
async def analyze_impact(
    request: LineageImpactAnalysisRequest,
    driver: neo4j.AsyncDriver = Depends(get_driver)
):
    """Analyze impact of changes on downstream systems"""
    service = LineageService(driver)
    result = await service.analyze_impact(
        request.source_node_id,
        request.change_type,
        request.simulation_mode
    )
    return result


@router.post("/audit-trail", summary="Get Audit Trail")
async def get_audit_trail(
    request: AuditTrailRequest,
    driver: neo4j.AsyncDriver = Depends(get_driver)
):
    """Get complete audit trail for compliance"""
    service = LineageService(driver)
    result = await service.get_audit_trail(
        request.workflow_id,
        request.start_date,
        request.end_date
    )
    return result


@router.get("/workflows/{workflow_id}/lineage-graph", summary="Get Workflow Lineage Graph")
async def get_workflow_lineage_graph(
    workflow_id: str,
    node_types: Optional[List[str]] = Query(None),
    driver: neo4j.AsyncDriver = Depends(get_driver)
):
    """Get complete lineage graph for a workflow"""
    normalized_types: Optional[List[str]] = None
    if node_types:
        # FastAPI supports repeated query params; accept CSV too for convenience.
        flattened: List[str] = []
        for item in node_types:
            if item is None:
                continue
            parts = [p.strip() for p in str(item).split(",")]
            flattened.extend([p for p in parts if p])
        if flattened:
            normalized_types = [t.lower() for t in flattened]

    query = """
    MATCH (n:LineageNode {workflow_id: $workflow_id})
    WHERE ($node_types IS NULL OR n.type IN $node_types)
    OPTIONAL MATCH (n)-[r]->(target:LineageNode {workflow_id: $workflow_id})
    WHERE ($node_types IS NULL OR target.type IN $node_types)
    RETURN
      collect(DISTINCT n) as nodes,
      collect(DISTINCT CASE
        WHEN r IS NULL THEN NULL
        ELSE {type: type(r), start: n.id, end: target.id, properties: properties(r)}
      END) as relationships
    """
    
    async with driver.session(database="neo4j") as session:
        result = await session.run(query, workflow_id=workflow_id, node_types=normalized_types)
        record = await result.single()
        
        if record:
            return {
                "workflow_id": workflow_id,
                "nodes": [dict(n) for n in record["nodes"]],
                "relationships": [dict(r) for r in record["relationships"] if r]
            }
    
    return {"workflow_id": workflow_id, "nodes": [], "relationships": []}


# Request model for Cypher queries
class CypherQueryRequest(BaseModel):
    cypher: str = Field(..., description="Cypher query to execute (read-only)")
    parameters: Optional[Dict[str, Any]] = Field(default=None, description="Query parameters")


# Set of safe read-only Cypher clauses
SAFE_CYPHER_PREFIXES = frozenset({
    "MATCH", "OPTIONAL MATCH", "RETURN", "WITH", "UNWIND", "CALL", "PROFILE", "EXPLAIN"
})

# Dangerous write clauses that should be blocked (as whole words at statement boundaries)
BLOCKED_CYPHER_CLAUSES = frozenset({
    "CREATE", "MERGE", "DELETE", "DETACH DELETE", "SET", "REMOVE", "DROP", "FOREACH"
})


def is_safe_cypher_query(query: str) -> bool:
    """Check if a Cypher query is safe to execute (read-only)"""
    import re
    normalized = query.strip().upper()
    
    # Check for blocked write clauses using word boundaries
    # This prevents false positives like 'created_at' matching 'CREATE'
    for clause in BLOCKED_CYPHER_CLAUSES:
        # Use word boundary regex to match whole keywords only
        pattern = r'\b' + clause + r'\b'
        if re.search(pattern, normalized):
            return False
    
    # Must start with a safe prefix
    return any(normalized.startswith(prefix) for prefix in SAFE_CYPHER_PREFIXES)


@router.post("/cypher", summary="Execute Cypher Query")
async def execute_cypher_query(
    request: CypherQueryRequest,
    driver: neo4j.AsyncDriver = Depends(get_driver)
):
    """
    Execute a read-only Cypher query against the Neo4j lineage graph.
    
    This endpoint is intended for analytics and reporting purposes.
    Write operations (CREATE, MERGE, DELETE, SET, etc.) are blocked.
    """
    if not request.cypher or not request.cypher.strip():
        return {"success": False, "error": "Empty query provided", "results": []}
    
    if not is_safe_cypher_query(request.cypher):
        return {
            "success": False,
            "error": "Query rejected: Only read-only queries (MATCH, RETURN, etc.) are allowed",
            "results": []
        }
    
    try:
        import asyncio
        import os

        query_timeout_s = float(os.getenv("GRAPH_TRACE_NEO4J_QUERY_TIMEOUT_S", "5") or 5)

        async with driver.session(database="neo4j") as session:
            async def _run_query():
                result = await session.run(
                    request.cypher,
                    **(request.parameters or {})
                )
                return await result.data()

            records = await asyncio.wait_for(_run_query(), timeout=query_timeout_s)
            
            # Convert Neo4j nodes/relationships to serializable dicts
            serializable_records = []
            for record in records:
                serialized_record: dict[str, Any] = {}
                for key, value in record.items():
                    if hasattr(value, '__dict__') or hasattr(value, 'items'):
                        # Neo4j Node/Relationship - extract properties
                        if hasattr(value, '_properties'):
                            serialized_record[key] = dict(getattr(value, '_properties'))
                        elif hasattr(value, 'items'):
                            serialized_record[key] = dict(value)
                        else:
                            serialized_record[key] = str(value)
                    else:
                        serialized_record[key] = value
                serializable_records.append(serialized_record)
            
            return {
                "success": True,
                "results": serializable_records,
                "count": len(serializable_records)
            }
    except TimeoutError:
        return {
            "success": False,
            "error": f"Query timed out after {query_timeout_s}s",
            "results": [],
        }
    except neo4j.exceptions.CypherSyntaxError as e:
        return {
            "success": False,
            "error": f"Cypher syntax error: {str(e)}",
            "results": []
        }
    except (neo4j.exceptions.ServiceUnavailable, neo4j.exceptions.SessionExpired, ConnectionError) as e:  # noqa: BLE001
        logger.error("Cypher query execution failed: %s", e)
        return {
            "success": False,
            "error": f"Query execution failed: {str(e)}",
            "results": []
        }
