"""
Tests for Advanced Migration Features
"""
import pytest
import asyncio
from services.advanced_migration_engine import (
    AdvancedMigrationEngine,
    MigrationState,
    MigrationEvent,
    MigrationSession
)


@pytest.fixture
def engine():
    """Create a migration engine instance for testing"""
    return AdvancedMigrationEngine()


@pytest.fixture
def sample_sources():
    """Sample source configurations"""
    return [
        {
            "type": "postgresql",
            "host": "source-db.example.com",
            "port": 5432,
            "database": "source_db"
        }
    ]


@pytest.fixture
def sample_target():
    """Sample target configuration"""
    return {
        "type": "postgresql",
        "host": "target-db.example.com",
        "port": 5432,
        "database": "target_db"
    }


@pytest.mark.asyncio
async def test_create_session(engine, sample_sources, sample_target):
    """Test creating a migration session"""
    session = await engine.create_session(
        sources=sample_sources,
        target=sample_target,
        strategy="incremental"
    )
    
    assert session is not None
    assert session.session_id is not None
    assert session.state == MigrationState.IDLE
    assert session.progress == 0.0
    assert len(session.sources) == 1
    assert session.strategy == "incremental"


@pytest.mark.asyncio
async def test_start_migration(engine, sample_sources, sample_target):
    """Test starting a migration"""
    session = await engine.create_session(
        sources=sample_sources,
        target=sample_target,
        strategy="incremental"
    )
    
    result = await engine.start_migration(session.session_id)
    assert result is True
    
    # Wait a bit for state transition
    await asyncio.sleep(0.5)
    
    # Should have transitioned from IDLE
    assert session.state != MigrationState.IDLE


@pytest.mark.asyncio
async def test_session_to_dict(engine, sample_sources, sample_target):
    """Test session serialization"""
    session = await engine.create_session(
        sources=sample_sources,
        target=sample_target,
        strategy="full"
    )
    
    session_dict = session.to_dict()
    
    assert "session_id" in session_dict
    assert "state" in session_dict
    assert "progress" in session_dict
    assert "quality_score" in session_dict
    assert "errors" in session_dict
    assert session_dict["strategy"] == "full"


@pytest.mark.asyncio
async def test_pause_resume_migration(engine, sample_sources, sample_target):
    """Test pause and resume functionality"""
    session = await engine.create_session(
        sources=sample_sources,
        target=sample_target,
        strategy="incremental"
    )
    
    await engine.start_migration(session.session_id)
    
    # Wait for migration to start
    await asyncio.sleep(1)
    
    # Pause the migration
    result = await engine.handle_event(session.session_id, MigrationEvent.PAUSE)
    assert result["status"] == "success"
    await asyncio.sleep(0.2)
    assert session.state == MigrationState.PAUSED
    
    # Resume the migration
    result = await engine.handle_event(session.session_id, MigrationEvent.RESUME)
    assert result["status"] == "success"


@pytest.mark.asyncio
async def test_cancel_migration(engine, sample_sources, sample_target):
    """Test cancelling a migration"""
    session = await engine.create_session(
        sources=sample_sources,
        target=sample_target,
        strategy="incremental"
    )
    
    await engine.start_migration(session.session_id)
    await asyncio.sleep(1)
    
    # Cancel the migration
    result = await engine.handle_event(session.session_id, MigrationEvent.CANCEL)
    assert result["status"] == "success"
    await asyncio.sleep(0.2)
    assert session.state == MigrationState.CANCELLED


@pytest.mark.asyncio
async def test_get_history(engine, sample_sources, sample_target):
    """Test retrieving migration history"""
    session = await engine.create_session(
        sources=sample_sources,
        target=sample_target,
        strategy="incremental"
    )
    
    await engine.start_migration(session.session_id)
    await asyncio.sleep(2)
    
    history = engine.get_history(session.session_id)
    
    assert isinstance(history, list)
    assert len(history) > 0
    
    # Check history entry structure
    for entry in history:
        assert "timestamp" in entry
        assert "from_state" in entry
        assert "to_state" in entry
        assert "event" in entry


@pytest.mark.asyncio
async def test_invalid_session(engine):
    """Test operations on non-existent session"""
    result = await engine.handle_event("non-existent-id", MigrationEvent.PAUSE)
    assert result["status"] == "error"
    
    session = engine.get_session("non-existent-id")
    assert session is None
    
    history = engine.get_history("non-existent-id")
    assert history == []


@pytest.mark.asyncio
async def test_migration_progress_tracking(engine, sample_sources, sample_target):
    """Test that progress is tracked during migration"""
    session = await engine.create_session(
        sources=sample_sources,
        target=sample_target,
        strategy="incremental"
    )
    
    await engine.start_migration(session.session_id)
    
    # Initial progress
    initial_progress = session.progress
    
    # Wait for some progress
    await asyncio.sleep(3)
    
    # Progress should have increased
    assert session.progress > initial_progress
    assert 0.0 <= session.progress <= 100.0


@pytest.mark.asyncio
async def test_state_transitions(engine, sample_sources, sample_target):
    """Test that state transitions follow expected pattern"""
    session = await engine.create_session(
        sources=sample_sources,
        target=sample_target,
        strategy="incremental"
    )
    
    # Should start in IDLE
    assert session.state == MigrationState.IDLE
    
    await engine.start_migration(session.session_id)
    await asyncio.sleep(0.5)
    
    # Should transition to INITIALIZING or beyond
    assert session.state != MigrationState.IDLE
    
    # Wait for completion or several transitions
    await asyncio.sleep(5)
    
    # Should have made progress through states
    history = engine.get_history(session.session_id)
    states_visited = set(entry["to_state"] for entry in history)
    
    # Should have visited multiple states
    assert len(states_visited) > 1
