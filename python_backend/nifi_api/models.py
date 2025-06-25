from pydantic import BaseModel
from typing import List, Dict, Optional

class NiFiComponentReference(BaseModel):
    id: str
    name: str
    componentType: str
    state: Optional[str] = None # For processors, etc.

class NiFiProcessorDTO(BaseModel):
    id: str
    name: str
    type: str
    state: str # RUNNING, STOPPED, DISABLED
    inputRequirement: Optional[str] = None
    position: Dict[str, float] # x, y coordinates

class NiFiConnectionDTO(BaseModel):
    id: str
    name: Optional[str] = None
    source: NiFiComponentReference
    destination: NiFiComponentReference
    selectedRelationships: Optional[List[str]] = None
    backPressureObjectThreshold: Optional[int] = None
    backPressureDataSizeThreshold: Optional[str] = None
    flowFileConcurrently: Optional[int] = None
    bends: Optional[List[Dict[str, float]]] = None # For visual routing

class NiFiPortDTO(BaseModel):
    id: str
    name: str
    type: str # INPUT_PORT, OUTPUT_PORT
    state: str # RUNNING, STOPPED, DISABLED
    position: Dict[str, float]

class NiFiProcessGroupFlowDTO(BaseModel):
    id: str
    name: str
    processors: Optional[List[Dict[str, NiFiProcessorDTO]]] = None # Wrapped in dict with 'component' key
    connections: Optional[List[Dict[str, NiFiConnectionDTO]]] = None
    inputPorts: Optional[List[Dict[str, NiFiPortDTO]]] = None
    outputPorts: Optional[List[Dict[str, NiFiPortDTO]]] = None
    processGroups: Optional[List[Dict[str, 'NiFiProcessGroupDTO']]] = None # Nested process groups

class NiFiProcessGroupDTO(BaseModel):
    id: str
    name: str
    position: Dict[str, float]
    contents: Optional[NiFiProcessGroupFlowDTO] = None # For recursive fetching

class NiFiFlowResponse(BaseModel):
    processGroupFlow: NiFiProcessGroupFlowDTO

class NiFiProcessGroupStatusDTO(BaseModel):
    id: str
    name: str
    bytesIn: Optional[int] = None
    bytesOut: Optional[int] = None
    flowFilesIn: Optional[int] = None
    flowFilesOut: Optional[int] = None
    activeThreadCount: Optional[int] = None
    queued: Optional[str] = None

class NiFiStatusResponse(BaseModel):
    processGroupStatus: NiFiProcessGroupStatusDTO

class NiFiProcessGroupSummary(BaseModel):
    id: str
    name: str

class NiFiProcessGroupListResponse(BaseModel):
    processGroups: List[NiFiProcessGroupSummary]

# Call model_rebuild() on all models after they are fully defined
NiFiProcessGroupFlowDTO.model_rebuild()
NiFiProcessGroupDTO.model_rebuild() # Also rebuild this one as it references NiFiProcessGroupFlowDTO