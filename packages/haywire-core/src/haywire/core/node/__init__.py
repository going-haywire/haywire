# haywire/core/node/__init__.py
"""
Node system for Haywire.
"""

from __future__ import annotations

from .base import BaseNode
from .behavior import BEHAVIOR_FIELDS, NodeBehaviorFlags, NodeType
from .data import NodeData
from .decorator import node
from .factory import NodeFactory
from .identity import NodeIdentity
from .info import NodeInfo
from .node_wrapper import NodeWrapper, NodeWrapperState
from .properties import NodeProperties
from .registry import NodeRegistry
from .user_data import NodeCache, NodeStore

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
