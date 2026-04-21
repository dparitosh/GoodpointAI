"""
 Self-Healing Orchestration Service
======================================

Resilient task execution with:
- Exponential backoff retry
- Circuit breaker pattern
- Intelligent routing
- Validation checkpoints
- Recovery strategies
- Dead letter queue

Integrations:
- Neo4j for lineage tracking
- OpenSearch for failure pattern analysis
- Ollama for error classification
"""

# pyright: reportUnusedImport=false
# pylint: disable=broad-exception-caught,broad-exception-raised,unused-argument,unused-import

import logging
import asyncio
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from enum import Enum
from dataclasses import dataclass, field
from fastapi import APIRouter, Depends, HTTPException, Query, Response, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import neo4j
import json

from .dependencies import get_driver

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/self-healing", tags=["Self-Healing Orchestration"])


# ============= MODELS =============

class TaskStatus(str, Enum):
    IDLE = "idle"
    EXECUTING = "executing"
    RETRYING = "retrying"
    VALIDATING = "validating"
    CIRCUIT_OPEN = "circuit_open"
    CIRCUIT_HALF_OPEN = "circuit_half_open"
    ROUTING_ALTERNATIVE = "routing_alternative"
    RECOVERING = "recovering"
    COMPLETED = "completed"
    FAILED = "failed"
    DEAD_LETTER = "dead_letter"


class ErrorSeverity(str, Enum):
    TRANSIENT = "transient"
    MEDIUM = "medium"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


@dataclass
class RetryConfig:
    max_attempts: int = 5
    initial_delay_ms: int = 1000
    max_delay_ms: int = 30000
    backoff_multiplier: float = 2.0
    jitter_factor: float = 0.1


@dataclass
class CircuitBreakerConfig:
    failure_threshold: int = 5
    success_threshold: int = 2
    timeout_ms: int = 60000
    half_open_max_attempts: int = 3


@dataclass
class Route:
    id: str
    name: str
    endpoint: str
    priority: int
    success_rate: float = 1.0
    avg_latency_ms: float = 0
    enabled: bool = True


@dataclass
class ErrorClassification:
    severity: ErrorSeverity
    retryable: bool
    category: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class TaskExecutionRequest(BaseModel):
    task_id: str
    workflow_id: str
    operation: str
    payload: Dict[str, Any]
    primary_route_id: str
    alternative_route_ids: List[str] = []
    validation_rules: List[str] = []
    retry_config: Optional[Dict[str, Any]] = None


class TaskExecutionResponse(BaseModel):
    task_id: str
    status: TaskStatus
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    retry_count: int = 0
    execution_time_ms: int = 0
    route_used: Optional[str] = None


# ============= SELF-HEALING SERVICE =============

class SelfHealingService:
    """Service for resilient task execution with self-healing capabilities"""
    
    def __init__(self, driver: neo4j.AsyncDriver):
        self.driver = driver
        self.retry_config = RetryConfig()
        self.circuit_breaker_config = CircuitBreakerConfig()
        self.circuit_states: Dict[str, Dict] = {}
        self.routes: Dict[str, Route] = {}
        self.dlq_messages: List[Dict] = []
        
    def calculate_backoff(self, attempt: int) -> float:
        """Calculate exponential backoff with jitter"""
        exponential_delay = min(
            self.retry_config.initial_delay_ms * (self.retry_config.backoff_multiplier ** attempt),
            self.retry_config.max_delay_ms
        )

        # Deterministic backoff: do not introduce randomness.
        return exponential_delay / 1000  # Convert to seconds
    
    def classify_error(self, error: Exception) -> ErrorClassification:
        """Classify error severity and determine if retryable"""
        error_message = str(error).lower()
        
        if any(keyword in error_message for keyword in ['network', 'timeout', 'connection']):
            return ErrorClassification(
                severity=ErrorSeverity.TRANSIENT,
                retryable=True,
                category="NETWORK"
            )
        elif any(keyword in error_message for keyword in ['auth', 'permission', 'forbidden']):
            return ErrorClassification(
                severity=ErrorSeverity.CRITICAL,
                retryable=False,
                category="AUTH"
            )
        elif any(keyword in error_message for keyword in ['schema', 'validation', 'invalid']):
            return ErrorClassification(
                severity=ErrorSeverity.MEDIUM,
                retryable=False,
                category="VALIDATION"
            )
        elif any(keyword in error_message for keyword in ['data quality', 'corrupt']):
            return ErrorClassification(
                severity=ErrorSeverity.MEDIUM,
                retryable=True,
                category="DATA_QUALITY"
            )
        else:
            return ErrorClassification(
                severity=ErrorSeverity.UNKNOWN,
                retryable=True,
                category="UNKNOWN"
            )
    
    def get_circuit_state(self, route_id: str) -> Dict:
        """Get or initialize circuit breaker state for a route"""
        if route_id not in self.circuit_states:
            self.circuit_states[route_id] = {
                "consecutive_failures": 0,
                "consecutive_successes": 0,
                "state": "closed",  # closed, open, half_open
                "open_time": None,
                "half_open_attempts": 0
            }
        return self.circuit_states[route_id]
    
    def should_trip_circuit_breaker(self, route_id: str) -> bool:
        """Check if circuit breaker should trip"""
        state = self.get_circuit_state(route_id)
        return state["consecutive_failures"] >= self.circuit_breaker_config.failure_threshold
    
    def can_attempt_half_open(self, route_id: str) -> bool:
        """Check if circuit can transition to half-open"""
        state = self.get_circuit_state(route_id)
        if state["state"] != "open" or state["open_time"] is None:
            return False
        
        elapsed_ms = (time.time() - state["open_time"]) * 1000
        return elapsed_ms >= self.circuit_breaker_config.timeout_ms
    
    def select_alternative_route(self, primary_route_id: str, alternative_ids: List[str]) -> Optional[Route]:
        """Select best alternative route based on success rate and latency"""
        available_routes = []
        
        for route_id in alternative_ids:
            if route_id == primary_route_id:
                continue
            
            state = self.get_circuit_state(route_id)
            if state["state"] == "open":
                if not self.can_attempt_half_open(route_id):
                    continue
            
            route = self.routes.get(route_id)
            if route and route.enabled:
                available_routes.append(route)
        
        if not available_routes:
            return None
        
        # Sort by success rate (descending) and latency (ascending)
        available_routes.sort(key=lambda r: (-r.success_rate, r.avg_latency_ms))
        return available_routes[0]
    
    async def validate_result(self, result: Dict, validation_rules: List[str]) -> bool:
        """Run validation checkpoints on execution result"""
        if not validation_rules:
            return True
        
        for rule in validation_rules:
            if rule == "not_empty":
                if not result or len(result) == 0:
                    return False
            elif rule == "has_data":
                if "data" not in result or result["data"] is None:
                    return False
            elif rule == "no_errors":
                if "error" in result and result["error"]:
                    return False
        
        return True
    
    async def execute_task(
        self,
        task_id: str,
        _workflow_id: str,
        _operation: str,
        _payload: Dict[str, Any],
        route: Route
    ) -> Dict[str, Any]:
        """Execute task on specified route.

        Execution is intentionally not implemented here to avoid mock/demo behavior.
        A real implementation should call an actual workflow runner / integration connector.
        """
        _ = task_id, _workflow_id, _operation, _payload, route
        raise NotImplementedError("Self-healing task execution is not configured")
    
    async def execute_with_self_healing(
        self,
        task_id: str,
        workflow_id: str,
        operation: str,
        payload: Dict,
        primary_route_id: str,
        alternative_route_ids: List[str],
        validation_rules: List[str]
    ) -> TaskExecutionResponse:
        """
        Execute task with self-healing orchestration:
        1. Try primary route with retries
        2. If circuit breaker trips, try alternative routes
        3. Validate results at checkpoints
        4. Move to DLQ if all attempts fail
        """
        start_time = time.time()
        retry_count = 0
        error_history = []
        
        # Get primary route
        current_route = self.routes.get(primary_route_id)
        if not current_route:
            current_route = Route(
                id=primary_route_id,
                name="Primary Route",
                endpoint="http://primary-service",
                priority=1
            )
            self.routes[primary_route_id] = current_route
        
        # Main execution loop
        while retry_count < self.retry_config.max_attempts:
            try:
                # Check circuit breaker state
                circuit_state = self.get_circuit_state(current_route.id)
                
                if circuit_state["state"] == "open":
                    if self.can_attempt_half_open(current_route.id):
                        logger.info("Circuit breaker for %s transitioning to HALF-OPEN", current_route.id)
                        circuit_state["state"] = "half_open"
                        circuit_state["half_open_attempts"] = 0
                    else:
                        logger.warning("Circuit breaker OPEN for %s, trying alternative route", current_route.id)
                        alternative_route = self.select_alternative_route(current_route.id, alternative_route_ids)
                        
                        if alternative_route:
                            current_route = alternative_route
                            retry_count = 0  # Reset retry count for new route
                        else:
                            raise RuntimeError("No alternative routes available and circuit is open")
                
                # Execute task
                logger.info(
                    "Executing task %s on route %s (attempt %s)",
                    task_id,
                    current_route.id,
                    retry_count + 1,
                )
                result = await self.execute_task(task_id, workflow_id, operation, payload, current_route)
                
                # Validate result
                is_valid = await self.validate_result(result, validation_rules)
                
                if not is_valid:
                    raise ValueError("Validation failed: Result does not meet validation criteria")
                
                # Success - update circuit breaker
                circuit_state["consecutive_successes"] += 1
                circuit_state["consecutive_failures"] = 0
                
                if circuit_state["state"] == "half_open":
                    if circuit_state["consecutive_successes"] >= self.circuit_breaker_config.success_threshold:
                        logger.info("Circuit breaker for %s CLOSED (recovered)", current_route.id)
                        circuit_state["state"] = "closed"
                        circuit_state["open_time"] = None
                
                execution_time_ms = int((time.time() - start_time) * 1000)
                
                # Track lineage
                await self._create_lineage_node(task_id, workflow_id, current_route.id, "success")
                
                return TaskExecutionResponse(
                    task_id=task_id,
                    status=TaskStatus.COMPLETED,
                    result=result,
                    retry_count=retry_count,
                    execution_time_ms=execution_time_ms,
                    route_used=current_route.id
                )
                
            except (TimeoutError, RuntimeError, ValueError, TypeError, OSError) as error:
                retry_count += 1
                classification = self.classify_error(error)
                error_history.append({
                    "attempt": retry_count,
                    "error": str(error),
                    "classification": classification.__dict__,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                })
                
                # Update circuit breaker
                circuit_state = self.get_circuit_state(current_route.id)
                circuit_state["consecutive_failures"] += 1
                circuit_state["consecutive_successes"] = 0
                
                # Check if should trip circuit breaker
                if self.should_trip_circuit_breaker(current_route.id):
                    logger.error("Circuit breaker TRIPPED for %s", current_route.id)
                    circuit_state["state"] = "open"
                    circuit_state["open_time"] = time.time()
                    
                    # Try alternative route
                    alternative_route = self.select_alternative_route(current_route.id, alternative_route_ids)
                    if alternative_route:
                        logger.info("Switching to alternative route: %s", alternative_route.id)
                        current_route = alternative_route
                        retry_count = 0  # Reset retry count for new route
                        continue
                
                # Check if error is retryable
                if not classification.retryable:
                    logger.error("Non-retryable error: %s", error)
                    break
                
                # Check if retries exhausted
                if retry_count >= self.retry_config.max_attempts:
                    logger.error("Retry attempts exhausted for task %s", task_id)
                    break
                
                # Calculate backoff and retry
                backoff_delay = self.calculate_backoff(retry_count)
                logger.info(
                    "Retrying task %s after %.2fs (attempt %s/%s)",
                    task_id,
                    backoff_delay,
                    retry_count + 1,
                    self.retry_config.max_attempts,
                )
                await asyncio.sleep(backoff_delay)
        
        # All retries failed - send to DLQ
        execution_time_ms = int((time.time() - start_time) * 1000)
        
        dlq_message = {
            "task_id": task_id,
            "workflow_id": workflow_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "error_history": error_history,
            "retry_count": retry_count
        }
        self.dlq_messages.append(dlq_message)
        
        logger.error(
            "Task %s moved to Dead Letter Queue after %s attempts",
            task_id,
            retry_count,
        )
        
        # Track lineage
        await self._create_lineage_node(task_id, workflow_id, current_route.id, "failed")
        
        return TaskExecutionResponse(
            task_id=task_id,
            status=TaskStatus.DEAD_LETTER,
            error=f"Task failed after {retry_count} retry attempts",
            retry_count=retry_count,
            execution_time_ms=execution_time_ms,
            route_used=current_route.id
        )
    
    async def _create_lineage_node(self, task_id: str, workflow_id: str, route_id: str, status: str):
        """Create lineage node for task execution"""
        try:
            query = """
            CREATE (n:LineageNode {
                id: $task_id,
                type: 'AGENT',
                name: $name,
                properties: $properties,
                created_at: $created_at,
                workflow_id: $workflow_id
            })
            RETURN n
            """
            
            async with self.driver.session(database="neo4j") as session:
                await session.run(
                    query,
                    task_id=task_id,
                    name=f"Self-Healing Task: {task_id}",
                    properties=json.dumps({"route_id": route_id, "status": status}),
                    created_at=datetime.now(timezone.utc).isoformat(),
                    workflow_id=workflow_id
                )
        except (neo4j.exceptions.Neo4jError, RuntimeError, ValueError, TypeError, OSError) as e:
            logger.warning("Failed to create lineage node: %s", e)


# ============= API ENDPOINTS =============


@router.websocket("/ws/monitor")
async def websocket_monitor(websocket: WebSocket):
    """WebSocket stream for the Self-Healing monitor UI.

    Sends a small, UI-compatible metrics payload periodically.
    Tolerates missing Neo4j driver: still streams in-memory orchestration state
    so the dashboard can show "Connected" even when Neo4j is offline.
    """
    await websocket.accept()
    driver = getattr(websocket.app.state, "driver", None)
    try:
        while True:
            service = SelfHealingService(driver) if driver is not None else None
            dlq_messages = list(getattr(service, "dlq_messages", []) or []) if service else []
            circuit_states = getattr(service, "circuit_states", {}) if service else {}
            payload = {
                "total_tasks": 0,
                "successful_tasks": 0,
                "failed_tasks": 0,
                "retried_tasks": 0,
                "circuit_breaker_trips": 0,
                "alternative_routes_used": 0,
                "dlq_messages": len(dlq_messages),
                "active_tasks": 0,
                "dlq_size": len(dlq_messages),
                "circuit_breakers": len(circuit_states),
            }
            await websocket.send_json(payload)
            await asyncio.sleep(2)
    except WebSocketDisconnect:
        return
    except (RuntimeError, ValueError, TypeError, OSError) as e:
        logger.warning(
            "Self-healing monitor websocket error: %s: %s",
            type(e).__name__,
            e,
        )
        try:
            await websocket.close(code=1011)
        except (RuntimeError, OSError):
            pass
        return

@router.post("/execute", summary="Execute Task with Self-Healing")
async def execute_task(
    request: Dict[str, Any],
    driver: neo4j.AsyncDriver = Depends(get_driver)
):
    """Execute a task with self-healing orchestration.

    This endpoint is currently disabled (no simulated execution). It returns a
    stable, UI-friendly error payload so the frontend can show the feature as unavailable.
    """
    _ = driver

    task_id = None
    workflow_id = None
    if isinstance(request, dict):
        task_id = request.get("task_id")
        workflow_id = request.get("workflow_id")

    payload = {
        "task_id": task_id or "",
        "status": TaskStatus.FAILED,
        "result": None,
        "error": "Self-healing execution is unavailable: integrate a real workflow runner/connector. No simulated execution is provided.",
        "retry_count": 0,
        "execution_time_ms": 0,
        "route_used": None,
        "workflow_id": workflow_id or "",
    }
    return JSONResponse(status_code=501, content=payload)


@router.get("/circuit-breaker/{route_id}", summary="Get Circuit Breaker Status")
async def get_circuit_breaker_status(
    route_id: str,
    driver: neo4j.AsyncDriver = Depends(get_driver)
):
    """Get circuit breaker status for a specific route"""
    service = SelfHealingService(driver)
    state = service.get_circuit_state(route_id)
    
    return {
        "route_id": route_id,
        "circuit_state": state["state"],
        "consecutive_failures": state["consecutive_failures"],
        "consecutive_successes": state["consecutive_successes"],
        "open_time": state["open_time"],
        "can_attempt_half_open": service.can_attempt_half_open(route_id) if state["state"] == "open" else None
    }


@router.get("/circuit-breakers", summary="List Circuit Breakers (UI Alias)")
async def list_circuit_breakers(
    response: Response,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    driver: neo4j.AsyncDriver = Depends(get_driver),
):
    """UI-friendly alias that returns a list instead of requiring a route_id."""
    service = SelfHealingService(driver)

    breakers = []
    for route_id, state in service.circuit_states.items():
        breakers.append({
            "route_id": route_id,
            "state": state.get("state", "closed"),
            "failure_count": state.get("consecutive_failures", 0),
            "success_count": state.get("consecutive_successes", 0),
            "last_failure": None,
        })
    response.headers["X-Total-Count"] = str(len(breakers))
    return breakers[skip : skip + limit]


@router.get("/dlq", summary="Get Dead Letter Queue Messages")
async def get_dead_letter_queue(
    response: Response,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    driver: neo4j.AsyncDriver = Depends(get_driver),
):
    """Get all messages in the Dead Letter Queue"""
    service = SelfHealingService(driver)

    response.headers["X-Total-Count"] = str(len(service.dlq_messages))
    messages = service.dlq_messages[skip : skip + limit]
    return {
        "total_messages": len(messages),
        "messages": messages,
    }


@router.get("/dead-letter-queue", summary="Get Dead Letter Queue Messages (UI Alias)")
async def get_dead_letter_queue_alias(
    response: Response,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    driver: neo4j.AsyncDriver = Depends(get_driver),
):
    """UI-friendly alias that returns the DLQ messages list directly."""
    service = SelfHealingService(driver)
    response.headers["X-Total-Count"] = str(len(service.dlq_messages))
    return service.dlq_messages[skip : skip + limit]


@router.post("/dlq/{task_id}/retry", summary="Retry DLQ Message")
async def retry_dlq_message(
    task_id: str,
    driver: neo4j.AsyncDriver = Depends(get_driver)
):
    """Retry a failed task from Dead Letter Queue"""
    service = SelfHealingService(driver)
    
    # Find message in DLQ
    message = next((msg for msg in service.dlq_messages if msg["task_id"] == task_id), None)
    
    if not message:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found in DLQ")
    
    # Remove from DLQ and retry
    service.dlq_messages.remove(message)
    
    return {
        "message": f"Task {task_id} removed from DLQ and will be retried",
        "task_id": task_id
    }


@router.post("/dead-letter-queue/{task_id}/retry", summary="Retry DLQ Message (UI Alias)")
async def retry_dlq_message_alias(
    task_id: str,
    driver: neo4j.AsyncDriver = Depends(get_driver)
):
    return await retry_dlq_message(task_id=task_id, driver=driver)


@router.delete("/dead-letter-queue/{task_id}", summary="Remove DLQ Message (UI Alias)")
async def delete_dlq_message_alias(
    task_id: str,
    driver: neo4j.AsyncDriver = Depends(get_driver)
):
    """UI-friendly delete route to remove a DLQ message."""
    service = SelfHealingService(driver)
    message = next((msg for msg in service.dlq_messages if msg.get("task_id") == task_id), None)
    if not message:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found in DLQ")
    service.dlq_messages.remove(message)
    return {"message": f"Task {task_id} removed from DLQ", "task_id": task_id}


@router.get("/metrics", summary="Get Self-Healing Metrics")
async def get_metrics(
    driver: neo4j.AsyncDriver = Depends(get_driver)
):
    """Get self-healing orchestration metrics"""
    service = SelfHealingService(driver)
    
    circuit_breaker_summary = {}
    for route_id, state in service.circuit_states.items():
        circuit_breaker_summary[route_id] = {
            "state": state["state"],
            "failures": state["consecutive_failures"],
            "successes": state["consecutive_successes"]
        }
    
    return {
        "total_routes": len(service.routes),
        "circuit_breakers": circuit_breaker_summary,
        "dlq_messages": len(service.dlq_messages),
        "config": {
            "max_retries": service.retry_config.max_attempts,
            "circuit_breaker_threshold": service.circuit_breaker_config.failure_threshold,
            "circuit_timeout_ms": service.circuit_breaker_config.timeout_ms
        }
    }
