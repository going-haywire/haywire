# haywire/core/node/decorators.py
"""
Node decorator for registering node classes.
"""

from dataclasses import asdict
from typing import Any, Callable, Type, TypeVar, cast

from haywire.core.library.utils import NODE, derive_library_identity, reg_key
from haywire.core.node import BaseNode, NodeIdentity, NodeBehaviorFlags, BEHAVIOR_FIELDS

T = TypeVar("T")


def _wire_settings_schemas(node_cls: type[BaseNode]) -> None:
    """
    Scan the node class body for all ``Settings`` subclasses, assign ``_setting_key``
    to their ``setting`` descriptors, and store the result as ``cls._settings_bags``.

    The accessor name is the inner class name in the node class body.

    ``_setting_key`` format::

        '{settings_name}.{field_name}'
        e.g. 'filter.strength'

    Node bags are never registered with ``SettingsRegistry``, so this key is
    not a global address — it is only ever a per-node identifier (``_set_keys``,
    ``_cells``, ``_ui_state``, ``_promoted_keys``, and the id of a promoted
    port). The accessor already disambiguates fields of the same name across
    bags on one node, so the node's registry_key adds nothing. Prefixing it
    was also actively wrong: the descriptors of an INHERITED bag (every
    node's ``props``) are shared objects, so the first-decorated node's name
    got stamped onto every other node's fields.

    Re-stamped on every ``@node``, deliberately: a bag subclassed per node
    class must key off ITS accessor, and re-stamping an inherited descriptor
    with the same accessor is idempotent.

    Conflict check: raises ``ValueError`` at class-definition time if an
    accessor name shadows any existing non-Settings attribute on the node MRO,
    or shadows an inherited bag WITHOUT subclassing it. Redeclaring an
    inherited bag as a subclass is the supported way for a node to override a
    framework prop's default (e.g. ``RerouteNode`` pinning its own skin).
    """
    from haywire.core.settings import NodeSettings, setting

    bags: dict[str, type] = {}

    # Walk MRO base-first so subclass declarations win over inherited ones
    for klass in reversed(node_cls.__mro__):
        for name, val in klass.__dict__.items():
            if not (isinstance(val, type) and issubclass(val, NodeSettings) and val is not NodeSettings):
                continue
            # Stamp '<accessor>.<field>' on every setting descriptor. Unconditional
            # (not "only if unset"): the key depends solely on the accessor, so
            # re-stamping a shared inherited descriptor writes the same string.
            for field_name, descriptor in val._property_settings().items():
                if isinstance(descriptor, setting):
                    descriptor._setting_key = f"{name}.{field_name}"
            bags[name] = val

    # Conflict check — must not shadow existing attributes on the MRO
    for accessor_name in bags:
        for klass in node_cls.__mro__:
            if accessor_name not in klass.__dict__:
                continue
            existing = klass.__dict__[accessor_name]
            if not (isinstance(existing, type) and issubclass(existing, NodeSettings)):
                # Conflicts with a non-NodeSettings attribute (method, property, etc.)
                raise ValueError(
                    f"@node: Settings accessor '{accessor_name}' on {node_cls.__name__} "
                    f"conflicts with {klass.__name__}.{accessor_name} "
                    f"({type(existing).__name__}). Choose a different inner class name."
                )
            if klass is not node_cls and accessor_name in node_cls.__dict__:
                # The node redeclares an inherited bag. Legal ONLY as a subclass
                # of the inherited one: that EXTENDS the bag (inheriting every
                # field it does not redeclare), which is how a node overrides a
                # framework prop's default — see NodeProperties and RerouteNode.
                # An unrelated class of the same name would silently drop the
                # inherited fields, so it stays an error.
                own = node_cls.__dict__[accessor_name]
                if not (isinstance(own, type) and issubclass(own, existing)):
                    raise ValueError(
                        f"@node: '{accessor_name}' on {node_cls.__name__} shadows the inherited "
                        f"settings bag '{accessor_name}' defined on {klass.__name__} without "
                        f"subclassing it, which would drop its fields. Either subclass "
                        f"{klass.__name__}.{accessor_name} or choose a different inner class name."
                    )

    node_cls._settings_bags = bags


def node(**kwargs: Any) -> Callable[[Type[T]], Type[T]]:
    """
    Decorator to register a class as a Haywire node.

    Always invoked with parentheses — `@node(...)` or `@node()`. The bare
    `@node` form (no parens) is not supported.

    Accepts NodeIdentity fields and NodeBehaviorFlags fields as keyword arguments.
    Supports inheritance: child classes inherit parent's identity and behavior,
    with child decorator arguments overriding parent values.

    Identity Fields (metadata):
        label (str): Human-readable display name. Default: class name
        description (str): Detailed description. Default: ""
        search_tags (list[str]): Tags for searching/filtering. Default: []
        menu (str): Menu category path (e.g., 'math/arithmetic'). Default: 'misc/custom'
        help_md (str): Markdown help content. Default: None
        help_url (str): URL to documentation. Default: 'https://haywire.io/internals/node-help'
        registry_id (str): Unique identifier within library. Default set to class name
        deprecation_warning (str): Advisory message shown on the node card and in
            the add-node menu when this node is deprecated. Default: ""
        _is_error (bool): Whether this is an error handler node. Default: False
        _error_priority (int): Priority for error handling. Default: 0

    Behavior Fields (execution characteristics):
        node_type (NodeType): Primary node type classification. Default: NodeType(0)
            - NodeType.DATA: Pure data processing (0 ctrl inlet/outlet)
            - NodeType.CONTROL: Standard control flow (1 ctrl inlet/1 outlet)
            - NodeType.EVENT: Flow entry point (0 ctrl inlet/1 outlet)
            - NodeType.OUTPUT: Flow termination (1 ctrl inlet/0 outlet)
            - NodeType.LOOPBACK: Loop construct (1 ctrl inlet/2+ outlets with loopback)
            - NodeType.REROUTE: A DATA node tolerating a port-less latent state
              (edge-split reroute; typed ports added after creation)
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
        parent_identity: NodeIdentity | None = None
        parent_behavior: NodeBehaviorFlags | None = None

        for base in inner_cls.__bases__:
            # base is a bare `type`; class_identity/class_behavior are framework
            # ClassVars whose attribute type a checker can't see through __bases__.
            if hasattr(base, "class_identity"):
                parent_identity = cast(NodeIdentity, base.class_identity)
            if hasattr(base, "class_behavior"):
                parent_behavior = cast(NodeBehaviorFlags, base.class_behavior)
            if parent_identity and parent_behavior:
                break

        # Split kwargs into identity and behavior. Freeform bags (mirrors the
        # NodeIdentity/NodeBehaviorFlags field sets); typed dict[str, Any] so the
        # **-splat into those dataclass constructors below isn't checked key-by-key
        # against a widened value union.
        behavior_kwargs: dict[str, Any] = {}
        identity_kwargs: dict[str, Any] = {}

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
        identity_kwargs["registry_key"] = reg_key(
            library_identity.name, NODE, identity_kwargs["registry_id"]
        )

        # Set source info from the class itself
        identity_kwargs["class_name"] = inner_cls.__name__
        identity_kwargs["module"] = inner_cls.__module__

        # Create and attach identity, behavior, and library
        inner_cls.class_identity = NodeIdentity(**identity_kwargs)
        inner_cls.class_behavior = NodeBehaviorFlags(**behavior_kwargs)
        inner_cls.class_library = library_identity

        # Wire Settings schemas; field keys are '<accessor>.<field>', scoped to
        # the node instance rather than to the registry_key.
        _wire_settings_schemas(inner_cls)

        return inner_cls

    return decorator
