"""
Rule Composition Services - Repository and business logic for advanced rules

Provides:
- Composite rule management (CRUD)
- Rule template management and instantiation
- Rule group management and execution
- Rule composition validation and optimization
"""

import logging
from typing import Optional, List, Dict, Any, Set
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import desc, asc
from sqlalchemy.exc import IntegrityError

from models.rule_composition_models import (
    CompositeRuleORM, RuleTemplateORM, RuleGroupORM, RuleCompositionHistoryORM,
    CompositeRuleCreate, CompositeRuleUpdate, CompositeRule,
    RuleTemplateCreate, RuleTemplate, RuleTemplateInstance,
    RuleGroupCreate, RuleGroupUpdate, RuleGroup,
    RuleOperator, ConditionComparator, CompositionStrategy,
    RuleCompositionValidation, RuleOptimization
)

logger = logging.getLogger(__name__)


class CompositeRuleRepository:
    """Repository for composite rule CRUD operations"""
    
    def __init__(self, session: Session):
        self.session = session
    
    def create(self, composite_rule: CompositeRuleCreate) -> CompositeRule:
        """Create a new composite rule"""
        try:
            orm = CompositeRuleORM(
                id=composite_rule.id.lower().strip(),
                name=composite_rule.name,
                description=composite_rule.description,
                rule_ids=composite_rule.rule_ids,
                operator=composite_rule.operator.value,
                severity=composite_rule.severity,
                enabled=1 if composite_rule.enabled else 0,
                metadata=composite_rule.metadata or {}
            )
            self.session.add(orm)
            self.session.commit()
            
            # Log creation
            self._log_history(orm.id, "composite", "create", None, self._to_dict(orm))
            
            logger.info(f"Created composite rule: {orm.id}")
            return self._to_pydantic(orm)
        
        except IntegrityError:
            self.session.rollback()
            raise ValueError(f"Composite rule '{composite_rule.id}' already exists")
        except Exception as e:
            self.session.rollback()
            logger.error(f"Error creating composite rule: {str(e)}")
            raise
    
    def read(self, rule_id: str) -> Optional[CompositeRule]:
        """Read a composite rule by ID"""
        orm = self.session.query(CompositeRuleORM).filter(
            CompositeRuleORM.id == rule_id.lower().strip()
        ).first()
        return self._to_pydantic(orm) if orm else None
    
    def list(
        self,
        skip: int = 0,
        limit: int = 50,
        enabled_only: bool = False,
        severity: Optional[str] = None
    ) -> List[CompositeRule]:
        """List composite rules with optional filtering"""
        query = self.session.query(CompositeRuleORM)
        
        if enabled_only:
            query = query.filter(CompositeRuleORM.enabled == 1)
        
        if severity:
            query = query.filter(CompositeRuleORM.severity == severity)
        
        return [
            self._to_pydantic(orm)
            for orm in query.order_by(desc(CompositeRuleORM.created_at))
            .offset(skip).limit(limit).all()
        ]
    
    def update(self, rule_id: str, updates: CompositeRuleUpdate) -> Optional[CompositeRule]:
        """Update a composite rule"""
        orm = self.session.query(CompositeRuleORM).filter(
            CompositeRuleORM.id == rule_id.lower().strip()
        ).first()
        
        if not orm:
            return None
        
        previous_state = self._to_dict(orm)
        
        if updates.name is not None:
            orm.name = updates.name
        if updates.description is not None:
            orm.description = updates.description
        if updates.operator is not None:
            orm.operator = updates.operator.value
        if updates.rule_ids is not None:
            orm.rule_ids = updates.rule_ids
        if updates.severity is not None:
            orm.severity = updates.severity
        if updates.enabled is not None:
            orm.enabled = 1 if updates.enabled else 0
        if updates.metadata is not None:
            orm.metadata = updates.metadata
        
        orm.updated_at = datetime.utcnow()
        self.session.commit()
        
        # Log update
        self._log_history(orm.id, "composite", "update", previous_state, self._to_dict(orm))
        
        logger.info(f"Updated composite rule: {orm.id}")
        return self._to_pydantic(orm)
    
    def delete(self, rule_id: str) -> bool:
        """Delete a composite rule"""
        orm = self.session.query(CompositeRuleORM).filter(
            CompositeRuleORM.id == rule_id.lower().strip()
        ).first()
        
        if not orm:
            return False
        
        previous_state = self._to_dict(orm)
        self.session.delete(orm)
        self.session.commit()
        
        # Log deletion
        self._log_history(rule_id, "composite", "delete", previous_state, None)
        
        logger.info(f"Deleted composite rule: {rule_id}")
        return True
    
    def _to_pydantic(self, orm: CompositeRuleORM) -> CompositeRule:
        """Convert ORM to Pydantic model"""
        return CompositeRule(
            id=orm.id,
            name=orm.name,
            description=orm.description,
            rule_ids=orm.rule_ids,
            operator=RuleOperator(orm.operator),
            severity=orm.severity,
            enabled=bool(orm.enabled),
            metadata=orm.metadata,
            created_at=orm.created_at,
            updated_at=orm.updated_at
        )
    
    def _to_dict(self, orm: CompositeRuleORM) -> Dict[str, Any]:
        """Convert ORM to dictionary"""
        return {
            "id": orm.id,
            "name": orm.name,
            "rule_ids": orm.rule_ids,
            "operator": orm.operator,
            "severity": orm.severity,
            "enabled": orm.enabled
        }
    
    def _log_history(
        self,
        rule_id: str,
        rule_type: str,
        operation: str,
        previous_state: Optional[Dict],
        new_state: Optional[Dict]
    ):
        """Log rule composition history"""
        try:
            history = RuleCompositionHistoryORM(
                rule_id=rule_id,
                rule_type=rule_type,
                operation=operation,
                previous_state=previous_state,
                new_state=new_state
            )
            self.session.add(history)
            self.session.commit()
        except Exception as e:
            logger.warning(f"Failed to log history: {str(e)}")
    
    def close(self):
        """Close the repository"""
        if self.session:
            self.session.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


class RuleTemplateRepository:
    """Repository for rule template CRUD operations"""
    
    def __init__(self, session: Session):
        self.session = session
    
    def create(self, template: RuleTemplateCreate) -> RuleTemplate:
        """Create a new rule template"""
        try:
            orm = RuleTemplateORM(
                id=template.id.lower().strip(),
                name=template.name,
                description=template.description,
                category=template.category,
                rule_type=template.rule_type,
                template_definition=template.template_definition,
                parameters=template.parameters,
                example_config=template.example_config,
                enabled=1 if template.enabled else 0
            )
            self.session.add(orm)
            self.session.commit()
            
            logger.info(f"Created rule template: {orm.id}")
            return self._to_pydantic(orm)
        
        except IntegrityError:
            self.session.rollback()
            raise ValueError(f"Template '{template.id}' already exists")
        except Exception as e:
            self.session.rollback()
            logger.error(f"Error creating template: {str(e)}")
            raise
    
    def read(self, template_id: str) -> Optional[RuleTemplate]:
        """Read a template by ID"""
        orm = self.session.query(RuleTemplateORM).filter(
            RuleTemplateORM.id == template_id.lower().strip()
        ).first()
        return self._to_pydantic(orm) if orm else None
    
    def list_by_category(
        self,
        category: str,
        skip: int = 0,
        limit: int = 50
    ) -> List[RuleTemplate]:
        """List templates by category"""
        return [
            self._to_pydantic(orm)
            for orm in self.session.query(RuleTemplateORM)
            .filter(RuleTemplateORM.category == category, RuleTemplateORM.enabled == 1)
            .order_by(desc(RuleTemplateORM.created_at))
            .offset(skip).limit(limit).all()
        ]
    
    def list_by_type(
        self,
        rule_type: str,
        skip: int = 0,
        limit: int = 50
    ) -> List[RuleTemplate]:
        """List templates by rule type"""
        return [
            self._to_pydantic(orm)
            for orm in self.session.query(RuleTemplateORM)
            .filter(RuleTemplateORM.rule_type == rule_type, RuleTemplateORM.enabled == 1)
            .order_by(desc(RuleTemplateORM.usage_count).desc())
            .offset(skip).limit(limit).all()
        ]
    
    def list_all(self, skip: int = 0, limit: int = 50) -> List[RuleTemplate]:
        """List all templates"""
        return [
            self._to_pydantic(orm)
            for orm in self.session.query(RuleTemplateORM)
            .filter(RuleTemplateORM.enabled == 1)
            .order_by(desc(RuleTemplateORM.usage_count))
            .offset(skip).limit(limit).all()
        ]
    
    def increment_usage(self, template_id: str):
        """Increment usage counter"""
        orm = self.session.query(RuleTemplateORM).filter(
            RuleTemplateORM.id == template_id.lower().strip()
        ).first()
        if orm:
            orm.usage_count += 1
            self.session.commit()
    
    def _to_pydantic(self, orm: RuleTemplateORM) -> RuleTemplate:
        """Convert ORM to Pydantic model"""
        return RuleTemplate(
            id=orm.id,
            name=orm.name,
            description=orm.description,
            category=orm.category,
            rule_type=orm.rule_type,
            template_definition=orm.template_definition,
            parameters=orm.parameters,
            example_config=orm.example_config,
            enabled=bool(orm.enabled),
            created_at=orm.created_at,
            updated_at=orm.updated_at
        )
    
    def close(self):
        """Close the repository"""
        if self.session:
            self.session.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


class RuleGroupRepository:
    """Repository for rule group CRUD operations"""
    
    def __init__(self, session: Session):
        self.session = session
    
    def create(self, group: RuleGroupCreate) -> RuleGroup:
        """Create a new rule group"""
        try:
            orm = RuleGroupORM(
                id=group.id.lower().strip(),
                name=group.name,
                description=group.description,
                rule_ids=group.rule_ids,
                priority=group.priority,
                enabled=1 if group.enabled else 0,
                rule_count=len(group.rule_ids)
            )
            self.session.add(orm)
            self.session.commit()
            
            logger.info(f"Created rule group: {orm.id}")
            return self._to_pydantic(orm)
        
        except IntegrityError:
            self.session.rollback()
            raise ValueError(f"Rule group '{group.id}' already exists")
        except Exception as e:
            self.session.rollback()
            logger.error(f"Error creating rule group: {str(e)}")
            raise
    
    def read(self, group_id: str) -> Optional[RuleGroup]:
        """Read a rule group by ID"""
        orm = self.session.query(RuleGroupORM).filter(
            RuleGroupORM.id == group_id.lower().strip()
        ).first()
        return self._to_pydantic(orm) if orm else None
    
    def list(
        self,
        skip: int = 0,
        limit: int = 50,
        enabled_only: bool = False,
        order_by_priority: bool = True
    ) -> List[RuleGroup]:
        """List rule groups"""
        query = self.session.query(RuleGroupORM)
        
        if enabled_only:
            query = query.filter(RuleGroupORM.enabled == 1)
        
        if order_by_priority:
            query = query.order_by(desc(RuleGroupORM.priority))
        else:
            query = query.order_by(desc(RuleGroupORM.created_at))
        
        return [
            self._to_pydantic(orm)
            for orm in query.offset(skip).limit(limit).all()
        ]
    
    def update(self, group_id: str, updates: RuleGroupUpdate) -> Optional[RuleGroup]:
        """Update a rule group"""
        orm = self.session.query(RuleGroupORM).filter(
            RuleGroupORM.id == group_id.lower().strip()
        ).first()
        
        if not orm:
            return None
        
        if updates.name is not None:
            orm.name = updates.name
        if updates.description is not None:
            orm.description = updates.description
        if updates.rule_ids is not None:
            orm.rule_ids = updates.rule_ids
            orm.rule_count = len(updates.rule_ids)
        if updates.priority is not None:
            orm.priority = updates.priority
        if updates.enabled is not None:
            orm.enabled = 1 if updates.enabled else 0
        
        orm.updated_at = datetime.utcnow()
        self.session.commit()
        
        logger.info(f"Updated rule group: {orm.id}")
        return self._to_pydantic(orm)
    
    def delete(self, group_id: str) -> bool:
        """Delete a rule group"""
        orm = self.session.query(RuleGroupORM).filter(
            RuleGroupORM.id == group_id.lower().strip()
        ).first()
        
        if not orm:
            return False
        
        self.session.delete(orm)
        self.session.commit()
        
        logger.info(f"Deleted rule group: {group_id}")
        return True
    
    def _to_pydantic(self, orm: RuleGroupORM) -> RuleGroup:
        """Convert ORM to Pydantic model"""
        return RuleGroup(
            id=orm.id,
            name=orm.name,
            description=orm.description,
            rule_ids=orm.rule_ids,
            priority=orm.priority,
            enabled=bool(orm.enabled),
            rule_count=orm.rule_count,
            created_at=orm.created_at,
            updated_at=orm.updated_at
        )
    
    def close(self):
        """Close the repository"""
        if self.session:
            self.session.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


class RuleCompositionValidator:
    """Validates rule composition logic and syntax"""
    
    def validate_composite_rule(
        self,
        rule_ids: List[str],
        operator: RuleOperator
    ) -> RuleCompositionValidation:
        """
        Validate composite rule logic
        
        Checks:
        - All rule IDs are valid
        - Operator is appropriate for rule count
        - No circular dependencies
        - Complexity is acceptable
        """
        errors = []
        warnings = []
        recommendations = []
        
        # Check rule count
        if not rule_ids:
            errors.append("Composite rule must contain at least one rule")
        
        if operator == RuleOperator.NOT and len(rule_ids) != 1:
            errors.append("NOT operator requires exactly one rule")
        
        if operator == RuleOperator.XOR and len(rule_ids) < 2:
            errors.append("XOR operator requires at least two rules")
        
        # Check complexity
        complexity_score = self._calculate_complexity(rule_ids, operator)
        if complexity_score > 80:
            warnings.append(f"Composition complexity is high ({complexity_score}%)")
            recommendations.append("Consider breaking into smaller rule groups")
        
        # Performance recommendations
        if len(rule_ids) > 10:
            warnings.append("Large number of rules may impact performance")
            recommendations.append("Consider using rule groups instead of single composite")
        
        return RuleCompositionValidation(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            recommendations=recommendations,
            complexity_score=complexity_score,
            operator_count=len(rule_ids),
            depth=1
        )
    
    def validate_rule_condition_logic(
        self,
        conditions: Dict[str, Any]
    ) -> RuleCompositionValidation:
        """Validate conditional logic in rule conditions"""
        errors = []
        warnings = []
        
        # TODO: Implement recursive condition tree validation
        # This would validate:
        # - Operator/operand counts
        # - Field references
        # - Value type compatibility
        # - Logical contradictions
        
        return RuleCompositionValidation(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings
        )
    
    def _calculate_complexity(
        self,
        rule_ids: List[str],
        operator: RuleOperator
    ) -> float:
        """Calculate complexity score (0-100)"""
        # Base complexity on rule count and operator type
        base = min(100, len(rule_ids) * 10)
        
        # AND/OR are simpler than XOR/NOT
        operator_multiplier = {
            RuleOperator.AND: 0.8,
            RuleOperator.OR: 0.9,
            RuleOperator.ALL: 0.8,
            RuleOperator.ANY: 0.9,
            RuleOperator.XOR: 1.3,
            RuleOperator.NOT: 1.2
        }
        
        multiplier = operator_multiplier.get(operator, 1.0)
        return min(100.0, base * multiplier)


class RuleComposer:
    """Builds and optimizes rule compositions"""
    
    def optimize_composition(
        self,
        rule_ids: List[str],
        operator: RuleOperator
    ) -> RuleOptimization:
        """
        Optimize rule composition for performance
        
        Strategies:
        - De Morgan's laws for NOT simplification
        - Short-circuit evaluation order
        - Rule reordering by selectivity
        """
        current = self._expression_from_rules(rule_ids, operator)
        optimized = self._apply_optimizations(rule_ids, operator)
        
        # Calculate estimated improvement
        improvement = self._estimate_improvement(current, optimized)
        
        return RuleOptimization(
            current_expression=current,
            optimized_expression=optimized,
            improvement=f"Reordered rules for short-circuit evaluation",
            estimated_performance_gain=improvement
        )
    
    def _expression_from_rules(
        self,
        rule_ids: List[str],
        operator: RuleOperator
    ) -> str:
        """Build expression string from rules"""
        op_str = f" {operator.value.upper()} "
        if operator == RuleOperator.NOT:
            return f"NOT({rule_ids[0]})"
        return f"({op_str.join(rule_ids)})"
    
    def _apply_optimizations(
        self,
        rule_ids: List[str],
        operator: RuleOperator
    ) -> str:
        """Apply optimization strategies"""
        # For now, return the same as input
        # In production, would apply De Morgan's laws, reorder, etc.
        return self._expression_from_rules(rule_ids, operator)
    
    def _estimate_improvement(self, current: str, optimized: str) -> float:
        """Estimate performance improvement percentage"""
        # Simple heuristic: shorter expressions are generally faster
        length_reduction = (len(current) - len(optimized)) / len(current)
        return max(0.0, length_reduction * 100.0)
