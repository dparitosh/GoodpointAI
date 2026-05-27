"""
 AGENTIC GRAPH ROUTER - Enhanced with Modular Cognition Pattern
Applies Pareto analysis to Neo4j operations: 20% of queries provide 80% of insights
Integrates multi-agent orchestration for intelligent graph processing
"""

import logging
import asyncio
from typing import Dict, List, Any, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
import neo4j
from datetime import datetime
import uuid

from .dependencies import get_driver
from core.config import NEO4J_DATABASE

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/agentic-graph", tags=["Agentic Graph Operations"])

#  AGENTIC MODELS
class GraphAnalysisRequest(BaseModel):
    focus_areas: List[str] = Field(default=["connectivity", "centrality", "clustering"])
    pareto_optimization: bool = Field(default=True, description="Apply Pareto analysis to prioritize insights")
    max_results: int = Field(default=100, description="Maximum results to return")
    agent_config: Dict[str, Any] = Field(default_factory=dict)

class AgentTaskRequest(BaseModel):
    agent_type: str = Field(..., description="Type of agent: analyzer, extractor, transformer, insights")
    task_config: Dict[str, Any] = Field(..., description="Agent-specific configuration")
    context: Dict[str, Any] = Field(default_factory=dict, description="Execution context")

class GraphInsightsResponse(BaseModel):
    insights: List[Dict[str, Any]]
    pareto_ranking: List[Dict[str, Any]]
    critical_nodes: List[Dict[str, Any]]
    recommendations: List[str]
    execution_metrics: Dict[str, Any]
    agent_status: Dict[str, str]

class MultiAgentOrchestrationRequest(BaseModel):
    orchestration_type: str = Field(..., description="Type: parallel, sequential, conditional")
    agents: List[AgentTaskRequest]
    coordination_rules: Dict[str, Any] = Field(default_factory=dict)

#  GRAPH ANALYSIS AGENTS
class GraphAnalysisAgent:
    """Base class for specialized graph analysis agents"""
    
    def __init__(self, agent_type: str, config: Optional[Dict[str, Any]] = None):
        self.agent_type = agent_type
        self.config = config or {}
        self.status = "idle"
        self.metrics: Dict[str, Any] = {}
        self.results: Dict[str, Any] = {}
    
    async def execute(self, task: Dict[str, Any], driver_instance: neo4j.AsyncDriver) -> Dict[str, Any]:
        """Execute agent task with error handling and metrics"""
        self.status = "running"
        start_time = datetime.now()
        
        try:
            result = await self._execute_task(task, driver_instance)
            self.status = "completed"
            
            execution_time = (datetime.now() - start_time).total_seconds()
            self.metrics = {
                "execution_time": execution_time,
                "records_processed": result.get("record_count", 0),
                "success_rate": 100.0
            }
            
            self.results = result
            return result
            
        except (RuntimeError, AttributeError, ValueError, OSError, asyncio.TimeoutError) as e:
            self.status = "error"
            execution_time = (datetime.now() - start_time).total_seconds()
            self.metrics = {
                "execution_time": execution_time,
                "error": str(e),
                "success_rate": 0.0
            }
            
            logger.error("Agent %s failed: %s", self.agent_type, e)
            raise HTTPException(
                status_code=500,
                detail=f"Agent {self.agent_type} execution failed: {str(e)}",
            ) from e
    
    async def _execute_task(self, task: Dict[str, Any], driver_instance: neo4j.AsyncDriver) -> Dict[str, Any]:
        """Override in subclasses"""
        raise NotImplementedError("Subclasses must implement _execute_task")

class ConnectivityAnalysisAgent(GraphAnalysisAgent):
    """Agent specialized in analyzing graph connectivity patterns"""
    
    async def _execute_task(self, task: Dict[str, Any], driver_instance: neo4j.AsyncDriver) -> Dict[str, Any]:
        #  Pareto Query: Focus on most connected nodes (20% that drive 80% of connections)
        connectivity_query = """
        MATCH (n)
        WITH n, size((n)--()) as degree
        WHERE degree > 0
        RETURN n.id as nodeId, labels(n) as labels, n as properties, degree
        ORDER BY degree DESC
        LIMIT $limit
        """
        
        results = await driver_instance.execute_query(
            connectivity_query, 
            {"limit": task.get("max_results", 50)},
            database_=NEO4J_DATABASE, 
            routing_="r"
        )
        
        connectivity_data = []
        for record in results.records:
            connectivity_data.append({
                "nodeId": record.get("nodeId"),
                "labels": record.get("labels", []),
                "properties": dict(record.get("properties", {})),
                "degree": record.get("degree"),
                "connectivity_score": record.get("degree") * 10  # Weighted scoring
            })
        
        # Apply Pareto analysis
        total_connections = sum(node["degree"] for node in connectivity_data)
        pareto_threshold = total_connections * 0.8
        
        running_sum = 0
        critical_nodes = []
        for node in connectivity_data:
            running_sum += node["degree"]
            critical_nodes.append(node)
            if running_sum >= pareto_threshold:
                break
        
        return {
            "analysis_type": "connectivity",
            "all_nodes": connectivity_data,
            "critical_nodes": critical_nodes,
            "pareto_efficiency": len(critical_nodes) / max(len(connectivity_data), 1),
            "total_connections": total_connections,
            "record_count": len(connectivity_data)
        }

class CentralityAnalysisAgent(GraphAnalysisAgent):
    """Agent specialized in centrality analysis"""
    
    async def _execute_task(self, task: Dict[str, Any], driver_instance: neo4j.AsyncDriver) -> Dict[str, Any]:
        #  Betweenness centrality approximation for key influencer nodes
        centrality_query = """
        MATCH (n)
        OPTIONAL MATCH (n)-[r1]-(m)-[r2]-(o)
        WHERE n <> o
        WITH n, count(DISTINCT m) as betweenness_approx
        RETURN n.id as nodeId, labels(n) as labels, n as properties, betweenness_approx
        ORDER BY betweenness_approx DESC
        LIMIT $limit
        """
        
        results = await driver_instance.execute_query(
            centrality_query,
            {"limit": task.get("max_results", 50)},
            database_=NEO4J_DATABASE,
            routing_="r"
        )
        
        centrality_data = []
        for record in results.records:
            centrality_data.append({
                "nodeId": record.get("nodeId"),
                "labels": record.get("labels", []),
                "properties": dict(record.get("properties", {})),
                "centrality_score": record.get("betweenness_approx", 0),
                "influence_level": "high" if record.get("betweenness_approx", 0) > 5 else "medium" if record.get("betweenness_approx", 0) > 2 else "low"
            })
        
        # Pareto analysis for top influencers
        high_influence = [node for node in centrality_data if node["influence_level"] == "high"]
        
        return {
            "analysis_type": "centrality",
            "all_nodes": centrality_data,
            "key_influencers": high_influence,
            "influence_distribution": {
                "high": len([n for n in centrality_data if n["influence_level"] == "high"]),
                "medium": len([n for n in centrality_data if n["influence_level"] == "medium"]),
                "low": len([n for n in centrality_data if n["influence_level"] == "low"])
            },
            "record_count": len(centrality_data)
        }

class ClusteringAnalysisAgent(GraphAnalysisAgent):
    """Agent specialized in community detection and clustering"""
    
    async def _execute_task(self, task: Dict[str, Any], driver_instance: neo4j.AsyncDriver) -> Dict[str, Any]:
        #  Simple clustering based on shared relationships
        clustering_query = """
        MATCH (n)-[r]-(m)
        WITH n, collect(DISTINCT type(r)) as relationship_types, count(r) as connections
        RETURN n.id as nodeId, labels(n) as labels, n as properties, 
               relationship_types, connections,
               size(relationship_types) as cluster_diversity
        ORDER BY cluster_diversity DESC, connections DESC
        LIMIT $limit
        """
        
        results = await driver_instance.execute_query(
            clustering_query,
            {"limit": task.get("max_results", 50)},
            database_=NEO4J_DATABASE,
            routing_="r"
        )
        
        clustering_data = []
        relationship_clusters: Dict[str, List[Dict[str, Any]]] = {}
        
        for record in results.records:
            node_data = {
                "nodeId": record.get("nodeId"),
                "labels": record.get("labels", []),
                "properties": dict(record.get("properties", {})),
                "relationship_types": record.get("relationship_types", []),
                "connections": record.get("connections", 0),
                "cluster_diversity": record.get("cluster_diversity", 0)
            }
            clustering_data.append(node_data)
            
            # Group by relationship patterns for clustering
            pattern_key = "_".join(sorted(node_data["relationship_types"]))
            if pattern_key not in relationship_clusters:
                relationship_clusters[pattern_key] = []
            relationship_clusters[pattern_key].append(node_data)
        
        # Identify major clusters (Pareto principle)
        cluster_sizes = [(pattern, len(nodes)) for pattern, nodes in relationship_clusters.items()]
        cluster_sizes.sort(key=lambda x: x[1], reverse=True)
        
        total_nodes = sum(size for _, size in cluster_sizes)
        major_clusters = []
        nodes_covered = 0
        
        for pattern, size in cluster_sizes:
            major_clusters.append({
                "pattern": pattern,
                "size": size,
                "percentage": (size / total_nodes) * 100,
                "nodes": relationship_clusters[pattern]
            })
            nodes_covered += size
            if nodes_covered >= total_nodes * 0.8:  # Pareto: 80% coverage
                break
        
        return {
            "analysis_type": "clustering",
            "all_nodes": clustering_data,
            "major_clusters": major_clusters,
            "cluster_summary": {
                "total_clusters": len(relationship_clusters),
                "major_cluster_count": len(major_clusters),
                "coverage_percentage": (nodes_covered / total_nodes) * 100
            },
            "record_count": len(clustering_data)
        }

class InsightGenerationAgent(GraphAnalysisAgent):
    """Agent specialized in generating actionable insights from graph analysis"""
    
    async def _execute_task(self, task: Dict[str, Any], driver_instance: neo4j.AsyncDriver) -> Dict[str, Any]:
        analysis_results = task.get("analysis_results", {})
        
        insights = []
        recommendations = []
        
        # Generate insights from connectivity analysis
        if "connectivity" in analysis_results:
            connectivity_data = analysis_results["connectivity"]
            critical_nodes = connectivity_data.get("critical_nodes", [])
            
            if critical_nodes:
                top_node = critical_nodes[0]
                insights.append({
                    "type": "connectivity",
                    "title": "High-Impact Connectivity Hub Identified",
                    "description": f"Node {top_node['nodeId']} has {top_node['degree']} connections, making it a critical hub",
                    "priority": "high",
                    "impact_score": top_node.get("connectivity_score", 0)
                })
                
                recommendations.append(f"Monitor node {top_node['nodeId']} closely as it's a critical connectivity hub")
        
        # Generate insights from centrality analysis
        if "centrality" in analysis_results:
            centrality_data = analysis_results["centrality"]
            key_influencers = centrality_data.get("key_influencers", [])
            
            if key_influencers:
                insights.append({
                    "type": "centrality",
                    "title": "Key Influencer Nodes Detected",
                    "description": f"Found {len(key_influencers)} high-influence nodes that control information flow",
                    "priority": "high",
                    "nodes": [node["nodeId"] for node in key_influencers]
                })
                
                recommendations.append("Focus optimization efforts on key influencer nodes for maximum impact")
        
        # Generate insights from clustering analysis
        if "clustering" in analysis_results:
            clustering_data = analysis_results["clustering"]
            major_clusters = clustering_data.get("major_clusters", [])
            
            if major_clusters:
                largest_cluster = major_clusters[0]
                insights.append({
                    "type": "clustering",
                    "title": "Dominant Relationship Pattern Identified",
                    "description": f"Pattern '{largest_cluster['pattern']}' represents {largest_cluster['percentage']:.1f}% of relationships",
                    "priority": "medium",
                    "cluster_info": largest_cluster
                })
                
                recommendations.append("Optimize processes around dominant relationship patterns for efficiency")
        
        # Generate Pareto-based recommendations
        pareto_recommendations = self._generate_pareto_recommendations(analysis_results)
        recommendations.extend(pareto_recommendations)
        
        return {
            "analysis_type": "insights",
            "insights": insights,
            "recommendations": recommendations,
            "insight_count": len(insights),
            "pareto_efficiency": self._calculate_pareto_efficiency(analysis_results),
            "record_count": len(insights)
        }
    
    def _generate_pareto_recommendations(self, analysis_results: Dict[str, Any]) -> List[str]:
        recommendations = []
        
        # Extract Pareto efficiencies from different analyses
        efficiencies = []
        for _analysis_type, data in analysis_results.items():
            if isinstance(data, dict) and "pareto_efficiency" in data:
                efficiencies.append(data["pareto_efficiency"])
        
        if efficiencies:
            avg_efficiency = sum(efficiencies) / len(efficiencies)
            if avg_efficiency > 0.8:
                recommendations.append("Excellent Pareto efficiency detected - current focus areas are well-optimized")
            else:
                recommendations.append("Consider rebalancing focus areas to improve Pareto efficiency")
        
        return recommendations
    
    def _calculate_pareto_efficiency(self, analysis_results: Dict[str, Any]) -> float:
        """Calculate overall Pareto efficiency across all analyses"""
        efficiencies = []
        for _analysis_type, data in analysis_results.items():
            if isinstance(data, dict) and "pareto_efficiency" in data:
                efficiencies.append(data["pareto_efficiency"])
        
        return sum(efficiencies) / len(efficiencies) if efficiencies else 0.0

#  MULTI-AGENT ORCHESTRATOR
class AgenticGraphOrchestrator:
    """Orchestrates multiple graph analysis agents using various coordination patterns"""
    
    def __init__(self):
        self.agents = {
            "connectivity": ConnectivityAnalysisAgent,
            "centrality": CentralityAnalysisAgent,
            "clustering": ClusteringAnalysisAgent,
            "insights": InsightGenerationAgent
        }
        self.active_orchestrations = {}
    
    async def orchestrate_analysis(
        self, 
        orchestration_request: MultiAgentOrchestrationRequest,
        driver_instance: neo4j.AsyncDriver
    ) -> Dict[str, Any]:
        """Execute multi-agent orchestration based on coordination type"""
        
        orchestration_id = str(uuid.uuid4())
        self.active_orchestrations[orchestration_id] = {
            "status": "running",
            "agents": {},
            "results": {},
            "start_time": datetime.now()
        }
        
        try:
            if orchestration_request.orchestration_type == "parallel":
                results = await self._execute_parallel(orchestration_request.agents, driver_instance)
            elif orchestration_request.orchestration_type == "sequential":
                results = await self._execute_sequential(orchestration_request.agents, driver_instance)
            elif orchestration_request.orchestration_type == "conditional":
                results = await self._execute_conditional(orchestration_request.agents, driver_instance, orchestration_request.coordination_rules)
            else:
                raise ValueError(f"Unknown orchestration type: {orchestration_request.orchestration_type}")
            
            # Generate insights from combined results
            if "insights" not in results:
                insights_agent = InsightGenerationAgent("insights")
                insights_result = await insights_agent.execute(
                    {"analysis_results": results}, 
                    driver_instance
                )
                results["insights"] = insights_result
            
            self.active_orchestrations[orchestration_id]["status"] = "completed"
            self.active_orchestrations[orchestration_id]["results"] = results
            
            return {
                "orchestration_id": orchestration_id,
                "status": "completed",
                "results": results,
                "execution_time": (datetime.now() - self.active_orchestrations[orchestration_id]["start_time"]).total_seconds()
            }
            
        except Exception as e:
            self.active_orchestrations[orchestration_id]["status"] = "error"
            self.active_orchestrations[orchestration_id]["error"] = str(e)
            raise
    
    async def _execute_parallel(self, agent_requests: List[AgentTaskRequest], driver_instance: neo4j.AsyncDriver) -> Dict[str, Any]:
        """Execute agents in parallel for maximum speed"""
        tasks = []
        agent_instances = {}
        
        for request in agent_requests:
            if request.agent_type in self.agents:
                agent_class = self.agents[request.agent_type]
                agent_instance = agent_class(request.agent_type, request.task_config)
                agent_instances[request.agent_type] = agent_instance
                
                task = agent_instance.execute(request.task_config, driver_instance)
                tasks.append((request.agent_type, task))
        
        # Execute all tasks in parallel
        results: Dict[str, Any] = {}
        completed_tasks = await asyncio.gather(*[task for _, task in tasks], return_exceptions=True)
        
        for i, (agent_type, _) in enumerate(tasks):
            result = completed_tasks[i]
            if isinstance(result, Exception):
                results[agent_type] = {"error": str(result), "status": "error"}
            else:
                results[agent_type] = result
        
        return results
    
    async def _execute_sequential(self, agent_requests: List[AgentTaskRequest], driver_instance: neo4j.AsyncDriver) -> Dict[str, Any]:
        """Execute agents sequentially, passing results between them"""
        results: Dict[str, Any] = {}
        context: Dict[str, Any] = {}
        
        for request in agent_requests:
            if request.agent_type in self.agents:
                agent_class = self.agents[request.agent_type]
                agent_instance = agent_class(request.agent_type, request.task_config)
                
                # Merge previous results into context
                task_config = {**request.task_config, **context}
                
                result = await agent_instance.execute(task_config, driver_instance)
                results[request.agent_type] = result
                
                # Update context for next agent
                context[f"{request.agent_type}_results"] = result
        
        return results
    
    async def _execute_conditional(
        self, 
        agent_requests: List[AgentTaskRequest], 
        driver_instance: neo4j.AsyncDriver,
        coordination_rules: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute agents based on conditional logic"""
        results: Dict[str, Any] = {}
        context: Dict[str, Any] = {}
        
        for request in agent_requests:
            # Check if agent should execute based on conditions
            should_execute = self._evaluate_execution_condition(
                request.agent_type, 
                coordination_rules, 
                context
            )
            
            if should_execute and request.agent_type in self.agents:
                agent_class = self.agents[request.agent_type]
                agent_instance = agent_class(request.agent_type, request.task_config)
                
                task_config = {**request.task_config, **context}
                result = await agent_instance.execute(task_config, driver_instance)
                results[request.agent_type] = result
                context[f"{request.agent_type}_results"] = result
            else:
                results[request.agent_type] = {"status": "skipped", "reason": "Condition not met"}
        
        return results
    
    def _evaluate_execution_condition(self, agent_type: str, rules: Dict[str, Any], context: Dict[str, Any]) -> bool:
        """Evaluate whether an agent should execute based on coordination rules"""
        if agent_type not in rules:
            return True  # Default to execute if no rules specified
        
        rule = rules[agent_type]
        if "depends_on" in rule:
            dependency = rule["depends_on"]
            if f"{dependency}_results" not in context:
                return False
            
            # Check if dependency results meet threshold
            if "threshold" in rule:
                dep_results = context[f"{dependency}_results"]
                if isinstance(dep_results, dict) and "record_count" in dep_results:
                    return dep_results["record_count"] >= rule["threshold"]
        
        return True

#  AGENT FACTORY
def create_agent(agent_type: str, config: Optional[Dict[str, Any]] = None) -> GraphAnalysisAgent:
    """Factory function to create agents"""
    agent_classes = {
        "connectivity": ConnectivityAnalysisAgent,
        "centrality": CentralityAnalysisAgent,
        "clustering": ClusteringAnalysisAgent,
        "insights": InsightGenerationAgent
    }
    
    if agent_type not in agent_classes:
        raise ValueError(f"Unknown agent type: {agent_type}")
    
    return agent_classes[agent_type](agent_type, config)

#  FASTAPI ENDPOINTS

@router.post("/analyze", response_model=GraphInsightsResponse)
async def execute_graph_analysis(
    request: GraphAnalysisRequest,
    driver_instance: neo4j.AsyncDriver = Depends(get_driver)
):
    """Execute intelligent graph analysis using Pareto-optimized agents"""
    
    try:
        # Create orchestration request based on focus areas
        agent_requests = []
        for focus_area in request.focus_areas:
            if focus_area in ["connectivity", "centrality", "clustering"]:
                agent_requests.append(AgentTaskRequest(
                    agent_type=focus_area,
                    task_config={
                        "max_results": request.max_results,
                        "pareto_optimization": request.pareto_optimization,
                        **request.agent_config
                    }
                ))
        
        # Add insights agent
        agent_requests.append(AgentTaskRequest(
            agent_type="insights",
            task_config={"generate_recommendations": True}
        ))
        
        orchestration_request = MultiAgentOrchestrationRequest(
            orchestration_type="sequential",
            agents=agent_requests
        )
        
        # Execute orchestration
        orchestrator = AgenticGraphOrchestrator()
        orchestration_result = await orchestrator.orchestrate_analysis(
            orchestration_request, 
            driver_instance
        )
        
        # Format response
        results = orchestration_result["results"]
        
        # Aggregate insights
        all_insights = []
        pareto_ranking = []
        critical_nodes = []
        recommendations = []
        agent_status = {}
        
        for agent_type, result in results.items():
            if isinstance(result, dict) and "error" not in result:
                agent_status[agent_type] = "completed"
                
                if agent_type == "insights":
                    all_insights.extend(result.get("insights", []))
                    recommendations.extend(result.get("recommendations", []))
                else:
                    # Extract critical nodes and rankings
                    if "critical_nodes" in result:
                        critical_nodes.extend(result["critical_nodes"])
                    if "all_nodes" in result:
                        for node in result["all_nodes"]:
                            pareto_ranking.append({
                                "analysis_type": agent_type,
                                "node": node,
                                "score": node.get("connectivity_score", node.get("centrality_score", node.get("cluster_diversity", 0)))
                            })
            else:
                agent_status[agent_type] = "error"
        
        # Sort pareto ranking by score
        pareto_ranking.sort(key=lambda x: x["score"], reverse=True)
        
        return GraphInsightsResponse(
            insights=all_insights,
            pareto_ranking=pareto_ranking[:request.max_results],
            critical_nodes=critical_nodes[:request.max_results],
            recommendations=recommendations,
            execution_metrics={
                "total_execution_time": orchestration_result["execution_time"],
                "agents_executed": len(agent_requests),
                "pareto_efficiency": results.get("insights", {}).get("pareto_efficiency", 0.0)
            },
            agent_status=agent_status
        )
        
    except (RuntimeError, AttributeError, ValueError, OSError, asyncio.TimeoutError, KeyError, TypeError) as e:
        logger.error("Graph analysis failed: %s", e)
        raise HTTPException(status_code=500, detail=f"Graph analysis failed: {str(e)}") from e

@router.post("/orchestrate")
async def execute_multi_agent_orchestration(
    request: MultiAgentOrchestrationRequest,
    driver_instance: neo4j.AsyncDriver = Depends(get_driver)
):
    """Execute custom multi-agent orchestration"""
    
    try:
        orchestrator = AgenticGraphOrchestrator()
        result = await orchestrator.orchestrate_analysis(request, driver_instance)
        return result
        
    except (RuntimeError, AttributeError, ValueError, OSError, KeyError) as e:
        logger.error("Multi-agent orchestration failed: %s", e)
        raise HTTPException(status_code=500, detail=f"Orchestration failed: {str(e)}") from e

@router.post("/agent/execute")
async def execute_single_agent(
    request: AgentTaskRequest,
    driver_instance: neo4j.AsyncDriver = Depends(get_driver)
):
    """Execute a single specialized agent"""
    
    try:
        agent = create_agent(request.agent_type, request.task_config)
        result = await agent.execute(request.task_config, driver_instance)
        
        return {
            "agent_type": request.agent_type,
            "status": agent.status,
            "metrics": agent.metrics,
            "results": result
        }
        
    except (RuntimeError, AttributeError, ValueError, OSError, KeyError, asyncio.TimeoutError) as e:
        logger.error("Single agent execution failed: %s", e)
        raise HTTPException(status_code=500, detail=f"Agent execution failed: {str(e)}") from e

@router.get("/agents/status")
async def get_agent_status():
    """Get status of available agents"""
    
    return {
        "available_agents": list(AgenticGraphOrchestrator().agents.keys()),
        "orchestration_types": ["parallel", "sequential", "conditional"],
        "focus_areas": ["connectivity", "centrality", "clustering", "insights"],
        "pareto_optimization": True
    }
