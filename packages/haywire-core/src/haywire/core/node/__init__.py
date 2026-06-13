# haywire/core/node/__init__.py
"""
Node system for Haywire.
"""

from .identity import NodeIdentity
from .info import NodeInfo
from .data import NodeData
from .base import BaseNode
from .behavior import NodeType, NodeBehaviorFlags, BEHAVIOR_FIELDS
from .decorator import node
from .user_data import NodeCache, NodeStore
from .properties import NodeProperties
from .node_wrapper import NodeWrapperState, NodeWrapper
from .registry import NodeRegistry
from .factory import NodeFactory

__all__ = [
    # Identity
    "NodeIdentity",
    "NodeInfo",
    # Base classes
    "NodeData",
    "BaseNode",
    # Behavior
    "NodeType",
    "NodeBehaviorFlags",
    "BEHAVIOR_FIELDS",
    # Decorator
    "node",
    # User data containers
    "NodeCache",
    "NodeStore",
    # Instance props (position, visual state, etc.)
    "NodeProperties",
    # Node wrapper & lifecycle
    "NodeWrapperState",
    "NodeWrapper",
    # Registry & factory
    "NodeRegistry",
    "NodeFactory",
]
