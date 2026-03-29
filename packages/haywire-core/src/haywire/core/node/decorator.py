# haywire/core/node/decorators.py
"""
Node decorator for registering node classes.
"""

from dataclasses import asdict
from typing import Callable, Type, TypeVar, Union

from haywire.core.library.utils import derive_library_identity, reg_key
from haywire.core.node import BaseNode, NodeIdentity, NodeBehaviorFlags, BEHAVIOR_FIELDS

T = TypeVar("T")


def _wire_settings_schemas(node_cls: type, registry_key: str) -> None:
    """
    Scan the node class body for all ``Settings`` subclasses, assign ``_field_key``
    to their ``setting`` descriptors, and store the result as ``cls._settings_bags``.

    The accessor name is the inner class name in the node class body.

    ``_field_key`` format::

        '{registry_key_dotted}.{settings_name}.{field_name}'
        e.g. 'haybale_core.node.transform.filter.strength'

    Conflict check: raises ``ValueError`` at class-definition time if an
    accessor name shadows any existing non-Settings attribute on the node MRO.
    """
    from haywire.core.settings import NodeSettings, setting as setting_cls

    bags: dict[str, type] = {}
    ns = registry_key.replace(":", ".")

    # Walk MRO base-first so subclass declarations win over inherited ones
    for klass in reversed(node_cls.__mro__):
        for name, val in klass.__dict__.items():
            if not (isinstance(val, type) and issubclass(val, NodeSettings) and val is not NodeSettings):
                continue
            # Set _field_key on every setting descriptor that doesn't already have one
            for field_name, descriptor in val._prop_fields().items():
                if isinstance(descriptor, setting_cls) and not descriptor._field_key:
                    descriptor._field_key = f"{ns}.{name}.{field_name}"
            bags[name] = val

    # Conflict check — must not shadow existing non-NodeSettings attributes
    for accessor_name in bags:
        for klass in node_cls.__mro__:
            if accessor_name not in klass.__dict__:
                continue
            existing = klass.__dict__[accessor_name]
            if isinstance(existing, type) and issubclass(existing, NodeSettings):
                continue  # it IS the NodeSettings being wired — that's fine
            raise ValueError(
                f"@node: Settings accessor '{accessor_name}' on {node_cls.__name__} "
                f"conflicts with {klass.__name__}.{accessor_name} "
                f"({type(existing).__name__}). Choose a different inner class name."
            )

    node_cls._settings_bags = bags


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
        node_type (NodeType): Primary node type classification. Default: NodeType(0)
            - NodeType.DATA: Pure data processing (0 ctrl inlet/outlet)
            - NodeType.CONTROL: Standard control flow (1 ctrl inlet/1 outlet)
            - NodeType.EVENT: Flow entry point (0 ctrl inlet/1 outlet)
            - NodeType.OUTPUT: Flow termination (1 ctrl inlet/0 outlet)
            - NodeType.LOOPBACK: Loop construct (1 ctrl inlet/2+ outlets with loopback)
        is_stateful (bool): Maintains state between executions. Default: False
        has_execute_async (bool): Supports async execution. Default: False
        is_mutable (bool): Configuration can change at runtime. Default: False
        is_thread_safe (bool): Safe for multithreaded execution. Default: False

    Important: Nodes in modules that start with dev_*.py or end with *_dev.py are not
    automatically registered in the node registry. On a File change though they will
    be loaded and are available.
    This is useful for nodes under development that should not yet be part of the library.

    Examples:
        Basic data node:

        .. code-block:: python

            @node(node_type=NodeType.DATA)
            class AddNode(BaseNode):
                def init(self):
                    self.add(FLOAT.as_inlet('a'))
                    self.add(FLOAT.as_inlet('b'))
                    self.add(FLOAT.as_outlet('result'))

                def worker(self, context, a: float, b: float):
                    self.out('result', a + b)

        Control flow node:

        .. code-block:: python

            @node(
                label="Print",
                menu="control/debug",
                node_type=NodeType.CONTROL
            )
            class PrintNode(BaseNode):
                ...

        Event node:

        .. code-block:: python

            @node(
                label="On Start",
                menu="events",
                node_type=NodeType.EVENT
            )
            class BeginPlayNode(BaseNode):
                ...

        Loop node:

        .. code-block:: python

            @node(
                label="For Loop",
                menu="control/loops",
                node_type=NodeType.LOOPBACK
            )
            class ForLoopNode(BaseNode):
                ...

        Stateful node:

        .. code-block:: python

            @node(
                label="Counter",
                node_type=NodeType.DATA,
                is_stateful=True
            )
            class CounterNode(BaseNode):
                def init(self):
                    self.store.count = 0

                def worker(self, context):
                    self.store.count += 1
                    self.out('count', self.store.count)

        Inheritance example (child overrides parent):

        .. code-block:: python

            @node(
                label="Base Math",
                menu="math",
                node_type=NodeType.DATA
            )
            class BaseMathNode(BaseNode):
                ...

            # Inherits menu="math", node_type=NodeType.DATA
            # Overrides label
            @node(label="Advanced Math")
            class AdvancedMathNode(BaseMathNode):
                ...
    """

    def decorator(inner_cls: Type[T]) -> Type[T]:
        if not issubclass(inner_cls, BaseNode):
            raise TypeError(f"@node can only be applied to BaseNode subclasses, got {inner_cls}")

        # Check for parent class attributes to inherit
        parent_identity = None
        parent_behavior = None

        for base in inner_cls.__bases__:
            if hasattr(base, "class_identity"):
                parent_identity = base.class_identity
            if hasattr(base, "class_behavior"):
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
            parent_dict.pop("registry_key", None)
            # Merge: parent values first, then child overrides
            identity_kwargs = {**parent_dict, **identity_kwargs}

        if parent_behavior:
            # Start with parent's behavior values (as dict)
            parent_dict = asdict(parent_behavior)
            # Merge: parent values first, then child overrides
            behavior_kwargs = {**parent_dict, **behavior_kwargs}

        # Set defaults from class name if not provided (and no parent)
        identity_kwargs.setdefault("registry_id", inner_cls.__name__)
        identity_kwargs.setdefault("label", inner_cls.__name__)

        # Get library identity (survives hot-reload)
        library_identity = derive_library_identity(inner_cls)

        # Auto-derive registry_key
        library_id = library_identity.id if library_identity else None
        identity_kwargs["registry_key"] = reg_key(library_id, "node", identity_kwargs["registry_id"])

        # Create and attach identity, behavior, and library
        inner_cls.class_identity = NodeIdentity(**identity_kwargs)
        inner_cls.class_behavior = NodeBehaviorFlags(**behavior_kwargs)
        inner_cls.class_library = library_identity

        # Wire Settings schemas using registry_key as the single source of truth
        _wire_settings_schemas(inner_cls, identity_kwargs["registry_key"])

        return inner_cls

    return decorator if cls is None else decorator(cls)
