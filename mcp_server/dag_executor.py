import asyncio
import logging
from datetime import datetime
from typing import Dict

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
        pending_subtasks = {st.id: st for st in task.subtasks}
        completed_ids = set()

        start_time = datetime.now()

        while pending_subtasks:
            # Find subtasks whose dependencies are completely met
            ready_subtasks = []
            for st in pending_subtasks.values():
                if all(dep in completed_ids for dep in st.dependencies):
                    ready_subtasks.append(st)

            if not ready_subtasks and pending_subtasks:
                task.status = TaskStatus.FAILED
                return AgenticTaskResult(
                    task_id=task.id,
                    agent_id="system",
                    agent_type="system", # type: ignore
                    success=False,
                    error="Deadlock detected in DAG subtask execution. Cycle or missing dependency.",
                    execution_time=(datetime.now() - start_time).total_seconds()
                )
            
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
                    logger.error("Subtask %s crashed: %s", st.id, result)
                    st.status = TaskStatus.FAILED
                else:
                    st.status = TaskStatus.COMPLETED if result.success else TaskStatus.FAILED
                    subtask_results[st.id] = result
                
                # Cleanup and progress
                if st.status == TaskStatus.COMPLETED:
                    completed_ids.add(st.id)
                del pending_subtasks[st.id]
        
        # Check overall success
        all_success = all(st.status == TaskStatus.COMPLETED for st in task.subtasks)
        task.status = TaskStatus.COMPLETED if all_success else TaskStatus.FAILED

        return AgenticTaskResult(
            task_id=task.id,
            agent_id="system_orchestrator",
            agent_type="etl_orchestrator", # type: ignore
            success=all_success,
            result={"subtask_results": [r.model_dump() if hasattr(r, "model_dump") else str(r) for r in subtask_results.values()]},
            execution_time=(datetime.now() - start_time).total_seconds()
        )

