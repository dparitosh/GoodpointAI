import os
import logging # Import the logging module
from fastapi import FastAPI, HTTPException, Body, Depends
from pydantic import BaseModel, Field
import neo4j.exceptions
from dotenv import load_dotenv
from contextlib import asynccontextmanager
import asyncio # For asyncio.iscoroutinefunction
from anyio import to_thread # For running sync code in async
from typing import List, Dict, Any, Optional, Set, Union, TYPE_CHECKING

# --- Setup Logging ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Environment and Configuration ---
load_dotenv()

NEO4J_URI = os.getenv("NEO4J_URI", "neo4j+s://2cccd05b.databases.neo4j.io")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE", "neo4j")

if not NEO4J_PASSWORD:
    logger.error("NEO4J_PASSWORD environment variable is not set. Cannot connect to Neo4j.")
    raise ValueError("NEO4J_PASSWORD environment variable is not set. Cannot connect to Neo4j.")

if TYPE_CHECKING:
    driver: Optional[neo4j.AsyncDriver] = None
else:
    driver: Optional[neo4j.Driver] = None # Keep general neo4j.Driver for runtime if needed, but logic assumes AsyncDriver

# --- Pydantic Models for API ---

class NodeModel(BaseModel):
    id: str = Field(..., description="The unique element ID of the node.")
    label: str = Field(..., description="A display label for the node, often derived from a 'name' property or its primary Neo4j label.")
    group: str = Field(..., description="A group identifier for the node, often its primary Neo4j label, used for visualization styling.")
    properties: Dict[str, Any] = Field(..., description="A dictionary of the node's properties.")
    title: str = Field(..., description="A string used for tooltips in visualizations, typically a formatted summary of node details.")

class EdgeModel(BaseModel):
    id: str = Field(..., description="The unique element ID of the relationship.")
    from_node: str = Field(..., alias="from", description="The element ID of the source node.") # 'from' is a reserved keyword, use alias
    to_node: str = Field(..., alias="to", description="The element ID of the target node.")
    label: str = Field(..., description="The type of the relationship.")
    properties: Dict[str, Any] = Field(..., description="A dictionary of the relationship's properties.")
    title: str = Field(..., description="A string used for tooltips in visualizations, typically a formatted summary of relationship details.")

    class Config:
        populate_by_name = True

class RawRecordItem(BaseModel):
    elementId: str
    labels: Optional[List[str]] = None # For nodes
    type: Optional[str] = None # For relationships
    startNodeElementId: Optional[str] = None # For relationships
    endNodeElementId: Optional[str] = None # For relationships
    properties: Dict[str, Any]

class RawRecordModel(BaseModel):
    n: Optional[RawRecordItem] = None
    r: Optional[RawRecordItem] = None
    m: Optional[RawRecordItem] = None
    # Allow other arbitrary keys that a custom query might return
    class Config:
        extra = "allow"


class GraphDataResponse(BaseModel):
    nodes: List[NodeModel]
    edges: List[EdgeModel]
    rawRecords: List[RawRecordModel]

class QueryRequest(BaseModel):
    query: str = Field(..., description="The Cypher query to execute.")
    params: Optional[Dict[str, Any]] = Field(None, description="Parameters for the Cypher query.")

class QuerySummaryModel(BaseModel):
    # Define based on what `results.summary.counters.summary()` actually returns
    # Example:
    nodes_created: Optional[int] = Field(None, alias="nodes-created")
    nodes_deleted: Optional[int] = Field(None, alias="nodes-deleted")
    relationships_created: Optional[int] = Field(None, alias="relationships-created")
    relationships_deleted: Optional[int] = Field(None, alias="relationships-deleted")
    properties_set: Optional[int] = Field(None, alias="properties-set")
    labels_added: Optional[int] = Field(None, alias="labels-added")
    labels_removed: Optional[int] = Field(None, alias="labels-removed")
    indexes_added: Optional[int] = Field(None, alias="indexes-added")
    indexes_removed: Optional[int] = Field(None, alias="indexes-removed")
    constraints_added: Optional[int] = Field(None, alias="constraints-added")
    constraints_removed: Optional[int] = Field(None, alias="constraints-removed")
    system_updates: Optional[int] = Field(None, alias="system-updates")

    class Config:
        populate_by_name = True # Allows using alias for field names

class QueryResponse(GraphDataResponse):
    summaryInfo: Optional[QuerySummaryModel] = Field(None, description="Summary information about the query execution.")


# --- Lifespan Management for Neo4j Driver ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    global driver
    temp_driver: Optional[neo4j.AsyncDriver] = None # Expect an AsyncDriver
    try:
        logger.info(f"Attempting to create Neo4j driver for {NEO4J_URI} as user {NEO4J_USER}...")
        # Explicitly use AsyncGraphDatabase to ensure an async driver
        temp_driver = neo4j.AsyncGraphDatabase.driver(NEO4J_URI, auth=neo4j.basic_auth(NEO4J_USER, NEO4J_PASSWORD))
        logger.info("Neo4j driver object created. Attempting to verify connectivity...")
        
        # The Neo4j Python driver's verify_connectivity() is synchronous.
        await to_thread.run_sync(temp_driver.verify_connectivity) # Ensures non-blocking startup
        
        
        logger.info("Successfully connected to Neo4j and verified connectivity.")
        driver = temp_driver
    except neo4j.exceptions.AuthError as auth_err:
        logger.error(f"Neo4j Authentication Error: {auth_err}. Please check your NEO4J_USER and NEO4J_PASSWORD.", exc_info=True)
        driver = None
    except neo4j.exceptions.ServiceUnavailable as su_err:
        logger.error(f"Neo4j Service Unavailable: {su_err}. Please check NEO4J_URI and network connectivity.", exc_info=True)
        driver = None
    except TypeError as te:
        logger.error(f"TypeError during Neo4j connection/verification: {te}", exc_info=True)
        logger.error("This might indicate an issue with the driver call or an unexpected non-awaitable return if an await was used incorrectly elsewhere.")
        driver = None    
    except Exception as e:
        logger.error(f"An unexpected error occurred during Neo4j driver initialization: {type(e).__name__} - {e}", exc_info=True)
        driver = None
    
    yield

    if driver:
        logger.info("Closing Neo4j driver...")
        await driver.close() # driver.close() is async
        logger.info("Neo4j driver closed.")
    elif temp_driver and driver is None:
        logger.info("Closing temporary Neo4j driver instance after setup failure...")
        try:
            await temp_driver.close()
            logger.info("Temporary Neo4j driver instance closed.")
        except Exception as e_close:
            logger.error(f"Error closing temporary Neo4j driver instance: {e_close}", exc_info=True)

app = FastAPI(
    title="GraphTrace API",
    description="API for interacting with a Neo4j graph database and visualizing trace data.",
    version="0.1.0",
    lifespan=lifespan
)

def get_driver_sync_dependency() -> neo4j.AsyncDriver: # Ensure this returns AsyncDriver
    """Dependency to get the initialized Neo4j driver."""
    if not driver:
        raise HTTPException(status_code=503, detail="Neo4j driver not initialized or connection failed.")
    return driver

# --- Helper Functions for Data Transformation ---

def _add_node_from_neo4j_node(node_obj: neo4j.graph.Node, nodes_map: Dict[str, NodeModel]):
    if node_obj and node_obj.element_id and not nodes_map.get(node_obj.element_id):
        node_id = node_obj.element_id
        labels = list(node_obj.labels)
        properties = dict(node_obj) # Corrected: Node object itself is a mapping
        
        default_label_text = labels[0] if labels else (properties.get("name") or f"Node ({node_id[:6]}...)")
        group_text = labels[0] if labels else properties.get("group", "Unknown")

        tooltip_parts = [f"ID: {node_id}"]
        if labels:
            tooltip_parts.append(f"Labels: {', '.join(labels)}")
        if properties:
            tooltip_parts.append("Properties:")
            for key, value in properties.items():
                tooltip_parts.append(f"  {key}: {value}")

        nodes_map[node_id] = NodeModel(
            id=node_id,
            label=str(default_label_text), # Ensure label is a string
            group=str(group_text), # Ensure group is a string
            properties=properties,
            title="\n".join(tooltip_parts)
        )

def _process_neo4j_relationship(rel_obj: neo4j.graph.Relationship, nodes_map: Dict[str, NodeModel], edges_list: List[EdgeModel], processed_rel_ids: Set[str]):
    if rel_obj and rel_obj.element_id and rel_obj.element_id not in processed_rel_ids:
        rel_id = rel_obj.element_id
        start_node_id = rel_obj.start_node.element_id
        end_node_id = rel_obj.end_node.element_id
        rel_type = rel_obj.type
        properties = dict(rel_obj) # Corrected: Relationship object itself is a mapping

        if start_node_id not in nodes_map:
            _add_node_from_neo4j_node(rel_obj.start_node, nodes_map)
        if end_node_id not in nodes_map:
            _add_node_from_neo4j_node(rel_obj.end_node, nodes_map)
            
        source_node_display_label = nodes_map.get(start_node_id).label if start_node_id in nodes_map else f"Node {start_node_id[:6]}..."
        target_node_display_label = nodes_map.get(end_node_id).label if end_node_id in nodes_map else f"Node {end_node_id[:6]}..."

        tooltip_parts = [
            f"ID: {rel_id}",
            f"Type: {rel_type}",
            f"Source: {source_node_display_label} ({start_node_id[:6]}...)",
            f"Target: {target_node_display_label} ({end_node_id[:6]}...)"
        ]
        if properties:
            tooltip_parts.append("Properties:")
            for key, value in properties.items():
                tooltip_parts.append(f"  {key}: {value}")
        
        edges_list.append(EdgeModel(
            id=rel_id,
            from_node=start_node_id, # Pydantic will use alias 'from'
            to_node=end_node_id,     # Pydantic will use alias 'to'
            label=rel_type,
            properties=properties,
            title="\n".join(tooltip_parts)
        ))
        processed_rel_ids.add(rel_id)

def _add_node_from_info_dict(node_info_dict: Dict[str, Any], nodes_map: Dict[str, NodeModel]):
    node_id = node_info_dict.get("id")
    if node_id and not nodes_map.get(node_id):
        labels = node_info_dict.get("labels", [])
        properties = node_info_dict.get("properties", {})
        
        default_label_text = labels[0] if labels else (properties.get("name") or f"Node ({str(node_id)[:6]}...)")
        group_text = labels[0] if labels else properties.get("group", "Unknown")

        tooltip_parts = [f"ID: {node_id}"]
        if labels:
            tooltip_parts.append(f"Labels: {', '.join(labels)}")
        if properties:
            tooltip_parts.append("Properties:")
            for key, value in properties.items():
                tooltip_parts.append(f"  {key}: {value}")

        nodes_map[node_id] = NodeModel(
            id=str(node_id),
            label=str(default_label_text),
            group=str(group_text),
            properties=properties,
            title="\n".join(tooltip_parts)
        )

def _process_relationship_from_info_dict(rel_info_dict: Dict[str, Any], nodes_map: Dict[str, NodeModel], edges_list: List[EdgeModel], processed_rel_ids: Set[str]):
    rel_id = rel_info_dict.get("id")
    if rel_id and rel_id not in processed_rel_ids:
        start_node_id = str(rel_info_dict["start"])
        end_node_id = str(rel_info_dict["end"])
        rel_type = rel_info_dict["type"]
        properties = rel_info_dict.get("properties", {})

        if start_node_id not in nodes_map:
            _add_node_from_info_dict({"id": start_node_id, "properties": {"name": f"Node {start_node_id[:6]}..."}}, nodes_map)
        if end_node_id not in nodes_map:
            _add_node_from_info_dict({"id": end_node_id, "properties": {"name": f"Node {end_node_id[:6]}..."}}, nodes_map)

        source_node_display_label = nodes_map.get(start_node_id).label if start_node_id in nodes_map else f"Node {start_node_id[:6]}..."
        target_node_display_label = nodes_map.get(end_node_id).label if end_node_id in nodes_map else f"Node {end_node_id[:6]}..."
        
        tooltip_parts = [
            f"ID: {rel_id}",
            f"Type: {rel_type}",
            f"Source: {source_node_display_label} ({start_node_id[:6]}...)",
            f"Target: {target_node_display_label} ({end_node_id[:6]}...)"
        ]
        if properties:
            tooltip_parts.append("Properties:")
            for key, value in properties.items():
                tooltip_parts.append(f"  {key}: {value}")

        edges_list.append(EdgeModel(
            id=str(rel_id),
            from_node=start_node_id,
            to_node=end_node_id,
            label=str(rel_type),
            properties=properties,
            title="\n".join(tooltip_parts)
        ))
        processed_rel_ids.add(rel_id)

# --- API Endpoints ---

# Warning: Fetching all nodes and relationships can be resource-intensive for large graphs.
# Consider implementing pagination or more specific queries for production environments.
# The current query aims to retrieve all nodes and their connected relationships.
DEFAULT_GRAPH_QUERY = "MATCH (n) OPTIONAL MATCH (n)-[r]-(m) RETURN n, r, m"

@app.get(
    "/api/graph",
    response_model=GraphDataResponse,
    summary="Get Default Graph Data",
    description="Fetches a default limited set of nodes and relationships from the Neo4j database.",
    tags=["Graph Operations"]
)
async def get_graph_data_endpoint(
    driver_instance: neo4j.AsyncDriver = Depends(get_driver_sync_dependency) # Expect AsyncDriver
):
    nodes_map: Dict[str, NodeModel] = {}
    edges_list: List[EdgeModel] = []
    processed_rel_ids: Set[str] = set()
    raw_records_payload: List[RawRecordModel] = []

    try:
        # --- BEGIN DIAGNOSTIC LOGS ---
        logger.info(f"Inside /api/graph - Driver instance type: {type(driver_instance)}")
        is_async_execute_query = False
        if hasattr(driver_instance, 'execute_query'):
            logger.info(f"Inside /api/graph - Driver execute_query type: {type(driver_instance.execute_query)}")
            is_async_execute_query = asyncio.iscoroutinefunction(driver_instance.execute_query)
            logger.info(f"Inside /api/graph - Is driver_instance.execute_query a coroutine function? {is_async_execute_query}")
            if not is_async_execute_query:
                logger.warning(
                    "Inside /api/graph - driver_instance.execute_query is NOT a coroutine function. "
                    "Attempting to run synchronously in a thread."
                )
        else:
            logger.error("Inside /api/graph - driver_instance does not have an execute_query method.")
            raise HTTPException(status_code=500, detail="Driver misconfiguration: execute_query not found.")
        # --- END DIAGNOSTIC LOGS ---
        
        if is_async_execute_query:
            results = await driver_instance.execute_query(DEFAULT_GRAPH_QUERY, database_=NEO4J_DATABASE, routing_="r")
        else: # Fallback for synchronous driver
            results = await to_thread.run_sync(driver_instance.execute_query, DEFAULT_GRAPH_QUERY, database_=NEO4J_DATABASE, routing_="r")

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
            
            if raw_record_data: # Only append if there's something to append
                raw_records_payload.append(RawRecordModel(**raw_record_data))

        return GraphDataResponse(
            nodes=list(nodes_map.values()),
            edges=edges_list, 
            rawRecords=raw_records_payload
        )
    except neo4j.exceptions.Neo4jError as db_err:
        logger.error(f"Neo4j database error in /api/graph: {db_err}", exc_info=True)
        raise HTTPException(status_code=503, detail=f"Database error: {str(db_err.message)}")
    except HTTPException: # Re-raise HTTPExceptions (like 503 from get_driver_sync_dependency)
        raise
    except Exception as e:
        logger.error(f"Unexpected error in /api/graph: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")

@app.post(
    "/api/query",
    response_model=QueryResponse,
    summary="Execute Custom Cypher Query",
    description="Executes a user-provided Cypher query against the Neo4j database. "
                "**Warning:** Use with caution, as this endpoint can execute arbitrary queries.",
    tags=["Graph Operations"]
)
async def execute_custom_query_endpoint(
    payload: QueryRequest,
    driver_instance: neo4j.AsyncDriver = Depends(get_driver_sync_dependency) # Expect AsyncDriver
):
    nodes_map: Dict[str, NodeModel] = {}
    edges_list: List[EdgeModel] = []
    processed_rel_ids: Set[str] = set()
    raw_records_payload: List[RawRecordModel] = [] # For Pydantic model
    summary_info_payload: Optional[QuerySummaryModel] = None


    try:
        # Similar check for the custom query endpoint
        is_async_execute_query_custom = False
        if hasattr(driver_instance, 'execute_query'):
            is_async_execute_query_custom = asyncio.iscoroutinefunction(driver_instance.execute_query)
        
        if is_async_execute_query_custom:
            results = await driver_instance.execute_query(
                payload.query, payload.params or {}, database_=NEO4J_DATABASE, routing_="r"
            )
        else: # Fallback for synchronous driver
            logger.warning(
                "Inside /api/query - driver_instance.execute_query is NOT a coroutine function. "
                "Attempting to run synchronously in a thread."
            )
            results = await to_thread.run_sync(driver_instance.execute_query, payload.query, payload.params or {}, database_=NEO4J_DATABASE, routing_="r")

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
                 current_raw_record_data["n"] = RawRecordItem(**n_info) # Assuming n_info matches RawRecordItem structure
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
                current_raw_record_data["r"] = RawRecordItem(**r_info) # Assuming r_info matches RawRecordItem structure for relationships
            elif r_rel:
                _process_neo4j_relationship(r_rel, nodes_map, edges_list, processed_rel_ids)
                current_raw_record_data["r"] = RawRecordItem(
                    elementId=r_rel.element_id, type=r_rel.type,
                    startNodeElementId=r_rel.start_node.element_id, endNodeElementId=r_rel.end_node.element_id,
                    properties=dict(r_rel)
                )
            
            # For truly arbitrary results, we might just pass record.data()
            # but trying to fit into RawRecordModel if possible
            if current_raw_record_data:
                raw_records_payload.append(RawRecordModel(**current_raw_record_data))
            else: # Fallback for completely arbitrary records
                raw_records_payload.append(RawRecordModel(**record.data()))


        # Process summary
        if results.summary and results.summary.counters:
            # Convert summary object to dict, handling potential hyphens in keys
            summary_dict = results.summary.counters.summary()
            # FastAPI/Pydantic expects field names, not aliases, for instantiation
            # So we need to map from "nodes-created" to "nodes_created" if using aliases in Pydantic model
            mapped_summary_dict = {}
            for key, value in summary_dict.items():
                mapped_summary_dict[key.replace('-', '_')] = value
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
    except HTTPException: # Re-raise HTTPExceptions
        raise
    except Exception as e:
        logger.error(f"Unexpected error in /api/query: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    logger.info("Starting Uvicorn server for GraphTrace API...")
    uvicorn.run(app, host="0.0.0.0", port=8000)
