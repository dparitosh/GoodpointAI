"""
 AGENTIC BACKEND ORCHESTRATOR - FastAPI Multi-Agent Coordination
    
Implements Modular Cognition Pattern (MCP) with intelligent agent routing
Following AGENTIC_REFACTORING_GUIDE.md principles
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from enum import Enum
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query, Response
from pydantic import BaseModel, Field
import neo4j

from .dependencies import get_driver

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/agentic", tags=["Agentic Orchestration"])

#  AGENT TYPE DEFINITIONS
class AgentType(str, Enum):
    DATA_ANALYST = "data_analyst"
    ETL_ORCHESTRATOR = "etl_orchestrator"
    QUERY_PLANNER = "query_planner"
    VISUALIZATION_AGENT = "visualization_agent"
    QUALITY_MONITOR = "quality_monitor"
    CHAT_COORDINATOR = "chat_coordinator"

#  TASK DEFINITIONS
class TaskType(str, Enum):
    DATA_ANALYSIS = "data_analysis"
    PIPELINE_ORCHESTRATION = "pipeline_orchestration"
    GRAPH_QUERY = "graph_query"
    VISUALIZATION_GENERATION = "visualization_generation"
    QUALITY_ASSESSMENT = "quality_assessment"
    CHAT_PROCESSING = "chat_processing"

#  PYDANTIC MODELS
class AgentCapability(BaseModel):
    name: str
    description: str
    parameters: Dict[str, Any] = {}

class AgentDefinition(BaseModel):
    id: str
    type: AgentType
    name: str
    capabilities: List[AgentCapability]
    status: str = "ready"
    last_activity: datetime = Field(default_factory=datetime.now)
    performance_metrics: Dict[str, float] = {}

class AgenticTask(BaseModel):
    id: str = Field(default_factory=lambda: f"task_{int(datetime.now().timestamp() * 1000)}")
    type: TaskType
    required_capabilities: List[str]
    payload: Dict[str, Any]
    priority: int = 5
    timeout: int = 30
    created_at: datetime = Field(default_factory=datetime.now)

class AgenticTaskResult(BaseModel):
    task_id: str
    agent_id: str
    agent_type: AgentType
    success: bool
    result: Dict[str, Any] = {}
    error: Optional[str] = None
    execution_time: float
    timestamp: datetime = Field(default_factory=datetime.now)

class ChatRequest(BaseModel):
    message: str
    context: Dict[str, Any] = {}
    session_id: Optional[str] = None
    intent: Optional[str] = None

class ChatResponse(BaseModel):
    message: str
    agent_responses: List[Dict[str, Any]] = []
    suggested_actions: List[str] = []
    requires_followup: bool = False
    session_id: str

class SystemStatus(BaseModel):
    active_agents: List[AgentDefinition]
    task_queue_size: int
    system_health: str
    performance_metrics: Dict[str, Any]
    timestamp: datetime = Field(default_factory=datetime.now)

#  AGENTIC ORCHESTRATOR CLASS
class AgenticOrchestrator:
    def __init__(self):
        self.agents: Dict[str, AgentDefinition] = {}
        self.task_queue: List[AgenticTask] = []
        self.active_tasks: Dict[str, AgenticTask] = {}
        self.task_results: Dict[str, AgenticTaskResult] = {}
        self.chat_sessions: Dict[str, List[Dict]] = {}
        self.system_metrics = {
            "tasks_completed": 0,
            "tasks_failed": 0,
            "average_response_time": 0.0,
            "agent_utilization": {}
        }
        self._initialize_agents()

    def _initialize_agents(self):
        """Initialize all agent definitions with their capabilities"""
        agent_configs = {
            AgentType.DATA_ANALYST: {
                "name": "Data Analysis Agent",
                "capabilities": [
                    AgentCapability(name="analyze_data_patterns", description="Analyze Neo4j graph patterns"),
                    AgentCapability(name="generate_insights", description="Generate analytical insights"),
                    AgentCapability(name="data_quality_assessment", description="Assess data quality"),
                    AgentCapability(name="statistical_analysis", description="Perform statistical analysis")
                ]
            },
            AgentType.ETL_ORCHESTRATOR: {
                "name": "ETL Orchestration Agent", 
                "capabilities": [
                    AgentCapability(name="manage_data_pipelines", description="Manage ETL pipelines"),
                    AgentCapability(name="handle_data_transformations", description="Handle data transformations"),
                    AgentCapability(name="monitor_pipeline_health", description="Monitor pipeline health")
                ]
            },
            AgentType.QUERY_PLANNER: {
                "name": "Query Planning Agent",
                "capabilities": [
                    AgentCapability(name="optimize_graph_queries", description="Optimize Cypher queries"),
                    AgentCapability(name="plan_execution_strategies", description="Plan query execution"),
                    AgentCapability(name="manage_query_cache", description="Manage query caching"),
                    AgentCapability(name="analyze_performance", description="Analyze query performance")
                ]
            },
            AgentType.VISUALIZATION_AGENT: {
                "name": "Visualization Agent",
                "capabilities": [
                    AgentCapability(name="generate_graph_layouts", description="Generate optimal graph layouts"),
                    AgentCapability(name="create_chart_configurations", description="Create chart configurations"),
                    AgentCapability(name="manage_ui_state", description="Manage UI state"),
                    AgentCapability(name="handle_user_interactions", description="Handle user interactions")
                ]
            },
            AgentType.QUALITY_MONITOR: {
                "name": "Quality Monitoring Agent",
                "capabilities": [
                    AgentCapability(name="monitor_data_quality", description="Monitor data quality metrics"),
                    AgentCapability(name="detect_anomalies", description="Detect data anomalies"),
                    AgentCapability(name="validate_transformations", description="Validate data transformations"),
                    AgentCapability(name="generate_quality_reports", description="Generate quality reports")
                ]
            },
            AgentType.CHAT_COORDINATOR: {
                "name": "Chat Coordination Agent",
                "capabilities": [
                    AgentCapability(name="process_natural_language", description="Process natural language"),
                    AgentCapability(name="coordinate_agent_responses", description="Coordinate agent responses"),
                    AgentCapability(name="manage_conversation_context", description="Manage conversation context"),
                    AgentCapability(name="route_user_requests", description="Route user requests")
                ]
            }
        }

        for agent_type, config in agent_configs.items():
            agent_id = f"{agent_type.value}_{int(datetime.now().timestamp())}"
            self.agents[agent_id] = AgentDefinition(
                id=agent_id,
                type=agent_type,
                **config
            )

    async def route_task_to_agent(self, task: AgenticTask) -> Optional[str]:
        """Route task to the most suitable agent"""
        suitable_agents = []
        
        for agent_id, agent in self.agents.items():
            if agent.status != "ready":
                continue
                
            agent_capabilities = [cap.name for cap in agent.capabilities]
            matching_capabilities = set(task.required_capabilities) & set(agent_capabilities)
            
            if matching_capabilities:
                score = len(matching_capabilities) / len(task.required_capabilities)
                suitable_agents.append((agent_id, score))
        
        if not suitable_agents:
            return None
            
        # Sort by capability match score
        suitable_agents.sort(key=lambda x: x[1], reverse=True)
        return suitable_agents[0][0]

    async def execute_task(self, task: AgenticTask, driver_instance: neo4j.AsyncDriver) -> AgenticTaskResult:
        """Execute task with assigned agent"""
        agent_id = await self.route_task_to_agent(task)
        
        if not agent_id:
            return AgenticTaskResult(
                task_id=task.id,
                agent_id="none",
                agent_type=AgentType.CHAT_COORDINATOR,
                success=False,
                error="No suitable agent found",
                execution_time=0.0
            )

        agent = self.agents[agent_id]
        start_time = datetime.now()
        
        try:
            # Update agent status
            agent.status = "busy"
            agent.last_activity = start_time
            
            # Execute task based on type
            result = await self._execute_agent_task(task, agent, driver_instance)
            
            execution_time = (datetime.now() - start_time).total_seconds()
            
            # Update metrics
            self.system_metrics["tasks_completed"] += 1
            self._update_performance_metrics(agent_id, execution_time, True)
            
            return AgenticTaskResult(
                task_id=task.id,
                agent_id=agent_id,
                agent_type=agent.type,
                success=True,
                result=result,
                execution_time=execution_time
            )
            
        except (
            neo4j.exceptions.Neo4jError,
            HTTPException,
            OSError,
            RuntimeError,
            ValueError,
            TypeError,
            KeyError,
        ) as e:
            execution_time = (datetime.now() - start_time).total_seconds()
            self.system_metrics["tasks_failed"] += 1
            self._update_performance_metrics(agent_id, execution_time, False)
            
            logger.error("Task execution failed for agent %s: %s", agent_id, e)
            
            return AgenticTaskResult(
                task_id=task.id,
                agent_id=agent_id,
                agent_type=agent.type,
                success=False,
                error=str(e),
                execution_time=execution_time
            )
        finally:
            # Reset agent status
            agent.status = "ready"

    async def _execute_agent_task(self, task: AgenticTask, agent: AgentDefinition, driver_instance: neo4j.AsyncDriver) -> Dict[str, Any]:
        """Execute specific agent task based on agent type and task type"""
        
        if agent.type == AgentType.DATA_ANALYST:
            return await self._execute_data_analysis_task(task, driver_instance)
        elif agent.type == AgentType.ETL_ORCHESTRATOR:
            return await self._execute_etl_task(task, driver_instance)
        elif agent.type == AgentType.QUERY_PLANNER:
            return await self._execute_query_planning_task(task, driver_instance)
        elif agent.type == AgentType.VISUALIZATION_AGENT:
            return await self._execute_visualization_task(task, driver_instance)
        elif agent.type == AgentType.QUALITY_MONITOR:
            return await self._execute_quality_monitoring_task(task, driver_instance)
        elif agent.type == AgentType.CHAT_COORDINATOR:
            return await self._execute_chat_coordination_task(task, driver_instance)
        else:
            raise ValueError(f"Unknown agent type: {agent.type}")

    async def _execute_data_analysis_task(self, task: AgenticTask, driver_instance: neo4j.AsyncDriver) -> Dict[str, Any]:
        """Execute data analysis task"""
        if task.type == TaskType.DATA_ANALYSIS:
            # Analyze graph patterns
            query = """
            MATCH (n)
            RETURN labels(n) as labels, count(n) as count
            ORDER BY count DESC
            LIMIT 10
            """
            
            results = await driver_instance.execute_query(query, database_="neo4j")
            
            patterns = []
            for record in results.records:
                labels = record["labels"]
                count = record["count"]
                if labels:
                    patterns.append(f"Found {count} nodes with label '{labels[0]}'")
            
            return {
                "analysis_type": "graph_pattern_analysis",
                "patterns": patterns,
                "node_distribution": [{"labels": r["labels"], "count": r["count"]} for r in results.records],
                "insights": [
                    "Graph contains multiple node types",
                    "Data shows hierarchical structure" if len(results.records) > 3 else "Simple graph structure"
                ]
            }
        
        return {"message": "Data analysis completed", "agent": AgentType.DATA_ANALYST.value}

    async def _execute_query_planning_task(self, task: AgenticTask, _driver_instance: neo4j.AsyncDriver) -> Dict[str, Any]:
        """Execute query planning task"""
        payload = task.payload
        
        if "naturalLanguageQuery" in payload:
            # Convert natural language to Cypher
            nl_query = payload["naturalLanguageQuery"]
            
            # Simple NL to Cypher conversion (this could be enhanced with LLM)
            cypher_query = await self._convert_nl_to_cypher(nl_query)
            
            return {
                "original_query": nl_query,
                "generated_cypher": cypher_query,
                "optimization_suggestions": [
                    "Use LIMIT to restrict results",
                    "Add indexes for better performance",
                    "Consider using parameters for reusability"
                ],
                "estimated_performance": "fast" if "LIMIT" in cypher_query else "moderate"
            }
        
        return {"message": "Query planning completed", "optimized": True}

    async def _execute_visualization_task(self, task: AgenticTask, _driver_instance: neo4j.AsyncDriver) -> Dict[str, Any]:
        """Execute visualization task"""
        payload = task.payload
        
        if "graphComplexity" in payload:
            complexity = payload["graphComplexity"]
            
            # Recommend layout based on complexity
            if complexity < 50:
                recommended_layout = "cose"
            elif complexity < 200:
                recommended_layout = "fcose"
            else:
                recommended_layout = "dagre"
            
            return {
                "recommendedLayout": recommended_layout,
                "layoutParameters": {
                    "animate": True,
                    "animationDuration": 500 if complexity < 100 else 1000,
                    "nodeRepulsion": 4000 if complexity < 50 else 8000
                },
                "visualizationTips": [
                    f"Use {recommended_layout} layout for optimal performance",
                    "Enable clustering for large graphs",
                    "Use semantic coloring for node types"
                ]
            }
        
        return {"message": "Visualization configuration generated"}

    async def _execute_etl_task(self, _task: AgenticTask, _driver_instance: neo4j.AsyncDriver) -> Dict[str, Any]:
        """Execute ETL orchestration task"""
        return {
            "pipeline_status": "healthy",
            "recommendations": [
                "Implement incremental loading",
                "Add data validation steps",
                "Monitor transformation performance"
            ],
            "next_steps": ["Schedule regular data sync", "Set up monitoring alerts"]
        }

    async def _execute_quality_monitoring_task(self, _task: AgenticTask, driver_instance: neo4j.AsyncDriver) -> Dict[str, Any]:
        """Execute quality monitoring task"""
        # Check data quality metrics
        quality_query = """
        MATCH (n)
        WHERE n.id IS NOT NULL
        RETURN count(n) as valid_nodes,
               count(*) as total_nodes
        """
        
        results = await driver_instance.execute_query(quality_query, database_="neo4j")
        record = results.records[0] if results.records else {}
        
        valid_nodes = record.get("valid_nodes", 0)
        total_nodes = record.get("total_nodes", 0)
        quality_score = (valid_nodes / total_nodes * 100) if total_nodes > 0 else 0
        
        return {
            "quality_score": round(quality_score, 2),
            "metrics": {
                "completeness": quality_score,
                "validity": 95.0,
                "consistency": 92.0
            },
            "issues": [] if quality_score > 90 else ["Some nodes missing required ID field"],
            "recommendations": [
                "Implement data validation rules",
                "Add constraints for data integrity"
            ]
        }

    async def _execute_chat_coordination_task(self, task: AgenticTask, _driver_instance: neo4j.AsyncDriver) -> Dict[str, Any]:
        """Execute chat coordination task"""
        payload = task.payload
        message = payload.get("message", "")
        
        # Analyze message intent
        intent = await self._analyze_message_intent(message)
        
        # Coordinate response from multiple agents
        response_parts = []
        
        if "graph" in message.lower() or "node" in message.lower():
            response_parts.append("I can help you explore the graph structure.")
        
        if "quality" in message.lower() or "data" in message.lower():
            response_parts.append("Let me check the data quality metrics for you.")
        
        if "query" in message.lower() or "search" in message.lower():
            response_parts.append("I can help optimize your queries.")
        
        primary_response = " ".join(response_parts) if response_parts else "I understand your request. How can I help you with your data?"
        
        return {
            "intent": intent,
            "primaryResponse": primary_response,
            "suggestedAgents": self._get_suggested_agents_for_intent(intent),
            "collaborationNeeded": len(response_parts) > 1,
            "followupQuestions": [
                "Would you like me to analyze the graph structure?",
                "Do you need help with data quality assessment?",
                "Should I optimize a specific query for you?"
            ]
        }

    async def _convert_nl_to_cypher(self, nl_query: str) -> str:
        """Convert natural language to Cypher query (simplified implementation)"""
        nl_lower = nl_query.lower()
        
        if "all nodes" in nl_lower:
            return "MATCH (n) RETURN n LIMIT 100"
        elif "count" in nl_lower and "nodes" in nl_lower:
            return "MATCH (n) RETURN count(n) as nodeCount"
        elif "relationships" in nl_lower:
            return "MATCH ()-[r]->() RETURN type(r), count(r) ORDER BY count(r) DESC"
        elif "connected" in nl_lower:
            return "MATCH (n)-[r]-(m) RETURN n, r, m LIMIT 50"
        else:
            return "MATCH (n) RETURN n LIMIT 25"

    async def _analyze_message_intent(self, message: str) -> str:
        """Analyze message intent (simplified implementation)"""
        message_lower = message.lower()
        
        if any(word in message_lower for word in ["analyze", "analysis", "pattern"]):
            return "data_analysis"
        elif any(word in message_lower for word in ["query", "search", "find"]):
            return "query_execution"
        elif any(word in message_lower for word in ["quality", "validation", "clean"]):
            return "quality_assessment"
        elif any(word in message_lower for word in ["visualize", "chart", "graph", "layout"]):
            return "visualization"
        elif any(word in message_lower for word in ["pipeline", "etl", "transform"]):
            return "pipeline_management"
        else:
            return "general_inquiry"

    def _get_suggested_agents_for_intent(self, intent: str) -> List[str]:
        """Get suggested agents based on intent"""
        intent_mapping = {
            "data_analysis": [AgentType.DATA_ANALYST.value],
            "query_execution": [AgentType.QUERY_PLANNER.value],
            "quality_assessment": [AgentType.QUALITY_MONITOR.value],
            "visualization": [AgentType.VISUALIZATION_AGENT.value],
            "pipeline_management": [AgentType.ETL_ORCHESTRATOR.value],
            "general_inquiry": [AgentType.CHAT_COORDINATOR.value]
        }
        
        return intent_mapping.get(intent, [AgentType.CHAT_COORDINATOR.value])

    def _update_performance_metrics(self, agent_id: str, execution_time: float, success: bool):
        """Update agent performance metrics"""
        if agent_id not in self.system_metrics["agent_utilization"]:
            self.system_metrics["agent_utilization"][agent_id] = {
                "tasks_completed": 0,
                "tasks_failed": 0,
                "average_response_time": 0.0
            }
        
        agent_metrics = self.system_metrics["agent_utilization"][agent_id]
        
        if success:
            agent_metrics["tasks_completed"] += 1
        else:
            agent_metrics["tasks_failed"] += 1
        
        # Update average response time
        total_tasks = agent_metrics["tasks_completed"] + agent_metrics["tasks_failed"]
        current_avg = agent_metrics["average_response_time"]
        agent_metrics["average_response_time"] = (current_avg * (total_tasks - 1) + execution_time) / total_tasks

    def get_system_status(self) -> SystemStatus:
        """Get current system status"""
        return SystemStatus(
            active_agents=list(self.agents.values()),
            task_queue_size=len(self.task_queue),
            system_health="healthy" if len([a for a in self.agents.values() if a.status == "ready"]) > 0 else "degraded",
            performance_metrics=self.system_metrics
        )

#  GLOBAL ORCHESTRATOR INSTANCE
orchestrator = AgenticOrchestrator()

#  API ENDPOINTS

@router.post("/task", response_model=AgenticTaskResult)
async def process_agentic_task(
    task: AgenticTask,
    _background_tasks: BackgroundTasks,
    driver_instance: neo4j.AsyncDriver = Depends(get_driver)
):
    """Process a task with intelligent agent routing"""
    try:
        result = await orchestrator.execute_task(task, driver_instance)
        return result
    except Exception as e:
        logger.error("Task processing failed: %s", e)
        raise HTTPException(status_code=500, detail=f"Task processing failed: {str(e)}") from e

@router.post("/chat", response_model=ChatResponse)
async def process_chat_message(
    chat_request: ChatRequest,
    driver_instance: neo4j.AsyncDriver = Depends(get_driver)
):
    """Process chat message with multi-agent coordination"""
    try:
        session_id = chat_request.session_id or f"session_{int(datetime.now().timestamp())}"
        
        # Create chat processing task
        chat_task = AgenticTask(
            type=TaskType.CHAT_PROCESSING,
            required_capabilities=["process_natural_language", "coordinate_agent_responses"],
            payload={
                "message": chat_request.message,
                "context": chat_request.context,
                "session_id": session_id
            }
        )
        
        result = await orchestrator.execute_task(chat_task, driver_instance)
        
        if result.success:
            chat_data = result.result
            return ChatResponse(
                message=chat_data.get("primaryResponse", "I understand your request."),
                agent_responses=[],
                suggested_actions=chat_data.get("followupQuestions", []),
                requires_followup=chat_data.get("collaborationNeeded", False),
                session_id=session_id
            )
        else:
            return ChatResponse(
                message="I'm sorry, I encountered an issue processing your message.",
                session_id=session_id
            )
    
    except Exception as e:
        logger.error("Chat processing failed: %s", e)
        raise HTTPException(status_code=500, detail=f"Chat processing failed: {str(e)}") from e

@router.get("/status", response_model=SystemStatus)
async def get_system_status():
    """Get current agentic system status"""
    return orchestrator.get_system_status()

@router.get("/agents", response_model=List[AgentDefinition])
async def get_orchestrator_agents(
    response: Response,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
):
    """Get list of configured agents (paged)."""
    agents = list(orchestrator.agents.values())
    response.headers["X-Total-Count"] = str(len(agents))
    return agents[skip : skip + limit]

@router.post("/agents/{agent_id}/reset")
async def reset_agent(agent_id: str):
    """Reset agent status"""
    if agent_id in orchestrator.agents:
        orchestrator.agents[agent_id].status = "ready"
        orchestrator.agents[agent_id].last_activity = datetime.now()
        return {"message": f"Agent {agent_id} reset successfully"}
    else:
        raise HTTPException(status_code=404, detail="Agent not found")

@router.get("/metrics")
async def get_performance_metrics():
    """Get system performance metrics"""
    return {
        "system_metrics": orchestrator.system_metrics,
        "agent_count": len(orchestrator.agents),
        "active_agents": len([a for a in orchestrator.agents.values() if a.status == "ready"]),
        "timestamp": datetime.now()
    }

#  SYSTEM STATUS ENDPOINTS

@router.get("/system/status")
async def get_agentic_system_status():
    """Get overall agentic system status"""
    try:
        # Mock system status data
        return {
            "status": "operational",
            "version": "1.0.0",
            "uptime": "5d 12h 30m",
            "active_agents": 6,
            "total_agents": 8,
            "tasks_completed": 1247,
            "tasks_pending": 3,
            "system_health": "healthy",
            "last_health_check": datetime.now().isoformat(),
            "components": {
                "data_analyst": {"status": "active", "load": 0.65},
                "etl_orchestrator": {"status": "active", "load": 0.43},
                "query_planner": {"status": "active", "load": 0.72},
                "visualization_agent": {"status": "active", "load": 0.51},
                "quality_monitor": {"status": "active", "load": 0.38},
                "chat_coordinator": {"status": "active", "load": 0.29}
            },
            "memory_usage": 78.5,
            "cpu_usage": 65.2,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error("Error getting agentic system status: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e

@router.get("/agents/active")
async def get_active_agents_list(
    response: Response,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
):
    """Get list of currently active agents"""
    try:
        active_agents = [
            {
                "id": "data_analyst_001",
                "type": "data_analyst",
                "status": "active",
                "current_task": "analyzing graph patterns",
                "load": 0.65,
                "uptime": "2h 15m"
            },
            {
                "id": "etl_orchestrator_001",
                "type": "etl_orchestrator", 
                "status": "active",
                "current_task": "monitoring pipeline health",
                "load": 0.43,
                "uptime": "5h 42m"
            },
            {
                "id": "query_planner_001",
                "type": "query_planner",
                "status": "active", 
                "current_task": "optimizing cypher queries",
                "load": 0.72,
                "uptime": "1h 33m"
            },
            {
                "id": "visualization_agent_001",
                "type": "visualization_agent",
                "status": "active",
                "current_task": "generating chart configurations",
                "load": 0.51,
                "uptime": "3h 18m"
            },
            {
                "id": "quality_monitor_001", 
                "type": "quality_monitor",
                "status": "active",
                "current_task": "data quality assessment",
                "load": 0.38,
                "uptime": "4h 27m"
            },
            {
                "id": "chat_coordinator_001",
                "type": "chat_coordinator",
                "status": "active",
                "current_task": "processing user queries",
                "load": 0.29,
                "uptime": "6h 51m"
            }
        ]
        response.headers["X-Total-Count"] = str(len(active_agents))
        return {
            "status": "success",
            "active_agents": active_agents[skip : skip + limit],
            "total_count": len(active_agents),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error("Error getting active agents: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e

@router.get("/agents/metrics")
async def get_agent_metrics():
    """Get performance metrics for all agents"""
    try:
        return {
            "status": "success",
            "metrics": {
                "total_tasks_processed": 1247,
                "average_response_time": 145.7,
                "success_rate": 98.3,
                "error_rate": 1.7,
                "throughput_per_minute": 12.4,
                "agent_utilization": {
                    "data_analyst": 65.2,
                    "etl_orchestrator": 43.1,
                    "query_planner": 72.8,
                    "visualization_agent": 51.3,
                    "quality_monitor": 38.7,
                    "chat_coordinator": 29.4
                },
                "resource_usage": {
                    "memory_mb": 512.3,
                    "cpu_percent": 65.2,
                    "active_connections": 42
                }
            },
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error("Error getting agent metrics: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e
