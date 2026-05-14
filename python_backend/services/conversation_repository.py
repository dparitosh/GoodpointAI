"""
Conversation Repository Service - Database persistence layer for conversations

Provides CRUD operations for conversation history with PostgreSQL persistence.
Enables multi-turn context management and conversation recovery.
"""

from typing import List, Optional
from datetime import datetime
import logging
import json

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from sqlalchemy import desc, and_

from models.conversation_models import (
    Conversation,
    ConversationORM,
    ChatMessage,
    ConversationMetadata,
    MessageRole,
    ConversationStatus,
)
from core.db_session import SessionLocal

logger = logging.getLogger(__name__)


class ConversationRepository:
    """Database repository for conversation persistence"""
    
    def __init__(self, session: Optional[Session] = None):
        """Initialize repository with optional session (defaults to SessionLocal)"""
        self.session = session or SessionLocal()
    
    def create(self, conversation: Conversation) -> Conversation:
        """
        Create a new conversation in the database
        
        Args:
            conversation: Pydantic Conversation model
            
        Returns:
            Created conversation with timestamps
            
        Raises:
            ValueError: If conversation_id already exists
        """
        try:
            # Check if conversation already exists
            existing = self.session.query(ConversationORM).filter(
                ConversationORM.conversation_id == conversation.conversation_id
            ).first()
            
            if existing:
                raise ValueError(f"Conversation '{conversation.conversation_id}' already exists")
            
            # Convert Pydantic to ORM
            orm_obj = ConversationORM.from_pydantic(conversation)
            orm_obj.created_at = datetime.utcnow()
            orm_obj.updated_at = datetime.utcnow()
            
            self.session.add(orm_obj)
            self.session.commit()
            self.session.refresh(orm_obj)
            
            logger.info(f"Created conversation: {conversation.conversation_id} (session: {conversation.session_id})")
            
            return orm_obj.to_pydantic()
            
        except IntegrityError as e:
            self.session.rollback()
            logger.error(f"Integrity error creating conversation: {str(e)}")
            raise ValueError(f"Conversation creation failed: {str(e)}")
        except Exception as e:
            self.session.rollback()
            logger.error(f"Error creating conversation: {str(e)}")
            raise
    
    def read(self, conversation_id: str) -> Optional[Conversation]:
        """
        Retrieve a conversation by ID
        
        Args:
            conversation_id: Conversation identifier
            
        Returns:
            Conversation or None if not found
        """
        try:
            orm_obj = self.session.query(ConversationORM).filter(
                ConversationORM.conversation_id == conversation_id
            ).first()
            
            if not orm_obj:
                return None
            
            return orm_obj.to_pydantic()
            
        except Exception as e:
            logger.error(f"Error reading conversation {conversation_id}: {str(e)}")
            raise
    
    def read_by_session(self, session_id: str) -> Optional[Conversation]:
        """
        Retrieve the active conversation for a session
        
        Args:
            session_id: Session identifier
            
        Returns:
            Most recent active conversation or None
        """
        try:
            orm_obj = self.session.query(ConversationORM).filter(
                and_(
                    ConversationORM.session_id == session_id,
                    ConversationORM.status == ConversationStatus.ACTIVE.value
                )
            ).order_by(desc(ConversationORM.created_at)).first()
            
            if not orm_obj:
                return None
            
            return orm_obj.to_pydantic()
            
        except Exception as e:
            logger.error(f"Error reading conversation for session {session_id}: {str(e)}")
            raise
    
    def add_message(
        self,
        conversation_id: str,
        message: ChatMessage
    ) -> Conversation:
        """
        Add a message to an existing conversation
        
        Args:
            conversation_id: Conversation identifier
            message: Message to add
            
        Returns:
            Updated conversation
            
        Raises:
            ValueError: If conversation not found
        """
        try:
            orm_obj = self.session.query(ConversationORM).filter(
                ConversationORM.conversation_id == conversation_id
            ).first()
            
            if not orm_obj:
                raise ValueError(f"Conversation not found: {conversation_id}")
            
            # Parse existing messages
            existing_messages = []
            if orm_obj.messages_json:
                try:
                    data = json.loads(orm_obj.messages_json)
                    existing_messages = [ChatMessage(**item) for item in data]
                except (json.JSONDecodeError, ValueError):
                    pass
            
            # Add new message with timestamp
            if not message.timestamp:
                message.timestamp = datetime.utcnow()
            
            existing_messages.append(message)
            
            # Update ORM
            orm_obj.messages_json = json.dumps([m.dict() for m in existing_messages])
            orm_obj.message_count = len(existing_messages)
            orm_obj.updated_at = datetime.utcnow()
            
            # Update last user message timestamp
            if message.role == MessageRole.USER:
                orm_obj.last_user_message_at = message.timestamp
            
            self.session.commit()
            self.session.refresh(orm_obj)
            
            logger.debug(f"Added message to conversation {conversation_id} (total: {orm_obj.message_count})")
            
            return orm_obj.to_pydantic()
            
        except Exception as e:
            self.session.rollback()
            logger.error(f"Error adding message to conversation {conversation_id}: {str(e)}")
            raise
    
    def list(
        self,
        skip: int = 0,
        limit: int = 100,
        session_id: Optional[str] = None,
        workflow_id: Optional[str] = None,
        status: Optional[ConversationStatus] = None,
        active_only: bool = True,
    ) -> List[Conversation]:
        """
        List conversations with optional filtering
        
        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return
            session_id: Filter by session
            workflow_id: Filter by workflow
            status: Filter by status
            active_only: Filter to active conversations only
            
        Returns:
            List of conversations
        """
        try:
            query = self.session.query(ConversationORM)
            
            if session_id:
                query = query.filter(ConversationORM.session_id == session_id)
            
            if workflow_id:
                query = query.filter(ConversationORM.workflow_id == workflow_id)
            
            if status:
                query = query.filter(ConversationORM.status == status.value)
            elif active_only:
                query = query.filter(ConversationORM.status == ConversationStatus.ACTIVE.value)
            
            # Order by most recently updated
            orm_objects = query.order_by(
                desc(ConversationORM.updated_at)
            ).offset(skip).limit(limit).all()
            
            return [obj.to_pydantic() for obj in orm_objects]
            
        except Exception as e:
            logger.error(f"Error listing conversations: {str(e)}")
            raise
    
    def update(
        self,
        conversation_id: str,
        updates: dict
    ) -> Optional[Conversation]:
        """
        Update conversation metadata
        
        Args:
            conversation_id: Conversation identifier
            updates: Dictionary of fields to update (workflow_id, step, tags, etc.)
            
        Returns:
            Updated conversation or None if not found
        """
        try:
            orm_obj = self.session.query(ConversationORM).filter(
                ConversationORM.conversation_id == conversation_id
            ).first()
            
            if not orm_obj:
                raise ValueError(f"Conversation not found: {conversation_id}")
            
            # Map updates to ORM fields
            if 'workflow_id' in updates:
                orm_obj.workflow_id = updates['workflow_id']
            if 'step' in updates:
                orm_obj.migration_step = updates['step']
            if 'source_id' in updates:
                orm_obj.source_id = updates['source_id']
            if 'file_count' in updates:
                orm_obj.file_count = updates['file_count']
            if 'tags' in updates:
                orm_obj.tags_json = json.dumps(updates['tags'])
            if 'metadata' in updates:
                orm_obj.metadata_json = json.dumps(updates['metadata'])
            if 'status' in updates:
                orm_obj.status = updates['status'].value if isinstance(updates['status'], ConversationStatus) else updates['status']
            
            orm_obj.updated_at = datetime.utcnow()
            self.session.commit()
            self.session.refresh(orm_obj)
            
            logger.info(f"Updated conversation: {conversation_id}")
            
            return orm_obj.to_pydantic()
            
        except Exception as e:
            self.session.rollback()
            logger.error(f"Error updating conversation {conversation_id}: {str(e)}")
            raise
    
    def archive(self, conversation_id: str) -> Optional[Conversation]:
        """
        Archive a conversation (soft delete)
        
        Args:
            conversation_id: Conversation identifier
            
        Returns:
            Archived conversation or None if not found
        """
        try:
            orm_obj = self.session.query(ConversationORM).filter(
                ConversationORM.conversation_id == conversation_id
            ).first()
            
            if not orm_obj:
                return None
            
            orm_obj.status = ConversationStatus.ARCHIVED.value
            orm_obj.is_archived = True
            orm_obj.updated_at = datetime.utcnow()
            
            self.session.commit()
            self.session.refresh(orm_obj)
            
            logger.info(f"Archived conversation: {conversation_id}")
            
            return orm_obj.to_pydantic()
            
        except Exception as e:
            self.session.rollback()
            logger.error(f"Error archiving conversation {conversation_id}: {str(e)}")
            raise
    
    def delete(self, conversation_id: str) -> bool:
        """
        Delete a conversation (hard delete)
        
        Args:
            conversation_id: Conversation identifier
            
        Returns:
            True if deleted, False if not found
        """
        try:
            orm_obj = self.session.query(ConversationORM).filter(
                ConversationORM.conversation_id == conversation_id
            ).first()
            
            if not orm_obj:
                return False
            
            self.session.delete(orm_obj)
            self.session.commit()
            
            logger.info(f"Deleted conversation: {conversation_id}")
            
            return True
            
        except Exception as e:
            self.session.rollback()
            logger.error(f"Error deleting conversation {conversation_id}: {str(e)}")
            raise
    
    def get_count(
        self,
        session_id: Optional[str] = None,
        workflow_id: Optional[str] = None,
        active_only: bool = True
    ) -> int:
        """Get total count of conversations"""
        try:
            query = self.session.query(ConversationORM)
            
            if session_id:
                query = query.filter(ConversationORM.session_id == session_id)
            
            if workflow_id:
                query = query.filter(ConversationORM.workflow_id == workflow_id)
            
            if active_only:
                query = query.filter(ConversationORM.status == ConversationStatus.ACTIVE.value)
            
            return query.count()
            
        except Exception as e:
            logger.error(f"Error getting conversation count: {str(e)}")
            raise
    
    def close(self):
        """Close database session"""
        if self.session:
            self.session.close()
    
    def __enter__(self):
        """Context manager support"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()
