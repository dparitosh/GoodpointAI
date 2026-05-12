import asyncio
import logging
import os
import httpx
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Tuple, TYPE_CHECKING, Callable, Awaitable, cast
import neo4j
from fastapi import HTTPException

if TYPE_CHECKING:
    from .state_manager import StateManager

from .models import (
    AgentType, AgentCapability, AgentDefinition,
    AgenticTask, AgenticTaskResult, SystemStatus, _utcnow,
)

# Per-task HTTP timeout for remote agent dispatch (seconds).
# Override via AGENT_DISPATCH_TIMEOUT_S env variable.
_AGENT_DISPATCH_TIMEOUT = float(os.getenv("AGENT_DISPATCH_TIMEOUT_S", "60"))

logger = logging.getLogger(__name__)

class AgenticOrchestrator:
    def __init__(self, state_manager: Optional['StateManager'] = None):
        self.state_manager = state_manager
        self.agents: Dict[str, AgentDefinition] = {}
        self.task_queue: List[AgenticTask] = []
        self.active_tasks: Dict[str, AgenticTask] = {}
        self.task_results: Dict[str, AgenticTaskResult] = {}
        self.chat_sessions: Dict[str, List[Dict]] = {}
        self.system_metrics: Dict[str, Any] = {
            "tasks_completed": 0,
            "tasks_failed": 0,
            "average_response_time": 0.0,
            "agent_utilization": {}
        }
        self._initialize_agents()

    async def _register_agents_state(self):
        """Register agents with state manager if available"""
        if self.state_manager and self.state_manager.is_connected:
            for agent in self.agents.values():
                await self.state_manager.register_agent(
                    agent.id,
                    agent.model_dump(mode="json"),
                    ttl=300
                )

    async def register_agent(self, agent: AgentDefinition) -> AgentDefinition:
        """Register a dynamic agent service"""
        self.agents[agent.id] = agent
        logger.info("Registered agent %s (%s) at %s", agent.id, agent.name, agent.service_url)
        
        # Persist to state manager
        if self.state_manager:
            await self.state_manager.register_agent(
                agent.id,
                agent.model_dump(mode="json"),
                ttl=300
            )
        return agent

    def _initialize_agents(self):
        """Initialize all agent definitions with their capabilities"""
        default_service_urls = {
            AgentType.DATA_DISCOVERY_AGENT: "http://127.0.0.1:8026",
            AgentType.ETL_ORCHESTRATOR: "http://127.0.0.1:8021",
            AgentType.VISUALIZATION_AGENT: "http://127.0.0.1:8022",
            AgentType.QUERY_PLANNER: "http://127.0.0.1:8023",
            AgentType.QUALITY_MONITOR: "http://127.0.0.1:8024",
            AgentType.CHAT_COORDINATOR: "http://127.0.0.1:8025",
            AgentType.DATA_ANALYST: "http://127.0.0.1:8020",
            AgentType.TASK_DECOMPOSER: "http://127.0.0.1:8027",
            AgentType.SCHEMA_CORRELATOR: "http://127.0.0.1:8028",
            AgentType.PLM_DIRECTOR: "http://127.0.0.1:8029",
            AgentType.REPORTING_AGENT: "http://127.0.0.1:8030",
            AgentType.DATA_PROFILER: "http://127.0.0.1:8031",
        }

        agent_configs = {
            AgentType.DATA_ANALYST: {
                "name": "Data Analysis Agent",
                "capabilities": [
                    AgentCapability(name="analyze_data_patterns", description="Analyze Neo4j graph patterns"),
                    AgentCapability(name="generate_insights", description="Generate analytical insights"),
                    AgentCapability(name="data_quality_assessment", description="Assess data quality"),
                    AgentCapability(name="statistical_analysis", description="Perform statistical analysis"),
                    AgentCapability(name="data_analysis", description="Analyze data patterns, distributions and statistics"),
                    AgentCapability(name="graph_query", description="Execute read-only queries against Neo4j"),
                    AgentCapability(name="sql_query", description="Execute read-only queries against Postgres"),
                    AgentCapability(name="execute_cypher_queries", description="Execute Cypher graph queries and return structured results"),
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
                    AgentCapability(name="generate_quality_reports", description="Generate quality reports"),
                    AgentCapability(name="execute_rules", description="Execute Rule Engine rule sets against data"),
                    AgentCapability(name="scan_datasource_quality", description="Run DQ scan on a registered data source by source_id"),
                ]
            },
            AgentType.DATA_DISCOVERY_AGENT: {
                "name": "Data Discovery Agent",
                "capabilities": [
                    AgentCapability(name="discover_files", description="Enumerate files in a folder-type data source"),
                    AgentCapability(name="profile_files", description="Profile file structure, row counts, column stats, null rates"),
                    AgentCapability(name="catalog_datasource", description="Build a data catalog entry for a registered data source"),
                    AgentCapability(name="scan_folder_quality", description="Run quality checks across all files in a folder data source"),
                    AgentCapability(name="infer_schema", description="Infer column types and schema from CSV/JSON/XML files"),
                ]
            },
            AgentType.ETL_ORCHESTRATOR: {
                "name": "ETL Orchestration Agent",
                "capabilities": [
                    AgentCapability(name="manage_data_pipelines", description="Manage ETL pipelines"),
                    AgentCapability(name="perform_data_discovery", description="Analyze sources, stage data, and run quality checks"),
                    AgentCapability(name="handle_data_transformations", description="Handle data transformations"),
                    AgentCapability(name="monitor_pipeline_health", description="Monitor pipeline health"),
                    AgentCapability(name="file_batch_processing", description="Discover and process thousands of files in parallel with lineage tracking"),
                ]
            },
            AgentType.CHAT_COORDINATOR: {
                "name": "Chat Coordination Agent",
                "capabilities": [
                    AgentCapability(name="process_natural_language", description="Process natural language"),
                    AgentCapability(name="coordinate_agent_responses", description="Coordinate agent responses"),
                    AgentCapability(name="manage_conversation_context", description="Manage conversation context"),
                    AgentCapability(name="route_user_requests", description="Route user requests"),
                ]
            },
            AgentType.TASK_DECOMPOSER: {
                "name": "Task Decomposer Agent",
                "capabilities": [
                    AgentCapability(name="decompose_task", description="Breaks down complex natural language requests into an executable DAG of subtasks"),
                    AgentCapability(name="decompose_goal", description="Decompose high-level goal into dependency-ordered subtasks"),
                    AgentCapability(name="build_task_dag", description="Build executable DAG from subtasks and dependencies"),
                ]
            },
            AgentType.SCHEMA_CORRELATOR: {
                "name": "Schema Correlator Agent",
                "capabilities": [
                    AgentCapability(name="correlate_schemas", description="Cross-file column frequency and type-consistency analysis across 200+ files"),
                    AgentCapability(name="detect_schema_drift", description="Detect columns with inconsistent types across files (e.g. int vs text)"),
                    AgentCapability(name="find_fk_candidates", description="Detect potential foreign-key relationships between files using naming patterns"),
                    AgentCapability(name="cluster_files_by_schema", description="Group files by Jaccard schema similarity for unified-schema migration"),
                    AgentCapability(name="generate_corpus_report", description="Generate full structured JSON profiling report with ETL, Quality, and Transformation recommendations"),
                ]
            },
            AgentType.PLM_DIRECTOR: {
                "name": "PLM Data Migration Director",
                "capabilities": [
                    AgentCapability(name="orchestrate_plm_migration", description="Run the full three-wave PLM corpus migration DAG: DataDiscovery ‖ SchemaCorrelator → QualityMonitor ‖ DataAnalyst → ETLOrchestrator"),
                    AgentCapability(name="generate_migration_plan", description="Build a phased migration plan from schema drift, FK candidates, and schema cluster analysis"),
                    AgentCapability(name="aggregate_corpus_report", description="Merge per-file profiles with cross-file corpus analysis into a unified PLMMigrationReport"),
                    AgentCapability(name="detect_cross_file_patterns", description="Identify schema drift, FK relationships, and schema clusters across 200+ heterogeneous PLM files"),
                ]
            },
            AgentType.REPORTING_AGENT: {
                "name": "PLM Reporting Agent",
                "capabilities": [
                    AgentCapability(name="generate_plm_report", description="Consume PLM profiling artifacts and emit a strict-JSON PLM Data Profiling Report (INTENT PROMPT contract)"),
                    AgentCapability(name="evaluate_dynamic_conditions", description="Re-evaluate new schema patterns, drift, unknown file types, and DQ threshold without restarting the pipeline"),
                    AgentCapability(name="update_schema_cluster", description="Add an auto-detected schema cluster and re-evaluate FK relationships"),
                    AgentCapability(name="trigger_reprofiling", description="Invoke selective re-profiling on files affected by high-severity schema drift"),
                    AgentCapability(name="route_unknown_files", description="Route files with unknown/unsupported types to ETLOrchestrator for extraction"),
                ]
            },
            AgentType.DATA_PROFILER: {
                "name": "Data Profiler Agent",
                "capabilities": [
                    AgentCapability(name="semantic_profile", description="Analyze dataset profiles and infer column semantic meaning, cross-file relationships, and entity classification with confidence scores"),
                    AgentCapability(name="infer_column_semantics", description="Column-level semantic role inference (identifier, FK, name, date, …) using cardinality + null-rate signals"),
                    AgentCapability(name="classify_entities", description="Vote-based per-file entity classification: Part / BOM / Supplier / Document / ECO / Revision"),
                    AgentCapability(name="detect_relationships", description="Detect cross-file FK/alignment relationships using column name similarity"),
                    AgentCapability(name="align_schemas", description="Group semantically equivalent column names across files into alignment clusters"),
                ]
            }
        }

        for agent_type, config in agent_configs.items():
            # Use a stable, deterministic ID so restarts don't create orphan entries.
            agent_id = f"{agent_type.value}_primary"
            self.agents[agent_id] = AgentDefinition(
                id=agent_id,
                type=agent_type,
                service_url=default_service_urls.get(agent_type),
                **config
            )

        # Per-agent asyncio locks: prevent concurrent tasks mutating the same agent status
        self._agent_locks: Dict[str, asyncio.Lock] = {
            aid: asyncio.Lock() for aid in self.agents
        }

    async def route_task_to_agent(self, task: AgenticTask) -> Optional[str]:
        """Route task to the most suitable agent."""
        suitable_agents: List[Tuple[str, float]] = []
        required = set(task.required_capabilities)

        for agent_id, agent in self.agents.items():
            if agent.status != "ready":
                continue

            agent_capabilities = [cap.name for cap in agent.capabilities]
            matching_capabilities = required & set(agent_capabilities)

            if matching_capabilities:
                # Guard against division-by-zero when required_capabilities is empty.
                if required:
                    score = len(matching_capabilities) / len(required)
                else:
                    # Any agent matches an empty capability set — score by capability count.
                    score = 1.0 / (len(agent_capabilities) + 1)
                suitable_agents.append((agent_id, score))

        if not suitable_agents:
            return None

        # Sort by capability match score
        suitable_agents.sort(key=lambda x: x[1], reverse=True)
        return suitable_agents[0][0]

    async def execute_task(self, task: AgenticTask, _driver: Optional[Any] = None) -> AgenticTaskResult:
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
        # Ensure lock exists for dynamically registered agents
        if agent_id not in self._agent_locks:
            self._agent_locks[agent_id] = asyncio.Lock()

        start_time = _utcnow()

        async with self._agent_locks[agent_id]:
            return await self._execute_with_agent(task, agent, agent_id, start_time)

    async def _execute_with_agent(
        self,
        task: AgenticTask,
        agent: AgentDefinition,
        agent_id: str,
        start_time: datetime,
    ) -> AgenticTaskResult:
        """Inner execution — called while holding the per-agent lock."""
        try:
            # Update agent status
            agent.status = "busy"
            agent.last_activity = start_time
            
            # Execute task based on type
            result = await self._execute_agent_task(task, agent)
            
            execution_time = (_utcnow() - start_time).total_seconds()
            
            # Update metrics
            self.system_metrics["tasks_completed"] += 1
            self._update_performance_metrics(agent_id, execution_time, True)
            
            task_result = AgenticTaskResult(
                task_id=task.id,
                agent_id=agent_id,
                agent_type=agent.type,
                success=True,
                result=result,
                execution_time=execution_time
            )
            self.task_results[task.id] = task_result
            
            # Save to state manager
            if self.state_manager:
                await self.state_manager.save_task_state(task.id, task_result.model_dump(mode="json"))

            return task_result
            
        except (
            neo4j.exceptions.Neo4jError,
            HTTPException,
            httpx.HTTPStatusError,
            httpx.RequestError,
            OSError,
            RuntimeError,
            ValueError,
            TypeError,
            KeyError,
        ) as e:
            execution_time = (_utcnow() - start_time).total_seconds()
            self.system_metrics["tasks_failed"] += 1
            self._update_performance_metrics(agent_id, execution_time, False)
            
            logger.error("Task execution failed for agent %s: %s", agent_id, e)
            
            error_result = AgenticTaskResult(
                task_id=task.id,
                agent_id=agent_id,
                agent_type=agent.type,
                success=False,
                error=str(e),
                execution_time=execution_time
            )
            self.task_results[task.id] = error_result
            
            # Save to state manager
            if self.state_manager:
                await self.state_manager.save_task_state(task.id, error_result.model_dump(mode="json"))

            return error_result
        finally:
            # Reset agent status
            agent.status = "ready"

    def _update_performance_metrics(self, agent_id: str, execution_time: float, success: bool):
        """Update metrics for an agent"""
        if agent_id in self.agents:
            agent = self.agents[agent_id]
            # Simple moving average for execution time
            current_avg = agent.performance_metrics.get("avg_execution_time", 0.0)
            count = agent.performance_metrics.get("task_count", 0)
            
            new_count = count + 1
            new_avg = ((current_avg * count) + execution_time) / new_count
            
            agent.performance_metrics["avg_execution_time"] = new_avg
            agent.performance_metrics["task_count"] = new_count
            
            if success:
                agent.performance_metrics["success_count"] = agent.performance_metrics.get("success_count", 0) + 1
            else:
                agent.performance_metrics["fail_count"] = agent.performance_metrics.get("fail_count", 0) + 1

    async def _execute_agent_task(self, task: AgenticTask, agent: AgentDefinition) -> Dict[str, Any]:
        """Execute specific agent task based on agent type and task type"""

        # Backward-compatible local execution hook for tests and legacy integration.
        legacy_executor_name = f"_execute_{task.type.value}_task"
        legacy_executor = cast(Optional[Callable[[AgenticTask], Any]], getattr(self, legacy_executor_name, None))
        if legacy_executor is not None:
            result = legacy_executor(task)
            if hasattr(result, "__await__"):
                return await cast(Awaitable[Dict[str, Any]], result)
            return result
        
        # Dispatch to remote agent if service_url is registered
        if agent.service_url:
            return await self._execute_remote_agent_task(task, agent)

        # STRICT MODE: No local fallback allowed.
        # All agents must be registered microservices.
        err_msg = f"Agent {agent.id} has no registered service_url. Local execution is deprecated and removed."
        logger.error(err_msg)
        raise RuntimeError(err_msg)

    async def _execute_remote_agent_task(self, task: AgenticTask, agent: AgentDefinition) -> Dict[str, Any]:
        """Execute task via remote agent service"""
        if not agent.service_url:
            raise RuntimeError("Agent has no service_url")
        # Ensure URL doesn't end with slash before appending endpoint
        base_url = agent.service_url.rstrip('/')
        url = f"{base_url}/execute"
        
        try:
            logger.info("Dispatching task %s to remote agent %s at %s", task.id, agent.id, url)
            # Construct payload matching AgentTaskRequest in agent_service
            payload = {
                "task_id": task.id,
                "task_type": task.type.value if hasattr(task.type, 'value') else str(task.type),
                "payload": task.payload,
                "priority": task.priority,
                # context is optional in AgentTaskRequest
            }
            
            async with httpx.AsyncClient(timeout=_AGENT_DISPATCH_TIMEOUT) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                
                # Parse response
                data = response.json()
                # data corresponds to AgentTaskResponse
                if data.get("status") == "completed":
                    # The result is nested in result field
                    return data.get("result", {})
                else:
                    error_msg = data.get("error", "Unknown remote error")
                    logger.error("Remote task failed with status %s: %s", data.get('status'), error_msg)
                    raise RuntimeError(f"Remote task failed: {error_msg}")
                    
        except Exception as e:  # noqa: BLE001
            logger.error("Failed to execute remote task on %s: %s", url, e)
            raise

    def get_system_status(self) -> SystemStatus:
        """Get current system status."""
        ready_agents = [a for a in self.agents.values() if a.status == "ready"]
        # System is only healthy when a majority of registered agents are ready.
        # A single ready agent out of many degraded ones is still "degraded".
        if len(self.agents) == 0:
            health = "degraded"
        elif len(ready_agents) / len(self.agents) >= 0.5:
            health = "healthy"
        else:
            health = "degraded"
        return SystemStatus(
            active_agents=list(self.agents.values()),
            task_queue_size=len(self.task_queue),
            system_health=health,
            performance_metrics=self.system_metrics
        )

