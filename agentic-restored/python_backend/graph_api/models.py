from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional

class NodeModel(BaseModel):
    id: str = Field(..., description="The unique element ID of the node.")
    label: str = Field(..., description="A display label for the node, often derived from a 'name' property or its primary Neo4j label.")
    group: str = Field(..., description="A group identifier for the node, often its primary Neo4j label, used for visualization styling.")
    properties: Dict[str, Any] = Field(..., description="A dictionary of the node's properties.")
    title: str = Field(..., description="A string used for tooltips in visualizations, typically a formatted summary of node details.")

class EdgeModel(BaseModel):
    id: str = Field(..., description="The unique element ID of the relationship.")
    from_node: str = Field(..., alias="from", serialization_alias="from", description="The element ID of the source node.") # 'from' is a reserved keyword, use alias
    to_node: str = Field(..., alias="to", serialization_alias="to", description="The element ID of the target node.")
    label: str = Field(..., description="The type of the relationship.")
    properties: Dict[str, Any] = Field(..., description="A dictionary of the relationship's properties.")
    title: str = Field(..., description="A string used for tooltips in visualizations, typically a formatted summary of relationship details.")

    class Config:
        populate_by_name = True
        by_alias = True  # Serialize using aliases for JSON output

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