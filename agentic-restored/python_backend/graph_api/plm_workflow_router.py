"""PLM workflow endpoints.

Strict policy: no mock/sample/demo data.

These endpoints remain available for UI routing compatibility but fail closed
(HTTP 503) until real PLM workflow data is wired in.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, NoReturn

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/plm", tags=["PLM Workflow"])


@router.get("/workflow/availability")
async def plm_workflow_availability() -> Dict[str, Any]:
    """Availability probe for PLM workflow graph data.

    Returns 200 always so UIs can check availability without triggering
    browser 'failed resource' console errors.
    """
    return {
        "available": False,
        "reason": (
            "PLM workflow endpoints are unavailable because real PLM workflow data is not configured. "
            "No demo/mock data is served."
        ),
    }


def _unavailable() -> NoReturn:
    raise HTTPException(
        status_code=503,
        detail=(
            "PLM workflow endpoints are unavailable because real PLM workflow data is not configured. "
            "No demo/mock data is served."
        ),
    )


class WorkflowNode(BaseModel):
    id: str
    label: str
    type: str
    stage: str
    status: str = "healthy"
    properties: Dict[str, Any] = Field(default_factory=dict)


class WorkflowEdge(BaseModel):
    id: str
    source: str
    target: str
    label: str
    type: str = "dataflow"


class PLMWorkflowResponse(BaseModel):
    nodes: List[WorkflowNode]
    edges: List[WorkflowEdge]
    metadata: Dict[str, Any] = Field(default_factory=dict)


class PLMSourceSystem(BaseModel):
    id: str
    name: str
    type: str
    version: str
    connection_details: Dict[str, Any]
    statistics: Dict[str, int]
    status: str = "active"


class AIAgentConfig(BaseModel):
    id: str
    name: str
    role: str
    capabilities: List[str]
    status: str = "active"
    performance_metrics: Dict[str, Any] = Field(default_factory=dict)


@router.get("/workflow", response_model=PLMWorkflowResponse)
async def get_plm_workflow() -> PLMWorkflowResponse:
    _unavailable()


@router.get("/sources", response_model=List[PLMSourceSystem])
async def get_plm_sources() -> List[PLMSourceSystem]:
    _unavailable()


@router.get("/agents", response_model=List[AIAgentConfig])
async def get_ai_agents() -> List[AIAgentConfig]:
    _unavailable()


@router.get("/health")
async def plm_workflow_health() -> Dict[str, Any]:
    _unavailable()
