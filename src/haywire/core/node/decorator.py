# haywire/core/node/decorators.py
"""
Node decorator for registering node classes.
"""

from haywire.core.library.utils import derive_library_identity, reg_key
from haywire.core.node.base import BaseNode, NodeIdentity
from haywire.core.node.behavior import NodeBehaviorFlags, BEHAVIOR_FIELDS

from dataclasses import asdict
from typing import Callable, Type, TypeVar, Union

T = TypeVar('T')


def node(cls: Type[T] = None, /, **kwargs) -> Union[Type[T], Callable[[Type[T]], Type[T]]]:
    """
    Decorator to register a class as a Haywire node.
    
    Accepts NodeIdentity fields and NodeBehaviorFlags fields as keyword arguments.
    Supports inheritance: child classes inherit parent's identity and behavior,
    with child decorator arguments overriding parent values.
    
    Identity Fields (metadata):
        registry_id (str): Unique identifier within library. Default: class name
        label (str): Human-readable display name. Default: class name
        description (str): Detailed description. Default: ""
        search_tags (list[str]): Tags for searching/filtering. Default: []
        menu (str): Menu category path (e.g., 'math/arithmetic'). Default: 'misc/custom'
        help_md (str): Markdown help content. Default: None
        help_url (str): URL to documentation. Default: 'https://haywire.io/docs/node-help'
        _is_error (bool): Whether this is an error handler node. Default: False
        _error_priority (int): Priority for error handling. Default: 0
    
    Behavior Fields (execution characteristics):
        is_control_node (bool): Participates in control flow. Default: False
        is_data_node (bool): Processes data. Default: True
        is_event_node (bool): Entry point for flows. Default: False
        is_output_node (bool): Terminal output node. Default: False
        is_pure (bool): No side effects, cacheable. Default: True
        is_stateful (bool): Maintains state between executions. Default: False
        is_loopback (bool): Control flow can return here. Default: False
        has_execute_async (bool): Supports async execution. Default: False
        is_mutable (bool): Configuration can change at runtime. Default: False
    
    Examples:
        Basic data node:
        
        .. code-block:: python
        
            @node
            class AddNode(BaseNode):
                def initialize(self):
                    self.add(FLOAT.as_inlet('a'))
                    self.add(FLOAT.as_inlet('b'))
                    self.add(FLOAT.as_outlet('result'))
                
                def worker(self, context, a: float, b: float):
                    self.out('result', a + b)
        
        Control flow node:
        
        .. code-block:: python
        
            @node(
                label="For Loop",
                menu="control/loops",
                is_control_node=True,
                is_loopback=True,
                is_pure=False
            )
            class ForLoopNode(BaseNode):
                ...
        
        Event node:
        
        .. code-block:: python
        
            @node(
                label="On Start",
                menu="events",
                is_event_node=True,
                is_control_node=True,
                is_data_node=False
            )
            class OnStartNode(BaseNode):
                ...
        
        Stateful node:
        
        .. code-block:: python
        
            @node(
                label="Counter",
                is_stateful=True,
                is_pure=False
            )
            class CounterNode(BaseNode):
                def initialize(self):
                    self.store.count = 0
                
                def worker(self, context):
                    self.store.count += 1
                    self.out('count', self.store.count)
        
        Inheritance example (child overrides parent):
        
        .. code-block:: python
        
            @node(
                label="Base Math",
                menu="math",
                is_data_node=True,
                is_pure=True
            )
            class BaseMathNode(BaseNode):
                ...
            
            # Inherits menu="math", is_data_node=True, is_pure=True
            # Overrides label
            @node(label="Advanced Math")
            class AdvancedMathNode(BaseMathNode):
                ...  # Still in "math" menu, still pure data node
    """
    def decorator(inner_cls: Type[T]) -> Type[T]:
        if not issubclass(inner_cls, BaseNode):
            raise TypeError(f"@node can only be applied to BaseNode subclasses, got {inner_cls}")
        
        # Check for parent class attributes to inherit
        parent_identity = None
        parent_behavior = None
        
        for base in inner_cls.__bases__:
            if hasattr(base, 'class_identity'):
                parent_identity = base.class_identity
            if hasattr(base, 'class_behavior'):
                parent_behavior = base.class_behavior
            if parent_identity and parent_behavior:
                break
        
        # Split kwargs into identity and behavior
        behavior_kwargs = {}
        identity_kwargs = {}
        
        for key, value in kwargs.items():
            if key in BEHAVIOR_FIELDS:
                behavior_kwargs[key] = value
            else:
                identity_kwargs[key] = value
        
        # Inherit from parent, then override with kwargs
        if parent_identity:
            # Start with parent's identity values (as dict)
            parent_dict = asdict(parent_identity)
            # Remove registry_key as it will be auto-derived for child
            parent_dict.pop('registry_key', None)
            # Merge: parent values first, then child overrides
            identity_kwargs = {**parent_dict, **identity_kwargs}
        
        if parent_behavior:
            # Start with parent's behavior values (as dict)
            parent_dict = asdict(parent_behavior)
            # Merge: parent values first, then child overrides
            behavior_kwargs = {**parent_dict, **behavior_kwargs}
        
        # Set defaults from class name if not provided (and no parent)
        identity_kwargs.setdefault('registry_id', inner_cls.__name__)
        identity_kwargs.setdefault('label', inner_cls.__name__)

        # Get library identity (survives hot-reload)
        library_identity = derive_library_identity(inner_cls)

        # Auto-derive registry_key
        library_id = library_identity.id if library_identity else None
        identity_kwargs['registry_key'] = reg_key(library_id, 'node', identity_kwargs['registry_id'])

        # Create and attach identity, behavior, and library
        inner_cls.class_identity = NodeIdentity(**identity_kwargs)
        inner_cls.class_behavior = NodeBehaviorFlags(**behavior_kwargs)
        inner_cls.class_library = library_identity
        
        return inner_cls

    return decorator if cls is None else decorator(cls)