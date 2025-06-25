import logging
import asyncio
from anyio import to_thread
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
from ..core.config import NEO4J_DATABASE

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["Graph Operations"])

DEFAULT_GRAPH_QUERY = "MATCH (n) OPTIONAL MATCH (n)-[r]-(m) RETURN n, r, m"

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
        results = await driver_instance.execute_query(
            DEFAULT_GRAPH_QUERY, database_=NEO4J_DATABASE, routing_="r"
        )

        for record in results.records:
            n_node = record.get("n")
            r_rel = record.get("r")
            m_node = record.get("m")

            raw_record_data = {}
            if n_node:
                _add_node_from_neo4j_node(n_node, nodes_map)
                raw_record_data["n"] = RawRecordItem(elementId=n_node.element_id, labels=list(n_node.labels), properties=dict(n_node))
            if m_node:
                _add_node_from_neo4j_node(m_node, nodes_map)
                raw_record_data["m"] = RawRecordItem(elementId=m_node.element_id, labels=list(m_node.labels), properties=dict(m_node))
            if r_rel:
                _process_neo4j_relationship(r_rel, nodes_map, edges_list, processed_rel_ids)
                raw_record_data["r"] = RawRecordItem(
                    elementId=r_rel.element_id, 
                    type=r_rel.type,
                    startNodeElementId=r_rel.start_node.element_id,
                    endNodeElementId=r_rel.end_node.element_id,
                    properties=dict(r_rel)
                )
            
            if raw_record_data:
                raw_records_payload.append(RawRecordModel(**raw_record_data))

        return GraphDataResponse(
            nodes=list(nodes_map.values()),
            edges=edges_list, 
            rawRecords=raw_records_payload
        )
    except neo4j.exceptions.Neo4jError as db_err:
        logger.error(f"Neo4j database error in /api/graph: {db_err}", exc_info=True)
        raise HTTPException(status_code=503, detail=f"Database error: {str(db_err.message)}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in /api/graph: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")

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
        results = await driver_instance.execute_query(
            payload.query, payload.params or {}, database_=NEO4J_DATABASE, routing_="r"
        )

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
                current_raw_record_data["n"] = RawRecordItem(elementId=n_node.element_id, labels=list(n_node.labels), properties=dict(n_node))

            if m_info:
                _add_node_from_info_dict(m_info, nodes_map)
                current_raw_record_data["m"] = RawRecordItem(**m_info)
            elif m_node:
                _add_node_from_neo4j_node(m_node, nodes_map)
                current_raw_record_data["m"] = RawRecordItem(elementId=m_node.element_id, labels=list(m_node.labels), properties=dict(m_node))
            
            if r_info:
                _process_relationship_from_info_dict(r_info, nodes_map, edges_list, processed_rel_ids)
                current_raw_record_data["r"] = RawRecordItem(**r_info)
            elif r_rel:
                _process_neo4j_relationship(r_rel, nodes_map, edges_list, processed_rel_ids)
                current_raw_record_data["r"] = RawRecordItem(
                    elementId=r_rel.element_id, type=r_rel.type,
                    startNodeElementId=r_rel.start_node.element_id, endNodeElementId=r_rel.end_node.element_id,
                    properties=dict(r_rel)
                )
            
            if current_raw_record_data:
                raw_records_payload.append(RawRecordModel(**current_raw_record_data))
            else:
                raw_records_payload.append(RawRecordModel(**record.data()))

        if results.summary and results.summary.counters:
            summary_dict = results.summary.counters.summary()
            mapped_summary_dict = {key.replace('-', '_'): value for key, value in summary_dict.items()}
            summary_info_payload = QuerySummaryModel(**mapped_summary_dict)

        return QueryResponse(
            nodes=list(nodes_map.values()), 
            edges=edges_list, 
            rawRecords=raw_records_payload,
            summaryInfo=summary_info_payload
        )
    except neo4j.exceptions.CypherSyntaxError as syntax_err:
        logger.warning(f"Cypher syntax error in /api/query: {syntax_err.message}", exc_info=True)
        raise HTTPException(status_code=400, detail=f"Cypher query syntax error: {syntax_err.message}")
    except neo4j.exceptions.Neo4jError as db_err:
        logger.error(f"Neo4j database error in /api/query: {db_err}", exc_info=True)
        raise HTTPException(status_code=503, detail=f"Database error: {str(db_err.message)}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in /api/query: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")