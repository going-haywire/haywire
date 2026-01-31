"""
Tests for the @node decorator, including inheritance behavior.
"""

import pytest
from haywire.core.node.decorator import node
from haywire.core.node.base import BaseNode


def test_basic_node_decorator():
    """Test that @node decorator sets basic attributes."""
    
    @node(
        label="Test Node",
        description="A test node",
        menu="test/basic",
        is_data_node=True,
        is_thread_safe=True
    )
    class TestNode(BaseNode):
        pass
    
    assert TestNode.class_identity.label == "Test Node"
    assert TestNode.class_identity.description == "A test node"
    assert TestNode.class_identity.menu == "test/basic"
    assert TestNode.class_behavior.is_data_node is True
    assert TestNode.class_behavior.is_thread_safe is True
    assert TestNode.class_behavior.is_control_node is False


def test_node_decorator_inheritance_no_override():
    """Test that child inherits parent's attributes when not overridden."""
    
    @node(
        label="Parent Node",
        description="Parent description",
        menu="test/parent",
        search_tags=["parent", "test"],
        is_control_node=True,
        is_pure=False,
        is_stateful=True
    )
    class ParentNode(BaseNode):
        pass
    
    # Child with no overrides - should inherit everything
    @node()
    class ChildNode(ParentNode):
        pass
    
    # Check identity inheritance
    assert ChildNode.class_identity.label == "Parent Node"
    assert ChildNode.class_identity.description == "Parent description"
    assert ChildNode.class_identity.menu == "test/parent"
    assert ChildNode.class_identity.search_tags == ["parent", "test"]
    
    # Check behavior inheritance
    assert ChildNode.class_behavior.is_control_node is True
    assert ChildNode.class_behavior.is_loopback is False
    assert ChildNode.class_behavior.is_stateful is True


def test_node_decorator_inheritance_with_override():
    """Test that child can override parent's attributes."""
    
    @node(
        label="Parent Node",
        description="Parent description",
        menu="test/parent",
        search_tags=["parent"],
        is_control_node=True,
        is_thread_safe=False,
        is_stateful=True
    )
    class ParentNode(BaseNode):
        pass
    
    # Child overrides some attributes
    @node(
        label="Child Node",
        menu="test/child",
        is_thread_safe=True  # Override behavior
    )
    class ChildNode(ParentNode):
        pass
    
    # Check overridden identity
    assert ChildNode.class_identity.label == "Child Node"
    assert ChildNode.class_identity.menu == "test/child"
    
    # Check inherited identity (not overridden)
    assert ChildNode.class_identity.description == "Parent description"
    assert ChildNode.class_identity.search_tags == ["parent"]
    
    # Check overridden behavior
    assert ChildNode.class_behavior.is_thread_safe is True
    
    # Check inherited behavior (not overridden)
    assert ChildNode.class_behavior.is_control_node is True
    assert ChildNode.class_behavior.is_stateful is True


def test_node_decorator_registry_key_not_inherited():
    """Test that registry_key is regenerated for child, not inherited."""
    
    @node(registry_id="parent_id")
    class ParentNode(BaseNode):
        pass
    
    @node(registry_id="child_id")
    class ChildNode(ParentNode):
        pass
    
    # registry_key should be different (based on child's registry_id)
    assert ParentNode.class_identity.registry_key != ChildNode.class_identity.registry_key
    assert "parent_id" in ParentNode.class_identity.registry_key
    assert "child_id" in ChildNode.class_identity.registry_key


def test_node_decorator_multilevel_inheritance():
    """Test inheritance through multiple levels."""
    
    @node(
        label="Grandparent",
        menu="test/gp",
        is_control_node=True,
        is_thread_safe=True
    )
    class GrandparentNode(BaseNode):
        pass
    
    @node(
        label="Parent",
        is_stateful=True  # Add new behavior
    )
    class ParentNode(GrandparentNode):
        pass
    
    @node(
        label="Child"
    )
    class ChildNode(ParentNode):
        pass
    
    # Child should inherit from immediate parent (ParentNode)
    # ParentNode has inherited menu from GrandparentNode
    assert ChildNode.class_identity.menu == "test/gp"
    assert ChildNode.class_behavior.is_control_node is True
    assert ChildNode.class_behavior.is_stateful is True
    assert ChildNode.class_behavior.is_thread_safe is True


def test_node_decorator_defaults_when_no_parent():
    """Test that defaults are still applied when no parent exists."""
    
    @node()
    class TestNode(BaseNode):
        pass
    
    # Should use class name as default for registry_id and label
    assert TestNode.class_identity.registry_id == "TestNode"
    assert TestNode.class_identity.label == "TestNode"
    
    # Should have default behavior values
    assert TestNode.class_behavior.is_control_node is False
    assert TestNode.class_behavior.is_data_node is False
    assert TestNode.class_behavior.is_loopback is False


def test_node_decorator_partial_override():
    """Test mixing inherited and new attributes."""
    
    @node(
        label="Base",
        description="Base desc",
        menu="base/menu",
        search_tags=["base"],
        is_control_node=True
    )
    class BaseNode1(BaseNode):
        pass
    
    @node(
        label="Derived",  # Override
        search_tags=["derived", "extended"],  # Override
        is_data_node=True  # Add new behavior
    )
    class DerivedNode(BaseNode1):
        pass
    
    # Overridden
    assert DerivedNode.class_identity.label == "Derived"
    assert DerivedNode.class_identity.search_tags == ["derived", "extended"]
    
    # Inherited
    assert DerivedNode.class_identity.description == "Base desc"
    assert DerivedNode.class_identity.menu == "base/menu"
    
    # Combined behaviors
    assert DerivedNode.class_behavior.is_control_node is True  # Inherited
    assert DerivedNode.class_behavior.is_data_node is True  # Added


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
