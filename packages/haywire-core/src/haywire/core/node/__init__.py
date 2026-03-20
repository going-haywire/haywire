# haywire/core/node/__init__.py
"""
Node system for Haywire.
"""

from .identity import NodeIdentity
from .base import NodeMeta, NodeData, BaseNode
from .behavior import NodeType, NodeBehaviorFlags, BEHAVIOR_FIELDS
from .decorator import node
from .user_data import NodeCache, NodeStore
from .node_instance import NodeInstanceSettings
from .node_wrapper import NodeWrapperState, NodeMiddleware, NodeWrapper
from .registry import NodeRegistry
from .factory import NodeFactory
from .dataclasses import NodeErrorInfo, NodeBehavior, NodeUIConfig, NodeUserMetadata

__all__ = [
    # Identity
    "NodeIdentity",
    # Base classes
    "NodeMeta",
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
    "NodeInstanceSettings",
    # Node wrapper & lifecycle
    "NodeWrapperState",
    "NodeMiddleware",
    "NodeWrapper",
    # Registry & factory
    "NodeRegistry",
    "NodeFactory",
    # Dataclasses (legacy)
    "NodeErrorInfo",
    "NodeBehavior",
    "NodeUIConfig",
    "NodeUserMetadata",
]
