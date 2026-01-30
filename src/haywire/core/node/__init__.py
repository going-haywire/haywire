# haywire/core/node/__init__.py
"""
Node system for Haywire.
"""

from .base import BaseNode, NodeData, NodeIdentity
from .behavior import NodeBehaviorFlags, BEHAVIOR_FIELDS
from .user_data import NodeCache, NodeStore
from .ui_state import NodeUI, NodeUIState
from .decorator import node

__all__ = [
    # Base classes
    'BaseNode',
    'NodeData',
    'NodeIdentity',
    
    # Behavior
    'NodeBehaviorFlags',
    'BEHAVIOR_FIELDS',
    
    # Containers
    'NodeCache',
    'NodeStore',
    'NodeUI',
    'NodeUIState',
    
    # Decorator
    'node',
]