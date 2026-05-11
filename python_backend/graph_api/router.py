import logging
import asyncio
from fastapi import APIRouter, Depends, HTTPException
import neo4j
from typing import List, Dict, Set, Optional

from .models import (
    GraphDataResponse, QueryRequest, QueryResponse, NodeModel, EdgeModel,
    RawRecordModel, QuerySummaryModel, RawRecordItem
)
from .helpers import (
    _add_node_from_neo4j_node, _process_neo4j_relationship,
    _add_node_from_info_dict, _process_relationship_from_info_dict
)
from .dependencies import get_driver
from core.config import NEO4J_DATABASE
from .neo4j_json import sanitize_properties

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["Graph Operations"])

DEFAULT_GRAPH_QUERY = "MATCH (n) OPTIONAL MATCH (n)-[r]-(m) RETURN n, r, m"
GRAPH_QUERY_TIMEOUT_SECONDS = 8
CUSTOM_QUERY_TIMEOUT_SECONDS = 15


def _demo_graph_response() -> GraphDataResponse:
    demo_nodes = [
        NodeModel(
            id="demo_db_1",
            label="Teamcenter DB",
            group="Database",
            properties={"name": "Teamcenter", "type": "Database"},
            title="ID: demo_db_1\nLabels: Database\nProperties:\n  name: Teamcenter\n  type: Database",
        ),
        NodeModel(
            id="demo_csv_1",
            label="tc_extract.csv",
            group="CSV",
            properties={"name": "tc_extract.csv", "type": "CSV"},
            title="ID: demo_csv_1\nLabels: CSV\nProperties:\n  name: tc_extract.csv\n  type: CSV",
        ),
        NodeModel(
            id="demo_etl_1",
            label="Transform",
            group="Processor",
            properties={"name": "Transform", "type": "ETL"},
            title="ID: demo_etl_1\nLabels: Processor\nProperties:\n  name: Transform\n  type: ETL",
        ),
        NodeModel(
            id="demo_api_1",
            label="Migration API",
            group="API",
            properties={"name": "Migration API", "type": "API"},
            title="ID: demo_api_1\nLabels: API\nProperties:\n  name: Migration API\n  type: API",
        ),
    ]

    demo_edges = [
        EdgeModel(
            id="demo_edge_1",
            **{"from": "demo_db_1", "to": "demo_csv_1"},
            label="EXTRACTS",
            properties={"weight": 1},
            title="ID: demo_edge_1\nType: EXTRACTS\nSource: Teamcenter DB (demo_db...)\nTarget: tc_extract.csv (demo_cs...)",
        ),
        EdgeModel(
            id="demo_edge_2",
            **{"from": "demo_csv_1", "to": "demo_etl_1"},
            label="FEEDS",
            properties={"weight": 1},
            title="ID: demo_edge_2\nType: FEEDS\nSource: tc_extract.csv (demo_cs...)\nTarget: Transform (demo_et...)",
        ),
        EdgeModel(
            id="demo_edge_3",
            **{"from": "demo_etl_1", "to": "demo_api_1"},
            label="PUBLISHES",
            properties={"weight": 1},
            title="ID: demo_edge_3\nType: PUBLISHES\nSource: Transform (demo_et...)\nTarget: Migration API (demo_ap...)",
        ),
    ]

    return GraphDataResponse(nodes=demo_nodes, edges=demo_edges, rawRecords=[])


@router.get(
    "/graph",
    response_model=GraphDataResponse,
    summary="Get Default Graph Data",
    description="Fetches a default limited set of nodes and relationships from the Neo4j database.",
)
async def get_graph_data_endpoint(
    driver_instance: neo4j.AsyncDriver = Depends(get_driver)
):
    nodes_map: Dict[str, NodeModel] = {}
    edges_list: List[EdgeModel] = []
    processed_rel_ids: Set[str] = set()
    raw_records_payload: List[RawRecordModel] = []

    try:
        try:
            results = await asyncio.wait_for(
                driver_instance.execute_query(
                    DEFAULT_GRAPH_QUERY, database_=NEO4J_DATABASE, routing_="r"
                ),
                timeout=GRAPH_QUERY_TIMEOUT_SECONDS,
            )
        except asyncio.TimeoutError:
            logger.warning(
                "Timed out executing default Neo4j graph query; returning demo graph.",
                extra={"timeout_seconds": GRAPH_QUERY_TIMEOUT_SECONDS},
            )
            return _demo_graph_response()

        for record in results.records:
            n_node = record.get("n")
            r_rel = record.get("r")
            m_node = record.get("m")

            raw_record_data = {}
            if n_node:
                _add_node_from_neo4j_node(n_node, nodes_map)
                raw_record_data["n"] = RawRecordItem(
                    elementId=n_node.element_id,
                    labels=list(n_node.labels),
                    properties=sanitize_properties(dict(n_node)),
                )
            if m_node:
                _add_node_from_neo4j_node(m_node, nodes_map)
                raw_record_data["m"] = RawRecordItem(
                    elementId=m_node.element_id,
                    labels=list(m_node.labels),
                    properties=sanitize_properties(dict(m_node)),
                )
            if r_rel:
                _process_neo4j_relationship(r_rel, nodes_map, edges_list, processed_rel_ids)
                raw_record_data["r"] = RawRecordItem(
                    elementId=r_rel.element_id, 
                    type=r_rel.type,
                    startNodeElementId=r_rel.start_node.element_id,
                    endNodeElementId=r_rel.end_node.element_id,
                    properties=sanitize_properties(dict(r_rel))
                )
            
            if raw_record_data:
                raw_records_payload.append(RawRecordModel(**raw_record_data))

        return GraphDataResponse(
            nodes=list(nodes_map.values()),
            edges=edges_list, 
            rawRecords=raw_records_payload
        )
    except neo4j.exceptions.Neo4jError as db_err:
        logger.error("Neo4j database error in /api/graph: %s", db_err, exc_info=True)
        # Keep UI usable even if Neo4j is down.
        return _demo_graph_response()
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Unexpected error in /api/graph: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}") from e

@router.post(
    "/query",
    response_model=QueryResponse,
    summary="Execute Custom Cypher Query",
    description="Executes a user-provided Cypher query against the Neo4j database. "
                "**Warning:** Use with caution, as this endpoint can execute arbitrary queries.",
)
async def execute_custom_query_endpoint(
    payload: QueryRequest,
    driver_instance: neo4j.AsyncDriver = Depends(get_driver)
):
    nodes_map: Dict[str, NodeModel] = {}
    edges_list: List[EdgeModel] = []
    processed_rel_ids: Set[str] = set()
    raw_records_payload: List[RawRecordModel] = []
    summary_info_payload: Optional[QuerySummaryModel] = None

    try:
        try:
            results = await asyncio.wait_for(
                driver_instance.execute_query(
                    payload.query,
                    payload.params or {},
                    database_=NEO4J_DATABASE,
                    routing_="r",
                ),
                timeout=CUSTOM_QUERY_TIMEOUT_SECONDS,
            )
        except asyncio.TimeoutError as exc:
            raise HTTPException(
                status_code=504,
                detail=f"Query timed out after {CUSTOM_QUERY_TIMEOUT_SECONDS}s",
            ) from exc

        for record in results.records:
            n_info = record.get("n_info")
            r_info = record.get("r_info")
            m_info = record.get("m_info")
            n_node = record.get("n")
            r_rel = record.get("r")
            m_node = record.get("m")

            current_raw_record_data = {}

            if n_info:
                _add_node_from_info_dict(n_info, nodes_map)
                current_raw_record_data["n"] = RawRecordItem(**n_info)
            elif n_node:
                _add_node_from_neo4j_node(n_node, nodes_map)
                current_raw_record_data["n"] = RawRecordItem(
                    elementId=n_node.element_id,
                    labels=list(n_node.labels),
                    properties=sanitize_properties(dict(n_node)),
                )

            if m_info:
                _add_node_from_info_dict(m_info, nodes_map)
                current_raw_record_data["m"] = RawRecordItem(**m_info)
            elif m_node:
                _add_node_from_neo4j_node(m_node, nodes_map)
                current_raw_record_data["m"] = RawRecordItem(
                    elementId=m_node.element_id,
                    labels=list(m_node.labels),
                    properties=sanitize_properties(dict(m_node)),
                )
            
            if r_info:
                _process_relationship_from_info_dict(r_info, nodes_map, edges_list, processed_rel_ids)
                current_raw_record_data["r"] = RawRecordItem(**r_info)
            elif r_rel:
                _process_neo4j_relationship(r_rel, nodes_map, edges_list, processed_rel_ids)
                current_raw_record_data["r"] = RawRecordItem(
                    elementId=r_rel.element_id, type=r_rel.type,
                    startNodeElementId=r_rel.start_node.element_id, endNodeElementId=r_rel.end_node.element_id,
                    properties=sanitize_properties(dict(r_rel))
                )
            
            if current_raw_record_data:
                raw_records_payload.append(RawRecordModel(**current_raw_record_data))
            else:
                raw_records_payload.append(RawRecordModel(**record.data()))

        if results.summary and results.summary.counters:
            counters = results.summary.counters
            summary_info_payload = QuerySummaryModel.model_validate(
                {
                    "nodes-created": getattr(counters, "nodes_created", None),
                    "nodes-deleted": getattr(counters, "nodes_deleted", None),
                    "relationships-created": getattr(counters, "relationships_created", None),
                    "relationships-deleted": getattr(counters, "relationships_deleted", None),
                    "properties-set": getattr(counters, "properties_set", None),
                    "labels-added": getattr(counters, "labels_added", None),
                    "labels-removed": getattr(counters, "labels_removed", None),
                    "indexes-added": getattr(counters, "indexes_added", None),
                    "indexes-removed": getattr(counters, "indexes_removed", None),
                    "constraints-added": getattr(counters, "constraints_added", None),
                    "constraints-removed": getattr(counters, "constraints_removed", None),
                    "system-updates": getattr(counters, "system_updates", None),
                }
            )

        return QueryResponse(
            nodes=list(nodes_map.values()), 
            edges=edges_list, 
            rawRecords=raw_records_payload,
            summaryInfo=summary_info_payload
        )
    except neo4j.exceptions.CypherSyntaxError as syntax_err:
        logger.warning("Cypher syntax error in /api/query: %s", syntax_err, exc_info=True)
        raise HTTPException(status_code=400, detail=f"Cypher query syntax error: {syntax_err}") from syntax_err
    except neo4j.exceptions.Neo4jError as db_err:
        logger.error("Neo4j database error in /api/query: %s", db_err, exc_info=True)
        raise HTTPException(status_code=503, detail=f"Database error: {str(db_err)}") from db_err
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Unexpected error in /api/query: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}") from e


from pydantic import BaseModel as PydanticBaseModel  # noqa: E402


class ValidateConnectionRequest(PydanticBaseModel):
    """Request model for connection validation"""
    uri: str
    user: str
    password: str


class ValidateConnectionResponse(PydanticBaseModel):
    """Response model for connection validation"""
    success: bool
    message: str
    database: Optional[str] = None
    version: Optional[str] = None


@router.post(
    "/graph/validate-connection",
    response_model=ValidateConnectionResponse,
    summary="Validate Neo4j Connection",
    description="Validates Neo4j connection credentials before establishing a session.",
)
async def validate_neo4j_connection(request: ValidateConnectionRequest):
    """Validate Neo4j connection with provided credentials"""
    try:
        # Create a temporary driver to test the connection
        test_driver = neo4j.AsyncGraphDatabase.driver(
            request.uri,
            auth=(request.user, request.password)
        )
        
        try:
            # Test the connection by running a simple query
            async with test_driver.session(database="neo4j") as session:
                result = await session.run("RETURN 1 as test")
                await result.consume()
            
            # Get server info
            server_info = await test_driver.get_server_info()
            version = getattr(server_info, 'agent', 'unknown')
            
            return ValidateConnectionResponse(
                success=True,
                message="Connection validated successfully",
                database="neo4j",
                version=version
            )
        finally:
            await test_driver.close()
            
    except neo4j.exceptions.AuthError as auth_err:
        logger.warning("Neo4j authentication failed: %s", auth_err)
        raise HTTPException(
            status_code=401,
            detail="Authentication failed: Invalid username or password"
        ) from auth_err
    except neo4j.exceptions.ServiceUnavailable as svc_err:
        logger.warning("Neo4j service unavailable: %s", svc_err)
        raise HTTPException(
            status_code=503,
            detail=f"Neo4j service unavailable: {str(svc_err)}"
        ) from svc_err
    except Exception as e:
        logger.error("Connection validation failed: %s", e)
        raise HTTPException(
            status_code=500,
            detail=f"Connection validation failed: {str(e)}"
        ) from e