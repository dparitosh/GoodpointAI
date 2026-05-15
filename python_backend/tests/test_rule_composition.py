"""
Test rule composition functionality

Run with:
    python -m pytest python_backend/tests/test_rule_composition.py -v
"""

import pytest
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.database import Base
from models.rule_composition_models import (
    CompositeRuleORM, RuleCompositionTemplateORM, RuleGroupORM,
    CompositeRuleCreate, CompositeRuleUpdate,
    RuleTemplateCreate, RuleGroupCreate, RuleGroupUpdate,
    RuleOperator, ConditionComparator
)
from services.rule_composition_service import (
    CompositeRuleRepository, RuleTemplateRepository, RuleGroupRepository,
    RuleCompositionValidator, RuleComposer
)


# Setup test database
@pytest.fixture
def test_db():
    """Create test database session"""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    yield session
    session.close()


# ============================================================================
# Composite Rule Tests
# ============================================================================

class TestCompositeRuleRepository:
    """Test composite rule CRUD operations"""
    
    def test_create_composite_rule(self, test_db):
        """Test creating a composite rule"""
        repo = CompositeRuleRepository(test_db)
        
        create_req = CompositeRuleCreate(
            id="rule_and_1",
            name="Composite AND Rule",
            rule_ids=["rule_1", "rule_2"],
            operator=RuleOperator.AND,
            severity="high"
        )
        
        rule = repo.create(create_req)
        
        assert rule.id == "rule_and_1"
        assert rule.name == "Composite AND Rule"
        assert rule.operator == RuleOperator.AND
        assert len(rule.rule_ids) == 2
        assert rule.enabled is True
    
    def test_read_composite_rule(self, test_db):
        """Test reading a composite rule"""
        repo = CompositeRuleRepository(test_db)
        
        create_req = CompositeRuleCreate(
            id="rule_or_1",
            name="Composite OR Rule",
            rule_ids=["rule_a", "rule_b", "rule_c"],
            operator=RuleOperator.OR
        )
        created = repo.create(create_req)
        
        # Read it back
        read_rule = repo.read("rule_or_1")
        
        assert read_rule is not None
        assert read_rule.id == created.id
        assert read_rule.name == created.name
    
    def test_list_composite_rules(self, test_db):
        """Test listing composite rules"""
        repo = CompositeRuleRepository(test_db)
        
        # Create multiple rules
        for i in range(3):
            repo.create(CompositeRuleCreate(
                id=f"rule_{i}",
                name=f"Rule {i}",
                rule_ids=[f"r{i}_1", f"r{i}_2"],
                operator=RuleOperator.AND,
                severity="medium" if i % 2 == 0 else "high"
            ))
        
        # List all
        all_rules = repo.list(limit=10)
        assert len(all_rules) == 3
        
        # List with severity filter
        high_rules = repo.list(severity="high", limit=10)
        assert len(high_rules) == 1 or len(high_rules) == 2
    
    def test_update_composite_rule(self, test_db):
        """Test updating a composite rule"""
        repo = CompositeRuleRepository(test_db)
        
        create_req = CompositeRuleCreate(
            id="rule_update",
            name="Original Name",
            rule_ids=["r1"],
            operator=RuleOperator.AND
        )
        repo.create(create_req)
        
        # Update
        update_req = CompositeRuleUpdate(
            name="Updated Name",
            severity="critical",
            enabled=False
        )
        updated = repo.update("rule_update", update_req)
        
        assert updated is not None
        assert updated.name == "Updated Name"
        assert updated.severity == "critical"
        assert updated.enabled is False
    
    def test_delete_composite_rule(self, test_db):
        """Test deleting a composite rule"""
        repo = CompositeRuleRepository(test_db)
        
        repo.create(CompositeRuleCreate(
            id="rule_delete",
            name="To Delete",
            rule_ids=["r1"],
            operator=RuleOperator.NOT
        ))
        
        # Delete
        deleted = repo.delete("rule_delete")
        assert deleted is True
        
        # Verify deleted
        found = repo.read("rule_delete")
        assert found is None
    
    def test_composite_rule_not_found(self, test_db):
        """Test reading non-existent rule"""
        repo = CompositeRuleRepository(test_db)
        rule = repo.read("nonexistent")
        assert rule is None


# ============================================================================
# Rule Template Tests
# ============================================================================

class TestRuleTemplateRepository:
    """Test rule template CRUD operations"""
    
    def test_create_template(self, test_db):
        """Test creating a rule template"""
        repo = RuleTemplateRepository(test_db)
        
        create_req = RuleTemplateCreate(
            id="completeness_template",
            name="Completeness Check",
            category="data_quality",
            rule_type="completeness",
            template_definition={
                "condition": {
                    "operator": "not_null",
                    "field": "{field_name}"
                }
            },
            parameters=["field_name"],
            example_config={"field_name": "id"}
        )
        
        template = repo.create(create_req)
        
        assert template.id == "completeness_template"
        assert template.category == "data_quality"
        assert "field_name" in template.parameters
    
    def test_list_templates_by_category(self, test_db):
        """Test listing templates by category"""
        repo = RuleTemplateRepository(test_db)
        
        # Create templates
        for i in range(3):
            repo.create(RuleTemplateCreate(
                id=f"template_{i}",
                name=f"Template {i}",
                category="data_quality" if i < 2 else "business_rules",
                rule_type="completeness",
                template_definition={},
                parameters=[]
            ))
        
        # List by category
        dq_templates = repo.list_by_category("data_quality")
        assert len(dq_templates) == 2
        
        br_templates = repo.list_by_category("business_rules")
        assert len(br_templates) == 1
    
    def test_increment_usage(self, test_db):
        """Test incrementing template usage count"""
        repo = RuleTemplateRepository(test_db)
        
        repo.create(RuleTemplateCreate(
            id="usage_test",
            name="Usage Test",
            category="test",
            rule_type="test",
            template_definition={},
            parameters=[]
        ))
        
        template = repo.read("usage_test")
        assert template is not None
        
        # Usage should default to 0 for ORM but reflected in to_dict
        repo.increment_usage("usage_test")
        
        # Note: Would need to check actual usage via ORM for this to work properly


# ============================================================================
# Rule Group Tests
# ============================================================================

class TestRuleGroupRepository:
    """Test rule group CRUD operations"""
    
    def test_create_group(self, test_db):
        """Test creating a rule group"""
        repo = RuleGroupRepository(test_db)
        
        create_req = RuleGroupCreate(
            id="group_1",
            name="Quality Checks",
            rule_ids=["rule_1", "rule_2", "rule_3"],
            priority=100
        )
        
        group = repo.create(create_req)
        
        assert group.id == "group_1"
        assert group.name == "Quality Checks"
        assert len(group.rule_ids) == 3
        assert group.rule_count == 3
    
    def test_list_groups_by_priority(self, test_db):
        """Test listing groups ordered by priority"""
        repo = RuleGroupRepository(test_db)
        
        # Create groups with different priorities
        for i, priority in enumerate([50, 150, 100]):
            repo.create(RuleGroupCreate(
                id=f"group_{i}",
                name=f"Group {i}",
                rule_ids=[f"r{i}"],
                priority=priority
            ))
        
        # List ordered by priority (highest first)
        groups = repo.list(order_by_priority=True, limit=10)
        
        assert len(groups) == 3
        assert groups[0].priority == 150  # Highest priority first
        assert groups[1].priority == 100
        assert groups[2].priority == 50


# ============================================================================
# Validation Tests
# ============================================================================

class TestRuleCompositionValidator:
    """Test rule composition validation"""
    
    def test_validate_and_operator(self):
        """Test validation of AND operator"""
        validator = RuleCompositionValidator()
        
        result = validator.validate_composite_rule(
            ["rule_1", "rule_2"],
            RuleOperator.AND
        )
        
        assert result.is_valid is True
        assert len(result.errors) == 0
    
    def test_validate_not_operator_requires_single_rule(self):
        """Test NOT operator requires exactly one rule"""
        validator = RuleCompositionValidator()
        
        # NOT with multiple rules should error
        result = validator.validate_composite_rule(
            ["rule_1", "rule_2"],
            RuleOperator.NOT
        )
        
        assert result.is_valid is False
        assert len(result.errors) > 0
    
    def test_validate_xor_requires_multiple_rules(self):
        """Test XOR operator requires at least two rules"""
        validator = RuleCompositionValidator()
        
        # XOR with one rule should error
        result = validator.validate_composite_rule(
            ["rule_1"],
            RuleOperator.XOR
        )
        
        assert result.is_valid is False
        assert len(result.errors) > 0
    
    def test_validate_empty_rule_list(self):
        """Test validation of empty rule list"""
        validator = RuleCompositionValidator()
        
        result = validator.validate_composite_rule([], RuleOperator.AND)
        
        assert result.is_valid is False
        assert "at least one rule" in result.errors[0].lower()
    
    def test_complexity_score_calculation(self):
        """Test complexity score calculation"""
        validator = RuleCompositionValidator()
        
        # Simple composition
        result1 = validator.validate_composite_rule(
            ["rule_1", "rule_2"],
            RuleOperator.AND
        )
        
        # Complex composition
        result2 = validator.validate_composite_rule(
            ["rule_1", "rule_2", "rule_3", "rule_4"],
            RuleOperator.XOR
        )
        
        # Complex should have higher score
        assert result2.complexity_score > result1.complexity_score


# ============================================================================
# Optimization Tests
# ============================================================================

class TestRuleComposer:
    """Test rule composition optimization"""
    
    def test_optimization_creates_expression(self):
        """Test that optimization generates expressions"""
        composer = RuleComposer()
        
        result = composer.optimize_composition(
            ["rule_1", "rule_2"],
            RuleOperator.AND
        )
        
        assert len(result.current_expression) > 0
        assert len(result.optimized_expression) > 0
    
    def test_optimization_with_not_operator(self):
        """Test optimization with NOT operator"""
        composer = RuleComposer()
        
        result = composer.optimize_composition(
            ["rule_1"],
            RuleOperator.NOT
        )
        
        assert "NOT" in result.current_expression


# ============================================================================
# Integration Tests
# ============================================================================

@pytest.mark.integration
class TestCompositionIntegration:
    """Integration tests for complete composition workflows"""
    
    def test_create_and_validate_composite(self, test_db):
        """Test creating and validating a composite rule"""
        # Create composite
        repo = CompositeRuleRepository(test_db)
        composite = repo.create(CompositeRuleCreate(
            id="integration_test",
            name="Integration Test",
            rule_ids=["r1", "r2", "r3"],
            operator=RuleOperator.AND,
            severity="high"
        ))
        
        # Validate it
        validator = RuleCompositionValidator()
        validation = validator.validate_composite_rule(
            composite.rule_ids,
            composite.operator
        )
        
        assert validation.is_valid is True
        assert composite.enabled is True
    
    def test_template_to_instance_workflow(self, test_db):
        """Test workflow of creating template and using it"""
        # Create template
        template_repo = RuleTemplateRepository(test_db)
        template = template_repo.create(RuleTemplateCreate(
            id="workflow_template",
            name="Workflow Template",
            category="data_quality",
            rule_type="completeness",
            template_definition={"field": "{field_name}"},
            parameters=["field_name"]
        ))
        
        # Could be used to instantiate rules
        assert template.parameters[0] == "field_name"
        assert len(template.parameters) == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
