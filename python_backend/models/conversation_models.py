"""
Conversation Models - Pydantic and SQLAlchemy ORM models for chat history persistence

Stores conversation sessions with multi-turn message history.
Enables context-aware conversations and workflow integration.
"""

from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any
from enum import Enum
from datetime import datetime

# SQLAlchemy imports
from sqlalchemy import String, Text, DateTime, Integer, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import text
from sqlalchemy.dialects.postgresql import JSON, UUID

from core.database import Base

import uuid
import json


class MessageRole(str, Enum):
    """Chat message role"""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class ConversationStatus(str, Enum):
    """Conversation status"""
    ACTIVE = "active"
    ARCHIVED = "archived"
    COMPLETED = "completed"


class ChatMessage(BaseModel):
    """Single chat message"""
    role: MessageRole
    content: str
    timestamp: Optional[datetime] = None
    metadata: Dict[str, Any] = {}

    class Config:
        example = {
            "role": "user",
            "content": "What is the data quality score?",
            "timestamp": "2026-05-14T10:30:00Z",
            "metadata": {"source": "ui"}
        }


class ConversationMetadata(BaseModel):
    """Conversation metadata"""
    workflow_id: Optional[str] = None
    step: Optional[int] = None  # Migration step (1-5)
    source_id: Optional[str] = None
    file_count: Optional[int] = None
    tags: List[str] = []
    custom: Dict[str, Any] = {}

    class Config:
        example = {
            "workflow_id": "workflow_123",
            "step": 2,
            "source_id": "plm_source",
            "file_count": 5,
            "tags": ["plm", "migration"],
            "custom": {"priority": "high"}
        }


class Conversation(BaseModel):
    """Complete conversation session"""
    conversation_id: str = Field(default_factory=lambda: f"conv_{uuid.uuid4().hex[:8]}")
    session_id: str = Field(...)
    messages: List[ChatMessage] = Field(default_factory=list)
    metadata: ConversationMetadata = Field(default_factory=ConversationMetadata)
    status: ConversationStatus = Field(default=ConversationStatus.ACTIVE)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    created_by: Optional[str] = None

    class Config:
        example = {
            "conversation_id": "conv_abc123def",
            "session_id": "session_xyz789",
            "messages": [
                {
                    "role": "user",
                    "content": "What should we do with this PLM data?",
                    "timestamp": "2026-05-14T10:30:00Z"
                },
                {
                    "role": "assistant",
                    "content": "I recommend starting with data discovery...",
                    "timestamp": "2026-05-14T10:30:05Z"
                }
            ],
            "metadata": {
                "workflow_id": "workflow_123",
                "step": 1,
                "source_id": "plm_source"
            },
            "status": "active",
            "created_at": "2026-05-14T10:30:00Z"
        }


# ============================================================
# SQLAlchemy ORM Models for Database Persistence
# ============================================================

class ConversationORM(Base):
    """
    SQLAlchemy ORM model for persistent conversation storage.
    Stores complete conversation history with messages in JSON.
    """
    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    conversation_id: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    session_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    
    # Messages stored as JSON array
    # Format: [{role, content, timestamp, metadata}, ...]
    messages_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Conversation metadata
    workflow_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    migration_step: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    source_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    file_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    tags_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON array
    metadata_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # Custom metadata
    
    # Status and timestamps
    status: Mapped[str] = mapped_column(String(20), default=ConversationStatus.ACTIVE.value, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), onupdate=text("CURRENT_TIMESTAMP"), server_default=text("CURRENT_TIMESTAMP")
    )
    created_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    
    # Audit and indexing
    message_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_user_message_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    is_archived: Mapped[bool] = mapped_column(default=False, nullable=False)
    
    __table_args__ = (
        Index('ix_conversation_session_id', 'session_id'),
        Index('ix_conversation_workflow_id', 'workflow_id'),
        Index('ix_conversation_created_at', 'created_at'),
        Index('ix_conversation_status', 'status'),
        Index('ix_conversation_is_archived', 'is_archived'),
    )

    @classmethod
    def from_pydantic(cls, conversation: 'Conversation') -> 'ConversationORM':
        """Convert Pydantic model to ORM model"""
        # Parse tags and metadata
        tags = conversation.metadata.tags if hasattr(conversation.metadata, 'tags') else []
        
        orm_obj = cls(
            conversation_id=conversation.conversation_id,
            session_id=conversation.session_id,
            messages_json=json.dumps([m.dict() for m in conversation.messages]),
            workflow_id=conversation.metadata.workflow_id,
            migration_step=conversation.metadata.step,
            source_id=conversation.metadata.source_id,
            file_count=conversation.metadata.file_count,
            tags_json=json.dumps(tags),
            metadata_json=json.dumps(conversation.metadata.custom),
            status=conversation.status.value,
            created_by=conversation.created_by,
            message_count=len(conversation.messages),
        )
        
        # Set last user message timestamp
        user_messages = [m for m in conversation.messages if m.role == MessageRole.USER]
        if user_messages:
            orm_obj.last_user_message_at = user_messages[-1].timestamp or datetime.utcnow()
        
        return orm_obj

    def to_pydantic(self) -> 'Conversation':
        """Convert ORM model back to Pydantic model"""
        def parse_messages(json_str):
            if not json_str:
                return []
            try:
                data = json.loads(json_str)
                messages = []
                for item in data:
                    # Handle timestamp parsing
                    if isinstance(item.get('timestamp'), str):
                        item['timestamp'] = datetime.fromisoformat(item['timestamp'].replace('Z', '+00:00'))
                    messages.append(ChatMessage(**item))
                return messages
            except (json.JSONDecodeError, ValueError, TypeError):
                return []

        def parse_tags(json_str):
            if not json_str:
                return []
            try:
                return json.loads(json_str)
            except (json.JSONDecodeError, ValueError):
                return []

        def parse_metadata(json_str):
            if not json_str:
                return {}
            try:
                return json.loads(json_str)
            except (json.JSONDecodeError, ValueError):
                return {}

        metadata = ConversationMetadata(
            workflow_id=self.workflow_id,
            step=self.migration_step,
            source_id=self.source_id,
            file_count=self.file_count,
            tags=parse_tags(self.tags_json),
            custom=parse_metadata(self.metadata_json)
        )

        return Conversation(
            conversation_id=self.conversation_id,
            session_id=self.session_id,
            messages=parse_messages(self.messages_json),
            metadata=metadata,
            status=ConversationStatus(self.status),
            created_at=self.created_at,
            updated_at=self.updated_at,
            created_by=self.created_by,
        )
