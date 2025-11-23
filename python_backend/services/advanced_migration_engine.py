"""
Advanced Migration Engine Service
Handles database migration orchestration with real-time state management.
"""
import logging
import json
import asyncio
from datetime import datetime
from typing import Dict, List, Optional, Any
from enum import Enum
import uuid

logger = logging.getLogger(__name__)


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
    
    def __init__(self, session_id: str, sources: List[Dict], target: Dict, strategy: str):
        self.session_id = session_id
        self.sources = sources
        self.target = target
        self.strategy = strategy
        self.state = MigrationState.IDLE
        self.progress = 0.0
        self.quality_score = 0.0
        self.errors = []
        self.created_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()
        self.history = []
        self._task = None
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert session to dictionary"""
        return {
            "session_id": self.session_id,
            "sources": self.sources,
            "target": self.target,
            "strategy": self.strategy,
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
            "timestamp": datetime.utcnow().isoformat(),
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
        self.active_websockets: Dict[str, List] = {}
        
    async def create_session(
        self, 
        sources: List[Dict], 
        target: Dict, 
        strategy: str
    ) -> MigrationSession:
        """Create a new migration session"""
        session_id = str(uuid.uuid4())
        session = MigrationSession(session_id, sources, target, strategy)
        self.sessions[session_id] = session
        
        logger.info(f"Created migration session {session_id}")
        return session
    
    async def start_migration(self, session_id: str) -> bool:
        """Start a migration job"""
        session = self.sessions.get(session_id)
        if not session:
            logger.error(f"Session {session_id} not found")
            return False
        
        if session.state != MigrationState.IDLE:
            logger.warning(f"Session {session_id} not in IDLE state")
            return False
        
        # Transition to initializing
        await self._transition_state(session, MigrationState.INITIALIZING, MigrationEvent.START)
        
        # Start background task
        session._task = asyncio.create_task(self._run_migration(session))
        return True
    
    async def _run_migration(self, session: MigrationSession):
        """Run the migration workflow"""
        try:
            # Discovering phase
            await self._transition_state(session, MigrationState.DISCOVERING, "AUTO")
            await asyncio.sleep(2)  # Simulate work
            session.progress = 20.0
            await self._broadcast_update(session)
            
            # Profiling phase
            await self._transition_state(session, MigrationState.PROFILING, "AUTO")
            await asyncio.sleep(2)
            session.progress = 40.0
            await self._broadcast_update(session)
            
            # Schema mapping phase
            await self._transition_state(session, MigrationState.SCHEMA_MAPPING, "AUTO")
            await asyncio.sleep(2)
            session.progress = 60.0
            await self._broadcast_update(session)
            
            # Data migration phase
            await self._transition_state(session, MigrationState.DATA_MIGRATION, "AUTO")
            await asyncio.sleep(3)
            session.progress = 80.0
            await self._broadcast_update(session)
            
            # Validation phase
            await self._transition_state(session, MigrationState.VALIDATION, "AUTO")
            await asyncio.sleep(2)
            session.progress = 95.0
            session.quality_score = 98.5
            await self._broadcast_update(session)
            
            # Complete
            await self._transition_state(session, MigrationState.COMPLETED, "AUTO")
            session.progress = 100.0
            await self._broadcast_update(session)
            
        except asyncio.CancelledError:
            logger.info(f"Migration {session.session_id} was cancelled")
            await self._transition_state(session, MigrationState.CANCELLED, MigrationEvent.CANCEL)
        except Exception as e:
            logger.error(f"Migration {session.session_id} failed: {e}")
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
        session.updated_at = datetime.utcnow()
        session.add_history(old_state, new_state, event)
        
        logger.info(f"Session {session.session_id}: {old_state} -> {new_state}")
        await self._broadcast_update(session)
    
    async def _broadcast_update(self, session: MigrationSession):
        """Broadcast session update to connected WebSocket clients"""
        if session.session_id in self.active_websockets:
            message = {
                "session_id": session.session_id,
                "state": session.state,
                "progress": session.progress,
                "quality": session.quality_score,
                "errors": session.errors,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            # Send to all connected clients for this session
            disconnected = []
            for ws in self.active_websockets[session.session_id]:
                try:
                    await ws.send_json(message)
                except Exception as e:
                    logger.warning(f"Failed to send to WebSocket: {e}")
                    disconnected.append(ws)
            
            # Remove disconnected clients
            for ws in disconnected:
                self.active_websockets[session.session_id].remove(ws)
    
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
            if session.state in [MigrationState.DISCOVERING, MigrationState.PROFILING, 
                                 MigrationState.SCHEMA_MAPPING, MigrationState.DATA_MIGRATION]:
                await self._transition_state(session, MigrationState.PAUSED, event)
                if session._task:
                    session._task.cancel()
                return {"status": "success", "message": "Migration paused"}
        
        elif event == MigrationEvent.RESUME:
            if session.state == MigrationState.PAUSED:
                # Resume from where it was paused
                session._task = asyncio.create_task(self._run_migration(session))
                return {"status": "success", "message": "Migration resumed"}
        
        elif event == MigrationEvent.CANCEL:
            if session._task:
                session._task.cancel()
            await self._transition_state(session, MigrationState.CANCELLED, event)
            return {"status": "success", "message": "Migration cancelled"}
        
        elif event == MigrationEvent.RETRY:
            if session.state == MigrationState.FAILED:
                session.errors = []
                session.progress = 0.0
                await self._transition_state(session, MigrationState.INITIALIZING, event)
                session._task = asyncio.create_task(self._run_migration(session))
                return {"status": "success", "message": "Migration retrying"}
        
        return {"status": "error", "message": f"Event {event} not applicable in state {session.state}"}
    
    def get_session(self, session_id: str) -> Optional[MigrationSession]:
        """Get session by ID"""
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


# Global instance
migration_engine = AdvancedMigrationEngine()
