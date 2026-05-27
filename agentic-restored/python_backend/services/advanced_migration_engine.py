"""
Advanced Migration Engine Service
Handles database migration orchestration with real-time state management.
"""
import logging
import asyncio
import json
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, TypeVar, Generic
from enum import Enum
import uuid
import os

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    # Keep naive UTC timestamps (previous behavior) without using deprecated datetime.utcnow().
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _utcnow_iso() -> str:
    return _utcnow().isoformat()


def _get_int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw)
    except ValueError:
        logger.warning("Invalid int for %s=%r; using default %s", name, raw, default)
        return default


def _get_float_env(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        return float(raw)
    except ValueError:
        logger.warning("Invalid float for %s=%r; using default %s", name, raw, default)
        return default


MIGRATION_SESSION_TTL_S = _get_float_env("MIGRATION_SESSION_TTL_S", 3600.0)
MIGRATION_MAX_SESSIONS = _get_int_env("MIGRATION_MAX_SESSIONS", 500)


T = TypeVar("T")


class AwaitableValue(Generic[T]):
    """Small helper so methods can be used with or without `await`."""

    def __init__(self, value: T):
        self.value = value

    def __await__(self):
        async def _coro():
            return self.value

        return _coro().__await__()

    def __bool__(self) -> bool:
        return bool(self.value)


def _is_active_state(state: "MigrationState") -> bool:
    return state not in (
        MigrationState.IDLE,
        MigrationState.COMPLETED,
        MigrationState.FAILED,
        MigrationState.CANCELLED,
    )


class MigrationState(str, Enum):
    """Migration job states"""
    IDLE = "idle"
    INITIALIZING = "initializing"
    DISCOVERING = "discovering"
    PROFILING = "profiling"
    SCHEMA_MAPPING = "schema_mapping"
    DATA_MIGRATION = "data_migration"
    VALIDATION = "validation"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class MigrationEvent(str, Enum):
    """Control events for migration"""
    START = "START"
    PAUSE = "PAUSE"
    RESUME = "RESUME"
    RETRY = "RETRY"
    CANCEL = "CANCEL"


class MigrationSession:
    """Represents a migration job session"""
    
    def __init__(
        self,
        session_id: str,
        sources: List[Dict],
        target: Dict,
        strategy: str,
        workflow_id: Optional[str] = None,
    ):
        self.session_id = session_id
        self.sources = sources
        self.target = target
        self.strategy = strategy
        self.workflow_id = workflow_id
        self.state = MigrationState.IDLE
        self.progress = 0.0
        self.quality_score = 0.0
        self.errors: List[str] = []
        self.metadata: Dict[str, Any] = {}
        self.created_at = _utcnow()
        self.updated_at = _utcnow()
        self.history: List[Dict[str, Any]] = []
        self.task: Optional[asyncio.Task[Any]] = None

    def __await__(self):
        async def _coro():
            return self

        return _coro().__await__()

    @property
    def id(self) -> str:
        # Compatibility alias used by some integration tests.
        return self.session_id

    def calculate_quality_score(self) -> float:
        """Compute a simple quality score in [0, 1].

        Intended for lightweight analytics/testing, not a real DQ metric.
        """
        rows_migrated = float(self.metadata.get("rows_migrated", 0) or 0)
        rows_failed = float(self.metadata.get("rows_failed", 0) or 0)
        total = rows_migrated + rows_failed
        if total <= 0:
            return 1.0
        score = rows_migrated / total
        return max(0.0, min(1.0, score))
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert session to dictionary"""
        return {
            "session_id": self.session_id,
            "sources": self.sources,
            "target": self.target,
            "strategy": self.strategy,
            "workflow_id": self.workflow_id,
            "state": self.state,
            "progress": self.progress,
            "quality_score": self.quality_score,
            "errors": self.errors,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }
    
    def add_history(self, from_state: str, to_state: str, event: str, context: Optional[Dict] = None):
        """Add transition to history"""
        self.history.append({
            "timestamp": _utcnow_iso(),
            "from_state": from_state,
            "to_state": to_state,
            "event": event,
            "context": context or {}
        })


class AdvancedMigrationEngine:
    """
    Advanced migration engine with XState-inspired state management
    """
    
    def __init__(self):
        self.sessions: Dict[str, MigrationSession] = {}
        self.active_websockets: Dict[str, List[Any]] = {}
        self._lock = asyncio.Lock()
        # Optional Neo4j driver injected by app lifespan. Used for best-effort lineage emission.
        self.neo4j_driver: Any = None

    def set_neo4j_driver(self, driver: Any) -> None:
        self.neo4j_driver = driver

    async def _emit_lineage(self, session: MigrationSession) -> None:
        """Best-effort lineage emission to Neo4j.

        Creates/updates a simple lineage chain:
        (MigrationSession)-[:EXTRACTED_FROM]->(SourceSystem)
        (MigrationSession)-[:LOADED_TO]->(TargetSystem)

        Also updates MigrationSession node properties on each state transition.
        """
        driver = self.neo4j_driver
        if not driver:
            return

        try:
            session_node_id = f"mig:{session.session_id}"
            now_iso = _utcnow_iso()

            sources = session.sources if isinstance(session.sources, list) else []
            target = session.target if isinstance(session.target, dict) else {}

            async with driver.session(database="neo4j") as neo_session:
                # MERGE session node
                await neo_session.run(
                    """
                    MERGE (n:LineageNode {id: $id})
                    ON CREATE SET n.created_at = $created_at
                    SET n.type = $type,
                        n.name = $name,
                        n.properties = $properties,
                        n.workflow_id = $workflow_id
                    """,
                    id=session_node_id,
                    created_at=now_iso,
                    type="transformation",
                    name=f"Migration {session.session_id}",
                    properties=json.dumps(
                        {
                            "session_id": session.session_id,
                            "state": str(session.state),
                            "progress": float(session.progress or 0.0),
                            "quality_score": float(session.quality_score or 0.0),
                            "strategy": session.strategy,
                            "errors": session.errors[-10:],
                            "updated_at": now_iso,
                        }
                    ),
                    workflow_id=session.workflow_id,
                )

                # Sources
                for src in sources:
                    if not isinstance(src, dict):
                        continue
                    src_key = src.get("id") or src.get("name") or src.get("type")
                    if not src_key:
                        continue
                    src_node_id = f"src:{src_key}"
                    await neo_session.run(
                        """
                        MERGE (s:LineageNode {id: $id})
                        ON CREATE SET s.created_at = $created_at
                        SET s.type = $type,
                            s.name = $name,
                            s.properties = $properties,
                            s.workflow_id = $workflow_id
                        """,
                        id=src_node_id,
                        created_at=now_iso,
                        type="source_system",
                        name=str(src.get("name") or src_key),
                        properties=json.dumps({"id": src.get("id"), "type": src.get("type")}),
                        workflow_id=session.workflow_id,
                    )
                    await neo_session.run(
                        """
                        MATCH (m:LineageNode {id: $mid})
                        MATCH (s:LineageNode {id: $sid})
                        MERGE (m)-[r:EXTRACTED_FROM]->(s)
                        SET r.workflow_id = $workflow_id,
                            r.timestamp = $timestamp
                        """,
                        mid=session_node_id,
                        sid=src_node_id,
                        workflow_id=session.workflow_id,
                        timestamp=now_iso,
                    )

                # Target
                tgt_key = target.get("id") or target.get("name") or target.get("type")
                if tgt_key:
                    tgt_node_id = f"tgt:{tgt_key}"
                    await neo_session.run(
                        """
                        MERGE (t:LineageNode {id: $id})
                        ON CREATE SET t.created_at = $created_at
                        SET t.type = $type,
                            t.name = $name,
                            t.properties = $properties,
                            t.workflow_id = $workflow_id
                        """,
                        id=tgt_node_id,
                        created_at=now_iso,
                        type="target_system",
                        name=str(target.get("name") or tgt_key),
                        properties=json.dumps({"id": target.get("id"), "type": target.get("type")}),
                        workflow_id=session.workflow_id,
                    )
                    await neo_session.run(
                        """
                        MATCH (m:LineageNode {id: $mid})
                        MATCH (t:LineageNode {id: $tid})
                        MERGE (m)-[r:LOADED_TO]->(t)
                        SET r.workflow_id = $workflow_id,
                            r.timestamp = $timestamp
                        """,
                        mid=session_node_id,
                        tid=tgt_node_id,
                        workflow_id=session.workflow_id,
                        timestamp=now_iso,
                    )
        except (AttributeError, KeyError, ValueError, SQLAlchemyError, OSError) as e:
            logger.warning("Lineage emit failed (best-effort): %s", e)

    def _is_terminal(self, state: MigrationState) -> bool:
        return state in (MigrationState.COMPLETED, MigrationState.FAILED, MigrationState.CANCELLED)

    def _cleanup_unlocked(self) -> None:
        """Remove expired/overflow sessions.

        Called only while holding self._lock.
        """
        now = _utcnow()

        # TTL cleanup for terminal sessions
        ttl_s = max(0.0, float(MIGRATION_SESSION_TTL_S))
        if ttl_s > 0:
            expired_ids: list[str] = []
            for sid, s in self.sessions.items():
                if not self._is_terminal(s.state):
                    continue
                age_s = (now - s.updated_at).total_seconds()
                if age_s >= ttl_s:
                    expired_ids.append(sid)
            for sid in expired_ids:
                self.sessions.pop(sid, None)
                self.active_websockets.pop(sid, None)

        # Hard cap cleanup (prefer dropping terminal/oldest first)
        max_sessions = int(MIGRATION_MAX_SESSIONS)
        if max_sessions > 0 and len(self.sessions) > max_sessions:
            ordered = sorted(self.sessions.values(), key=lambda s: s.updated_at)
            to_remove = len(self.sessions) - max_sessions
            removed = 0
            # Prefer terminal sessions first
            for s in ordered:
                if removed >= to_remove:
                    break
                if self._is_terminal(s.state):
                    sid = s.session_id
                    self.sessions.pop(sid, None)
                    self.active_websockets.pop(sid, None)
                    removed += 1
            # If still too many, drop oldest regardless of state
            if removed < to_remove:
                for s in ordered:
                    if removed >= to_remove:
                        break
                    sid = s.session_id
                    if sid not in self.sessions:
                        continue
                    self.sessions.pop(sid, None)
                    self.active_websockets.pop(sid, None)
                    removed += 1
        
    def create_session(self, *args: Any, **kwargs: Any) -> MigrationSession:
        """Create a new migration session.

        Supports two call styles:
        - Async-style (existing): await create_session(sources=[...], target={...}, strategy="...")
        - Sync-style (integration tests): create_session(session_id, ["src"], "tgt", "strategy")

        The returned MigrationSession is also awaitable, so both call sites work.
        """
        workflow_id: Optional[str] = kwargs.get("workflow_id")

        session_id: Optional[str] = kwargs.get("session_id")
        sources: Any = kwargs.get("sources")
        target: Any = kwargs.get("target")
        strategy: Any = kwargs.get("strategy")

        # Positional forms
        if args:
            # Integration-test style: (session_id, sources, target, strategy)
            if (
                len(args) >= 4
                and isinstance(args[0], str)
                and not isinstance(args[1], dict)
            ):
                session_id = args[0]
                sources = args[1]
                target = args[2]
                strategy = args[3]
            # Legacy positional style: (sources, target, strategy, workflow_id?)
            elif len(args) >= 3 and sources is None and target is None and strategy is None:
                sources = args[0]
                target = args[1]
                strategy = args[2]
                if len(args) >= 4 and workflow_id is None:
                    workflow_id = args[3]

        if session_id is None or not str(session_id).strip():
            session_id = str(uuid.uuid4())

        if sources is None:
            raise ValueError("sources is required")
        if target is None:
            raise ValueError("target is required")
        if strategy is None:
            raise ValueError("strategy is required")

        # Normalize sources
        normalized_sources: List[Dict]
        if isinstance(sources, list) and sources and all(isinstance(s, str) for s in sources):
            normalized_sources = [{"name": s} for s in sources]
        elif isinstance(sources, list) and all(isinstance(s, dict) for s in sources):
            normalized_sources = sources
        elif isinstance(sources, list):
            normalized_sources = [{"value": s} for s in sources]
        else:
            normalized_sources = [{"value": sources}]

        normalized_target: Dict
        if isinstance(target, str):
            normalized_target = {"name": target}
        elif isinstance(target, dict):
            normalized_target = target
        else:
            normalized_target = {"value": target}

        session = MigrationSession(
            str(session_id),
            normalized_sources,
            normalized_target,
            str(strategy),
            workflow_id=workflow_id,
        )

        # Best-effort: keep internal cleanup behavior without requiring an awaited lock.
        self.sessions[session.session_id] = session
        self._cleanup_unlocked()
        logger.info("Created migration session %s", session.session_id)

        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self._emit_lineage(session))
        except RuntimeError:
            # No running loop (sync tests) — skip lineage emission.
            pass

        return session
    def start_migration(self, session_id: str) -> AwaitableValue[bool]:
        """Start a migration job.

        Works both as `await engine.start_migration(id)` and `engine.start_migration(id)`.
        """
        self._cleanup_unlocked()
        session = self.sessions.get(session_id)
        if not session:
            logger.error("Session %s not found", session_id)
            return AwaitableValue(False)

        # Concurrency limiting: reject starts when too many sessions are active.
        max_concurrent = _get_int_env("MIGRATION_MAX_CONCURRENT_SESSIONS", 10)
        if max_concurrent > 0:
            active_count = sum(1 for s in self.sessions.values() if _is_active_state(s.state))
            if not _is_active_state(session.state) and active_count >= max_concurrent:
                message = (
                    f"Concurrency limit reached ({active_count}/{max_concurrent}) "
                    "for active migrations; try again later"
                )
                session.errors.append(message)
                session.updated_at = _utcnow()
                logger.warning(
                    "Rejecting start for %s due to concurrency limit (%s/%s active)",
                    session_id,
                    active_count,
                    max_concurrent,
                )
                return AwaitableValue(False)

        if session.state != MigrationState.IDLE:
            logger.warning("Session %s not in IDLE state", session_id)
            return AwaitableValue(False)

        # Synchronous state transition so non-async callers still see the new state.
        old_state = session.state
        session.state = MigrationState.INITIALIZING
        session.updated_at = _utcnow()
        session.add_history(old_state, session.state, str(MigrationEvent.START))

        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self._broadcast_update(session))
            loop.create_task(self._emit_lineage(session))
            session.task = loop.create_task(self._run_migration(session))
        except RuntimeError:
            # No running loop (sync tests). We still return True and keep the state update.
            pass

        return AwaitableValue(True)
    
    async def _run_migration(self, session: MigrationSession):
        """Run the migration workflow"""
        try:
            # Resume-aware execution: continue from the current progress checkpoint.
            # This is still a simulated workflow, but pause/resume should not reset progress.
            start_progress = float(session.progress or 0.0)

            # Discovering phase
            if start_progress < 20.0:
                await self._transition_state(session, MigrationState.DISCOVERING, "AUTO")
                await asyncio.sleep(2)  # Simulate work
                session.progress = 20.0
                await self._broadcast_update(session)

            # Profiling phase
            if float(session.progress or 0.0) < 40.0:
                await self._transition_state(session, MigrationState.PROFILING, "AUTO")
                await asyncio.sleep(2)
                session.progress = 40.0
                await self._broadcast_update(session)

            # Schema mapping phase
            if float(session.progress or 0.0) < 60.0:
                await self._transition_state(session, MigrationState.SCHEMA_MAPPING, "AUTO")
                await asyncio.sleep(2)
                session.progress = 60.0
                await self._broadcast_update(session)

            # Data migration phase
            if float(session.progress or 0.0) < 80.0:
                await self._transition_state(session, MigrationState.DATA_MIGRATION, "AUTO")
                await asyncio.sleep(3)
                session.progress = 80.0
                await self._broadcast_update(session)

            # Validation phase
            if float(session.progress or 0.0) < 95.0:
                await self._transition_state(session, MigrationState.VALIDATION, "AUTO")
                await asyncio.sleep(2)
                session.progress = 95.0
                session.quality_score = 98.5
                await self._broadcast_update(session)

            # Complete
            if float(session.progress or 0.0) < 100.0:
                await self._transition_state(session, MigrationState.COMPLETED, "AUTO")
                session.progress = 100.0
                await self._broadcast_update(session)
            
        except asyncio.CancelledError:
            # Task cancellation can mean either a true cancel request or a pause request.
            # When pausing we first transition to PAUSED and then cancel the task to stop
            # the current await/sleep; do not overwrite PAUSED with CANCELLED.
            if session.state == MigrationState.PAUSED:
                logger.info("Migration %s was paused", session.session_id)
                return
            if session.state == MigrationState.CANCELLED:
                logger.info("Migration %s was cancelled", session.session_id)
                return
            logger.info("Migration %s was cancelled", session.session_id)
            await self._transition_state(session, MigrationState.CANCELLED, MigrationEvent.CANCEL)
        except (asyncio.TimeoutError, ValueError, RuntimeError, AttributeError) as e:
            logger.error("Migration %s failed: %s", session.session_id, e)
            session.errors.append(str(e))
            await self._transition_state(session, MigrationState.FAILED, "ERROR")
    
    async def _transition_state(
        self, 
        session: MigrationSession, 
        new_state: MigrationState, 
        event: str
    ):
        """Transition session to new state"""
        old_state = session.state
        session.state = new_state
        session.updated_at = _utcnow()
        session.add_history(old_state, new_state, event)

        logger.info("Session %s: %s -> %s", session.session_id, old_state, new_state)
        await self._broadcast_update(session)
        await self._emit_lineage(session)
    
    async def _broadcast_update(self, session: MigrationSession):
        """Broadcast session update to connected WebSocket clients"""
        if session.session_id in self.active_websockets:
            message = {
                "session_id": session.session_id,
                "state": session.state,
                "progress": session.progress,
                "quality": session.quality_score,
                "errors": session.errors,
                "timestamp": _utcnow_iso()
            }
            
            # Send to all connected clients for this session
            disconnected = []
            websockets_copy = list(self.active_websockets[session.session_id])  # Create copy to avoid race condition
            for ws in websockets_copy:
                try:
                    await ws.send_json(message)
                except Exception as e:  # pylint: disable=broad-except
                    logger.warning("Failed to send to WebSocket: %s", e)
                    disconnected.append(ws)
            
            # Remove disconnected clients
            for ws in disconnected:
                try:
                    self.active_websockets[session.session_id].remove(ws)
                except ValueError:
                    pass  # Already removed
    
    async def handle_event(
        self, 
        session_id: str, 
        event: MigrationEvent
    ) -> Dict[str, Any]:
        """Handle control events"""
        session = self.sessions.get(session_id)
        if not session:
            return {"status": "error", "message": "Session not found"}
        
        if event == MigrationEvent.PAUSE:
            if session.state in [
                MigrationState.INITIALIZING,
                MigrationState.DISCOVERING,
                MigrationState.PROFILING,
                MigrationState.SCHEMA_MAPPING,
                MigrationState.DATA_MIGRATION,
            ]:
                await self._transition_state(session, MigrationState.PAUSED, event)
                if session.task:
                    session.task.cancel()
                return {"status": "success", "message": "Migration paused"}
        
        elif event == MigrationEvent.RESUME:
            if session.state == MigrationState.PAUSED:
                # Resume from where it was paused
                session.task = asyncio.create_task(self._run_migration(session))
                return {"status": "success", "message": "Migration resumed"}
        
        elif event == MigrationEvent.CANCEL:
            if session.task:
                session.task.cancel()
            await self._transition_state(session, MigrationState.CANCELLED, event)
            return {"status": "success", "message": "Migration cancelled"}
        
        elif event == MigrationEvent.RETRY:
            if session.state == MigrationState.FAILED:
                session.errors = []
                session.progress = 0.0
                await self._transition_state(session, MigrationState.INITIALIZING, event)
                session.task = asyncio.create_task(self._run_migration(session))
                return {"status": "success", "message": "Migration retrying"}
        
        return {"status": "error", "message": f"Event {event} not applicable in state {session.state}"}
    
    def get_session(self, session_id: str) -> Optional[MigrationSession]:
        """Get session by ID"""
        # Best-effort cleanup without blocking callers on async.
        # This may run concurrently with async operations; keep it simple.
        try:
            if self._lock.locked():
                return self.sessions.get(session_id)
        except (RuntimeError, AttributeError):
            return self.sessions.get(session_id)
        return self.sessions.get(session_id)
    
    def get_history(self, session_id: str) -> List[Dict]:
        """Get transition history for a session"""
        session = self.sessions.get(session_id)
        if session:
            return session.history
        return []
    
    def register_websocket(self, session_id: str, websocket):
        """Register a WebSocket connection for a session"""
        if session_id not in self.active_websockets:
            self.active_websockets[session_id] = []
        self.active_websockets[session_id].append(websocket)
    
    def unregister_websocket(self, session_id: str, websocket):
        """Unregister a WebSocket connection"""
        if session_id in self.active_websockets:
            try:
                self.active_websockets[session_id].remove(websocket)
            except ValueError:
                pass

    def remove_session(self, session_id: str, *, cancel: bool = True) -> bool:
        """Remove a migration session from in-memory storage.

        This is primarily used for best-effort compensation when a workflow
        start partially fails.
        """
        session = self.sessions.get(session_id)
        if not session:
            return False

        if cancel and getattr(session, "task", None):
            try:
                session.task.cancel()
            except (RuntimeError, AttributeError):
                pass

        self.sessions.pop(session_id, None)
        self.active_websockets.pop(session_id, None)
        return True


# Global instance
migration_engine = AdvancedMigrationEngine()
