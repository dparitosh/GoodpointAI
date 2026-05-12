import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, Set

from .models import AgenticTask, TaskStatus, AgenticTaskResult
from .orchestrator import AgenticOrchestrator

logger = logging.getLogger(__name__)

class DAGExecutor:
    """Modular Task Executor for handling DAG Subtasks via the Orchestrator."""
    def __init__(self, orchestrator: AgenticOrchestrator):
        self.orchestrator = orchestrator

    async def execute_task_with_subtasks(self, task: AgenticTask) -> AgenticTaskResult:
        if not hasattr(task, "subtasks") or not task.subtasks:
            # Fallback to normal execution if no subtasks defined
            return await self.orchestrator.execute_task(task)
        
        logger.info("Executing composite task %s with %s subtasks", task.id, len(task.subtasks))
        task.status = TaskStatus.IN_PROGRESS

        # Track state
        subtask_results: Dict[str, AgenticTaskResult] = {}
        failed_results: Dict[str, str] = {}   # subtask_id → error message
        pending_subtasks = {st.id: st for st in task.subtasks}
        completed_ids: Set[str] = set()
        failed_ids: Set[str] = set()

        start_time = datetime.now(timezone.utc)

        while pending_subtasks:
            # Find subtasks whose dependencies are all completed (not failed/blocked)
            ready_subtasks = []
            blocked_subtasks = []
            for st in list(pending_subtasks.values()):
                # If any dependency has failed, this subtask is permanently blocked
                if any(dep in failed_ids for dep in st.dependencies):
                    blocked_subtasks.append(st)
                elif all(dep in completed_ids for dep in st.dependencies):
                    ready_subtasks.append(st)

            # Mark blocked subtasks as FAILED and remove from pending
            for st in blocked_subtasks:
                st.status = TaskStatus.FAILED
                failed_ids.add(st.id)
                failed_results[st.id] = f"Blocked: dependency failed ({[d for d in st.dependencies if d in failed_ids]})"
                del pending_subtasks[st.id]
                logger.warning("Subtask %s blocked due to failed dependency", st.id)

            # After clearing blocked subtasks, re-check for deadlock
            if not ready_subtasks and pending_subtasks:
                # True deadlock: remaining subtasks have unresolvable dependencies
                task.status = TaskStatus.FAILED
                return AgenticTaskResult(
                    task_id=task.id,
                    agent_id="system",
                    agent_type="system",
                    success=False,
                    error="DAG deadlock: unresolvable dependency cycle in subtask graph.",
                    execution_time=(datetime.now(timezone.utc) - start_time).total_seconds(),
                )
            
            if not ready_subtasks:
                # All remaining subtasks were blocked and cleared; exit loop
                break

            # Execute ready subtasks concurrently
            exec_coroutines = []
            for st in ready_subtasks:
                st.status = TaskStatus.IN_PROGRESS
                # Convert subtask to full task for orchestrator routing
                sub_agent_task = AgenticTask(
                    id=st.id,
                    type=st.type,
                    required_capabilities=st.required_capabilities,
                    payload=st.payload,
                    priority=st.priority
                )
                exec_coroutines.append(self.orchestrator.execute_task(sub_agent_task))
            
            results = await asyncio.gather(*exec_coroutines, return_exceptions=True)

            for i, result in enumerate(results):
                st = ready_subtasks[i]
                if isinstance(result, BaseException):
                    logger.error("Subtask %s raised exception: %s", st.id, result)
                    st.status = TaskStatus.FAILED
                    failed_ids.add(st.id)
                    failed_results[st.id] = str(result)
                elif not result.success:
                    st.status = TaskStatus.FAILED
                    failed_ids.add(st.id)
                    failed_results[st.id] = result.error or "subtask failed"
                    subtask_results[st.id] = result  # store failed result for inspection
                else:
                    st.status = TaskStatus.COMPLETED
                    completed_ids.add(st.id)
                    subtask_results[st.id] = result

                del pending_subtasks[st.id]
        
        # Check overall success: all subtasks must have completed (not failed/blocked)
        all_success = all(st.status == TaskStatus.COMPLETED for st in task.subtasks)
        task.status = TaskStatus.COMPLETED if all_success else TaskStatus.FAILED

        # Include both successful and failed subtask results
        result_list = []
        for st in task.subtasks:
            if st.id in subtask_results:
                entry = subtask_results[st.id].model_dump() if hasattr(subtask_results[st.id], "model_dump") else str(subtask_results[st.id])
            elif st.id in failed_results:
                entry = {"subtask_id": st.id, "status": "failed", "error": failed_results[st.id]}
            else:
                entry = {"subtask_id": st.id, "status": str(st.status)}
            result_list.append(entry)

        return AgenticTaskResult(
            task_id=task.id,
            agent_id="system_orchestrator",
            agent_type="system",
            success=all_success,
            result={
                "subtask_results": result_list,
                "completed_count": len(completed_ids),
                "failed_count": len(failed_ids),
            },
            execution_time=(datetime.now(timezone.utc) - start_time).total_seconds(),
        )

