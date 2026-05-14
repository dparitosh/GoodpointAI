"""
RuleSet Repository Service - Database persistence layer for data quality rule sets

Provides CRUD operations for rule sets with PostgreSQL persistence.
Replaces in-memory storage for production deployments.
"""

from typing import List, Optional
from datetime import datetime
import logging

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from sqlalchemy import desc

from models.data_quality_rules_models import (
    DataQualityRuleSet,
    DataQualityRuleSetORM,
)
from core.db_session import SessionLocal

logger = logging.getLogger(__name__)


class RuleSetRepository:
    """Database repository for rule set persistence"""
    
    def __init__(self, session: Optional[Session] = None):
        """Initialize repository with optional session (defaults to SessionLocal)"""
        self.session = session or SessionLocal()
    
    def create(self, rule_set: DataQualityRuleSet, created_by: Optional[str] = None) -> DataQualityRuleSet:
        """
        Create a new rule set in the database
        
        Args:
            rule_set: Pydantic DataQualityRuleSet model
            created_by: Optional user identifier
            
        Returns:
            Created rule set with timestamps
            
        Raises:
            ValueError: If rule_set_id already exists
        """
        try:
            # Check if rule set already exists
            existing = self.session.query(DataQualityRuleSetORM).filter(
                DataQualityRuleSetORM.rule_set_id == rule_set.rule_set_id
            ).first()
            
            if existing:
                raise ValueError(f"Rule set with ID '{rule_set.rule_set_id}' already exists")
            
            # Convert Pydantic to ORM
            orm_obj = DataQualityRuleSetORM.from_pydantic(rule_set)
            orm_obj.created_by = created_by
            orm_obj.created_at = datetime.utcnow()
            orm_obj.updated_at = datetime.utcnow()
            
            self.session.add(orm_obj)
            self.session.commit()
            self.session.refresh(orm_obj)
            
            logger.info(f"Created rule set: {rule_set.rule_set_id} ({rule_set.name})")
            
            return orm_obj.to_pydantic()
            
        except IntegrityError as e:
            self.session.rollback()
            logger.error(f"Integrity error creating rule set: {str(e)}")
            raise ValueError(f"Rule set creation failed: {str(e)}")
        except Exception as e:
            self.session.rollback()
            logger.error(f"Error creating rule set: {str(e)}")
            raise
    
    def read(self, rule_set_id: str) -> Optional[DataQualityRuleSet]:
        """
        Retrieve a rule set by ID
        
        Args:
            rule_set_id: Rule set identifier
            
        Returns:
            Rule set or None if not found
        """
        try:
            orm_obj = self.session.query(DataQualityRuleSetORM).filter(
                DataQualityRuleSetORM.rule_set_id == rule_set_id,
                DataQualityRuleSetORM.is_active == True
            ).first()
            
            if not orm_obj:
                return None
            
            return orm_obj.to_pydantic()
            
        except Exception as e:
            logger.error(f"Error reading rule set {rule_set_id}: {str(e)}")
            raise
    
    def list(
        self,
        skip: int = 0,
        limit: int = 100,
        enabled_only: bool = False,
        created_by: Optional[str] = None,
    ) -> List[DataQualityRuleSet]:
        """
        List rule sets with optional filtering
        
        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return
            enabled_only: Filter to enabled rule sets only
            created_by: Filter by creator
            
        Returns:
            List of rule sets
        """
        try:
            query = self.session.query(DataQualityRuleSetORM).filter(
                DataQualityRuleSetORM.is_active == True
            )
            
            if enabled_only:
                query = query.filter(DataQualityRuleSetORM.enabled == True)
            
            if created_by:
                query = query.filter(DataQualityRuleSetORM.created_by == created_by)
            
            # Order by most recently created
            orm_objects = query.order_by(
                desc(DataQualityRuleSetORM.created_at)
            ).offset(skip).limit(limit).all()
            
            return [obj.to_pydantic() for obj in orm_objects]
            
        except Exception as e:
            logger.error(f"Error listing rule sets: {str(e)}")
            raise
    
    def update(
        self,
        rule_set_id: str,
        rule_set_update: DataQualityRuleSet,
        updated_by: Optional[str] = None
    ) -> Optional[DataQualityRuleSet]:
        """
        Update an existing rule set
        
        Args:
            rule_set_id: Rule set identifier
            rule_set_update: Updated rule set data
            updated_by: Optional user identifier
            
        Returns:
            Updated rule set or None if not found
            
        Raises:
            ValueError: If rule set not found
        """
        try:
            orm_obj = self.session.query(DataQualityRuleSetORM).filter(
                DataQualityRuleSetORM.rule_set_id == rule_set_id,
                DataQualityRuleSetORM.is_active == True
            ).first()
            
            if not orm_obj:
                raise ValueError(f"Rule set not found: {rule_set_id}")
            
            # Update fields
            orm_obj.name = rule_set_update.name
            orm_obj.description = rule_set_update.description
            orm_obj.enabled = rule_set_update.enabled
            
            # Update rules JSON
            import json
            orm_obj.mandatory_rules_json = json.dumps([r.dict() for r in rule_set_update.mandatory_rules])
            orm_obj.uniqueness_rules_json = json.dumps([r.dict() for r in rule_set_update.uniqueness_rules])
            orm_obj.dropdown_rules_json = json.dumps([r.dict() for r in rule_set_update.dropdown_rules])
            orm_obj.format_rules_json = json.dumps([r.dict() for r in rule_set_update.format_rules])
            orm_obj.range_rules_json = json.dumps([r.dict() for r in rule_set_update.range_rules])
            orm_obj.datatype_rules_json = json.dumps([r.dict() for r in rule_set_update.datatype_rules])
            orm_obj.cross_field_rules_json = json.dumps([r.dict() for r in rule_set_update.cross_field_rules])
            
            orm_obj.updated_at = datetime.utcnow()
            orm_obj.updated_by = updated_by
            orm_obj.version += 1
            
            self.session.commit()
            self.session.refresh(orm_obj)
            
            logger.info(f"Updated rule set: {rule_set_id} (v{orm_obj.version})")
            
            return orm_obj.to_pydantic()
            
        except Exception as e:
            self.session.rollback()
            logger.error(f"Error updating rule set {rule_set_id}: {str(e)}")
            raise
    
    def delete(self, rule_set_id: str, soft_delete: bool = True) -> bool:
        """
        Delete a rule set
        
        Args:
            rule_set_id: Rule set identifier
            soft_delete: If True, mark as inactive instead of hard delete
            
        Returns:
            True if deleted, False if not found
        """
        try:
            orm_obj = self.session.query(DataQualityRuleSetORM).filter(
                DataQualityRuleSetORM.rule_set_id == rule_set_id
            ).first()
            
            if not orm_obj:
                return False
            
            if soft_delete:
                # Soft delete - mark as inactive
                orm_obj.is_active = False
                orm_obj.updated_at = datetime.utcnow()
                self.session.commit()
                logger.info(f"Soft-deleted rule set: {rule_set_id}")
            else:
                # Hard delete
                self.session.delete(orm_obj)
                self.session.commit()
                logger.info(f"Hard-deleted rule set: {rule_set_id}")
            
            return True
            
        except Exception as e:
            self.session.rollback()
            logger.error(f"Error deleting rule set {rule_set_id}: {str(e)}")
            raise
    
    def get_count(self, enabled_only: bool = False) -> int:
        """Get total count of rule sets"""
        try:
            query = self.session.query(DataQualityRuleSetORM).filter(
                DataQualityRuleSetORM.is_active == True
            )
            
            if enabled_only:
                query = query.filter(DataQualityRuleSetORM.enabled == True)
            
            return query.count()
            
        except Exception as e:
            logger.error(f"Error getting rule set count: {str(e)}")
            raise
    
    def restore(self, rule_set_id: str) -> Optional[DataQualityRuleSet]:
        """Restore a soft-deleted rule set"""
        try:
            orm_obj = self.session.query(DataQualityRuleSetORM).filter(
                DataQualityRuleSetORM.rule_set_id == rule_set_id
            ).first()
            
            if not orm_obj:
                return None
            
            orm_obj.is_active = True
            orm_obj.updated_at = datetime.utcnow()
            
            self.session.commit()
            self.session.refresh(orm_obj)
            
            logger.info(f"Restored rule set: {rule_set_id}")
            
            return orm_obj.to_pydantic()
            
        except Exception as e:
            self.session.rollback()
            logger.error(f"Error restoring rule set {rule_set_id}: {str(e)}")
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
